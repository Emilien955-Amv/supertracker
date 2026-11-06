"""Source AniList : animes. Gratuite et sans clé d'API.

AniList utilise GraphQL : au lieu de plusieurs adresses, une seule, à laquelle
on envoie une requête décrivant exactement les champs voulus.
Documentation : https://docs.anilist.co
"""

import asyncio
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

# Liens avec les autres œuvres (suites, films…) : sert à regrouper les
# saisons d'un même anime, qu'AniList enregistre comme des œuvres séparées.
_RELATIONS = """
  format
  relations { edges { relationType node { id type format } } }
"""

SEASON_QUERY = f"""
query ($id: Int) {{
  Media(id: $id, type: ANIME) {{
    id
    title {{ romaji english native }}
    episodes
    nextAiringEpisode {{ episode }}
    status
    startDate {{ year month day }}
    endDate {{ year month day }}
    coverImage {{ large }}
    {_RELATIONS}
  }}
}}
"""

CHARACTERS_QUERY = """
query ($id: Int, $page: Int) {
  Media(id: $id, type: ANIME) {
    characters(sort: [ROLE, RELEVANCE, ID], page: $page, perPage: 25) {
      pageInfo { hasNextPage }
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
MAX_CHARACTERS = 300  # le plus possible : jusqu'à 12 pages de 25
POPULAR_PAGES = 4  # 4 × 50 animes les plus populaires (avant regroupement)
MAX_SEASONS = 20
# Seconds rôles : les 6 premiers sont Rares, les 15 suivants « récurrents ».
SUPPORTING_RARE = 6
SUPPORTING_RECURRING = 15
# Formats « série » : une suite de ce format est une nouvelle saison.
SERIES_FORMATS = ("TV", "TV_SHORT", "ONA")
ALL_FORMATS = ("TV", "TV_SHORT", "ONA", "MOVIE", "OVA", "SPECIAL", "MUSIC")

POPULAR_QUERY = f"""
query ($page: Int) {{
  Page(page: $page, perPage: 50) {{
    media(type: ANIME, isAdult: false, sort: POPULARITY_DESC) {{
      {_CHAMPS_COMMUNS}
      bannerImage
      siteUrl
      externalLinks {{ site type }}
      {_RELATIONS}
    }}
  }}
}}
"""

SEARCH_QUERY = f"""
query ($search: String) {{
  Page(perPage: 20) {{
    media(search: $search, type: ANIME, isAdult: false, sort: SEARCH_MATCH) {{
      {_CHAMPS_COMMUNS}
      {_RELATIONS}
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
    {_RELATIONS}
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


def _linked(media: dict[str, Any], relation: str, formats: tuple[str, ...]) -> list[int]:
    """Identifiants des animes liés par « relation » (ex. SEQUEL) et d'un des formats."""
    edges = (media.get("relations") or {}).get("edges") or []
    return [
        edge["node"]["id"]
        for edge in edges
        if edge.get("relationType") == relation
        and (edge.get("node") or {}).get("type") == "ANIME"
        and edge["node"].get("format") in formats
    ]


def is_main_entry(media: dict[str, Any]) -> bool:
    """Vrai si l'anime est une œuvre « principale » à montrer seule.

    - une série TV est principale si aucune série TV ne la précède (sinon
      c'est une saison 2, 3… regroupée avec la première) et si ce n'est pas
      une série dérivée d'une autre (ex. « Attack on Titan: Junior High ») ;
      un court épisode web avant elle ne compte pas (cas de One Piece) ;
    - une série web (ONA) suit la même règle, toute série la précédant comptant ;
    - un film, un épisode spécial ou un résumé lié à un autre anime n'est pas
      montré seul (« Your Name », sans lien, l'est).
    """
    fmt = media.get("format")
    if fmt in ("TV", "TV_SHORT"):
        return not (
            _linked(media, "PREQUEL", ("TV", "TV_SHORT"))
            or _linked(media, "PARENT", SERIES_FORMATS)
        )
    if fmt == "ONA":
        return not (
            _linked(media, "PREQUEL", SERIES_FORMATS) or _linked(media, "PARENT", SERIES_FORMATS)
        )
    return not any(
        _linked(media, relation, ALL_FORMATS)
        for relation in (
            "PREQUEL",
            "SEQUEL",
            "PARENT",
            "SIDE_STORY",
            "SUMMARY",
            "COMPILATION",
            "ALTERNATIVE",
            "SPIN_OFF",
        )
    )


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
        for attempt in range(3):
            try:
                response = await http.post(API_URL, json={"query": query, "variables": variables})
            except httpx.HTTPError as exc:
                raise ProviderError(f"AniList injoignable : {exc}") from exc
            # 429 : AniList demande de ralentir. On attend le délai indiqué
            # (au plus une minute) puis on réessaie, deux fois au maximum.
            if response.status_code != 429 or attempt == 2:
                break
            delay = min(60, int(response.headers.get("Retry-After", "10") or 10))
            await asyncio.sleep(delay)
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
        medias = (data.get("Page") or {}).get("media", [])
        # Une seule entrée par anime : les saisons 2, 3… et les films rattachés
        # sont regroupés avec la série. (Si la recherche ne trouve QUE des
        # suites, on les montre quand même.)
        main = [media for media in medias if is_main_entry(media)] or medias
        return [self._result(media) for media in main]

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
        chain = await self._seasons(http, media)
        seasons = [
            SeasonSummary(
                number=number,
                name=f"Saison {number}" if len(chain) > 1 else "Épisodes",
                episode_count=_aired_episodes(season),
                air_date=_date(season.get("startDate")),
                poster_url=(season.get("coverImage") or {}).get("large"),
            )
            for number, season in enumerate(chain, start=1)
        ]
        last = chain[-1]
        total = sum(s.episode_count or 0 for s in seasons)
        return ContentDetail(
            **base.model_dump(exclude={"poster_url"}),
            poster_url=cover.get("extraLarge") or cover.get("large"),
            backdrop_url=media.get("bannerImage"),
            genres=[GENRES.get(genre, genre) for genre in media.get("genres", [])],
            release_date=_date(media.get("startDate")),
            end_date=_date(last.get("endDate")),
            runtime_minutes=media.get("duration"),
            status=STATUTS.get(last.get("status", ""), last.get("status")),
            seasons_count=len(seasons),
            episodes_count=total or None,
            seasons=[s for s in seasons if s.episode_count],
            source_url=media.get("siteUrl") or f"https://anilist.co/anime/{media['id']}",
            is_finished=last.get("status") in ("FINISHED", "CANCELLED"),
        )

    async def _seasons(
        self, http: httpx.AsyncClient, first: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """La série puis ses suites (saison 2, 3…), en suivant les liens SEQUEL."""
        chain = [first]
        seen = {first["id"]}
        current = first
        while len(chain) < MAX_SEASONS:
            following = [i for i in _linked(current, "SEQUEL", SERIES_FORMATS) if i not in seen]
            if not following:
                break
            current = (await self._query(http, SEASON_QUERY, {"id": following[0]})).get(
                "Media"
            ) or {}
            if not current:
                break
            seen.add(current["id"])
            chain.append(current)
        return chain

    async def get_season(
        self, http: httpx.AsyncClient, external_id: str, season_number: int
    ) -> list[EpisodeSummary] | None:
        if season_number < 1 or not external_id.isdigit():
            return None
        media = (await self._query(http, SEASON_QUERY, {"id": int(external_id)})).get("Media")
        if not media:
            return None
        chain = await self._seasons(http, media)
        if season_number > len(chain):
            return None
        # AniList ne fournit ni titre ni image par épisode : seulement les numéros.
        return [
            EpisodeSummary(season_number=season_number, number=number)
            for number in range(1, (_aired_episodes(chain[season_number - 1]) or 0) + 1)
        ]

    async def get_characters(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> list[CharacterSummary]:
        if kind != ContentKind.ANIME or not external_id.isdigit():
            return []
        # Le plus de personnages possible : jusqu'à 4 pages de 25.
        edges: list[dict[str, Any]] = []
        for page in range(1, MAX_CHARACTERS // 25 + 1):
            data = await self._query(http, CHARACTERS_QUERY, {"id": int(external_id), "page": page})
            block = ((data.get("Media") or {}).get("characters")) or {}
            edges += block.get("edges") or []
            if not (block.get("pageInfo") or {}).get("hasNextPage"):
                break
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
            if not is_main_entry(media):
                continue  # saison 2, film rattaché… : déjà dans la série principale
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
