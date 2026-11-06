"""Formats d'échange des cartes."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import Card, CardKind, Content, Rarity
from app.providers.base import ContentKind, Source
from app.schemas.gamification import RewardsRead
from app.services.cards import PackTheme


class CardContent(BaseModel):
    id: int
    source: Source
    kind: ContentKind
    external_id: str
    title: str


class CardRead(BaseModel):
    id: int
    rarity: Rarity
    kind: CardKind
    title: str
    subtitle: str | None
    image_url: str
    content: CardContent

    @classmethod
    def of(cls, card: Card, content: Content) -> "CardRead":
        return cls(
            id=card.id,
            rarity=Rarity(card.rarity),
            kind=CardKind(card.kind),
            title=card.title,
            subtitle=card.subtitle,
            image_url=card.image_url,
            content=CardContent(
                id=content.id,
                source=Source(content.source),
                kind=ContentKind(content.kind),
                external_id=content.external_id,
                title=content.title,
            ),
        )


class CollectionCard(CardRead):
    owned: bool
    # Coût en fragments (None : impossible à fabriquer, ex. Divine).
    craft_cost: int | None


class RarityStat(BaseModel):
    rarity: Rarity
    owned: int
    total: int
    chance_percent: float  # probabilité par carte tirée


class ThemeRead(BaseModel):
    theme: PackTheme
    label: str
    cards: int  # cartes existantes dans ce thème


class CollectionRead(BaseModel):
    boosters: int  # boosters à ouvrir
    fragments: int
    boosters_until_pity: int  # boosters restants avant une Épique garantie
    # Secondes avant le prochain booster gratuit (None : réserve pleine).
    next_free_booster_in: int | None
    free_booster_minutes: int
    free_booster_max_stock: int
    themes: list[ThemeRead]
    stats: list[RarityStat]


class OpenRequest(BaseModel):
    theme: PackTheme = PackTheme.MIXED
    count: int = Field(default=1, ge=1, le=10, description="Boosters à ouvrir d'un coup")


class DrawnCardRead(BaseModel):
    card: CardRead
    is_new: bool
    fragments: int  # fragments obtenus si c'est un doublon


class MasteryRead(BaseModel):
    """Une collection complète : la carte « Maître » et le titre débloqué."""

    content_id: int
    work_title: str
    poster_url: str | None
    title: str  # titre de profil (ex. « Roi des pirates »)
    completed_at: datetime | None = None
    # Récompenses (seulement au moment où la collection vient d'être complétée).
    rewards: RewardsRead | None = None


class BoosterOpened(BaseModel):
    theme: PackTheme
    boosters_opened: int = 1
    cards: list[DrawnCardRead]
    fragments: int
    boosters_left: int
    masteries: list[MasteryRead] = []


class CraftResult(BaseModel):
    card: CardRead
    fragments: int
    masteries: list[MasteryRead] = []


class RarityCount(BaseModel):
    rarity: Rarity
    count: int


class PackContents(BaseModel):
    """Liste des cartes qu'on peut obtenir dans un pack (paginée)."""

    theme: PackTheme
    label: str
    total: int
    matching: int
    rarities: list[RarityCount]
    cards: list[CollectionCard]


class BinderContent(CardContent):
    poster_url: str | None
    year: int | None


class BinderEntryRead(BaseModel):
    """Une pochette du classeur : une œuvre et sa progression."""

    content: BinderContent
    owned: int
    total: int
    mastered: bool = False


class BinderPageRead(BaseModel):
    """Toutes les cartes d'une œuvre."""

    content: BinderContent
    fragments: int
    cards: list[CollectionCard]
    mastery: MasteryRead | None = None
