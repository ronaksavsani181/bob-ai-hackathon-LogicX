"""
test_synthetic_data.py — Sub-Task 3 validation tests.

Tests run entirely against the in-memory generated DataFrames (no DB required).
They verify the generator contract and scenario integrity without touching
analytics logic.

Tested properties:
1. Row counts within expected ranges
2. All 7 scenarios represented in ground truth
3. Scenario-specific lots / chambers exist
4. Particle scenario defect density higher than control
5. Scenario yields degraded vs control (per-scenario)
6. Defect coordinates within wafer radius
7. Timestamps are logically ordered (lot start < run start < metrology < yield tested_at)
8. Generator is deterministic (calling twice with seed=42 gives identical results)
9. S-MAINT unscheduled PM exists before affected lot window
10. Pre-run feature separation: no future columns in PRE_RUN_FEATURE_WHITELIST
11. Generator-level ground truth never leaks into production ORM table columns
"""
import math

import numpy as np
import pandas as pd
import pytest

from data.synthetic.generator import FabDataset, generate_all
from data.synthetic.scenarios import (
    PRE_RUN_FEATURE_WHITELIST,
    PRE_RUN_FORBIDDEN_COLUMNS,
    SCENARIOS,
    WAFER_RADIUS_MM,
    LOTS_TOTAL,
    WAFERS_PER_LOT,
)


# ---------------------------------------------------------------------------
# Session-scoped fixture — generate once for the whole test session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def ds() -> FabDataset:
    return generate_all(seed=42)


@pytest.fixture(scope="session")
def ds2() -> FabDataset:
    """Second independent run used for determinism test."""
    return generate_all(seed=42)


# ---------------------------------------------------------------------------
# 1. Row counts
# ---------------------------------------------------------------------------

class TestRowCounts:
    def test_tools(self, ds):
        assert len(ds.tools) == 6, f"Expected 6 tools, got {len(ds.tools)}"

    def test_chambers(self, ds):
        assert len(ds.chambers) == 12, f"Expected 12 chambers, got {len(ds.chambers)}"

    def test_recipes(self, ds):
        assert 4 <= len(ds.recipes) <= 10, f"Unexpected recipe count: {len(ds.recipes)}"

    def test_lots(self, ds):
        assert len(ds.lots) == LOTS_TOTAL, f"Expected {LOTS_TOTAL} lots, got {len(ds.lots)}"

    def test_wafers(self, ds):
        expected = LOTS_TOTAL * WAFERS_PER_LOT
        assert len(ds.wafers) == expected, f"Expected {expected} wafers, got {len(ds.wafers)}"

    def test_runs(self, ds):
        # One run per wafer
        expected = LOTS_TOTAL * WAFERS_PER_LOT
        assert len(ds.runs) == expected, f"Expected {expected} runs, got {len(ds.runs)}"

    def test_process_parameters(self, ds):
        # 8 params per run × 12,500 runs
        expected_min = LOTS_TOTAL * WAFERS_PER_LOT * 7
        expected_max = LOTS_TOTAL * WAFERS_PER_LOT * 9
        n = len(ds.process_parameters)
        assert expected_min <= n <= expected_max, \
            f"process_parameters count {n} outside [{expected_min}, {expected_max}]"

    def test_trace_data(self, ds):
        # 10 points per run
        expected = LOTS_TOTAL * WAFERS_PER_LOT * 10
        assert len(ds.trace_data) == expected, \
            f"Expected {expected} trace rows, got {len(ds.trace_data)}"

    def test_metrology(self, ds):
        # 5 sites × 5 measurement types × 12,500 wafers
        expected_min = LOTS_TOTAL * WAFERS_PER_LOT * 20
        expected_max = LOTS_TOTAL * WAFERS_PER_LOT * 30
        n = len(ds.metrology)
        assert expected_min <= n <= expected_max, \
            f"metrology count {n} outside [{expected_min}, {expected_max}]"

    def test_defects_baseline(self, ds):
        # At least 8 defects/wafer average over all wafers
        n = len(ds.defects)
        total_wafers = LOTS_TOTAL * WAFERS_PER_LOT
        avg = n / total_wafers
        assert avg >= 8, f"Average defects/wafer {avg:.1f} below 8 baseline"

    def test_maintenance_events(self, ds):
        # At least 1 per chamber per month + unscheduled
        assert len(ds.maintenance_events) >= 12 * 6, \
            f"Too few maintenance events: {len(ds.maintenance_events)}"

    def test_yield_results(self, ds):
        assert len(ds.yield_results) == LOTS_TOTAL * WAFERS_PER_LOT, \
            f"Expected {LOTS_TOTAL * WAFERS_PER_LOT} yield records, got {len(ds.yield_results)}"

    def test_ground_truth(self, ds):
        assert len(ds.lot_ground_truth) == LOTS_TOTAL, \
            f"Expected {LOTS_TOTAL} ground truth rows, got {len(ds.lot_ground_truth)}"


