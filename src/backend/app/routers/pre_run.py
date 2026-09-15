"""
app/routers/pre_run.py — Pre-run risk assessment endpoints.

GET  /api/pre-run/risk         — risk scores for all pending/upcoming lots
GET  /api/pre-run/risk/{lot_id_str} — risk score for a specific lot

PRE-RUN SAFETY RULE:
  The model is trained and scored using only columns in PRE_RUN_FEATURE_WHITELIST.
  The leakage audit is called at training and inference time.
  Any forbidden column causes a 500 error — not a silent pass-through.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import PreRunRiskListResponse, PreRunRiskSummary
from app.services import ingestion
from app.services.pre_run_risk import (
    PRE_RUN_FEATURE_WHITELIST,
    PreRunRiskResult,
    audit_for_leakage,
    train_risk_model,
    score_pre_run_risk,
    score_pre_run_risk_bulk,
)

router = APIRouter(prefix="/api/pre-run", tags=["pre-run"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_feature_df(lots_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the pre-run feature DataFrame from the lots table.

    Only whitelist columns are included.  No future data is used.
    """
    df = lots_df.copy()
    df["product_encoded"] = df["product"].astype("category").cat.codes.astype(float)
    df["technology_node_encoded"] = df["technology_node"].astype("category").cat.codes.astype(float)
    df["lot_priority"] = df["priority"].map(
        {"low": 0.0, "normal": 1.0, "high": 2.0}
    ).fillna(1.0)
    df["planned_recipe_encoded"]  = 0.0
    df["planned_chamber_encoded"] = 0.0
    df["chamber_yield_30d"]    = 0.94
    df["days_since_last_pm"]   = 30.0
    df["chamber_ooc_rate_30d"] = 0.02
    df["queue_time_planned_h"] = df["queue_time_h"].fillna(24.0)
    # Enforce audit before returning
    audit_for_leakage(df, raise_on_forbidden=True)
    return df


@router.get("/risk", response_model=PreRunRiskListResponse)
def get_pre_run_risk_all(
    db: Session = Depends(get_db),
    top_n: int = 50,
):
    """
    Return pre-run risk assessments for the most recent lots.

    The model is trained on completed lots (chronological split) and scored
    on all lots.  Only whitelist features are used.
    """
    lots_df   = ingestion.load_lots(db)
    yields_df = ingestion.load_yield_results(db)
    wafers_df = ingestion.load_wafers(db)

    if len(lots_df) < 20:
        raise HTTPException(
            status_code=503,
            detail="Insufficient historical data to train pre-run risk model (need ≥20 lots).",
        )

    yield_with_lot = yields_df.merge(
        wafers_df[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )
    feat_df = _build_feature_df(lots_df)

    try:
        clf = train_risk_model(feat_df, yield_with_lot)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model training failed: {e}")

    # Score on the most recent lots
    score_df = feat_df.sort_values("actual_start_at", ascending=False).head(top_n)
    try:
        results = score_pre_run_risk_bulk(clf, score_df)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Map back to schema
    start_map = lots_df.set_index("lot_id_str")["planned_start_at"].to_dict()
    assessments = [
        PreRunRiskSummary(
            lot_id_str=r.lot_id,
            planned_start_at=start_map.get(r.lot_id),
            risk_score=r.risk_score,
            risk_class=r.risk_class,
            top_features=r.top_features,
            model_version=r.model_version,
            evidence_id=r.evidence_id,
            generated_at=r.generated_at,
        )
        for r in results
    ]
    assessments.sort(key=lambda a: a.risk_score, reverse=True)

    from app.services.pre_run_risk import VERSIONS  # local import to avoid circular
    return PreRunRiskListResponse(
        assessments=assessments,
        model_version="pre_run_risk_v1",
        generated_at=_utcnow(),
    )


@router.get("/risk/{lot_id_str}", response_model=PreRunRiskSummary)
def get_pre_run_risk_single(
    lot_id_str: str,
    db: Session = Depends(get_db),
):
    """Return pre-run risk for a single lot."""
    lots_df   = ingestion.load_lots(db)
    lot_row   = lots_df[lots_df["lot_id_str"] == lot_id_str]
    if lot_row.empty:
        raise HTTPException(status_code=404, detail=f"Lot '{lot_id_str}' not found")

    yields_df = ingestion.load_yield_results(db)
    wafers_df = ingestion.load_wafers(db)
    yield_with_lot = yields_df.merge(
        wafers_df[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )
    feat_df = _build_feature_df(lots_df)
    clf = train_risk_model(feat_df, yield_with_lot)

    row = lot_row.iloc[0]
    features = {f: float(feat_df[feat_df["lot_id_str"] == lot_id_str][f].iloc[0])
                for f in PRE_RUN_FEATURE_WHITELIST
                if f in feat_df.columns}
    result = score_pre_run_risk(clf, lot_id_str, features)

    return PreRunRiskSummary(
        lot_id_str=result.lot_id,
        planned_start_at=row.get("planned_start_at"),
        risk_score=result.risk_score,
        risk_class=result.risk_class,
        top_features=result.top_features,
        model_version=result.model_version,
        evidence_id=result.evidence_id,
        generated_at=result.generated_at,
    )
