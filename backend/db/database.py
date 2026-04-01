"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings


def _normalize_database_url(url: str) -> str:
    if url.startswith("sqlite+aiosqlite:///"):
        return url.replace("sqlite+aiosqlite:///", "sqlite+pysqlite:///", 1)
    return url


def _ensure_sqlite_parent_dir(url: str) -> None:
    prefix = "sqlite+pysqlite:///"
    if not url.startswith(prefix):
        return
    raw_path = url.removeprefix(prefix)
    if raw_path == ":memory:":
        return
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
normalized_database_url = _normalize_database_url(settings.database_url)
_ensure_sqlite_parent_dir(normalized_database_url)
engine = create_engine(normalized_database_url, future=True, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def get_db_session() -> Iterator[Session]:
    """Yield a synchronous database session."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
