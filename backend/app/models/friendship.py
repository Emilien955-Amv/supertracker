"""Amitiés entre utilisateurs : une demande, puis son acceptation."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FriendStatus(StrEnum):
    PENDING = "pending"  # demande envoyée, pas encore acceptée
    ACCEPTED = "accepted"  # amis


class Friendship(Base):
    """« requester » a demandé « addressee » en ami.

    Une seule ligne par paire, quel que soit le sens : un index unique sur
    (plus petit id, plus grand id) empêche d'avoir à la fois A→B et B→A.
    """

    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("requester_id <> addressee_id", name="not_self"),
        CheckConstraint("status IN ('pending', 'accepted')", name="status_valid"),
        Index(
            "uq_friendships_pair",
            text("least(requester_id, addressee_id)"),
            text("greatest(requester_id, addressee_id)"),
            unique=True,
        ),
        Index("ix_friendships_addressee_id", "addressee_id"),
    )

    requester_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    addressee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(10), server_default=FriendStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
