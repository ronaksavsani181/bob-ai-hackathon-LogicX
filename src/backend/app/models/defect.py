"""
Defect model.

wafer → defects (spatial defect map — x/y coordinates in mm on a 300mm wafer)
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Defect(Base):
    """
    A single defect on a wafer.

    Coordinates are in mm from wafer centre.
    Wafer radius = 150mm, so x/y range is [-150, +150].
    Geometry is stored as plain FLOAT columns (no PostGIS required).
    """

    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wafer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Spatial position in mm from wafer centre
    x_coord: Mapped[float] = mapped_column(Float, nullable=False)
    y_coord: Mapped[float] = mapped_column(Float, nullable=False)
    size_um: Mapped[float | None] = mapped_column(Float, nullable=True)
    defect_class: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    inspection_tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    wafer: Mapped["Wafer"] = relationship("Wafer", back_populates="defects")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<Defect id={self.id} wafer_id={self.wafer_id} "
            f"x={self.x_coord:.1f} y={self.y_coord:.1f} class={self.defect_class!r}>"
        )
