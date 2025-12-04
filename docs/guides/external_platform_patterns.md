# External Quant Platform Patterns – LEAN, Backtrader, QLib

This note captures what Prometheus v2 should borrow from three well-known open-source quant platforms **without** changing our core architecture:

- **LEAN** (QuantConnect) – event-driven trading engine with strong execution & brokerage modeling.
- **Backtrader** – Python backtesting framework with clean strategy/analyzer APIs.
- **QLib** (Microsoft) – AI-oriented quant research platform with factor/label/ML workflows.

The goal is to treat them as **pattern libraries**, not replacements.

## 1. LEAN (QuantConnect)

### 1.1 What LEAN is good at

Key properties of LEAN’s engine and ecosystem:

- **Event-driven algorithm engine**
  - Strategies subclass `QCAlgorithm`; the engine manages data feeds, portfolio state, orders, fills, and scheduled events.
  - The engine synchronizes requested data, injects it into the algorithm, processes orders, and updates portfolio automatically. citeturn1search9turn1search0

- **Rich modular plugin interfaces**
  - Pluggable handlers (core interfaces):
    - `IDataFeed` – backtest data from disk vs live streaming feeds.
    - `ITransactionHandler` – order routing, fill modeling, brokerage integration.
    - `IResultHandler` – metrics, logs, charting, reporting.
    - `IRealtimeHandler` – scheduled/time-based events.
    - `ISetupHandler` – algorithm initialization, starting capital, subscriptions. citeturn1search1turn1search3
  - Strong separation between **strategy code** and **engine plumbing**.

- **Reality modeling for portfolios**
  - Survivorship-bias-free data: automatic handling of splits, dividends, listings, delistings. citeturn1search3
  - Brokerage models for margin, fees, cash accounts, settlement, option assignment, shorting rules, etc. citeturn1search3turn1search6

- **Universe selection & scheduled events**
  - Built-in concept of **Universe Selection** to dynamically construct asset universes.
  - Scheduling API for time-based callbacks (`OnEndOfDay`, specific times, etc.), unified across backtest/live. citeturn1search3turn1search9

### 1.2 Patterns Prometheus should borrow

1. **Execution / brokerage modeling pattern**
   - Define explicit, pluggable components for:
     - Order routing & fill simulation (our Execution Service / Transaction model).
     - Fee & slippage models.
     - Margin/borrowing & cash/settlement models.
   - Use LEAN’s pattern of **interfaces + default models** so we can swap broker models per strategy or per environment.

2. **Engine plugin boundaries**
   - Mirror LEAN’s clear responsibilities:
     - DataFeed ↔ our Data & Encoders.
     - TransactionHandler ↔ our Execution + broker model.
     - ResultHandler ↔ our Monitoring & Decision Logging (Meta-Orch inputs).
     - RealtimeHandler ↔ our Scheduling / pipeline DAG.
   - Keep Prometheus engines (Regime, STAB, Assessment, Universe, Portfolio) as **pure numeric/decision engines**, and treat execution as a separate plugin layer.

3. **Universe selection as a first-class engine**
   - LEAN’s Universe Selection is conceptually similar to our Universe Engine.
   - Pattern to copy: treat **universe decisions as pluggable models** with their own configs and logs, not just filters sprinkled inside strategies.

4. **Scheduled events & state machine**
   - Use their scheduling concept to inform our orchestration:
     - Time-based triggers (EOD, weekly, monthly) for runs.
     - Regime-/event-based intraday triggers.
   - Our `EngineRun`/`RunPhase` pipeline already resembles this; we should keep leaning into that pattern.

### 1.3 What we should *not* copy from LEAN

- **Single-algorithm-centric design**
  - LEAN revolves around one `QCAlgorithm` class that owns alpha, risk, and portfolio logic.
  - Prometheus’ edge is in **multi-engine, stateful separation** (Regime, STAB, Profiles, Assessment, Universe, Portfolio, Meta).
  - We should not collapse our engines into a monolithic “strategy” class.

