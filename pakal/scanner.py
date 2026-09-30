"""
Installer share scanner.

Share layout:
    <APPS_ROOT>/<AppName>/<installer>                  primary installers
    <APPS_ROOT>/<AppName>/<version|os>/<installer>     up to MAX_SCAN_DEPTH folder levels
    <APPS_ROOT>/<AppName>/info.json                    optional metadata
    <APPS_ROOT>/<AppName>/icon.png                     optional custom icon

Only primary installers are indexed. Clutter directories are never entered, offline layouts and
payload directories collapse into a single launcher (plus ISOs) that carries the total bundle size.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote

from . import config, icons
from .knowledge import (
    ALIAS_MAP, BUILTIN_APP_ICONS, CORE_APP_KEYS, KNOWN_APPS, category_labels, guess_category, match_known_app,
    normalize_key, resolve_category,
)
from .models import AppEntry, AppFile, Release, ScanResult

log = logging.getLogger("pakal.scanner")

ICON_CANDIDATES: Tuple[str, ...] = (
    "icon.svg", "icon.png", "icon.ico", "icon.jpg", "icon.jpeg", "icon.webp", "logo.svg", "logo.png",
)

IGNORED_DIR_NAMES = {
    "extentions", "extensions", "vs_layout", "payloads", "payload", "node_modules", "bin", "temp", "tmp",
    "cache", ".cache", "$recycle.bin", "#recycle", "@eadir", "system volume information", ".snapshot",
    "~snapshot", "__macosx", ".git", ".trash", "thumbs", "packages", "resources", "locales", "lib",
    "obj", "logs", "certificates", "archive.cache", "debug", "debugger", "symbols", "redist",
}
LAYOUT_MARKER_FILES = {
    "catalog.json", "channelmanifest.json", "layout.json", "response.json", "vs_installer.opc",
    "vs_setup_bootstrapper.json",
}
LAYOUT_DIR_NAMES = {"vs_layout", "payloads", "payload", "layout"}
EXTRACTED_APP_DIR_NAMES = {"resources", "locales", "bin", "lib"}

_HASH_NAME_RE = re.compile(
    r"(?i)^(?:[0-9a-f]{16,}|\{?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\}?)$"
)
_NOISE_FILE_RE = re.compile(
    r"(?i)^(?:unins\d{0,3}|uninstall[\w.-]*|[\w.-]*-srv\d*|crashpad_handler|elevation_service|"
    r"notification_helper|createdump|squirrel|update|updater|[\w.-]*\.vshost|vsdbg(?:-ui)?|"
    r"cpptools[\w.-]*|opendebugad7|msvsmon|vsjitdebugger|clang[\w.-]*|lldb[\w.-]*|gdb[\w.-]*|"
    r"crashreporter|pingsender|maintenanceservice[\w.-]*|elevate|[\w.-]*helper|[\w.-]*_stub|"
    r"setup_helper|dotnet-[\w.-]*-host)$"
)
_PRIMARY_NAME_RE = re.compile(
    r"(?i)(setup|install|bootstrap|launcher|offline|standalone|full|complete|"
    r"vs_(?:community|professional|enterprise|buildtools))"
)

# --------------------------------------------------------------------------- #
# Version extraction & OS detection
# --------------------------------------------------------------------------- #

_ARCH_RE = re.compile(
    r"(?i)(?:x86[_-]?64|amd64|arm64|aarch64|armhf|win32|win64|i[3-6]86|x64|x86|(?:32|64)[-_ ]?bit)"
)
_SEMVER_RE = re.compile(
    r"(?i)(?<!\d)(?<!\d\.)(\d+(?:\.\d+){1,3})(?:[-_.+]?(alpha|beta|rc|preview|pre)[-_.]?(\d+)?)?(?!\d)"
)
_VPREFIX_RE = re.compile(r"(?i)v(?:er|ersion)?[ ._-]?(\d{1,6})(?![\d.])")
_PLAIN_NUMBER_RE = re.compile(r"(?<!\d)(\d{2,8})(?!\d)")
_DIR_VERSION_RE = re.compile(r"(?i)^v?(?:er|ersion)?[ ._-]?(\d+)$")

_MAC_TOKENS = {"mac", "macos", "osx", "darwin", "apple", "macintosh", "universal2"}
_LINUX_TOKENS = {"linux", "ubuntu", "debian", "rhel", "centos", "fedora", "redhat", "suse", "opensuse",
                 "deb", "rpm", "appimage", "el7", "el8", "el9", "alpine", "rocky", "alma", "gnu"}
_WINDOWS_TOKENS = {"win", "windows", "win32", "win64", "win10", "win11", "x64", "x86", "amd64", "msvc", "setup",
                   "installer", "portable"}
PLATFORM_ORDER = ["Windows", "Linux", "macOS", "Universal"]


def installer_extension(filename: str) -> Optional[str]:
    lower = filename.lower()
    if lower.startswith((".", "~$")):
        return None
    for ext in sorted(config.INSTALLER_EXTENSIONS, key=len, reverse=True):
        if lower.endswith(ext):
            return ext
    return None


def _stem(filename: str, ext: str) -> str:
    return filename[: -len(ext)] if ext and filename.lower().endswith(ext) else filename


def is_primary_candidate(filename: str) -> Optional[str]:
    ext = installer_extension(filename)
    if not ext:
        return None
    stem = _stem(filename, ext)
    if _HASH_NAME_RE.match(stem) or _NOISE_FILE_RE.match(stem):
        return None
    return ext


def _format_semver(match: re.Match) -> str:
    version = match.group(1)
    if match.group(2):
        version += f"-{match.group(2).lower()}{match.group(3) or ''}"
    return version


def extract_version_from_name(filename: str, ext: str) -> Optional[str]:
    cleaned = _ARCH_RE.sub(" ", _stem(filename, ext))
    semver = _SEMVER_RE.search(cleaned)
    if semver:
        return _format_semver(semver)
    vprefix = _VPREFIX_RE.search(cleaned)
    if vprefix:
        return f"{int(vprefix.group(1))}.0"
    for plain in _PLAIN_NUMBER_RE.finditer(cleaned):
        if plain.group(1) not in {"32", "64", "86"}:
            return plain.group(1)
    return None


def extract_version(filename: str, ext: str, parent_parts: Sequence[str]) -> Optional[str]:
    version = extract_version_from_name(filename, ext)
    if version:
        return version
    for part in reversed(parent_parts):
        cleaned = _ARCH_RE.sub(" ", part)
        semver = _SEMVER_RE.search(cleaned)
        if semver:
            return _format_semver(semver)
        single = _DIR_VERSION_RE.match(cleaned.strip())
        if single:
            return f"{int(single.group(1))}.0"
    return None


def version_sort_key(version: Optional[str]) -> Tuple[Tuple[int, ...], int, int]:
    if not version:
        return ((), -1, 0)
    match = re.match(r"([\d.]+)(?:-([a-z]+)(\d*))?", version)
    if not match:
        return ((), -1, 0)
    numbers = tuple(int(n) for n in match.group(1).split(".") if n.isdigit())
    is_release = 0 if match.group(2) else 1
    pre_number = int(match.group(3)) if match.group(3) else 0
    return (numbers, is_release, pre_number)


# Installer type hierarchy: lower rank wins when choosing the primary / "latest" file.
EXTENSION_PRIORITY: Dict[str, int] = {".exe": 0, ".msi": 1, ".iso": 2, ".zip": 3, ".tar.gz": 3}

# Relevance tiers of a file within its application folder.
RELEVANCE_MATCH, RELEVANCE_GENERIC, RELEVANCE_FOREIGN = 0, 1, 2

_GENERIC_WORDS = {
    "setup", "install", "installer", "offline", "online", "full", "complete", "standalone", "portable",
    "release", "stable", "latest", "final", "update", "upgrade", "windows", "linux", "macos", "darwin",
    "universal", "bits", "user", "system", "machine", "community", "professional", "enterprise", "ultimate",
    "express", "edition", "bootstrapper", "bootstrap", "launcher", "client", "server", "desktop", "package",
    "image", "disk", "media", "lite", "core", "runtime", "multilingual", "english", "hebrew", "signed",
    "build", "preview", "beta", "alpha", "nightly", "insider", "only", "main", "base", "free", "version",
}


def file_relevance(filename: str, ext: str, app_tokens: Sequence[str], known_key: Optional[str]) -> int:
    """Whether an installer belongs to its folder's app (e.g. a stray flutter_*.zip inside VSCode does not)."""
    stem = _stem(filename, ext)
    norm = normalize_key(stem)
    if any(token in norm for token in app_tokens):
        return RELEVANCE_MATCH
    other = match_known_app(stem)
    if other and other != known_key:
        return RELEVANCE_FOREIGN
    words = re.findall(r"[a-z]{4,}", _ARCH_RE.sub(" ", stem.lower()))
    if any(word not in _GENERIC_WORDS for word in words):
        return RELEVANCE_FOREIGN
    return RELEVANCE_GENERIC


