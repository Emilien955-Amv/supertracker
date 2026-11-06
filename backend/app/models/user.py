"""Table des utilisateurs (utilisée par l'authentification à l'étape 1)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Identity, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    # Identifiant auto-incrémenté géré par PostgreSQL (norme SQL « IDENTITY »).
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    # 320 caractères : longueur maximale théorique d'une adresse e-mail.
    # L'e-mail sera toujours enregistré en minuscules par l'application,
    # ce qui rend l'unicité insensible à la casse.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    username: Mapped[str] = mapped_column(String(30), unique=True)

    # On ne stocke JAMAIS le mot de passe, seulement son empreinte Argon2id.
    password_hash: Mapped[str] = mapped_column(String(255))

    avatar_url: Mapped[str | None] = mapped_column(String(500))
    # Petite présentation affichée sur le profil (facultative).
    bio: Mapped[str | None] = mapped_column(String(300))

    # Profil privé par défaut (protection des données dès la conception, RGPD).
    is_public: Mapped[bool] = mapped_column(Boolean, server_default=false())

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
