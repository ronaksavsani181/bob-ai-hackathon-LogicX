"""
generator.py — Deterministic synthetic fab dataset generator.

Produces all tables as pandas DataFrames in-memory, ready for bulk DB insertion.
All random draws use a single numpy Generator seeded with GLOBAL_SEED (42).

IMPORTANT:
- This is synthetic demonstration data only.
- It does not represent any real semiconductor fab or process.
- Ground-truth scenario labels are stored in lot_ground_truth (not in ORM tables)
  so the analytics layer cannot use them.

Output DataFrames and their primary key columns:

    tools             : tool_id (business key: tool_name)
    chambers          : chamber_id (business key: chamber_name)
    recipes           : recipe_id
    lots              : lot_id (business key: lot_id_str)
    wafers            : wafer_id
    runs              : run_id
    process_parameters: pp_id
    trace_data        : trace_id
    metrology         : metro_id
    defects           : defect_id
    maintenance_events: maint_id
    yield_results     : yield_id
    lot_ground_truth  : (lot_id_str → scenario_id mapping, NOT inserted to DB)
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import numpy as np
import pandas as pd

from data.synthetic.scenarios import (
    CHAMBERS,
    GLOBAL_SEED,
    HISTORY_DAYS,
    LOTS_TOTAL,
    PRE_RUN_FORBIDDEN_COLUMNS,
    SCENARIOS,
    TOOL_NAMES,
    WAFER_RADIUS_MM,
    WAFERS_PER_LOT,
    ScenarioDef,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HISTORY_START = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
HISTORY_END = HISTORY_START + timedelta(days=HISTORY_DAYS)

PARAMS_PER_RUN = 8
METROLOGY_SITES_PER_WAFER = 5
TRACE_POINTS_PER_RUN = 10
NOMINAL_YIELD = 0.945   # healthy baseline mean
YIELD_SIGMA = 0.015     # natural process variation

# Nominal process parameter specs (name → {nominal, sigma, unit, lsl, usl})
PARAM_SPECS: dict[str, dict] = {
    "etch_rate":     {"nominal": 120.0, "sigma": 2.0,  "unit": "nm/min", "lsl": 100.0, "usl": 140.0},
    "pressure":      {"nominal": 5.0,   "sigma": 0.1,  "unit": "mTorr",  "lsl": 4.0,   "usl": 6.0},
    "rf_power":      {"nominal": 300.0, "sigma": 5.0,  "unit": "W",      "lsl": 260.0, "usl": 340.0},
    "temperature":   {"nominal": 400.0, "sigma": 3.0,  "unit": "C",      "lsl": 380.0, "usl": 420.0},
    "gas_flow_ar":   {"nominal": 50.0,  "sigma": 1.0,  "unit": "sccm",   "lsl": 40.0,  "usl": 60.0},
    "gas_flow_cf4":  {"nominal": 20.0,  "sigma": 0.5,  "unit": "sccm",   "lsl": 16.0,  "usl": 24.0},
    "bias_voltage":  {"nominal": 200.0, "sigma": 4.0,  "unit": "V",      "lsl": 180.0, "usl": 220.0},
    "chuck_temp":    {"nominal": 20.0,  "sigma": 0.5,  "unit": "C",      "lsl": 18.0,  "usl": 22.0},
}
PARAM_NAMES: list[str] = list(PARAM_SPECS.keys())

METROLOGY_TYPES = ["overlay_x", "overlay_y", "cd_mean", "thickness", "roughness"]

PRODUCTS = ["PROD-A", "PROD-B", "PROD-C"]
TECH_NODES = ["7nm", "5nm", "10nm"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FabDataset(NamedTuple):
    tools: pd.DataFrame
    chambers: pd.DataFrame
    recipes: pd.DataFrame
    lots: pd.DataFrame
    wafers: pd.DataFrame
    runs: pd.DataFrame
    process_parameters: pd.DataFrame
    trace_data: pd.DataFrame
    metrology: pd.DataFrame
    defects: pd.DataFrame
    maintenance_events: pd.DataFrame
    yield_results: pd.DataFrame
    lot_ground_truth: pd.DataFrame   # validation only — NOT inserted to DB


def _utcnow_str() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# 1. Tools and Chambers
# ---------------------------------------------------------------------------

def generate_tools_chambers() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (tools_df, chambers_df).

    tools columns   : tool_id, name, tool_type, fab_area, created_at, updated_at
    chambers columns: chamber_id, tool_id, name, chamber_index, created_at, updated_at
    """
    now = _ts(HISTORY_START)

    tool_rows = []
    for tid, tname in enumerate(TOOL_NAMES, start=1):
        chamber = next(c for c in CHAMBERS if c.tool_name == tname)
        tool_rows.append({
            "tool_id": tid,
            "name": tname,
            "tool_type": chamber.tool_type,
            "fab_area": chamber.fab_area,
            "created_at": now,
            "updated_at": now,
        })
    tools_df = pd.DataFrame(tool_rows)

    tool_name_to_id = {r["name"]: r["tool_id"] for r in tool_rows}

    chamber_rows = []
    for cid, c in enumerate(CHAMBERS, start=1):
        chamber_rows.append({
            "chamber_id": cid,
            "tool_id": tool_name_to_id[c.tool_name],
            "name": c.chamber_name,
            "chamber_index": c.chamber_index,
            "created_at": now,
            "updated_at": now,
        })
    chambers_df = pd.DataFrame(chamber_rows)

    return tools_df, chambers_df


