"""Outils partagés par tous les tests (« fixtures » pytest)."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import redis_client
from app.core.rate_limit import KEY_PREFIX
from app.db import engine, get_session
from app.main import app


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
