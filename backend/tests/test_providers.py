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
from app.providers.base import CharacterRole, ContentKind, ProviderError, Source
from app.providers.tmdb import TmdbProvider
from app.providers.watch_links import search_url


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


# --- Où regarder (données JustWatch via TMDB) ---------------------------------

TMDB_FILM_AVEC_PLATEFORMES = {
    "id": 603,
    "title": "Matrix",
    "release_date": "1999-03-30",
    "runtime": 136,
    "status": "Released",
    "genres": [],
    "watch/providers": {
        "results": {
            "FR": {
                "link": "https://www.themoviedb.org/movie/603/watch?locale=FR",
                "flatrate": [
                    {"provider_name": "Max", "logo_path": "/max.png", "display_priority": 5},
                    {"provider_name": "Netflix", "logo_path": "/nf.png", "display_priority": 1},
                    {"provider_name": "Netflix Standard with Ads", "display_priority": 2},
                    {"provider_name": "Max Amazon Channel", "display_priority": 6},
                ],
                "rent": [{"provider_name": "Apple TV", "logo_path": "/apple.png"}],
                "ads": [{"provider_name": "Pluto TV", "display_priority": 2}],
                "free": [{"provider_name": "Pluto TV", "display_priority": 2}],
            },
            "US": {"flatrate": [{"provider_name": "Hulu"}]},
        }
    },
}


async def test_tmdb_plateformes_de_diffusion_en_france() -> None:
    requetes: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requetes.append(request)
        return httpx.Response(200, json=TMDB_FILM_AVEC_PLATEFORMES)

    async with faux_client(handler) as http:
        fiche = await TmdbProvider("jeton").get_detail(http, ContentKind.MOVIE, "603")

    assert fiche is not None and fiche.watch is not None
    # Un seul appel : fiche et plateformes demandées ensemble.
    assert len(requetes) == 1
    assert requetes[0].url.params["append_to_response"] == "watch/providers"

    watch = fiche.watch
    assert watch.region == "FR"
    assert watch.link == "https://www.themoviedb.org/movie/603/watch?locale=FR"
    # Triés par priorité, variantes (« with Ads », « Amazon Channel ») masquées.
    assert [p.name for p in watch.subscription] == ["Netflix", "Max"]
    assert watch.subscription[0].logo_url == "https://image.tmdb.org/t/p/w92/nf.png"
    # Lien direct vers la recherche Netflix ; « Max » n'est pas reconnu (None).
    assert watch.subscription[0].url == "https://www.netflix.com/search?q=Matrix"
    assert watch.subscription[1].url is None
    assert [p.name for p in watch.free] == ["Pluto TV"]  # doublon « ads »/« free » fusionné
    assert [p.name for p in watch.rent] == ["Apple TV"]
    assert watch.buy == []
    # Hulu n'est disponible qu'aux États-Unis : absent de la liste française.
    assert "Hulu" not in [p.name for p in watch.subscription]


async def test_tmdb_aucune_plateforme() -> None:
    sans = {**TMDB_FILM_AVEC_PLATEFORMES, "watch/providers": {"results": {}}}
    async with faux_client(lambda _: httpx.Response(200, json=sans)) as http:
        fiche = await TmdbProvider("jeton").get_detail(http, ContentKind.MOVIE, "603")

    assert fiche is not None and fiche.watch is not None
    assert fiche.watch.subscription == fiche.watch.rent == fiche.watch.buy == []
    assert fiche.watch.link is None


# --- Épisodes d'une saison ----------------------------------------------------


