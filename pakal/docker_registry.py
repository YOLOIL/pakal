"""Read-only client for the Nexus Docker registry (Registry HTTP API V2).

Used by the portal's Docker tab: repository catalog, tags, and per-tag image details (exposed ports, volumes,
environment, entrypoint) read from the image config blob. Credentials stay on the server; Nexus may answer
with a Bearer challenge (Docker Bearer Token Realm), which is followed transparently.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urljoin, urlsplit

from . import auth_config
from .db import get_setting, set_setting

log = logging.getLogger("pakal.registry")

MANIFEST_TYPES = ", ".join((
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
))
INDEX_TYPES = {"application/vnd.docker.distribution.manifest.list.v2+json", "application/vnd.oci.image.index.v1+json"}
REPO_RE = re.compile(r"^[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*$")
TAG_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_SECRET_ENV = re.compile(r"PASS|SECRET|TOKEN|KEY|CREDENTIAL|PRIVATE", re.IGNORECASE)
_CHALLENGE_RE = re.compile(r'(\w+)="([^"]*)"')
_MAX_REPOS = 2000
_MAX_BODY = 4 * 1024 * 1024
_CATALOG_TTL = 60.0
_DETAIL_TTL = 300.0


class RegistryError(Exception):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


def settings(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Saved settings (or the given preview); a blank username borrows the Nexus repository credentials."""
    cfg = dict(cfg) if cfg is not None else auth_config.load("docker")
    if not cfg.get("username"):
        nexus = auth_config.load("nexus")
        cfg["username"], cfg["password"] = nexus.get("username", ""), nexus.get("password", "")
    return cfg


def configured(cfg: Dict[str, Any]) -> bool:
    return bool(cfg.get("enabled") and cfg.get("registry"))


def registry_host(cfg: Dict[str, Any]) -> str:
    """host[:port] as used in image references (docker pull <host>/<name>:<tag>)."""
    return re.sub(r"^https?://", "", str(cfg.get("registry", ""))).rstrip("/")


def base_url(cfg: Dict[str, Any]) -> str:
    registry = str(cfg.get("registry", "")).rstrip("/")
    return registry if registry.startswith(("http://", "https://")) else f"https://{registry}"


def repository_path(cfg: Dict[str, Any], name: str) -> str:
    namespace = str(cfg.get("namespace") or "").strip("/")
    return f"{namespace}/{name}" if namespace and not name.startswith(namespace + "/") else name


def image_ref(cfg: Dict[str, Any], repository: str, tag: str) -> str:
    return f"{registry_host(cfg)}/{repository}:{tag}"


def valid_repo(name: str) -> bool:
    return len(name) <= 255 and bool(REPO_RE.match(name))


def valid_tag(tag: str) -> bool:
    return bool(TAG_RE.match(tag))


# --------------------------------------------------------------------------- #
# HTTP with Basic / Bearer-challenge auth
# --------------------------------------------------------------------------- #

_tokens: Dict[Tuple[str, str], Tuple[str, float]] = {}
_tokens_lock = threading.Lock()


