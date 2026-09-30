"""Admin API (/api/admin/*): JWT-protected management of platforms, stacks and app metadata."""

from __future__ import annotations

import base64
import binascii
import logging
import re
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import auth_config, config, directory, docker_build, docker_registry, icons, nexus, portal_ui, sso
from .db import AppOverride, DevStack, Feedback, PlatformLink, get_session, normalize_order, place_in_order
from .knowledge import BUILTIN_ICON_NAMES, CATEGORIES, STACK_GLYPHS
from .schemas import (
    FEEDBACK_CATEGORIES, FEEDBACK_STATUSES, AnnouncementIn, AppOverrideIn, AppOverrideOut, FeedbackStatusIn, IconUploadIn, LoginIn,
    AUTH_SECTION_MODELS, DockerSettingsIn, LdapLookupTestIn, NexusSettingsIn, PlatformIn, PlatformOut, SettingsIn, StackIn, StackOut,
    VisibilityIn,
)
from .security import (
    COOKIE_NAME, CSRF_HEADER, admin_configured, client_ip, cookie_secure, create_token, global_login_throttle,
    USER_COOKIE, decode_user_token, login_throttle, require_admin, revoke_token, verify_credentials,
)
from .store import apply_override, platform_icon_url, refresh_favicons, refresh_favicons_async, store

log = logging.getLogger("pakal.admin")

router = APIRouter(prefix="/api/admin", tags=["admin"])
protected = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

NO_STORE = {"Cache-Control": "no-store"}


class RescanIn(BaseModel):
    invalidate: bool = True


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #


def _issue_admin_cookie(request: Request, response: Response, username: str, source: str, name: str = "") -> Dict[str, Any]:
    token, expires = create_token(username, source, name)
    response.set_cookie(
        COOKIE_NAME, token, max_age=config.JWT_TTL_MINUTES * 60, httponly=True,
        secure=cookie_secure(request), samesite="strict", path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"username": username, "name": name or username, "source": source, "expires_at": expires}


@router.get("/meta")
def meta() -> JSONResponse:
    return JSONResponse({
        "configured": admin_configured() or directory.configured(),
        "local": admin_configured(),
        "ldap": directory.configured(),
        "sso": sso.is_active(sso.load()),
    }, headers=NO_STORE)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> Dict[str, Any]:
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing request header")
    ldap_on = directory.configured()
    if not admin_configured() and not ldap_on:
        raise HTTPException(status_code=503, detail="Admin access is not configured (local admin password or LDAP)")
    ip = client_ip(request)
    wait = max(login_throttle.retry_after(ip), global_login_throttle.retry_after("*"))
    if wait:
        raise HTTPException(status_code=429, detail="Too many failed attempts",
                            headers={"Retry-After": str(wait)})

    def fail(reason: str) -> HTTPException:
        login_throttle.failure(ip)
        global_login_throttle.failure("*")
        log.warning("Failed admin login for %r from %s (%s)", body.username[:64], ip, reason)
        return HTTPException(status_code=401, detail="Invalid username or password")

    # The local account is checked first so it keeps working when LDAP / Keycloak are down.
    if verify_credentials(body.username, body.password):
        login_throttle.reset(ip)
        log.info("Admin login (local) from %s", ip)
        return _issue_admin_cookie(request, response, body.username, "local")
    if not ldap_on:
        raise fail("local credentials rejected")
    try:
        identity = directory.authenticate(body.username, body.password)
    except directory.DirectoryAuthError:
        raise fail("LDAP credentials rejected")
    except directory.DirectoryUnavailable as exc:
        log.error("Admin login: LDAP unavailable (%s) - only the local admin account can sign in", exc)
        raise HTTPException(status_code=503, detail="The directory service is unavailable - sign in with the local admin account")
    login_throttle.reset(ip)
    if not identity["admin"]:
        log.warning("Admin login refused for %s from %s: not a member of LDAP_ADMIN_GROUP_DN", identity["username"], ip)
        raise HTTPException(status_code=403, detail="Your account is not a member of the PAKAL admin group")
    log.info("Admin login (LDAP) %s from %s", identity["username"], ip)
    return _issue_admin_cookie(request, response, identity["username"], "ldap", identity["name"])