# ---------------------------------------------------------------------------
# 2. All 7 scenarios represented
# ---------------------------------------------------------------------------

class TestScenarioCoverage:
    def test_all_scenario_ids_present(self, ds):
        present = set(ds.lot_ground_truth["scenario_id"].unique())
        required = {"S-ETCH", "S-OVL", "S-PART", "S-MAINT", "S-CHAM", "S-TIME", "S-CTRL"}
        missing = required - present
        assert not missing, f"Scenarios missing from ground truth: {missing}"

    def test_s_etch_lot_range(self, ds):
        etch_lots = ds.lot_ground_truth.loc[
            ds.lot_ground_truth["scenario_id"] == "S-ETCH", "lot_id_str"
        ]
        assert len(etch_lots) > 0
        # All should be in L300–L360
        indices = [int(l[1:]) for l in etch_lots]
        assert all(300 <= i <= 360 for i in indices), \
            f"S-ETCH lot outside expected range: {[i for i in indices if not (300 <= i <= 360)]}"

    def test_s_ovl_lot_range(self, ds):
        ovl_lots = ds.lot_ground_truth.loc[
            ds.lot_ground_truth["scenario_id"] == "S-OVL", "lot_id_str"
        ]
        assert len(ovl_lots) > 0
        indices = [int(l[1:]) for l in ovl_lots]
        assert all(200 <= i <= 215 for i in indices)

    def test_s_part_lot_range(self, ds):
        part_lots = ds.lot_ground_truth.loc[
            ds.lot_ground_truth["scenario_id"] == "S-PART", "lot_id_str"
        ]
        assert len(part_lots) > 0
        indices = [int(l[1:]) for l in part_lots]
        assert all(400 <= i <= 412 for i in indices)

    def test_s_maint_lot_range(self, ds):
        maint_lots = ds.lot_ground_truth.loc[
            ds.lot_ground_truth["scenario_id"] == "S-MAINT", "lot_id_str"
        ]
        assert len(maint_lots) > 0
        indices = [int(l[1:]) for l in maint_lots]
        assert all(413 <= i <= 428 for i in indices)

    def test_s_ctrl_is_majority(self, ds):
        counts = ds.lot_ground_truth["scenario_id"].value_counts()
        ctrl_count = counts.get("S-CTRL", 0)
        assert ctrl_count > LOTS_TOTAL * 0.4, \
            f"S-CTRL should be majority; got {ctrl_count} / {LOTS_TOTAL}"


# ---------------------------------------------------------------------------
# 3. Scenario chambers exist in runs
# ---------------------------------------------------------------------------

