"""Cartes à collectionner : des PERSONNAGES, en boosters par thème.

Raretés (probabilité par carte tirée) selon l'importance du personnage,
avec un personnage DIFFÉRENT à chaque rareté haute :
    Divine        0,5 %  le héros (n° 1) — une seule par œuvre, non fabricable
    Mythique      1 %    le n° 2 de l'histoire
    Légendaire    3,5 %  les n° 3 et 4
    Épique        7 %    les autres rôles principaux
    Rare         13 %    seconds rôles
    Peu commune  25 %    personnages récurrents
    Commune      50 %    petits rôles

Règles :
- cartes de personnages uniquement (nom du personnage, jamais l'acteur) ;
- catalogue commun : contenus populaires et mieux notés, titres phares de
  chaque plateforme (renouvelés chaque jour), et contenus suivis par les
  joueurs. Pas besoin d'avoir vu un contenu pour obtenir ses cartes ;
- les contenus de VOTRE suivi ont deux fois plus de chances de sortir ;
- packs au choix : animes, films, séries, mélange, ou par plateforme
  (Netflix, Disney+, Prime Video…) ;
- 5 cartes par booster, dont au moins une Rare (ou mieux) ;
- filet de sécurité : après 19 boosters sans Épique ou mieux, le 20e en
  contient forcément une ;
- boosters gagnés : bienvenue, un toutes les 5 minutes (12 en réserve au
  maximum), un par niveau, un par film, série ou anime terminé ;
- un doublon se transforme en fragments, qui servent à fabriquer la carte
  manquante de son choix (sauf les Divines : uniquement par chance) ;
- tout est tiré côté serveur, avec un générateur aléatoire non prévisible.
"""

import hashlib
import random
import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import httpx
import structlog
from pydantic import TypeAdapter
from sqlalchemy import Select, and_, case, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Booster,
    BoosterCard,
    Card,
    CardKind,
    CardWallet,
    Content,
    ContentPlatform,
    Rarity,
    Tracking,
    TrackingStatus,
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
# Les 4 personnages les plus importants ont chacun leur rareté haute
# (n° 1 Divine, n° 2 Mythique, n° 3 et 4 Légendaires) ; ensuite, la rareté
# dépend du rôle.
TOP_RARITIES = [Rarity.DIVINE, Rarity.MYTHIC, Rarity.LEGENDARY, Rarity.LEGENDARY]
ROLE_RARITY = {
    CharacterRole.HERO: Rarity.DIVINE,
    CharacterRole.MAIN: Rarity.EPIC,
    CharacterRole.SUPPORTING: Rarity.RARE,
    CharacterRole.RECURRING: Rarity.UNCOMMON,
    CharacterRole.BACKGROUND: Rarity.COMMON,
}
# Texte affiché sous le nom du personnage (jamais l'acteur ni le doubleur).
ROLE_LABELS = {
    CharacterRole.HERO: "Héros",
    CharacterRole.MAIN: "Rôle principal",
    CharacterRole.SUPPORTING: "Second rôle",
    CharacterRole.RECURRING: "Personnage récurrent",
    CharacterRole.BACKGROUND: "Personnage",
}
CARDS_REFRESH = timedelta(days=1)
CHARACTERS_CACHE_SECONDS = 7 * 24 * 3600

_characters_adapter = TypeAdapter(list[CharacterSummary])


class PackTheme(StrEnum):
    ANIME = "anime"
    MOVIE = "movie"
    SERIES = "series"
    MIXED = "mixed"
    # Packs par plateforme (films et séries inclus dans l'abonnement, en France)
    NETFLIX = "netflix"
    DISNEY = "disney"
    PRIME = "prime"
    APPLE = "apple"
    MAX = "max"
    CANAL = "canal"
    PARAMOUNT = "paramount"
    CRUNCHYROLL = "crunchyroll"
    ADN = "adn"


