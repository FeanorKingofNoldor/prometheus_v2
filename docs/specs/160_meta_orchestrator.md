# 160 – Meta-Orchestrator (Kronos v2) Specification

## 1. Purpose

Kronos v2 (Meta-Orchestrator) oversees all engines in Prometheus v2. It:
- Observes **decisions and outcomes** across engines and configs.
- Computes **analytics**: performance, risk, robustness by regime/stability/fragility.
- Proposes **config changes and experiments** in a controlled, backtestable way.
- Powers the **Kronos Chat** interface as a conversational layer over this analytics.

Kronos does not trade or change configs directly; it **recommends** changes that must pass numeric checks and explicit approval.

---

## 2. Scope

- Operates at a slower cadence than daily trading engines:
  - daily summary updates,
  - weekly/monthly deeper analyses.
- Works across all engines:
  - Regime, Stability, Assessment, Universe, Portfolio, etc.
- Uses decision logs and realized outcomes as primary data.

---

## 3. Data Sources

Kronos relies on:

1. **Decision logs** (`engine_decisions` table; see 020):
   - `decision_id`, `timestamp`, `engine_name`, `config_id`, `context_id`, `as_of_date`, `proposed_action`, `input_refs`.

2. **Outcomes** (`decision_outcomes`):
   - Realized P&L, returns, drawdowns, risk metrics by horizon.

3. **Configs** (`engine_configs`):
   - Current and historical config versions per engine.

4. **Model registry** (`models`):
   - Model_ids, types, training_specs, metrics.

5. **Regime & stability/fragility context**:
   - `regimes`, `stability_vectors`, `fragility_measures`, `soft_target_classes`.

6. **Portfolio risk reports**:
   - `portfolio_risk_reports` for realized risk/exposures.

---

## 4. Core Responsibilities

### 4.1 Decision analytics

For each engine (REGIME, STABILITY, ASSESSMENT, UNIVERSE, PORTFOLIO) and config:

- Aggregate outcomes by:
  - time period,
  - regime,
  - stability/fragility state,
  - market/region.

- Compute metrics:
  - P&L contribution and Sharpe-like stats.
  - Max drawdown.
  - Hit rates / calibration (for probabilistic outputs).
  - Constraint violations (for Portfolio & Risk).

### 4.2 Config comparison

For each engine and set of configs:
- Compare performance across:
  - regimes,
  - markets,
  - time windows.

- Identify:
  - configs that are dominated (worse in most conditions),
  - configs that are robust (good across many conditions),
  - configs that are niche (good only in specific regimes).

### 4.3 Experiment management

Kronos manages **experiments**:
- A config experiment is:
  - a new or modified config for an engine,
  - tested via backtests or shadow decisions.

Kronos tracks:
- Experiment definition: engine, base config, modifications, start/end dates.
- Backtest results and live shadow metrics.
- Final verdict: adopt / reject / continue testing.

Configs are only promoted after:
- sufficient backtest evidence,
- no unacceptable behavior in stress/regime slices.

---

## 5. APIs (Backend)

Module: `prometheus/meta/api.py`

### 5.1 Performance summary

```python
from datetime import date
from typing import Dict, List

class MetaOrchestrator:
    """Meta-level analytics and config management for Prometheus engines."""

    def engine_performance(
        self,
        engine_name: str,
        config_id: str | None,
        start_date: date,
        end_date: date,
    ) -> "EnginePerformanceReport":
        """Compute performance metrics for an engine/config over a period."""

    def compare_configs(
        self,
        engine_name: str,
        config_ids: List[str],
        start_date: date,
        end_date: date,
    ) -> Dict[str, "EnginePerformanceReport"]:
        """Compare multiple configs for the same engine."""
```

`EnginePerformanceReport` (conceptual):

```python
from dataclasses import dataclass
from typing import Dict

@dataclass
class EnginePerformanceReport:
    engine_name: str
    config_id: str
    period_start: date
    period_end: date
    metrics: Dict[str, float]  # e.g., avg_return, volatility, sharpe, max_dd
    by_regime: Dict[str, Dict[str, float]]  # regime_label -> metrics
    by_stability_bucket: Dict[str, Dict[str, float]]
    by_market: Dict[str, Dict[str, float]]
```

