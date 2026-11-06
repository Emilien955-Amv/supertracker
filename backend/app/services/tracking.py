"""Suivi d'un contenu : statut, note, avis, épisodes vus et progression."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Subquery, and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Content, Episode, EpisodeView, Tracking, TrackingStatus
from app.providers.base import ContentKind
from app.services import gamification
from app.services.gamification import Rewards


class EpisodeNotFoundError(Exception):
    """Un des épisodes demandés n'appartient pas à ce contenu."""


@dataclass
class Progress:
    watched: int
    total: int | None  # None : nombre d'épisodes inconnu (anime en cours…)

    @property
    def percent(self) -> int | None:
        if not self.total:
            return None
        return min(100, round(100 * self.watched / self.total))


def _now() -> datetime:
    return datetime.now(UTC)


async def get_tracking(session: AsyncSession, user_id: int, content_id: int) -> Tracking | None:
    return await session.scalar(
        select(Tracking).where(Tracking.user_id == user_id, Tracking.content_id == content_id)
    )


def _watched_counts(user_id: int) -> Subquery:
    """Sous-requête : nombre d'épisodes vus par contenu, hors épisodes spéciaux."""
    return (
        select(Episode.content_id, func.count().label("watched"))
        .join(EpisodeView, EpisodeView.episode_id == Episode.id)
        .where(EpisodeView.user_id == user_id, Episode.season_number > 0)
        .group_by(Episode.content_id)
        .subquery()
    )


def compute_progress(content: Content, tracking: Tracking | None, watched: int) -> Progress:
    if content.kind == ContentKind.MOVIE:
        # Un film n'a pas d'épisodes : il est vu quand son suivi est « terminé ».
        seen = tracking is not None and tracking.status == TrackingStatus.COMPLETED
        return Progress(watched=int(seen), total=1)
    return Progress(watched=watched, total=content.episodes_count)


async def get_progress(
    session: AsyncSession, user_id: int, content: Content, tracking: Tracking | None
) -> Progress:
    watched = await session.scalar(
        select(func.count())
        .select_from(EpisodeView)
        .join(Episode, EpisodeView.episode_id == Episode.id)
        .where(
            EpisodeView.user_id == user_id,
            Episode.content_id == content.id,
            Episode.season_number > 0,
        )
    )
    return compute_progress(content, tracking, watched or 0)


def _apply_status(tracking: Tracking, status: TrackingStatus) -> None:
    """Change le statut et tient à jour les dates de début et de fin."""
    if status in (TrackingStatus.WATCHING, TrackingStatus.COMPLETED) and not tracking.started_at:
        tracking.started_at = _now()
    if status == TrackingStatus.COMPLETED and tracking.status != TrackingStatus.COMPLETED:
        tracking.completed_at = _now()
    tracking.status = status


async def _get_or_create(
    session: AsyncSession, user_id: int, content_id: int, status: TrackingStatus
) -> Tracking:
    # ON CONFLICT DO NOTHING : deux requêtes simultanées ne créent pas de doublon.
    await session.execute(
        insert(Tracking)
        .values(user_id=user_id, content_id=content_id, status=TrackingStatus.PLANNED)
        .on_conflict_do_nothing(index_elements=["user_id", "content_id"])
    )
    tracking = await get_tracking(session, user_id, content_id)
    assert tracking is not None  # noqa: S101 (créé juste au-dessus)
    if tracking.status == TrackingStatus.PLANNED and status != TrackingStatus.PLANNED:
        _apply_status(tracking, status)
    return tracking


async def save_tracking(
    session: AsyncSession,
    user_id: int,
    content: Content,
    status: TrackingStatus,
    rating: int | None,
    review: str | None,
) -> tuple[Tracking, Rewards]:
    existing = await get_tracking(session, user_id, content.id)
    status_before = existing.status if existing else None
    tracking = await _get_or_create(session, user_id, content.id, status)
    _apply_status(tracking, status)
    tracking.rating = rating
    tracking.review = review
    await session.flush()
    # Même transaction : suivi et XP sont enregistrés ensemble, ou pas du tout.
    rewards = await gamification.on_status_changed(
        session, user_id, content, status_before, tracking.status
    )
    await session.commit()
    await session.refresh(tracking)
    return tracking, rewards


async def delete_tracking(session: AsyncSession, user_id: int, content: Content) -> None:
    """Retire le contenu du suivi ET oublie les épisodes cochés."""
    await session.execute(
        delete(Tracking).where(Tracking.user_id == user_id, Tracking.content_id == content.id)
    )
    await session.execute(
        delete(EpisodeView).where(
            EpisodeView.user_id == user_id,
            EpisodeView.episode_id.in_(select(Episode.id).where(Episode.content_id == content.id)),
        )
    )
    await gamification.forget_content(session, user_id, content.id)
    await session.commit()


async def watched_episode_ids(
    session: AsyncSession, user_id: int, episode_ids: list[int]
) -> set[int]:
    if not episode_ids:
        return set()
    rows = await session.scalars(
        select(EpisodeView.episode_id).where(
            EpisodeView.user_id == user_id, EpisodeView.episode_id.in_(episode_ids)
        )
    )
    return set(rows)


