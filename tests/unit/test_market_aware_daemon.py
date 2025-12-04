"""Unit tests for the market-aware DAG orchestration daemon."""

import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from prometheus.orchestration.market_aware_daemon import (
    JobExecution,
    MarketAwareDaemon,
    MarketAwareDaemonConfig,
    calculate_retry_delay,
    create_job_execution,
    execute_job,
    get_dag_executions,
    get_latest_job_execution,
    increment_job_execution_attempt,
    should_retry_job,
    update_job_execution_status,
)
from prometheus.orchestration.dag import JobMetadata, JobPriority, JobStatus, build_market_dag
from prometheus.core.market_state import MarketState
from prometheus.pipeline.state import EngineRun, RunPhase


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_manager():
    """Mock DatabaseManager for testing."""
    db = MagicMock()
    db.get_runtime_connection.return_value.__enter__ = Mock()
    db.get_runtime_connection.return_value.__exit__ = Mock(return_value=False)
    return db


@pytest.fixture
def sample_job():
    """Sample JobMetadata for testing."""
    return JobMetadata(
        job_id="test_job_1",
        job_type="run_signals",
        market_id="US_EQ",
        required_state=MarketState.POST_CLOSE,
        dependencies=set(),
        run_phase=None,
        max_retries=3,
        retry_delay_seconds=30,
        priority=JobPriority.STANDARD,
        timeout_seconds=300,
    )


