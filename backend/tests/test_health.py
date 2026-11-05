"""Tests des points de contrôle de santé."""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from app.cache import redis_client
from app.db import get_session
from app.main import app


async def test_liveness_repond_toujours(client: AsyncClient) -> None:
    response = await client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
async def test_readiness_avec_base_et_redis(client: AsyncClient) -> None:
    """Test d'intégration : nécessite PostgreSQL et Redis réellement démarrés."""
    response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert body["redis"] is True


class SessionFactice:
    """Imite une session SQLAlchemy dont la requête réussit toujours."""

    async def execute(self, *_args: object) -> None:
        return None


async def session_factice() -> AsyncIterator[SessionFactice]:
    yield SessionFactice()


async def test_readiness_signale_une_panne_redis(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si Redis est injoignable, l'API doit répondre 503 et le préciser.

    Test unitaire : la base et Redis sont simulés, aucun service n'est requis.
    """

    async def ping_en_panne() -> bool:
        raise ConnectionError("Redis injoignable")

    monkeypatch.setattr(redis_client, "ping", ping_en_panne)
    app.dependency_overrides[get_session] = session_factice
    try:
        response = await client.get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["redis"] is False
    assert response.json()["database"] is True