- **Tightly integrated research + live loops**
  - LEAN’s research/backtest/live cycle is heavily tied to its own project and cloud tooling.
  - Prometheus should stay DB/engine-first and allow multiple research front-ends (Jupyter, scripts, LLM tooling) without forcing a LEAN-style project tree.

---

## 2. Backtrader

### 2.1 What Backtrader is good at

Backtrader is a pure-Python backtesting & live trading framework with a strong focus on ergonomics and extensibility. citeturn2search2turn2search1

Key traits:

- **Simple, expressive strategy API**
  - Users subclass `bt.Strategy` / `bt.SignalStrategy` and implement methods like `next()`, `notify_order`, `notify_trade`.
  - A central `Cerebro` engine wires data feeds, broker, strategies, analyzers, and runs the backtest.

- **Composable building blocks**
  - Data feeds: CSV, Pandas, live brokers.
  - Broker abstraction: commission models, order types, slippage, margin.
  - Sizers: position sizing policies.
  - Indicators: 100+ built-in indicators + easy custom ones.
  - Analyzers: Sharpe, returns, drawdowns, etc., plug into any backtest. citeturn2search2turn2search6

- **Strong plotting & inspection tools**
  - Built-in matplotlib integration (`cerebro.plot()`) for inspecting strategies visually. citeturn2search11turn2search2

### 2.2 Patterns Prometheus should borrow

1. **Analyzer pattern for backtests**
   - Backtrader’s analyzers are small, pluggable components that compute metrics over a backtest run.
   - For Prometheus’ **book/backtest harness**, we should:
     - Define analyzer-like modules (e.g. `SharpeByRegime`, `MaxDDByStabBucket`, `TurnoverStats`).
     - Let Meta-Orchestrator consume these metrics per config.

2. **DataFeed/Broker/Sizer separation**
   - Map to our world as:
     - DataFeed → our historical_db + DataReader + Encoders.
     - Broker → our Execution Service + brokerage models.
     - Sizer → our PortfolioModel inside the Portfolio & Risk Engine.
   - Keep those boundaries clean so we can reuse portfolio models across books and change execution assumptions independently.

3. **Developer ergonomics**
   - For research users, we can provide a **thin wrapper API** similar to Backtrader’s:
     - e.g. a “strategy harness” to run Prometheus engines on a subset of instruments with minimal boilerplate, and attach analyzers.
   - Borrow their style for quick experiments while keeping the core engines DB-driven.

### 2.3 What we should *not* copy from Backtrader

- **Strategy-as-everything model**
  - In Backtrader the `Strategy` owns indicator logic, alpha, risk, sizing, and sometimes even data selection.
  - Prometheus intentionally decomposes those concerns into engines; we must not re-introduce a monolith.

- **No explicit shared state layer**
  - Backtrader does not have first-class regimes, stability vectors, or profile embeddings.
  - We should not try to retrofit those into a Backtrader-like API; instead, keep our shared spaces (regimes/STAB/profiles) as DB-backed objects that backtests read from.

---

## 3. QLib (Microsoft)

### 3.1 What QLib is good at

QLib is an AI-oriented quant research platform focusing on **factors, ML models, and workflows** rather than live execution. citeturn0search0

Core capabilities:

- **Full ML pipeline for factors & labels**
  - Data layer with standardized Alpha datasets (e.g. Alpha158, Alpha360).
  - Factor definitions as configs; labels typically forward returns over given horizons.
  - Workflow configs (`qrun` YAML) that define:
    - data sets (features/labels),
    - model (LightGBM, XGBoost, NN, etc.),
    - training/validation/test periods,
    - evaluation metrics (IC, rank IC, backtest metrics).

- **Research workflow automation**
  - `qrun` CLI to execute complete workflows from config.
  - Support for rolling retraining, model serving, high-frequency examples, and recently ML/RL pipelines. citeturn0search0

