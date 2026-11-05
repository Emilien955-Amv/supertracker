"""Liste des sources actives, selon la configuration."""

from app.config import get_settings
from app.providers.anilist import AniListProvider
from app.providers.base import MetadataProvider
from app.providers.tmdb import TmdbProvider


def get_providers() -> list[MetadataProvider]:
    """Dépendance FastAPI : les sources à interroger (remplaçable en test)."""
    providers: list[MetadataProvider] = []
    token = get_settings().tmdb_api_token
    if token:
        providers.append(TmdbProvider(token))
    providers.append(AniListProvider())  # sans clé : toujours disponible
    return providers
