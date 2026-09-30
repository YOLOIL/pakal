"""Validated Pydantic schemas for the admin API. Every text field is sanitised on input."""

from __future__ import annotations

import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .knowledge import CATEGORY_IDS
from .security import clean_text

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_ICON_RE = re.compile(r"^[a-z0-9-]{1,40}$")
_STACK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_APP_ID_RE = re.compile(r"^[a-z0-9\u0590-\u05ff][a-z0-9\u0590-\u05ff-]{0,119}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=20000)


def _color(value: str) -> str:
    value = value.strip()
    if not _COLOR_RE.match(value):
        raise ValueError("Color must be a hex value like #6366F1")
    return value.upper()


def _icon(value: str) -> str:
    value = value.strip().lower()
    if not _ICON_RE.match(value):
        raise ValueError("Invalid icon name")
    return value


def _required(value: str, max_len: int) -> str:
    cleaned = clean_text(value, max_len)
    if not cleaned:
        raise ValueError("Field is required")
    return cleaned


def validate_url(value: str) -> str:
    value = clean_text(value, 500)
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or any(c.isspace() for c in value):
        raise ValueError("URL must start with http:// or https://")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed")
    return value.rstrip("/") if parsed.path in ("", "/") else value


class LoginIn(StrictModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class SettingsIn(StrictModel):
    auto_rescan_minutes: int = Field(ge=0, le=10080)


class PlatformIn(StrictModel):
    name: str = Field(max_length=200)
    url: str = Field(max_length=600)
    description_he: str = Field(default="", max_length=1000)
    description_en: str = Field(default="", max_length=1000)
    icon: str = "globe"
    color: str = "#6366F1"
    # 1-based display position; omitted keeps the current place (new items go last).
    sort_order: Optional[int] = Field(default=None, ge=0, le=9999)

    @field_validator("name")
    @classmethod
    def v_name(cls, value: str) -> str:
        return _required(value, 80)

    @field_validator("url")
    @classmethod
    def v_url(cls, value: str) -> str:
        return validate_url(value)

    @field_validator("description_he", "description_en")
    @classmethod
    def v_description(cls, value: str) -> str:
        return clean_text(value, 300)

    @field_validator("icon")
    @classmethod
    def v_icon(cls, value: str) -> str:
        return _icon(value)

    @field_validator("color")
    @classmethod
    def v_color(cls, value: str) -> str:
        return _color(value)


class PlatformOut(BaseModel):
    id: int
    name: str
    url: str
    description_he: str
    description_en: str
    icon: str
    color: str
    sort_order: int
    icon_file: Optional[str] = None
    favicon_file: Optional[str] = None
    icon_url: Optional[str] = None


class StackIn(StrictModel):
    id: Optional[str] = Field(default=None, max_length=64)
    name_he: str = Field(max_length=200)
    name_en: str = Field(max_length=200)
    description_he: str = Field(default="", max_length=1000)
    description_en: str = Field(default="", max_length=1000)
    icon: str = "package"
    color: str = "#6366F1"
    apps: List[str] = Field(default_factory=list, max_length=100)
    sort_order: Optional[int] = Field(default=None, ge=0, le=9999)

    @field_validator("name_he", "name_en")
    @classmethod
    def v_names(cls, value: str) -> str:
        return _required(value, 80)

    @field_validator("description_he", "description_en")
    @classmethod
    def v_description(cls, value: str) -> str:
        return clean_text(value, 300)

    @field_validator("icon")
    @classmethod
    def v_icon(cls, value: str) -> str:
        return _icon(value)

    @field_validator("color")
    @classmethod
    def v_color(cls, value: str) -> str:
        return _color(value)

    @field_validator("id")
    @classmethod
    def _stack_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip().lower()
        if not _STACK_ID_RE.match(value):
            raise ValueError("ID may contain lowercase letters, digits and dashes only")
        return value

    @field_validator("apps")
    @classmethod
    def _apps(cls, value: List[str]) -> List[str]:
        result: List[str] = []
        for item in value:
            app_id = clean_text(item, 120).lower()
            if not _APP_ID_RE.match(app_id):
                raise ValueError(f"Invalid application id: {app_id!r}")
            if app_id not in result:
                result.append(app_id)
        return result


class StackOut(BaseModel):
    id: str
    name_he: str
    name_en: str
    description_he: str
    description_en: str
    icon: str
    color: str
    apps: List[str]
    sort_order: int


class AppOverrideIn(StrictModel):
    display_name: Optional[str] = Field(default=None, max_length=400)
    description_he: Optional[str] = Field(default=None, max_length=6000)
    description_en: Optional[str] = Field(default=None, max_length=6000)
    category: Optional[str] = None
    tags: Optional[List[str]] = Field(default=None, max_length=12)
    featured: Optional[bool] = None
    hidden: bool = False
    hidden_files: List[str] = Field(default_factory=list, max_length=5000)

    @field_validator("display_name")
    @classmethod
    def _display_name(cls, value: Optional[str]) -> Optional[str]:
        return clean_text(value, 120) or None

    @field_validator("description_he", "description_en")
    @classmethod
    def _description(cls, value: Optional[str]) -> Optional[str]:
        return clean_text(value, 2000, multiline=True) or None

    @field_validator("category")
    @classmethod
    def _category(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        if value not in CATEGORY_IDS:
            raise ValueError("Unknown category")
        return value

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        tags = []
        for tag in value:
            cleaned = clean_text(tag, 30)
            if cleaned and cleaned not in tags:
                tags.append(cleaned)
        return tags

    @field_validator("hidden_files")
    @classmethod
    def _hidden_files(cls, value: List[str]) -> List[str]:
        result = []
        for rel in value:
            rel = str(rel).strip()[:1000]
            if rel and ".." not in rel.split("/") and not rel.startswith("/") and rel not in result:
                result.append(rel)
        return result


class AppOverrideOut(BaseModel):
    display_name: Optional[str] = None
    description_he: Optional[str] = None
    description_en: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    featured: Optional[bool] = None
    hidden: bool = False
    hidden_files: List[str] = Field(default_factory=list)
    icon_file: Optional[str] = None


class IconUploadIn(StrictModel):
    data_base64: str = Field(min_length=8, max_length=800_000)


# --------------------------------------------------------------------------- #
# SSO settings & feedback
# --------------------------------------------------------------------------- #

_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9._:@-]{1,200}$")
_SCOPE_RE = re.compile(r"^[A-Za-z0-9_.:/-]{1,64}$")
_REALM_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_HINT_RE = re.compile(r"^[A-Za-z0-9._-]{0,100}$")
_ROLE_RE = re.compile(r"^[A-Za-z0-9._:/ -]{0,100}$")
_PROMPTS = {"none", "login", "consent", "select_account"}
_NETBIOS_RE = re.compile(r"^[A-Za-z0-9-]{0,15}$")
_DOMAIN_RE = re.compile(r"^(?=.{0,253}$)([A-Za-z0-9-]{1,63}\.)*[A-Za-z0-9-]{1,63}$")
_ADMIN_USER_RE = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")


def validate_endpoint(value: str) -> str:
    """Absolute http(s) URL kept byte-exact (Keycloak compares redirect URIs literally)."""
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("URL must be an absolute http:// or https:// address")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("URLs with credentials or fragments are not allowed")
    return value


def _secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Secret contains control characters")
    return value if value.strip() else None


def _dn(value: str) -> str:
    """Empty, or a syntactically valid distinguished name (CN=...,OU=...,DC=...)."""
    from ldap3.core.exceptions import LDAPInvalidDnError
    from ldap3.utils.dn import parse_dn

    value = value.strip()
    if not value:
        return ""
    if any(ord(c) < 32 for c in value):
        raise ValueError("DN contains control characters")
    try:
        parts = parse_dn(value)
    except (LDAPInvalidDnError, ValueError, IndexError):
        raise ValueError("Not a valid distinguished name - expected e.g. CN=Group,OU=Groups,DC=example,DC=com")
    if not parts:
        raise ValueError("Not a valid distinguished name")
    return value


class KeycloakSettingsIn(StrictModel):
    enabled: bool
    url: str = Field(max_length=300)
    realm: str = Field(max_length=100)
    client_id: str = Field(max_length=200)
    # Write-only: omitted/empty keeps the stored secret, clear_client_secret removes it.
    client_secret: Optional[str] = Field(default=None, max_length=500)
    clear_client_secret: bool = False
    redirect_uri: str = Field(max_length=600)
    post_logout_redirect_uri: str = Field(max_length=600)
    cooldown_after_logout_ms: int = Field(ge=0, le=600_000)
    idp_hint: str = Field(default="", max_length=100)
    prompt: str = Field(default="", max_length=100)
    admin_role: str = Field(default="", max_length=100)
    timeout_ms: int = Field(ge=500, le=60_000)
    tls_insecure: bool
    extra_scopes: str = Field(default="", max_length=400)

    @field_validator("url")
    @classmethod
    def v_url(cls, value: str) -> str:
        value = validate_endpoint(value).rstrip("/")
        if "/realms/" in value:
            raise ValueError("Enter only the Keycloak base URL (without /realms/...) - the realm has its own field")
        return value

    @field_validator("realm")
    @classmethod
    def v_realm(cls, value: str) -> str:
        value = value.strip()
        if not _REALM_RE.match(value):
            raise ValueError("Realm may contain letters, digits and . _ - only")
        return value

    @field_validator("client_id")
    @classmethod
    def v_client_id(cls, value: str) -> str:
        value = value.strip()
        if not _CLIENT_ID_RE.match(value):
            raise ValueError("Client ID may contain letters, digits and . _ : @ - only")
        return value

    @field_validator("client_secret")
    @classmethod
    def v_secret(cls, value: Optional[str]) -> Optional[str]:
        return _secret(value)

    @field_validator("redirect_uri", "post_logout_redirect_uri")
    @classmethod
    def v_uris(cls, value: str) -> str:
        return validate_endpoint(value)

    @field_validator("idp_hint")
    @classmethod
    def v_hint(cls, value: str) -> str:
        value = value.strip()
        if not _HINT_RE.match(value):
            raise ValueError("IdP hint is an identity-provider alias (letters, digits, . _ -)")
        return value

    @field_validator("prompt")
    @classmethod
    def v_prompt(cls, value: str) -> str:
        parts = value.split()
        if any(p not in _PROMPTS for p in parts):
            raise ValueError("Prompt must be empty or one of: login, consent, select_account, none")
        return " ".join(dict.fromkeys(parts))

    @field_validator("admin_role")
    @classmethod
    def v_role(cls, value: str) -> str:
        value = value.strip()
        if not _ROLE_RE.match(value):
            raise ValueError("Invalid role name")
        return value

    @field_validator("extra_scopes")
    @classmethod
    def v_scopes(cls, value: str) -> str:
        scopes = [s for s in dict.fromkeys(value.split()) if s not in ("openid", "profile", "email")]
        if len(scopes) > 20 or not all(_SCOPE_RE.match(s) for s in scopes):
            raise ValueError("Extra scopes must be space-separated identifiers")
        return " ".join(scopes)


class LdapServerIn(StrictModel):
    url: str = Field(default="", max_length=600)
    search_base: str = Field(default="", max_length=500)
    bind_dn: str = Field(default="", max_length=500)
    bind_password: Optional[str] = Field(default=None, max_length=500)
    clear_bind_password: bool = False

    @field_validator("url")
    @classmethod
    def v_url(cls, value: str) -> str:
        from .directory import parse_urls

        value = " ".join(value.split())
        if value:
            parse_urls(value)
        return value

    @field_validator("search_base", "bind_dn")
    @classmethod
    def v_dn(cls, value: str) -> str:
        return _dn(value)

    @field_validator("bind_password")
    @classmethod
    def v_secret(cls, value: Optional[str]) -> Optional[str]:
        return _secret(value)


class LdapGroupsIn(StrictModel):
    admin_group_dn: str = Field(default="", max_length=500)
    netbios_domain: str = Field(default="", max_length=15)

    @field_validator("admin_group_dn")
    @classmethod
    def v_dn(cls, value: str) -> str:
        return _dn(value)

    @field_validator("netbios_domain")
    @classmethod
    def v_netbios(cls, value: str) -> str:
        value = value.strip().upper()
        if not _NETBIOS_RE.match(value):
            raise ValueError("NetBIOS domain: up to 15 letters, digits or dashes (e.g. CORP)")
        return value


class LdapLookupIn(StrictModel):
    enabled: bool
    timeout_ms: int = Field(ge=100, le=30_000)
    pause_sec: int = Field(ge=0, le=86_400)


class LoginIdentityIn(StrictModel):
    email_domain: str = Field(default="", max_length=253)

    @field_validator("email_domain")
    @classmethod
    def v_domain(cls, value: str) -> str:
        value = value.strip().lstrip("@").lower()
        if value and not _DOMAIN_RE.match(value):
            raise ValueError("Enter a domain such as example.com (without @)")
        return value


class LocalAdminIn(StrictModel):
    username: str = Field(max_length=64)
    password: Optional[str] = Field(default=None, max_length=256)

    @field_validator("username")
    @classmethod
    def v_username(cls, value: str) -> str:
        value = value.strip()
        if not _ADMIN_USER_RE.match(value):
            raise ValueError("Username may contain letters, digits and . _ @ - only")
        return value

    @field_validator("password")
    @classmethod
    def v_password(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return _secret(value)


class NexusSettingsIn(StrictModel):
    enabled: bool
    url: str = Field(default="", max_length=300)
    username: str = Field(default="", max_length=200)
    # Write-only: omitted/empty keeps the stored password, clear_password removes it.
    password: Optional[str] = Field(default=None, max_length=500)
    clear_password: bool = False
    pypi_repo: str = Field(default="", max_length=1200)
    npm_repo: str = Field(default="", max_length=1200)
    powershell_repo: str = Field(default="", max_length=1200)
    tls_insecure: bool
    check_existing: bool
    max_upload_mb: int = Field(ge=1, le=10240)
    timeout_seconds: int = Field(ge=5, le=3600)

    @field_validator("url")
    @classmethod
    def v_url(cls, value: str) -> str:
        value = value.strip()
        return validate_endpoint(value).rstrip("/") if value else ""

    @field_validator("username")
    @classmethod
    def v_username(cls, value: str) -> str:
        value = value.strip()
        if any(ord(c) < 32 or c == ":" for c in value):
            raise ValueError("Username may not contain control characters or ':'")
        return value

    @field_validator("password")
    @classmethod
    def v_secret(cls, value: Optional[str]) -> Optional[str]:
        return _secret(value)

    @field_validator("pypi_repo", "npm_repo", "powershell_repo")
    @classmethod
    def v_repos(cls, value: str) -> str:
        from .nexus import MAX_REPOS_PER_KIND, REPO_NAME_RE, split_repos

        names = [n for n in dict.fromkeys(re.split(r"[\s,;]+", value)) if n]
        if len(names) > MAX_REPOS_PER_KIND:
            raise ValueError(f"At most {MAX_REPOS_PER_KIND} repositories per format")
        bad = [n for n in names if not REPO_NAME_RE.match(n)]
        if bad:
            raise ValueError(f"Invalid repository name: {bad[0]!r} (letters, digits, . _ - only)")
        return ", ".join(split_repos(", ".join(names)))


_REGISTRY_RE = re.compile(r"^(https?://)?[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*"
                          r"(:\d{1,5})?$")
_NAMESPACE_RE = re.compile(r"^[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*$")


class DockerSettingsIn(StrictModel):
    enabled: bool
    registry: str = Field(default="", max_length=300)
    username: str = Field(default="", max_length=200)
    # Write-only like the Nexus password; a blank username/password pair reuses the Nexus account.
    password: Optional[str] = Field(default=None, max_length=500)
    clear_password: bool = False
    namespace: str = Field(default="", max_length=120)
    tls_insecure: bool
    build_enabled: bool
    build_admin_only: bool
    max_context_mb: int = Field(ge=1, le=20480)
    build_timeout_seconds: int = Field(ge=60, le=86400)

    @field_validator("registry")
    @classmethod
    def v_registry(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if value and not _REGISTRY_RE.match(value):
            raise ValueError("Use host:port, optionally with http:// or https:// (no path)")
        return value

    @field_validator("username")
    @classmethod
    def v_username(cls, value: str) -> str:
        value = value.strip()
        if any(ord(c) < 32 or c == ":" for c in value):
            raise ValueError("Username may not contain control characters or ':'")
        return value

    @field_validator("password")
    @classmethod
    def v_secret(cls, value: Optional[str]) -> Optional[str]:
        return _secret(value)

    @field_validator("namespace")
    @classmethod
    def v_namespace(cls, value: str) -> str:
        value = value.strip().strip("/")
        if value and not _NAMESPACE_RE.match(value):
            raise ValueError("Lowercase letters, digits and . _ - separated by /")
        return value


AUTH_SECTION_MODELS = {
    "keycloak": KeycloakSettingsIn,
    "ldap_server": LdapServerIn,
    "ldap_groups": LdapGroupsIn,
    "ldap_lookup": LdapLookupIn,
    "login_identity": LoginIdentityIn,
    "local_admin": LocalAdminIn,
    "nexus": NexusSettingsIn,
    "docker": DockerSettingsIn,
}


class VisibilityIn(StrictModel):
    visibility: Dict[str, bool] = Field(max_length=100)

    @field_validator("visibility")
    @classmethod
    def v_keys(cls, value: Dict[str, bool]) -> Dict[str, bool]:
        from .portal_ui import DEFAULTS

        unknown = [k for k in value if k not in DEFAULTS]
        if unknown:
            raise ValueError(f"Unknown interface element: {unknown[0]!r}")
        return value


class AnnouncementIn(StrictModel):
    enabled: bool
    severity: str
    title: str = Field(default="", max_length=400)
    message: str = Field(default="", max_length=4000)
    # Show it again to users who already dismissed it, even when the text did not change.
    republish: bool = False

    @field_validator("severity")
    @classmethod
    def v_severity(cls, value: str) -> str:
        from .portal_ui import SEVERITIES

        if value not in SEVERITIES:
            raise ValueError("Unknown severity")
        return value

    @field_validator("title")
    @classmethod
    def v_title(cls, value: str) -> str:
        return clean_text(value, 120)

    @field_validator("message")
    @classmethod
    def v_message(cls, value: str) -> str:
        return clean_text(value, 1000, multiline=True)

    @model_validator(mode="after")
    def v_message_required(self) -> "AnnouncementIn":
        if self.enabled and not self.message:
            raise ValueError("A message is required to show the announcement")
        return self


class LdapLookupTestIn(StrictModel):
    username: str = Field(max_length=120)


class CredentialsIn(StrictModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


FEEDBACK_CATEGORIES = ("suggestion", "bug", "app_request")
FEEDBACK_STATUSES = ("new", "in_progress", "closed")


class FeedbackIn(StrictModel):
    category: str
    subject: str = Field(max_length=500)
    message: str = Field(max_length=12000)

    @field_validator("category")
    @classmethod
    def v_category(cls, value: str) -> str:
        if value not in FEEDBACK_CATEGORIES:
            raise ValueError("Unknown category")
        return value

    @field_validator("subject")
    @classmethod
    def v_subject(cls, value: str) -> str:
        return _required(value, 150)

    @field_validator("message")
    @classmethod
    def v_message(cls, value: str) -> str:
        cleaned = clean_text(value, 4000, multiline=True)
        if not cleaned:
            raise ValueError("Field is required")
        return cleaned


class FeedbackStatusIn(StrictModel):
    status: str

    @field_validator("status")
    @classmethod
    def v_status(cls, value: str) -> str:
        if value not in FEEDBACK_STATUSES:
            raise ValueError("Unknown status")
        return value
