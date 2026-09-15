"""
Run, ProcessParameter and TraceData models.

wafer → run (a wafer passes through one or more process steps/runs)
chamber → run (each run executes in a specific chamber)
recipe → run (the recipe governs the run)
run → process_parameters (measured parameter values for this run)
run → trace_data (time-series channel data captured during the run)
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Run(Base):
    """A single process run — one wafer through one chamber using one recipe."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wafer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chamber_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chambers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed", index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    wafer: Mapped["Wafer"] = relationship("Wafer", back_populates="runs")  # type: ignore[name-defined]
    chamber: Mapped["Chamber"] = relationship("Chamber", back_populates="runs")  # type: ignore[name-defined]
    recipe: Mapped["Recipe"] = relationship("Recipe", back_populates="runs")  # type: ignore[name-defined]
    process_parameters: Mapped[list["ProcessParameter"]] = relationship(
        "ProcessParameter", back_populates="run", cascade="all, delete-orphan"
    )
    trace_data: Mapped[list["TraceData"]] = relationship(
        "TraceData", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Run id={self.id} wafer_id={self.wafer_id} "
            f"chamber_id={self.chamber_id} status={self.run_status!r}>"
        )


class ProcessParameter(Base):
    """A single measured process parameter value for a run."""

    __tablename__ = "process_parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    param_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nominal: Mapped[float | None] = mapped_column(Float, nullable=True)
    lsl: Mapped[float | None] = mapped_column(Float, nullable=True)   # lower spec limit
    usl: Mapped[float | None] = mapped_column(Float, nullable=True)   # upper spec limit

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="process_parameters")

    def __repr__(self) -> str:
        return f"<ProcessParameter id={self.id} run_id={self.run_id} name={self.param_name!r} value={self.value}>"


class TraceData(Base):
    """Time-series channel data captured during a run (lightweight: one channel)."""

    __tablename__ = "trace_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    run: Mapped["Run"] = relationship("Run", back_populates="trace_data")

    def __repr__(self) -> str:
        return f"<TraceData id={self.id} run_id={self.run_id} channel={self.channel!r}>"
