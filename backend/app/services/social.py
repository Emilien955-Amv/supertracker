"""Social : amis et profils.

Confidentialité (RGPD) : un profil est PRIVÉ par défaut. Seuls ses amis en
voient le détail ; les autres ne voient que le pseudo (nécessaire pour envoyer
une demande d'ami). L'utilisateur peut rendre son profil public.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import ColumnElement, and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Card,
    Content,
    Episode,
    EpisodeView,
    Friendship,
    FriendStatus,
    Rarity,
    Tracking,
    TrackingStatus,
    User,
    UserBadge,
    UserCard,
)
from app.services import gamification
from app.services.badges import BADGES_BY_CODE, Badge

MAX_PENDING = 100  # demandes en attente envoyées par une même personne
SEARCH_LIMIT = 20


class Relation(StrEnum):
    SELF = "self"
    FRIENDS = "friends"
    OUTGOING = "outgoing"  # j'ai envoyé une demande
    INCOMING = "incoming"  # on m'a envoyé une demande
    NONE = "none"


class UserNotFoundError(Exception):
    pass


class TooManyRequestsError(Exception):
    pass


def _pair(a: int, b: int) -> ColumnElement[bool]:
    """Condition SQL : l'amitié entre a et b, quel que soit le sens."""
    return or_(
        and_(Friendship.requester_id == a, Friendship.addressee_id == b),
        and_(Friendship.requester_id == b, Friendship.addressee_id == a),
    )


async def find_user(session: AsyncSession, username: str) -> User:
    # Pseudo insensible à la casse : « Emilien » et « emilien » sont la même personne.
    user = await session.scalar(select(User).where(func.lower(User.username) == username.lower()))
    if user is None:
        raise UserNotFoundError
    return user


async def relation(session: AsyncSession, me: User, other: User) -> Relation:
    if me.id == other.id:
        return Relation.SELF
    friendship = await session.scalar(select(Friendship).where(_pair(me.id, other.id)))
    if friendship is None:
        return Relation.NONE
    if friendship.status == FriendStatus.ACCEPTED:
        return Relation.FRIENDS
    return Relation.OUTGOING if friendship.requester_id == me.id else Relation.INCOMING


async def add_friend(session: AsyncSession, me: User, other: User) -> Relation:
    """Envoie une demande d'ami, ou accepte celle que l'autre m'a envoyée."""
    current = await relation(session, me, other)
    if current in (Relation.SELF, Relation.FRIENDS, Relation.OUTGOING):
        return current
    if current == Relation.INCOMING:
        friendship = await session.scalar(select(Friendship).where(_pair(me.id, other.id)))
        assert friendship is not None  # noqa: S101 (vu juste au-dessus)
        friendship.status = FriendStatus.ACCEPTED
        friendship.accepted_at = datetime.now(UTC)
        await session.commit()
        return Relation.FRIENDS
    pending = await session.scalar(
        select(func.count())
        .select_from(Friendship)
        .where(Friendship.requester_id == me.id, Friendship.status == FriendStatus.PENDING)
    )
    if (pending or 0) >= MAX_PENDING:
        raise TooManyRequestsError
    # ON CONFLICT DO NOTHING : si l'autre envoie sa demande au même instant,
    # l'index unique de la paire évite un doublon.
    await session.execute(
        insert(Friendship)
        .values(requester_id=me.id, addressee_id=other.id)
        .on_conflict_do_nothing()
    )
    await session.commit()
    return await relation(session, me, other)


async def remove_friend(session: AsyncSession, me: User, other: User) -> None:
    """Retire un ami, refuse une demande reçue ou annule une demande envoyée."""
    await session.execute(delete(Friendship).where(_pair(me.id, other.id)))
    await session.commit()


@dataclass
class FriendLists:
    friends: list[User] = field(default_factory=list)
    incoming: list[User] = field(default_factory=list)
    outgoing: list[User] = field(default_factory=list)


async def friend_lists(session: AsyncSession, me: User) -> FriendLists:
    rows = await session.execute(
        select(Friendship, User)
        .join(
            User,
            User.id
            == func.coalesce(
                # L'autre personne de la paire.
                func.nullif(Friendship.requester_id, me.id),
                Friendship.addressee_id,
            ),
        )
        .where(or_(Friendship.requester_id == me.id, Friendship.addressee_id == me.id))
        .order_by(func.lower(User.username))
    )
    lists = FriendLists()
    for friendship, user in rows.tuples():
        if friendship.status == FriendStatus.ACCEPTED:
            lists.friends.append(user)
        elif friendship.requester_id == me.id:
            lists.outgoing.append(user)
        else:
            lists.incoming.append(user)
    return lists


async def search_users(session: AsyncSession, me: User, query: str) -> list[User]:
    """Pseudos qui commencent par le texte cherché (hors soi-même)."""
    pattern = query.replace("\\", "").replace("%", "\\%").replace("_", "\\_") + "%"
    return list(
        await session.scalars(
            select(User)
            .where(User.id != me.id, User.username.ilike(pattern, escape="\\"))
            .order_by(func.length(User.username), func.lower(User.username))
            .limit(SEARCH_LIMIT)
        )
    )


@dataclass
class ProfileStats:
    xp: int
    level: int
    badges: list[Badge]
    episodes: int
    movies: int
    series_completed: int
    cards: int
    top_cards: dict[Rarity, int]


def can_see(user: User, viewer_relation: Relation) -> bool:
    """Le détail d'un profil est visible par soi-même, ses amis, ou tous s'il est public."""
    return user.is_public or viewer_relation in (Relation.SELF, Relation.FRIENDS)


async def profile_stats(session: AsyncSession, user: User) -> ProfileStats:
    xp = await gamification.total_xp(session, user.id)
    codes = await session.scalars(
        select(UserBadge.code).where(UserBadge.user_id == user.id).order_by(UserBadge.earned_at)
    )
    completed = (
        select(Content.kind, func.count())
        .join(Tracking, Tracking.content_id == Content.id)
        .where(Tracking.user_id == user.id, Tracking.status == TrackingStatus.COMPLETED)
        .group_by(Content.kind)
    )
    by_kind = dict((await session.execute(completed)).tuples().all())
    episodes = await session.scalar(
        select(func.count())
        .select_from(EpisodeView)
        .join(Episode, Episode.id == EpisodeView.episode_id)
        .where(EpisodeView.user_id == user.id, Episode.season_number > 0)
    )
    rarities = dict(
        (
            await session.execute(
                select(Card.rarity, func.count())
                .join(UserCard, UserCard.card_id == Card.id)
                .where(UserCard.user_id == user.id)
                .group_by(Card.rarity)
            )
        )
        .tuples()
        .all()
    )
    return ProfileStats(
        xp=xp,
        level=gamification.level_for_xp(xp),
        badges=[BADGES_BY_CODE[c] for c in codes if c in BADGES_BY_CODE],
        episodes=int(episodes or 0),
        movies=int(by_kind.get("movie", 0)),
        series_completed=int(by_kind.get("series", 0)) + int(by_kind.get("anime", 0)),
        cards=sum(rarities.values()),
        top_cards={
            Rarity(r): n
            for r, n in rarities.items()
            if r in (Rarity.LEGENDARY, Rarity.MYTHIC, Rarity.DIVINE)
        },
    )
