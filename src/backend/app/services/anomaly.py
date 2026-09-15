"""
app/services/anomaly.py — Yield excursion and process parameter anomaly detection.

Algorithm versions:
    yield_excursion_v1 : rolling-window median/MAD baseline; severity by sigma bands.
    process_anomaly_v1 : z-score per (chamber, recipe, param_name); |z| > threshold.

No FastAPI imports.  Input: pandas DataFrames.  Output: typed result objects.

PROTOTYPE NOTE:
Thresholds are documented heuristics for demonstration purposes.
These are not production-certified SPC (Statistical Process Control) limits.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

import numpy as np
import pandas as pd

from app.services.evidence import (
    VERSIONS,
    ParameterAnomalyResult,
    YieldExcursionResult,
    _utcnow,
    make_evidence_id,
)

# ---------------------------------------------------------------------------
# Documented thresholds
# ---------------------------------------------------------------------------

# Yield excursion — minimum historical window before flagging
MIN_HISTORY_LOTS = 10

# Yield severity bands (in MAD units from median)
# Uses MAD (Median Absolute Deviation) as robust alternative to std.
# σ_robust ≈ 1.4826 × MAD for a normal distribution.
YIELD_SEVERITY_THRESHOLDS = {
    "severe":   4.0,   # > 4 robust-σ below baseline
    "moderate": 3.0,   # > 3 robust-σ below baseline
    "mild":     2.5,   # > 2.5 robust-σ below baseline
}

# Process parameter anomaly — z-score threshold
PARAM_ANOMALY_Z_THRESHOLD = 3.0

# Parameter severity bands
PARAM_SEVERITY_THRESHOLDS = {
    "severe":   5.0,
    "moderate": 4.0,
    "mild":     PARAM_ANOMALY_Z_THRESHOLD,
}


def _robust_sigma(values: np.ndarray) -> float:
    """
    Compute the robust standard deviation estimate from Median Absolute Deviation.

    σ_robust = 1.4826 × MAD
    Returns 0.0 if fewer than 3 values (insufficient for a meaningful estimate).
    """
    if len(values) < 3:
        return 0.0
    mad = float(np.median(np.abs(values - np.median(values))))
    return 1.4826 * mad


def _classify_yield_severity(deviation_sigma: float) -> str:
    """Map deviation (in robust-σ units) to a severity string."""
    abs_dev = abs(deviation_sigma)
    if abs_dev >= YIELD_SEVERITY_THRESHOLDS["severe"]:
        return "severe"
    if abs_dev >= YIELD_SEVERITY_THRESHOLDS["moderate"]:
        return "moderate"
    if abs_dev >= YIELD_SEVERITY_THRESHOLDS["mild"]:
        return "mild"
    return "none"


def _classify_param_severity(z: float) -> str:
    abs_z = abs(z)
    if abs_z >= PARAM_SEVERITY_THRESHOLDS["severe"]:
        return "severe"
    if abs_z >= PARAM_SEVERITY_THRESHOLDS["moderate"]:
        return "moderate"
    if abs_z >= PARAM_SEVERITY_THRESHOLDS["mild"]:
        return "mild"
    return "none"


# ---------------------------------------------------------------------------
# 1. Yield excursion detection
# ---------------------------------------------------------------------------

def detect_yield_excursion(
    target_lot_id: str,
    target_yield: float,
    target_lot_actual_start: datetime,
    historical_yields: pd.DataFrame,
) -> YieldExcursionResult:
    """
    Detect whether a lot's yield is a statistical excursion relative to
    historical baseline lots on the same chamber.

    Parameters
    ----------
    target_lot_id         : business-key of the lot under investigation
    target_yield          : mean die_yield for the target lot's wafers
    target_lot_actual_start : when the target lot started (for temporal gate)
    historical_yields     : DataFrame with columns [lot_id, actual_start_at,
                            die_yield, chamber_id] for historical lots.
                            Must NOT include the target lot itself.

    Returns
    -------
    YieldExcursionResult

    Notes
    -----
    Algorithm  : rolling median + MAD-based robust σ over the preceding
                 MIN_HISTORY_LOTS lots on the same chamber.
    Formula    : deviation_sigma = (observed − median) / (1.4826 × MAD)
    Threshold  : mild ≥ 2.5σ | moderate ≥ 3σ | severe ≥ 4σ (below baseline)
    Reference  : Montgomery, D.C. "Introduction to Statistical Quality Control"
    """
    # Sort by start time, keep only prior lots
    hist = historical_yields.copy()
    if "actual_start_at" in hist.columns:
        hist = hist[hist["actual_start_at"] < target_lot_actual_start]
    hist = hist.sort_values("actual_start_at") if "actual_start_at" in hist.columns else hist

    n_available = len(hist)
    if n_available < MIN_HISTORY_LOTS:
        # Insufficient history — cannot determine excursion
        eid = make_evidence_id("yield_result", target_lot_id, "die_yield")
        return YieldExcursionResult(
            lot_id=target_lot_id,
            observed_yield=target_yield,
            baseline_yield=float("nan"),
            deviation=float("nan"),
            deviation_sigma=float("nan"),
            severity="none",
            is_excursion=False,
            method="insufficient_history",
            n_lots_used=n_available,
            evidence_id=eid,
            algorithm_version=VERSIONS["yield_excursion"],
        )

    yields = hist["die_yield"].values.astype(float)
    baseline_median = float(np.median(yields))
    rob_sigma = _robust_sigma(yields)

    if rob_sigma == 0.0:
        # Degenerate — all identical yields; treat as no excursion
        deviation_sigma = 0.0
    else:
        deviation_sigma = (target_yield - baseline_median) / rob_sigma

    severity = _classify_yield_severity(deviation_sigma)
    is_excursion = severity != "none" and deviation_sigma < 0

    eid = make_evidence_id("yield_result", target_lot_id, "die_yield")
    return YieldExcursionResult(
        lot_id=target_lot_id,
        observed_yield=round(target_yield, 4),
        baseline_yield=round(baseline_median, 4),
        deviation=round(target_yield - baseline_median, 4),
        deviation_sigma=round(deviation_sigma, 3),
        severity=severity,
        is_excursion=is_excursion,
        method=f"median_mad_robust_sigma (n={n_available})",
        n_lots_used=n_available,
        evidence_id=eid,
        algorithm_version=VERSIONS["yield_excursion"],
    )


def detect_yield_excursions_bulk(
    lots_df: pd.DataFrame,
    yield_df: pd.DataFrame,
    wafers_df: pd.DataFrame | None = None,
    min_history: int = MIN_HISTORY_LOTS,
) -> list[YieldExcursionResult]:
    """
    Run excursion detection across all lots in lots_df.

    Parameters
    ----------
    lots_df   : columns [lot_id (int PK), lot_id_str, actual_start_at, ...]
    yield_df  : columns [wafer_id, die_yield] OR [wafer_id, lot_id, die_yield]
    wafers_df : columns [wafer_id, lot_id] — required if yield_df has no lot_id column
    min_history : minimum historical lots required

    Returns
    -------
    List of YieldExcursionResult — one per lot, sorted by lot actual_start_at.
    """
    # Resolve lot_id in yield_df
    if "lot_id" not in yield_df.columns:
        if wafers_df is None:
            raise ValueError(
                "yield_df has no lot_id column; supply wafers_df to resolve the mapping."
            )
        yield_with_lot = yield_df.merge(wafers_df[["wafer_id", "lot_id"]], on="wafer_id", how="left")
    else:
        yield_with_lot = yield_df.copy()

    # Aggregate yield to lot level
    lot_yields = (
        yield_with_lot.groupby("lot_id")["die_yield"]
        .mean()
        .reset_index()
        .rename(columns={"die_yield": "mean_yield"})
    )
    merged = lots_df.merge(lot_yields, on="lot_id", how="left")
    merged = merged.sort_values("actual_start_at")

    results: list[YieldExcursionResult] = []
    for _, row in merged.iterrows():
        lot_id_str = str(row["lot_id_str"])
        if pd.isna(row.get("mean_yield", float("nan"))):
            continue
        obs_yield = float(row["mean_yield"])
        start = row["actual_start_at"]

        # Historical lots started before this one
        hist_rows = merged[merged["actual_start_at"] < start][
            ["lot_id_str", "actual_start_at", "mean_yield"]
        ].copy()
        hist_rows = hist_rows.rename(columns={"mean_yield": "die_yield"})

        result = detect_yield_excursion(
            target_lot_id=lot_id_str,
            target_yield=obs_yield,
            target_lot_actual_start=start,
            historical_yields=hist_rows,
        )
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# 2. Process parameter anomaly detection
# ---------------------------------------------------------------------------

def detect_parameter_anomalies(
    target_lot_id: str,
    target_run_ids: Sequence[int],
    params_df: pd.DataFrame,
    runs_df: pd.DataFrame,
    historical_params_df: pd.DataFrame,
) -> list[ParameterAnomalyResult]:
    """
    Detect out-of-control process parameters for runs associated with a target lot.

    Parameters
    ----------
    target_lot_id     : business key of the lot
    target_run_ids    : run IDs belonging to the target lot's wafers
    params_df         : process_parameters rows for the target lot's runs
                        columns: [pp_id, run_id, param_name, value, unit,
                                  nominal, lsl, usl]
    runs_df           : all runs, columns: [run_id, wafer_id, chamber_id,
                                            recipe_id, start_time, ...]
    historical_params_df : process_parameters for ALL historical runs
                        (must NOT include target_run_ids)

    Returns
    -------
    List of ParameterAnomalyResult for parameters with |z| ≥ threshold.

    Algorithm
    ---------
    For each (chamber_id, recipe_id, param_name) group, compute:
        z = (observed − group_mean) / group_std
    Flag if |z| ≥ PARAM_ANOMALY_Z_THRESHOLD (3.0).
    Minimum group size: 5 observations.
    """
    results: list[ParameterAnomalyResult] = []

    # Build run→chamber/recipe mapping
    run_meta = runs_df.set_index("run_id")[["chamber_id", "recipe_id", "start_time"]].to_dict("index")

    # Filter to target runs
    target_params = params_df[params_df["run_id"].isin(target_run_ids)].copy()

    # Exclude target runs from historical baseline
    hist_params = historical_params_df[~historical_params_df["run_id"].isin(target_run_ids)].copy()

    # Add chamber/recipe to historical params
    hist_runs_meta = runs_df[["run_id", "chamber_id", "recipe_id"]].copy()
    hist_params = hist_params.merge(hist_runs_meta, on="run_id", how="left")

    # Compute baselines: group by (chamber_id, recipe_id, param_name)
    baselines = (
        hist_params.groupby(["chamber_id", "recipe_id", "param_name"])["value"]
        .agg(["mean", "std", "count"])
        .reset_index()
        .rename(columns={"mean": "base_mean", "std": "base_std", "count": "n"})
    )

    for _, prow in target_params.iterrows():
        run_id = int(prow["run_id"])
        param_name = str(prow["param_name"])
        value = float(prow["value"])

        meta = run_meta.get(run_id)
        if meta is None:
            continue
        chamber_id = int(meta["chamber_id"])
        recipe_id = int(meta["recipe_id"])
        run_time = meta.get("start_time", _utcnow())

        # Look up baseline
        base_row = baselines[
            (baselines["chamber_id"] == chamber_id)
            & (baselines["recipe_id"] == recipe_id)
            & (baselines["param_name"] == param_name)
        ]

        if base_row.empty or int(base_row["n"].iloc[0]) < 5:
            continue  # insufficient history for this group

        base_mean = float(base_row["base_mean"].iloc[0])
        base_std = float(base_row["base_std"].iloc[0])

        if base_std == 0.0 or pd.isna(base_std):
            continue  # degenerate — all identical values

        z = (value - base_mean) / base_std
        if abs(z) < PARAM_ANOMALY_Z_THRESHOLD:
            continue  # within control

        severity = _classify_param_severity(z)
        direction = "high" if z > 0 else "low"

        eid = make_evidence_id("process_parameter", run_id, param_name)
        results.append(ParameterAnomalyResult(
            lot_id=target_lot_id,
            run_id=run_id,
            chamber_id=chamber_id,
            tool_id=-1,  # resolved by caller if needed
            param_name=param_name,
            observed_value=round(value, 4),
            baseline_mean=round(base_mean, 4),
            baseline_std=round(base_std, 4),
            z_score=round(z, 3),
            direction=direction,
            severity=severity,
            is_anomaly=True,
            evidence_id=eid,
            algorithm_version=VERSIONS["process_anomaly"],
        ))

    return results