class TestScenarioChambers:
    def _lot_ids_for_scenario(self, ds: FabDataset, scenario_id: str) -> list[int]:
        rows = ds.lot_ground_truth.loc[ds.lot_ground_truth["scenario_id"] == scenario_id]
        return rows["lot_id"].tolist()

    def _wafer_ids_for_lots(self, ds: FabDataset, lot_ids: list[int]) -> list[int]:
        return ds.wafers.loc[ds.wafers["lot_id"].isin(lot_ids), "wafer_id"].tolist()

    def _chamber_names_for_wafers(self, ds: FabDataset, wafer_ids: list[int]) -> set[str]:
        run_rows = ds.runs.loc[ds.runs["wafer_id"].isin(wafer_ids)]
        chamber_ids = run_rows["chamber_id"].unique()
        names = ds.chambers.loc[ds.chambers["chamber_id"].isin(chamber_ids), "name"]
        return set(names)

    def test_etch_lots_use_eth02(self, ds):
        lot_ids = self._lot_ids_for_scenario(ds, "S-ETCH")
        wafer_ids = self._wafer_ids_for_lots(ds, lot_ids)
        cnames = self._chamber_names_for_wafers(ds, wafer_ids)
        assert cnames & {"ETH-02-A", "ETH-02-B"}, \
            f"S-ETCH lots should use ETH-02; got {cnames}"

    def test_ovl_lots_use_lit01(self, ds):
        lot_ids = self._lot_ids_for_scenario(ds, "S-OVL")
        wafer_ids = self._wafer_ids_for_lots(ds, lot_ids)
        cnames = self._chamber_names_for_wafers(ds, wafer_ids)
        assert cnames & {"LIT-01-A", "LIT-01-B"}, \
            f"S-OVL lots should use LIT-01; got {cnames}"

    def test_part_lots_use_cvd03(self, ds):
        lot_ids = self._lot_ids_for_scenario(ds, "S-PART")
        wafer_ids = self._wafer_ids_for_lots(ds, lot_ids)
        cnames = self._chamber_names_for_wafers(ds, wafer_ids)
        assert cnames & {"CVD-03-A", "CVD-03-B"}, \
            f"S-PART lots should use CVD-03; got {cnames}"

    def test_cham_lots_use_cmp02(self, ds):
        lot_ids = self._lot_ids_for_scenario(ds, "S-CHAM")
        wafer_ids = self._wafer_ids_for_lots(ds, lot_ids)
        cnames = self._chamber_names_for_wafers(ds, wafer_ids)
        assert cnames & {"CMP-02-A", "CMP-02-B"}, \
            f"S-CHAM lots should use CMP-02; got {cnames}"


# ---------------------------------------------------------------------------
# 4. Particle scenario has higher defect density
# ---------------------------------------------------------------------------

class TestDefectDensity:
    def _mean_defects_per_wafer(self, ds: FabDataset, scenario_id: str) -> float:
        gt = ds.lot_ground_truth
        lot_ids = gt.loc[gt["scenario_id"] == scenario_id, "lot_id"].tolist()
        wafer_ids = ds.wafers.loc[ds.wafers["lot_id"].isin(lot_ids), "wafer_id"]
        n_defects = ds.defects.loc[ds.defects["wafer_id"].isin(wafer_ids)].shape[0]
        n_wafers = len(wafer_ids)
        return n_defects / max(n_wafers, 1)

    def test_particle_defects_above_threshold(self, ds):
        mean_part = self._mean_defects_per_wafer(ds, "S-PART")
        assert mean_part >= 50, \
            f"S-PART mean defects/wafer {mean_part:.1f} should be >= 50"

    def test_particle_higher_than_control(self, ds):
        mean_part = self._mean_defects_per_wafer(ds, "S-PART")
        mean_ctrl = self._mean_defects_per_wafer(ds, "S-CTRL")
        assert mean_part > mean_ctrl * 4, \
            f"S-PART ({mean_part:.1f}) should be > 4× S-CTRL ({mean_ctrl:.1f})"

    def test_control_defects_in_baseline_range(self, ds):
        mean_ctrl = self._mean_defects_per_wafer(ds, "S-CTRL")
        assert 5 <= mean_ctrl <= 20, \
            f"S-CTRL mean defects/wafer {mean_ctrl:.1f} outside [5, 20]"


# ---------------------------------------------------------------------------
# 5. Scenario yield degradation
# ---------------------------------------------------------------------------

