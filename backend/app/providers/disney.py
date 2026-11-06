"""Dessins des personnages Disney, via la Disney API (gratuite, sans clé).

Pour un film d'animation (« Le Roi Lion »), TMDB ne connaît que les VOIX :
leurs photos sont celles des doubleurs. La Disney API fournit les dessins
des personnages (images du wiki Disney de Fandom).

La Disney API mélange les apparitions (Donald Duck « apparaît » dans « Le Roi
Lion »). On garde donc en priorité les personnages du casting vocal de TMDB,
qui donne aussi leur ordre d'importance.
Documentation : https://disneyapi.dev
"""

import re
import unicodedata
from typing import Any

import httpx

from app.providers.base import ProviderError

API_URL = "https://api.disneyapi.dev/character"


def normalize(name: str) -> str:
    """« Simba (voice) » → « simba » ; accents et ponctuation retirés."""
    name = re.sub(r"\(.*?\)", "", name)
    name = unicodedata.normalize("NFD", name).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", name.lower()).split())


async def characters_of(
    http: httpx.AsyncClient, title: str, is_movie: bool
) -> list[dict[str, Any]]:
    """Personnages Disney dont la liste d'œuvres contient EXACTEMENT ce titre."""
    field = "films" if is_movie else "tvShows"
    try:
        response = await http.get(API_URL, params={field: title, "pageSize": "300"})
    except httpx.HTTPError as exc:
        raise ProviderError(f"Disney API injoignable : {exc}") from exc
    if response.status_code >= 500 or response.status_code == 429:
        raise ProviderError(f"Disney API a répondu {response.status_code}")
    if response.status_code != 200:
        return []
    data = response.json().get("data") or []
    if isinstance(data, dict):  # un seul résultat : la Disney API renvoie un objet
        data = [data]
    wanted = normalize(title)
    return [
        item
        for item in data
        if item.get("imageUrl")
        and item.get("name")
        and any(normalize(work) == wanted for work in item.get(field) or [])
    ]


def ranked(disney: list[dict[str, Any]], voices: list[str]) -> list[dict[str, Any]]:
    """Trie les personnages Disney selon l'ordre du casting vocal de TMDB.

    Les personnages absents du casting (simples apparitions) viennent après,
    du plus présent dans l'univers Disney au moins présent.
    """
    voice_names = [normalize(v) for v in voices]

    def rank(item: dict[str, Any]) -> tuple[int, int]:
        name = normalize(item["name"])
        for index, voice in enumerate(voice_names):
            # « Simba » correspond à « simba » et à « young simba ».
            if name and (voice == name or voice.endswith(" " + name) or name in voice.split(" / ")):
                return (0, index)
        appearances = sum(len(item.get(k) or []) for k in ("films", "shortFilms", "tvShows"))
        return (1, -appearances)

    in_cast = [item for item in disney if rank(item)[0] == 0]
    others = [item for item in disney if rank(item)[0] == 1]
    # Sans aucune correspondance avec le casting, la liste est peu fiable
    # (homonymes) : on ne garde rien plutôt que des personnages au hasard.
    if not in_cast:
        return []
    # La Disney API a parfois plusieurs fiches pour un même personnage : on
    # n'en garde qu'une (la mieux classée).
    unique: dict[str, dict[str, Any]] = {}
    for item in sorted(in_cast, key=rank) + sorted(others, key=rank):
        unique.setdefault(normalize(item["name"]), item)
    return list(unique.values())
