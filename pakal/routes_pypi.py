"""PyPI catalog: Nexus-hosted wheels and sdists, with a proxied download."""

from __future__ import annotations

import logging
from typing import Iterator
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import iterate_in_threadpool, run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from . import nexus, portal_ui, pypi_catalog

log = logging.getLogger("pakal.pypi.api")
router = APIRouter(prefix="/api/pypi", tags=["pypi"])
NO_STORE = {"Cache-Control": "no-store"}
_CHUNK = 1024 * 1024


def _require(cfg: dict) -> str:
    if not portal_ui.enabled("tab_pypi"):
        raise HTTPException(status_code=403, detail="The PyPI catalog is disabled by the administrator")
    if not nexus.configured(cfg):
        raise HTTPException(status_code=503, detail="Nexus is not configured")
    return pypi_catalog.catalog_repository(cfg)


@router.get("/packages")
async def packages(q: str = Query(default="", max_length=100), fresh: bool = False) -> JSONResponse:
    cfg = nexus.settings()
    _require(cfg)
    try:
        body = await run_in_threadpool(pypi_catalog.catalog, cfg, q, fresh)
    except nexus.NexusError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return JSONResponse(body, headers=NO_STORE)


@router.get("/download")
async def download(path: str = Query(max_length=500)) -> StreamingResponse:
    cfg = nexus.settings()
    repository = _require(cfg)
    asset = pypi_catalog.safe_asset_path(path)
    if not asset:
        raise HTTPException(status_code=422, detail="Only .whl and .tar.gz files from this repository can be downloaded")
    try:
        upstream = await run_in_threadpool(nexus.open_repository_file, cfg, repository, asset)
    except nexus.NexusError as exc:
        raise HTTPException(status_code=404 if exc.status == 404 else 502, detail=str(exc))
    filename = asset.rsplit("/", 1)[-1]

    def chunks() -> Iterator[bytes]:
        try:
            while True:
                block = upstream.read(_CHUNK)
                if not block:
                    break
                yield block
        finally:
            upstream.close()

    log.info("PyPI download %s/%s", repository, asset)
    return StreamingResponse(iterate_in_threadpool(chunks()), media_type="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "no-store",
    })
