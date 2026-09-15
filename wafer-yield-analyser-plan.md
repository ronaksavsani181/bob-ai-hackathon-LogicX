# Wafer Yield Root Cause & Defect Pattern Analyser — Implementation Plan

## Top-Level Overview

**Goal:** Build a working, locally reproducible prototype for hackathon challenge S1.
The system is a semiconductor manufacturing analytics control-tower — NOT a chatbot.
It ingests synthetic fab-style data, runs deterministic analytics pipelines, surfaces
yield excursions, ranks root-cause candidates by evidence fusion, and flags pre-run
risk for upcoming lots — all presented to a process/yield engineer through a
purpose-built React dashboard.

**Approach:** Greenfield build, vertical-slice strategy.
A single complete data path (ingestion → analytics → API → UI) is prioritised over
breadth. Each sub-task produces a runnable, testable increment.

**Tech Stack:**
- Frontend: React 18 + TypeScript + Vite + TailwindCSS
- Backend: Python 3.11 + FastAPI + SQLAlchemy (async) + Alembic
- Analytics: pandas, NumPy, SciPy, scikit-learn
- Database: PostgreSQL 15 (via Docker Compose)
- Testing: pytest (backend), Vitest + React Testing Library (frontend)
- Containerisation: Docker Compose

**Non-goals (explicitly excluded):**
- Kafka, Spark, Kubernetes, vector databases, cloud infrastructure
- LLM root-cause generation
- Real proprietary fab data

---

## Architecture

### Component Map

```
Browser (React/Vite)
  └─ REST + JSON ──► FastAPI (uvicorn)
                        ├─ Routers (monitor / investigate / wafer / predict / evidence / actions)
                        ├─ Services (ingestion / analytics / root_cause / pre_run_risk)
                        │     └─ pandas / NumPy / scikit-learn
                        └─ SQLAlchemy ORM ──► PostgreSQL 15
                                                 └─ Alembic migrations
```

### Data Flow

```
Synthetic Data Generator (seed=42)
  └─► seed_db.py ──► PostgreSQL (raw tables)
                         └─► FastAPI analytics services
                                 ├─► yield excursion detector
                                 ├─► anomaly detector (IsolationForest / Z-score)
                                 ├─► defect spatial classifier (heuristics)
                                 ├─► historical similar-lot finder (cosine similarity)
                                 ├─► root-cause ranker (evidence fusion)
                                 └─► pre-run risk scorer (no future leakage)
                                         └─► API responses ──► React UI
```

### Human Approval Boundary

All corrective-action recommendations are advisory.
An engineer must explicitly approve/reject via the **Actions / Engineer Review** screen.
Approved actions are written to the `action_reviews` table with engineer ID, timestamp,
and rationale, forming a full audit trail.

---

## Repository Structure

```
/
├── submission.yaml
├── README.md
├── CONTRIBUTING.md
├── .gitignore
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── validate.yml          # provided by hackathon — do not modify
├── src/
│   ├── backend/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── alembic/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   │       └── 0001_initial_schema.py
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── tool.py
│   │   │   │   ├── lot.py
│   │   │   │   ├── wafer.py
│   │   │   │   ├── run.py
│   │   │   │   ├── defect.py
│   │   │   │   ├── metrology.py
│   │   │   │   ├── maintenance.py
│   │   │   │   └── yield_result.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── monitor.py
│   │   │   │   ├── investigate.py
│   │   │   │   ├── wafer.py
│   │   │   │   ├── predict.py
│   │   │   │   ├── evidence.py
│   │   │   │   └── actions.py
│   │   │   ├── routers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── monitor.py
│   │   │   │   ├── investigate.py
│   │   │   │   ├── wafer.py
│   │   │   │   ├── predict.py
│   │   │   │   ├── evidence.py
│   │   │   │   └── actions.py
│   │   │   └── services/
│   │   │       ├── __init__.py
│   │   │       ├── ingestion.py
│   │   │       ├── anomaly.py
│   │   │       ├── defect_pattern.py
│   │   │       ├── similar_lot.py
│   │   │       ├── root_cause.py
│   │   │       └── pre_run_risk.py
│   │   ├── data/
│   │   │   ├── seed_db.py
│   │   │   └── synthetic/
│   │   │       ├── generator.py
│   │   │       └── scenarios.py
│   │   └── tests/
│   │       ├── conftest.py
│   │       ├── test_synthetic_data.py
│   │       ├── test_anomaly.py
│   │       ├── test_defect_pattern.py
│   │       ├── test_root_cause.py
│   │       ├── test_pre_run_risk.py
│   │       └── test_api.py
│   └── frontend/
│       ├── Dockerfile
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── tailwind.config.ts
│       ├── index.html
│       ├── src/
│       │   ├── main.tsx
│       │   ├── App.tsx
│       │   ├── api/
│       │   │   └── client.ts
│       │   ├── types/
│       │   │   └── index.ts
│       │   ├── components/
│       │   │   ├── layout/
│       │   │   │   ├── Sidebar.tsx
│       │   │   │   └── TopBar.tsx
│       │   │   ├── charts/
│       │   │   │   ├── YieldTrendChart.tsx
│       │   │   │   ├── WaferMap.tsx
│       │   │   │   ├── ParamDeviation.tsx
│       │   │   │   └── EvidenceBar.tsx
│       │   │   └── shared/
│       │   │       ├── Badge.tsx
│       │   │       ├── Table.tsx
│       │   │       └── RiskChip.tsx
│       │   └── pages/
│       │       ├── Monitor.tsx
│       │       ├── Investigate.tsx
│       │       ├── WaferPatternLab.tsx
│       │       ├── Predict.tsx
│       │       ├── Evidence.tsx
│       │       └── Actions.tsx
│       └── tests/
│           ├── Monitor.test.tsx
│           └── api.test.ts
├── docs/
│   ├── problem-statement.md
│   ├── solution-overview.md
│   ├── architecture.md
│   ├── setup-guide.md
│   ├── data-model.md
│   ├── analytics-methodology.md
│   ├── root-cause-methodology.md
│   ├── pre-run-risk.md
│   ├── demo-scenarios.md
│   ├── testing-strategy.md
│   ├── limitations.md
│   └── bob-development.md
└── demo/
    └── demo-walkthrough.md
```

