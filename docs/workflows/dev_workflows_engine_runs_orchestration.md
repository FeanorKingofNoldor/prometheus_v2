# Dev Workflow  Engine Runs and Orchestration

This workflow describes how to operate the daily **engine_runs** state machine
in practice, and how orchestration should evolve over time.

It is intentionally written in three stages:

- **Short term (current recommended)**  use simple timers (cron/systemd) to
  call the existing CLIs as one-shot managers.
- **Medium term (optional)**  introduce a small long-running engine daemon
  that wraps the same helpers.
- **Long term**  plug the same state machine into a full DAG-based
  orchestrator (Airflow/Prefect/Dagster/custom).

The important invariant across all stages is:

> All workflow logic lives in the database and engine code
> (the **engine_runs** state machine and phase tasks). Orchestration layers
> only trigger state transitions; they do not contain business logic.

## 1. Short term  timer-driven CLIs (current recommended)

In this stage you rely on **cron** or **systemd timers** to call the existing
manager scripts at the right times. These timers are intentionally dumb: they
have no DAGs or branching logic and simply act as heartbeats.

### 1.1 Ensure runs exist and mark DATA_READY

After your daily EOD ingestion for a region has completed successfully
(prices, features, profiles, etc.), call:

```bash
python -m prometheus.scripts.run_engine_state \
  --as-of YYYY-MM-DD \
  --region US \
  --ensure \
  --data-ready
```

This does the following:

- Ensures there is exactly one **engine_runs** row for `(as_of_date, region)`.
- If the run is in `WAITING_FOR_DATA`, bumps it to `DATA_READY`.

You can repeat this safely; the transition is validated in
`prometheus.pipeline.state.update_phase`.

### 1.2 Periodically advance all active runs

Independently of ingestion, run a simple heartbeat every few minutes
(e.g. every 5 minutes):

```bash
python -m prometheus.scripts.run_engine_state --advance-all
```

This:

- Uses `list_active_runs` to find all runs not in `COMPLETED`/`FAILED`.
- Calls `advance_run(db_manager, run)` once per run.
- Lets the state machine decide what to do:
  - `WAITING_FOR_DATA`  log and no-op.
  - `DATA_READY`  compute Profiles/STAB/Assessment.
  - `SIGNALS_DONE`  build universes.
  - `UNIVERSES_DONE`  run books and finalise to `COMPLETED`.

You can schedule this with cron or systemd; the orchestrator does not need to
know anything about the phases or dependency graph.

### 1.3 Operational notes

- **Idempotence**: The phase tasks in `prometheus.pipeline.tasks` are designed
  to be idempotent; re-running them for the same `(date, region)` should be
  a no-op or overwrite with the same results.
- **Manual overrides**: In case of issues you can run
  `run_engine_state` manually with the same flags to inspect or fix runs.
- **Monitoring**: In early stages, monitoring can rely on:
  - Rows and timestamps in `engine_runs`.
  - Logs emitted by `run_engine_state` and the phase tasks.
  - The `show_engine_runs` CLI for a quick CSV view of run state.

This stage is sufficient for a single-node production setup and is the
recommended initial deployment model.

## 2. Medium term  engine daemon (optional)

Once you are comfortable with the short-term model, you may want to replace
multiple small timers with a single **long-running engine daemon** process.

The daemon would live in `prometheus.orchestration.engine_daemon` and:

- Use `TradingCalendar` to understand market days and closing windows.
- After ingestion confirms that data for `(date, region)` is complete,
  call the same helpers used by `run_engine_state`:
  - `get_or_create_run` / `update_phase(..., DATA_READY)`.
  - `list_active_runs` + `advance_run` in a loop with backoff.
- Expose basic health/metrics (e.g. last successful tick, runs in progress).

Functionally this is just a more integrated replacement for the shell-level
heartbeats in Section 1. The key constraints remain:

- The daemon must **not** embed business rules about phases or risk; those
  stay in the state machine and phase tasks.
- The daemon should be safe to restart at any time; it re-derives its world
  view from the `engine_runs` table.

This stage is **optional** before going live; you can remain on the
short-term model if operational complexity is low.

## 3. Long term  DAG-based orchestrator integration

For a larger multi-region system or cluster deployment, you can plug the
same state machine into a DAG-based orchestrator as described in the
`docs/specs/012_calendars_and_scheduling.md` and
`docs/specs/013_orchestration_and_dags.md` specs.

In that model:

- The external orchestrator owns **DAGs and triggers** per market/phase.
- Individual DAG tasks call small Python entrypoints that:
  - Mark runs `DATA_READY` when ingestion DAGs succeed.
  - Call `advance_run` or phase-specific helpers.
- The `engine_runs` table remains the **single source of truth** for run
  state and timing.

Examples of DAG tasks:

- `us_eq_engines_T` DAG task that, after ingestion/features DAGs succeed,
  triggers `ensure_run` + `DATA_READY` for `US` and date `T`.
- Follow-up task that runs one or more `advance_run` steps (or just lets the
  periodic "engine daemon" handle it).

In this stage, the existing CLIs continue to serve as useful manual tools,
and the daemon (Section 2) can either be retired or kept as a backstop.

## 4. Checklist before live trading

Before enabling live trading, revisit this document and confirm:

- [ ] You have a clear, tested process for marking runs `DATA_READY`.
- [ ] A heartbeat (timer or daemon) reliably advances `engine_runs` to
      `COMPLETED` on schedule for each region.
- [ ] Monitoring is in place for:
  - Stuck runs (phase not updating for too long).
  - Excessive failures in any phase.
- [ ] If a DAG orchestrator is introduced, it calls only small wrappers that
      in turn call the state-machine helpers (no hidden business logic).

The initial implementation should focus on the **short-term model**; medium
and long-term stages can be phased in incrementally without changing the
core state machine or engine code.
