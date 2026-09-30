"""Authentication and integration settings (Keycloak, LDAP / Active Directory, local admin, Nexus).

Each admin subsection is stored as its own JSON document in the settings table (``auth.<section>``)
and falls back to the environment variables in :mod:`pakal.config`. Secrets are write-only:
they are never returned to the browser, and a blank value on save keeps the stored one.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any, Dict, Optional, Tuple

import bcrypt

from . import config
from .db import get_setting, set_setting

log = logging.getLogger("pakal.auth")

SECTIONS = ("keycloak", "ldap_server", "ldap_groups", "ldap_lookup", "login_identity", "local_admin", "nexus",
            "docker")
SECRET_FIELDS = {"keycloak": "client_secret", "ldap_server": "bind_password", "nexus": "password", "docker": "password"}
_KEY = "auth.{}"
_LEGACY_SSO_KEY = "sso_config"
_LEGACY_AUTH_URL = re.compile(r"^(https?://.+?)/realms/([^/]+)/protocol/openid-connect/auth$")


def env_defaults(section: str) -> Dict[str, Any]:
    if section == "keycloak":
        return {
            "enabled": config.KEYCLOAK_ENABLED,
            "url": config.KEYCLOAK_URL.rstrip("/"),
            "realm": config.KEYCLOAK_REALM,
            "client_id": config.KEYCLOAK_CLIENT_ID,
            "client_secret": config.KEYCLOAK_CLIENT_SECRET,
            "redirect_uri": config.KEYCLOAK_REDIRECT_URI,
            "post_logout_redirect_uri": config.KEYCLOAK_POST_LOGOUT_REDIRECT_URI,
            "cooldown_after_logout_ms": config.KEYCLOAK_SSO_COOLDOWN_AFTER_LOGOUT_MS,
            "idp_hint": config.KEYCLOAK_IDP_HINT,
            "prompt": config.KEYCLOAK_PROMPT,
            "admin_role": config.KEYCLOAK_ADMIN_ROLE,
            "timeout_ms": config.KEYCLOAK_TIMEOUT_MS,
            "tls_insecure": config.KEYCLOAK_TLS_INSECURE,
            "extra_scopes": config.KEYCLOAK_EXTRA_SCOPES,
        }
    if section == "ldap_server":
        return {"url": config.LDAP_URL, "search_base": config.LDAP_SEARCH_BASE,
                "bind_dn": config.LDAP_ADMIN, "bind_password": config.LDAP_PASSWORD}
    if section == "ldap_groups":
        return {"admin_group_dn": config.LDAP_ADMIN_GROUP_DN, "netbios_domain": config.LDAP_NETBIOS_DOMAIN}
    if section == "ldap_lookup":
        return {"enabled": config.LDAP_DISPLAY_NAME_LOOKUP, "timeout_ms": config.LDAP_LOOKUP_TIMEOUT_MS,
                "pause_sec": config.LDAP_DISPLAY_NAME_PAUSE_SEC}
    if section == "login_identity":
        return {"email_domain": config.USER_EMAIL_DOMAIN}
    if section == "local_admin":
        username, password_hash = _env_local_admin()
        return {"username": username, "password_hash": password_hash}
    if section == "nexus":
        return {
            "enabled": config.NEXUS_ENABLED,
            "url": config.NEXUS_URL.rstrip("/"),
            "username": config.NEXUS_USERNAME,
            "password": config.NEXUS_PASSWORD,
            "pypi_repo": config.NEXUS_PYPI_REPO,
            "npm_repo": config.NEXUS_NPM_REPO,
            "powershell_repo": config.NEXUS_POWERSHELL_REPO,
            "tls_insecure": config.NEXUS_TLS_INSECURE,
            "check_existing": config.NEXUS_CHECK_EXISTING,
            "max_upload_mb": config.NEXUS_MAX_UPLOAD_MB,
            "timeout_seconds": config.NEXUS_TIMEOUT_SECONDS,
        }
    if section == "docker":
        return {
            "enabled": True,
            "registry": config.NEXUS_DOCKER_REGISTRY.rstrip("/"),
            "username": config.NEXUS_DOCKER_USERNAME,
            "password": config.NEXUS_DOCKER_PASSWORD,
            "namespace": config.NEXUS_DOCKER_NAMESPACE.strip("/"),
            "tls_insecure": config.NEXUS_TLS_INSECURE,
            "build_enabled": config.DOCKER_BUILD_ENABLED,
            "build_admin_only": config.DOCKER_BUILD_ADMIN_ONLY,
            "max_context_mb": config.DOCKER_MAX_CONTEXT_MB,
            "build_timeout_seconds": config.DOCKER_BUILD_TIMEOUT_SECONDS,
        }
    raise KeyError(section)


_env_hash_lock = threading.Lock()
_env_hash_cache: Optional[Tuple[str, str]] = None


def _env_local_admin() -> Tuple[str, str]:
    """LOCAL_ADMIN_* wins; otherwise the ADMIN_USERNAME / ADMIN_PASSWORD_HASH pair used since v1.0."""
    global _env_hash_cache
    username = config.LOCAL_ADMIN_USERNAME or config.ADMIN_USERNAME
    if not config.LOCAL_ADMIN_PASSWORD:
        return username, config.ADMIN_PASSWORD_HASH
    with _env_hash_lock:
        if _env_hash_cache is None or _env_hash_cache[0] != config.LOCAL_ADMIN_PASSWORD:
            _env_hash_cache = (config.LOCAL_ADMIN_PASSWORD, hash_password(config.LOCAL_ADMIN_PASSWORD))
        return username, _env_hash_cache[1]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode("ascii")


def _legacy_keycloak() -> Dict[str, Any]:
    """Carry over what the v1.3.1 single-form SSO settings stored."""
    raw = get_setting(_LEGACY_SSO_KEY)
    if not raw:
        return {}
    try:
        old = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(old, dict):
        return {}
    migrated: Dict[str, Any] = {k: old[k] for k in ("enabled", "client_id", "client_secret", "redirect_uri") if k in old}
    match = _LEGACY_AUTH_URL.match(str(old.get("auth_url", "")))
    if match:
        migrated["url"], migrated["realm"] = match.group(1), match.group(2)
    if isinstance(old.get("relogin_seconds"), int):
        migrated["cooldown_after_logout_ms"] = old["relogin_seconds"] * 1000
    return migrated


def stored(section: str) -> Dict[str, Any]:
    raw = get_setting(_KEY.format(section))
    if not raw:
        return _legacy_keycloak() if section == "keycloak" else {}
    try:
        data = json.loads(raw)
    except ValueError:
        log.warning("Ignoring corrupt %s settings", section)
        return {}
    return data if isinstance(data, dict) else {}


def load(section: str) -> Dict[str, Any]:
    merged = env_defaults(section)
    merged.update({k: v for k, v in stored(section).items() if k in merged})
    return merged


def public_view(section: str, values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    values = load(section) if values is None else values
    view = dict(values)
    secret = SECRET_FIELDS.get(section)
    if secret:
        view[f"has_{secret}"] = bool(view.pop(secret, ""))
    if section == "local_admin":
        view["has_password"] = bool(view.pop("password_hash", ""))
        view["password_source"] = "database" if stored("local_admin").get("password_hash") else "environment"
    return view


def preview(section: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Effective settings if ``data`` were saved (blank secret keeps the stored one); nothing is written."""
    merged = load(section)
    merged.update(_merge(section, merged, data))
    return merged


