"""Configuration de l'application, lue depuis les variables d'environnement.

Principe « 12-factor » : le même code tourne en développement, en recette
et en production ; seules les variables d'environnement changent. Aucun
secret n'est donc écrit en dur dans le code.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres validés par Pydantic : une valeur invalide fait échouer
    le démarrage immédiatement, plutôt qu'une erreur obscure plus tard."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SuperTracker"
    environment: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/supertracker"
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    """Renvoie toujours la même instance (lue une seule fois au démarrage)."""
    return Settings()
