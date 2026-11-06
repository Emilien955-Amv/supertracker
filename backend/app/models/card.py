"""Cartes à collectionner, boosters et portefeuille de fragments."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Rarity(StrEnum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    MYTHIC = "mythic"
    DIVINE = "divine"


class CardKind(StrEnum):
    # Uniquement des personnages (pas d'affiches ni de décors). Le champ est
    # gardé pour pouvoir ajouter d'autres sortes de cartes plus tard.
    CHARACTER = "character"


class Card(Base):
    """Une carte du catalogue. Elle est créée à partir des images d'un contenu ;
    les joueurs en possèdent ensuite des exemplaires (UserCard)."""

    __tablename__ = "cards"
    # « source_key » identifie l'origine de la carte (ex. « char:0 », « poster ») :
    # régénérer les cartes d'un contenu met à jour les mêmes lignes.
    __table_args__ = (UniqueConstraint("content_id", "source_key"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    source_key: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(20))
    rarity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    subtitle: Mapped[str | None] = mapped_column(String(200))
    image_url: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserCard(Base):
    """Carte possédée par un joueur (les doublons deviennent des fragments)."""

    __tablename__ = "user_cards"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    card_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    obtained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Booster(Base):
    """Un paquet de 5 cartes gagné (montée de niveau, série terminée…)."""

    __tablename__ = "boosters"
    # La clé (ex. « level:3 ») est unique par joueur : un même exploit ne
    # rapporte jamais deux boosters.
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(80))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BoosterCard(Base):
    """Carte tirée dans un booster (historique des ouvertures)."""

    __tablename__ = "booster_cards"

    booster_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boosters.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    card_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cards.id", ondelete="CASCADE"))
    duplicate: Mapped[bool] = mapped_column(Boolean, server_default=false())
    fragments: Mapped[int] = mapped_column(Integer, server_default="0")


class CardWallet(Base):
    """Fragments et compteur de « malchance » d'un joueur."""

    __tablename__ = "card_wallets"
    __table_args__ = (CheckConstraint("fragments >= 0", name="fragments_positive"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    fragments: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Boosters ouverts d'affilée sans carte Épique ou Légendaire (filet de sécurité).
    boosters_since_epic: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Dernier « créneau » de 5 minutes pour lequel un booster gratuit a été donné
    # (nombre de tranches de 5 min depuis 1970). None : jamais.
    timer_slot: Mapped[int | None] = mapped_column(BigInteger)


class ContentPlatform(Base):
    """Plateforme où un contenu est inclus dans l'abonnement (boosters Netflix…)."""

    __tablename__ = "content_platforms"

    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True
    )
    platform: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
