"""Gamification : points d'expérience (XP), bonus, niveaux et succès.

Règles anti-triche (tout est calculé côté serveur, jamais dans le navigateur) :
- chaque récompense a une clé unique : impossible de la toucher deux fois ;
- décocher un épisode retire l'XP qu'il avait rapporté : cocher/décocher en
  boucle ne rapporte rien ;
- pas d'XP pour un épisode ou un film pas encore sorti ;
- plafond quotidien pour les visionnages : cocher 1 000 épisodes de One Piece
  d'un coup (rattrapage) ne fait pas exploser le compteur.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy import delete, distinct, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Booster,
    Content,
    Episode,
    EpisodeView,
    Library,
    Mastery,
    Tracking,
    TrackingStatus,
    UserBadge,
    XpEvent,
)
from app.providers.base import ContentKind
from app.services.badges import BADGES, TIER_XP, Badge, Metric

PARIS = ZoneInfo("Europe/Paris")

EPISODE_XP = 10
MOVIE_XP = 50
JOUR_J_XP = 25  # épisode vu le jour de sa sortie (ou le lendemain)
MARATHON_XP = 40  # au moins MARATHON_EPISODES épisodes dans la journée
MARATHON_EPISODES = 5
DISCOVERY_XP = 15  # premier épisode d'une nouvelle série
COMPLETION_XP = 100  # série ou anime terminé
MASTERY_XP = 500  # toutes les cartes d'une œuvre
MASTERY_BOOSTERS = 5
DAILY_CAP = 300  # plafond quotidien des XP de visionnage
STREAK_STEP_PERCENT = 5  # +5 % par jour d'affilée…
STREAK_MAX_PERCENT = 50  # … jusqu'à +50 %


class XpKind(StrEnum):
    EPISODE = "episode"
    MOVIE = "movie"
    JOUR_J = "jour_j"
    MARATHON = "marathon"
    DISCOVERY = "discovery"
    COMPLETION = "completion"
    BADGE = "badge"
    MASTERY = "mastery"


LABELS = {
    XpKind.EPISODE: "Épisodes vus",
    XpKind.MOVIE: "Film vu",
    XpKind.JOUR_J: "Bonus Jour J",
    XpKind.MARATHON: "Bonus marathon",
    XpKind.DISCOVERY: "Nouvelle série",
    XpKind.COMPLETION: "Série terminée",
    XpKind.BADGE: "Succès débloqué",
    XpKind.MASTERY: "Collection complète",
}

# Seuls ces gains comptent dans le plafond quotidien et la série de jours.
WATCH_KINDS = (XpKind.EPISODE, XpKind.MOVIE)


def today() -> date:
    return datetime.now(PARIS).date()


def xp_for_level(level: int) -> int:
    """XP totaux nécessaires pour atteindre un niveau : 0, 100, 283, 520, 800…

    La courbe en puissance 1,5 rend chaque niveau un peu plus long que le
    précédent, sans devenir décourageante.
    """
    return round(100 * (level - 1) ** 1.5)


def level_for_xp(xp: int) -> int:
    level = 1
    while xp_for_level(level + 1) <= xp:
        level += 1
    return level


def streak_bonus_percent(streak_days: int) -> int:
    """Bonus de régularité : +5 % par jour d'affilée au-delà du premier."""
    return min(STREAK_MAX_PERCENT, STREAK_STEP_PERCENT * max(0, streak_days - 1))


@dataclass
class Rewards:
    """Ce qu'une action vient de rapporter (affiché dans une notification)."""

    gains: Counter[XpKind] = field(default_factory=Counter)
    badges: list[Badge] = field(default_factory=list)
    level_before: int = 1
    level_after: int = 1
    streak_days: int = 0
    boosters: int = 0  # boosters de cartes gagnés

    @property
    def xp(self) -> int:
        return sum(self.gains.values())

    def merge(self, other: "Rewards") -> "Rewards":
        """Additionne deux récompenses (ex. changement de statut + épisodes cochés)."""
        return Rewards(
            gains=self.gains + other.gains,
            badges=self.badges + other.badges,
            level_before=self.level_before,
            level_after=max(self.level_after, other.level_after),
            streak_days=max(self.streak_days, other.streak_days),
            boosters=self.boosters + other.boosters,
        )

    @property
    def is_empty(self) -> bool:
        return not self.gains and not self.badges and not self.boosters


