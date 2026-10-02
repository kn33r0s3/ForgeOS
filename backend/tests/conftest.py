"""Shared fixtures — use in-memory SQLite to avoid modifying real storage/forge.db."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override environment BEFORE any app module imports settings or database engine.
# Keep the local-first default: tests must exercise the app without a shared
# API secret unless they explicitly set one for a security-specific case.
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
    """Fresh in-memory DB per test with all tables.

    Use a shared connection pool so sqlite:// memory tables remain visible to
    both the app dependency override and any startup hooks that touch the same
    engine during the request lifecycle.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    import app.database as database
    from app.database import Base
    from app import models  # noqa: F401 — register models
    from app.services import source_manager

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    database.engine = engine
    database.SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    Base.metadata.create_all(bind=engine)
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
