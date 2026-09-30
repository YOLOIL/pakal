"""Docker API: Nexus registry browser (Docker tab) and ZIP-to-image builds (Actions → Docker Image Builder)."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import threading
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.requests import ClientDisconnect

from . import docker_build, docker_registry, portal_ui
from .routes_actions import _uploader
from .security import CSRF_HEADER, client_ip, portal_admin

log = logging.getLogger("pakal.docker.api")
router = APIRouter(prefix="/api/docker", tags=["docker"])

NO_STORE = {"Cache-Control": "no-store"}
_MB = 1024 * 1024
_KEEPALIVE_SECONDS = 15


def _build_access(request: Request, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Whether this visitor may build, and why not."""
    if not portal_ui.enabled("docker_build") or not cfg.get("build_enabled"):
        return {"allowed": False, "reason": "disabled"}
    if not docker_registry.configured(cfg):
        return {"allowed": False, "reason": "not_configured"}
    who = _uploader(request)
    if not who:
        return {"allowed": False, "reason": "sign_in"}
    if cfg.get("build_admin_only") and not portal_admin(request):
        return {"allowed": False, "reason": "admin_only"}
    return {"allowed": True, "reason": None, "who": who}


def _require_catalog(cfg: Dict[str, Any]) -> None:
    if not portal_ui.enabled("tab_docker"):
        raise HTTPException(status_code=403, detail="The Docker catalog is disabled by the administrator")
    if not docker_registry.configured(cfg):
        raise HTTPException(status_code=503, detail="The Docker registry is not configured")


@router.get("/config")
def docker_config(request: Request) -> JSONResponse:
    cfg = docker_registry.settings()
    access = _build_access(request, cfg)
    access.pop("who", None)
    engine = docker_build.engine_status() if access["allowed"] else None
    return JSONResponse({
        "catalog": portal_ui.enabled("tab_docker") and docker_registry.configured(cfg),
        "configured": docker_registry.configured(cfg),
        "registry": docker_registry.registry_host(cfg),
        "namespace": cfg.get("namespace") or "",
        "build": {**access, "max_context_mb": int(cfg.get("max_context_mb") or 0),
                  "engine": engine, "visible": portal_ui.enabled("docker_build")},
    }, headers=NO_STORE)


@router.get("/images")
async def list_images(fresh: bool = False) -> JSONResponse:
    cfg = docker_registry.settings()
    _require_catalog(cfg)
    try:
        body = await run_in_threadpool(docker_registry.catalog, cfg, fresh)
    except docker_registry.RegistryError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return JSONResponse({**body, "registry": docker_registry.registry_host(cfg)}, headers=NO_STORE)


@router.get("/image")
async def image_details(name: str = Query(max_length=255), tag: Optional[str] = Query(default=None, max_length=128)
                        ) -> JSONResponse:
    cfg = docker_registry.settings()
    _require_catalog(cfg)
    if not docker_registry.valid_repo(name) or (tag and not docker_registry.valid_tag(tag)):
        raise HTTPException(status_code=422, detail="Invalid image name or tag")
    try:
        tags = await run_in_threadpool(docker_registry.tags, cfg, name)
        if not tags:
            raise HTTPException(status_code=404, detail="This image has no tags")
        selected = tag if tag in tags else tags[0]
        info = await run_in_threadpool(docker_registry.details, cfg, name, selected)
    except docker_registry.RegistryError as exc:
        raise HTTPException(status_code=404 if exc.status == 404 else 502, detail=str(exc))
    readme = await run_in_threadpool(docker_registry.readme, name)
    return JSONResponse({**info, "tags": tags, "registry": docker_registry.registry_host(cfg), "readme": readme},
                        headers=NO_STORE)


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _event_stream(job: docker_build.BuildJob) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    events: "asyncio.Queue[Optional[Dict[str, Any]]]" = asyncio.Queue()

    def pump() -> None:
        while True:
            item = job.events.get()
            try:
                loop.call_soon_threadsafe(events.put_nowait, item)
            except RuntimeError:
                return  # the event loop is gone; the job was cancelled with the request
            if item is None:
                return

    threading.Thread(target=pump, name="docker-build-events", daemon=True).start()
    finished = False
    try:
        yield ": build stream\n\n"
        while True:
            try:
                item = await asyncio.wait_for(events.get(), _KEEPALIVE_SECONDS)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if item is None:
                finished = True
                return
            kind = item.pop("event")
            yield _sse(kind, item)
    finally:
        if not finished:
            log.info("Docker build %s: client disconnected, cancelling", job.reference)
            job.cancel()


@router.post("/build-and-push")
async def build_and_push(
    request: Request,
    image: str = Query(max_length=128),
    tag: str = Query(default="latest", max_length=128),
    dockerfile: str = Query(default="Dockerfile", max_length=200),
) -> StreamingResponse:
    """Raw request body = the project ZIP. Answers with text/event-stream build and push progress."""
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing request header")
    cfg = docker_registry.settings()
    access = _build_access(request, cfg)
    if not access["allowed"]:
        status, detail = {
            "disabled": (403, "Image builds are disabled by the administrator"),
            "not_configured": (503, "The Docker registry is not configured"),
            "sign_in": (401, "Sign in to build images"),
            "admin_only": (403, "Only administrators may build images"),
        }[access["reason"]]
        raise HTTPException(status_code=status, detail=detail)
    image = image.strip().lower()
    tag = tag.strip()
    if not docker_build.IMAGE_NAME_RE.match(image):
        raise HTTPException(status_code=422, detail="Invalid image name (lowercase letters, digits, . _ - and /)")
    if not docker_registry.valid_tag(tag):
        raise HTTPException(status_code=422, detail="Invalid tag (letters, digits, . _ -; up to 128 characters)")
    dockerfile_rel = docker_build.safe_member(dockerfile.strip())
    if dockerfile_rel is None:
        raise HTTPException(status_code=422, detail="Invalid Dockerfile path")
    engine = await run_in_threadpool(docker_build.engine_status)
    if not engine["available"]:
        raise HTTPException(status_code=503, detail=engine["error"])

    limit = int(cfg.get("max_context_mb") or 1) * _MB
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail=f"The ZIP exceeds {limit // _MB} MB")
    if not docker_build.acquire_slot():
        raise HTTPException(status_code=429, detail="Too many builds are running - try again in a few minutes",
                            headers={"Retry-After": "60"})
    workdir = docker_build.new_workdir()
    archive = workdir / "upload.zip"
    started = False
    try:
        size = 0
        head = b""
        with archive.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(status_code=413, detail=f"The ZIP exceeds {limit // _MB} MB")
                if len(head) < 4:
                    head += chunk[:4]
                handle.write(chunk)
        if not size:
            raise HTTPException(status_code=422, detail="Empty file")
        if not head.startswith(b"PK"):
            raise HTTPException(status_code=422, detail="The file is not a ZIP archive")
        repository = docker_registry.repository_path(cfg, image)
        job = docker_build.BuildJob(cfg, archive, workdir, repository, tag, dockerfile_rel.as_posix(), access["who"])
        log.info("Docker build %s requested by %s (%s), %d bytes", job.reference, access["who"], client_ip(request), size)
        # From here the job owns the slot and the work directory and always releases both.
        threading.Thread(target=job.run, name=f"docker-build-{repository}", daemon=True).start()
        started = True
    except ClientDisconnect:
        raise HTTPException(status_code=400, detail="Upload cancelled")
    finally:
        if not started:
            shutil.rmtree(workdir, ignore_errors=True)
            docker_build.release_slot()
    return StreamingResponse(_event_stream(job), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