@router.post("/sso-session")
def sso_session(request: Request, response: Response) -> Dict[str, Any]:
    """Trade a portal session (Keycloak / LDAP) that carries the admin flag for an admin console session."""
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing request header")
    user = decode_user_token(request.cookies.get(USER_COOKIE))
    if not user:
        raise HTTPException(status_code=401, detail="Not signed in")
    if not user.get("admin"):
        raise HTTPException(status_code=403, detail="Your account does not have the PAKAL admin role")
    source = "ldap" if user.get("src") == "ldap" else "sso"
    log.info("Admin login (%s session) %s from %s", source, user["sub"], client_ip(request))
    return _issue_admin_cookie(request, response, user["sub"], source, user.get("name", ""))


@protected.post("/logout")
def logout(request: Request, response: Response, session: dict = Depends(require_admin)) -> Dict[str, str]:
    revoke_token(session)
    response.delete_cookie(COOKIE_NAME, path="/", samesite="strict", secure=cookie_secure(request), httponly=True)
    return {"status": "ok"}


@protected.get("/session")
def current_session(session: dict = Depends(require_admin)) -> JSONResponse:
    return JSONResponse({"username": session["sub"], "name": session.get("name") or session["sub"],
                         "source": session.get("src", "local"), "expires_at": session["exp"]}, headers=NO_STORE)


@protected.get("/options")
def options() -> Dict[str, Any]:
    return {
        "builtin_icons": BUILTIN_ICON_NAMES,
        "stack_glyphs": STACK_GLYPHS,
        "categories": [{"id": cid, "label_he": he, "label_en": en} for cid, he, en in CATEGORIES if cid != "all"],
    }


# --------------------------------------------------------------------------- #
# Overview & rescan
# --------------------------------------------------------------------------- #


@protected.get("/overview")
def overview(db: Session = Depends(get_session)) -> JSONResponse:
    catalog = store.public_catalog()
    raw = store.raw_apps
    hidden = db.scalar(select(func.count()).select_from(AppOverride).where(AppOverride.hidden.is_(True))) or 0
    body = {
        "scan": store.status.model_dump(mode="json"),
        "counts": {
            "scanned_apps": len(raw),
            "visible_apps": len(catalog.apps),
            "hidden_apps": hidden,
            "installers": sum(len(a.files) for a in catalog.apps),
            "overrides": db.scalar(select(func.count()).select_from(AppOverride)) or 0,
            "stacks": db.scalar(select(func.count()).select_from(DevStack)) or 0,
            "platforms": db.scalar(select(func.count()).select_from(PlatformLink)) or 0,
            "feedback_new": db.scalar(
                select(func.count()).select_from(Feedback).where(Feedback.status == "new")) or 0,
        },
        "config": {
            "apps_root": str(config.APPS_ROOT),
            "auto_rescan_minutes": store.rescan_interval_minutes(),
            "installer_extensions": list(config.INSTALLER_EXTENSIONS),
            "max_scan_depth": config.MAX_SCAN_DEPTH,
            "icon_extraction": icons.extraction_available(),
            "msi_icon_extraction": icons.msi_extraction_available(),
            "favicon_fetch": config.FETCH_FAVICONS,
        },
    }
    return JSONResponse(body, headers=NO_STORE)


@protected.post("/rescan", status_code=202)
def rescan(body: RescanIn) -> Dict[str, Any]:
    started = store.trigger_rescan(invalidate=body.invalidate)
    return {"status": "started" if started else "already_running", "scan": store.status.model_dump(mode="json")}


def _settings_out() -> Dict[str, Any]:
    return {"auto_rescan_minutes": store.rescan_interval_minutes(), "default_rescan_minutes": config.AUTO_RESCAN_MINUTES}


@protected.get("/settings")
def get_settings() -> JSONResponse:
    return JSONResponse(_settings_out(), headers=NO_STORE)


