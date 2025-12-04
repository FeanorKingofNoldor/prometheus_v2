# Prometheus v2

Prometheus v2 is a quantitative trading system built from the ground up with a
complete, documented architecture and a strict iterative implementation plan.

This repository currently contains the **architecture and implementation
plans**, plus the **Iteration 1** foundation code as it is developed.

---

## Status

- Architecture: **COMPLETE** (see `ARCHITECTURE_COMPLETE.md` and `docs/`)
- Implementation: **Iteration 1 – Foundation & Database Core (in progress)**

We build in small, validated iterations:

1. Foundation & database core
2. Time/calendar + data access
3. Backtesting infrastructure (TimeMachine)
4. First engine (Regime, simplified)
5. Profiles service (basic)
6. Simple backtesting engine (buy-and-hold)
7. Assessment engine skeleton
8. Universe selection
9. Portfolio construction
10. End-to-end backtest

---

## Development Setup

### 1. Create & Activate Virtualenv

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 3. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your database credentials
```

You will need two PostgreSQL databases:

- `prometheus_historical` – historical market data
- `prometheus_runtime` – runtime state (decisions, portfolios, etc.)

---

## Coding Standards

This project has **strict coding standards**:

- Every file has a **header with metadata**
- Every function has a **Google-style docstring**
- All code is **fully type hinted** (mypy `--strict`)
- Clear **section dividers** and **commenting guidelines**

See:

- `CODING_STANDARDS.md` – full guide
- `CODING_STANDARDS_QUICK_REF.md` – one-page cheat sheet

All new code **must** comply with these.

---

## Testing

Pytest is configured in `pyproject.toml` with `--strict-markers` and
`-m 'not integration'` by default, so **plain `pytest` only runs
unit/fast tests**.

Run unit and other non-integration tests (default fast suite):

```bash
pytest
```

Run only unit tests explicitly:

```bash
pytest tests/unit
```

Run all integration tests (requires PostgreSQL running, `.env`
configured, and Alembic migrations applied for both historical and
runtime DBs):

```bash
pytest -m integration tests/integration
```

Coverage (on the fast/unit suite by default):

```bash
pytest --cov=prometheus --cov-report=html
```

Open `htmlcov/index.html` in a browser to inspect coverage.

---

## Type Checking & Linting

```bash
# Type checking
mypy prometheus/ --strict

# Linting
ruff check prometheus/

# Auto-format (where applicable)
ruff format prometheus/
```

---

## Iterative Implementation

The detailed plan for the current iteration lives in:

- `ITERATION_1_DETAILED.md`

After Iteration 1 completes, subsequent iteration plans will be tracked
similarly under `dev_workflows/`.

---

## Architecture Docs

High-level and detailed architecture documentation lives under `docs/`:

- `docs/specs/` – specification documents (000–210)
- `docs/architecture/` – Mermaid + PlantUML diagrams
- `docs/new_project_plan/` – macro and subsystem plans

See `docs/architecture/README.md` for navigation.

---

## License

TBD.
