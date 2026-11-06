"""Tests des cartes : tirage, raretés, boosters, fragments et fabrication."""

import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, update

from app.models import Booster, CardWallet, Rarity
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


FILMS_DU_CATALOGUE = {"Matrix", "Pulp Fiction"}


async def remplir_catalogue(contexte: Contexte) -> int:
    """Catalogue de la fausse source : Matrix et Pulp Fiction (films), Frieren (anime)."""
    return await card_catalog.seed_catalog(
        contexte.session,
        None,  # type: ignore[arg-type]  (la fausse source n'utilise pas le réseau)
        [contexte.source],
    )


async def offrir_boosters(contexte: Contexte, nombre: int) -> None:
    for n in range(nombre):
        await gamification.grant_booster(contexte.session, contexte.alice.id, f"test:{n}")
    await contexte.session.commit()


@pytest.mark.integration
async def test_booster_de_bienvenue_catalogue_vide(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    moi = await collection(db_client)
    assert (moi["boosters"], moi["fragments"]) == (1, 0)
    assert (await db_client.get("/api/cards/binder")).json() == []
    assert 0 < moi["next_free_booster_in"] <= 300  # minuteur de 5 minutes lancé

    response = await db_client.post("/api/cards/boosters/open", json={"theme": "anime"})
    assert response.status_code == 409  # catalogue encore vide…
    assert (await collection(db_client))["boosters"] == 1  # … le booster est gardé


@pytest.mark.integration
async def test_cartes_sans_avoir_vu_le_contenu(db_client: AsyncClient, contexte: Contexte) -> None:
    await remplir_catalogue(contexte)

    # Bob n'a rien vu ni suivi : il obtient quand même des cartes du catalogue.
    contexte.connecter(contexte.bob)
    booster = await ouvrir(db_client, "movie")
    assert booster["theme"] == "movie"
    assert len(booster["cards"]) == 5
    assert {c["card"]["content"]["title"] for c in booster["cards"]} <= FILMS_DU_CATALOGUE
    # Aucune œuvre Disney+ dans le catalogue : pack indisponible.
    await offrir_boosters(contexte, 1)
    response = await db_client.post("/api/cards/boosters/open", json={"theme": "disney"})
    assert response.status_code == 409


@pytest.mark.integration
async def test_suivre_une_oeuvre_ne_l_ajoute_pas_au_catalogue(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    # Game of Thrones n'est pas dans le classement de la fausse source.
    await db_client.put(SERIE, json={"status": "watching"})
    await remplir_catalogue(contexte)
    response = await db_client.post("/api/cards/boosters/open", json={"theme": "series"})
    assert response.status_code == 409  # pas de série dans le catalogue


@pytest.mark.integration
async def test_doublons_en_fragments(db_client: AsyncClient, contexte: Contexte) -> None:
    await remplir_catalogue(contexte)
    await offrir_boosters(contexte, 2)

    fragments = 0
    for _ in range(3):
        booster = await ouvrir(db_client, "movie")
        for tirage in booster["cards"]:
            if not tirage["is_new"]:
                assert tirage["fragments"] > 0
                fragments += tirage["fragments"]
    # 15 cartes tirées parmi 10 cartes de films : forcément des doublons.
    assert fragments > 0
    assert (await collection(db_client))["fragments"] == fragments


@pytest.mark.integration
async def test_vos_contenus_ont_deux_fois_plus_de_chances(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    await remplir_catalogue(contexte)
    await db_client.put(FILM, json={"status": "watching"})  # Alice suit Matrix
    alice = await cards.available_pool(contexte.session, contexte.alice.id, PackTheme.MOVIE)
    bob = await cards.available_pool(contexte.session, contexte.bob.id, PackTheme.MOVIE)
    # Les 5 cartes de Matrix comptent double pour Alice.
    assert len(bob) == 10
    assert len(alice) == len(bob) + 5


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
async def test_un_booster_par_oeuvre_terminee(db_client: AsyncClient, contexte: Contexte) -> None:
    ids = [e["id"] for e in (await db_client.get(f"{SERIE}/seasons/1")).json()]
    etat = (
        await db_client.post(f"{SERIE}/episodes", json={"episode_ids": ids, "watched": True})
    ).json()
    assert etat["rewards"]["boosters"] == 0  # cocher des épisodes ne donne pas de booster

    # Dernier épisode : la série est terminée (+1 booster), niveau 2 atteint (+1).
    ids2 = [e["id"] for e in (await db_client.get(f"{SERIE}/seasons/2")).json()]
    etat = (
        await db_client.post(f"{SERIE}/episodes", json={"episode_ids": ids2, "watched": True})
    ).json()
    assert etat["tracking"]["status"] == "completed"
    assert etat["rewards"]["boosters"] == 2

    # Un film terminé : +1 booster.
    film = (await db_client.put(FILM, json={"status": "completed"})).json()
    assert film["rewards"]["boosters"] == 1
    # Changer d'avis puis le remettre en « terminé » ne redonne rien.
    await db_client.put(FILM, json={"status": "watching"})
    film = (await db_client.put(FILM, json={"status": "completed"})).json()
    assert (film["rewards"] or {}).get("boosters", 0) == 0
    assert (await collection(db_client))["boosters"] == 1 + 2 + 1  # + bienvenue


@pytest.mark.integration
async def test_fabriquer_une_carte(db_client: AsyncClient, contexte: Contexte) -> None:
    await remplir_catalogue(contexte)
    await db_client.put(FILM, json={"status": "watching"})  # Matrix dans le classeur
    await ouvrir(db_client, "movie")
    classeur = (await db_client.get("/api/cards/binder")).json()
    matrix = next(p for p in classeur if p["content"]["title"] == "Matrix")
    assert matrix["total"] == 5
    page = (await db_client.get(f"/api/cards/binder/{matrix['content']['id']}")).json()
    cartes = page["cards"]
    assert cartes[0]["rarity"] == "divine"  # de la plus rare à la plus commune
    assert sum(c["owned"] for c in cartes) == matrix["owned"]
    divine = next(c for c in cartes if c["rarity"] == "divine")
    # Sous le nom : l'importance du personnage, jamais l'acteur ni le doubleur.
    assert (divine["title"], divine["subtitle"]) == ("Neo (603)", "Héros")
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
    assert await remplir_catalogue(contexte) == 3  # Matrix, Pulp Fiction, Frieren

    # Personne ne suit ces œuvres, et pourtant leurs cartes sont tirables.
    booster = await ouvrir(db_client, "movie")
    assert {c["card"]["content"]["title"] for c in booster["cards"]} <= FILMS_DU_CATALOGUE
    # Uniquement des personnages : ni affiche ni décor.
    assert {c["card"]["kind"] for c in booster["cards"]} == {"character"}


@pytest.mark.integration
async def test_les_films_d_une_saga_sont_regroupes(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    from app.providers.base import ContentDetail, ContentKind, SearchResult, Source

    # Matrix et Pulp Fiction appartiennent (pour le test) à la même saga.
    contexte.source.sagas = {"603": ("77", "Saga test"), "680": ("77", "Saga test")}
    parties = [
        SearchResult(source=Source.TMDB, kind=ContentKind.MOVIE, external_id=i, title=t)
        for i, t in (("603", "Matrix"), ("680", "Pulp Fiction"))
    ]
    fiche_normale = contexte.source.get_detail

    async def fiche(http, kind, external_id):  # type: ignore[no-untyped-def]
        if kind == ContentKind.SAGA:
            return ContentDetail(
                source=Source.TMDB,
                kind=ContentKind.SAGA,
                external_id=external_id,
                title="Saga test",
                source_url="https://exemple.fr/saga",
                parts=parties,
            )
        return await fiche_normale(http, kind, external_id)

    contexte.source.get_detail = fiche  # type: ignore[method-assign]

    # Une seule œuvre pour les deux films (plus Frieren côté animes).
    assert await remplir_catalogue(contexte) == 2
    booster = await ouvrir(db_client, "movie")
    assert {c["card"]["content"]["title"] for c in booster["cards"]} == {"Saga test"}
    assert {c["card"]["content"]["kind"] for c in booster["cards"]} == {"saga"}


@pytest.mark.integration
async def test_packs_par_plateforme(db_client: AsyncClient, contexte: Contexte) -> None:
    await remplir_catalogue(contexte)  # Matrix : sur aucune plateforme
    moi = await collection(db_client)
    packs = {theme["theme"]: theme["cards"] for theme in moi["themes"]}
    assert packs["netflix"] == 5  # les 5 personnages
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
    assert (pack["label"], pack["total"], pack["matching"]) == ("Netflix", 5, 5)
    # De la plus rare à la plus commune, un personnage différent à chaque rareté haute.
    assert [(c["rarity"], c["title"]) for c in pack["cards"]] == [
        ("divine", "Neo (680)"),
        ("mythic", "Morpheus (680)"),
        ("legendary", "Oracle (680)"),
        ("legendary", "Tank (680)"),
        ("common", "Figurant (680)"),
    ]
    assert not any(c["owned"] for c in pack["cards"])
    # Une seule Divine par œuvre : celle de son héros.
    assert {r["rarity"]: r["count"] for r in pack["rarities"]}["divine"] == 1

    params = {"rarity": "mythic"}
    mythiques = (await db_client.get("/api/cards/packs/netflix", params=params)).json()
    assert [c["title"] for c in mythiques["cards"]] == ["Morpheus (680)"]
    trouve = (await db_client.get("/api/cards/packs/netflix", params={"q": "tank"})).json()
    assert [c["title"] for c in trouve["cards"]] == ["Tank (680)"]
    # Les caractères spéciaux ne cassent pas la recherche.
    vide = (await db_client.get("/api/cards/packs/netflix", params={"q": "%_"})).json()
    assert vide["matching"] == 0
    params = {"offset": 3, "limit": 5}
    page2 = (await db_client.get("/api/cards/packs/netflix", params=params)).json()
    assert len(page2["cards"]) == 2
    assert (await db_client.get("/api/cards/packs/inconnu")).status_code == 422


@pytest.mark.integration
async def test_rattrapage_des_oeuvres_deja_terminees(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    await db_client.put(FILM, json={"status": "completed"})
    # Simule un film terminé avant la règle « un booster par œuvre terminée ».
    await contexte.session.execute(
        delete(Booster).where(
            Booster.user_id == contexte.alice.id, Booster.key.like("completion:%")
        )
    )
    await contexte.session.commit()

    assert (await collection(db_client))["boosters"] == 1 + 1  # bienvenue + Matrix


@pytest.mark.integration
async def test_ouvrir_plusieurs_boosters_d_un_coup(
    db_client: AsyncClient, contexte: Contexte
) -> None:
    await remplir_catalogue(contexte)
    await offrir_boosters(contexte, 3)  # 4 boosters avec celui de bienvenue

    response = await db_client.post(
        "/api/cards/boosters/open", json={"theme": "movie", "count": 10}
    )
    assert response.status_code == 200
    resultat = response.json()
    assert resultat["boosters_opened"] == 4  # on s'arrête quand il n'y en a plus
    assert len(resultat["cards"]) == 20
    assert resultat["boosters_left"] == 0
    response = await db_client.post("/api/cards/boosters/open", json={"count": 11})
    assert response.status_code == 422  # 10 au maximum


@pytest.mark.integration
async def test_classeur_oeuvre_introuvable(db_client: AsyncClient, contexte: Contexte) -> None:
    assert (await db_client.get("/api/cards/binder/999999999")).status_code == 404


def test_un_personnage_different_par_rarete_haute() -> None:
    from app.providers.base import CharacterRole as Role
    from app.services.cards import rarity_for

    assert [rarity_for(rang, Role.MAIN) for rang in range(6)] == [
        Rarity.DIVINE,
        Rarity.MYTHIC,
        Rarity.LEGENDARY,
        Rarity.LEGENDARY,
        Rarity.EPIC,
        Rarity.EPIC,
    ]
    assert rarity_for(10, Role.SUPPORTING) == Rarity.RARE
    assert rarity_for(30, Role.BACKGROUND) == Rarity.COMMON


def test_titres_de_profil() -> None:
    from app.services.titles import title_for

    assert title_for("ONE PIECE") == "Roi des pirates"
    assert title_for("Naruto Shippuden") == "Hokage"
    assert title_for("Harry Potter") == "Grand sorcier"
    assert title_for("Le Seigneur des anneaux") == "Porteur de l'Anneau"
    assert title_for("Matrix") == "Maître de Matrix"


@pytest.mark.integration
async def test_collection_complete(db_client: AsyncClient, contexte: Contexte) -> None:
    from sqlalchemy import select

    from app.models import Card, Content, UserCard

    await remplir_catalogue(contexte)
    matrix = await contexte.session.scalar(select(Content).where(Content.external_id == "603"))
    assert matrix is not None
    cartes = list(await contexte.session.scalars(select(Card).where(Card.content_id == matrix.id)))
    # Alice possède déjà toutes les cartes de Matrix sauf une (fabricable).
    derniere = next(c for c in cartes if c.rarity != "divine")
    contexte.session.add_all(
        UserCard(user_id=contexte.alice.id, card_id=c.id) for c in cartes if c.id != derniere.id
    )
    await contexte.session.execute(
        update(CardWallet).where(CardWallet.user_id == contexte.alice.id).values(fragments=1000)
    )
    await collection(db_client)  # crée le portefeuille
    await contexte.session.execute(
        update(CardWallet).where(CardWallet.user_id == contexte.alice.id).values(fragments=1000)
    )
    await contexte.session.commit()

    fabrique = (await db_client.post(f"/api/cards/{derniere.id}/craft")).json()

    [maitrise] = fabrique["masteries"]
    assert (maitrise["work_title"], maitrise["title"]) == ("Matrix", "Maître de Matrix")
    gains = {line["label"]: line["amount"] for line in maitrise["rewards"]["lines"]}
    assert gains["Collection complète"] == 500
    # 5 boosters de collection (+ ceux des niveaux gagnés grâce aux 500 XP).
    assert maitrise["rewards"]["boosters"] >= 5
    assert "maitre_collection" in [b["code"] for b in maitrise["rewards"]["badges"]]

    # Classeur et page de l'œuvre : la carte « Maître » est là.
    classeur = (await db_client.get("/api/cards/binder")).json()
    assert next(p for p in classeur if p["content"]["id"] == matrix.id)["mastered"] is True
    page = (await db_client.get(f"/api/cards/binder/{matrix.id}")).json()
    assert page["mastery"]["title"] == "Maître de Matrix"

    # Le titre s'affiche sur le profil, une fois choisi.
    moi = (await db_client.patch("/api/users/me", json={"title_content_id": matrix.id})).json()
    assert moi["title"] == "Maître de Matrix"
    assert (await db_client.get("/api/users/me")).json()["title"] == "Maître de Matrix"
    # Et s'enlève avec null.
    assert (await db_client.patch("/api/users/me", json={"title_content_id": None})).json()[
        "title"
    ] is None


@pytest.mark.integration
async def test_titre_non_merite_refuse(db_client: AsyncClient, contexte: Contexte) -> None:
    await remplir_catalogue(contexte)
    from sqlalchemy import select

    from app.models import Content

    pulp = await contexte.session.scalar(select(Content).where(Content.external_id == "680"))
    assert pulp is not None
    reponse = await db_client.patch("/api/users/me", json={"title_content_id": pulp.id})
    assert reponse.status_code == 409
    assert (await db_client.get("/api/cards/masteries")).json() == []