@protected.put("/settings")
def update_settings(body: SettingsIn) -> Dict[str, Any]:
    store.set_rescan_interval(body.auto_rescan_minutes)
    log.info("Auto-rescan interval set to %d minutes", body.auto_rescan_minutes)
    return _settings_out()


# --------------------------------------------------------------------------- #
# Authentication settings (Keycloak SSO, LDAP / Active Directory, local admin)
# --------------------------------------------------------------------------- #


def _auth_out() -> Dict[str, Any]:
    cfg = sso.load()
    return {
        "sections": {s: auth_config.public_view(s) for s in auth_config.SECTIONS},
        "defaults": {s: auth_config.public_view(s, auth_config.env_defaults(s)) for s in auth_config.SECTIONS},
        "stored": {s: bool(auth_config.stored(s)) for s in auth_config.SECTIONS},
        "keycloak_endpoints": cfg.get("endpoints") or {},
        "keycloak_scopes": sso.scopes(cfg),
        "ldap_configured": directory.configured(),
        "lookup": directory.lookup_status(),
    }


def _section(section: str) -> str:
    if section not in auth_config.SECTIONS:
        raise HTTPException(status_code=404, detail="Unknown settings section")
    return section


def _auth_changed(section: str) -> None:
    if section == "keycloak":
        sso.clear_probe_cache()
    elif section == "docker":
        docker_registry.clear_cache()
    elif section != "nexus":
        directory.clear_cache()


@protected.get("/auth")
def get_auth() -> JSONResponse:
    return JSONResponse(_auth_out(), headers=NO_STORE)


@protected.put("/auth/{section}")
async def update_auth(section: str, request: Request, session: dict = Depends(require_admin)) -> JSONResponse:
    _section(section)
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    try:
        body = AUTH_SECTION_MODELS[section].model_validate(payload)
    except ValidationError as exc:
        errors = [{"loc": ["body", *e["loc"]], "msg": e["msg"], "type": e["type"]} for e in exc.errors(include_url=False,
                                                                                                        include_input=False)]
        return JSONResponse({"detail": errors}, status_code=422, headers=NO_STORE)
    data = body.model_dump()
    if section == "local_admin" and session.get("src") == "local" and data["username"] != session["sub"] \
            and not data.get("password") and not auth_config.load("local_admin").get("password_hash"):
        raise HTTPException(status_code=400, detail="Set a password before renaming the local admin account")
    auth_config.save(section, data)
    _auth_changed(section)
    log.info("Auth settings '%s' updated by %s", section, session["sub"])
    return JSONResponse(_auth_out(), headers=NO_STORE)


@protected.post("/auth/{section}/reset")
def reset_auth(section: str, session: dict = Depends(require_admin)) -> JSONResponse:
    auth_config.reset(_section(section))
    _auth_changed(section)
    log.info("Auth settings '%s' reset to environment defaults by %s", section, session["sub"])
    return JSONResponse(_auth_out(), headers=NO_STORE)


@protected.post("/auth/keycloak/test")
def test_keycloak() -> JSONResponse:
    cfg = sso.load()
    sso.clear_probe_cache()
    return JSONResponse(sso.test_endpoints(cfg), headers=NO_STORE)


@protected.post("/auth/ldap/test")
def test_ldap() -> JSONResponse:
    try:
        return JSONResponse(directory.test_connection(), headers=NO_STORE)
    except Exception as exc:  # noqa: BLE001 - always answer the admin button with JSON
        log.exception("LDAP test endpoint crashed")
        return JSONResponse({"ok": False, "bind": False, "base_found": False, "servers": [], "ms": 0,
                             "error": f"{type(exc).__name__}: {exc}"[:300]}, headers=NO_STORE)


