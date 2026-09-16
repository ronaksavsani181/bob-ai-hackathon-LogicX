# Testing Strategy

## Overview

The project uses three test layers: backend unit/integration tests (pytest), frontend component tests (vitest + @testing-library/react), and TypeScript type checking (tsc).

## Backend Tests

**Framework:** pytest  
**Location:** [`src/backend/tests/`](../src/backend/tests/)  
**Database:** SQLite in-memory (no PostgreSQL required for tests)

### Test files

| File | Count | What it tests |
|---|---|---|
| `test_models.py` | 8 | ORM model instantiation, FK constraints, unique constraints, repr |
| `test_synthetic_data.py` | 50 | Generator output shape, scenario row counts, column presence, scenario stats |
| `test_analytics.py` | 42 | All 9 analytics services: excursion detection, parameter anomaly, defect patterns, chamber recurrence, temporal analysis, similar lots, root cause fusion, pre-run risk, leakage audit |

**Total: 100 tests**

### Running backend tests

```bash
cd src/backend
python -m pytest tests/ -v
```

### SQLite compatibility

The analytics services are tested against DataFrames generated directly from the synthetic data generator — not from the database. This means the SQLite test fixtures only need to test ORM correctness. The analytics tests run entirely in-memory without any DB dependency.

### Pre-run leakage test

`test_analytics.py::test_audit_for_leakage_raises_on_forbidden_column` verifies that passing a forbidden column (e.g. `die_yield`) to `audit_for_leakage()` raises a `ValueError`. This test enforces the pre-run safety rule.

## Frontend Tests

**Framework:** vitest + @testing-library/react  
**Location:** [`src/frontend/tests/`](../src/frontend/tests/)  
**Environment:** jsdom (no browser required)

### Test files

| File | Count | What it tests |
|---|---|---|
| `api.test.ts` | 13 | URL construction, pagination params, POST body, error handling |
| `Monitor.test.tsx` | 10 | KPI rendering, excursion table, chamber table, error state |

**Total: 23 tests**

### Running frontend tests

```bash
cd src/frontend
npm test
```

### API client tests

`api.test.ts` mocks `global.fetch` with `vi.stubGlobal` and verifies that each `api.*` method:
1. Calls the correct URL.
2. Includes the correct query parameters.
3. Uses the correct HTTP method for POST endpoints.
4. Throws on non-2xx responses.

No real network calls are made. All tests run in ~1 second.

## TypeScript Type Checking

```bash
cd src/frontend
npx tsc --noEmit
```

Runs in strict mode. Zero errors are required for a passing build.

## CI

The `.github/workflows/validate.yml` is provided by the hackathon organisers and should not be modified.

## What Is NOT Tested

| Gap | Reason | Impact |
|---|---|---|
| End-to-end API tests (`test_api.py`) | Requires live DB + seeded data | Medium — covered by unit tests of each service |
| Docker Compose integration | Docker not available locally | Low — compose config is straightforward |
| Cross-browser rendering | No Playwright/Cypress | Low — prototype only |
| Pre-run model performance metrics | No held-out real dataset | Low — synthetic data only |

## Acceptance Criteria for Submission

- [ ] `pytest tests/ -v` → 100/100 passing
- [ ] `npx vitest run tests/` → 23/23 passing
- [ ] `npx tsc --noEmit` → 0 errors
- [ ] `docker compose up` starts all services (requires Docker)
- [ ] `GET /api/health` returns `{"status": "ok"}`
- [ ] `GET /api/monitor/fleet-summary` returns fleet KPIs
- [ ] `POST /api/actions/review` records engineer decision
