"""Tests des images de personnages tirées des wikis Fandom."""

import httpx

from app.providers import fandom
from app.providers.base import CharacterRole, CharacterSummary


def perso(nom: str) -> CharacterSummary:
    return CharacterSummary(
        name=nom,
        image_url=f"https://image.tmdb.org/acteur/{nom}.jpg",
        role=CharacterRole.MAIN,
        order=0,
    )


def test_wikis_candidats() -> None:
    assert fandom.wiki_candidates(["Harry Potter"])[0] == "harrypotter"
    assert fandom.wiki_candidates(["Le Seigneur des anneaux"])[0] == "lotr"
    # Œuvre inconnue : déduit du titre (« The Walking Dead » → walkingdead).
    assert "walkingdead" in fandom.wiki_candidates(["The Walking Dead"])


async def test_images_du_personnage_et_redirections() -> None:
    reponse = {
        "query": {
            "redirects": [{"from": "Ron Weasley", "to": "Ronald Weasley"}],
            "pages": {
                "1": {"title": "Harry Potter", "thumbnail": {"source": "https://wiki/harry.jpg"}},
                "2": {"title": "Ronald Weasley", "thumbnail": {"source": "https://wiki/ron.jpg"}},
                "-1": {"title": "Figurant", "missing": ""},
            },
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "harrypotter.fandom.com"
        return httpx.Response(200, json=reponse)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        persos = await fandom.enrich(
            http, ["Harry Potter"], [perso("Harry Potter"), perso("Ron Weasley"), perso("Figurant")]
        )

    assert [p.image_url for p in persos] == [
        "https://wiki/harry.jpg",
        "https://wiki/ron.jpg",  # retrouvé grâce à la redirection du wiki
        "https://image.tmdb.org/acteur/Figurant.jpg",  # inconnu du wiki : photo gardée
    ]


async def test_wiki_sans_rapport_ignore() -> None:
    # Le wiki ne reconnaît presque personne : sans doute un homonyme, on n'y touche pas.
    reponse = {"query": {"pages": {"-1": {"title": "X", "missing": ""}}}}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=reponse))
    ) as http:
        persos = await fandom.enrich(http, ["Une œuvre"], [perso("A"), perso("B")])
    assert all("image.tmdb.org" in p.image_url for p in persos)


async def test_wiki_inexistant() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(404))
    ) as http:
        persos = await fandom.enrich(http, ["Inconnu"], [perso("A")])
    assert persos[0].image_url.startswith("https://image.tmdb.org")
