"""Cartes à collectionner.

Tables : cards (catalogue), user_cards (collection), boosters, booster_cards
(historique des tirages), card_wallets (fragments) ; colonne
contents.cards_generated_at.

Révision : 0005
Précédente : 0004
Créée le : 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "boosters",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_boosters_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_boosters")),
        sa.UniqueConstraint("user_id", "key", name=op.f("uq_boosters_user_id")),
    )
    op.create_index(op.f("ix_boosters_user_id"), "boosters", ["user_id"], unique=False)
    op.create_table(
        "card_wallets",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("fragments", sa.Integer(), server_default="0", nullable=False),
        sa.Column("boosters_since_epic", sa.Integer(), server_default="0", nullable=False),
        sa.Column("timer_slot", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("fragments >= 0", name=op.f("ck_card_wallets_fragments_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_card_wallets_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_card_wallets")),
    )
    op.create_table(
        "cards",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("source_key", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("rarity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.String(length=200), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_cards_content_id_contents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cards")),
        sa.UniqueConstraint("content_id", "source_key", name=op.f("uq_cards_content_id")),
    )
    op.create_index(op.f("ix_cards_content_id"), "cards", ["content_id"], unique=False)
    op.create_table(
        "booster_cards",
        sa.Column("booster_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column("duplicate", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("fragments", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["booster_id"],
            ["boosters.id"],
            name=op.f("fk_booster_cards_booster_id_boosters"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["cards.id"],
            name=op.f("fk_booster_cards_card_id_cards"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("booster_id", "position", name=op.f("pk_booster_cards")),
    )
    op.create_table(
        "user_cards",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("card_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "obtained_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["card_id"], ["cards.id"], name=op.f("fk_user_cards_card_id_cards"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_cards_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "card_id", name=op.f("pk_user_cards")),
    )
    op.create_index(op.f("ix_user_cards_card_id"), "user_cards", ["card_id"], unique=False)
    op.add_column(
        "contents", sa.Column("cards_generated_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("contents", "cards_generated_at")
    op.drop_index(op.f("ix_user_cards_card_id"), table_name="user_cards")
    op.drop_table("user_cards")
    op.drop_table("booster_cards")
    op.drop_index(op.f("ix_cards_content_id"), table_name="cards")
    op.drop_table("cards")
    op.drop_table("card_wallets")
    op.drop_index(op.f("ix_boosters_user_id"), table_name="boosters")
    op.drop_table("boosters")
