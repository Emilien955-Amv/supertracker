"""Routes liées au compte de l'utilisateur connecté."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.schemas.auth import UserRead
from app.services import social

router = APIRouter(prefix="/users", tags=["Utilisateurs"])


@router.get("/me", summary="Mon compte", responses={401: {"description": "Non connecté"}})
async def read_me(user: CurrentUser, session: SessionDep) -> UserRead:
    return UserRead.model_validate(user).model_copy(
        update={"title": await social.title_of(session, user)}
    )
