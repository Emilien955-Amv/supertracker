"""Tests des échanges de cartes entre amis."""

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select

from app.models import Card, UserCard
from tests.conftest import Contexte
from tests.test_cards import remplir_catalogue


async def devenir_amis(client: AsyncClient, contexte: Contexte) -> None:
    contexte.connecter(contexte.bob)
    await client.post("/api/friends/alice_test")
    contexte.connecter(contexte.alice)
    await client.post("/api/friends/bob_test")


async def donner(contexte: Contexte, user_id: int, card: Card, copies: int = 1) -> None:
    contexte.session.add(UserCard(user_id=user_id, card_id=card.id, copies=copies))
    await contexte.session.commit()


async def exemplaires(contexte: Contexte, user_id: int, card: Card | int) -> int:
    card_id = card if isinstance(card, int) else card.id
    copies = await contexte.session.scalar(
        select(UserCard.copies).where(UserCard.user_id == user_id, UserCard.card_id == card_id)
    )
    return copies or 0


async def deux_cartes(contexte: Contexte) -> tuple[Card, Card]:
    await remplir_catalogue(contexte)
    zoro, luffy = list(await contexte.session.scalars(select(Card).order_by(Card.id).limit(2)))
    return zoro, luffy


async def preparer(client: AsyncClient, contexte: Contexte) -> tuple[Card, Card]:
    """Alice a « Zoro » en double, Bob a « Luffy » : de quoi échanger."""
    zoro, luffy = await deux_cartes(contexte)
    await donner(contexte, contexte.alice.id, zoro, copies=2)
    await donner(contexte, contexte.bob.id, luffy)
    await devenir_amis(client, contexte)
    return zoro, luffy


async def proposer(client: AsyncClient, give: list[int], take: list[int]) -> Response:
    return await client.post(
        "/api/trades",
        json={"username": "bob_test", "give": give, "take": take, "message": "Ça te va ?"},
    )


@pytest.mark.integration
async def test_echange_accepte(db_client: AsyncClient, contexte: Contexte) -> None:
    zoro, luffy = await preparer(db_client, contexte)
    response = await proposer(db_client, [zoro.id], [luffy.id])
    assert response.status_code == 201, response.text
    echange = response.json()
    assert (echange["direction"], echange["status"], echange["partner"]) == (
        "outgoing",
        "pending",
        "bob_test",
    )
    # Rien ne bouge tant que Bob n'a pas accepté.
    assert await exemplaires(contexte, contexte.alice.id, zoro) == 2

    contexte.connecter(contexte.bob)
    recus = (await db_client.get("/api/trades")).json()
    assert [(t["id"], t["direction"]) for t in recus] == [(echange["id"], "incoming")]
    assert [c["id"] for c in recus[0]["gives"]] == [zoro.id]
    response = await db_client.post(f"/api/trades/{echange['id']}/accept")
    assert response.status_code == 200, response.text

    assert await exemplaires(contexte, contexte.alice.id, zoro) == 1  # un exemplaire gardé
    assert await exemplaires(contexte, contexte.alice.id, luffy) == 1
    assert await exemplaires(contexte, contexte.bob.id, zoro) == 1
    assert await exemplaires(contexte, contexte.bob.id, luffy) == 0  # sa seule carte est partie
    # Déjà accepté : impossible de recommencer.
    assert (await db_client.post(f"/api/trades/{echange['id']}/accept")).status_code == 409


@pytest.mark.integration
async def test_carte_plus_disponible_rien_ne_bouge(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    zoro, luffy = await preparer(db_client, contexte)
    zoro_id, alice_id = zoro.id, contexte.alice.id  # l'échec annule la session
    echange = (await proposer(db_client, [zoro.id], [luffy.id])).json()
    # Entre-temps, Bob a perdu Luffy (par exemple dans un autre échange).
    ligne = await contexte.session.get(UserCard, (contexte.bob.id, luffy.id))
    await contexte.session.delete(ligne)
    await contexte.session.commit()

    contexte.connecter(contexte.bob)
    assert (await db_client.post(f"/api/trades/{echange['id']}/accept")).status_code == 409
    assert await exemplaires(contexte, alice_id, zoro_id) == 2  # tout ou rien


@pytest.mark.integration
async def test_refuser_et_annuler(db_client: AsyncClient, contexte: Contexte) -> None:
    zoro, luffy = await preparer(db_client, contexte)
    premier = (await proposer(db_client, [zoro.id], [luffy.id])).json()
    second = (await proposer(db_client, [zoro.id], [])).json()  # un cadeau

    # Alice ne peut pas accepter son propre échange.
    assert (await db_client.post(f"/api/trades/{premier['id']}/accept")).status_code == 404
    assert (await db_client.post(f"/api/trades/{second['id']}/cancel")).status_code == 204

    contexte.connecter(contexte.bob)
    assert (await db_client.post(f"/api/trades/{second['id']}/accept")).status_code == 409
    assert (await db_client.post(f"/api/trades/{premier['id']}/decline")).status_code == 204
    statuts = {t["id"]: t["status"] for t in (await db_client.get("/api/trades")).json()}
    assert statuts == {premier["id"]: "declined", second["id"]: "cancelled"}
    assert await exemplaires(contexte, contexte.bob.id, luffy) == 1


@pytest.mark.integration
async def test_reserve_aux_amis_et_aux_cartes_possedees(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    zoro, luffy = await deux_cartes(contexte)
    await donner(contexte, contexte.alice.id, zoro)
    # Pas encore amis.
    assert (await proposer(db_client, [zoro.id], [])).status_code == 403
    assert (await db_client.get("/api/trades/partner/bob_test/works")).status_code == 403

    await devenir_amis(db_client, contexte)
    assert (await proposer(db_client, [], [])).status_code == 409  # rien choisi
    assert (await proposer(db_client, [luffy.id], [])).status_code == 409  # pas à Alice
    assert (await proposer(db_client, [], [luffy.id])).status_code == 409  # pas à Bob
    assert (await proposer(db_client, [zoro.id], [zoro.id])).status_code == 409


@pytest.mark.integration
async def test_collection_d_un_ami(db_client: AsyncClient, contexte: Contexte) -> None:
    zoro, luffy = await preparer(db_client, contexte)
    oeuvres = (await db_client.get("/api/trades/partner/bob_test/works")).json()
    assert sum(o["mine"] for o in oeuvres) == 1
    assert sum(o["theirs"] for o in oeuvres) == 1

    url = f"/api/trades/partner/bob_test/works/{zoro.content_id}"
    par_id = {c["card"]["id"]: (c["mine"], c["theirs"]) for c in (await db_client.get(url)).json()}
    assert par_id[zoro.id] == (2, 0)
    if luffy.content_id == zoro.content_id:
        assert par_id[luffy.id] == (0, 1)
