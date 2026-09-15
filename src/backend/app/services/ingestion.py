"""
app/services/ingestion.py — DataFrames loader from the DB session.

Provides thin functions that execute SQL via SQLAlchemy and return typed
pandas DataFrames ready for consumption by analytics services.

IMPORTANT:
- This is the ONLY analytics file that may import from app.database or
  use a SQLAlchemy Session / Connection.
- All analytics services (anomaly, recurrence, etc.) accept DataFrames
  as arguments and never call ingestion functions directly.
- No scenario labels are ever queried here.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Generic helper
# ---------------------------------------------------------------------------

def _query_df(session: Session, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    """Execute a SQL query and return the result as a DataFrame."""
    result = session.execute(text(sql), params or {})
    rows = result.fetchall()
    columns = list(result.keys())
    return pd.DataFrame(rows, columns=columns)


# ---------------------------------------------------------------------------
# Table loaders
# ---------------------------------------------------------------------------

def load_tools(session: Session) -> pd.DataFrame:
    """Return tools table as DataFrame."""
    return _query_df(session, "SELECT tool_id, name AS tool_name, tool_type, fab_area FROM tools")


def load_chambers(session: Session) -> pd.DataFrame:
    """Return chambers with tool_name joined (aliased as chamber_name, tool_name)."""
    return _query_df(session, """
        SELECT c.chamber_id,
               c.name        AS chamber_name,
               t.name        AS tool_name,
               t.tool_type,
               t.fab_area
        FROM chambers c
        JOIN tools t ON c.tool_id = t.tool_id
    """)


def load_lots(session: Session) -> pd.DataFrame:
    """Return lots table."""
    return _query_df(session, """
        SELECT lot_id, lot_id_str, product, technology_node, priority,
               planned_start_at, actual_start_at, queue_time_h,
               status
        FROM lots
        ORDER BY actual_start_at
    """)


def load_wafers(session: Session, lot_id: int | None = None) -> pd.DataFrame:
    """Return wafers, optionally filtered to a specific lot."""
    if lot_id is not None:
        return _query_df(session, """
            SELECT wafer_id, lot_id, slot_number, wafer_status
            FROM wafers
            WHERE lot_id = :lot_id
        """, {"lot_id": lot_id})
    return _query_df(session, "SELECT wafer_id, lot_id, slot_number, wafer_status FROM wafers")


def load_runs(session: Session, lot_id: int | None = None) -> pd.DataFrame:
    """Return runs with chamber and recipe info, optionally filtered by lot."""
    if lot_id is not None:
        return _query_df(session, """
            SELECT r.run_id, r.wafer_id, r.chamber_id, r.recipe_id,
                   r.start_time, r.end_time
            FROM runs r
            JOIN wafers w ON r.wafer_id = w.wafer_id
            WHERE w.lot_id = :lot_id
        """, {"lot_id": lot_id})
    return _query_df(session, """
        SELECT run_id, wafer_id, chamber_id, recipe_id, start_time, end_time
        FROM runs
    """)


def load_process_parameters(
    session: Session,
    run_ids: list[int] | None = None,
) -> pd.DataFrame:
    """Return process_parameters, optionally filtered to specific run IDs."""
    if run_ids:
        # SQLAlchemy text() cannot accept a list directly — use IN with bind params
        placeholders = ", ".join(str(i) for i in run_ids)
        return _query_df(session, f"""
            SELECT pp_id, run_id, param_name, value, unit, nominal, lsl, usl
            FROM process_parameters
            WHERE run_id IN ({placeholders})
        """)
    return _query_df(session, """
        SELECT pp_id, run_id, param_name, value, unit, nominal, lsl, usl
        FROM process_parameters
    """)


def load_metrology(session: Session, lot_id: int | None = None) -> pd.DataFrame:
    """Return metrology rows."""
    if lot_id is not None:
        return _query_df(session, """
            SELECT m.metro_id, m.wafer_id, m.metric_name, m.value, m.unit,
                   m.measured_at, m.site_x, m.site_y
            FROM metrology m
            JOIN wafers w ON m.wafer_id = w.wafer_id
            WHERE w.lot_id = :lot_id
        """, {"lot_id": lot_id})
    return _query_df(session, """
        SELECT metro_id, wafer_id, metric_name, value, unit, measured_at, site_x, site_y
        FROM metrology
    """)


def load_defects(session: Session, wafer_ids: list[int] | None = None) -> pd.DataFrame:
    """Return defects, optionally filtered to specific wafer IDs."""
    if wafer_ids:
        placeholders = ", ".join(str(i) for i in wafer_ids)
        return _query_df(session, f"""
            SELECT defect_id, wafer_id, x_coord, y_coord, defect_class, inspected_at
            FROM defects
            WHERE wafer_id IN ({placeholders})
        """)
    return _query_df(session, """
        SELECT defect_id, wafer_id, x_coord, y_coord, defect_class, inspected_at
        FROM defects
    """)


def load_maintenance_events(
    session: Session,
    chamber_id: int | None = None,
) -> pd.DataFrame:
    """Return maintenance events, optionally filtered to a chamber."""
    if chamber_id is not None:
        return _query_df(session, """
            SELECT maint_id, chamber_id, event_type, performed_at,
                   performed_by, description
            FROM maintenance_events
            WHERE chamber_id = :chamber_id
            ORDER BY performed_at
        """, {"chamber_id": chamber_id})
    return _query_df(session, """
        SELECT maint_id, chamber_id, event_type, performed_at,
               performed_by, description
        FROM maintenance_events
        ORDER BY performed_at
    """)


def load_yield_results(session: Session, lot_id: int | None = None) -> pd.DataFrame:
    """Return yield_results, optionally filtered by lot."""
    if lot_id is not None:
        return _query_df(session, """
            SELECT yr.yield_id, yr.wafer_id, yr.lot_id, yr.die_yield,
                   yr.bin1_count, yr.bin_fail_count, yr.tested_at
            FROM yield_results yr
            WHERE yr.lot_id = :lot_id
        """, {"lot_id": lot_id})
    return _query_df(session, """
        SELECT yield_id, wafer_id, lot_id, die_yield, bin1_count, bin_fail_count, tested_at
        FROM yield_results
    """)


def load_pre_run_features(session: Session) -> pd.DataFrame:
    """
    Load pre-run feature vectors for all lots.

    Uses ONLY columns that are available before a lot starts.
    See PRE_RUN_FEATURE_WHITELIST in scenarios.py for the authoritative list.

    Note: This query pre-computes derived features (chamber_yield_30d,
    days_since_last_pm, chamber_ooc_rate_30d) from historical data using
    window functions / correlated sub-selects.  For the prototype these are
    approximated by joining pre-computed columns stored in the lots table
    (feature columns written by seed_db.py).
    """
    return _query_df(session, """
        SELECT
            l.lot_id,
            l.lot_id_str,
            l.priority         AS lot_priority,
            l.product          AS product_encoded,
            l.technology_node  AS technology_node_encoded,
            l.planned_start_at,
            l.actual_start_at,
            l.actual_end_at,
            l.queue_time_h     AS queue_time_planned_h
        FROM lots l
        ORDER BY l.actual_start_at
    """)
