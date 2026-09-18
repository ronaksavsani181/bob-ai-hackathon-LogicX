"""0001_initial_schema

Full initial schema for the Wafer Yield Root Cause & Defect Pattern Analyser.

Tables created (in FK dependency order):
  1.  tools
  2.  chambers              → tools
  3.  recipes
  4.  lots
  5.  wafers                → lots
  6.  runs                  → wafers, chambers, recipes
  7.  process_parameters    → runs
  8.  trace_data            → runs
  9.  metrology             → wafers
  10. defects               → wafers
  11. maintenance_events    → chambers
  12. yield_results         → wafers
  13. excursions            → lots (nullable), wafers (nullable)
  14. root_cause_rankings   → excursions (nullable)
  15. pre_run_assessments   → lots
  16. action_recommendations→ excursions
  17. action_reviews        → action_recommendations

Revision ID: 0001
Revises: (none — first migration)
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | tuple | None = None
depends_on: str | tuple | None = None


def upgrade() -> None:
    # ── 1. tools ──────────────────────────────────────────────────────────────
    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("tool_type", sa.String(64), nullable=False),
        sa.Column("fab_area", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_tools_name"),
    )
    op.create_index("ix_tools_name", "tools", ["name"])

    # ── 2. chambers ───────────────────────────────────────────────────────────
    op.create_table(
        "chambers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("chamber_index", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_id", "name", name="uq_chamber_tool_name"),
    )
    op.create_index("ix_chambers_tool_id", "chambers", ["tool_id"])
    op.create_index("ix_chambers_name", "chambers", ["name"])

    # ── 3. recipes ────────────────────────────────────────────────────────────
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("process_step", sa.String(64), nullable=False),
        sa.Column("nominal_params", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_recipe_name_version"),
    )
    op.create_index("ix_recipes_name", "recipes", ["name"])

    # ── 4. lots ───────────────────────────────────────────────────────────────
    op.create_table(
        "lots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lot_id", sa.String(32), nullable=False),
        sa.Column("product", sa.String(64), nullable=False),
        sa.Column("technology_node", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lot_id", name="uq_lots_lot_id"),
    )
    op.create_index("ix_lots_lot_id", "lots", ["lot_id"])
    op.create_index("ix_lots_product", "lots", ["product"])
    op.create_index("ix_lots_status", "lots", ["status"])
    op.create_index("ix_lots_planned_start_at", "lots", ["planned_start_at"])
    op.create_index("ix_lots_actual_start_at", "lots", ["actual_start_at"])

    # ── 5. wafers ─────────────────────────────────────────────────────────────
    op.create_table(
        "wafers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("wafer_slot", sa.Integer(), nullable=False),
        sa.Column("die_count_total", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lot_id", "wafer_slot", name="uq_wafer_lot_slot"),
    )
    op.create_index("ix_wafers_lot_id", "wafers", ["lot_id"])

    # ── 6. runs ───────────────────────────────────────────────────────────────
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wafer_id", sa.Integer(), nullable=False),
        sa.Column("chamber_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wafer_id"], ["wafers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chamber_id"], ["chambers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_wafer_id", "runs", ["wafer_id"])
    op.create_index("ix_runs_chamber_id", "runs", ["chamber_id"])
    op.create_index("ix_runs_recipe_id", "runs", ["recipe_id"])
    op.create_index("ix_runs_start_time", "runs", ["start_time"])
    op.create_index("ix_runs_run_status", "runs", ["run_status"])

    # ── 7. process_parameters ─────────────────────────────────────────────────
    op.create_table(
        "process_parameters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("param_name", sa.String(64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("nominal", sa.Float(), nullable=True),
        sa.Column("lsl", sa.Float(), nullable=True),
        sa.Column("usl", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_process_parameters_run_id", "process_parameters", ["run_id"])
    op.create_index("ix_process_parameters_param_name", "process_parameters", ["param_name"])

    # ── 8. trace_data ─────────────────────────────────────────────────────────
    op.create_table(
        "trace_data",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trace_data_run_id", "trace_data", ["run_id"])
    op.create_index("ix_trace_data_timestamp", "trace_data", ["timestamp"])

    # ── 9. metrology ──────────────────────────────────────────────────────────
    op.create_table(
        "metrology",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wafer_id", sa.Integer(), nullable=False),
        sa.Column("measurement_type", sa.String(64), nullable=False),
        sa.Column("site_index", sa.Integer(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wafer_id"], ["wafers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metrology_wafer_id", "metrology", ["wafer_id"])
    op.create_index("ix_metrology_measurement_type", "metrology", ["measurement_type"])
    op.create_index("ix_metrology_measured_at", "metrology", ["measured_at"])

    # ── 10. defects ───────────────────────────────────────────────────────────
    op.create_table(
        "defects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wafer_id", sa.Integer(), nullable=False),
        sa.Column("x_coord", sa.Float(), nullable=False),
        sa.Column("y_coord", sa.Float(), nullable=False),
        sa.Column("size_um", sa.Float(), nullable=True),
        sa.Column("defect_class", sa.String(64), nullable=True),
        sa.Column("inspection_tool", sa.String(64), nullable=True),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wafer_id"], ["wafers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_defects_wafer_id", "defects", ["wafer_id"])
    op.create_index("ix_defects_defect_class", "defects", ["defect_class"])
    op.create_index("ix_defects_inspected_at", "defects", ["inspected_at"])

    # ── 11. maintenance_events ────────────────────────────────────────────────
    op.create_table(
        "maintenance_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chamber_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("performed_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chamber_id"], ["chambers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_maintenance_events_chamber_id", "maintenance_events", ["chamber_id"])
    op.create_index("ix_maintenance_events_event_type", "maintenance_events", ["event_type"])
    op.create_index("ix_maintenance_events_performed_at", "maintenance_events", ["performed_at"])

    # ── 12. yield_results ─────────────────────────────────────────────────────
    op.create_table(
        "yield_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wafer_id", sa.Integer(), nullable=False),
        sa.Column("die_yield", sa.Float(), nullable=False),
        sa.Column("bin1_count", sa.Integer(), nullable=True),
        sa.Column("bin_fail_count", sa.Integer(), nullable=True),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wafer_id"], ["wafers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_yield_results_wafer_id", "yield_results", ["wafer_id"])
    op.create_index("ix_yield_results_die_yield", "yield_results", ["die_yield"])
    op.create_index("ix_yield_results_tested_at", "yield_results", ["tested_at"])

    # ── 13. excursions ────────────────────────────────────────────────────────
    op.create_table(
        "excursions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=True),
        sa.Column("wafer_id", sa.Integer(), nullable=True),
        sa.Column("excursion_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["wafer_id"], ["wafers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_excursions_lot_id", "excursions", ["lot_id"])
    op.create_index("ix_excursions_wafer_id", "excursions", ["wafer_id"])
    op.create_index("ix_excursions_excursion_type", "excursions", ["excursion_type"])
    op.create_index("ix_excursions_severity", "excursions", ["severity"])
    op.create_index("ix_excursions_detected_at", "excursions", ["detected_at"])

    # ── 14. root_cause_rankings ───────────────────────────────────────────────
    op.create_table(
        "root_cause_rankings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("excursion_id", sa.Integer(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("cause", sa.String(128), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_ids", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("supporting_signals", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("contradicting_signals", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(32), nullable=False),
        sa.Column("produced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["excursion_id"], ["excursions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_root_cause_rankings_excursion_id", "root_cause_rankings", ["excursion_id"])
    op.create_index("ix_root_cause_rankings_cause", "root_cause_rankings", ["cause"])
    op.create_index("ix_root_cause_rankings_produced_at", "root_cause_rankings", ["produced_at"])

    # ── 15. pre_run_assessments ───────────────────────────────────────────────
    op.create_table(
        "pre_run_assessments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_label", sa.String(16), nullable=False),
        sa.Column("feature_vector", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("features_used", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False),
        sa.Column("produced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pre_run_assessments_lot_id", "pre_run_assessments", ["lot_id"])
    op.create_index("ix_pre_run_assessments_risk_score", "pre_run_assessments", ["risk_score"])
    op.create_index("ix_pre_run_assessments_risk_label", "pre_run_assessments", ["risk_label"])
    op.create_index("ix_pre_run_assessments_produced_at", "pre_run_assessments", ["produced_at"])

    # ── 16. action_recommendations ────────────────────────────────────────────
    op.create_table(
        "action_recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("excursion_id", sa.Integer(), nullable=False),
        sa.Column("action_text", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("produced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["excursion_id"], ["excursions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_recommendations_excursion_id", "action_recommendations", ["excursion_id"])
    op.create_index("ix_action_recommendations_priority", "action_recommendations", ["priority"])

    # ── 17. action_reviews ────────────────────────────────────────────────────
    op.create_table(
        "action_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("engineer_id", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["action_recommendations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_reviews_recommendation_id", "action_reviews", ["recommendation_id"])
    op.create_index("ix_action_reviews_engineer_id", "action_reviews", ["engineer_id"])
    op.create_index("ix_action_reviews_decision", "action_reviews", ["decision"])
    op.create_index("ix_action_reviews_reviewed_at", "action_reviews", ["reviewed_at"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("action_reviews")
    op.drop_table("action_recommendations")
    op.drop_table("pre_run_assessments")
    op.drop_table("root_cause_rankings")
    op.drop_table("excursions")
    op.drop_table("yield_results")
    op.drop_table("maintenance_events")
    op.drop_table("defects")
    op.drop_table("metrology")
    op.drop_table("trace_data")
    op.drop_table("process_parameters")
    op.drop_table("runs")
    op.drop_table("wafers")
    op.drop_table("lots")
    op.drop_table("recipes")
    op.drop_table("chambers")
    op.drop_table("tools")
