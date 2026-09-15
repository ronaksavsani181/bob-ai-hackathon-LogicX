"""
tests/test_analytics.py — Analytics service tests.

Covers: anomaly, defect_pattern, similar_lot, recurrence, temporal,
        root_cause, pre_run_risk.

All tests use the in-memory synthetic dataset (generate_all(seed=42)).
No DB connection required.

Schema reference (from generator.py):
  lots         : lot_id, lot_id_str, product, technology_node, priority,
                 status, planned_start_at, actual_start_at, queue_time_h
  wafers       : wafer_id, lot_id, wafer_slot, die_count_total
  runs         : run_id, wafer_id, chamber_id, recipe_id, start_time, end_time
  yield_results: yield_id, wafer_id, die_yield, bin1_count, bin_fail_count, tested_at
  defects      : defect_id, wafer_id, x_coord, y_coord, defect_class, ...
  chambers     : chamber_id, tool_id, name (chamber name), chamber_index
  tools        : tool_id, name (tool name), tool_type, fab_area
  maintenance_events: maint_id, chamber_id, event_type, performed_at, ...

NOTE: lots does NOT have a scenario_id column in the DB-facing DataFrames.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from data.synthetic.generator import generate_all, FabDataset


@pytest.fixture(scope="module")
def fab() -> FabDataset:
    return generate_all(seed=42)


def _lot_yield_series(fab: FabDataset) -> pd.DataFrame:
    """Return DataFrame [lot_id, lot_id_str, actual_start_at, die_yield]."""
    yield_with_lot = fab.yield_results.merge(
        fab.wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )
    lot_yield = (
        yield_with_lot.groupby("lot_id")["die_yield"]
        .mean()
        .reset_index()
        .rename(columns={"die_yield": "die_yield"})
    )
    merged = fab.lots.merge(lot_yield, on="lot_id", how="left").sort_values("actual_start_at")
    return merged


# ===========================================================================
# 1. Anomaly detection
# ===========================================================================
from app.services.anomaly import (
    detect_yield_excursion,
    detect_yield_excursions_bulk,
    MIN_HISTORY_LOTS,
)
from app.services.evidence import YieldExcursionResult


class TestYieldExcursion:
    def test_returns_result_object(self, fab: FabDataset):
        """detect_yield_excursion returns a YieldExcursionResult."""
        merged = _lot_yield_series(fab)
        row = merged.iloc[50]
        hist = merged.iloc[:50][["lot_id_str", "actual_start_at", "die_yield"]].copy()
        result = detect_yield_excursion(
            str(row["lot_id_str"]),
            float(row["die_yield"]),
            row["actual_start_at"],
            hist,
        )
        assert isinstance(result, YieldExcursionResult)

    def test_insufficient_history_returns_no_excursion(self, fab: FabDataset):
        """Fewer than MIN_HISTORY_LOTS history → no excursion flagged."""
        merged = _lot_yield_series(fab)
        row = merged.iloc[3]
        hist = pd.DataFrame(columns=["lot_id_str", "actual_start_at", "die_yield"])
        result = detect_yield_excursion(
            str(row["lot_id_str"]),
            float(row["die_yield"]),
            row["actual_start_at"],
            hist,
        )
        assert not result.is_excursion
        assert result.method == "insufficient_history"

    def test_evidence_id_format(self, fab: FabDataset):
        """Evidence IDs must follow EVD-XXXXXXXX format (12 chars total)."""
        merged = _lot_yield_series(fab)
        row = merged.iloc[50]
        hist = merged.iloc[:50][["lot_id_str", "actual_start_at", "die_yield"]].copy()
        result = detect_yield_excursion(
            str(row["lot_id_str"]),
            float(row["die_yield"]),
            row["actual_start_at"],
            hist,
        )
        assert result.evidence_id.startswith("EVD-")
        assert len(result.evidence_id) == 12

    def test_algorithm_version_set(self, fab: FabDataset):
        """Algorithm version must be populated."""
        merged = _lot_yield_series(fab)
        row = merged.iloc[50]
        hist = merged.iloc[:50][["lot_id_str", "actual_start_at", "die_yield"]].copy()
        result = detect_yield_excursion(
            str(row["lot_id_str"]),
            float(row["die_yield"]),
            row["actual_start_at"],
            hist,
        )
        assert result.algorithm_version == "yield_excursion_v1"

    def test_bulk_excursion_returns_list(self, fab: FabDataset):
        """Bulk detection returns one result per lot with valid yield."""
        results = detect_yield_excursions_bulk(
            fab.lots, fab.yield_results, fab.wafers
        )
        assert len(results) > 0
        assert all(isinstance(r, YieldExcursionResult) for r in results)

    def test_bulk_detects_some_excursions(self, fab: FabDataset):
        """Bulk detection must find at least some excursions (scenarios inject yield drops)."""
        results = detect_yield_excursions_bulk(
            fab.lots, fab.yield_results, fab.wafers
        )
        excursion_count = sum(1 for r in results if r.is_excursion)
        assert excursion_count > 5, (
            f"Expected >5 excursions across 500 lots with injected scenarios, "
            f"got {excursion_count}"
        )

    def test_severity_classification(self):
        """Severity classification logic is consistent."""
        from app.services.anomaly import _classify_yield_severity
        assert _classify_yield_severity(-2.0) == "none"
        assert _classify_yield_severity(-2.6) == "mild"
        assert _classify_yield_severity(-3.5) == "moderate"
        assert _classify_yield_severity(-4.5) == "severe"


# ===========================================================================
# 2. Defect pattern classification
# ===========================================================================
from app.services.defect_pattern import classify_defect_pattern, classify_lot_defect_patterns
from app.services.evidence import DefectPatternResult


class TestDefectPattern:
    def test_center_heavy_detected(self):
        """Dense center cluster → center_heavy."""
        rng = np.random.default_rng(0)
        r = rng.uniform(0, 35, 40)
        theta = rng.uniform(0, 2 * np.pi, 40)
        coords = list(zip((r * np.cos(theta)).tolist(), (r * np.sin(theta)).tolist()))
        result = classify_defect_pattern(wafer_id=1, defect_coords=coords)
        assert result.pattern_type == "center_heavy", (
            f"Expected center_heavy, got {result.pattern_type}, "
            f"stats={result.spatial_statistics}"
        )

    def test_edge_ring_detected(self):
        """Dense edge band → edge_ring."""
        rng = np.random.default_rng(1)
        r = rng.uniform(122, 148, 50)
        theta = rng.uniform(0, 2 * np.pi, 50)
        coords = list(zip((r * np.cos(theta)).tolist(), (r * np.sin(theta)).tolist()))
        result = classify_defect_pattern(wafer_id=2, defect_coords=coords)
        assert result.pattern_type == "edge_ring", (
            f"Expected edge_ring, got {result.pattern_type}, "
            f"stats={result.spatial_statistics}"
        )

    def test_scratch_line_detected(self):
        """Linear streak → scratch_line."""
        rng = np.random.default_rng(2)
        xs = rng.uniform(-120, 120, 60).tolist()
        ys = rng.normal(0, 2, 60).tolist()
        result = classify_defect_pattern(wafer_id=3, defect_coords=list(zip(xs, ys)))
        assert result.pattern_type == "scratch_line", (
            f"Expected scratch_line, got {result.pattern_type}, "
            f"stats={result.spatial_statistics}"
        )

    def test_insufficient_data(self):
        """< MIN_DEFECTS → insufficient_data with score 0."""
        result = classify_defect_pattern(wafer_id=4, defect_coords=[(10, 10), (20, 20)])
        assert result.pattern_type == "insufficient_data"
        assert result.pattern_score == 0.0

    def test_result_fields_populated(self):
        """All required fields must be present on the result."""
        rng = np.random.default_rng(5)
        r = rng.uniform(0, 140, 20)
        theta = rng.uniform(0, 2 * np.pi, 20)
        coords = list(zip((r * np.cos(theta)).tolist(), (r * np.sin(theta)).tolist()))
        result = classify_defect_pattern(wafer_id=99, defect_coords=coords)
        assert result.wafer_id == 99
        assert result.evidence_id.startswith("EVD-")
        assert result.algorithm_version == "defect_pattern_v1"
        assert isinstance(result.spatial_statistics, dict)
        assert 0.0 <= result.pattern_score <= 1.0

    def test_lot_batch_classification(self, fab: FabDataset):
        """classify_lot_defect_patterns returns one result per sampled wafer."""
        wafer_ids = fab.wafers["wafer_id"].tolist()[:10]
        results = classify_lot_defect_patterns(wafer_ids, fab.defects, sample_wafers=5)
        assert len(results) == 5
        assert all(isinstance(r, DefectPatternResult) for r in results)


# ===========================================================================
# 3. Similar lot finder
# ===========================================================================
from app.services.similar_lot import find_similar_lots, MIN_SIMILARITY, MIN_HISTORY_LOTS as SIM_MIN_HIST
from app.services.evidence import SimilarLotResult


def _make_sim_feature_df(fab: FabDataset) -> pd.DataFrame:
    """Build feature DataFrame matching PRE_RUN_FEATURE_WHITELIST."""
    lots = fab.lots.copy()
    yields_with_lot = fab.yield_results.merge(
        fab.wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
    )
    lot_yield = yields_with_lot.groupby("lot_id")["die_yield"].mean().reset_index()

    lots["product_encoded"] = lots["product"].astype("category").cat.codes.astype(float)
    lots["technology_node_encoded"] = lots["technology_node"].astype("category").cat.codes.astype(float)
    lots["lot_priority"] = lots["priority"].map({"low": 0.0, "normal": 1.0, "high": 2.0}).fillna(1.0)
    lots["planned_recipe_encoded"] = 0.0
    lots["planned_chamber_encoded"] = 0.0
    lots["chamber_yield_30d"] = 0.94
    lots["days_since_last_pm"] = 30.0
    lots["chamber_ooc_rate_30d"] = 0.02
    lots["queue_time_planned_h"] = lots["queue_time_h"].fillna(24.0)
    lots["chamber_name"] = "ETH-01-A"
    lots["tool_name"] = "ETH-01"
    lots["recipe_name"] = "RCP-A"
    return lots.merge(lot_yield, on="lot_id", how="left")


class TestSimilarLot:
    def test_returns_list_of_similar_lots(self, fab: FabDataset):
        """Returns a list of SimilarLotResult objects."""
        df = _make_sim_feature_df(fab)
        target = df.iloc[200]
        target_id = str(target["lot_id_str"])
        history = df[df["lot_id_str"] != target_id].copy()
        features = {
            "lot_priority": float(target.get("lot_priority", 1.0)),
            "product_encoded": float(target["product_encoded"]),
            "technology_node_encoded": float(target["technology_node_encoded"]),
            "planned_recipe_encoded": float(target["planned_recipe_encoded"]),
            "planned_chamber_encoded": float(target["planned_chamber_encoded"]),
            "chamber_yield_30d": float(target["chamber_yield_30d"]),
            "days_since_last_pm": float(target["days_since_last_pm"]),
            "chamber_ooc_rate_30d": float(target["chamber_ooc_rate_30d"]),
            "queue_time_planned_h": float(target["queue_time_planned_h"]),
        }
        results = find_similar_lots(target_id, features, history)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, SimilarLotResult)
            assert r.similarity_score >= MIN_SIMILARITY

    def test_target_not_in_results(self, fab: FabDataset):
        """Target lot must not appear in its own similar-lot list."""
        df = _make_sim_feature_df(fab)
        target = df.iloc[100]
        target_id = str(target["lot_id_str"])
        features = {f: 0.5 for f in [
            "lot_priority", "product_encoded", "technology_node_encoded",
            "planned_recipe_encoded", "planned_chamber_encoded",
            "chamber_yield_30d", "days_since_last_pm",
            "chamber_ooc_rate_30d", "queue_time_planned_h",
        ]}
        results = find_similar_lots(target_id, features, df)
        assert target_id not in [r.similar_lot_id for r in results]

    def test_empty_on_tiny_history(self):
        """With < MIN_HISTORY_LOTS historical lots → empty result."""
        df = pd.DataFrame({
            "lot_id_str": [f"L{i:04d}" for i in range(5)],
            "die_yield": [0.92] * 5,
            "chamber_name": ["ETH-01-A"] * 5,
            "tool_name": ["ETH-01"] * 5,
            "recipe_name": ["RCP-A"] * 5,
            "lot_priority": [1.0] * 5,
            "product_encoded": [0.0] * 5,
            "technology_node_encoded": [0.0] * 5,
            "planned_recipe_encoded": [0.0] * 5,
            "planned_chamber_encoded": [0.0] * 5,
            "chamber_yield_30d": [0.94] * 5,
            "days_since_last_pm": [30.0] * 5,
            "chamber_ooc_rate_30d": [0.02] * 5,
            "queue_time_planned_h": [24.0] * 5,
        })
        features = {f: 0.5 for f in [
            "lot_priority", "product_encoded", "technology_node_encoded",
            "planned_recipe_encoded", "planned_chamber_encoded",
            "chamber_yield_30d", "days_since_last_pm",
            "chamber_ooc_rate_30d", "queue_time_planned_h",
        ]}
        results = find_similar_lots("LOT-X", features, df)
        assert results == []


# ===========================================================================
# 4. Chamber recurrence
# ===========================================================================
from app.services.recurrence import analyze_chamber_recurrence
from app.services.evidence import ChamberRecurrenceResult


class TestChamberRecurrence:
    def _build_chambers_df(self, fab: FabDataset) -> pd.DataFrame:
        """Join chambers with tools to add tool_name and chamber_name."""
        chambers = fab.chambers.copy().rename(columns={"name": "chamber_name"})
        tools = fab.tools.copy().rename(columns={"name": "tool_name"})
        return chambers.merge(tools[["tool_id", "tool_name"]], on="tool_id", how="left")

    def _build_yield_with_lot(self, fab: FabDataset) -> pd.DataFrame:
        """Add lot_id to yield_results via wafers."""
        return fab.yield_results.merge(
            fab.wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
        )

    def test_returns_results_for_all_chambers(self, fab: FabDataset):
        """Should return a result for every chamber with sufficient lots."""
        chambers_df = self._build_chambers_df(fab)
        yield_df = self._build_yield_with_lot(fab)
        results = analyze_chamber_recurrence(fab.lots, yield_df, fab.runs, chambers_df)
        assert len(results) > 0
        assert all(isinstance(r, ChamberRecurrenceResult) for r in results)

    def test_scores_in_tanh_range(self, fab: FabDataset):
        """Recurrence scores are in [-1, 1]."""
        chambers_df = self._build_chambers_df(fab)
        yield_df = self._build_yield_with_lot(fab)
        results = analyze_chamber_recurrence(fab.lots, yield_df, fab.runs, chambers_df)
        for r in results:
            assert -1.0 <= r.recurrence_score <= 1.0

    def test_results_sorted_descending(self, fab: FabDataset):
        """Results sorted by recurrence_score descending."""
        chambers_df = self._build_chambers_df(fab)
        yield_df = self._build_yield_with_lot(fab)
        results = analyze_chamber_recurrence(fab.lots, yield_df, fab.runs, chambers_df)
        scores = [r.recurrence_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_algorithm_version(self, fab: FabDataset):
        """Algorithm version set on every result."""
        chambers_df = self._build_chambers_df(fab)
        yield_df = self._build_yield_with_lot(fab)
        results = analyze_chamber_recurrence(fab.lots, yield_df, fab.runs, chambers_df)
        for r in results:
            assert r.algorithm_version == "chamber_recurrence_v1"

    def test_some_recurrent_chamber_detected(self, fab: FabDataset):
        """S-CHAM injects a persistent 8% deficit → at least one chamber is flagged recurrent."""
        chambers_df = self._build_chambers_df(fab)
        yield_df = self._build_yield_with_lot(fab)
        results = analyze_chamber_recurrence(fab.lots, yield_df, fab.runs, chambers_df)
        recurrent = [r for r in results if r.is_recurrent]
        assert len(recurrent) > 0, (
            "Expected at least one recurrent chamber (S-CHAM injects 7-9% yield deficit)"
        )


# ===========================================================================
# 5. Temporal precedence & maintenance proximity
# ===========================================================================
from app.services.temporal import check_temporal_precedence, analyze_maintenance_proximity
from app.services.evidence import TemporalPrecedenceResult, MaintenanceProximityResult


class TestTemporalPrecedence:
    def test_valid_precedence(self):
        t1 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 1, 16, 0, tzinfo=timezone.utc)
        result = check_temporal_precedence("etch_rate_drift", t1, t2)
        assert result.precedence_valid is True
        assert result.time_delta_hours == pytest.approx(6.0)

    def test_invalid_precedence(self):
        t1 = datetime(2024, 1, 2, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = check_temporal_precedence("late_factor", t1, t2)
        assert result.precedence_valid is False
        assert result.time_delta_hours < 0

    def test_same_time_invalid(self):
        t = datetime(2024, 3, 15, 12, 0, tzinfo=timezone.utc)
        result = check_temporal_precedence("simultaneous", t, t)
        assert result.precedence_valid is False

    def test_evidence_id_populated(self):
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 2, tzinfo=timezone.utc)
        result = check_temporal_precedence("test_factor", t1, t2)
        assert result.evidence_id.startswith("EVD-")

    def test_algorithm_version(self):
        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 2, tzinfo=timezone.utc)
        result = check_temporal_precedence("f", t1, t2)
        assert result.algorithm_version == "temporal_precedence_v1"


class TestMaintenanceProximity:
    def test_runs_without_error(self, fab: FabDataset):
        """analyze_maintenance_proximity completes without exception."""
        # Rename columns to match service expectations
        maint = fab.maintenance_events.rename(columns={"performed_at": "event_at"})
        lots = fab.lots.copy()
        if "actual_end_at" not in lots.columns:
            lots["actual_end_at"] = lots["actual_start_at"] + pd.Timedelta(hours=8)
        yield_df = fab.yield_results.merge(
            fab.wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
        )
        chamber_id = int(maint["chamber_id"].iloc[0])
        cham_maint = maint[maint["chamber_id"] == chamber_id].copy()

        results = analyze_maintenance_proximity(
            chamber_id=chamber_id,
            chamber_name=f"CHAMBER-{chamber_id}",
            maintenance_events_df=cham_maint,
            lots_df=lots,
            yield_df=yield_df,
            runs_df=fab.runs,
        )
        assert isinstance(results, list)


# ===========================================================================
# 6. Root cause fusion
# ===========================================================================
from app.services.root_cause import rank_root_causes
from app.services.evidence import RootCauseFusionResult, RootCauseCandidate


def _make_ye(lot_id: str, sigma: float) -> YieldExcursionResult:
    return YieldExcursionResult(
        lot_id=lot_id,
        observed_yield=0.80,
        baseline_yield=0.93,
        deviation=-0.13,
        deviation_sigma=sigma,
        severity="severe",
        is_excursion=True,
        method="test",
        n_lots_used=50,
        evidence_id="EVD-TESTEID1",
        algorithm_version="yield_excursion_v1",
    )


def _make_pa(lot_id: str, param: str, z: float):
    from app.services.evidence import ParameterAnomalyResult
    return ParameterAnomalyResult(
        lot_id=lot_id, run_id=1, chamber_id=3, tool_id=2,
        param_name=param, observed_value=138.0,
        baseline_mean=120.0, baseline_std=3.0, z_score=z,
        direction="high", severity="severe", is_anomaly=True,
        evidence_id="EVD-TESTPAA1", algorithm_version="process_anomaly_v1",
    )


class TestRootCauseFusion:
    def test_etch_anomaly_ranks_etch_drift_first(self):
        """Strong etch parameter anomaly + yield excursion → etch_chamber_drift ranked #1."""
        result = rank_root_causes(
            lot_id="L0305",
            yield_excursion=_make_ye("L0305", -5.0),
            param_anomalies=[_make_pa("L0305", "etch_rate", 6.0)],
            chamber_recurrences=[], maintenance_proximity=[],
            similar_lots=[], defect_patterns=[],
            queue_time_h=24.0, affected_wafer_count=25,
        )
        assert not result.insufficient_evidence
        assert result.candidates[0].cause_id == "etch_chamber_drift"

    def test_insufficient_evidence_no_signals(self):
        """No signals → insufficient_evidence = True, empty candidates list."""
        result = rank_root_causes(
            lot_id="L0001",
            yield_excursion=None,
            param_anomalies=[], chamber_recurrences=[],
            maintenance_proximity=[], similar_lots=[], defect_patterns=[],
        )
        assert result.insufficient_evidence is True
        assert result.candidates == []

    def test_at_most_three_candidates(self):
        """Must never return more than 3 candidates."""
        result = rank_root_causes(
            lot_id="L0400",
            yield_excursion=_make_ye("L0400", -4.0),
            param_anomalies=[_make_pa("L0400", "etch_rate", 5.0)],
            chamber_recurrences=[], maintenance_proximity=[],
            similar_lots=[], defect_patterns=[],
        )
        assert len(result.candidates) <= 3

    def test_candidates_sorted_descending(self):
        """Candidates sorted by score descending."""
        result = rank_root_causes(
            lot_id="L0350",
            yield_excursion=_make_ye("L0350", -3.5),
            param_anomalies=[_make_pa("L0350", "etch_rate", 4.0)],
            chamber_recurrences=[], maintenance_proximity=[],
            similar_lots=[], defect_patterns=[],
        )
        scores = [c.score for c in result.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_candidate_fields_complete(self):
        """Every candidate has all required fields."""
        result = rank_root_causes(
            lot_id="L0305",
            yield_excursion=_make_ye("L0305", -5.0),
            param_anomalies=[_make_pa("L0305", "etch_rate", 6.0)],
            chamber_recurrences=[], maintenance_proximity=[],
            similar_lots=[], defect_patterns=[],
        )
        for c in result.candidates:
            assert c.rank >= 1
            assert c.cause_id != ""
            assert c.cause_description != ""
            assert c.model_version == "root_cause_fusion_v1"
            assert isinstance(c.evidence_ids, list)
            assert 0.0 <= c.score <= 1.0
            assert 0.0 <= c.confidence <= 1.0

    def test_no_llm_imports_in_root_cause_module(self):
        """root_cause.py must never import any LLM library."""
        import ast, inspect
        import app.services.root_cause as rc_mod
        source = inspect.getsource(rc_mod)
        llm_packages = {"openai", "anthropic", "langchain", "transformers", "llama"}
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in getattr(node, "names", [])]
                module = getattr(node, "module", "") or ""
                for name in names + [module]:
                    base = name.split(".")[0].lower()
                    assert base not in llm_packages, (
                        f"LLM library '{base}' found in root_cause.py — "
                        "root cause ranking must be deterministic."
                    )

    def test_result_carries_model_version_and_timestamp(self):
        """RootCauseFusionResult must carry model_version and generated_at."""
        result = rank_root_causes(
            lot_id="L0305",
            yield_excursion=_make_ye("L0305", -5.0),
            param_anomalies=[_make_pa("L0305", "etch_rate", 6.0)],
            chamber_recurrences=[], maintenance_proximity=[],
            similar_lots=[], defect_patterns=[],
        )
        assert result.model_version == "root_cause_fusion_v1"
        assert result.generated_at is not None


