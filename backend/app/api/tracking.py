"""Routes du suivi : statut, note, avis, épisodes vus.

Un contenu est désigné comme dans le catalogue : /{source}/{kind}/{external_id}
(ex. /tmdb/series/1399). Il est copié dans notre base à la première action.
"""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Response, status

from app.api.deps import CurrentUser, ExternalId, HttpDep, ProvidersDep, SessionDep
from app.core.rate_limit import enforce_rate_limit
from app.models import Content, TrackingStatus
from app.providers.base import ContentKind, ProviderError, Source
from app.schemas.gamification import RewardsRead
from app.schemas.tracking import (
    ContentRead,
    ContentState,
    EpisodeRead,
    EpisodesWatchedWrite,
    ProgressRead,
    TrackedItem,
    TrackingRead,
    TrackingWrite,
    WatchedUntilWrite,
)
from app.services import catalog
from app.services import content as content_service
from app.services import tracking as tracking_service
from app.services.gamification import Rewards

router = APIRouter(prefix="/tracking", tags=["Suivi"])

CONTENT_PATH = "/{source}/{kind}/{external_id}"
ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"description": "Contenu ou épisode introuvable"},
    502: {"description": "Source indisponible"},
}


async def _load_content(
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    user_id: int,
    source: Source,
    kind: ContentKind,
    external_id: str,
) -> Content:
    """Contenu copié en base (créé au besoin), avec les erreurs HTTP adaptées."""
    # Chaque écriture peut déclencher un appel à TMDB : on limite le rythme.
    await enforce_rate_limit(f"write:{user_id}", limit=120, window_seconds=60)
    try:
        return await content_service.ensure_content(
            session, http, providers, source, kind, external_id
        )
    except content_service.ContentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contenu introuvable.") from None
    except ProviderError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "La source de données ne répond pas. Réessayez dans un instant.",
        ) from None


async def _state(
    session: SessionDep, user_id: int, content: Content, rewards: Rewards | None = None
) -> ContentState:
    tracking = await tracking_service.get_tracking(session, user_id, content.id)
    progress = await tracking_service.get_progress(session, user_id, content, tracking)
    return ContentState(
        content_id=content.id,
        tracking=TrackingRead.model_validate(tracking) if tracking else None,
        progress=ProgressRead.of(progress),
        rewards=RewardsRead.of(rewards) if rewards else None,
    )


@router.get("", summary="Mon suivi (du plus récemment actif au plus ancien)")
async def list_my_trackings(
    user: CurrentUser,
    session: SessionDep,
    status_filter: Annotated[TrackingStatus | None, Query(alias="status")] = None,
) -> list[TrackedItem]:
    rows = await tracking_service.list_trackings(session, user.id, status_filter)
    return [
        TrackedItem(
            content=ContentRead.model_validate(content),
            tracking=TrackingRead.model_validate(tracking),
            progress=ProgressRead.of(progress),
        )
        for tracking, content, progress in rows
    ]


@router.get(CONTENT_PATH, summary="Où j'en suis sur un contenu")
async def get_state(
    user: CurrentUser,
    session: SessionDep,
    source: Source,
    kind: ContentKind,
    external_id: ExternalId,
) -> ContentState:
    # Lecture seule : on ne copie pas le contenu juste parce qu'on consulte sa fiche.
    content = await content_service.find_content(session, source, kind, external_id)
    if content is None:
        return ContentState(
            content_id=None,
            tracking=None,
            progress=ProgressRead(watched=0, total=None, percent=0),
        )
    return await _state(session, user.id, content)


@router.put(CONTENT_PATH, summary="Ajouter au suivi ou modifier statut, note et avis")
async def save_tracking(
    user: CurrentUser,
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    source: Source,
    kind: ContentKind,
    external_id: ExternalId,
    body: TrackingWrite,
) -> ContentState:
    content = await _load_content(session, http, providers, user.id, source, kind, external_id)
    _, rewards = await tracking_service.save_tracking(
        session, user.id, content, body.status, body.rating, body.review or None
    )
    changed: list[int] = []
    if body.status == TrackingStatus.COMPLETED and kind != ContentKind.MOVIE:
        # « Terminé » : tous les épisodes déjà diffusés sont cochés.
        last = await _sync_seasons(session, http, providers, content, source, kind, external_id)
        ids = await tracking_service.episodes_until(
            session, user.id, content, last, 1_000_000, watched=True, aired_only=True
        )
        if ids:
            _, more, changed = await tracking_service.set_episodes_watched(
                session, user.id, content, ids, True
            )
            rewards = rewards.merge(more)
    state = await _state(session, user.id, content, rewards)
    return state.model_copy(update={"changed_episode_ids": changed})


