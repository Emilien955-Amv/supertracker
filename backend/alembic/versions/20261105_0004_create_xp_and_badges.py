"""Gamification : registre des points d'expérience et succès débloqués.

Tables : xp_events (un gain d'XP par ligne), user_badges.

Révision : 0004
Précédente : 0003
Créée le : 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_badges",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column(
            "earned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_badges_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "code", name=op.f("pk_user_badges")),
    )
    op.create_table(
        "xp_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_xp_events_content_id_contents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_xp_events_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_xp_events")),
        sa.UniqueConstraint("user_id", "key", name=op.f("uq_xp_events_user_id")),
    )
    op.create_index("ix_xp_events_user_id_day", "xp_events", ["user_id", "day"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_xp_events_user_id_day", table_name="xp_events")
    op.drop_table("xp_events")
    op.drop_table("user_badges")
