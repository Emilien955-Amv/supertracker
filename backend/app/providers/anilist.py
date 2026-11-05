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
    ContentDetail,
    ContentKind,
    ProviderError,
    SearchResult,
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
        return ContentDetail(
            **base.model_dump(exclude={"poster_url"}),
            poster_url=cover.get("extraLarge") or cover.get("large"),
            backdrop_url=media.get("bannerImage"),
            genres=[GENRES.get(genre, genre) for genre in media.get("genres", [])],
            release_date=_date(media.get("startDate")),
            end_date=_date(media.get("endDate")),
            runtime_minutes=media.get("duration"),
            status=STATUTS.get(media.get("status", ""), media.get("status")),
            episodes_count=media.get("episodes"),
            source_url=media.get("siteUrl") or f"https://anilist.co/anime/{media['id']}",
        )
