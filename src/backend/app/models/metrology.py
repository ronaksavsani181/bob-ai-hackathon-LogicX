"""
Metrology model.

wafer → metrology (multiple measurement sites per wafer, multiple types)
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Metrology(Base):
    """A single metrology measurement (one site, one measurement type) on a wafer."""

    __tablename__ = "metrology"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wafer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    measurement_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    site_index: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    measured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    wafer: Mapped["Wafer"] = relationship("Wafer", back_populates="metrology_records")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<Metrology id={self.id} wafer_id={self.wafer_id} "
            f"type={self.measurement_type!r} site={self.site_index} value={self.value}>"
        )