async def set_episodes_watched(
    session: AsyncSession,
    user_id: int,
    content: Content,
    episode_ids: list[int],
    watched: bool,
) -> tuple[Tracking | None, Rewards, list[int]]:
    """Coche ou décoche des épisodes, puis ajuste le statut automatiquement :
    - premier épisode coché → « en cours » ;
    - tous les épisodes d'une série terminée cochés → « terminé » ;
    - un épisode décoché sur un contenu « terminé » → « en cours ».
    """
    unique_ids = set(episode_ids)
    valid = set(
        await session.scalars(
            select(Episode.id).where(Episode.id.in_(unique_ids), Episode.content_id == content.id)
        )
    )
    # Protection : impossible de cocher les épisodes d'un autre contenu.
    if valid != unique_ids:
        raise EpisodeNotFoundError

    # RETURNING : on récupère les épisodes VRAIMENT changés (un épisode déjà
    # coché ne rapporte pas de points une seconde fois).
    if watched:
        changed = await session.scalars(
            insert(EpisodeView)
            .values([{"user_id": user_id, "episode_id": eid} for eid in sorted(valid)])
            .on_conflict_do_nothing()
            .returning(EpisodeView.episode_id)
        )
    else:
        changed = await session.scalars(
            delete(EpisodeView)
            .where(EpisodeView.user_id == user_id, EpisodeView.episode_id.in_(valid))
            .returning(EpisodeView.episode_id)
        )
    changed_ids = set(changed)

    tracking = await get_tracking(session, user_id, content.id)
    status_before = tracking.status if tracking else None
    if tracking is None and watched:
        tracking = await _get_or_create(session, user_id, content.id, TrackingStatus.WATCHING)

    if tracking is not None:
        progress = await get_progress(session, user_id, content, tracking)
        all_seen = progress.total is not None and progress.watched >= progress.total
        if watched and content.is_finished and all_seen:
            _apply_status(tracking, TrackingStatus.COMPLETED)
        elif watched and tracking.status != TrackingStatus.COMPLETED:
            _apply_status(tracking, TrackingStatus.WATCHING)
        elif not watched and tracking.status == TrackingStatus.COMPLETED and not all_seen:
            _apply_status(tracking, TrackingStatus.WATCHING)
        # Remonte le contenu en haut de « Mon suivi » (tri par activité récente).
        tracking.updated_at = _now()

    episodes = list(
        await session.scalars(
            select(Episode).where(Episode.id.in_(changed_ids)).order_by(Episode.number)
        )
    )
    rewards = await gamification.on_episodes_changed(
        session,
        user_id,
        content,
        episodes,
        watched,
        status_before,
        tracking.status if tracking else None,
    )
    await session.commit()
    if tracking is not None:
        await session.refresh(tracking)
    # Les épisodes réellement modifiés : permettent d'annuler l'action.
    return tracking, rewards, sorted(changed_ids)


async def episodes_until(
    session: AsyncSession,
    user_id: int,
    content: Content,
    season_number: int,
    episode_number: int,
    watched: bool,
) -> list[int]:
    """Épisodes à modifier pour « vu jusqu'ici » ou « pas vu à partir d'ici ».

    - watched=True : tous les épisodes NON vus avant ce point (saisons
      précédentes comprises) et celui-ci ;
    - watched=False : tous les épisodes VUS à partir de ce point (saisons
      suivantes comprises).
    Les épisodes spéciaux (saison 0) ne sont jamais concernés.
    """
    if watched:
        position = or_(
            Episode.season_number < season_number,
            and_(Episode.season_number == season_number, Episode.number <= episode_number),
        )
    else:
        position = or_(
            Episode.season_number > season_number,
            and_(Episode.season_number == season_number, Episode.number >= episode_number),
        )
    seen = select(EpisodeView.episode_id).where(EpisodeView.user_id == user_id)
    query = select(Episode.id).where(
        Episode.content_id == content.id,
        Episode.season_number > 0,
        position,
        Episode.id.in_(seen) if not watched else Episode.id.not_in(seen),
    )
    return list(await session.scalars(query))


async def list_trackings(
    session: AsyncSession, user_id: int, status: TrackingStatus | None
) -> list[tuple[Tracking, Content, Progress]]:
    counts = _watched_counts(user_id)
    query = (
        select(Tracking, Content, func.coalesce(counts.c.watched, 0))
        .join(Content, Content.id == Tracking.content_id)
        .outerjoin(counts, counts.c.content_id == Content.id)
        .where(Tracking.user_id == user_id)
        .order_by(Tracking.updated_at.desc(), Tracking.id.desc())
    )
    if status is not None:
        query = query.where(Tracking.status == status)
    rows = await session.execute(query)
    return [
        (tracking, content, compute_progress(content, tracking, watched))
        for tracking, content, watched in rows.tuples()
    ]
