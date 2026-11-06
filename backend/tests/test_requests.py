"""Tests des sondages : demander les cartes d'une œuvre et voter."""

import pytest
from httpx import AsyncClient

from app.config import get_settings
from tests.conftest import Contexte

pytestmark = pytest.mark.integration

GOT = {"source": "tmdb", "kind": "series", "external_id": "1399"}
MATRIX = {"source": "tmdb", "kind": "movie", "external_id": "603"}


@pytest.fixture
def deux_votes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Seuil abaissé à 2 votes : Alice et Bob suffisent."""
    monkeypatch.setattr(get_settings(), "card_request_votes", 2)


async def test_demande_puis_ajout_au_seuil(
    db_client: AsyncClient, contexte: Contexte, deux_votes: None
) -> None:
    demande = (await db_client.post("/api/requests", json=GOT)).json()
    assert (demande["title"], demande["votes"], demande["status"]) == ("Game of Thrones", 1, "open")
    # Revoter ne compte pas deux fois.
    assert (await db_client.post("/api/requests", json=GOT)).json()["votes"] == 1
    assert (
        await db_client.post("/api/cards/boosters/open", json={"theme": "series"})
    ).status_code == 409

    # Bob vote à son tour : le seuil est atteint, la série entre au catalogue.
    contexte.connecter(contexte.bob)
    demande = (await db_client.post("/api/requests", json=GOT)).json()
    assert (demande["votes"], demande["status"]) == (2, "added")
    etat = (await db_client.get("/api/requests/status/tmdb/series/1399")).json()
    assert etat["in_catalog"] is True
    booster = (await db_client.post("/api/cards/boosters/open", json={"theme": "series"})).json()
    assert {c["card"]["content"]["title"] for c in booster["cards"]} == {"Game of Thrones"}

    # Déjà au catalogue : plus de demande possible.
    assert (await db_client.post("/api/requests", json=GOT)).status_code == 409


async def test_liste_et_retrait_de_vote(db_client: AsyncClient, contexte: Contexte) -> None:
    demande = (await db_client.post("/api/requests", json=MATRIX)).json()
    liste = (await db_client.get("/api/requests")).json()
    assert [(d["title"], d["voted"], d["votes_needed"]) for d in liste] == [("Matrix", True, 3)]

    etat = (await db_client.get("/api/requests/status/tmdb/movie/603")).json()
    assert etat["in_catalog"] is False and etat["request"]["votes"] == 1

    # Plus aucun vote : la demande disparaît.
    assert (await db_client.delete(f"/api/requests/{demande['id']}/vote")).status_code == 204
    assert (await db_client.get("/api/requests")).json() == []


async def test_film_d_une_saga_demande_la_saga(db_client: AsyncClient, contexte: Contexte) -> None:
    from app.providers.base import ContentDetail, ContentKind, Source

    contexte.source.sagas = {"603": ("77", "Matrix - Saga")}
    fiche_normale = contexte.source.get_detail

    async def fiche(http, kind, external_id):  # type: ignore[no-untyped-def]
        if kind == ContentKind.SAGA:
            return ContentDetail(
                source=Source.TMDB,
                kind=kind,
                external_id=external_id,
                title="Matrix",
                source_url="https://exemple.fr/saga",
            )
        return await fiche_normale(http, kind, external_id)

    contexte.source.get_detail = fiche  # type: ignore[method-assign]

    demande = (await db_client.post("/api/requests", json=MATRIX)).json()
    assert (demande["kind"], demande["external_id"]) == ("saga", "77")
