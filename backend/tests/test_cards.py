"""Tests des cartes : tirage, raretés, boosters, fragments et fabrication."""

import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models import CardWallet, Rarity
from app.services import card_catalog, cards, gamification
from app.services.cards import EPIC_OR_BETTER, RARE_OR_BETTER, PackTheme, draw
from tests.conftest import Contexte

FILM = "/api/tracking/tmdb/movie/603"
SERIE = "/api/tracking/tmdb/series/1399"

# Réserve de test : 20 cartes de chaque rareté.
POOL = [(i * 100 + n, rarity) for i, rarity in enumerate(Rarity) for n in range(20)]


# --- Tirage (fonction pure, générateur aléatoire fixé : résultats reproductibles) --


def test_booster_de_5_cartes_avec_une_rare_garantie() -> None:
    rng = random.Random(42)
    for _ in range(500):
        cartes = draw(POOL, boosters_since_epic=0, rng=rng)
        assert len(cartes) == 5
        assert len({card_id for card_id, _ in cartes}) == 5  # jamais deux fois la même
        assert any(rarity in RARE_OR_BETTER for _, rarity in cartes)


def test_filet_de_securite_apres_19_boosters_sans_epique() -> None:
    rng = random.Random(7)
    for _ in range(500):
        cartes = draw(POOL, boosters_since_epic=19, rng=rng)
        assert any(rarity in EPIC_OR_BETTER for _, rarity in cartes)


def test_probabilites_respectees() -> None:
    rng = random.Random(1)
    # Les 4 premières cartes suivent les probabilités affichées (la 5e est
    # « améliorée » par la Rare garantie) : 20 000 boosters = 80 000 cartes.
    compte = Counter(rarity for _ in range(20_000) for _, rarity in draw(POOL, 0, rng)[:4])
    pourcent = {rarity: 100 * n / 80_000 for rarity, n in compte.items()}
    assert pourcent[Rarity.COMMON] == pytest.approx(50, abs=1)
    assert pourcent[Rarity.LEGENDARY] == pytest.approx(3.5, abs=0.4)
    assert pourcent[Rarity.MYTHIC] == pytest.approx(1, abs=0.25)
    assert pourcent[Rarity.DIVINE] == pytest.approx(0.5, abs=0.2)


def test_rarete_absente_remplacee_par_la_plus_proche() -> None:
    # Que des Communes (ex. contenu sans personnages) : le tirage fonctionne quand même.
    cartes = draw([(1, Rarity.COMMON), (2, Rarity.COMMON)], 0, random.Random(3))
    assert {rarity for _, rarity in cartes} == {Rarity.COMMON}


# --- Avec la base de données --------------------------------------------------


async def collection(client: AsyncClient) -> dict[str, Any]:
    result: dict[str, Any] = (await client.get("/api/cards/me")).json()
    return result


async def ouvrir(client: AsyncClient, theme: str = "mixed") -> dict[str, Any]:
    response = await client.post("/api/cards/boosters/open", json={"theme": theme})
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


async def offrir_boosters(contexte: Contexte, nombre: int) -> None:
    for n in range(nombre):
        await gamification.grant_booster(contexte.session, contexte.alice.id, f"test:{n}")
    await contexte.session.commit()


