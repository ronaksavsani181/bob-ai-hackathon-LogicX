"""
app/services/evidence.py — Shared evidence and result types for all analytics services.

Every analytical result carries:
  - a stable evidence_id for traceability
  - source entity identification
  - the calculation performed
  - the algorithm version that produced it
  - a generated_at timestamp

IMPORTANT:
These types are data containers only.
No FastAPI, no DB session, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import hashlib
import json


# ---------------------------------------------------------------------------
# Algorithm versions — bump when algorithm logic changes
# ---------------------------------------------------------------------------
VERSIONS = {
    "yield_excursion": "yield_excursion_v1",
    "process_anomaly": "process_anomaly_v1",
    "similar_lot":     "similar_lot_v1",
    "chamber_recurrence": "chamber_recurrence_v1",
    "temporal_precedence": "temporal_precedence_v1",
    "maintenance_proximity": "maintenance_proximity_v1",
    "defect_pattern":  "defect_pattern_v1",
    "root_cause_fusion": "root_cause_fusion_v1",
    "pre_run_risk":    "pre_run_risk_v1",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_evidence_id(source_type: str, source_id: str | int, feature: str = "") -> str:
    """
    Create a stable, deterministic evidence ID from its components.

    Format: EVD-<8-char-hash>
    The hash is derived from source_type + source_id + feature so the same
    analytical result always produces the same evidence ID.
    """
    key = f"{source_type}:{source_id}:{feature}"
    h = hashlib.sha256(key.encode()).hexdigest()[:8].upper()
    return f"EVD-{h}"


# ---------------------------------------------------------------------------
# Evidence record — atomic unit of analytical support
# ---------------------------------------------------------------------------
@dataclass
class EvidenceRecord:
    """
    An atomic piece of analytical evidence supporting or contradicting a cause.

    Fields
    ------
    evidence_id     : stable ID for UI/audit linkage
    source_type     : 'yield_result' | 'process_parameter' | 'metrology' |
                      'defect' | 'maintenance_event' | 'run' | 'lot'
    source_id       : PK of the source record in the database
    feature         : name of the measured feature (e.g. 'etch_rate')
    observed_value  : the measured/computed value
    baseline_value  : expected/historical baseline
    deviation       : signed deviation (observed − baseline)
    deviation_score : normalised score (e.g. z-score)
    direction       : 'high' | 'low' | 'none'
    timestamp       : when the source event occurred
    calculation     : human-readable formula description
    algorithm_version : version string from VERSIONS
    generated_at    : when this evidence was computed
    """
    evidence_id: str
    source_type: str
    source_id: int | str
    feature: str
    observed_value: float
    baseline_value: float
    deviation: float
    deviation_score: float
    direction: str
    timestamp: datetime
    calculation: str
    algorithm_version: str
    generated_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "feature": self.feature,
            "observed_value": self.observed_value,
            "baseline_value": self.baseline_value,
            "deviation": self.deviation,
            "deviation_score": self.deviation_score,
            "direction": self.direction,
            "timestamp": self.timestamp.isoformat(),
            "calculation": self.calculation,
            "algorithm_version": self.algorithm_version,
            "generated_at": self.generated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Yield excursion result
# ---------------------------------------------------------------------------
@dataclass
class YieldExcursionResult:
    lot_id: str
    observed_yield: float
    baseline_yield: float
    deviation: float            # observed − baseline
    deviation_sigma: float      # how many σ below baseline
    severity: str               # 'none' | 'mild' | 'moderate' | 'severe'
    is_excursion: bool
    method: str
    n_lots_used: int
    evidence_id: str
    algorithm_version: str
    generated_at: datetime = field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Process parameter anomaly result
# ---------------------------------------------------------------------------
@dataclass
class ParameterAnomalyResult:
    lot_id: str
    run_id: int
    chamber_id: int
    tool_id: int
    param_name: str
    observed_value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    direction: str              # 'high' | 'low'
    severity: str               # 'mild' | 'moderate' | 'severe'
    is_anomaly: bool
    evidence_id: str
    algorithm_version: str
    generated_at: datetime = field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Similar lot result
# ---------------------------------------------------------------------------
@dataclass
class SimilarLotResult:
    target_lot_id: str
    similar_lot_id: str
    similarity_score: float     # cosine similarity [0, 1]
    common_chamber: str | None
    common_tool: str | None
    common_recipe: str | None
    historical_yield: float
    distance_method: str
    evidence_id: str
    algorithm_version: str
    generated_at: datetime = field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Chamber recurrence result
# ---------------------------------------------------------------------------
@dataclass
class ChamberRecurrenceResult:
    chamber_id: int
    chamber_name: str
    tool_name: str
    affected_lot_count: int
    reference_lot_count: int
    chamber_mean_yield: float
    fleet_mean_yield: float
    yield_gap: float
    recurrence_score: float     # [0, 1]  higher = stronger recurrence signal
    is_recurrent: bool
    evidence_ids: list[str]
    algorithm_version: str
    generated_at: datetime = field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Temporal precedence result
# ---------------------------------------------------------------------------
@dataclass
class TemporalPrecedenceResult:
    candidate_factor: str
    factor_timestamp: datetime
    outcome_timestamp: datetime
    time_delta_hours: float
    precedence_valid: bool      # True only if factor occurred BEFORE outcome
    evidence_id: str
    algorithm_version: str
    generated_at: datetime = field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Maintenance proximity result
# ---------------------------------------------------------------------------
@dataclass
class MaintenanceProximityResult:
    chamber_id: int
    chamber_name: str
    maintenance_event_id: int
    event_type: str
    maintenance_at: datetime
    lot_start_at: datetime
    elapsed_hours: float
    post_maint_yield: float
    pre_maint_yield: float
    yield_shift: float
    evidence_id: str
    algorithm_version: str
    generated_at: datetime = field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Defect pattern result
# ---------------------------------------------------------------------------
@dataclass
class DefectPatternResult:
    wafer_id: int
    pattern_type: str           # 'center_heavy'|'edge_ring'|'localized_hotspot'|
                                # 'radial'|'scratch_line'|'uniform'|'insufficient_data'
    pattern_score: float        # [0, 1] confidence in the classified pattern
    defect_count: int
    spatial_statistics: dict[str, float]   # center_ratio, edge_ratio, etc.
    evidence_id: str
    algorithm_version: str
    generated_at: datetime = field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# Root cause candidate
# ---------------------------------------------------------------------------
@dataclass
class RootCauseCandidate:
    rank: int
    cause_id: str               # stable slug: 'etch_chamber_drift' etc.
    cause_type: str             # 'chamber' | 'tool' | 'process_parameter' | ...
    cause_description: str
    score: float                # normalised [0, 1]
    confidence: float           # separation ratio vs next-ranked candidate
    evidence_ids: list[str]
    supporting_signals: dict[str, float]
    contradicting_signals: dict[str, float]
    affected_lot_count: int
    affected_wafer_count: int
    temporal_precedence: bool
    model_version: str
    generated_at: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "cause_id": self.cause_id,
            "cause_type": self.cause_type,
            "cause_description": self.cause_description,
            "score": round(self.score, 4),
            "confidence": round(self.confidence, 4),
            "evidence_ids": self.evidence_ids,
            "supporting_signals": {k: round(v, 4) for k, v in self.supporting_signals.items()},
            "contradicting_signals": {k: round(v, 4) for k, v in self.contradicting_signals.items()},
            "affected_lot_count": self.affected_lot_count,
            "affected_wafer_count": self.affected_wafer_count,
            "temporal_precedence": self.temporal_precedence,
            "model_version": self.model_version,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class RootCauseFusionResult:
    lot_id: str
    candidates: list[RootCauseCandidate]   # max 3, may be empty
    insufficient_evidence: bool
    evidence_summary: dict[str, Any]
    model_version: str
    generated_at: datetime = field(default_factory=_utcnow)