@protected.post("/nexus/test")
def test_nexus(body: Optional[NexusSettingsIn] = None) -> JSONResponse:
    """Without a body the saved settings are tested; with one, the unsaved form values are."""
    cfg = auth_config.preview("nexus", body.model_dump()) if body else nexus.settings()
    try:
        return JSONResponse(nexus.test_connection(cfg), headers=NO_STORE)
    except Exception as exc:  # noqa: BLE001 - always answer the admin button with JSON
        log.exception("Nexus test endpoint crashed")
        return JSONResponse({"ok": False, "reachable": False, "auth": None, "repos": [], "ms": 0,
                             "error": f"{type(exc).__name__}: {exc}"[:300]}, headers=NO_STORE)


@protected.post("/docker/test")
def test_docker(body: Optional[DockerSettingsIn] = None) -> JSONResponse:
    """Registry reachability/credentials plus the Docker engine socket (needed for builds)."""
    cfg = docker_registry.settings(auth_config.preview("docker", body.model_dump()) if body else None)
    try:
        result = docker_registry.test_connection(cfg)
    except Exception as exc:  # noqa: BLE001 - always answer the admin button with JSON
        log.exception("Docker registry test endpoint crashed")
        result = {"ok": False, "reachable": False, "auth": None, "repositories": 0, "ms": 0,
                  "error": f"{type(exc).__name__}: {exc}"[:300]}
    result["engine"] = docker_build.engine_status()
    return JSONResponse(result, headers=NO_STORE)


# --------------------------------------------------------------------------- #
# Portal interface visibility
# --------------------------------------------------------------------------- #


def _ui_out() -> Dict[str, Any]:
    return {
        "visibility": portal_ui.load(),
        "defaults": portal_ui.DEFAULTS,
        "elements": [{"key": key, "group": group} for key, group in portal_ui.ELEMENTS],
        "stored": portal_ui.is_stored(),
    }


@protected.get("/ui")
def get_ui_visibility() -> JSONResponse:
    return JSONResponse(_ui_out(), headers=NO_STORE)


@protected.put("/ui")
def update_ui_visibility(body: VisibilityIn, session: dict = Depends(require_admin)) -> JSONResponse:
    portal_ui.save(body.visibility)
    hidden = sorted(k for k, v in portal_ui.load().items() if not v)
    log.info("Portal visibility updated by %s (hidden: %s)", session["sub"], ", ".join(hidden) or "none")
    return JSONResponse(_ui_out(), headers=NO_STORE)


@protected.get("/announcement")
def get_announcement() -> JSONResponse:
    return JSONResponse(portal_ui.announcement(), headers=NO_STORE)


@protected.put("/announcement")
def update_announcement(body: AnnouncementIn, session: dict = Depends(require_admin)) -> JSONResponse:
    item = portal_ui.save_announcement(body.model_dump(exclude={"republish"}), republish=body.republish)
    log.info("Announcement %s by %s (revision %s, %s)", "shown" if item["enabled"] else "hidden",
             session["sub"], item["revision"], item["severity"])
    return JSONResponse(item, headers=NO_STORE)


@protected.post("/ui/reset")
def reset_ui_visibility(session: dict = Depends(require_admin)) -> JSONResponse:
    portal_ui.reset()
    log.info("Portal visibility reset to defaults by %s", session["sub"])
    return JSONResponse(_ui_out(), headers=NO_STORE)


@protected.post("/auth/ldap/lookup")
def test_lookup(body: LdapLookupTestIn) -> JSONResponse:
    username = directory.normalize_username(body.username)
    if not username:
        raise HTTPException(status_code=422, detail="Enter a sAMAccountName such as ilayg")
    directory.clear_cache()
    started = time.monotonic()
    try:
        info = directory.lookup_user(username)
    except directory.DirectoryUnavailable as exc:
        return JSONResponse({"found": False, "error": str(exc), "ms": int((time.monotonic() - started) * 1000)},
                            headers=NO_STORE)
    return JSONResponse({"found": bool(info), "user": info, "ms": int((time.monotonic() - started) * 1000)},
                        headers=NO_STORE)


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #


def _feedback_out(row: Feedback) -> Dict[str, Any]:
    return {
        "id": row.id, "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "category": row.category, "subject": row.subject, "message": row.message,
        "user_name": row.user_name, "username": row.username, "email": row.email, "ip": row.ip,
        "status": row.status,
    }