class TestYieldDegradation:
    def _mean_yield(self, ds: FabDataset, scenario_id: str) -> float:
        gt = ds.lot_ground_truth
        lot_ids = gt.loc[gt["scenario_id"] == scenario_id, "lot_id"].tolist()
        wafer_ids = ds.wafers.loc[ds.wafers["lot_id"].isin(lot_ids), "wafer_id"]
        yields = ds.yield_results.loc[ds.yield_results["wafer_id"].isin(wafer_ids), "die_yield"]
        return float(yields.mean()) if len(yields) > 0 else float("nan")

    def test_ctrl_yield_healthy(self, ds):
        mean_ctrl = self._mean_yield(ds, "S-CTRL")
        assert mean_ctrl >= 0.88, f"S-CTRL mean yield {mean_ctrl:.4f} too low"

    def test_etch_yield_below_ctrl(self, ds):
        mean_etch = self._mean_yield(ds, "S-ETCH")
        mean_ctrl = self._mean_yield(ds, "S-CTRL")
        assert mean_etch < mean_ctrl, \
            f"S-ETCH yield {mean_etch:.4f} should be < S-CTRL {mean_ctrl:.4f}"

    def test_ovl_yield_below_ctrl(self, ds):
        mean_ovl = self._mean_yield(ds, "S-OVL")
        mean_ctrl = self._mean_yield(ds, "S-CTRL")
        assert mean_ovl < mean_ctrl, \
            f"S-OVL yield {mean_ovl:.4f} should be < S-CTRL {mean_ctrl:.4f}"

    def test_part_yield_substantially_below_ctrl(self, ds):
        mean_part = self._mean_yield(ds, "S-PART")
        mean_ctrl = self._mean_yield(ds, "S-CTRL")
        assert mean_part < mean_ctrl - 0.08, \
            f"S-PART yield {mean_part:.4f} should be >8pp below S-CTRL {mean_ctrl:.4f}"

    def test_maint_yield_below_ctrl(self, ds):
        mean_maint = self._mean_yield(ds, "S-MAINT")
        mean_ctrl = self._mean_yield(ds, "S-CTRL")
        assert mean_maint < mean_ctrl, \
            f"S-MAINT yield {mean_maint:.4f} should be < S-CTRL {mean_ctrl:.4f}"

    def test_cham_yield_below_ctrl(self, ds):
        mean_cham = self._mean_yield(ds, "S-CHAM")
        mean_ctrl = self._mean_yield(ds, "S-CTRL")
        assert mean_cham < mean_ctrl, \
            f"S-CHAM yield {mean_cham:.4f} should be < S-CTRL {mean_ctrl:.4f}"

    def test_time_yield_below_ctrl(self, ds):
        mean_time = self._mean_yield(ds, "S-TIME")
        mean_ctrl = self._mean_yield(ds, "S-CTRL")
        assert mean_time < mean_ctrl, \
            f"S-TIME yield {mean_time:.4f} should be < S-CTRL {mean_ctrl:.4f}"


# ---------------------------------------------------------------------------
# 6. Defect coordinates within wafer radius
# ---------------------------------------------------------------------------

class TestDefectCoordinates:
    def test_all_coords_within_radius(self, ds):
        df = ds.defects
        r = np.sqrt(df["x_coord"] ** 2 + df["y_coord"] ** 2)
        outside = (r > WAFER_RADIUS_MM).sum()
        assert outside == 0, \
            f"{outside} defects outside wafer radius ({WAFER_RADIUS_MM} mm)"

    def test_particle_defects_center_heavy(self, ds):
        """S-PART defects should be predominantly in r < 50 mm."""
        gt = ds.lot_ground_truth
        lot_ids = gt.loc[gt["scenario_id"] == "S-PART", "lot_id"].tolist()
        wafer_ids = ds.wafers.loc[ds.wafers["lot_id"].isin(lot_ids), "wafer_id"]
        part_defects = ds.defects.loc[ds.defects["wafer_id"].isin(wafer_ids)]
        r = np.sqrt(part_defects["x_coord"] ** 2 + part_defects["y_coord"] ** 2)
        center_fraction = (r < 50).sum() / max(len(r), 1)
        assert center_fraction > 0.3, \
            f"S-PART center fraction {center_fraction:.2f} too low (expected > 0.3)"

    def test_etch_defects_edge_heavy(self, ds):
        """S-ETCH defects should be predominantly in the edge ring (r > 100 mm)."""
        gt = ds.lot_ground_truth
        lot_ids = gt.loc[gt["scenario_id"] == "S-ETCH", "lot_id"].tolist()
        wafer_ids = ds.wafers.loc[ds.wafers["lot_id"].isin(lot_ids), "wafer_id"]
        etch_defects = ds.defects.loc[ds.defects["wafer_id"].isin(wafer_ids)]
        r = np.sqrt(etch_defects["x_coord"] ** 2 + etch_defects["y_coord"] ** 2)
        edge_fraction = (r > 100).sum() / max(len(r), 1)
        assert edge_fraction > 0.5, \
            f"S-ETCH edge fraction {edge_fraction:.2f} too low (expected > 0.5)"


# ---------------------------------------------------------------------------
# 7. Timestamp ordering
# ---------------------------------------------------------------------------

