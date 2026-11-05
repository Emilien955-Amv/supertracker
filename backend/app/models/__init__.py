"""Modèles de données.

Chaque nouveau modèle doit être importé ici : c'est ce qui permet à
Alembic de le « voir » pour générer automatiquement les migrations.
"""

from app.db import Base
from app.models.content import Content, Episode
from app.models.gamification import UserBadge, XpEvent
from app.models.library import Library, LibraryItem, SortMode, ViewMode
from app.models.refresh_token import RefreshToken
from app.models.tracking import EpisodeView, Tracking, TrackingStatus
from app.models.user import User

__all__ = [
    "Base",
    "Content",
    "Episode",
    "EpisodeView",
    "Library",
    "LibraryItem",
    "RefreshToken",
    "SortMode",
    "Tracking",
    "TrackingStatus",
    "User",
    "UserBadge",
    "ViewMode",
    "XpEvent",
]
