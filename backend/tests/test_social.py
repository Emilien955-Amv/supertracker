"""Tests du social : recherche, demandes d'amis, profils privés et publics."""

import pytest
from httpx import AsyncClient

from app.models import User
from tests.conftest import Contexte

pytestmark = pytest.mark.integration


async def profil(client: AsyncClient, pseudo: str) -> dict[str, object]:
    response = await client.get(f"/api/users/{pseudo}/profile")
    assert response.status_code == 200, response.text
    result: dict[str, object] = response.json()
    return result


async def test_profil_prive_par_defaut(db_client: AsyncClient, contexte: Contexte) -> None:
    await db_client.patch("/api/users/me", json={"bio": "Fan de One Piece"})

    contexte.connecter(contexte.bob)
    vu_par_bob = await profil(db_client, "alice_test")

    # Un inconnu ne voit que le pseudo : ni présentation, ni statistiques.
    assert vu_par_bob["visible"] is False
    assert vu_par_bob["bio"] is None and vu_par_bob["stats"] is None
    assert vu_par_bob["relation"] == "none"


async def test_demande_d_ami_puis_acceptation(db_client: AsyncClient, contexte: Contexte) -> None:
    contexte.connecter(contexte.bob)
    trouves = (await db_client.get("/api/users/search", params={"q": "ALI"})).json()
    assert [(u["username"], u["relation"]) for u in trouves] == [("alice_test", "none")]

    demande = (await db_client.post("/api/friends/alice_test")).json()
    assert demande["relation"] == "outgoing"
    # Redemander ne crée pas de doublon.
    assert (await db_client.post("/api/friends/ALICE_TEST")).json()["relation"] == "outgoing"

    contexte.connecter(contexte.alice)
    amis = (await db_client.get("/api/friends")).json()
    assert [u["username"] for u in amis["incoming"]] == ["bob_test"]
    # Alice « ajoute » Bob en retour : cela accepte sa demande.
    assert (await db_client.post("/api/friends/bob_test")).json()["relation"] == "friends"
    amis = (await db_client.get("/api/friends")).json()
    assert ([u["username"] for u in amis["friends"]], amis["incoming"]) == (["bob_test"], [])

    # Amis : Bob voit le profil complet d'Alice.
    await db_client.patch("/api/users/me", json={"bio": "Fan de One Piece"})
    contexte.connecter(contexte.bob)
    vu_par_bob = await profil(db_client, "alice_test")
    assert vu_par_bob["visible"] is True
    assert vu_par_bob["bio"] == "Fan de One Piece"
    assert vu_par_bob["stats"]["level"] == 1  # type: ignore[index]

    # Bob retire Alice : retour à « inconnu ».
    assert (await db_client.delete("/api/friends/alice_test")).status_code == 204
    assert (await profil(db_client, "alice_test"))["visible"] is False


async def test_profil_public(db_client: AsyncClient, contexte: Contexte) -> None:
    reponse = await db_client.patch("/api/users/me", json={"is_public": True, "bio": "  Salut  "})
    assert (reponse.json()["is_public"], reponse.json()["bio"]) == (True, "Salut")

    contexte.connecter(contexte.bob)
    vu_par_bob = await profil(db_client, "alice_test")
    assert vu_par_bob["visible"] is True  # public : visible même sans être amis
    assert vu_par_bob["bio"] == "Salut"


async def test_refuser_une_demande_et_cas_d_erreur(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    contexte.connecter(contexte.bob)
    await db_client.post("/api/friends/alice_test")

    contexte.connecter(contexte.alice)
    assert (await db_client.delete("/api/friends/bob_test")).status_code == 204  # refus
    assert (await db_client.get("/api/friends")).json()["incoming"] == []

    assert (await db_client.post("/api/friends/alice_test")).status_code == 409  # soi-même
    assert (await db_client.post("/api/friends/personne")).status_code == 404
    assert (await db_client.get("/api/users/personne/profile")).status_code == 404
    assert (await db_client.get("/api/users/search", params={"q": "a"})).status_code == 422
    # Les caractères spéciaux ne cassent pas la recherche.
    assert (await db_client.get("/api/users/search", params={"q": "%_"})).json() == []


async def test_la_recherche_ne_montre_pas_soi_meme(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    trouves = (await db_client.get("/api/users/search", params={"q": "alice"})).json()
    assert trouves == []
    assert isinstance(contexte.alice, User)
