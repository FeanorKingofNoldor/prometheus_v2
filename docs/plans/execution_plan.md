# Execution Plan – Build Order, File Structure & Interfaces

This document defines **how** to build the new system, bottom-up, and outlines the planned file structure and key interfaces for each player. It also covers how to design the LLM agents and which aspects of the system are dynamic vs static.

---

## 1. Build Order – Bottom-Up Phases

We build in layers. Each phase becomes the foundation for the next; no jumping ahead.

### Phase 0 – New Project Skeleton & Core Infrastructure

**Goals:**
- Create new repo / package skeleton (no business logic yet).
- Establish core utilities and patterns.

**Tasks:**
- Create root package (e.g. `trading_system_v2/`).
- Core modules:
  - `trading_system_v2/core/config.py` – env/config loader.
  - `trading_system_v2/core/logging.py` – structured logging.
  - `trading_system_v2/core/database.py` – DB connection factories (training/prod, historical/runtime).
  - `trading_system_v2/core/types.py` – shared type aliases and dataclasses for IDs (e.g. `CompanyId`, `UniverseId`, `RegimeId`).
- Set up dependency management and basic test harness.

**Dynamic vs static:**
- Static: core utilities, type definitions, logging format.
- Dynamic via config: DB URLs, environment (TRAINING vs PRODUCTION).

---

### Phase 1 – Database Schema & Migrations

**Goals:**
- Implement the schemas defined in the macro plan as SQL migrations / Alembic.

**Tasks:**
- Create migration files for:
  - Historical DB: `companies`, `equity_prices_daily`, `financial_statements`, `fundamental_ratios`, `macro_time_series`, `news_events`, `filings`, `earnings_calls`, `sp500_constituents`, `corporate_actions`.
  - Runtime DB: `stock_metrics`, `positions`, `trades`, `pipeline_decisions`, `risk_actions`, `regime_history`, `universe_snapshots`, `universe_members`, `company_profile_versions`, `company_profile_audit`, `company_current_profile`, `sector_profile_versions`, `sector_current_profile`, `black_swan_events`, `black_swan_state_history`, `black_swan_sop_actions`, `meta_controller_config_proposals`, core config tables.
- Add minimal helper script to run migrations.

**Dynamic vs static:**
- Schema is mostly static; we can add columns via migrations later.

---

### Phase 2 – Data Ingestion & Normalization Service

**Depends on:** Phases 0–1.

**Goal:**
- Implement `data_ingestion` module and wire it to historical DBs.

**File structure:**

```text
trading_system_v2/data_ingestion/__init__.py
trading_system_v2/data_ingestion/sources/market_data_client.py
trading_system_v2/data_ingestion/sources/fundamentals_client.py
trading_system_v2/data_ingestion/sources/macro_data_client.py
trading_system_v2/data_ingestion/sources/news_client.py
trading_system_v2/data_ingestion/sources/filings_client.py

trading_system_v2/data_ingestion/normalizers/market_normalizer.py
trading_system_v2/data_ingestion/normalizers/fundamentals_normalizer.py
trading_system_v2/data_ingestion/normalizers/macro_normalizer.py
trading_system_v2/data_ingestion/normalizers/news_normalizer.py
trading_system_v2/data_ingestion/normalizers/filings_normalizer.py

trading_system_v2/data_ingestion/writers/historical_db_writer.py
trading_system_v2/data_ingestion/validation/dq_rules.py
trading_system_v2/data_ingestion/validation/dq_runner.py

trading_system_v2/data_ingestion/orchestration/daily_pipeline.py
trading_system_v2/data_ingestion/orchestration/event_driven_pipeline.py

trading_system_v2/data_ingestion/api.py
```

**Key interfaces (function prototypes):**

```python
# api.py
from datetime import date, datetime
from typing import Optional


def run_daily_ingestion(run_date: date) -> None:
    """Fetch and load all daily data (prices, daily macro, corporate actions) for run_date."""


def run_fundamentals_ingestion(since: Optional[datetime] = None) -> None:
    """Fetch and load fundamentals and filings updated since the given timestamp."""


def run_news_ingestion(since: Optional[datetime] = None) -> None:
    """Fetch and load news/events updated since the given timestamp."""


def get_last_ingestion_status(component: str) -> dict:
    """Return last ingestion run status for the given component (for monitoring)."""
```

