"""Catalog store: background scans, cache.json persistence and the admin-override overlay."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select

from . import config, icons
from .db import AppOverride, DevStack, PlatformLink, get_setting, session_scope, set_setting
from .knowledge import CATEGORIES, match_known_app, normalize_key
from .models import AppEntry, Bundle, Catalog, Category, Platform, ScanResult, ScanStatus
from .scanner import human_size, read_json, scan_share, with_files

log = logging.getLogger("pakal.store")

CACHE_SCHEMA = 4
AUTO_RESCAN_SETTING = "auto_rescan_minutes"
MAX_RESCAN_MINUTES = 10080


def platform_icon_url(row: PlatformLink) -> Optional[str]:
    return icons.upload_url(row.icon_file) or icons.extracted_url(row.favicon_file) or icons.builtin_icon_url(row.icon)


def apply_override(app: AppEntry, override: Optional[AppOverride]) -> Optional[AppEntry]:
    """Return the app as shown publicly, or None when hidden (or every installer is hidden)."""
    if override is None:
        return app
    if override.hidden:
        return None
    update: Dict[str, object] = {}
    if override.display_name:
        update["name"] = override.display_name
    if override.description_he:
        update["description_he"] = override.description_he
    if override.description_en:
        update["description_en"] = override.description_en
    if override.category:
        update["category"] = override.category
    if override.tags is not None:
        update["tags"] = list(override.tags)
    if override.featured is not None:
        update["featured"] = override.featured
    uploaded = icons.upload_url(override.icon_file)
    if uploaded:
        update["icon_url"], update["icon_source"] = uploaded, "upload"
    result = app.model_copy(update=update)
    hidden_files = set(override.hidden_files or [])
    if hidden_files:
        files = [f for f in app.files if f.rel_path not in hidden_files]
        if not files:
            return None
        result = with_files(result, files)
    return result


def _resolve_stacks(stacks: Iterable[DevStack], apps: List[AppEntry]) -> List[Bundle]:
    lookup: Dict[str, AppEntry] = {}
    for app in apps:
        for key in (app.id, normalize_key(app.folder), normalize_key(app.name), app.known_key):
            if key:
                lookup.setdefault(key, app)
    bundles: List[Bundle] = []
    for stack in stacks:
        found: List[str] = []
        missing: List[str] = []
        total = 0
        for ref in stack.apps or []:
            app = lookup.get(ref) or lookup.get(normalize_key(ref)) or lookup.get(match_known_app(ref) or "")
            if app and app.id not in found:
                found.append(app.id)
                if app.latest:
                    total += app.latest.bundle_size_bytes or app.latest.size_bytes
            elif not app:
                missing.append(ref)
        bundles.append(Bundle(
            id=stack.id, name_he=stack.name_he, name_en=stack.name_en,
            description_he=stack.description_he, description_en=stack.description_en,
            icon=stack.icon, color=stack.color, apps=found, missing=missing,
            total_size_bytes=total, total_size_human=human_size(total),
        ))
    return bundles


class CatalogStore:
    """Thread-safe scan state with a persistent disk cache and a memoized public view."""

    def __init__(self) -> None:
        self._scan_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._result = ScanResult()
        self._status = ScanStatus()
        self._generation = 0
        self._view_generation = -1
        self._view_json: Optional[bytes] = None
        self._view_catalog: Optional[Catalog] = None
        self._view_paths: frozenset = frozenset()
        self.first_scan_done = threading.Event()
        self.schedule_changed = threading.Event()
        self._rescan_again = threading.Event()

    # ---------------------------------------------------------------- schedule

    def rescan_interval_minutes(self) -> int:
        """Admin-configured interval (settings table), falling back to AUTO_RESCAN_MINUTES. 0 disables."""
        stored = get_setting(AUTO_RESCAN_SETTING)
        try:
            minutes = int(stored) if stored is not None else config.AUTO_RESCAN_MINUTES
        except ValueError:
            minutes = config.AUTO_RESCAN_MINUTES
        return max(0, min(minutes, MAX_RESCAN_MINUTES))

    def set_rescan_interval(self, minutes: int) -> None:
        set_setting(AUTO_RESCAN_SETTING, str(max(0, min(minutes, MAX_RESCAN_MINUTES))))
        self.schedule_changed.set()

    # ---------------------------------------------------------------- state

    @property
    def status(self) -> ScanStatus:
        with self._state_lock:
            return self._status.model_copy()

    @property
    def raw_apps(self) -> List[AppEntry]:
        with self._state_lock:
            return list(self._result.apps)

    def raw_app(self, app_id: str) -> Optional[AppEntry]:
        return next((a for a in self.raw_apps if a.id == app_id), None)

    def folder_icon(self, app_id: str) -> Optional[Path]:
        with self._state_lock:
            path = self._result.folder_icons.get(app_id)
        return Path(path) if path else None

    def invalidate_view(self) -> None:
        with self._state_lock:
            self._generation += 1

    # ---------------------------------------------------------------- public view

    def _build_view(self) -> Catalog:
        with self._state_lock:
            result, status = self._result, self._status.model_copy()
        with session_scope() as session:
            overrides = {o.app_id: o for o in session.scalars(select(AppOverride))}
            stacks = list(session.scalars(select(DevStack).order_by(DevStack.sort_order, DevStack.name_en)))
            platform_rows = list(session.scalars(select(PlatformLink).order_by(PlatformLink.sort_order,
                                                                               PlatformLink.id)))
        apps = [a for a in (apply_override(app, overrides.get(app.id)) for app in result.apps) if a]
        apps.sort(key=lambda a: a.name.lower())
        counts: Dict[str, int] = {}
        for app in apps:
            counts[app.category] = counts.get(app.category, 0) + 1
        platforms = [Platform(
            id=row.id, name=row.name, url=row.url, description_he=row.description_he,
            description_en=row.description_en, icon=row.icon, icon_url=platform_icon_url(row), color=row.color,
        ) for row in platform_rows]
        return Catalog(
            apps=apps,
            bundles=_resolve_stacks(stacks, apps),
            platforms=platforms,
            categories=[Category(id=cid, label_he=he, label_en=en,
                                 count=len(apps) if cid == "all" else counts.get(cid, 0))
                        for cid, he, en in CATEGORIES],
            scan=status,
        )

    def _ensure_view(self) -> None:
        with self._state_lock:
            generation = self._generation
            if self._view_generation == generation and self._view_catalog is not None:
                return
        catalog = self._build_view()
        payload = json.dumps(catalog.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
        paths = frozenset(f.rel_path for app in catalog.apps for f in app.files)
        with self._state_lock:
            if generation >= self._view_generation:
                self._view_catalog = catalog
                self._view_json = payload.encode("utf-8")
                self._view_paths = paths
                self._view_generation = generation

    def is_downloadable(self, rel_path: str) -> bool:
        self._ensure_view()
        with self._state_lock:
            return rel_path in self._view_paths

    def public_json(self) -> bytes:
        self._ensure_view()
        with self._state_lock:
            return self._view_json or b"{}"

    def public_catalog(self) -> Catalog:
        self._ensure_view()
        with self._state_lock:
            return self._view_catalog or Catalog()

    # ---------------------------------------------------------------- cache

    def load_cache(self) -> bool:
        raw = read_json(config.CACHE_FILE)
        if not isinstance(raw, dict) or raw.get("schema") != CACHE_SCHEMA:
            return False
        try:
            result = ScanResult.model_validate(raw["result"])
            status = ScanStatus.model_validate(raw.get("status") or {})
        except (KeyError, ValueError) as exc:
            log.warning("Ignoring invalid cache %s: %s", config.CACHE_FILE, exc)
            return False
        with self._state_lock:
            self._result = result
            self._status = status.model_copy(update={"scanning": False, "source": "cache"})
            self._generation += 1
        self.first_scan_done.set()
        log.info("Loaded %d apps from cache %s", len(result.apps), config.CACHE_FILE)
        return True

    def _save_cache(self) -> None:
        with self._state_lock:
            payload = {
                "schema": CACHE_SCHEMA,
                "result": self._result.model_dump(mode="json"),
                "status": self._status.model_dump(mode="json"),
            }
        tmp = config.CACHE_FILE.with_name(config.CACHE_FILE.name + ".tmp")
        try:
            config.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, config.CACHE_FILE)
        except OSError as exc:
            log.warning("Cannot write cache %s: %s", config.CACHE_FILE, exc)

    def invalidate_cache(self) -> None:
        try:
            config.CACHE_FILE.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Cannot delete cache %s: %s", config.CACHE_FILE, exc)
        icons.clear_extraction_misses()

    # ---------------------------------------------------------------- scanning

    def trigger_rescan(self, invalidate: bool = False) -> bool:
        if not self._scan_lock.acquire(blocking=False):
            return False
        with self._state_lock:
            self._status = self._status.model_copy(update={"scanning": True})
            self._generation += 1
        threading.Thread(target=self._run_scan, args=(invalidate,), name="catalog-scan", daemon=True).start()
        return True

    def request_rescan(self) -> bool:
        """Rescan now, or right after the scan in progress (its directory listing may predate a new file)."""
        if self.trigger_rescan():
            return True
        self._rescan_again.set()
        return False

    def _run_scan(self, invalidate: bool) -> None:
        started = time.monotonic()
        try:
            if invalidate:
                self.invalidate_cache()
            log.info("Scanning %s ...", config.APPS_ROOT)
            result = scan_share()
            duration_ms = int((time.monotonic() - started) * 1000)
            now = time.time()
            file_count = sum(len(a.files) for a in result.apps)
            status = ScanStatus(
                scanning=False, source="scan",
                last_scan=datetime.fromtimestamp(now).isoformat(timespec="seconds"), last_scan_ts=now,
                duration_ms=duration_ms, root_available=result.root_available,
                error=None if result.root_available else f"Apps root {config.APPS_ROOT} is not available",
                apps=len(result.apps), files=file_count,
            )
            with self._state_lock:
                keep_previous = not result.root_available and self._result.apps
                if keep_previous:
                    self._status = self._status.model_copy(update={"scanning": False, "error": status.error})
                else:
                    self._result, self._status = result, status
                self._generation += 1
            if result.root_available:
                self._save_cache()
            log.info("Scan finished: %d apps, %d installers in %d ms", len(result.apps), file_count, duration_ms)
        except Exception as exc:  # noqa: BLE001 - keep the last good catalog on any failure
            log.exception("Scan failed")
            with self._state_lock:
                self._status = self._status.model_copy(update={"scanning": False, "error": str(exc)})
                self._generation += 1
        finally:
            self._scan_lock.release()
            self.first_scan_done.set()
        if self._rescan_again.is_set():
            self._rescan_again.clear()
            self.trigger_rescan()


store = CatalogStore()

_favicon_lock = threading.Lock()


def refresh_favicons(platform_ids: Optional[List[int]] = None, only_missing: bool = True) -> int:
    """Fetch favicons for platforms (blocking). Returns the number of icons stored."""
    if not config.FETCH_FAVICONS:
        return 0
    with _favicon_lock:
        with session_scope() as session:
            query = select(PlatformLink)
            if platform_ids:
                query = query.where(PlatformLink.id.in_(platform_ids))
            targets = [(row.id, row.url) for row in session.scalars(query)
                       if not (only_missing and row.favicon_file and icons.extracted_url(row.favicon_file))]
        fetched = 0
        for platform_id, url in targets:
            name = icons.fetch_favicon(url, platform_id)
            if not name:
                continue
            with session_scope() as session:
                row = session.get(PlatformLink, platform_id)
                if row:
                    row.favicon_file = name
                    fetched += 1
        if fetched:
            store.invalidate_view()
        return fetched


def refresh_favicons_async(platform_ids: Optional[List[int]] = None, only_missing: bool = True) -> None:
    threading.Thread(target=refresh_favicons, args=(platform_ids, only_missing), name="favicons",
                     daemon=True).start()
