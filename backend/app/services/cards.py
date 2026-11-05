"""Cartes à collectionner : catalogue, boosters par thème, fragments.

Raretés et probabilités par carte tirée :
    Commune      50 %    affiches, figurants
    Peu commune  25 %    images de fond, images d'épisodes
    Rare         13 %    seconds rôles, premier et dernier épisodes
    Épique        7 %    rôles principaux
    Légendaire    3,5 %  LE héros (le personnage principal)
    Mythique      1 %    le héros, édition Mythique
    Divine        0,5 %  le héros, édition Divine (impossible à fabriquer)

Règles :
- les cartes viennent d'un catalogue commun : contenus populaires du moment
  (renouvelés chaque jour) + contenus suivis par les joueurs. Pas besoin
  d'avoir vu un contenu pour obtenir ses cartes ;
- les contenus de VOTRE suivi ont deux fois plus de chances de sortir ;
- on choisit le thème du booster : animes, films, séries ou mélange ;
- 5 cartes par booster, dont au moins une Rare (ou mieux) ;
- filet de sécurité : après 19 boosters sans Épique ou mieux, le 20e en
  contient forcément une ;
- boosters gagnés : bienvenue, un toutes les 5 minutes (12 en réserve au
  maximum), un par épisode vu (récompensé en XP), un par niveau, un par
  série terminée ;
- un doublon se transforme en fragments, qui servent à fabriquer la carte
  manquante de son choix (sauf les Divines : uniquement par chance) ;
- tout est tiré côté serveur, avec un générateur aléatoire non prévisible.
"""

import random
import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import httpx
import structlog
from pydantic import TypeAdapter
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Booster,
    BoosterCard,
    Card,
    CardKind,
    CardWallet,
    Content,
    Episode,
    Rarity,
    Tracking,
    UserCard,
)
from app.providers.base import (
    CharacterRole,
    CharacterSummary,
    ContentKind,
    MetadataProvider,
    ProviderError,
)
from app.services import catalog, gamification

log = structlog.get_logger()

BOOSTER_SIZE = 5
PITY_BOOSTERS = 20
TIMER_SECONDS = 5 * 60  # un booster gratuit toutes les 5 minutes…
TIMER_MAX_STOCK = 12  # … dans la limite de 12 en attente (1 heure)
TRACKED_WEIGHT = 2  # vos contenus suivis sortent deux fois plus souvent

RARITY_ORDER = list(Rarity)  # de la plus courante à la plus rare
# Poids sur 1 000 (pour garder des nombres entiers : 5 = 0,5 %).
WEIGHTS = {
    Rarity.COMMON: 500,
    Rarity.UNCOMMON: 250,
    Rarity.RARE: 130,
    Rarity.EPIC: 70,
    Rarity.LEGENDARY: 35,
    Rarity.MYTHIC: 10,
    Rarity.DIVINE: 5,
}
EPIC_OR_BETTER = RARITY_ORDER[RARITY_ORDER.index(Rarity.EPIC) :]
RARE_OR_BETTER = RARITY_ORDER[RARITY_ORDER.index(Rarity.RARE) :]
# Fragments rendus par un doublon, et coût de fabrication d'une carte.
DUPLICATE_FRAGMENTS = {
    Rarity.COMMON: 1,
    Rarity.UNCOMMON: 2,
    Rarity.RARE: 5,
    Rarity.EPIC: 15,
    Rarity.LEGENDARY: 50,
    Rarity.MYTHIC: 120,
    Rarity.DIVINE: 300,
}
# Absente de la liste = impossible à fabriquer (les Divines).
CRAFT_COST = {
    Rarity.COMMON: 5,
    Rarity.UNCOMMON: 10,
    Rarity.RARE: 25,
    Rarity.EPIC: 75,
    Rarity.LEGENDARY: 250,
    Rarity.MYTHIC: 600,
}
ROLE_RARITY = {
    CharacterRole.HERO: Rarity.LEGENDARY,
    CharacterRole.MAIN: Rarity.EPIC,
    CharacterRole.SUPPORTING: Rarity.RARE,
    CharacterRole.BACKGROUND: Rarity.COMMON,
}
# Texte affiché sous le nom du personnage (jamais l'acteur ni le doubleur).
ROLE_LABELS = {
    CharacterRole.HERO: "Héros",
    CharacterRole.MAIN: "Rôle principal",
    CharacterRole.SUPPORTING: "Second rôle",
    CharacterRole.BACKGROUND: "Personnage",
}
MAX_STILLS = 8  # images d'épisodes « ordinaires » par contenu
CARDS_REFRESH = timedelta(days=1)
CHARACTERS_CACHE_SECONDS = 7 * 24 * 3600

