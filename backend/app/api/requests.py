"""Routes des sondages : demander les cartes d'une œuvre et voter."""

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, ExternalId, HttpDep, ProvidersDep, SessionDep
from app.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.models import RequestStatus
from app.providers.base import ContentKind, ProviderError, Source
from app.services import requests as service

router = APIRouter(prefix="/requests", tags=["Sondages"])


class RequestRead(BaseModel):
    id: int
    source: Source
    kind: ContentKind
    external_id: str
    title: str
    poster_url: str | None
    year: int | None
    status: RequestStatus
    votes: int
    votes_needed: int  # seuil pour entrer au catalogue
    voted: bool


class RequestCreate(BaseModel):
    source: Source
    kind: ContentKind
    external_id: str = Field(pattern=r"^\d{1,12}$")


class CatalogStatus(BaseModel):
    in_catalog: bool
    request: RequestRead | None


def _read(view: service.RequestView) -> RequestRead:
    r = view.request
    return RequestRead(
        id=r.id,
        source=Source(r.source),
        kind=ContentKind(r.kind),
        external_id=r.external_id,
        title=r.title,
        poster_url=r.poster_url,
        year=r.year,
        status=RequestStatus(r.status),
        votes=view.votes,
        votes_needed=get_settings().card_request_votes,
        voted=view.voted,
    )


@router.get("", summary="Demandes de cartes (les plus votées d'abord)")
async def list_requests(user: CurrentUser, session: SessionDep) -> list[RequestRead]:
    return [_read(view) for view in await service.list_requests(session, user)]


@router.post(
    "",
    summary="Demander les cartes d'une œuvre (ou voter pour la demande existante)",
    responses={404: {"description": "Œuvre introuvable"}, 409: {"description": "Refusé"}},
)
async def request_work(
    user: CurrentUser,
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    body: RequestCreate,
) -> RequestRead:
    await enforce_rate_limit(f"requests:{user.id}", limit=30, window_seconds=60)
    try:
        view = await service.request_work(
            session, http, providers, user, body.source, body.kind, body.external_id
        )
    except service.AlreadyInCatalogError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette œuvre a déjà ses cartes.") from None
    except service.TooManyRequestsError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Trop de demandes ouvertes ({service.MAX_OPEN_PER_USER} au maximum).",
        ) from None
    except service.WorkNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Œuvre introuvable.") from None
    except ProviderError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "La source de données ne répond pas. Réessayez dans un instant.",
        ) from None
    return _read(view)


@router.delete(
    "/{request_id}/vote", status_code=status.HTTP_204_NO_CONTENT, summary="Retirer mon vote"
)
async def unvote(user: CurrentUser, session: SessionDep, request_id: int) -> Response:
    await service.unvote(session, user, request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/status/{source}/{kind}/{external_id}",
    summary="L'œuvre a-t-elle ses cartes ? Sinon, la demande en cours",
)
async def catalog_status(
    user: CurrentUser,
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    source: Source,
    kind: ContentKind,
    external_id: ExternalId,
) -> CatalogStatus:
    try:
        in_catalog, view = await service.status_for(
            session, http, providers, user, source, kind, external_id
        )
    except ProviderError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "La source de données ne répond pas. Réessayez dans un instant.",
        ) from None
    return CatalogStatus(in_catalog=in_catalog, request=_read(view) if view else None)