@pytest.fixture
def sample_execution():
    """Sample JobExecution for testing."""
    return JobExecution(
        execution_id="exec_123",
        job_id="test_job_1",
        job_type="run_signals",
        dag_id="US_EQ_2025-12-02",
        market_id="US_EQ",
        as_of_date=date(2025, 12, 2),
        status=JobStatus.PENDING,
        started_at=None,
        completed_at=None,
        attempt_number=1,
        error_message=None,
        error_details=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ============================================================================
# Job Execution Tracking Tests
# ============================================================================


def test_create_job_execution(mock_db_manager, sample_job):
    """Test creating a new job execution record."""
    cursor_mock = MagicMock()
    conn_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock
    conn_mock.__enter__ = Mock(return_value=conn_mock)
    conn_mock.__exit__ = Mock(return_value=False)

    mock_db_manager.get_runtime_connection.return_value = conn_mock

    execution = create_job_execution(
        mock_db_manager,
        sample_job,
        "US_EQ_2025-12-02",
        date(2025, 12, 2),
    )

    assert execution.job_id == "test_job_1"
    assert execution.job_type == "run_signals"
    assert execution.status == JobStatus.PENDING
    assert execution.attempt_number == 1
    cursor_mock.execute.assert_called_once()
    conn_mock.commit.assert_called_once()


def test_update_job_execution_status_to_running(mock_db_manager):
    """Test updating execution status to RUNNING."""
    cursor_mock = MagicMock()
    conn_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock
    conn_mock.__enter__ = Mock(return_value=conn_mock)
    conn_mock.__exit__ = Mock(return_value=False)

    mock_db_manager.get_runtime_connection.return_value = conn_mock

    update_job_execution_status(
        mock_db_manager,
        "exec_123",
        JobStatus.RUNNING,
    )

    cursor_mock.execute.assert_called_once()
    sql_call = cursor_mock.execute.call_args[0][0]
    assert "started_at" in sql_call
    conn_mock.commit.assert_called_once()


def test_update_job_execution_status_to_failed(mock_db_manager):
    """Test updating execution status to FAILED with error."""
    cursor_mock = MagicMock()
    conn_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock
    conn_mock.__enter__ = Mock(return_value=conn_mock)
    conn_mock.__exit__ = Mock(return_value=False)

    mock_db_manager.get_runtime_connection.return_value = conn_mock

    error_details = {"traceback": "line 1\nline 2"}
    update_job_execution_status(
        mock_db_manager,
        "exec_123",
        JobStatus.FAILED,
        error_message="Test error",
        error_details=error_details,
    )

    cursor_mock.execute.assert_called_once()
    sql_call = cursor_mock.execute.call_args[0][0]
    assert "completed_at" in sql_call
    assert "error_message" in sql_call
    conn_mock.commit.assert_called_once()


def test_get_dag_executions(mock_db_manager):
    """Test retrieving all executions for a DAG."""
    cursor_mock = MagicMock()
    conn_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock
    conn_mock.__enter__ = Mock(return_value=conn_mock)
    conn_mock.__exit__ = Mock(return_value=False)

    # Mock database rows
    now = datetime.now(timezone.utc)
    cursor_mock.fetchall.return_value = [
        (
            "exec_1",
            "job_1",
            "run_signals",
            "US_EQ_2025-12-02",
            "US_EQ",
            date(2025, 12, 2),
            "SUCCESS",
            now,
            now,
            1,
            None,
            None,
            now,
            now,
        ),
        (
            "exec_2",
            "job_2",
            "run_universes",
            "US_EQ_2025-12-02",
            "US_EQ",
            date(2025, 12, 2),
            "RUNNING",
            now,
            None,
            1,
            None,
            None,
            now,
            now,
        ),
    ]

    mock_db_manager.get_runtime_connection.return_value = conn_mock

    executions = get_dag_executions(mock_db_manager, "US_EQ_2025-12-02")

    assert len(executions) == 2
    assert executions[0].execution_id == "exec_1"
    assert executions[0].status == JobStatus.SUCCESS
    assert executions[1].execution_id == "exec_2"
    assert executions[1].status == JobStatus.RUNNING


def test_get_latest_job_execution(mock_db_manager):
    """Test retrieving the most recent execution for a job."""
    cursor_mock = MagicMock()
    conn_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock
    conn_mock.__enter__ = Mock(return_value=conn_mock)
    conn_mock.__exit__ = Mock(return_value=False)

    now = datetime.now(timezone.utc)
    cursor_mock.fetchone.return_value = (
        "exec_latest",
        "job_1",
        "run_signals",
        "US_EQ_2025-12-02",
        "US_EQ",
        date(2025, 12, 2),
        "FAILED",
        now,
        now,
        2,
        "Connection timeout",
        json.dumps({"error_type": "TimeoutError"}),
        now,
        now,
    )

    mock_db_manager.get_runtime_connection.return_value = conn_mock

    execution = get_latest_job_execution(mock_db_manager, "job_1", "US_EQ_2025-12-02")

    assert execution is not None
    assert execution.execution_id == "exec_latest"
    assert execution.status == JobStatus.FAILED
    assert execution.attempt_number == 2
    assert execution.error_message == "Connection timeout"
    assert execution.error_details == {"error_type": "TimeoutError"}


def test_get_latest_job_execution_not_found(mock_db_manager):
    """Test retrieving execution when none exists."""
    cursor_mock = MagicMock()
    conn_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock
    conn_mock.__enter__ = Mock(return_value=conn_mock)
    conn_mock.__exit__ = Mock(return_value=False)

    cursor_mock.fetchone.return_value = None

    mock_db_manager.get_runtime_connection.return_value = conn_mock

    execution = get_latest_job_execution(mock_db_manager, "nonexistent", "US_EQ_2025-12-02")

    assert execution is None


def test_increment_job_execution_attempt(mock_db_manager):
    """Test incrementing retry attempt number."""
    cursor_mock = MagicMock()
    conn_mock = MagicMock()
    conn_mock.cursor.return_value = cursor_mock
    conn_mock.__enter__ = Mock(return_value=conn_mock)
    conn_mock.__exit__ = Mock(return_value=False)

    mock_db_manager.get_runtime_connection.return_value = conn_mock

    increment_job_execution_attempt(mock_db_manager, "exec_123")

    cursor_mock.execute.assert_called_once()
    sql_call = cursor_mock.execute.call_args[0][0]
    assert "attempt_number = attempt_number + 1" in sql_call
    conn_mock.commit.assert_called_once()


# ============================================================================
# Retry Logic Tests
# ============================================================================


def test_calculate_retry_delay_first_attempt(sample_job):
    """Test exponential backoff calculation for first retry."""
    delay = calculate_retry_delay(sample_job, attempt_number=1)

    # First attempt: base_delay * 2^0 = 30 * 1 = 30, with ±25% jitter
    assert 22.5 <= delay <= 37.5


def test_calculate_retry_delay_third_attempt(sample_job):
    """Test exponential backoff for third retry."""
    delay = calculate_retry_delay(sample_job, attempt_number=3)

    # Third attempt: 30 * 2^2 = 120, with ±25% jitter
    assert 90 <= delay <= 150


def test_calculate_retry_delay_minimum():
    """Test that delay never goes below 1 second."""
    job = JobMetadata(
        job_id="test_job",
        job_type="run_signals",
        market_id="US_EQ",
        required_state=MarketState.POST_CLOSE,
        dependencies=set(),
        run_phase=None,
        max_retries=3,
        retry_delay_seconds=0.1,  # Very small delay
        priority=JobPriority.STANDARD,
        timeout_seconds=300,
    )
    delay = calculate_retry_delay(job, attempt_number=1)

    assert delay >= 1.0


def test_should_retry_job_within_limit(sample_job, sample_execution):
    """Test retry decision when attempts are within limit."""
    sample_execution.status = JobStatus.FAILED
    sample_execution.attempt_number = 2

    assert should_retry_job(sample_job, sample_execution) is True


def test_should_retry_job_at_limit(sample_job, sample_execution):
    """Test retry decision when max retries reached."""
    sample_execution.status = JobStatus.FAILED
    sample_execution.attempt_number = 3  # max_retries = 3

    assert should_retry_job(sample_job, sample_execution) is False


def test_should_retry_job_success_status(sample_job, sample_execution):
    """Test that successful jobs are not retried."""
    sample_execution.status = JobStatus.SUCCESS

    assert should_retry_job(sample_job, sample_execution) is False


# ============================================================================
# Job Execution Tests
# ============================================================================


@patch("prometheus.orchestration.market_aware_daemon._get_or_create_engine_run")
@patch("prometheus.orchestration.market_aware_daemon.run_signals_for_run")
def test_execute_job_run_signals(mock_run_signals, mock_get_run, mock_db_manager, sample_job, sample_execution):
    """Test executing run_signals job type."""
    mock_run = EngineRun(
        run_id="run_123",
        region="US",
        as_of_date=date(2025, 12, 2),
        phase=RunPhase.DATA_READY,
        error=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        phase_started_at=datetime.now(timezone.utc),
        phase_completed_at=None,
    )
    mock_get_run.return_value = mock_run

    success, error = execute_job(mock_db_manager, sample_job, sample_execution)

    assert success is True
    assert error is None
    mock_run_signals.assert_called_once_with(mock_db_manager, mock_run)


@patch("prometheus.orchestration.market_aware_daemon._get_or_create_engine_run")
def test_execute_job_unknown_type(mock_get_run, mock_db_manager, sample_execution):
    """Test executing unknown job type."""
    job = JobMetadata(
        job_id="test_job",
        job_type="unknown_job",
        market_id="US_EQ",
        required_state=MarketState.POST_CLOSE,
        dependencies=set(),
        run_phase=None,
        max_retries=3,
        retry_delay_seconds=30,
        priority=JobPriority.STANDARD,
        timeout_seconds=300,
    )
    mock_run = EngineRun(
        run_id="run_123",
        region="US",
        as_of_date=date(2025, 12, 2),
        phase=RunPhase.DATA_READY,
        error=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        phase_started_at=datetime.now(timezone.utc),
        phase_completed_at=None,
    )
    mock_get_run.return_value = mock_run

    success, error = execute_job(mock_db_manager, job, sample_execution)

    assert success is False
    assert "Unknown job_type" in error


@patch("prometheus.orchestration.market_aware_daemon._get_or_create_engine_run")
def test_execute_job_no_engine_run(mock_get_run, mock_db_manager, sample_job, sample_execution):
    """Test job execution when EngineRun cannot be created."""
    mock_get_run.return_value = None

    success, error = execute_job(mock_db_manager, sample_job, sample_execution)

    assert success is False
    assert "Could not create EngineRun" in error


@patch("prometheus.orchestration.market_aware_daemon._get_or_create_engine_run")
@patch("prometheus.orchestration.market_aware_daemon.run_signals_for_run")
def test_execute_job_exception(mock_run_signals, mock_get_run, mock_db_manager, sample_job, sample_execution):
    """Test job execution with exception."""
    mock_run = EngineRun(
        run_id="run_123",
        region="US",
        as_of_date=date(2025, 12, 2),
        phase=RunPhase.DATA_READY,
        error=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        phase_started_at=datetime.now(timezone.utc),
        phase_completed_at=None,
    )
    mock_get_run.return_value = mock_run
    mock_run_signals.side_effect = RuntimeError("Database connection lost")

    success, error = execute_job(mock_db_manager, sample_job, sample_execution)

    assert success is False
    assert "RuntimeError: Database connection lost" in error


# ============================================================================
# MarketAwareDaemon Tests
# ============================================================================


def test_daemon_config_creation():
    """Test creating daemon configuration."""
    config = MarketAwareDaemonConfig(
        markets=["US_EQ", "EU_EQ"],
        poll_interval_seconds=30,
        as_of_date=date(2025, 12, 2),
    )

    assert config.markets == ["US_EQ", "EU_EQ"]
    assert config.poll_interval_seconds == 30
    assert config.as_of_date == date(2025, 12, 2)


def test_daemon_initialization(mock_db_manager):
    """Test daemon initialization."""
    config = MarketAwareDaemonConfig(
        markets=["US_EQ"],
        poll_interval_seconds=60,
    )

    daemon = MarketAwareDaemon(config, mock_db_manager)

    assert daemon.config == config
    assert daemon.db_manager == mock_db_manager
    assert daemon.shutdown_requested is False
    assert len(daemon.active_dags) == 0
    assert len(daemon.running_jobs) == 0


def test_daemon_initialize_dags(mock_db_manager):
    """Test DAG initialization for configured markets."""
    config = MarketAwareDaemonConfig(markets=["US_EQ", "EU_EQ"])
    daemon = MarketAwareDaemon(config, mock_db_manager)

    daemon._initialize_dags(date(2025, 12, 2))

    assert len(daemon.active_dags) == 2
    assert "US_EQ" in daemon.active_dags
    assert "EU_EQ" in daemon.active_dags

    us_dag, us_dag_id = daemon.active_dags["US_EQ"]
    assert us_dag_id == "US_EQ_2025-12-02"
    assert len(us_dag.jobs) == 9  # Standard market DAG has 9 jobs


@patch("prometheus.orchestration.market_aware_daemon.get_dag_executions")
def test_daemon_get_completed_jobs(mock_get_executions, mock_db_manager):
    """Test retrieving completed job IDs."""
    config = MarketAwareDaemonConfig(markets=["US_EQ"])
    daemon = MarketAwareDaemon(config, mock_db_manager)

    mock_executions = [
        Mock(job_id="job_1", status=JobStatus.SUCCESS),
        Mock(job_id="job_2", status=JobStatus.RUNNING),
        Mock(job_id="job_3", status=JobStatus.SUCCESS),
        Mock(job_id="job_4", status=JobStatus.FAILED),
    ]
    mock_get_executions.return_value = mock_executions

    completed = daemon._get_completed_jobs("US_EQ_2025-12-02")

    assert completed == {"job_1", "job_3"}


def test_daemon_get_running_job_ids(mock_db_manager):
    """Test retrieving running job IDs."""
    config = MarketAwareDaemonConfig(markets=["US_EQ"])
    daemon = MarketAwareDaemon(config, mock_db_manager)

    job1 = Mock(job_id="job_1")
    job2 = Mock(job_id="job_2")

    daemon.running_jobs = {
        "exec_1": (job1, datetime.now(timezone.utc)),
        "exec_2": (job2, datetime.now(timezone.utc)),
    }

    running = daemon._get_running_job_ids()

    assert running == {"job_1", "job_2"}


@patch("prometheus.orchestration.market_aware_daemon.update_job_execution_status")
def test_daemon_check_timeouts(mock_update_status, mock_db_manager):
    """Test timeout detection and handling."""
    config = MarketAwareDaemonConfig(markets=["US_EQ"])
    daemon = MarketAwareDaemon(config, mock_db_manager)

    job = Mock(job_id="job_timeout", timeout_seconds=60)
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)

    daemon.running_jobs = {
        "exec_timeout": (job, old_time),
    }

    daemon._check_timeouts(datetime.now(timezone.utc))

    # Job should be marked as failed and removed from running
    mock_update_status.assert_called_once()
    assert "exec_timeout" not in daemon.running_jobs