_characters_adapter = TypeAdapter(list[CharacterSummary])


class PackTheme(StrEnum):
    ANIME = "anime"
    MOVIE = "movie"
    SERIES = "series"
    MIXED = "mixed"


THEME_LABELS = {
    PackTheme.ANIME: "Animes & mangas",
    PackTheme.MOVIE: "Films",
    PackTheme.SERIES: "Séries",
    PackTheme.MIXED: "Mélange",
}
THEME_KINDS = {
    PackTheme.ANIME: [ContentKind.ANIME],
    PackTheme.MOVIE: [ContentKind.MOVIE],
    PackTheme.SERIES: [ContentKind.SERIES],
    PackTheme.MIXED: list(ContentKind),
}


class NoBoosterError(Exception):
    """Aucun booster à ouvrir."""


class EmptyPoolError(Exception):
    """Aucune carte disponible pour ce thème (catalogue en préparation)."""


class CardNotAvailableError(Exception):
    pass


class AlreadyOwnedError(Exception):
    pass


class NotEnoughFragmentsError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


# --- Création des cartes d'un contenu -----------------------------------------


async def ensure_cards(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    content: Content,
) -> None:
    """Crée (ou met à jour) les cartes d'un contenu à partir de ses images."""
    rows: list[dict[str, object]] = []

    def add(
        key: str, kind: CardKind, rarity: Rarity, title: str, subtitle: str, image: str | None
    ) -> None:
        if image:  # pas d'image : pas de carte (jamais de carte vide)
            rows.append(
                {
                    "content_id": content.id,
                    "source_key": key,
                    "kind": kind,
                    "rarity": rarity,
                    "title": title[:200],
                    "subtitle": subtitle[:200],
                    "image_url": image,
                }
            )

    add("poster", CardKind.POSTER, Rarity.COMMON, content.title, "Affiche", content.poster_url)
    add(
        "backdrop", CardKind.BACKDROP, Rarity.UNCOMMON, content.title, "Décor", content.backdrop_url
    )

    provider = next((p for p in providers if p.source == content.source), None)
    characters: list[CharacterSummary] = []
    complete = True  # False : à refaire plus tard (source momentanément en panne)
    if provider is not None:
        kind = ContentKind(content.kind)
        try:
            characters = await catalog.cached(
                f"characters:{content.source}:{content.kind}:{content.external_id}",
                CHARACTERS_CACHE_SECONDS,
                _characters_adapter,
                lambda: provider.get_characters(http, kind, content.external_id),
            )
        except ProviderError:
            # On garde l'affiche et le décor ; les personnages viendront plus tard.
            log.warning("cards.personnages_indisponibles", content_id=content.id)
            complete = False
    for character in characters:
        key = f"char:{character.order}"
        add(
            key,
            CardKind.CHARACTER,
            ROLE_RARITY[character.role],
            character.name,
            ROLE_LABELS[character.role],
            character.image_url,
        )
        if character.role == CharacterRole.HERO:
            # Le héros existe aussi en éditions Mythique et Divine.
            for edition, label in ((Rarity.MYTHIC, "Mythique"), (Rarity.DIVINE, "Divine")):
                add(
                    f"{key}:{edition}",
                    CardKind.CHARACTER,
                    edition,
                    character.name,
                    f"Édition {label}",
                    character.image_url,
                )

    # Images d'épisodes déjà copiés en base (saisons ouvertes au moins une fois).
    episodes = list(
        await session.scalars(
            select(Episode)
            .where(
                Episode.content_id == content.id,
                Episode.season_number > 0,
                Episode.still_url.is_not(None),
            )
            .order_by(Episode.season_number, Episode.number)
        )
    )
    if episodes:
        premiere, finale = episodes[0], episodes[-1]
        add(
            f"still:{premiere.id}",
            CardKind.STILL,
            Rarity.RARE,
            premiere.title or content.title,
            f"S{premiere.season_number}·É{premiere.number} — premier épisode",
            premiere.still_url,
        )
        if content.is_finished and finale is not premiere:
            add(
                f"still:{finale.id}",
                CardKind.STILL,
                Rarity.RARE,
                finale.title or content.title,
                f"S{finale.season_number}·É{finale.number} — dernier épisode",
                finale.still_url,
            )
        ordinary = episodes[1:-1]
        step = max(1, len(ordinary) // MAX_STILLS)  # répartis sur toute la série
        for episode in ordinary[::step][:MAX_STILLS]:
            add(
                f"still:{episode.id}",
                CardKind.STILL,
                Rarity.UNCOMMON,
                episode.title or content.title,
                f"S{episode.season_number}·É{episode.number}",
                episode.still_url,
            )

    if rows:
        statement = insert(Card).values(rows)
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=["content_id", "source_key"],
                set_={
                    "rarity": statement.excluded.rarity,
                    "title": statement.excluded.title,
                    "subtitle": statement.excluded.subtitle,
                    "image_url": statement.excluded.image_url,
                },
            )
        )
    if complete:
        content.cards_generated_at = _now()
    await session.commit()


