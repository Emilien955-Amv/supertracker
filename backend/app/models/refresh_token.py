"""Jetons de renouvellement (un par appareil connecté)."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    # ondelete="CASCADE" : supprimer un utilisateur supprime ses jetons (RGPD).
    # index=True : on retrouve vite tous les jetons d'un utilisateur.
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Empreinte SHA-256 du jeton (64 caractères hexadécimaux), jamais le jeton lui-même.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Renseigné quand le jeton est utilisé (rotation) ou à la déconnexion.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
