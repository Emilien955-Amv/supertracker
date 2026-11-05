"""Points d'expérience (XP) et succès débloqués."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class XpEvent(Base):
    """Une ligne par gain d'XP : c'est un « registre », comme un relevé bancaire.

    Le total d'un joueur est la somme de ses lignes. La clé « key » décrit ce
    qui a été récompensé (ex. « episode:123 ») et elle est UNIQUE par joueur :
    impossible d'être récompensé deux fois pour la même chose, même en cliquant
    très vite ou en cochant/décochant en boucle.
    """

    __tablename__ = "xp_events"
    __table_args__ = (
        UniqueConstraint("user_id", "key"),
        # Accélère le calcul « XP gagnés aujourd'hui » (plafond quotidien, séries de jours).
        Index("ix_xp_events_user_id_day", "user_id", "day"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20))  # episode, movie, jour_j, badge…
    amount: Mapped[int] = mapped_column(Integer)
    content_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="SET NULL")
    )
    # Jour du gain à l'heure de Paris (minuit ici, pas minuit à Londres).
    day: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserBadge(Base):
    """Succès débloqué par un joueur (un seul exemplaire de chaque)."""

    __tablename__ = "user_badges"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
