"""Échanges de cartes : doublons gardés et propositions d'échange.

- user_cards.copies : nombre d'exemplaires d'une carte (au moins 1) ;
- tables trades et trade_items : échanges proposés entre amis.

Révision : 0012
Précédente : 0011
Créée le : 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("proposer_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column("message", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'cancelled')",
            name=op.f("ck_trades_status_valid"),
        ),
        sa.CheckConstraint("proposer_id <> recipient_id", name=op.f("ck_trades_not_self")),
        sa.ForeignKeyConstraint(
            ["proposer_id"],
            ["users.id"],
            name=op.f("fk_trades_proposer_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            name=op.f("fk_trades_recipient_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trades")),
    )
    op.create_index(
        "ix_trades_proposer_id_status", "trades", ["proposer_id", "status"], unique=False
    )
    op.create_index(
        "ix_trades_recipient_id_status", "trades", ["recipient_id", "status"], unique=False
    )
    op.create_table(
        "trade_items",
        sa.Column("trade_id", sa.BigInteger(), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("from_proposer", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["card_id"], ["cards.id"], name=op.f("fk_trade_items_card_id_cards"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["trade_id"],
            ["trades.id"],
            name=op.f("fk_trade_items_trade_id_trades"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "trade_id", "card_id", "from_proposer", name=op.f("pk_trade_items")
        ),
    )
    op.add_column(
        "user_cards", sa.Column("copies", sa.Integer(), server_default="1", nullable=False)
    )
    op.create_check_constraint(op.f("ck_user_cards_copies_positive"), "user_cards", "copies >= 1")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_user_cards_copies_positive"), "user_cards", type_="check")
    op.drop_column("user_cards", "copies")
    op.drop_table("trade_items")
    op.drop_index("ix_trades_recipient_id_status", table_name="trades")
    op.drop_index("ix_trades_proposer_id_status", table_name="trades")
    op.drop_table("trades")
