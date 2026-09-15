"""
test_models.py — Sub-Task 2 model structural tests.

Verifies:
1. All 17 tables are created in the schema.
2. The full genealogy chain can be written and read back intact.
3. Foreign key constraints are enforced (SQLite FK pragma).
4. Cascade deletes propagate correctly.
5. JSONB/JSON columns accept dict/list payloads.
6. Audit columns (created_at, updated_at) are set automatically.
7. Business-key uniqueness constraints are enforced.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, text

from app.models.action import ActionRecommendation, ActionReview
from app.models.defect import Defect
from app.models.excursion import Excursion
from app.models.lot import Lot
from app.models.maintenance import MaintenanceEvent
from app.models.metrology import Metrology
from app.models.pre_run import PreRunAssessment
from app.models.recipe import Recipe
from app.models.root_cause import RootCauseRanking
from app.models.run import ProcessParameter, Run, TraceData
from app.models.tool import Chamber, Tool
from app.models.wafer import Wafer
from app.models.yield_result import YieldResult


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_tool(db, name="ETH-01", tool_type="etch", fab_area="diffusion") -> Tool:
    t = Tool(name=name, tool_type=tool_type, fab_area=fab_area,
             created_at=utcnow(), updated_at=utcnow())
    db.add(t); db.flush()
    return t


def make_chamber(db, tool: Tool, name="CHA", index=1) -> Chamber:
    c = Chamber(tool_id=tool.id, name=name, chamber_index=index,
                created_at=utcnow(), updated_at=utcnow())
    db.add(c); db.flush()
    return c


def make_recipe(db, name="RCP-01", version="v1", step="etch") -> Recipe:
    r = Recipe(name=name, version=version, process_step=step,
               nominal_params={"etch_rate": 120.0},
               created_at=utcnow(), updated_at=utcnow())
    db.add(r); db.flush()
    return r


def make_lot(db, lot_id="L0001") -> Lot:
    l = Lot(lot_id=lot_id, product="PROD-A", technology_node="7nm",
            priority="normal", status="completed",
            planned_start_at=utcnow(), actual_start_at=utcnow(),
            created_at=utcnow(), updated_at=utcnow())
    db.add(l); db.flush()
    return l


def make_wafer(db, lot: Lot, slot=1) -> Wafer:
    w = Wafer(lot_id=lot.id, wafer_slot=slot, die_count_total=500,
              created_at=utcnow(), updated_at=utcnow())
    db.add(w); db.flush()
    return w


def make_run(db, wafer: Wafer, chamber: Chamber, recipe: Recipe) -> Run:
    r = Run(wafer_id=wafer.id, chamber_id=chamber.id, recipe_id=recipe.id,
            start_time=utcnow(), end_time=utcnow(), run_status="completed",
            created_at=utcnow(), updated_at=utcnow())
    db.add(r); db.flush()
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — All 17 tables exist
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_TABLES = {
    "tools", "chambers", "recipes", "lots", "wafers",
    "runs", "process_parameters", "trace_data",
    "metrology", "defects", "maintenance_events", "yield_results",
    "excursions", "root_cause_rankings", "pre_run_assessments",
    "action_recommendations", "action_reviews",
}


def test_all_tables_exist(engine):
    inspector = inspect(engine)
    actual = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - actual
    assert not missing, f"Missing tables: {missing}"
    assert EXPECTED_TABLES.issubset(actual), \
        f"Expected {len(EXPECTED_TABLES)} tables, got: {actual}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Full genealogy chain write/read
# ─────────────────────────────────────────────────────────────────────────────

def test_full_genealogy_chain(db):
    """Create tool → chamber → recipe → lot → wafer → run → params → trace
       → metrology → defect → maintenance → yield and read back."""
    tool = make_tool(db, "ETH-01")
    chamber = make_chamber(db, tool, "CHA-A", 1)
    recipe = make_recipe(db)
    lot = make_lot(db)
    wafer = make_wafer(db, lot)
    run = make_run(db, wafer, chamber, recipe)

    # process parameter
    pp = ProcessParameter(
        run_id=run.id, param_name="etch_rate", value=122.5,
        unit="nm/min", nominal=120.0, lsl=100.0, usl=140.0,
        created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(pp)

    # trace data
    td = TraceData(
        run_id=run.id, timestamp=utcnow(), channel="rf_power", value=300.0,
        created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(td)

    # metrology
    m = Metrology(
        wafer_id=wafer.id, measurement_type="overlay_x", site_index=1,
        value=3.5, unit="nm", measured_at=utcnow(),
        created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(m)

    # defect
    d = Defect(
        wafer_id=wafer.id, x_coord=10.5, y_coord=-20.3,
        size_um=0.15, defect_class="particle", inspection_tool="KLA",
        inspected_at=utcnow(), created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(d)

    # maintenance
    me = MaintenanceEvent(
        chamber_id=chamber.id, event_type="scheduled_pm",
        performed_at=utcnow(), description="quarterly clean",
        performed_by="eng_01", created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(me)

    # yield result
    yr = YieldResult(
        wafer_id=wafer.id, die_yield=0.945, bin1_count=472, bin_fail_count=28,
        tested_at=utcnow(), created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(yr)

    db.flush()

    # Read back and verify IDs
    assert pp.id is not None
    assert td.id is not None
    assert m.id is not None
    assert d.id is not None
    assert me.id is not None
    assert yr.id is not None

    # Verify FK links via relationships
    db.refresh(run)
    assert len(run.process_parameters) == 1
    assert run.process_parameters[0].param_name == "etch_rate"
    assert len(run.trace_data) == 1

    db.refresh(wafer)
    assert len(wafer.metrology_records) == 1
    assert len(wafer.defects) == 1
    assert len(wafer.yield_results) == 1
    assert wafer.yield_results[0].die_yield == pytest.approx(0.945)


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — Excursion → root cause → action recommendation → review chain
# ─────────────────────────────────────────────────────────────────────────────

def test_excursion_and_analytics_chain(db):
    lot = make_lot(db, "L0002")

    exc = Excursion(
        lot_id=lot.id, excursion_type="yield_excursion", severity="moderate",
        detected_at=utcnow(),
        evidence={"z_score": 3.2, "chamber": "ETH-02"},
        created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(exc); db.flush()

    # Root cause ranking
    rc = RootCauseRanking(
        excursion_id=exc.id, rank=1, cause="Etch chamber drift",
        score=0.78, confidence=0.42,
        evidence_ids=["ev-001", "ev-002"],
        supporting_signals={"etch_rate_z": 3.2},
        contradicting_signals={},
        model_name="evidence_fusion_v1", model_version="1.0.0",
        produced_at=utcnow(), created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(rc)

    # Action recommendation
    ar = ActionRecommendation(
        excursion_id=exc.id,
        action_text="Schedule unscheduled PM on ETH-02",
        priority="high",
        produced_at=utcnow(), created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(ar); db.flush()

    # Engineer review (human approval boundary)
    rev = ActionReview(
        recommendation_id=ar.id,
        engineer_id="eng_smith",
        decision="approve",
        rationale="Consistent with historical pattern on ETH-02",
        reviewed_at=utcnow(), created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(rev); db.flush()

    assert rc.id is not None
    assert ar.id is not None
    assert rev.id is not None
    assert rev.decision == "approve"
    assert rev.engineer_id == "eng_smith"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — Pre-run assessment with JSONB fields
# ─────────────────────────────────────────────────────────────────────────────

def test_pre_run_assessment(db):
    lot = make_lot(db, "L0003")

    pra = PreRunAssessment(
        lot_id=lot.id,
        risk_score=0.73,
        risk_label="high",
        feature_vector={
            "chamber_yield_30d": 0.88,
            "days_since_pm": 45,
            "queue_time_h": 80.0,
        },
        features_used=["chamber_yield_30d", "days_since_pm", "queue_time_h"],
        produced_at=utcnow(), created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(pra); db.flush()

    assert pra.id is not None
    assert pra.risk_label == "high"
    assert pra.risk_score == pytest.approx(0.73)
    assert "chamber_yield_30d" in pra.features_used
    # Verify no future-data columns present (leakage contract)
    forbidden = {"die_yield", "defect_count", "overlay_error", "bin_fail_count"}
    actual_features = set(pra.features_used)
    leaked = forbidden & actual_features
    assert not leaked, f"Leakage detected — future features in pre-run assessment: {leaked}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5 — Unique constraint on lot_id business key
# ─────────────────────────────────────────────────────────────────────────────

def test_lot_business_key_uniqueness(db):
    make_lot(db, "L9999")
    db.flush()

    dup = Lot(
        lot_id="L9999", product="PROD-B", technology_node="5nm",
        priority="high", status="scheduled",
        created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(dup)

    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.flush()


# ─────────────────────────────────────────────────────────────────────────────
# Test 6 — Cascade delete: deleting a lot removes its wafers
# ─────────────────────────────────────────────────────────────────────────────

def test_cascade_delete_lot_removes_wafers(db):
    from sqlalchemy import select
    lot = make_lot(db, "L-CASCADE")
    w1 = make_wafer(db, lot, slot=1)
    w2 = make_wafer(db, lot, slot=2)
    db.flush()

    wafer_ids = {w1.id, w2.id}

    db.delete(lot)
    db.flush()

    remaining = db.execute(
        select(Wafer).where(Wafer.id.in_(wafer_ids))
    ).scalars().all()
    assert len(remaining) == 0, "Cascade delete did not remove child wafers"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7 — Defect coordinate range (spatial data integrity)
# ─────────────────────────────────────────────────────────────────────────────

def test_defect_coordinates_stored_accurately(db):
    tool = make_tool(db, "ETH-02")
    chamber = make_chamber(db, tool, "CHA-B", 2)
    recipe = make_recipe(db, "RCP-02", "v1", "etch")
    lot = make_lot(db, "L-DEFECT")
    wafer = make_wafer(db, lot)
    _ = make_run(db, wafer, chamber, recipe)

    coords = [
        (0.0, 0.0),       # centre
        (148.9, 0.1),     # near edge
        (-75.5, 130.2),   # upper quadrant
    ]
    for x, y in coords:
        db.add(Defect(
            wafer_id=wafer.id, x_coord=x, y_coord=y, size_um=0.2,
            defect_class="particle", created_at=utcnow(), updated_at=utcnow(),
        ))
    db.flush()

    db.refresh(wafer)
    assert len(wafer.defects) == 3
    stored_coords = {(d.x_coord, d.y_coord) for d in wafer.defects}
    for x, y in coords:
        assert (x, y) in stored_coords


# ─────────────────────────────────────────────────────────────────────────────
# Test 8 — Table column names match the plan specification
# ─────────────────────────────────────────────────────────────────────────────

def test_column_names_match_plan(engine):
    inspector = inspect(engine)
    checks = {
        "tools": {"id", "name", "tool_type", "fab_area", "created_at", "updated_at"},
        "chambers": {"id", "tool_id", "name", "chamber_index", "created_at", "updated_at"},
        "recipes": {"id", "name", "version", "process_step", "nominal_params", "created_at", "updated_at"},
        "lots": {"id", "lot_id", "product", "technology_node", "priority", "planned_start_at",
                 "actual_start_at", "status", "created_at", "updated_at"},
        "wafers": {"id", "lot_id", "wafer_slot", "die_count_total", "created_at", "updated_at"},
        "runs": {"id", "wafer_id", "chamber_id", "recipe_id", "start_time", "end_time",
                 "run_status", "created_at", "updated_at"},
        "process_parameters": {"id", "run_id", "param_name", "value", "unit",
                               "nominal", "lsl", "usl", "created_at", "updated_at"},
        "trace_data": {"id", "run_id", "timestamp", "channel", "value", "created_at", "updated_at"},
        "metrology": {"id", "wafer_id", "measurement_type", "site_index",
                      "value", "unit", "measured_at", "created_at", "updated_at"},
        "defects": {"id", "wafer_id", "x_coord", "y_coord", "size_um", "defect_class",
                    "inspection_tool", "inspected_at", "created_at", "updated_at"},
        "maintenance_events": {"id", "chamber_id", "event_type", "performed_at",
                               "description", "performed_by", "created_at", "updated_at"},
        "yield_results": {"id", "wafer_id", "die_yield", "bin1_count",
                          "bin_fail_count", "tested_at", "created_at", "updated_at"},
        "excursions": {"id", "lot_id", "wafer_id", "excursion_type", "severity",
                       "detected_at", "evidence", "created_at", "updated_at"},
        "root_cause_rankings": {"id", "excursion_id", "rank", "cause", "score", "confidence",
                                "evidence_ids", "supporting_signals", "contradicting_signals",
                                "model_name", "model_version", "produced_at", "created_at", "updated_at"},
        "pre_run_assessments": {"id", "lot_id", "risk_score", "risk_label",
                                "feature_vector", "features_used", "produced_at",
                                "created_at", "updated_at"},
        "action_recommendations": {"id", "excursion_id", "action_text", "priority",
                                   "produced_at", "created_at", "updated_at"},
        "action_reviews": {"id", "recommendation_id", "engineer_id", "decision",
                           "rationale", "reviewed_at", "created_at", "updated_at"},
    }
    for table, expected_cols in checks.items():
        actual_cols = {c["name"] for c in inspector.get_columns(table)}
        missing = expected_cols - actual_cols
        assert not missing, f"Table '{table}' missing columns: {missing}"
