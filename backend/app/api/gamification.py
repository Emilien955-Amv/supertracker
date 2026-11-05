"""Route du profil de joueur : niveau, série de jours, succès, derniers gains."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models import UserBadge, XpEvent
from app.schemas.gamification import BadgeRead, ProfileRead, XpEventRead
from app.services import gamification as game
from app.services.badges import BADGES

router = APIRouter(prefix="/gamification", tags=["Gamification"])


@router.get("/me", summary="Mon niveau, ma série de jours et mes succès")
async def my_profile(user: CurrentUser, session: SessionDep) -> ProfileRead:
    xp = await game.total_xp(session, user.id)
    level = game.level_for_xp(xp)
    streak = await game.streak_days(session, user.id)
    progress = await game.badge_progress(session, user.id)
    earned = {
        badge.code: badge.earned_at
        for badge in await session.scalars(select(UserBadge).where(UserBadge.user_id == user.id))
    }
    recent = await session.scalars(
        select(XpEvent)
        .where(XpEvent.user_id == user.id)
        .order_by(XpEvent.created_at.desc(), XpEvent.id.desc())
        .limit(15)
    )
    return ProfileRead(
        xp=xp,
        level=level,
        level_start_xp=game.xp_for_level(level),
        next_level_xp=game.xp_for_level(level + 1),
        streak_days=streak,
        streak_bonus_percent=game.streak_bonus_percent(streak),
        today_watch_xp=await game.watch_xp_on(session, user.id, game.today()),
        daily_cap=game.DAILY_CAP,
        badges=[
            BadgeRead(
                code=badge.code,
                name=badge.name,
                icon=badge.icon,
                tier=badge.tier,
                description=badge.description,
                threshold=badge.threshold,
                progress=min(progress[badge.metric], badge.threshold),
                earned_at=earned.get(badge.code),
            )
            for badge in BADGES
        ],
        recent=[
            XpEventRead(
                label=game.LABELS[game.XpKind(event.kind)],
                amount=event.amount,
                created_at=event.created_at,
            )
            for event in recent
        ],
    )
