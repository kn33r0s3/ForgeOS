"""Shared fixtures — use in-memory SQLite to avoid modifying real storage/forge.db."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override environment BEFORE any app module imports settings or database engine
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AI_PROVIDER"] = "mock"


def pytest_configure(config):
    db_url = os.environ.get("DATABASE_URL", "")
    if "forge.db" in db_url.lower():
        raise RuntimeError("CRITICAL: Pytest execution blocked: DATABASE_URL points to real historical storage/forge.db!")


@pytest.fixture
def db():
    """Fresh in-memory DB per test with all tables."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app import models  # noqa: F401 — register models
    from app.services import source_manager

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    source_manager.seed_default_sources(session)
    yield session
    session.close()
    engine.dispose()
