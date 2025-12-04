# Risk Management Service – Detailed Plan

## 1. Purpose & Scope

Consume proposed decisions from Assessment Engine v2 and enforce risk constraints (position sizing, exposures, liquidity, drawdowns), producing final target positions and risk rationales.


## 2. High-Level Architecture

Modules under `risk/`:

- `constraints/` – definitions of risk rules and constraints.
- `engine/` – applies constraints to candidate decisions.
- `exposure_calculator/` – computes current and projected exposures.
- `storage/` – logs risk actions and overrides.
- `api/` – entrypoint for producing final target positions.


## 3. Data Contracts

### 3.1 Inputs

- Proposed decisions from Assessment Engine v2.
- Portfolio state from runtime DB:
  - Positions, PnL, realized/unrealized risk metrics.
- Market data:
  - Liquidity metrics (ADV, bid/ask spreads, volatility) from `stock_metrics`.
- Config:
  - Per-strategy risk budgets.
  - Global caps (max gross/net exposure, sector caps, factor caps).
  - Per-name caps, leverage limits, drawdown thresholds.
- `black_swan_state` from Black Swan Engine.

### 3.2 Outputs

- Final target positions per ticker:
  - `ticker`, `target_position`, `delta_position`, `priority`.
  - `risk_reasoning_summary`.
- Risk logs table:
  - `risk_actions` with:
    - `action_id`, `timestamp`, `ticker`, `decision_id` (from pipeline_decisions),
    - `action_type` (SCALED_DOWN, REJECTED, CAPPED, OK),
    - `details_json`.


## 4. Risk Processing Flow

1. Receive list of decisions from Assessment Engine v2.
2. Load current positions and exposures.
3. For each decision:
   - Compute proposed position change.
   - Evaluate against constraints:
     - Per-name size limit.
     - Sector/country exposure limits.
     - Correlation cluster limits.
     - Liquidity constraints (%ADV, tick size, etc.).
     - Drawdown/sanity checks.
   - Under EMERGENCY state:
     - Tighter limits or forced de-risking based on emergency SOP.
4. Adjust decisions:
   - Scale down, cap, or reject as necessary.
   - Document reason in `risk_reasoning_summary` and `risk_actions`.
5. Produce final target positions list ordered by priority.


## 5. Interactions with Other Players

- **Assessment Engine v2**:
  - Input source; can be informed of systematic risk overrides for future learning.
- **Execution Service**:
  - Receives final target positions for order generation.
- **Meta Orchestrator**:
  - Reads `risk_actions` to understand how often risk constraints override strategy.
- **Black Swan Engine**:
  - Provides emergency state and SOP instructions.


## 6. Failure Modes & Safeguards

- If risk calculations fail or portfolio state cannot be loaded:
  - Default to maintaining or reducing risk (e.g. no new positions, allow only de-risking).
- If config is inconsistent (e.g. impossible constraints):
  - Log and alert, and default to conservative behavior.


## 7. Current Implementation Status (Phase 8 core)

- Implemented modules under `prometheus/risk/`:
  - `constraints.py` – defines `StrategyRiskConfig` and per-name limits
    (`apply_per_name_limit`), with conservative in-code defaults for
    `QUALITY_GROWTH_CORE` and a generic fallback.
  - `engine.py` – maps assessment decisions to proposed weights, applies
    per-name limits, logs `risk_actions`, and returns target weights with
    simple priorities and reasoning summaries.
  - `exposure_calculator.py` – helper to compute gross exposure from positions
    and prices (not yet wired into the main flow).
  - `storage.py` – helper to insert rows into `risk_actions`.
  - `api.py` – provides `apply_risk_constraints(decisions)` and
    `run_assessment_and_apply_risk(...)` glue across Assessment + Risk.
- Tests:
  - `tests/unit/test_risk_imports.py` – smoke tests for the public API.
  - `tests/unit/test_risk_engine_and_storage.py` – in-memory SQLite tests for
    per-name limits, `insert_risk_actions`, and end-to-end
    `apply_risk_constraints` behaviour.
- Dev workflows:
  - `dev_workflows/PHASE8_RISK.md` documents how to call the risk API directly
    and how to run Assessment + Risk together, and how to inspect `risk_actions`.


## 8. Deferred Enhancements / TODOs (later passes)

The following items are intentionally **not** part of the Phase 8 core and
should be implemented in later passes:

- Portfolio and exposure constraints
  - Implement `exposure_calculator`-driven checks for gross/net exposure,
    sector/factor caps, and correlation/cluster limits.
- Liquidity-aware risk
  - Use `stock_metrics` to enforce %ADV, volatility, and spread-based
    liquidity constraints.
- Emergency state integration
  - Incorporate `black_swan_state` into constraints and emergency SOPs,
    including forced de-risking behaviours.
- Config-driven parameters
  - Load risk parameters from `risk_configs` and `strategy_configs` instead
    of in-code defaults in `constraints.py`.
- Richer logging and observability
  - Extend `details_json` in `risk_actions` with structured exposure snapshots
    and risk rationale.
  - Add metrics/logging hooks for monitoring how often and how strongly
    strategies are modified by risk.
