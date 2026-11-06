"""Outils partagés par tous les tests (« fixtures » pytest)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.cache import redis_client
from app.core.rate_limit import KEY_PREFIX
from app.db import engine, get_session
from app.http_client import get_http_client
from app.main import app
from app.models import Card, Content, User
from app.providers.base import (
    CharacterRole,
    CharacterSummary,
    ContentDetail,
    ContentKind,
    EpisodeSummary,
    ProviderError,
    SearchResult,
    SeasonSummary,
    Source,
)
from app.providers.registry import get_providers


async def vider_cache_catalogue() -> None:
    """Supprime les fiches mises en cache. Appelé avant ET après les tests qui
    utilisent de fausses sources : sinon leurs fausses fiches resteraient dans
    le Redis local et l'application les servirait ensuite comme de vraies."""
    keys = [k async for k in redis_client.scan_iter("cache:*")]
    if keys:
        await redis_client.delete(*keys)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Client HTTP qui appelle l'API directement en mémoire, sans réseau."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    # Chaque test a sa propre boucle asyncio : on ferme les connexions Redis
    # ouvertes pendant ce test pour qu'elles ne soient pas réutilisées ailleurs.
    await redis_client.connection_pool.disconnect()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Session de base de données dont TOUT est annulé à la fin du test.

    On ouvre une transaction, puis chaque « commit » de l'application devient
    un simple point de sauvegarde (savepoint) à l'intérieur de celle-ci. À la
    fin, on annule la transaction : la base retrouve son état initial, et les
    tests ne se gênent jamais entre eux.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def db_client(client: AsyncClient, db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """Client HTTP branché sur la session de test (nécessite PostgreSQL et Redis)."""

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    # Remet à zéro les compteurs de tentatives, pour des tests indépendants.
    keys = [key async for key in redis_client.scan_iter(f"{KEY_PREFIX}*")]
    if keys:
        await redis_client.delete(*keys)

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


# --- Suivi et bibliothèques ---------------------------------------------------


class FausseSource:
    """Source TMDB simulée : un film (Matrix) et une série terminée de 3 épisodes
    (2 en saison 1, 1 en saison 2), plus un épisode spécial en saison 0."""

    source = Source.TMDB

    def __init__(self) -> None:
        self.en_panne = False
        self.appels = 0

    async def search(self, http: httpx.AsyncClient, query: str) -> list[SearchResult]:
        return []

    async def get_detail(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> ContentDetail | None:
        self.appels += 1
        if self.en_panne:
            raise ProviderError("source en panne")
        if (kind, external_id) == (ContentKind.MOVIE, "603"):
            return ContentDetail(
                source=Source.TMDB,
                kind=kind,
                external_id="603",
                title="Matrix",
                year=1999,
                source_url="https://exemple.fr/603",
                is_finished=True,
            )
        if (kind, external_id) == (ContentKind.SERIES, "1399"):
            return ContentDetail(
                source=Source.TMDB,
                kind=kind,
                external_id="1399",
                title="Game of Thrones",
                episodes_count=3,
                seasons=[
                    SeasonSummary(number=1, name="Saison 1", episode_count=2),
                    SeasonSummary(number=2, name="Saison 2", episode_count=1),
                    SeasonSummary(number=0, name="Épisodes spéciaux", episode_count=1),
                ],
                source_url="https://exemple.fr/1399",
                is_finished=True,
            )
        return None

    async def get_season(
        self, http: httpx.AsyncClient, external_id: str, season_number: int
    ) -> list[EpisodeSummary] | None:
        if self.en_panne:
            raise ProviderError("source en panne")
        episodes = {0: 1, 1: 2, 2: 1}.get(season_number) if external_id == "1399" else None
        if episodes is None:
            return None
        return [
            EpisodeSummary(season_number=season_number, number=n, title=f"Épisode {n}")
            for n in range(1, episodes + 1)
        ]

    async def get_popular(self, http: httpx.AsyncClient, kind: ContentKind) -> list[ContentDetail]:
        """Un film populaire, et un anime signalé sur Crunchyroll."""
        if kind == ContentKind.ANIME:
            return [
                ContentDetail(
                    source=Source.TMDB,
                    kind=ContentKind.ANIME,
                    external_id="9001",
                    title="Frieren",
                    source_url="https://exemple.fr/9001",
                    streaming_sites=["Crunchyroll", "Site inconnu"],
                )
            ]
        if kind != ContentKind.MOVIE:
            return []
        return [
            ContentDetail(
                source=Source.TMDB,
                kind=ContentKind.MOVIE,
                external_id="680",
                title="Pulp Fiction",
                poster_url="https://img/680.jpg",
                source_url="https://exemple.fr/680",
            )
        ]

    async def get_platform_titles(
        self, http: httpx.AsyncClient, kind: ContentKind, provider_id: int, anime: bool = False
    ) -> list[ContentDetail]:
        """Netflix (8) propose Pulp Fiction ; les autres plateformes, rien."""
        if anime or provider_id != 8 or kind != ContentKind.MOVIE:
            return []
        return await self.get_popular(http, kind)

    async def get_characters(
        self, http: httpx.AsyncClient, kind: ContentKind, external_id: str
    ) -> list[CharacterSummary]:
        """Un personnage de chaque importance."""
        roles = [
            ("Neo", CharacterRole.HERO),
            ("Morpheus", CharacterRole.MAIN),
            ("Oracle", CharacterRole.SUPPORTING),
            ("Tank", CharacterRole.RECURRING),
            ("Figurant", CharacterRole.BACKGROUND),
        ]
        return [
            CharacterSummary(
                name=f"{name} ({external_id})",
                image_url=f"https://img/{external_id}/{order}.jpg",
                role=role,
                order=order,
            )
            for order, (name, role) in enumerate(roles)
        ]


@dataclass
class Contexte:
    """Ce dont un test de suivi a besoin : la fausse source et deux comptes."""

    source: FausseSource
    alice: User
    bob: User
    session: AsyncSession

    def connecter(self, user: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture
async def contexte(db_client: AsyncClient, db_session: AsyncSession) -> AsyncIterator[Contexte]:
    alice = User(email="alice@exemple.fr", username="alice_test", password_hash="x")
    bob = User(email="bob@exemple.fr", username="bob_test", password_hash="x")
    db_session.add_all([alice, bob])
    # Les contenus de la fausse source existent peut-être déjà dans la base
    # locale (essais à la main) : on les retire DANS la transaction du test,
    # annulée à la fin. Les vraies données ne sont donc jamais touchées.
    await db_session.execute(
        delete(Content).where(
            Content.source == "tmdb", Content.external_id.in_(["603", "1399", "680", "9001"])
        )
    )
    # Le catalogue de cartes local (contenus populaires) est vidé lui aussi,
    # le temps du test : les tirages ne dépendent que des données du test.
    await db_session.execute(delete(Card))
    await db_session.commit()

    # Cache vidé : les fiches doivent venir de la fausse source, pas de Redis.
    await vider_cache_catalogue()

    ctx = Contexte(source=FausseSource(), alice=alice, bob=bob, session=db_session)
    ctx.connecter(alice)
    app.dependency_overrides[get_providers] = lambda: [ctx.source]
    app.dependency_overrides[get_http_client] = lambda: None
    try:
        yield ctx
    finally:
        for dependency in (get_current_user, get_providers, get_http_client):
            app.dependency_overrides.pop(dependency, None)
        await vider_cache_catalogue()
