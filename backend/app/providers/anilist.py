"""Source AniList : animes. Gratuite et sans clé d'API.

AniList utilise GraphQL : au lieu de plusieurs adresses, une seule, à laquelle
on envoie une requête décrivant exactement les champs voulus.
Documentation : https://docs.anilist.co
"""

import re
from datetime import date
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
)

API_URL = "https://graphql.anilist.co"

_CHAMPS_COMMUNS = """
  id
  title { romaji english native }
  startDate { year month day }
  coverImage { large extraLarge }
  description(asHtml: false)
"""

EPISODES_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    episodes
    nextAiringEpisode { episode }
  }
}
"""

CHARACTERS_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    characters(sort: [ROLE, RELEVANCE, ID], perPage: 40) {
      edges {
        role
        node { name { full } image { large } }
      }
    }
  }
}
"""

# Rôles AniList → importance de la carte (le premier rôle principal devient le héros).
ANILIST_ROLES = {
    "MAIN": CharacterRole.MAIN,
    "SUPPORTING": CharacterRole.SUPPORTING,
    "BACKGROUND": CharacterRole.BACKGROUND,
}
MAX_CHARACTERS = 25
POPULAR_PAGES = 3  # 3 × 50 animes les plus populaires
# Seconds rôles : les 4 premiers sont Rares, les 6 suivants « récurrents ».
SUPPORTING_RARE = 4
SUPPORTING_RECURRING = 6

POPULAR_QUERY = f"""
query ($page: Int) {{
  Page(page: $page, perPage: 50) {{
    media(type: ANIME, isAdult: false, sort: POPULARITY_DESC) {{
      {_CHAMPS_COMMUNS}
      bannerImage
      siteUrl
      externalLinks {{ site type }}
    }}
  }}
}}
"""

SEARCH_QUERY = f"""
query ($search: String) {{
  Page(perPage: 20) {{
    media(search: $search, type: ANIME, isAdult: false, sort: SEARCH_MATCH) {{
      {_CHAMPS_COMMUNS}
    }}
  }}
}}
"""

DETAIL_QUERY = f"""
query ($id: Int) {{
  Media(id: $id, type: ANIME) {{
    {_CHAMPS_COMMUNS}
    bannerImage
    endDate {{ year month day }}
    genres
    episodes
    nextAiringEpisode {{ episode }}
    duration
    status
    siteUrl
  }}
}}
"""

STATUTS = {
    "FINISHED": "Terminé",
    "RELEASING": "En cours de diffusion",
    "NOT_YET_RELEASED": "À venir",
    "CANCELLED": "Annulé",
    "HIATUS": "En pause",
}

GENRES = {
    "Action": "Action",
    "Adventure": "Aventure",
    "Comedy": "Comédie",
    "Drama": "Drame",
    "Ecchi": "Ecchi",
    "Fantasy": "Fantastique",
    "Horror": "Horreur",
    "Mahou Shoujo": "Magical girl",
    "Mecha": "Mecha",
    "Music": "Musique",
    "Mystery": "Mystère",
    "Psychological": "Psychologique",
    "Romance": "Romance",
    "Sci-Fi": "Science-fiction",
    "Slice of Life": "Tranche de vie",
    "Sports": "Sport",
    "Supernatural": "Surnaturel",
    "Thriller": "Thriller",
}


def _clean_description(text: str | None) -> str | None:
    """Les descriptions AniList contiennent des balises (<br>, <i>…) : on les
    retire pour n'afficher que du texte brut."""
    if not text:
        return None
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() or None


def _date(value: dict[str, Any] | None) -> date | None:
    if not value or not value.get("year"):
        return None
    try:
        return date(value["year"], value.get("month") or 1, value.get("day") or 1)
    except ValueError:
        return None


def _aired_episodes(media: dict[str, Any]) -> int | None:
    """Nombre d'épisodes déjà diffusés.

    Pour un anime en cours (ex. One Piece), AniList ne donne pas de total
    (« episodes » vaut null) mais indique le prochain épisode à paraître.
    """
    if media.get("episodes"):
        return int(media["episodes"])
    upcoming = (media.get("nextAiringEpisode") or {}).get("episode")
    return int(upcoming) - 1 if upcoming and upcoming > 1 else None


def _title(media: dict[str, Any]) -> tuple[str, str | None]:
    titles = media.get("title") or {}
    # Le titre anglais est souvent le plus connu en France ; sinon, le romaji.
    title = titles.get("english") or titles.get("romaji") or "Sans titre"
    original = titles.get("native") or titles.get("romaji")
    return title, original if original != title else None


