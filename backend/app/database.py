"""
Database engine + session management.

SQLite is used for the local MVP: zero setup, one file, tiny footprint
(fits the "low RAM/storage laptop" constraint). Because access happens
through SQLAlchemy's ORM layer, moving to Postgres/MySQL for the SaaS
version later is a one-line change to DATABASE_URL plus removing the
sqlite-only connect_args below.
"""

import os
import sys
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings


def _database_url() -> str:
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit
    # Vercel functions have no durable disk. /tmp is the writable path so
    # the existing SQLite engine can boot. Rows live for that instance only.
    if os.getenv("VERCEL"):
        return "sqlite:////tmp/forge.db"
    return getattr(settings, "DATABASE_URL", "sqlite:///:memory:")


def _configure_engine() -> None:
    global engine, SessionLocal
    database_url = _database_url()
    if "engine" not in globals():
        engine = None
    if engine is not None and str(engine.url) == database_url:
        return

    # Make sure the storage/ directory exists before SQLite tries to create
    # the file in it.
    if database_url.startswith("sqlite"):
        db_path = database_url.split("sqlite:///")[-1]
        is_pytest = "pytest" in sys.modules or bool(os.getenv("PYTEST_CURRENT_TEST"))
        if is_pytest and "forge.db" in database_url.lower():
            raise RuntimeError(
                "CRITICAL: Test database safety violation! Tests must never run against real historical storage/forge.db"
            )
        if db_path != ":memory:" and not os.path.isabs(db_path):
            raise RuntimeError(
                "SQLite DATABASE_URL must be absolute; use the canonical repository storage/forge.db "
                "or sqlite:////app/storage/forge.db in containers"
            )
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        print(f"[database] resolved SQLite path: {os.path.abspath(db_path)}", file=sys.stderr)

    connect_args = ({"check_same_thread": False} if database_url.startswith("sqlite") else {})
    engine = create_engine(database_url, connect_args=connect_args)

    if database_url.startswith("sqlite"):
        # WAL journal mode lets readers and a writer work concurrently instead
        # of taking an exclusive file lock for every write — the daily
        # scheduler, the worker, and a manually-run cycle can all touch
        # forge.db without tripping each other into "database is locked" /
        # "disk I/O error" the way the default rollback-journal mode does
        # under concurrent access. busy_timeout makes SQLite retry internally
        # for up to 30s on a transient lock instead of failing immediately.
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


_configure_engine()

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    _configure_engine()
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist yet, then patch any
    existing tables with columns added since the DB file was created.
    Called on startup. Safe to run every time — never drops data."""
    _configure_engine()
    # Import models here so they register with Base.metadata before
    # create_all runs, without causing circular imports at module load.
    from app import models  # noqa: F401
    from app.migrations import run_migrations

    Base.metadata.create_all(bind=engine)
    run_migrations(engine)
    from app.services.belief_engine import repair_historical_beliefs
    from app.services.world_graph import seed_core_types

    with SessionLocal() as db:
        seed_core_types(db)
        db.commit()
        repair_historical_beliefs(db)