- **Factor zoo & experiment management**
  - Many baseline models and datasets preconfigured.
  - Emphasis on comparing models consistently using standardized data and metrics.

### 3.2 Patterns Prometheus should borrow

1. **Config-driven factor/label definitions for Assessment**
   - For each Assessment model (e.g. `Assessment_US_EQ_20d`), define:
     - A **feature spec**: which fields from `(p, r, s, price features, text)` go into the model.
     - A **label spec**: `forward_return_H` (or alpha vs factor model) as training target.
   - Mirror QLib’s pattern of a **dataset config** driving both training and evaluation.

2. **Experiment/workflow abstraction**
   - Introduce a light equivalent of QLib’s `qrun`:
     - For Prometheus: a “workflow config” that describes:
       - scope (e.g. `US_EQ`),
       - horizon(s),
       - model IDs,
       - train/val/test time ranges,
       - metrics and analyzers to run.
   - This can be implemented using our `engine_configs` + a simple CLI around Assessment training and sleeve backtests.

3. **Time-based splits and rolling retraining discipline**
   - Adopt QLib’s norm of:
     - Strict chronological splits,
     - Rolling windows for retraining Assessment models,
     - Re-evaluating models as underlying tape grows.

4. **Standard evaluation metrics**
   - Use QLib’s IC/rank-IC and backtest metrics as part of our **Assessment-level** evaluation, not just portfolio-level.
   - This gives Meta-Orchestrator richer signals for “is this model still working?” even before looking at portfolio P&L.

### 3.3 What we should *not* copy from QLib

- **Tight coupling of research & live execution into one stack**
  - QLib does include backtesting and some portfolio logic, but it’s primarily a research platform.
  - Prometheus should keep **live execution** and engine orchestration decoupled from the ML experiment runner.

- **QLib’s internal data formats**
  - We already have a rich Postgres schema and encoders; we shouldn’t try to mirror QLib’s internal file layout or dataset formats.
  - Instead, we treat our DB as the source of truth and build QLib-like datasets from it.

---

## 4. Cross-cutting guidance for Prometheus

### 4.1 Where to leverage LEAN patterns

- **Execution layer and live trading**
  - When implementing `prometheus/execution` and any broker adapters, follow LEAN’s:
    - split between data feed, transaction handler, result handler, realtime handler,
    - explicit brokerage/margin/fee models.
- **Universe selection & scheduled tasks**
  - Keep **Universe Engine** as a distinct, pluggable component.
  - Use a scheduling model (like LEAN’s realtime handler) inside our pipeline (`EngineRun` phases) for EOD runs and special event triggers.

### 4.2 Where to leverage Backtrader patterns

- **Backtesting harness & analyzers**
  - Build a Prometheus backtest runner around books/sleeves that:
    - attaches analyzer-style components for metrics (Sharpe, drawdowns, turnover, regime-sliced metrics),
    - makes it easy to add/remove analyzers without touching core engine logic.
- **Developer UX for experiments**
  - Consider a small “strategy harness” or notebook API that wraps engines and analyzers in a Backtrader-like way purely for research convenience.

### 4.3 Where to leverage QLib patterns

- **Assessment training pipeline**
  - Implement factor/label dataset specs for each Assessment model,
  - Use config-driven training/evaluation similar to QLib workflows.
- **Meta-Orchestrator analytics**
  - Use QLib-style metrics (IC, rank-IC, information ratio) as first-class metrics for configs, not just portfolios.

### 4.4 What stays uniquely Prometheus

- **Stateful shared spaces**: regime embeddings, STAB vectors, profile embeddings, fragility measures.
- **Multi-engine architecture**: Regime, STAB, Profiles, Black Swan, Assessment, Universe, Portfolio, Meta.
- **Books/sleeves concept**: multiple portfolios with different scopes/horizons, mixed by Meta-Orchestrator.

External platforms should inform how we *implement* pieces (execution modeling, analyzers, ML workflows), but not change this core architecture.