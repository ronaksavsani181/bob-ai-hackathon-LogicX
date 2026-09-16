# Data Model

## Overview

The database has 17 tables representing the fab data genealogy from tool down to yield result. The primary key of every table is an integer `id`. Business-layer string keys (lot_id, chamber names) are separate columns.

## Entity Relationship

```
tools (1) ──► chambers (N)
                │
                └──► runs (N) ◄── wafers (N) ◄── lots (1)
                       │                │
                       └── process_parameters   ├── metrology
                       └── trace_data           └── defects
                                                └── yield_results

maintenance_events ── belongs to chamber

excursions ── belongs to lot
root_cause_candidates ── belongs to lot
pre_run_assessments ── belongs to lot
action_recommendations ── belongs to lot
action_reviews ── belongs to action_recommendation
```

## Table Descriptions

### `tools`
The physical process tool (e.g. ETCH-A, OVL-B, CVD-C).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| tool_id | String | Legacy equipment ID (e.g. "ETCH-01") |
| name | String | Human-readable name |
| tool_type | String | "etch", "litho", "cvd", "clean" |
| fab_area | String | Fab bay location |

### `chambers`
A process chamber within a tool. Multiple chambers per tool enable recurrence analysis.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| tool_id | Integer FK → tools.id | |
| chamber_id | String | Legacy ID (e.g. "CHA-1") |
| name | String | Human-readable name |

### `recipes`
Process recipe definitions. One recipe can be used across many runs.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| recipe_id | String | |
| name | String | |
| tool_type | String | Constrains which tool types can run this recipe |
| version | String | |

### `lots`
The primary fab scheduling unit. Each lot contains N wafers (typically 25).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | Used as FK in all child tables |
| lot_id | String | Business key, e.g. "L0042" |
| product | String | Product family |
| technology_node | String | "28nm", "14nm", etc. |
| priority | String | "low", "normal", "high" |
| status | String | "scheduled", "in_process", "completed", "on_hold" |
| planned_start_at | DateTime | Pre-run boundary for leakage enforcement |
| actual_start_at | DateTime | When lot physically started |

**Pre-run leakage boundary:** `planned_start_at` is the cutoff. Any feature derived from data timestamped AFTER this time is forbidden in the pre-run risk model.

### `wafers`
Individual wafers within a lot. Typically 25 per lot.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | Referenced as wafer_id in analytical code |
| lot_id | Integer FK → lots.id | |
| wafer_slot | Integer | 1–25 slot position in the lot carrier |
| die_count_total | Integer | Total die on the wafer |

### `runs`
A single process step — one wafer through one chamber using one recipe.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | Referenced as run_id in analytical code |
| wafer_id | Integer FK → wafers.id | |
| chamber_id | Integer FK → chambers.id | |
| recipe_id | Integer FK → recipes.id | |
| start_time | DateTime | |
| end_time | DateTime | |
| run_status | String | |

### `process_parameters`
Measured parameter values for a run. Multiple rows per run (one per parameter).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| run_id | Integer FK → runs.id | |
| param_name | String | e.g. "etch_rate_angs_min", "pressure_mtorr" |
| value | Float | Measured value |
| unit | String | |
| nominal | Float | Target value |
| lsl / usl | Float | Lower/upper spec limits |

### `trace_data`
Time-series sensor trace captured during a run.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| run_id | Integer FK | |
| timestamp | DateTime | Measurement time |
| channel | String | Sensor channel name |
| value | Float | |

### `metrology`
Post-process measurement results (CD, overlay, film thickness).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| wafer_id | Integer FK → wafers.id | |
| metric_name | String | e.g. "cd_nm", "overlay_error_nm" |
| value | Float | |
| unit | String | |
| measured_at | DateTime | |
| site_x / site_y | Float | Measurement site coordinates (mm) |

### `defects`
Individual defect records with wafer coordinates.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| wafer_id | Integer FK → wafers.id | |
| x_coord / y_coord | Float | Position in mm from wafer centre |
| defect_class | String | "particle", "scratch", "bridge", "void", "unknown" |
| inspected_at | DateTime | |

### `maintenance_events`
Maintenance history per chamber. Used in temporal proximity analysis.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| chamber_id | Integer FK → chambers.id | |
| event_type | String | "PM", "unscheduled_repair", "qualification" |
| performed_at | DateTime | |
| performed_by | String | Technician/engineer ID |
| description | String | |

### `yield_results`
Electrical test results per wafer.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| wafer_id | Integer FK → wafers.id | |
| die_yield | Float | Fraction [0.0, 1.0] |
| bin1_count | Integer | Passing die |
| bin_fail_count | Integer | Total failing die |
| tested_at | DateTime | |

### Analytics output tables

| Table | Purpose |
|---|---|
| `excursions` | Persisted yield excursion detections |
| `root_cause_candidates` | Persisted ranked root-cause outputs |
| `pre_run_assessments` | Pre-run risk scores |
| `action_recommendations` | System-generated corrective action suggestions |
| `action_reviews` | Engineer approval/rejection records |

## Column Naming Conventions (SQL ↔ DataFrame)

The `ingestion.py` module aliases DB column names to stable DataFrame column names used throughout the analytics services:

| DB column | DataFrame alias | Reason |
|---|---|---|
| `lots.id` | `lot_id` (integer) | FK join key for wafers, yields |
| `lots.lot_id` | `lot_id_str` | Human-readable business key |
| `wafers.id` | `wafer_id` | FK join key for runs, defects, metrology |
| `runs.id` | `run_id` | FK join key for process_parameters |
| `chambers.id` | `chamber_id` | |
| `maintenance_events.id` | `maint_id` | |
| `yield_results.id` | `yield_id` | |

This aliasing ensures that changes to the DB schema do not propagate beyond `ingestion.py`.
