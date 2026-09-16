# Bob Development Log

This document describes how IBM Bob was used as the development and SDLC agent throughout the construction of this prototype.

**Important:** IBM Bob was the development tool. Bob did NOT contribute to the runtime analytics pipeline. Bob was NOT used to generate root causes, predict yield, or classify defects at runtime. All analytical code is deterministic Python.

## What Bob Did

### Planning Phase

Bob was used to produce the full implementation plan (`wafer-yield-analyser-plan.md`) including:
- Architecture diagram and component map
- Repository structure
- Database schema
- Synthetic data design with 7 documented scenarios
- Analytics algorithm specifications
- API contract definitions
- UI screen specifications
- Testing strategy
- Risk identification

### Implementation Phase

Bob executed the following development sub-tasks under human engineering direction:

1. **Repository Skeleton** — created all top-level files, Docker Compose, Dockerfiles, and submission metadata.
2. **Database Schema** — designed and implemented 17 ORM models with SQLAlchemy, Alembic migration, and a JSONB/SQLite-compatible column adapter.
3. **Synthetic Data Generator** — wrote `scenarios.py` (7 documented scenarios), `generator.py` (deterministic seed=42, 700k+ rows), and `seed_db.py` (idempotent DB seeder).
4. **Analytics Services** — implemented 9 service files: anomaly detection, defect pattern classification, chamber recurrence, temporal analysis, similar-lot matching, root-cause fusion, pre-run risk scoring, evidence types.
5. **FastAPI Routers** — implemented 4 routers covering 17 REST endpoints with typed Pydantic schemas.
6. **React Frontend** — implemented all 6 screens, shared component library, typed API client, and SVG yield trend chart.
7. **Bug Fixes** — identified and fixed SQL column aliasing mismatches in `ingestion.py` (3 blockers) by comparing ORM models against SQL queries.
8. **Testing** — wrote 23 frontend tests (vitest/RTL) and verified all 100 backend tests remain passing.
9. **Documentation** — wrote all 12 documentation files.

### Quality Assurance

Bob ran the following checks after each implementation step:
- `pytest tests/ -v` — backend test suite
- `npx tsc --noEmit` — TypeScript strict type checking
- `npx vitest run tests/` — frontend test suite
- `python -c "from app.main import app; ..."` — import smoke test

### Engineering Decisions Made by Human Engineers

The following decisions were made by the human engineer and communicated as constraints to Bob:

- No LLM for root cause (absolute rule)
- Pre-run feature whitelist definition
- Cause type vocabulary
- Evidence fusion weights
- SQLite for test compatibility (no Docker on dev machine)
- pyproject.toml build backend selection (`setuptools.build_meta`)
- FastAPI version pinning (0.115.5 due to starlette compatibility)

## What Bob Did NOT Do

- Bob did not invent or hallucinate analytics results
- Bob did not write any LLM inference code
- Bob did not bypass the pre-run leakage audit
- Bob did not generate synthetic data that claims to represent real fabs
- Bob did not modify the `.github/workflows/validate.yml` provided by the hackathon organisers
