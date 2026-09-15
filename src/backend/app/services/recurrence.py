"""
app/services/recurrence.py — Chamber / tool recurrence analysis.

Algorithm version: chamber_recurrence_v1

Identifies chambers where yield is systematically and persistently lower
than the fleet average.  A "recurrent" chamber contributes a strong signal
to the chamber-systematic root-cause candidate.

IMPORTANT:
- No FastAPI, no DB session, no side effects.
- Inputs are plain pandas DataFrames.
- Does NOT read scenario labels.

Algorithm
---------
For each chamber:
  1.  Compute mean die_yield over all lots that processed on that chamber
      (affected lots) vs the fleet mean over all lots.
  2.  yield_gap = fleet_mean_yield - chamber_mean_yield
      (positive gap → chamber is underperforming)
  3.  recurrence_score is a sigmoid-like normalisation of yield_gap:
          score = tanh(yield_gap / GAP_SCALE)
      This maps a gap of ~GAP_SCALE to a score of ~0.76.
      GAP_SCALE = 0.05 (5 pp yield gap) is documented below.
  4.  A chamber is flagged is_recurrent if:
          score >= RECURRENCE_THRESHOLD
          AND affected_lot_count >= MIN_LOTS_PER_CHAMBER

Reference: score uses tanh so it saturates gracefully at large gaps and
           is symmetric around zero.  Negative gap (chamber better than fleet)
           produces a score < 0.

Notes
-----
This prototype computes chamber yield using ALL available historical lots,
not just a rolling window.  A production implementation would apply a
time-bounded window to detect transient vs persistent effects.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.evidence import (
    VERSIONS,
    ChamberRecurrenceResult,
    _utcnow,
    make_evidence_id,
)

# ---------------------------------------------------------------------------
# Documented thresholds
# ---------------------------------------------------------------------------

# Minimum lots per chamber to compute a meaningful yield average
MIN_LOTS_PER_CHAMBER = 5

# Yield gap scale for tanh normalisation (5 percentage points)
GAP_SCALE: float = 0.05

# Recurrence threshold: score ≥ this → chamber is recurrently affected
RECURRENCE_THRESHOLD: float = 0.50


def analyze_chamber_recurrence(
    lots_df: pd.DataFrame,
    yield_df: pd.DataFrame,
    runs_df: pd.DataFrame,
    chambers_df: pd.DataFrame,
) -> list[ChamberRecurrenceResult]:
    """
    Identify chambers with persistent yield deficits vs the fleet average.

    Parameters
    ----------
    lots_df      : columns [lot_id (int PK), lot_id_str]
    yield_df     : columns [wafer_id (int), lot_id (int FK), die_yield (float)]
    runs_df      : columns [run_id, wafer_id (int FK), chamber_id (int FK)]
    chambers_df  : columns [chamber_id (int PK), chamber_name, tool_name]

    Returns
    -------
    List of ChamberRecurrenceResult — one per chamber, sorted by
    recurrence_score descending.  Chambers with < MIN_LOTS_PER_CHAMBER
    affected lots are skipped.
    """
    # Lot-level mean yield
    lot_yield = (
        yield_df.groupby("lot_id")["die_yield"]
        .mean()
        .reset_index()
        .rename(columns={"die_yield": "lot_mean_yield"})
    )

    fleet_mean = float(lot_yield["lot_mean_yield"].mean())

    # Map wafer → lot
    wafer_lot = (
        yield_df[["wafer_id", "lot_id"]]
        .drop_duplicates("wafer_id")
    )

    # Map run → chamber
    run_chamber = runs_df[["run_id", "wafer_id", "chamber_id"]].copy()

    # Combine: wafer → lot → yield, run → chamber
    wafer_yield = wafer_lot.merge(lot_yield, on="lot_id", how="left")
    run_wafer = run_chamber.merge(wafer_yield, on="wafer_id", how="left")

    # For each chamber: collect affected lots (unique lot_ids)
    results: list[ChamberRecurrenceResult] = []

    if chambers_df.empty:
        return results

    for _, cham_row in chambers_df.iterrows():
        cid = int(cham_row["chamber_id"])
        cname = str(cham_row.get("chamber_name", f"chamber_{cid}"))
        tname = str(cham_row.get("tool_name", "unknown"))

        cham_runs = run_wafer[run_wafer["chamber_id"] == cid]
        if cham_runs.empty:
            continue

        # De-duplicate by lot
        affected_lots = (
            cham_runs[["lot_id", "lot_mean_yield"]]
            .dropna()
            .drop_duplicates("lot_id")
        )

        n_affected = len(affected_lots)
        if n_affected < MIN_LOTS_PER_CHAMBER:
            continue

        chamber_mean = float(affected_lots["lot_mean_yield"].mean())
        yield_gap = fleet_mean - chamber_mean  # positive → chamber underperforms

        recurrence_score = float(np.tanh(yield_gap / GAP_SCALE))
        is_recurrent = (
            recurrence_score >= RECURRENCE_THRESHOLD
            and n_affected >= MIN_LOTS_PER_CHAMBER
        )

        # Build evidence IDs for affected lots above excursion threshold
        low_yield_lots = affected_lots[
            affected_lots["lot_mean_yield"] < (fleet_mean - GAP_SCALE)
        ]
        evidence_ids = [
            make_evidence_id("lot", int(row["lot_id"]), f"chamber_recurrence_{cid}")
            for _, row in low_yield_lots.iterrows()
        ]

        results.append(ChamberRecurrenceResult(
            chamber_id=cid,
            chamber_name=cname,
            tool_name=tname,
            affected_lot_count=n_affected,
            reference_lot_count=len(lot_yield),
            chamber_mean_yield=round(chamber_mean, 4),
            fleet_mean_yield=round(fleet_mean, 4),
            yield_gap=round(yield_gap, 4),
            recurrence_score=round(recurrence_score, 4),
            is_recurrent=is_recurrent,
            evidence_ids=evidence_ids[:20],  # cap for response size
            algorithm_version=VERSIONS["chamber_recurrence"],
        ))

    results.sort(key=lambda r: r.recurrence_score, reverse=True)
    return results