---

## Sub-Task 1 — Repository Skeleton, Tooling & Submission Files

**Status:** [x] done

**Intent:**
Establish the repository structure, top-level config files, Docker Compose,
and hackathon submission files so every subsequent sub-task has a stable home.

**Expected Outcomes:**
- All top-level directories and placeholder files exist
- `docker-compose.yml` defines `db`, `backend`, and `frontend` services
- `submission.yaml` follows the Bobathon template exactly
- `.gitignore` covers Python, Node, and Docker artifacts
- `README.md` contains project overview, quickstart, and screen descriptions
- `CONTRIBUTING.md` contains contribution guidelines
- Backend `pyproject.toml` declares all Python dependencies (pinned)
- Frontend `package.json` declares all JS/TS dependencies (pinned)

**Todo List:**
1. Create root `.gitignore`
2. Create `submission.yaml` (Bobathon template fields)
3. Create `README.md` (overview, quickstart, screens)
4. Create `CONTRIBUTING.md`
5. Create `docker-compose.yml` with `db` (postgres:15), `backend`, `frontend` services
   and a `backend-test` service for CI
6. Create `src/backend/Dockerfile` (python:3.11-slim, installs pyproject deps)
7. Create `src/backend/pyproject.toml` (fastapi, uvicorn, sqlalchemy, alembic,
   psycopg2-binary, pandas, numpy, scipy, scikit-learn, pydantic, pytest, httpx)
8. Create `src/frontend/Dockerfile` (node:20-alpine, vite build)
9. Create `src/frontend/package.json` (react 18, typescript, vite, tailwind,
   recharts, vitest, @testing-library/react)
10. Create `src/frontend/vite.config.ts` with proxy to backend
11. Create `src/frontend/tailwind.config.ts`
12. Create `src/frontend/tsconfig.json`
13. Create `src/frontend/index.html`
14. Create all `docs/` placeholder markdown files (content added in Sub-Task 11)
15. Create `demo/demo-walkthrough.md` placeholder

**Relevant Context:**
- No existing files to inherit from — pure greenfield
- Hackathon validation workflow must not be modified; leave `.github/workflows/validate.yml`
  as provided (it will be committed as-is if it already exists, or stubbed if not)

---

## Sub-Task 2 — Database Schema & Alembic Migration

**Status:** [x] done

**Intent:**
Define the full PostgreSQL domain model that captures the
`tool → chamber → lot → wafer → run → recipe → process parameters →
trace data → metrology → inspection/defect → maintenance → yield` relationship chain
with timestamps and genealogy preserved throughout.

**Expected Outcomes:**
- All ORM models defined with correct foreign keys and indexes
- Single Alembic migration `0001_initial_schema.py` creates all tables
- `alembic upgrade head` runs cleanly against a fresh database

**Database Tables (all have `created_at`, `updated_at` audit columns):**

| Table | Key Columns |
|---|---|
| `tools` | id, name, tool_type, fab_area |
| `chambers` | id, tool_id (FK), name, chamber_index |
| `recipes` | id, name, version, process_step, nominal_params (JSONB) |
| `lots` | id, lot_id (business key), product, technology_node, priority, planned_start_at, actual_start_at, status |
| `wafers` | id, lot_id (FK), wafer_slot, die_count_total |
| `runs` | id, wafer_id (FK), chamber_id (FK), recipe_id (FK), start_time, end_time, run_status |
| `process_parameters` | id, run_id (FK), param_name, value, unit, nominal, lsl, usl |
| `trace_data` | id, run_id (FK), timestamp, channel, value |
| `metrology` | id, wafer_id (FK), measurement_type, site_index, value, unit, measured_at |
| `defects` | id, wafer_id (FK), x_coord, y_coord, size_um, defect_class, inspection_tool, inspected_at |
| `maintenance_events` | id, chamber_id (FK), event_type, performed_at, description, performed_by |
| `yield_results` | id, wafer_id (FK), die_yield (float 0-1), bin1_count, bin_fail_count, tested_at |
| `excursions` | id, lot_id/wafer_id (FK, nullable), excursion_type, severity, detected_at, evidence (JSONB) |
| `root_cause_rankings` | id, excursion_id (FK), rank, cause, score, confidence, evidence_ids (JSONB), supporting_signals (JSONB), contradicting_signals (JSONB), model_name, model_version, produced_at |
| `pre_run_assessments` | id, lot_id (FK), risk_score, risk_label, feature_vector (JSONB), produced_at, features_used (JSONB) |
| `action_recommendations` | id, excursion_id (FK), action_text, priority, produced_at |
| `action_reviews` | id, recommendation_id (FK), engineer_id, decision (approve/reject/defer), rationale, reviewed_at |

**Todo List:**
1. Create `src/backend/app/database.py` (async engine + session factory, settings-driven URL)
2. Create `src/backend/app/config.py` (pydantic-settings, DATABASE_URL, SEED, environment)
3. Create `src/backend/app/models/__init__.py` and one file per table group:
   - `tool.py` — Tool, Chamber
   - `lot.py` — Lot
   - `wafer.py` — Wafer
   - `run.py` — Run, ProcessParameter, TraceData
   - `metrology.py` — Metrology
   - `defect.py` — Defect
   - `maintenance.py` — MaintenanceEvent
   - `yield_result.py` — YieldResult
   - `excursion.py` — Excursion
   - `root_cause.py` — RootCauseRanking
   - `pre_run.py` — PreRunAssessment
   - `action.py` — ActionRecommendation, ActionReview
4. Create `alembic.ini` and `alembic/env.py` pointing to the ORM metadata
5. Generate migration `alembic/versions/0001_initial_schema.py`
6. Verify migration runs against the Docker Compose `db` service

**Relevant Context:**
- All geometry columns (x_coord, y_coord) are FLOAT, not PostGIS — keep it simple
- JSONB columns hold evidence payloads; no separate evidence table needed for v1
- `excursion_id` is nullable on `root_cause_rankings` to allow stand-alone analysis

---