class TestTimestampOrdering:
    def test_lot_planned_before_actual(self, ds):
        bad = (ds.lots["planned_start_at"] > ds.lots["actual_start_at"]).sum()
        assert bad == 0, f"{bad} lots have planned_start_at > actual_start_at"

    def test_run_start_after_lot_start(self, ds):
        """Every run's start_time should be >= its wafer's lot's actual_start_at."""
        wafer_lot = ds.wafers[["wafer_id", "lot_id"]]
        lot_start = ds.lots[["lot_id", "actual_start_at"]]
        merged = ds.runs.merge(wafer_lot, on="wafer_id").merge(lot_start, on="lot_id")
        bad = (merged["start_time"] < merged["actual_start_at"]).sum()
        assert bad == 0, f"{bad} runs start before their lot's actual_start_at"

    def test_yield_tested_after_run_end(self, ds):
        """Yield tested_at should be >= run end_time for same wafer."""
        run_end = ds.runs[["wafer_id", "end_time"]]
        merged = ds.yield_results.merge(run_end, on="wafer_id")
        bad = (merged["tested_at"] < merged["end_time"]).sum()
        assert bad == 0, f"{bad} yield records tested before run ended"

    def test_metrology_after_run_start(self, ds):
        """Metrology measured_at should be >= run start_time for same wafer."""
        run_start = ds.runs[["wafer_id", "start_time"]]
        merged = ds.metrology.merge(run_start, on="wafer_id")
        bad = (merged["measured_at"] < merged["start_time"]).sum()
        assert bad == 0, f"{bad} metrology records measured before run started"

    def test_maint_unscheduled_before_affected_lots(self, ds):
        """S-MAINT unscheduled PM at day 120 must precede the S-MAINT lot window."""
        from data.synthetic.scenarios import SCENARIOS
        from datetime import timedelta, timezone

        pm_day = SCENARIOS["S-MAINT"].pm_day_offset
        history_start = ds.maintenance_events["performed_at"].min()

        # Find unscheduled PM events on ETH-02 chambers
        eth02_chamber_ids = ds.chambers.loc[
            ds.chambers["name"].isin(["ETH-02-A", "ETH-02-B"]), "chamber_id"
        ].tolist()
        unscheduled = ds.maintenance_events.loc[
            (ds.maintenance_events["event_type"] == "unscheduled_pm")
            & (ds.maintenance_events["chamber_id"].isin(eth02_chamber_ids))
        ]
        assert len(unscheduled) > 0, "No unscheduled PM found on ETH-02"

        # Find the earliest S-MAINT lot start
        maint_lot_ids = ds.lot_ground_truth.loc[
            ds.lot_ground_truth["scenario_id"] == "S-MAINT", "lot_id"
        ].tolist()
        maint_lot_starts = ds.lots.loc[
            ds.lots["lot_id"].isin(maint_lot_ids), "actual_start_at"
        ]
        earliest_maint_lot = maint_lot_starts.min()

        # At least one unscheduled PM must precede the earliest S-MAINT lot
        pm_before_lot = unscheduled.loc[unscheduled["performed_at"] < earliest_maint_lot]
        assert len(pm_before_lot) > 0, (
            f"No unscheduled PM precedes earliest S-MAINT lot ({earliest_maint_lot}). "
            f"PM times: {unscheduled['performed_at'].tolist()}"
        )


# ---------------------------------------------------------------------------
# 8. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_lot_ids_identical(self, ds, ds2):
        pd.testing.assert_frame_equal(
            ds.lots[["lot_id_str", "product"]].reset_index(drop=True),
            ds2.lots[["lot_id_str", "product"]].reset_index(drop=True),
        )

    def test_yield_identical(self, ds, ds2):
        pd.testing.assert_series_equal(
            ds.yield_results["die_yield"].reset_index(drop=True),
            ds2.yield_results["die_yield"].reset_index(drop=True),
        )

    def test_defect_count_identical(self, ds, ds2):
        assert len(ds.defects) == len(ds2.defects), \
            f"Defect counts differ between runs: {len(ds.defects)} vs {len(ds2.defects)}"


# ---------------------------------------------------------------------------
# 9. Pre-run data separation (leakage prevention)
# ---------------------------------------------------------------------------

