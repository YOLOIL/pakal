"""Admin-only portal actions: add an installer straight into an application's folder on the share."""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import shutil
import unicodedata
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

from . import config
from .db import get_setting, set_setting
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
_STATUS_KEY = re.compile(r"^(app|tool):[A-Za-z0-9._~-]{1,120}$")
_STATUSES = {"active", "construction", "soon"}
_NOTES_KEY = "installer_notes"
_STATUS_STORE = "card_status"
_ACTION_TOOLS = {"nexus", "docker", "powershell"}
_VISIBILITY_STORE = "action_visibility"


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


def _json_map(key: str) -> dict:
    raw = get_setting(key) or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_map(key: str, data: dict) -> None:
    set_setting(key, json.dumps(data, ensure_ascii=False))


def _clean_notes(value: Optional[str]) -> str:
    text = unicodedata.normalize("NFC", value or "").replace("\x00", "").strip()
    return text[:2000]


def _require_admin(request: Request) -> str:
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing request header")
    who = portal_admin(request)
    if not who:
        raise HTTPException(status_code=403, detail="Only administrators can add files")
    return who


@router.get("/presentation")
def presentation() -> JSONResponse:
    """Public card availability, hidden actions and installer release notes."""
    hidden = sorted(k for k, v in _json_map(_VISIBILITY_STORE).items() if k in _ACTION_TOOLS and v == "hidden")
    return JSONResponse({
        "status": _json_map(_STATUS_STORE), "notes": _json_map(_NOTES_KEY), "hidden_actions": hidden,
    }, headers=NO_STORE)


@router.put("/action-visibility")
async def set_action_visibility(request: Request) -> JSONResponse:
    who = _require_admin(request)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="Expected a JSON body")
    tool = str((body or {}).get("tool") or "")
    visibility = str((body or {}).get("visibility") or "")
    if tool not in _ACTION_TOOLS or visibility not in {"active", "hidden"}:
        raise HTTPException(status_code=422, detail="Unknown action or visibility")
    data = _json_map(_VISIBILITY_STORE)
    if visibility == "active":
        data.pop(tool, None)
    else:
        data[tool] = "hidden"
    _save_map(_VISIBILITY_STORE, data)
    log.info("Action visibility %s=%s by %s", tool, visibility, who)
    return JSONResponse({"tool": tool, "visibility": visibility}, headers=NO_STORE)


@router.put("/card-status")
async def set_card_status(request: Request) -> JSONResponse:
    who = _require_admin(request)
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="Expected a JSON body")
    key = str((body or {}).get("key") or "")
    status = str((body or {}).get("status") or "")
    if not _STATUS_KEY.match(key) or status not in _STATUSES:
        raise HTTPException(status_code=422, detail="Unknown card or status")
    data = _json_map(_STATUS_STORE)
    if status == "active":
        data.pop(key, None)
    else:
        data[key] = status
    _save_map(_STATUS_STORE, data)
    log.info("Card status %s=%s by %s", key, status, who)
    return JSONResponse({"key": key, "status": status}, headers=NO_STORE)


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


def _storage_error(path: Path, exc: BaseException, op: str) -> HTTPException:
    """Log the failing operation, path and OS error; answer with a message an admin can act on."""
    log.error("Storage error while %s at %s: %r", op, path, exc, exc_info=exc)
    if isinstance(exc, OSError):
        reason = f"{exc.strerror or exc} (errno {exc.errno})"
    else:
        reason = str(exc) or type(exc).__name__
    return HTTPException(status_code=500, detail=f"Storage error while {op}: {reason} [{path}]")


def _publish(part: Path, target: Path, overwrite: bool) -> None:
    """Move the finished temp file into place; copy instead if the share refuses the rename."""
    try:
        os.replace(part, target)
        return
    except OSError as exc:  # CIFS/NetApp can answer EACCES/EBUSY/EXDEV to a rename over an existing file
        log.warning("Atomic rename %s -> %s failed (%r); falling back to copy", part, target, exc)
    try:
        with part.open("rb") as src, target.open("wb" if overwrite else "xb") as dst:
            shutil.copyfileobj(src, dst, length=_MB)
            dst.flush()
    except FileExistsError:
        raise HTTPException(status_code=409, detail="A file with this name already exists in the folder")
    except BaseException:
        target.unlink(missing_ok=True)  # never leave a truncated installer behind
        raise


