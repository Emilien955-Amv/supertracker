"""Images des personnages (et non des acteurs) via les wikis de fans Fandom.

TMDB ne fournit que des portraits officiels d'acteurs (Daniel Radcliffe en
costume). Les wikis Fandom (Harry Potter Wiki, Wookieepedia, Marvel…) ont,
pour presque chaque personnage, une image tirée du film ou de la série :
Harry, baguette à la main, à Poudlard.

Fonctionnement :
1. on trouve le wiki de l'œuvre (liste connue, sinon déduit du titre) ;
2. on demande, par paquets de 50, l'image principale de la page de chaque
   personnage (« Harry Potter », « Ron Weasley »… les redirections du wiki
   font le lien vers « Ronald Weasley ») ;
3. un wiki n'est retenu que s'il reconnaît au moins 30 % des personnages :
   un wiki homonyme sans rapport est ainsi écarté.
La photo de l'acteur ne sert plus qu'en dernier recours.

Contenu des wikis Fandom : licence CC BY-SA ; images hébergées par Fandom.
"""

import re
import unicodedata
from typing import Any

import httpx
import structlog

from app.providers.base import CharacterSummary, ProviderError

log = structlog.get_logger()

BATCH = 50  # titres par requête (limite de l'API MediaWiki)
MIN_MATCH = 0.3  # part des personnages reconnus pour faire confiance au wiki
THUMB_SIZE = "500"

# Wikis connus : mot-clé du titre (minuscules, sans accents) → sous-domaine Fandom.
WIKIS: tuple[tuple[str, str], ...] = (
    ("harry potter", "harrypotter"),
    ("animaux fantastiques", "harrypotter"),
    ("fantastic beasts", "harrypotter"),
    ("star wars", "starwars"),
    ("mandalorian", "starwars"),
    ("seigneur des anneaux", "lotr"),
    ("lord of the rings", "lotr"),
    ("hobbit", "lotr"),
    ("avengers", "marvelcinematicuniverse"),
    ("iron man", "marvelcinematicuniverse"),
    ("captain america", "marvelcinematicuniverse"),
    ("thor", "marvelcinematicuniverse"),
    ("gardiens de la galaxie", "marvelcinematicuniverse"),
    ("guardians of the galaxy", "marvelcinematicuniverse"),
    ("black panther", "marvelcinematicuniverse"),
    ("doctor strange", "marvelcinematicuniverse"),
    ("ant-man", "marvelcinematicuniverse"),
    ("wandavision", "marvelcinematicuniverse"),
    ("loki", "marvelcinematicuniverse"),
    ("spider-man", "spiderman"),
    ("deadpool", "xmenmovies"),
    ("x-men", "xmenmovies"),
    ("dark knight", "batman"),
    ("batman", "batman"),
    ("joker", "batman"),
    ("game of thrones", "gameofthrones"),
    ("house of the dragon", "gameofthrones"),
    ("breaking bad", "breakingbad"),
    ("better call saul", "breakingbad"),
    ("stranger things", "strangerthings"),
    ("walking dead", "walkingdead"),
    ("the boys", "amazons-the-boys"),
    ("pirates des caraibes", "pirates"),
    ("pirates of the caribbean", "pirates"),
    ("hunger games", "thehungergames"),
    ("jurassic", "jurassicpark"),
    ("fast & furious", "fastandfurious"),
    ("fast and furious", "fastandfurious"),
    ("the witcher", "witcher"),
    ("the office", "theoffice"),
    ("friends", "friends"),
    ("sherlock", "bakerstreet"),
    ("peaky blinders", "peaky-blinders"),
    ("the last of us", "thelastofus"),
    ("la casa de papel", "money-heist"),
    ("money heist", "money-heist"),
    ("squid game", "squid-game"),
    ("matrix", "matrix"),
    ("terminator", "terminator"),
    ("alien", "avp"),
    ("transformers", "transformers"),
    ("mission impossible", "missionimpossible"),
    ("james bond", "jamesbond"),
    ("john wick", "johnwick"),
    ("toy story", "pixar"),
    ("dexter", "dexter"),
    ("lucifer", "lucifer"),
    ("supernatural", "supernatural"),
    ("vikings", "vikings"),
    ("the big bang theory", "bigbangtheory"),
    ("how i met your mother", "himym"),
    ("grey's anatomy", "greysanatomy"),
    ("prison break", "prisonbreak"),
    ("lost", "lostpedia"),
    ("doctor who", "tardis"),
    ("the simpsons", "simpsons"),
)


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def wiki_candidates(titles: list[str]) -> list[str]:
    """Sous-domaines à essayer pour une œuvre : liste connue, puis déduits du titre."""
    found: list[str] = []
    for title in titles:
        plain = _plain(title)
        for keyword, slug in WIKIS:
            if keyword in plain and slug not in found:
                found.append(slug)
    for title in titles:
        words = re.sub(r"[^a-z0-9 ]", "", _plain(title)).split()
        for guess in ("".join(words), "".join(w for w in words if w != "the"), "-".join(words)):
            if guess and guess not in found:
                found.append(guess)
    return found[:6]


