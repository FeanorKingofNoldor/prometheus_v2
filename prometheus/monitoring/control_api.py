"""Prometheus v2 – Control API.

This module provides write-side endpoints for the C2 UI to launch
backtests, create synthetic datasets, schedule DAGs, and apply config
changes.

All control operations are logged and tracked via job registry.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Path
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/control", tags=["control"])


# ============================================================================
# Request/Response Models
# ============================================================================


class BacktestRequest(BaseModel):
    """Request to run a backtest."""

    strategy_id: str
    start_date: str
    end_date: str
    market_ids: list[str] = Field(default_factory=list)
    config_overrides: Dict[str, Any] = Field(default_factory=dict)


class SyntheticDatasetRequest(BaseModel):
    """Request to create synthetic scenario dataset."""

    dataset_name: str
    scenario_type: str
    num_samples: int = 1000
    parameters: Dict[str, Any] = Field(default_factory=dict)


class DAGScheduleRequest(BaseModel):
    """Request to schedule DAG execution."""

    market_id: str
    dag_name: str
    force: bool = False
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ConfigChangeRequest(BaseModel):
    """Request to apply config change."""

    engine_name: str
    config_key: str
    config_value: Any
    reason: str
    requires_approval: bool = True


class JobResponse(BaseModel):
    """Response for job submission."""

    job_id: str
    status: str = "PENDING"
    message: str = ""


class JobStatus(BaseModel):
    """Job status and progress."""

    job_id: str
    type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress_pct: float = 0.0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# Simple in-memory job registry (replace with DB storage later)
_job_registry: Dict[str, JobStatus] = {}


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/run_backtest", response_model=JobResponse)
async def run_backtest(request: BacktestRequest = Body(...)) -> JobResponse:
    """Submit backtest job for execution.

    Creates a job that will be picked up by the orchestrator and
    executed asynchronously.
    """
    job_id = f"backtest_{uuid.uuid4().hex[:8]}"

    _job_registry[job_id] = JobStatus(
        job_id=job_id,
        type="BACKTEST",
        status="PENDING",
        created_at=datetime.now(),
        message=f"Backtest {request.strategy_id} from {request.start_date} to {request.end_date}",
    )

    return JobResponse(
        job_id=job_id,
        status="PENDING",
        message=f"Backtest job submitted: {job_id}",
    )


@router.post("/create_synthetic_dataset", response_model=JobResponse)
async def create_synthetic_dataset(
    request: SyntheticDatasetRequest = Body(...)
) -> JobResponse:
    """Submit synthetic dataset creation job.

    Creates a job that will generate synthetic scenarios using the
    specified parameters.
    """
    job_id = f"synthetic_{uuid.uuid4().hex[:8]}"

    _job_registry[job_id] = JobStatus(
        job_id=job_id,
        type="SYNTHETIC_DATASET",
        status="PENDING",
        created_at=datetime.now(),
        message=f"Creating {request.dataset_name} with {request.num_samples} samples",
    )

    return JobResponse(
        job_id=job_id,
        status="PENDING",
        message=f"Synthetic dataset job submitted: {job_id}",
    )


@router.post("/schedule_dag", response_model=JobResponse)
async def schedule_dag(request: DAGScheduleRequest = Body(...)) -> JobResponse:
    """Schedule DAG execution for a market.

    Triggers immediate execution of specified DAG, optionally forcing
    re-run even if already completed today.
    """
    job_id = f"dag_{uuid.uuid4().hex[:8]}"

    _job_registry[job_id] = JobStatus(
        job_id=job_id,
        type="DAG_EXECUTION",
        status="PENDING",
        created_at=datetime.now(),
        message=f"Scheduling {request.dag_name} for {request.market_id}",
    )

    return JobResponse(
        job_id=job_id,
        status="PENDING",
        message=f"DAG execution job submitted: {job_id}",
    )


@router.post("/apply_config_change", response_model=JobResponse)
async def apply_config_change(request: ConfigChangeRequest = Body(...)) -> JobResponse:
    """Apply configuration change.

    If requires_approval is True, stages the change for review.
    Otherwise applies immediately (use with caution).
    """
    job_id = f"config_{uuid.uuid4().hex[:8]}"

    status = "STAGED" if request.requires_approval else "PENDING"

    _job_registry[job_id] = JobStatus(
        job_id=job_id,
        type="CONFIG_CHANGE",
        status=status,
        created_at=datetime.now(),
        message=f"Config change: {request.engine_name}.{request.config_key}",
    )

    return JobResponse(
        job_id=job_id,
        status=status,
        message=(
            f"Config change staged for approval: {job_id}"
            if request.requires_approval
            else f"Config change applied: {job_id}"
        ),
    )


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str = Path(..., description="Job identifier")) -> JobStatus:
    """Query job status and progress.

    Used by UI to poll for job completion and display progress.
    """
    if job_id in _job_registry:
        return _job_registry[job_id]

    # Mock completed job for demo
    return JobStatus(
        job_id=job_id,
        type="UNKNOWN",
        status="NOT_FOUND",
        created_at=datetime.now(),
        message=f"Job {job_id} not found in registry",
    )
