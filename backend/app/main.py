"""Point d'entrée de l'API FastAPI.

Toutes les routes sont préfixées par /api : en production, un même nom de
domaine servira le site (/) et l'API (/api), sans configuration CORS.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app import __version__
from app.api import auth, catalog, gamification, health, libraries, tracking, users
from app.cache import redis_client
from app.config import get_settings
from app.db import engine
from app.http_client import close_http_client
from app.logging import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Code exécuté au démarrage (avant « yield ») et à l'arrêt (après)."""
    configure_logging()
    structlog.get_logger().info("app.startup", environment=get_settings().environment)
    yield
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
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
