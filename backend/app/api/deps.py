"""Dépendances partagées par les routes (injectées par FastAPI)."""

from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db import get_session
from app.http_client import get_http_client
from app.models import User
from app.providers.base import MetadataProvider
from app.providers.registry import get_providers

# auto_error=False : on renvoie nous-mêmes un message d'erreur en français.
# Ce schéma ajoute aussi le bouton « Authorize » dans la documentation /api/docs.
_bearer = HTTPBearer(auto_error=False, description="Jeton obtenu via /api/auth/login")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
HttpDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
ProvidersDep = Annotated[list[MetadataProvider], Depends(get_providers)]

# Identifiant chez la source : uniquement des chiffres, ce qui rend impossible
# l'injection d'un chemin ou de paramètres dans l'adresse envoyée à la source.
ExternalId = Annotated[str, Path(pattern=r"^\d{1,12}$")]


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Identifie l'utilisateur à partir du jeton d'accès, ou répond 401."""
    user_id = decode_access_token(credentials.credentials) if credentials else None
    user = await session.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
