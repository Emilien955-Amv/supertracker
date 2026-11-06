"""Formats d'échange des bibliothèques."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models import ItemSize, SortMode, TrackingStatus, ViewMode, Wood
from app.providers.base import ContentKind, Source
from app.schemas.tracking import ContentRead

LibraryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
# Couleur au format « #7c5cff », toujours enregistrée en minuscules.
Color = Annotated[
    str,
    StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$"),
    AfterValidator(str.lower),
]


class LibraryCreate(BaseModel):
    name: LibraryName
    color: Color = "#7c5cff"
    view_mode: ViewMode = ViewMode.BOOKCASE
    sort_mode: SortMode = SortMode.MANUAL


class LibraryUpdate(BaseModel):
    """Modification partielle : seuls les champs envoyés changent."""

    name: LibraryName | None = None
    color: Color | None = None
    view_mode: ViewMode | None = None
    sort_mode: SortMode | None = None
    wood: Wood | None = None
    wall: Color | None = None
    item_size: ItemSize | None = None


class LibraryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    view_mode: ViewMode
    sort_mode: SortMode
    wood: Wood
    wall: str
    item_size: ItemSize
    created_at: datetime
    items_count: int = 0
    preview: list[str | None] = []
    contains: bool | None = Field(None, description="Présence du contenu demandé (si demandé)")


class LibraryItemRead(BaseModel):
    content: ContentRead
    shelf_id: int | None
    position: int
    added_at: datetime
    tracking_status: TrackingStatus | None


class ShelfRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None
    position: int


class ShelfWrite(BaseModel):
    # Plaque de l'étagère : vide ou absente = pas de plaque.
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None = None


class ShelfLayout(BaseModel):
    id: int
    content_ids: list[int] = Field(max_length=1000)


class LayoutWrite(BaseModel):
    """Rangement complet : étagères de haut en bas, objets de gauche à droite."""

    shelves: list[ShelfLayout] = Field(min_length=1, max_length=30)


class LibraryDetail(LibraryRead):
    shelves: list[ShelfRead]
    items: list[LibraryItemRead]


class LibraryItemAdd(BaseModel):
    source: Source
    kind: ContentKind
    external_id: str = Field(pattern=r"^\d{1,12}$")


class LibraryOrder(BaseModel):
    content_ids: list[int] = Field(max_length=1000)
