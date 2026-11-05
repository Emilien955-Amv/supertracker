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
    GRID = "grid"  # grille d'affiches
    SHELF = "shelf"  # étagère (défilement horizontal)
    LIST = "list"  # liste compacte


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
        CheckConstraint("view_mode IN ('grid', 'shelf', 'list')", name="view_mode_valid"),
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LibraryItem(Base):
    __tablename__ = "library_items"

    library_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("libraries.id", ondelete="CASCADE"), primary_key=True
    )
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # Rang dans le tri manuel (0 = premier).
    position: Mapped[int] = mapped_column(Integer)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
