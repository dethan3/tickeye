"""SQLAlchemy engine and session construction."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker


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
    return create_engine(
        database_url,
        connect_args=connect_args,
        echo=echo,
        pool_pre_ping=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create the transaction boundary used by repositories."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
