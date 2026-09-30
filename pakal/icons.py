"""Air-gapped icon engine: EXE/MSI icon extraction, platform favicons, admin uploads and built-in SVGs."""

from __future__ import annotations

import codecs
import hashlib
import logging
import os
import re
import secrets
import ssl
import struct
import urllib.error
import urllib.request
import zlib
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

from . import config

log = logging.getLogger("pakal.icons")

try:  # optional at runtime: extraction is skipped when the library is unavailable
    from icoextract import IconExtractor, IconExtractorError
    from pefile import PEFormatError
except Exception:  # noqa: BLE001
    IconExtractor = None  # type: ignore[assignment]
    IconExtractorError = PEFormatError = Exception  # type: ignore[assignment,misc]

try:  # optional at runtime: MSI icons are skipped when the library is unavailable
    import olefile
except Exception:  # noqa: BLE001
    olefile = None  # type: ignore[assignment]

EXTRACTED_URL_PREFIX = "/static/extracted_icons/"
UPLOADS_URL_PREFIX = "/static/uploads/"
MAX_FAVICON_BYTES = 256 * 1024
MAX_HTML_BYTES = 512 * 1024
_SAFE_FILE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,120}$")

_SVG_FORBIDDEN = re.compile(
    r"(?is)<\s*script|<\s*foreignobject|<\s*iframe|<\s*embed|<\s*object|<!\s*entity|<!\s*doctype|"
    r"\bon[a-z]+\s*=|javascript\s*:|vbscript\s*:|@import|url\s*\(\s*['\"]?\s*(?!#|data:image/)"
)
_SVG_EXTERNAL_HREF = re.compile(r"""(?is)\bhref\s*=\s*["']\s*(?!#|data:image/(?:png|jpeg|gif|webp);)""")


# --------------------------------------------------------------------------- #
# Image validation
# --------------------------------------------------------------------------- #


def sniff_image(data: bytes) -> Optional[str]:
    """Return a safe file extension for supported image bytes, or None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\x00\x00\x01\x00"):
        return ".ico"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    head = data[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return ".svg"
    return None


def sanitize_svg(data: bytes) -> bytes:
    """Reject SVGs carrying scripts, event handlers, entities or external references."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("SVG must be UTF-8 encoded") from exc
    if _SVG_FORBIDDEN.search(text) or _SVG_EXTERNAL_HREF.search(text):
        raise ValueError("SVG contains scripts, event handlers or external references")
    if "<svg" not in text.lower():
        raise ValueError("Not an SVG document")
    return text.encode("utf-8")


def validate_image(data: bytes, max_bytes: int = config.MAX_UPLOAD_BYTES) -> Tuple[bytes, str]:
    if not data:
        raise ValueError("Empty file")
    if len(data) > max_bytes:
        raise ValueError(f"File exceeds {max_bytes // 1024} KB")
    ext = sniff_image(data)
    if not ext:
        raise ValueError("Unsupported image type (allowed: SVG, PNG, ICO, JPG, GIF, WEBP)")
    if ext == ".svg":
        data = sanitize_svg(data)
    return data, ext


