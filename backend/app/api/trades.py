"""Routes des échanges de cartes entre amis."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints

from app.api.cards import _binder_content, _new_masteries
from app.api.deps import CurrentUser, SessionDep
from app.core.rate_limit import enforce_rate_limit
from app.models import Content, TradeStatus, User
from app.schemas.cards import BinderContent, CardRead, MasteryRead
from app.services import social
from app.services import trades as service

router = APIRouter(prefix="/trades", tags=["Échanges"])

NOT_FOUND = "Échange introuvable."


class TradeRead(BaseModel):
    id: int
    status: TradeStatus
    # incoming : on me propose ; outgoing : je propose.
    direction: Literal["incoming", "outgoing"]
    partner: str  # pseudo de l'autre joueur
    message: str | None
    gives: list[CardRead]  # ce que donne celui qui propose
    takes: list[CardRead]  # ce qu'il demande en échange
    created_at: datetime
    resolved_at: datetime | None


class TradeCreate(BaseModel):
    username: str
    give: list[int] = Field(default=[], max_length=service.MAX_CARDS_PER_SIDE)
    take: list[int] = Field(default=[], max_length=service.MAX_CARDS_PER_SIDE)
    message: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class AcceptResult(BaseModel):
    masteries: list[MasteryRead]  # collections complétées grâce à l'échange


class PartnerWorkRead(BaseModel):
    content: BinderContent
    mine: int
    theirs: int


class PartnerCardRead(BaseModel):
    card: CardRead
    mine: int  # mes exemplaires
    theirs: int  # ceux de mon ami


def _read(view: service.TradeView, me: User) -> TradeRead:
    incoming = view.recipient.id == me.id
    return TradeRead(
        id=view.trade.id,
        status=TradeStatus(view.trade.status),
        direction="incoming" if incoming else "outgoing",
        partner=view.proposer.username if incoming else view.recipient.username,
        message=view.trade.message,
        gives=[CardRead.of(card, content) for card, content in view.gives],
        takes=[CardRead.of(card, content) for card, content in view.takes],
        created_at=view.trade.created_at,
        resolved_at=view.trade.resolved_at,
    )


async def _friend(session: SessionDep, me: User, username: str) -> User:
    try:
        friend = await social.find_user(session, username)
    except social.UserNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.") from None
    if await social.relation(session, me, friend) != social.Relation.FRIENDS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Les échanges se font entre amis.")
    return friend


@router.get("", summary="Mes échanges (en attente d'abord)")
async def list_trades(user: CurrentUser, session: SessionDep) -> list[TradeRead]:
    return [_read(view, user) for view in await service.list_trades(session, user)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Proposer un échange à un ami",
    responses={403: {"description": "Pas amis"}, 409: {"description": "Échange impossible"}},
)
async def propose(user: CurrentUser, session: SessionDep, body: TradeCreate) -> TradeRead:
    await enforce_rate_limit(f"trades:{user.id}", limit=30, window_seconds=60)
    friend = await _friend(session, user, body.username)
    try:
        trade = await service.propose(session, user, friend, body.give, body.take, body.message)
    except service.TradeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    view = next(v for v in await service.list_trades(session, user) if v.trade.id == trade.id)
    return _read(view, user)


@router.post(
    "/{trade_id}/accept",
    summary="Accepter un échange reçu",
    responses={404: {"description": NOT_FOUND}, 409: {"description": "Échange impossible"}},
)
async def accept(user: CurrentUser, session: SessionDep, trade_id: int) -> AcceptResult:
    try:
        masteries = await service.accept(session, user, trade_id)
    except service.TradeNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except service.TradeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return AcceptResult(masteries=_new_masteries(masteries))


@router.post(
    "/{trade_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Refuser un échange reçu",
)
async def decline(user: CurrentUser, session: SessionDep, trade_id: int) -> Response:
    try:
        await service.decline(session, user, trade_id)
    except service.TradeNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except service.TradeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{trade_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Annuler un échange que j'ai proposé",
)
async def cancel(user: CurrentUser, session: SessionDep, trade_id: int) -> Response:
    try:
        await service.cancel(session, user, trade_id)
    except service.TradeNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except service.TradeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/partner/{username}/works",
    summary="Œuvres où un ami ou moi avons des cartes (pour préparer un échange)",
)
async def partner_works(
    user: CurrentUser, session: SessionDep, username: str
) -> list[PartnerWorkRead]:
    friend = await _friend(session, user, username)
    return [
        PartnerWorkRead(content=_binder_content(w.content), mine=w.mine, theirs=w.theirs)
        for w in await service.partner_works(session, user, friend)
    ]


@router.get(
    "/partner/{username}/works/{content_id}",
    summary="Cartes d'une œuvre : mes exemplaires et ceux de mon ami",
)
async def partner_cards(
    user: CurrentUser, session: SessionDep, username: str, content_id: int
) -> list[PartnerCardRead]:
    friend = await _friend(session, user, username)
    try:
        rows = await service.partner_cards(session, user, friend, content_id)
    except service.TradeNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Œuvre introuvable.") from None
    content = await session.get(Content, content_id)
    assert content is not None  # noqa: S101 (vérifiée par partner_cards)
    return [
        PartnerCardRead(card=CardRead.of(card, content), mine=mine, theirs=theirs)
        for card, mine, theirs in rows
    ]
