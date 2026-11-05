"""Tests des routes du catalogue, avec de fausses sources (Redis requis pour le cache)."""

from collections.abc import AsyncIterator

import httpx
import pytest
from httpx import AsyncClient

from app.api.deps import get_current_user
from app.cache import redis_client
from app.http_client import get_http_client
from app.main import app
from app.models import User
from app.providers.base import (
    ContentDetail,
    ContentKind,
    ProviderError,
    SearchResult,
    Source,
)
from app.providers.registry import get_providers
from app.services.catalog import CACHE_PREFIX, normalize_query
from tests.conftest import vider_cache_catalogue

pytestmark = pytest.mark.integration


def resultat(source: Source, titre: str) -> SearchResult:
    kind = ContentKind.ANIME if source == Source.ANILIST else ContentKind.MOVIE
    return SearchResult(source=source, kind=kind, external_id="1", title=titre)


class FausseSource:
    """Source simulée : réponses prévues à l'avance et compteur d'appels."""

    def __init__(self, source: Source, titres: list[str], en_panne: bool = False) -> None:
        self.source = source
        self.titres = titres
        self.en_panne = en_panne
        self.appels = 0

    async def search(self, http: httpx.AsyncClient, query: str) -> list[SearchResult]:
        self.appels += 1
        if self.en_panne:
            raise ProviderError("source en panne")
        return [resultat(self.source, titre) for titre in self.titres]

    async def get_detail(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> ContentDetail | None:
        self.appels += 1
        if self.en_panne:
            raise ProviderError("source en panne")
        if external_id != "603":
            return None
        return ContentDetail(
            **resultat(self.source, "Matrix").model_dump(exclude={"external_id"}),
            external_id="603",
            source_url="https://exemple.fr/603",
        )


@pytest.fixture
async def catalogue(client: AsyncClient) -> AsyncIterator[dict[str, FausseSource]]:
    """Utilisateur connecté simulé et sources contrôlées par le test."""
    sources = {
        "tmdb": FausseSource(Source.TMDB, ["Film A", "Film B", "Film C"]),
        "anilist": FausseSource(Source.ANILIST, ["Anime A"]),
    }
    await vider_cache_catalogue()
    keys = [k async for k in redis_client.scan_iter("ratelimit:*")]
    if keys:
        await redis_client.delete(*keys)

    app.dependency_overrides[get_current_user] = lambda: User(id=1, username="test")
    app.dependency_overrides[get_providers] = lambda: list(sources.values())
    app.dependency_overrides[get_http_client] = lambda: None
    try:
        yield sources
    finally:
        for dependency in (get_current_user, get_providers, get_http_client):
            app.dependency_overrides.pop(dependency, None)
        await vider_cache_catalogue()


async def test_recherche_fusionne_en_alternance(
    client: AsyncClient, catalogue: dict[str, FausseSource]
) -> None:
    response = await client.get("/api/catalog/search", params={"q": "Matrix"})

    assert response.status_code == 200
    titres = [r["title"] for r in response.json()["results"]]
    assert titres == ["Film A", "Anime A", "Film B", "Film C"]
    assert response.json()["unavailable_sources"] == []


async def test_recherche_tolere_une_source_en_panne(
    client: AsyncClient, catalogue: dict[str, FausseSource]
) -> None:
    catalogue["anilist"].en_panne = True

    response = await client.get("/api/catalog/search", params={"q": "Matrix"})

    assert response.status_code == 200
    assert len(response.json()["results"]) == 3
    assert response.json()["unavailable_sources"] == ["anilist"]


async def test_recherche_mise_en_cache(
    client: AsyncClient, catalogue: dict[str, FausseSource]
) -> None:
    await client.get("/api/catalog/search", params={"q": "Matrix"})
    # Même recherche, casse et espaces différents : servie par le cache.
    await client.get("/api/catalog/search", params={"q": "  MATRIX "})

    assert catalogue["tmdb"].appels == 1
    assert await redis_client.exists(f"{CACHE_PREFIX}search:tmdb:matrix")


@pytest.mark.parametrize("q", ["a", "x" * 101])
async def test_recherche_longueur_invalide(
    client: AsyncClient, catalogue: dict[str, FausseSource], q: str
) -> None:
    assert (await client.get("/api/catalog/search", params={"q": q})).status_code == 422


async def test_recherche_reservee_aux_comptes_connectes(client: AsyncClient) -> None:
    assert (await client.get("/api/catalog/search", params={"q": "Matrix"})).status_code == 401


async def test_fiche_detaillee(client: AsyncClient, catalogue: dict[str, FausseSource]) -> None:
    response = await client.get("/api/catalog/tmdb/movie/603")

    assert response.status_code == 200
    assert response.json()["title"] == "Matrix"


async def test_fiche_introuvable(client: AsyncClient, catalogue: dict[str, FausseSource]) -> None:
    assert (await client.get("/api/catalog/tmdb/movie/404")).status_code == 404


@pytest.mark.parametrize("chemin", ["tmdb/movie/abc", "tmdb/livre/603", "imdb/movie/603"])
async def test_fiche_parametres_invalides(
    client: AsyncClient, catalogue: dict[str, FausseSource], chemin: str
) -> None:
    assert (await client.get(f"/api/catalog/{chemin}")).status_code == 422


async def test_fiche_source_en_panne(
    client: AsyncClient, catalogue: dict[str, FausseSource]
) -> None:
    catalogue["tmdb"].en_panne = True
    assert (await client.get("/api/catalog/tmdb/movie/603")).status_code == 502


def test_normalisation_de_la_recherche() -> None:
    assert normalize_query("  One   PIECE ") == "one piece"
