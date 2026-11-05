"""Suivi des contenus et bibliothèques personnelles.

Tables : contents, episodes (copie locale des sources), trackings,
episode_views (suivi), libraries, library_items (bibliothèques).

Révision : 0003
Précédente : 0002
Créée le : 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contents",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("external_id", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("original_title", sa.String(length=300), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("poster_url", sa.String(length=500), nullable=True),
        sa.Column("backdrop_url", sa.String(length=500), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("episodes_count", sa.Integer(), nullable=True),
        sa.Column("is_finished", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contents")),
        sa.UniqueConstraint("source", "kind", "external_id", name=op.f("uq_contents_source")),
    )
    op.create_table(
        "episodes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("season_number", sa.SmallInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("air_date", sa.Date(), nullable=True),
        sa.Column("runtime_minutes", sa.Integer(), nullable=True),
        sa.Column("still_url", sa.String(length=500), nullable=True),
        sa.Column(
            "synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_episodes_content_id_contents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_episodes")),
        sa.UniqueConstraint(
            "content_id", "season_number", "number", name=op.f("uq_episodes_content_id")
        ),
    )
    op.create_table(
        "libraries",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("view_mode", sa.String(length=10), server_default="grid", nullable=False),
        sa.Column("sort_mode", sa.String(length=10), server_default="manual", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("color ~ '^#[0-9a-f]{6}$'", name=op.f("ck_libraries_color_hex")),
        sa.CheckConstraint(
            "sort_mode IN ('manual', 'alpha', 'category', 'recent')",
            name=op.f("ck_libraries_sort_mode_valid"),
        ),
        sa.CheckConstraint(
            "view_mode IN ('grid', 'shelf', 'list')", name=op.f("ck_libraries_view_mode_valid")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_libraries_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_libraries")),
        sa.UniqueConstraint("user_id", "name", name=op.f("uq_libraries_user_id")),
    )
    op.create_index(op.f("ix_libraries_user_id"), "libraries", ["user_id"], unique=False)
    op.create_table(
        "trackings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=True),
        sa.Column("review", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'watching', 'completed', 'paused', 'dropped')",
            name=op.f("ck_trackings_status_valid"),
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 10", name=op.f("ck_trackings_rating_range")),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_trackings_content_id_contents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_trackings_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trackings")),
        sa.UniqueConstraint("user_id", "content_id", name=op.f("uq_trackings_user_id")),
    )
    op.create_index(op.f("ix_trackings_content_id"), "trackings", ["content_id"], unique=False)
    op.create_table(
        "episode_views",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("episode_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "watched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["episode_id"],
            ["episodes.id"],
            name=op.f("fk_episode_views_episode_id_episodes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_episode_views_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "episode_id", name=op.f("pk_episode_views")),
    )
    op.create_index(
        op.f("ix_episode_views_episode_id"), "episode_views", ["episode_id"], unique=False
    )
    op.create_table(
        "library_items",
        sa.Column("library_id", sa.BigInteger(), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["contents.id"],
            name=op.f("fk_library_items_content_id_contents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["library_id"],
            ["libraries.id"],
            name=op.f("fk_library_items_library_id_libraries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("library_id", "content_id", name=op.f("pk_library_items")),
    )
    op.create_index(
        op.f("ix_library_items_content_id"), "library_items", ["content_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_library_items_content_id"), table_name="library_items")
    op.drop_table("library_items")
    op.drop_index(op.f("ix_episode_views_episode_id"), table_name="episode_views")
    op.drop_table("episode_views")
    op.drop_index(op.f("ix_trackings_content_id"), table_name="trackings")
    op.drop_table("trackings")
    op.drop_index(op.f("ix_libraries_user_id"), table_name="libraries")
    op.drop_table("libraries")
    op.drop_table("episodes")
    op.drop_table("contents")
