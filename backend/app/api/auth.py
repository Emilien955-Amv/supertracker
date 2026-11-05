"""Routes d'authentification : inscription, connexion, renouvellement, déconnexion.

Protection CSRF : le cookie de renouvellement est « SameSite=Strict ». Le
navigateur ne l'envoie donc JAMAIS lors d'une requête venant d'un autre site,
ce qui empêche un site malveillant de déclencher /refresh à votre insu. Le
jeton d'accès, lui, n'est jamais dans un cookie : il est ajouté explicitement
par notre frontend, ce qu'un autre site ne peut pas faire.
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from app.api.deps import SessionDep
from app.config import get_settings
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["Authentification"])

REFRESH_COOKIE = "refresh_token"
# Le cookie n'est envoyé QUE vers /api/auth : il ne voyage pas avec les autres requêtes.
REFRESH_COOKIE_PATH = "/api/auth"


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "inconnue"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.refresh_token_days * 24 * 3600,
        httponly=True,  # illisible par JavaScript : protège d'une faille XSS
        secure=settings.cookie_secure,  # HTTPS uniquement en production
        samesite="strict",  # jamais envoyé depuis un autre site : protège du CSRF
        path=REFRESH_COOKIE_PATH,
    )


def _token_response(user_id: int) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id),
        expires_in=get_settings().access_token_minutes * 60,
    )


def _invalid_session() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expirée. Veuillez vous reconnecter.",
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
    responses={409: {"description": "E-mail ou pseudo déjà utilisé"}},
)
async def register(data: RegisterRequest, request: Request, session: SessionDep) -> UserRead:
    # 5 créations de compte par heure et par adresse IP : freine les robots.
    await enforce_rate_limit(f"register:{_client_ip(request)}", limit=5, window_seconds=3600)
    try:
        user = await auth_service.register_user(session, data)
    except auth_service.EmailAlreadyUsedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Un compte existe déjà avec cet e-mail."
        ) from None
    except auth_service.UsernameAlreadyUsedError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce pseudo est déjà pris.") from None
    return UserRead.model_validate(user)


@router.post(
    "/login",
    summary="Se connecter",
    responses={
        401: {"description": "Identifiants incorrects"},
        429: {"description": "Trop de tentatives"},
    },
)
async def login(
    data: LoginRequest, request: Request, response: Response, session: SessionDep
) -> TokenResponse:
    ip = _client_ip(request)
    # Deux limites complémentaires contre la force brute :
    # - 5 essais / 15 min sur un même compte depuis une même adresse IP ;
    # - 20 essais / 15 min depuis une même IP, tous comptes confondus.
    await enforce_rate_limit(f"login:{ip}:{data.email}", limit=5, window_seconds=900)
    await enforce_rate_limit(f"login:{ip}", limit=20, window_seconds=900)

    user = await auth_service.authenticate(session, data.email, data.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou mot de passe incorrect.")

    _set_refresh_cookie(response, await auth_service.issue_refresh_token(session, user.id))
    return _token_response(user.id)


@router.post(
    "/refresh",
    summary="Obtenir un nouveau jeton d'accès",
    responses={401: {"description": "Session absente, expirée ou révoquée"}},
)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenResponse:
    await enforce_rate_limit(f"refresh:{_client_ip(request)}", limit=60, window_seconds=60)
    if not refresh_token:
        raise _invalid_session()

    result = await auth_service.rotate_refresh_token(session, refresh_token)
    if result is None:
        response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
        raise _invalid_session()

    user, new_token = result
    _set_refresh_cookie(response, new_token)
    return _token_response(user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Se déconnecter")
async def logout(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> None:
    if refresh_token:
        await auth_service.revoke_refresh_token(session, refresh_token)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
