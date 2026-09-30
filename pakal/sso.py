"""Keycloak / OpenID Connect client (authorization code + PKCE).

Settings come from :mod:`pakal.auth_config` (section ``keycloak``); endpoints are derived from
``KEYCLOAK_URL`` + ``KEYCLOAK_REALM``. HTTP uses the standard library so no extra dependencies are needed.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import logging
import secrets
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from . import auth_config, config

log = logging.getLogger("pakal.sso")

BASE_SCOPES = ("openid", "profile", "email")
SILENT_ERRORS = {"login_required", "interaction_required", "consent_required", "account_selection_required"}
_MAX_BODY = 1024 * 1024
_PROBE_TTL = 60.0
_PROBE_TIMEOUT = 3.0


class SsoError(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


def endpoints(cfg: Dict[str, Any]) -> Dict[str, str]:
    base = f"{cfg['url'].rstrip('/')}/realms/{urllib.parse.quote(cfg['realm'], safe='')}/protocol/openid-connect"
    return {"auth": f"{base}/auth", "token": f"{base}/token", "userinfo": f"{base}/userinfo", "logout": f"{base}/logout"}


def load() -> Dict[str, Any]:
    cfg = auth_config.load("keycloak")
    cfg["endpoints"] = endpoints(cfg) if cfg.get("url") and cfg.get("realm") else {}
    return cfg


def is_active(cfg: Dict[str, Any]) -> bool:
    return bool(cfg.get("enabled") and cfg.get("client_id") and cfg.get("endpoints"))


def scopes(cfg: Dict[str, Any], base_only: bool = False) -> str:
    wanted = list(BASE_SCOPES)
    if not base_only:
        wanted += [s for s in str(cfg.get("extra_scopes") or "").split() if s not in wanted]
    return " ".join(wanted)


def _timeout(cfg: Dict[str, Any]) -> float:
    return max(0.5, int(cfg.get("timeout_ms") or 5000) / 1000)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

_ssl_lock = threading.Lock()
_ssl_cache: Dict[Tuple[bool, str], ssl.SSLContext] = {}


def ssl_context(insecure: bool) -> ssl.SSLContext:
    key = (insecure, config.KEYCLOAK_CA_BUNDLE)
    with _ssl_lock:
        ctx = _ssl_cache.get(key)
        if ctx is None:
            if insecure:
                # Equivalent of Node's rejectUnauthorized: false - for internal CAs / self-signed certificates.
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            else:
                ctx = ssl.create_default_context(cafile=config.KEYCLOAK_CA_BUNDLE or None)
            _ssl_cache[key] = ctx
        return ctx


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _http(cfg: Dict[str, Any], url: str, *, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None,
          timeout: Optional[float] = None, method: Optional[str] = None) -> Tuple[int, bytes]:
    """Return (status, body). HTTP error statuses are returned; network/TLS failures raise SsoError."""
    request = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json", **(headers or {})})
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl_context(bool(cfg.get("tls_insecure")))), _NoRedirect())
    try:
        with opener.open(request, timeout=timeout or _timeout(cfg)) as response:
            return response.status, response.read(_MAX_BODY)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(_MAX_BODY)
        except Exception:  # noqa: BLE001
            body = b""
        return exc.code, body
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
            raise SsoError("tls_error", f"{reason} - enable KEYCLOAK_TLS_INSECURE or set KEYCLOAK_CA_BUNDLE") from exc
        raise SsoError("unreachable", str(reason)) from exc


def _json(body: bytes) -> Dict[str, Any]:
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SsoError("bad_response", "invalid JSON") from exc
    if not isinstance(data, dict):
        raise SsoError("bad_response", "unexpected JSON")
    return data


def _error_detail(body: bytes) -> str:
    try:
        data = _json(body)
    except SsoError:
        return body[:200].decode("utf-8", "replace")
    return " - ".join(str(data[k]) for k in ("error", "error_description") if data.get(k))[:300]


# --------------------------------------------------------------------------- #
# Protocol
# --------------------------------------------------------------------------- #


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def new_transaction() -> Dict[str, str]:
    verifier = secrets.token_urlsafe(64)
    return {
        "state": secrets.token_urlsafe(24),
        "nonce": secrets.token_urlsafe(24),
        "verifier": verifier,
        "challenge": _b64url(hashlib.sha256(verifier.encode("ascii")).digest()),
    }


def _with_query(url: str, params: Dict[str, str]) -> str:
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)


def authorization_url(cfg: Dict[str, Any], tx: Dict[str, str], silent: bool, scope: str) -> str:
    params = {
        "client_id": cfg["client_id"],
        "response_type": "code",
        "scope": scope,
        "redirect_uri": cfg["redirect_uri"],
        "state": tx["state"],
        "nonce": tx["nonce"],
        "code_challenge": tx["challenge"],
        "code_challenge_method": "S256",
    }
    if silent:
        params["prompt"] = "none"
    elif cfg.get("prompt"):
        params["prompt"] = cfg["prompt"]
    if cfg.get("idp_hint"):
        params["kc_idp_hint"] = cfg["idp_hint"]
    return _with_query(cfg["endpoints"]["auth"], params)


def exchange_code(cfg: Dict[str, Any], code: str, verifier: str) -> Dict[str, Any]:
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": cfg["redirect_uri"],
        "code_verifier": verifier,
        "client_id": cfg["client_id"],
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if cfg.get("client_secret"):
        # RFC 6749 §2.3.1: client_secret_basic with form-encoded credentials.
        pair = f"{urllib.parse.quote_plus(cfg['client_id'])}:{urllib.parse.quote_plus(cfg['client_secret'])}"
        headers["Authorization"] = "Basic " + base64.b64encode(pair.encode("utf-8")).decode("ascii")
    url = cfg["endpoints"]["token"]
    status, body = _http(cfg, url, data=urllib.parse.urlencode(form).encode("ascii"), headers=headers)
    if status != 200:
        detail = _error_detail(body)
        log.error("Keycloak token exchange failed: HTTP %s from %s (client_id=%s, redirect_uri=%s): %s",
                  status, url, cfg["client_id"], cfg["redirect_uri"], detail or "<empty body>")
        raise SsoError("token_rejected", f"HTTP {status} {detail}".strip())
    tokens = _json(body)
    if not tokens.get("access_token"):
        log.error("Keycloak token response from %s has no access_token (keys: %s)", url, sorted(tokens))
        raise SsoError("bad_response", "no access_token")
    return tokens


def jwt_claims(token: str) -> Dict[str, Any]:
    """Decode JWT claims without signature validation.

    Only used for tokens received directly from the token endpoint over TLS
    (OpenID Connect Core §3.1.3.7 allows TLS server validation in place of the signature check).
    """
    try:
        payload = token.split(".")[1]
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise SsoError("bad_token") from exc
    if not isinstance(data, dict):
        raise SsoError("bad_token")
    return data


def validate_id_token(cfg: Dict[str, Any], claims: Dict[str, Any], nonce: str) -> None:
    if not secrets.compare_digest(str(claims.get("nonce", "")).encode("utf-8"), nonce.encode("utf-8")):
        raise SsoError("nonce_mismatch", "the id_token nonce does not match this login")
    aud = claims.get("aud")
    audiences = aud if isinstance(aud, list) else [aud]
    if cfg["client_id"] not in audiences and claims.get("azp") != cfg["client_id"]:
        raise SsoError("audience_mismatch", f"aud={aud!r} azp={claims.get('azp')!r} client_id={cfg['client_id']!r}")
    exp = claims.get("exp")
    if isinstance(exp, (int, float)) and exp < time.time() - 60:
        raise SsoError("id_token_expired", "check the clock of the PAKAL host and Keycloak")


def fetch_userinfo(cfg: Dict[str, Any], access_token: str) -> Dict[str, Any]:
    url = cfg["endpoints"]["userinfo"]
    status, body = _http(cfg, url, headers={"Authorization": f"Bearer {access_token}"})
    if status != 200:
        detail = _error_detail(body)
        log.error("Keycloak userinfo failed: HTTP %s from %s: %s", status, url, detail or "<empty body>")
        raise SsoError("userinfo_rejected", f"HTTP {status} {detail}".strip())
    return _json(body)


def _claim(claims: Dict[str, Any], name: str) -> str:
    value = claims.get(name)
    if value is None:
        lowered = name.lower()
        value = next((v for k, v in claims.items() if k.lower() == lowered), None)
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value).strip() if value not in (None, "") else ""


def roles(cfg: Dict[str, Any], *claim_sets: Dict[str, Any]) -> List[str]:
    """Realm roles, client roles of this client and a flat "roles"/"groups" claim, from any token."""
    found: List[str] = []
    for claims in claim_sets:
        realm = claims.get("realm_access")
        if isinstance(realm, dict):
            found += [str(r) for r in realm.get("roles") or []]
        client = (claims.get("resource_access") or {}).get(cfg["client_id"])
        if isinstance(client, dict):
            found += [str(r) for r in client.get("roles") or []]
        for key in ("roles", "groups"):
            if isinstance(claims.get(key), list):
                found += [str(r).lstrip("/") for r in claims[key]]
    return list(dict.fromkeys(found))


def extract_identity(cfg: Dict[str, Any], claims: Dict[str, Any], role_list: List[str]) -> Dict[str, Any]:
    username = _claim(claims, config.KEYCLOAK_USER_FIELD or "sAMAccountName") or _claim(claims, "preferred_username")
    if "\\" in username:  # DOMAIN\user
        username = username.split("\\", 1)[1]
    if "@" in username and not _claim(claims, config.KEYCLOAK_USER_FIELD or "sAMAccountName"):
        username = username.split("@", 1)[0]
    name = _claim(claims, "name") or " ".join(
        p for p in (_claim(claims, "given_name"), _claim(claims, "family_name")) if p)
    admin_role = str(cfg.get("admin_role") or "").strip()
    return {
        "username": username[:120], "name": name[:120], "email": _claim(claims, "email")[:200],
        "roles": role_list, "admin": bool(admin_role and admin_role in role_list), "source": "sso",
    }


def logout_url(cfg: Dict[str, Any], id_token_hint: Optional[str]) -> Optional[str]:
    if not cfg.get("endpoints"):
        return None
    params = {"client_id": cfg["client_id"], "post_logout_redirect_uri": cfg["post_logout_redirect_uri"]}
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    return _with_query(cfg["endpoints"]["logout"], params)


# --------------------------------------------------------------------------- #
# Reachability
# --------------------------------------------------------------------------- #

_probe_cache: Dict[str, Tuple[float, bool]] = {}


def probe_url(cfg: Dict[str, Any], url: str, method: str = "GET") -> Dict[str, Any]:
    started = time.monotonic()
    try:
        data = b"" if method == "POST" else None
        status, _ = _http(cfg, url, data=data, method=method, timeout=min(_PROBE_TIMEOUT, _timeout(cfg)),
                          headers={"Content-Type": "application/x-www-form-urlencoded"} if data is not None else None)
    except SsoError as exc:
        return {"ok": False, "status": None, "error": str(exc)[:300], "ms": int((time.monotonic() - started) * 1000)}
    # Any HTTP answer (even 400/401) proves the endpoint is reachable; 404/5xx point to a wrong URL/realm or a broken server.
    return {"ok": status < 500 and status != 404, "status": status, "error": "",
            "ms": int((time.monotonic() - started) * 1000)}


def reachable(cfg: Dict[str, Any]) -> bool:
    url = cfg.get("endpoints", {}).get("auth", "")
    key = f"{url}|{cfg.get('tls_insecure')}"
    cached = _probe_cache.get(key)
    now = time.monotonic()
    if cached and now - cached[0] < _PROBE_TTL:
        return cached[1]
    ok = probe_url(cfg, url)["status"] is not None
    _probe_cache[key] = (now, ok)
    return ok


def clear_probe_cache() -> None:
    _probe_cache.clear()


def test_endpoints(cfg: Dict[str, Any]) -> Dict[str, Any]:
    eps = cfg.get("endpoints") or {}
    checks = {"auth": "GET", "token": "POST", "userinfo": "GET", "logout": "GET"}

    def run(name: str) -> Tuple[str, Dict[str, Any]]:
        url = eps.get(name)
        result = probe_url(cfg, url, checks[name]) if url else {"ok": False, "status": None, "error": "not set", "ms": 0}
        return name, {**result, "url": url or ""}

    with ThreadPoolExecutor(max_workers=len(checks)) as pool:
        results = dict(pool.map(run, checks))
    clear_probe_cache()
    for name, r in results.items():
        if not r["ok"]:
            log.warning("Keycloak %s endpoint check failed (%s): %s", name, r["url"], r["error"] or f"HTTP {r['status']}")
    return {"results": results, "ok": all(r["ok"] for r in results.values())}
