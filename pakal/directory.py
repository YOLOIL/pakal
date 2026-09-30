"""LDAP / Active Directory client: credential login, group membership and display-name lookup.

Authentication is the standard AD "search & bind": bind with the service account, find the user by
sAMAccountName under LDAP_SEARCH_BASE, then bind as that user's DN with the supplied password.
Without a service account the user binds directly as DOMAIN\\user (or user@USER_EMAIL_DOMAIN).
"""

from __future__ import annotations

import logging
import math
import re
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ldap3 import NONE, SIMPLE, SUBTREE, SYNC, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from . import auth_config, config

log = logging.getLogger("pakal.ldap")

# Swapped for ldap3.MOCK_SYNC by the test-suite.
STRATEGY = SYNC
USER_ATTRIBUTES = ["sAMAccountName", "displayName", "cn", "givenName", "sn", "mail", "userPrincipalName",
                   "memberOf", "userAccountControl"]
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._$-]{1,64}$")
_ACCOUNT_DISABLED = 0x2
_IN_CHAIN = "1.2.840.113556.1.4.1941"
_CACHE_TTL = 3600.0


class DirectoryUnavailable(Exception):
    """LDAP is not configured, not reachable, or the service account was rejected."""


class DirectoryAuthError(Exception):
    """Unknown user, wrong password or disabled account (never tells the caller which)."""


# --------------------------------------------------------------------------- #
# Connections
# --------------------------------------------------------------------------- #


def configured(cfg: Optional[Dict[str, Any]] = None) -> bool:
    cfg = cfg or auth_config.ldap()
    return bool(cfg.get("url") and cfg.get("search_base"))


def parse_urls(value: str) -> List[Tuple[str, int, bool]]:
    """``ldap://host:389 ldaps://host2`` -> [(host, port, use_ssl)]. Raises ValueError on bad input."""
    servers = []
    for raw in re.split(r"[\s,;]+", value.strip()):
        if not raw:
            continue
        parsed = urlparse(raw)
        if parsed.scheme not in ("ldap", "ldaps") or not parsed.hostname or parsed.path not in ("", "/"):
            raise ValueError(f"Invalid LDAP URL: {raw} (expected ldap://host:389 or ldaps://host:636)")
        use_ssl = parsed.scheme == "ldaps"
        servers.append((parsed.hostname, parsed.port or (636 if use_ssl else 389), use_ssl))
    if not servers:
        raise ValueError("LDAP URL is empty")
    return servers


def _servers(cfg: Dict[str, Any], timeout: float) -> Any:
    """One Server per configured URL, tried in order (ldap3's ServerPool sleeps 10 s between failed rounds)."""
    tls = Tls(validate=ssl.CERT_NONE if config.LDAP_TLS_INSECURE else ssl.CERT_REQUIRED)
    return [Server(host, port=port, use_ssl=use_ssl, tls=tls, connect_timeout=timeout, get_info=NONE)
            for host, port, use_ssl in parse_urls(cfg["url"])]


def _connect(cfg: Dict[str, Any], user: str, password: str, timeout: float) -> Optional[Connection]:
    """Bound connection, None for rejected credentials; DirectoryUnavailable for network/server problems."""
    if not password:
        # An empty password would be an unauthenticated bind, which AD accepts - never allow it.
        return None
    try:
        servers = _servers(cfg, timeout)
    except ValueError as exc:
        raise DirectoryUnavailable(str(exc)) from exc
    servers = servers if isinstance(servers, list) else [servers]
    errors: List[str] = []
    # ldap3 packs receive_timeout with struct.pack('LL', ...) which only accepts an INTEGER number of seconds;
    # a float (e.g. 5.0) raises struct.error - not an LDAPException - as soon as the TCP connection succeeds.
    receive_timeout = max(1, int(math.ceil(timeout)))
    for server in servers:
        try:
            conn = Connection(server, user=user, password=password, authentication=SIMPLE,
                              client_strategy=STRATEGY, receive_timeout=receive_timeout, read_only=True,
                              auto_referrals=False, raise_exceptions=False)
            if conn.bind():
                return conn
        except Exception as exc:  # noqa: BLE001 - LDAPException, socket/TLS errors, struct.error, pyasn1 errors ...
            errors.append(f"{server.host}:{server.port} {type(exc).__name__}: {exc}")
            continue
        result = conn.result or {}
        if result.get("result") == 49:  # invalidCredentials
            return None
        errors.append(f"{server.host}:{server.port} bind failed: {result.get('description')} {result.get('message', '')}".strip())
    raise DirectoryUnavailable("; ".join(errors)[:500] or "no LDAP server configured")


