from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class FileType(str, Enum):
    STL = "stl"
    THREE_MF = "3mf"
    GCODE = "gcode"
    OBJ = "obj"


class PrinterStatus(str, Enum):
    UNKNOWN = "unknown"
    OFFLINE = "offline"
    READY = "ready"
    PRINTING = "printing"
    PAUSED = "paused"
    ERROR = "error"


class PrintJobState(str, Enum):
    QUEUED = "queued"
    UPLOADING = "uploading"
    STARTED = "started"
    PRINTING = "printing"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


def _utcnow() -> datetime:
    return datetime.utcnow()


class Metadata(SQLModel, table=True):
    """Slicer-derived facts. 1:1 with File."""

    __tablename__ = "metadata"

    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: int = Field(foreign_key="files.id", unique=True, index=True)

    # Slicer
    slicer_name: Optional[str] = Field(default=None, max_length=64)
    slicer_version: Optional[str] = Field(default=None, max_length=32)
    printer_model: Optional[str] = Field(default=None, max_length=128)
    nozzle_diameter_mm: Optional[float] = None
    layer_height_mm: Optional[float] = None
    infill_percent: Optional[float] = None

    # Print stats
    estimated_time_s: Optional[int] = None
    filament_weight_g: Optional[float] = None
    filament_length_mm: Optional[float] = None
    filament_cost: Optional[float] = None
    material_type: Optional[str] = Field(default=None, max_length=64)
    material_brand: Optional[str] = Field(default=None, max_length=128)

    # Geometry (filled later by Trimesh; left None in Stage 1 for STL/3MF)
    bbox_x_mm: Optional[float] = None
    bbox_y_mm: Optional[float] = None
    bbox_z_mm: Optional[float] = None
    volume_mm3: Optional[float] = None
    triangle_count: Optional[int] = None

    created_at: datetime = Field(default_factory=_utcnow)

    file: Optional["File"] = Relationship(back_populates="file_metadata")


class File(SQLModel, table=True):
    """Physical artifact stored on disk; many-to-one with Model."""

    __tablename__ = "files"

    id: Optional[int] = Field(default=None, primary_key=True)
    model_id: int = Field(foreign_key="models.id", index=True)

    path: str = Field(max_length=1024)
    original_filename: str = Field(max_length=512)
    file_type: FileType = Field(index=True)
    version: int = Field(default=1)
    size_bytes: int
    sha256: str = Field(index=True, max_length=64)

    uploaded_at: datetime = Field(default_factory=_utcnow)

    model: Optional["Model"] = Relationship(back_populates="files")
    file_metadata: Optional[Metadata] = Relationship(
        back_populates="file",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )


# ---------------------------------------------------------------------------
# Categories (hierarchical) & Tags (flat, many-to-many)
# ---------------------------------------------------------------------------

class Category(SQLModel, table=True):
    """Hierarchical category. Self-referential via parent_id.

    `path` is the materialised slash-joined slug chain ("functional/brackets"),
    used for fast filtering and stable URLs.
    """

    __tablename__ = "categories"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=128)
    slug: str = Field(max_length=128, index=True)
    parent_id: Optional[int] = Field(default=None, foreign_key="categories.id", index=True)
    path: str = Field(max_length=512, unique=True, index=True)

    created_at: datetime = Field(default_factory=_utcnow)


class Tag(SQLModel, table=True):
    __tablename__ = "tags"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=64, unique=True, index=True)
    slug: str = Field(max_length=64, unique=True, index=True)
    created_at: datetime = Field(default_factory=_utcnow)


class ModelTagLink(SQLModel, table=True):
    """Association table for Model <-> Tag."""

    __tablename__ = "model_tags"

    model_id: Optional[int] = Field(default=None, foreign_key="models.id", primary_key=True)
    tag_id: Optional[int] = Field(default=None, foreign_key="tags.id", primary_key=True)


class Model(SQLModel, table=True):
    """Logical asset, deduplicated by `hash` (source mesh sha256, gcode fallback)."""

    __tablename__ = "models"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=255)
    slug: str = Field(index=True, unique=True, max_length=255)
    hash: str = Field(index=True, unique=True, max_length=64)

    # Legacy free-form category string — retained for backwards compat & the
    # OrcaSlicer push --category flag. New code should use category_id.
    category: Optional[str] = Field(default=None, index=True, max_length=128)
    category_id: Optional[int] = Field(default=None, foreign_key="categories.id", index=True)

    description: Optional[str] = None
    tags_csv: Optional[str] = Field(default=None, max_length=512)  # legacy
    thumbnail_path: Optional[str] = Field(default=None, max_length=512)
    thumbnail_file_id: Optional[int] = Field(default=None, foreign_key="files.id")

    deleted_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    files: List[File] = Relationship(
        back_populates="model",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "File.model_id",
        },
    )
    tags: List[Tag] = Relationship(
        link_model=ModelTagLink,
        sa_relationship_kwargs={"lazy": "selectin"},
    )


# ---------------------------------------------------------------------------
# Printers & Print Jobs (Stage 3 — Klipper / Moonraker integration)
# ---------------------------------------------------------------------------

class Printer(SQLModel, table=True):
    __tablename__ = "printers"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=128)
    # Base URL of Moonraker, e.g. "http://mainsailos.local" or "http://10.0.0.42:7125".
    moonraker_url: str = Field(max_length=512)
    api_key: Optional[str] = Field(default=None, max_length=128)
    notes: Optional[str] = None

    # Cached liveness info (refreshed by the live-state worker).
    status: PrinterStatus = Field(default=PrinterStatus.UNKNOWN, index=True)
    last_seen_at: Optional[datetime] = None
    last_error: Optional[str] = Field(default=None, max_length=512)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class PrintJob(SQLModel, table=True):
    __tablename__ = "print_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    printer_id: int = Field(foreign_key="printers.id", index=True)
    file_id: int = Field(foreign_key="files.id", index=True)
    model_id: int = Field(foreign_key="models.id", index=True)

    remote_filename: str = Field(max_length=512)  # filename as uploaded to Moonraker
    state: PrintJobState = Field(default=PrintJobState.QUEUED, index=True)
    progress: float = Field(default=0.0)  # 0.0–1.0
    error: Optional[str] = Field(default=None, max_length=1024)

    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
