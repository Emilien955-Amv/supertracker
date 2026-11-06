"""Catalogue de cartes : alimenté chaque jour avec les contenus populaires.

Grâce à lui, on peut obtenir les cartes de contenus qu'on n'a jamais vus
(ex. ouvrir un booster « Animes » et tomber sur Demon Slayer).

La tâche tourne en arrière-plan dans l'API : au démarrage, puis toutes les
24 heures. Un verrou Redis garantit qu'une seule copie de l'API la lance à la
fois (utile en production, quand plusieurs copies tourneront en parallèle).
"""

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import httpx
import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import redis_client
from app.db import SessionLocal
from app.http_client import get_http_client
from app.models import Content, ContentPlatform
from app.providers.base import (
    ContentDetail,
    ContentKind,
    MetadataProvider,
    ProviderError,
    Source,
)
from app.providers.registry import get_providers
from app.services.cards import (
    ANILIST_SITES,
    ANIME_PLATFORM_IDS,
    CARDS_REFRESH,
    PLATFORM_IDS,
    PackTheme,
    ensure_cards,
)

log = structlog.get_logger()


@runtime_checkable
class PlatformCatalog(Protocol):
    """Source capable de lister les titres d'une plateforme (TMDB)."""

    async def get_platform_titles(
        self, http: httpx.AsyncClient, kind: ContentKind, provider_id: int, anime: bool = False
    ) -> list[ContentDetail]: ...


@runtime_checkable
class AnimeFinder(Protocol):
    """Source capable de retrouver un anime par son titre (AniList)."""

    async def find_anime(self, http: httpx.AsyncClient, title: str) -> ContentDetail | None: ...


LOCK_KEY = "lock:card_catalog"
LOCK_SECONDS = 3600
REFRESH_SECONDS = 24 * 3600
RETRY_SECONDS = 10 * 60
# Pause entre deux contenus, pour respecter les limites des API gratuites
# (AniList : 90 appels par minute au maximum, parfois moins).
PAUSE_SECONDS = {Source.TMDB: 0.3, Source.ANILIST: 2.0}
# Date très ancienne : la fiche complète sera chargée au premier suivi.
NEVER = datetime(2000, 1, 1, tzinfo=UTC)


async def _store(session: AsyncSession, item: ContentDetail) -> Content | None:
    """Enregistre un contenu du catalogue. ON CONFLICT DO NOTHING : un contenu
    déjà connu garde sa fiche complète (on ne l'écrase pas avec ce résumé)."""
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
    return content


async def _cards(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    content: Content,
) -> None:
    """Crée les cartes du contenu, sauf si elles sont récentes."""
    if content.cards_generated_at is not None and (
        content.cards_generated_at > datetime.now(UTC) - CARDS_REFRESH
    ):
        return
    await ensure_cards(session, http, providers, content)
    await asyncio.sleep(PAUSE_SECONDS.get(Source(content.source), 1.0))


async def seed_catalog(
    session: AsyncSession, http: httpx.AsyncClient, providers: list[MetadataProvider]
) -> int:
    """Remplit le catalogue de cartes, puis met à jour les packs par plateforme.
    Renvoie le nombre de contenus différents traités."""
    seen: set[int] = set()
    # Contenus de chaque plateforme. Une plateforme absente du dictionnaire
    # (source en panne) garde son ancienne liste.
    platforms: dict[PackTheme, set[int]] = {}

    async def keep(item: ContentDetail) -> Content | None:
        content = await _store(session, item)
        if content is not None:
            await _cards(session, http, providers, content)
            seen.add(content.id)
        return content

    # 1. Contenus populaires et mieux notés (films, séries, animes). Pour les
    #    animes, AniList indique aussi où les regarder (Netflix, Crunchyroll…).
    anime_sites: dict[PackTheme, set[int]] = defaultdict(set)
    for provider in providers:
        for kind in ContentKind:
            try:
                items = await provider.get_popular(http, kind)
            except ProviderError:
                log.warning("catalogue.source_indisponible", source=provider.source, kind=kind)
                continue
            for item in items:
                content = await keep(item)
                for site in item.streaming_sites:
                    if content is not None and site in ANILIST_SITES:
                        anime_sites[ANILIST_SITES[site]].add(content.id)

    tmdb = next((p for p in providers if isinstance(p, PlatformCatalog)), None)
    anilist = next((p for p in providers if isinstance(p, AnimeFinder)), None)

    # 2. Films et séries phares de chaque plateforme (Netflix, Disney+…).
    if tmdb is not None:
        for platform, provider_id in PLATFORM_IDS.items():
            try:
                ids: set[int] = set()
                for kind in (ContentKind.MOVIE, ContentKind.SERIES):
                    for item in await tmdb.get_platform_titles(http, kind, provider_id):
                        if content := await keep(item):
                            ids.add(content.id)
                platforms[platform] = ids
            except ProviderError:
                log.warning("catalogue.plateforme_indisponible", platform=platform)

    # 3. Crunchyroll et ADN : catalogue français (TMDB), chaque anime étant
    #    retrouvé chez AniList pour avoir les dessins des personnages.
    if tmdb is not None and anilist is not None:
        for platform, provider_id in ANIME_PLATFORM_IDS.items():
            try:
                ids = set()
                titles = await tmdb.get_platform_titles(
                    http, ContentKind.SERIES, provider_id, anime=True
                )
                for title in titles:
                    match = await anilist.find_anime(http, title.original_title or title.title)
                    await asyncio.sleep(PAUSE_SECONDS[Source.ANILIST])
                    if match is not None and (content := await keep(match)):
                        ids.add(content.id)
                platforms[platform] = ids
            except ProviderError:
                log.warning("catalogue.plateforme_indisponible", platform=platform)

    # Les animes signalés par AniList s'ajoutent aux listes des plateformes.
    for platform, ids in anime_sites.items():
        platforms.setdefault(platform, set()).update(ids)

    # On remplace chaque liste : un titre retiré du catalogue Netflix en sort.
    for platform, ids in platforms.items():
        await session.execute(delete(ContentPlatform).where(ContentPlatform.platform == platform))
        if ids:
            await session.execute(
                insert(ContentPlatform).values(
                    [{"content_id": i, "platform": platform} for i in ids]
                )
            )
    await session.commit()

    log.info("catalogue.termine", contenus=len(seen))
    return len(seen)


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
