"""SQLAlchemy session factory for the CPL-2 Scheduling System.

Creates the synchronous engine and ``SessionLocal`` factory from the
``DATABASE_URL`` environment variable.

The engine is created lazily on first access so that the ``DATABASE_URL``
environment variable can be overridden in tests (e.g. set to SQLite in
conftest.py) before the engine is initialised.

Usage (in FastAPI dependency functions)::

    from db.session import SessionLocal

Design references: Requirements 11.3
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            # Use an absolute path so the DB is always at backend/cpl2_dev.db
            # regardless of which directory the server is launched from.
            _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _db_path = os.path.join(_backend_dir, "cpl2_dev.db")
            url = f"sqlite:///{_db_path}"
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            future=True,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        )
    return _engine


def _get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_get_engine(),
        )
    return _SessionLocal


class _LazySession:
    """Proxy that creates the real SessionLocal on first call."""

    def __call__(self, *args, **kwargs):
        return _get_session_local()(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(_get_session_local(), item)


SessionLocal = _LazySession()