### 5.2 Experiment management

```python
class MetaOrchestrator:
    # ...

    def list_experiments(self) -> List["Experiment"]:
        """Return all active and historical experiments."""

    def create_experiment(
        self,
        engine_name: str,
        base_config_id: str,
        proposed_config: dict,
        description: str,
    ) -> "Experiment":
        """Register a new config experiment for backtesting and/or shadowing."""

    def experiment_results(
        self,
        experiment_id: str,
    ) -> "ExperimentResult":
        """Get aggregated backtest and (optionally) live results for an experiment."""
```

Experiments will be stored in dedicated tables (see Section 7).

---

## 6. Kronos Chat Integration

Kronos Chat (see 200 spec) calls into Meta-Orchestrator APIs.

### 6.1 Chat flow

1. User sends query via `/api/kronos/chat`:
   - e.g., "Why did EU_EQ portfolio draw down last month?" or "Which Assessment configs are robust in crisis regimes?".

2. Backend:
   - Parses intent (engine, portfolio, period, regimes of interest).
   - Fetches relevant performance reports, configs, risk reports, and decision logs.

3. LLM component:
   - Receives structured context + question.
   - Uses tools (via MetaOrchestrator API) to drill further if needed.
   - Produces:
     - Natural-language explanation.
     - Optional structured proposals, e.g.:
       - new config JSON,
       - experiments to run.

4. Response:
   - Text answer.
   - `proposals` array with typed objects like `ConfigProposal`, `ExperimentProposal`.

### 6.2 Safety

- Kronos Chat cannot:
  - write to `engine_configs` directly,
  - change live configs or portfolios.

- A separate **Change Manager** (see below) must:
  - validate proposals,
  - run backtests,
  - apply approvals.

---

## 7. Storage: Experiments & Proposals

### 7.1 Experiments

**Table:** `experiments`

- `experiment_id` (PK, uuid)
- `engine_name` (text)
- `base_config_id` (text)
- `proposed_config_id` (text) – reference into `engine_configs` after registration
- `description` (text)
- `created_at` (timestamptz)
- `created_by` (text) – user or "Kronos"
- `status` (text: `PENDING`, `QUEUED_FOR_BACKTEST`, `RUNNING_BACKTESTS`, `AWAITING_REVIEW`, `APPROVED`, `REJECTED`)
- `priority` (int) – lower = more important (e.g. 0–9)
- `auto_generated` (bool) – `true` if proposed by Kronos itself
- `resource_class` (text) – rough resource type: `CPU_HEAVY`, `GPU_HEAVY`, `MIXED`
- `expected_outcome` (text) – e.g. `BASELINE`, `CANDIDATE`, `NEGATIVE_CONTROL`
- `metadata` (jsonb)

**Table:** `experiment_results`

- `experiment_id` (uuid, FK → experiments.experiment_id)
- `period_start` (date)
- `period_end` (date)
- `metrics` (jsonb) – summary metrics
- `by_regime` (jsonb)
- `by_market` (jsonb)
- `by_stability_bucket` (jsonb)

PK: (`experiment_id`, `period_start`, `period_end`).

### 7.2 Config proposals

Optionally, maintain a table for **pending config proposals** coming from Kronos Chat or manual input:

**Table:** `config_proposals`

- `proposal_id` (PK, uuid)
- `engine_name` (text)
- `base_config_id` (text)
- `proposed_config_body` (jsonb)
- `created_at` (timestamptz)
- `created_by` (text)
- `status` (text: `PENDING_REVIEW`, `CONVERTED_TO_EXPERIMENT`, `DISCARDED`)
- `metadata` (jsonb)

This allows tracking the lifecycle from suggestion → experiment → final config and distinguishing auto-generated experiments from manually created ones.

---

## 8. Change Management

### 8.1 Flow