@pytest.mark.integration
async def test_booster_de_bienvenue_catalogue_vide(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    moi = await collection(db_client)
    assert (moi["boosters"], moi["fragments"], moi["cards"]) == (1, 0, [])
    assert 0 < moi["next_free_booster_in"] <= 300  # minuteur de 5 minutes lancé

    response = await db_client.post("/api/cards/boosters/open", json={"theme": "anime"})
    assert response.status_code == 409  # catalogue encore vide…
    assert (await collection(db_client))["boosters"] == 1  # … le booster est gardé


@pytest.mark.integration
async def test_cartes_sans_avoir_vu_le_contenu(db_client: AsyncClient, contexte: Contexte) -> None:
    # Alice ajoute Matrix à « À voir » : ses cartes rejoignent le catalogue commun.
    await db_client.put(FILM, json={"status": "planned"})
    await collection(db_client)

    # Bob n'a rien vu ni suivi : il obtient quand même des cartes Matrix.
    contexte.connecter(contexte.bob)
    booster = await ouvrir(db_client, "movie")
    assert booster["theme"] == "movie"
    assert len(booster["cards"]) == 5
    assert {c["card"]["content"]["title"] for c in booster["cards"]} == {"Matrix"}
    # Aucun anime dans le catalogue : pack « Animes » indisponible.
    await offrir_boosters(contexte, 1)
    response = await db_client.post("/api/cards/boosters/open", json={"theme": "anime"})
    assert response.status_code == 409


@pytest.mark.integration
async def test_doublons_en_fragments(db_client: AsyncClient, contexte: Contexte) -> None:
    await db_client.put(FILM, json={"status": "watching"})
    await collection(db_client)
    await offrir_boosters(contexte, 2)

    fragments = 0
    for _ in range(3):
        booster = await ouvrir(db_client, "movie")
        for tirage in booster["cards"]:
            if not tirage["is_new"]:
                assert tirage["fragments"] > 0
                fragments += tirage["fragments"]
    # 15 cartes tirées parmi 7 cartes Matrix : forcément des doublons.
    assert fragments > 0
    assert (await collection(db_client))["fragments"] == fragments


@pytest.mark.integration
async def test_vos_contenus_ont_deux_fois_plus_de_chances(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    await db_client.put(FILM, json={"status": "watching"})
    await collection(db_client)
    alice = await cards.available_pool(contexte.session, contexte.alice.id, PackTheme.MOVIE)
    bob = await cards.available_pool(contexte.session, contexte.bob.id, PackTheme.MOVIE)
    assert len(alice) == 2 * len(bob) > 0


@pytest.mark.integration
async def test_un_booster_toutes_les_5_minutes(contexte: Contexte) -> None:
    session = contexte.session
    user_id = contexte.alice.id
    # Début d'un créneau de 5 minutes (+1 seconde), pour un calcul exact.
    debut = datetime.fromtimestamp(cards.current_slot() * cards.TIMER_SECONDS + 1, UTC)

    await cards.sync_boosters(session, user_id, now=debut)
    assert await cards.count_boosters(session, user_id) == 1  # bienvenue
    await cards.sync_boosters(session, user_id, now=debut + timedelta(minutes=12))
    assert await cards.count_boosters(session, user_id) == 1 + 2  # 2 créneaux écoulés
    # Absent 10 heures : la réserve s'arrête à 12 boosters du minuteur.
    await cards.sync_boosters(session, user_id, now=debut + timedelta(hours=10))
    assert await cards.count_boosters(session, user_id) == 1 + cards.TIMER_MAX_STOCK


@pytest.mark.integration
async def test_un_booster_par_episode_vu(db_client: AsyncClient, contexte: Contexte) -> None:
    ids = [e["id"] for e in (await db_client.get(f"{SERIE}/seasons/1")).json()]
    etat = (
        await db_client.post(f"{SERIE}/episodes", json={"episode_ids": ids, "watched": True})
    ).json()
    assert etat["rewards"]["boosters"] == 2  # 2 épisodes

    # Décocher puis recocher ne redonne aucun booster.
    await db_client.post(f"{SERIE}/episodes", json={"episode_ids": ids, "watched": False})
    etat = (
        await db_client.post(f"{SERIE}/episodes", json={"episode_ids": ids, "watched": True})
    ).json()
    assert (etat["rewards"] or {}).get("boosters", 0) == 0

    # Dernier épisode : +1 (épisode) +1 (série terminée) +1 (niveau 2).
    ids2 = [e["id"] for e in (await db_client.get(f"{SERIE}/seasons/2")).json()]
    etat = (
        await db_client.post(f"{SERIE}/episodes", json={"episode_ids": ids2, "watched": True})
    ).json()
    assert etat["rewards"]["boosters"] == 3
    assert (await collection(db_client))["boosters"] == 1 + 2 + 3  # + bienvenue


@pytest.mark.integration
async def test_fabriquer_une_carte(db_client: AsyncClient, contexte: Contexte) -> None:
    await db_client.put(FILM, json={"status": "watching"})
    await ouvrir(db_client, "movie")
    cartes = (await collection(db_client))["cards"]
    divine = next(c for c in cartes if c["rarity"] == "divine")
    # Sous le nom : l'importance du personnage, jamais l'acteur ni le doubleur.
    assert divine["subtitle"] == "Édition Divine"
    morpheus = {c["subtitle"] for c in cartes if c["title"].startswith("Morpheus")}
    assert morpheus == {"Rôle principal"}

    manquante = next((c for c in cartes if not c["owned"] and c["craft_cost"]), None)
    if manquante is not None:  # sinon : toutes obtenues d'un coup, rien à fabriquer
        response = await db_client.post(f"/api/cards/{manquante['id']}/craft")
        assert response.status_code == 409  # pas assez de fragments
        await contexte.session.execute(
            update(CardWallet).where(CardWallet.user_id == contexte.alice.id).values(fragments=1000)
        )
        await contexte.session.commit()

        response = await db_client.post(f"/api/cards/{manquante['id']}/craft")
        assert response.status_code == 200
        assert response.json()["fragments"] == 1000 - manquante["craft_cost"]
        response = await db_client.post(f"/api/cards/{manquante['id']}/craft")
        assert response.status_code == 409  # déjà possédée

    # Les Divines ne se fabriquent pas : uniquement par chance.
    assert divine["craft_cost"] is None
    if not divine["owned"]:
        assert (await db_client.post(f"/api/cards/{divine['id']}/craft")).status_code == 404


@pytest.mark.integration
async def test_catalogue_des_contenus_populaires(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    traites = await card_catalog.seed_catalog(
        contexte.session,
        None,  # type: ignore[arg-type]  (la fausse source n'utilise pas le réseau)
        [contexte.source],
    )

    assert traites == 2  # Pulp Fiction et Frieren
    # Personne ne suit Pulp Fiction, et pourtant ses cartes sont tirables.
    booster = await ouvrir(db_client, "movie")
    assert {c["card"]["content"]["title"] for c in booster["cards"]} == {"Pulp Fiction"}
    # Uniquement des personnages : ni affiche ni décor.
    assert {c["card"]["kind"] for c in booster["cards"]} == {"character"}


@pytest.mark.integration
async def test_packs_par_plateforme(db_client: AsyncClient, contexte: Contexte) -> None:
    await db_client.put(FILM, json={"status": "watching"})  # Matrix : sur aucune plateforme
    await card_catalog.seed_catalog(
        contexte.session,
        None,  # type: ignore[arg-type]  (la fausse source n'utilise pas le réseau)
        [contexte.source],
    )
    moi = await collection(db_client)
    packs = {theme["theme"]: theme["cards"] for theme in moi["themes"]}
    assert packs["netflix"] == 7  # les 7 cartes de Pulp Fiction
    assert packs["disney"] == 0

    booster = await ouvrir(db_client, "netflix")
    assert {c["card"]["content"]["title"] for c in booster["cards"]} == {"Pulp Fiction"}
    await offrir_boosters(contexte, 1)
    response = await db_client.post("/api/cards/boosters/open", json={"theme": "disney"})
    assert response.status_code == 409  # aucune carte Disney+ pour l'instant


@pytest.mark.integration
async def test_anime_signale_sur_crunchyroll(db_client: AsyncClient, contexte: Contexte) -> None:
    await card_catalog.seed_catalog(
        contexte.session,
        None,  # type: ignore[arg-type]
        [contexte.source],
    )
    booster = await ouvrir(db_client, "crunchyroll")
    assert {c["card"]["content"]["title"] for c in booster["cards"]} == {"Frieren"}


@pytest.mark.integration
async def test_liste_des_cartes_d_un_pack(db_client: AsyncClient, contexte: Contexte) -> None:
    await card_catalog.seed_catalog(
        contexte.session,
        None,  # type: ignore[arg-type]
        [contexte.source],
    )

    pack = (await db_client.get("/api/cards/packs/netflix")).json()
    assert (pack["label"], pack["total"], pack["matching"]) == ("Netflix", 7, 7)
    # De la plus rare à la plus commune.
    assert [c["rarity"] for c in pack["cards"]] == [
        "divine",
        "mythic",
        "legendary",
        "epic",
        "rare",
        "uncommon",
        "common",
    ]
    assert not any(c["owned"] for c in pack["cards"])
    assert {r["rarity"]: r["count"] for r in pack["rarities"]}["epic"] == 1
    # Une seule Divine par œuvre : celle de son héros.
    assert {r["rarity"]: r["count"] for r in pack["rarities"]}["divine"] == 1

    epiques = (await db_client.get("/api/cards/packs/netflix", params={"rarity": "epic"})).json()
    assert [c["title"] for c in epiques["cards"]] == ["Morpheus (680)"]
    trouve = (await db_client.get("/api/cards/packs/netflix", params={"q": "tank"})).json()
    assert [c["title"] for c in trouve["cards"]] == ["Tank (680)"]
    # Les caractères spéciaux ne cassent pas la recherche.
    assert (await db_client.get("/api/cards/packs/netflix", params={"q": "%_"})).json()[
        "matching"
    ] == 0
    page2 = (
        await db_client.get("/api/cards/packs/netflix", params={"offset": 5, "limit": 5})
    ).json()
    assert len(page2["cards"]) == 2
    assert (await db_client.get("/api/cards/packs/inconnu")).status_code == 422
