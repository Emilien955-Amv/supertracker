"""Formats d'échange de la gamification."""

from datetime import datetime

from pydantic import BaseModel

from app.services.badges import Badge, Tier
from app.services.gamification import LABELS, Rewards


class BadgeBrief(BaseModel):
    code: str
    name: str
    icon: str
    tier: Tier

    @classmethod
    def of(cls, badge: Badge) -> "BadgeBrief":
        return cls(code=badge.code, name=badge.name, icon=badge.icon, tier=badge.tier)


class RewardLine(BaseModel):
    label: str
    amount: int


class RewardsRead(BaseModel):
    """Ce que l'action vient de rapporter (notification « +25 XP »)."""

    xp: int
    lines: list[RewardLine]
    badges: list[BadgeBrief]
    level_up: int | None  # nouveau niveau atteint, s'il y en a un
    streak_days: int

    @classmethod
    def of(cls, rewards: Rewards) -> "RewardsRead | None":
        if rewards.is_empty and rewards.level_after == rewards.level_before:
            return None
        return cls(
            xp=rewards.xp,
            lines=[
                RewardLine(label=LABELS[kind], amount=amount)
                for kind, amount in rewards.gains.items()
                if amount
            ],
            badges=[BadgeBrief.of(badge) for badge in rewards.badges],
            level_up=rewards.level_after if rewards.level_after > rewards.level_before else None,
            streak_days=rewards.streak_days,
        )


class BadgeRead(BadgeBrief):
    description: str
    threshold: int
    progress: int  # valeur actuelle de la mesure (plafonnée au seuil)
    earned_at: datetime | None


class XpEventRead(BaseModel):
    label: str
    amount: int
    created_at: datetime


class ProfileRead(BaseModel):
    xp: int
    level: int
    level_start_xp: int  # XP au début du niveau actuel
    next_level_xp: int  # XP nécessaires pour le niveau suivant
    streak_days: int
    streak_bonus_percent: int
    today_watch_xp: int
    daily_cap: int
    badges: list[BadgeRead]
    recent: list[XpEventRead]
