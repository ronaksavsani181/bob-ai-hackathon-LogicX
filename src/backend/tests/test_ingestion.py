"""Regression tests for database-to-DataFrame ingestion helpers."""
from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from app.services import ingestion


def test_process_parameter_loader_uses_schema_primary_key(db: Session) -> None:
    """Return the process-parameter key under the stable ``pp_id`` alias."""
    result = ingestion.load_process_parameters(db)

    assert list(result.columns) == [
        "pp_id",
        "run_id",
        "param_name",
        "value",
        "unit",
        "nominal",
        "lsl",
        "usl",
    ]


def test_datetime_conversion_does_not_convert_queue_duration(db: Session) -> None:
    """Keep queue-duration fields separate from datetime values."""
    result = ingestion._query_df(
        db,
        "SELECT NULL AS queue_time_h, '2024-01-01T00:00:00Z' AS actual_start_at",
    )

    assert result.loc[0, "queue_time_h"] is None
    assert isinstance(result.loc[0, "actual_start_at"], pd.Timestamp)
