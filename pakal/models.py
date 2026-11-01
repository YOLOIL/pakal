"""Pydantic response models for the public catalog API."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class AppFile(BaseModel):
    filename: str
    rel_path: str
    download_url: str
    version: Optional[str] = None
    os: str
    ext: str
    size_bytes: int
    size_human: str
    modified: str
    modified_ts: float
    bundle_size_bytes: Optional[int] = None
    bundle_size_human: Optional[str] = None
    bundle_files: Optional[int] = None
    relevance: int = 1


class Release(BaseModel):
    version: Optional[str] = None
    modified: str
    total_size_bytes: int
    total_size_human: str
    files: List[AppFile] = Field(default_factory=list)


class AppEntry(BaseModel):
    id: str
    name: str
    folder: str
    description_he: str
    description_en: str
    category: str
    tags: List[str] = Field(default_factory=list)
    icon_url: Optional[str] = None
    icon_source: Optional[str] = None
    homepage: Optional[str] = None
    featured: bool = False
    known_key: Optional[str] = None
    platforms: List[str] = Field(default_factory=list)
    latest_version: Optional[str] = None
    latest: Optional[AppFile] = None
    latest_by_os: Dict[str, AppFile] = Field(default_factory=dict)
    files: List[AppFile] = Field(default_factory=list)
    releases: List[Release] = Field(default_factory=list)
    total_size_bytes: int = 0
    total_size_human: str = "0 B"
    updated: Optional[str] = None
    updated_ts: float = 0


class Bundle(BaseModel):
    id: str
    name_he: str
    name_en: str
    description_he: str = ""
    description_en: str = ""
    icon: str = "package"
    color: str = "#6366F1"
    apps: List[str] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)
    total_size_bytes: int = 0
    total_size_human: str = "0 B"


class Platform(BaseModel):
    id: int
    name: str
    url: str
    description_he: str = ""
    description_en: str = ""
    icon: str = "globe"
    icon_url: Optional[str] = None
    color: str = "#6366F1"


class Repository(BaseModel):
    id: int
    name: str
    tech: str = "other"
    url: str = ""
    description_he: str = ""
    description_en: str = ""
    icon: str = "package"
    color: str = "#6366F1"
    sort_order: int = 0


class ActionItem(BaseModel):
    key: str
    builtin: str = ""
    kind: str = "link"
    name_he: str = ""
    name_en: str = ""
    description_he: str = ""
    description_en: str = ""
    icon: str = "sliders"
    target: str = ""
    chips: List[str] = Field(default_factory=list)
    english: bool = False
    sort_order: int = 0


class Category(BaseModel):
    id: str
    label_he: str
    label_en: str
    count: int = 0


class ScanStatus(BaseModel):
    scanning: bool = False
    source: str = "none"
    last_scan: Optional[str] = None
    last_scan_ts: Optional[float] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    root_available: bool = False
    apps: int = 0
    files: int = 0


class Catalog(BaseModel):
    apps: List[AppEntry] = Field(default_factory=list)
    bundles: List[Bundle] = Field(default_factory=list)
    platforms: List[Platform] = Field(default_factory=list)
    repositories: List[Repository] = Field(default_factory=list)
    actions: List[ActionItem] = Field(default_factory=list)
    categories: List[Category] = Field(default_factory=list)
    scan: ScanStatus = Field(default_factory=ScanStatus)


class DocPointer(BaseModel):
    """Where a guide file lives. `member` is set when the file is inside a zip."""

    filename: str
    type: str = "text"
    rel_path: str
    member: str = ""


class SoftwareDocs(BaseModel):
    files: List[DocPointer] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _legacy_pair(cls, value):
        """Older caches stored a single readme and license instead of a file list."""
        if isinstance(value, dict) and "files" not in value:
            files = [item for key in ("readme", "license") if isinstance((item := value.get(key)), dict)]
            return {"files": files}
        return value


class SoftwareDocOut(BaseModel):
    text: str = ""
    type: str = "text"
    filename: str = ""
    found: bool = False
    truncated: bool = False


class ScanResult(BaseModel):
    """Raw scanner output persisted to cache.json (admin overrides are applied on top at read time)."""

    apps: List[AppEntry] = Field(default_factory=list)
    folder_icons: Dict[str, str] = Field(default_factory=dict)
    docs: Dict[str, SoftwareDocs] = Field(default_factory=dict)
    root_available: bool = False
