"""Routes liées au compte de l'utilisateur connecté."""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.auth import UserRead

router = APIRouter(prefix="/users", tags=["Utilisateurs"])


@router.get("/me", summary="Mon compte", responses={401: {"description": "Non connecté"}})
async def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