# ===========================================================================
# 7. Pre-run risk model
# ===========================================================================
from app.services.pre_run_risk import (
    audit_for_leakage,
    train_risk_model,
    score_pre_run_risk,
    score_pre_run_risk_bulk,
    PRE_RUN_FEATURE_WHITELIST,
    PRE_RUN_FORBIDDEN_COLUMNS,
    PreRunRiskResult,
)


def _build_pre_run_features(fab: FabDataset) -> pd.DataFrame:
    """Build pre-run feature DataFrame from synthetic data."""
    lots = fab.lots.copy()
    lots["product_encoded"] = lots["product"].astype("category").cat.codes.astype(float)
    lots["technology_node_encoded"] = lots["technology_node"].astype("category").cat.codes.astype(float)
    lots["lot_priority"] = lots["priority"].map({"low": 0.0, "normal": 1.0, "high": 2.0}).fillna(1.0)
    lots["planned_recipe_encoded"] = 0.0
    lots["planned_chamber_encoded"] = 0.0
    lots["chamber_yield_30d"] = 0.94
    lots["days_since_last_pm"] = 30.0
    lots["chamber_ooc_rate_30d"] = 0.02
    lots["queue_time_planned_h"] = lots["queue_time_h"].fillna(24.0)
    return lots


class TestPreRunLeakageAudit:
    def test_clean_df_passes(self):
        """Whitelist-only DataFrame passes leakage audit."""
        df = pd.DataFrame({col: [1.0, 2.0] for col in PRE_RUN_FEATURE_WHITELIST})
        assert audit_for_leakage(df, raise_on_forbidden=False) == []

    def test_forbidden_column_raises(self):
        """DataFrame with forbidden column must raise ValueError."""
        df = pd.DataFrame({"lot_priority": [1.0], "die_yield": [0.95]})
        with pytest.raises(ValueError, match="PRE-RUN LEAKAGE DETECTED"):
            audit_for_leakage(df, raise_on_forbidden=True)

    def test_every_forbidden_column_detected(self):
        """Every forbidden column must be individually flagged."""
        for col in PRE_RUN_FORBIDDEN_COLUMNS:
            df = pd.DataFrame({"lot_priority": [1.0], col: [0.0]})
            found = audit_for_leakage(df, raise_on_forbidden=False)
            assert col in found, f"Forbidden column '{col}' not detected"

    def test_no_whitelist_forbidden_overlap(self):
        """No column can be in both whitelist and forbidden list."""
        overlap = set(PRE_RUN_FEATURE_WHITELIST) & set(PRE_RUN_FORBIDDEN_COLUMNS)
        assert overlap == set()