async def _query(
    http: httpx.AsyncClient, slug: str, params: dict[str, str]
) -> dict[str, Any] | None:
    try:
        response = await http.get(
            f"https://{slug}.fandom.com/api.php",
            params={"action": "query", "format": "json", **params},
            follow_redirects=False,  # un wiki inexistant redirige vers la page d'accueil Fandom
        )
    except httpx.HTTPError as exc:
        raise ProviderError(f"Fandom injoignable : {exc}") from exc
    if response.status_code != 200:
        return None
    try:
        data: dict[str, Any] = response.json()
    except ValueError:
        return None
    return data


async def character_images(
    http: httpx.AsyncClient, slug: str, names: list[str]
) -> dict[str, str] | None:
    """Image de la page de chaque personnage (nom → adresse). None : wiki introuvable."""
    images: dict[str, str] = {}
    for start in range(0, len(names), BATCH):
        batch = names[start : start + BATCH]
        data = await _query(
            http,
            slug,
            {
                "prop": "pageimages",
                "piprop": "thumbnail",
                "pithumbsize": THUMB_SIZE,
                "redirects": "1",
                "titles": "|".join(batch),
            },
        )
        if data is None:
            return None
        query = data.get("query") or {}
        # Le wiki corrige les titres (« Ron Weasley » → « Ronald Weasley ») :
        # on suit ces corrections pour retrouver le nom d'origine.
        renamed: dict[str, str] = {}
        for step in (query.get("normalized") or []) + (query.get("redirects") or []):
            renamed[step["from"]] = step["to"]
        by_title = {
            page.get("title"): (page.get("thumbnail") or {}).get("source")
            for page in (query.get("pages") or {}).values()
        }
        for name in batch:
            title = name
            for _ in range(3):  # normalisation puis redirection
                title = renamed.get(title, title)
            if source := by_title.get(title):
                images[name] = source
    return images


async def enrich(
    http: httpx.AsyncClient, titles: list[str], characters: list[CharacterSummary]
) -> list[CharacterSummary]:
    """Remplace les photos d'acteurs par les images des personnages, si un wiki
    de l'œuvre les connaît. En cas de souci, les personnages sont rendus tels quels."""
    if not characters:
        return characters
    names = [c.name for c in characters]
    for slug in wiki_candidates(titles):
        try:
            images = await character_images(http, slug, names)
        except ProviderError:
            log.warning("fandom.injoignable", wiki=slug)
            return characters
        if images is None or len(images) < MIN_MATCH * len(names):
            continue  # wiki absent, ou sans rapport avec cette œuvre
        log.info("fandom.images", wiki=slug, trouvees=len(images), personnages=len(names))
        return [
            c.model_copy(update={"image_url": images[c.name]}) if c.name in images else c
            for c in characters
        ]
    return characters
