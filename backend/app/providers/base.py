"""Interface commune à toutes les sources de métadonnées.

Chaque source (TMDB, AniList, et plus tard Open Library, IGDB…) traduit ses
propres réponses vers CES modèles. Le reste de l'application ne connaît donc
qu'un seul format : ajouter une source ne demande aucune refonte.
"""

from datetime import date
from enum import StrEnum
from typing import Protocol

import httpx
from pydantic import BaseModel, Field


class Source(StrEnum):
    TMDB = "tmdb"
    ANILIST = "anilist"


class ContentKind(StrEnum):
    MOVIE = "movie"
    SERIES = "series"
    ANIME = "anime"


class SearchResult(BaseModel):
    source: Source
    kind: ContentKind
    external_id: str = Field(description="Identifiant chez la source (ex. « 603 » chez TMDB)")
    title: str
    original_title: str | None = None
    year: int | None = None
    poster_url: str | None = None
    overview: str | None = None


class SeasonSummary(BaseModel):
    number: int
    name: str
    episode_count: int | None = None
    air_date: date | None = None
    poster_url: str | None = None


class ContentDetail(SearchResult):
    backdrop_url: str | None = None
    genres: list[str] = []
    release_date: date | None = None
    end_date: date | None = None
    runtime_minutes: int | None = Field(None, description="Durée du film ou d'un épisode")
    status: str | None = None
    seasons_count: int | None = None
    episodes_count: int | None = None
    seasons: list[SeasonSummary] = []
    source_url: str = Field(description="Page du contenu sur le site de la source")


class ProviderError(Exception):
    """La source est injoignable ou a répondu de façon inattendue."""


class MetadataProvider(Protocol):
    """Contrat que chaque source doit respecter."""

    source: Source

    async def search(self, http: httpx.AsyncClient, query: str) -> list[SearchResult]: ...

    async def get_detail(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> ContentDetail | None: ...


def parse_date(value: str | None) -> date | None:
    """Convertit « 2026-11-05 » en date ; renvoie None si vide ou invalide."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
