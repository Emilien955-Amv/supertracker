"""Points de contrôle de santé de l'API.

Ils serviront à Kubernetes (étape 5) pour savoir si un conteneur est :
- « vivant » (liveness) : sinon, Kubernetes le redémarre ;
- « prêt » (readiness) : sinon, Kubernetes ne lui envoie pas de trafic.
"""

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.cache import redis_client
from app.db import get_session

router = APIRouter(prefix="/health", tags=["Santé"])
log = structlog.get_logger()


class LivenessResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    redis: bool
    version: str


@router.get("/live", summary="Le processus répond-il ?")
async def liveness() -> LivenessResponse:
    # Volontairement trivial : ne dépend d'aucun service externe.
    return LivenessResponse(status="ok")


@router.get(
    "",
    summary="L'API et ses dépendances sont-elles opérationnelles ?",
    responses={503: {"model": ReadinessResponse, "description": "Une dépendance est en panne"}},
)
async def readiness(
    response: Response,
    session: AsyncSession = Depends(get_session),  # noqa: B008 (usage normal avec FastAPI)
) -> ReadinessResponse:
    database_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
        log.exception("health.database_unreachable")

    redis_ok = True
    try:
        await redis_client.ping()
    except Exception:
        redis_ok = False
        log.exception("health.redis_unreachable")

    healthy = database_ok and redis_ok
    if not healthy:
        # Code HTTP 503 : les outils de supervision comprennent la panne
        # sans avoir à lire le contenu de la réponse.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ok" if healthy else "degraded",
        database=database_ok,
        redis=redis_ok,
        version=__version__,
    )
