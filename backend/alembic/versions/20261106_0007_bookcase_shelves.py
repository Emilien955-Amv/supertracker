"""Bibliothèque visuelle : étagères et personnalisation du meuble.

- table library_shelves (étagères d'une bibliothèque) ;
- library_items.shelf_id : étagère où l'objet est rangé ;
- libraries.wood / wall / item_size : bois, couleur du mur, taille des objets ;
- nouvelle vue « bookcase » ;
- chaque bibliothèque existante reçoit une étagère avec tout son contenu.

Révision : 0007
Précédente : 0006
Créée le : 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_shelves",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("library_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["library_id"],
            ["libraries.id"],
            name=op.f("fk_library_shelves_library_id_libraries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_library_shelves")),
    )
    op.create_index(
        op.f("ix_library_shelves_library_id"), "library_shelves", ["library_id"], unique=False
    )
    op.add_column(
        "libraries", sa.Column("wood", sa.String(length=10), server_default="oak", nullable=False)
    )
    op.add_column(
        "libraries",
        sa.Column("wall", sa.String(length=7), server_default="#2b2236", nullable=False),
    )
    op.add_column(
        "libraries",
        sa.Column("item_size", sa.String(length=10), server_default="medium", nullable=False),
    )
    op.add_column("library_items", sa.Column("shelf_id", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_library_items_shelf_id"), "library_items", ["shelf_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_library_items_shelf_id_library_shelves"),
        "library_items",
        "library_shelves",
        ["shelf_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Contraintes de validation (non détectées automatiquement par Alembic).
    op.drop_constraint(op.f("ck_libraries_view_mode_valid"), "libraries", type_="check")
    op.create_check_constraint(
        op.f("ck_libraries_view_mode_valid"),
        "libraries",
        "view_mode IN ('bookcase', 'grid', 'shelf', 'list')",
    )
    op.create_check_constraint(
        op.f("ck_libraries_wood_valid"), "libraries", "wood IN ('oak', 'walnut', 'ebony', 'white')"
    )
    op.create_check_constraint(
        op.f("ck_libraries_item_size_valid"),
        "libraries",
        "item_size IN ('small', 'medium', 'large')",
    )
    op.create_check_constraint(
        op.f("ck_libraries_wall_hex"), "libraries", "wall ~ '^#[0-9a-f]{6}$'"
    )

    # Données : une première étagère par bibliothèque, avec tout son contenu,
    # et la nouvelle vue « bibliothèque » par défaut.
    op.execute(
        "INSERT INTO library_shelves (library_id, name, position) SELECT id, NULL, 0 FROM libraries"
    )
    op.execute(
        "UPDATE library_items AS i SET shelf_id = s.id "
        "FROM library_shelves AS s WHERE s.library_id = i.library_id"
    )
    op.execute("UPDATE libraries SET view_mode = 'bookcase'")


def downgrade() -> None:
    op.execute("UPDATE libraries SET view_mode = 'grid' WHERE view_mode = 'bookcase'")
    op.drop_constraint(op.f("ck_libraries_wall_hex"), "libraries", type_="check")
    op.drop_constraint(op.f("ck_libraries_item_size_valid"), "libraries", type_="check")
    op.drop_constraint(op.f("ck_libraries_wood_valid"), "libraries", type_="check")
    op.drop_constraint(op.f("ck_libraries_view_mode_valid"), "libraries", type_="check")
    op.create_check_constraint(
        op.f("ck_libraries_view_mode_valid"), "libraries", "view_mode IN ('grid', 'shelf', 'list')"
    )
    op.drop_constraint(
        op.f("fk_library_items_shelf_id_library_shelves"), "library_items", type_="foreignkey"
    )
    op.drop_index(op.f("ix_library_items_shelf_id"), table_name="library_items")
    op.drop_column("library_items", "shelf_id")
    op.drop_column("libraries", "item_size")
    op.drop_column("libraries", "wall")
    op.drop_column("libraries", "wood")
    op.drop_index(op.f("ix_library_shelves_library_id"), table_name="library_shelves")
    op.drop_table("library_shelves")