def _ssl_context(cfg: Dict[str, Any]) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if cfg.get("tls_insecure"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _basic(cfg: Dict[str, Any]) -> Optional[str]:
    if not cfg.get("username"):
        return None
    raw = f"{cfg['username']}:{cfg.get('password') or ''}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _open(cfg: Dict[str, Any], url: str, headers: Dict[str, str], timeout: float):
    request = urllib.request.Request(url, headers={"User-Agent": "PAKAL-registry/1.0", **headers})
    return urllib.request.urlopen(request, timeout=timeout, context=_ssl_context(cfg))


def _bearer_token(cfg: Dict[str, Any], challenge: str) -> Optional[str]:
    params = dict(_CHALLENGE_RE.findall(challenge))
    realm = params.pop("realm", "")
    if not realm:
        return None
    key = (realm, params.get("scope", ""))
    with _tokens_lock:
        cached = _tokens.get(key)
        if cached and cached[1] > time.monotonic():
            return cached[0]
    headers = {"Accept": "application/json"}
    basic = _basic(cfg)
    if basic:
        headers["Authorization"] = basic
    try:
        with _open(cfg, f"{realm}?{urlencode(params)}", headers, 15) as response:
            body = json.loads(response.read(_MAX_BODY).decode("utf-8") or "{}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RegistryError(f"Registry token request failed: {getattr(exc, 'reason', exc)}",
                            getattr(exc, "code", 0)) from exc
    token = body.get("token") or body.get("access_token")
    if token:
        ttl = max(30, int(body.get("expires_in") or 300) - 20)
        with _tokens_lock:
            _tokens[key] = (token, time.monotonic() + ttl)
    return token


def _get(cfg: Dict[str, Any], path: str, accept: str = "application/json",
         timeout: float = 15) -> Tuple[bytes, Dict[str, str]]:
    url = base_url(cfg) + path
    auth = _basic(cfg)
    for attempt in range(2):
        headers = {"Accept": accept}
        if auth:
            headers["Authorization"] = auth
        try:
            with _open(cfg, url, headers, timeout) as response:
                return response.read(_MAX_BODY), {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            challenge = exc.headers.get("WWW-Authenticate", "") if exc.headers else ""
            if exc.code == 401 and attempt == 0 and challenge.lower().startswith("bearer"):
                token = _bearer_token(cfg, challenge)
                if token:
                    auth = f"Bearer {token}"
                    continue
            messages = {401: "The registry rejected the configured credentials (401)",
                        403: "The registry account may not read this repository (403)",
                        404: "Not found in the registry (404)"}
            raise RegistryError(messages.get(exc.code, f"Registry HTTP {exc.code}"), exc.code) from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise RegistryError(f"Cannot reach the registry: {getattr(exc, 'reason', exc)}") from exc
    raise RegistryError("Registry authentication failed", 401)


def _get_json(cfg: Dict[str, Any], path: str, accept: str = "application/json") -> Tuple[Any, Dict[str, str]]:
    body, headers = _get(cfg, path, accept)
    try:
        return json.loads(body.decode("utf-8") or "null"), headers
    except ValueError as exc:
        raise RegistryError("The registry returned a non-JSON response") from exc


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #

_cache: Dict[Tuple[Any, ...], Tuple[float, Any]] = {}
_cache_lock = threading.Lock()


def _cached(key: Tuple[Any, ...], ttl: float, loader: Callable[[], Any], fresh: bool = False) -> Any:
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now and not fresh:
            return hit[1]
    value = loader()
    with _cache_lock:
        if len(_cache) > 2000:
            _cache.clear()
        _cache[key] = (now + ttl, value)
    return value


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
    with _tokens_lock:
        _tokens.clear()


def _cache_scope(cfg: Dict[str, Any]) -> Tuple[str, str, str]:
    return base_url(cfg), str(cfg.get("username", "")), str(cfg.get("namespace", ""))


# --------------------------------------------------------------------------- #
# Image overview (README captured from the build ZIP)
# --------------------------------------------------------------------------- #

README_MAX_CHARS = 64 * 1024


def _readme_key(repository: str) -> str:
    return "docker.readme." + hashlib.sha256(repository.encode("utf-8")).hexdigest()[:40]


def readme(repository: str) -> Optional[Dict[str, Any]]:
    raw = get_setting(_readme_key(repository))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("repository") != repository or not data.get("text"):
        return None
    return {"text": str(data["text"])[:README_MAX_CHARS], "tag": data.get("tag") or "",
            "updated_at": data.get("updated_at")}


def save_readme(repository: str, text: str, tag: str) -> None:
    text = text.replace("\r\n", "\n").strip()[:README_MAX_CHARS]
    if not text:
        return
    set_setting(_readme_key(repository), json.dumps({
        "repository": repository, "text": text, "tag": tag,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, ensure_ascii=False))


# --------------------------------------------------------------------------- #
# Catalog, tags, details
# --------------------------------------------------------------------------- #


def _version_key(tag: str) -> Tuple[int, List[Any]]:
    parts = [int(p) if p.isdigit() else p for p in re.split(r"[.\-_+]", tag.lstrip("vV"))]
    numeric = bool(parts) and isinstance(parts[0], int)
    return (1 if numeric else 0, [(0, p) if isinstance(p, int) else (-1, p) for p in parts])


def sort_tags(tags: List[str]) -> List[str]:
    """'latest' first, then versions newest first, then other names."""
    unique = [t for t in dict.fromkeys(tags) if isinstance(t, str) and t]
    rest = sorted((t for t in unique if t != "latest"), key=_version_key, reverse=True)
    return (["latest"] if "latest" in unique else []) + rest


def _list_repositories(cfg: Dict[str, Any]) -> List[str]:
    repos: List[str] = []
    path = "/v2/_catalog?n=500"
    for _page in range(10):
        body, headers = _get_json(cfg, path)
        repos.extend(r for r in (body or {}).get("repositories") or [] if isinstance(r, str))
        match = re.search(r"<([^>]+)>", headers.get("link", ""))
        if not match or len(repos) >= _MAX_REPOS:
            break
        target = urlsplit(urljoin("/v2/_catalog", match.group(1)))
        path = f"{target.path}?{target.query}" if target.query else target.path
    namespace = str(cfg.get("namespace") or "").strip("/")
    if namespace:
        repos = [r for r in repos if r == namespace or r.startswith(namespace + "/")]
    return sorted(dict.fromkeys(r for r in repos if valid_repo(r)))[:_MAX_REPOS]


def tags(cfg: Dict[str, Any], repository: str, fresh: bool = False) -> List[str]:
    def load() -> List[str]:
        body, _headers = _get_json(cfg, f"/v2/{repository}/tags/list?n=1000")
        return sort_tags((body or {}).get("tags") or [])
    return _cached(("tags", *_cache_scope(cfg), repository), _CATALOG_TTL, load, fresh)


def catalog(cfg: Dict[str, Any], fresh: bool = False) -> Dict[str, Any]:
    def load() -> Dict[str, Any]:
        repositories = _list_repositories(cfg)

        def entry(repo: str) -> Dict[str, Any]:
            try:
                found = tags(cfg, repo, fresh)
                return {"name": repo, "tags": found[:50], "tag_count": len(found), "latest": found[0] if found else None}
            except RegistryError as exc:
                return {"name": repo, "tags": [], "tag_count": 0, "latest": None, "error": str(exc)}

        with ThreadPoolExecutor(max_workers=8) as pool:
            images = list(pool.map(entry, repositories))
        return {"images": [i for i in images if i["tag_count"] or i.get("error")], "fetched_at": int(time.time())}
    return _cached(("catalog", *_cache_scope(cfg)), _CATALOG_TTL, load, fresh)


def _pick_platform(index: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
    platforms: List[str] = []
    preferred: Optional[str] = None
    fallback: Optional[str] = None
    for m in index.get("manifests") or []:
        if not isinstance(m, dict):
            continue
        p = m.get("platform") or {}
        if p.get("architecture") == "unknown":
            continue  # BuildKit attestation manifests
        label = "/".join(x for x in (p.get("os"), p.get("architecture"), p.get("variant")) if x)
        if label:
            platforms.append(label)
        fallback = fallback or m.get("digest")
        if preferred is None and p.get("os") == "linux" and p.get("architecture") == "amd64":
            preferred = m.get("digest")
    return preferred or fallback, platforms


def _env_entries(env: List[str]) -> List[Dict[str, Any]]:
    out = []
    for item in env or []:
        key, _sep, value = str(item).partition("=")
        masked = bool(_SECRET_ENV.search(key) and value)
        out.append({"key": key, "value": "" if masked else value[:500], "masked": masked})
    return out


def _parse_ports(exposed: Dict[str, Any]) -> List[Dict[str, Any]]:
    ports = []
    for spec in exposed or {}:
        number, _sep, proto = str(spec).partition("/")
        if number.isdigit():
            ports.append({"port": int(number), "protocol": proto or "tcp"})
    return sorted(ports, key=lambda p: (p["port"], p["protocol"]))


def details(cfg: Dict[str, Any], repository: str, tag: str) -> Dict[str, Any]:
    def load() -> Dict[str, Any]:
        manifest, headers = _get_json(cfg, f"/v2/{repository}/manifests/{tag}", MANIFEST_TYPES)
        digest = headers.get("docker-content-digest")
        media = (manifest or {}).get("mediaType") or headers.get("content-type", "").split(";")[0]
        platforms: List[str] = []
        if media in INDEX_TYPES or (manifest or {}).get("manifests"):
            chosen, platforms = _pick_platform(manifest)
            if not chosen:
                raise RegistryError("The image index lists no usable platform")
            manifest, _h = _get_json(cfg, f"/v2/{repository}/manifests/{chosen}", MANIFEST_TYPES)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("config"), dict):
            raise RegistryError("Unsupported manifest format (schema 1 images are not supported)")
        layers = [layer for layer in manifest.get("layers") or [] if isinstance(layer, dict)]
        size = sum(int(layer.get("size") or 0) for layer in layers) + int(manifest["config"].get("size") or 0)
        blob, _h = _get_json(cfg, f"/v2/{repository}/blobs/{manifest['config']['digest']}")
        image_cfg = (blob or {}).get("config") or {}
        labels = image_cfg.get("Labels") or {}
        return {
            "name": repository,
            "tag": tag,
            "digest": digest,
            "created": (blob or {}).get("created"),
            "os": (blob or {}).get("os"),
            "architecture": (blob or {}).get("architecture"),
            "platforms": platforms,
            "size_bytes": size,
            "layers": len(layers),
            "ports": _parse_ports(image_cfg.get("ExposedPorts") or {}),
            "volumes": sorted((image_cfg.get("Volumes") or {}).keys()),
            "env": _env_entries(image_cfg.get("Env") or []),
            "entrypoint": image_cfg.get("Entrypoint") or [],
            "cmd": image_cfg.get("Cmd") or [],
            "workdir": image_cfg.get("WorkingDir") or "",
            "user": image_cfg.get("User") or "",
            "labels": {str(k): str(v)[:500] for k, v in list(labels.items())[:40]},
            "description": labels.get("org.opencontainers.image.description") or labels.get("description") or "",
            "reference": image_ref(cfg, repository, tag),
        }
    return _cached(("details", *_cache_scope(cfg), repository, tag), _DETAIL_TTL, load)


def test_connection(cfg: Dict[str, Any]) -> Dict[str, Any]:
    started = time.monotonic()
    out: Dict[str, Any] = {"ok": False, "reachable": False, "auth": None, "repositories": 0, "error": None, "ms": 0}
    if not cfg.get("registry"):
        out["error"] = "No registry configured"
    else:
        try:
            _get(cfg, "/v2/", timeout=10)
            out["reachable"] = out["auth"] = True
            out["repositories"] = len(_list_repositories(cfg))
            out["ok"] = True
        except RegistryError as exc:
            out["reachable"] = exc.status != 0
            out["auth"] = False if exc.status in (401, 403) else None
            out["error"] = str(exc)
    out["ms"] = int((time.monotonic() - started) * 1000)
    return out