**Dynamic vs static:**
- Dynamic: provider list, endpoints, symbol mappings, schedules, in config tables.
- Static: normalization logic and canonical schemas.

---

### Phase 3 – Macro Regime Service

**Depends on:** Phases 0–2.

**File structure:**

```text
trading_system_v2/macro/__init__.py
trading_system_v2/macro/indicators/yield_curve_indicator.py
trading_system_v2/macro/indicators/credit_spread_indicator.py
trading_system_v2/macro/indicators/volatility_indicator.py

trading_system_v2/macro/models/regime_model.py
trading_system_v2/macro/engine.py
trading_system_v2/macro/storage.py
trading_system_v2/macro/api.py
```

**Key interfaces:**

```python
# api.py
from datetime import date
from typing import Dict, Any


def compute_regime_for_date(d: date) -> None:
    """Compute and persist regime for a single date into regime_history."""


def backfill_regimes(start_date: date, end_date: date) -> None:
    """Compute regimes for a historical range."""


def get_regime(as_of_date: date) -> Dict[str, Any]:
    """Return regime dict with id, name, sub_stage, scores, confidence."""


def get_regime_series(start_date: date, end_date: date) -> list[Dict[str, Any]]:
    """Return regime series over the date range."""
```

**Dynamic vs static:**
- Static: indicator computation code, transformation logic.
- Dynamic: thresholds, regime names, model parameters in config.

---

### Phase 4 – Profile Service (Companies & Sectors)

**Depends on:** Phases 0–3 (needs DB, macro, ingestion data).

**File structure:**

```text
trading_system_v2/profiles/__init__.py
trading_system_v2/profiles/models.py
trading_system_v2/profiles/storage.py

trading_system_v2/profiles/builders/company_profile_builder.py
trading_system_v2/profiles/builders/sector_profile_builder.py

trading_system_v2/profiles/updaters/company_profile_updater.py
trading_system_v2/profiles/updaters/sector_profile_updater.py

trading_system_v2/profiles/api.py
```

**Key interfaces:**

```python
# api.py
from datetime import date
from typing import Optional, Dict, Any


def build_initial_company_profiles() -> None:
    """Build initial profiles for all companies using available historical data."""


def update_company_profile(company_id: int) -> None:
    """Rebuild profile for a single company after new events."""


def update_profiles_for_new_events(since: date) -> None:
    """Scan for new filings/events since date and update affected profiles."""


def get_company_profile_by_ticker(ticker: str, as_of_date: Optional[date] = None) -> Dict[str, Any]:
    """Return profile snapshot for a ticker as of a date (or current)."""


def get_sector_profile(sector_id: str, as_of_date: Optional[date] = None) -> Dict[str, Any]:
    """Return sector profile snapshot."""
```

**Dynamic vs static:**
- Static: profile field schema, core aggregation logic.
- Dynamic: scoring weights, narrative prompt templates, generator versions in config.

---

### Phase 5 – Universe Selection Service

**Depends on:** Phases 0–4.

**File structure:**

```text
trading_system_v2/universe/__init__.py
trading_system_v2/universe/analyzer/performance_analyzer.py
trading_system_v2/universe/analyzer/factor_analyzer.py

trading_system_v2/universe/builder/universe_builder.py
trading_system_v2/universe/storage.py
trading_system_v2/universe/api.py
```

**Key interfaces:**

```python
# api.py
from datetime import date
from typing import Dict, Any


def precompute_cycle_performance() -> None:
    """Compute and store cycle performance metrics for companies/sectors."""


def build_universe(as_of_date: date, regime_id: int, strategy_id: str) -> int:
    """Build universe snapshot and return universe_id."""


def get_universe(universe_id: int) -> Dict[str, Any]:
    """Return universe metadata and member list."""
```

