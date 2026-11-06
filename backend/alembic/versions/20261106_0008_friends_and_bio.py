"""Social : amitiés et présentation du profil.

- table friendships (demande d'ami, puis acceptation), une par paire ;
- users.bio : petite présentation affichée sur le profil.

Révision : 0008
Précédente : 0007
Créée le : 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "friendships",
        sa.Column("requester_id", sa.BigInteger(), nullable=False),
        sa.Column("addressee_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted')", name=op.f("ck_friendships_status_valid")
        ),
        sa.CheckConstraint("requester_id <> addressee_id", name=op.f("ck_friendships_not_self")),
        sa.ForeignKeyConstraint(
            ["addressee_id"],
            ["users.id"],
            name=op.f("fk_friendships_addressee_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name=op.f("fk_friendships_requester_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("requester_id", "addressee_id", name=op.f("pk_friendships")),
    )
    op.create_index("ix_friendships_addressee_id", "friendships", ["addressee_id"], unique=False)
    # Une seule amitié par paire, quel que soit le sens (A→B ou B→A).
    op.create_index(
        "uq_friendships_pair",
        "friendships",
        [
            sa.text("least(requester_id, addressee_id)"),
            sa.text("greatest(requester_id, addressee_id)"),
        ],
        unique=True,
    )
    op.add_column("users", sa.Column("bio", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "bio")
    op.drop_index("uq_friendships_pair", table_name="friendships")
    op.drop_index("ix_friendships_addressee_id", table_name="friendships")
    op.drop_table("friendships")
