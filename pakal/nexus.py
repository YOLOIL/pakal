"""Sonatype Nexus publishing for the portal's bulk package uploader.

Supported formats and the Nexus repository format they are published to:
    Python     .whl, .tar.gz  -> pypi  (form field pypi.asset)
    NPM        .tgz           -> npm   (form field npm.asset)
    PowerShell .nupkg         -> nuget (form field nuget.asset; Nexus serves PowerShell galleries from NuGet repos)

Uploads use the components REST API (POST /service/rest/v1/components?repository=<name>). The Nexus
credentials never reach the browser: files are streamed to the portal, validated, then forwarded.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import secrets
import shutil
import ssl
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import urlencode

from . import auth_config, config

log = logging.getLogger("pakal.nexus")

KINDS: Dict[str, Dict[str, Any]] = {
    "pypi": {"extensions": (".whl", ".tar.gz"), "field": "pypi.asset", "repo_key": "pypi_repo", "format": "pypi"},
    "npm": {"extensions": (".tgz", ".tar.gz"), "field": "npm.asset", "repo_key": "npm_repo", "format": "npm"},
    "powershell": {"extensions": (".nupkg",), "field": "nuget.asset", "repo_key": "powershell_repo", "format": "nuget"},
}
# Automatic detection: the extension decides the format (".tar.gz" is a Python sdist unless overridden).
DETECT_ORDER: Tuple[Tuple[str, str], ...] = ((".whl", "pypi"), (".tar.gz", "pypi"), (".tgz", "npm"),
                                             (".nupkg", "powershell"))
REPO_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
MAX_REPOS_PER_KIND = 10

_FILENAME_RE = re.compile(r"^[\w@+.,~()\[\] -]{1,255}$")
# One ZIP path segment. A leading @ is an npm scope directory (@angular), not a sanitization error.
_ZIP_PART_RE = re.compile(r"^@?[A-Za-z0-9._+-]{1,214}$")
_MAX_ZIP_PACKAGES = 400
_WHEEL_RE = re.compile(r"^(?P<name>[A-Za-z0-9_.]+?)-(?P<version>[A-Za-z0-9_.!+]+)(-\d[^-]*)?-[^-]+-[^-]+-[^-]+\.whl$",
                       re.IGNORECASE)
_EXISTS_RE = re.compile(r"does not allow updating|already exists|redeploy|cannot be updated|not allowed to update",
                        re.IGNORECASE)
_MAX_META_BYTES = 5 * 1024 * 1024
_MAX_ARCHIVE_MEMBERS = 2000
_CHUNK = 1024 * 1024


class PackageError(ValueError):
    """The uploaded file is not a valid package of the requested format."""


class NexusError(Exception):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


def settings() -> Dict[str, Any]:
    return auth_config.load("nexus")


def configured(cfg: Dict[str, Any]) -> bool:
    return bool(cfg.get("enabled") and cfg.get("url"))


def split_repos(value: str) -> List[str]:
    return [r for r in dict.fromkeys(re.split(r"[\s,;]+", value or "")) if r][:MAX_REPOS_PER_KIND]


def repos_for(cfg: Dict[str, Any], kind: str) -> List[str]:
    return split_repos(str(cfg.get(KINDS[kind]["repo_key"], "")))


def public_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "configured": configured(cfg),
        "max_upload_mb": int(cfg.get("max_upload_mb") or 0),
        "kinds": {kind: {"extensions": list(meta["extensions"]), "repositories": repos_for(cfg, kind)}
                  for kind, meta in KINDS.items()},
        "detect": [list(pair) for pair in DETECT_ORDER],
    }


# --------------------------------------------------------------------------- #
# File validation & package metadata
# --------------------------------------------------------------------------- #


def clean_filename(value: str) -> str:
    """Basename only. ``@`` is kept, so ``@angular-core-1.0.0.tgz`` is a valid upload name."""
    name = re.split(r"[\\/]", str(value or ""))[-1].strip()
    if not name or name.startswith(".") or not _FILENAME_RE.match(name):
        raise PackageError("Invalid file name")
    return name


def safe_zip_member(name: str) -> str:
    """Archive-relative path, or "" when it is unsafe.

    Scope directories are preserved: ``@angular/core/core-1.0.0.tgz`` stays intact.
    ``..``, absolute paths and drive letters are rejected.
    """
    raw = str(name or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw) or "\x00" in raw:
        return ""
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts) or any(not _ZIP_PART_RE.match(part) for part in parts):
        return ""
    return "/".join(parts)


def member_kind(rel_path: str) -> Optional[str]:
    """Package type of a ZIP member. A ``.tar.gz`` under an ``@scope`` directory is an npm package."""
    lower = rel_path.lower()
    scoped = any(part.startswith("@") for part in rel_path.split("/"))
    if lower.endswith(".tgz") or (lower.endswith(".tar.gz") and scoped):
        return "npm"
    if lower.endswith(".tar.gz") or lower.endswith(".whl"):
        return "pypi"
    if lower.endswith(".nupkg"):
        return "powershell"
    return None


def file_extension(filename: str) -> Optional[str]:
    lower = filename.lower()
    for ext, _kind in DETECT_ORDER:
        if lower.endswith(ext):
            return ext
    return None


def detect_kind(filename: str) -> Optional[str]:
    lower = filename.lower()
    return next((kind for ext, kind in DETECT_ORDER if lower.endswith(ext)), None)


def accepts(kind: str, filename: str) -> bool:
    ext = file_extension(filename)
    return bool(ext) and ext in KINDS[kind]["extensions"]


def _parse_core_metadata(text: str) -> Tuple[Optional[str], Optional[str]]:
    header = text.split("\n\n", 1)[0]
    name = re.search(r"^Name:\s*(\S.*?)\s*$", header, re.MULTILINE)
    version = re.search(r"^Version:\s*(\S.*?)\s*$", header, re.MULTILINE)
    return (name.group(1) if name else None), (version.group(1) if version else None)


def _zip_member(path: Path, predicate) -> Optional[bytes]:
    if not zipfile.is_zipfile(path):
        raise PackageError("The file is not a valid ZIP-based package")
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist()[:_MAX_ARCHIVE_MEMBERS]:
                if predicate(info.filename) and info.file_size <= _MAX_META_BYTES:
                    return archive.read(info)
    except (zipfile.BadZipFile, OSError, zlib.error, EOFError) as exc:
        raise PackageError(f"Corrupt ZIP archive: {exc}") from exc
    return None


def _tar_member(path: Path, predicate) -> Optional[bytes]:
    with path.open("rb") as handle:
        if handle.read(2) != b"\x1f\x8b":
            raise PackageError("The file is not a gzip-compressed tarball")
    try:
        with tarfile.open(path, "r:gz") as archive:
            for index, member in enumerate(archive):
                if index >= _MAX_ARCHIVE_MEMBERS:
                    break
                if member.isfile() and predicate(member.name) and member.size <= _MAX_META_BYTES:
                    extracted = archive.extractfile(member)
                    return extracted.read() if extracted else None
    except (tarfile.TarError, OSError, zlib.error, EOFError) as exc:
        raise PackageError(f"Corrupt tarball: {exc}") from exc
    return None


def _top_level(name: str, filename: str) -> bool:
    parts = name.strip("/").split("/")
    return len(parts) == 2 and parts[1] == filename


def inspect_package(kind: str, path: Path, filename: str) -> Tuple[str, str]:
    """(name, version) read from the package metadata; raises PackageError for files Nexus would reject."""
    lower = filename.lower()
    name: Optional[str] = None
    version: Optional[str] = None
    if kind == "pypi" and lower.endswith(".whl"):
        raw = _zip_member(path, lambda n: n.count("/") == 1 and n.split("/")[0].endswith(".dist-info")
                          and n.endswith("/METADATA"))
        if raw:
            name, version = _parse_core_metadata(raw.decode("utf-8", errors="replace"))
        if not (name and version):
            match = _WHEEL_RE.match(filename)
            if not match:
                raise PackageError("Wheel metadata (*.dist-info/METADATA) not found")
            name, version = match.group("name"), match.group("version")
    elif kind == "pypi":
        raw = _tar_member(path, lambda n: _top_level(n, "PKG-INFO"))
        if raw:
            name, version = _parse_core_metadata(raw.decode("utf-8", errors="replace"))
        if not (name and version):
            stem = filename[: -len(".tar.gz")]
            if "-" not in stem:
                raise PackageError("Source distribution metadata (PKG-INFO) not found")
            name, version = stem.rsplit("-", 1)
    elif kind == "npm":
        raw = _tar_member(path, lambda n: _top_level(n, "package.json"))
        if not raw:
            raise PackageError("package.json not found - this is not an npm package tarball")
        try:
            manifest = json.loads(raw.decode("utf-8-sig"))
        except ValueError as exc:
            raise PackageError("package.json is not valid JSON") from exc
        if isinstance(manifest, dict):
            name, version = manifest.get("name"), manifest.get("version")
        if not (isinstance(name, str) and isinstance(version, str) and name and version):
            raise PackageError("package.json has no name/version")
    elif kind == "powershell":
        raw = _zip_member(path, lambda n: "/" not in n and n.lower().endswith(".nuspec"))
        if not raw:
            raise PackageError("No .nuspec manifest found - this is not a NuGet/PowerShell package")
        text = raw.decode("utf-8-sig", errors="replace")
        id_match = re.search(r"<id>\s*([^<]+?)\s*</id>", text, re.IGNORECASE)
        version_match = re.search(r"<version>\s*([^<]+?)\s*</version>", text, re.IGNORECASE)
        if not (id_match and version_match):
            raise PackageError("The .nuspec manifest has no id/version")
        name, version = id_match.group(1), version_match.group(1)
    else:
        raise PackageError("Unsupported package type")
    return str(name).strip()[:214], str(version).strip()[:128]


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #


def _ssl_context(cfg: Dict[str, Any]) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if cfg.get("tls_insecure"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _headers(cfg: Dict[str, Any], auth: bool = True) -> Dict[str, str]:
    headers = {"User-Agent": "PAKAL-uploader/1.0", "Accept": "application/json"}
    if auth and cfg.get("username"):
        token = base64.b64encode(f"{cfg['username']}:{cfg.get('password') or ''}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    return headers


def _error_text(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read(4096).decode("utf-8", errors="replace").strip()
    except OSError:
        body = ""
    try:
        parsed = json.loads(body)
        if isinstance(parsed, list):
            body = " · ".join(str(item.get("message", item)) if isinstance(item, dict) else str(item) for item in parsed)
        elif isinstance(parsed, dict):
            body = str(parsed.get("message") or parsed)
    except ValueError:
        pass
    return re.sub(r"<[^>]+>", " ", body)[:300].strip()


def _request(cfg: Dict[str, Any], method: str, path: str, *, auth: bool = True, data: Any = None,
             headers: Optional[Dict[str, str]] = None, timeout: Optional[float] = None) -> Tuple[int, bytes]:
    url = str(cfg.get("url", "")).rstrip("/") + path
    request = urllib.request.Request(url, data=data, method=method, headers={**_headers(cfg, auth), **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout or float(cfg.get("timeout_seconds") or 300),
                                    context=_ssl_context(cfg)) as response:
            return response.status, response.read(2 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        raise NexusError(_error_text(exc) or exc.reason or f"HTTP {exc.code}", exc.code) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        raise NexusError(f"Cannot reach Nexus: {reason}") from exc


def open_repository_file(cfg: Dict[str, Any], repository: str, path: str, timeout: float = 120):
    """GET a file from a Nexus hosted repository. The caller closes the response."""
    url = str(cfg.get("url", "")).rstrip("/") + f"/repository/{repository}/{path.lstrip('/')}"
    request = urllib.request.Request(url, method="GET", headers={**_headers(cfg), "Accept": "*/*"})
    try:
        return urllib.request.urlopen(request, timeout=timeout, context=_ssl_context(cfg))
    except urllib.error.HTTPError as exc:
        raise NexusError(_error_text(exc) or exc.reason or f"HTTP {exc.code}", exc.code) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        raise NexusError(f"Cannot reach Nexus: {reason}") from exc


def _request_json(cfg: Dict[str, Any], path: str, *, auth: bool = True, timeout: float = 15) -> Any:
    _status, body = _request(cfg, "GET", path, auth=auth, timeout=timeout)
    try:
        return json.loads(body.decode("utf-8")) if body else None
    except ValueError as exc:
        raise NexusError("Nexus returned a non-JSON response") from exc


def component_exists(cfg: Dict[str, Any], kind: str, repository: str, name: str, version: str) -> Optional[bool]:
    """Best-effort search for name+version in the target repository; None when the search itself fails."""
    queries: List[Dict[str, str]] = []
    if kind == "npm" and name.startswith("@") and "/" in name:
        scope, bare = name[1:].split("/", 1)
        queries.append({"group": scope, "name": bare})
    else:
        queries.append({"name": name})
        if kind == "pypi":
            normalized = re.sub(r"[-_.]+", "-", name).lower()
            if normalized != name:
                queries.append({"name": normalized})
    try:
        for query in queries:
            body = _request_json(cfg, "/service/rest/v1/search?" + urlencode(
                {"repository": repository, "version": version, **query}))
            if isinstance(body, dict) and body.get("items"):
                return True
    except NexusError as exc:
        log.debug("Existence check for %s %s in %s failed: %s", name, version, repository, exc)
        return None
    return False


class _MultipartFile:
    """multipart/form-data body streamed from disk so large packages never sit in memory."""

    def __init__(self, field: str, filename: str, path: Path) -> None:
        self.boundary = f"----PakalUpload{secrets.token_hex(16)}"
        safe_name = re.sub(r'["\r\n]', "_", filename)
        self._head = (f'--{self.boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{safe_name}"'
                      f"\r\nContent-Type: application/octet-stream\r\n\r\n").encode("utf-8")
        self._tail = f"\r\n--{self.boundary}--\r\n".encode("ascii")
        self._path = path
        self.length = len(self._head) + path.stat().st_size + len(self._tail)

    def __iter__(self) -> Iterator[bytes]:
        yield self._head
        with self._path.open("rb") as handle:
            while chunk := handle.read(_CHUNK):
                yield chunk
        yield self._tail


def _classify_failure(exc: NexusError, repository: str) -> Tuple[str, str]:
    detail = str(exc)
    if exc.status in (400, 409) and _EXISTS_RE.search(detail):
        return "exists", f"This version already exists in {repository}"
    messages = {
        401: "Nexus rejected the configured credentials (401)",
        403: f"The Nexus account may not deploy to {repository} (403)",
        404: f"Repository {repository} was not found in Nexus (404)",
        413: "The file is larger than Nexus or its reverse proxy accepts (413)",
    }
    if exc.status in messages:
        return "failed", messages[exc.status]
    return "failed", f"Nexus HTTP {exc.status}: {detail}" if exc.status else detail


def upload_asset(cfg: Dict[str, Any], kind: str, repository: str, path: Path, filename: str) -> Tuple[str, str]:
    body = _MultipartFile(KINDS[kind]["field"], filename, path)
    try:
        _request(cfg, "POST", "/service/rest/v1/components?" + urlencode({"repository": repository}), data=iter(body),
                 headers={"Content-Type": f"multipart/form-data; boundary={body.boundary}",
                          "Content-Length": str(body.length)})
    except NexusError as exc:
        return _classify_failure(exc, repository)
    return "success", f"Published to {repository}"


def expand_package_zip(archive_path: Path, dest: Path) -> List[Dict[str, Any]]:
    """Extract publishable members, recreating ``@scope`` directories under ``dest``."""
    if not zipfile.is_zipfile(archive_path):
        raise PackageError("The file is not a valid ZIP archive")
    found: List[Dict[str, Any]] = []
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                rel = safe_zip_member(info.filename)
                kind = member_kind(rel) if rel else None
                if not kind:
                    continue
                if len(found) >= _MAX_ZIP_PACKAGES:
                    raise PackageError(f"The archive has more than {_MAX_ZIP_PACKAGES} packages")
                target = dest.joinpath(*rel.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise PackageError(f"Duplicate path in archive: {rel}")
                with archive.open(info) as source, open(target, "xb") as sink:
                    shutil.copyfileobj(source, sink, _CHUNK)
                found.append({"path": rel, "filename": rel.rsplit("/", 1)[-1], "file": target, "kind": kind})
    except PackageError:
        raise
    except (zipfile.BadZipFile, OSError, zlib.error, EOFError) as exc:
        raise PackageError(f"Corrupt ZIP archive: {exc}") from exc
    if not found:
        raise PackageError("The ZIP contains no .tgz, .tar.gz, .whl or .nupkg files")
    return found


def publish_zip(cfg: Dict[str, Any], kind_hint: str, repository: str, archive_path: Path, filename: str) -> Dict[str, Any]:
    """Publish every package inside a ZIP. Scoped npm paths are kept and sent to the NPM repository."""
    work = Path(tempfile.mkdtemp(prefix="pakal-zip-", dir=config.UPLOAD_TMP_DIR))
    try:
        members = expand_package_zip(archive_path, work)
        results: List[Dict[str, Any]] = []
        for member in members:
            kind = member["kind"]
            repos = repos_for(cfg, kind)
            target = repository if kind == kind_hint and repository in repos else (repos[0] if repos else "")
            if not target:
                results.append({
                    "path": member["path"], "filename": member["filename"], "kind": kind, "repository": "",
                    "package": "", "version": "", "status": "failed",
                    "detail": f"No {kind} repository is configured",
                })
                continue
            try:
                published = publish(cfg, kind, target, member["file"], member["filename"])
            except PackageError as exc:
                published = {
                    "filename": member["filename"], "kind": kind, "repository": target,
                    "package": "", "version": "", "status": "failed", "detail": str(exc),
                }
            published["path"] = member["path"]
            results.append(published)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    failed = sum(1 for item in results if item["status"] == "failed")
    existed = sum(1 for item in results if item["status"] == "exists")
    published_ok = sum(1 for item in results if item["status"] == "success")
    if failed and not published_ok and not existed:
        status = "failed"
    elif failed:
        status = "failed"
    elif published_ok:
        status = "success"
    else:
        status = "exists"
    first = next((item for item in results if item.get("package")), results[0])
    detail = f"Published {published_ok}, already present {existed}, failed {failed}"
    return {
        "filename": filename, "kind": kind_hint, "repository": repository, "status": status, "detail": detail,
        "package": first.get("package") or "", "version": first.get("version") or "", "packages": results,
    }


def publish(cfg: Dict[str, Any], kind: str, repository: str, path: Path, filename: str) -> Dict[str, Any]:
    """Validate, de-duplicate and upload one package. Raises PackageError for invalid files."""
    name, version = inspect_package(kind, path, filename)
    result: Dict[str, Any] = {"filename": filename, "kind": kind, "repository": repository,
                              "package": name, "version": version}
    if cfg.get("check_existing") and component_exists(cfg, kind, repository, name, version):
        return {**result, "status": "exists", "detail": f"{name} {version} already exists in {repository}"}
    status, detail = upload_asset(cfg, kind, repository, path, filename)
    return {**result, "status": status, "detail": detail}


# --------------------------------------------------------------------------- #
# Admin connection test
# --------------------------------------------------------------------------- #


def test_connection(cfg: Dict[str, Any]) -> Dict[str, Any]:
    started = time.monotonic()
    out: Dict[str, Any] = {"ok": False, "reachable": False, "auth": None, "repos": [], "error": None, "ms": 0}

    def done() -> Dict[str, Any]:
        out["ms"] = int((time.monotonic() - started) * 1000)
        return out

    if not cfg.get("url"):
        out["error"] = "No Nexus URL configured"
        return done()
    try:
        _request(cfg, "GET", "/service/rest/v1/status", auth=False, timeout=10)
        out["reachable"] = True
    except NexusError as exc:
        out["error"] = str(exc)
        return done()
    try:
        repositories = _request_json(cfg, "/service/rest/v1/repositories")
        out["auth"] = True
    except NexusError as exc:
        out["auth"] = False if exc.status in (401, 403) else None
        out["error"] = f"HTTP {exc.status}: {exc}" if exc.status else str(exc)
        return done()
    index = {r.get("name"): r for r in repositories or [] if isinstance(r, dict)}
    for kind, meta in KINDS.items():
        for name in repos_for(cfg, kind):
            repo = index.get(name) or {}
            out["repos"].append({
                "kind": kind, "name": name, "found": bool(repo), "format": repo.get("format"), "type": repo.get("type"),
                "ok": repo.get("format") == meta["format"] and repo.get("type") == "hosted",
            })
    out["ok"] = bool(out["repos"]) and all(r["ok"] for r in out["repos"])
    if not out["repos"]:
        out["error"] = "No target repositories configured"
    return done()