**Dynamic vs static:**
- Static: computations, constraints application code.
- Dynamic: strategy-specific filters and scoring weights in config.

---

### Phase 6 – Backtesting Engine

**Depends on:** Phases 0–5.

**File structure:**

```text
trading_system_v2/backtesting/__init__.py
trading_system_v2/backtesting/time_machine.py
trading_system_v2/backtesting/market_simulator.py
trading_system_v2/backtesting/portfolio.py
trading_system_v2/backtesting/engine.py
trading_system_v2/backtesting/storage.py
trading_system_v2/backtesting/api.py
```

**Key interfaces:**

```python
# api.py
from datetime import date
from typing import Dict, Any


def run_backtest(run_config: Dict[str, Any]) -> int:
    """Run a backtest with given config and return run_id."""


def get_backtest_results(run_id: int) -> Dict[str, Any]:
    """Return summary metrics and possibly equity curve info."""
```

**Dynamic vs static:**
- Static: simulation engine, PnL math.
- Dynamic: strategy configs, risk configs, scenario definitions.

---

### Phase 7 – Assessment Engine v2 (Decision Layer)

**Depends on:** Phases 0–6.

**File structure:**

```text
trading_system_v2/assessment/__init__.py
trading_system_v2/assessment/context_builder.py

trading_system_v2/assessment/agents/fundamental_agent.py
trading_system_v2/assessment/agents/technical_agent.py
trading_system_v2/assessment/agents/risk_aware_agent.py
trading_system_v2/assessment/agents/synthesis_agent.py

trading_system_v2/assessment/orchestrator.py
trading_system_v2/assessment/storage.py
trading_system_v2/assessment/api.py

trading_system_v2/assessment/llm/llm_client.py
trading_system_v2/assessment/llm/prompt_templates.py
trading_system_v2/assessment/llm/agent_graph_config.py
```

**Key interfaces:**

```python
# api.py
from datetime import date
from typing import Dict, Any, List


def run_assessment_cycle(as_of_date: date, regime_id: int, universe_id: int, strategy_id: str) -> List[Dict[str, Any]]:
    """Run assessment for all tickers in universe, return list of decision objects."""
```

**Dynamic vs static:**
- Static: structure of `DecisionContext`, agent roles, orchestrator rules.
- Dynamic: LLM model names, prompts, weights for how agents are combined.

**LLM Agents Design (high level):**
- `llm_client.py` wraps chosen LLM provider(s) with:
  - Functions like `call_model(model_name: str, prompt: str, params: dict) -> str`.
- `prompt_templates.py` loads templates from `prompt_templates` config table.
- `agent_graph_config.py` defines which agents run, in what order, and how outputs are combined.
- Agents:
  - Receive `DecisionContext` → convert to prompt input → call `llm_client` → parse output into structured recommendation.

---

### Phase 8 – Risk Management Service

**Depends on:** Phases 0–7.

**File structure:**

```text
trading_system_v2/risk/__init__.py
trading_system_v2/risk/constraints.py
trading_system_v2/risk/exposure_calculator.py
trading_system_v2/risk/engine.py
trading_system_v2/risk/storage.py
trading_system_v2/risk/api.py
```

**Key interfaces:**

```python
# api.py
from typing import List, Dict, Any


def apply_risk_constraints(decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Given decisions from Assessment, return final target positions with risk annotations."""
```

**Dynamic vs static:**
- Static: structure of constraints and exposure calculations.
- Dynamic: specific limit values and flags from `risk_configs`.

---

### Phase 9 – Execution Service

**Depends on:** Phases 0–8.

**File structure:**

```text
trading_system_v2/execution/__init__.py
trading_system_v2/execution/order_planner.py
trading_system_v2/execution/broker_adapters/ibkr_adapter.py
trading_system_v2/execution/simulated_execution.py
trading_system_v2/execution/router.py
trading_system_v2/execution/storage.py
trading_system_v2/execution/api.py
```

**Key interfaces:**

