"""Modèles de données.

Chaque nouveau modèle doit être importé ici : c'est ce qui permet à
Alembic de le « voir » pour générer automatiquement les migrations.
"""

from app.db import Base
from app.models.card import (
    Booster,
    BoosterCard,
    Card,
    CardKind,
    CardWallet,
    ContentPlatform,
    Rarity,
    UserCard,
)
from app.models.content import Content, Episode
from app.models.gamification import UserBadge, XpEvent
from app.models.library import Library, LibraryItem, SortMode, ViewMode
from app.models.refresh_token import RefreshToken
from app.models.tracking import EpisodeView, Tracking, TrackingStatus
from app.models.user import User

__all__ = [
    "Base",
    "Booster",
    "BoosterCard",
    "Card",
    "CardKind",
    "CardWallet",
    "Content",
    "ContentPlatform",
    "Episode",
    "EpisodeView",
    "Library",
    "LibraryItem",
    "Rarity",
    "RefreshToken",
    "SortMode",
    "Tracking",
    "TrackingStatus",
    "User",
    "UserBadge",
    "UserCard",
    "ViewMode",
    "XpEvent",
]