class TestPreRunRiskModel:
    def test_trains_and_scores(self, fab: FabDataset):
        """Model trains and returns risk scores in [0, 1]."""
        feat_df = _build_pre_run_features(fab)
        yield_df = fab.yield_results.merge(
            fab.wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
        )
        clf = train_risk_model(feat_df, yield_df)
        row = feat_df.iloc[300]
        features = {f: float(row.get(f, 0.0)) for f in PRE_RUN_FEATURE_WHITELIST}
        result = score_pre_run_risk(clf, str(row["lot_id_str"]), features)
        assert isinstance(result, PreRunRiskResult)
        assert 0.0 <= result.risk_score <= 1.0
        assert result.risk_class in {"low", "medium", "high"}

    def test_bulk_scoring(self, fab: FabDataset):
        """Bulk scoring returns one result per row."""
        feat_df = _build_pre_run_features(fab)
        yield_df = fab.yield_results.merge(
            fab.wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
        )
        clf = train_risk_model(feat_df, yield_df)
        sample = feat_df.head(20).copy()
        results = score_pre_run_risk_bulk(clf, sample)
        assert len(results) == 20
        assert all(isinstance(r, PreRunRiskResult) for r in results)

    def test_forbidden_feature_raises_at_inference(self, fab: FabDataset):
        """Forbidden column in inference features raises ValueError."""
        feat_df = _build_pre_run_features(fab)
        yield_df = fab.yield_results.merge(
            fab.wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
        )
        clf = train_risk_model(feat_df, yield_df)
        features = {f: 0.5 for f in PRE_RUN_FEATURE_WHITELIST}
        features["die_yield"] = 0.95
        with pytest.raises(ValueError, match="PRE-RUN LEAKAGE at inference"):
            score_pre_run_risk(clf, "L0999", features)

    def test_evidence_id_on_result(self, fab: FabDataset):
        """PreRunRiskResult must have a valid evidence_id."""
        feat_df = _build_pre_run_features(fab)
        yield_df = fab.yield_results.merge(
            fab.wafers[["wafer_id", "lot_id"]], on="wafer_id", how="left"
        )
        clf = train_risk_model(feat_df, yield_df)
        row = feat_df.iloc[50]
        features = {f: float(row.get(f, 0.0)) for f in PRE_RUN_FEATURE_WHITELIST}
        result = score_pre_run_risk(clf, str(row["lot_id_str"]), features)
        assert result.evidence_id.startswith("EVD-")