class TestPreRunSeparation:
    def test_whitelist_contains_no_future_columns(self):
        """No column in the pre-run whitelist should appear in the forbidden list."""
        overlap = set(PRE_RUN_FEATURE_WHITELIST) & set(PRE_RUN_FORBIDDEN_COLUMNS)
        assert not overlap, f"Leakage: these columns are in both lists: {overlap}"

    def test_forbidden_columns_not_in_lots_pre_run_data(self, ds):
        """
        Columns available before lot.actual_start_at (the pre-run gate) must not
        include yield, defect, or metrology measurement outcomes.
        """
        # Columns available at lot creation time (before actual_start_at)
        pre_run_lot_cols = {"lot_id_str", "product", "technology_node", "priority",
                            "status", "planned_start_at", "actual_start_at", "queue_time_h"}
        forbidden_in_pre_run = set(PRE_RUN_FORBIDDEN_COLUMNS) & pre_run_lot_cols
        assert not forbidden_in_pre_run, \
            f"Forbidden future columns found in pre-run lot data: {forbidden_in_pre_run}"

    def test_yield_not_available_before_run_ends(self, ds):
        """
        For every wafer, yield tested_at must be strictly after run end_time.
        This is the temporal guarantee that yield can never be a pre-run feature.
        """
        run_ends = ds.runs[["wafer_id", "end_time"]]
        merged = ds.yield_results.merge(run_ends, on="wafer_id")
        pre_yield = (merged["tested_at"] <= merged["end_time"]).sum()
        assert pre_yield == 0, \
            f"{pre_yield} yield records have tested_at <= run end_time"

    def test_ground_truth_not_in_orm_columns(self, ds):
        """
        The 'scenario_id' and 'expected_root_cause' ground-truth columns must NOT
        appear in any production ORM table DataFrame.

        These columns are only allowed in lot_ground_truth, which is never inserted
        into the database.
        """
        production_dfs = {
            "lots": ds.lots,
            "wafers": ds.wafers,
            "runs": ds.runs,
            "process_parameters": ds.process_parameters,
            "metrology": ds.metrology,
            "yield_results": ds.yield_results,
        }
        gt_cols = {"scenario_id", "expected_root_cause"}
        for table_name, df in production_dfs.items():
            leaked = gt_cols & set(df.columns)
            assert not leaked, \
                f"Ground-truth columns {leaked} found in production table '{table_name}'"


# ---------------------------------------------------------------------------
# 10. Overlay metrology sigma inflation (S-OVL)
# ---------------------------------------------------------------------------

class TestMetrologySignal:
    def test_ovl_overlay_sigma_inflated(self, ds):
        """S-OVL lots should have larger overlay_x std than S-CTRL."""
        gt = ds.lot_ground_truth

        def overlay_std(scenario_id: str) -> float:
            lot_ids = gt.loc[gt["scenario_id"] == scenario_id, "lot_id"].tolist()
            wafer_ids = ds.wafers.loc[ds.wafers["lot_id"].isin(lot_ids), "wafer_id"]
            vals = ds.metrology.loc[
                (ds.metrology["wafer_id"].isin(wafer_ids))
                & (ds.metrology["measurement_type"] == "overlay_x"),
                "value"
            ]
            return float(vals.std()) if len(vals) > 1 else 0.0

        std_ovl = overlay_std("S-OVL")
        std_ctrl = overlay_std("S-CTRL")
        assert std_ovl > std_ctrl * 2, \
            f"S-OVL overlay_x std {std_ovl:.3f} not > 2× S-CTRL {std_ctrl:.3f}"


# ---------------------------------------------------------------------------
# 11. Etch rate drift (S-ETCH)
# ---------------------------------------------------------------------------

class TestEtchDrift:
    def test_etch_rate_elevated_in_s_etch_lots(self, ds):
        """S-ETCH lots should have higher mean etch_rate than S-CTRL."""
        gt = ds.lot_ground_truth

        def mean_etch_rate(scenario_id: str) -> float:
            lot_ids = gt.loc[gt["scenario_id"] == scenario_id, "lot_id"].tolist()
            wafer_ids = ds.wafers.loc[ds.wafers["lot_id"].isin(lot_ids), "wafer_id"]
            run_ids = ds.runs.loc[ds.runs["wafer_id"].isin(wafer_ids), "run_id"]
            vals = ds.process_parameters.loc[
                (ds.process_parameters["run_id"].isin(run_ids))
                & (ds.process_parameters["param_name"] == "etch_rate"),
                "value"
            ]
            return float(vals.mean()) if len(vals) > 0 else 0.0

        mean_etch = mean_etch_rate("S-ETCH")
        mean_ctrl = mean_etch_rate("S-CTRL")
        assert mean_etch > mean_ctrl, \
            f"S-ETCH mean etch_rate {mean_etch:.2f} should be > S-CTRL {mean_ctrl:.2f}"
