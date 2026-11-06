"""Demandes d'ajout au catalogue de cartes, et votes des joueurs."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RequestStatus(StrEnum):
    OPEN = "open"  # en attente de votes
    ADDED = "added"  # ajoutée au catalogue de cartes


class WorkRequest(Base):
    """« Je veux les cartes de Frieren ! » : une demande par œuvre."""

    __tablename__ = "work_requests"
    __table_args__ = (
        UniqueConstraint("source", "kind", "external_id"),
        CheckConstraint("status IN ('open', 'added')", name="status_valid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    poster_url: Mapped[str | None] = mapped_column(String(500))
    year: Mapped[int | None] = mapped_column(SmallInteger)
    requested_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(10), server_default=RequestStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkRequestVote(Base):
    """Un vote par joueur et par demande."""

    __tablename__ = "work_request_votes"

    request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("work_requests.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