## Sub-Task 3 — Synthetic Data Generator

**Status:** [x] done

**Intent:**
Create a deterministic (seed=42) synthetic fab dataset covering all 7 required
scenarios with enough history (~180 days, ~500 lots, ~12,500 wafers) to make
analytics meaningful and demo-able.

**Expected Outcomes:**
- `generator.py` produces all tables in memory as pandas DataFrames
- `scenarios.py` encodes each named scenario's parameter deviations
- `seed_db.py` inserts all data into PostgreSQL idempotently
- Running `python seed_db.py` twice does not create duplicates
- Every scenario is traceable to specific lot IDs and chamber IDs

**Synthetic Scenario Definitions:**

| Scenario ID | Description | Injected Signal |
|---|---|---|
| S-ETCH | Etch drift | Chamber ETH-02 etch rate drifts +15% over 30 days (lots L300–L360) |
| S-OVL | Overlay excursion | Overlay metrology 3σ excursion on lots L200–L215, tool LIT-01 |
| S-PART | Particle excursion | Defect density spike (>50 defects/wafer) lots L400–L412, chamber CVD-03 |
| S-MAINT | Maintenance shift | Yield step-change after unscheduled PM on chamber ETH-02, day 120 |
| S-CHAM | Chamber recurrence | Yield 8% below fleet average for chamber CMP-02 across entire history |
| S-TIME | Temporal/cycle exposure | Lots with >72h queue time before etch show yield degradation |
| S-CTRL | Normal/control | Baseline lots — nominal parameters, normal defect density, expected yield |

**Data Volume Assumptions:**
- 6 tools × 2 chambers each = 12 chambers
- 500 lots × 25 wafers/lot = 12,500 wafers
- ~8 process parameters per run, ~5 metrology sites/wafer
- ~10 defects/wafer (baseline), up to 80 in particle scenario
- Maintenance events: 1/chamber/month on average + 2 unscheduled

**Wafer Defect Spatial Signatures (per scenario):**
- S-PART: center-heavy cluster (Gaussian at wafer centre r < 30mm)
- S-ETCH: edge/ring pattern (annular band 120 < r < 148mm)
- S-OVL: radial spoke pattern (angular bins 0°, 90°, 180°, 270°)
- S-CHAM: localized hotspot (fixed quadrant)
- S-CTRL: uniform random (Poisson spatial process)
- S-MAINT: line/scratch pattern (y = const ± 5mm)
- S-TIME: diffuse centre-heavy

**Todo List:**
1. Create `src/backend/data/synthetic/scenarios.py` — dataclass per scenario,
   parameters as typed fields, seed=42 documented
2. Create `src/backend/data/synthetic/generator.py`:
   - `generate_tools_chambers()` → DataFrame
   - `generate_recipes()` → DataFrame
   - `generate_lots_wafers()` → DataFrames with timestamps
   - `generate_runs_params()` — injects scenario deviations
   - `generate_trace_data()` — lightweight (1 channel, 10 points/run)
   - `generate_metrology()` — per-wafer, per-site
   - `generate_defects()` — spatial signatures per scenario
   - `generate_maintenance_events()` — including unscheduled PM
   - `generate_yield_results()` — yield correlated to scenario signals
3. Create `src/backend/data/seed_db.py`:
   - Calls generator, maps DataFrames to ORM objects, bulk inserts
   - Uses `INSERT ... ON CONFLICT DO NOTHING` or checks existence
4. Write `tests/test_synthetic_data.py`:
   - Assert row counts within expected ranges
   - Assert scenario lot IDs exist
   - Assert defect density elevated in S-PART lots
   - Assert yield degraded in scenario lots vs S-CTRL
   - Assert no data leakage: pre-run features only use pre-start columns

**Relevant Context:**
- Wafer radius = 150mm (300mm wafer halved for coordinate space)
- All random draws use `np.random.default_rng(seed=42)`
- Scenario deviations are additive offsets applied to otherwise normal distributions
- Timestamps use timezone-aware UTC datetimes

---

## Sub-Task 4 — Analytics Services

**Status:** [ ] pending

**Intent:**
Implement all backend analytics as pure Python services (no FastAPI dependency).
Each service is independently testable and returns typed Python structures.

**Services and Algorithms:**

### 4a. `anomaly.py` — Yield Excursion & Parameter Anomaly Detection
- **Yield excursion:** Rolling 5-lot window mean ± 3σ control chart per chamber.
  Flag lot if yield drops below (mean − 2.5σ). Return severity (mild/moderate/severe).
- **Parameter anomaly:** Z-score per parameter per chamber per recipe.
  |z| > 3 → flag. Return parameter name, z-score, direction, run_id.
- **Trace anomaly:** Not implemented in v1 (noted as limitation).

### 4b. `defect_pattern.py` — Wafer Defect Spatial Classifier
- Inputs: list of (x, y) defect coordinates for a wafer
- Algorithm: compute radial distribution, angular distribution, cluster statistics
  - center_ratio: fraction of defects with r < 40mm / total
  - edge_ratio: fraction with r > 120mm
  - cluster_score: DBSCAN eps=10mm, min_samples=3 → largest cluster fraction
  - radial_score: radial variance / total variance
  - scratch_score: PCA axis ratio (major/minor eigenvalue) on defect coordinates
- Rules (deterministic thresholds, documented):
  - center_ratio > 0.5 → "center-heavy"
  - edge_ratio > 0.4 → "edge-ring"
  - cluster_score > 0.6 and center_ratio < 0.3 → "localized-hotspot"
  - radial_score > 0.5 → "radial"
  - scratch_score > 5 → "scratch-line"
  - else → "uniform"
- Returns: pattern_label, confidence, feature_dict

### 4c. `similar_lot.py` — Historical Similar-Lot Finder
- Feature vector per lot: mean yield, defect density, mean overlay error,
  mean etch rate deviation, cycle time to etch, chamber ID one-hot (top 12)
- Normalise with StandardScaler fitted on all historical lots (excluding target)
- Cosine similarity → top-5 most similar historical lots
- Returns: list of (lot_id, similarity_score, scenario_label, yield)