def sort_files(files: List[AppFile]) -> List[AppFile]:
    """Relevance, then installer type (.exe > .msi > .iso > archives), then SemVer and mtime (newest first)."""
    ordered = sorted(files, key=lambda f: (version_sort_key(f.version), f.modified_ts), reverse=True)
    ordered.sort(key=lambda f: (f.relevance, EXTENSION_PRIORITY.get(f.ext, 9)))
    return ordered


def detect_os(parent_parts: Sequence[str], filename: str, ext: str) -> str:
    tokens: set = set()
    for part in list(parent_parts) + [filename]:
        tokens.update(t for t in re.split(r"[^a-z0-9]+", part.lower()) if t)
    if ext == ".dmg" or tokens & _MAC_TOKENS or any(t.startswith(("macos", "osx")) for t in tokens):
        return "macOS"
    if ext in (".tar.gz", ".deb", ".rpm", ".appimage") or tokens & _LINUX_TOKENS \
            or any(t.startswith("linux") for t in tokens):
        return "Linux"
    if ext in (".exe", ".msi", ".zip") or tokens & _WINDOWS_TOKENS or any(t.startswith("win") for t in tokens):
        return "Windows"
    return "Universal"


def human_size(num_bytes: int) -> str:
    if num_bytes >= 1024 ** 3:
        return f"{num_bytes / 1024 ** 3:.2f} GB"
    if num_bytes >= 1024 ** 2:
        return f"{num_bytes / 1024 ** 2:.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.0f} KB"
    return f"{num_bytes} B"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9\u0590-\u05ff]+", "-", value.lower().replace("+", "p")).strip("-")
    return slug or "app"


