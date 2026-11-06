"""Catalogue de cartes : les œuvres dont on peut obtenir les cartes.

Il est volontairement resserré, pour des collections complètes et riches :
- les 100 séries les plus populaires de tous les temps ;
- les 100 films les plus populaires, les sagas étant regroupées (« Harry
  Potter » = une seule œuvre, avec les personnages des 8 films) ;
- les 100 animes les plus populaires (jusqu'à 300 personnages chacun).
Une œuvre n'y entre que si elle a au moins quelques personnages illustrés.

Les packs par plateforme (Netflix, Crunchyroll…) ne contiennent que des œuvres
de ce catalogue.

La tâche tourne en arrière-plan dans l'API : au démarrage, puis toutes les
24 heures. Un verrou Redis garantit qu'une seule copie de l'API la lance à la
fois (utile en production, quand plusieurs copies tourneront en parallèle).
"""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import httpx
import structlog
from pydantic import TypeAdapter
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import redis_client
from app.db import SessionLocal
from app.http_client import get_http_client
from app.models import Card, Content, ContentPlatform
from app.providers.base import (
    ContentDetail,
    ContentKind,
    MetadataProvider,
    ProviderError,
    Source,
)
from app.providers.registry import get_providers
from app.services import catalog
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
    """Source des films et séries (TMDB) : classements, sagas, plateformes."""

    async def get_top(self, http: httpx.AsyncClient, kind: ContentKind) -> list[ContentDetail]: ...

    async def movie_collection(
        self, http: httpx.AsyncClient, movie_id: str
    ) -> tuple[str, str] | None: ...

    async def get_detail(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> ContentDetail | None: ...

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
TARGET_PER_KIND = 100  # œuvres par catégorie (séries, films, animes)
MIN_CARDS = 5  # personnages illustrés au minimum pour entrer au catalogue
COLLECTION_CACHE_SECONDS = 30 * 24 * 3600  # un film change rarement de saga
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
) -> int:
    """Crée les cartes du contenu (sauf si elles sont récentes) ; renvoie leur nombre."""
    if content.cards_generated_at is None or (
        content.cards_generated_at < datetime.now(UTC) - CARDS_REFRESH
    ):
        try:
            await ensure_cards(session, http, providers, content)
        except Exception:
            # Un contenu qui pose problème ne doit pas bloquer tout le catalogue.
            log.exception("catalogue.contenu_en_erreur", content_id=content.id)
            await session.rollback()
        await asyncio.sleep(PAUSE_SECONDS.get(Source(content.source), 1.0))
    count = await session.scalar(
        select(func.count()).select_from(Card).where(Card.content_id == content.id)
    )
    return int(count or 0)


_collection_adapter = TypeAdapter(list[str] | None)


async def _collection_of(
    http: httpx.AsyncClient, tmdb: PlatformCatalog, movie_id: str
) -> str | None:
    """Identifiant de la saga d'un film (mis en cache 30 jours), ou None."""

    async def fetch() -> list[str] | None:
        found = await tmdb.movie_collection(http, movie_id)
        return list(found) if found else None

    found = await catalog.cached(
        f"collection_of:{movie_id}", COLLECTION_CACHE_SECONDS, _collection_adapter, fetch
    )
    return found[0] if found else None


