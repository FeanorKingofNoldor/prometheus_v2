"""Prometheus v2 – C2 Backend Application.

FastAPI application that serves all monitoring, visualization, control,
and meta-orchestration APIs for the Prometheus C2 UI.

Run with:
    uvicorn prometheus.monitoring.app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from prometheus.monitoring.api import router as status_router
from prometheus.monitoring.control_api import router as control_router
from prometheus.monitoring.meta_api import geo_router, kronos_router, meta_router
from prometheus.monitoring.visualization_api import router as viz_router
from prometheus.monitoring.intelligence_api import intelligence_router


# ============================================================================
# Application Setup
# ============================================================================


app = FastAPI(
    title="Prometheus C2 Backend",
    description="Monitoring, visualization, and control APIs for Prometheus v2",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


# ============================================================================
# CORS Configuration
# ============================================================================

# Allow Godot client to connect from localhost during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "godot://",  # For Godot client
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Router Registration
# ============================================================================

# Monitoring/status endpoints
app.include_router(status_router)

# Visualization endpoints (ANT_HILL, scenes, traces)
app.include_router(viz_router)

# Control endpoints (backtests, configs, DAG scheduling)
app.include_router(control_router)

# Meta endpoints (configs, performance)
app.include_router(meta_router)

# Kronos Chat endpoint
app.include_router(kronos_router)

# Geo endpoints (world map data)
app.include_router(geo_router)

# Intelligence endpoints (diagnostics, proposals, applicator)
app.include_router(intelligence_router)


# ============================================================================
# Health Check
# ============================================================================


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with basic system info."""
    return {
        "service": "Prometheus C2 Backend",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/api/docs",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


# ============================================================================
# Startup/Shutdown Events
# ============================================================================


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize connections and resources on startup."""
    print("Prometheus C2 Backend starting up...")
    print("API docs available at: http://localhost:8000/api/docs")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up resources on shutdown."""
    print("Prometheus C2 Backend shutting down...")