def download_url(rel_path: str) -> str:
    return "/api/download/" + quote(rel_path, safe="/")


# --------------------------------------------------------------------------- #
# Directory walking
# --------------------------------------------------------------------------- #


def is_ignored_dir(name: str) -> bool:
    lower = name.lower()
    return (
        lower in IGNORED_DIR_NAMES
        or lower.startswith((".", "~"))
        or "," in lower
        or bool(_HASH_NAME_RE.match(lower))
    )


def read_json(path: Path) -> Optional[Any]:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        log.warning("Failed to read %s: %s", path, exc)
        return None


def _find_folder_icon(app_dir: Path, meta: Dict[str, Any]) -> Optional[Path]:
    candidates: List[str] = []
    if isinstance(meta.get("icon"), str) and meta["icon"].strip():
        candidates.append(meta["icon"].strip())
    candidates.extend(ICON_CANDIDATES)
    app_root = app_dir.resolve()
    for name in candidates:
        path = app_dir / name
        try:
            if path.is_file() and path.resolve().is_relative_to(app_root):
                return path
        except OSError:
            continue
    return None


def _dir_usage(path: Path) -> Tuple[int, int]:
    """Total bytes and file count below a directory (bundle size of an offline layout)."""
    total, count = 0, 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            count += 1
                    except OSError:
                        continue
        except OSError as exc:
            log.debug("Cannot measure %s: %s", current, exc)
    return total, count


