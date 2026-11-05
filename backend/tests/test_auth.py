"""Tests d'intégration de l'authentification (PostgreSQL et Redis requis)."""

from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

COMPTE = {
    "email": "Emilien@Exemple.fr",
    "username": "emilien",
    "password": "un-mot-de-passe-solide",
}


async def inscrire(client: AsyncClient, **modifs: str) -> Any:
    return await client.post("/api/auth/register", json={**COMPTE, **modifs})


async def connecter(client: AsyncClient, email: str = "emilien@exemple.fr") -> Any:
    return await client.post(
        "/api/auth/login", json={"email": email, "password": COMPTE["password"]}
    )


# --- Inscription -------------------------------------------------------------


async def test_inscription_reussie(db_client: AsyncClient) -> None:
    response = await inscrire(db_client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "emilien@exemple.fr"  # enregistré en minuscules
    assert body["username"] == "emilien"
    assert body["is_public"] is False  # profil privé par défaut
    assert "password" not in body and "password_hash" not in body


async def test_inscription_email_deja_utilise(db_client: AsyncClient) -> None:
    await inscrire(db_client)
    response = await inscrire(db_client, email="EMILIEN@exemple.fr", username="autre")

    assert response.status_code == 409
    assert "e-mail" in response.json()["detail"]


async def test_inscription_pseudo_deja_pris_quelle_que_soit_la_casse(
    db_client: AsyncClient,
) -> None:
    await inscrire(db_client)
    response = await inscrire(db_client, email="autre@exemple.fr", username="EMILIEN")

    assert response.status_code == 409
    assert "pseudo" in response.json()["detail"]


@pytest.mark.parametrize(
    "champ, valeur",
    [
        ("password", "court"),  # moins de 10 caractères
        ("username", "é!"),  # caractères interdits et trop court
        ("email", "pas-un-email"),
    ],
)
async def test_inscription_donnees_invalides(
    db_client: AsyncClient, champ: str, valeur: str
) -> None:
    response = await inscrire(db_client, **{champ: valeur})
    assert response.status_code == 422


# --- Connexion ---------------------------------------------------------------


async def test_connexion_puis_acces_au_compte(db_client: AsyncClient) -> None:
    await inscrire(db_client)
    response = await connecter(db_client, email="EMILIEN@exemple.fr")

    assert response.status_code == 200
    token = response.json()["access_token"]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/auth" in cookie

    me = await db_client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "emilien"


async def test_connexion_mauvais_mot_de_passe(db_client: AsyncClient) -> None:
    await inscrire(db_client)
    response = await db_client.post(
        "/api/auth/login", json={"email": "emilien@exemple.fr", "password": "mauvais"}
    )
    assert response.status_code == 401


async def test_connexion_email_inconnu_meme_message(db_client: AsyncClient) -> None:
    """Le message ne doit pas révéler si l'adresse est inscrite."""
    await inscrire(db_client)
    inconnu = await connecter(db_client, email="inconnu@exemple.fr")
    mauvais = await db_client.post(
        "/api/auth/login", json={"email": "emilien@exemple.fr", "password": "mauvais"}
    )

    assert inconnu.status_code == 401
    assert inconnu.json() == mauvais.json()


async def test_trop_de_tentatives_bloquees(db_client: AsyncClient) -> None:
    await inscrire(db_client)
    essai = {"email": "emilien@exemple.fr", "password": "mauvais"}
    for _ in range(5):
        assert (await db_client.post("/api/auth/login", json=essai)).status_code == 401

    response = await db_client.post("/api/auth/login", json=essai)
    assert response.status_code == 429
    assert "Retry-After" in response.headers


# --- Accès protégé -----------------------------------------------------------


async def test_compte_inaccessible_sans_jeton(db_client: AsyncClient) -> None:
    assert (await db_client.get("/api/users/me")).status_code == 401


async def test_compte_inaccessible_avec_jeton_invalide(db_client: AsyncClient) -> None:
    response = await db_client.get("/api/users/me", headers={"Authorization": "Bearer faux"})
    assert response.status_code == 401


# --- Renouvellement et déconnexion ------------------------------------------


async def test_renouvellement_donne_un_nouveau_jeton(db_client: AsyncClient) -> None:
    await inscrire(db_client)
    await connecter(db_client)  # le cookie est conservé par le client

    response = await db_client.post("/api/auth/refresh")

    assert response.status_code == 200
    token = response.json()["access_token"]
    me = await db_client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200


async def test_renouvellement_sans_cookie_refuse(db_client: AsyncClient) -> None:
    assert (await db_client.post("/api/auth/refresh")).status_code == 401


async def test_reutilisation_d_un_jeton_revoque_toute_la_session(
    db_client: AsyncClient,
) -> None:
    """Un jeton déjà utilisé a sans doute été volé : tout est révoqué."""
    await inscrire(db_client)
    ancien = (await connecter(db_client)).cookies["refresh_token"]
    nouveau = (await db_client.post("/api/auth/refresh")).cookies["refresh_token"]
    db_client.cookies.clear()

    vol = await db_client.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={ancien}"})
    assert vol.status_code == 401

    # Par précaution, le jeton légitime est révoqué lui aussi.
    legit = await db_client.post(
        "/api/auth/refresh", headers={"Cookie": f"refresh_token={nouveau}"}
    )
    assert legit.status_code == 401


async def test_deconnexion_revoque_la_session(db_client: AsyncClient) -> None:
    await inscrire(db_client)
    jeton = (await connecter(db_client)).cookies["refresh_token"]

    logout = await db_client.post("/api/auth/logout")
    assert logout.status_code == 204

    db_client.cookies.clear()
    response = await db_client.post(
        "/api/auth/refresh", headers={"Cookie": f"refresh_token={jeton}"}
    )
    assert response.status_code == 401