### 4d. `root_cause.py` — Evidence-Based Root Cause Ranker
- Inputs: excursion record + anomaly results + similar lot results + defect patterns +
  maintenance proximity
- Evidence signals and weights:

| Signal | Weight |
|---|---|
| historical_association (similar lots same chamber) | 0.25 |
| anomaly_strength (max z-score) | 0.20 |
| temporal_precedence (maintenance within 7 days before) | 0.15 |
| chamber_recurrence (chamber below fleet mean >3 times) | 0.15 |
| defect_pattern_match (pattern consistent with cause hypothesis) | 0.10 |
| process_param_deviation (parameter OOC) | 0.10 |
| maintenance_proximity (within 30 days) | 0.05 |

- Candidate causes (deterministic enumeration, not LLM):
  - "Etch chamber drift" (triggers: etch param OOC + chamber recurrence)
  - "Overlay tool excursion" (triggers: overlay metrology OOC)
  - "Particle contamination" (triggers: high defect density + center pattern)
  - "Post-maintenance shift" (triggers: maintenance proximity + yield step)
  - "Chamber-specific systematic" (triggers: chamber recurrence alone)
  - "Queue-time exposure" (triggers: cycle time feature deviation)

- Score each candidate by summing weighted evidence signals
- Normalise to [0,1], return top-3
- Return schema per candidate:
  `{cause, score, confidence, evidence_ids, supporting_signals,
    contradicting_signals, model_name, model_version, produced_at}`
- `model_name = "evidence_fusion_v1"`, `model_version = "1.0.0"`

### 4e. `pre_run_risk.py` — Pre-Run Risk Scorer
- Leakage-prevention contract: ONLY features available before `lot.actual_start_at`:
  - lot priority, product type, technology node
  - planned recipe (from lot creation record)
  - planned chamber assignment (if known pre-run)
  - chamber historical yield (fleet average up to T-1 day)
  - chamber last maintenance gap (days since last PM, at planned_start_at)
  - historical chamber OOC rate (last 30 days before planned_start_at)
  - queue_time_planned (planned_start_at − previous_step_end_at, if available)
- Model: GradientBoostingClassifier (scikit-learn, random_state=42)
  trained on historical lots (label = 1 if final yield < 0.90 threshold)
- Outputs: risk_score (0–1), risk_label (low/medium/high), top-3 contributing features
  (SHAP-lite: permutation importance on test set, pre-computed)
- Leakage audit: unit test asserts no future column appears in feature_names

**Todo List:**
1. Create `src/backend/app/services/anomaly.py` with `detect_yield_excursions()`
   and `detect_parameter_anomalies()` functions
2. Create `src/backend/app/services/defect_pattern.py` with
   `classify_defect_pattern()` function
3. Create `src/backend/app/services/similar_lot.py` with
   `find_similar_lots()` function
4. Create `src/backend/app/services/root_cause.py` with
   `rank_root_causes()` function
5. Create `src/backend/app/services/pre_run_risk.py` with
   `score_pre_run_risk()` function and `train_risk_model()` helper
6. Write `tests/test_anomaly.py` — inject known excursion, assert detection
7. Write `tests/test_defect_pattern.py` — inject centre defects, assert "center-heavy"
8. Write `tests/test_root_cause.py` — construct synthetic evidence, assert top cause
9. Write `tests/test_pre_run_risk.py` — assert no future features, assert risk HIGH
   for S-ETCH lots

**Relevant Context:**
- All services receive DataFrames / SQLAlchemy query results as input
- No FastAPI import inside services — pure functions only
- Pre-run risk model is trained once at startup via lifespan event and cached in memory
- SHAP-lite uses permutation importance, not the `shap` library, to avoid extra deps

---

## Sub-Task 5 — FastAPI Backend & Typed API Contracts

**Status:** [ ] pending

**Intent:**
Wire the analytics services to HTTP endpoints with typed Pydantic request/response
schemas. All six UI screens map to a router.

**API Contracts:**

### Monitor — `/api/monitor`
```
GET /api/monitor/yield-trend
  Query: tool_id?, chamber_id?, days=30
  Response: YieldTrendResponse
    { points: [{lot_id, start_time, yield, chamber_id, is_excursion}] }

GET /api/monitor/excursions
  Query: severity?, days=7
  Response: ExcursionListResponse
    { excursions: [{id, lot_id, type, severity, detected_at, top_cause}] }

GET /api/monitor/kpis
  Response: KpiResponse
    { avg_yield_7d, avg_yield_30d, open_excursion_count,
      high_risk_upcoming_count, lots_in_flight }
```

### Investigate — `/api/investigate`
```
GET /api/investigate/lot/{lot_id}
  Response: LotDetailResponse
    { lot, wafers: [{wafer_id, yield, defect_count, pattern_label}],
      excursions, root_cause_ranking, similar_lots }

GET /api/investigate/lots
  Query: status?, product?, days=30, page=1, page_size=25
  Response: LotListResponse
    { lots: [{lot_id, product, status, yield, risk_label}], total }
```

### Wafer Pattern Lab — `/api/wafer`
```
GET /api/wafer/{wafer_id}/defects
  Response: WaferDefectResponse
    { wafer_id, defects: [{x, y, size_um, class}],
      pattern: {label, confidence, features} }

GET /api/wafer/{wafer_id}/metrology
  Response: WaferMetrologyResponse
    { wafer_id, sites: [{site_index, measurement_type, value, unit}] }
```

### Predict / Pre-Run Risk — `/api/predict`
```
GET /api/predict/upcoming
  Query: days_ahead=7
  Response: UpcomingRiskResponse
    { lots: [{lot_id, planned_start, risk_score, risk_label,
               top_features: [{name, importance, direction}]}] }

GET /api/predict/lot/{lot_id}/risk
  Response: LotRiskResponse
    { lot_id, risk_score, risk_label, features_used, produced_at,
      leakage_audit: {features_checked, passed} }
```

### Evidence — `/api/evidence`
```
GET /api/evidence/excursion/{excursion_id}
  Response: EvidenceDetailResponse
    { excursion, root_causes: [RootCauseCandidate x3],
      evidence_items: [{id, type, description, value, weight}] }
```

