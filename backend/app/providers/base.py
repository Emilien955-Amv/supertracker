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


class EpisodeSummary(BaseModel):
    season_number: int
    number: int
    title: str | None = None
    air_date: date | None = None
    runtime_minutes: int | None = None
    still_url: str | None = Field(default=None, description="Image tirée de l'épisode")


class CharacterRole(StrEnum):
    """Importance d'un personnage : elle détermine la rareté de sa carte."""

    HERO = "hero"  # LE personnage principal (premier rôle)
    MAIN = "main"  # rôles principaux
    SUPPORTING = "supporting"  # seconds rôles
    RECURRING = "recurring"  # personnages récurrents
    BACKGROUND = "background"  # petits rôles


class CharacterSummary(BaseModel):
    # Uniquement le personnage : ni acteur, ni doubleur, ni réalisateur.
    name: str
    image_url: str
    role: CharacterRole
    order: int = Field(description="Rang d'importance (0 = le plus important)")


class WatchProvider(BaseModel):
    name: str
    logo_url: str | None = None
    # Lien vers le titre sur la plateforme (None : plateforme non reconnue).
    url: str | None = None


class WatchAvailability(BaseModel):
    """Où regarder un contenu dans un pays donné (données JustWatch via TMDB)."""

    region: str = Field(description="Code pays ISO, ex. « FR »")
    link: str | None = Field(None, description="Page récapitulant toutes les offres")
    subscription: list[WatchProvider] = Field([], description="Inclus dans un abonnement")
    free: list[WatchProvider] = Field([], description="Gratuit, avec ou sans publicités")
    rent: list[WatchProvider] = Field([], description="Location")
    buy: list[WatchProvider] = Field([], description="Achat")


class ContentDetail(SearchResult):
    backdrop_url: str | None = None
    genres: list[str] = []
    release_date: date | None = None
    end_date: date | None = None
    runtime_minutes: int | None = Field(default=None, description="Durée du film ou d'un épisode")
    status: str | None = None
    seasons_count: int | None = None
    episodes_count: int | None = None
    seasons: list[SeasonSummary] = []
    source_url: str = Field(description="Page du contenu sur le site de la source")
    # Plus aucun épisode ne sortira (série terminée ou annulée, film sorti) :
    # permet de passer automatiquement le suivi à « terminé ».
    is_finished: bool = False
    # Sites de streaming signalés par la source (ex. « Crunchyroll », « Netflix »).
    streaming_sites: list[str] = []
    # None : la source ne fournit pas cette information (ex. AniList).
    watch: WatchAvailability | None = None


class ProviderError(Exception):
    """La source est injoignable ou a répondu de façon inattendue."""


class MetadataProvider(Protocol):
    """Contrat que chaque source doit respecter."""

    source: Source

    async def search(self, http: httpx.AsyncClient, query: str) -> list[SearchResult]: ...

    async def get_detail(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> ContentDetail | None: ...

    async def get_season(
        self, http: httpx.AsyncClient, external_id: str, season_number: int
    ) -> list[EpisodeSummary] | None:
        """Épisodes d'une saison ; None si la saison n'existe pas."""
        ...

    async def get_characters(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> list[CharacterSummary]:
        """Personnages avec une image (ceux sans image sont ignorés)."""
        ...

    async def get_popular(self, http: httpx.AsyncClient, kind: ContentKind) -> list[ContentDetail]:
        """Contenus populaires du moment (fiches simplifiées), pour le catalogue
        de cartes. Liste vide si la source ne gère pas ce type."""
        ...


def parse_date(value: str | None) -> date | None:
    """Convertit « 2026-11-05 » en date ; renvoie None si vide ou invalide."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
