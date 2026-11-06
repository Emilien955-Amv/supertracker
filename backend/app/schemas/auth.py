"""Schémas Pydantic : forme exacte des données reçues et renvoyées par l'API.

Toute requête qui ne respecte pas ces règles est rejetée automatiquement
avec une erreur 422, avant même d'atteindre notre code.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Lettres sans accent, chiffres et « _ », de 3 à 30 caractères.
USERNAME_PATTERN = r"^[A-Za-z0-9_]{3,30}$"
PASSWORD_MIN_LENGTH = 10
# Plafond : évite qu'un mot de passe géant ne monopolise le serveur (Argon2).
PASSWORD_MAX_LENGTH = 128


class RegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=320, examples=["emilien@exemple.fr"])
    username: str = Field(pattern=USERNAME_PATTERN, examples=["emilien"])
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        examples=["un-mot-de-passe-solide"],
    )

    @field_validator("email")
    @classmethod
    def _email_en_minuscules(cls, value: str) -> str:
        # « Emilien@Exemple.fr » et « emilien@exemple.fr » sont le même compte.
        return value.lower()


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def _email_en_minuscules(cls, value: str) -> str:
        return value.lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 (pas un secret)
    expires_in: int = Field(description="Durée de validité du jeton, en secondes")


class UserRead(BaseModel):
    """Ce que l'API révèle d'un utilisateur : jamais l'empreinte du mot de passe."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    avatar_url: str | None
    bio: str | None
    is_public: bool
    created_at: datetime