# --------------------------------------------------------------------------- #
# Stored files (uploads & fetched favicons)
# --------------------------------------------------------------------------- #


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{secrets.token_hex(4)}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _safe_stem(kind: str, obj_id: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", obj_id.lower()).strip("-")[:60] or "item"
    return f"{kind}-{slug}"


def store_upload(kind: str, obj_id: str, data: bytes) -> str:
    """Validate and persist an uploaded icon; returns the stored file name."""
    data, ext = validate_image(data)
    name = f"{_safe_stem(kind, obj_id)}-{hashlib.sha1(data).hexdigest()[:10]}{ext}"
    _write_atomic(config.UPLOADS_DIR / name, data)
    return name


def delete_upload(filename: Optional[str]) -> None:
    if not filename or not _SAFE_FILE_RE.match(filename):
        return
    try:
        (config.UPLOADS_DIR / filename).unlink(missing_ok=True)
    except OSError as exc:
        log.warning("Cannot delete upload %s: %s", filename, exc)


def upload_url(filename: Optional[str]) -> Optional[str]:
    if filename and _SAFE_FILE_RE.match(filename) and (config.UPLOADS_DIR / filename).is_file():
        return UPLOADS_URL_PREFIX + filename
    return None


def extracted_url(filename: Optional[str]) -> Optional[str]:
    if filename and _SAFE_FILE_RE.match(filename) and (config.EXTRACTED_ICONS_DIR / filename).is_file():
        return EXTRACTED_URL_PREFIX + filename
    return None


def builtin_icon_url(name: Optional[str]) -> Optional[str]:
    if name and re.fullmatch(r"[a-z0-9-]{1,40}", name) and (config.BUILTIN_ICONS_DIR / f"{name}.svg").is_file():
        return f"/static/icons/{name}.svg"
    return None


# --------------------------------------------------------------------------- #
# Installer icon extraction (EXE / MSI -> highest-resolution PNG)
# --------------------------------------------------------------------------- #

# Part of the cache key: bumping it re-extracts every installer icon on the next scan.
ICON_ENGINE_VERSION = 2
EXTRACTED_PREFIX = "inst-"
_LEGACY_PREFIX = "exe-"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_ICON_GROUPS = 24
# The first icon group is what Windows Explorer shows; a larger group only wins when the first one is tiny.
PREFERRED_MIN_PX = 64
MAX_ICON_PX = 1024
MAX_MSI_STREAM_BYTES = 32 * 1024 * 1024
_EXTRACTION_ERRORS = (IconExtractorError, PEFormatError, OSError, ValueError, IndexError, KeyError, AttributeError,
                      struct.error, zlib.error, EOFError)


def extraction_available() -> bool:
    return config.EXTRACT_EXE_ICONS and IconExtractor is not None


def msi_extraction_available() -> bool:
    return extraction_available() and config.EXTRACT_MSI_ICONS and olefile is not None


def _ico_images(data: bytes) -> List[bytes]:
    """Image payloads (PNG or DIB) of every entry in an ICO file."""
    if len(data) < 6:
        return []
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or kind != 1:
        return []
    images: List[bytes] = []
    for index in range(min(count, 256)):
        entry = 6 + 16 * index
        if entry + 16 > len(data):
            break
        length, offset = struct.unpack_from("<II", data, entry + 8)
        if length and offset + length <= len(data):
            images.append(data[offset:offset + length])
    return images


def _image_info(image: bytes) -> Optional[Tuple[int, int, int]]:
    """(width, height, bits per pixel) read from the image itself - ICO directory sizes are unreliable."""
    if image.startswith(PNG_SIGNATURE) and len(image) >= 26 and image[12:16] == b"IHDR":
        width, height = struct.unpack_from(">II", image, 16)
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(image[25], 1)
        return width, height, image[24] * channels
    if len(image) >= 40:
        header, width, double_height, _planes, bpp = struct.unpack_from("<IiiHH", image, 0)
        if header >= 40 and width > 0 and double_height:
            return width, abs(double_height) // 2, bpp
    return None


def _largest_image(images: Iterable[bytes]) -> Optional[Tuple[int, int, bytes]]:
    """(min side, pixel depth, image) of the highest-resolution entry, e.g. the 256x256 PNG."""
    best: Optional[Tuple[int, int, int, bytes]] = None
    for image in images:
        info = _image_info(image)
        if not info:
            continue
        width, height, depth = info
        if not (0 < width <= MAX_ICON_PX and 0 < height <= MAX_ICON_PX):
            continue
        key = (width * height, depth)
        if best is None or key > (best[0], best[1]):
            best = (width * height, depth, min(width, height), image)
    return (best[2], best[1], best[3]) if best else None


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def _encode_png(width: int, height: int, rgba_rows: bytes) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (PNG_SIGNATURE + _png_chunk(b"IHDR", header) + _png_chunk(b"IDAT", zlib.compress(rgba_rows, 9))
            + _png_chunk(b"IEND", b""))


def _dib_to_png(image: bytes) -> Optional[bytes]:
    """Convert an ICO bitmap entry (BITMAPINFOHEADER + XOR bitmap + AND mask) into an RGBA PNG."""
    header, width, double_height, _planes, bpp, compression = struct.unpack_from("<IiiHHI", image, 0)
    colors_used = struct.unpack_from("<I", image, 32)[0]
    height = abs(double_height) // 2
    if compression not in (0, 3) or bpp not in (1, 4, 8, 24, 32) or not (0 < width <= MAX_ICON_PX) \
            or not (0 < height <= MAX_ICON_PX):
        return None
    offset = header + (12 if compression == 3 and header == 40 else 0)
    palette: List[Tuple[int, int, int]] = []
    if bpp <= 8:
        count = min(colors_used or (1 << bpp), 1 << bpp)
        palette = [(image[offset + 4 * i + 2], image[offset + 4 * i + 1], image[offset + 4 * i])
                   for i in range(count) if offset + 4 * i + 3 <= len(image)]
        offset += 4 * count
    xor_stride = ((width * bpp + 31) // 32) * 4
    and_stride = ((width + 31) // 32) * 4
    xor = image[offset:offset + xor_stride * height]
    if len(xor) < xor_stride * height:
        return None
    mask = image[offset + xor_stride * height:offset + (xor_stride + and_stride) * height]
    has_mask = len(mask) == and_stride * height
    use_alpha = bpp == 32 and any(xor[i] for i in range(3, len(xor), 4))
    top_down = double_height < 0
    pixel_mask = (1 << bpp) - 1 if bpp <= 8 else 0
    rows = bytearray()
    for y in range(height):
        source = y if top_down else height - 1 - y
        row = xor[source * xor_stride:(source + 1) * xor_stride]
        mask_row = mask[source * and_stride:(source + 1) * and_stride] if has_mask else b""
        rows.append(0)  # PNG filter type "None"
        for x in range(width):
            if bpp == 32:
                b, g, r, a = row[4 * x:4 * x + 4]
                if not use_alpha:
                    a = 255
            elif bpp == 24:
                b, g, r = row[3 * x:3 * x + 3]
                a = 255
            else:
                bit = x * bpp
                index = (row[bit >> 3] >> (8 - bpp - (bit & 7))) & pixel_mask
                r, g, b = palette[index] if index < len(palette) else (0, 0, 0)
                a = 255
            if not use_alpha and has_mask and (mask_row[x >> 3] >> (7 - (x & 7))) & 1:
                a = 0
            rows += bytes((r, g, b, a))
    return _encode_png(width, height, bytes(rows))


def _as_png(image: bytes) -> Optional[bytes]:
    return image if image.startswith(PNG_SIGNATURE) else _dib_to_png(image)


def _pe_best_image(extractor) -> Optional[Tuple[int, int, bytes]]:
    """Highest-resolution image of the first icon group, or of the largest group when the first one is tiny."""
    best: Optional[Tuple[int, int, bytes]] = None
    groups = extractor.list_group_icons()
    for index in range(min(len(groups), MAX_ICON_GROUPS)):
        try:
            top = _largest_image(_ico_images(extractor.get_icon(num=index).getvalue()))
        except _EXTRACTION_ERRORS as exc:
            log.debug("Skipping icon group %d: %s", index, exc)
            continue
        if not top:
            continue
        if index == 0 and top[0] >= PREFERRED_MIN_PX:
            return top
        if best is None or top[:2] > best[:2]:
            best = top
    return best


def _blob_best_image(blob: bytes) -> Optional[Tuple[int, int, bytes]]:
    """An MSI Icon-table entry is either a raw ICO file or a PE (EXE/DLL) carrying icon resources."""
    if blob.startswith(b"\x00\x00\x01\x00"):
        return _largest_image(_ico_images(blob))
    if blob.startswith(b"MZ"):
        return _pe_best_image(IconExtractor(data=blob))
    return None


# MSI databases are OLE compound files whose stream names are packed into the U+3800-U+483F range.
_MSI_TABLE_PREFIX = "\u4840"


def _msi_char(value: int) -> str:
    if value < 10:
        return chr(48 + value)
    if value < 36:
        return chr(55 + value)
    if value < 62:
        return chr(61 + value)
    return "." if value == 62 else "_"


def _msi_decode_name(name: str) -> str:
    out: List[str] = []
    for ch in name:
        code = ord(ch)
        if 0x3800 <= code < 0x4800:
            code -= 0x3800
            out.append(_msi_char(code & 0x3F))
            out.append(_msi_char((code >> 6) & 0x3F))
        elif 0x4800 <= code < 0x4840:
            out.append(_msi_char(code - 0x4800))
        else:
            out.append(ch)
    return "".join(out)


def _msi_codec(codepage: int) -> str:
    for candidate in (f"cp{codepage}" if codepage else "cp1252", "cp1252"):
        try:
            codecs.lookup(candidate)
            return candidate
        except LookupError:
            continue
    return "latin-1"


def _msi_strings(ole, streams: Dict[Tuple[bool, str], str]) -> Optional[Tuple[List[str], int]]:
    """The database string pool and the byte width of string references in table columns."""
    pool_name, data_name = streams.get((True, "_StringPool")), streams.get((True, "_StringData"))
    if not pool_name or not data_name:
        return None
    pool = ole.openstream(pool_name).read()
    data = ole.openstream(data_name).read()
    if len(pool) < 4:
        return None
    codepage = struct.unpack_from("<I", pool, 0)[0]
    codec = _msi_codec(codepage & 0xFFFF)
    words = struct.unpack_from(f"<{len(pool) // 2}H", pool)
    strings, offset, index, count = [""], 0, 1, len(words) // 2
    while index < count:
        length, refs = words[2 * index], words[2 * index + 1]
        if length == 0 and refs == 0:
            strings.append("")
            index += 1
            continue
        if length == 0:  # strings over 64 KB spill their length into the following entry
            if 2 * index + 3 >= len(words):
                break
            length = (words[2 * index + 3] << 16) + words[2 * index + 2]
            index += 2
        else:
            index += 1
        strings.append(data[offset:offset + length].decode(codec, errors="replace"))
        offset += length
    return strings, 3 if codepage & 0x80000000 else 2


def _msi_property(ole, streams: Dict[Tuple[bool, str], str], wanted: str) -> Optional[str]:
    """Read one value from the Property table (two string columns, stored column by column)."""
    table = streams.get((True, "Property"))
    pool = _msi_strings(ole, streams)
    if not table or not pool:
        return None
    strings, width = pool
    raw = ole.openstream(table).read()
    rows = len(raw) // (2 * width)

    def ref(position: int) -> int:
        return int.from_bytes(raw[position * width:(position + 1) * width], "little")

    for row in range(rows):
        key = ref(row)
        if 0 < key < len(strings) and strings[key] == wanted:
            value = ref(rows + row)
            return strings[value] if 0 < value < len(strings) else None
    return None


def _msi_best_image(path: Path) -> Optional[Tuple[int, int, bytes]]:
    """Largest icon from the MSI Icon table, preferring the Add/Remove Programs icon (ARPPRODUCTICON)."""
    if not olefile.isOleFile(str(path)):
        return None
    with olefile.OleFileIO(str(path)) as ole:
        streams: Dict[Tuple[bool, str], str] = {}
        for parts in ole.listdir(streams=True, storages=False):
            if len(parts) != 1:
                continue
            raw = parts[0]
            is_table = raw.startswith(_MSI_TABLE_PREFIX)
            streams[(is_table, _msi_decode_name(raw[1:] if is_table else raw))] = raw
        icons = sorted((name[5:], raw) for (is_table, name), raw in streams.items()
                       if not is_table and name.startswith("Icon."))
        if not icons:
            return None
        try:
            product_icon = _msi_property(ole, streams, "ARPPRODUCTICON")
        except _EXTRACTION_ERRORS as exc:
            log.debug("Cannot read ARPPRODUCTICON from %s: %s", path, exc)
            product_icon = None
        icons.sort(key=lambda item: item[0] != product_icon)
        best: Optional[Tuple[int, int, bytes]] = None
        for position, (icon_name, raw) in enumerate(icons[:MAX_ICON_GROUPS]):
            if ole.get_size(raw) > MAX_MSI_STREAM_BYTES:
                continue
            try:
                top = _blob_best_image(ole.openstream(raw).read())
            except _EXTRACTION_ERRORS as exc:
                log.debug("Skipping MSI icon %s: %s", icon_name, exc)
                continue
            if not top:
                continue
            if position == 0 and icon_name == product_icon and top[0] >= PREFERRED_MIN_PX:
                return top
            if best is None or top[:2] > best[:2]:
                best = top
        return best


def _installer_icon_png(path: Path, ext: str) -> Optional[bytes]:
    best = _msi_best_image(path) if ext == ".msi" else _pe_best_image(IconExtractor(str(path)))
    return _as_png(best[2]) if best else None


def extract_installer_icon(path: Path, rel_path: str, size: int, mtime: float) -> Optional[str]:
    """Extract the highest-resolution icon of an EXE or MSI as a PNG into EXTRACTED_ICONS_DIR; returns the file name."""
    ext = ".msi" if rel_path.lower().endswith(".msi") else ".exe"
    available = msi_extraction_available() if ext == ".msi" else extraction_available()
    if not available or size > config.MAX_ICON_EXE_MB * 1024 * 1024:
        return None
    key = f"v{ICON_ENGINE_VERSION}|{rel_path}|{size}|{int(mtime)}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    name = f"{EXTRACTED_PREFIX}{digest}.png"
    target = config.EXTRACTED_ICONS_DIR / name
    miss_marker = config.EXTRACTED_ICONS_DIR / f"{EXTRACTED_PREFIX}{digest}.none"
    if target.is_file():
        return name
    if miss_marker.exists():
        return None
    try:
        png = _installer_icon_png(path, ext)
        if png:
            _write_atomic(target, png)
            log.debug("Extracted icon from %s", rel_path)
            return name
        log.debug("No usable icon in %s", rel_path)
    except _EXTRACTION_ERRORS as exc:
        log.debug("No icon in %s: %s", rel_path, exc)
    except Exception as exc:  # noqa: BLE001 - malformed installers must never break a scan
        log.warning("Icon extraction failed for %s: %s", rel_path, exc)
    try:
        miss_marker.parent.mkdir(parents=True, exist_ok=True)
        miss_marker.touch()
    except OSError:
        pass
    return None


def prune_extracted(keep: Iterable[str]) -> None:
    keep_set: Set[str] = set(keep)
    try:
        for entry in config.EXTRACTED_ICONS_DIR.iterdir():
            legacy = entry.name.startswith(_LEGACY_PREFIX)
            stale = entry.name.startswith(EXTRACTED_PREFIX) and entry.suffix == ".png" and entry.name not in keep_set
            if legacy or stale:
                entry.unlink(missing_ok=True)
    except OSError as exc:
        log.debug("Cannot prune extracted icons: %s", exc)


def clear_extraction_misses() -> None:
    try:
        for prefix in (EXTRACTED_PREFIX, _LEGACY_PREFIX):
            for entry in config.EXTRACTED_ICONS_DIR.glob(f"{prefix}*.none"):
                entry.unlink(missing_ok=True)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Platform favicon fetcher
# --------------------------------------------------------------------------- #


class _IconLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[Tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "link":
            return
        data = {k.lower(): (v or "") for k, v in attrs}
        rel = data.get("rel", "").lower()
        href = data.get("href", "").strip()
        if "icon" not in rel or not href:
            return
        score = 1
        if "apple-touch-icon" in rel or href.lower().endswith(".svg") or "svg" in data.get("type", ""):
            score = 3
        else:
            sizes = re.findall(r"(\d+)x\d+", data.get("sizes", ""))
            if sizes and max(int(s) for s in sizes) >= 32:
                score = 2
        self.links.append((score, href))


def _ssl_context() -> ssl.SSLContext:
    if config.FAVICON_VERIFY_TLS:
        return ssl.create_default_context()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _http_get(url: str, limit: int) -> Optional[Tuple[bytes, str]]:
    if urlparse(url).scheme not in ("http", "https"):
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "PAKAL-favicon/1.0", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(request, timeout=config.FAVICON_TIMEOUT_SECONDS,
                                    context=_ssl_context()) as response:
            if response.status != 200:
                return None
            data = response.read(limit + 1)
            if len(data) > limit:
                return None
            return data, response.geturl()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.debug("GET %s failed: %s", url, exc)
        return None


def fetch_favicon(site_url: str, platform_id: int) -> Optional[str]:
    """Download the best icon advertised by an internal site; returns the stored file name."""
    parsed = urlparse(site_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    origin = f"{parsed.scheme}://{parsed.netloc}"

    candidates: List[str] = []
    page = _http_get(site_url, MAX_HTML_BYTES)
    if page:
        parser = _IconLinkParser()
        try:
            parser.feed(page[0].decode("utf-8", errors="ignore"))
        except Exception:  # noqa: BLE001 - tolerate broken markup
            pass
        for _score, href in sorted(parser.links, key=lambda item: -item[0]):
            candidates.append(urljoin(page[1], href))
    candidates.append(origin + "/favicon.ico")

    seen: Set[str] = set()
    for url in candidates:
        if url in seen or urlparse(url).scheme not in ("http", "https"):
            continue
        seen.add(url)
        result = _http_get(url, MAX_FAVICON_BYTES)
        if not result:
            continue
        try:
            data, ext = validate_image(result[0], MAX_FAVICON_BYTES)
        except ValueError:
            continue
        name = f"platform-{platform_id}-{hashlib.sha1(data).hexdigest()[:10]}{ext}"
        for old in config.EXTRACTED_ICONS_DIR.glob(f"platform-{platform_id}-*"):
            old.unlink(missing_ok=True)
        _write_atomic(config.EXTRACTED_ICONS_DIR / name, data)
        log.info("Fetched favicon for %s from %s", site_url, url)
        return name
    log.info("No favicon available for %s", site_url)
    return None