# --- Lecture -------------------------------------------------------------------


async def total_xp(session: AsyncSession, user_id: int) -> int:
    value = await session.scalar(
        select(func.coalesce(func.sum(XpEvent.amount), 0)).where(XpEvent.user_id == user_id)
    )
    return int(value or 0)


async def watch_xp_on(session: AsyncSession, user_id: int, day: date) -> int:
    value = await session.scalar(
        select(func.coalesce(func.sum(XpEvent.amount), 0)).where(
            XpEvent.user_id == user_id, XpEvent.day == day, XpEvent.kind.in_(WATCH_KINDS)
        )
    )
    return int(value or 0)


async def streak_days(session: AsyncSession, user_id: int) -> int:
    """Jours d'affilée avec au moins un visionnage récompensé.

    La série reste « vivante » jusqu'au soir du lendemain : si vous avez
    regardé hier mais pas encore aujourd'hui, elle n'est pas perdue.
    """
    since = today() - timedelta(days=60)
    days = set(
        await session.scalars(
            select(distinct(XpEvent.day)).where(
                XpEvent.user_id == user_id,
                XpEvent.day >= since,
                XpEvent.kind.in_(WATCH_KINDS),
            )
        )
    )
    cursor = today() if today() in days else today() - timedelta(days=1)
    count = 0
    while cursor in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


async def _metric(session: AsyncSession, user_id: int, metric: Metric) -> int:
    """Valeur actuelle d'une mesure utilisée par les succès."""
    episodes = (
        select(func.count())
        .select_from(EpisodeView)
        .join(Episode, Episode.id == EpisodeView.episode_id)
        .where(
            EpisodeView.user_id == user_id,
            Episode.season_number > 0,
            # Un épisode pas encore diffusé ne compte pas pour les succès.
            or_(Episode.air_date.is_(None), Episode.air_date <= today()),
        )
    )
    completed = (
        select(func.count())
        .select_from(Tracking)
        .join(Content, Content.id == Tracking.content_id)
        .where(Tracking.user_id == user_id, Tracking.status == TrackingStatus.COMPLETED)
    )
    events = select(func.count()).select_from(XpEvent).where(XpEvent.user_id == user_id)

    match metric:
        case Metric.EPISODES:
            query = episodes
        case Metric.ANIME_EPISODES:
            query = episodes.join(Content, Content.id == Episode.content_id).where(
                Content.kind == ContentKind.ANIME
            )
        case Metric.MOVIES:
            query = completed.where(Content.kind == ContentKind.MOVIE)
        case Metric.SERIES_COMPLETED:
            query = completed.where(Content.kind != ContentKind.MOVIE)
        case Metric.REVIEWS:
            query = (
                select(func.count())
                .select_from(Tracking)
                .where(Tracking.user_id == user_id, Tracking.review.is_not(None))
            )
        case Metric.LIBRARIES:
            query = select(func.count()).select_from(Library).where(Library.user_id == user_id)
        case Metric.MARATHONS:
            query = events.where(XpEvent.kind == XpKind.MARATHON)
        case Metric.JOUR_J:
            query = events.where(XpEvent.kind == XpKind.JOUR_J)
        case Metric.MASTERIES:
            query = select(func.count()).select_from(Mastery).where(Mastery.user_id == user_id)
        case Metric.STREAK:
            return await streak_days(session, user_id)
        case Metric.LEVEL:
            return level_for_xp(await total_xp(session, user_id))
    return int(await session.scalar(query) or 0)


async def badge_progress(session: AsyncSession, user_id: int) -> dict[Metric, int]:
    """Toutes les mesures d'un joueur (pour afficher la progression des succès)."""
    return {metric: await _metric(session, user_id, metric) for metric in Metric}


# --- Écriture ------------------------------------------------------------------


