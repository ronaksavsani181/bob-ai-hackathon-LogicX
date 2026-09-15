"""
FastAPI application entry point.

Team LogicX — Hackathon Challenge S1 — Wafer Yield Root Cause & Defect Pattern Analyser.

IMPORTANT:
- This is NOT a chatbot or AI assistant interface.
- All analytics are deterministic; no LLM is invoked at runtime.
- Root-cause ranking is produced by evidence fusion in app/services/root_cause.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import lots, monitor, pre_run
from app.schemas import HealthResponse

app = FastAPI(
    title="Wafer Yield Root Cause & Defect Pattern Analyser",
    description=(
        "Team LogicX — Hackathon Challenge S1.  "
        "Semiconductor manufacturing analytics control tower.  "
        "All root-cause ranking is deterministic evidence fusion — no LLM."
    ),
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow the React dev server and the nginx-served frontend
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
        "http://localhost",
        "http://frontend",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(lots.router)
app.include_router(monitor.router)
app.include_router(pre_run.router)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version="0.1.0",
        generated_at=datetime.now(timezone.utc),
    )
