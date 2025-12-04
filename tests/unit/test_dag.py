"""Unit tests for prometheus.orchestration.dag module."""

from datetime import date

import pytest

from prometheus.core.market_state import MarketState
from prometheus.orchestration.dag import (
    JobMetadata,
    JobPriority,
    JobStatus,
    DAG,
    build_market_dag,
    build_global_dag,
)
from prometheus.pipeline.state import RunPhase


# ============================================================================
# Test: JobMetadata
# ============================================================================


def test_job_metadata_creation():
    """JobMetadata should be created with required fields."""
    job = JobMetadata(
        job_id="test_job_1",
        job_type="ingest_prices",
        market_id="US_EQ",
    )
    
    assert job.job_id == "test_job_1"
    assert job.job_type == "ingest_prices"
    assert job.market_id == "US_EQ"
    assert job.required_state is None
    assert job.dependencies == ()
    assert job.max_retries == 3
    assert job.priority == JobPriority.STANDARD


def test_job_metadata_with_dependencies():
    """JobMetadata should accept dependencies."""
    job = JobMetadata(
        job_id="compute_returns",
        job_type="compute_returns",
        market_id="US_EQ",
        dependencies=("ingest_prices",),
        priority=JobPriority.CRITICAL,
    )
    
    assert job.dependencies == ("ingest_prices",)
    assert job.priority == JobPriority.CRITICAL


def test_job_priority_ordering():
    """JobPriority should have correct ordering (lower = higher priority)."""
    assert JobPriority.CRITICAL < JobPriority.STANDARD < JobPriority.OPTIONAL
    assert JobPriority.CRITICAL.value == 1
    assert JobPriority.STANDARD.value == 2
    assert JobPriority.OPTIONAL.value == 3


# ============================================================================
# Test: DAG Structure
# ============================================================================