### Actions / Engineer Review — `/api/actions`
```
GET /api/actions/recommendations
  Query: status=pending, page=1
  Response: RecommendationListResponse

POST /api/actions/review/{recommendation_id}
  Body: ReviewRequest { engineer_id, decision, rationale }
  Response: ReviewResponse { id, status, reviewed_at }

GET /api/actions/audit
  Query: days=30
  Response: AuditResponse { reviews: [AuditEntry] }
```

**Todo List:**
1. Create `src/backend/app/main.py` — FastAPI app, CORS, lifespan (model training),
   router mounting, health endpoint `/api/health`
2. Create all Pydantic schemas in `src/backend/app/schemas/`
3. Create all routers in `src/backend/app/routers/` calling services via DB session
4. Create `src/backend/app/services/ingestion.py` — query helpers that load DataFrames
   from the DB for analytics services
5. Write `tests/test_api.py` — HTTP integration tests using `httpx.AsyncClient`
   covering at least: `/api/health`, `/api/monitor/kpis`, `/api/predict/upcoming`,
   `/api/actions/review/{id}` (approve + reject)
6. Verify OpenAPI docs auto-generated at `/docs`

**Relevant Context:**
- Use SQLAlchemy 2.x async style throughout
- All endpoints return `application/json`
- CORS origin = `http://localhost:5173` (Vite default)
- Pagination: `page` + `page_size` on list endpoints

---

## Sub-Task 6 — React Frontend — Shell & Navigation

**Status:** [ ] pending

**Intent:**
Build the React shell: routing, sidebar navigation, top bar, and the layout that
all six pages will inhabit. No page content yet.

**Expected Outcomes:**
- `npm run dev` starts Vite dev server on port 5173 with HMR
- Six routes render their page components without errors
- Sidebar shows active route highlighting
- TopBar shows system name and live KPI badge (open excursions count)
- TailwindCSS design system colours match semiconductor-industrial aesthetic
  (dark sidebar, neutral content area, accent amber/red for risk)
- TypeScript strict mode, no `any`

**Todo List:**
1. Create `src/frontend/src/main.tsx` — ReactDOM.createRoot, BrowserRouter
2. Create `src/frontend/src/App.tsx` — routes + layout shell
3. Create `src/frontend/src/api/client.ts` — typed axios/fetch wrapper, base URL from env
4. Create `src/frontend/src/types/index.ts` — TypeScript interfaces mirroring Pydantic schemas
5. Create `src/frontend/src/components/layout/Sidebar.tsx` — six nav items with icons
6. Create `src/frontend/src/components/layout/TopBar.tsx` — KPI badge, system title
7. Create shared components: `Badge.tsx`, `Table.tsx`, `RiskChip.tsx`
8. Create page stubs: all six `pages/*.tsx` (render headings only)
9. Write `tests/Monitor.test.tsx` — renders without crash (smoke test)

**Relevant Context:**
- Use `react-router-dom` v6 for routing
- Use `recharts` for all charts (already in package.json)
- TailwindCSS colour tokens: bg-slate-900 sidebar, bg-slate-50 content, red-600/amber-500 risk

---

## Sub-Task 7 — React Frontend — Monitor & Investigate Pages

**Status:** [ ] pending

**Intent:**
Implement the two highest-priority engineer-facing pages that give real-time
production visibility and drill-down investigation capability.

**Monitor Page:**
- KPI cards: Avg yield (7d), open excursions, high-risk upcoming, lots in-flight
- Yield trend chart (line chart, per-chamber, 30-day rolling, excursion markers)
- Excursion table: severity badge, lot ID, type, detected time, top cause link
- Auto-refresh every 30s (polling, no WebSocket)

**Investigate Page:**
- Lot search / filter bar (product, status, date range)
- Lot list table with yield sparkline, risk chip, click to drill-down
- Lot detail panel:
  - Wafer grid (25 cells, colour = yield heat)
  - Process parameter deviation bar chart (z-score per param)
  - Root cause ranking panel (top-3 candidates with score bars)
  - Similar lots table

**Todo List:**
1. Implement `pages/Monitor.tsx` — fetch `/api/monitor/kpis` and `/api/monitor/yield-trend`
   and `/api/monitor/excursions`; render KPI cards + chart + table
2. Create `components/charts/YieldTrendChart.tsx` — Recharts LineChart,
   custom dot renderer for excursion markers
3. Implement `pages/Investigate.tsx` — lot list + lot detail split panel
4. Create `components/charts/ParamDeviation.tsx` — Recharts BarChart horizontal,
   z-score coloured green/yellow/red

**Relevant Context:**
- All data fetched via `client.ts` — no direct fetch() calls in pages
- Error states and loading spinners required on every async call
- Lot detail uses React state (selected lot ID) not a separate route

---

## Sub-Task 8 — React Frontend — Wafer Pattern Lab, Predict, Evidence, Actions Pages

**Status:** [ ] pending

**Intent:**
Implement the remaining four pages.

**Wafer Pattern Lab:**
- Wafer map: SVG canvas 300px diameter, defect dots coloured by class
- Pattern label badge with confidence percentage
- Toggle between defect map and metrology heat map
- Lot/wafer selector dropdown

**Predict / Pre-Run Risk:**
- Upcoming lots table: planned start, risk score, risk label chip, top feature list
- Feature importance mini-bar per lot (top 3 features)
- Leakage audit badge (green "audit passed")
- Date range filter (default: next 7 days)

**Evidence:**
- Excursion selector
- Evidence card list: each card shows signal type, value, weight, direction
- Root cause candidate accordion: expand to see supporting + contradicting signals
- Model version and produced_at metadata displayed

**Actions / Engineer Review:**
- Pending recommendations table
- Per-recommendation: action text, priority badge, linked excursion
- Approve / Reject / Defer buttons → `POST /api/actions/review/{id}`
- Audit log tab: reviewed decisions, engineer ID, rationale, timestamp

**Todo List:**
1. Create `components/charts/WaferMap.tsx` — SVG defect map, pattern label overlay
2. Implement `pages/WaferPatternLab.tsx`
3. Implement `pages/Predict.tsx` — upcoming risk table + feature bar
4. Create `components/charts/EvidenceBar.tsx` — weighted evidence visualisation
5. Implement `pages/Evidence.tsx`
6. Implement `pages/Actions.tsx` — review form + audit tab