def _require_feedback(db: Session, feedback_id: int) -> Feedback:
    row = db.get(Feedback, feedback_id)
    if not row:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return row


@protected.get("/feedback")
def list_feedback(status_filter: Optional[str] = Query(default=None, alias="status"), category: Optional[str] = None,
                  db: Session = Depends(get_session)) -> JSONResponse:
    query = select(Feedback).order_by(Feedback.created_at.desc(), Feedback.id.desc())
    if status_filter in FEEDBACK_STATUSES:
        query = query.where(Feedback.status == status_filter)
    if category in FEEDBACK_CATEGORIES:
        query = query.where(Feedback.category == category)
    items = [_feedback_out(row) for row in db.scalars(query.limit(2000))]
    counts = dict(db.execute(select(Feedback.status, func.count()).group_by(Feedback.status)).all())
    return JSONResponse({"items": items, "counts": {s: counts.get(s, 0) for s in FEEDBACK_STATUSES}},
                        headers=NO_STORE)


@protected.patch("/feedback/{feedback_id}")
def update_feedback(feedback_id: int, body: FeedbackStatusIn, db: Session = Depends(get_session)) -> Dict[str, Any]:
    row = _require_feedback(db, feedback_id)
    row.status = body.status
    db.commit()
    return _feedback_out(row)


