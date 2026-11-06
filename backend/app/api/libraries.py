"""Routes des bibliothèques personnelles."""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, HttpDep, ProvidersDep, SessionDep
from app.core.rate_limit import enforce_rate_limit
from app.models import Library, LibraryShelf, TrackingStatus
from app.providers.base import ContentKind, ProviderError, Source
from app.schemas.library import (
    LayoutWrite,
    LibraryCreate,
    LibraryDetail,
    LibraryItemAdd,
    LibraryItemRead,
    LibraryOrder,
    LibraryRead,
    LibraryUpdate,
    ShelfRead,
    ShelfWrite,
)
from app.schemas.tracking import ContentRead
from app.services import content as content_service
from app.services import gamification
from app.services import libraries as service

router = APIRouter(prefix="/libraries", tags=["Bibliothèques"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"description": "Bibliothèque introuvable"}}
NAME_TAKEN = "Vous avez déjà une bibliothèque avec ce nom."


async def _get(session: SessionDep, user_id: int, library_id: int) -> Library:
    try:
        return await service.get_library(session, user_id, library_id)
    except service.LibraryNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bibliothèque introuvable.") from None


async def _read(session: SessionDep, library: Library) -> LibraryRead:
    summary = next(
        s
        for s in await service.list_libraries(session, library.user_id)
        if s.library.id == library.id
    )
    return LibraryRead.model_validate(library).model_copy(
        update={"items_count": summary.items_count, "preview": summary.preview}
    )


@router.get("", summary="Mes bibliothèques")
async def list_libraries(
    user: CurrentUser,
    session: SessionDep,
    source: Source | None = None,
    kind: ContentKind | None = None,
    external_id: Annotated[str | None, Query(pattern=r"^\d{1,12}$")] = None,
) -> list[LibraryRead]:
    """Avec source/kind/external_id, chaque bibliothèque indique si elle
    contient ce contenu (champ « contains ») : utile pour la fiche contenu."""
    content_id = None
    asked = False
    if source is not None and kind is not None and external_id is not None:
        asked = True
        content = await content_service.find_content(session, source, kind, external_id)
        content_id = content.id if content else -1  # -1 : n'est dans aucune bibliothèque
    summaries = await service.list_libraries(session, user.id, content_id)
    return [
        LibraryRead.model_validate(s.library).model_copy(
            update={
                "items_count": s.items_count,
                "preview": s.preview,
                "contains": s.contains if asked else None,
            }
        )
        for s in summaries
    ]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Créer une bibliothèque")
async def create_library(
    user: CurrentUser, session: SessionDep, body: LibraryCreate
) -> LibraryRead:
    await enforce_rate_limit(f"write:{user.id}", limit=120, window_seconds=60)
    try:
        library = await service.create_library(
            session, user.id, body.name, body.color, body.view_mode, body.sort_mode
        )
    except service.LibraryNameTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, NAME_TAKEN) from None
    except service.LibraryLimitError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Limite atteinte : {service.MAX_LIBRARIES} bibliothèques au maximum.",
        ) from None
    # Succès « Bibliothécaire » : visible ensuite sur le profil.
    await gamification.check_badges(session, user.id)
    await session.commit()
    return LibraryRead.model_validate(library)


@router.get("/{library_id}", summary="Une bibliothèque et son contenu", responses=NOT_FOUND)
async def get_library(user: CurrentUser, session: SessionDep, library_id: int) -> LibraryDetail:
    library = await _get(session, user.id, library_id)
    rows = await service.list_items(session, library)
    items = [
        LibraryItemRead(
            content=ContentRead.model_validate(content),
            shelf_id=item.shelf_id,
            position=item.position,
            added_at=item.added_at,
            tracking_status=TrackingStatus(tracking_status) if tracking_status else None,
        )
        for item, content, tracking_status in rows
    ]
    summary = await _read(session, library)
    shelves = [ShelfRead.model_validate(s) for s in await service.list_shelves(session, library)]
    return LibraryDetail(**summary.model_dump(), shelves=shelves, items=items)


@router.patch("/{library_id}", summary="Renommer, recolorer, changer l'affichage ou le tri")
async def update_library(
    user: CurrentUser, session: SessionDep, library_id: int, body: LibraryUpdate
) -> LibraryRead:
    library = await _get(session, user.id, library_id)
    # exclude_none : un champ absent ou null ne modifie rien.
    changes = body.model_dump(exclude_none=True)
    try:
        library = await service.update_library(session, library, changes)
    except service.LibraryNameTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, NAME_TAKEN) from None
    return await _read(session, library)


