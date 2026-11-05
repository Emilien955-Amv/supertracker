"""Copie locale des contenus et des épisodes depuis les sources externes."""

from datetime import UTC, datetime, timedelta

import httpx
import structlog
from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Content, Episode
from app.providers.base import (
    ContentKind,
    EpisodeSummary,
    MetadataProvider,
    ProviderError,
    Source,
)
from app.services import catalog

log = structlog.get_logger()

# Au-delà, on recopie les informations depuis la source (nouveaux épisodes…).
REFRESH_AFTER = timedelta(days=1)

_season_adapter = TypeAdapter(list[EpisodeSummary] | None)


class ContentNotFoundError(Exception):
    """Le contenu (ou la saison) n'existe pas chez la source."""


def _now() -> datetime:
    return datetime.now(UTC)


async def find_content(
    session: AsyncSession, source: Source, kind: ContentKind, external_id: str
) -> Content | None:
    """Contenu déjà copié en base, sans appeler la source."""
    return await session.scalar(
        select(Content).where(
            Content.source == source,
            Content.kind == kind,
            Content.external_id == external_id,
        )
    )


async def ensure_content(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    source: Source,
    kind: ContentKind,
    external_id: str,
) -> Content:
    """Renvoie le contenu en base, en le créant ou le rafraîchissant si besoin.

    Lève ContentNotFoundError s'il n'existe pas, ProviderError si la source
    est en panne ET qu'on n'en a encore aucune copie.
    """
    existing = await find_content(session, source, kind, external_id)
    if existing is not None and existing.refreshed_at > _now() - REFRESH_AFTER:
        return existing

    try:
        detail = await catalog.get_detail(http, providers, source, kind, external_id)
    except ProviderError:
        if existing is not None:
            # Source en panne : la copie un peu ancienne fait très bien l'affaire.
            log.warning("content.rafraichissement_impossible", content_id=existing.id)
            return existing
        raise
    if detail is None:
        if existing is not None:
            return existing
        raise ContentNotFoundError

    values = {
        "title": detail.title[:300],
        "original_title": detail.original_title[:300] if detail.original_title else None,
        "year": detail.year,
        "poster_url": detail.poster_url,
        "backdrop_url": detail.backdrop_url,
        "release_date": detail.release_date,
        "runtime_minutes": detail.runtime_minutes,
        "status": detail.status,
        "episodes_count": detail.episodes_count,
        "is_finished": detail.is_finished,
        "refreshed_at": _now(),
    }
    # « Upsert » : insère, ou met à jour si une autre requête vient de
    # l'insérer en même temps (deux onglets ouverts, par exemple).
    statement = (
        insert(Content)
        .values(source=source, kind=kind, external_id=external_id, **values)
        .on_conflict_do_update(index_elements=["source", "kind", "external_id"], set_=values)
        .returning(Content)
    )
    content = await session.scalar(statement, execution_options={"populate_existing": True})
    assert content is not None  # noqa: S101 (RETURNING renvoie toujours la ligne)
    await session.commit()
    return content


async def ensure_season(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    content: Content,
    season_number: int,
) -> list[Episode]:
    """Épisodes d'une saison, copiés depuis la source au premier affichage."""
    query = (
        select(Episode)
        .where(Episode.content_id == content.id, Episode.season_number == season_number)
        .order_by(Episode.number)
    )
    episodes = list(await session.scalars(query))
    oldest_sync = min((e.synced_at for e in episodes), default=None)
    if oldest_sync is not None and oldest_sync > _now() - REFRESH_AFTER:
        return episodes

    provider = next((p for p in providers if p.source == content.source), None)
    if provider is None:
        return episodes
    try:
        summaries = await catalog.cached(
            f"season:{content.source}:{content.external_id}:{season_number}",
            get_settings().detail_cache_seconds,
            _season_adapter,
            lambda: provider.get_season(http, content.external_id, season_number),
        )
    except ProviderError:
        if episodes:
            return episodes
        raise
    if summaries is None:
        if episodes:
            return episodes
        raise ContentNotFoundError
    if not summaries:
        return episodes

    rows = [
        {
            "content_id": content.id,
            "season_number": season_number,
            "number": s.number,
            "title": s.title[:300] if s.title else None,
            "air_date": s.air_date,
            "runtime_minutes": s.runtime_minutes,
            "still_url": s.still_url,
        }
        for s in summaries
    ]
    statement = insert(Episode).values(rows)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["content_id", "season_number", "number"],
            set_={
                "title": statement.excluded.title,
                "air_date": statement.excluded.air_date,
                "runtime_minutes": statement.excluded.runtime_minutes,
                "still_url": statement.excluded.still_url,
                "synced_at": func.now(),
            },
        )
    )
    await session.commit()
    return list(await session.scalars(query, execution_options={"populate_existing": True}))