THEME_LABELS = {
    PackTheme.ANIME: "Animes & mangas",
    PackTheme.MOVIE: "Films",
    PackTheme.SERIES: "Séries",
    PackTheme.MIXED: "Mélange",
    PackTheme.NETFLIX: "Netflix",
    PackTheme.DISNEY: "Disney+",
    PackTheme.PRIME: "Prime Video",
    PackTheme.APPLE: "Apple TV+",
    PackTheme.MAX: "HBO Max",
    PackTheme.CANAL: "Canal+",
    PackTheme.PARAMOUNT: "Paramount+",
    PackTheme.CRUNCHYROLL: "Crunchyroll",
    PackTheme.ADN: "ADN",
}
# Identifiant de chaque plateforme chez TMDB (données JustWatch).
PLATFORM_IDS = {
    PackTheme.NETFLIX: 8,
    PackTheme.DISNEY: 337,
    PackTheme.PRIME: 119,
    PackTheme.APPLE: 350,
    PackTheme.MAX: 1899,
    PackTheme.CANAL: 381,
    PackTheme.PARAMOUNT: 531,
}
# Plateformes d'animes : leur catalogue français vient de TMDB, et chaque titre
# est retrouvé chez AniList (dessins des personnages, pas de doubleurs).
ANIME_PLATFORM_IDS = {
    PackTheme.CRUNCHYROLL: 283,
    PackTheme.ADN: 415,
}
# Sites de streaming signalés par AniList → pack correspondant.
ANILIST_SITES = {
    "Crunchyroll": PackTheme.CRUNCHYROLL,
    "Netflix": PackTheme.NETFLIX,
    "Amazon Prime Video": PackTheme.PRIME,
    "Disney Plus": PackTheme.DISNEY,
    "Max": PackTheme.MAX,
}
PLATFORM_THEMES = [*PLATFORM_IDS, *ANIME_PLATFORM_IDS]
THEME_KINDS = {
    PackTheme.ANIME: [ContentKind.ANIME],
    PackTheme.MOVIE: [ContentKind.MOVIE, ContentKind.SAGA],
    PackTheme.SERIES: [ContentKind.SERIES],
    PackTheme.MIXED: list(ContentKind),
    **{platform: list(ContentKind) for platform in PLATFORM_IDS},
    **{platform: [ContentKind.ANIME] for platform in ANIME_PLATFORM_IDS},
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


def rarity_for(rank: int, role: CharacterRole) -> Rarity:
    """Rareté d'un personnage selon son rang d'importance (0 = le héros)."""
    if rank < len(TOP_RARITIES):
        return TOP_RARITIES[rank]
    return ROLE_RARITY[role]


async def ensure_cards(
    session: AsyncSession,
    http: httpx.AsyncClient,
    providers: list[MetadataProvider],
    content: Content,
) -> None:
    """Crée (ou met à jour) les cartes des personnages d'un contenu."""
    provider = next((p for p in providers if p.source == content.source), None)
    if provider is None:
        return
    kind = ContentKind(content.kind)
    try:
        characters = await catalog.cached(
            f"characters:{content.source}:{content.kind}:{content.external_id}",
            CHARACTERS_CACHE_SECONDS,
            _characters_adapter,
            lambda: provider.get_characters(http, kind, content.external_id),
        )
    except ProviderError:
        # Source momentanément en panne : on réessaiera plus tard.
        log.warning("cards.personnages_indisponibles", content_id=content.id)
        return

    rows: list[dict[str, object]] = []
    keys: set[str] = set()

    def add(key: str, rarity: Rarity, character: CharacterSummary, subtitle: str) -> None:
        # Deux personnages du même nom (ex. « Soldat ») : on garde le premier,
        # le plus important. Sinon la base refuserait deux cartes identiques.
        if key in keys:
            return
        keys.add(key)
        rows.append(
            {
                "content_id": content.id,
                "source_key": key,
                "kind": CardKind.CHARACTER,
                "rarity": rarity,
                "title": character.name[:200],
                "subtitle": subtitle,
                "image_url": character.image_url,
            }
        )

    for character in characters:
        # Clé stable : l'empreinte du nom. Si le casting change d'ordre, une
        # carte déjà obtenue reste le même personnage.
        digest = hashlib.sha1(character.name.lower().encode(), usedforsecurity=False)
        key = f"char:{digest.hexdigest()[:16]}"
        add(key, rarity_for(len(rows), character.role), character, ROLE_LABELS[character.role])

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
    # Cartes qui ne correspondent plus à aucun personnage (doublons, anime
    # désormais fourni par AniList…) : supprimées.
    await session.execute(
        delete(Card).where(Card.content_id == content.id, Card.source_key.not_in(keys))
    )
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
    # Un booster par œuvre déjà terminée (rattrapage, une seule fois : la clé
    # « completion:<id> » est unique).
    await session.execute(
        insert(Booster)
        .from_select(
            ["user_id", "key"],
            select(Tracking.user_id, func.concat("completion:", Tracking.content_id)).where(
                Tracking.user_id == user_id, Tracking.status == TrackingStatus.COMPLETED
            ),
        )
        .on_conflict_do_nothing(index_elements=["user_id", "key"])
    )
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


def _in_theme[Q: Select[Any]](query: Q, theme: PackTheme) -> Q:
    """Restreint une requête (qui joint déjà Content) aux cartes d'un pack :
    œuvres du catalogue de cartes, du bon type ou de la bonne plateforme."""
    query = query.where(Content.in_card_catalog.is_(True), Content.kind.in_(THEME_KINDS[theme]))
    if theme in PLATFORM_THEMES:
        query = query.where(
            Card.content_id.in_(
                select(ContentPlatform.content_id).where(ContentPlatform.platform == theme)
            )
        )
    return query


async def available_pool(
    session: AsyncSession, user_id: int, theme: PackTheme
) -> list[tuple[int, Rarity]]:
    """Cartes du thème. Les contenus suivis apparaissent deux fois dans la
    liste : ils ont deux fois plus de chances de sortir."""
    tracked = select(Tracking.content_id).where(Tracking.user_id == user_id)
    query = _in_theme(
        select(Card.id, Card.rarity, Card.content_id.in_(tracked)).join(
            Content, Content.id == Card.content_id
        ),
        theme,
    )
    rows = await session.execute(query)
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


@dataclass
class BinderEntry:
    content: Content
    owned: int
    total: int


async def binder(session: AsyncSession, user_id: int) -> list[BinderEntry]:
    """Classeur : une « pochette » par œuvre dont on possède au moins une carte
    (ou qu'on suit), avec le nombre de cartes obtenues sur le total."""
    started = (
        select(Card.content_id)
        .join(UserCard, UserCard.card_id == Card.id)
        .where(UserCard.user_id == user_id)
    )
    tracked = select(Tracking.content_id).where(Tracking.user_id == user_id)
    owned_card = and_(UserCard.card_id == Card.id, UserCard.user_id == user_id)
    rows = await session.execute(
        select(Content, func.count(UserCard.card_id), func.count(Card.id))
        .join(Card, Card.content_id == Content.id)
        .outerjoin(UserCard, owned_card)
        .where(or_(Content.id.in_(started), Content.id.in_(tracked)))
        .group_by(Content.id)
        .order_by(func.lower(Content.title), Content.id)
    )
    return [
        BinderEntry(content=content, owned=owned, total=total)
        for content, owned, total in rows.tuples()
    ]


async def binder_page(
    session: AsyncSession, user_id: int, content_id: int
) -> tuple[Content, list[CollectionEntry]] | None:
    """Toutes les cartes d'une œuvre, de la plus rare à la plus commune."""
    content = await session.get(Content, content_id)
    if content is None:
        return None
    order = case({r.value: i for i, r in enumerate(RARITY_ORDER)}, value=Card.rarity)
    cards = list(
        await session.scalars(
            select(Card).where(Card.content_id == content_id).order_by(order.desc(), Card.title)
        )
    )
    owned = set(
        await session.scalars(
            select(UserCard.card_id).where(
                UserCard.user_id == user_id, UserCard.card_id.in_([c.id for c in cards])
            )
        )
    )
    return content, [CollectionEntry(card=c, content=content, owned=c.id in owned) for c in cards]


async def catalog_stats(
    session: AsyncSession, user_id: int
) -> tuple[dict[Rarity, int], dict[Rarity, int], dict[PackTheme, int]]:
    """Cartes possédées et existantes par rareté, et nombre de cartes par thème."""
    in_catalog = Content.in_card_catalog.is_(True)
    totals = {
        Rarity(rarity): count
        for rarity, count in (
            await session.execute(
                select(Card.rarity, func.count())
                .join(Content, Content.id == Card.content_id)
                .where(in_catalog)
                .group_by(Card.rarity)
            )
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
                .where(in_catalog)
                .group_by(Content.kind)
            )
        ).tuples()
    }
    by_platform = {
        platform: count
        for platform, count in (
            await session.execute(
                select(ContentPlatform.platform, func.count())
                .select_from(Card)
                .join(ContentPlatform, ContentPlatform.content_id == Card.content_id)
                .join(Content, Content.id == Card.content_id)
                .where(in_catalog)
                .group_by(ContentPlatform.platform)
            )
        ).tuples()
    }
    themes = {
        theme: by_platform.get(theme, 0)
        if theme in PLATFORM_THEMES
        else sum(by_kind.get(kind, 0) for kind in THEME_KINDS[theme])
        for theme in PackTheme
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


@dataclass
class PackPage:
    total: int  # cartes du pack
    matching: int  # cartes correspondant aux filtres
    by_rarity: dict[Rarity, int]
    entries: list[CollectionEntry]


async def pack_cards(
    session: AsyncSession,
    user_id: int,
    theme: PackTheme,
    rarity: Rarity | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 60,
) -> PackPage:
    """Cartes qu'on peut obtenir dans un pack, de la plus rare à la plus commune."""
    by_rarity = {
        Rarity(r): n
        for r, n in (
            await session.execute(
                _in_theme(
                    select(Card.rarity, func.count())
                    .select_from(Card)
                    .join(Content, Content.id == Card.content_id),
                    theme,
                ).group_by(Card.rarity)
            )
        ).tuples()
    }
    query = _in_theme(select(Card, Content).join(Content, Content.id == Card.content_id), theme)
    if rarity is not None:
        query = query.where(Card.rarity == rarity)
    if search:
        # Les caractères spéciaux de LIKE (% et _) sont neutralisés.
        pattern = "%" + search.replace("\\", "").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(
            or_(Card.title.ilike(pattern, escape="\\"), Content.title.ilike(pattern, escape="\\"))
        )
    matching = await session.scalar(select(func.count()).select_from(query.subquery()))
    order = case({r.value: i for i, r in enumerate(RARITY_ORDER)}, value=Card.rarity)
    rows = list(
        (
            await session.execute(
                query.order_by(order.desc(), Content.title, Card.title, Card.id)
                .offset(offset)
                .limit(limit)
            )
        ).tuples()
    )
    owned = set(
        await session.scalars(
            select(UserCard.card_id).where(
                UserCard.user_id == user_id, UserCard.card_id.in_([c.id for c, _ in rows])
            )
        )
    )
    return PackPage(
        total=sum(by_rarity.values()),
        matching=int(matching or 0),
        by_rarity=by_rarity,
        entries=[CollectionEntry(card=c, content=ct, owned=c.id in owned) for c, ct in rows],
    )