def _primary_score(entry: os.DirEntry, app_tokens: List[str]) -> Tuple[int, int]:
    name = entry.name.lower()
    norm = normalize_key(name)
    score = 0
    if name.endswith(".iso"):
        score += 50
    if _PRIMARY_NAME_RE.search(name):
        score += 30
    if any(token and token in norm for token in app_tokens):
        score += 20
    if name.startswith(("vs_setup", "vs_installer", "vs_bootstrapper")):
        score -= 25
    try:
        size = entry.stat(follow_symlinks=False).st_size
    except OSError:
        size = 0
    return score, size


def _pick_primaries(installers: List[os.DirEntry], app_tokens: List[str]) -> List[os.DirEntry]:
    """From a payload/layout directory keep every ISO plus the single best launcher."""
    isos = [e for e in installers if e.name.lower().endswith(".iso")]
    others = [e for e in installers if not e.name.lower().endswith(".iso")]
    picked = list(isos)
    if others:
        picked.append(max(others, key=lambda e: _primary_score(e, app_tokens)))
    return picked


def _looks_like_extracted_app(files: List[os.DirEntry], dirs: List[os.DirEntry]) -> bool:
    if any(f.name.lower().endswith(".dll") for f in files):
        return True
    return bool({d.name.lower() for d in dirs} & EXTRACTED_APP_DIR_NAMES)


