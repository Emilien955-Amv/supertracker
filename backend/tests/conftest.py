"""Outils partagés par tous les tests (« fixtures » pytest)."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.cache import redis_client
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