async def refresh_cards(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    user_id: int,
) -> None:
    """Ajoute au catalogue les contenus suivis par le joueur (cartes manquantes
    ou anciennes)."""
    contents = list(
        await session.scalars(
            select(Content)
            .join(Tracking, Tracking.content_id == Content.id)
            .where(
                Tracking.user_id == user_id,
                or_(
                    Content.cards_generated_at.is_(None),
                    Content.cards_generated_at < _now() - CARDS_REFRESH,
                ),
            )
        )
    )
    for content in contents:
        try:
            await ensure_cards(session, http, providers, content)
        except ProviderError:
            # Source en panne : ce contenu aura ses cartes la prochaine fois.
            log.warning("cards.creation_impossible", content_id=content.id)


# --- Boosters gagnés ---------------------------------------------------------------


async def _wallet(session: AsyncSession, user_id: int, lock: bool = False) -> CardWallet:
    await session.execute(insert(CardWallet).values(user_id=user_id).on_conflict_do_nothing())
    query = select(CardWallet).where(CardWallet.user_id == user_id)
    if lock:
        # FOR UPDATE : personne d'autre ne modifie ce portefeuille en même temps.
        query = query.with_for_update()
    wallet = await session.scalar(query, execution_options={"populate_existing": True})
    assert wallet is not None  # noqa: S101 (créé juste au-dessus)
    return wallet


def current_slot(now: datetime | None = None) -> int:
    """Numéro de la tranche de 5 minutes en cours (depuis le 1er janvier 1970)."""
    return int((now or _now()).timestamp()) // TIMER_SECONDS


async def _waiting_timer_boosters(session: AsyncSession, user_id: int) -> int:
    value = await session.scalar(
        select(func.count())
        .select_from(Booster)
        .where(
            Booster.user_id == user_id,
            Booster.opened_at.is_(None),
            Booster.key.like("timer:%"),
        )
    )
    return int(value or 0)


async def sync_boosters(session: AsyncSession, user_id: int, now: datetime | None = None) -> None:
    """Distribue les boosters dus : bienvenue, rattrapage des niveaux, minuteur."""
    await gamification.grant_booster(session, user_id, "welcome")
    level = gamification.level_for_xp(await gamification.total_xp(session, user_id))
    for lvl in range(2, level + 1):
        await gamification.grant_booster(session, user_id, f"level:{lvl}")

    wallet = await _wallet(session, user_id, lock=True)
    slot = current_slot(now)
    if wallet.timer_slot is None:
        wallet.timer_slot = slot  # le minuteur démarre maintenant
    elif slot > wallet.timer_slot:
        # Réserve pleine : le minuteur ne donne plus rien tant qu'on n'ouvre pas.
        room = TIMER_MAX_STOCK - await _waiting_timer_boosters(session, user_id)
        for granted in range(max(0, min(slot - wallet.timer_slot, room))):
            await gamification.grant_booster(session, user_id, f"timer:{slot - granted}")
        wallet.timer_slot = slot
    await session.commit()


async def count_boosters(session: AsyncSession, user_id: int) -> int:
    value = await session.scalar(
        select(func.count())
        .select_from(Booster)
        .where(Booster.user_id == user_id, Booster.opened_at.is_(None))
    )
    return int(value or 0)


async def timer_status(session: AsyncSession, user_id: int) -> int | None:
    """Secondes avant le prochain booster gratuit (None : réserve pleine)."""
    if await _waiting_timer_boosters(session, user_id) >= TIMER_MAX_STOCK:
        return None
    next_at = (current_slot() + 1) * TIMER_SECONDS
    return max(0, next_at - int(_now().timestamp()))


# --- Tirage --------------------------------------------------------------------


