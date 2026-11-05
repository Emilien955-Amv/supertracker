"""Suivi d'un contenu par un utilisateur, et épisodes vus."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TrackingStatus(StrEnum):
    PLANNED = "planned"  # à voir
    WATCHING = "watching"  # en cours
    COMPLETED = "completed"  # terminé
    PAUSED = "paused"  # en pause
    DROPPED = "dropped"  # abandonné


class Tracking(Base):
    __tablename__ = "trackings"
    __table_args__ = (
        # Un utilisateur suit un contenu une seule fois.
        UniqueConstraint("user_id", "content_id"),
        # Garde-fous côté base, en plus de la validation de l'API.
        CheckConstraint("rating BETWEEN 1 AND 10", name="rating_range"),
        CheckConstraint(
            "status IN ('planned', 'watching', 'completed', 'paused', 'dropped')",
            name="status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    rating: Mapped[int | None] = mapped_column(SmallInteger)  # note sur 10
    review: Mapped[str | None] = mapped_column(Text)  # avis personnel
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EpisodeView(Base):
    """Un épisode coché « vu ». La clé primaire double interdit les doublons."""

    __tablename__ = "episode_views"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    episode_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("episodes.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # Servira aux points d'expérience de l'étape 2 (bonus « Jour J », séries…).
    watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
