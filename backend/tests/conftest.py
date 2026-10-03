"""Shared fixtures — use in-memory SQLite to avoid modifying real storage/forge.db."""
import os
import sys
import pytest
from sqlalchemy.engine import make_url

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override environment BEFORE any app module imports settings or database engine.
# Keep the local-first default: tests must exercise the app without a shared
# API secret unless they explicitly set one for a security-specific case.
_postgres_test_url = os.getenv("FORGEOS_TEST_DATABASE_URL")
if _postgres_test_url:
    _test_url = make_url(_postgres_test_url)
    if (
        _test_url.get_backend_name() != "postgresql"
        or _test_url.host not in {"localhost", "127.0.0.1", "::1"}
        or _test_url.database not in {"forgeos_test", "forgeos_test_db"}
    ):
        raise RuntimeError(
            "FORGEOS_TEST_DATABASE_URL must target a loopback PostgreSQL database "
            "named forgeos_test or forgeos_test_db."
        )
    os.environ["DATABASE_URL"] = _postgres_test_url
else:
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AI_PROVIDER"] = "mock"
os.environ["FORGE_API_KEY"] = ""
os.environ["FORGEOS_LEGACY_INTELLIGENCE_ENABLED"] = "true"


def pytest_configure(config):
    db_url = os.environ.get("DATABASE_URL", "")
    if "forge.db" in db_url.lower():
        raise RuntimeError("CRITICAL: Pytest execution blocked: DATABASE_URL points to real historical storage/forge.db!")


@pytest.fixture
def db():
    """Fresh test database per test with all tables.

    FORGEOS_TEST_DATABASE_URL permits PostgreSQL dialect checks, but only on
    loopback and in a dedicated test database. SQLite stays the default.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    import app.database as database
    from app.database import Base
    from app import models  # noqa: F401 — register models
    from app.services import source_manager

    postgres_test_url = os.getenv("FORGEOS_TEST_DATABASE_URL")
    if postgres_test_url:
        engine = create_engine(postgres_test_url, pool_pre_ping=True)
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    database.engine = engine
    database.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    Base.metadata.create_all(bind=engine)
    if postgres_test_url:
        from sqlalchemy import text

        quote = engine.dialect.identifier_preparer.quote
        tables = ", ".join(quote(table.name) for table in Base.metadata.tables.values())
        with engine.begin() as connection:
            connection.execute(
                text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE")
            )
    session = database.SessionLocal()
    source_manager.seed_default_sources(session)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def govinfo_review_clock(monkeypatch):
    """Freeze source-registry validation at the notice's reviewed-through date."""
    from datetime import datetime as RealDateTime, timezone
    from app.services import source_clearance_registry

    class ReviewDateTime(RealDateTime):
        @classmethod
        def now(cls, tz=None):
            reviewed_at = RealDateTime(2026, 9, 25, 12, tzinfo=timezone.utc)
            return reviewed_at.astimezone(tz) if tz else reviewed_at.replace(tzinfo=None)

    monkeypatch.setattr(source_clearance_registry, "datetime", ReviewDateTime)