@patch("prometheus.orchestration.market_aware_daemon.get_market_state")
@patch("prometheus.orchestration.market_aware_daemon.get_dag_executions")
@patch("prometheus.orchestration.market_aware_daemon.execute_job")
@patch("prometheus.orchestration.market_aware_daemon.create_job_execution")
@patch("prometheus.orchestration.market_aware_daemon.update_job_execution_status")
@patch("prometheus.orchestration.market_aware_daemon.get_latest_job_execution")
def test_daemon_process_market_with_runnable_jobs(
    mock_get_latest,
    mock_update_status,
    mock_create_exec,
    mock_execute,
    mock_get_execs,
    mock_get_state,
    mock_db_manager,
):
    """Test processing a market with runnable jobs."""
    config = MarketAwareDaemonConfig(markets=["US_EQ"])
    daemon = MarketAwareDaemon(config, mock_db_manager)

    # Initialize DAG
    daemon._initialize_dags(date(2025, 12, 2))
    dag, dag_id = daemon.active_dags["US_EQ"]

    # Mock market state
    mock_get_state.return_value = MarketState.POST_CLOSE

    # Mock no completed jobs
    mock_get_execs.return_value = []

    # Mock no latest execution (new job)
    mock_get_latest.return_value = None

    # Mock successful job creation and execution
    mock_execution = Mock(
        execution_id="new_exec",
        job_id="US_EQ_2025-12-02_ingest_prices",
        status=JobStatus.PENDING,
        attempt_number=1,
    )
    mock_create_exec.return_value = mock_execution
    mock_execute.return_value = (True, None)

    daemon._process_market(
        "US_EQ",
        dag,
        dag_id,
        MarketState.POST_CLOSE,
        date(2025, 12, 2),
        datetime.now(timezone.utc),
    )

    # Should create execution and run job
    mock_create_exec.assert_called()
    mock_execute.assert_called()
    mock_update_status.assert_called()


