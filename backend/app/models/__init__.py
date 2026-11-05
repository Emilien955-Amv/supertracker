"""Modèles de données.

Chaque nouveau modèle doit être importé ici : c'est ce qui permet à
Alembic de le « voir » pour générer automatiquement les migrations.
"""

from app.db import Base
from app.models.refresh_token import RefreshToken
from app.models.user import User

__all__ = ["Base", "RefreshToken", "User"]
