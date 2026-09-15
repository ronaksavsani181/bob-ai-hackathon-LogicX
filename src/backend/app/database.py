"""
Database engine and session factory.
Uses SQLAlchemy 2.x synchronous engine (psycopg2 in production, aiosqlite/SQLite in tests).

The engine is created lazily on first use so that the DATABASE_URL environment
variable can be overridden in tests before the engine is constructed.
"""
from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

if TYPE_CHECKING:
    from sqlalchemy import Engine


# ---------------------------------------------------------------------------
# Declarative base — all ORM models inherit from this
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Lazy engine — constructed once on first access
# ---------------------------------------------------------------------------
_engine: "Engine | None" = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> "Engine":
    global _engine
    if _engine is None:
        from app.config import settings
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=settings.environment == "test",
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False
        )
    return _SessionLocal


# ---------------------------------------------------------------------------
# FastAPI dependency — yields a DB session and closes it after the request
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