**Relevant Context:**
- WaferMap SVG uses viewBox="0 0 300 300", wafer circle cx=150 cy=150 r=148
- Defect coordinates from API are in mm (−150 to +150); scale to SVG pixels
- Actions page uses optimistic UI: button disables immediately after click

---

## Sub-Task 9 — Testing Suite

**Status:** [ ] pending

**Intent:**
Complete all tests across both layers to ensure analytics correctness,
API contract compliance, and UI render correctness.

**Backend Tests (`pytest`):**

| Test File | What it asserts |
|---|---|
| `test_synthetic_data.py` | Row counts, scenario lot presence, yield degradation by scenario, no future leakage in pre-run feature set |
| `test_anomaly.py` | Known excursion detected, severity correct, clean lots not flagged |
| `test_defect_pattern.py` | Center-heavy → "center-heavy", edge ring → "edge-ring", scratch → "scratch-line" |
| `test_root_cause.py` | Evidence fusion returns exactly 3 candidates, scores sum ≤ 1, particle scenario top cause = "Particle contamination" |
| `test_pre_run_risk.py` | No future-data columns in feature list, S-ETCH lots score HIGH risk, S-CTRL lots score LOW risk |
| `test_api.py` | HTTP 200 for all GET endpoints, 422 for bad input, 200 for review POST |

**Frontend Tests (Vitest):**

| Test File | What it asserts |
|---|---|
| `Monitor.test.tsx` | Renders without crash with mocked API response |
| `api.test.ts` | client.ts builds correct URL and handles 200/error |

**Todo List:**
1. Create `src/backend/tests/conftest.py` — pytest fixtures: in-memory SQLite engine,
   seeded test database, FastAPI TestClient
2. Complete all backend test files
3. Complete all frontend test files
4. Ensure `pytest` passes with zero failures
5. Ensure `npm run test` (vitest) passes with zero failures

**Relevant Context:**
- Backend tests use SQLite in-memory via test fixture (not Postgres) for speed
- Generator is deterministic — same seed always produces same test assertions
- Frontend tests use `msw` (mock service worker) or simple vi.mock for API calls

---

## Sub-Task 10 — Docker Compose Integration & Local Reproducibility

**Status:** [ ] pending

**Intent:**
Ensure that `docker compose up --build` starts the full stack, seeds the database,
and serves the UI — reproducibly, from a clean checkout.

**Expected Outcomes:**
- `docker compose up --build` produces a working system at `http://localhost:5173`
- Backend health check passes at `http://localhost:8000/api/health`
- Database seeding happens automatically on first startup
- Subsequent restarts do not re-seed (idempotent)
- `docker compose run backend-test pytest` runs all tests and exits 0

**Services in `docker-compose.yml`:**
```yaml
db:       postgres:15, port 5432, named volume
backend:  python:3.11-slim, port 8000, depends_on db healthcheck
frontend: node:20-alpine build → nginx:alpine serve, port 5173
backend-test: same image as backend, command: pytest, no port
```

**Todo List:**
1. Ensure `docker-compose.yml` has proper `healthcheck` for `db`
   (`pg_isready -U postgres`) so `backend` waits for DB ready
2. Add `entrypoint.sh` to backend: runs `alembic upgrade head`,
   then `python data/seed_db.py`, then starts `uvicorn`
3. Add `nginx.conf` to frontend container for SPA routing
4. Test clean checkout → `docker compose up --build` → all screens load
5. Document in `docs/setup-guide.md`

**Relevant Context:**
- Use `depends_on: db: condition: service_healthy` syntax
- Frontend build output goes to `/usr/share/nginx/html`
- Backend `DATABASE_URL` injected via environment variable in compose

---

## Sub-Task 11 — Documentation Suite

**Status:** [ ] pending

**Intent:**
Write all required documentation files to a level that a judge or engineer can
understand the system without reading code.

**Documents and Required Content:**

| File | Required Sections |
|---|---|
| `problem-statement.md` | Problem description, cost of yield loss, manual correlation pain, challenge statement |
| `solution-overview.md` | System summary, how it addresses each challenge point, key design decisions |
| `architecture.md` | Mermaid diagram, data flow, component responsibilities, DB/domain model, analytics pipeline, security considerations, scalability path, auditability, human approval boundary |
| `setup-guide.md` | Prerequisites, Docker Compose quickstart, manual setup, environment variables, seeding |
| `data-model.md` | Entity-relationship description, all tables, key relationships, JSONB fields |
| `analytics-methodology.md` | Excursion detection, anomaly scoring, defect pattern classification, similar-lot matching |
| `root-cause-methodology.md` | Evidence signals, weights, candidate enumeration, scoring formula, output schema, why no LLM |
| `pre-run-risk.md` | Feature set, leakage-prevention contract, model choice, training procedure, output schema |
| `demo-scenarios.md` | All 7 scenarios with lot IDs, expected detections, expected root cause, how to navigate UI |
| `testing-strategy.md` | Test pyramid, unit/integration/smoke, coverage targets, how to run |
| `limitations.md` | Prototype constraints, not production-certified, heuristic thresholds not validated, etc |
| `bob-development.md` | How Bob (IBM Bob) was used as SDLC agent, prompts used, plan-driven workflow |

**Todo List:**
1. Write all 12 documentation files
2. Ensure `docs/architecture.md` Mermaid diagram renders correctly in GitHub Markdown
3. Cross-link documents where relevant
4. Update `README.md` with accurate quickstart reflecting final implementation

---

## Database Schema Summary

