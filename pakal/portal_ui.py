"""Admin-controlled portal interface: visibility of tabs, buttons and actions (settings key ``ui.visibility``)
and the side announcement card (``ui.announcement``).

Hiding an element that has a server-side endpoint also disables that endpoint (bundle ZIP, feedback,
package uploads, repository override), so the toggle is not merely cosmetic.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from .db import get_setting, set_setting

log = logging.getLogger("pakal.ui")

SETTING_KEY = "ui.visibility"

# (key, group) in the order the admin console lists them.
ELEMENTS: Tuple[Tuple[str, str], ...] = (
    ("tab_bundles", "tabs"),
    ("tab_platforms", "tabs"),
    ("tab_actions", "tabs"),
    ("tab_docker", "tabs"),
    ("btn_sync", "header"),
    ("btn_language", "header"),
    ("btn_theme", "header"),
    ("btn_admin", "header"),
    ("btn_feedback", "header"),
    ("btn_quick_download", "content"),
    ("btn_bundle_zip", "content"),
    ("btn_homepage", "content"),
    ("upload_repo_override", "content"),
    ("docker_build", "content"),
)
DEFAULTS: Dict[str, bool] = {key: True for key, _group in ELEMENTS}


def _stored() -> Dict[str, bool]:
    raw = get_setting(SETTING_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        log.warning("Ignoring corrupt %s setting", SETTING_KEY)
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: bool(v) for k, v in data.items() if k in DEFAULTS}


def is_stored() -> bool:
    return bool(_stored())


def load() -> Dict[str, bool]:
    return {**DEFAULTS, **_stored()}


def enabled(key: str) -> bool:
    return load().get(key, True)


def save(values: Dict[str, bool]) -> Dict[str, bool]:
    merged = {**load(), **{k: bool(v) for k, v in values.items() if k in DEFAULTS}}
    set_setting(SETTING_KEY, json.dumps(merged))
    return merged


def reset() -> Dict[str, bool]:
    set_setting(SETTING_KEY, "")
    return load()


# --------------------------------------------------------------------------- #
# Side announcement card
# --------------------------------------------------------------------------- #

ANNOUNCEMENT_KEY = "ui.announcement"
SEVERITIES = ("info", "success", "warning", "danger")
ANNOUNCEMENT_DEFAULTS: Dict[str, Any] = {
    "enabled": False, "severity": "info", "title": "", "message": "", "revision": 0, "updated_at": None,
}


def announcement() -> Dict[str, Any]:
    raw = get_setting(ANNOUNCEMENT_KEY)
    data: Dict[str, Any] = {}
    if raw:
        try:
            parsed = json.loads(raw)
            data = parsed if isinstance(parsed, dict) else {}
        except ValueError:
            log.warning("Ignoring corrupt %s setting", ANNOUNCEMENT_KEY)
    return {**ANNOUNCEMENT_DEFAULTS, **{k: v for k, v in data.items() if k in ANNOUNCEMENT_DEFAULTS}}


def public_announcement() -> Optional[Dict[str, Any]]:
    """What the portal shows, or None. Users dismiss per revision, so a new message reappears for everyone."""
    item = announcement()
    if not item["enabled"] or not item["message"]:
        return None
    return {k: item[k] for k in ("severity", "title", "message", "revision", "updated_at")}


def save_announcement(values: Dict[str, Any], republish: bool = False) -> Dict[str, Any]:
    current = announcement()
    new = {**current, **{k: values[k] for k in ("enabled", "severity", "title", "message") if k in values}}
    content_changed = any(new[k] != current[k] for k in ("severity", "title", "message"))
    newly_enabled = new["enabled"] and not current["enabled"]
    if content_changed or newly_enabled or republish:
        new["revision"] = int(current["revision"] or 0) + 1
    new["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    set_setting(ANNOUNCEMENT_KEY, json.dumps(new, ensure_ascii=False))
    return new
