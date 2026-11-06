"""Point d'entrée de l'API FastAPI.

Toutes les routes sont préfixées par /api : en production, un même nom de
domaine servira le site (/) et l'API (/api), sans configuration CORS.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import structlog
from fastapi import FastAPI

from app import __version__
from app.api import (
    auth,
    cards,
    catalog,
    friends,
    gamification,
    health,
    libraries,
    requests,
    tracking,
    trades,
    users,
)
from app.cache import redis_client
from app.config import get_settings
from app.db import engine
from app.http_client import close_http_client
from app.logging import configure_logging
from app.services import card_catalog


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Code exécuté au démarrage (avant « yield ») et à l'arrêt (après)."""
    configure_logging()
    structlog.get_logger().info("app.startup", environment=get_settings().environment)
    # Catalogue de cartes en arrière-plan (désactivé pendant les tests).
    task = None
    if get_settings().environment != "test":
        task = asyncio.create_task(card_catalog.run_forever())
    yield
    if task is not None:
        task.cancel()
        # On attend la fin de la tâche : elle libère ainsi son verrou Redis.
        with suppress(asyncio.CancelledError):
            await task
    # Arrêt propre : on libère les connexions ouvertes.
    await close_http_client()
    await redis_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SuperTracker API",
        description="API de suivi de séries, animes, films, livres et jeux vidéo.",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    for router in (
        health.router,
        auth.router,
        users.router,
        catalog.router,
        tracking.router,
        libraries.router,
        gamification.router,
        cards.router,
        friends.router,
        requests.router,
        trades.router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
