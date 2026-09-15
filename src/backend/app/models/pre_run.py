"""
PreRunAssessment model.

lot → pre_run_assessments (pre-run risk score produced before the lot starts)

PRE-RUN SAFETY RULE:
This table stores risk assessments that were produced using ONLY information
available before lot.actual_start_at.  The features_used JSONB column records
the exact feature names to enable leakage auditing.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._types import JsonColumn

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PreRunAssessment(Base):
    """
    Pre-run risk assessment for an upcoming lot.

    risk_score: model output probability [0,1] of yield < 0.90.
    risk_label: 'low' | 'medium' | 'high'
    feature_vector: JSONB dict of {feature_name: value} used for the prediction.
    features_used: JSONB list of feature names (whitelist audit).
    produced_at: when this assessment was generated.
    """

    __tablename__ = "pre_run_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    risk_label: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    feature_vector: Mapped[dict] = mapped_column(JsonColumn, nullable=False, default=dict)
    features_used: Mapped[list] = mapped_column(JsonColumn, nullable=False, default=list)
    produced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    lot: Mapped["Lot"] = relationship("Lot", back_populates="pre_run_assessments")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<PreRunAssessment id={self.id} lot_id={self.lot_id} "
            f"risk_label={self.risk_label!r} score={self.risk_score:.3f}>"
        )
