"""Source TMDB (The Movie Database) : films et séries.

Documentation : https://developer.themoviedb.org/reference
Mention obligatoire (conditions d'utilisation) : l'application doit indiquer
qu'elle utilise l'API TMDB sans être approuvée ni certifiée par TMDB.
"""

from typing import Any

import httpx

from app.providers.base import (
    CharacterRole,
    CharacterSummary,
    ContentDetail,
    ContentKind,
    EpisodeSummary,
    ProviderError,
    SearchResult,
    SeasonSummary,
    Source,
    WatchAvailability,
    WatchProvider,
    parse_date,
)
from app.providers.watch_links import search_url

API_URL = "https://api.themoviedb.org/3"
IMAGE_URL = "https://image.tmdb.org/t/p"

VARIANT_SUFFIXES = (" Amazon Channel", " with Ads")

# TMDB renvoie les statuts en anglais, même en demandant le français.
STATUTS = {
    "Released": "Sorti",
    "Post Production": "En post-production",
    "In Production": "En production",
    "Planned": "Prévu",
    "Rumored": "Annoncé",
    "Canceled": "Annulé",
    "Returning Series": "En cours",
    "Ended": "Terminée",
    "Pilot": "Pilote",
}


def _image(path: str | None, size: str) -> str | None:
    # « w342 » : largeur de 342 px, suffisante pour une affiche sur mobile.
    return f"{IMAGE_URL}/{size}{path}" if path else None


def _year(value: str | None) -> int | None:
    parsed = parse_date(value)
    return parsed.year if parsed else None


# Contenus populaires : 2 pages de 20 par type, renouvelées chaque jour.
POPULAR_PAGES = 2
ANIMATION_GENRE = 16  # identifiant du genre « Animation » chez TMDB

# On garde les 15 personnages les plus importants : au-delà, ce sont des
# apparitions qui rempliraient la collection de cartes sans intérêt.
MAX_CHARACTERS = 15


def _role_from_order(order: int) -> CharacterRole:
    """TMDB classe le casting par importance (« order ») : 0 = premier rôle."""
    if order == 0:
        return CharacterRole.HERO
    if order <= 3:
        return CharacterRole.MAIN
    if order <= 9:
        return CharacterRole.SUPPORTING
    return CharacterRole.BACKGROUND


