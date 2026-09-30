"""SQLite persistence via the SQLAlchemy ORM (no raw SQL anywhere)."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from . import config
from .knowledge import DEFAULT_BUNDLES, DEFAULT_PLATFORMS, ROLE_BUNDLES
from .scanner import read_json

log = logging.getLogger("pakal.db")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class PlatformLink(Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(String(500))
    description_he: Mapped[str] = mapped_column(String(300), default="")
    description_en: Mapped[str] = mapped_column(String(300), default="")
    icon: Mapped[str] = mapped_column(String(40), default="globe")
    color: Mapped[str] = mapped_column(String(7), default="#6366F1")
    icon_file: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    favicon_file: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class DevStack(Base):
    __tablename__ = "stacks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_he: Mapped[str] = mapped_column(String(80))
    name_en: Mapped[str] = mapped_column(String(80))
    description_he: Mapped[str] = mapped_column(String(300), default="")
    description_en: Mapped[str] = mapped_column(String(300), default="")
    icon: Mapped[str] = mapped_column(String(40), default="package")
    color: Mapped[str] = mapped_column(String(7), default="#6366F1")
    apps: Mapped[List[str]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class AppOverride(Base):
    __tablename__ = "app_overrides"

    app_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    description_he: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    featured: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden_files: Mapped[List[str]] = mapped_column(JSON, default=list)
    icon_file: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    category: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(150))
    message: Mapped[str] = mapped_column(Text)
    user_name: Mapped[str] = mapped_column(String(120), default="")
    username: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


engine = create_engine(
    f"sqlite:///{config.DATABASE_FILE.as_posix()}",
    connect_args={"check_same_thread": False, "timeout": 15},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with session_scope() as session:
        yield session


def _get_setting(session: Session, key: str) -> Optional[str]:
    row = session.get(Setting, key)
    return row.value if row else None


def _set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(Setting, key)
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))


def get_setting(key: str) -> Optional[str]:
    with session_scope() as session:
        return _get_setting(session, key)


def set_setting(key: str, value: str) -> None:
    with session_scope() as session:
        _set_setting(session, key, value)


def _ordered(session: Session, model: Any) -> List[Any]:
    tiebreak = model.id if model is PlatformLink else model.name_en
    return list(session.scalars(select(model).order_by(model.sort_order, tiebreak)))


def place_in_order(session: Session, model: Any, row: Any, position: Optional[int]) -> None:
    """Move `row` to 1-based `position` (None keeps its place, new rows go last); renumber the rest 1..N."""
    rows = _ordered(session, model)
    current = next((i for i, r in enumerate(rows) if r is row), None)
    others = [r for r in rows if r is not row]
    if position is None:
        index = current if current is not None else len(others)
    else:
        index = max(0, min(position - 1, len(others)))
    others.insert(index, row)
    for number, item in enumerate(others, start=1):
        item.sort_order = number


def normalize_order(session: Session, model: Any) -> None:
    for number, item in enumerate(_ordered(session, model), start=1):
        item.sort_order = number


def _seed_platforms(session: Session) -> None:
    legacy = read_json(config.APPS_ROOT / "_platforms.json")
    definitions: List[Dict[str, Any]] = legacy if isinstance(legacy, list) and legacy else DEFAULT_PLATFORMS
    for index, item in enumerate(definitions):
        if not isinstance(item, dict) or not item.get("name") or not item.get("url"):
            continue
        description = str(item.get("description") or "")
        session.add(PlatformLink(
            name=str(item["name"])[:80],
            url=str(item["url"])[:500],
            description_he=str(item.get("description_he") or description)[:300],
            description_en=str(item.get("description_en") or description)[:300],
            icon=str(item.get("icon") or "globe")[:40],
            color=str(item.get("color") or "#6366F1")[:7],
            sort_order=index,
        ))


def _seed_stacks(session: Session) -> None:
    legacy = read_json(config.APPS_ROOT / "_bundles.json")
    definitions: List[Dict[str, Any]] = legacy if isinstance(legacy, list) and legacy else DEFAULT_BUNDLES
    seen = set()
    for index, item in enumerate(definitions):
        if not isinstance(item, dict):
            continue
        stack_id = str(item.get("id") or f"stack-{index + 1}")[:64]
        if stack_id in seen:
            continue
        seen.add(stack_id)
        session.add(_stack_row(stack_id, item, index))


def _stack_row(stack_id: str, item: Dict[str, Any], sort_order: int) -> DevStack:
    name = str(item.get("name") or stack_id)
    description = str(item.get("description") or "")
    return DevStack(
        id=stack_id,
        name_he=str(item.get("name_he") or name)[:80],
        name_en=str(item.get("name_en") or name)[:80],
        description_he=str(item.get("description_he") or description)[:300],
        description_en=str(item.get("description_en") or description)[:300],
        icon=str(item.get("icon") or "package")[:40],
        color=str(item.get("color") or "#6366F1")[:7],
        apps=[str(a)[:120] for a in item.get("apps", []) if str(a).strip()][:100],
        sort_order=sort_order,
    )


def _add_role_bundles(session: Session) -> None:
    """Existing installations get the role presets once, placed first; ids already in use are left alone."""
    existing = set(session.scalars(select(DevStack.id)))
    for index, item in enumerate(ROLE_BUNDLES):
        if item["id"] not in existing:
            session.add(_stack_row(item["id"], item, index - len(ROLE_BUNDLES)))


def init_db() -> None:
    config.ensure_data_dirs()
    Base.metadata.create_all(engine)
    with session_scope() as session:
        if _get_setting(session, "seeded_platforms") is None:
            if session.scalars(select(PlatformLink.id).limit(1)).first() is None:
                _seed_platforms(session)
            _set_setting(session, "seeded_platforms", "1")
        if _get_setting(session, "seeded_stacks") is None:
            if session.scalars(select(DevStack.id).limit(1)).first() is None:
                _seed_stacks(session)
            _set_setting(session, "seeded_stacks", "1")
        if _get_setting(session, "seeded_role_bundles") is None:
            session.flush()
            _add_role_bundles(session)
            _set_setting(session, "seeded_role_bundles", "1")
        session.flush()
        normalize_order(session, PlatformLink)
        normalize_order(session, DevStack)
    log.info("Database ready at %s", config.DATABASE_FILE)
