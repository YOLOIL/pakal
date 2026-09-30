"""FastAPI application factory: middleware, lifespan, routers and static mounts."""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import config
from .db import init_db
from .routes_actions import cleanup_temp_uploads
from .routes_actions import router as actions_router
from .routes_admin import protected as admin_protected_router
from .routes_admin import router as admin_router
from .docker_build import cleanup_stale_workdirs
from .routes_auth import router as auth_router
from .routes_docker import router as docker_router
from .routes_manage import cleanup_partial_uploads
from .routes_manage import router as manage_router
from .routes_public import router as public_router
from .store import refresh_favicons_async, store

log = logging.getLogger("pakal")

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'self'"
)
SANDBOX_POLICY = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
_USER_CONTENT_PREFIXES = ("/static/uploads/", "/static/extracted_icons/")


class SecurityHeadersMiddleware:
    """Pure ASGI middleware (keeps large file downloads streaming)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "same-origin")
                headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
                headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
                if path.startswith(_USER_CONTENT_PREFIXES):
                    headers["Content-Security-Policy"] = SANDBOX_POLICY
                else:
                    headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
                if path.startswith((config.ADMIN_SECURE_PATH, "/api/admin", "/api/manage")):
                    headers["X-Robots-Tag"] = "noindex, nofollow"
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _auto_rescan_loop(stop: threading.Event) -> None:
    """Rescan every N minutes; an admin change to N restarts the countdown immediately."""
    while not stop.is_set():
        store.schedule_changed.clear()
        minutes = store.rescan_interval_minutes()
        changed = store.schedule_changed.wait(minutes * 60 if minutes > 0 else None)
        if not changed and not stop.is_set():
            store.trigger_rescan()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    cleanup_temp_uploads()
    cleanup_stale_workdirs()
    threading.Thread(target=cleanup_partial_uploads, name="cleanup-partial-uploads", daemon=True).start()
    stop = threading.Event()
    store.load_cache()
    store.trigger_rescan()
    refresh_favicons_async(only_missing=True)
    threading.Thread(target=_auto_rescan_loop, args=(stop,), name="auto-rescan", daemon=True).start()
    yield
    stop.set()
    store.schedule_changed.set()


def create_app() -> FastAPI:
    config.ensure_data_dirs()
    application = FastAPI(
        title="PAKAL API",
        description="PAKAL - Software & Development Portal",
        version="2.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.include_router(public_router)
    application.include_router(admin_router)
    application.include_router(admin_protected_router)
    application.include_router(auth_router)
    application.include_router(actions_router)
    application.include_router(manage_router)
    application.include_router(docker_router)

    page_headers = {"Cache-Control": "no-cache"}

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(config.STATIC_DIR / "index.html", headers=page_headers)

    # The console lives only under ADMIN_SECURE_PATH; the well-known /admin is not routed and answers 404.
    admin_path = config.ADMIN_SECURE_PATH

    @application.get(admin_path, include_in_schema=False)
    @application.get(admin_path + "/", include_in_schema=False)
    @application.get(admin_path + "/{view:path}", include_in_schema=False)
    def admin_page(view: str = "") -> FileResponse:
        return FileResponse(config.STATIC_DIR / "admin.html", headers={"Cache-Control": "no-store"})

    application.mount("/static/extracted_icons", StaticFiles(directory=config.EXTRACTED_ICONS_DIR),
                      name="extracted_icons")
    application.mount("/static/uploads", StaticFiles(directory=config.UPLOADS_DIR), name="uploads")
    application.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
    return application


app = create_app()
