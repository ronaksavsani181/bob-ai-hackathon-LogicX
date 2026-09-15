"""
pytest configuration and shared fixtures for backend tests.

Uses SQLite in-memory for speed and CI portability.
Sets DATABASE_URL to SQLite BEFORE importing any app modules so the lazy
engine in database.py never tries to connect to Postgres.
"""
import os

# Override DATABASE_URL before any app module is imported
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Now safe to import app modules
from app.database import Base


# ---------------------------------------------------------------------------
# SQLite in-memory engine (session-scoped — one schema for the test session)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def engine():
    """Session-scoped in-memory SQLite engine with all tables created."""
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Enable FK enforcement in SQLite
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Import all ORM models so their tables are registered on Base.metadata
    import app.models  # noqa: F401

    Base.metadata.create_all(_engine)

    yield _engine

    Base.metadata.drop_all(_engine)


# ---------------------------------------------------------------------------
# Per-test session that rolls back after each test
# ---------------------------------------------------------------------------
@pytest.fixture()
def db(engine) -> Session:
    """Function-scoped DB session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
