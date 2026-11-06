"""Catalogue de cartes resserré : œuvres choisies et leur rang.

contents.in_card_catalog : l'œuvre fait partie du catalogue de cartes (les 100
séries, films et animes les plus populaires, et les œuvres demandées) ;
contents.catalog_rank : son rang dans le classement.

Révision : 0009
Précédente : 0008
Créée le : 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column("in_card_catalog", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("contents", sa.Column("catalog_rank", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("contents", "catalog_rank")
    op.drop_column("contents", "in_card_catalog")
