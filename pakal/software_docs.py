"""Locate guide and license files for a catalog app and read them on demand.

Discovery looks beside the installers (the app folder and one level down) and inside zip
packages. Named guides match a prefix; any other root-level .txt or .md is kept as a fallback.
Only pointers are stored on the scan; the bytes are read when an API or bundle download asks.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

from .models import DocPointer, SoftwareDocs

log = logging.getLogger("pakal.docs")

MAX_DOC_BYTES = 256 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_DOCS = 24
MAX_ZIPS = 16
MAX_ZIP_BYTES = 8 * 1024 * 1024 * 1024
MAX_MEMBERS = 4000

# Case-insensitive prefixes. howto* covers HowTo.txt; setup* covers setup_guide.txt.
_GUIDE_PREFIXES = (
    "readme", "install", "instructions", "setup", "guide", "howto", "notes",
    "license", "licence", "copying",
)
_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst"}
_ROOT_TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
_SKIP_DIRS = {
    "node_modules", "bin", "packages", "payload", "payloads", "temp", "tmp", "cache",
    ".git", ".svn", "__pycache__",
}


def _basename(filename: str) -> str:
    return Path(str(filename).replace("\\", "/")).name


def _stem(filename: str) -> str:
    name = _basename(filename).lower()
    suffix = Path(name).suffix
    return Path(name).stem if suffix else name


def matches_guide(filename: str) -> bool:
    """True for text guides whose name starts with a known prefix, including extensionless files."""
    name = _basename(filename)
    if not name or name.startswith("."):
        return False
    suffix = Path(name).suffix.lower()
    if suffix and suffix not in _TEXT_SUFFIXES:
        return False
    return _stem(name).startswith(_GUIDE_PREFIXES)


def matches_root_text(filename: str) -> bool:
    return Path(_basename(filename)).suffix.lower() in _ROOT_TEXT_SUFFIXES


def is_doc_candidate(filename: str, at_root: bool) -> bool:
    if matches_guide(filename):
        return True
    return at_root and matches_root_text(filename)


def doc_type(filename: str, sample: str = "") -> str:
    lower = filename.lower()
    if lower.endswith((".md", ".markdown")):
        return "markdown"
    if lower.endswith((".txt", ".rst")):
        return "text"
    head = sample.lstrip()[:800]
    if head.startswith("#") or "```" in head:
        return "markdown"
    return "text"


def _name_rank(filename: str) -> int:
    stem = _stem(filename)
    for index, prefix in enumerate(_GUIDE_PREFIXES):
        if stem.startswith(prefix):
            return index
    return 50


def _skip_dir(name: str) -> bool:
    lower = name.lower()
    return name.startswith(("_", "$", "#", "@", ".")) or lower in _SKIP_DIRS


def _safe_member(name: str) -> bool:
    if not name or name.endswith("/") or name.startswith(("/", "\\")) or ":" in name:
        return False
    parts = name.replace("\\", "/").split("/")
    if any(part in ("", ".", "..") or part.lower() in _SKIP_DIRS for part in parts):
        return False
    if len(parts) > 2:
        return False
    return is_doc_candidate(parts[-1], at_root=len(parts) == 1)


def _rel(path: Path, root: Path) -> Optional[str]:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _gather(app_dir: Path) -> Tuple[List[Path], List[Path]]:
    loose: List[Path] = []
    zips: List[Path] = []

    def consider(path: Path) -> None:
        if not path.is_file():
            return
        try:
            size = path.stat().st_size
        except OSError:
            return
        if path.suffix.lower() == ".zip" and 0 < size <= MAX_ZIP_BYTES:
            zips.append(path)
        if size <= 0 or size > MAX_FILE_BYTES:
            return
        if is_doc_candidate(path.name, at_root=path.parent.resolve() == app_dir.resolve()):
            loose.append(path)

    try:
        children = list(app_dir.iterdir())
    except OSError as exc:
        log.warning("Docs: cannot list %s: %s", app_dir, exc)
        return loose, zips
    for child in children:
        try:
            if child.is_file():
                consider(child)
            elif child.is_dir() and not _skip_dir(child.name):
                for nested in child.iterdir():
                    if nested.is_file():
                        consider(nested)
        except OSError:
            continue
    return loose, zips[:MAX_ZIPS]


def _sort_key(filename: str, depth: int) -> Tuple:
    suffix = Path(_basename(filename)).suffix.lower()
    markdown = 0 if suffix in {".md", ".markdown"} else 1
    return (_name_rank(filename), depth, markdown, _basename(filename).lower())


def _zip_members(zips: List[Path]) -> List[Tuple[Path, str, str]]:
    """Return (zip path, member name, doc type) for every safe guide member."""
    found: List[Tuple[Path, str, str]] = []
    for archive_path in zips:
        try:
            with zipfile.ZipFile(archive_path) as archive:
                members = archive.infolist()
                if len(members) > MAX_MEMBERS:
                    members = members[:MAX_MEMBERS]
                for info in members:
                    if info.is_dir() or info.flag_bits & 0x1 or not _safe_member(info.filename):
                        continue
                    if info.file_size <= 0 or info.file_size > MAX_FILE_BYTES:
                        continue
                    sample = ""
                    if not Path(info.filename).suffix:
                        with archive.open(info, "r") as handle:
                            sample = handle.read(512).decode("utf-8", "replace")
                    found.append((
                        archive_path, info.filename, doc_type(Path(info.filename).name, sample),
                    ))
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            log.warning("Docs: skipping zip %s: %s", archive_path.name, exc)
    return found


def find_software_docs(app_dir: Path, root: Path) -> SoftwareDocs:
    loose, zips = _gather(app_dir)
    ranked: List[Tuple] = []

    def add(filename: str, depth: int, pointer: DocPointer) -> None:
        ranked.append((*_sort_key(filename, depth), pointer))

    for path in loose:
        rel = _rel(path, root)
        if not rel:
            continue
        try:
            depth = len(path.resolve().relative_to(app_dir.resolve()).parts) - 1
            sample = path.read_bytes()[:512].decode("utf-8", "replace")
        except (OSError, ValueError):
            continue
        add(path.name, depth, DocPointer(
            filename=path.name, type=doc_type(path.name, sample), rel_path=rel,
        ))
    for archive_path, member, kind_type in _zip_members(zips):
        rel = _rel(archive_path, root)
        if not rel:
            continue
        depth = member.replace("\\", "/").count("/")
        add(Path(member).name, depth + 1, DocPointer(
            filename=Path(member).name, type=kind_type, rel_path=rel, member=member,
        ))
    ranked.sort(key=lambda row: row[:4])
    files: List[DocPointer] = []
    seen: set = set()
    for row in ranked:
        pointer = row[4]
        key = pointer.filename.lower()
        if key in seen:
            continue
        seen.add(key)
        files.append(pointer)
        if len(files) >= MAX_DOCS:
            break
    return SoftwareDocs(files=files)


def _resolve(pointer: DocPointer, root: Path) -> Optional[Path]:
    rel = pointer.rel_path.replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    try:
        path = (root / rel).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        return None
    return path


def read_doc_text(pointer: DocPointer, root: Path) -> Optional[Tuple[str, bool]]:
    """Return (text, truncated). None when the file is missing or no longer a safe doc."""
    path = _resolve(pointer, root)
    if path is None:
        return None
    truncated = False
    try:
        if pointer.member:
            if not _safe_member(pointer.member):
                return None
            with zipfile.ZipFile(path) as archive:
                info = archive.getinfo(pointer.member)
                if info.is_dir() or info.flag_bits & 0x1 or not _safe_member(info.filename):
                    return None
                truncated = info.file_size > MAX_DOC_BYTES
                with archive.open(info, "r") as handle:
                    raw = handle.read(MAX_DOC_BYTES)
        else:
            size = path.stat().st_size
            truncated = size > MAX_DOC_BYTES
            with path.open("rb") as handle:
                raw = handle.read(MAX_DOC_BYTES)
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError) as exc:
        log.warning("Docs: cannot read %s: %s", pointer.rel_path, exc)
        return None
    text = raw.decode("utf-8-sig", "replace").replace("\x00", "")
    if truncated:
        text = text.rstrip() + "\n"
    return text, truncated
