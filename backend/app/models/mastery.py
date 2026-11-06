"""Maîtrises : œuvres dont un joueur possède toutes les cartes."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Mastery(Base):
    """Une collection complète : elle rapporte la carte « Maître », un titre de
    profil, des XP, des boosters et compte pour les succès de collectionneur."""

    __tablename__ = "masteries"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
