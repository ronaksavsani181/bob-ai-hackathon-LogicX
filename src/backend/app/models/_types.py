"""
Portable JSON column type.

Uses PostgreSQL JSONB when running against PostgreSQL,
falls back to SQLAlchemy's built-in JSON (stored as TEXT in SQLite)
when running in the test environment.

Production behaviour (PostgreSQL): JSONB — binary storage, indexable, operators.
Test behaviour (SQLite): JSON — text-serialised, functionally equivalent for tests.
"""
import os

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB


def _use_postgres() -> bool:
    db_url = os.environ.get("DATABASE_URL", "")
    return "postgresql" in db_url or "postgres" in db_url


# JsonColumn: use JSONB for PostgreSQL, JSON for everything else (SQLite in tests)
JsonColumn = _PG_JSONB if _use_postgres() else JSON
