"""Pydantic response models for the public catalog API."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


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
    categories: List[Category] = Field(default_factory=list)
    scan: ScanStatus = Field(default_factory=ScanStatus)


class ScanResult(BaseModel):
    """Raw scanner output persisted to cache.json (admin overrides are applied on top at read time)."""

    apps: List[AppEntry] = Field(default_factory=list)
    folder_icons: Dict[str, str] = Field(default_factory=dict)
    root_available: bool = False
