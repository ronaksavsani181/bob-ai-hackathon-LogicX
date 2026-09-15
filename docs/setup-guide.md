# Setup Guide

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Backend + analytics |
| Node.js | 20+ | Frontend build |
| npm | 9+ | Frontend dependencies |
| Docker + Compose | 24+ | Full-stack run (optional for local) |
| PostgreSQL | 15+ | Database (Docker handles this) |

---

## Quick Start (Docker Compose)

```bash
# Clone and enter the repository
git clone <repo-url>
cd bob-ai-hackathon-LogicX

# Start all services (DB, backend, frontend)
docker compose up --build

# Seed the database with synthetic data
docker compose exec backend python data/seed_db.py

# Open the UI
open http://localhost:5173
# API docs
open http://localhost:8000/api/docs
```

---

## Local Development (no Docker)

### Backend

```bash
cd src/backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set environment variables
export DATABASE_URL="postgresql+psycopg2://logicx:logicx@localhost:5432/wafer_yield"
export SEED=42

# Run Alembic migrations
alembic upgrade head

# Seed the database
python data/seed_db.py

# Start the backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd src/frontend

# Install dependencies
npm install

# Start dev server (proxies /api to localhost:8000)
npm run dev

# Open browser
open http://localhost:5173
```

---

## Running Tests

### Backend tests (pytest)

```bash
cd src/backend
python -m pytest tests/ -v
```

Tests use SQLite in-memory; no PostgreSQL connection required.

Expected: **100 tests pass** in ~4 minutes.

### Frontend TypeScript check

```bash
cd src/frontend
node node_modules/typescript/bin/tsc --noEmit
```

Expected: no errors.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./test.db` | SQLAlchemy DB URL |
| `SEED` | `42` | Deterministic data generation seed |
| `VITE_API_URL` | `http://localhost:8000` | Backend URL for the React app |

---

## Database Schema Migrations

```bash
# Apply all migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Generate new migration (after model change)
alembic revision --autogenerate -m "description"
```

---

## Resetting Synthetic Data

```bash
# Drop and recreate (destroys all data)
alembic downgrade base
alembic upgrade head
python data/seed_db.py
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: psycopg2` | Tests use SQLite; for live DB install `psycopg2-binary` |
| `tsc not found` | Run via `node node_modules/typescript/bin/tsc` |
| Frontend shows "API Error" | Confirm backend is running on port 8000; check CORS |
| Seed takes too long | Normal — 735K rows take ~60s; run once then leave DB up |