# ---------------------------------------------------------------------------
# 2. Recipes
# ---------------------------------------------------------------------------

def generate_recipes() -> pd.DataFrame:
    """
    One recipe per process step (etch, litho, cvd, cmp, implant), version v1.

    columns: recipe_id, name, version, process_step, nominal_params, created_at, updated_at
    """
    now = _ts(HISTORY_START)
    steps = ["etch", "litho", "cvd", "cmp", "implant"]
    rows = []
    for rid, step in enumerate(steps, start=1):
        rows.append({
            "recipe_id": rid,
            "name": f"RCP-{step.upper()}-01",
            "version": "v1",
            "process_step": step,
            "nominal_params": {
                pname: {"nominal": spec["nominal"], "lsl": spec["lsl"], "usl": spec["usl"], "unit": spec["unit"]}
                for pname, spec in PARAM_SPECS.items()
            },
            "created_at": now,
            "updated_at": now,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Lots and Wafers
# ---------------------------------------------------------------------------

def _assign_scenario_tags(
    lot_indices: np.ndarray,
    rng: np.random.Generator,
) -> dict[int, str]:
    """
    Map lot index → scenario_id.

    Priority (highest wins):
      S-PART (L400-L412) > S-MAINT (L413-L428) > S-ETCH (L300-L360) > S-OVL (L200-L215)
      > S-CHAM (all, ~20% random) > S-TIME (~10% random) > S-CTRL (remainder)

    S-MAINT must use lots with actual_start_at > day 120 (unscheduled PM day).
    L413-L428 start around 2024-05-28 which is after the day-120 PM on 2024-04-30.
    """
    tags: dict[int, str] = {}
    for idx in lot_indices:
        if 400 <= idx <= 412:
            tags[idx] = "S-PART"
        elif 413 <= idx <= 428:
            tags[idx] = "S-MAINT"
        elif 300 <= idx <= 360:
            tags[idx] = "S-ETCH"
        elif 200 <= idx <= 215:
            tags[idx] = "S-OVL"
        else:
            tags[idx] = "S-CTRL"  # default; S-CHAM and S-TIME applied later

    # S-CHAM: 20% of non-scenario lots randomly assigned to CMP chamber lots
    # (marked for CMP routing; yield penalty applied in yield step)
    cham_candidates = [i for i, t in tags.items() if t == "S-CTRL"]
    n_cham = max(1, int(len(cham_candidates) * 0.20))
    cham_chosen = rng.choice(cham_candidates, size=n_cham, replace=False)
    for idx in cham_chosen:
        tags[idx] = "S-CHAM"

    # S-TIME: 10% of remaining S-CTRL lots get long queue time
    time_candidates = [i for i, t in tags.items() if t == "S-CTRL"]
    n_time = max(1, int(len(time_candidates) * 0.10))
    time_chosen = rng.choice(time_candidates, size=n_time, replace=False)
    for idx in time_chosen:
        tags[idx] = "S-TIME"

    return tags


def generate_lots_wafers(
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[int, str]]:
    """
    Returns (lots_df, wafers_df, lot_idx_to_scenario).

    lots columns:
        lot_id (int PK), lot_id_str, product, technology_node, priority,
        status, planned_start_at, actual_start_at, queue_time_h,
        created_at, updated_at

    wafers columns:
        wafer_id (int PK), lot_id (FK), wafer_slot, die_count_total,
        created_at, updated_at

    lot_idx_to_scenario: {lot_index → scenario_id}  (ground truth, NOT in DB schema)
    """
    lot_indices = np.arange(1, LOTS_TOTAL + 1)
    scenario_map = _assign_scenario_tags(lot_indices, rng)

    # Spread lots evenly across 180-day window
    seconds_per_lot = (HISTORY_DAYS * 86400) / LOTS_TOTAL
    products = rng.choice(PRODUCTS, size=LOTS_TOTAL)
    nodes = rng.choice(TECH_NODES, size=LOTS_TOTAL)
    priorities = rng.choice(["normal", "high", "low"], size=LOTS_TOTAL, p=[0.75, 0.15, 0.10])

    lot_rows = []
    wafer_rows = []
    wafer_id_counter = 1

    for i, idx in enumerate(lot_indices):
        planned_start = HISTORY_START + timedelta(seconds=i * seconds_per_lot)
        # Actual start: 0–4 hours after planned
        jitter_h = rng.uniform(0, 4)
        actual_start = planned_start + timedelta(hours=jitter_h)

        # S-TIME: inject long queue time for affected lots
        queue_time_h = rng.uniform(2.0, 12.0)  # normal queue 2–12 h
        if scenario_map.get(idx) == "S-TIME":
            queue_time_h = SCENARIOS["S-TIME"].queue_time_hours + rng.uniform(-5, 5)

        lot_id = i + 1
        lot_id_str = f"L{idx:04d}"

        lot_rows.append({
            "lot_id": lot_id,
            "lot_id_str": lot_id_str,
            "product": products[i],
            "technology_node": nodes[i],
            "priority": priorities[i],
            "status": "completed",
            "planned_start_at": _ts(planned_start),
            "actual_start_at": _ts(actual_start),
            "queue_time_h": round(queue_time_h, 2),
            "created_at": _ts(planned_start - timedelta(hours=1)),
            "updated_at": _ts(actual_start),
        })

        # Wafers: 25 per lot
        for slot in range(1, WAFERS_PER_LOT + 1):
            wafer_rows.append({
                "wafer_id": wafer_id_counter,
                "lot_id": lot_id,
                "wafer_slot": slot,
                "die_count_total": 500,
                "created_at": _ts(actual_start),
                "updated_at": _ts(actual_start),
            })
            wafer_id_counter += 1

    lots_df = pd.DataFrame(lot_rows)
    wafers_df = pd.DataFrame(wafer_rows)
    return lots_df, wafers_df, scenario_map


# ---------------------------------------------------------------------------
# 4. Chamber assignment for runs
# ---------------------------------------------------------------------------

def _chamber_for_lot(
    lot_idx: int,
    scenario: str,
    chambers_df: pd.DataFrame,
    recipes_df: pd.DataFrame,
    rng: np.random.Generator,
) -> tuple[int, int]:
    """
    Returns (chamber_id, recipe_id) for a lot's primary process run.

    Scenario-affected lots are routed to their designated chamber.
    Other lots are distributed across chambers of the relevant tool type.
    """
    # Scenario routing
    if scenario == "S-ETCH":
        target_chamber = rng.choice(["ETH-02-A", "ETH-02-B"])
    elif scenario == "S-OVL":
        target_chamber = rng.choice(["LIT-01-A", "LIT-01-B"])
    elif scenario == "S-PART":
        target_chamber = rng.choice(["CVD-03-A", "CVD-03-B"])
    elif scenario == "S-MAINT":
        target_chamber = rng.choice(["ETH-02-A", "ETH-02-B"])
    elif scenario == "S-CHAM":
        target_chamber = rng.choice(["CMP-02-A", "CMP-02-B"])
    else:
        # Distribute uniformly across all etch chambers for normal lots
        etch_chambers = ["ETH-01-A", "ETH-01-B", "ETH-02-A", "ETH-02-B"]
        target_chamber = rng.choice(etch_chambers)

    cid_row = chambers_df.loc[chambers_df["name"] == target_chamber]
    chamber_id = int(cid_row["chamber_id"].iloc[0])

    # Pick recipe by tool type
    chamber_row = cid_row.iloc[0]
    tool_id = chamber_row["tool_id"]
    # Map tool_id → tool_type via CHAMBERS constant
    tool_name = TOOL_NAMES[int(tool_id) - 1]
    cdef = next(c for c in CHAMBERS if c.tool_name == tool_name)
    step = cdef.tool_type if cdef.tool_type in ["etch", "litho", "cvd", "cmp", "implant"] else "etch"
    recipe_row = recipes_df.loc[recipes_df["process_step"] == step]
    recipe_id = int(recipe_row["recipe_id"].iloc[0])

    return chamber_id, recipe_id


# ---------------------------------------------------------------------------
# 5. Runs and Process Parameters
# ---------------------------------------------------------------------------

def generate_runs_params(
    lots_df: pd.DataFrame,
    wafers_df: pd.DataFrame,
    chambers_df: pd.DataFrame,
    recipes_df: pd.DataFrame,
    scenario_map: dict[int, str],
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    One run per wafer. Returns (runs_df, process_parameters_df).

    runs columns:
        run_id, wafer_id, chamber_id, recipe_id,
        start_time, end_time, run_status, created_at, updated_at

    process_parameters columns:
        pp_id, run_id, param_name, value, unit, nominal, lsl, usl,
        created_at, updated_at
    """
    run_rows = []
    pp_rows = []
    run_id = 1
    pp_id = 1

    # Pre-build lot_id → (scenario, actual_start_at, lot_idx_str) lookup
    lot_meta: dict[int, tuple[str, datetime, str]] = {}
    for _, row in lots_df.iterrows():
        lid = int(row["lot_id"])
        lot_idx_n = int(row["lot_id_str"][1:])
        scen = scenario_map.get(lot_idx_n, "S-CTRL")
        lot_meta[lid] = (scen, row["actual_start_at"], row["lot_id_str"])

    for _, wrow in wafers_df.iterrows():
        wafer_id = int(wrow["wafer_id"])
        lot_id = int(wrow["lot_id"])
        scen, actual_start, lot_id_str = lot_meta[lot_id]
        lot_idx = int(lot_id_str[1:])

        # Chamber and recipe for this lot
        chamber_id, recipe_id = _chamber_for_lot(
            lot_idx, scen, chambers_df, recipes_df, rng
        )

        # Run timing: 20-60 min per run
        run_duration_min = rng.uniform(20, 60)
        slot_offset_min = (int(wrow["wafer_slot"]) - 1) * rng.uniform(2, 5)
        start_time = actual_start + timedelta(minutes=slot_offset_min)
        end_time = start_time + timedelta(minutes=run_duration_min)

        run_rows.append({
            "run_id": run_id,
            "wafer_id": wafer_id,
            "chamber_id": chamber_id,
            "recipe_id": recipe_id,
            "start_time": _ts(start_time),
            "end_time": _ts(end_time),
            "run_status": "completed",
            "created_at": _ts(start_time),
            "updated_at": _ts(end_time),
        })

        # Process parameters
        for pname in PARAM_NAMES:
            spec = PARAM_SPECS[pname]
            base_value = rng.normal(spec["nominal"], spec["sigma"])

            # S-ETCH: drift etch_rate for affected lots
            if scen == "S-ETCH" and pname == "etch_rate":
                scen_def = SCENARIOS["S-ETCH"]
                total_lots = scen_def.lot_index_end - scen_def.lot_index_start
                progress = (lot_idx - scen_def.lot_index_start) / max(total_lots, 1)
                drift = scen_def.param_drift_end - scen_def.param_drift_start
                base_value = rng.normal(
                    scen_def.param_drift_start + progress * drift,
                    spec["sigma"],
                )

            pp_rows.append({
                "pp_id": pp_id,
                "run_id": run_id,
                "param_name": pname,
                "value": round(float(base_value), 4),
                "unit": spec["unit"],
                "nominal": spec["nominal"],
                "lsl": spec["lsl"],
                "usl": spec["usl"],
                "created_at": _ts(end_time),
                "updated_at": _ts(end_time),
            })
            pp_id += 1

        run_id += 1

    return pd.DataFrame(run_rows), pd.DataFrame(pp_rows)


# ---------------------------------------------------------------------------
# 6. Trace Data
# ---------------------------------------------------------------------------

def generate_trace_data(
    runs_df: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Lightweight: 10 time-series points per run, one channel (rf_power).

    columns: trace_id, run_id, timestamp, channel, value, created_at, updated_at
    """
    rows = []
    trace_id = 1
    for _, rrow in runs_df.iterrows():
        run_id = int(rrow["run_id"])
        start = rrow["start_time"]
        end = rrow["end_time"]
        duration_s = (end - start).total_seconds()
        for pt in range(TRACE_POINTS_PER_RUN):
            t_offset = duration_s * pt / (TRACE_POINTS_PER_RUN - 1)
            ts = start + timedelta(seconds=t_offset)
            value = rng.normal(300.0, 5.0)
            rows.append({
                "trace_id": trace_id,
                "run_id": run_id,
                "timestamp": _ts(ts),
                "channel": "rf_power",
                "value": round(float(value), 3),
                "created_at": _ts(ts),
                "updated_at": _ts(ts),
            })
            trace_id += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 7. Metrology
# ---------------------------------------------------------------------------

def generate_metrology(
    wafers_df: pd.DataFrame,
    lots_df: pd.DataFrame,
    scenario_map: dict[int, str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    5 sites × 5 measurement types per wafer.

    columns: metro_id, wafer_id, measurement_type, site_index, value, unit,
             measured_at, created_at, updated_at
    """
    metro_specs = {
        "overlay_x":  {"nominal": 0.0,  "sigma": 1.5,  "unit": "nm"},
        "overlay_y":  {"nominal": 0.0,  "sigma": 1.5,  "unit": "nm"},
        "cd_mean":    {"nominal": 14.0, "sigma": 0.3,  "unit": "nm"},
        "thickness":  {"nominal": 50.0, "sigma": 0.5,  "unit": "nm"},
        "roughness":  {"nominal": 0.5,  "sigma": 0.05, "unit": "nm"},
    }

    lot_id_to_meta: dict[int, tuple[str, datetime, str]] = {}
    for _, row in lots_df.iterrows():
        lid = int(row["lot_id"])
        lot_idx = int(row["lot_id_str"][1:])
        scen = scenario_map.get(lot_idx, "S-CTRL")
        lot_id_to_meta[lid] = (scen, row["actual_start_at"], row["lot_id_str"])

    rows = []
    metro_id = 1

    for _, wrow in wafers_df.iterrows():
        wafer_id = int(wrow["wafer_id"])
        lot_id = int(wrow["lot_id"])
        scen, actual_start, _ = lot_id_to_meta[lot_id]

        # Metrology measured ~2 hours after wafer start
        measured_at = actual_start + timedelta(hours=2, minutes=float(wrow["wafer_slot"]) * 3)

        for site in range(1, METROLOGY_SITES_PER_WAFER + 1):
            for mtype, spec in metro_specs.items():
                sigma_mult = 1.0
                # S-OVL: inflate overlay sigma
                if scen == "S-OVL" and mtype in ("overlay_x", "overlay_y"):
                    sigma_mult = SCENARIOS["S-OVL"].metrology_sigma_multiplier

                value = rng.normal(spec["nominal"], spec["sigma"] * sigma_mult)

                rows.append({
                    "metro_id": metro_id,
                    "wafer_id": wafer_id,
                    "measurement_type": mtype,
                    "site_index": site,
                    "value": round(float(value), 4),
                    "unit": spec["unit"],
                    "measured_at": _ts(measured_at),
                    "created_at": _ts(measured_at),
                    "updated_at": _ts(measured_at),
                })
                metro_id += 1

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 8. Defect Spatial Patterns
# ---------------------------------------------------------------------------

def _gen_defects_for_pattern(
    n_defects: int,
    pattern: str,
    rng: np.random.Generator,
) -> list[tuple[float, float]]:
    """
    Generate n_defects (x, y) coordinates in mm within a 150 mm radius wafer.
    Each pattern produces a recognisable spatial signature.
    """
    R = WAFER_RADIUS_MM
    coords: list[tuple[float, float]] = []

    while len(coords) < n_defects:
        needed = n_defects - len(coords)

        if pattern == "center_heavy":
            # Gaussian cluster centred at origin, σ ≈ 25 mm
            xs = rng.normal(0, 25, needed * 2)
            ys = rng.normal(0, 25, needed * 2)

        elif pattern == "edge_ring":
            # Annular band: 120 < r < 148 mm
            r = rng.uniform(120, 148, needed * 2)
            theta = rng.uniform(0, 2 * math.pi, needed * 2)
            xs = r * np.cos(theta)
            ys = r * np.sin(theta)

        elif pattern == "radial":
            # Four spoke directions: 0°, 90°, 180°, 270° ± 5°
            spoke_angles = [0, math.pi / 2, math.pi, 3 * math.pi / 2]
            angles = rng.choice(spoke_angles, size=needed * 2)
            angles = angles + rng.normal(0, 0.09, needed * 2)  # ±5° jitter
            r = rng.uniform(20, R - 5, needed * 2)
            xs = r * np.cos(angles)
            ys = r * np.sin(angles)

        elif pattern == "localized_hotspot":
            # Fixed quadrant: upper-right (x > 50, y > 50)
            xs = rng.uniform(50, R - 5, needed * 2)
            ys = rng.uniform(50, R - 5, needed * 2)

        elif pattern == "scratch_line":
            # Horizontal scratch: y ≈ 30 mm ± 5 mm, x spans full width
            y0 = 30.0
            xs = rng.uniform(-R + 5, R - 5, needed * 2)
            ys = rng.normal(y0, 5.0, needed * 2)

        elif pattern == "diffuse_center":
            # Moderate centre tendency, σ ≈ 60 mm
            xs = rng.normal(0, 60, needed * 2)
            ys = rng.normal(0, 60, needed * 2)

        else:  # uniform
            # Rejection sampling for uniform disk
            xs = rng.uniform(-R, R, needed * 2)
            ys = rng.uniform(-R, R, needed * 2)

        # Keep only points inside wafer radius
        r_check = np.sqrt(xs ** 2 + ys ** 2)
        mask = r_check < R
        valid_x = xs[mask]
        valid_y = ys[mask]
        for x, y in zip(valid_x[:needed], valid_y[:needed]):
            coords.append((float(x), float(y)))

    return coords[:n_defects]


def generate_defects(
    wafers_df: pd.DataFrame,
    lots_df: pd.DataFrame,
    scenario_map: dict[int, str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Per-wafer defect map with scenario-driven spatial patterns.

    columns: defect_id, wafer_id, x_coord, y_coord, size_um, defect_class,
             inspection_tool, inspected_at, created_at, updated_at
    """
    lot_id_to_meta: dict[int, tuple[str, datetime, str]] = {}
    for _, row in lots_df.iterrows():
        lid = int(row["lot_id"])
        lot_idx = int(row["lot_id_str"][1:])
        scen = scenario_map.get(lot_idx, "S-CTRL")
        lot_id_to_meta[lid] = (scen, row["actual_start_at"], row["lot_id_str"])

    rows = []
    defect_id = 1

    for _, wrow in wafers_df.iterrows():
        wafer_id = int(wrow["wafer_id"])
        lot_id = int(wrow["lot_id"])
        scen, actual_start, _ = lot_id_to_meta[lot_id]

        scen_def = SCENARIOS.get(scen, SCENARIOS["S-CTRL"])
        n_defects = int(rng.integers(scen_def.defect_count_min, scen_def.defect_count_max + 1))
        pattern = scen_def.defect_spatial_pattern

        coords = _gen_defects_for_pattern(n_defects, pattern, rng)
        inspected_at = actual_start + timedelta(hours=3)

        for x, y in coords:
            size_um = float(rng.exponential(0.15))
            rows.append({
                "defect_id": defect_id,
                "wafer_id": wafer_id,
                "x_coord": round(x, 3),
                "y_coord": round(y, 3),
                "size_um": round(size_um, 4),
                "defect_class": scen,  # ground-truth class — analytics must NOT use this field directly
                "inspection_tool": "KLA-01",
                "inspected_at": _ts(inspected_at),
                "created_at": _ts(inspected_at),
                "updated_at": _ts(inspected_at),
            })
            defect_id += 1

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 9. Maintenance Events
# ---------------------------------------------------------------------------

def generate_maintenance_events(
    chambers_df: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Scheduled PMs (~monthly) + 2 unscheduled events on ETH-02.

    columns: maint_id, chamber_id, event_type, performed_at, description,
             performed_by, created_at, updated_at
    """
    rows = []
    maint_id = 1

    for _, crow in chambers_df.iterrows():
        chamber_id = int(crow["chamber_id"])
        chamber_name = crow["name"]

        # Scheduled PM: approximately once per month (every 30 days)
        n_scheduled = HISTORY_DAYS // 30
        for pm_num in range(n_scheduled):
            base_day = pm_num * 30 + rng.integers(0, 5)
            performed_at = HISTORY_START + timedelta(days=int(base_day))
            rows.append({
                "maint_id": maint_id,
                "chamber_id": chamber_id,
                "event_type": "scheduled_pm",
                "performed_at": _ts(performed_at),
                "description": f"Monthly scheduled PM #{pm_num + 1}",
                "performed_by": rng.choice(["eng_smith", "eng_jones", "eng_patel"]),
                "created_at": _ts(performed_at),
                "updated_at": _ts(performed_at),
            })
            maint_id += 1

        # Unscheduled PM on ETH-02 chambers at day 120 (S-MAINT scenario)
        if chamber_name in ("ETH-02-A", "ETH-02-B"):
            performed_at = HISTORY_START + timedelta(days=120, hours=int(rng.integers(0, 6)))
            rows.append({
                "maint_id": maint_id,
                "chamber_id": chamber_id,
                "event_type": "unscheduled_pm",
                "performed_at": _ts(performed_at),
                "description": "Unscheduled PM — chamber wall deposit removal",
                "performed_by": "eng_smith",
                "created_at": _ts(performed_at),
                "updated_at": _ts(performed_at),
            })
            maint_id += 1

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 10. Yield Results
# ---------------------------------------------------------------------------

def generate_yield_results(
    wafers_df: pd.DataFrame,
    lots_df: pd.DataFrame,
    runs_df: pd.DataFrame,
    scenario_map: dict[int, str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    One yield result per wafer.  Scenario-driven penalties applied.

    columns: yield_id, wafer_id, die_yield, bin1_count, bin_fail_count,
             tested_at, created_at, updated_at
    """
    # Build lot_id → (scenario, actual_start_at, lot_id_str)
    lot_id_to_meta: dict[int, tuple[str, datetime, str]] = {}
    for _, row in lots_df.iterrows():
        lid = int(row["lot_id"])
        lot_idx = int(row["lot_id_str"][1:])
        scen = scenario_map.get(lot_idx, "S-CTRL")
        lot_id_to_meta[lid] = (scen, row["actual_start_at"], row["lot_id_str"])

    # Build wafer_id → run end time for tested_at anchor
    wafer_run_end: dict[int, datetime] = {}
    for _, rrow in runs_df.iterrows():
        wid = int(rrow["wafer_id"])
        if wid not in wafer_run_end:
            wafer_run_end[wid] = rrow["end_time"]

    rows = []
    yield_id = 1

    for _, wrow in wafers_df.iterrows():
        wafer_id = int(wrow["wafer_id"])
        lot_id = int(wrow["lot_id"])
        scen, actual_start, _ = lot_id_to_meta[lot_id]

        # Base yield with natural process variation
        base_yield = float(rng.normal(NOMINAL_YIELD, YIELD_SIGMA))
        base_yield = float(np.clip(base_yield, 0.70, 0.99))

        # Apply scenario penalty
        penalty = 0.0
        scen_def = SCENARIOS.get(scen, SCENARIOS["S-CTRL"])
        if scen != "S-CTRL":
            penalty = float(rng.uniform(scen_def.yield_penalty_min, scen_def.yield_penalty_max))

        die_yield = float(np.clip(base_yield - penalty, 0.55, 0.99))

        # CMP-02 systematic penalty (S-CHAM already has penalty in scenarios)
        # S-TIME is also already encoded

        die_count = 500
        bin1 = int(round(die_count * die_yield))
        bin_fail = die_count - bin1

        run_end = wafer_run_end.get(wafer_id, actual_start + timedelta(hours=1))
        tested_at = run_end + timedelta(hours=rng.uniform(0.5, 2.0))

        rows.append({
            "yield_id": yield_id,
            "wafer_id": wafer_id,
            "die_yield": round(die_yield, 4),
            "bin1_count": bin1,
            "bin_fail_count": bin_fail,
            "tested_at": _ts(tested_at),
            "created_at": _ts(tested_at),
            "updated_at": _ts(tested_at),
        })
        yield_id += 1

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 11. Ground Truth (validation only, NOT inserted to DB)
# ---------------------------------------------------------------------------

def generate_lot_ground_truth(
    lots_df: pd.DataFrame,
    scenario_map: dict[int, str],
) -> pd.DataFrame:
    """
    Machine-readable scenario label per lot.

    columns: lot_id_str, scenario_id, expected_root_cause

    NOT inserted into the database.
    Used only by validation tests and demo scripts.
    """
    rows = []
    for _, row in lots_df.iterrows():
        lot_idx = int(row["lot_id_str"][1:])
        scen = scenario_map.get(lot_idx, "S-CTRL")
        scen_def = SCENARIOS.get(scen, SCENARIOS["S-CTRL"])
        rows.append({
            "lot_id_str": row["lot_id_str"],
            "lot_id": int(row["lot_id"]),
            "scenario_id": scen,
            "expected_root_cause": scen_def.expected_root_cause,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 12. Top-level generator function
# ---------------------------------------------------------------------------

def generate_all(seed: int = GLOBAL_SEED) -> FabDataset:
    """
    Generate the complete synthetic fab dataset deterministically.

    Returns a FabDataset NamedTuple of DataFrames.
    Calling this function twice with the same seed produces identical results.
    """
    rng = np.random.default_rng(seed)

    tools_df, chambers_df = generate_tools_chambers()
    recipes_df = generate_recipes()
    lots_df, wafers_df, scenario_map = generate_lots_wafers(rng)
    runs_df, pp_df = generate_runs_params(lots_df, wafers_df, chambers_df, recipes_df, scenario_map, rng)
    trace_df = generate_trace_data(runs_df, rng)
    metro_df = generate_metrology(wafers_df, lots_df, scenario_map, rng)
    defects_df = generate_defects(wafers_df, lots_df, scenario_map, rng)
    maint_df = generate_maintenance_events(chambers_df, rng)
    yield_df = generate_yield_results(wafers_df, lots_df, runs_df, scenario_map, rng)
    ground_truth_df = generate_lot_ground_truth(lots_df, scenario_map)

    return FabDataset(
        tools=tools_df,
        chambers=chambers_df,
        recipes=recipes_df,
        lots=lots_df,
        wafers=wafers_df,
        runs=runs_df,
        process_parameters=pp_df,
        trace_data=trace_df,
        metrology=metro_df,
        defects=defects_df,
        maintenance_events=maint_df,
        yield_results=yield_df,
        lot_ground_truth=ground_truth_df,
    )
