"""Public, read-only catalog API."""

from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from . import config, portal_ui
from .models import AppEntry, Catalog, ScanStatus
from .scanner import installer_extension
from .store import store

log = logging.getLogger("pakal.api")
router = APIRouter(prefix="/api", tags=["catalog"])

NO_STORE = {"Cache-Control": "no-store"}


@router.get("/apps", response_model=Catalog)
def get_catalog() -> Response:
    store.first_scan_done.wait(timeout=config.INITIAL_SCAN_WAIT_SECONDS)
    return Response(store.public_json(), media_type="application/json", headers=NO_STORE)


@router.get("/apps/{app_id}", response_model=AppEntry)
def get_app(app_id: str) -> JSONResponse:
    for entry in store.public_catalog().apps:
        if entry.id == app_id:
            return JSONResponse(entry.model_dump(mode="json"), headers=NO_STORE)
    raise HTTPException(status_code=404, detail="Application not found")


@router.get("/status", response_model=ScanStatus)
def get_status() -> JSONResponse:
    return JSONResponse(store.status.model_dump(mode="json"), headers=NO_STORE)


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/ui")
def get_ui() -> JSONResponse:
    """Which portal tabs, buttons and actions the admins chose to show, and the active announcement."""
    return JSONResponse({"visibility": portal_ui.load(), "announcement": portal_ui.public_announcement()},
                        headers=NO_STORE)


@router.get("/icon/{app_id}")
def get_folder_icon(app_id: str) -> FileResponse:
    path = store.folder_icon(app_id)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="No icon for this application")
    return FileResponse(path, headers={
        "Cache-Control": "public, max-age=86400",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    })


@router.get("/download/{file_path:path}")
def download(file_path: str) -> FileResponse:
    root = config.APPS_ROOT.resolve()
    try:
        target = (root / file_path).resolve(strict=True)
    except (OSError, RuntimeError):
        raise HTTPException(status_code=404, detail="File not found")
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    rel_path = target.relative_to(root).as_posix()
    if not store.is_downloadable(rel_path):
        raise HTTPException(status_code=404, detail="File not found")

    log.info("Download: %s", rel_path)
    return FileResponse(
        target,
        filename=target.name,
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store"},
    )


# --------------------------------------------------------------------------- #
# Role bundle as a single streamed ZIP
# --------------------------------------------------------------------------- #

_ZIP_CHUNK = 1024 * 1024
_UNSAFE_ARC_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


class _ChunkSink(io.RawIOBase):
    """Non-seekable sink: zipfile writes into it, the response generator drains it."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[bytes] = []

    def writable(self) -> bool:
        return True

    def write(self, data) -> int:  # type: ignore[override]
        self._chunks.append(bytes(data))
        return len(data)

    def drain(self) -> bytes:
        data = b"".join(self._chunks)
        self._chunks.clear()
        return data


def _stream_zip(entries: List[Tuple[str, Path]]) -> Iterator[bytes]:
    # Installers are already compressed: STORED keeps CPU flat, ZIP64 allows multi-GB ISOs.
    sink = _ChunkSink()
    with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_STORED, allowZip64=True,
                         strict_timestamps=False) as archive:
        for arcname, path in entries:
            try:
                source = path.open("rb")
            except OSError as exc:
                log.warning("Bundle zip: skipping %s: %s", path, exc)
                continue
            with source:
                info = zipfile.ZipInfo.from_file(path, arcname, strict_timestamps=False)
                info.compress_type = zipfile.ZIP_STORED
                with archive.open(info, "w", force_zip64=True) as target:
                    while chunk := source.read(_ZIP_CHUNK):
                        target.write(chunk)
                        yield sink.drain()
            yield sink.drain()
    yield sink.drain()


def _flat_arcname(filename: str, used: set) -> str:
    """Root-level entry name; a clashing filename gets a ' (2)' style suffix instead of overwriting."""
    name = _UNSAFE_ARC_CHARS.sub("_", filename).strip(" .") or "installer"
    ext = installer_extension(name) or (name[-7:] if name.lower().endswith(".tar.gz") else Path(name).suffix)
    stem = name[: len(name) - len(ext)] if ext else name
    candidate, counter = name, 2
    while candidate.lower() in used:
        candidate = f"{stem} ({counter}){ext}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def _zip_name(name_en: str, bundle_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name_en).strip("_") or re.sub(r"[^A-Za-z0-9]+", "_", bundle_id)
    return f"PAKAL_{slug}_Kit.zip"


@router.get("/bundles/{bundle_id}/download-zip")
def download_bundle_zip(bundle_id: str, platform: str = Query("Windows", alias="os", max_length=16)
                        ) -> StreamingResponse:
    if not portal_ui.enabled("btn_bundle_zip"):
        raise HTTPException(status_code=403, detail="Bundle downloads are disabled by the administrator")
    catalog = store.public_catalog()
    bundle = next((b for b in catalog.bundles if b.id == bundle_id), None)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Bundle not found")
    apps = {a.id: a for a in catalog.apps}
    root = config.APPS_ROOT.resolve()
    entries: List[Tuple[str, Path]] = []
    used: set = set()
    for app_id in bundle.apps:
        app = apps.get(app_id)
        file = app and (app.latest_by_os.get(platform) or app.latest)
        if not file or not store.is_downloadable(file.rel_path):
            continue
        try:
            target = (root / file.rel_path).resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if not target.is_relative_to(root) or not target.is_file():
            continue
        if target in {path for _, path in entries}:
            continue
        entries.append((_flat_arcname(file.filename, used), target))
    if not entries:
        raise HTTPException(status_code=404, detail="Bundle has no downloadable installers")

    filename = _zip_name(bundle.name_en, bundle.id)
    log.info("Bundle zip: %s (%d files)", filename, len(entries))
    return StreamingResponse(
        _stream_zip(entries),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
