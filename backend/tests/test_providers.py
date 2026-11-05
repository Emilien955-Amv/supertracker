"""Tests des sources de données, avec de fausses réponses HTTP.

httpx.MockTransport intercepte les requêtes : aucun appel ne part sur
internet, les tests sont rapides, gratuits et toujours reproductibles.
"""

import json
from collections.abc import Callable
from datetime import date

import httpx
import pytest

from app.providers.anilist import AniListProvider
from app.providers.base import ContentKind, ProviderError, Source
from app.providers.tmdb import TmdbProvider


def faux_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- TMDB --------------------------------------------------------------------

TMDB_RECHERCHE = {
    "results": [
        {
            "id": 603,
            "media_type": "movie",
            "title": "Matrix",
            "original_title": "The Matrix",
            "release_date": "1999-03-30",
            "poster_path": "/matrix.jpg",
            "overview": "Un pirate informatique découvre la vérité.",
        },
        {"id": 6384, "media_type": "person", "name": "Keanu Reeves"},
        {
            "id": 1399,
            "media_type": "tv",
            "name": "Game of Thrones",
            "original_name": "Game of Thrones",
            "first_air_date": "2011-04-17",
            "poster_path": None,
            "overview": "",
        },
    ]
}

TMDB_SERIE = {
    "id": 1399,
    "name": "Game of Thrones",
    "original_name": "Game of Thrones",
    "first_air_date": "2011-04-17",
    "last_air_date": "2019-05-19",
    "status": "Ended",
    "episode_run_time": [60],
    "genres": [{"id": 18, "name": "Drame"}],
    "number_of_seasons": 8,
    "number_of_episodes": 73,
    "poster_path": "/got.jpg",
    "backdrop_path": "/got-fond.jpg",
    "overview": "Neuf familles nobles…",
    "seasons": [
        {"season_number": 0, "name": "Épisodes spéciaux", "episode_count": 17},
        {"season_number": 1, "name": "Saison 1", "episode_count": 10, "air_date": "2011-04-17"},
    ],
}


async def test_tmdb_recherche_garde_films_et_series() -> None:
    requetes: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requetes.append(request)
        return httpx.Response(200, json=TMDB_RECHERCHE)

    async with faux_client(handler) as http:
        resultats = await TmdbProvider("jeton").search(http, "matrix")

    assert [(r.kind, r.title) for r in resultats] == [
        (ContentKind.MOVIE, "Matrix"),
        (ContentKind.SERIES, "Game of Thrones"),
    ]  # la personne (Keanu Reeves) est ignorée
    assert resultats[0].year == 1999
    assert resultats[0].poster_url == "https://image.tmdb.org/t/p/w342/matrix.jpg"
    assert resultats[1].poster_url is None and resultats[1].overview is None
    # Résultats demandés en français, jeton transmis dans l'en-tête.
    assert requetes[0].url.params["language"] == "fr-FR"
    assert requetes[0].headers["Authorization"] == "Bearer jeton"


async def test_tmdb_fiche_serie() -> None:
    async with faux_client(lambda _: httpx.Response(200, json=TMDB_SERIE)) as http:
        fiche = await TmdbProvider("jeton").get_detail(http, ContentKind.SERIES, "1399")

    assert fiche is not None
    assert fiche.status == "Terminée"
    assert fiche.end_date == date(2019, 5, 19)
    assert fiche.runtime_minutes == 60
    assert (fiche.seasons_count, fiche.episodes_count) == (8, 73)
    # Les épisodes spéciaux (saison 0) passent en fin de liste.
    assert [s.number for s in fiche.seasons] == [1, 0]
    assert fiche.source_url == "https://www.themoviedb.org/tv/1399"


async def test_tmdb_contenu_inexistant() -> None:
    async with faux_client(lambda _: httpx.Response(404, json={})) as http:
        assert await TmdbProvider("jeton").get_detail(http, ContentKind.MOVIE, "999") is None


async def test_tmdb_en_panne_leve_une_erreur() -> None:
    async with faux_client(lambda _: httpx.Response(503)) as http:
        with pytest.raises(ProviderError):
            await TmdbProvider("jeton").search(http, "matrix")


async def test_tmdb_injoignable_leve_une_erreur() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("réseau coupé", request=request)

    async with faux_client(handler) as http:
        with pytest.raises(ProviderError):
            await TmdbProvider("jeton").search(http, "matrix")


# --- AniList -----------------------------------------------------------------

ANILIST_MEDIA = {
    "id": 21,
    "title": {"romaji": "ONE PIECE", "english": "One Piece", "native": "ONE PIECE"},
    "startDate": {"year": 1999, "month": 10, "day": 20},
    "endDate": {"year": None},
    "coverImage": {"large": "https://img/moyen.jpg", "extraLarge": "https://img/grand.jpg"},
    "bannerImage": "https://img/banniere.jpg",
    "description": "Gold Roger était <i>le roi des pirates</i>.<br><br><br>Fin.",
    "genres": ["Action", "Adventure", "Comedy", "Genre inconnu"],
    "episodes": None,
    "duration": 24,
    "status": "RELEASING",
    "siteUrl": "https://anilist.co/anime/21",
}


async def test_anilist_recherche() -> None:
    corps: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        corps.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"Page": {"media": [ANILIST_MEDIA]}}})

    async with faux_client(handler) as http:
        resultats = await AniListProvider().search(http, "one piece")

    assert len(resultats) == 1
    anime = resultats[0]
    assert (anime.source, anime.kind, anime.external_id) == (
        Source.ANILIST,
        ContentKind.ANIME,
        "21",
    )
    assert anime.title == "One Piece"
    assert anime.original_title == "ONE PIECE"  # titre japonais d'origine
    assert corps[0]["variables"] == {"search": "one piece"}


async def test_anilist_fiche_nettoie_et_traduit() -> None:
    reponse = {"data": {"Media": ANILIST_MEDIA}}
    async with faux_client(lambda _: httpx.Response(200, json=reponse)) as http:
        fiche = await AniListProvider().get_detail(http, ContentKind.ANIME, "21")

    assert fiche is not None
    assert fiche.overview == "Gold Roger était le roi des pirates.\n\nFin."  # balises retirées
    assert fiche.genres == ["Action", "Aventure", "Comédie", "Genre inconnu"]
    assert fiche.status == "En cours de diffusion"
    assert fiche.release_date == date(1999, 10, 20)
    assert fiche.end_date is None
    assert fiche.poster_url == "https://img/grand.jpg"  # la plus grande image
    assert fiche.runtime_minutes == 24


async def test_anilist_refuse_un_autre_type() -> None:
    async with faux_client(lambda _: httpx.Response(500)) as http:
        # Aucun appel réseau : AniList ne gère que les animes.
        assert await AniListProvider().get_detail(http, ContentKind.MOVIE, "21") is None