def test_dag_creation():
    """DAG should be created with jobs."""
    jobs = {
        "job1": JobMetadata(job_id="job1", job_type="test", market_id="US_EQ"),
        "job2": JobMetadata(
            job_id="job2",
            job_type="test",
            market_id="US_EQ",
            dependencies=("job1",),
        ),
    }
    
    dag = DAG(
        dag_id="test_dag",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    assert dag.dag_id == "test_dag"
    assert dag.market_id == "US_EQ"
    assert len(dag.jobs) == 2


def test_dag_get_runnable_jobs_no_dependencies():
    """get_runnable_jobs should return jobs with no dependencies."""
    jobs = {
        "job1": JobMetadata(job_id="job1", job_type="ingest", market_id="US_EQ"),
        "job2": JobMetadata(job_id="job2", job_type="ingest", market_id="US_EQ"),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    runnable = dag.get_runnable_jobs(
        completed_jobs=set(),
        running_jobs=set(),
        current_market_state=MarketState.POST_CLOSE,
    )
    
    assert len(runnable) == 2
    assert runnable[0].job_id in ("job1", "job2")


def test_dag_get_runnable_jobs_with_dependencies():
    """get_runnable_jobs should respect dependencies."""
    jobs = {
        "job1": JobMetadata(job_id="job1", job_type="ingest", market_id="US_EQ"),
        "job2": JobMetadata(
            job_id="job2",
            job_type="compute",
            market_id="US_EQ",
            dependencies=("job1",),
        ),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    # Initially, only job1 is runnable
    runnable = dag.get_runnable_jobs(
        completed_jobs=set(),
        running_jobs=set(),
        current_market_state=MarketState.POST_CLOSE,
    )
    
    assert len(runnable) == 1
    assert runnable[0].job_id == "job1"
    
    # After job1 completes, job2 is runnable
    runnable = dag.get_runnable_jobs(
        completed_jobs={"job1"},
        running_jobs=set(),
        current_market_state=MarketState.POST_CLOSE,
    )
    
    assert len(runnable) == 1
    assert runnable[0].job_id == "job2"


def test_dag_get_runnable_jobs_market_state_filter():
    """get_runnable_jobs should filter by market state."""
    jobs = {
        "job1": JobMetadata(
            job_id="job1",
            job_type="ingest",
            market_id="US_EQ",
            required_state=MarketState.POST_CLOSE,
        ),
        "job2": JobMetadata(
            job_id="job2",
            job_type="compute",
            market_id="US_EQ",
            required_state=None,  # Can run any time
        ),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    # In SESSION state, only job2 is runnable
    runnable = dag.get_runnable_jobs(
        completed_jobs=set(),
        running_jobs=set(),
        current_market_state=MarketState.SESSION,
    )
    
    assert len(runnable) == 1
    assert runnable[0].job_id == "job2"
    
    # In POST_CLOSE state, both are runnable
    runnable = dag.get_runnable_jobs(
        completed_jobs=set(),
        running_jobs=set(),
        current_market_state=MarketState.POST_CLOSE,
    )
    
    assert len(runnable) == 2


def test_dag_get_runnable_jobs_priority_ordering():
    """get_runnable_jobs should return jobs sorted by priority."""
    jobs = {
        "job1": JobMetadata(
            job_id="job1",
            job_type="optional",
            market_id="US_EQ",
            priority=JobPriority.OPTIONAL,
        ),
        "job2": JobMetadata(
            job_id="job2",
            job_type="critical",
            market_id="US_EQ",
            priority=JobPriority.CRITICAL,
        ),
        "job3": JobMetadata(
            job_id="job3",
            job_type="standard",
            market_id="US_EQ",
            priority=JobPriority.STANDARD,
        ),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    runnable = dag.get_runnable_jobs(
        completed_jobs=set(),
        running_jobs=set(),
        current_market_state=MarketState.POST_CLOSE,
    )
    
    # Should be ordered: CRITICAL, STANDARD, OPTIONAL
    assert runnable[0].job_id == "job2"
    assert runnable[1].job_id == "job3"
    assert runnable[2].job_id == "job1"


def test_dag_get_runnable_jobs_excludes_running():
    """get_runnable_jobs should exclude currently running jobs."""
    jobs = {
        "job1": JobMetadata(job_id="job1", job_type="test", market_id="US_EQ"),
        "job2": JobMetadata(job_id="job2", job_type="test", market_id="US_EQ"),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    runnable = dag.get_runnable_jobs(
        completed_jobs=set(),
        running_jobs={"job1"},  # job1 is running
        current_market_state=MarketState.POST_CLOSE,
    )
    
    assert len(runnable) == 1
    assert runnable[0].job_id == "job2"


# ============================================================================
# Test: DAG Dependency Chain
# ============================================================================


def test_dag_get_dependency_chain_linear():
    """get_dependency_chain should return transitive dependencies."""
    jobs = {
        "job1": JobMetadata(job_id="job1", job_type="a", market_id="US_EQ"),
        "job2": JobMetadata(
            job_id="job2",
            job_type="b",
            market_id="US_EQ",
            dependencies=("job1",),
        ),
        "job3": JobMetadata(
            job_id="job3",
            job_type="c",
            market_id="US_EQ",
            dependencies=("job2",),
        ),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    # job3 depends on job2 and job1 (transitively)
    deps = dag.get_dependency_chain("job3")
    assert set(deps) == {"job1", "job2"}


def test_dag_get_dependency_chain_diamond():
    """get_dependency_chain should handle diamond dependencies."""
    jobs = {
        "job1": JobMetadata(job_id="job1", job_type="a", market_id="US_EQ"),
        "job2": JobMetadata(
            job_id="job2",
            job_type="b",
            market_id="US_EQ",
            dependencies=("job1",),
        ),
        "job3": JobMetadata(
            job_id="job3",
            job_type="c",
            market_id="US_EQ",
            dependencies=("job1",),
        ),
        "job4": JobMetadata(
            job_id="job4",
            job_type="d",
            market_id="US_EQ",
            dependencies=("job2", "job3"),
        ),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    # job4 depends on job1, job2, job3
    deps = dag.get_dependency_chain("job4")
    assert set(deps) == {"job1", "job2", "job3"}


# ============================================================================
# Test: DAG Validation
# ============================================================================


def test_dag_validate_success():
    """validate should return empty list for valid DAG."""
    jobs = {
        "job1": JobMetadata(job_id="job1", job_type="a", market_id="US_EQ"),
        "job2": JobMetadata(
            job_id="job2",
            job_type="b",
            market_id="US_EQ",
            dependencies=("job1",),
        ),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    errors = dag.validate()
    assert errors == []


def test_dag_validate_missing_dependency():
    """validate should detect missing dependencies."""
    jobs = {
        "job1": JobMetadata(
            job_id="job1",
            job_type="test",
            market_id="US_EQ",
            dependencies=("nonexistent",),
        ),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    errors = dag.validate()
    assert len(errors) == 1
    assert "nonexistent" in errors[0]


def test_dag_validate_circular_dependency():
    """validate should detect circular dependencies."""
    jobs = {
        "job1": JobMetadata(
            job_id="job1",
            job_type="a",
            market_id="US_EQ",
            dependencies=("job2",),
        ),
        "job2": JobMetadata(
            job_id="job2",
            job_type="b",
            market_id="US_EQ",
            dependencies=("job1",),
        ),
    }
    
    dag = DAG(
        dag_id="test",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 1),
        jobs=jobs,
    )
    
    errors = dag.validate()
    assert len(errors) >= 1
    assert any("circular" in err.lower() for err in errors)


# ============================================================================
# Test: build_market_dag
# ============================================================================


def test_build_market_dag_structure():
    """build_market_dag should create valid DAG with correct structure."""
    dag = build_market_dag("US_EQ", date(2025, 12, 1))
    
    assert dag.dag_id == "us_eq_daily_2025-12-01"
    assert dag.market_id == "US_EQ"
    assert dag.as_of_date == date(2025, 12, 1)
    
    # Should have all expected jobs
    assert len(dag.jobs) >= 9  # At least 9 standard jobs
    
    # Check key jobs exist
    job_types = {job.job_type for job in dag.jobs.values()}
    assert "ingest_prices" in job_types
    assert "compute_returns" in job_types
    assert "build_numeric_windows" in job_types
    assert "run_signals" in job_types
    assert "run_universes" in job_types
    assert "run_books" in job_types


def test_build_market_dag_dependencies():
    """build_market_dag should have correct dependencies."""
    dag = build_market_dag("US_EQ", date(2025, 12, 1))
    
    # Find compute_returns job
    compute_returns = next(
        job for job in dag.jobs.values() if job.job_type == "compute_returns"
    )
    
    # Should depend on ingest_prices
    assert len(compute_returns.dependencies) == 1
    ingest_dep = list(compute_returns.dependencies)[0]
    assert "ingest_prices" in ingest_dep


def test_build_market_dag_market_states():
    """build_market_dag jobs should have correct market state requirements."""
    dag = build_market_dag("US_EQ", date(2025, 12, 1))
    
    # Ingestion should require POST_CLOSE
    ingest = next(job for job in dag.jobs.values() if job.job_type == "ingest_prices")
    assert ingest.required_state == MarketState.POST_CLOSE
    
    # Feature computation doesn't require specific state
    compute = next(job for job in dag.jobs.values() if job.job_type == "compute_returns")
    assert compute.required_state is None


def test_build_market_dag_run_phases():
    """build_market_dag engine jobs should map to RunPhases."""
    dag = build_market_dag("US_EQ", date(2025, 12, 1))
    
    signals = next(job for job in dag.jobs.values() if job.job_type == "run_signals")
    assert signals.run_phase == RunPhase.SIGNALS_DONE
    
    universes = next(job for job in dag.jobs.values() if job.job_type == "run_universes")
    assert universes.run_phase == RunPhase.UNIVERSES_DONE
    
    books = next(job for job in dag.jobs.values() if job.job_type == "run_books")
    assert books.run_phase == RunPhase.BOOKS_DONE


def test_build_market_dag_validates():
    """build_market_dag should produce valid DAG."""
    dag = build_market_dag("US_EQ", date(2025, 12, 1))
    errors = dag.validate()
    assert errors == []


# ============================================================================
# Test: build_global_dag
# ============================================================================


def test_build_global_dag():
    """build_global_dag should create cross-market dependencies."""
    # Create regional DAGs
    us_dag = build_market_dag("US_EQ", date(2025, 12, 1))
    eu_dag = build_market_dag("EU_EQ", date(2025, 12, 1))
    
    # Create global DAG
    global_dag = build_global_dag(date(2025, 12, 1), [us_dag, eu_dag])
    
    assert global_dag.dag_id == "global_daily_2025-12-01"
    assert global_dag.market_id == "GLOBAL"
    
    # Should have global_regime job
    assert len(global_dag.jobs) >= 1
    global_regime = next(
        job for job in global_dag.jobs.values() if job.job_type == "global_regime"
    )
    
    # Should depend on both regional run_signals jobs
    assert len(global_regime.dependencies) == 2
    assert any("us_eq_run_signals" in dep for dep in global_regime.dependencies)
    assert any("eu_eq_run_signals" in dep for dep in global_regime.dependencies)


def test_build_global_dag_validates():
    """build_global_dag should produce valid DAG (with skip_missing_deps)."""
    us_dag = build_market_dag("US_EQ", date(2025, 12, 1))
    global_dag = build_global_dag(date(2025, 12, 1), [us_dag])
    
    # Global DAG should validate cleanly with skip_missing_deps=True
    # (since dependencies are in other DAGs)
    errors = global_dag.validate(skip_missing_deps=True)
    assert errors == []
    
    # Without skipping, it would report missing dependencies
    errors = global_dag.validate(skip_missing_deps=False)
    assert any("non-existent" in err.lower() for err in errors)
