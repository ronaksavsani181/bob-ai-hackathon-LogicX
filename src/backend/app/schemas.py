"""
app/schemas.py — Pydantic response schemas for all API endpoints.

These are the typed API contracts between the FastAPI backend and
the React frontend.  All schemas use snake_case field names.

IMPORTANT: These schemas are pure data containers.  No analytics logic here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    version: str
    generated_at: datetime


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Monitor screen — lot list + fleet yield summary
# ---------------------------------------------------------------------------

class LotSummary(BaseModel):
    lot_id: int
    lot_id_str: str
    product: str
    technology_node: str
    priority: str
    status: str
    actual_start_at: datetime | None
    mean_yield: float | None
    excursion: bool
    excursion_severity: str   # 'none'|'mild'|'moderate'|'severe'
    risk_score: float | None
    risk_class: str | None    # 'low'|'medium'|'high'

class LotListResponse(BaseModel):
    lots: list[LotSummary]
    meta: PaginationMeta

class FleetYieldSummary(BaseModel):
    fleet_mean_yield: float
    fleet_std_yield: float
    excursion_count_7d: int
    excursion_count_30d: int
    high_risk_lots_pending: int
    generated_at: datetime


# ---------------------------------------------------------------------------
# Investigate screen — lot detail
# ---------------------------------------------------------------------------

class ParameterAnomalySummary(BaseModel):
    param_name: str
    z_score: float
    direction: str
    severity: str
    baseline_mean: float
    baseline_std: float
    observed_value: float
    evidence_id: str

class YieldExcursionSummary(BaseModel):
    observed_yield: float
    baseline_yield: float
    deviation_sigma: float
    severity: str
    is_excursion: bool
    method: str
    evidence_id: str

class LotDetailResponse(BaseModel):
    lot_id: int
    lot_id_str: str
    product: str
    technology_node: str
    priority: str
    status: str
    actual_start_at: datetime | None
    actual_end_at: datetime | None
    queue_time_h: float | None
    mean_yield: float | None
    wafer_count: int
    yield_excursion: YieldExcursionSummary | None
    parameter_anomalies: list[ParameterAnomalySummary]
    generated_at: datetime


# ---------------------------------------------------------------------------
# Wafer Pattern Lab screen
# ---------------------------------------------------------------------------

class WaferDefectPattern(BaseModel):
    wafer_id: int
    pattern_type: str
    pattern_score: float
    defect_count: int
    spatial_statistics: dict[str, float]
    evidence_id: str

class WaferPatternResponse(BaseModel):
    lot_id_str: str
    patterns: list[WaferDefectPattern]
    generated_at: datetime


# ---------------------------------------------------------------------------
# Evidence screen
# ---------------------------------------------------------------------------

class EvidenceSummaryItem(BaseModel):
    evidence_id: str
    source_type: str
    feature: str
    observed_value: float
    baseline_value: float
    deviation_score: float
    direction: str
    algorithm_version: str
    generated_at: datetime

class EvidenceResponse(BaseModel):
    lot_id_str: str
    items: list[EvidenceSummaryItem]
    total: int


# ---------------------------------------------------------------------------
# Root Cause screen — Evidence
# ---------------------------------------------------------------------------

class RootCauseCandidateSchema(BaseModel):
    rank: int
    cause_id: str
    cause_type: str
    cause_description: str
    score: float
    confidence: float
    evidence_ids: list[str]
    supporting_signals: dict[str, float]
    contradicting_signals: dict[str, float]
    affected_lot_count: int
    affected_wafer_count: int
    temporal_precedence: bool
    model_version: str
    generated_at: datetime

class RootCauseResponse(BaseModel):
    lot_id_str: str
    candidates: list[RootCauseCandidateSchema]
    insufficient_evidence: bool
    evidence_summary: dict[str, Any]
    model_version: str
    generated_at: datetime
    disclaimer: str = (
        "Results represent the highest-ranked candidates based on available evidence. "
        "These are not confirmed causes. Engineering review is required before action."
    )


# ---------------------------------------------------------------------------
# Pre-run risk screen
# ---------------------------------------------------------------------------

class PreRunRiskSummary(BaseModel):
    lot_id_str: str
    planned_start_at: datetime | None
    risk_score: float
    risk_class: str
    top_features: dict[str, float]
    model_version: str
    evidence_id: str
    generated_at: datetime

class PreRunRiskListResponse(BaseModel):
    assessments: list[PreRunRiskSummary]
    model_version: str
    generated_at: datetime


# ---------------------------------------------------------------------------
# Actions / Engineer Review screen
# ---------------------------------------------------------------------------

class ActionRecommendationSchema(BaseModel):
    action_id: int | None
    lot_id_str: str
    recommendation: str
    action_type: str       # 'hold' | 're-inspect' | 'expedite' | 'monitor' | 'disposition'
    priority: str          # 'critical' | 'high' | 'medium' | 'low'
    evidence_ids: list[str]
    status: str            # 'pending' | 'acknowledged' | 'approved' | 'rejected' | 'completed'
    created_at: datetime
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None

class ReviewRequest(BaseModel):
    action_id: int
    decision: str = Field(..., pattern="^(approved|rejected)$")
    reviewer: str
    notes: str | None = None

class ReviewResponse(BaseModel):
    action_id: int
    decision: str
    reviewer: str
    reviewed_at: datetime
    message: str


# ---------------------------------------------------------------------------
# Chamber recurrence
# ---------------------------------------------------------------------------

class ChamberRecurrenceSummary(BaseModel):
    chamber_id: int
    chamber_name: str
    tool_name: str
    affected_lot_count: int
    chamber_mean_yield: float
    fleet_mean_yield: float
    yield_gap: float
    recurrence_score: float
    is_recurrent: bool
    algorithm_version: str

class ChamberRecurrenceResponse(BaseModel):
    chambers: list[ChamberRecurrenceSummary]
    generated_at: datetime


# ---------------------------------------------------------------------------
# Yield trend (monitor screen chart)
# ---------------------------------------------------------------------------

class YieldTrendPoint(BaseModel):
    lot_id_str: str
    actual_start_at: datetime
    mean_yield: float
    is_excursion: bool
    scenario_hint: str | None = None   # broad label for demo colouring — never used in analytics

class YieldTrendResponse(BaseModel):
    points: list[YieldTrendPoint]
    fleet_mean: float
    excursion_threshold: float
    generated_at: datetime


# ---------------------------------------------------------------------------
# Actions list (for GET /api/actions)
# ---------------------------------------------------------------------------

class ActionListResponse(BaseModel):
    actions: list[ActionRecommendationSchema]
    total: int
    generated_at: datetime
