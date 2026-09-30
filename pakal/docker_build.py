"""ZIP-to-image builds through the host Docker engine (Actions tab).

A project ZIP is extracted into a private temporary directory, packed as a build context and sent to the
Docker Engine API over the mounted socket (``POST /build``). The result is tagged for the Nexus Docker
registry, pushed (``POST /images/<name>/push``) and the local tag removed again. Every step is reported as
an event on a queue that the HTTP layer turns into Server-Sent Events.

The engine API is used directly instead of the ``docker`` CLI, so the image needs no Docker binaries.
"""

from __future__ import annotations

import base64
import fnmatch
import http.client
import json
import logging
import os
import queue
import re
import shutil
import socket
import stat
import tarfile
import tempfile
import threading
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterator, List, Optional, Tuple
from urllib.parse import quote, urlencode

from . import config, docker_registry

log = logging.getLogger("pakal.docker")

_PUSHED_RE = re.compile(r"digest: (sha256:[0-9a-f]{64}) size: (\d+)")
IMAGE_NAME_RE = re.compile(r"^[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*){0,3}$")
_MAX_MEMBERS = 20000
_EXPANSION_FACTOR = 4
_ENGINE_TIMEOUT = 30.0
_WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com\d|lpt\d)(\..*)?$", re.IGNORECASE)

_slots = threading.BoundedSemaphore(config.DOCKER_MAX_CONCURRENT_BUILDS)


class BuildError(Exception):
    """A user-facing failure; the message is shown in the terminal as-is."""


# --------------------------------------------------------------------------- #
# Docker Engine API over the unix socket
# --------------------------------------------------------------------------- #


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float) -> None:
        super().__init__("localhost", timeout=timeout)
        self._socket_path = path

    def connect(self) -> None:
        family = getattr(socket, "AF_UNIX", None)
        if family is None:
            raise OSError("Unix sockets are not available on this platform")
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self._socket_path)
        self.sock = sock


def _connection(timeout: float = _ENGINE_TIMEOUT) -> http.client.HTTPConnection:
    endpoint = config.DOCKER_SOCKET
    if endpoint.startswith(("tcp://", "http://")):
        host = re.sub(r"^(tcp|http)://", "", endpoint).rstrip("/")
        return http.client.HTTPConnection(host, timeout=timeout)
    return _UnixConnection(re.sub(r"^unix://", "", endpoint), timeout)


def engine_status() -> Dict[str, Any]:
    """Is the engine reachable? Cheap enough for the Actions tab config call."""
    endpoint = config.DOCKER_SOCKET
    if not endpoint.startswith(("tcp://", "http://")):
        path = re.sub(r"^unix://", "", endpoint)
        if not getattr(socket, "AF_UNIX", None) or not os.path.exists(path):
            return {"available": False, "error": f"Docker socket {path} is not mounted"}
        if not os.access(path, os.R_OK | os.W_OK):
            return {"available": False, "error": f"No permission on {path} (add the container to the docker group)"}
    conn = _connection(5)
    try:
        conn.request("GET", "/version")
        response = conn.getresponse()
        body = json.loads(response.read(65536) or b"{}")
        if response.status != 200:
            return {"available": False, "error": f"Docker engine HTTP {response.status}"}
        return {"available": True, "version": body.get("Version"), "api": body.get("ApiVersion")}
    except (OSError, ValueError, http.client.HTTPException) as exc:
        return {"available": False, "error": f"Docker engine unreachable: {exc}"}
    finally:
        conn.close()


def _registry_auth(cfg: Dict[str, Any]) -> Dict[str, str]:
    return {"username": str(cfg.get("username") or ""), "password": str(cfg.get("password") or ""),
            "serveraddress": docker_registry.registry_host(cfg)}


def _b64json(value: Any) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode("utf-8")).decode("ascii")


# --------------------------------------------------------------------------- #
# Build context: safe extraction, .dockerignore, tar
# --------------------------------------------------------------------------- #


def safe_member(name: str) -> Optional[PurePosixPath]:
    name = name.replace("\\", "/")
    if not name or name.startswith("/") or re.match(r"^[A-Za-z]:", name) or "\x00" in name:
        return None
    parts = [p for p in PurePosixPath(name).parts if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts) or any(_WINDOWS_RESERVED.match(p) for p in parts):
        return None
    return PurePosixPath(*parts)


