"""Tests des points d'expérience, bonus, niveaux et succès (dont l'anti-triche)."""

from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Episode, XpEvent
from app.services.gamification import (
    level_for_xp,
    streak_bonus_percent,
    today,
    xp_for_level,
)
from tests.conftest import Contexte

FILM = "/api/tracking/tmdb/movie/603"
SERIE = "/api/tracking/tmdb/series/1399"


async def episodes(client: AsyncClient, saison: int = 1) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = (await client.get(f"{SERIE}/seasons/{saison}")).json()
    return result


async def cocher(client: AsyncClient, ids: list[int], vu: bool = True) -> dict[str, Any]:
    response = await client.post(f"{SERIE}/episodes", json={"episode_ids": ids, "watched": vu})
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


async def profil(client: AsyncClient) -> dict[str, Any]:
    result: dict[str, Any] = (await client.get("/api/gamification/me")).json()
    return result


def gains(etat: dict[str, Any]) -> dict[str, int]:
    return {line["label"]: line["amount"] for line in etat["rewards"]["lines"]}


# --- Règles de calcul (sans base de données) ----------------------------------


def test_courbe_des_niveaux() -> None:
    assert [xp_for_level(n) for n in (1, 2, 3, 4, 10)] == [0, 100, 283, 520, 2700]
    assert level_for_xp(0) == 1
    assert level_for_xp(99) == 1
    assert level_for_xp(100) == 2
    assert level_for_xp(2700) == 10


def test_bonus_de_serie_plafonne() -> None:
    assert streak_bonus_percent(1) == 0
    assert streak_bonus_percent(4) == 15
    assert streak_bonus_percent(30) == 50


# --- Avec la base de données --------------------------------------------------


@pytest.mark.integration
async def test_premiers_episodes(db_client: AsyncClient, contexte: Contexte) -> None:
    saison1 = await episodes(db_client)

    etat = await cocher(db_client, [e["id"] for e in saison1])

    assert gains(etat) == {"Épisodes vus": 20, "Nouvelle série": 15, "Succès débloqué": 20}
    assert etat["rewards"]["xp"] == 55
    assert [b["code"] for b in etat["rewards"]["badges"]] == ["premier_pas"]
    assert etat["rewards"]["level_up"] is None
    moi = await profil(db_client)
    assert (moi["xp"], moi["level"], moi["next_level_xp"]) == (55, 1, 100)
    premier_pas = next(b for b in moi["badges"] if b["code"] == "premier_pas")
    assert premier_pas["earned_at"] is not None


@pytest.mark.integration
async def test_cocher_decocher_ne_rapporte_rien(db_client: AsyncClient, contexte: Contexte) -> None:
    ids = [e["id"] for e in await episodes(db_client)]
    await cocher(db_client, ids)
    for _ in range(3):  # tentative de « farm »
        await cocher(db_client, ids, vu=False)
        assert (await profil(db_client))["xp"] == 35  # épisodes repris, bonus gardés
        await cocher(db_client, ids)
    assert (await profil(db_client))["xp"] == 55


@pytest.mark.integration
async def test_film_vu_puis_change_d_avis(db_client: AsyncClient, contexte: Contexte) -> None:
    etat = (await db_client.put(FILM, json={"status": "completed"})).json()
    assert gains(etat) == {"Film vu": 50}

    await db_client.put(FILM, json={"status": "watching"})
    assert (await profil(db_client))["xp"] == 0
    await db_client.put(FILM, json={"status": "completed"})
    # Modifier la note d'un film déjà vu ne rapporte rien de plus.
    etat = (await db_client.put(FILM, json={"status": "completed", "rating": 8})).json()
    assert etat["rewards"] is None
    assert (await profil(db_client))["xp"] == 50


