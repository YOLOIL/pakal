"""Runtime configuration, read once from environment variables."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Tuple


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
BUILTIN_ICONS_DIR = STATIC_DIR / "icons"

APPS_ROOT = Path(os.environ.get("APPS_ROOT", "/mnt/apps"))
PORT = _env_int("PORT", 8971)

# Writable state: SQLite database, scan cache, extracted icons and admin uploads.
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))
CACHE_FILE = Path(os.environ.get("CACHE_FILE", str(DATA_DIR / "cache.json")))
DATABASE_FILE = Path(os.environ.get("DATABASE_FILE", str(DATA_DIR / "pakal.db")))
EXTRACTED_ICONS_DIR = DATA_DIR / "extracted_icons"
UPLOADS_DIR = DATA_DIR / "uploads"

AUTO_RESCAN_MINUTES = _env_int("AUTO_RESCAN_MINUTES", 30)
INITIAL_SCAN_WAIT_SECONDS = _env_float("INITIAL_SCAN_WAIT_SECONDS", 20)
MAX_SCAN_DEPTH = _env_int("MAX_SCAN_DEPTH", 2)
PAYLOAD_THRESHOLD = _env_int("PAYLOAD_THRESHOLD", 15)

INSTALLER_EXTENSIONS: Tuple[str, ...] = tuple(
    ext.strip().lower() if ext.strip().startswith(".") else "." + ext.strip().lower()
    for ext in os.environ.get("INSTALLER_EXTENSIONS", ".exe,.msi,.iso,.zip").split(",")
    if ext.strip()
)

EXTRACT_EXE_ICONS = _env_bool("EXTRACT_EXE_ICONS", True)
EXTRACT_MSI_ICONS = _env_bool("EXTRACT_MSI_ICONS", True)
MAX_ICON_EXE_MB = _env_int("MAX_ICON_EXE_MB", 4096)

FETCH_FAVICONS = _env_bool("FETCH_FAVICONS", True)
FAVICON_TIMEOUT_SECONDS = _env_float("FAVICON_TIMEOUT_SECONDS", 5)
# Internal services typically use an organisational CA that is not in the container trust store.
FAVICON_VERIFY_TLS = _env_bool("FAVICON_VERIFY_TLS", False)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "pakal").strip() or "pakal"
# No built-in password: without ADMIN_PASSWORD_HASH / LOCAL_ADMIN_PASSWORD (or one saved in the console)
# the emergency local login is disabled.
# Some stack managers pass .env quotes through literally; a bcrypt hash never contains quotes.
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "").strip().strip("'\"")
JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()
JWT_TTL_MINUTES = _env_int("JWT_TTL_MINUTES", 480)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "auto").strip().lower()
LOGIN_MAX_ATTEMPTS = _env_int("LOGIN_MAX_ATTEMPTS", 5)
LOGIN_WINDOW_SECONDS = _env_int("LOGIN_WINDOW_SECONDS", 300)

MAX_UPLOAD_BYTES = _env_int("MAX_UPLOAD_KB", 512) * 1024

DEFAULT_ADMIN_SECURE_PATH = "/pakal-management-console"
_ADMIN_PATH_RE = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9._~-]{5,63}$")
_RESERVED_PATHS = {"/admin", "/api", "/static", "/health"}


def _admin_secure_path() -> str:
    """Single path segment the admin console is served under; the legacy /admin answers 404."""
    raw = os.environ.get("ADMIN_SECURE_PATH", "").strip().strip("'\"").strip()
    if not raw:
        return DEFAULT_ADMIN_SECURE_PATH
    value = "/" + raw.strip("/")
    if not _ADMIN_PATH_RE.match(value) or value.lower() in _RESERVED_PATHS:
        logging.getLogger("pakal.config").error(
            "Ignoring ADMIN_SECURE_PATH=%r (one path segment, 6-64 of A-Z a-z 0-9 . _ ~ -); using %s",
            raw, DEFAULT_ADMIN_SECURE_PATH)
        return DEFAULT_ADMIN_SECURE_PATH
    return value


ADMIN_SECURE_PATH = _admin_secure_path()
# Installers an admin adds from the portal's app card are written straight into the app's folder.
ADMIN_APP_UPLOAD_MAX_MB = _env_int("ADMIN_APP_UPLOAD_MAX_MB", 8192)

def _env_str(name: str, default: str = "") -> str:
    # Stack managers sometimes pass .env quotes through literally.
    return os.environ.get(name, default).strip().strip("'\"").strip()


# Authentication defaults. Every value can be overridden in the admin console (settings table wins).
# Organisation-specific values (URLs, DNs, credentials) come from .env; see .env.example.
KEYCLOAK_ENABLED = _env_bool("KEYCLOAK_ENABLED", True)
KEYCLOAK_URL = _env_str("KEYCLOAK_URL")
KEYCLOAK_REALM = _env_str("KEYCLOAK_REALM", "master")
KEYCLOAK_CLIENT_ID = _env_str("KEYCLOAK_CLIENT_ID", "pakal")
KEYCLOAK_CLIENT_SECRET = _env_str("KEYCLOAK_CLIENT_SECRET")
KEYCLOAK_REDIRECT_URI = _env_str("KEYCLOAK_REDIRECT_URI")
KEYCLOAK_POST_LOGOUT_REDIRECT_URI = _env_str("KEYCLOAK_POST_LOGOUT_REDIRECT_URI")
KEYCLOAK_SSO_COOLDOWN_AFTER_LOGOUT_MS = _env_int("KEYCLOAK_SSO_COOLDOWN_AFTER_LOGOUT_MS", 10000)
KEYCLOAK_IDP_HINT = _env_str("KEYCLOAK_IDP_HINT")
KEYCLOAK_PROMPT = _env_str("KEYCLOAK_PROMPT")
KEYCLOAK_ADMIN_ROLE = _env_str("KEYCLOAK_ADMIN_ROLE", "admin")
KEYCLOAK_TIMEOUT_MS = _env_int("KEYCLOAK_TIMEOUT_MS", 5000)
KEYCLOAK_TLS_INSECURE = _env_bool("KEYCLOAK_TLS_INSECURE", True)
# Scopes requested on top of "openid profile email" (space separated). Unknown scopes make Keycloak fail the login.
KEYCLOAK_EXTRA_SCOPES = _env_str("KEYCLOAK_EXTRA_SCOPES")
KEYCLOAK_USER_FIELD = _env_str("KEYCLOAK_USER_FIELD", "sAMAccountName")
# PEM bundle of the organisational CA, used when KEYCLOAK_TLS_INSECURE is off.
KEYCLOAK_CA_BUNDLE = _env_str("KEYCLOAK_CA_BUNDLE")
USER_SESSION_MINUTES = _env_int("USER_SESSION_MINUTES", 480)

LDAP_URL = _env_str("LDAP_URL")
LDAP_SEARCH_BASE = _env_str("LDAP_SEARCH_BASE")
LDAP_ADMIN = _env_str("LDAP_ADMIN")
LDAP_PASSWORD = os.environ.get("LDAP_PASSWORD", "")
LDAP_ADMIN_GROUP_DN = _env_str("LDAP_ADMIN_GROUP_DN")
LDAP_NETBIOS_DOMAIN = _env_str("LDAP_NETBIOS_DOMAIN")
LDAP_DISPLAY_NAME_LOOKUP = _env_bool("LDAP_DISPLAY_NAME_LOOKUP", True)
LDAP_LOOKUP_TIMEOUT_MS = _env_int("LDAP_LOOKUP_TIMEOUT_MS", 1500)
LDAP_DISPLAY_NAME_PAUSE_SEC = _env_int("LDAP_DISPLAY_NAME_PAUSE_SEC", 120)
LDAP_AUTH_TIMEOUT_MS = _env_int("LDAP_AUTH_TIMEOUT_MS", 5000)
# Only relevant for ldaps:// - internal domain controllers usually present an organisational CA.
LDAP_TLS_INSECURE = _env_bool("LDAP_TLS_INSECURE", True)
USER_EMAIL_DOMAIN = _env_str("USER_EMAIL_DOMAIN")

# Local emergency admin. LOCAL_ADMIN_PASSWORD (plain) wins over ADMIN_PASSWORD_HASH when set.
LOCAL_ADMIN_USERNAME = _env_str("LOCAL_ADMIN_USERNAME", ADMIN_USERNAME)
LOCAL_ADMIN_PASSWORD = os.environ.get("LOCAL_ADMIN_PASSWORD", "")

FEEDBACK_MAX_PER_WINDOW = _env_int("FEEDBACK_MAX_PER_WINDOW", 5)
FEEDBACK_WINDOW_SECONDS = _env_int("FEEDBACK_WINDOW_SECONDS", 600)

# Nexus bulk package uploader (Actions tab). No server or repository is built in: the connection is
# configured in the admin console (stored in the settings table, which wins), or seeded from these variables.
NEXUS_ENABLED = _env_bool("NEXUS_ENABLED", True)
NEXUS_URL = _env_str("NEXUS_URL")
NEXUS_USERNAME = _env_str("NEXUS_USERNAME")
NEXUS_PASSWORD = os.environ.get("NEXUS_PASSWORD", "")
# Comma separated; the first repository of each format is the default upload target.
NEXUS_PYPI_REPO = _env_str("NEXUS_PYPI_REPO")
NEXUS_NPM_REPO = _env_str("NEXUS_NPM_REPO")
NEXUS_POWERSHELL_REPO = _env_str("NEXUS_POWERSHELL_REPO")
NEXUS_TLS_INSECURE = _env_bool("NEXUS_TLS_INSECURE", True)
NEXUS_CHECK_EXISTING = _env_bool("NEXUS_CHECK_EXISTING", True)
NEXUS_MAX_UPLOAD_MB = _env_int("NEXUS_MAX_UPLOAD_MB", 1024)
NEXUS_TIMEOUT_SECONDS = _env_int("NEXUS_TIMEOUT_SECONDS", 300)
UPLOAD_TMP_DIR = DATA_DIR / "upload-tmp"

# Docker: registry browser (Docker tab) and ZIP-to-image builds (Actions tab). Managed in the admin console
# like the Nexus settings; these variables only seed it. A blank registry username reuses the Nexus account.
NEXUS_DOCKER_REGISTRY = _env_str("NEXUS_DOCKER_REGISTRY")
NEXUS_DOCKER_USERNAME = _env_str("NEXUS_DOCKER_USERNAME")
NEXUS_DOCKER_PASSWORD = os.environ.get("NEXUS_DOCKER_PASSWORD", "")
NEXUS_DOCKER_NAMESPACE = _env_str("NEXUS_DOCKER_NAMESPACE")
DOCKER_BUILD_ENABLED = _env_bool("DOCKER_BUILD_ENABLED", True)
DOCKER_BUILD_ADMIN_ONLY = _env_bool("DOCKER_BUILD_ADMIN_ONLY", True)
DOCKER_MAX_CONTEXT_MB = _env_int("DOCKER_MAX_CONTEXT_MB", 2048)
DOCKER_BUILD_TIMEOUT_SECONDS = _env_int("DOCKER_BUILD_TIMEOUT_SECONDS", 3600)
# Host engine endpoint: a unix socket path (mounted from the host) or tcp://host:2375 for development.
DOCKER_SOCKET = _env_str("DOCKER_SOCKET", "/var/run/docker.sock")
DOCKER_MAX_CONCURRENT_BUILDS = max(1, _env_int("DOCKER_MAX_CONCURRENT_BUILDS", 2))
DOCKER_BUILD_DIR = DATA_DIR / "docker-builds"

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def ensure_data_dirs() -> None:
    for path in (DATA_DIR, EXTRACTED_ICONS_DIR, UPLOADS_DIR, UPLOAD_TMP_DIR, DOCKER_BUILD_DIR, CACHE_FILE.parent,
                 DATABASE_FILE.parent):
        path.mkdir(parents=True, exist_ok=True)