def extract_zip(archive_path: Path, target: Path, max_bytes: int) -> int:
    """Extract regular files only; rejects traversal, links and archives that expand far beyond the limit."""
    try:
        archive = zipfile.ZipFile(archive_path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise BuildError(f"Not a valid ZIP archive: {exc}") from exc
    with archive:
        members = archive.infolist()
        if len(members) > _MAX_MEMBERS:
            raise BuildError(f"The archive has more than {_MAX_MEMBERS} entries")
        budget = max_bytes * _EXPANSION_FACTOR
        total = 0
        count = 0
        for info in members:
            mode = info.external_attr >> 16
            if info.is_dir() or stat.S_ISLNK(mode):
                continue
            rel = safe_member(info.filename)
            if rel is None:
                raise BuildError(f"Unsafe path in archive: {info.filename[:200]}")
            total += info.file_size
            if total > budget:
                raise BuildError(f"The archive expands beyond {budget // (1024 * 1024)} MB")
            dest = target.joinpath(*rel.parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                with archive.open(info) as source, open(dest, "xb") as sink:
                    shutil.copyfileobj(source, sink, 1024 * 1024)
            except FileExistsError:
                raise BuildError(f"Duplicate path in archive: {info.filename[:200]}")
            except (zipfile.BadZipFile, OSError, RuntimeError, EOFError) as exc:
                raise BuildError(f"Cannot extract {info.filename[:200]}: {exc}") from exc
            if mode & 0o111:
                dest.chmod(0o755)
            count += 1
    if not count:
        raise BuildError("The archive contains no files")
    return count


def context_root(extracted: Path, dockerfile: str) -> Path:
    """The ZIP root, or its single top-level folder (the usual "Compress folder" result)."""
    if (extracted / dockerfile).is_file():
        return extracted
    entries = [p for p in extracted.iterdir() if p.name not in ("__MACOSX",)]
    if len(entries) == 1 and entries[0].is_dir() and (entries[0] / dockerfile).is_file():
        return entries[0]
    raise BuildError(f"No {dockerfile} found at the root of the archive (or of its single top-level folder)")


def _ignore_rules(root: Path) -> List[Tuple[bool, str]]:
    path = root / ".dockerignore"
    if not path.is_file():
        return []
    rules = []
    for line in path.read_text("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negate = line.startswith("!")
        pattern = line[1:].strip() if negate else line
        pattern = pattern.replace("\\", "/").strip("/")
        if pattern.startswith("./"):
            pattern = pattern[2:]
        if pattern:
            rules.append((negate, pattern))
    return rules


def _ignored(rel: str, rules: List[Tuple[bool, str]]) -> bool:
    result = False
    for negate, pattern in rules:
        loose = pattern.replace("**/", "*").replace("/**", "/*")
        inside_dir = "*" not in pattern and "?" not in pattern and rel.startswith(pattern + "/")
        if inside_dir or fnmatch.fnmatchcase(rel, pattern) or fnmatch.fnmatchcase(rel, loose):
            result = not negate
    return result


def pack_context(root: Path, dockerfile: str, tar_path: Path) -> Tuple[int, int]:
    rules = _ignore_rules(root)
    keep = {dockerfile, ".dockerignore"}
    files = 0
    with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as tar:
        for current, dirs, names in os.walk(root):
            dirs.sort()
            for name in sorted(names):
                full = Path(current) / name
                rel = full.relative_to(root).as_posix()
                if rel not in keep and _ignored(rel, rules):
                    continue
                if not full.is_file() or full.is_symlink():
                    continue
                info = tar.gettarinfo(str(full), arcname=rel)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with full.open("rb") as handle:
                    tar.addfile(info, handle)
                files += 1
    return files, tar_path.stat().st_size


# --------------------------------------------------------------------------- #
# Build job
# --------------------------------------------------------------------------- #


_README_NAMES = ("readme.md", "readme.markdown", "readme.txt", "readme")


def find_readme(root: Path) -> str:
    """The project's README at the context root (regular file only), as text."""
    try:
        candidates = {entry.name.lower(): entry for entry in root.iterdir()}
    except OSError:
        return ""
    for name in _README_NAMES:
        entry = candidates.get(name)
        if entry is None or entry.is_symlink() or not entry.is_file():
            continue
        try:
            with entry.open("rb") as handle:
                raw = handle.read(docker_registry.README_MAX_CHARS * 4)
        except OSError:
            return ""
        return raw.decode("utf-8", errors="replace").lstrip("\ufeff")[:docker_registry.README_MAX_CHARS]
    return ""


def acquire_slot() -> bool:
    return _slots.acquire(blocking=False)


def release_slot() -> None:
    _slots.release()


class BuildJob:
    """Runs in a worker thread; ``events`` yields dicts until a final ``None``."""

    def __init__(self, cfg: Dict[str, Any], archive: Path, workdir: Path, repository: str, tag: str,
                 dockerfile: str, who: str) -> None:
        self.cfg = cfg
        self.archive = archive
        self.workdir = workdir
        self.repository = repository
        self.tag = tag
        self.dockerfile = dockerfile
        self.who = who
        self.reference = docker_registry.image_ref(cfg, repository, tag)
        self.events: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()
        self.cancelled = threading.Event()
        self._sock: Optional[socket.socket] = None
        self.readme = ""
        self._deadline = time.monotonic() + int(cfg.get("build_timeout_seconds") or 3600)

    # -- plumbing ---------------------------------------------------------------

    def emit(self, kind: str, **data: Any) -> None:
        self.events.put({"event": kind, **data})

    def cancel(self) -> None:
        """Abort the running engine call; the socket is shut down so a blocked read returns at once."""
        self.cancelled.set()
        sock = self._sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def _check(self) -> None:
        if self.cancelled.is_set():
            raise BuildError("Cancelled")
        if time.monotonic() > self._deadline:
            raise BuildError(f"Timed out after {self.cfg.get('build_timeout_seconds')} seconds")

    def _stream(self, method: str, path: str, *, body: Any = None,
                headers: Optional[Dict[str, str]] = None) -> Iterator[Dict[str, Any]]:
        """Newline-delimited JSON messages of a long-running engine call."""
        self._check()
        # Long silent RUN steps are normal; only the overall build deadline limits a call.
        conn = _connection(timeout=max(30.0, self._deadline - time.monotonic()))
        try:
            # http.client drops conn.sock once a response is marked close-on-end, so keep our own handle.
            conn.connect()
            self._sock = conn.sock
            if self.cancelled.is_set():
                raise BuildError("Cancelled")
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            if response.status >= 400:
                raw = response.read(65536).decode("utf-8", errors="replace")
                try:
                    message = json.loads(raw).get("message") or raw
                except ValueError:
                    message = raw
                raise BuildError(f"Docker engine HTTP {response.status}: {message.strip()[:500]}")
            buffer = b""
            while True:
                self._check()
                chunk = response.read1(65536) if hasattr(response, "read1") else response.read(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except ValueError:
                            yield {"stream": line.decode("utf-8", errors="replace") + "\n"}
            self._check()
            if buffer.strip():
                try:
                    yield json.loads(buffer)
                except ValueError:
                    pass
        except (OSError, http.client.HTTPException, ValueError) as exc:
            if self.cancelled.is_set():
                raise BuildError("Cancelled") from exc
            raise BuildError(f"Lost connection to the Docker engine: {exc}") from exc
        finally:
            self._sock = None
            conn.close()

    def _simple(self, method: str, path: str) -> Tuple[int, str]:
        conn = _connection()
        try:
            conn.request(method, path)
            response = conn.getresponse()
            return response.status, response.read(65536).decode("utf-8", errors="replace")
        except (OSError, http.client.HTTPException) as exc:
            return 0, str(exc)
        finally:
            conn.close()

    # -- phases -----------------------------------------------------------------

    def _prepare(self) -> Path:
        self.emit("step", phase="extract")
        extracted = self.workdir / "src"
        extracted.mkdir()
        limit = int(self.cfg.get("max_context_mb") or 1) * 1024 * 1024
        count = extract_zip(self.archive, extracted, limit)
        self.archive.unlink(missing_ok=True)
        root = context_root(extracted, self.dockerfile)
        self.emit("log", text=f"Extracted {count} files" + (f" (context: {root.name}/)" if root != extracted else ""))
        self._check()
        tar_path = self.workdir / "context.tar"
        files, size = pack_context(root, self.dockerfile, tar_path)
        if size > limit:
            raise BuildError(f"The build context is {size // (1024 * 1024)} MB; the limit is "
                             f"{limit // (1024 * 1024)} MB")
        self.emit("log", text=f"Build context: {files} files, {size / (1024 * 1024):.1f} MB")
        self.readme = find_readme(root)
        if self.readme:
            self.emit("log", text="Found README - it becomes the image overview in the Docker catalog")
        shutil.rmtree(extracted, ignore_errors=True)
        return tar_path

    def _build(self, tar_path: Path) -> str:
        self.emit("step", phase="build")
        params = {"t": self.reference, "dockerfile": self.dockerfile, "rm": "1", "forcerm": "1",
                  "labels": json.dumps({"org.opencontainers.image.vendor": "PAKAL",
                                        "pakal.built-by": self.who[:120]})}
        headers = {"Content-Type": "application/x-tar", "Content-Length": str(tar_path.stat().st_size),
                   "X-Registry-Config": _b64json({docker_registry.registry_host(self.cfg): _registry_auth(self.cfg)})}
        image_id = ""
        with tar_path.open("rb") as body:
            for message in self._stream("POST", f"/build?{urlencode(params)}", body=body, headers=headers):
                if message.get("error") or message.get("errorDetail"):
                    detail = (message.get("errorDetail") or {}).get("message") or message.get("error")
                    raise BuildError(f"Build failed: {detail}")
                if "stream" in message:
                    text = str(message["stream"]).rstrip("\n")
                    if text.strip():
                        self.emit("log", text=text)
                elif "status" in message:
                    self._progress(message)
                aux = message.get("aux") or {}
                if isinstance(aux, dict) and aux.get("ID"):
                    image_id = aux["ID"]
        tar_path.unlink(missing_ok=True)
        if not image_id:
            status, text = self._simple("GET", f"/images/{quote(self.reference, safe='/:')}/json")
            if status != 200:
                raise BuildError("The build finished without producing an image")
            image_id = json.loads(text).get("Id", "")
        self.emit("log", text=f"Built {image_id[:19]} → {self.reference}")
        return image_id

    def _progress(self, message: Dict[str, Any]) -> None:
        detail = message.get("progressDetail") or {}
        if message.get("id") and detail.get("total"):
            self.emit("progress", id=message["id"], status=message.get("status", ""),
                      current=int(detail.get("current") or 0), total=int(detail["total"]))
        else:
            text = " ".join(str(x) for x in (message.get("id"), message.get("status")) if x)
            if text:
                self.emit("layer", id=message.get("id") or "", text=text)

    def _push(self) -> Dict[str, Any]:
        self.emit("step", phase="push")
        name = self.reference.rsplit(":", 1)[0]
        headers = {"X-Registry-Auth": _b64json(_registry_auth(self.cfg))}
        result: Dict[str, Any] = {}
        path = f"/images/{quote(name, safe='/:')}/push?{urlencode({'tag': self.tag})}"
        for message in self._stream("POST", path, headers=headers):
            if message.get("error") or message.get("errorDetail"):
                detail = (message.get("errorDetail") or {}).get("message") or message.get("error")
                raise BuildError(f"Push failed: {detail}")
            aux = message.get("aux") or {}
            if isinstance(aux, dict) and aux.get("Digest"):
                result = {"digest": aux["Digest"], "size": aux.get("Size")}
            if "status" in message:
                # Engines with the containerd image store confirm only through this status line, without aux.
                confirmed = _PUSHED_RE.search(str(message["status"]))
                if confirmed and not result:
                    result = {"digest": confirmed.group(1), "size": int(confirmed.group(2))}
                self._progress(message)
        if not result:
            raise BuildError("The registry did not confirm the push")
        return result

    def _cleanup_image(self) -> None:
        status, _text = self._simple("DELETE", f"/images/{quote(self.reference, safe='/:')}?noprune=0")
        if status in (200, 404):
            self.emit("log", text=f"Removed the local tag {self.reference}")

    def run(self) -> None:
        started = time.monotonic()
        built = False
        try:
            self.emit("start", reference=self.reference, repository=self.repository, tag=self.tag)
            tar_path = self._prepare()
            self._build(tar_path)
            built = True
            pushed = self._push()
            self.emit("step", phase="cleanup")
            self._cleanup_image()
            built = False
            if self.readme:
                try:
                    docker_registry.save_readme(self.repository, self.readme, self.tag)
                except Exception as exc:  # noqa: BLE001 - the image is pushed; the overview is optional
                    log.warning("Cannot store the README of %s: %s", self.repository, exc)
            docker_registry.clear_cache()
            seconds = int(time.monotonic() - started)
            self.emit("done", reference=self.reference, repository=self.repository, tag=self.tag,
                      digest=pushed.get("digest"), size=pushed.get("size"), seconds=seconds)
            log.info("Docker build %s pushed by %s in %ss (%s)", self.reference, self.who, seconds, pushed.get("digest"))
        except BuildError as exc:
            self.emit("error", message=str(exc))
            log.info("Docker build %s by %s failed: %s", self.reference, self.who, exc)
        except Exception as exc:  # noqa: BLE001 - the stream must always end with an event
            log.exception("Docker build %s crashed", self.reference)
            self.emit("error", message=f"Internal error: {type(exc).__name__}: {exc}"[:500])
        finally:
            if built:
                self._cleanup_image()
            shutil.rmtree(self.workdir, ignore_errors=True)
            release_slot()
            self.events.put(None)


def new_workdir() -> Path:
    config.DOCKER_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="build-", dir=config.DOCKER_BUILD_DIR))


def cleanup_stale_workdirs() -> None:
    """Leftovers of builds interrupted by a restart."""
    try:
        for entry in config.DOCKER_BUILD_DIR.glob("build-*"):
            shutil.rmtree(entry, ignore_errors=True)
    except OSError as exc:
        log.debug("Cannot clean %s: %s", config.DOCKER_BUILD_DIR, exc)
