"""Routes du catalogue : recherche unifiée et fiche détaillée d'un contenu."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.rate_limit import enforce_rate_limit
from app.http_client import get_http_client
from app.providers.base import (
    ContentDetail,
    ContentKind,
    MetadataProvider,
    ProviderError,
    SearchResult,
    Source,
)
from app.providers.registry import get_providers
from app.services import catalog

router = APIRouter(prefix="/catalog", tags=["Catalogue"])

HttpDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
ProvidersDep = Annotated[list[MetadataProvider], Depends(get_providers)]


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    unavailable_sources: list[Source]


@router.get("/search", summary="Recherche unifiée (films, séries, animes)")
async def search(
    user: CurrentUser,
    http: HttpDep,
    providers: ProvidersDep,
    q: Annotated[str, Query(min_length=2, max_length=100, description="Texte recherché")],
) -> SearchResponse:
    # Réservé aux comptes connectés et limité : protège notre quota chez TMDB.
    await enforce_rate_limit(f"search:{user.id}", limit=60, window_seconds=60)
    results, unavailable = await catalog.search_all(http, providers, q)
    return SearchResponse(query=q, results=results, unavailable_sources=unavailable)


@router.get(
    "/{source}/{kind}/{external_id}",
    summary="Fiche détaillée d'un contenu",
    responses={
        404: {"description": "Contenu introuvable"},
        502: {"description": "Source indisponible"},
    },
)
async def detail(
    user: CurrentUser,
    http: HttpDep,
    providers: ProvidersDep,
    source: Source,
    kind: ContentKind,
    # Uniquement des chiffres : impossible d'injecter un chemin ou des
    # paramètres dans l'adresse envoyée à la source.
    external_id: Annotated[str, Path(pattern=r"^\d{1,12}$")],
) -> ContentDetail:
    await enforce_rate_limit(f"detail:{user.id}", limit=120, window_seconds=60)
    try:
        content = await catalog.get_detail(http, providers, source, kind, external_id)
    except ProviderError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "La source de données ne répond pas. Réessayez dans un instant.",
        ) from None
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contenu introuvable.")
    return content
