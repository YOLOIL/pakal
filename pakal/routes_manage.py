"""Admin-only portal actions: add an installer straight into an application's folder on the share."""

from __future__ import annotations

import logging
import os
import re
import secrets
import unicodedata
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

from . import config
from .scanner import installer_extension
from .security import CSRF_HEADER, client_ip, portal_admin
from .store import store

log = logging.getLogger("pakal.manage")
router = APIRouter(prefix="/api/manage", tags=["manage"])

NO_STORE = {"Cache-Control": "no-store"}
_MB = 1024 * 1024
PART_SUFFIX = ".pakal-part"
_BAD_NAME_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*\u200b-\u200f\u202a-\u202e\u2066-\u2069]')
_VERSION_DIR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,63}$")
_WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com\d|lpt\d)(\..*)?$", re.I)


def _clean_filename(value: str) -> str:
    name = unicodedata.normalize("NFC", value).strip().rstrip(".")
    if not name or name != Path(name).name or _BAD_NAME_CHARS.search(name) or name.startswith("."):
        raise HTTPException(status_code=422, detail="Invalid file name")
    if len(name.encode("utf-8")) > 200 or _WINDOWS_RESERVED.match(name):
        raise HTTPException(status_code=422, detail="Invalid file name")
    if not installer_extension(name):
        allowed = " ".join(config.INSTALLER_EXTENSIONS)
        raise HTTPException(status_code=422, detail=f"Only installer files can be added ({allowed})")
    return name


def _clean_subfolder(value: Optional[str]) -> str:
    value = unicodedata.normalize("NFC", (value or "").strip()).strip(".")
    if not value:
        return ""
    if not _VERSION_DIR_RE.match(value) or ".." in value or _WINDOWS_RESERVED.match(value):
        raise HTTPException(status_code=422, detail="Invalid version folder name (letters, digits, space . _ + ( ) -)")
    return value


def cleanup_partial_uploads() -> None:
    """Remove half-written uploads left in app folders by a crash or restart (one level deep)."""
    root = config.APPS_ROOT
    try:
        for app_dir in (p for p in root.iterdir() if p.is_dir()):
            for pattern in (f"*{PART_SUFFIX}", f"*/*{PART_SUFFIX}"):
                for part in app_dir.glob(pattern):
                    part.unlink(missing_ok=True)
    except OSError as exc:
        log.debug("Cannot clean partial uploads under %s: %s", root, exc)


@router.put("/apps/{app_id}/files")
async def add_app_file(
    app_id: str,
    request: Request,
    filename: str = Query(max_length=300),
    folder: Optional[str] = Query(default=None, max_length=80),
    overwrite: bool = False,
) -> JSONResponse:
    """Raw request body = the installer. Written atomically into the app's folder, then the share is rescanned."""
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing request header")
    who = portal_admin(request)
    if not who:
        raise HTTPException(status_code=403, detail="Only administrators can add files")
    app = store.raw_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    name = _clean_filename(filename)
    subfolder = _clean_subfolder(folder)

    root = config.APPS_ROOT.resolve()
    app_dir = (config.APPS_ROOT / app.folder).resolve()
    target_dir = (app_dir / subfolder).resolve() if subfolder else app_dir
    if app_dir.parent != root or not target_dir.is_relative_to(app_dir) or not app_dir.is_dir():
        raise HTTPException(status_code=404, detail="The application folder is not available on the share")
    target = target_dir / name
    if target.exists() and not overwrite:
        raise HTTPException(status_code=409, detail="A file with this name already exists in the folder")

    limit = max(1, config.ADMIN_APP_UPLOAD_MAX_MB) * _MB
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail=f"File exceeds {limit // _MB} MB")

    part = target_dir / f".{name}.{secrets.token_hex(4)}{PART_SUFFIX}"
    size = 0
    try:
        target_dir.mkdir(exist_ok=True)
        with part.open("xb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"File exceeds {limit // _MB} MB")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if not size:
            raise HTTPException(status_code=422, detail="Empty file")
        if target.exists() and not overwrite:
            raise HTTPException(status_code=409, detail="A file with this name already exists in the folder")
        os.replace(part, target)
    except ClientDisconnect:
        log.info("Upload of %s into %s cancelled by %s", name, app.folder, who)
        raise HTTPException(status_code=400, detail="Upload cancelled")
    except PermissionError:
        log.error("No write permission for %s (is the apps share mounted read-only?)", target_dir)
        raise HTTPException(status_code=507, detail="The server cannot write to the application folder "
                                                    "(the share may be mounted read-only)")
    except OSError as exc:
        log.error("Writing %s failed: %s", target, exc)
        raise HTTPException(status_code=507, detail=f"Could not save the file: {exc.strerror or exc}")
    finally:
        part.unlink(missing_ok=True)

    rel_path = target.relative_to(root).as_posix()
    started = store.request_rescan()
    log.info("Admin upload %s (%d bytes) by %s from %s; rescan %s", rel_path, size, who, client_ip(request),
             "started" if started else "queued")
    return JSONResponse({"status": "saved", "rel_path": rel_path, "size": size, "rescan": "started" if started else "queued"},
                        status_code=201, headers=NO_STORE)