class TmdbProvider:
    source = Source.TMDB

    def __init__(self, token: str, region: str = "FR") -> None:
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        self._region = region

    async def _get(self, http: httpx.AsyncClient, path: str, **params: str) -> dict[str, Any]:
        try:
            response = await http.get(
                f"{API_URL}{path}",
                params={"language": "fr-FR", **params},
                headers=self._headers,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"TMDB injoignable : {exc}") from exc
        if response.status_code == 404:
            return {}
        if response.status_code != 200:
            raise ProviderError(f"TMDB a répondu {response.status_code}")
        data: dict[str, Any] = response.json()
        return data

    async def search(self, http: httpx.AsyncClient, query: str) -> list[SearchResult]:
        # « multi » cherche à la fois dans les films, les séries et les personnes.
        data = await self._get(http, "/search/multi", query=query, include_adult="false")
        results = []
        for item in data.get("results", []):
            media_type = item.get("media_type")
            if media_type not in ("movie", "tv"):
                continue  # on ignore les personnes (acteurs, réalisateurs)
            is_movie = media_type == "movie"
            results.append(
                SearchResult(
                    source=Source.TMDB,
                    kind=ContentKind.MOVIE if is_movie else ContentKind.SERIES,
                    external_id=str(item["id"]),
                    title=item.get("title" if is_movie else "name") or "Sans titre",
                    original_title=item.get("original_title" if is_movie else "original_name"),
                    year=_year(item.get("release_date" if is_movie else "first_air_date")),
                    poster_url=_image(item.get("poster_path"), "w342"),
                    overview=item.get("overview") or None,
                )
            )
        return results

    async def get_detail(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> ContentDetail | None:
        # « append_to_response » : la fiche ET les plateformes de diffusion en
        # un seul appel, au lieu de deux.
        extra = {"append_to_response": "watch/providers"}
        if kind == ContentKind.MOVIE:
            data = await self._get(http, f"/movie/{external_id}", **extra)
            return self._movie(data) if data else None
        if kind == ContentKind.SERIES:
            data = await self._get(http, f"/tv/{external_id}", **extra)
            return self._series(data) if data else None
        return None

    async def get_season(
        self, http: httpx.AsyncClient, external_id: str, season_number: int
    ) -> list[EpisodeSummary] | None:
        data = await self._get(http, f"/tv/{external_id}/season/{season_number}")
        if not data:
            return None
        return [
            EpisodeSummary(
                season_number=season_number,
                number=episode["episode_number"],
                title=episode.get("name") or None,
                air_date=parse_date(episode.get("air_date")),
                runtime_minutes=episode.get("runtime") or None,
                # « w300 » : vignette suffisante pour la liste des épisodes.
                still_url=_image(episode.get("still_path"), "w300"),
            )
            for episode in data.get("episodes", [])
            if isinstance(episode.get("episode_number"), int)
        ]

    async def get_characters(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> list[CharacterSummary]:
        # Pour une série, « aggregate_credits » regroupe toutes les saisons.
        if kind == ContentKind.MOVIE:
            data = await self._get(http, f"/movie/{external_id}/credits")
        elif kind == ContentKind.SERIES:
            data = await self._get(http, f"/tv/{external_id}/aggregate_credits")
        else:
            return []
        characters: list[CharacterSummary] = []
        for item in sorted(data.get("cast", []), key=lambda c: c.get("order", 999)):
            roles = item.get("roles") or [{}]
            name = (item.get("character") or roles[0].get("character") or "").strip()
            photo = item.get("profile_path")
            # Données manquantes (pas de nom de personnage ou pas de photo) :
            # pas de carte, plutôt qu'une carte vide.
            if not name or not photo:
                continue
            order = len(characters)
            characters.append(
                CharacterSummary(
                    name=name[:200],
                    # « h632 » : photo haute, au format d'une carte.
                    image_url=f"{IMAGE_URL}/h632{photo}",
                    role=_role_from_order(order),
                    order=order,
                )
            )
            if len(characters) >= MAX_CHARACTERS:
                break
        return characters

    async def get_popular(self, http: httpx.AsyncClient, kind: ContentKind) -> list[ContentDetail]:
        if kind not in (ContentKind.MOVIE, ContentKind.SERIES):
            return []
        is_movie = kind == ContentKind.MOVIE
        path = "/movie/popular" if is_movie else "/tv/popular"
        items: list[ContentDetail] = []
        for page in range(1, POPULAR_PAGES + 1):
            data = await self._get(http, path, page=str(page), region=self._region)
            for item in data.get("results", []):
                # Les animes japonais viennent d'AniList (pack « Animes ») :
                # on les retire des séries TMDB pour éviter les doublons.
                if (
                    not is_movie
                    and ANIMATION_GENRE in item.get("genre_ids", [])
                    and (item.get("original_language") == "ja")
                ):
                    continue
                title = item.get("title" if is_movie else "name") or "Sans titre"
                items.append(
                    ContentDetail(
                        source=Source.TMDB,
                        kind=kind,
                        external_id=str(item["id"]),
                        title=title,
                        original_title=item.get("original_title" if is_movie else "original_name"),
                        year=_year(item.get("release_date" if is_movie else "first_air_date")),
                        poster_url=_image(item.get("poster_path"), "w500"),
                        backdrop_url=_image(item.get("backdrop_path"), "w1280"),
                        overview=item.get("overview") or None,
                        source_url=f"https://www.themoviedb.org/{path.split('/')[1]}/{item['id']}",
                    )
                )
        return items

    def _watch(self, data: dict[str, Any], title: str) -> WatchAvailability:
        """Plateformes disponibles dans le pays choisi.

        Ces données viennent de JustWatch, partenaire de TMDB : la mention
        « JustWatch » doit être affichée à côté (conditions d'utilisation).
        """
        offers = ((data.get("watch/providers") or {}).get("results") or {}).get(self._region) or {}

        def providers(*keys: str) -> list[WatchProvider]:
            items = [item for key in keys for item in offers.get(key, [])]
            items.sort(key=lambda item: item.get("display_priority", 999))
            seen: set[str] = set()
            result = []
            for item in items:
                name = item.get("provider_name")
                if name and name not in seen:  # « ads » et « free » peuvent se recouper
                    seen.add(name)
                    result.append(
                        WatchProvider(
                            name=name,
                            logo_url=_image(item.get("logo_path"), "w92"),
                            url=search_url(name, title),
                        )
                    )
            # Variantes d'une même offre (« Netflix Standard with Ads »,
            # « Crunchyroll Amazon Channel »…) : on les masque s'il reste
            # d'autres plateformes, pour garder une liste lisible.
            if len(result) > 1:
                result = [p for p in result if not p.name.endswith(VARIANT_SUFFIXES)] or result
            return result

        return WatchAvailability(
            region=self._region,
            link=offers.get("link"),
            subscription=providers("flatrate"),
            free=providers("free", "ads"),
            rent=providers("rent"),
            buy=providers("buy"),
        )

    def _movie(self, data: dict[str, Any]) -> ContentDetail:
        title = data.get("title") or "Sans titre"
        return ContentDetail(
            source=Source.TMDB,
            kind=ContentKind.MOVIE,
            external_id=str(data["id"]),
            title=title,
            original_title=data.get("original_title"),
            year=_year(data.get("release_date")),
            poster_url=_image(data.get("poster_path"), "w500"),
            backdrop_url=_image(data.get("backdrop_path"), "w1280"),
            overview=data.get("overview") or None,
            genres=[genre["name"] for genre in data.get("genres", [])],
            release_date=parse_date(data.get("release_date")),
            runtime_minutes=data.get("runtime") or None,
            status=STATUTS.get(data.get("status", ""), data.get("status")),
            source_url=f"https://www.themoviedb.org/movie/{data['id']}",
            is_finished=data.get("status") == "Released",
            watch=self._watch(data, title),
        )

    def _series(self, data: dict[str, Any]) -> ContentDetail:
        title = data.get("name") or "Sans titre"
        run_times = data.get("episode_run_time") or []
        seasons = [
            SeasonSummary(
                number=season["season_number"],
                name=season.get("name") or f"Saison {season['season_number']}",
                episode_count=season.get("episode_count"),
                air_date=parse_date(season.get("air_date")),
                poster_url=_image(season.get("poster_path"), "w342"),
            )
            for season in data.get("seasons", [])
        ]
        return ContentDetail(
            source=Source.TMDB,
            kind=ContentKind.SERIES,
            external_id=str(data["id"]),
            title=title,
            original_title=data.get("original_name"),
            year=_year(data.get("first_air_date")),
            poster_url=_image(data.get("poster_path"), "w500"),
            backdrop_url=_image(data.get("backdrop_path"), "w1280"),
            overview=data.get("overview") or None,
            genres=[genre["name"] for genre in data.get("genres", [])],
            release_date=parse_date(data.get("first_air_date")),
            end_date=parse_date(data.get("last_air_date"))
            if data.get("status") == "Ended"
            else None,
            runtime_minutes=run_times[0] if run_times else None,
            status=STATUTS.get(data.get("status", ""), data.get("status")),
            seasons_count=data.get("number_of_seasons"),
            episodes_count=data.get("number_of_episodes"),
            # La « saison 0 » regroupe les épisodes spéciaux : on la place à la fin.
            seasons=sorted(seasons, key=lambda s: (s.number == 0, s.number)),
            source_url=f"https://www.themoviedb.org/tv/{data['id']}",
            is_finished=data.get("status") in ("Ended", "Canceled"),
            watch=self._watch(data, title),
        )
