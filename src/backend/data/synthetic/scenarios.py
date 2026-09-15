"""
scenarios.py — Typed scenario definitions for the synthetic fab dataset.

Each ScenarioDef encodes the parameters of one synthetic failure mode.
This file is the single source of truth for all injected signals.

IMPORTANT:
- This file defines ground-truth for VALIDATION and DEMO purposes only.
- The analytics services in app/services/ must NOT import from this file.
- The separation ensures the root-cause ranker cannot cheat by reading labels.

All synthetic data is demonstration data only and does not represent any
real semiconductor fabrication facility or process.
"""

from __future__ import annotations

from dataclasses import dataclass, field


WAFER_RADIUS_MM: float = 150.0   # 300 mm wafer; radius used for coordinates
HISTORY_DAYS: int = 180
LOTS_TOTAL: int = 500
WAFERS_PER_LOT: int = 25
GLOBAL_SEED: int = 42


# ---------------------------------------------------------------------------
# Tool / chamber layout
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChamberDef:
    tool_name: str
    chamber_name: str
    tool_type: str
    fab_area: str
    chamber_index: int


# Six tools, two chambers each = 12 chambers
CHAMBERS: list[ChamberDef] = [
    # Etch tools
    ChamberDef("ETH-01", "ETH-01-A", "etch", "etch_bay", 0),
    ChamberDef("ETH-01", "ETH-01-B", "etch", "etch_bay", 1),
    ChamberDef("ETH-02", "ETH-02-A", "etch", "etch_bay", 0),
    ChamberDef("ETH-02", "ETH-02-B", "etch", "etch_bay", 1),
    # Lithography tools
    ChamberDef("LIT-01", "LIT-01-A", "litho", "litho_bay", 0),
    ChamberDef("LIT-01", "LIT-01-B", "litho", "litho_bay", 1),
    # CVD tools
    ChamberDef("CVD-03", "CVD-03-A", "cvd", "deposition_bay", 0),
    ChamberDef("CVD-03", "CVD-03-B", "cvd", "deposition_bay", 1),
    # CMP tools
    ChamberDef("CMP-02", "CMP-02-A", "cmp", "cmp_bay", 0),
    ChamberDef("CMP-02", "CMP-02-B", "cmp", "cmp_bay", 1),
    # Implant tools
    ChamberDef("IMP-01", "IMP-01-A", "implant", "implant_bay", 0),
    ChamberDef("IMP-01", "IMP-01-B", "implant", "implant_bay", 1),
]

TOOL_NAMES: list[str] = list(dict.fromkeys(c.tool_name for c in CHAMBERS))


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScenarioDef:
    """
    Complete specification of a synthetic scenario.

    Fields document both the injected signal AND the expected analytics
    consequence, so validation tests can assert without importing analytics code.
    """
    scenario_id: str
    description: str

    # Lot range that is affected (inclusive, 1-based lot index)
    lot_index_start: int
    lot_index_end: int

    # Chamber(s) associated with this scenario
    affected_chambers: list[str] = field(default_factory=list)

    # Process parameter injection
    param_name: str = ""
    param_nominal: float = 0.0
    param_drift_start: float = 0.0   # value at start of scenario window
    param_drift_end: float = 0.0     # value at end of scenario window

    # Yield effect
    yield_penalty_min: float = 0.0   # min penalty applied to die_yield
    yield_penalty_max: float = 0.0   # max penalty applied to die_yield

    # Defect injection
    defect_count_min: int = 8        # defects/wafer minimum
    defect_count_max: int = 12       # defects/wafer maximum
    defect_spatial_pattern: str = "uniform"

    # Metrology injection
    metrology_sigma_multiplier: float = 1.0  # multiply normal σ by this factor

    # Maintenance
    has_unscheduled_pm: bool = False
    pm_day_offset: int = 0           # day within history window for unscheduled PM

    # Queue time (S-TIME)
    queue_time_hours: float = 0.0    # hours; > 0 means inject long queue

    # Ground-truth label (for validation only)
    expected_root_cause: str = ""


