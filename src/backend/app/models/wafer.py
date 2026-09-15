"""
Wafer model.

lot → wafer (one lot has many wafers, typically 25)
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Wafer(Base):
    """Individual wafer within a lot."""

    __tablename__ = "wafers"
    __table_args__ = (
        UniqueConstraint("lot_id", "wafer_slot", name="uq_wafer_lot_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wafer_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    die_count_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    lot: Mapped["Lot"] = relationship("Lot", back_populates="wafers")  # type: ignore[name-defined]
    runs: Mapped[list["Run"]] = relationship(  # type: ignore[name-defined]
        "Run", back_populates="wafer", cascade="all, delete-orphan"
    )
    metrology_records: Mapped[list["Metrology"]] = relationship(  # type: ignore[name-defined]
        "Metrology", back_populates="wafer", cascade="all, delete-orphan"
    )
    defects: Mapped[list["Defect"]] = relationship(  # type: ignore[name-defined]
        "Defect", back_populates="wafer", cascade="all, delete-orphan"
    )
    yield_results: Mapped[list["YieldResult"]] = relationship(  # type: ignore[name-defined]
        "YieldResult", back_populates="wafer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Wafer id={self.id} lot_id={self.lot_id} slot={self.wafer_slot}>"
