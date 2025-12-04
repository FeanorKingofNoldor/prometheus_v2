# 010 – Prometheus v2 Foundations

## 1. Purpose

This document fixes global architectural choices for Prometheus v2 so that all engine and infrastructure specs (020+, 100–170) are consistent.

It defines:
- Tech stack assumptions.
- Package/directory layout.
- Configuration conventions.
- ID and naming conventions.
- Time and calendar rules.
- Type and error-handling conventions.

No engine implementation should violate these foundations.

---

## 2. Tech Stack

### 2.1 Language & Runtime
- Language: **Python 3.11+**.
- Type checking: **mypy** (or equivalent) with `--strict` for core modules.
- Style: **PEP8** + project-specific rules (refer to `documentation_standards.md`).

### 2.2 Core Libraries
- Numerical: `numpy`, `pandas`.
- ML / DL: `pytorch` (primary), `scikit-learn` for classical models.
- Database: `psycopg2` or `asyncpg` (Postgres client), plus ORM if needed (e.g. `SQLAlchemy`) for runtime DB.
- Config: `pydantic` for typed configs, plus `yaml` for config files.
- Time & calendars: `pandas`, `python-dateutil`, custom trading calendar module.
- Testing: `pytest`.

*(Exact library versions will be pinned in `pyproject.toml` or `requirements.txt`.)*

---

## 3. Package & Directory Layout

Top-level layout (Python packages only):

- `prometheus/core/`
  - Config loading, logging setup, DB connections, ID utilities, shared types.
- `prometheus/data/`
  - Data access layer (readers for historical_db and runtime_db).
  - Feature builders (numeric windows, panel extraction).
- `prometheus/encoders/`
  - Text encoders, numeric time-series encoders, joint embedding models.
- `prometheus/profiles/`
  - Profile service (ProfileSnapshot, builders, updaters) as per `035_profiles.md`.
- `prometheus/regime/`
  - Regime Engine implementation.
- `prometheus/stability/`
  - Stability & Soft-Target Engine implementation (continuous stability + scenario-based fragility).
- `prometheus/assessment/`
  - Assessment Engine, including Fragility Alpha (`135_fragility_alpha.md`) and other alphas.
- `prometheus/universe/`
  - Universe Selection Engine implementation.
- `prometheus/portfolio/`
  - Portfolio & Risk Engine implementation.
- `prometheus/meta/`
  - Meta-Orchestrator (Kronos v2): decision logs, analytics, config optimization.
- `prometheus/synthetic/`
  - Synthetic Scenario Engine.
- `prometheus/monitoring/`
  - Monitoring & observability (metrics, dashboards, alerts, optional web frontend).
- `prometheus/execution/`
  - Execution services (broker adapters, routers, simulated execution) – to be aligned with v2 specs later.
- `prometheus/scripts/`
  - CLI entrypoints for running backtests, daily cycles, migrations, etc.

Specs live under `docs/specs/*.md` and are the source of truth.

---

## 4. Configuration Conventions

### 4.1 Config stack

- Base configs in `configs/*.yaml`.
- Engine-specific configs in `configs/{engine_name}/*.yaml`.
- Environment overlays via:
  - Environment variables, or
  - `configs/env/{env_name}/*.yaml`.

### 4.2 Config objects

- Use `pydantic` models for all configs.
- Each engine defines a `Config` class in its package, e.g. `prometheus/regime/config.py`:

```python
from pydantic import BaseModel

class RegimeConfig(BaseModel):
    window_length_days: int
    num_clusters: int
    min_regime_duration_days: int
    model_id_numeric: str
    model_id_text: str
```

- Configs are immutable at runtime (no in-place mutation); changes go through Meta-Orchestrator, logged and versioned.

### 4.3 Config loading

- Central loader in `prometheus/core/config.py`:
  - resolves base + engine + env overlays,
  - instantiates typed config models,
  - exposes read-only config trees.

---

## 5. ID & Naming Conventions

### 5.1 Entities

- `instrument_id`: string, unique across all financial instruments.
  - Format: `"{asset_class}:{native_symbol_or_code}"` (exact format to be refined in 020).
- `issuer_id`: string, unique for each issuer (company, sovereign, etc.).
- `portfolio_id`, `strategy_id`, `engine_id`: strings, short and stable.

### 5.2 Configs & models

- `config_id`: `{engine_name}_v{major}.{minor}` or `{engine_name}_{hash}`.
- `model_id`: short string referencing model artifacts and training metadata, e.g. `"text-encoder-v1"`, `"joint-embed-v2"`.

### 5.3 Decisions & contexts

- `decision_id`: globally unique (e.g. UUIDv4), stored in `engine_decisions`.
- `context_id`: identifies the decision context (e.g. `{date}_{portfolio_id}_{strategy_id}`), used to tie together multiple engine outputs.

---

## 6. Time & Calendar Conventions

- All timestamps in DB are stored in **UTC**.
- `as_of_date` means:
  - For daily engines: end-of-day in the relevant trading calendar, based on close.
  - For intraday engines (if any later): specify both `as_of_date` and `as_of_time` in UTC.

- A central **TradingCalendar** abstraction in `prometheus/core/time.py` provides:
  - `is_trading_day(exchange, date)`
  - `get_prev_trading_day(exchange, date, n)`
  - `get_next_trading_day(exchange, date, n)`
  - `trading_days_between(exchange, start_date, end_date)`

- All engines must:
  - Use `as_of_date` explicitly in public APIs.
  - Avoid implicitly “using now()” without it being passed in.

---

## 7. Types & Error Handling

### 7.1 Types

- Use type hints everywhere in public APIs and core logic.
- Prefer `dataclasses` / pydantic models for structured results (e.g. `RegimeState`, `StabilityVector`, `FragilityAlphaResult`).
- Embeddings:
  - Represented as `numpy.ndarray` or `torch.Tensor` consistently within a given layer.
  - Public APIs should clarify which they return.

### 7.2 Errors & logging

- Do not silently swallow exceptions in engine boundaries.
- Use a central logger (from `prometheus/core/logging.py`).
- For recoverable issues (e.g., missing data for one instrument):
  - Log with warning level; degrade gracefully.
- For unrecoverable issues (schema violations, config errors):
  - Raise explicit custom exceptions (e.g., `ConfigError`, `DataSchemaError`).

---

## 8. Cross-Cutting Design Rules

1. **Backtestability**
   - Every engine API that affects trading or risk must:
     - Take `as_of_date` (and `as_of_time` if needed).
     - Only depend on data available up to that point.
     - Be reproducible given DB state + config + model versions.

2. **No hidden side effects in pure engines**
   - Regime, Stability, Black Swan, Assessment, Universe, Portfolio engines may read from DBs and write logs, but:
     - They should not directly execute trades.
     - Execution is handled by `prometheus/execution` based on explicit orders.

3. **LLMs are advisory, not authoritative**
   - Any use of decoder models (GPT-like) must:
     - Have a clear boundary (e.g., in `prometheus/meta/llm` or `prometheus/profiles/llm`).
     - Operate on already computed numeric facts.
     - Never directly commit trades or config changes without numeric validation + logging.

4. **Separation of representation vs decision vs optimization**
   - Encoders and Profiles: learn representations.
   - Assessment & Fragility Alpha: map representations + raw data to expected returns / scores.
   - Portfolio & Risk: solve optimization problems using those scores under constraints.
   - Meta-Orchestrator: adjust configs based on logged outcomes.

These foundations are the baseline constraints for all subsequent specs and implementations.