async def seed_catalog(
    session: AsyncSession, http: httpx.AsyncClient, providers: list[MetadataProvider]
) -> int:
    """Choisit les œuvres du catalogue de cartes, crée leurs cartes, puis met à
    jour les packs par plateforme. Renvoie le nombre d'œuvres retenues."""
    tmdb = next((p for p in providers if isinstance(p, PlatformCatalog)), None)
    anilist = next((p for p in providers if isinstance(p, AnimeFinder)), None)
    selected: list[int] = []
    # Film TMDB → œuvre du catalogue (le film lui-même, ou sa saga).
    movie_work: dict[str, int] = {}
    anime_sites: dict[PackTheme, set[int]] = defaultdict(set)

    async def candidate(item: ContentDetail) -> Content | None:
        """Enregistre l'œuvre ; la garde si elle a assez de personnages illustrés."""
        content = await _store(session, item)
        if content is None or await _cards(session, http, providers, content) < MIN_CARDS:
            return None
        return content

    async def safely(fetch: Awaitable[list[ContentDetail]], label: str) -> list[ContentDetail]:
        try:
            return await fetch
        except ProviderError:
            log.warning("catalogue.source_indisponible", liste=label)
            return []

    # 1. Les 100 séries les plus populaires.
    if tmdb is not None:
        count = 0
        for item in await safely(tmdb.get_top(http, ContentKind.SERIES), "séries"):
            if count >= TARGET_PER_KIND:
                break
            if content := await candidate(item):
                selected.append(content.id)
                count += 1

    # 2. Les 100 films les plus populaires, sagas regroupées.
    if tmdb is not None:
        count = 0
        sagas: dict[str, int | None] = {}  # saga → œuvre retenue (None : refusée)
        for item in await safely(tmdb.get_top(http, ContentKind.MOVIE), "films"):
            if count >= TARGET_PER_KIND:
                break
            try:
                saga_id = await _collection_of(http, tmdb, item.external_id)
            except ProviderError:
                continue
            if saga_id is None:
                if content := await candidate(item):
                    selected.append(content.id)
                    movie_work[item.external_id] = content.id
                    count += 1
                continue
            if saga_id in sagas:  # saga déjà traitée (Harry Potter 2 après le 1)
                if sagas[saga_id] is not None:
                    movie_work[item.external_id] = sagas[saga_id]  # type: ignore[assignment]
                continue
            try:
                saga = await tmdb.get_detail(http, ContentKind.SAGA, saga_id)
            except ProviderError:
                continue
            content = await candidate(saga) if saga else None
            sagas[saga_id] = content.id if content else None
            if content is not None and saga is not None:
                selected.append(content.id)
                count += 1
                for part in saga.parts:
                    movie_work[part.external_id] = content.id

    # 3. Les 100 animes les plus populaires (AniList indique aussi où les regarder).
    for provider in providers:
        count = 0
        for item in await safely(provider.get_popular(http, ContentKind.ANIME), "animes"):
            if count >= TARGET_PER_KIND:
                break
            if content := await candidate(item):
                selected.append(content.id)
                count += 1
                for site in item.streaming_sites:
                    if site in ANILIST_SITES:
                        anime_sites[ANILIST_SITES[site]].add(content.id)

    # Le catalogue : exactement les œuvres retenues, dans l'ordre du classement.
    # (Les cartes déjà obtenues d'une œuvre sortie du catalogue restent à leur
    # propriétaire ; elles ne sortent simplement plus dans les boosters.)
    if not selected:
        log.warning("catalogue.vide_garde_l_ancien")
        return 0
    await session.execute(
        update(Content)
        .where(Content.in_card_catalog.is_(True))
        .values(in_card_catalog=False, catalog_rank=None)
    )
    for rank, content_id in enumerate(selected):
        await session.execute(
            update(Content)
            .where(Content.id == content_id)
            .values(in_card_catalog=True, catalog_rank=rank)
        )
    await session.commit()
    catalog_ids = set(selected)

    async def catalog_id(source: Source, kind: ContentKind, external_id: str) -> int | None:
        found = await session.scalar(
            select(Content.id).where(
                Content.source == source,
                Content.kind == kind,
                Content.external_id == external_id,
            )
        )
        return found if found in catalog_ids else None

    # 4. Packs par plateforme : les œuvres du catalogue disponibles sur chacune.
    platforms: dict[PackTheme, set[int]] = {}
    if tmdb is not None:
        for platform, provider_id in PLATFORM_IDS.items():
            try:
                ids: set[int] = set()
                for item in await tmdb.get_platform_titles(http, ContentKind.SERIES, provider_id):
                    if found := await catalog_id(Source.TMDB, ContentKind.SERIES, item.external_id):
                        ids.add(found)
                for item in await tmdb.get_platform_titles(http, ContentKind.MOVIE, provider_id):
                    work = movie_work.get(item.external_id)
                    if work is None:
                        saga_id = await _collection_of(http, tmdb, item.external_id)
                        if saga_id is not None:
                            work = await catalog_id(Source.TMDB, ContentKind.SAGA, saga_id)
                    if work is not None:
                        ids.add(work)
                platforms[platform] = ids
            except ProviderError:
                log.warning("catalogue.plateforme_indisponible", platform=platform)
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
                    if match is not None and (
                        found := await catalog_id(
                            match.source, ContentKind.ANIME, match.external_id
                        )
                    ):
                        ids.add(found)
                platforms[platform] = ids
            except ProviderError:
                log.warning("catalogue.plateforme_indisponible", platform=platform)
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

    log.info("catalogue.termine", oeuvres=len(selected))
    return len(selected)


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