def _first(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip() if value is not None else ""


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    return [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]


def _norm_dn(dn: str) -> str:
    return ",".join(part.strip() for part in dn.split(",")).lower()


def normalize_username(raw: str) -> Optional[str]:
    """Accept ``user``, ``DOMAIN\\user`` and ``user@domain``; return the bare sAMAccountName."""
    value = (raw or "").strip()
    if "\\" in value:
        value = value.split("\\", 1)[1]
    if "@" in value:
        value = value.split("@", 1)[0]
    return value if _USERNAME_RE.match(value) else None


def _find_user(conn: Connection, cfg: Dict[str, Any], username: str) -> Optional[Dict[str, Any]]:
    search = f"(&(objectClass=user)(sAMAccountName={escape_filter_chars(username)}))"
    try:
        conn.search(cfg["search_base"], search, SUBTREE, attributes=USER_ATTRIBUTES, size_limit=2)
    except Exception as exc:  # noqa: BLE001
        raise DirectoryUnavailable(f"search failed: {type(exc).__name__}: {exc}") from exc
    entries = [e for e in (conn.response or []) if e.get("type") == "searchResEntry"]
    if len(entries) != 1:
        return None
    return {"dn": entries[0]["dn"], "attributes": entries[0].get("attributes") or {}}


def _is_member(conn: Connection, cfg: Dict[str, Any], entry: Dict[str, Any], group_dn: str) -> bool:
    if not group_dn:
        return False
    wanted = _norm_dn(group_dn)
    if any(_norm_dn(g) == wanted for g in _as_list(entry["attributes"].get("memberOf"))):
        return True
    # Nested groups: AD's LDAP_MATCHING_RULE_IN_CHAIN.
    try:
        conn.search(cfg["search_base"],
                    f"(&(distinguishedName={escape_filter_chars(entry['dn'])})"
                    f"(memberOf:{_IN_CHAIN}:={escape_filter_chars(group_dn)}))",
                    SUBTREE, attributes=["cn"], size_limit=1)
        return any(e.get("type") == "searchResEntry" for e in conn.response or [])
    except Exception:  # noqa: BLE001 - non-AD servers reject the matching rule
        return False


def _identity(cfg: Dict[str, Any], conn: Connection, username: str, entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    attrs = entry["attributes"] if entry else {}
    sam = _first(attrs.get("sAMAccountName")) or username
    name = _first(attrs.get("displayName")) or " ".join(
        p for p in (_first(attrs.get("givenName")), _first(attrs.get("sn"))) if p) or _first(attrs.get("cn")) or sam
    email = _first(attrs.get("mail")) or (f"{sam}@{cfg['email_domain']}" if cfg.get("email_domain") else "")
    admin = bool(entry and _is_member(conn, cfg, entry, cfg.get("admin_group_dn", "")))
    roles = ["admin"] if admin else []
    return {"username": sam[:120], "name": name[:120], "email": email[:200], "admin": admin, "roles": roles,
            "source": "ldap", "dn": entry["dn"] if entry else ""}


def _close(*conns: Optional[Connection]) -> None:
    for conn in conns:
        try:
            if conn is not None:
                conn.unbind()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #


def authenticate(raw_username: str, password: str) -> Dict[str, Any]:
    cfg = auth_config.ldap()
    if not configured(cfg):
        raise DirectoryUnavailable("LDAP is not configured")
    username = normalize_username(raw_username)
    if not username or not password:
        raise DirectoryAuthError("invalid input")
    timeout = max(0.5, config.LDAP_AUTH_TIMEOUT_MS / 1000)
    service = user_conn = None
    try:
        if cfg.get("bind_dn"):
            service = _connect(cfg, cfg["bind_dn"], cfg.get("bind_password", ""), timeout)
            if service is None:
                log.error("LDAP service account bind was rejected (LDAP_ADMIN=%s) - check LDAP_PASSWORD", cfg["bind_dn"])
                raise DirectoryUnavailable("service account bind rejected")
            entry = _find_user(service, cfg, username)
            if entry is None:
                raise DirectoryAuthError("unknown user")
            uac = _first(entry["attributes"].get("userAccountControl"))
            if uac.isdigit() and int(uac) & _ACCOUNT_DISABLED:
                raise DirectoryAuthError("account disabled")
            user_conn = _connect(cfg, entry["dn"], password, timeout)
            if user_conn is None:
                raise DirectoryAuthError("bad password")
            identity = _identity(cfg, service, username, entry)
        else:
            principal = f"{cfg['netbios_domain']}\\{username}" if cfg.get("netbios_domain") else (
                f"{username}@{cfg['email_domain']}" if cfg.get("email_domain") else username)
            user_conn = _connect(cfg, principal, password, timeout)
            if user_conn is None:
                raise DirectoryAuthError("bad password")
            identity = _identity(cfg, user_conn, username, _find_user(user_conn, cfg, username))
    finally:
        _close(service, user_conn)
    _remember(identity["username"], identity)
    return identity


def test_connection() -> Dict[str, Any]:
    cfg = auth_config.ldap()
    started = time.monotonic()
    result: Dict[str, Any] = {"ok": False, "bind": False, "base_found": False, "error": "", "servers": []}
    conn = None
    try:
        result["servers"] = [f"{'ldaps' if s else 'ldap'}://{h}:{p}" for h, p, s in parse_urls(cfg.get("url", ""))]
        if not cfg.get("search_base"):
            raise DirectoryUnavailable("LDAP_SEARCH_BASE is not set")
        if not cfg.get("bind_dn"):
            raise DirectoryUnavailable("LDAP_ADMIN (service account) is not set - only direct user binds are possible")
        conn = _connect(cfg, cfg["bind_dn"], cfg.get("bind_password", ""), max(0.5, config.LDAP_AUTH_TIMEOUT_MS / 1000))
        if conn is None:
            raise DirectoryUnavailable("service account credentials were rejected (invalidCredentials)")
        result["bind"] = True
        conn.search(cfg["search_base"], "(objectClass=*)", "BASE", attributes=["objectClass"])
        result["base_found"] = any(e.get("type") == "searchResEntry" for e in conn.response or [])
        if not result["base_found"]:
            raise DirectoryUnavailable(f"search base not found: {cfg['search_base']}")
        result["ok"] = True
    except (DirectoryUnavailable, ValueError, LDAPException) as exc:
        result["error"] = str(exc)[:300]
        log.warning("LDAP connection test failed: %s", exc)
    except Exception as exc:  # noqa: BLE001 - the admin button must always get a JSON answer, never a 500
        result["error"] = f"{type(exc).__name__}: {exc}"[:300]
        log.exception("LDAP connection test crashed")
    finally:
        _close(conn)
    result["ms"] = int((time.monotonic() - started) * 1000)
    return result


# --------------------------------------------------------------------------- #
# Display-name lookup (cached, time-boxed, pauses after failures)
# --------------------------------------------------------------------------- #

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ldap-lookup")
_cache: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}
_cache_lock = threading.Lock()
_paused_until = 0.0


def _remember(username: str, info: Optional[Dict[str, Any]]) -> None:
    with _cache_lock:
        _cache[username.lower()] = (time.monotonic(), info)


def _lookup(username: str) -> Optional[Dict[str, Any]]:
    global _paused_until
    cfg = auth_config.ldap()
    timeout = max(0.1, int(cfg["lookup"]["timeout_ms"]) / 1000)
    conn = None
    try:
        conn = _connect(cfg, cfg["bind_dn"], cfg.get("bind_password", ""), timeout)
        if conn is None:
            raise DirectoryUnavailable("service account bind rejected")
        entry = _find_user(conn, cfg, username)
        info = _identity(cfg, conn, username, entry) if entry else None
        _remember(username, info)
        return info
    except Exception as exc:  # noqa: BLE001 - a lookup must never break a login
        pause = int(cfg["lookup"]["pause_sec"])
        _paused_until = time.monotonic() + pause
        log.warning("LDAP display-name lookup for %s failed (%s) - pausing lookups for %ss", username, exc, pause)
        return None
    finally:
        _close(conn)


def lookup_user(username: str) -> Optional[Dict[str, Any]]:
    """Uncached, unpaused lookup for the admin test button; raises DirectoryUnavailable with the reason."""
    cfg = auth_config.ldap()
    if not configured(cfg):
        raise DirectoryUnavailable("LDAP is not configured (LDAP_URL / LDAP_SEARCH_BASE)")
    if not cfg.get("bind_dn"):
        raise DirectoryUnavailable("display-name lookup needs the LDAP_ADMIN service account")
    conn = None
    try:
        conn = _connect(cfg, cfg["bind_dn"], cfg.get("bind_password", ""), max(0.1, int(cfg["lookup"]["timeout_ms"]) / 1000))
        if conn is None:
            raise DirectoryUnavailable("service account credentials were rejected (invalidCredentials)")
        entry = _find_user(conn, cfg, username)
        return _identity(cfg, conn, username, entry) if entry else None
    except DirectoryUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DirectoryUnavailable(f"{type(exc).__name__}: {exc}"[:300]) from exc
    finally:
        _close(conn)


def lookup_status() -> Dict[str, Any]:
    return {"paused_for_sec": max(0, int(_paused_until - time.monotonic())), "cached": len(_cache)}


def resolve(username: str, wait: bool = True) -> Optional[Dict[str, Any]]:
    """Directory info for a sAMAccountName, waiting at most LDAP_LOOKUP_TIMEOUT_MS.

    A lookup that outlives the timeout keeps running in the background and fills the cache.
    """
    cfg = auth_config.ldap()
    if not username or not cfg["lookup"]["enabled"] or not configured(cfg) or not cfg.get("bind_dn"):
        return None
    with _cache_lock:
        cached = _cache.get(username.lower())
    if cached and time.monotonic() - cached[0] < _CACHE_TTL:
        return cached[1]
    if time.monotonic() < _paused_until:
        return None
    future = _executor.submit(_lookup, username)
    if not wait:
        return None
    try:
        return future.result(timeout=max(0.1, int(cfg["lookup"]["timeout_ms"]) / 1000))
    except FutureTimeout:
        log.info("LDAP display-name lookup for %s exceeded %sms - continuing in the background",
                 username, cfg["lookup"]["timeout_ms"])
        return None
    except Exception:  # noqa: BLE001 - display-name enrichment is optional
        log.exception("LDAP display-name lookup for %s failed", username)
        return None


def clear_cache() -> None:
    global _paused_until
    with _cache_lock:
        _cache.clear()
    _paused_until = 0.0
