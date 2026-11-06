"""Formats d'échange du suivi (entrées validées, sorties documentées)."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import TrackingStatus
from app.providers.base import ContentKind, Source
from app.schemas.gamification import RewardsRead
from app.services.tracking import Progress


class ContentRead(BaseModel):
    """Résumé d'un contenu enregistré dans notre base."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source: Source
    kind: ContentKind
    external_id: str
    title: str
    year: int | None
    poster_url: str | None
    episodes_count: int | None


class TrackingWrite(BaseModel):
    status: TrackingStatus
    rating: int | None = Field(None, ge=1, le=10, description="Note sur 10")
    # strip_whitespace : un avis composé uniquement d'espaces devient vide.
    review: Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None = None


class TrackingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: TrackingStatus
    rating: int | None
    review: str | None
    started_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime


class ProgressRead(BaseModel):
    watched: int
    total: int | None
    percent: int | None

    @classmethod
    def of(cls, progress: Progress) -> "ProgressRead":
        return cls(watched=progress.watched, total=progress.total, percent=progress.percent)


class ContentState(BaseModel):
    """Où en est l'utilisateur sur un contenu."""

    content_id: int | None = Field(description="Identifiant interne (None : jamais enregistré)")
    tracking: TrackingRead | None
    progress: ProgressRead
    # Récompenses de l'action qui vient d'avoir lieu (absent en simple lecture).
    rewards: RewardsRead | None = None
    # Épisodes que l'action vient de modifier (pour pouvoir l'annuler).
    changed_episode_ids: list[int] = []


class TrackedItem(BaseModel):
    content: ContentRead
    tracking: TrackingRead
    progress: ProgressRead


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_number: int
    number: int
    title: str | None
    air_date: date | None
    runtime_minutes: int | None
    still_url: str | None
    watched: bool = False


class WatchedUntilWrite(BaseModel):
    """« Vu jusqu'ici » (watched=True) ou « pas vu à partir d'ici » (False)."""

    season_number: int = Field(ge=1, le=500)
    episode_number: int = Field(ge=1, le=100_000)
    watched: bool


class EpisodesWatchedWrite(BaseModel):
    # 2 000 au maximum : de quoi cocher d'un coup la plus longue des saisons.
    episode_ids: list[int] = Field(min_length=1, max_length=2000)
    watched: bool