async def available_pool(
    session: AsyncSession, user_id: int, theme: PackTheme
) -> list[tuple[int, Rarity]]:
    """Cartes du thème. Les contenus suivis apparaissent deux fois dans la
    liste : ils ont deux fois plus de chances de sortir."""
    tracked = select(Tracking.content_id).where(Tracking.user_id == user_id)
    rows = await session.execute(
        select(Card.id, Card.rarity, Card.content_id.in_(tracked))
        .join(Content, Content.id == Card.content_id)
        .where(Content.kind.in_(THEME_KINDS[theme]))
    )
    pool: list[tuple[int, Rarity]] = []
    for card_id, rarity, is_tracked in rows.tuples():
        pool.extend([(card_id, Rarity(rarity))] * (TRACKED_WEIGHT if is_tracked else 1))
    return pool


def draw(
    pool: list[tuple[int, Rarity]], boosters_since_epic: int, rng: random.Random
) -> list[tuple[int, Rarity]]:
    """Tire les 5 cartes d'un booster (fonction pure : facile à tester)."""
    by_rarity: dict[Rarity, list[int]] = defaultdict(list)
    for card_id, rarity in pool:
        by_rarity[rarity].append(card_id)

    def pick(rarity: Rarity, taken: set[int]) -> tuple[int, Rarity]:
        # Rareté sans aucune carte : on descend d'un cran, puis on remonte.
        index = RARITY_ORDER.index(rarity)
        for candidate in RARITY_ORDER[index::-1] + RARITY_ORDER[index + 1 :]:
            cards = by_rarity[candidate]
            if cards:
                fresh = [c for c in cards if c not in taken]  # pas deux fois la même
                return rng.choice(fresh or cards), candidate
        raise EmptyPoolError

    def roll(allowed: list[Rarity]) -> Rarity:
        return rng.choices(allowed, weights=[WEIGHTS[r] for r in allowed])[0]

    result: list[tuple[int, Rarity]] = []
    taken: set[int] = set()
    for slot in range(BOOSTER_SIZE):
        allowed = RARITY_ORDER
        if slot == BOOSTER_SIZE - 1:
            rarities = {r for _, r in result}
            if boosters_since_epic + 1 >= PITY_BOOSTERS and not rarities & set(EPIC_OR_BETTER):
                allowed = EPIC_OR_BETTER  # filet de sécurité
            elif not rarities & set(RARE_OR_BETTER):
                allowed = RARE_OR_BETTER  # Rare garantie
        card = pick(roll(allowed), taken)
        taken.add(card[0])
        result.append(card)
    return result


@dataclass
class DrawnCard:
    card: Card
    content: Content
    is_new: bool
    fragments: int


@dataclass
class OpenResult:
    theme: PackTheme
    cards: list[DrawnCard]
    fragments: int
    boosters_left: int


async def open_booster(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    user_id: int,
    theme: PackTheme,
    rng: random.Random | None = None,
) -> OpenResult:
    first = await session.scalar(
        select(Booster.id)
        .where(Booster.user_id == user_id, Booster.opened_at.is_(None))
        .order_by(Booster.created_at, Booster.id)
        .limit(1)
    )
    if first is None:
        raise NoBoosterError
    # Les appels aux sources se font AVANT de verrouiller quoi que ce soit.
    await refresh_cards(session, http, providers, user_id)
    pool = await available_pool(session, user_id, theme)
    if not pool:
        raise EmptyPoolError  # le booster n'est pas consommé

    # FOR UPDATE : si deux requêtes ouvrent le même booster en même temps
    # (double clic), la seconde attend, puis voit qu'il est déjà ouvert.
    booster = await session.scalar(
        select(Booster).where(Booster.id == first, Booster.opened_at.is_(None)).with_for_update(),
        execution_options={"populate_existing": True},
    )
    if booster is None:
        raise NoBoosterError
    wallet = await _wallet(session, user_id, lock=True)
    drawn = draw(pool, wallet.boosters_since_epic, rng or secrets.SystemRandom())

    ids = [card_id for card_id, _ in drawn]
    owned = set(
        await session.scalars(
            select(UserCard.card_id).where(UserCard.user_id == user_id, UserCard.card_id.in_(ids))
        )
    )
    results: list[tuple[int, bool, int]] = []
    for position, (card_id, rarity) in enumerate(drawn):
        duplicate = card_id in owned
        fragments = DUPLICATE_FRAGMENTS[rarity] if duplicate else 0
        if not duplicate:
            session.add(UserCard(user_id=user_id, card_id=card_id))
            owned.add(card_id)
        wallet.fragments += fragments
        session.add(
            BoosterCard(
                booster_id=booster.id,
                position=position,
                card_id=card_id,
                duplicate=duplicate,
                fragments=fragments,
            )
        )
        results.append((card_id, not duplicate, fragments))

    got_epic = any(r in EPIC_OR_BETTER for _, r in drawn)
    wallet.boosters_since_epic = 0 if got_epic else wallet.boosters_since_epic + 1
    booster.opened_at = _now()
    await session.commit()

    rows = await session.execute(
        select(Card, Content).join(Content, Content.id == Card.content_id).where(Card.id.in_(ids))
    )
    cards = {card.id: (card, content) for card, content in rows.tuples()}
    return OpenResult(
        theme=theme,
        cards=[
            DrawnCard(card=cards[cid][0], content=cards[cid][1], is_new=new, fragments=frag)
            for cid, new, frag in results
        ],
        fragments=wallet.fragments,
        boosters_left=await count_boosters(session, user_id),
    )


