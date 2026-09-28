"""Hypothesis profile configuration and shared test fixtures for the CPL-2 test suite."""

import os
import sys

# Set env vars BEFORE any app module is imported so that db/session.py picks
# up the SQLite URL instead of trying to connect to PostgreSQL.
os.environ.setdefault("JWT_SECRET", "test-secret-shared")
os.environ.setdefault("JWT_EXPIRY_MINUTES", "60")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

# Also reset the lazy engine cache if session was already imported with wrong URL
if "db.session" in sys.modules:
    import db.session as _sess
    _sess._engine = None
    _sess._SessionLocal = None

import pytest
from hypothesis import HealthCheck, settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

settings.register_profile(
    "fast",
    max_examples=3,
    deadline=None,
    suppress_health_check=list(HealthCheck),
    database=None,
)
settings.load_profile("fast")

SQLITE_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=SQLITE_ENGINE)

_tables_created = False


def init_test_db():
    """Create all tables in the shared test engine. Safe to call multiple times."""
    global _tables_created
    from db.models import Base

    if not _tables_created:
        Base.metadata.create_all(SQLITE_ENGINE)
        _tables_created = True


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_db():
    init_test_db()


def override_get_db():
    """FastAPI dependency override that yields a SQLite test session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
