"""Échanges de cartes entre amis.

Déroulé : Alice propose à Bob « je te donne Zoro et Nami, je veux ton Luffy ».
Bob accepte ou refuse ; Alice peut annuler tant que Bob n'a pas répondu.

Sécurité : rien ne bouge à la proposition. À l'acceptation, dans UNE seule
transaction, on verrouille les cartes des deux joueurs (SELECT … FOR UPDATE,
toujours dans le même ordre pour éviter les blocages), on vérifie que chacun
possède encore ce qu'il donne, puis on transfère tout — ou rien.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Content, Trade, TradeItem, TradeStatus, User, UserCard
from app.services import cards
from app.services.social import Relation, relation

MAX_CARDS_PER_SIDE = 10
MAX_PENDING = 20  # échanges en attente proposés par une même personne


class TradeError(Exception):
    """Échange impossible ; le message est destiné au joueur."""


class TradeNotFoundError(Exception):
    pass


@dataclass
class TradeView:
    trade: Trade
    proposer: User
    recipient: User
    gives: list[tuple[Card, Content]] = field(default_factory=list)  # donne le proposeur
    takes: list[tuple[Card, Content]] = field(default_factory=list)  # demandé au destinataire


async def _owned_copies(session: AsyncSession, user_id: int, card_ids: list[int]) -> dict[int, int]:
    if not card_ids:
        return {}
    rows = await session.execute(
        select(UserCard.card_id, UserCard.copies).where(
            UserCard.user_id == user_id, UserCard.card_id.in_(card_ids)
        )
    )
    return dict(rows.tuples().all())


async def propose(
    session: AsyncSession,
    me: User,
    friend: User,
    give: list[int],
    take: list[int],
    message: str | None,
) -> Trade:
    if await relation(session, me, friend) != Relation.FRIENDS:
        raise TradeError("Les échanges se font entre amis.")
    give, take = sorted(set(give)), sorted(set(take))
    if not give and not take:
        raise TradeError("Choisissez au moins une carte.")
    if len(give) > MAX_CARDS_PER_SIDE or len(take) > MAX_CARDS_PER_SIDE:
        raise TradeError(f"{MAX_CARDS_PER_SIDE} cartes au maximum de chaque côté.")
    if set(give) & set(take):
        raise TradeError("Une même carte ne peut pas être donnée et demandée.")
    if set(await _owned_copies(session, me.id, give)) != set(give):
        raise TradeError("Vous ne possédez pas toutes les cartes proposées.")
    if set(await _owned_copies(session, friend.id, take)) != set(take):
        raise TradeError(f"{friend.username} ne possède pas toutes les cartes demandées.")
    pending = await session.scalar(
        select(func.count())
        .select_from(Trade)
        .where(Trade.proposer_id == me.id, Trade.status == TradeStatus.PENDING)
    )
    if (pending or 0) >= MAX_PENDING:
        raise TradeError(f"Trop d'échanges en attente ({MAX_PENDING} au maximum).")

    trade = Trade(proposer_id=me.id, recipient_id=friend.id, message=message or None)
    session.add(trade)
    await session.flush()
    session.add_all(
        [TradeItem(trade_id=trade.id, card_id=c, from_proposer=True) for c in give]
        + [TradeItem(trade_id=trade.id, card_id=c, from_proposer=False) for c in take]
    )
    await session.commit()
    await session.refresh(trade)
    return trade


async def _pending(session: AsyncSession, trade_id: int, lock: bool = False) -> Trade:
    query = select(Trade).where(Trade.id == trade_id)
    if lock:
        query = query.with_for_update()
    trade = await session.scalar(query, execution_options={"populate_existing": True})
    if trade is None:
        raise TradeNotFoundError
    if trade.status != TradeStatus.PENDING:
        raise TradeError("Cet échange n'est plus en attente.")
    return trade


async def _move(
    session: AsyncSession,
    rows: dict[tuple[int, int], UserCard],
    card_id: int,
    giver: int,
    receiver: int,
) -> None:
    """Déplace un exemplaire d'une carte de « giver » vers « receiver »."""
    source = rows[(giver, card_id)]
    if source.copies > 1:
        source.copies -= 1
    else:
        await session.delete(source)
    target = rows.get((receiver, card_id))
    if target is not None:
        target.copies += 1
    else:
        rows[(receiver, card_id)] = UserCard(user_id=receiver, card_id=card_id, copies=1)
        session.add(rows[(receiver, card_id)])