# ============================================================================
# CLI Tests
# ============================================================================


def test_parse_args_basic():
    """Test parsing basic CLI arguments."""
    from prometheus.orchestration.market_aware_daemon import _parse_args

    args = _parse_args(["--market", "US_EQ", "--poll-interval-seconds", "30"])

    assert args.market == ["US_EQ"]
    assert args.poll_interval_seconds == 30
    assert args.as_of_date is None


def test_parse_args_multiple_markets():
    """Test parsing multiple market arguments."""
    from prometheus.orchestration.market_aware_daemon import _parse_args

    args = _parse_args(["--market", "US_EQ", "--market", "EU_EQ", "--market", "ASIA_EQ"])

    assert args.market == ["US_EQ", "EU_EQ", "ASIA_EQ"]


def test_parse_args_with_date():
    """Test parsing with as-of-date."""
    from prometheus.orchestration.market_aware_daemon import _parse_args

    args = _parse_args(["--market", "US_EQ", "--as-of-date", "2025-12-15"])

    assert args.as_of_date == date(2025, 12, 15)


def test_parse_args_invalid_poll_interval():
    """Test error on invalid poll interval."""
    from prometheus.orchestration.market_aware_daemon import _parse_args

    with pytest.raises(SystemExit):
        _parse_args(["--market", "US_EQ", "--poll-interval-seconds", "0"])


def test_parse_args_invalid_date_format():
    """Test error on invalid date format."""
    from prometheus.orchestration.market_aware_daemon import _parse_args

    with pytest.raises(SystemExit):
        _parse_args(["--market", "US_EQ", "--as-of-date", "12/15/2025"])
