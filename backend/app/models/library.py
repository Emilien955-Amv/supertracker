"""Bibliothèques personnelles (« Mes coups de cœur », « Animes d'enfance »…)."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ViewMode(StrEnum):
    BOOKCASE = "bookcase"  # meuble avec étagères en bois, rangement libre
    GRID = "grid"  # grille d'affiches
    SHELF = "shelf"  # étagère (défilement horizontal)
    LIST = "list"  # liste compacte


class Wood(StrEnum):
    """Essence du bois du meuble."""

    OAK = "oak"  # chêne clair
    WALNUT = "walnut"  # noyer
    EBONY = "ebony"  # ébène
    WHITE = "white"  # blanc laqué


class ItemSize(StrEnum):
    """Taille des objets posés sur les étagères."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class SortMode(StrEnum):
    MANUAL = "manual"  # ordre choisi par l'utilisateur
    ALPHA = "alpha"  # ordre alphabétique
    CATEGORY = "category"  # films, puis séries, puis animes
    RECENT = "recent"  # derniers ajouts en premier


class Library(Base):
    __tablename__ = "libraries"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        CheckConstraint("color ~ '^#[0-9a-f]{6}$'", name="color_hex"),
        CheckConstraint(
            "view_mode IN ('bookcase', 'grid', 'shelf', 'list')", name="view_mode_valid"
        ),
        CheckConstraint("wood IN ('oak', 'walnut', 'ebony', 'white')", name="wood_valid"),
        CheckConstraint("item_size IN ('small', 'medium', 'large')", name="item_size_valid"),
        CheckConstraint("wall ~ '^#[0-9a-f]{6}$'", name="wall_hex"),
        CheckConstraint(
            "sort_mode IN ('manual', 'alpha', 'category', 'recent')", name="sort_mode_valid"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(50))
    color: Mapped[str] = mapped_column(String(7))  # ex. « #7c5cff »
    view_mode: Mapped[str] = mapped_column(String(10), server_default=ViewMode.GRID.value)
    sort_mode: Mapped[str] = mapped_column(String(10), server_default=SortMode.MANUAL.value)
    # Personnalisation du meuble (vue « bibliothèque »).
    wood: Mapped[str] = mapped_column(String(10), server_default=Wood.OAK.value)
    wall: Mapped[str] = mapped_column(String(7), server_default="#2b2236")  # couleur du mur
    item_size: Mapped[str] = mapped_column(String(10), server_default=ItemSize.MEDIUM.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LibraryShelf(Base):
    """Une étagère du meuble. L'utilisateur en ajoute, renomme, réordonne."""

    __tablename__ = "library_shelves"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    library_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("libraries.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str | None] = mapped_column(String(50))  # petite plaque (facultative)
    position: Mapped[int] = mapped_column(Integer)  # 0 = étagère du haut
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LibraryItem(Base):
    __tablename__ = "library_items"

    library_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("libraries.id", ondelete="CASCADE"), primary_key=True
    )
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # Étagère où l'objet est rangé (None : pas encore rangé).
    shelf_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("library_shelves.id", ondelete="SET NULL"), index=True
    )
    # Rang sur l'étagère, ou dans le tri manuel (0 = premier).
    position: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
