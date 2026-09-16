# Solution Overview

## What We Built

**Wafer Yield Root Cause & Defect Pattern Analyser** is a semiconductor manufacturing analytics control tower. It is purpose-built for process engineers, yield engineers, and manufacturing engineers who need to investigate yield excursions and pre-empt problematic lots.

This is NOT a chatbot, AI assistant, or LLM-backed system. All analytical outputs are produced by deterministic statistical and ML algorithms with traceable evidence IDs.

## Core Capability Map

| Capability | How it works | Screen |
|---|---|---|
| Fleet monitoring | MAD-based yield excursion detection, chamber recurrence scoring | Monitor |
| Lot investigation | Z-score parameter anomaly + yield deviation analysis | Investigate |
| Defect spatial analysis | Coordinate-based pattern classification (BFS clustering, PCA, angular entropy) | Wafer Pattern Lab |
| Pre-run risk scoring | GradientBoosting on whitelist-only features, leakage audit enforced | Pre-Run Risk |
| Root-cause ranking | 7-signal weighted evidence fusion, Top-3 candidates | Evidence |
| Engineer review | Human approval boundary with full audit trail | Actions / Review |

## The Analytics Pipeline

```
Synthetic Data Generator (seed=42)
  └─► PostgreSQL (raw tables, 700k+ rows)
        └─► FastAPI (ingestion layer — DataFrames)
              ├─► Yield Excursion Detector      → evidence IDs
              ├─► Parameter Anomaly Detector    → evidence IDs
              ├─► Defect Pattern Classifier     → evidence IDs
              ├─► Chamber Recurrence Analyser   → evidence IDs
              ├─► Temporal / Maintenance Analyser → evidence IDs
              ├─► Similar-Lot Finder            → evidence IDs
              └─► Root Cause Ranker             → Top-3 candidates
                    └─► Pre-Run Risk Scorer     → risk class + features
                          └─► React Dashboard
```

## Key Design Decisions

### Deterministic Root Cause Ranking

Root causes are ranked by evidence fusion — a weighted sum of 7 independently computed signal scores. No language model is involved. Each candidate carries:
- a `cause_type` from a controlled vocabulary
- a `score` and `confidence` (0–1 scale)
- `evidence_ids` linking to the specific records that contributed
- `supporting_signals` and `contradicting_signals`
- `model_version` and `generated_at` timestamp

The disclaimer "highest-ranked candidates based on available evidence — NOT confirmed causes" is enforced in the API schema.

### Pre-Run Safety Rule

The pre-run risk model is trained and scored using only a whitelist of features available before a lot physically starts. A `PRE_RUN_FEATURE_WHITELIST` constant is the single source of truth. An `audit_for_leakage()` function raises a hard error if any forbidden column (future yield, future defects, etc.) appears in the feature matrix. This is validated by automated tests.

### Human Approval Boundary

All corrective-action recommendations are advisory. An engineer must explicitly supply their reviewer ID, a decision (approve/reject), and optional rationale via `POST /api/actions/review`. The system never auto-approves. Reviews are stored with engineer ID, timestamp, and notes.

### Auditability

Every analytical result carries:
- `evidence_id` — deterministically generated UUID-style string
- `algorithm_version` — version string from `services/evidence.py`
- `generated_at` — UTC timestamp of computation

These allow any result to be reproduced and verified.
