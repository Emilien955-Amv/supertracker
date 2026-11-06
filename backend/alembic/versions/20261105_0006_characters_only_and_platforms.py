"""Cartes : uniquement des personnages, et plateformes de diffusion.

- vide le catalogue de cartes (nouveau format : personnages uniquement,
  sans rôles de doublage), recréé automatiquement ;
- force la régénération des cartes (nouvelles raretés par importance) ;
- table content_platforms pour les boosters Netflix, Disney+, Prime Video…

Révision : 0006
Précédente : 0005
Créée le : 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Données : on ne garde que les cartes de personnages.
    # Nouveau format (personnages uniquement, clé par nom) : catalogue recréé
    # automatiquement par la tâche d'arrière-plan.
    op.execute("DELETE FROM cards")
    op.execute("UPDATE contents SET cards_generated_at = NULL")
    op.create_table(
        "content_platforms",
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_content_platforms_content_id_contents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("content_id", "platform", name=op.f("pk_content_platforms")),
    )
    op.create_index(
        op.f("ix_content_platforms_platform"), "content_platforms", ["platform"], unique=False
    )


def downgrade() -> None:
    # Les cartes supprimées ne reviennent pas : elles seraient recréées au besoin.
    op.drop_index(op.f("ix_content_platforms_platform"), table_name="content_platforms")
    op.drop_table("content_platforms")