async def grant_booster(session: AsyncSession, user_id: int, key: str) -> bool:
    """Donne un booster de cartes. Clé unique (ex. « level:3 ») : jamais deux fois."""
    created = await session.scalar(
        insert(Booster)
        .values(user_id=user_id, key=key)
        .on_conflict_do_nothing(index_elements=["user_id", "key"])
        .returning(Booster.id)
    )
    return created is not None


class _Session:
    """Accumule les récompenses d'une action, puis vérifie succès et niveau."""

    def __init__(self, session: AsyncSession, user_id: int) -> None:
        self.session = session
        self.user_id = user_id
        self.rewards = Rewards()

    async def start(self) -> "_Session":
        self.rewards.level_before = level_for_xp(await total_xp(self.session, self.user_id))
        return self

    async def award(
        self, key: str, kind: XpKind, amount: int, content_id: int | None = None
    ) -> int:
        """Enregistre un gain. Renvoie 0 si cette récompense a déjà été donnée."""
        if amount <= 0:
            return 0
        gained = await self.session.scalar(
            insert(XpEvent)
            .values(
                user_id=self.user_id,
                key=key,
                kind=kind,
                amount=amount,
                content_id=content_id,
                day=today(),
            )
            .on_conflict_do_nothing(index_elements=["user_id", "key"])
            .returning(XpEvent.amount)
        )
        if gained:
            self.rewards.gains[kind] += gained
        return gained or 0

    async def revoke(self, keys: list[str]) -> None:
        if keys:
            await self.session.execute(
                delete(XpEvent).where(XpEvent.user_id == self.user_id, XpEvent.key.in_(keys))
            )

    async def watch_budget(self) -> tuple[int, float]:
        """XP de visionnage encore possibles aujourd'hui, et multiplicateur de série."""
        remaining = DAILY_CAP - await watch_xp_on(self.session, self.user_id, today())
        # La série compte aujourd'hui, même si c'est le premier visionnage du jour.
        streak = await streak_days(self.session, self.user_id)
        if await watch_xp_on(self.session, self.user_id, today()) == 0:
            streak += 1
        self.rewards.streak_days = streak
        return max(0, remaining), 1 + streak_bonus_percent(streak) / 100

    async def finish(self) -> Rewards:
        """Débloque les succès atteints, puis calcule le nouveau niveau."""
        earned = set(
            await self.session.scalars(
                select(UserBadge.code).where(UserBadge.user_id == self.user_id)
            )
        )
        cache: dict[Metric, int] = {}
        # Deux passes : un succès rapporte des XP qui peuvent débloquer « Vétéran ».
        for _ in range(2):
            for badge in BADGES:
                if badge.code in earned:
                    continue
                if badge.metric not in cache or badge.metric == Metric.LEVEL:
                    cache[badge.metric] = await _metric(self.session, self.user_id, badge.metric)
                if cache[badge.metric] < badge.threshold:
                    continue
                inserted = await self.session.scalar(
                    insert(UserBadge)
                    .values(user_id=self.user_id, code=badge.code)
                    .on_conflict_do_nothing()
                    .returning(UserBadge.code)
                )
                earned.add(badge.code)
                if inserted:
                    self.rewards.badges.append(badge)
                    await self.award(f"badge:{badge.code}", XpKind.BADGE, TIER_XP[badge.tier])
        self.rewards.level_after = level_for_xp(await total_xp(self.session, self.user_id))
        # Un booster de cartes par niveau gagné.
        for level in range(self.rewards.level_before + 1, self.rewards.level_after + 1):
            await self.booster(f"level:{level}")
        return self.rewards

    async def booster(self, key: str) -> None:
        if await grant_booster(self.session, self.user_id, key):
            self.rewards.boosters += 1


