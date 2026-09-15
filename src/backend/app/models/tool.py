"""
Tool and Chamber models.

tool → chamber (one tool has many chambers)
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tool(Base):
    """Physical fab tool (e.g. an etch tool, lithography scanner, CVD furnace)."""

    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    tool_type: Mapped[str] = mapped_column(String(64), nullable=False)
    fab_area: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    chambers: Mapped[list["Chamber"]] = relationship(
        "Chamber", back_populates="tool", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tool id={self.id} name={self.name!r} type={self.tool_type!r}>"


class Chamber(Base):
    """Individual process chamber within a tool."""

    __tablename__ = "chambers"
    __table_args__ = (
        UniqueConstraint("tool_id", "name", name="uq_chamber_tool_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chamber_index: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    tool: Mapped["Tool"] = relationship("Tool", back_populates="chambers")
    runs: Mapped[list["Run"]] = relationship(  # type: ignore[name-defined]
        "Run", back_populates="chamber"
    )
    maintenance_events: Mapped[list["MaintenanceEvent"]] = relationship(  # type: ignore[name-defined]
        "MaintenanceEvent", back_populates="chamber", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Chamber id={self.id} name={self.name!r} tool_id={self.tool_id}>"
