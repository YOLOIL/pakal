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

from . import config, portal_ui, powershell_setup
from .models import AppEntry, Catalog, ScanStatus, SoftwareDocOut
from .scanner import installer_extension
from .software_docs import read_doc_text
from .store import store

log = logging.getLogger("pakal.api")
router = APIRouter(prefix="/api", tags=["catalog"])

NO_STORE = {"Cache-Control": "no-store"}


@router.get("/tools/setup-nuget.cmd")
def setup_nuget_cmd() -> Response:
    """Download Install-PAKAL-NuGet.cmd. The file runs PowerShell 7 without a typed command."""
    if not portal_ui.enabled("tab_actions"):
        raise HTTPException(status_code=403, detail="The actions hub is disabled by the administrator")
    body = powershell_setup.build_cmd_file()
    if not body:
        raise HTTPException(status_code=503, detail="NuGet setup is not configured")
    return Response(
        content=body,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{powershell_setup.CMD_FILENAME}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/tools/setup-nuget.ps1")
def setup_nuget_ps1() -> Response:
    """Download the filled PowerShell 7 bootstrap. ``Register-PSRepository`` has no ``-Scope``."""
    if not portal_ui.enabled("tab_actions"):
        raise HTTPException(status_code=403, detail="The actions hub is disabled by the administrator")
    body = powershell_setup.build_ps1_file()
    if not body:
        raise HTTPException(status_code=503, detail="NuGet setup is not configured")
    return Response(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{powershell_setup.PS1_FILENAME}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/apps", response_model=Catalog)
def get_catalog() -> Response:
    store.first_scan_done.wait(timeout=config.INITIAL_SCAN_WAIT_SECONDS)
    return Response(store.public_json(), media_type="application/json", headers=NO_STORE)


def _require_app(item_id: str):
    app = next((entry for entry in store.public_catalog().apps if entry.id == item_id), None)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def _doc_payload(pointer) -> Optional[dict]:
    loaded = read_doc_text(pointer, config.APPS_ROOT)
    if loaded is None:
        return None
    text, truncated = loaded
    return {
        "filename": pointer.filename,
        "content": text,
        "type": pointer.type if pointer.type in ("markdown", "text") else "text",
        "truncated": truncated,
    }


@router.get("/software/{item_id}/docs")
def software_docs(item_id: str) -> JSONResponse:
    """Every detected guide: [{ filename, content, type }]."""
    _require_app(item_id)
    files = [payload for pointer in store.software_docs(item_id) if (payload := _doc_payload(pointer))]
    return JSONResponse(files, headers=NO_STORE)


def _software_doc_response(item_id: str, kind: str) -> JSONResponse:
    _require_app(item_id)
    prefixes = ("readme",) if kind == "readme" else ("license", "licence", "copying")
    payload = SoftwareDocOut()
    for pointer in store.software_docs(item_id):
        if not pointer.filename.lower().startswith(prefixes):
            continue
        loaded = read_doc_text(pointer, config.APPS_ROOT)
        if loaded is None:
            continue
        text, truncated = loaded
        payload = SoftwareDocOut(
            text=text,
            type=pointer.type if pointer.type in ("markdown", "text") else "text",
            filename=pointer.filename,
            found=True,
            truncated=truncated,
        )
        break
    return JSONResponse(payload.model_dump(), headers=NO_STORE)


@router.get("/software/{item_id}/readme", response_model=SoftwareDocOut)
def software_readme(item_id: str) -> JSONResponse:
    return _software_doc_response(item_id, "readme")


@router.get("/software/{item_id}/license", response_model=SoftwareDocOut)
def software_license(item_id: str) -> JSONResponse:
    return _software_doc_response(item_id, "license")


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


def _stream_zip(entries: List[Tuple[str, Path]], extras: List[Tuple[str, bytes]] | None = None) -> Iterator[bytes]:
    # Installers are already compressed: STORED keeps CPU flat, ZIP64 allows multi-GB ISOs.
    # README and LICENSE are small text, so they are deflated.
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
        for arcname, payload in extras or []:
            info = zipfile.ZipInfo(filename=arcname, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with archive.open(info, "w") as target:
                target.write(payload)
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


def _doc_arcname(folder: str, filename: str, used: set) -> str:
    safe_folder = _UNSAFE_ARC_CHARS.sub("_", folder).strip(" .") or "app"
    name = _UNSAFE_ARC_CHARS.sub("_", Path(filename).name).strip(" .") or "README"
    candidate, counter = f"{safe_folder}/{name}", 2
    while candidate.lower() in used:
        stem = Path(name).stem
        suffix = Path(name).suffix
        candidate = f"{safe_folder}/{stem} ({counter}){suffix}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def _bundle_doc_entries(app, root: Path, used: set) -> List[Tuple[str, bytes]]:
    extras: List[Tuple[str, bytes]] = []
    for pointer in store.software_docs(app.id):
        loaded = read_doc_text(pointer, root)
        if loaded is None or not loaded[0].strip():
            continue
        extras.append((_doc_arcname(app.folder, pointer.filename, used), loaded[0].encode("utf-8")))
    return extras


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
    extras: List[Tuple[str, bytes]] = []
    used: set = set()
    documented: set = set()
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
        if app_id not in documented:
            documented.add(app_id)
            extras.extend(_bundle_doc_entries(app, root, used))
    if not entries:
        raise HTTPException(status_code=404, detail="Bundle has no downloadable installers")

    filename = _zip_name(bundle.name_en, bundle.id)
    log.info("Bundle zip: %s (%d files, %d docs)", filename, len(entries), len(extras))
    return StreamingResponse(
        _stream_zip(entries, extras),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
