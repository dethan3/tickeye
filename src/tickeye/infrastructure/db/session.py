"""SQLAlchemy engine and session construction."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry


def _enable_sqlite_foreign_keys(
    dbapi_connection: object,
    _connection_record: ConnectionPoolEntry,
) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def _ensure_sqlite_directory(database_url: str) -> None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return
    if not url.database or url.database == ":memory:":
        return

    Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create an engine while applying SQLite's local-thread requirement."""

    _ensure_sqlite_directory(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        echo=echo,
        pool_pre_ping=True,
    )
    if database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the transaction boundary used by repositories."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
