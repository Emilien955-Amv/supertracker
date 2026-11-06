"""Tests du suivi : statut, note, avis, épisodes vus et progression."""

import pytest
from httpx import AsyncClient

from tests.conftest import Contexte

pytestmark = pytest.mark.integration

FILM = "/api/tracking/tmdb/movie/603"
SERIE = "/api/tracking/tmdb/series/1399"


async def episodes(client: AsyncClient, saison: int) -> list[dict[str, object]]:
    response = await client.get(f"{SERIE}/seasons/{saison}")
    assert response.status_code == 200
    result: list[dict[str, object]] = response.json()
    return result


async def cocher(client: AsyncClient, ids: list[object], vu: bool = True) -> dict[str, object]:
    response = await client.post(f"{SERIE}/episodes", json={"episode_ids": ids, "watched": vu})
    assert response.status_code == 200, response.text
    result: dict[str, object] = response.json()
    return result


async def test_contenu_jamais_suivi(db_client: AsyncClient, contexte: Contexte) -> None:
    response = await db_client.get(FILM)

    assert response.status_code == 200
    assert response.json()["tracking"] is None
    assert response.json()["content_id"] is None
    # Simple consultation : la source n'est pas appelée, rien n'est copié.
    assert contexte.source.appels == 0


async def test_suivre_un_film_noter_et_donner_son_avis(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    response = await db_client.put(
        FILM, json={"status": "completed", "rating": 9, "review": "  Culte.  "}
    )

    assert response.status_code == 200
    etat = response.json()
    assert etat["tracking"]["status"] == "completed"
    assert etat["tracking"]["rating"] == 9
    assert etat["tracking"]["review"] == "Culte."  # espaces retirés
    assert etat["tracking"]["completed_at"] is not None
    assert etat["progress"] == {"watched": 1, "total": 1, "percent": 100}


@pytest.mark.parametrize(
    "corps",
    [
        {"status": "completed", "rating": 11},
        {"status": "completed", "rating": 0},
        {"status": "fini"},
        {"status": "watching", "review": "x" * 5001},
    ],
)
async def test_suivi_invalide(
    db_client: AsyncClient, contexte: Contexte, corps: dict[str, object]
) -> None:
    assert (await db_client.put(FILM, json=corps)).status_code == 422


async def test_contenu_inexistant_ou_source_en_panne(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    corps = {"status": "planned"}
    assert (await db_client.put("/api/tracking/tmdb/movie/404", json=corps)).status_code == 404
    contexte.source.en_panne = True
    assert (await db_client.put(FILM, json=corps)).status_code == 502


async def test_episodes_et_statut_automatique(db_client: AsyncClient, contexte: Contexte) -> None:
    saison1 = await episodes(db_client, 1)
    assert [(e["number"], e["watched"]) for e in saison1] == [(1, False), (2, False)]

    # Premier épisode coché : le suivi est créé automatiquement « en cours ».
    etat = await cocher(db_client, [e["id"] for e in saison1])
    assert etat["tracking"]["status"] == "watching"  # type: ignore[index]
    assert etat["progress"] == {"watched": 2, "total": 3, "percent": 67}
    assert all(e["watched"] for e in await episodes(db_client, 1))

    # Dernier épisode d'une série terminée : passage automatique à « terminé ».
    saison2 = await episodes(db_client, 2)
    etat = await cocher(db_client, [saison2[0]["id"]])
    assert etat["tracking"]["status"] == "completed"  # type: ignore[index]
    assert etat["progress"]["percent"] == 100  # type: ignore[index]

    # Un épisode décoché : retour à « en cours ».
    etat = await cocher(db_client, [saison2[0]["id"]], vu=False)
    assert etat["tracking"]["status"] == "watching"  # type: ignore[index]


async def test_episodes_speciaux_hors_progression(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    speciaux = await episodes(db_client, 0)
    etat = await cocher(db_client, [speciaux[0]["id"]])
    assert etat["progress"]["watched"] == 0  # type: ignore[index]


async def test_impossible_de_cocher_l_episode_d_un_autre_contenu(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    saison1 = await episodes(db_client, 1)
    await db_client.put(FILM, json={"status": "planned"})

    response = await db_client.post(
        f"{FILM}/episodes", json={"episode_ids": [saison1[0]["id"]], "watched": True}
    )
    assert response.status_code == 404


async def test_saison_ou_film_sans_episodes(db_client: AsyncClient, contexte: Contexte) -> None:
    assert (await db_client.get(f"{SERIE}/seasons/9")).status_code == 404
    assert (await db_client.get(f"{FILM}/seasons/1")).status_code == 404


async def test_mon_suivi_filtre_et_cloisonne(db_client: AsyncClient, contexte: Contexte) -> None:
    await db_client.put(FILM, json={"status": "completed"})
    await db_client.put(SERIE, json={"status": "planned"})

    tout = (await db_client.get("/api/tracking")).json()
    # Le plus récemment modifié en premier.
    assert [item["content"]["title"] for item in tout] == ["Game of Thrones", "Matrix"]
    termines = (await db_client.get("/api/tracking", params={"status": "completed"})).json()
    assert [item["content"]["title"] for item in termines] == ["Matrix"]

    # Bob ne voit rien du suivi d'Alice.
    contexte.connecter(contexte.bob)
    assert (await db_client.get("/api/tracking")).json() == []
    assert (await db_client.get(FILM)).json()["tracking"] is None


async def test_retirer_du_suivi_oublie_les_episodes(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    saison1 = await episodes(db_client, 1)
    await cocher(db_client, [saison1[0]["id"]])

    assert (await db_client.delete(SERIE)).status_code == 204

    etat = (await db_client.get(SERIE)).json()
    assert etat["tracking"] is None
    assert etat["progress"]["watched"] == 0
    assert not any(e["watched"] for e in await episodes(db_client, 1))


async def test_vu_jusqu_ici_coche_aussi_les_saisons_precedentes(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    # La saison 1 n'a jamais été ouverte : elle est chargée automatiquement.
    reponse = await db_client.post(
        f"{SERIE}/watched-until", json={"season_number": 2, "episode_number": 1, "watched": True}
    )
    assert reponse.status_code == 200
    etat = reponse.json()
    assert len(etat["changed_episode_ids"]) == 3  # S1É1, S1É2, S2É1 (pas l'épisode spécial)
    assert etat["progress"]["watched"] == 3
    assert all(e["watched"] for e in await episodes(db_client, 1))
    assert not any(e["watched"] for e in await episodes(db_client, 0))

    # « Pas vu à partir d'ici » depuis S1É2 : décoche S1É2 et toute la saison 2.
    etat = (
        await db_client.post(
            f"{SERIE}/watched-until",
            json={"season_number": 1, "episode_number": 2, "watched": False},
        )
    ).json()
    assert len(etat["changed_episode_ids"]) == 2
    assert etat["progress"]["watched"] == 1

    # Annuler (on erreur) : on recoche exactement les épisodes modifiés.
    etat = await cocher(db_client, etat["changed_episode_ids"])
    assert etat["progress"]["watched"] == 3


async def test_vu_jusqu_ici_refuse_pour_un_film(db_client: AsyncClient, contexte: Contexte) -> None:
    corps = {"season_number": 1, "episode_number": 1, "watched": True}
    assert (await db_client.post(f"{FILM}/watched-until", json=corps)).status_code == 404


async def test_termine_coche_tous_les_episodes_diffuses(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    etat = (await db_client.put(SERIE, json={"status": "completed"})).json()

    assert etat["tracking"]["status"] == "completed"
    assert etat["progress"] == {"watched": 3, "total": 3, "percent": 100}
    assert len(etat["changed_episode_ids"]) == 3  # saisons 1 et 2, pas l'épisode spécial
    assert etat["rewards"]["boosters"] >= 3  # un par épisode
    assert not any(e["watched"] for e in await episodes(db_client, 0))
