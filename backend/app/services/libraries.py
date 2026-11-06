"""Bibliothèques personnelles : création, contenu, tri et ordre manuel."""

from dataclasses import dataclass

from sqlalchemy import and_, case, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Content, Library, LibraryItem, LibraryShelf, SortMode, Tracking

# Limites anti-abus : largement au-dessus d'un usage normal.
MAX_LIBRARIES = 50
MAX_ITEMS = 1000
PREVIEW_SIZE = 4
MAX_SHELVES = 30
DEFAULT_SHELVES = 3


class LibraryNotFoundError(Exception):
    pass


class LibraryNameTakenError(Exception):
    pass


class LibraryLimitError(Exception):
    pass


class LastShelfError(Exception):
    """On ne peut pas supprimer la dernière étagère."""


class InvalidOrderError(Exception):
    """La liste envoyée ne correspond pas exactement au contenu de la bibliothèque."""


@dataclass
class LibrarySummary:
    library: Library
    items_count: int
    preview: list[str | None]  # affiches des premiers éléments (aperçu)
    contains: bool | None  # le contenu demandé y figure-t-il ? (None : pas demandé)


async def list_libraries(
    session: AsyncSession, user_id: int, content_id: int | None = None
) -> list[LibrarySummary]:
    counts = (
        select(LibraryItem.library_id, func.count().label("n"))
        .group_by(LibraryItem.library_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Library, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.library_id == Library.id)
            .where(Library.user_id == user_id)
            .order_by(Library.created_at, Library.id)
        )
    ).tuples()
    libraries = list(rows)
    ids = [library.id for library, _ in libraries]
    if not ids:
        return []

    # row_number() numérote les éléments de CHAQUE bibliothèque : on garde
    # les 4 premiers de chacune en une seule requête (au lieu d'une par bibliothèque).
    ranked = (
        select(
            LibraryItem.library_id,
            Content.poster_url,
            func.row_number()
            .over(
                partition_by=LibraryItem.library_id,
                order_by=(LibraryItem.position, LibraryItem.added_at),
            )
            .label("rank"),
        )
        .join(Content, Content.id == LibraryItem.content_id)
        .where(LibraryItem.library_id.in_(ids))
        .subquery()
    )
    previews: dict[int, list[str | None]] = {library_id: [] for library_id in ids}
    for library_id, poster_url in await session.execute(
        select(ranked.c.library_id, ranked.c.poster_url)
        .where(ranked.c.rank <= PREVIEW_SIZE)
        .order_by(ranked.c.library_id, ranked.c.rank)
    ):
        previews[library_id].append(poster_url)

    containing: set[int] = set()
    if content_id is not None:
        containing = set(
            await session.scalars(
                select(LibraryItem.library_id).where(
                    LibraryItem.content_id == content_id, LibraryItem.library_id.in_(ids)
                )
            )
        )

    return [
        LibrarySummary(
            library=library,
            items_count=count,
            preview=previews[library.id],
            contains=(library.id in containing) if content_id is not None else None,
        )
        for library, count in libraries
    ]


async def get_library(session: AsyncSession, user_id: int, library_id: int) -> Library:
    """Bibliothèque de l'utilisateur. Celle d'un autre est « introuvable » :
    on ne révèle même pas qu'elle existe."""
    library = await session.scalar(
        select(Library).where(Library.id == library_id, Library.user_id == user_id)
    )
    if library is None:
        raise LibraryNotFoundError
    return library


async def _check_name_free(
    session: AsyncSession, user_id: int, name: str, exclude_id: int | None = None
) -> None:
    # « Favoris » et « favoris » sont considérés comme le même nom.
    query = select(Library.id).where(
        Library.user_id == user_id, func.lower(Library.name) == name.lower()
    )
    if exclude_id is not None:
        query = query.where(Library.id != exclude_id)
    if await session.scalar(query) is not None:
        raise LibraryNameTakenError