async def _store_installer(app, request: Request, name: str, subfolder: str, overwrite: bool,
                           chunks: AsyncIterator[bytes], who: str, notes: str, status_code: int) -> JSONResponse:
    # Shares (CIFS/NFS mounts or \\server\share UNC roots) can fail on a plain stat with EACCES or a
    # stale handle, and Python 3.11 lets those escape exists()/is_dir(), so every filesystem touch is guarded.
    op = "resolving the application folder"
    try:
        root = Path(config.APPS_ROOT).resolve()
        app_dir = (root / app.folder).resolve()
        target_dir = (app_dir / subfolder).resolve() if subfolder else app_dir
        log.debug("Upload paths: root=%s app.folder=%r app_dir=%s target_dir=%s", root, app.folder, app_dir, target_dir)
        # app.folder may be nested ("microsoft/visual studio"); require it under root and block traversal.
        inside = app_dir != root and app_dir.is_relative_to(root) and target_dir.is_relative_to(app_dir)
        if not inside or not app_dir.is_dir():
            raise HTTPException(status_code=404, detail="The application folder is not available on the share")
        op = "creating the version folder"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / name
        op = "checking for an existing file"
        if target.exists() and not overwrite:
            raise HTTPException(status_code=409, detail="A file with this name already exists in the folder")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _storage_error(Path(config.APPS_ROOT) / app.folder / subfolder, exc, op) from exc

    limit = max(1, config.ADMIN_APP_UPLOAD_MAX_MB) * _MB
    part = target_dir / f".{name}.{secrets.token_hex(4)}{PART_SUFFIX}"
    size = 0
    op, where = "creating the temporary file", part
    try:
        with part.open("wb") as handle:  # random temp name, so O_EXCL ("xb") adds nothing here
            op = "writing the upload"
            async for chunk in chunks:
                if not chunk:
                    continue
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"File exceeds {limit // _MB} MB")
                handle.write(chunk)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError as exc:  # some SMB/CIFS mounts reject fsync; the close below still flushes
                log.debug("fsync not supported for %s: %s", part, exc)
        if not size:
            raise HTTPException(status_code=400, detail="Missing required version data (the file is empty)")
        op, where = "publishing the installer (rename/copy)", target
        if target.exists() and not overwrite:
            raise HTTPException(status_code=409, detail="A file with this name already exists in the folder")
        _publish(part, target, overwrite)
    except HTTPException:
        raise
    except ClientDisconnect:
        log.info("Upload of %s into %s cancelled by %s", name, app.folder, who)
        raise HTTPException(status_code=400, detail="Upload cancelled")
    except Exception as exc:  # noqa: BLE001
        raise _storage_error(where, exc, op) from exc
    finally:
        try:
            part.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Could not remove the partial upload %s: %s", part, exc)

    # The installer is on the share now; bookkeeping failures below must not turn the save into an error.
    rel_path = target.relative_to(root).as_posix()
    notes_saved = True
    if notes:
        try:
            stored = _json_map(_NOTES_KEY)
            stored[rel_path] = notes
            _save_map(_NOTES_KEY, stored)
        except Exception:  # noqa: BLE001
            notes_saved = False
            log.exception("Saved %s but storing its release notes failed", rel_path)
    try:
        rescan = "started" if store.request_rescan() else "queued"
    except Exception:  # noqa: BLE001
        rescan = "failed"
        log.exception("Saved %s but the catalog rescan could not be scheduled", rel_path)
    log.info("Admin upload %s (%d bytes) by %s from %s; rescan %s", rel_path, size, who, client_ip(request), rescan)
    return JSONResponse({
        "status": "saved", "rel_path": rel_path, "size": size, "notes": notes if notes_saved else "",
        "notes_saved": notes_saved, "rescan": rescan,
    }, status_code=status_code, headers=NO_STORE)


@router.put("/apps/{app_id}/files")
async def add_app_file(
    app_id: str,
    request: Request,
    filename: str = Query(max_length=300),
    folder: Optional[str] = Query(default=None, max_length=80),
    overwrite: bool = False,
) -> JSONResponse:
    """Raw request body = the installer. Written atomically into the app's folder, then the share is rescanned."""
    who = _require_admin(request)
    app = store.raw_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    limit = max(1, config.ADMIN_APP_UPLOAD_MAX_MB) * _MB
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail=f"File exceeds {limit // _MB} MB")
    return await _store_installer(
        app, request, _clean_filename(filename), _clean_subfolder(folder), overwrite, request.stream(), who, "", 201,
    )


@router.post("/apps/{app_id}/installers")
async def upload_installer(
    app_id: str,
    request: Request,
    file: Optional[UploadFile] = File(default=None),
    folder: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    overwrite: str = Form(default="false"),
) -> JSONResponse:
    """multipart/form-data upload: file, optional version folder, optional release notes."""
    who = _require_admin(request)
    if file is None or not (file.filename or "").strip():
        raise HTTPException(status_code=400, detail="Missing required version data")
    app = store.raw_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    name = _clean_filename(file.filename)
    replace = str(overwrite).lower() in {"1", "true", "yes", "on"}

    async def chunks() -> AsyncIterator[bytes]:
        while True:
            block = await file.read(_MB)
            if not block:
                break
            yield block

    return await _store_installer(
        app, request, name, _clean_subfolder(folder), replace, chunks(), who, _clean_notes(notes), 200,
    )