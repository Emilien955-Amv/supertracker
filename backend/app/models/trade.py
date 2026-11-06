"""Échanges de cartes entre amis."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TradeStatus(StrEnum):
    PENDING = "pending"  # en attente de réponse
    ACCEPTED = "accepted"  # cartes échangées
    DECLINED = "declined"  # refusé par le destinataire
    CANCELLED = "cancelled"  # annulé par celui qui l'a proposé


class Trade(Base):
    """Une proposition : « je te donne ces cartes contre celles-là »."""

    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("proposer_id <> recipient_id", name="not_self"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'cancelled')", name="status_valid"
        ),
        Index("ix_trades_recipient_id_status", "recipient_id", "status"),
        Index("ix_trades_proposer_id_status", "proposer_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    proposer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    recipient_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(10), server_default=TradeStatus.PENDING.value)
    message: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TradeItem(Base):
    """Une carte de l'échange. from_proposer : donnée par celui qui propose
    (sinon : demandée au destinataire)."""

    __tablename__ = "trade_items"

    trade_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trades.id", ondelete="CASCADE"), primary_key=True
    )
    card_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True
    )
    from_proposer: Mapped[bool] = mapped_column(Boolean, primary_key=True)
