"""
app/services/temporal.py — Temporal precedence and maintenance proximity.

Algorithm versions:
    temporal_precedence_v1  : verify that a candidate factor occurred BEFORE
                              the yield outcome (strict causal ordering).
    maintenance_proximity_v1: measure yield shift around a maintenance event.

IMPORTANT:
- No FastAPI, no DB session, no side effects.
- Inputs are plain pandas DataFrames / datetime values.
- Does NOT read scenario labels.

Design notes
------------
Temporal precedence is a NECESSARY (not sufficient) condition for causality.
A factor that occurred AFTER the yield excursion cannot be its cause.

Maintenance proximity measures whether yield changed significantly in the
period immediately following a maintenance event on the same chamber.
The "before" window is MAINT_BEFORE_LOTS lots completed before the PM.
The "after" window is MAINT_AFTER_LOTS lots completed after the PM.
Minimum of MIN_WINDOW_LOTS lots required in each window.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

import numpy as np
import pandas as pd

from app.services.evidence import (
    VERSIONS,
    MaintenanceProximityResult,
    TemporalPrecedenceResult,
    _utcnow,
    make_evidence_id,
)

# ---------------------------------------------------------------------------
# Documented thresholds
# ---------------------------------------------------------------------------

# Maintenance proximity windows (in lots)
MAINT_BEFORE_LOTS = 10   # lots completed before the PM event
MAINT_AFTER_LOTS  = 10   # lots completed after the PM event
MIN_WINDOW_LOTS   = 3    # minimum lots in each window to compute a mean

# Minimum yield shift to flag maintenance proximity
MAINT_YIELD_SHIFT_THRESHOLD: float = 0.02  # 2 percentage points


def check_temporal_precedence(
    candidate_factor: str,
    factor_timestamp: datetime,
    outcome_timestamp: datetime,
) -> TemporalPrecedenceResult:
    """
    Assert that a candidate causal factor occurred strictly before the outcome.

    Parameters
    ----------
    candidate_factor  : human-readable label of the candidate (e.g. 'etch_rate_drift')
    factor_timestamp  : when the candidate factor was first observed
    outcome_timestamp : when the yield excursion / outcome was observed

    Returns
    -------
    TemporalPrecedenceResult with precedence_valid = True only if
    factor_timestamp < outcome_timestamp.

    Notes
    -----
    If timestamps are equal (same resolution), precedence is considered invalid
    to be conservative.
    """
    delta = outcome_timestamp - factor_timestamp
    delta_hours = delta.total_seconds() / 3600.0
    precedence_valid = delta_hours > 0.0

    eid = make_evidence_id(
        "temporal",
        candidate_factor,
        f"{factor_timestamp.date()}",
    )

    return TemporalPrecedenceResult(
        candidate_factor=candidate_factor,
        factor_timestamp=factor_timestamp,
        outcome_timestamp=outcome_timestamp,
        time_delta_hours=round(delta_hours, 2),
        precedence_valid=precedence_valid,
        evidence_id=eid,
        algorithm_version=VERSIONS["temporal_precedence"],
    )


def analyze_maintenance_proximity(
    chamber_id: int,
    chamber_name: str,
    maintenance_events_df: pd.DataFrame,
    lots_df: pd.DataFrame,
    yield_df: pd.DataFrame,
    runs_df: pd.DataFrame,
) -> list[MaintenanceProximityResult]:
    """
    Measure yield shift around each maintenance event on a chamber.

    Parameters
    ----------
    chamber_id            : DB PK of the chamber to analyse
    chamber_name          : display name
    maintenance_events_df : columns [maint_id, chamber_id, event_type,
                                     event_at, event_subtype]
                            (subset for this chamber)
    lots_df               : columns [lot_id (int PK), lot_id_str,
                                     actual_start_at, actual_end_at]
    yield_df              : columns [wafer_id, lot_id (int FK), die_yield]
    runs_df               : columns [run_id, wafer_id, chamber_id (int FK)]

    Returns
    -------
    List of MaintenanceProximityResult — one per maintenance event where
    both before- and after-windows have sufficient lots.

    Algorithm
    ---------
    For each PM event at time T:
      before_lots = lots that completed on this chamber in the window
                    [T - MAINT_BEFORE_LOTS, T)   (by lot order)
      after_lots  = lots that completed on this chamber in the window
                    (T, T + MAINT_AFTER_LOTS]    (by lot order)
      yield_shift = after_mean - before_mean
      Flag if |yield_shift| >= MAINT_YIELD_SHIFT_THRESHOLD
    """
    results: list[MaintenanceProximityResult] = []

    # Filter maintenance events to this chamber
    cham_events = maintenance_events_df[
        maintenance_events_df["chamber_id"] == chamber_id
    ].copy()

    if cham_events.empty:
        return results

    # Lot-level mean yield
    lot_yield = (
        yield_df.groupby("lot_id")["die_yield"]
        .mean()
        .reset_index()
        .rename(columns={"die_yield": "lot_mean_yield"})
    )

    # Identify lots processed on this chamber (via runs)
    chamber_runs = runs_df[runs_df["chamber_id"] == chamber_id][["run_id", "wafer_id"]].copy()
    # Map wafer → lot
    wafer_lot = yield_df[["wafer_id", "lot_id"]].drop_duplicates("wafer_id")
    cham_lots_series = (
        chamber_runs
        .merge(wafer_lot, on="wafer_id", how="left")["lot_id"]
        .dropna()
        .unique()
    )
    cham_lot_ids = set(int(x) for x in cham_lots_series)

    cham_lots_df = lots_df[lots_df["lot_id"].isin(cham_lot_ids)].copy()
    cham_lots_df = cham_lots_df.merge(lot_yield, on="lot_id", how="left").dropna(
        subset=["lot_mean_yield", "actual_end_at"]
    )
    cham_lots_df = cham_lots_df.sort_values("actual_end_at")

    for _, maint_row in cham_events.iterrows():
        maint_id   = int(maint_row["maint_id"])
        event_type = str(maint_row.get("event_type", "pm"))
        event_at   = pd.to_datetime(maint_row["event_at"])

        before = cham_lots_df[cham_lots_df["actual_end_at"] < event_at].tail(MAINT_BEFORE_LOTS)
        after  = cham_lots_df[cham_lots_df["actual_start_at"] > event_at].head(MAINT_AFTER_LOTS)

        if len(before) < MIN_WINDOW_LOTS or len(after) < MIN_WINDOW_LOTS:
            continue

        pre_yield  = float(before["lot_mean_yield"].mean())
        post_yield = float(after["lot_mean_yield"].mean())
        yield_shift = post_yield - pre_yield

        # lot_start_at: use the first after-window lot's start
        lot_start_at = pd.to_datetime(after.iloc[0]["actual_start_at"])
        # elapsed_hours from event_at to first post-maint lot start
        elapsed_hours = (
            (lot_start_at - event_at).total_seconds() / 3600.0
        )

        eid = make_evidence_id(
            "maintenance_event",
            maint_id,
            f"chamber_{chamber_id}",
        )

        results.append(MaintenanceProximityResult(
            chamber_id=chamber_id,
            chamber_name=chamber_name,
            maintenance_event_id=maint_id,
            event_type=event_type,
            maintenance_at=event_at.to_pydatetime(),
            lot_start_at=lot_start_at.to_pydatetime(),
            elapsed_hours=round(elapsed_hours, 2),
            post_maint_yield=round(post_yield, 4),
            pre_maint_yield=round(pre_yield, 4),
            yield_shift=round(yield_shift, 4),
            evidence_id=eid,
            algorithm_version=VERSIONS["maintenance_proximity"],
        ))

    return results
