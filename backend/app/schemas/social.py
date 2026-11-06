"""Formats d'échange du social (amis et profils)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models import Rarity
from app.schemas.gamification import BadgeBrief
from app.services.social import Relation


class PublicUser(BaseModel):
    """Ce que tout le monde voit d'un utilisateur : son pseudo, rien d'autre."""

    username: str
    avatar_url: str | None
    relation: Relation


class RarityCount(BaseModel):
    rarity: Rarity
    count: int


class ProfileStatsRead(BaseModel):
    level: int
    xp: int
    episodes: int
    movies: int
    series_completed: int
    cards: int
    top_cards: list[RarityCount]  # Légendaires, Mythiques, Divines
    badges: list[BadgeBrief]


class ProfileRead(BaseModel):
    username: str
    avatar_url: str | None
    relation: Relation
    # False : profil privé et pas amis → ni présentation ni statistiques.
    visible: bool
    is_public: bool
    bio: str | None = None
    member_since: datetime | None = None
    stats: ProfileStatsRead | None = None


class FriendsRead(BaseModel):
    friends: list[PublicUser]
    incoming: list[PublicUser]  # demandes reçues, à accepter ou refuser
    outgoing: list[PublicUser]  # demandes envoyées, en attente


class ProfileUpdate(BaseModel):
    """Modification partielle du profil : seuls les champs envoyés changent."""

    bio: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    is_public: bool | None = None