async def _sync_seasons(
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    content: Content,
    source: Source,
    kind: ContentKind,
    external_id: str,
    up_to: int | None = None,
) -> int:
    """Copie les épisodes des saisons 1 à « up_to » (toutes par défaut) depuis
    la source. Renvoie le numéro de la dernière saison copiée."""
    try:
        detail = await catalog.get_detail(http, providers, source, kind, external_id)
        numbers = sorted(
            s.number
            for s in (detail.seasons if detail else [])
            if s.number > 0 and (up_to is None or s.number <= up_to)
        )
        for number in numbers:
            await content_service.ensure_season(session, http, providers, content, number)
    except (ProviderError, content_service.ContentNotFoundError):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "La source de données ne répond pas. Réessayez dans un instant.",
        ) from None
    return numbers[-1] if numbers else 0


@router.delete(CONTENT_PATH, status_code=status.HTTP_204_NO_CONTENT, summary="Retirer de mon suivi")
async def delete_tracking(
    user: CurrentUser,
    session: SessionDep,
    source: Source,
    kind: ContentKind,
    external_id: ExternalId,
) -> Response:
    content = await content_service.find_content(session, source, kind, external_id)
    if content is not None:
        await tracking_service.delete_tracking(session, user.id, content)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    CONTENT_PATH + "/seasons/{season_number}",
    summary="Épisodes d'une saison, avec ceux déjà vus",
    responses=ERRORS,
)
async def list_episodes(
    user: CurrentUser,
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    source: Source,
    kind: ContentKind,
    external_id: ExternalId,
    season_number: Annotated[int, Path(ge=0, le=500)],
) -> list[EpisodeRead]:
    if kind == ContentKind.MOVIE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Un film n'a pas d'épisodes.")
    content = await _load_content(session, http, providers, user.id, source, kind, external_id)
    try:
        episodes = await content_service.ensure_season(
            session, http, providers, content, season_number
        )
    except content_service.ContentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Saison introuvable.") from None
    except ProviderError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "La source de données ne répond pas. Réessayez dans un instant.",
        ) from None
    seen = await tracking_service.watched_episode_ids(session, user.id, [e.id for e in episodes])
    return [
        EpisodeRead.model_validate(episode).model_copy(update={"watched": episode.id in seen})
        for episode in episodes
    ]


@router.post(
    CONTENT_PATH + "/episodes",
    summary="Cocher ou décocher des épisodes « vus »",
    responses=ERRORS,
)
async def mark_episodes(
    user: CurrentUser,
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    source: Source,
    kind: ContentKind,
    external_id: ExternalId,
    body: EpisodesWatchedWrite,
) -> ContentState:
    content = await _load_content(session, http, providers, user.id, source, kind, external_id)
    try:
        _, rewards, changed = await tracking_service.set_episodes_watched(
            session, user.id, content, body.episode_ids, body.watched
        )
    except tracking_service.EpisodeNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Épisode introuvable.") from None
    state = await _state(session, user.id, content, rewards)
    return state.model_copy(update={"changed_episode_ids": changed})


@router.post(
    CONTENT_PATH + "/watched-until",
    summary="Vu jusqu'ici (saisons précédentes comprises) ou pas vu à partir d'ici",
    responses=ERRORS,
)
async def mark_until(
    user: CurrentUser,
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    source: Source,
    kind: ContentKind,
    external_id: ExternalId,
    body: WatchedUntilWrite,
) -> ContentState:
    if kind == ContentKind.MOVIE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Un film n'a pas d'épisodes.")
    content = await _load_content(session, http, providers, user.id, source, kind, external_id)
    if body.watched:
        # Les saisons précédentes n'ont peut-être jamais été ouvertes : on
        # copie leurs épisodes depuis la source avant de les cocher.
        await _sync_seasons(
            session, http, providers, content, source, kind, external_id, body.season_number
        )
    ids = await tracking_service.episodes_until(
        session, user.id, content, body.season_number, body.episode_number, body.watched
    )
    if not ids:
        return await _state(session, user.id, content)
    _, rewards, changed = await tracking_service.set_episodes_watched(
        session, user.id, content, ids, body.watched
    )
    state = await _state(session, user.id, content, rewards)
    return state.model_copy(update={"changed_episode_ids": changed})