class AniListProvider:
    source = Source.ANILIST

    async def _query(
        self, http: httpx.AsyncClient, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            response = await http.post(API_URL, json={"query": query, "variables": variables})
        except httpx.HTTPError as exc:
            raise ProviderError(f"AniList injoignable : {exc}") from exc
        if response.status_code == 404:
            return {}
        if response.status_code != 200:
            raise ProviderError(f"AniList a répondu {response.status_code}")
        data: dict[str, Any] = response.json().get("data") or {}
        return data

    def _result(self, media: dict[str, Any]) -> SearchResult:
        title, original = _title(media)
        cover = media.get("coverImage") or {}
        return SearchResult(
            source=Source.ANILIST,
            kind=ContentKind.ANIME,
            external_id=str(media["id"]),
            title=title,
            original_title=original,
            year=(media.get("startDate") or {}).get("year"),
            poster_url=cover.get("large"),
            overview=_clean_description(media.get("description")),
        )

    async def search(self, http: httpx.AsyncClient, query: str) -> list[SearchResult]:
        data = await self._query(http, SEARCH_QUERY, {"search": query})
        return [self._result(media) for media in (data.get("Page") or {}).get("media", [])]

    async def get_detail(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> ContentDetail | None:
        if kind != ContentKind.ANIME or not external_id.isdigit():
            return None
        media = (await self._query(http, DETAIL_QUERY, {"id": int(external_id)})).get("Media")
        if not media:
            return None

        base = self._result(media)
        cover = media.get("coverImage") or {}
        aired = _aired_episodes(media)
        return ContentDetail(
            **base.model_dump(exclude={"poster_url"}),
            poster_url=cover.get("extraLarge") or cover.get("large"),
            backdrop_url=media.get("bannerImage"),
            genres=[GENRES.get(genre, genre) for genre in media.get("genres", [])],
            release_date=_date(media.get("startDate")),
            end_date=_date(media.get("endDate")),
            runtime_minutes=media.get("duration"),
            status=STATUTS.get(media.get("status", ""), media.get("status")),
            episodes_count=aired,
            # AniList n'a pas de saisons : une saison unique regroupe les épisodes.
            seasons=[SeasonSummary(number=1, name="Épisodes", episode_count=aired)]
            if aired
            else [],
            source_url=media.get("siteUrl") or f"https://anilist.co/anime/{media['id']}",
            is_finished=media.get("status") in ("FINISHED", "CANCELLED"),
        )

    async def get_season(
        self, http: httpx.AsyncClient, external_id: str, season_number: int
    ) -> list[EpisodeSummary] | None:
        if season_number != 1 or not external_id.isdigit():
            return None
        media = (await self._query(http, EPISODES_QUERY, {"id": int(external_id)})).get("Media")
        if not media:
            return None
        # AniList ne fournit ni titre ni image par épisode : seulement les numéros.
        return [
            EpisodeSummary(season_number=1, number=number)
            for number in range(1, (_aired_episodes(media) or 0) + 1)
        ]

    async def get_characters(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> list[CharacterSummary]:
        if kind != ContentKind.ANIME or not external_id.isdigit():
            return []
        data = await self._query(http, CHARACTERS_QUERY, {"id": int(external_id)})
        edges = (((data.get("Media") or {}).get("characters")) or {}).get("edges") or []
        characters: list[CharacterSummary] = []
        hero_given = False
        supporting = 0
        for edge in edges:
            node = edge.get("node") or {}
            name = ((node.get("name") or {}).get("full") or "").strip()
            image = (node.get("image") or {}).get("large")
            # Image par défaut d'AniList (silhouette grise) : considérée comme absente.
            if not name or not image or "default.jpg" in image:
                continue
            role = ANILIST_ROLES.get(edge.get("role", ""), CharacterRole.BACKGROUND)
            if role == CharacterRole.MAIN and not hero_given:
                role, hero_given = CharacterRole.HERO, True
            elif role == CharacterRole.SUPPORTING:
                supporting += 1
                if supporting > SUPPORTING_RARE + SUPPORTING_RECURRING:
                    role = CharacterRole.BACKGROUND
                elif supporting > SUPPORTING_RARE:
                    role = CharacterRole.RECURRING
            characters.append(
                CharacterSummary(
                    name=name[:200],
                    image_url=image,
                    role=role,
                    order=len(characters),
                )
            )
            if len(characters) >= MAX_CHARACTERS:
                break
        return characters

    async def get_popular(self, http: httpx.AsyncClient, kind: ContentKind) -> list[ContentDetail]:
        if kind != ContentKind.ANIME:
            return []
        medias: list[dict[str, Any]] = []
        for page in range(1, POPULAR_PAGES + 1):
            data = await self._query(http, POPULAR_QUERY, {"page": page})
            medias += (data.get("Page") or {}).get("media", [])
        items = []
        for media in medias:
            base = self._result(media)
            cover = media.get("coverImage") or {}
            items.append(
                ContentDetail(
                    **base.model_dump(exclude={"poster_url"}),
                    poster_url=cover.get("extraLarge") or cover.get("large"),
                    backdrop_url=media.get("bannerImage"),
                    source_url=media.get("siteUrl") or f"https://anilist.co/anime/{media['id']}",
                    streaming_sites=[
                        link["site"]
                        for link in media.get("externalLinks") or []
                        if link.get("type") == "STREAMING" and link.get("site")
                    ],
                )
            )
        return items

    async def find_anime(self, http: httpx.AsyncClient, title: str) -> ContentDetail | None:
        """Retrouve un anime par son titre (japonais ou traduit). Sert à relier
        les catalogues Crunchyroll et ADN (connus de TMDB) aux fiches AniList."""
        results = await self.search(http, title)
        if not results:
            return None
        best = results[0]
        return ContentDetail(
            **best.model_dump(),
            source_url=f"https://anilist.co/anime/{best.external_id}",
        )