async def accept(session: AsyncSession, me: User, trade_id: int) -> list[cards.MasteryResult]:
    """Accepte l'échange : transfert complet et vérifié, ou rien du tout."""
    trade = await _pending(session, trade_id, lock=True)
    if trade.recipient_id != me.id:
        raise TradeNotFoundError
    items = list(await session.scalars(select(TradeItem).where(TradeItem.trade_id == trade.id)))
    card_ids = sorted({item.card_id for item in items})
    players = sorted((trade.proposer_id, trade.recipient_id))
    # Verrou des cartes des deux joueurs, dans un ordre fixe (évite les blocages).
    rows = {
        (row.user_id, row.card_id): row
        for row in await session.scalars(
            select(UserCard)
            .where(UserCard.user_id.in_(players), UserCard.card_id.in_(card_ids))
            .order_by(UserCard.user_id, UserCard.card_id)
            .with_for_update()
        )
    }
    for item in items:
        giver = trade.proposer_id if item.from_proposer else trade.recipient_id
        if (giver, item.card_id) not in rows:
            await session.rollback()
            raise TradeError("Une des cartes n'est plus disponible : l'échange est impossible.")
    for item in items:
        giver, receiver = (
            (trade.proposer_id, trade.recipient_id)
            if item.from_proposer
            else (trade.recipient_id, trade.proposer_id)
        )
        await _move(session, rows, item.card_id, giver, receiver)
    trade.status = TradeStatus.ACCEPTED
    trade.resolved_at = datetime.now(UTC)
    await session.commit()

    # Collections complétées grâce à l'échange (pour les deux joueurs).
    contents = set(await session.scalars(select(Card.content_id).where(Card.id.in_(card_ids))))
    mine = await cards.check_masteries(session, me.id, contents)
    await cards.check_masteries(session, trade.proposer_id, contents)
    return mine


async def decline(session: AsyncSession, me: User, trade_id: int) -> None:
    trade = await _pending(session, trade_id, lock=True)
    if trade.recipient_id != me.id:
        raise TradeNotFoundError
    trade.status = TradeStatus.DECLINED
    trade.resolved_at = datetime.now(UTC)
    await session.commit()


async def cancel(session: AsyncSession, me: User, trade_id: int) -> None:
    trade = await _pending(session, trade_id, lock=True)
    if trade.proposer_id != me.id:
        raise TradeNotFoundError
    trade.status = TradeStatus.CANCELLED
    trade.resolved_at = datetime.now(UTC)
    await session.commit()


async def list_trades(session: AsyncSession, me: User) -> list[TradeView]:
    """Mes échanges : en attente d'abord, puis les 30 derniers terminés."""
    trades = list(
        await session.scalars(
            select(Trade)
            .where(or_(Trade.proposer_id == me.id, Trade.recipient_id == me.id))
            .order_by((Trade.status != TradeStatus.PENDING), Trade.created_at.desc())
            .limit(50)
        )
    )
    if not trades:
        return []
    users = {
        u.id: u
        for u in await session.scalars(
            select(User).where(
                User.id.in_({t.proposer_id for t in trades} | {t.recipient_id for t in trades})
            )
        )
    }
    rows = await session.execute(
        select(TradeItem, Card, Content)
        .join(Card, Card.id == TradeItem.card_id)
        .join(Content, Content.id == Card.content_id)
        .where(TradeItem.trade_id.in_([t.id for t in trades]))
    )
    views = {
        t.id: TradeView(trade=t, proposer=users[t.proposer_id], recipient=users[t.recipient_id])
        for t in trades
    }
    for item, card, content in rows.tuples():
        side = views[item.trade_id].gives if item.from_proposer else views[item.trade_id].takes
        side.append((card, content))
    return [views[t.id] for t in trades]


# --- Collection d'un ami (pour choisir les cartes à échanger) -----------------------


@dataclass
class PartnerWork:
    content: Content
    mine: int  # cartes différentes que je possède dans cette œuvre
    theirs: int  # … et que mon ami possède


async def partner_works(session: AsyncSession, me: User, friend: User) -> list[PartnerWork]:
    """Œuvres où l'un des deux possède des cartes, avec les compteurs de chacun."""
    rows = await session.execute(
        select(
            Content,
            func.count(UserCard.card_id).filter(UserCard.user_id == me.id),
            func.count(UserCard.card_id).filter(UserCard.user_id == friend.id),
        )
        .join(Card, Card.content_id == Content.id)
        .join(UserCard, UserCard.card_id == Card.id)
        .where(UserCard.user_id.in_([me.id, friend.id]))
        .group_by(Content.id)
        .order_by(func.lower(Content.title))
    )
    return [PartnerWork(content=c, mine=m, theirs=t) for c, m, t in rows.tuples()]


async def partner_cards(
    session: AsyncSession, me: User, friend: User, content_id: int
) -> list[tuple[Card, int, int]]:
    """Cartes d'une œuvre avec mes exemplaires et ceux de mon ami."""
    entries = await cards.binder_page(session, me.id, content_id)
    if entries is None:
        raise TradeNotFoundError
    _, collection = entries
    theirs = await _owned_copies(session, friend.id, [e.card.id for e in collection])
    return [(e.card, e.copies, theirs.get(e.card.id, 0)) for e in collection]