def _merge(section: str, current: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    new = {k: v for k, v in data.items() if k in current and k not in (SECRET_FIELDS.get(section), "password_hash")}
    secret = SECRET_FIELDS.get(section)
    if secret:
        if data.get(f"clear_{secret}"):
            new[secret] = ""
        elif data.get(secret):
            new[secret] = data[secret]
        else:
            new[secret] = current.get(secret, "")
    return new


def save(section: str, data: Dict[str, Any]) -> Dict[str, Any]:
    new = _merge(section, load(section), data)
    if section == "local_admin":
        previous = stored("local_admin").get("password_hash")
        new["password_hash"] = hash_password(data["password"]) if data.get("password") else previous or ""
        if not new["password_hash"]:
            new.pop("password_hash")
    set_setting(_KEY.format(section), json.dumps(new, ensure_ascii=False))
    return load(section)


def reset(section: str) -> Dict[str, Any]:
    set_setting(_KEY.format(section), "")
    if section == "keycloak":
        set_setting(_LEGACY_SSO_KEY, "")
    return load(section)


def ldap() -> Dict[str, Any]:
    """Flattened LDAP view used by the directory client."""
    return {**load("ldap_server"), **load("ldap_groups"), "lookup": load("ldap_lookup"),
            "email_domain": load("login_identity")["email_domain"]}


def local_admin() -> Tuple[str, str]:
    values = load("local_admin")
    return values["username"], values.get("password_hash", "")
