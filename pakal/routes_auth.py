"""End-user identity (Keycloak OIDC or LDAP credentials) and the feedback submission API."""

from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from . import config, directory, portal_ui, sso
from .db import Feedback, get_session
from .schemas import CredentialsIn, FeedbackIn
from .security import (
    COOKIE_NAME, CSRF_HEADER, JWT_ALGORITHM, USER_COOKIE, LoginThrottle, _jwt_secret, client_ip, cookie_secure,
    create_user_token, decode_token, decode_user_token, global_login_throttle, login_throttle, portal_admin,
    revoke_token,
)

log = logging.getLogger("pakal.auth")

router = APIRouter(tags=["auth"])

TX_COOKIE = "pakal_sso_tx"
TX_PATH = "/api/auth/sso"
IDT_COOKIE = "pakal_idt"
IDT_PATH = "/api/auth"
TX_TTL = 600
NO_STORE = {"Cache-Control": "no-store"}

feedback_throttle = LoginThrottle(config.FEEDBACK_MAX_PER_WINDOW, config.FEEDBACK_WINDOW_SECONDS)
global_feedback_throttle = LoginThrottle(config.FEEDBACK_MAX_PER_WINDOW * 20, config.FEEDBACK_WINDOW_SECONDS)


def _safe_next(value: Optional[str]) -> str:
    """Only same-origin relative paths are accepted as post-login targets."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    if any(ord(c) < 32 for c in value) or len(value) > 300:
        return "/"
    return value


def _with_flag(path: str, **params: str) -> str:
    base, hash_sep, fragment = path.partition("#")
    return base + ("&" if "?" in base else "?") + urlencode(params) + hash_sep + fragment


def _require_csrf(request: Request) -> None:
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing request header")


def current_user(request: Request) -> Optional[dict]:
    return decode_user_token(request.cookies.get(USER_COOKIE))


def _clear_sso_cookies(response, request: Request) -> None:
    secure = cookie_secure(request)
    response.delete_cookie(USER_COOKIE, path="/", samesite="lax", secure=secure, httponly=True)
    response.delete_cookie(IDT_COOKIE, path=IDT_PATH, samesite="lax", secure=secure, httponly=True)


def _set_user_cookie(response, request: Request, identity: Dict[str, Any]) -> None:
    token, _ = create_user_token(identity)
    response.set_cookie(USER_COOKIE, token, max_age=config.USER_SESSION_MINUTES * 60, httponly=True,
                        secure=cookie_secure(request), samesite="lax", path="/")


def _enrich_from_directory(identity: Dict[str, Any]) -> Dict[str, Any]:
    """Fill a missing display name and apply LDAP_ADMIN_GROUP_DN for SSO users (time-boxed)."""
    info = directory.resolve(identity["username"])
    if not info:
        if not identity.get("name"):
            identity["name"] = identity["username"]
        return identity
    if not identity.get("name") or identity["name"] == identity["username"]:
        identity["name"] = info["name"]
    identity["email"] = identity.get("email") or info.get("email", "")
    identity["roles"] = list(dict.fromkeys([*identity.get("roles", []), *[f"ldap:{r}" for r in info.get("roles", [])]]))
    identity["admin"] = bool(identity.get("admin") or info.get("admin"))
    return identity


# --------------------------------------------------------------------------- #
# Keycloak OIDC flow
# --------------------------------------------------------------------------- #


@router.get("/api/auth/sso/login")
def sso_login(request: Request, silent: int = 0, next: Optional[str] = None,  # noqa: A002
              base_scopes: int = 0) -> RedirectResponse:
    cfg = sso.load()
    target = _safe_next(next)
    if not sso.is_active(cfg):
        return RedirectResponse(_with_flag(target, sso="disabled"), status_code=303, headers=NO_STORE)

    tx = sso.new_transaction()
    scope = sso.scopes(cfg, base_only=bool(base_scopes))
    now = int(time.time())
    cookie = jwt.encode({
        "scope": "sso_tx", "state": tx["state"], "nonce": tx["nonce"], "verifier": tx["verifier"],
        "next": target, "silent": bool(silent), "extra": scope != sso.scopes(cfg, base_only=True),
        "iat": now, "exp": now + TX_TTL,
    }, _jwt_secret(), algorithm=JWT_ALGORITHM)
    response = RedirectResponse(sso.authorization_url(cfg, tx, bool(silent), scope), status_code=303, headers=NO_STORE)
    response.set_cookie(TX_COOKIE, cookie, max_age=TX_TTL, httponly=True, secure=cookie_secure(request),
                        samesite="lax", path=TX_PATH)
    return response


@router.get("/api/auth/sso/callback")
def sso_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None,
                 error: Optional[str] = None, error_description: Optional[str] = None) -> RedirectResponse:
    tx: Dict[str, Any] = {}
    raw = request.cookies.get(TX_COOKIE)
    if raw:
        try:
            tx = jwt.decode(raw, _jwt_secret(), algorithms=[JWT_ALGORITHM], options={"require": ["exp"]})
        except jwt.PyJWTError:
            tx = {}
    target = _safe_next(tx.get("next"))

    def finish(url: str) -> RedirectResponse:
        response = RedirectResponse(url, status_code=303, headers=NO_STORE)
        response.delete_cookie(TX_COOKIE, path=TX_PATH, samesite="lax", secure=cookie_secure(request), httponly=True)
        return response

    if tx.get("scope") != "sso_tx" or not state or not secrets.compare_digest(
            str(tx.get("state", "")).encode("utf-8"), state.encode("utf-8")):
        log.warning("SSO callback with missing/invalid state from %s (expired tab or replay)", client_ip(request))
        return finish(_with_flag(target, sso="error", reason="state"))
    if error:
        detail = (error_description or "")[:300]
        if error in sso.SILENT_ERRORS:
            return finish(_with_flag(target, sso="none"))
        if error == "invalid_scope" and tx.get("extra"):
            log.error("Keycloak rejected the requested scopes (%s) - retrying with 'openid profile email'. "
                      "Create the missing client scope or clear KEYCLOAK_EXTRA_SCOPES.", detail or error)
            response = finish(f"/api/auth/sso/login?{urlencode({'silent': int(bool(tx.get('silent'))), 'next': target, 'base_scopes': 1})}")
            return response
        log.error("Keycloak returned an error to the callback: %s - %s", error[:64], detail or "<no description>")
        return finish(_with_flag(target, sso="error", reason=error[:40]))
    if not code:
        return finish(_with_flag(target, sso="error", reason="code"))

    cfg = sso.load()
    if not sso.is_active(cfg):
        return finish(_with_flag(target, sso="disabled"))
    try:
        tokens = sso.exchange_code(cfg, code, tx["verifier"])
        id_token = str(tokens.get("id_token") or "")
        if not id_token:
            raise sso.SsoError("no_id_token", "the token response has no id_token - is 'openid' an allowed scope?")
        claims = sso.jwt_claims(id_token)
        sso.validate_id_token(cfg, claims, tx["nonce"])
        info = sso.fetch_userinfo(cfg, tokens["access_token"])
        if info and info.get("sub") and info["sub"] != claims.get("sub"):
            raise sso.SsoError("subject_mismatch", "userinfo sub differs from the id_token sub")
        try:
            access_claims = sso.jwt_claims(str(tokens["access_token"]))
        except sso.SsoError:
            access_claims = {}  # opaque access token
        identity = sso.extract_identity(cfg, {**claims, **info}, sso.roles(cfg, access_claims, claims, info))
        if not identity["username"]:
            raise sso.SsoError("no_identity", f"neither {config.KEYCLOAK_USER_FIELD} nor preferred_username is in the token")
    except sso.SsoError as exc:
        log.error("SSO login failed (%s): %s", exc.reason, exc.detail or exc)
        return finish(_with_flag(target, sso="error", reason=exc.reason))
    except Exception as exc:  # noqa: BLE001 - never surface a bare 500 to the browser mid-redirect
        log.exception("SSO callback crashed while completing the login")
        return finish(_with_flag(target, sso="error", reason="internal"))

    try:
        identity = _enrich_from_directory(identity)
    except Exception:  # noqa: BLE001 - LDAP enrichment is optional; the Keycloak login already succeeded
        log.exception("LDAP enrichment failed for %s - continuing without it", identity.get("username"))
        identity.setdefault("name", identity["username"])
    response = finish(target)
    _set_user_cookie(response, request, identity)
    if len(id_token) < 3500:
        response.set_cookie(IDT_COOKIE, id_token, max_age=config.USER_SESSION_MINUTES * 60, httponly=True,
                            secure=cookie_secure(request), samesite="lax", path=IDT_PATH)
    log.info("SSO login: %s (admin=%s) from %s", identity["username"], identity["admin"], client_ip(request))
    return response


@router.get("/api/auth/sso/post-logout")
def sso_post_logout() -> RedirectResponse:
    """KEYCLOAK_POST_LOGOUT_REDIRECT_URI lands here; the portal then waits the cooldown before a silent login."""
    return RedirectResponse("/?sso=logged_out", status_code=303, headers=NO_STORE)


# --------------------------------------------------------------------------- #
# LDAP credential login
# --------------------------------------------------------------------------- #


@router.post("/api/auth/ldap/login")
def ldap_login(body: CredentialsIn, request: Request) -> JSONResponse:
    _require_csrf(request)
    ip = client_ip(request)
    wait = max(login_throttle.retry_after(f"user:{ip}"), global_login_throttle.retry_after("user:*"))
    if wait:
        raise HTTPException(status_code=429, detail="Too many failed attempts", headers={"Retry-After": str(wait)})
    try:
        identity = directory.authenticate(body.username, body.password)
    except directory.DirectoryAuthError:
        login_throttle.failure(f"user:{ip}")
        global_login_throttle.failure("user:*")
        log.warning("LDAP login failed for %r from %s", body.username[:64], ip)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    except directory.DirectoryUnavailable as exc:
        log.error("LDAP login unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="The directory service is unavailable")
    except Exception:  # noqa: BLE001
        log.exception("LDAP login crashed")
        raise HTTPException(status_code=503, detail="The directory service is unavailable")
    login_throttle.reset(f"user:{ip}")
    response = JSONResponse({"user": {k: identity[k] for k in ("username", "name", "email", "admin")}}, headers=NO_STORE)
    _set_user_cookie(response, request, identity)
    log.info("LDAP login: %s (admin=%s) from %s", identity["username"], identity["admin"], ip)
    return response


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #


@router.get("/api/auth/me")
def me(request: Request) -> JSONResponse:
    cfg = sso.load()
    active = sso.is_active(cfg)
    user = current_user(request)
    admin = portal_admin(request)
    body = {
        # The console path is only disclosed to admins; everyone else never learns it from the portal.
        "admin": {
            "allowed": True, "path": config.ADMIN_SECURE_PATH,
            "upload_extensions": list(config.INSTALLER_EXTENSIONS), "upload_max_mb": config.ADMIN_APP_UPLOAD_MAX_MB,
        } if admin else {"allowed": False, "path": None},
        "sso_enabled": active,
        "sso_reachable": sso.reachable(cfg) if active and not user else active,
        "sso_cooldown_ms": int(cfg.get("cooldown_after_logout_ms", 10000)),
        "ldap_enabled": directory.configured(),
        "authenticated": bool(user),
        "user": {
            "username": user["sub"], "name": user.get("name") or user["sub"], "email": user.get("email", ""),
            "source": user.get("src", "sso"), "admin": bool(user.get("admin")),
        } if user else None,
        "ip": client_ip(request),
        "server_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return JSONResponse(body, headers=NO_STORE)


@router.post("/api/auth/logout")
def logout(request: Request) -> JSONResponse:
    _require_csrf(request)
    user = current_user(request)
    if user:
        revoke_token(user)
        log.info("Logout: %s (%s)", user["sub"], user.get("src", "sso"))
    # Signing out of the portal also ends the admin console session of this browser, so admin-only
    # portal controls cannot outlive the sign-out on a shared machine.
    admin_token = request.cookies.get(COOKIE_NAME)
    admin_session = decode_token(admin_token) if admin_token else None
    if admin_session:
        revoke_token(admin_session)
    cfg = sso.load()
    via_sso = bool(user and user.get("src", "sso") == "sso" and sso.is_active(cfg))
    url = sso.logout_url(cfg, request.cookies.get(IDT_COOKIE)) if via_sso else None
    response = JSONResponse({"logout_url": url, "sso_cooldown_ms": int(cfg.get("cooldown_after_logout_ms", 10000)),
                             "relogin": via_sso}, headers=NO_STORE)
    _clear_sso_cookies(response, request)
    if admin_token:
        response.delete_cookie(COOKIE_NAME, path="/", samesite="strict", secure=cookie_secure(request), httponly=True)
    return response


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #


@router.post("/api/feedback", status_code=201)
def submit_feedback(body: FeedbackIn, request: Request, db: Session = Depends(get_session)) -> Dict[str, Any]:
    _require_csrf(request)
    if not portal_ui.enabled("btn_feedback"):
        raise HTTPException(status_code=403, detail="Feedback is disabled by the administrator")
    user = current_user(request)
    admin = None if user else portal_admin(request)
    if not user and not admin:
        raise HTTPException(status_code=401, detail="Sign in to send a request")
    if admin:
        name = admin.split(":", 1)[1]
        user = {"sub": name, "name": name, "email": ""}
    ip = client_ip(request)
    wait = max(feedback_throttle.retry_after(ip), global_feedback_throttle.retry_after("*"))
    if wait:
        raise HTTPException(status_code=429, detail="Too many submissions", headers={"Retry-After": str(wait)})
    feedback_throttle.failure(ip)
    global_feedback_throttle.failure("*")

    row = Feedback(
        category=body.category, subject=body.subject, message=body.message, ip=ip, status="new",
        user_name=(user.get("name") or user["sub"])[:120],
        username=user["sub"][:120],
        email=(user.get("email") or "")[:200],
    )
    db.add(row)
    db.commit()
    log.info("Feedback #%d (%s) from %s", row.id, row.category, row.username or ip)
    return {"id": row.id, "status": "received"}
