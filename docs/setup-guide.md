# Setup Guide

This guide starts the Wafer Yield Root Cause & Defect Pattern Analyser locally on Windows PowerShell or with Docker Desktop. The backend is a FastAPI application backed by SQLite for local development or PostgreSQL in Docker. It seeds deterministic, synthetic demonstration data only.

## What starts where

| Service | Local address | Purpose |
|---|---|---|
| FastAPI backend | `http://127.0.0.1:8000` | REST API and OpenAPI documentation |
| React/Vite frontend | `http://127.0.0.1:5173` | Dashboard during local development |
| PostgreSQL | `localhost:5432` | Docker-only persistent database |

The local Vite development server proxies `/api` requests to port `8000`. The Docker frontend uses Nginx to proxy `/api` to the backend container. Leave `VITE_API_URL` unset unless the API runs on another host.

## Fresh clone on any Windows PC

Open PowerShell in the folder where you keep projects, then clone the repository and enter it:

```powershell
git clone https://github.com/ronaksavsani181/bob-ai-hackathon-LogicX.git
Set-Location .\bob-ai-hackathon-LogicX
git status --short
```

`git status --short` should print nothing immediately after a clone. Continue with the native setup below. Do not copy `node_modules`, `.venv`, or any `*.db` file from another PC: the commands below create the compatible local dependencies and synthetic database.

## Prerequisites

| Tool | Supported version | Required for |
|---|---|---|
| Python | 3.11 through 3.14 | Backend and tests |
| Node.js | 20 or later | Frontend |
| npm | Bundled with Node.js | Frontend dependencies |
| Docker Desktop + Docker Compose v2 | Current stable | Optional full-stack Docker setup |

Check the installed tools from the repository root:

```powershell
python --version
py -0p
node --version
npm --version
docker version
docker compose version
```

If `py -0p` does not list Python 3.11 through 3.14, install one of those versions before continuing. If `docker` is not found, use the native setup below or install and start Docker Desktop.

## Recommended: native Windows setup

Use two PowerShell terminals. This path needs no Docker or PostgreSQL installation.

### 1. Create and install the backend environment

In the first terminal, from the repository root:

```powershell
Set-Location .\src\backend

# Use the installed supported Python version. This project was verified with Python 3.14.
py -3.14 -m venv .venv

# Calling the venv interpreter directly avoids PowerShell execution-policy issues.
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

If your supported interpreter is, for example, Python 3.12, replace `py -3.14` with `py -3.12` in the virtual-environment command. Do not use a global `pip`; always run `python -m pip` through `.venv`.

### 2. Configure and prepare the local database

Set the values for the current terminal, apply the schema migration, then seed the data:

```powershell
$env:DATABASE_URL = "sqlite:///./wafer_yield.db"
$env:ENVIRONMENT = "development"
$env:SEED = "42"

.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe data\seed_db.py
```

The seed is idempotent: after a successful first run it detects existing data and exits without duplicates. Initial generation and loading can take several minutes because it produces the complete synthetic analytics dataset. The generated `wafer_yield.db` is intentionally ignored by Git.

### 3. Start and verify the backend

Keep the same terminal and environment variables, then run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Leave that process running. In a second terminal, verify it:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/monitor/fleet-summary
Start-Process http://127.0.0.1:8000/api/docs
```

The health response must contain `"status": "ok"`. If it does not, read the backend terminal output before starting the frontend.

### 4. Start the frontend

In the second terminal, from the repository root:

```powershell
Set-Location .\src\frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend will use the Vite proxy to reach the backend; no frontend `.env` file is needed for this standard local setup.

## Docker full-stack setup

Use this path only after Docker Desktop is running. Docker provisions PostgreSQL, runs the migration and idempotent seed automatically, starts FastAPI, and serves the built frontend.

From the repository root:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --follow backend
```

Wait for the backend log line that indicates Uvicorn has started, then open:

```powershell
Start-Process http://localhost:5173
Start-Process http://localhost:8000/api/docs
Invoke-RestMethod http://localhost:8000/api/health
```

Do not run `python data/seed_db.py` manually inside the Docker backend after `docker compose up`; `src/backend/entrypoint.sh` already runs the migration and seed. To stop the stack while preserving the PostgreSQL volume:

```powershell
docker compose down
```

## Configuration

The backend reads environment variables or an optional `src/backend/.env` file. `.env` files and local databases are ignored by Git.

| Variable | Local value | Docker value | Meaning |
|---|---|---|---|
| `DATABASE_URL` | `sqlite:///./wafer_yield.db` | `postgresql+psycopg://logicx:logicx@db:5432/wafer_yield` | SQLAlchemy connection URL |
| `ENVIRONMENT` | `development` | `production` | Runtime label; tests set `test` |
| `SEED` | `42` | `42` | Deterministic synthetic-data seed used on first seed |
| `VITE_API_URL` | unset | unset | Optional frontend API override; normally unnecessary |

For a locally managed PostgreSQL database, use the `psycopg` SQLAlchemy dialect, for example:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://<user>:<password>@127.0.0.1:5432/wafer_yield"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe data\seed_db.py
```

## Run tests and checks

Run the backend tests from `src/backend` after dependencies are installed:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v --tb=short
```

Run frontend checks from `src/frontend`:

```powershell
npm ci
npm run lint
npm run test
```

With Docker Desktop, the isolated backend test service uses an in-memory SQLite database:

```powershell
docker compose --profile test run --rm backend-test
```

## Reset synthetic data

These commands permanently delete only the generated development data. Stop the running backend first.

### Local SQLite reset

From `src/backend`:

```powershell
Remove-Item -LiteralPath .\wafer_yield.db -Force
Remove-Item -LiteralPath .\wafer_yield.db-shm -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath .\wafer_yield.db-wal -Force -ErrorAction SilentlyContinue

$env:DATABASE_URL = "sqlite:///./wafer_yield.db"
$env:ENVIRONMENT = "development"
$env:SEED = "42"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe data\seed_db.py
```

### Docker PostgreSQL reset

From the repository root, this removes the named PostgreSQL volume and all Docker database data:

```powershell
docker compose down -v
docker compose up --build -d
docker compose logs --follow backend
```

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `docker` is not recognized | Docker Desktop is not installed or running. Use the native setup, or install Docker Desktop and restart PowerShell. |
| `No module named fastapi` or `pytest` | The virtual environment has not been installed, or the wrong interpreter is being used. Run `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`. |
| `pg_config executable not found` | A stale environment is attempting to install the retired `psycopg2` driver. Recreate `.venv` and install the current project dependencies, which use prebuilt `psycopg` binaries. |
| `Address already in use` on port 8000 or 5173 | Find the owner with `Get-NetTCPConnection -LocalPort 8000` or `Get-NetTCPConnection -LocalPort 5173`, stop that process, or select another port. |
| Frontend displays an API error | Confirm `Invoke-RestMethod http://127.0.0.1:8000/api/health` succeeds before running Vite. Keep `VITE_API_URL` unset for local development. |
| `database is locked` | Stop all backend processes using the same SQLite file, then start one backend instance. Do not seed while the application is writing. |
| Seed feels slow | The dataset intentionally contains a large set of deterministic wafer, trace, defect, and process records. Let the initial seed complete; later seed calls are idempotent and quick. |

## Clean shutdown

Press `Ctrl+C` in the terminal running Uvicorn and Vite. For Docker, use `docker compose down`. Both approaches preserve locally generated data unless you explicitly run one of the reset procedures above.
