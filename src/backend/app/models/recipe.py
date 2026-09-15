"""
Recipe model.

Recipes are referenced by Runs.  They are independent of the tool/lot hierarchy
and hold nominal process parameters as JSONB for flexibility.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._types import JsonColumn

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Recipe(Base):
    """Process recipe — versioned, with nominal parameter targets stored as JSONB."""

    __tablename__ = "recipes"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_recipe_name_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    process_step: Mapped[str] = mapped_column(String(64), nullable=False)
    # Stores nominal parameter targets, limits, units as structured JSON
    nominal_params: Mapped[dict] = mapped_column(JsonColumn, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    runs: Mapped[list["Run"]] = relationship(  # type: ignore[name-defined]
        "Run", back_populates="recipe"
    )

    def __repr__(self) -> str:
        return f"<Recipe id={self.id} name={self.name!r} version={self.version!r}>"
