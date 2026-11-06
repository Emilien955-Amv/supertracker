"""Collections complètes : maîtrises et titre de profil.

- table masteries : œuvres dont un joueur possède toutes les cartes ;
- users.title_content_id : titre affiché sous le pseudo (œuvre complétée choisie).

Révision : 0010
Précédente : 0009
Créée le : 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "masteries",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_masteries_content_id_contents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_masteries_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "content_id", name=op.f("pk_masteries")),
    )
    op.add_column("users", sa.Column("title_content_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_users_title_content_id_contents"),
        "users",
        "contents",
        ["title_content_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_users_title_content_id_contents"), "users", type_="foreignkey")
    op.drop_column("users", "title_content_id")
    op.drop_table("masteries")
