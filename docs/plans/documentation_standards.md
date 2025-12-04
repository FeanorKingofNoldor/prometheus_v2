# Documentation Standards & Enforcement – Plan

## 1. Goals

- Every part of the system is understandable from code + markdown docs alone.
- Public APIs are self-documenting via consistent docstrings.
- Documentation quality is enforced automatically (linting), not just by convention.

---

## 2. Levels of Documentation

### 2.1 Module-Level Docstrings

- Every Python module must start with a docstring that:
  - Describes the module’s purpose (2–4 sentences).
  - Mentions external systems it touches (DB, network, broker, etc.).
  - States key invariants (e.g., "All operations are idempotent by date" or "No network access; pure computation.").

### 2.2 Public API Docstrings

- All public functions and classes (especially those exposed in `api.py` modules) use **Google-style** docstrings.
- Required sections:
  - One-line summary.
  - `Args:` list with types and meanings.
  - `Returns:` description (or `None`).
  - `Raises:` for expected exceptions.
  - Any side effects (DB writes, external calls) and important assumptions.

Example:

```python
def run_daily_ingestion(run_date: date) -> None:
    """Ingest and validate all daily data for a given date.

    Args:
        run_date: Trading date for which to fetch and load data.

    Raises:
        IngestionError: If any required feed fails validation. No partial
            updates to main tables are committed for this date.
    """
```

### 2.3 Subsystem Markdown Docs

- Each major subsystem (data_ingestion, profiles, macro, universe, backtesting, assessment, risk, execution, black_swan, meta, monitoring, config_mgmt) has a markdown doc in the new repo under `docs/`:
  - `docs/data_ingestion.md`
  - `docs/profiles.md`
  - `docs/macro_regime.md`
  - `docs/universe.md`
  - `docs/backtesting.md`
  - `docs/assessment.md`
  - `docs/risk.md`
  - `docs/execution.md`
  - `docs/black_swan.md`
  - `docs/meta_orchestrator.md`
  - `docs/monitoring.md`
  - `docs/config_mgmt.md`
- Each doc contains:
  - Purpose and scope.
  - High-level architecture and main modules.
  - Key API functions and example usage.
  - Brief description of important algorithms/assumptions.

### 2.4 Algorithms / Scientific Notes

- For algorithm-heavy components (e.g. macro regime models, factor scoring, sizing, black swan detection), include a short "Math & Assumptions" section in the relevant `docs/*.md`:
  - What models are used (e.g. threshold rules, Markov switching, factor models).
  - Key formulas or references.
  - Any approximations or simplifications.

---

## 3. Enforcement

### 3.1 Linting

- Use `ruff` (or similar) with docstring rules enabled (pydocstyle-like):
  - Require module docstrings.
  - Require docstrings on public functions and classes.
  - Enforce basic style (summary line, blank line before sections).
- CI / pre-commit equivalent (when set up):
  - Fails if required docstrings are missing or malformed.

### 3.2 Tests (Optional but Recommended)

- Add a simple test that:
  - Walks selected API modules (e.g. `*/api.py`).
  - Asserts that all exported functions/classes have non-empty docstrings.

### 3.3 Process

- No new public API should be merged without docstrings.
- When significant behavior changes, associated docs in `docs/*.md` must be updated as part of the same change.

---

## 4. Relationship to Plan Files

- The `new_project_plan/*.md` files are the **design-time plans**.
- The `docs/*.md` files in the new repo are the **runtime documentation** for developers and the Meta Orchestrator.
- Docstrings link implementation back to both by:
  - Referencing concepts defined in plan docs (e.g. "DecisionContext", "black_swan_state").

This document is the reference for how we document everything as we build Prometheus from the ground up.