"""Routes du catalogue : recherche unifiée et fiche détaillée d'un contenu."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, ExternalId, HttpDep, ProvidersDep
from app.core.rate_limit import enforce_rate_limit
from app.providers.base import (
    ContentDetail,
    ContentKind,
    ProviderError,
    SearchResult,
    Source,
)
from app.services import catalog

router = APIRouter(prefix="/catalog", tags=["Catalogue"])


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
    external_id: ExternalId,
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