```python
# api.py
from typing import List, Dict, Any


def apply_execution_plan(target_positions: List[Dict[str, Any]], mode: str = "PRODUCTION") -> None:
    """Turn target positions into orders and send to broker or simulator depending on mode."""
```

**Dynamic vs static:**
- Static: order planning and routing logic.
- Dynamic: broker endpoints, order type preferences in config.

---

### Phase 10 – Black Swan Emergency Engine

**Depends on:** Phases 0–3, 2, 6 (for SOP tuning) but can be developed after core flows.

**File structure:**

```text
trading_system_v2/black_swan/__init__.py
trading_system_v2/black_swan/signal_ingestion.py
trading_system_v2/black_swan/event_detector.py
trading_system_v2/black_swan/state_manager.py
trading_system_v2/black_swan/sop_engine.py
trading_system_v2/black_swan/storage.py
trading_system_v2/black_swan/api.py

trading_system_v2/black_swan/llm/llm_client.py
trading_system_v2/black_swan/llm/prompt_templates.py
```

**Key interfaces:**

```python
# api.py
from typing import Dict, Any


def update_black_swan_state() -> None:
    """Ingest latest signals, update state, and record events/SOP actions."""


def get_black_swan_state() -> Dict[str, Any]:
    """Return current emergency state and metadata."""


def get_active_black_swan_event() -> Dict[str, Any] | None:
    """Return latest high-severity event, if any."""


def get_sop_actions_for_component(component: str) -> list[Dict[str, Any]]:
    """Return SOP actions that apply to a given component (RISK, ASSESSMENT, etc.)."""
```

**Dynamic vs static:**
- Static: state machine structure (NORMAL/ELEVATED_RISK/EMERGENCY) and integration points.
- Dynamic: source lists, keywords, SOP templates, LLM prompts.

---

### Phase 11 – Meta Orchestrator (Kronos v2)

**Depends on:** Phases 0–10.

**File structure:**

```text
trading_system_v2/meta/__init__.py
trading_system_v2/meta/data_aggregator.py
trading_system_v2/meta/analysis.py
trading_system_v2/meta/proposal_generator.py
trading_system_v2/meta/storage.py
trading_system_v2/meta/api.py

trading_system_v2/meta/llm/llm_client.py
trading_system_v2/meta/llm/prompt_templates.py
```

**Key interfaces:**

```python
# api.py
from typing import Dict, Any


def run_meta_analysis() -> None:
    """Run diagnostics and write proposals into meta_controller_config_proposals."""


def get_pending_proposals() -> list[Dict[str, Any]]:
    """Return proposals awaiting review or application."""
```

**Dynamic vs static:**
- Static: analysis patterns and data aggregation.
- Dynamic: thresholds for what constitutes underperformance, prompt templates for proposal explanations.

---

### Phase 12 – Monitoring & Observability

**Depends on:** All earlier phases emitting metrics/logs.

**File structure:**

```text
trading_system_v2/monitoring/__init__.py
trading_system_v2/monitoring/metrics.py
trading_system_v2/monitoring/logging_setup.py
trading_system_v2/monitoring/dashboards.py
trading_system_v2/monitoring/alerts.py
```

**Key interfaces:**

```python
# metrics.py

def record_metric(name: str, value: float, tags: dict | None = None) -> None:
    """Emit a numeric metric with optional tags."""
```

**Dynamic vs static:**
- Static: logging/metrics API shape.
- Dynamic: which alerts and dashboards to define.

---

### Phase 13 – Configuration & Strategy Management

**Depends on:** Phases 0–1.

This can be partially implemented earlier, but full integration requires other components.

**File structure:**

```text
trading_system_v2/config_mgmt/__init__.py
trading_system_v2/config_mgmt/models.py
trading_system_v2/config_mgmt/storage.py
trading_system_v2/config_mgmt/api.py
trading_system_v2/config_mgmt/versioning.py
```

**Key interfaces:**

