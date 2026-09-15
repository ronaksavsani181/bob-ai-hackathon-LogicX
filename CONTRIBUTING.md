# Contributing to Wafer Yield Root Cause & Defect Pattern Analyser

Team LogicX — Hackathon Challenge S1

---

## Branch Strategy

| Branch | Purpose |
|---|---|
| `main` | Stable, deployable state — all tests must pass |
| `feature/<short-description>` | New feature or sub-task implementation |
| `fix/<short-description>` | Bug fixes |

Open a pull request against `main`. Merge only when all CI checks pass.

---

## Pull Request Checklist

Before requesting review, confirm:

- [ ] All `pytest` tests pass: `docker compose run --rm backend-test`
- [ ] All Vitest tests pass: `npm run test` inside `src/frontend/`
- [ ] No `any` types introduced in TypeScript (strict mode enforced)
- [ ] New analytics logic has a corresponding unit test
- [ ] `pyproject.toml` / `package.json` updated if new dependencies added
- [ ] Documentation updated if public API or behaviour changed
- [ ] No future-data columns added to pre-run risk feature set

---

## Running Tests Locally

### Backend (Python / pytest)

```bash
# With Docker (recommended)
docker compose run --rm backend-test

# Without Docker
cd src/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest tests/
```

### Frontend (TypeScript / Vitest)

```bash
cd src/frontend
npm install
npm run test
```

---

## Code Style

### Python
- Follow PEP 8.
- Use type annotations on all function signatures.
- Keep services as pure functions — no FastAPI imports inside `app/services/`.
- Use `np.random.default_rng(seed=42)` for all random draws in synthetic data.

### TypeScript / React
- Strict TypeScript (`"strict": true` in `tsconfig.json`).
- No `any` types.
- All API calls go through `src/api/client.ts` — no direct `fetch()` in page components.
- Loading and error states required on every async data fetch.

---

## Adding a New Dependency

### Python
Add to `[project.dependencies]` in `src/backend/pyproject.toml` with a pinned version range.
Run `pip install -e .` to update your local environment.

### JavaScript / TypeScript
Add to `dependencies` or `devDependencies` in `src/frontend/package.json` with a pinned version.
Run `npm install` to update `package-lock.json`. Commit both files.

---

## Synthetic Data

Do not add proprietary or real fab data.
All synthetic scenarios are defined in `src/backend/data/synthetic/scenarios.py`.
Use `seed=42` for all random number generation to keep the dataset deterministic.

---

## Analytics Rules (non-negotiable)

1. **No LLM root causes.** Root-cause ranking must use only deterministic/statistical evidence fusion.
2. **No future data in pre-run risk.** Features must only use information available before `lot.actual_start_at`. Add a unit test for any new feature.
3. **Human approval boundary.** No automated action may be taken without engineer review via the Actions screen.