SCENARIOS: dict[str, ScenarioDef] = {
    # ── S-ETCH ────────────────────────────────────────────────────────────────
    "S-ETCH": ScenarioDef(
        scenario_id="S-ETCH",
        description=(
            "Etch rate drift on chamber ETH-02. "
            "Rate increases linearly from nominal to +15% over 30 days."
        ),
        lot_index_start=300,
        lot_index_end=360,
        affected_chambers=["ETH-02-A", "ETH-02-B"],
        param_name="etch_rate",
        param_nominal=120.0,
        param_drift_start=120.0,
        param_drift_end=138.0,   # +15 %
        yield_penalty_min=0.02,
        yield_penalty_max=0.08,
        defect_count_min=8,
        defect_count_max=15,
        defect_spatial_pattern="edge_ring",
        expected_root_cause="Etch chamber drift",
    ),

    # ── S-OVL ─────────────────────────────────────────────────────────────────
    "S-OVL": ScenarioDef(
        scenario_id="S-OVL",
        description=(
            "Overlay metrology excursion on tool LIT-01. "
            "Overlay error 3–4 × nominal σ."
        ),
        lot_index_start=200,
        lot_index_end=215,
        affected_chambers=["LIT-01-A", "LIT-01-B"],
        param_name="overlay_x",
        param_nominal=0.0,
        param_drift_start=0.0,
        param_drift_end=0.0,
        metrology_sigma_multiplier=3.5,
        yield_penalty_min=0.04,
        yield_penalty_max=0.10,
        defect_count_min=8,
        defect_count_max=14,
        defect_spatial_pattern="radial",
        expected_root_cause="Overlay tool excursion",
    ),

    # ── S-PART ────────────────────────────────────────────────────────────────
    "S-PART": ScenarioDef(
        scenario_id="S-PART",
        description=(
            "Particle contamination excursion on chamber CVD-03. "
            "Defect density spikes to 60–80 defects/wafer with center-heavy spatial pattern."
        ),
        lot_index_start=400,
        lot_index_end=412,
        affected_chambers=["CVD-03-A", "CVD-03-B"],
        param_name="",
        param_nominal=0.0,
        defect_count_min=60,
        defect_count_max=80,
        defect_spatial_pattern="center_heavy",
        yield_penalty_min=0.10,
        yield_penalty_max=0.20,
        expected_root_cause="Particle contamination",
    ),

    # ── S-MAINT ───────────────────────────────────────────────────────────────
    "S-MAINT": ScenarioDef(
        scenario_id="S-MAINT",
        description=(
            "Unscheduled PM on ETH-02 at day 120. "
            "Yield degrades for ~15 lots post-maintenance then recovers. "
            "Lots L0413-L0428 start after the day-120 PM event."
        ),
        lot_index_start=413,   # AFTER day-120 PM; verified by timestamp check
        lot_index_end=428,
        affected_chambers=["ETH-02-A", "ETH-02-B"],
        yield_penalty_min=0.04,
        yield_penalty_max=0.08,
        defect_count_min=10,
        defect_count_max=20,
        defect_spatial_pattern="scratch_line",
        has_unscheduled_pm=True,
        pm_day_offset=120,
        expected_root_cause="Post-maintenance shift",
    ),

    # ── S-CHAM ────────────────────────────────────────────────────────────────
    "S-CHAM": ScenarioDef(
        scenario_id="S-CHAM",
        description=(
            "Persistent chamber-systematic yield deficit on CMP-02. "
            "Yield is ~8% below the fleet average across all history."
        ),
        lot_index_start=1,     # all lots; filtered by chamber assignment
        lot_index_end=LOTS_TOTAL,
        affected_chambers=["CMP-02-A", "CMP-02-B"],
        yield_penalty_min=0.07,
        yield_penalty_max=0.09,
        defect_count_min=10,
        defect_count_max=18,
        defect_spatial_pattern="localized_hotspot",
        expected_root_cause="Chamber-specific systematic",
    ),

    # ── S-TIME ────────────────────────────────────────────────────────────────
    "S-TIME": ScenarioDef(
        scenario_id="S-TIME",
        description=(
            "Long queue time (> 72 h) before etch step correlates with yield loss. "
            "Scattered across ~10% of lots."
        ),
        lot_index_start=1,     # scattered; identified by queue_time > threshold
        lot_index_end=LOTS_TOTAL,
        affected_chambers=[],  # no specific chamber; exposure-based
        yield_penalty_min=0.03,
        yield_penalty_max=0.06,
        defect_count_min=10,
        defect_count_max=18,
        defect_spatial_pattern="diffuse_center",
        queue_time_hours=80.0,
        expected_root_cause="Queue-time exposure",
    ),

    # ── S-CTRL ────────────────────────────────────────────────────────────────
    "S-CTRL": ScenarioDef(
        scenario_id="S-CTRL",
        description=(
            "Normal/control lots. Nominal parameters, normal defect density, "
            "healthy yield 0.92–0.98."
        ),
        lot_index_start=1,
        lot_index_end=LOTS_TOTAL,
        affected_chambers=[],
        defect_count_min=8,
        defect_count_max=12,
        defect_spatial_pattern="uniform",
        expected_root_cause="",
    ),
}

# ---------------------------------------------------------------------------
# Pre-run feature whitelist — used by analytics AND leakage tests
# ONLY columns that are known BEFORE a lot starts may appear here.
# ---------------------------------------------------------------------------
PRE_RUN_FEATURE_WHITELIST: list[str] = [
    "lot_priority",
    "product_encoded",
    "technology_node_encoded",
    "planned_recipe_encoded",
    "planned_chamber_encoded",
    "chamber_yield_30d",       # chamber historical yield, T-1 day window
    "days_since_last_pm",      # days since last PM on planned chamber, at planned_start_at
    "chamber_ooc_rate_30d",    # parameter OOC rate, 30 days before planned_start_at
    "queue_time_planned_h",    # planned queue time in hours (estimated)
]

# Columns that are FORBIDDEN in any pre-run model feature vector
PRE_RUN_FORBIDDEN_COLUMNS: list[str] = [
    "die_yield",
    "bin1_count",
    "bin_fail_count",
    "defect_count",
    "defect_density",
    "overlay_error",
    "metrology_value",
    "tested_at",
    "inspected_at",
    "measured_at",
]
