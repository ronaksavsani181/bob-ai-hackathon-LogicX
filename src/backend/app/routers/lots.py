"""
app/routers/lots.py — Lot list, lot detail, yield excursion, parameter anomaly endpoints.

GET /api/lots                   — paginated lot list with yield + risk summary
GET /api/lots/{lot_id_str}      — full lot detail with yield excursion + param anomalies
GET /api/lots/{lot_id_str}/patterns  — wafer defect spatial patterns
GET /api/lots/{lot_id_str}/root-cause — evidence-based root cause ranking
GET /api/lots/{lot_id_str}/evidence  — evidence items for a lot
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    LotDetailResponse,
    LotListResponse,
    LotSummary,
    PaginationMeta,
    ParameterAnomalySummary,
    RootCauseCandidateSchema,
    RootCauseResponse,
    WaferDefectPattern,
    WaferPatternResponse,
    YieldExcursionSummary,
    EvidenceResponse,
    EvidenceSummaryItem,
)
from app.services import ingestion
from app.services.anomaly import detect_yield_excursion, detect_parameter_anomalies
from app.services.defect_pattern import classify_lot_defect_patterns
from app.services.recurrence import analyze_chamber_recurrence
from app.services.root_cause import rank_root_causes
from app.services.temporal import analyze_maintenance_proximity
from app.services.similar_lot import find_similar_lots

router = APIRouter(prefix="/api/lots", tags=["lots"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# GET /api/lots
# ---------------------------------------------------------------------------
@router.get("", response_model=LotListResponse)
def list_lots(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    excursion_only: bool = Query(default=False),
    status: str | None = Query(default=None),
):
    """
    Return a paginated list of lots with mean yield and excursion flag.

    Query parameters:
        page         : 1-based page number
        page_size    : lots per page (max 200)
        excursion_only : if true, only return lots with detected excursions
        status       : filter by lot status string
    """
    lots_df = ingestion.load_lots(db)
    yields_df = ingestion.load_yield_results(db)
    wafers_df = ingestion.load_wafers(db)

    # Aggregate yield to lot level
    yield_with_lot = yields_df.merge(
        wafers_df[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )
    lot_yield = (
        yield_with_lot.groupby("lot_id")["die_yield"]
        .mean()
        .reset_index()
        .rename(columns={"die_yield": "mean_yield"})
    )
    merged = lots_df.merge(lot_yield, on="lot_id", how="left").sort_values(
        "actual_start_at", ascending=False
    )

    if status:
        merged = merged[merged["status"] == status]

    # Compute excursion flags (simplified bulk — full MAD not run on every list call)
    # Use a threshold-based quick check for the list view
    grand_median = float(lot_yield["mean_yield"].median()) if len(lot_yield) else 0.93
    merged["is_excursion"] = merged["mean_yield"] < (grand_median - 0.08)
    merged["excursion_severity"] = "none"
    merged.loc[merged["is_excursion"], "excursion_severity"] = "moderate"
    merged.loc[merged["mean_yield"] < (grand_median - 0.15), "excursion_severity"] = "severe"

    if excursion_only:
        merged = merged[merged["is_excursion"]]

    total = len(merged)
    offset = (page - 1) * page_size
    page_df = merged.iloc[offset: offset + page_size]

    summaries = []
    for _, row in page_df.iterrows():
        summaries.append(LotSummary(
            lot_id=int(row["lot_id"]),
            lot_id_str=str(row["lot_id_str"]),
            product=str(row.get("product", "")),
            technology_node=str(row.get("technology_node", "")),
            priority=str(row.get("priority", "normal")),
            status=str(row.get("status", "completed")),
            actual_start_at=row.get("actual_start_at"),
            mean_yield=round(float(row["mean_yield"]), 4) if pd.notna(row.get("mean_yield")) else None,
            excursion=bool(row["is_excursion"]),
            excursion_severity=str(row["excursion_severity"]),
            risk_score=None,
            risk_class=None,
        ))

    return LotListResponse(
        lots=summaries,
        meta=PaginationMeta(
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, (total + page_size - 1) // page_size),
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/lots/{lot_id_str}
# ---------------------------------------------------------------------------
@router.get("/{lot_id_str}", response_model=LotDetailResponse)
def get_lot_detail(
    lot_id_str: str,
    db: Annotated[Session, Depends(get_db)],
):
    """Return full detail for a single lot including yield excursion and parameter anomalies."""
    lots_df = ingestion.load_lots(db)
    lot_row = lots_df[lots_df["lot_id_str"] == lot_id_str]
    if lot_row.empty:
        raise HTTPException(status_code=404, detail=f"Lot '{lot_id_str}' not found")

    row = lot_row.iloc[0]
    lot_id = int(row["lot_id"])

    wafers_df = ingestion.load_wafers(db, lot_id=lot_id)
    yields_df = ingestion.load_yield_results(db, lot_id=lot_id)
    runs_df   = ingestion.load_runs(db, lot_id=lot_id)

    mean_yield = float(yields_df["die_yield"].mean()) if len(yields_df) else None

    # --- Yield excursion detection ---
    all_yields = ingestion.load_yield_results(db)
    all_wafers = ingestion.load_wafers(db)
    yield_with_lot = all_yields.merge(
        all_wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )
    all_lots = ingestion.load_lots(db)
    lot_yield_agg = (
        yield_with_lot.groupby("lot_id")["die_yield"]
        .mean()
        .reset_index()
        .rename(columns={"die_yield": "die_yield"})
    )
    hist_merged = all_lots.merge(lot_yield_agg, on="lot_id", how="left").sort_values(
        "actual_start_at"
    )
    start_at = row.get("actual_start_at")
    hist_prior = hist_merged[hist_merged["actual_start_at"] < start_at][
        ["lot_id_str", "actual_start_at", "die_yield"]
    ].copy() if start_at is not None else pd.DataFrame()

    ye_result = None
    if mean_yield is not None and start_at is not None:
        ye = detect_yield_excursion(lot_id_str, mean_yield, start_at, hist_prior)
        ye_result = YieldExcursionSummary(
            observed_yield=ye.observed_yield,
            baseline_yield=ye.baseline_yield if ye.baseline_yield == ye.baseline_yield else 0.0,
            deviation_sigma=ye.deviation_sigma if ye.deviation_sigma == ye.deviation_sigma else 0.0,
            severity=ye.severity,
            is_excursion=ye.is_excursion,
            method=ye.method,
            evidence_id=ye.evidence_id,
        )

    # --- Parameter anomaly detection ---
    run_ids = runs_df["run_id"].tolist() if len(runs_df) else []
    pa_results: list[ParameterAnomalySummary] = []
    if run_ids:
        target_params = ingestion.load_process_parameters(db, run_ids=run_ids)
        all_params = ingestion.load_process_parameters(db)
        all_runs = ingestion.load_runs(db)
        anomalies = detect_parameter_anomalies(
            lot_id_str, run_ids, target_params, all_runs, all_params
        )
        for a in anomalies[:20]:  # cap at 20 for response size
            pa_results.append(ParameterAnomalySummary(
                param_name=a.param_name,
                z_score=a.z_score,
                direction=a.direction,
                severity=a.severity,
                baseline_mean=a.baseline_mean,
                baseline_std=a.baseline_std,
                observed_value=a.observed_value,
                evidence_id=a.evidence_id,
            ))

    actual_end = row.get("actual_end_at") or row.get("actual_start_at")

    return LotDetailResponse(
        lot_id=lot_id,
        lot_id_str=lot_id_str,
        product=str(row.get("product", "")),
        technology_node=str(row.get("technology_node", "")),
        priority=str(row.get("priority", "normal")),
        status=str(row.get("status", "completed")),
        actual_start_at=start_at,
        actual_end_at=actual_end,
        queue_time_h=float(row["queue_time_h"]) if pd.notna(row.get("queue_time_h")) else None,
        mean_yield=round(mean_yield, 4) if mean_yield is not None else None,
        wafer_count=len(wafers_df),
        yield_excursion=ye_result,
        parameter_anomalies=pa_results,
        generated_at=_utcnow(),
    )


# ---------------------------------------------------------------------------
# GET /api/lots/{lot_id_str}/patterns
# ---------------------------------------------------------------------------
@router.get("/{lot_id_str}/patterns", response_model=WaferPatternResponse)
def get_wafer_patterns(
    lot_id_str: str,
    db: Annotated[Session, Depends(get_db)],
    sample_wafers: int = Query(default=5, ge=1, le=25),
):
    """Return defect spatial pattern classifications for up to sample_wafers wafers."""
    lots_df = ingestion.load_lots(db)
    lot_row = lots_df[lots_df["lot_id_str"] == lot_id_str]
    if lot_row.empty:
        raise HTTPException(status_code=404, detail=f"Lot '{lot_id_str}' not found")

    lot_id = int(lot_row.iloc[0]["lot_id"])
    wafers_df = ingestion.load_wafers(db, lot_id=lot_id)
    wafer_ids = wafers_df["wafer_id"].tolist()
    defects_df = ingestion.load_defects(db, wafer_ids=wafer_ids)

    patterns = classify_lot_defect_patterns(wafer_ids, defects_df, sample_wafers=sample_wafers)

    return WaferPatternResponse(
        lot_id_str=lot_id_str,
        patterns=[
            WaferDefectPattern(
                wafer_id=p.wafer_id,
                pattern_type=p.pattern_type,
                pattern_score=p.pattern_score,
                defect_count=p.defect_count,
                spatial_statistics=p.spatial_statistics,
                evidence_id=p.evidence_id,
            )
            for p in patterns
        ],
        generated_at=_utcnow(),
    )


# ---------------------------------------------------------------------------
# GET /api/lots/{lot_id_str}/root-cause
# ---------------------------------------------------------------------------
@router.get("/{lot_id_str}/root-cause", response_model=RootCauseResponse)
def get_root_cause(
    lot_id_str: str,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Run the evidence fusion pipeline and return ranked root-cause candidates.

    ROOT CAUSE RULE: This endpoint never invokes an LLM.  All ranking is
    produced deterministically by root_cause.rank_root_causes().

    DISCLAIMER: Results are the highest-ranked candidates based on available
    evidence.  They are NOT confirmed causes.  Engineering review is required.
    """
    lots_df = ingestion.load_lots(db)
    lot_row = lots_df[lots_df["lot_id_str"] == lot_id_str]
    if lot_row.empty:
        raise HTTPException(status_code=404, detail=f"Lot '{lot_id_str}' not found")

    row = lot_row.iloc[0]
    lot_id = int(row["lot_id"])
    start_at = row.get("actual_start_at")
    queue_time_h = float(row.get("queue_time_h") or 0.0)

    # Gather evidence inputs
    wafers_df   = ingestion.load_wafers(db, lot_id=lot_id)
    yields_df   = ingestion.load_yield_results(db, lot_id=lot_id)
    runs_df     = ingestion.load_runs(db, lot_id=lot_id)
    all_yields  = ingestion.load_yield_results(db)
    all_wafers  = ingestion.load_wafers(db)
    all_lots    = ingestion.load_lots(db)

    wafer_ids = wafers_df["wafer_id"].tolist()
    defects_df = ingestion.load_defects(db, wafer_ids=wafer_ids)
    defect_patterns = classify_lot_defect_patterns(wafer_ids, defects_df, sample_wafers=5)

    # Yield excursion
    yield_with_lot = all_yields.merge(
        all_wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )
    lot_yield_agg = yield_with_lot.groupby("lot_id")["die_yield"].mean().reset_index()
    hist_merged = all_lots.merge(lot_yield_agg, on="lot_id", how="left").sort_values("actual_start_at")
    mean_yield = float(yields_df["die_yield"].mean()) if len(yields_df) else None

    ye_result = None
    if mean_yield is not None and start_at is not None:
        hist_prior = hist_merged[hist_merged["actual_start_at"] < start_at][
            ["lot_id_str", "actual_start_at", "die_yield"]
        ].copy()
        ye_result = detect_yield_excursion(lot_id_str, mean_yield, start_at, hist_prior)

    # Chamber recurrence
    chambers_df = ingestion.load_chambers(db).rename(
        columns={"chamber_name": "chamber_name", "tool_name": "tool_name"}
    )
    all_runs = ingestion.load_runs(db)
    yield_for_recurrence = yield_with_lot.copy()
    recurrence_results = analyze_chamber_recurrence(
        all_lots, yield_for_recurrence, all_runs, chambers_df
    )

    # Maintenance proximity — run for each chamber used by this lot
    maint_df = ingestion.load_maintenance_events(db)
    lot_chamber_ids = runs_df["chamber_id"].unique().tolist() if len(runs_df) else []
    maint_results = []
    maint_renamed = maint_df.rename(columns={"performed_at": "event_at"})
    all_lots_for_maint = all_lots.copy()
    if "actual_end_at" not in all_lots_for_maint.columns:
        all_lots_for_maint["actual_end_at"] = (
            all_lots_for_maint["actual_start_at"] + pd.Timedelta(hours=8)
        )
    for cid in lot_chamber_ids[:3]:
        cham_info = chambers_df[chambers_df["chamber_id"] == cid]
        cname = str(cham_info["chamber_name"].iloc[0]) if len(cham_info) else f"C-{cid}"
        cham_maint = maint_renamed[maint_renamed["chamber_id"] == cid]
        if not cham_maint.empty:
            mp = analyze_maintenance_proximity(
                chamber_id=cid, chamber_name=cname,
                maintenance_events_df=cham_maint,
                lots_df=all_lots_for_maint,
                yield_df=yield_for_recurrence,
                runs_df=all_runs,
            )
            maint_results.extend(mp)

    fusion = rank_root_causes(
        lot_id=lot_id_str,
        yield_excursion=ye_result,
        param_anomalies=[],
        chamber_recurrences=recurrence_results,
        maintenance_proximity=maint_results,
        similar_lots=[],
        defect_patterns=defect_patterns,
        queue_time_h=queue_time_h,
        affected_wafer_count=len(wafer_ids),
    )

    return RootCauseResponse(
        lot_id_str=lot_id_str,
        candidates=[
            RootCauseCandidateSchema(
                rank=c.rank,
                cause_id=c.cause_id,
                cause_type=c.cause_type,
                cause_description=c.cause_description,
                score=c.score,
                confidence=c.confidence,
                evidence_ids=c.evidence_ids,
                supporting_signals=c.supporting_signals,
                contradicting_signals=c.contradicting_signals,
                affected_lot_count=c.affected_lot_count,
                affected_wafer_count=c.affected_wafer_count,
                temporal_precedence=c.temporal_precedence,
                model_version=c.model_version,
                generated_at=c.generated_at,
            )
            for c in fusion.candidates
        ],
        insufficient_evidence=fusion.insufficient_evidence,
        evidence_summary=fusion.evidence_summary,
        model_version=fusion.model_version,
        generated_at=fusion.generated_at,
    )