@protected.delete("/feedback/{feedback_id}", status_code=204)
def delete_feedback(feedback_id: int, db: Session = Depends(get_session)) -> Response:
    db.delete(_require_feedback(db, feedback_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- #
# Applications (metadata overrides)
# --------------------------------------------------------------------------- #


def _override_out(row: Optional[AppOverride]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return AppOverrideOut(
        display_name=row.display_name, description_he=row.description_he, description_en=row.description_en,
        category=row.category, tags=row.tags, featured=row.featured, hidden=row.hidden,
        hidden_files=list(row.hidden_files or []), icon_file=row.icon_file,
    ).model_dump()


def _admin_app(app, row: Optional[AppOverride]) -> Dict[str, Any]:
    effective = apply_override(app, row)
    shown = effective or app
    hidden_files = set(row.hidden_files or []) if row else set()
    return {
        "id": app.id,
        "folder": app.folder,
        "known_key": app.known_key,
        "scanned_name": app.name,
        "name": shown.name,
        "category": shown.category,
        "description_he": shown.description_he,
        "description_en": shown.description_en,
        "scanned_description_he": app.description_he,
        "scanned_description_en": app.description_en,
        "tags": shown.tags,
        "featured": shown.featured,
        "icon_url": shown.icon_url,
        "icon_source": shown.icon_source,
        "latest_version": shown.latest_version,
        "total_size_human": app.total_size_human,
        "hidden": bool(row and row.hidden) or effective is None,
        "files": [{
            "rel_path": f.rel_path, "filename": f.filename, "version": f.version, "os": f.os, "ext": f.ext,
            "size_human": f.bundle_size_human or f.size_human, "modified": f.modified,
            "hidden": f.rel_path in hidden_files,
        } for f in app.files],
        "override": _override_out(row),
    }


def _require_app(app_id: str):
    app = store.raw_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found in the latest scan")
    return app


@protected.get("/apps")
def list_apps(db: Session = Depends(get_session)) -> JSONResponse:
    overrides = {o.app_id: o for o in db.scalars(select(AppOverride))}
    apps = [_admin_app(app, overrides.get(app.id)) for app in store.raw_apps]
    return JSONResponse(apps, headers=NO_STORE)


@protected.put("/apps/{app_id}")
def save_override(app_id: str, body: AppOverrideIn, db: Session = Depends(get_session)) -> Dict[str, Any]:
    app = _require_app(app_id)
    known_paths = {f.rel_path for f in app.files}
    row = db.get(AppOverride, app_id) or AppOverride(app_id=app_id, hidden_files=[])
    row.display_name = body.display_name
    row.description_he = body.description_he
    row.description_en = body.description_en
    row.category = body.category
    row.tags = body.tags
    row.featured = body.featured
    row.hidden = body.hidden
    row.hidden_files = [p for p in body.hidden_files if p in known_paths]
    db.add(row)
    db.commit()
    store.invalidate_view()
    return _admin_app(app, row)


@protected.delete("/apps/{app_id}")
def reset_override(app_id: str, db: Session = Depends(get_session)) -> Dict[str, Any]:
    row = db.get(AppOverride, app_id)
    if row:
        icons.delete_upload(row.icon_file)
        db.delete(row)
        db.commit()
    store.invalidate_view()
    app = store.raw_app(app_id)
    return _admin_app(app, None) if app else {"status": "deleted"}


def _decode_upload(body: IconUploadIn) -> bytes:
    data = body.data_base64.strip()
    if data.startswith("data:"):
        data = data.split(",", 1)[-1]
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="Invalid base64 payload")


def _store_icon(kind: str, obj_id: str, body: IconUploadIn) -> str:
    try:
        return icons.store_upload(kind, obj_id, _decode_upload(body))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@protected.post("/apps/{app_id}/icon")
def upload_app_icon(app_id: str, body: IconUploadIn, db: Session = Depends(get_session)) -> Dict[str, Any]:
    app = _require_app(app_id)
    filename = _store_icon("app", app_id, body)
    row = db.get(AppOverride, app_id) or AppOverride(app_id=app_id, hidden_files=[])
    if row.icon_file and row.icon_file != filename:
        icons.delete_upload(row.icon_file)
    row.icon_file = filename
    db.add(row)
    db.commit()
    store.invalidate_view()
    return _admin_app(app, row)


@protected.delete("/apps/{app_id}/icon")
def delete_app_icon(app_id: str, db: Session = Depends(get_session)) -> Dict[str, Any]:
    app = _require_app(app_id)
    row = db.get(AppOverride, app_id)
    if row and row.icon_file:
        icons.delete_upload(row.icon_file)
        row.icon_file = None
        db.commit()
    store.invalidate_view()
    return _admin_app(app, row)


# --------------------------------------------------------------------------- #
# Platforms
# --------------------------------------------------------------------------- #


def _platform_out(row: PlatformLink) -> Dict[str, Any]:
    return PlatformOut(
        id=row.id, name=row.name, url=row.url, description_he=row.description_he,
        description_en=row.description_en, icon=row.icon, color=row.color, sort_order=row.sort_order,
        icon_file=row.icon_file, favicon_file=row.favicon_file, icon_url=platform_icon_url(row),
    ).model_dump()


def _require_platform(db: Session, platform_id: int) -> PlatformLink:
    row = db.get(PlatformLink, platform_id)
    if not row:
        raise HTTPException(status_code=404, detail="Platform not found")
    return row


@protected.get("/platforms")
def list_platforms(db: Session = Depends(get_session)) -> List[Dict[str, Any]]:
    rows = db.scalars(select(PlatformLink).order_by(PlatformLink.sort_order, PlatformLink.id))
    return [_platform_out(row) for row in rows]


@protected.post("/platforms", status_code=201)
def create_platform(body: PlatformIn, db: Session = Depends(get_session)) -> Dict[str, Any]:
    row = PlatformLink(**body.model_dump(exclude={"sort_order"}))
    db.add(row)
    place_in_order(db, PlatformLink, row, body.sort_order)
    db.commit()
    store.invalidate_view()
    refresh_favicons_async([row.id], only_missing=False)
    return _platform_out(row)


@protected.put("/platforms/{platform_id}")
def update_platform(platform_id: int, body: PlatformIn, db: Session = Depends(get_session)) -> Dict[str, Any]:
    row = _require_platform(db, platform_id)
    url_changed = row.url != body.url
    for key, value in body.model_dump(exclude={"sort_order"}).items():
        setattr(row, key, value)
    if url_changed:
        row.favicon_file = None
    place_in_order(db, PlatformLink, row, body.sort_order)
    db.commit()
    store.invalidate_view()
    if url_changed:
        refresh_favicons_async([row.id], only_missing=False)
    return _platform_out(row)


@protected.delete("/platforms/{platform_id}", status_code=204)
def delete_platform(platform_id: int, db: Session = Depends(get_session)) -> Response:
    row = _require_platform(db, platform_id)
    icons.delete_upload(row.icon_file)
    db.delete(row)
    db.flush()
    normalize_order(db, PlatformLink)
    db.commit()
    store.invalidate_view()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@protected.post("/platforms/{platform_id}/icon")
def upload_platform_icon(platform_id: int, body: IconUploadIn, db: Session = Depends(get_session)) -> Dict[str, Any]:
    row = _require_platform(db, platform_id)
    filename = _store_icon("platform", str(platform_id), body)
    if row.icon_file and row.icon_file != filename:
        icons.delete_upload(row.icon_file)
    row.icon_file = filename
    db.commit()
    store.invalidate_view()
    return _platform_out(row)


@protected.delete("/platforms/{platform_id}/icon")
def delete_platform_icon(platform_id: int, db: Session = Depends(get_session)) -> Dict[str, Any]:
    row = _require_platform(db, platform_id)
    icons.delete_upload(row.icon_file)
    row.icon_file = None
    db.commit()
    store.invalidate_view()
    return _platform_out(row)


@protected.post("/platforms/{platform_id}/favicon")
def fetch_platform_favicon(platform_id: int, db: Session = Depends(get_session)) -> Dict[str, Any]:
    _require_platform(db, platform_id)
    db.commit()
    fetched = refresh_favicons([platform_id], only_missing=False)
    db.expire_all()
    row = _require_platform(db, platform_id)
    return {"fetched": bool(fetched), "platform": _platform_out(row)}


# --------------------------------------------------------------------------- #
# Dev stacks
# --------------------------------------------------------------------------- #


def _stack_out(row: DevStack) -> Dict[str, Any]:
    return StackOut(
        id=row.id, name_he=row.name_he, name_en=row.name_en, description_he=row.description_he,
        description_en=row.description_en, icon=row.icon, color=row.color, apps=list(row.apps or []),
        sort_order=row.sort_order,
    ).model_dump()


def _stack_slug(body: StackIn) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", body.name_en.lower()).strip("-")[:48]
    return slug or f"stack-{secrets.token_hex(3)}"


@protected.get("/stacks")
def list_stacks(db: Session = Depends(get_session)) -> List[Dict[str, Any]]:
    rows = db.scalars(select(DevStack).order_by(DevStack.sort_order, DevStack.name_en))
    return [_stack_out(row) for row in rows]


@protected.post("/stacks", status_code=201)
def create_stack(body: StackIn, db: Session = Depends(get_session)) -> Dict[str, Any]:
    stack_id = body.id or _stack_slug(body)
    if db.get(DevStack, stack_id):
        raise HTTPException(status_code=409, detail=f"A stack with id '{stack_id}' already exists")
    data = body.model_dump(exclude={"id", "sort_order"})
    row = DevStack(id=stack_id, **data)
    db.add(row)
    place_in_order(db, DevStack, row, body.sort_order)
    db.commit()
    store.invalidate_view()
    return _stack_out(row)


@protected.put("/stacks/{stack_id}")
def update_stack(stack_id: str, body: StackIn, db: Session = Depends(get_session)) -> Dict[str, Any]:
    row = db.get(DevStack, stack_id)
    if not row:
        raise HTTPException(status_code=404, detail="Stack not found")
    for key, value in body.model_dump(exclude={"id", "sort_order"}).items():
        setattr(row, key, value)
    place_in_order(db, DevStack, row, body.sort_order)
    db.commit()
    store.invalidate_view()
    return _stack_out(row)


@protected.delete("/stacks/{stack_id}", status_code=204)
def delete_stack(stack_id: str, db: Session = Depends(get_session)) -> Response:
    row = db.get(DevStack, stack_id)
    if not row:
        raise HTTPException(status_code=404, detail="Stack not found")
    db.delete(row)
    db.flush()
    normalize_order(db, DevStack)
    db.commit()
    store.invalidate_view()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
