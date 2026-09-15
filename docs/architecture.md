# Architecture

## Overview

```
React Frontend (Vite/TypeScript)
         │  HTTP/JSON
         ▼
FastAPI Backend (Python 3.11+)
         │  SQLAlchemy
         ▼
PostgreSQL 15
```

The system is a single-process analytics control tower.  No microservices, no message queues, no cloud dependencies.

---

## Mermaid Architecture Diagram

```mermaid
graph TB
    subgraph "Browser — React/TypeScript"
        UI_MON[Monitor Screen]
        UI_INV[Investigate Screen]
        UI_WAF[Wafer Pattern Lab]
        UI_PRE[Pre-Run Risk Screen]
        UI_EVI[Evidence Screen]
        UI_ACT[Actions / Review Screen]
    end

    subgraph "FastAPI Backend"
        R_LOT[/api/lots router]
        R_MON[/api/monitor router]
        R_PRE[/api/pre-run router]
        R_HLT[/api/health]

        subgraph "Analytics Services"
            SVC_ANO[anomaly.py — yield excursion + param anomaly]
            SVC_DEF[defect_pattern.py — spatial classifier]
            SVC_SIM[similar_lot.py — cosine similarity]
            SVC_REC[recurrence.py — chamber recurrence]
            SVC_TEM[temporal.py — precedence + maint proximity]
            SVC_RC[root_cause.py — evidence fusion TOP-3]
            SVC_PRE[pre_run_risk.py — GBM risk model]
            SVC_ING[ingestion.py — DB → DataFrame]
        end
    end

    subgraph "Data Layer"
        DB[(PostgreSQL 15)]
        ALM[Alembic migrations]
        SEED[seed_db.py — synthetic data]
    end

    UI_MON & UI_INV & UI_WAF & UI_PRE & UI_EVI & UI_ACT --> R_LOT & R_MON & R_PRE
    R_LOT & R_MON & R_PRE --> SVC_ANO & SVC_DEF & SVC_SIM & SVC_REC & SVC_TEM & SVC_RC & SVC_PRE
    SVC_ING --> DB
    SVC_ANO & SVC_DEF & SVC_SIM & SVC_REC & SVC_TEM & SVC_RC & SVC_PRE --> SVC_ING
    SEED --> DB
    ALM --> DB
```

---

## Data Flow

```
Synthetic fab data (seed_db.py)
    │ bulk insert
    ▼
PostgreSQL (17 tables)
    │ ingestion.py — SQL → DataFrame
    ▼
Analytics pipeline (per lot request):
    ├─ anomaly.py       → YieldExcursionResult, ParameterAnomalyResult
    ├─ defect_pattern.py→ DefectPatternResult (per wafer)
    ├─ recurrence.py    → ChamberRecurrenceResult (per chamber)
    ├─ similar_lot.py   → SimilarLotResult (top-K)
    ├─ temporal.py      → TemporalPrecedenceResult, MaintenanceProximityResult
    └─ root_cause.py    → RootCauseFusionResult (Top-3 candidates)
                              │
                              ▼
                     FastAPI → Pydantic schema → JSON response
                              │
                              ▼
                     React component renders result
```

---

## Component Responsibilities

| Component | Responsibility |
|---|---|
| `seed_db.py` | Generate and bulk-insert deterministic synthetic data (seed=42) |
| `ingestion.py` | Execute SQL and return typed DataFrames; the only DB-aware analytics file |
| `anomaly.py` | Yield excursion (median/MAD), process parameter z-score anomaly |
| `defect_pattern.py` | Wafer defect spatial classification (DBSCAN, PCA, angular entropy) |
| `similar_lot.py` | StandardScaler + cosine similarity; find K most similar historical lots |
| `recurrence.py` | Chamber systematic yield deficit (tanh-normalised gap score) |
| `temporal.py` | Temporal precedence check + maintenance proximity yield shift |
| `root_cause.py` | Deterministic weighted evidence fusion → Top-3 root-cause candidates |
| `pre_run_risk.py` | GradientBoostingClassifier on whitelist-only features; leakage audit |
| FastAPI routers | Orchestrate analytics pipeline; produce Pydantic-typed responses |
| React screens | Render results; no analytics logic in the frontend |

---

## Database / Domain Model

17 ORM tables:

```
tools (6)
  └─ chambers (12)
       └─ runs ──────────────── recipes
            └─ process_parameters
            └─ trace_data
            └─ wafers ─────────── lots
                 └─ metrology
                 └─ defects
                 └─ yield_results
maintenance_events → chambers
excursions (analytics output)
root_cause_rankings (analytics output)
pre_run_assessments (analytics output)
action_recommendations
action_reviews
```

See [`docs/data-model.md`](data-model.md) for full column definitions.

---

## Analytics Pipeline

```
For a target lot:
 1. Load historical DataFrames via ingestion.py
 2. detect_yield_excursion()        → severity + sigma
 3. detect_parameter_anomalies()    → z-scored OOC params
 4. classify_lot_defect_patterns()  → spatial pattern per wafer
 5. analyze_chamber_recurrence()    → fleet-vs-chamber gap
 6. analyze_maintenance_proximity() → pre/post PM yield shift
 7. find_similar_lots()             → cosine-similar history
 8. rank_root_causes()              → fuse all signals → Top-3
```

Every result carries: `evidence_id`, `algorithm_version`, `generated_at`.

---

## Security Considerations

- No authentication in the prototype (add OAuth2/JWT for production)
- No PII in synthetic data
- CORS restricted to known frontend origins
- No SQL injection exposure (parameterised queries via SQLAlchemy)
- No LLM API keys anywhere in the system

---

## Scalability Path

| Concern | Prototype approach | Production path |
|---|---|---|
| Data volume | 735K rows in-memory | TimescaleDB partitions, materialized views |
| Analytics latency | On-request computation | Pre-computed excursion table, async job queue |
| Multi-tenant | Single fab | Row-level security + fab_id FK |
| Model retraining | Per-request training | Scheduled job, model registry |

---

## Auditability

Every analytical result carries:
- `evidence_id` — stable, deterministic SHA-256 hash of source entity + feature
- `algorithm_version` — version string (e.g. `yield_excursion_v1`)
- `generated_at` — UTC timestamp

Root-cause output carries an explicit disclaimer:
> "Results represent the highest-ranked candidates based on available evidence. These are not confirmed causes. Engineering review is required before action."

---

## Human Approval Boundary

The `action_reviews` table and `ActionsScreen.tsx` enforce an explicit engineer approval step:
- Every recommendation starts as `status = 'pending'`
- Requires a named reviewer before `approved` or `rejected`
- State machine: `pending → acknowledged → approved | rejected → completed`
- No action is taken automatically; the system only recommends

---

## Pre-Run Safety Boundary

`PRE_RUN_FEATURE_WHITELIST` in `pre_run_risk.py` and `scenarios.py` defines the only columns permitted as model inputs.  `audit_for_leakage()` raises `ValueError` at both training and inference time if any forbidden column is present.  This is tested in `tests/test_analytics.py::TestPreRunLeakageAudit`.