# ---------------------------------------------------------------------------
# GET /api/lots/{lot_id_str}/evidence
# ---------------------------------------------------------------------------
@router.get("/{lot_id_str}/evidence", response_model=EvidenceResponse)
def get_lot_evidence(
    lot_id_str: str,
    db: Annotated[Session, Depends(get_db)],
):
    """Return all evidence items collected for a lot."""
    lots_df = ingestion.load_lots(db)
    lot_row = lots_df[lots_df["lot_id_str"] == lot_id_str]
    if lot_row.empty:
        raise HTTPException(status_code=404, detail=f"Lot '{lot_id_str}' not found")

    # Lightweight evidence list: yield + param anomalies
    row = lot_row.iloc[0]
    lot_id = int(row["lot_id"])
    runs_df = ingestion.load_runs(db, lot_id=lot_id)
    run_ids = runs_df["run_id"].tolist()

    items: list[EvidenceSummaryItem] = []
    if run_ids:
        target_params = ingestion.load_process_parameters(db, run_ids=run_ids)
        all_params    = ingestion.load_process_parameters(db)
        all_runs      = ingestion.load_runs(db)
        anomalies = detect_parameter_anomalies(
            lot_id_str, run_ids, target_params, all_runs, all_params
        )
        for a in anomalies:
            items.append(EvidenceSummaryItem(
                evidence_id=a.evidence_id,
                source_type="process_parameter",
                feature=a.param_name,
                observed_value=a.observed_value,
                baseline_value=a.baseline_mean,
                deviation_score=a.z_score,
                direction=a.direction,
                algorithm_version=a.algorithm_version,
                generated_at=a.generated_at,
            ))

    return EvidenceResponse(
        lot_id_str=lot_id_str,
        items=items,
        total=len(items),
    )
