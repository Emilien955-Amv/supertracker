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
    # Nouvelle bibliothèque : vue « meuble », chêne clair, objets de taille moyenne.
    assert (biblio["view_mode"], biblio["sort_mode"]) == ("bookcase", "manual")
    assert (biblio["wood"], biblio["item_size"]) == ("oak", "medium")
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


async def test_meuble_et_etageres(db_client: AsyncClient, contexte: Contexte) -> None:
    biblio = await creer(db_client)
    url = f"/api/libraries/{biblio['id']}"
    for contenu in (MATRIX, GOT):
        await db_client.post(f"{url}/items", json=contenu)

    detail = (await db_client.get(url)).json()
    etageres = [e["id"] for e in detail["shelves"]]
    assert len(etageres) == 3  # meuble neuf : trois étagères
    # Les nouveaux objets arrivent sur l'étagère du haut.
    assert {item["shelf_id"] for item in detail["items"]} == {etageres[0]}

    # Personnalisation : bois, mur, taille.
    reponse = await db_client.patch(
        url, json={"wood": "walnut", "wall": "#112233", "item_size": "large"}
    )
    assert (reponse.json()["wood"], reponse.json()["wall"]) == ("walnut", "#112233")
    assert (await db_client.patch(url, json={"wood": "plastique"})).status_code == 422

    # Ranger : Game of Thrones sur l'étagère du bas, ordre des étagères inversé.
    ids = {item["content"]["title"]: item["content"]["id"] for item in detail["items"]}
    rangement = {
        "shelves": [
            {"id": etageres[2], "content_ids": [ids["Game of Thrones"]]},
            {"id": etageres[1], "content_ids": []},
            {"id": etageres[0], "content_ids": [ids["Matrix"]]},
        ]
    }
    assert (await db_client.put(f"{url}/layout", json=rangement)).status_code == 204
    detail = (await db_client.get(url)).json()
    assert [e["id"] for e in detail["shelves"]] == etageres[::-1]
    place = {item["content"]["title"]: item["shelf_id"] for item in detail["items"]}
    assert place == {"Game of Thrones": etageres[2], "Matrix": etageres[0]}

    # Rangement incomplet (un objet oublié) : refusé.
    incomplet = {"shelves": [{"id": e, "content_ids": []} for e in etageres]}
    assert (await db_client.put(f"{url}/layout", json=incomplet)).status_code == 422

    # Ajouter, renommer, supprimer une étagère.
    nouvelle = (await db_client.post(f"{url}/shelves", json={"name": "  Mangas  "})).json()
    assert nouvelle["name"] == "Mangas"
    reponse = await db_client.patch(f"{url}/shelves/{nouvelle['id']}", json={"name": "Animes"})
    assert reponse.json()["name"] == "Animes"
    # Supprimer l'étagère de Matrix : Matrix glisse sur l'étagère voisine.
    assert (await db_client.delete(f"{url}/shelves/{etageres[0]}")).status_code == 204
    detail = (await db_client.get(url)).json()
    assert len(detail["shelves"]) == 3
    assert all(item["shelf_id"] is not None for item in detail["items"])


async def test_derniere_etagere_et_cloisonnement(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    biblio = await creer(db_client)
    url = f"/api/libraries/{biblio['id']}"
    etageres = [e["id"] for e in (await db_client.get(url)).json()["shelves"]]
    for etagere in etageres[:-1]:
        assert (await db_client.delete(f"{url}/shelves/{etagere}")).status_code == 204
    # Un meuble garde au moins une étagère.
    assert (await db_client.delete(f"{url}/shelves/{etageres[-1]}")).status_code == 409

    # Bob ne touche pas aux étagères d'Alice.
    contexte.connecter(contexte.bob)
    assert (await db_client.post(f"{url}/shelves", json={})).status_code == 404
    reponse = await db_client.patch(f"{url}/shelves/{etageres[-1]}", json={"name": "x"})
    assert reponse.status_code == 404
