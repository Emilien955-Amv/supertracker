"""Formats d'échange des bibliothèques."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.models import SortMode, TrackingStatus, ViewMode
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
    view_mode: ViewMode = ViewMode.GRID
    sort_mode: SortMode = SortMode.MANUAL


class LibraryUpdate(BaseModel):
    """Modification partielle : seuls les champs envoyés changent."""

    name: LibraryName | None = None
    color: Color | None = None
    view_mode: ViewMode | None = None
    sort_mode: SortMode | None = None


class LibraryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    view_mode: ViewMode
    sort_mode: SortMode
    created_at: datetime
    items_count: int = 0
    preview: list[str | None] = []
    contains: bool | None = Field(None, description="Présence du contenu demandé (si demandé)")


class LibraryItemRead(BaseModel):
    content: ContentRead
    position: int
    added_at: datetime
    tracking_status: TrackingStatus | None


class LibraryDetail(LibraryRead):
    items: list[LibraryItemRead]


class LibraryItemAdd(BaseModel):
    source: Source
    kind: ContentKind
    external_id: str = Field(pattern=r"^\d{1,12}$")


class LibraryOrder(BaseModel):
    content_ids: list[int] = Field(max_length=1000)