```
tools (id PK, name, tool_type, fab_area)
  └─ chambers (id PK, tool_id FK, name, chamber_index)
       └─ runs (id PK, chamber_id FK, wafer_id FK, recipe_id FK, start_time, end_time)
            └─ process_parameters (id PK, run_id FK, param_name, value, nominal, lsl, usl)
            └─ trace_data (id PK, run_id FK, timestamp, channel, value)
       └─ maintenance_events (id PK, chamber_id FK, event_type, performed_at)

recipes (id PK, name, version, process_step, nominal_params JSONB)

lots (id PK, lot_id biz-key, product, technology_node, priority,
       planned_start_at, actual_start_at, status)
  └─ wafers (id PK, lot_id FK, wafer_slot, die_count_total)
       └─ runs (via wafer_id FK)
       └─ metrology (id PK, wafer_id FK, measurement_type, site_index, value)
       └─ defects (id PK, wafer_id FK, x_coord, y_coord, size_um, defect_class)
       └─ yield_results (id PK, wafer_id FK, die_yield, tested_at)
  └─ excursions (id PK, lot_id FK nullable, excursion_type, severity, evidence JSONB)
       └─ root_cause_rankings (id PK, excursion_id FK, rank, cause, score,
                                confidence, evidence_ids JSONB, produced_at)
       └─ action_recommendations (id PK, excursion_id FK, action_text, priority)
            └─ action_reviews (id PK, recommendation_id FK, engineer_id,
                               decision, rationale, reviewed_at)
  └─ pre_run_assessments (id PK, lot_id FK, risk_score, risk_label,
                          feature_vector JSONB, features_used JSONB, produced_at)
```

---

## Synthetic Data Design

### Volume Summary
- 12 chambers across 6 tools
- 500 lots, ~12,500 wafers
- ~100,000 process parameter records
- ~62,500 metrology measurements
- ~150,000 defect records (spikes in particle scenario)
- 180-day history window
- Deterministic seed=42 throughout

### Scenario Injection Points

Each scenario modifies specific columns in specific lots:

**S-ETCH:** `process_parameters.value` for `etch_rate` in `chamber_id = ETH-02`,
lots L300–L360. Value drifts from nominal 120 nm/min to 138 nm/min linearly.
`yield_results.die_yield` reduced by 0.02–0.08 proportional to drift magnitude.

**S-OVL:** `metrology.value` for `overlay_x` and `overlay_y`, lots L200–L215,
tool LIT-01. Values 3–4× nominal σ. Yield reduced 0.04–0.10.

**S-PART:** `defects` table — defect_count 60–80/wafer (vs 8–12 baseline),
spatial pattern = Gaussian centre cluster. Lots L400–L412, chamber CVD-03.
Yield reduced 0.10–0.20.

**S-MAINT:** `yield_results.die_yield` step change −0.06 after `maintenance_events`
unscheduled PM on ETH-02 at day 120. Pre-maintenance lots normal; post-maintenance
lots degraded for 15 lots, then recover.

**S-CHAM:** `yield_results.die_yield` systematically −0.08 for all wafers
on chamber CMP-02 across full history.

**S-TIME:** `lots.actual_start_at` − previous step end = >72h queue.
`yield_results.die_yield` reduced 0.03–0.06 for affected lots.

**S-CTRL:** All parameters within ±1σ nominal. Defects 8–12/wafer uniform random.
Yield 0.92–0.98.

---

## Analytics Algorithms

### Yield Excursion Detection
- Control chart: 30-lot rolling mean and σ per chamber
- Flag if current lot yield < (rolling_mean − 2.5 × rolling_std)
- Severity: mild (< −2.5σ), moderate (< −3σ), severe (< −4σ)
- Min window = 10 lots (no flag if insufficient history)

### Parameter Anomaly Scoring
- Z-score: z = (value − chamber_recipe_mean) / chamber_recipe_std
- Flag if |z| > 3.0
- Direction: "high" / "low"

### Defect Pattern Classification
- DBSCAN for cluster detection (eps=10mm, min_samples=3)
- Radial and angular histograms for ring/radial detection
- PCA axis ratio for scratch detection
- Thresholds are prototype heuristics (not fab-certified)

### Similar-Lot Matching
- Feature vector (10 dimensions): mean yield, defect density, overlay error,
  etch rate deviation, cycle time, chamber one-hot (top-5)
- StandardScaler normalisation
- Cosine similarity (not Euclidean — scale-invariant)
- Top-5 historical matches

### Root-Cause Evidence Fusion
- No LLM involvement. 100% deterministic weighted sum.
- Candidate causes enumerated from known fab failure modes
- Evidence signals from anomaly, defect, similar-lot, maintenance lookups
- Score = Σ(weight_i × signal_i) normalised
- Confidence = 1 − (score_2 / score_1) (separation ratio)
- Output frozen at analysis time, versioned

### Pre-Run Risk Model
- GradientBoostingClassifier (n_estimators=100, max_depth=3, random_state=42)
- Features: 8 pre-run-only columns (no future data)
- Label: yield < 0.90 threshold (binary classification)
- Train/test split: 80/20 on historical lots by time (no random split — time-ordered)
- Evaluation metric: ROC-AUC (target > 0.75 on synthetic data)
- Leakage test: column names asserted against whitelist at runtime

---

## Implementation Order

The sub-tasks must be executed in this order to avoid blocked dependencies:

```
1. Skeleton & Tooling
2. Database Schema
3. Synthetic Data Generator  ← depends on 2
4. Analytics Services        ← depends on 3
5. FastAPI Backend            ← depends on 4
6. React Shell                ← can start in parallel after 1
7. Monitor & Investigate      ← depends on 5 + 6
8. Remaining Pages            ← depends on 7
9. Testing Suite              ← depends on 4 + 5 + 6
10. Docker Compose Integration ← depends on all above
11. Documentation             ← depends on all above
```

---

## Acceptance Criteria

| Criteria | Test |
|---|---|
| `docker compose up --build` starts cleanly | Manual run, all containers healthy |
| `/api/health` returns 200 | pytest + curl |
| All 7 synthetic scenarios seeded | `test_synthetic_data.py` |
| Yield excursion detected in S-ETCH, S-PART, S-OVL, S-MAINT lots | `test_anomaly.py` |
| Defect pattern correctly classified for all 6 spatial types | `test_defect_pattern.py` |
| Root cause top-1 correct for each scenario | `test_root_cause.py` |
| Pre-run risk HIGH for scenario lots, LOW for S-CTRL | `test_pre_run_risk.py` |
| No future data in pre-run feature set | `test_pre_run_risk.py` leakage test |
| All 6 UI pages render without console errors | Vitest smoke tests |
| Engineer approve/reject action writes audit record | `test_api.py` |
| All pytest tests pass | CI / `pytest` |
| All vitest tests pass | CI / `npm run test` |
| OpenAPI schema auto-generated at `/docs` | Browser check |
| `submission.yaml` present and valid | Hackathon validation workflow |