async def _commit_or_name_taken(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:  # course entre deux requêtes simultanées
        await session.rollback()
        raise LibraryNameTakenError from exc


async def create_library(
    session: AsyncSession, user_id: int, name: str, color: str, view_mode: str, sort_mode: str
) -> Library:
    count = await session.scalar(
        select(func.count()).select_from(Library).where(Library.user_id == user_id)
    )
    if (count or 0) >= MAX_LIBRARIES:
        raise LibraryLimitError
    await _check_name_free(session, user_id, name)
    library = Library(
        user_id=user_id, name=name, color=color, view_mode=view_mode, sort_mode=sort_mode
    )
    session.add(library)
    await _commit_or_name_taken(session)
    await session.refresh(library)
    # Un meuble neuf : trois étagères vides.
    session.add_all(
        LibraryShelf(library_id=library.id, position=position)
        for position in range(DEFAULT_SHELVES)
    )
    await session.commit()
    return library


async def update_library(
    session: AsyncSession, library: Library, changes: dict[str, str]
) -> Library:
    if "name" in changes:
        await _check_name_free(session, library.user_id, changes["name"], exclude_id=library.id)
    for field, value in changes.items():
        setattr(library, field, value)
    await _commit_or_name_taken(session)
    await session.refresh(library)
    return library


async def delete_library(session: AsyncSession, library: Library) -> None:
    await session.delete(library)  # les éléments partent avec (ON DELETE CASCADE)
    await session.commit()


async def list_items(
    session: AsyncSession, library: Library
) -> list[tuple[LibraryItem, Content, str | None]]:
    """Éléments triés selon le choix de l'utilisateur, avec son statut de suivi."""
    kind_order = case({"movie": 0, "series": 1, "anime": 2}, value=Content.kind, else_=3)
    order_by = {
        SortMode.MANUAL: (LibraryItem.position, LibraryItem.added_at),
        SortMode.ALPHA: (func.lower(Content.title), Content.id),
        SortMode.CATEGORY: (kind_order, func.lower(Content.title), Content.id),
        SortMode.RECENT: (LibraryItem.added_at.desc(), Content.id.desc()),
    }[SortMode(library.sort_mode)]

    rows = await session.execute(
        select(LibraryItem, Content, Tracking.status)
        .join(Content, Content.id == LibraryItem.content_id)
        .outerjoin(
            Tracking,
            and_(Tracking.content_id == Content.id, Tracking.user_id == library.user_id),
        )
        .where(LibraryItem.library_id == library.id)
        .order_by(*order_by)
    )
    return list(rows.tuples())


async def add_item(session: AsyncSession, library: Library, content: Content) -> None:
    """Ajoute un contenu au bout de la première étagère. Sans effet s'il y est déjà."""
    count, last = (
        await session.execute(
            select(func.count(), func.max(LibraryItem.position)).where(
                LibraryItem.library_id == library.id
            )
        )
    ).one()
    if count >= MAX_ITEMS:
        raise LibraryLimitError
    shelves = await list_shelves(session, library)
    if not shelves:  # bibliothèque sans étagère : on en crée une
        shelf = LibraryShelf(library_id=library.id, position=0)
        session.add(shelf)
        await session.flush()
        shelves = [shelf]
    await session.execute(
        insert(LibraryItem)
        .values(
            library_id=library.id,
            content_id=content.id,
            shelf_id=shelves[0].id,
            position=0 if last is None else last + 1,
        )
        .on_conflict_do_nothing()
    )
    await session.commit()


# --- Étagères (vue « bibliothèque ») -------------------------------------------------


async def list_shelves(session: AsyncSession, library: Library) -> list[LibraryShelf]:
    return list(
        await session.scalars(
            select(LibraryShelf)
            .where(LibraryShelf.library_id == library.id)
            .order_by(LibraryShelf.position, LibraryShelf.id)
        )
    )


async def get_shelf(session: AsyncSession, library: Library, shelf_id: int) -> LibraryShelf:
    shelf = await session.scalar(
        select(LibraryShelf).where(
            LibraryShelf.id == shelf_id, LibraryShelf.library_id == library.id
        )
    )
    if shelf is None:
        raise LibraryNotFoundError
    return shelf


async def add_shelf(session: AsyncSession, library: Library, name: str | None) -> LibraryShelf:
    """Ajoute une étagère en bas du meuble."""
    shelves = await list_shelves(session, library)
    if len(shelves) >= MAX_SHELVES:
        raise LibraryLimitError
    shelf = LibraryShelf(
        library_id=library.id, name=name, position=(shelves[-1].position + 1) if shelves else 0
    )
    session.add(shelf)
    await session.commit()
    await session.refresh(shelf)
    return shelf


async def rename_shelf(session: AsyncSession, shelf: LibraryShelf, name: str | None) -> None:
    shelf.name = name
    await session.commit()


async def delete_shelf(session: AsyncSession, library: Library, shelf: LibraryShelf) -> None:
    """Supprime une étagère : ses objets glissent sur l'étagère voisine."""
    shelves = await list_shelves(session, library)
    if len(shelves) <= 1:
        raise LastShelfError
    others = [s for s in shelves if s.id != shelf.id]
    # L'étagère du dessus si elle existe, sinon celle du dessous.
    above = [s for s in others if s.position <= shelf.position]
    target = above[-1] if above else others[0]
    last = await session.scalar(
        select(func.max(LibraryItem.position)).where(LibraryItem.shelf_id == target.id)
    )
    moving = list(
        await session.scalars(
            select(LibraryItem)
            .where(LibraryItem.shelf_id == shelf.id)
            .order_by(LibraryItem.position)
        )
    )
    for offset, item in enumerate(moving, start=1):
        item.shelf_id = target.id
        item.position = (last if last is not None else -1) + offset
    await session.delete(shelf)
    await session.commit()


async def save_layout(
    session: AsyncSession, library: Library, layout: list[tuple[int, list[int]]]
) -> None:
    """Enregistre tout le rangement : ordre des étagères et des objets.

    « layout » : [(id de l'étagère, [ids des contenus de gauche à droite]), …],
    de l'étagère du haut à celle du bas. Chaque étagère et chaque objet de la
    bibliothèque doit y figurer exactement une fois.
    """
    shelves = {s.id: s for s in await list_shelves(session, library)}
    items = {
        item.content_id: item
        for item in await session.scalars(
            select(LibraryItem).where(LibraryItem.library_id == library.id)
        )
    }
    shelf_ids = [shelf_id for shelf_id, _ in layout]
    content_ids = [cid for _, ids in layout for cid in ids]
    if (
        len(shelf_ids) != len(set(shelf_ids))
        or set(shelf_ids) != set(shelves)
        or len(content_ids) != len(set(content_ids))
        or set(content_ids) != set(items)
    ):
        raise InvalidOrderError
    for shelf_position, (shelf_id, ids) in enumerate(layout):
        shelves[shelf_id].position = shelf_position
        for position, content_id in enumerate(ids):
            items[content_id].shelf_id = shelf_id
            items[content_id].position = position
    await session.commit()


async def remove_item(session: AsyncSession, library: Library, content_id: int) -> bool:
    result = await session.execute(
        delete(LibraryItem).where(
            LibraryItem.library_id == library.id, LibraryItem.content_id == content_id
        )
    )
    await session.commit()
    return bool(getattr(result, "rowcount", 0))


async def reorder(session: AsyncSession, library: Library, content_ids: list[int]) -> None:
    """Enregistre l'ordre manuel (passe aussi la bibliothèque en tri manuel)."""
    items = {
        item.content_id: item
        for item in await session.scalars(
            select(LibraryItem).where(LibraryItem.library_id == library.id)
        )
    }
    if len(content_ids) != len(set(content_ids)) or set(content_ids) != set(items):
        raise InvalidOrderError
    for position, content_id in enumerate(content_ids):
        items[content_id].position = position
    library.sort_mode = SortMode.MANUAL
    await session.commit()
