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
    df = pd.DataFrame(rows, columns=columns)
    # SQLite stores datetimes as strings — coerce columns with datetime-like
    # names so downstream pandas comparisons work correctly.
    datetime_suffixes = ("_at", "_time", "_date", "_timestamp")
    for col in df.columns:
        col_lower = col.lower()
        is_datetime_column = (
            col_lower.endswith(datetime_suffixes)
            or col_lower in {"date", "timestamp"}
        )
        if is_datetime_column and df[col].notna().any():
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df


# ---------------------------------------------------------------------------
# Table loaders
# ---------------------------------------------------------------------------

def load_tools(session: Session) -> pd.DataFrame:
    """Return tools table as DataFrame."""
    return _query_df(session, "SELECT id AS tool_id, name AS tool_name, tool_type, fab_area FROM tools")


def load_chambers(session: Session) -> pd.DataFrame:
    """Return chambers with tool_name joined (aliased as chamber_name, tool_name)."""
    return _query_df(session, """
        SELECT c.id          AS chamber_id,
               c.name        AS chamber_name,
               t.name        AS tool_name,
               t.tool_type,
               t.fab_area
        FROM chambers c
        JOIN tools t ON c.tool_id = t.id
    """)


def load_lots(session: Session) -> pd.DataFrame:
    """
    Return lots table.

    Column aliases so downstream analytics use stable names:
      lot_id      → integer primary key (used as FK join key for wafers/yields)
      lot_id_str  → human-readable business key (e.g. "L0042")
      queue_time_h → NULL (not stored; pre-run router fills with a default)
      actual_end_at → NULL (not stored in prototype; router handles gracefully)
    """
    return _query_df(session, """
        SELECT id              AS lot_id,
               lot_id         AS lot_id_str,
               product,
               technology_node,
               priority,
               status,
               planned_start_at,
               actual_start_at,
               NULL           AS actual_end_at,
               NULL           AS queue_time_h
        FROM lots
        ORDER BY actual_start_at
    """)


def load_wafers(session: Session, lot_id: int | None = None) -> pd.DataFrame:
    """
    Return wafers, optionally filtered to a specific lot.

    Column aliases:
      wafer_id → integer primary key
      lot_id   → integer FK to lots.id (matches load_lots lot_id)
    """
    if lot_id is not None:
        return _query_df(session, """
            SELECT id       AS wafer_id,
                   lot_id,
                   wafer_slot,
                   die_count_total
            FROM wafers
            WHERE lot_id = :lot_id
        """, {"lot_id": lot_id})
    return _query_df(session, """
        SELECT id       AS wafer_id,
               lot_id,
               wafer_slot,
               die_count_total
        FROM wafers
    """)


def load_runs(session: Session, lot_id: int | None = None) -> pd.DataFrame:
    """Return runs, optionally filtered by lot (via wafer FK)."""
    if lot_id is not None:
        return _query_df(session, """
            SELECT r.id         AS run_id,
                   r.wafer_id,
                   r.chamber_id,
                   r.recipe_id,
                   r.start_time,
                   r.end_time
            FROM runs r
            JOIN wafers w ON r.wafer_id = w.id
            WHERE w.lot_id = :lot_id
        """, {"lot_id": lot_id})
    return _query_df(session, """
        SELECT id AS run_id, wafer_id, chamber_id, recipe_id, start_time, end_time
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
            SELECT id AS pp_id, run_id, param_name, value, unit, nominal, lsl, usl
            FROM process_parameters
            WHERE run_id IN ({placeholders})
        """)
    return _query_df(session, """
        SELECT id AS pp_id, run_id, param_name, value, unit, nominal, lsl, usl
        FROM process_parameters
    """)


def load_metrology(session: Session, lot_id: int | None = None) -> pd.DataFrame:
    """Return metrology rows."""
    if lot_id is not None:
        return _query_df(session, """
            SELECT m.id AS metro_id, m.wafer_id, m.metric_name, m.value, m.unit,
                   m.measured_at, m.site_x, m.site_y
            FROM metrology m
            JOIN wafers w ON m.wafer_id = w.id
            WHERE w.lot_id = :lot_id
        """, {"lot_id": lot_id})
    return _query_df(session, """
        SELECT id AS metro_id, wafer_id, metric_name, value, unit, measured_at, site_x, site_y
        FROM metrology
    """)


def load_defects(session: Session, wafer_ids: list[int] | None = None) -> pd.DataFrame:
    """Return defects, optionally filtered to specific wafer IDs."""
    if wafer_ids:
        placeholders = ", ".join(str(i) for i in wafer_ids)
        return _query_df(session, f"""
            SELECT id AS defect_id, wafer_id, x_coord, y_coord, defect_class, inspected_at
            FROM defects
            WHERE wafer_id IN ({placeholders})
        """)
    return _query_df(session, """
        SELECT id AS defect_id, wafer_id, x_coord, y_coord, defect_class, inspected_at
        FROM defects
    """)


def load_maintenance_events(
    session: Session,
    chamber_id: int | None = None,
) -> pd.DataFrame:
    """Return maintenance events, optionally filtered to a chamber."""
    if chamber_id is not None:
        return _query_df(session, """
            SELECT id AS maint_id, chamber_id, event_type, performed_at,
                   performed_by, description
            FROM maintenance_events
            WHERE chamber_id = :chamber_id
            ORDER BY performed_at
        """, {"chamber_id": chamber_id})
    return _query_df(session, """
        SELECT id AS maint_id, chamber_id, event_type, performed_at,
               performed_by, description
        FROM maintenance_events
        ORDER BY performed_at
    """)


def load_yield_results(session: Session, lot_id: int | None = None) -> pd.DataFrame:
    """Return yield_results."""
    if lot_id is not None:
        return _query_df(session, """
            SELECT yr.id       AS yield_id,
                   yr.wafer_id,
                   yr.die_yield,
                   yr.bin1_count,
                   yr.bin_fail_count,
                   yr.tested_at
            FROM yield_results yr
            JOIN wafers w ON yr.wafer_id = w.id
            WHERE w.lot_id = :lot_id
        """, {"lot_id": lot_id})
    return _query_df(session, """
        SELECT id       AS yield_id,
               wafer_id,
               die_yield,
               bin1_count,
               bin_fail_count,
               tested_at
        FROM yield_results
    """)


def load_pre_run_features(session: Session) -> pd.DataFrame:
    """
    Load pre-run feature vectors for all lots.

    Uses ONLY columns that are available before a lot starts.
    See PRE_RUN_FEATURE_WHITELIST in scenarios.py for the authoritative list.

    Derived features (chamber_yield_30d, days_since_last_pm, chamber_ooc_rate_30d)
    are approximated with defaults in the pre_run router — they are not stored
    as columns in the prototype DB.
    """
    return _query_df(session, """
        SELECT
            l.id               AS lot_id,
            l.lot_id           AS lot_id_str,
            l.priority,
            l.product,
            l.technology_node,
            l.planned_start_at,
            l.actual_start_at,
            NULL               AS actual_end_at,
            NULL               AS queue_time_h
        FROM lots l
        ORDER BY l.actual_start_at
    """)