def walk_app(app_dir: Path, app_tokens: List[str]) -> List[Tuple[os.DirEntry, Optional[Tuple[int, int]]]]:
    """Collect primary installers of one application as (entry, bundle_usage) tuples."""
    results: List[Tuple[os.DirEntry, Optional[Tuple[int, int]]]] = []
    stack: List[Tuple[Path, int]] = [(app_dir, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError as exc:
            log.warning("Cannot read %s: %s", current, exc)
            continue

        files = [e for e in entries if e.is_file(follow_symlinks=False)]
        dirs = [e for e in entries if e.is_dir(follow_symlinks=False)]
        file_names = {f.name.lower() for f in files}
        dir_names = {d.name.lower() for d in dirs}

        is_layout = bool(file_names & LAYOUT_MARKER_FILES) or bool(dir_names & LAYOUT_DIR_NAMES) \
            or sum("," in d.name for d in dirs) >= 3
        if depth > 0 and not is_layout and _looks_like_extracted_app(files, dirs):
            continue

        installers = [f for f in files if is_primary_candidate(f.name)]
        is_payload = False
        if len(installers) > config.PAYLOAD_THRESHOLD:
            named = sum(1 for f in installers if any(t in normalize_key(f.name) for t in app_tokens))
            is_payload = named * 2 < len(installers)
        if is_layout or is_payload:
            primaries = _pick_primaries(installers, app_tokens)
            if primaries:
                usage = _dir_usage(current)
                for entry in primaries:
                    results.append((entry, None if entry.name.lower().endswith(".iso") else usage))
            continue

        results.extend((f, None) for f in installers)
        if depth < config.MAX_SCAN_DEPTH:
            stack.extend((Path(d.path), depth + 1) for d in dirs if not is_ignored_dir(d.name))
    return results


def _collect_files(app_dir: Path, app_name: str, known_key: Optional[str]) -> List[AppFile]:
    app_tokens = [t for t in {normalize_key(app_dir.name), normalize_key(app_name), known_key or ""} if len(t) >= 3]
    match_tokens = list(dict.fromkeys(
        app_tokens + [alias for alias, key in ALIAS_MAP.items() if known_key and key == known_key and len(alias) >= 3]
    ))
    files: List[AppFile] = []
    for entry, bundle in walk_app(app_dir, app_tokens):
        ext = installer_extension(entry.name) or ""
        try:
            stat = entry.stat(follow_symlinks=False)
        except OSError as exc:
            log.warning("Cannot stat %s: %s", entry.path, exc)
            continue
        full_path = Path(entry.path)
        parent_parts = full_path.relative_to(app_dir).parts[:-1]
        rel_path = full_path.relative_to(config.APPS_ROOT).as_posix()
        files.append(AppFile(
            filename=entry.name,
            rel_path=rel_path,
            download_url=download_url(rel_path),
            version=extract_version(entry.name, ext, parent_parts),
            os=detect_os(parent_parts, entry.name, ext),
            ext=ext,
            size_bytes=stat.st_size,
            size_human=human_size(stat.st_size),
            modified=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
            modified_ts=stat.st_mtime,
            bundle_size_bytes=bundle[0] if bundle else None,
            bundle_size_human=human_size(bundle[0]) if bundle else None,
            bundle_files=bundle[1] if bundle else None,
            relevance=file_relevance(entry.name, ext, match_tokens, known_key),
        ))
    return sort_files(files)


def group_releases(files: List[AppFile]) -> List[Release]:
    groups: Dict[Optional[str], List[AppFile]] = {}
    for file in files:
        groups.setdefault(file.version, []).append(file)
    releases = []
    for version, group in groups.items():
        size = sum(f.bundle_size_bytes or f.size_bytes for f in group)
        releases.append(Release(
            version=version,
            modified=max(group, key=lambda f: f.modified_ts).modified,
            total_size_bytes=size,
            total_size_human=human_size(size),
            files=group,
        ))
    releases.sort(key=lambda r: (version_sort_key(r.version), max(f.modified_ts for f in r.files)), reverse=True)
    return releases


def with_files(app: AppEntry, files: List[AppFile]) -> AppEntry:
    """Recompute every file-derived field (releases, latest, platforms, totals)."""
    files = sort_files(files)
    latest_version = None
    if files:
        peers = [f for f in files if f.relevance == files[0].relevance and f.version]
        latest_version = files[0].version or (
            max(peers, key=lambda f: (version_sort_key(f.version), f.modified_ts)).version if peers else None)
    latest_by_os: Dict[str, AppFile] = {}
    for file in files:
        latest_by_os.setdefault(file.os, file)
    platforms = sorted(latest_by_os, key=lambda p: PLATFORM_ORDER.index(p) if p in PLATFORM_ORDER else 99)
    total = sum(f.bundle_size_bytes or f.size_bytes for f in files)
    newest = max(files, key=lambda f: f.modified_ts) if files else None
    return app.model_copy(update={
        "files": files,
        "releases": group_releases(files),
        "latest": files[0] if files else None,
        "latest_version": latest_version,
        "latest_by_os": latest_by_os,
        "platforms": platforms,
        "total_size_bytes": total,
        "total_size_human": human_size(total),
        "updated": newest.modified if newest else None,
        "updated_ts": newest.modified_ts if newest else 0,
    })


ICON_SOURCE_EXTENSIONS = (".exe", ".msi")
MAX_ICON_CANDIDATES = 4


def _icon_candidates(files: List[AppFile]) -> List[AppFile]:
    """Installers to extract a brand icon from: own EXEs first, then MSIs (files are already relevance-sorted)."""
    own = [f for f in files if f.relevance != RELEVANCE_FOREIGN] or files
    ordered: List[AppFile] = []
    for ext in ICON_SOURCE_EXTENSIONS:
        matches = [f for f in own if f.ext == ext]
        named = [f for f in matches if not f.filename.lower().startswith(("vs_setup", "vs_installer"))]
        ordered.extend(named + [f for f in matches if f not in named])
    return ordered[:MAX_ICON_CANDIDATES]


def _resolve_icon(app_id: str, folder_icon: Optional[Path], files: List[AppFile],
                  known_key: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if folder_icon:
        try:
            return f"/api/icon/{quote(app_id)}?v={int(folder_icon.stat().st_mtime)}", "folder"
        except OSError:
            pass
    for candidate in _icon_candidates(files):
        name = icons.extract_installer_icon(config.APPS_ROOT / candidate.rel_path, candidate.rel_path,
                                            candidate.size_bytes, candidate.modified_ts)
        url = icons.extracted_url(name)
        if url:
            return url, candidate.ext.lstrip(".")
    builtin = icons.builtin_icon_url(BUILTIN_APP_ICONS.get(known_key or ""))
    if builtin:
        return builtin, "builtin"
    return None, None


def build_app(app_dir: Path, used_ids: set) -> Optional[Tuple[AppEntry, Optional[Path]]]:
    raw_meta = read_json(app_dir / "info.json")
    meta: Dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}

    folder = app_dir.name
    name = str(meta.get("name") or folder).strip()
    known_key = match_known_app(folder) or match_known_app(name)
    known = KNOWN_APPS.get(known_key) if known_key else None

    files = _collect_files(app_dir, name, known_key)
    if not files:
        return None

    category = resolve_category(meta.get("category")) or (known[0] if known else guess_category(name))
    label_he, label_en = category_labels(category)
    description_he = str(meta.get("description") or meta.get("description_he") or "").strip() \
        or (known[1] if known else f"{name} - זמין להתקנה מהמאגר הארגוני ({label_he}).")
    description_en = str(meta.get("description_en") or "").strip() \
        or (known[2] if known else f"{name} - available from the enterprise repository ({label_en}).")

    tags = meta.get("tags")
    if not isinstance(tags, list) or not tags:
        tags = list(known[3]) if known else []
    tags = [str(t).strip() for t in tags if str(t).strip()][:8]

    app_id = slugify(folder)
    base_id, counter = app_id, 2
    while app_id in used_ids:
        app_id = f"{base_id}-{counter}"
        counter += 1
    used_ids.add(app_id)

    folder_icon = _find_folder_icon(app_dir, meta)
    icon_url, icon_source = _resolve_icon(app_id, folder_icon, files, known_key)
    featured = meta.get("featured")
    homepage = meta.get("homepage") if isinstance(meta.get("homepage"), str) else None
    if homepage and not re.match(r"^https?://", homepage, re.I):
        homepage = None

    entry = AppEntry(
        id=app_id,
        name=name,
        folder=folder,
        description_he=description_he,
        description_en=description_en,
        category=category,
        tags=tags,
        icon_url=icon_url,
        icon_source=icon_source,
        homepage=homepage,
        featured=bool(featured) if featured is not None else (known_key in CORE_APP_KEYS),
        known_key=known_key,
    )
    return with_files(entry, files), folder_icon


def scan_share() -> ScanResult:
    apps: List[AppEntry] = []
    folder_icons: Dict[str, str] = {}
    used_ids: set = set()
    root = config.APPS_ROOT
    root_available = root.is_dir()

    if not root_available:
        log.warning("Apps root %s is not available (is the share mounted?)", root)
        return ScanResult(root_available=False)

    try:
        app_dirs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.lower())
    except OSError as exc:
        raise RuntimeError(f"Cannot read apps root {root}: {exc}") from exc

    for app_dir in app_dirs:
        if is_ignored_dir(app_dir.name) or app_dir.name.startswith(("_", "$", "#", "@")):
            continue
        try:
            built = build_app(app_dir, used_ids)
        except OSError as exc:
            log.warning("Skipping %s: %s", app_dir, exc)
            continue
        if built:
            entry, folder_icon = built
            apps.append(entry)
            if folder_icon:
                folder_icons[entry.id] = str(folder_icon)

    apps.sort(key=lambda a: a.name.lower())
    icons.prune_extracted(a.icon_url.rsplit("/", 1)[-1] for a in apps
                          if a.icon_source in ("exe", "msi") and a.icon_url)
    return ScanResult(apps=apps, folder_icons=folder_icons, root_available=True)
