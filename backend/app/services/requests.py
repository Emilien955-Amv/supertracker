"""Sondages : les joueurs demandent les cartes d'une œuvre absente du catalogue.

Chaque joueur vote une fois par demande (la créer compte comme un vote). Dès
que le seuil est atteint (3 votes par défaut), l'œuvre entre au catalogue et
ses cartes sont créées tout de suite.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import and_, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Card, Content, RequestStatus, User, WorkRequest, WorkRequestVote
from app.providers.base import ContentKind, MetadataProvider, Source
from app.services import card_catalog, cards, catalog
from app.services import content as content_service

MAX_OPEN_PER_USER = 30  # demandes ouvertes créées par une même personne


class AlreadyInCatalogError(Exception):
    pass


class WorkNotFoundError(Exception):
    pass


class TooManyRequestsError(Exception):
    pass


@dataclass
class RequestView:
    request: WorkRequest
    votes: int
    voted: bool  # le joueur connecté a voté


async def _resolve(
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    source: Source,
    kind: ContentKind,
    external_id: str,
) -> tuple[ContentKind, str]:
    """Un film d'une saga est demandé au nom de sa saga (« Harry Potter »)."""
    if source == Source.TMDB and kind == ContentKind.MOVIE:
        tmdb = next((p for p in providers if isinstance(p, card_catalog.PlatformCatalog)), None)
        if tmdb is not None:
            saga_id = await card_catalog._collection_of(http, tmdb, external_id)
            if saga_id is not None:
                return ContentKind.SAGA, saga_id
    return kind, external_id


async def _in_catalog(session: AsyncSession, source: str, kind: str, external_id: str) -> bool:
    found = await session.scalar(
        select(Content.in_card_catalog).where(
            Content.source == source, Content.kind == kind, Content.external_id == external_id
        )
    )
    return bool(found)


async def _votes(session: AsyncSession, request_id: int) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(WorkRequestVote)
        .where(WorkRequestVote.request_id == request_id)
    )
    return int(count or 0)


async def request_work(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    user: User,
    source: Source,
    kind: ContentKind,
    external_id: str,
) -> RequestView:
    """Crée la demande (ou y ajoute son vote) ; l'œuvre entre au catalogue au seuil."""
    kind, external_id = await _resolve(http, providers, source, kind, external_id)
    if await _in_catalog(session, source, kind, external_id):
        raise AlreadyInCatalogError
    request = await session.scalar(
        select(WorkRequest).where(
            WorkRequest.source == source,
            WorkRequest.kind == kind,
            WorkRequest.external_id == external_id,
        )
    )
    if request is None:
        mine = await session.scalar(
            select(func.count())
            .select_from(WorkRequest)
            .where(WorkRequest.requested_by == user.id, WorkRequest.status == RequestStatus.OPEN)
        )
        if (mine or 0) >= MAX_OPEN_PER_USER:
            raise TooManyRequestsError
        detail = await catalog.get_detail(http, providers, source, kind, external_id)
        if detail is None:
            raise WorkNotFoundError
        await session.execute(
            insert(WorkRequest)
            .values(
                source=source,
                kind=kind,
                external_id=external_id,
                title=detail.title[:300],
                poster_url=detail.poster_url,
                year=detail.year,
                requested_by=user.id,
            )
            .on_conflict_do_nothing(index_elements=["source", "kind", "external_id"])
        )
        request = await session.scalar(
            select(WorkRequest).where(
                WorkRequest.source == source,
                WorkRequest.kind == kind,
                WorkRequest.external_id == external_id,
            )
        )
        assert request is not None  # noqa: S101 (créée juste au-dessus)
    await session.execute(
        insert(WorkRequestVote)
        .values(request_id=request.id, user_id=user.id)
        .on_conflict_do_nothing()
    )
    await session.commit()

    votes = await _votes(session, request.id)
    if request.status == RequestStatus.OPEN and votes >= get_settings().card_request_votes:
        await add_to_catalog(session, http, providers, request)
    return RequestView(request=request, votes=votes, voted=True)


async def add_to_catalog(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    request: WorkRequest,
) -> bool:
    """Ajoute l'œuvre demandée au catalogue si elle a assez de personnages illustrés."""
    content = await content_service.ensure_content(
        session,
        http,
        providers,
        Source(request.source),
        ContentKind(request.kind),
        request.external_id,
    )
    await cards.ensure_cards(session, http, providers, content)
    count = await session.scalar(
        select(func.count()).select_from(Card).where(Card.content_id == content.id)
    )
    if (count or 0) < card_catalog.MIN_CARDS:
        return False  # reste ouverte : pas (encore) de personnages illustrés
    content.in_card_catalog = True
    request.status = RequestStatus.ADDED
    request.added_at = datetime.now(UTC)
    await session.commit()
    return True


async def unvote(session: AsyncSession, user: User, request_id: int) -> None:
    await session.execute(
        delete(WorkRequestVote).where(
            WorkRequestVote.request_id == request_id, WorkRequestVote.user_id == user.id
        )
    )
    # Plus aucun vote sur une demande encore ouverte : elle disparaît.
    request = await session.get(WorkRequest, request_id)
    if request is not None and request.status == RequestStatus.OPEN:
        if await _votes(session, request_id) == 0:
            await session.delete(request)
    await session.commit()


async def list_requests(session: AsyncSession, user: User) -> list[RequestView]:
    """Demandes ouvertes (les plus votées d'abord), puis les dernières ajoutées."""
    votes = (
        select(WorkRequestVote.request_id, func.count().label("n"))
        .group_by(WorkRequestVote.request_id)
        .subquery()
    )
    mine = select(WorkRequestVote.request_id).where(WorkRequestVote.user_id == user.id)
    rows = await session.execute(
        select(WorkRequest, func.coalesce(votes.c.n, 0), WorkRequest.id.in_(mine))
        .outerjoin(votes, votes.c.request_id == WorkRequest.id)
        .order_by(
            (WorkRequest.status == RequestStatus.ADDED),
            func.coalesce(votes.c.n, 0).desc(),
            WorkRequest.added_at.desc().nulls_last(),
            WorkRequest.created_at,
        )
        .limit(200)
    )
    return [RequestView(request=r, votes=int(n), voted=bool(v)) for r, n, v in rows.tuples()]


async def status_for(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    user: User,
    source: Source,
    kind: ContentKind,
    external_id: str,
) -> tuple[bool, RequestView | None]:
    """L'œuvre est-elle au catalogue ? Sinon, la demande en cours (s'il y en a une)."""
    kind, external_id = await _resolve(http, providers, source, kind, external_id)
    if await _in_catalog(session, source, kind, external_id):
        return True, None
    row = (
        await session.execute(
            select(WorkRequest).where(
                and_(
                    WorkRequest.source == source,
                    WorkRequest.kind == kind,
                    WorkRequest.external_id == external_id,
                )
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False, None
    voted = await session.scalar(
        select(WorkRequestVote.user_id).where(
            WorkRequestVote.request_id == row.id, WorkRequestVote.user_id == user.id
        )
    )
    return False, RequestView(
        request=row, votes=await _votes(session, row.id), voted=voted is not None
    )