@pytest.mark.integration
async def test_serie_terminee_et_niveau_superieur(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    await cocher(db_client, [e["id"] for e in await episodes(db_client, 1)])
    etat = await cocher(db_client, [e["id"] for e in await episodes(db_client, 2)])

    assert etat["tracking"]["status"] == "completed"
    assert gains(etat) == {"Épisodes vus": 10, "Série terminée": 100, "Succès débloqué": 20}
    assert [b["code"] for b in etat["rewards"]["badges"]] == ["fin_de_saga"]
    assert etat["rewards"]["level_up"] == 2  # 55 + 130 = 185 XP


@pytest.mark.integration
async def test_episode_pas_encore_sorti(
    db_client: AsyncClient, contexte: Contexte, db_session: AsyncSession
) -> None:
    saison1 = await episodes(db_client)
    await db_session.execute(update(Episode).values(air_date=today() + timedelta(days=7)))

    etat = await cocher(db_client, [saison1[0]["id"]])

    # Ni XP ni succès « Premier pas » : on ne peut pas avoir vu cet épisode.
    assert etat["rewards"] is None
    assert (await profil(db_client))["xp"] == 0


@pytest.mark.integration
async def test_bonus_jour_j(
    db_client: AsyncClient, contexte: Contexte, db_session: AsyncSession
) -> None:
    saison1 = await episodes(db_client)
    await db_session.execute(update(Episode).values(air_date=today()))

    etat = await cocher(db_client, [saison1[0]["id"]])

    assert gains(etat)["Bonus Jour J"] == 25
    assert "jour_j" in [b["code"] for b in etat["rewards"]["badges"]]


@pytest.mark.integration
async def test_plafond_quotidien(
    db_client: AsyncClient, contexte: Contexte, db_session: AsyncSession
) -> None:
    db_session.add(
        XpEvent(user_id=contexte.alice.id, key="deja", kind="episode", amount=295, day=today())
    )
    await db_session.commit()

    etat = await cocher(db_client, [e["id"] for e in await episodes(db_client)])

    assert gains(etat)["Épisodes vus"] == 5  # 300 au maximum par jour


@pytest.mark.integration
async def test_serie_de_jours_et_marathon(
    db_client: AsyncClient, contexte: Contexte, db_session: AsyncSession
) -> None:
    # Visionnages les 3 jours précédents, et déjà 3 épisodes aujourd'hui.
    jours = [today() - timedelta(days=n) for n in (3, 2, 1, 0, 0, 0)]
    db_session.add_all(
        XpEvent(user_id=contexte.alice.id, key=f"ancien:{i}", kind="episode", amount=1, day=day)
        for i, day in enumerate(jours)
    )
    await db_session.commit()

    etat = await cocher(db_client, [e["id"] for e in await episodes(db_client)])

    assert etat["rewards"]["streak_days"] == 4
    # 4e jour d'affilée : +15 % → 10 × 1,15 = 11,5, arrondi à 12 par épisode.
    assert gains(etat)["Épisodes vus"] == 24
    # 3 épisodes plus tôt + 2 maintenant = 5 dans la journée : marathon.
    assert gains(etat)["Bonus marathon"] == 40
    moi = await profil(db_client)
    assert moi["streak_days"] == 4
    assert moi["streak_bonus_percent"] == 15


@pytest.mark.integration
async def test_succes_bibliothecaire(db_client: AsyncClient, contexte: Contexte) -> None:
    for nom in ("Un", "Deux", "Trois"):
        await db_client.post("/api/libraries", json={"name": nom})

    moi = await profil(db_client)
    badge = next(b for b in moi["badges"] if b["code"] == "bibliothecaire")
    assert badge["earned_at"] is not None
    assert badge["progress"] == badge["threshold"] == 3
    assert moi["recent"][0]["label"] == "Succès débloqué"


@pytest.mark.integration
async def test_simple_lecture_sans_recompense(db_client: AsyncClient, contexte: Contexte) -> None:
    assert (await db_client.get(SERIE)).json()["rewards"] is None
