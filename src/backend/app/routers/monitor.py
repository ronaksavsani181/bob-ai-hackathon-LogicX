"""
app/routers/monitor.py — Fleet-level monitoring endpoints.

GET /api/monitor/fleet-summary   — fleet yield KPIs
GET /api/monitor/excursions      — recent yield excursions
GET /api/monitor/chambers        — chamber recurrence analysis
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ChamberRecurrenceResponse,
    ChamberRecurrenceSummary,
    FleetYieldSummary,
    YieldTrendPoint,
    YieldTrendResponse,
)
from app.services import ingestion
from app.services.recurrence import analyze_chamber_recurrence

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/fleet-summary", response_model=FleetYieldSummary)
def fleet_summary(db: Session = Depends(get_db)):
    """Return fleet-level yield KPIs."""
    yields_df = ingestion.load_yield_results(db)
    wafers_df = ingestion.load_wafers(db)
    lots_df   = ingestion.load_lots(db)

    if yields_df.empty:
        return FleetYieldSummary(
            fleet_mean_yield=0.0,
            fleet_std_yield=0.0,
            excursion_count_7d=0,
            excursion_count_30d=0,
            high_risk_lots_pending=0,
            generated_at=_utcnow(),
        )

    yield_with_lot = yields_df.merge(
        wafers_df[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )
    lot_yield = yield_with_lot.groupby("lot_id")["die_yield"].mean().reset_index()
    fleet_mean = float(lot_yield["die_yield"].mean())
    fleet_std  = float(lot_yield["die_yield"].std())
    threshold  = fleet_mean - 2.5 * fleet_std

    merged = lots_df.merge(lot_yield, on="lot_id", how="left")
    excursion_mask = merged["die_yield"] < threshold
    now = pd.Timestamp.now(tz="UTC")

    ex_7d = int(
        merged[
            excursion_mask
            & (merged["actual_start_at"] >= now - pd.Timedelta(days=7))
        ].shape[0]
    )
    ex_30d = int(
        merged[
            excursion_mask
            & (merged["actual_start_at"] >= now - pd.Timedelta(days=30))
        ].shape[0]
    )

    return FleetYieldSummary(
        fleet_mean_yield=round(fleet_mean, 4),
        fleet_std_yield=round(fleet_std, 4),
        excursion_count_7d=ex_7d,
        excursion_count_30d=ex_30d,
        high_risk_lots_pending=0,   # populated by pre-run router when model is trained
        generated_at=_utcnow(),
    )


@router.get("/yield-trend", response_model=YieldTrendResponse)
def yield_trend(
    db: Session = Depends(get_db),
    last_n: int = 150,
):
    """
    Return the yield trend series for the most recent lots.

    Used by the Monitor screen chart.  Points are sorted chronologically.
    Excursion threshold = fleet_mean - 2.5 * fleet_std.
    """
    yields_df = ingestion.load_yield_results(db)
    wafers_df = ingestion.load_wafers(db)
    lots_df   = ingestion.load_lots(db)

    if yields_df.empty or lots_df.empty:
        return YieldTrendResponse(
            points=[], fleet_mean=0.93, excursion_threshold=0.85, generated_at=_utcnow()
        )

    yield_with_lot = yields_df.merge(
        wafers_df[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )
    lot_yield = yield_with_lot.groupby("lot_id")["die_yield"].mean().reset_index()
    merged = lots_df.merge(lot_yield, on="lot_id", how="left").dropna(subset=["die_yield"])
    merged = merged.sort_values("actual_start_at").tail(last_n)

    fleet_mean = float(lot_yield["die_yield"].mean())
    fleet_std  = float(lot_yield["die_yield"].std())
    threshold  = fleet_mean - 2.5 * fleet_std

    points = []
    for _, row in merged.iterrows():
        if pd.isna(row.get("actual_start_at")):
            continue
        points.append(YieldTrendPoint(
            lot_id_str=str(row["lot_id_str"]),
            actual_start_at=row["actual_start_at"],
            mean_yield=round(float(row["die_yield"]), 4),
            is_excursion=bool(float(row["die_yield"]) < threshold),
        ))

    return YieldTrendResponse(
        points=points,
        fleet_mean=round(fleet_mean, 4),
        excursion_threshold=round(threshold, 4),
        generated_at=_utcnow(),
    )


@router.get("/chambers", response_model=ChamberRecurrenceResponse)
def chamber_recurrence(db: Session = Depends(get_db)):
    """Return chamber recurrence analysis for all chambers."""
    yields_df = ingestion.load_yield_results(db)
    wafers_df = ingestion.load_wafers(db)
    lots_df   = ingestion.load_lots(db)
    runs_df   = ingestion.load_runs(db)
    chambers_raw = ingestion.load_chambers(db)

    yield_with_lot = yields_df.merge(
        wafers_df[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )

    results = analyze_chamber_recurrence(lots_df, yield_with_lot, runs_df, chambers_raw)

    return ChamberRecurrenceResponse(
        chambers=[
            ChamberRecurrenceSummary(
                chamber_id=r.chamber_id,
                chamber_name=r.chamber_name,
                tool_name=r.tool_name,
                affected_lot_count=r.affected_lot_count,
                chamber_mean_yield=r.chamber_mean_yield,
                fleet_mean_yield=r.fleet_mean_yield,
                yield_gap=r.yield_gap,
                recurrence_score=r.recurrence_score,
                is_recurrent=r.is_recurrent,
                algorithm_version=r.algorithm_version,
            )
            for r in results
        ],
        generated_at=_utcnow(),
    )
