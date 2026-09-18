"""
seed_db.py — Insert the synthetic fab dataset into the configured PostgreSQL database.

Usage:
    cd src/backend
    python data/seed_db.py

The script is IDEMPOTENT: it checks whether the tools table already has rows
before inserting.  If data already exists the script exits gracefully without
creating duplicates.

DATABASE_URL must be set in the environment (or .env file).
In Docker Compose this is injected automatically by the entrypoint.sh.
"""
from __future__ import annotations

import os
import sys
import logging
from datetime import datetime

# ---------------------------------------------------------------------------
# Make src/backend importable when run as a standalone script
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="[seed_db] %(message)s")
log = logging.getLogger("seed_db")

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, get_engine
from data.synthetic.generator import generate_all


def _already_seeded(session: Session) -> bool:
    """Return True if the tools table already contains rows."""
    count = session.execute(text("SELECT COUNT(*) FROM tools")).scalar()
    return int(count) > 0


def _insert_tools(session: Session, df: pd.DataFrame) -> dict[str, int]:
    """Insert tools; return {name → db_id} map."""
    from app.models.tool import Tool
    name_to_id: dict[str, int] = {}
    for _, row in df.iterrows():
        obj = Tool(
            name=row["name"],
            tool_type=row["tool_type"],
            fab_area=row["fab_area"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        session.add(obj)
        session.flush()
        name_to_id[row["name"]] = obj.id
    return name_to_id


def _insert_chambers(
    session: Session,
    df: pd.DataFrame,
    tool_name_to_db_id: dict[str, int],
    tools_df: pd.DataFrame,
) -> dict[str, int]:
    """Insert chambers; return {chamber_name → db_id} map."""
    from app.models.tool import Chamber

    # Map generator tool_id → tool_name
    gen_tool_id_to_name = {int(r["tool_id"]): r["name"] for _, r in tools_df.iterrows()}

    name_to_id: dict[str, int] = {}
    for _, row in df.iterrows():
        tool_name = gen_tool_id_to_name[int(row["tool_id"])]
        db_tool_id = tool_name_to_db_id[tool_name]
        obj = Chamber(
            tool_id=db_tool_id,
            name=row["name"],
            chamber_index=int(row["chamber_index"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        session.add(obj)
        session.flush()
        name_to_id[row["name"]] = obj.id
    return name_to_id


def _insert_recipes(session: Session, df: pd.DataFrame) -> dict[int, int]:
    """Insert recipes; return {generator_recipe_id → db_id} map."""
    from app.models.recipe import Recipe
    gen_to_db: dict[int, int] = {}
    for _, row in df.iterrows():
        obj = Recipe(
            name=row["name"],
            version=row["version"],
            process_step=row["process_step"],
            nominal_params=row["nominal_params"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        session.add(obj)
        session.flush()
        gen_to_db[int(row["recipe_id"])] = obj.id
    return gen_to_db


def _insert_lots(session: Session, df: pd.DataFrame) -> dict[int, int]:
    """Insert lots; return {generator_lot_id → db_id} map."""
    from app.models.lot import Lot
    gen_to_db: dict[int, int] = {}
    for _, row in df.iterrows():
        obj = Lot(
            lot_id=row["lot_id_str"],
            product=row["product"],
            technology_node=row["technology_node"],
            priority=row["priority"],
            status=row["status"],
            planned_start_at=row["planned_start_at"],
            actual_start_at=row["actual_start_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        session.add(obj)
        session.flush()
        gen_to_db[int(row["lot_id"])] = obj.id
    return gen_to_db


def _insert_wafers(
    session: Session,
    df: pd.DataFrame,
    lot_gen_to_db: dict[int, int],
) -> dict[int, int]:
    """Insert wafers; return {generator_wafer_id → db_id} map."""
    from app.models.wafer import Wafer
    gen_to_db: dict[int, int] = {}
    for _, row in df.iterrows():
        obj = Wafer(
            lot_id=lot_gen_to_db[int(row["lot_id"])],
            wafer_slot=int(row["wafer_slot"]),
            die_count_total=int(row["die_count_total"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        session.add(obj)
        session.flush()
        gen_to_db[int(row["wafer_id"])] = obj.id
    return gen_to_db


def _insert_runs(
    session: Session,
    df: pd.DataFrame,
    wafer_gen_to_db: dict[int, int],
    chamber_name_to_db_id: dict[str, int],
    recipe_gen_to_db: dict[int, int],
    chambers_df: pd.DataFrame,
) -> dict[int, int]:
    """Insert runs; return {generator_run_id → db_id} map."""
    from app.models.run import Run

    # Map generator chamber_id → chamber_name
    gen_cid_to_name = {int(r["chamber_id"]): r["name"] for _, r in chambers_df.iterrows()}

    gen_to_db: dict[int, int] = {}
    for _, row in df.iterrows():
        cname = gen_cid_to_name[int(row["chamber_id"])]
        db_chamber_id = chamber_name_to_db_id[cname]
        obj = Run(
            wafer_id=wafer_gen_to_db[int(row["wafer_id"])],
            chamber_id=db_chamber_id,
            recipe_id=recipe_gen_to_db[int(row["recipe_id"])],
            start_time=row["start_time"],
            end_time=row["end_time"],
            run_status=row["run_status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        session.add(obj)
        session.flush()
        gen_to_db[int(row["run_id"])] = obj.id
    return gen_to_db


def _bulk_insert_process_parameters(
    session: Session,
    df: pd.DataFrame,
    run_gen_to_db: dict[int, int],
) -> None:
    from app.models.run import ProcessParameter
    objs = []
    for _, row in df.iterrows():
        objs.append(ProcessParameter(
            run_id=run_gen_to_db[int(row["run_id"])],
            param_name=row["param_name"],
            value=float(row["value"]),
            unit=row["unit"],
            nominal=float(row["nominal"]) if row["nominal"] is not None else None,
            lsl=float(row["lsl"]) if row["lsl"] is not None else None,
            usl=float(row["usl"]) if row["usl"] is not None else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ))
    session.bulk_save_objects(objs)


def _bulk_insert_trace_data(
    session: Session,
    df: pd.DataFrame,
    run_gen_to_db: dict[int, int],
) -> None:
    from app.models.run import TraceData
    objs = []
    for _, row in df.iterrows():
        objs.append(TraceData(
            run_id=run_gen_to_db[int(row["run_id"])],
            timestamp=row["timestamp"],
            channel=row["channel"],
            value=float(row["value"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ))
    session.bulk_save_objects(objs)


def _bulk_insert_metrology(
    session: Session,
    df: pd.DataFrame,
    wafer_gen_to_db: dict[int, int],
) -> None:
    from app.models.metrology import Metrology
    objs = []
    for _, row in df.iterrows():
        objs.append(Metrology(
            wafer_id=wafer_gen_to_db[int(row["wafer_id"])],
            measurement_type=row["measurement_type"],
            site_index=int(row["site_index"]),
            value=float(row["value"]),
            unit=row["unit"],
            measured_at=row["measured_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ))
    session.bulk_save_objects(objs)


def _bulk_insert_defects(
    session: Session,
    df: pd.DataFrame,
    wafer_gen_to_db: dict[int, int],
) -> None:
    from app.models.defect import Defect
    objs = []
    for _, row in df.iterrows():
        objs.append(Defect(
            wafer_id=wafer_gen_to_db[int(row["wafer_id"])],
            x_coord=float(row["x_coord"]),
            y_coord=float(row["y_coord"]),
            size_um=float(row["size_um"]),
            defect_class=row["defect_class"],
            inspection_tool=row["inspection_tool"],
            inspected_at=row["inspected_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ))
    session.bulk_save_objects(objs)


def _bulk_insert_maintenance(
    session: Session,
    df: pd.DataFrame,
    chamber_name_to_db_id: dict[str, int],
    chambers_df: pd.DataFrame,
) -> None:
    from app.models.maintenance import MaintenanceEvent
    gen_cid_to_name = {int(r["chamber_id"]): r["name"] for _, r in chambers_df.iterrows()}
    objs = []
    for _, row in df.iterrows():
        cname = gen_cid_to_name[int(row["chamber_id"])]
        objs.append(MaintenanceEvent(
            chamber_id=chamber_name_to_db_id[cname],
            event_type=row["event_type"],
            performed_at=row["performed_at"],
            description=row["description"],
            performed_by=row["performed_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ))
    session.bulk_save_objects(objs)


def _bulk_insert_yield_results(
    session: Session,
    df: pd.DataFrame,
    wafer_gen_to_db: dict[int, int],
) -> None:
    from app.models.yield_result import YieldResult
    objs = []
    for _, row in df.iterrows():
        objs.append(YieldResult(
            wafer_id=wafer_gen_to_db[int(row["wafer_id"])],
            die_yield=float(row["die_yield"]),
            bin1_count=int(row["bin1_count"]),
            bin_fail_count=int(row["bin_fail_count"]),
            tested_at=row["tested_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ))
    session.bulk_save_objects(objs)


def seed(batch_size: int = 500) -> None:
    """
    Run the full seed pipeline.

    All inserts are wrapped in a single transaction.
    If any step fails the entire transaction is rolled back.
    """
    engine = get_engine()

    # Ensure schema exists
    import app.models  # noqa: F401 — registers all ORM models
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        if _already_seeded(session):
            log.info("Database already contains data — skipping seed (idempotent).")
            return

        log.info("Generating synthetic dataset (seed=%s)…", settings.seed)
        ds = generate_all(seed=settings.seed)

        log.info(f"  tools:       {len(ds.tools)}")
        log.info(f"  chambers:    {len(ds.chambers)}")
        log.info(f"  recipes:     {len(ds.recipes)}")
        log.info(f"  lots:        {len(ds.lots)}")
        log.info(f"  wafers:      {len(ds.wafers)}")
        log.info(f"  runs:        {len(ds.runs)}")
        log.info(f"  params:      {len(ds.process_parameters)}")
        log.info(f"  trace_data:  {len(ds.trace_data)}")
        log.info(f"  metrology:   {len(ds.metrology)}")
        log.info(f"  defects:     {len(ds.defects)}")
        log.info(f"  maintenance: {len(ds.maintenance_events)}")
        log.info(f"  yield:       {len(ds.yield_results)}")

        log.info("Inserting tools…")
        tool_map = _insert_tools(session, ds.tools)

        log.info("Inserting chambers…")
        chamber_map = _insert_chambers(session, ds.chambers, tool_map, ds.tools)

        log.info("Inserting recipes…")
        recipe_map = _insert_recipes(session, ds.recipes)

        log.info("Inserting lots…")
        lot_map = _insert_lots(session, ds.lots)

        log.info("Inserting wafers…")
        wafer_map = _insert_wafers(session, ds.wafers, lot_map)

        log.info("Inserting runs…")
        run_map = _insert_runs(session, ds.runs, wafer_map, chamber_map, recipe_map, ds.chambers)

        log.info("Inserting process parameters…")
        _bulk_insert_process_parameters(session, ds.process_parameters, run_map)

        log.info("Inserting trace data…")
        _bulk_insert_trace_data(session, ds.trace_data, run_map)

        log.info("Inserting metrology…")
        _bulk_insert_metrology(session, ds.metrology, wafer_map)

        log.info("Inserting defects…")
        _bulk_insert_defects(session, ds.defects, wafer_map)

        log.info("Inserting maintenance events…")
        _bulk_insert_maintenance(session, ds.maintenance_events, chamber_map, ds.chambers)

        log.info("Inserting yield results…")
        _bulk_insert_yield_results(session, ds.yield_results, wafer_map)

        session.commit()
        log.info("Seed complete.")


if __name__ == "__main__":
    seed()
