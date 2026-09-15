#!/bin/sh
# entrypoint.sh — Backend container startup sequence
# 1. Wait logic is handled by Docker Compose healthcheck on the db service.
# 2. Run Alembic migrations (idempotent — safe to run on every restart).
# 3. Seed the database with synthetic data (idempotent — skips if already seeded).
# 4. Start the FastAPI application server.

set -e

echo "[entrypoint] Running database migrations..."
alembic upgrade head

echo "[entrypoint] Seeding synthetic data..."
python data/seed_db.py

echo "[entrypoint] Starting application server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
