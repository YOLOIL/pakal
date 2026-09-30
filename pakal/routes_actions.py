"""Actions tab API: bulk package uploads to the local Sonatype Nexus repositories."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

from . import config, nexus, portal_ui
from .security import COOKIE_NAME, CSRF_HEADER, USER_COOKIE, client_ip, decode_token, decode_user_token

log = logging.getLogger("pakal.actions")
router = APIRouter(prefix="/api/actions", tags=["actions"])

NO_STORE = {"Cache-Control": "no-store"}
_MB = 1024 * 1024


def _uploader(request: Request) -> Optional[str]:
    """Signed-in portal user (Keycloak / LDAP) or an admin console session."""
    user = decode_user_token(request.cookies.get(USER_COOKIE))
    if user:
        return str(user["sub"])
    token = request.cookies.get(COOKIE_NAME)
    admin = decode_token(token) if token else None
    return f"admin:{admin['sub']}" if admin else None


def cleanup_temp_uploads() -> None:
    """Remove partial uploads left behind by a crash or restart."""
    try:
        for entry in config.UPLOAD_TMP_DIR.glob("upload-*.part"):
            entry.unlink(missing_ok=True)
    except OSError as exc:
        log.debug("Cannot clean %s: %s", config.UPLOAD_TMP_DIR, exc)


@router.get("/config")
def actions_config(request: Request) -> JSONResponse:
    cfg = nexus.settings()
    body = {
        "enabled": portal_ui.enabled("tab_actions"),
        "repo_override": portal_ui.enabled("upload_repo_override"),
        "authenticated": bool(_uploader(request)),
        **nexus.public_config(cfg),
    }
    return JSONResponse(body, headers=NO_STORE)


@router.put("/upload")
async def upload_package(
    request: Request,
    kind: str = Query(max_length=20),
    filename: str = Query(max_length=300),
    repository: Optional[str] = Query(default=None, max_length=100),
) -> JSONResponse:
    """Raw request body = the package file. 201 published, 409 already exists, 4xx/502 failure."""
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing request header")
    if not portal_ui.enabled("tab_actions"):
        raise HTTPException(status_code=403, detail="The package uploader is disabled by the administrator")
    who = _uploader(request)
    if not who:
        raise HTTPException(status_code=401, detail="Sign in to upload packages")
    cfg = nexus.settings()
    if not nexus.configured(cfg):
        raise HTTPException(status_code=503, detail="The Nexus connection is not configured")
    if kind not in nexus.KINDS:
        raise HTTPException(status_code=422, detail="Unknown package type")
    try:
        name = nexus.clean_filename(filename)
    except nexus.PackageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    detected = nexus.detect_kind(name)
    if not detected or not nexus.accepts(kind, name):
        raise HTTPException(status_code=422, detail="This file type cannot be uploaded to the selected repository")
    targets = nexus.repos_for(cfg, kind)
    target = repository or (targets[0] if targets else "")
    if not target or target not in targets:
        raise HTTPException(status_code=422, detail="The selected repository is not configured for this package type")
    if (kind != detected or target != targets[0]) and not portal_ui.enabled("upload_repo_override"):
        raise HTTPException(status_code=403, detail="Choosing a different repository is disabled by the administrator")

    limit = int(cfg.get("max_upload_mb") or 1) * _MB
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail=f"File exceeds {limit // _MB} MB")

    config.UPLOAD_TMP_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="upload-", suffix=".part", dir=config.UPLOAD_TMP_DIR)
    tmp = Path(tmp_name)
    try:
        size = 0
        with os.fdopen(fd, "wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"File exceeds {limit // _MB} MB")
                handle.write(chunk)
        if not size:
            raise HTTPException(status_code=422, detail="Empty file")
        result = await run_in_threadpool(nexus.publish, cfg, kind, target, tmp, name)
    except ClientDisconnect:
        log.info("Upload of %s cancelled by %s", name, who)
        raise HTTPException(status_code=400, detail="Upload cancelled")
    except nexus.PackageError as exc:
        log.info("Rejected %s from %s: %s", name, who, exc)
        raise HTTPException(status_code=422, detail=str(exc))
    finally:
        tmp.unlink(missing_ok=True)

    log.info("Nexus upload %s -> %s by %s (%s): %s %s", name, target, who, client_ip(request),
             result["status"], result.get("detail", ""))
    status_code = {"success": 201, "exists": 409}.get(result["status"], 502)
    return JSONResponse(result, status_code=status_code, headers=NO_STORE)
