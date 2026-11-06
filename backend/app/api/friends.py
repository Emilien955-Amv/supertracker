"""Routes du social : recherche d'utilisateurs, profils, amis."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.core.rate_limit import enforce_rate_limit
from app.models import Rarity, User
from app.schemas.auth import UserRead
from app.schemas.gamification import BadgeBrief
from app.schemas.social import (
    FriendsRead,
    ProfileRead,
    ProfileStatsRead,
    ProfileUpdate,
    PublicUser,
    RarityCount,
)
from app.services import social
from app.services.social import Relation

router = APIRouter(tags=["Social"])

USER_NOT_FOUND = "Utilisateur introuvable."


async def _find(session: SessionDep, username: str) -> User:
    try:
        return await social.find_user(session, username)
    except social.UserNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, USER_NOT_FOUND) from None


async def _public(session: SessionDep, me: User, user: User) -> PublicUser:
    return PublicUser(
        username=user.username,
        avatar_url=user.avatar_url,
        relation=await social.relation(session, me, user),
    )


@router.patch("/users/me", summary="Modifier ma présentation et la visibilité de mon profil")
async def update_me(user: CurrentUser, session: SessionDep, body: ProfileUpdate) -> UserRead:
    if body.bio is not None:
        user.bio = body.bio or None
    if body.is_public is not None:
        user.is_public = body.is_public
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.get("/users/search", summary="Chercher des utilisateurs par pseudo")
async def search_users(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=30)],
) -> list[PublicUser]:
    await enforce_rate_limit(f"usersearch:{user.id}", limit=60, window_seconds=60)
    return [
        await _public(session, user, other) for other in await social.search_users(session, user, q)
    ]


@router.get(
    "/users/{username}/profile",
    summary="Profil d'un utilisateur (détail visible par ses amis, ou par tous s'il est public)",
    responses={404: {"description": USER_NOT_FOUND}},
)
async def profile(user: CurrentUser, session: SessionDep, username: str) -> ProfileRead:
    other = await _find(session, username)
    rel = await social.relation(session, user, other)
    visible = social.can_see(other, rel)
    result = ProfileRead(
        username=other.username,
        avatar_url=other.avatar_url,
        relation=rel,
        visible=visible,
        is_public=other.is_public,
    )
    if not visible:
        return result
    stats = await social.profile_stats(session, other)
    return result.model_copy(
        update={
            "bio": other.bio,
            "member_since": other.created_at,
            "stats": ProfileStatsRead(
                level=stats.level,
                xp=stats.xp,
                episodes=stats.episodes,
                movies=stats.movies,
                series_completed=stats.series_completed,
                cards=stats.cards,
                top_cards=[
                    RarityCount(rarity=r, count=stats.top_cards.get(r, 0))
                    for r in (Rarity.DIVINE, Rarity.MYTHIC, Rarity.LEGENDARY)
                ],
                badges=[BadgeBrief.of(b) for b in stats.badges],
            ),
        }
    )


@router.get("/friends", summary="Mes amis et mes demandes d'amis")
async def my_friends(user: CurrentUser, session: SessionDep) -> FriendsRead:
    lists = await social.friend_lists(session, user)

    def public(users: list[User], relation: Relation) -> list[PublicUser]:
        return [
            PublicUser(username=u.username, avatar_url=u.avatar_url, relation=relation)
            for u in users
        ]

    return FriendsRead(
        friends=public(lists.friends, Relation.FRIENDS),
        incoming=public(lists.incoming, Relation.INCOMING),
        outgoing=public(lists.outgoing, Relation.OUTGOING),
    )


@router.post(
    "/friends/{username}",
    summary="Envoyer une demande d'ami, ou accepter celle reçue",
    responses={404: {"description": USER_NOT_FOUND}, 409: {"description": "Refusé"}},
)
async def add_friend(user: CurrentUser, session: SessionDep, username: str) -> PublicUser:
    await enforce_rate_limit(f"friends:{user.id}", limit=30, window_seconds=60)
    other = await _find(session, username)
    if other.id == user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous ne pouvez pas vous ajouter vous-même.")
    try:
        rel = await social.add_friend(session, user, other)
    except social.TooManyRequestsError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Trop de demandes en attente ({social.MAX_PENDING} au maximum).",
        ) from None
    return PublicUser(username=other.username, avatar_url=other.avatar_url, relation=rel)


@router.delete(
    "/friends/{username}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un ami, refuser ou annuler une demande",
    responses={404: {"description": USER_NOT_FOUND}},
)
async def remove_friend(user: CurrentUser, session: SessionDep, username: str) -> Response:
    other = await _find(session, username)
    await social.remove_friend(session, user, other)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
