"""Tests des personnages Disney (dessins à la place des photos de doubleurs)."""

import httpx

from app.config import get_settings
from app.providers import disney
from app.providers.base import CharacterRole, ContentKind
from app.providers.tmdb import TmdbProvider


def perso(nom: str, films: list[str], image: str = "https://img/x.png") -> dict[str, object]:
    return {"name": nom, "films": films, "imageUrl": image}


def test_normalisation_des_noms() -> None:
    assert disney.normalize("Simba (voice)") == "simba"
    assert disney.normalize("Young Simba (voice)") == "young simba"
    assert disney.normalize("Rafiki") == "rafiki"


def test_ordre_du_casting_et_apparitions_ecartees_en_dernier() -> None:
    trouves = [
        perso("Donald Duck", ["The Lion King", "Fantasia", "Mickey"]),
        perso("Scar", ["The Lion King"]),
        perso("Simba", ["The Lion King"]),
        perso("Simba", ["The Lion King"]),  # fiche en double
    ]
    voix = ["Simba (voice)", "Young Simba (voice)", "Scar (voice)"]

    resultat = [item["name"] for item in disney.ranked(trouves, voix)]

    assert resultat == ["Simba", "Scar", "Donald Duck"]


def test_aucun_lien_avec_le_casting() -> None:
    # Homonymes sans rapport : rien plutôt que des personnages au hasard.
    assert disney.ranked([perso("Bob", ["The Lion King"])], ["Simba (voice)"]) == []


async def test_film_d_animation_occidental_avec_dessins() -> None:
    fiche = {
        "original_title": "The Lion King",
        "genres": [{"id": 16}],
        "original_language": "en",
        "credits": {
            "cast": [
                {"order": 0, "character": "Simba (voice)", "profile_path": "/doubleur.jpg"},
                {"order": 1, "character": "Mufasa (voice)", "profile_path": "/doubleur2.jpg"},
            ]
        },
    }
    personnages = {
        "data": [
            perso("Mufasa", ["The Lion King"], "https://wiki/mufasa.png"),
            perso("Simba", ["The Lion King"], "https://wiki/simba.png"),
            perso("Kovu", ["The Lion King II: Simba's Pride"]),  # autre film
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.disneyapi.dev":
            assert request.url.params["films"] == "The Lion King"
            return httpx.Response(200, json=personnages)
        return httpx.Response(200, json=fiche)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        persos = await TmdbProvider(get_settings().tmdb_api_token or "jeton").get_characters(
            http, ContentKind.MOVIE, "8587"
        )

    assert [(p.name, p.image_url, p.role) for p in persos] == [
        ("Simba", "https://wiki/simba.png", CharacterRole.HERO),  # le dessin, pas le doubleur
        ("Mufasa", "https://wiki/mufasa.png", CharacterRole.MAIN),
    ]
