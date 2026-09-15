"""
YieldResult model.

wafer → yield_results (final electrical test / bin results per wafer)
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class YieldResult(Base):
    """
    Electrical test result for a wafer.

    die_yield is a fraction [0.0, 1.0].
    bin1_count = passing die.
    bin_fail_count = total failing die across all fail bins.
    """

    __tablename__ = "yield_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wafer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wafers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    die_yield: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    bin1_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bin_fail_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    wafer: Mapped["Wafer"] = relationship("Wafer", back_populates="yield_results")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<YieldResult id={self.id} wafer_id={self.wafer_id} "
            f"die_yield={self.die_yield:.3f}>"
        )