@router.delete(
    "/{library_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une bibliothèque"
)
async def delete_library(user: CurrentUser, session: SessionDep, library_id: int) -> Response:
    library = await _get(session, user.id, library_id)
    await service.delete_library(session, library)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{library_id}/items",
    summary="Ajouter un contenu (sans effet s'il y est déjà)",
    responses={**NOT_FOUND, 502: {"description": "Source indisponible"}},
)
async def add_item(
    user: CurrentUser,
    session: SessionDep,
    http: HttpDep,
    providers: ProvidersDep,
    library_id: int,
    body: LibraryItemAdd,
) -> ContentRead:
    library = await _get(session, user.id, library_id)
    await enforce_rate_limit(f"write:{user.id}", limit=120, window_seconds=60)
    try:
        content = await content_service.ensure_content(
            session, http, providers, body.source, body.kind, body.external_id
        )
        await service.add_item(session, library, content)
    except content_service.ContentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contenu introuvable.") from None
    except ProviderError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "La source de données ne répond pas. Réessayez dans un instant.",
        ) from None
    except service.LibraryLimitError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cette bibliothèque est pleine ({service.MAX_ITEMS} éléments au maximum).",
        ) from None
    return ContentRead.model_validate(content)


@router.delete(
    "/{library_id}/items/{content_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un contenu",
    responses=NOT_FOUND,
)
async def remove_item(
    user: CurrentUser, session: SessionDep, library_id: int, content_id: int
) -> Response:
    library = await _get(session, user.id, library_id)
    await service.remove_item(session, library, content_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{library_id}/order",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Enregistrer l'ordre manuel",
    responses={**NOT_FOUND, 422: {"description": "Liste incomplète ou avec doublons"}},
)
async def reorder(
    user: CurrentUser, session: SessionDep, library_id: int, body: LibraryOrder
) -> Response:
    library = await _get(session, user.id, library_id)
    try:
        await service.reorder(session, library, body.content_ids)
    except service.InvalidOrderError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "La liste doit contenir chaque élément de la bibliothèque, une seule fois.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Étagères (vue « bibliothèque ») -------------------------------------------------


@router.post(
    "/{library_id}/shelves",
    status_code=status.HTTP_201_CREATED,
    summary="Ajouter une étagère en bas du meuble",
    responses=NOT_FOUND,
)
async def add_shelf(
    user: CurrentUser, session: SessionDep, library_id: int, body: ShelfWrite
) -> ShelfRead:
    library = await _get(session, user.id, library_id)
    try:
        shelf = await service.add_shelf(session, library, body.name or None)
    except service.LibraryLimitError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ce meuble est complet ({service.MAX_SHELVES} étagères au maximum).",
        ) from None
    return ShelfRead.model_validate(shelf)


async def _shelf(
    session: SessionDep, user_id: int, library_id: int, shelf_id: int
) -> tuple[Library, LibraryShelf]:
    library = await _get(session, user_id, library_id)
    try:
        return library, await service.get_shelf(session, library, shelf_id)
    except service.LibraryNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Étagère introuvable.") from None


@router.patch(
    "/{library_id}/shelves/{shelf_id}", summary="Renommer une étagère", responses=NOT_FOUND
)
async def rename_shelf(
    user: CurrentUser, session: SessionDep, library_id: int, shelf_id: int, body: ShelfWrite
) -> ShelfRead:
    _, shelf = await _shelf(session, user.id, library_id, shelf_id)
    await service.rename_shelf(session, shelf, body.name or None)
    return ShelfRead.model_validate(shelf)


@router.delete(
    "/{library_id}/shelves/{shelf_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une étagère (ses objets glissent sur l'étagère voisine)",
    responses={**NOT_FOUND, 409: {"description": "Dernière étagère"}},
)
async def delete_shelf(
    user: CurrentUser, session: SessionDep, library_id: int, shelf_id: int
) -> Response:
    library, shelf = await _shelf(session, user.id, library_id, shelf_id)
    try:
        await service.delete_shelf(session, library, shelf)
    except service.LastShelfError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Un meuble garde au moins une étagère."
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{library_id}/layout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Enregistrer le rangement (étagères et objets)",
    responses={**NOT_FOUND, 422: {"description": "Rangement incomplet ou incohérent"}},
)
async def save_layout(
    user: CurrentUser, session: SessionDep, library_id: int, body: LayoutWrite
) -> Response:
    library = await _get(session, user.id, library_id)
    try:
        await service.save_layout(
            session, library, [(shelf.id, shelf.content_ids) for shelf in body.shelves]
        )
    except service.InvalidOrderError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Le rangement doit contenir chaque étagère et chaque objet une seule fois.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
