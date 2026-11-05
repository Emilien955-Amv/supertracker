"""Catalogue de cartes : alimenté chaque jour avec les contenus populaires.

Grâce à lui, on peut obtenir les cartes de contenus qu'on n'a jamais vus
(ex. ouvrir un booster « Animes » et tomber sur Demon Slayer).

La tâche tourne en arrière-plan dans l'API : au démarrage, puis toutes les
24 heures. Un verrou Redis garantit qu'une seule copie de l'API la lance à la
fois (utile en production, quand plusieurs copies tourneront en parallèle).
"""

import asyncio
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import redis_client
from app.db import SessionLocal
from app.http_client import get_http_client
from app.models import Content
from app.providers.base import ContentKind, MetadataProvider, ProviderError, Source
from app.providers.registry import get_providers
from app.services.cards import CARDS_REFRESH, ensure_cards

log = structlog.get_logger()

LOCK_KEY = "lock:card_catalog"
LOCK_SECONDS = 3600
REFRESH_SECONDS = 24 * 3600
RETRY_SECONDS = 10 * 60
# Pause entre deux contenus, pour respecter les limites des API gratuites
# (AniList : 90 appels par minute au maximum, parfois moins).
PAUSE_SECONDS = {Source.TMDB: 0.3, Source.ANILIST: 2.0}
# Date très ancienne : la fiche complète sera chargée au premier suivi.
NEVER = datetime(2000, 1, 1, tzinfo=UTC)


async def seed_catalog(
    session: AsyncSession, http: httpx.AsyncClient, providers: list[MetadataProvider]
) -> int:
    """Ajoute les contenus populaires et crée leurs cartes. Renvoie le nombre
    de contenus traités."""
    done = 0
    for provider in providers:
        for kind in ContentKind:
            try:
                items = await provider.get_popular(http, kind)
            except ProviderError:
                log.warning("catalogue.source_indisponible", source=provider.source, kind=kind)
                continue
            for item in items:
                # ON CONFLICT DO NOTHING : un contenu déjà connu garde sa fiche
                # complète (on ne l'écrase pas avec ce résumé).
                await session.execute(
                    insert(Content)
                    .values(
                        source=item.source,
                        kind=item.kind,
                        external_id=item.external_id,
                        title=item.title[:300],
                        original_title=(item.original_title or "")[:300] or None,
                        year=item.year,
                        poster_url=item.poster_url,
                        backdrop_url=item.backdrop_url,
                        refreshed_at=NEVER,
                    )
                    .on_conflict_do_nothing(index_elements=["source", "kind", "external_id"])
                )
                content = await session.scalar(
                    select(Content).where(
                        Content.source == item.source,
                        Content.kind == item.kind,
                        Content.external_id == item.external_id,
                    )
                )
                await session.commit()
                if content is None:
                    continue
                fresh = content.cards_generated_at is not None and (
                    content.cards_generated_at > datetime.now(UTC) - CARDS_REFRESH
                )
                if not fresh:
                    try:
                        await ensure_cards(session, http, providers, content)
                    except ProviderError:
                        log.warning("catalogue.cartes_impossibles", content_id=content.id)
                    await asyncio.sleep(PAUSE_SECONDS.get(Source(content.source), 1.0))
                done += 1
    log.info("catalogue.termine", contenus=done)
    return done


async def run_forever() -> None:
    """Boucle d'arrière-plan lancée au démarrage de l'API."""
    while True:
        delay = REFRESH_SECONDS
        try:
            # SET NX : ne réussit que si personne ne tient déjà le verrou.
            if await redis_client.set(LOCK_KEY, "1", nx=True, ex=LOCK_SECONDS):
                try:
                    async with SessionLocal() as session:
                        await seed_catalog(session, get_http_client(), get_providers())
                finally:
                    # Libéré même si l'API s'arrête en plein travail.
                    await redis_client.delete(LOCK_KEY)
            else:
                delay = RETRY_SECONDS  # une autre copie travaille : on repassera
        except asyncio.CancelledError:
            raise
        except Exception:
            # Ne jamais faire tomber l'API pour le catalogue : on réessaiera.
            log.exception("catalogue.erreur")
            delay = RETRY_SECONDS
        await asyncio.sleep(delay)


async def _run_once() -> None:
    async with SessionLocal() as session:
        await seed_catalog(session, get_http_client(), get_providers())


if __name__ == "__main__":
    # Lancement à la main : docker compose exec api python -m app.services.card_catalog
    asyncio.run(_run_once())
