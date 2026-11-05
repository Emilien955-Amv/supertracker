"""Tests des bibliothèques personnelles."""

import pytest
from httpx import AsyncClient

from tests.conftest import Contexte

pytestmark = pytest.mark.integration

MATRIX = {"source": "tmdb", "kind": "movie", "external_id": "603"}
GOT = {"source": "tmdb", "kind": "series", "external_id": "1399"}


async def creer(client: AsyncClient, nom: str = "Coups de cœur", **extra: str) -> dict[str, object]:
    response = await client.post("/api/libraries", json={"name": nom, **extra})
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


async def titres(client: AsyncClient, library_id: object) -> list[str]:
    detail = (await client.get(f"/api/libraries/{library_id}")).json()
    return [item["content"]["title"] for item in detail["items"]]


async def test_creer_et_lister(db_client: AsyncClient, contexte: Contexte) -> None:
    biblio = await creer(db_client, "  Coups de cœur ", color="#FF0055")

    assert biblio["name"] == "Coups de cœur"  # espaces retirés
    assert biblio["color"] == "#ff0055"  # toujours en minuscules
    assert (biblio["view_mode"], biblio["sort_mode"]) == ("grid", "manual")
    liste = (await db_client.get("/api/libraries")).json()
    assert [(b["name"], b["items_count"]) for b in liste] == [("Coups de cœur", 0)]


async def test_nom_deja_pris_insensible_a_la_casse(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    await creer(db_client, "Favoris")
    response = await db_client.post("/api/libraries", json={"name": "FAVORIS"})
    assert response.status_code == 409

    # Mais Bob peut avoir sa propre bibliothèque « Favoris ».
    contexte.connecter(contexte.bob)
    await creer(db_client, "Favoris")


@pytest.mark.parametrize(
    "corps",
    [
        {"name": ""},
        {"name": "x" * 51},
        {"name": "A", "color": "rouge"},
        {"name": "A", "view_mode": "3d"},
    ],
)
async def test_creation_invalide(
    db_client: AsyncClient, contexte: Contexte, corps: dict[str, str]
) -> None:
    assert (await db_client.post("/api/libraries", json=corps)).status_code == 422


async def test_ajouter_trier_et_reordonner(db_client: AsyncClient, contexte: Contexte) -> None:
    biblio = await creer(db_client)
    url = f"/api/libraries/{biblio['id']}"
    for contenu in (MATRIX, GOT, MATRIX):  # le doublon est ignoré
        assert (await db_client.post(f"{url}/items", json=contenu)).status_code == 200

    assert await titres(db_client, biblio["id"]) == ["Matrix", "Game of Thrones"]

    await db_client.patch(url, json={"sort_mode": "alpha"})
    assert await titres(db_client, biblio["id"]) == ["Game of Thrones", "Matrix"]

    await db_client.patch(url, json={"sort_mode": "category"})  # films d'abord
    assert await titres(db_client, biblio["id"]) == ["Matrix", "Game of Thrones"]

    detail = (await db_client.get(url)).json()
    ids = [item["content"]["id"] for item in detail["items"]]
    assert (await db_client.put(f"{url}/order", json={"content_ids": ids[::-1]})).status_code == 204
    detail = (await db_client.get(url)).json()
    assert detail["sort_mode"] == "manual"  # réordonner repasse en tri manuel
    assert [item["content"]["title"] for item in detail["items"]] == ["Game of Thrones", "Matrix"]
    assert detail["items_count"] == 2
    assert len(detail["preview"]) == 2

    # Liste incomplète ou avec doublons : refusée.
    for mauvais in ([ids[0]], [ids[0], ids[0]], [*ids, 999999]):
        response = await db_client.put(f"{url}/order", json={"content_ids": mauvais})
        assert response.status_code == 422


async def test_indique_les_bibliotheques_contenant_un_contenu(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    avec = await creer(db_client, "Avec")
    await creer(db_client, "Sans")
    await db_client.post(f"/api/libraries/{avec['id']}/items", json=MATRIX)

    liste = (await db_client.get("/api/libraries", params=MATRIX)).json()
    assert {b["name"]: b["contains"] for b in liste} == {"Avec": True, "Sans": False}
    # Contenu jamais enregistré : présent nulle part.
    liste = (await db_client.get("/api/libraries", params=GOT)).json()
    assert all(b["contains"] is False for b in liste)


async def test_statut_de_suivi_affiche(db_client: AsyncClient, contexte: Contexte) -> None:
    biblio = await creer(db_client)
    await db_client.post(f"/api/libraries/{biblio['id']}/items", json=MATRIX)
    await db_client.put("/api/tracking/tmdb/movie/603", json={"status": "completed"})

    detail = (await db_client.get(f"/api/libraries/{biblio['id']}")).json()
    assert detail["items"][0]["tracking_status"] == "completed"


async def test_retirer_et_supprimer(db_client: AsyncClient, contexte: Contexte) -> None:
    biblio = await creer(db_client)
    url = f"/api/libraries/{biblio['id']}"
    content_id = (await db_client.post(f"{url}/items", json=MATRIX)).json()["id"]

    assert (await db_client.delete(f"{url}/items/{content_id}")).status_code == 204
    assert await titres(db_client, biblio["id"]) == []

    assert (await db_client.delete(url)).status_code == 204
    assert (await db_client.get(url)).status_code == 404


async def test_renommer(db_client: AsyncClient, contexte: Contexte) -> None:
    biblio = await creer(db_client, "Ancien")
    await creer(db_client, "Pris")
    url = f"/api/libraries/{biblio['id']}"

    response = await db_client.patch(url, json={"name": "Nouveau", "view_mode": "shelf"})
    assert response.status_code == 200
    assert (response.json()["name"], response.json()["view_mode"]) == ("Nouveau", "shelf")
    assert (await db_client.patch(url, json={"name": "pris"})).status_code == 409


async def test_bibliotheque_d_un_autre_utilisateur_invisible(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    biblio = await creer(db_client)
    url = f"/api/libraries/{biblio['id']}"

    contexte.connecter(contexte.bob)
    assert (await db_client.get(url)).status_code == 404
    assert (await db_client.patch(url, json={"name": "Piratée"})).status_code == 404
    assert (await db_client.post(f"{url}/items", json=MATRIX)).status_code == 404
    assert (await db_client.delete(url)).status_code == 404
    assert (await db_client.get("/api/libraries")).json() == []