---

## Risks and Limitations

| Risk | Mitigation |
|---|---|
| Synthetic data does not match real fab distributions | Documented in `limitations.md`; scenarios are illustrative, not calibrated |
| Defect classification thresholds are heuristic | Documented; labelled as prototype heuristics, not production-certified |
| Pre-run model trained on synthetic data only | Leakage test ensures contract is sound; real data would require retraining |
| Root-cause scoring weights are assumed, not empirically derived | Documented; weights are a starting point for domain expert calibration |
| PostgreSQL schema may need extension for real SEMI E142/E10 data | Documented in scalability section of architecture |
| GradientBoosting ROC-AUC may be modest on small synthetic dataset | ROC-AUC reported honestly; purpose is to demonstrate framework, not production accuracy |
| Browser SVG wafer map may be slow for >10,000 defects | Noted in limitations; v1 caps wafer defect display at 500 per wafer |

---

## Exact Files Created / Modified

### New Files — Root Level
- `submission.yaml`
- `README.md`
- `CONTRIBUTING.md`
- `.gitignore`
- `docker-compose.yml`

### New Files — `.github/`
- `.github/workflows/validate.yml` (stub / provided by hackathon)

### New Files — `src/backend/`
- `src/backend/Dockerfile`
- `src/backend/pyproject.toml`
- `src/backend/alembic.ini`
- `src/backend/alembic/env.py`
- `src/backend/alembic/versions/0001_initial_schema.py`
- `src/backend/app/main.py`
- `src/backend/app/config.py`
- `src/backend/app/database.py`
- `src/backend/app/models/__init__.py`
- `src/backend/app/models/tool.py`
- `src/backend/app/models/lot.py`
- `src/backend/app/models/wafer.py`
- `src/backend/app/models/run.py`
- `src/backend/app/models/metrology.py`
- `src/backend/app/models/defect.py`
- `src/backend/app/models/maintenance.py`
- `src/backend/app/models/yield_result.py`
- `src/backend/app/models/excursion.py`
- `src/backend/app/models/root_cause.py`
- `src/backend/app/models/pre_run.py`
- `src/backend/app/models/action.py`
- `src/backend/app/schemas/__init__.py`
- `src/backend/app/schemas/monitor.py`
- `src/backend/app/schemas/investigate.py`
- `src/backend/app/schemas/wafer.py`
- `src/backend/app/schemas/predict.py`
- `src/backend/app/schemas/evidence.py`
- `src/backend/app/schemas/actions.py`
- `src/backend/app/routers/__init__.py`
- `src/backend/app/routers/monitor.py`
- `src/backend/app/routers/investigate.py`
- `src/backend/app/routers/wafer.py`
- `src/backend/app/routers/predict.py`
- `src/backend/app/routers/evidence.py`
- `src/backend/app/routers/actions.py`
- `src/backend/app/services/__init__.py`
- `src/backend/app/services/ingestion.py`
- `src/backend/app/services/anomaly.py`
- `src/backend/app/services/defect_pattern.py`
- `src/backend/app/services/similar_lot.py`
- `src/backend/app/services/root_cause.py`
- `src/backend/app/services/pre_run_risk.py`
- `src/backend/data/seed_db.py`
- `src/backend/data/synthetic/generator.py`
- `src/backend/data/synthetic/scenarios.py`
- `src/backend/tests/conftest.py`
- `src/backend/tests/test_synthetic_data.py`
- `src/backend/tests/test_anomaly.py`
- `src/backend/tests/test_defect_pattern.py`
- `src/backend/tests/test_root_cause.py`
- `src/backend/tests/test_pre_run_risk.py`
- `src/backend/tests/test_api.py`

### New Files — `src/frontend/`
- `src/frontend/Dockerfile`
- `src/frontend/package.json`
- `src/frontend/tsconfig.json`
- `src/frontend/vite.config.ts`
- `src/frontend/tailwind.config.ts`
- `src/frontend/index.html`
- `src/frontend/nginx.conf`
- `src/frontend/src/main.tsx`
- `src/frontend/src/App.tsx`
- `src/frontend/src/api/client.ts`
- `src/frontend/src/types/index.ts`
- `src/frontend/src/components/layout/Sidebar.tsx`
- `src/frontend/src/components/layout/TopBar.tsx`
- `src/frontend/src/components/shared/Badge.tsx`
- `src/frontend/src/components/shared/Table.tsx`
- `src/frontend/src/components/shared/RiskChip.tsx`
- `src/frontend/src/components/charts/YieldTrendChart.tsx`
- `src/frontend/src/components/charts/WaferMap.tsx`
- `src/frontend/src/components/charts/ParamDeviation.tsx`
- `src/frontend/src/components/charts/EvidenceBar.tsx`
- `src/frontend/src/pages/Monitor.tsx`
- `src/frontend/src/pages/Investigate.tsx`
- `src/frontend/src/pages/WaferPatternLab.tsx`
- `src/frontend/src/pages/Predict.tsx`
- `src/frontend/src/pages/Evidence.tsx`
- `src/frontend/src/pages/Actions.tsx`
- `src/frontend/tests/Monitor.test.tsx`
- `src/frontend/tests/api.test.ts`

### New Files — `docs/`
- `docs/problem-statement.md`
- `docs/solution-overview.md`
- `docs/architecture.md`
- `docs/setup-guide.md`
- `docs/data-model.md`
- `docs/analytics-methodology.md`
- `docs/root-cause-methodology.md`
- `docs/pre-run-risk.md`
- `docs/demo-scenarios.md`
- `docs/testing-strategy.md`
- `docs/limitations.md`
- `docs/bob-development.md`

### New Files — `demo/`
- `demo/demo-walkthrough.md`

**Total new files: ~85**
