"""
app/services/root_cause.py — Evidence-based root-cause ranking (fusion engine).

Algorithm version: root_cause_fusion_v1

ROOT CAUSE RULE (non-negotiable):
  Root-cause ranking is produced by deterministic weighted evidence fusion.
  An LLM may NEVER invent, guess, or directly provide a root-cause verdict.
  This module never imports any language-model library.

Output language convention:
  Results are described as "highest-ranked candidate based on available evidence".
  The words "confirmed cause" and "certain cause" must never appear in output.

Fusion inputs
-------------
Seven weighted evidence signals are fused per candidate:
  1. yield_excursion_score   — severity of yield drop (0-1)
  2. param_anomaly_score     — max z-score normalised (0-1)
  3. chamber_recurrence_score — chamber systematic yield gap (0-1)
  4. temporal_precedence     — boolean (1 if factor preceded outcome, else 0)
  5. maintenance_proximity   — magnitude of post-PM yield shift (0-1)
  6. similar_lot_score       — fraction of top-K similar lots with same pattern (0-1)
  7. defect_pattern_score    — pattern classifier confidence for matching pattern (0-1)

Weights are documented constants — not learned — for full auditability.

Candidate types
---------------
The engine considers these candidate types based on available evidence:
  'etch_chamber_drift'       — param anomaly on etch chamber
  'overlay_excursion'        — metrology anomaly on litho tool
  'particle_contamination'   — high defect density with center-heavy pattern
  'post_maintenance_shift'   — maintenance proximity with temporal precedence
  'chamber_systematic'       — chamber recurrence without other specific signal
  'queue_time_exposure'      — long queue time + yield drop
  'unknown'                  — catch-all when no signal reaches threshold

Insufficient evidence path
--------------------------
If no candidate scores ≥ MIN_CANDIDATE_SCORE the result sets
insufficient_evidence = True and returns an empty candidates list.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.services.evidence import (
    VERSIONS,
    RootCauseCandidate,
    RootCauseFusionResult,
    YieldExcursionResult,
    ParameterAnomalyResult,
    ChamberRecurrenceResult,
    MaintenanceProximityResult,
    SimilarLotResult,
    DefectPatternResult,
    _utcnow,
    make_evidence_id,
)

# ---------------------------------------------------------------------------
# Documented signal weights  (must sum to 1.0)
# ---------------------------------------------------------------------------
SIGNAL_WEIGHTS: dict[str, float] = {
    "yield_excursion":      0.20,
    "param_anomaly":        0.20,
    "chamber_recurrence":   0.18,
    "temporal_precedence":  0.15,
    "maintenance_proximity":0.12,
    "similar_lot":          0.08,
    "defect_pattern":       0.07,
}
assert abs(sum(SIGNAL_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
MIN_CANDIDATE_SCORE: float = 0.15   # minimum score to include in output
MAX_CANDIDATES:      int   = 3
MIN_YIELD_EXCURSION_SIGMA: float = 2.5

# Defect-pattern → candidate type mapping
_DEFECT_PATTERN_TO_CAUSE: dict[str, str] = {
    "center_heavy":       "particle_contamination",
    "edge_ring":          "etch_chamber_drift",
    "localized_hotspot":  "chamber_systematic",
    "radial":             "overlay_excursion",
    "scratch_line":       "post_maintenance_shift",
    "uniform":            "unknown",
    "insufficient_data":  "unknown",
}

# Human-readable descriptions
_CAUSE_DESCRIPTIONS: dict[str, str] = {
    "etch_chamber_drift":    "Etch rate drift on affected chamber",
    "overlay_excursion":     "Overlay metrology excursion on litho tool",
    "particle_contamination":"Particle contamination (center-heavy defect pattern)",
    "post_maintenance_shift":"Post-maintenance process shift on affected chamber",
    "chamber_systematic":    "Chamber-specific systematic yield deficit",
    "queue_time_exposure":   "Queue-time exposure causing process degradation",
    "unknown":               "Unclassified — insufficient discriminating evidence",
}

_CAUSE_TYPES: dict[str, str] = {
    "etch_chamber_drift":    "chamber",
    "overlay_excursion":     "tool",
    "particle_contamination":"chamber",
    "post_maintenance_shift":"maintenance",
    "chamber_systematic":    "chamber",
    "queue_time_exposure":   "process_parameter",
    "unknown":               "unknown",
}


def _norm_z_score(z: float, cap: float = 8.0) -> float:
    """Map a z-score to [0, 1] by dividing by cap and clipping."""
    return float(min(1.0, abs(z) / cap))


def _norm_yield_sigma(sigma: float) -> float:
    """Map yield deviation sigma to [0, 1]; beyond 8σ → 1.0."""
    if np.isnan(sigma):
        return 0.0
    return float(min(1.0, abs(sigma) / 8.0))


def rank_root_causes(
    lot_id: str,
    # Evidence inputs — each may be None / empty if not available
    yield_excursion: YieldExcursionResult | None,
    param_anomalies: list[ParameterAnomalyResult],
    chamber_recurrences: list[ChamberRecurrenceResult],
    maintenance_proximity: list[MaintenanceProximityResult],
    similar_lots: list[SimilarLotResult],
    defect_patterns: list[DefectPatternResult],
    # Contextual metadata
    queue_time_h: float = 0.0,
    affected_wafer_count: int = 0,
) -> RootCauseFusionResult:
    """
    Produce a ranked list of root-cause candidates by fusing seven
    evidence signals.

    All inputs are typed result objects from the preceding analytics services.
    This function is purely deterministic — no randomness, no LLM calls.

    Parameters
    ----------
    lot_id                : business key of the lot under investigation
    yield_excursion       : from anomaly.detect_yield_excursion()
    param_anomalies       : from anomaly.detect_parameter_anomalies()
    chamber_recurrences   : from recurrence.analyze_chamber_recurrence()
    maintenance_proximity : from temporal.analyze_maintenance_proximity()
    similar_lots          : from similar_lot.find_similar_lots()
    defect_patterns       : from defect_pattern.classify_lot_defect_patterns()
    queue_time_h          : queue time in hours for this lot (from lots table)
    affected_wafer_count  : number of wafers in the lot

    Returns
    -------
    RootCauseFusionResult with up to MAX_CANDIDATES ranked candidates.
    Sets insufficient_evidence = True if no candidate clears MIN_CANDIDATE_SCORE.
    """
    # -----------------------------------------------------------------------
    # Signal extraction
    # -----------------------------------------------------------------------

    # S1: Yield excursion score
    ye_score = 0.0
    ye_evidence_ids: list[str] = []
    if yield_excursion and yield_excursion.is_excursion:
        ye_score = _norm_yield_sigma(yield_excursion.deviation_sigma)
        ye_evidence_ids = [yield_excursion.evidence_id]

    # S2: Process parameter anomaly
    pa_scores: dict[str, float] = {}    # cause_type → max score
    pa_evidence_ids: dict[str, list[str]] = {}
    for pa in param_anomalies:
        pname = pa.param_name.lower()
        if "etch" in pname:
            ctype = "etch_chamber_drift"
        elif "overlay" in pname or "align" in pname:
            ctype = "overlay_excursion"
        else:
            ctype = "chamber_systematic"
        s = _norm_z_score(pa.z_score)
        if s > pa_scores.get(ctype, 0.0):
            pa_scores[ctype] = s
            pa_evidence_ids[ctype] = [pa.evidence_id]
        elif ctype in pa_evidence_ids:
            pa_evidence_ids[ctype].append(pa.evidence_id)

    # S3: Chamber recurrence
    recurrence_signals: dict[str, tuple[float, str, list[str]]] = {}
    for cr in chamber_recurrences:
        if cr.is_recurrent:
            ctype = "chamber_systematic"
            if cr.recurrence_score > recurrence_signals.get(ctype, (0, "", []))[0]:
                recurrence_signals[ctype] = (
                    cr.recurrence_score,
                    cr.chamber_name,
                    cr.evidence_ids[:5],
                )

    # S4: Temporal precedence — implied by maintenance proximity ordering
    # (maintenance_proximity already enforces event_at < lot_start_at)
    temporal_precedence_bonus: dict[str, bool] = {}
    for mp in maintenance_proximity:
        if mp.lot_start_at > mp.maintenance_at:
            temporal_precedence_bonus["post_maintenance_shift"] = True

    # S5: Maintenance proximity
    maint_score = 0.0
    maint_evidence_ids: list[str] = []
    if maintenance_proximity:
        shifts = [abs(mp.yield_shift) for mp in maintenance_proximity]
        maint_score = float(min(1.0, max(shifts) / 0.15))
        maint_evidence_ids = [mp.evidence_id for mp in maintenance_proximity]

    # S6: Similar lot evidence — fraction with same dominant defect pattern
    sim_score = 0.0
    sim_evidence_ids: list[str] = []
    if similar_lots:
        sim_evidence_ids = [sl.evidence_id for sl in similar_lots]
        # Score = mean similarity of top-3
        top3 = sorted(similar_lots, key=lambda x: x.similarity_score, reverse=True)[:3]
        sim_score = float(np.mean([sl.similarity_score for sl in top3]))

    # S7: Defect pattern score → cause type
    defect_cause_scores: dict[str, float] = {}
    defect_evidence_ids: dict[str, list[str]] = {}
    if defect_patterns:
        dominant = max(defect_patterns, key=lambda dp: dp.pattern_score)
        if dominant.pattern_type != "insufficient_data":
            ctype = _DEFECT_PATTERN_TO_CAUSE.get(dominant.pattern_type, "unknown")
            defect_cause_scores[ctype] = dominant.pattern_score
            defect_evidence_ids[ctype] = [dp.evidence_id for dp in defect_patterns]

    # Queue time signal → queue_time_exposure candidate
    queue_score = 0.0
    if queue_time_h >= 72.0:
        queue_score = float(min(1.0, (queue_time_h - 72.0) / 80.0))

    # -----------------------------------------------------------------------
    # Candidate assembly — enumerate all possible causes
    # -----------------------------------------------------------------------
    all_causes = list(_CAUSE_DESCRIPTIONS.keys())
    candidates_raw: list[dict] = []

    for cause in all_causes:
        if cause == "unknown":
            continue

        sig: dict[str, float] = {}
        contra: dict[str, float] = {}
        ev_ids: list[str] = []

        # Signal 1: yield excursion (applies to all yield-impacting causes)
        sig["yield_excursion"] = ye_score
        ev_ids.extend(ye_evidence_ids)

        # Signal 2: param anomaly
        sig["param_anomaly"] = pa_scores.get(cause, 0.0)
        ev_ids.extend(pa_evidence_ids.get(cause, []))

        # Signal 3: chamber recurrence
        sig["chamber_recurrence"] = recurrence_signals.get(cause, (0,))[0]
        ev_ids.extend(recurrence_signals.get(cause, (0, "", []))[2])

        # Signal 4: temporal precedence (binary)
        tp = temporal_precedence_bonus.get(cause, False)
        sig["temporal_precedence"] = 1.0 if tp else 0.0

        # Signal 5: maintenance proximity
        if cause == "post_maintenance_shift":
            sig["maintenance_proximity"] = maint_score
            ev_ids.extend(maint_evidence_ids)
        else:
            sig["maintenance_proximity"] = 0.0
            # Having a maint event that points ELSEWHERE is mild contraindication
            if maint_score > 0.3:
                contra["maintenance_proximity_other"] = maint_score * 0.3

        # Signal 6: similar lot
        sig["similar_lot"] = sim_score
        ev_ids.extend(sim_evidence_ids)

        # Signal 7: defect pattern
        sig["defect_pattern"] = defect_cause_scores.get(cause, 0.0)
        ev_ids.extend(defect_evidence_ids.get(cause, []))

        # queue_time signal for queue_time_exposure cause
        if cause == "queue_time_exposure":
            sig["queue_time"] = queue_score
        else:
            sig["queue_time"] = 0.0

        # Weighted fusion score
        weighted = sum(
            SIGNAL_WEIGHTS.get(k, 0.0) * v
            for k, v in sig.items()
        )

        # Contraindication penalty (mild)
        penalty = sum(contra.values()) * 0.1
        final_score = max(0.0, weighted - penalty)

        candidates_raw.append({
            "cause_id": cause,
            "score": final_score,
            "signals": sig,
            "contradicting": contra,
            "evidence_ids": list(dict.fromkeys(ev_ids)),  # deduplicate
            "temporal_precedence": tp,
        })

    # -----------------------------------------------------------------------
    # Sort, filter, rank
    # -----------------------------------------------------------------------
    candidates_raw.sort(key=lambda c: c["score"], reverse=True)
    candidates_raw = [c for c in candidates_raw if c["score"] >= MIN_CANDIDATE_SCORE]
    candidates_raw = candidates_raw[:MAX_CANDIDATES]

    if not candidates_raw:
        return RootCauseFusionResult(
            lot_id=lot_id,
            candidates=[],
            insufficient_evidence=True,
            evidence_summary={
                "yield_excursion_score": ye_score,
                "param_anomaly_count": len(param_anomalies),
                "chamber_recurrence_count": len(chamber_recurrences),
                "maintenance_events": len(maintenance_proximity),
            },
            model_version=VERSIONS["root_cause_fusion"],
        )

    ranked: list[RootCauseCandidate] = []
    for rank_i, c in enumerate(candidates_raw, start=1):
        # Confidence = score separation from next candidate
        if rank_i < len(candidates_raw):
            next_score = candidates_raw[rank_i]["score"]
        else:
            next_score = 0.0
        separation = c["score"] - next_score
        confidence = float(min(1.0, separation / max(c["score"], 1e-9)))

        ranked.append(RootCauseCandidate(
            rank=rank_i,
            cause_id=c["cause_id"],
            cause_type=_CAUSE_TYPES.get(c["cause_id"], "unknown"),
            cause_description=_CAUSE_DESCRIPTIONS.get(c["cause_id"], c["cause_id"]),
            score=round(c["score"], 4),
            confidence=round(confidence, 4),
            evidence_ids=c["evidence_ids"],
            supporting_signals={k: round(v, 4) for k, v in c["signals"].items() if v > 0},
            contradicting_signals={k: round(v, 4) for k, v in c["contradicting"].items()},
            affected_lot_count=1,
            affected_wafer_count=affected_wafer_count,
            temporal_precedence=c["temporal_precedence"],
            model_version=VERSIONS["root_cause_fusion"],
        ))

    return RootCauseFusionResult(
        lot_id=lot_id,
        candidates=ranked,
        insufficient_evidence=False,
        evidence_summary={
            "yield_excursion_score": round(ye_score, 4),
            "param_anomaly_count": len(param_anomalies),
            "chamber_recurrence_count": len(chamber_recurrences),
            "maintenance_events": len(maintenance_proximity),
            "similar_lots_found": len(similar_lots),
            "defect_patterns_classified": len(defect_patterns),
            "queue_time_h": queue_time_h,
        },
        model_version=VERSIONS["root_cause_fusion"],
    )
