"""Database engine factory with SQLite and MySQL support."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine


DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "estimation.db"


def get_engine(db_path: Path | str | None = None, db_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine from either a file path (SQLite) or a URL.

    Priority:
    1. Explicit db_url parameter
    2. DB_URL environment variable
    3. Explicit db_path parameter (SQLite)
    4. DB_PATH environment variable (SQLite)
    5. Default SQLite path
    """
    url = db_url or os.environ.get("DB_URL")

    if url:
        engine = create_engine(url, echo=False, pool_pre_ping=True)
    else:
        path = db_path or os.environ.get("DB_PATH") or DEFAULT_DB_PATH
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{path}", echo=False)

    # Enable WAL mode and foreign keys for SQLite
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

    return engine


def get_db_type(engine: Engine) -> str:
    """Return the database backend type: 'sqlite' or 'mysql'."""
    return engine.dialect.name