1. **Proposal creation**
   - From human or Kronos Chat → `config_proposals`.
   - Kronos itself may also generate proposals automatically based on analytics (marked `auto_generated = true`).

2. **Experiment creation**
   - A reviewer or automated rule converts a proposal into an `experiment`:
     - registers proposed config in `engine_configs` with a unique `config_id`.
     - enqueues the experiment for backtesting with an appropriate `priority` and `resource_class`.

3. **Automatic pre-screening backtests**
   - A **Meta Backtest Scheduler** (see Orchestration) monitors cluster/node utilization and free resource windows.
   - When resources are available without impacting production SLOs (per 012/013):
     - it dequeues experiments in priority order (typically auto-generated, low-risk ones first),
     - runs backtests (and optionally shadow runs) in the background,
     - updates experiment `status` from `QUEUED_FOR_BACKTEST` → `RUNNING_BACKTESTS` → `AWAITING_REVIEW`.
   - This means many Kronos-proposed configs already come with backtest evidence **before** they are surfaced for human authorization.

4. **Experiment evaluation**
   - Backtest jobs run (via orchestration), writing `experiment_results`.
   - MetaOrchestrator aggregates and produces an `ExperimentResult` view.

5. **Review & decision**
   - Human (you) or policy-based rule decides:
     - `APPROVED`: promote `proposed_config_id` to current for engine.
     - `REJECTED`: keep current config.

6. **Promotion**
   - Updating `engine_configs` to mark new active config (outside Kronos Chat, in a controlled path).

### 8.2 Logging

All changes must be:
- Logged with timestamps and authors.
- Traceable back through experiments and proposals.
- Annotated with whether the evidence came from **automatic pre-screening** vs human-triggered backtests.

---

## 9. Orchestration

Kronos runs on its own DAGs:

- `meta_daily_T`:
  - Summarize previous day’s decisions and outcomes.
  - Update short-horizon performance metrics per engine/config.

- `meta_weekly_T` / `meta_monthly_T`:
  - Compute deeper performance breakdowns by regime/stability.
  - Evaluate active experiments.
  - Generate reports for monitoring UI and Kronos Chat.

These DAGs run after all regional engine DAGs and portfolio optimizations are complete.

### 9.1 Resource-aware backtest scheduling

A dedicated **Meta Backtest Scheduler** component integrates with the orchestration layer (see 012/013):

- Maintains a queue of experiments in `QUEUED_FOR_BACKTEST` state.
- Uses resource telemetry and policies to decide when it is safe to launch backtests:
  - respects resource classes (IO/CPU/GPU) and priority tiers,
  - never violates trading-critical DAG SLOs,
  - can be configured with quiet windows (e.g. overnight, weekends) where it is more aggressive.
- When a window is available, submits backtest jobs for one or more experiments and tracks their lifecycle.

This makes Kronos effectively **self-testing**: it can explore its own config ideas in the background and only escalate the promising ones—with completed backtests—to you for review.

### 9.2 Negative control experiments

Kronos also manages **negative control experiments** using the Negative Config Suite (see 180):

- Certain experiments have `expected_outcome = "NEGATIVE_CONTROL"` and are backed by deliberately bad configs.
- The Meta Backtest Scheduler periodically runs these experiments through the same backtest + scenario batteries used for normal candidates, subject to low priority and resource limits.
- Gating policies are expected to **reject** all negative controls; if any negative control would qualify for promotion under current numeric rules, Kronos:
  - raises an alert,
  - flags the gating logic, metrics, or data pipeline as suspect,
  - and prevents automatic promotion actions until the issue is investigated.

This turns obviously bad configs into a standing regression test for the entire evaluation stack, not just individual functions.

---

## 10. Monitoring & UI

Kronos drives the **Meta & Experiments** panel and Kronos Chat described in 200:

- Shows:
  - active configs per engine and their performance.
  - experiments and their status.
  - change logs (which configs went live when, why).

This spec, combined with the decision logging in 020 and the Monitoring/UI spec 200, defines how Kronos v2 sits as the “brain on top of the brains,” without directly pulling any triggers.