"""
Lot model.

A Lot is the unit of fab work scheduling.  It contains wafers and carries
genealogy timestamps for pre-run risk analysis.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lot(Base):
    """
    Fab lot — the primary scheduling and tracking unit.

    planned_start_at: set at lot creation, used as the leakage boundary for
                      pre-run risk scoring.  NO future data (yield, defects,
                      metrology) may be used as a feature for any lot whose
                      planned_start_at has not yet elapsed.
    actual_start_at:  set when the lot physically starts processing.
    """

    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Business key — human-readable lot identifier (e.g. "L0042")
    lot_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    product: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    technology_node: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled", index=True)

    # Timestamps — these are the genealogy anchor points
    planned_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    actual_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    wafers: Mapped[list["Wafer"]] = relationship(  # type: ignore[name-defined]
        "Wafer", back_populates="lot", cascade="all, delete-orphan"
    )
    excursions: Mapped[list["Excursion"]] = relationship(  # type: ignore[name-defined]
        "Excursion", back_populates="lot"
    )
    pre_run_assessments: Mapped[list["PreRunAssessment"]] = relationship(  # type: ignore[name-defined]
        "PreRunAssessment", back_populates="lot", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Lot id={self.id} lot_id={self.lot_id!r} product={self.product!r} status={self.status!r}>"