async def test_tmdb_episodes_d_une_saison() -> None:
    saison = {
        "episodes": [
            {
                "episode_number": 1,
                "name": "L'hiver vient",
                "air_date": "2011-04-17",
                "runtime": 62,
                "still_path": "/e1.jpg",
            },
            {"episode_number": 2, "name": "", "air_date": None, "still_path": None},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/3/tv/1399/season/1"
        return httpx.Response(200, json=saison)

    async with faux_client(handler) as http:
        episodes = await TmdbProvider("jeton").get_season(http, "1399", 1)

    assert episodes is not None
    assert [(e.number, e.title) for e in episodes] == [(1, "L'hiver vient"), (2, None)]
    assert episodes[0].still_url == "https://image.tmdb.org/t/p/w300/e1.jpg"
    assert episodes[0].air_date == date(2011, 4, 17)


async def test_tmdb_saison_inexistante() -> None:
    async with faux_client(lambda _: httpx.Response(404)) as http:
        assert await TmdbProvider("jeton").get_season(http, "1399", 99) is None


async def test_tmdb_serie_terminee() -> None:
    async with faux_client(lambda _: httpx.Response(200, json=TMDB_SERIE)) as http:
        fiche = await TmdbProvider("jeton").get_detail(http, ContentKind.SERIES, "1399")
    assert fiche is not None
    assert fiche.is_finished


async def test_anilist_anime_en_cours_compte_les_episodes_diffuses() -> None:
    # One Piece : pas de total, mais le prochain épisode à paraître est le 1150.
    media = {**ANILIST_MEDIA, "nextAiringEpisode": {"episode": 1150}}
    async with faux_client(lambda _: httpx.Response(200, json={"data": {"Media": media}})) as http:
        fiche = await AniListProvider().get_detail(http, ContentKind.ANIME, "21")
        episodes = await AniListProvider().get_season(http, "21", 1)
        autre_saison = await AniListProvider().get_season(http, "21", 2)

    assert fiche is not None
    assert fiche.episodes_count == 1149
    assert not fiche.is_finished
    assert [(s.number, s.episode_count) for s in fiche.seasons] == [(1, 1149)]
    assert episodes is not None
    assert len(episodes) == 1149
    assert (episodes[0].number, episodes[-1].number) == (1, 1149)
    assert autre_saison is None  # AniList n'a qu'une « saison »


def test_lien_de_recherche_encode_le_titre() -> None:
    assert search_url("Crunchyroll", "One Piece") == (
        "https://www.crunchyroll.com/fr/search?q=One%20Piece"
    )
    assert search_url("Apple TV", "Amélie & co") == (
        "https://tv.apple.com/fr/search?term=Am%C3%A9lie%20%26%20co"
    )
    assert search_url("Disney Plus", "Matrix") is None  # pas de lien vérifié : page des offres


# --- Personnages (cartes) -----------------------------------------------------


async def test_tmdb_personnages_classes_par_importance() -> None:
    casting = {
        "cast": [
            {"order": 1, "character": "Morpheus", "name": "L. Fishburne", "profile_path": "/m.jpg"},
            {"order": 0, "character": "Neo", "name": "K. Reeves", "profile_path": "/n.jpg"},
            {"order": 2, "character": "Sans photo", "name": "X", "profile_path": None},
            {"order": 3, "character": "", "name": "Sans rôle", "profile_path": "/x.jpg"},
        ]
        + [
            {"order": 10 + i, "character": f"Rôle {i}", "name": "Y", "profile_path": f"/{i}.jpg"}
            for i in range(20)
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/3/movie/603/credits"
        return httpx.Response(200, json=casting)

    async with faux_client(handler) as http:
        persos = await TmdbProvider("jeton").get_characters(http, ContentKind.MOVIE, "603")

    assert len(persos) == 15  # les 15 plus importants seulement
    assert (persos[0].name, persos[0].role) == ("Neo", CharacterRole.HERO)
    assert persos[0].image_url == "https://image.tmdb.org/t/p/h632/n.jpg"
    assert (persos[1].name, persos[1].role) == ("Morpheus", CharacterRole.MAIN)
    # Personnages sans photo ou sans nom : ignorés (pas de carte vide).
    assert "Sans photo" not in [p.name for p in persos]
    assert persos[-1].role == CharacterRole.BACKGROUND


async def test_anilist_personnages_premier_role_principal_devient_heros() -> None:
    def edge(nom: str, role: str, image: str = "https://img/x.png") -> dict[str, object]:
        return {
            "role": role,
            "node": {"name": {"full": nom}, "image": {"large": image}},
        }

    reponse = {
        "data": {
            "Media": {
                "characters": {
                    "edges": [
                        edge("Luffy", "MAIN"),
                        edge("Zoro", "MAIN"),
                        edge("Anonyme", "SUPPORTING", "https://s4.anilist.co/default.jpg"),
                        edge("Koby", "SUPPORTING"),
                    ]
                }
            }
        }
    }
    async with faux_client(lambda _: httpx.Response(200, json=reponse)) as http:
        persos = await AniListProvider().get_characters(http, ContentKind.ANIME, "21")

    assert [(p.name, p.role) for p in persos] == [
        ("Luffy", CharacterRole.HERO),
        ("Zoro", CharacterRole.MAIN),
        ("Koby", CharacterRole.SUPPORTING),  # image par défaut : ignoré
    ]