```python
# api.py
from typing import Dict, Any


def get_strategy_config(strategy_id: str) -> Dict[str, Any]:
    """Load current strategy config with version_id."""


def get_risk_config(scope: str, scope_id: str | None = None) -> Dict[str, Any]:
    """Load risk config for given scope (GLOBAL/STRATEGY/ACCOUNT)."""


def get_prompt_template(template_id: str) -> Dict[str, Any]:
    """Return prompt template text + metadata for a given id."""
```

**Dynamic vs static:**
- Static: schema of configs.
- Dynamic: actual config values and versions.

---

## 2. LLM Agents – Design Principles & Dynamic Parts

### 2.1 Shared Design Principles

- **No raw web access in agents:** all context comes from DB and profiles; ingestion handles web.
- **Deterministic enough:** store model name, prompt template id, and key parameters.
- **Structured outputs:** agents must return structured JSON-like data, parsed by our code.
- **Pluggable models:** model names, providers, and temperature settings come from config.

### 2.2 LLM Layers per Player

- **Profile Service:**
  - Uses LLMs in `company_profile_builder` and `sector_profile_builder` for narratives and strengths/weaknesses.
  - Prompts include structured fundamentals and key metrics.
- **Assessment Engine v2:**
  - Agents interpret profiles + market context and output decisions.
  - Prompts are tightly constrained and focused on decision-making, not data fetching.
- **Black Swan Engine:**
  - Event detector uses LLMs to classify events and summarize crises.
- **Meta Orchestrator:**
  - Uses LLMs to draft human-readable rationales for proposals and group patterns.

### 2.3 Dynamic vs Static in LLM Design

- **Static:**
  - Code structure for agents, how prompts are constructed from context objects.
  - Parsing logic for LLM outputs.
- **Dynamic:**
  - Model names (e.g. `gpt-4o-mini`, `gpt-4.1`, etc.).
  - Prompt templates and system messages.
  - Weights/parameters controlling randomness and cost.

---

## 3. Data Source Strategy – Backtesting vs Live

- **Training / backtesting:**
  - Historical data (prices, fundamentals, macro, news) primarily from offline sources such as Bloomberg CSV exports and any other historical datasets you provide.
  - Data is loaded into `training_historical` via ad-hoc import scripts that use the same `data_ingestion` normalization and writer logic.
- **Live / production (initial phase):**
  - Use open-source / free APIs for *current* data (prices, macro, fundamentals, news) wired through the `*_client` modules.
  - Later, when paid feeds are available, swap in new provider clients that write into the same tables and follow the same ingestion semantics.
- **Provider-agnostic design:**
  - All external providers (free or paid, APIs or CSVs) plug into the same ingestion interfaces and canonical schemas.

## 4. Documentation & Enforcement Overview

- Every module must have a top-level docstring explaining its role and side effects.
- Every public function/class (especially those in `api.py` modules) must have a structured docstring (Google-style: summary, Args, Returns, Raises).
- Each subsystem has:
  - A planning document in `new_project_plan/` (these files).
  - A matching markdown doc under `docs/` in the new repo describing its role, main APIs, and key algorithms.
- Tooling:
  - Use a linter (e.g. ruff with pydocstyle rules) to enforce presence of docstrings on public APIs.
  - Optionally, generate reference docs from docstrings and `docs/*.md` using mkdocs or similar later.

## 5. Summary

- Build strictly bottom-up: core → DB → ingestion → macro → profiles → universe → backtesting → assessment → risk → execution → black swan → meta → monitoring → config integration.
- Each player now has:
  - A defined directory structure.
  - Key modules and function prototypes.
  - Clear inbound/outbound data contracts.
- LLM components are treated as services behind `llm_client` modules, with all dynamic aspects (models, prompts, weights) in config, and all static structure (contexts, parsing, agent graphs) in code.
- Ingestion is atomic per data unit (staging + swap), and the data source layer is explicitly designed to start with free/open live sources and backtesting CSVs, then swap to paid feeds without changing schemas.
- Documentation is a first-class requirement, with conventions and linting to enforce it from day one.

We will implement each phase in order, only moving up once the current layer’s contracts, documentation, and tests are stable.
