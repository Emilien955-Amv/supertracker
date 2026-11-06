"""Sondages : demandes d'ajout au catalogue de cartes et votes.

Révision : 0011
Précédente : 0010
Créée le : 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "work_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("poster_url", sa.String(length=500), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("requested_by", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=10), server_default="open", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'added')", name=op.f("ck_work_requests_status_valid")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name=op.f("fk_work_requests_requested_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_requests")),
        sa.UniqueConstraint("source", "kind", "external_id", name=op.f("uq_work_requests_source")),
    )
    op.create_table(
        "work_request_votes",
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["work_requests.id"],
            name=op.f("fk_work_request_votes_request_id_work_requests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_work_request_votes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("request_id", "user_id", name=op.f("pk_work_request_votes")),
    )
    op.create_index(
        op.f("ix_work_request_votes_user_id"), "work_request_votes", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_work_request_votes_user_id"), table_name="work_request_votes")
    op.drop_table("work_request_votes")
    op.drop_table("work_requests")
