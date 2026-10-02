"""Engine, sessions, and Alembic upgrades for the service database."""

from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    """An engine for `url`. SQLite connections may be used from the request thread."""
    kwargs: dict[str, Any] = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Sessions that keep attributes after commit, so a route can read them."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def upgrade_database(database_url: str) -> None:
    """Apply the service migrations to `database_url`."""
    command.upgrade(_alembic_config(database_url), "head")


def _alembic_config(database_url: str) -> Config:
    ini = Path(__file__).resolve().parent / "migrations" / "alembic.ini"
    config = Config(str(ini))
    # ConfigParser treats % as interpolation. Escape it before storing the URL.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config
