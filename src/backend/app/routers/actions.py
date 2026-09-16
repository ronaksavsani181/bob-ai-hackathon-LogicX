"""
app/routers/actions.py — Engineer review / corrective-action endpoints.

GET  /api/actions          — list pending action recommendations
POST /api/actions/review   — submit an engineer approval or rejection

HUMAN APPROVAL BOUNDARY:
    All recommendations are advisory.  An engineer MUST explicitly approve or
    reject via this endpoint.  Approved actions are written to the
    action_reviews table with engineer ID, timestamp, and rationale.

    The system NEVER auto-approves.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ActionListResponse,
    ActionRecommendationSchema,
    ReviewRequest,
    ReviewResponse,
)
from app.services import ingestion

router = APIRouter(prefix="/api/actions", tags=["actions"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Static demo recommendations derived from known scenario excursions.
# In production these would be generated from the analytics pipeline and
# persisted in the action_recommendations table.
# ---------------------------------------------------------------------------

_DEMO_ACTIONS: list[dict] = [
    {
        "action_id": 1,
        "lot_id_str": "L0050",
        "recommendation": "Inspect ETCH-A/CHA-1 chamber — persistent etch-rate drift detected "
                          "across 8 consecutive lots. Schedule preventive maintenance.",
        "action_type": "hold",
        "priority": "high",
        "evidence_ids": ["EXC-L0050-yield", "REC-ETCH-A-CHA-1"],
        "status": "pending",
        "created_at": "2024-06-15T08:00:00Z",
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": None,
    },
    {
        "action_id": 2,
        "lot_id_str": "L0120",
        "recommendation": "Re-inspect wafers processed through OVL-B/CHA-3. Overlay error "
                          "exceeds 2σ on 15 of 25 wafers. Rework candidate.",
        "action_type": "re-inspect",
        "priority": "high",
        "evidence_ids": ["EXC-L0120-yield", "PA-overlay_error_nm"],
        "status": "pending",
        "created_at": "2024-06-18T10:30:00Z",
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": None,
    },
    {
        "action_id": 3,
        "lot_id_str": "L0220",
        "recommendation": "Particle count spike on CLEAN-C/CHA-5. Run chamber qualification "
                          "lot before resuming production.",
        "action_type": "hold",
        "priority": "critical",
        "evidence_ids": ["EXC-L0220-yield", "DP-L0220-localized", "PA-particle_count_cm2"],
        "status": "pending",
        "created_at": "2024-06-20T14:00:00Z",
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": None,
    },
    {
        "action_id": 4,
        "lot_id_str": "L0315",
        "recommendation": "Post-PM yield shift on ETCH-A/CHA-2 within expected stabilisation "
                          "window. Monitor next 5 lots before escalation.",
        "action_type": "monitor",
        "priority": "medium",
        "evidence_ids": ["MAINT-ETCH-A-CHA-2", "TEMP-proximity"],
        "status": "pending",
        "created_at": "2024-06-22T09:15:00Z",
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": None,
    },
    {
        "action_id": 5,
        "lot_id_str": "L0410",
        "recommendation": "Chamber recurrence score >0.75 on ETCH-A/CHA-1. Recommend "
                          "engineering review of chamber seasoning recipe.",
        "action_type": "re-inspect",
        "priority": "high",
        "evidence_ids": ["REC-ETCH-A-CHA-1-v2", "EXC-L0410-yield"],
        "status": "acknowledged",
        "created_at": "2024-06-23T11:00:00Z",
        "reviewed_by": "eng_chen",
        "reviewed_at": "2024-06-23T13:45:00Z",
        "review_notes": "Acknowledged. Chamber inspection scheduled for next maintenance window.",
    },
]

# In-memory review store (resets on server restart — prototype only)
_review_store: dict[int, dict] = {a["action_id"]: dict(a) for a in _DEMO_ACTIONS}


@router.get("", response_model=ActionListResponse)
def list_actions(
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
):
    """
    Return pending (and recent) action recommendations.

    HUMAN APPROVAL BOUNDARY: All items require explicit engineer approval via POST /review.
    """
    actions = list(_review_store.values())
    if status:
        actions = [a for a in actions if a["status"] == status]
    actions.sort(key=lambda a: a["created_at"], reverse=True)

    return ActionListResponse(
        actions=[
            ActionRecommendationSchema(
                action_id=a["action_id"],
                lot_id_str=a["lot_id_str"],
                recommendation=a["recommendation"],
                action_type=a["action_type"],
                priority=a["priority"],
                evidence_ids=a["evidence_ids"],
                status=a["status"],
                created_at=datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")),
                reviewed_by=a.get("reviewed_by"),
                reviewed_at=(
                    datetime.fromisoformat(a["reviewed_at"].replace("Z", "+00:00"))
                    if a.get("reviewed_at")
                    else None
                ),
                review_notes=a.get("review_notes"),
            )
            for a in actions
        ],
        total=len(actions),
        generated_at=_utcnow(),
    )


@router.post("/review", response_model=ReviewResponse)
def submit_review(
    body: ReviewRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Submit an engineer approval or rejection for an action recommendation.

    HUMAN APPROVAL BOUNDARY:
    - An engineer MUST supply their reviewer ID and a decision.
    - Auto-approval is explicitly prohibited.
    - Review is recorded with timestamp and optional notes for full audit trail.
    """
    action = _review_store.get(body.action_id)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action {body.action_id} not found")
    if action["status"] not in ("pending", "acknowledged"):
        raise HTTPException(
            status_code=409,
            detail=f"Action {body.action_id} already has status '{action['status']}' — cannot re-review.",
        )

    now = _utcnow()
    action["status"] = body.decision         # 'approved' or 'rejected'
    action["reviewed_by"] = body.reviewer
    action["reviewed_at"] = now.isoformat()
    action["review_notes"] = body.notes

    return ReviewResponse(
        action_id=body.action_id,
        decision=body.decision,
        reviewer=body.reviewer,
        reviewed_at=now,
        message=f"Action {body.action_id} {body.decision} by {body.reviewer} at {now.isoformat()}",
    )
