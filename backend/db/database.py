"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
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


@event.listens_for(engine, "connect")
def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    try:
        # Some Windows dev environments deny journal-file deletion, which makes SQLite
        # fail with "disk I/O error" on ordinary writes. Keep local dev usable by
        # disabling rollback journals for this single-user desktop database.
        cursor.execute("PRAGMA journal_mode=OFF")
        cursor.execute("PRAGMA synchronous=OFF")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


def _sqlite_table_exists(connection, table_name: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).first()
    return row is not None


def _sqlite_column_names(connection, table_name: str) -> set[str]:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").all()
    return {row[1] for row in rows}


def _ensure_sqlite_compat_schema() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as connection:
        if _sqlite_table_exists(connection, "calendar_events"):
            column_names = _sqlite_column_names(connection, "calendar_events")
            if "status" not in column_names:
                connection.exec_driver_sql(
                    "ALTER TABLE calendar_events ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'not_started'"
                )
        if _sqlite_table_exists(connection, "task_history"):
            column_names = _sqlite_column_names(connection, "task_history")
            if "token_count" not in column_names:
                connection.exec_driver_sql(
                    "ALTER TABLE task_history ADD COLUMN token_count INTEGER NOT NULL DEFAULT 0"
                )
            if "importance_score" not in column_names:
                connection.exec_driver_sql(
                    "ALTER TABLE task_history ADD COLUMN importance_score FLOAT NOT NULL DEFAULT 1.0"
                )


def initialize_database() -> None:
    from backend.db.models import Base

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_compat_schema()


def get_db_session() -> Iterator[Session]:
    """Yield a synchronous database session."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
