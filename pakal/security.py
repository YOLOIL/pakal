"""
Admin authentication: bcrypt password verification, JWT session cookies, CSRF header check,
login throttling and input sanitisation helpers.

Generate a password hash for ADMIN_PASSWORD_HASH with:
    python -m pakal.security hash-password
"""

from __future__ import annotations

import hmac
import html
import logging
import re
import secrets
import threading
import time
import unicodedata
import uuid
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

import bcrypt
import jwt
from fastapi import HTTPException, Request, status

from . import config

log = logging.getLogger("pakal.security")

COOKIE_NAME = "pakal_admin"
CSRF_HEADER = "x-pakal-request"
JWT_ALGORITHM = "HS256"
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

_CONTROL_RE = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
_BLOCK_RE = re.compile(r"(?is)<\s*(script|style|iframe|object|embed|svg|math)\b.*?(?:<\s*/\s*\1\s*>|$)")
_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"[ \t\r\n]+")

# --------------------------------------------------------------------------- #
# Sanitisation
# --------------------------------------------------------------------------- #


def clean_text(value: Optional[str], max_len: int, multiline: bool = False) -> str:
    """Normalise user text: NFC, strip control/bidi-override chars and markup, collapse whitespace."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    text = html.unescape(text)
    text = _CONTROL_RE.sub("", text)
    text = _BLOCK_RE.sub("", text)
    text = _TAG_RE.sub("", text).replace("<", "").replace(">", "")
    if multiline:
        text = "\n".join(_WS_RE.sub(" ", line).strip() for line in text.splitlines())
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
    else:
        text = _WS_RE.sub(" ", text).strip()
    return text[:max_len]


# --------------------------------------------------------------------------- #
# Passwords & tokens
# --------------------------------------------------------------------------- #


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode("ascii")


_DUMMY_HASH = bcrypt.hashpw(b"pakal-timing-equaliser", bcrypt.gensalt(rounds=12))


def verify_credentials(username: str, password: str) -> bool:
    """Local (emergency) admin account - works even when LDAP and Keycloak are unreachable."""
    from .auth_config import local_admin

    admin_user, admin_hash = local_admin()
    configured = admin_hash.encode("utf-8") if admin_hash else None
    user_ok = hmac.compare_digest(username.encode("utf-8"), admin_user.encode("utf-8"))
    try:
        password_ok = bcrypt.checkpw(password.encode("utf-8")[:72], configured or _DUMMY_HASH)
    except ValueError:
        log.error("The local admin password hash is not a valid bcrypt hash")
        return False
    return bool(configured) and user_ok and password_ok


def admin_configured() -> bool:
    from .auth_config import local_admin

    return bool(local_admin()[1])


_secret_lock = threading.Lock()
_secret_cache: Optional[str] = None


def _jwt_secret() -> str:
    global _secret_cache
    if config.JWT_SECRET:
        return config.JWT_SECRET
    with _secret_lock:
        if _secret_cache:
            return _secret_cache
        from .db import get_setting, set_setting

        secret = get_setting("jwt_secret")
        if not secret:
            secret = secrets.token_urlsafe(48)
            set_setting("jwt_secret", secret)
        _secret_cache = secret
        return secret


_revoked: Dict[str, float] = {}
_revoked_lock = threading.Lock()


ADMIN_SOURCES = ("local", "ldap", "sso")


def create_token(username: str, source: str = "local", name: str = "") -> Tuple[str, int]:
    now = int(time.time())
    exp = now + config.JWT_TTL_MINUTES * 60
    payload = {"sub": username, "name": name or username, "src": source, "iat": now, "nbf": now, "exp": exp,
               "jti": uuid.uuid4().hex, "scope": "admin"}
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM), exp


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, _jwt_secret(), algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
    except jwt.PyJWTError:
        return None
    source = payload.get("src", "local")
    if payload.get("scope") != "admin" or source not in ADMIN_SOURCES:
        return None
    if source == "local":
        from .auth_config import local_admin

        # Renaming the local admin invalidates sessions issued to the old name.
        if payload.get("sub") != local_admin()[0]:
            return None
    with _revoked_lock:
        if payload["jti"] in _revoked:
            return None
    return payload


def revoke_token(payload: dict) -> None:
    now = time.time()
    with _revoked_lock:
        for jti, exp in list(_revoked.items()):
            if exp < now:
                del _revoked[jti]
        _revoked[payload["jti"]] = float(payload.get("exp", now))


USER_COOKIE = "pakal_user"


def create_user_token(identity: Dict[str, str]) -> Tuple[str, int]:
    now = int(time.time())
    exp = now + config.USER_SESSION_MINUTES * 60
    payload = {
        "sub": identity["username"], "name": identity.get("name", ""), "email": identity.get("email", ""),
        "src": identity.get("source", "sso"), "admin": bool(identity.get("admin")),
        "roles": list(identity.get("roles", []))[:20],
        "iat": now, "nbf": now, "exp": exp, "jti": uuid.uuid4().hex, "scope": "user",
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM), exp


def decode_user_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, _jwt_secret(), algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("scope") != "user" or not payload.get("sub"):
        return None
    with _revoked_lock:
        if payload["jti"] in _revoked:
            return None
    return payload


def portal_admin(request: Request) -> Optional[str]:
    """Who may use admin-only portal controls: an admin console session, or a portal session (Keycloak role /
    LDAP admin group) that carries the admin flag. Returns an audit label, or None."""
    token = request.cookies.get(COOKIE_NAME)
    session = decode_token(token) if token else None
    if session:
        return f"admin:{session['sub']}"
    user = decode_user_token(request.cookies.get(USER_COOKIE))
    if user and user.get("admin"):
        return f"{user.get('src', 'sso')}:{user['sub']}"
    return None


def cookie_secure(request: Request) -> bool:
    if config.COOKIE_SECURE in {"1", "true", "yes", "on"}:
        return True
    if config.COOKIE_SECURE in {"0", "false", "no", "off"}:
        return False
    return request.url.scheme == "https"


def require_admin(request: Request) -> dict:
    """FastAPI dependency protecting every /api/admin/* route."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    payload = decode_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if request.method in _UNSAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing request header")
    return payload


# --------------------------------------------------------------------------- #
# Login throttling
# --------------------------------------------------------------------------- #


class LoginThrottle:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._failures: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        attempts = self._failures[key]
        while attempts and attempts[0] < now - self.window:
            attempts.popleft()
        return attempts

    def retry_after(self, key: str) -> int:
        now = time.time()
        with self._lock:
            attempts = self._prune(key, now)
            if len(attempts) >= self.max_attempts:
                return max(1, int(attempts[0] + self.window - now))
        return 0

    def failure(self, key: str) -> None:
        with self._lock:
            self._prune(key, time.time()).append(time.time())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


login_throttle = LoginThrottle(config.LOGIN_MAX_ATTEMPTS, config.LOGIN_WINDOW_SECONDS)
global_login_throttle = LoginThrottle(config.LOGIN_MAX_ATTEMPTS * 10, config.LOGIN_WINDOW_SECONDS)


def client_ip(request: Request) -> str:
    # The right-most X-Forwarded-For entry is appended by the reverse proxy and cannot be forged by the client.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()[:64]
    return request.client.host if request.client else "unknown"


if __name__ == "__main__":
    import getpass
    import sys

    if len(sys.argv) < 2 or sys.argv[1] != "hash-password":
        print("usage: python -m pakal.security hash-password")
        sys.exit(2)
    first = getpass.getpass("New admin password: ")
    if len(first) < 10:
        print("Password must be at least 10 characters.")
        sys.exit(1)
    if getpass.getpass("Repeat password: ") != first:
        print("Passwords do not match.")
        sys.exit(1)
    print(hash_password(first))