# --- Collection et fabrication --------------------------------------------------


@dataclass
class CollectionEntry:
    card: Card
    content: Content
    owned: bool


async def collection(session: AsyncSession, user_id: int) -> list[CollectionEntry]:
    """Cartes des contenus dont on possède au moins une carte, ou qu'on suit.

    Le catalogue complet compte des milliers de cartes : on ne montre que
    les séries de cartes commencées (avec celles qui manquent) et vos contenus.
    """
    owned = set(await session.scalars(select(UserCard.card_id).where(UserCard.user_id == user_id)))
    tracked = select(Tracking.content_id).where(Tracking.user_id == user_id)
    started = (
        select(Card.content_id)
        .join(UserCard, UserCard.card_id == Card.id)
        .where(UserCard.user_id == user_id)
    )
    rows = await session.execute(
        select(Card, Content)
        .join(Content, Content.id == Card.content_id)
        .where(or_(Card.content_id.in_(tracked), Card.content_id.in_(started)))
        .order_by(Content.title, Card.content_id, Card.id)
    )
    return [
        CollectionEntry(card=card, content=content, owned=card.id in owned)
        for card, content in rows.tuples()
    ]


async def catalog_stats(
    session: AsyncSession, user_id: int
) -> tuple[dict[Rarity, int], dict[Rarity, int], dict[PackTheme, int]]:
    """Cartes possédées et existantes par rareté, et nombre de cartes par thème."""
    totals = {
        Rarity(rarity): count
        for rarity, count in (
            await session.execute(select(Card.rarity, func.count()).group_by(Card.rarity))
        ).tuples()
    }
    owned = {
        Rarity(rarity): count
        for rarity, count in (
            await session.execute(
                select(Card.rarity, func.count())
                .join(UserCard, UserCard.card_id == Card.id)
                .where(UserCard.user_id == user_id)
                .group_by(Card.rarity)
            )
        ).tuples()
    }
    by_kind = {
        kind: count
        for kind, count in (
            await session.execute(
                select(Content.kind, func.count())
                .select_from(Card)
                .join(Content, Content.id == Card.content_id)
                .group_by(Content.kind)
            )
        ).tuples()
    }
    themes = {
        theme: sum(by_kind.get(kind, 0) for kind in kinds) for theme, kinds in THEME_KINDS.items()
    }
    return owned, totals, themes


async def wallet_state(session: AsyncSession, user_id: int) -> CardWallet:
    wallet = await _wallet(session, user_id)
    await session.commit()
    return wallet


async def craft(session: AsyncSession, user_id: int, card_id: int) -> tuple[Card, Content, int]:
    """Fabrique une carte manquante avec des fragments. Renvoie le solde restant."""
    row = (
        await session.execute(
            select(Card, Content)
            .join(Content, Content.id == Card.content_id)
            .where(Card.id == card_id)
        )
    ).first()
    if row is None:
        raise CardNotAvailableError
    card, content = row
    cost = CRAFT_COST.get(Rarity(card.rarity))
    if cost is None:
        raise CardNotAvailableError  # Divine : uniquement par chance
    if await session.scalar(
        select(UserCard.card_id).where(UserCard.user_id == user_id, UserCard.card_id == card_id)
    ):
        raise AlreadyOwnedError
    wallet = await _wallet(session, user_id, lock=True)
    if wallet.fragments < cost:
        # Pas d'écriture : la session est annulée à la fin de la requête.
        raise NotEnoughFragmentsError
    wallet.fragments -= cost
    session.add(UserCard(user_id=user_id, card_id=card_id))
    await session.commit()
    return card, content, wallet.fragments