async def on_episodes_changed(
    session: AsyncSession,
    user_id: int,
    content: Content,
    episodes: list[Episode],
    watched: bool,
    status_before: str | None,
    status_after: str | None,
) -> Rewards:
    """À appeler quand des épisodes viennent d'être cochés ou décochés."""
    game = await _Session(session, user_id).start()

    if not watched:
        ids = [episode.id for episode in episodes]
        await game.revoke([f"episode:{i}" for i in ids] + [f"jour_j:{i}" for i in ids])
    else:
        remaining, multiplier = await game.watch_budget()
        day = today()
        for episode in episodes:
            # Pas d'XP pour un épisode pas encore diffusé : impossible de l'avoir vu.
            if episode.air_date is not None and episode.air_date > day:
                continue
            amount = min(round(EPISODE_XP * multiplier), remaining)
            gained = await game.award(f"episode:{episode.id}", XpKind.EPISODE, amount, content.id)
            remaining -= gained
            if episode.air_date is not None and episode.air_date >= day - timedelta(days=1):
                await game.award(f"jour_j:{episode.id}", XpKind.JOUR_J, JOUR_J_XP, content.id)

        if game.rewards.gains[XpKind.EPISODE]:
            await game.award(f"discovery:{content.id}", XpKind.DISCOVERY, DISCOVERY_XP, content.id)
            watched_today = await session.scalar(
                select(func.count())
                .select_from(XpEvent)
                .where(
                    XpEvent.user_id == user_id,
                    XpEvent.day == day,
                    XpEvent.kind == XpKind.EPISODE,
                )
            )
            if (watched_today or 0) >= MARATHON_EPISODES:
                await game.award(f"marathon:{day.isoformat()}", XpKind.MARATHON, MARATHON_XP)

    await _status_rewards(game, content, status_before, status_after)
    return await game.finish()


async def on_status_changed(
    session: AsyncSession,
    user_id: int,
    content: Content,
    status_before: str | None,
    status_after: str | None,
) -> Rewards:
    """À appeler quand le statut, la note ou l'avis d'un suivi change."""
    game = await _Session(session, user_id).start()
    await _status_rewards(game, content, status_before, status_after)
    return await game.finish()


async def forget_content(session: AsyncSession, user_id: int, content_id: int) -> None:
    """Contenu retiré du suivi : on reprend les XP de ses épisodes et de sa fin.
    Les bonus déjà acquis (marathon, succès…) restent gagnés."""
    await session.execute(
        delete(XpEvent).where(
            XpEvent.user_id == user_id,
            XpEvent.content_id == content_id,
            XpEvent.kind.in_([XpKind.EPISODE, XpKind.JOUR_J, XpKind.MOVIE, XpKind.COMPLETION]),
        )
    )


async def on_mastery(session: AsyncSession, user_id: int, content_id: int) -> Rewards:
    """Collection complète : 500 XP, 5 boosters, et les succès de collectionneur."""
    game = await _Session(session, user_id).start()
    await game.award(f"mastery:{content_id}", XpKind.MASTERY, MASTERY_XP, content_id)
    for number in range(MASTERY_BOOSTERS):
        await game.booster(f"mastery:{content_id}:{number}")
    return await game.finish()


async def check_badges(session: AsyncSession, user_id: int) -> Rewards:
    """Vérifie seulement les succès (ex. après la création d'une bibliothèque)."""
    return await (await _Session(session, user_id).start()).finish()


async def _status_rewards(
    game: _Session, content: Content, before: str | None, after: str | None
) -> None:
    done = TrackingStatus.COMPLETED
    if before == done and after != done:
        # Plus « terminé » : on reprend ce que la fin avait rapporté.
        await game.revoke([f"movie:{content.id}", f"completion:{content.id}"])
        return
    if after != done or before == done:
        return
    if content.kind == ContentKind.MOVIE:
        if content.release_date is not None and content.release_date > today():
            return  # film pas encore sorti
        remaining, multiplier = await game.watch_budget()
        amount = min(round(MOVIE_XP * multiplier), remaining)
        await game.award(f"movie:{content.id}", XpKind.MOVIE, amount, content.id)
    else:
        await game.award(f"completion:{content.id}", XpKind.COMPLETION, COMPLETION_XP, content.id)
    # Un booster par film, série ou anime terminé. Clé unique : changer de
    # statut puis revenir à « terminé » ne redonne pas de booster.
    await game.booster(f"completion:{content.id}")
