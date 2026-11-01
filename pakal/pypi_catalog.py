"""PyPI catalog backed by the Nexus Search API.

The full repository listing is cached briefly. Live search (``q``) filters that cache, so typing
does not call Nexus again until the cache expires.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import quote, urlencode

from .nexus import _request_json, repos_for

log = logging.getLogger("pakal.pypi")

CACHE_TTL = 60.0
MAX_PAGES = 40
PAGE_TIMEOUT = 20.0
_SAFE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+/-]{0,500}$")
_WHEEL_TAIL = re.compile(r"-(?P<py>[A-Za-z0-9.]+)-(?P<abi>[A-Za-z0-9.]+)-(?P<plat>[A-Za-z0-9._]+)\.whl$", re.IGNORECASE)

_cache: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def catalog_repository(cfg: Dict[str, Any]) -> str:
    repos = repos_for(cfg, "pypi")
    return repos[0] if repos else "pypi-hosted"


def index_url(cfg: Dict[str, Any], repository: str) -> str:
    base = str(cfg.get("url", "")).rstrip("/")
    return f"{base}/repository/{quote(repository, safe='')}/simple"


def safe_asset_path(path: str) -> str:
    value = (path or "").strip().lstrip("/")
    if ".." in value.split("/") or not _SAFE_PATH.match(value):
        return ""
    lower = value.lower()
    if not (lower.endswith(".whl") or lower.endswith(".tar.gz")):
        return ""
    return value


def wheel_tags(filename: str) -> List[str]:
    """Python tag, ABI and platform from a wheel name (cp311, manylinux, win_amd64)."""
    match = _WHEEL_TAIL.search(filename or "")
    if not match:
        return ["sdist"] if (filename or "").lower().endswith(".tar.gz") else []
    tags = [match.group("py")]
    abi = match.group("abi")
    plat = _short_platform(match.group("plat"))
    if abi and abi.lower() not in ("none", tags[0].lower()):
        tags.append(abi)
    if plat:
        tags.append(plat)
    return tags


def _short_platform(plat: str) -> str:
    """Keep tags readable: manylinux / win_amd64 / macosx, not the full compatibility string."""
    value = (plat or "").strip()
    lower = value.lower()
    if not lower or lower == "any":
        return "any"
    if lower.startswith("manylinux"):
        return "manylinux"
    if lower.startswith("musllinux"):
        return "musllinux"
    if lower.startswith("macosx"):
        return "macosx"
    return value


def _filename(asset: Dict[str, Any]) -> str:
    path = str(asset.get("path") or "")
    name = path.rsplit("/", 1)[-1]
    if name:
        return name
    url = str(asset.get("downloadUrl") or "")
    return url.rsplit("/", 1)[-1].split("?", 1)[0]


def _search_page(cfg: Dict[str, Any], repository: str, token: str = "") -> Dict[str, Any]:
    params = {"repository": repository}
    if token:
        params["continuationToken"] = token
    body = _request_json(cfg, "/service/rest/v1/search?" + urlencode(params), timeout=PAGE_TIMEOUT)
    return body if isinstance(body, dict) else {}


def _load(cfg: Dict[str, Any], repository: str) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    token = ""
    pages = 0
    truncated = False
    while True:
        pages += 1
        body = _search_page(cfg, repository, token)
        for item in body.get("items") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            version = str(item.get("version") or "").strip()
            if not name:
                continue
            for asset in item.get("assets") or []:
                if not isinstance(asset, dict):
                    continue
                filename = _filename(asset)
                path = safe_asset_path(str(asset.get("path") or filename))
                if not path:
                    continue
                files.append({
                    "name": name,
                    "version": version,
                    "filename": filename,
                    "path": path,
                    "size": int(asset.get("fileSize") or 0),
                    "uploaded": str(asset.get("lastModified") or ""),
                    "download_url": str(asset.get("downloadUrl") or ""),
                    "tags": wheel_tags(filename),
                    "kind": "wheel" if filename.lower().endswith(".whl") else "sdist",
                })
        token = str(body.get("continuationToken") or "")
        if not token:
            break
        if pages >= MAX_PAGES:
            truncated = True
            break
    packages = _group(files)
    log.info("PyPI catalog %s: %d packages, %d files%s", repository, len(packages), len(files),
             " (truncated)" if truncated else "")
    return {"packages": packages, "truncated": truncated}


def _group(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in files:
        key = item["name"].lower()
        entry = grouped.get(key)
        if entry is None:
            entry = {"name": item["name"], "files": []}
            grouped[key] = entry
        entry["files"].append({k: item[k] for k in ("filename", "version", "path", "size", "uploaded", "download_url", "tags", "kind")})
    packages = []
    for entry in grouped.values():
        entry["files"].sort(key=lambda f: (f["uploaded"], f["kind"] == "wheel"), reverse=True)
        wheels = [f for f in entry["files"] if f["kind"] == "wheel"]
        newest = wheels[0] if wheels else entry["files"][0]
        versions = list(dict.fromkeys(f["version"] for f in entry["files"] if f["version"]))
        packages.append({
            "name": entry["name"],
            "latest": newest["version"],
            "versions": versions,
            "tags": newest["tags"],
            "files": entry["files"],
        })
    packages.sort(key=lambda p: p["name"].lower())
    return packages


def _cached(cfg: Dict[str, Any], repository: str, fresh: bool) -> Dict[str, Any]:
    key = (str(cfg.get("url", "")).rstrip("/"), repository)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now and not fresh:
            return hit[1]
    value = _load(cfg, repository)
    with _cache_lock:
        _cache[key] = (now + CACHE_TTL, value)
    return value


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def catalog(cfg: Dict[str, Any], query: str = "", fresh: bool = False) -> Dict[str, Any]:
    repository = catalog_repository(cfg)
    loaded = _cached(cfg, repository, fresh)
    packages = loaded["packages"]
    needle = query.strip().lower()
    if needle:
        packages = [p for p in packages if needle in p["name"].lower() or any(
            needle in f["filename"].lower() or needle in (f["version"] or "").lower() for f in p["files"])]
    return {
        "repository": repository,
        "index_url": index_url(cfg, repository),
        "packages": packages,
        "total": len(packages),
        "truncated": bool(loaded["truncated"]),
    }


__all__ = ["catalog", "catalog_repository", "clear_cache", "safe_asset_path", "wheel_tags"]
