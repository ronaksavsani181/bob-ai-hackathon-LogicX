"""
Excursion model.

lot → excursions (a detected yield or process excursion on a lot or wafer)
The evidence JSONB field holds raw supporting data at detection time.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._types import JsonColumn

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Excursion(Base):
    """
    A detected yield or process excursion.

    lot_id is nullable so stand-alone wafer-level excursions can be recorded.
    severity: 'mild' | 'moderate' | 'severe'
    evidence: JSONB blob capturing the raw signals at detection time.
    """

    __tablename__ = "excursions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Both FKs nullable — excursion may be at lot or wafer level
    lot_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("lots.id", ondelete="SET NULL"), nullable=True, index=True
    )
    wafer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("wafers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    excursion_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, default=_utcnow
    )
    evidence: Mapped[dict] = mapped_column(JsonColumn, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    lot: Mapped["Lot | None"] = relationship("Lot", back_populates="excursions")  # type: ignore[name-defined]
    root_cause_rankings: Mapped[list["RootCauseRanking"]] = relationship(  # type: ignore[name-defined]
        "RootCauseRanking", back_populates="excursion", cascade="all, delete-orphan"
    )
    action_recommendations: Mapped[list["ActionRecommendation"]] = relationship(  # type: ignore[name-defined]
        "ActionRecommendation", back_populates="excursion", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Excursion id={self.id} lot_id={self.lot_id} "
            f"type={self.excursion_type!r} severity={self.severity!r}>"
        )
