"""
MaintenanceEvent model.

chamber → maintenance_events (PM logs, unscheduled repairs, qualifications)
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MaintenanceEvent(Base):
    """
    A maintenance event on a chamber.

    event_type examples: 'scheduled_pm', 'unscheduled_pm', 'qualification', 'repair'
    performed_at is the timestamp used for temporal precedence checks in root-cause ranking.
    """

    __tablename__ = "maintenance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chamber_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chambers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    chamber: Mapped["Chamber"] = relationship("Chamber", back_populates="maintenance_events")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return (
            f"<MaintenanceEvent id={self.id} chamber_id={self.chamber_id} "
            f"type={self.event_type!r} at={self.performed_at}>"
        )
