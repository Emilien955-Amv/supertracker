"""Contenus (films, séries, animes) et leurs épisodes, copiés depuis les sources.

Pourquoi les recopier en base alors que TMDB et AniList les fournissent ?
- Le suivi, les bibliothèques et (plus tard) les cartes doivent pointer vers
  une ligne stable de NOTRE base (clé étrangère), pas vers une API externe.
- On peut afficher « Mon suivi » sans appeler 50 fois TMDB.
On ne garde que l'essentiel ; la fiche complète reste servie par le cache Redis.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
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


class Content(Base):
    __tablename__ = "contents"
    # Un même numéro peut exister chez deux sources (TMDB 21 ≠ AniList 21),
    # et chez TMDB un film et une série peuvent partager le même numéro.
    __table_args__ = (UniqueConstraint("source", "kind", "external_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(20))

    title: Mapped[str] = mapped_column(String(300))
    original_title: Mapped[str | None] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(SmallInteger)
    poster_url: Mapped[str | None] = mapped_column(String(500))
    backdrop_url: Mapped[str | None] = mapped_column(String(500))
    release_date: Mapped[date | None] = mapped_column(Date)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(50))
    # Nombre d'épisodes hors épisodes spéciaux : sert au calcul de la progression.
    episodes_count: Mapped[int | None] = mapped_column(Integer)
    is_finished: Mapped[bool] = mapped_column(Boolean, server_default=false())

    # Date de la dernière copie depuis la source : au-delà d'un jour, on rafraîchit.
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Date de création des cartes de ce contenu (None : pas encore créées).
    cards_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (UniqueConstraint("content_id", "season_number", "number"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    content_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contents.id", ondelete="CASCADE")
    )
    # Saison 0 = épisodes spéciaux (convention TMDB), exclus de la progression.
    season_number: Mapped[int] = mapped_column(SmallInteger)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(300))
    air_date: Mapped[date | None] = mapped_column(Date)
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)
    still_url: Mapped[str | None] = mapped_column(String(500))

    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
