"""Logique métier de l'authentification.

Les routes HTTP (app/api/auth.py) restent fines : elles valident l'entrée,
appellent ces fonctions, puis mettent en forme la réponse. Cette séparation
permet de tester la logique sans passer par HTTP, et de la réutiliser
ailleurs (tâches planifiées, scripts d'administration…).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas.auth import RegisterRequest


class EmailAlreadyUsedError(Exception):
    pass


class UsernameAlreadyUsedError(Exception):
    pass


async def register_user(session: AsyncSession, data: RegisterRequest) -> User:
    if await session.scalar(select(User.id).where(User.email == data.email)):
        raise EmailAlreadyUsedError
    # Comparaison insensible à la casse : « Emilien » et « emilien » sont le même pseudo.
    if await session.scalar(
        select(User.id).where(func.lower(User.username) == data.username.lower())
    ):
        raise UsernameAlreadyUsedError

    user = User(
        email=data.email,
        username=data.username,
        password_hash=hash_password(data.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Deux inscriptions simultanées avec le même e-mail : la contrainte
        # d'unicité de PostgreSQL tranche, et on renvoie la même erreur.
        await session.rollback()
        raise EmailAlreadyUsedError from exc
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User | None:
    """Renvoie l'utilisateur si l'e-mail et le mot de passe sont corrects."""
    user = await session.scalar(select(User).where(User.email == email))
    # Même message et même durée de calcul que l'e-mail existe ou non :
    # un attaquant ne peut pas savoir quelles adresses sont inscrites.
    if not verify_password(password, user.password_hash if user else None):
        return None
    return user


async def issue_refresh_token(session: AsyncSession, user_id: int) -> str:
    """Crée un jeton de renouvellement et renvoie sa valeur en clair (à placer
    dans le cookie). Seule son empreinte est enregistrée."""
    token = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
        )
    )
    await session.commit()
    return token


async def rotate_refresh_token(session: AsyncSession, token: str) -> tuple[User, str] | None:
    """Échange un jeton de renouvellement valide contre un nouveau (rotation).

    Chaque jeton ne sert qu'une fois. Si un jeton DÉJÀ utilisé est présenté,
    c'est le signe qu'il a été volé et copié : par précaution, on révoque
    tous les jetons de l'utilisateur, ce qui déconnecte tous ses appareils.
    """
    now = datetime.now(UTC)
    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if stored is None or stored.expires_at <= now:
        return None

    if stored.revoked_at is not None:
        await revoke_all_tokens(session, stored.user_id)
        return None

    user = await session.get(User, stored.user_id)
    if user is None:
        return None

    stored.revoked_at = now
    new_token = await issue_refresh_token(session, user.id)  # valide aussi la révocation
    return user, new_token


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()


async def revoke_all_tokens(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
