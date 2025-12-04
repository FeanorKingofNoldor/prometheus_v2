# 035 – Profile Subsystem Specification

## 1. Purpose

Define the **Profile Service** for issuers (companies, sovereigns, sectors, indices):
- How profile snapshots are defined and stored.
- How structured + textual information is combined into embeddings.
- How downstream engines access profile data.

Profiles capture **slow-moving structural state** (balance sheet, business model, macro vulnerabilities), not high-frequency ticks.

---

## 2. ProfileSnapshot Schema

Profiles are stored in `runtime_db.profiles` as per `020_data_model.md`.

Conceptual Python representation:

```python
from dataclasses import dataclass
from datetime import date
from typing import Dict, Any
import numpy as np

@dataclass
class ProfileSnapshot:
    issuer_id: str
    as_of_date: date
    structured: Dict[str, Any]
    profile_embedding: np.ndarray | None
    risk_flags: Dict[str, float]
```

Where:
- `structured`: normalized, schema-stable representation of fundamentals and qualitative tags.
- `profile_embedding`: vector used by engines (Assessment, Stability & Soft-Target, Universe).
- `risk_flags`: scalar scores (e.g., leverage_score, governance_risk_score) precomputed for convenience.

### 2.1 Structured fields (examples)

For **companies (COMPANY)**:
- Financials:
  - `total_assets`, `total_liabilities`, `equity`.
  - `revenue`, `ebitda`, `net_income`.
  - `operating_cash_flow`, `free_cash_flow`.
- Ratios:
  - `debt_to_ebitda`, `debt_to_equity`, `interest_coverage`.
  - `gross_margin`, `ebit_margin`, `net_margin`.
  - `roe`, `roic`.
- Growth:
  - historical growth rates for revenue, earnings, cashflow.
- Quality & risk:
  - accruals measures, earnings quality, accounting red flags.
  - litigation flags, regulatory investigations (if available).

For **sovereigns (SOVEREIGN)**:
- Public debt metrics:
  - `debt_to_gdp`, `debt_service_to_revenue`.
  - maturity structure summary.
- External accounts:
  - `current_account_to_gdp`, `fx_reserves_to_short_term_debt`.
- Fiscal position:
  - `fiscal_balance_to_gdp`.
- Banking system linkage:
  - `bank_assets_to_gdp`.

For **sectors/indices**:
- Aggregated corporate metrics (e.g. cap-weighted or earnings-weighted averages).

For **FX/currencies**:
- Underlying sovereign macro metrics,
- Relevant external vulnerability indicators.

Structured schema should be defined in a central JSON/YAML and versioned (e.g., `profile_schema_v1`).

---

## 3. Textual Inputs to Profiles

Profiles also consume text-derived information from:
- Filings (`filings` table): selected sections (MD&A, risk factors, etc.).
- Earnings call transcripts (`earnings_calls`).
- Curated news (e.g. major events, downgrades, scandals).

Text processing pipeline:
- Extract relevant text segments.
- Optionally summarize using LLMs (with strict prompts) into:
  - `business_description` summary.
  - `risk_summary`.
  - `recent_events_summary`.
- Embed these summaries with text encoders (see `030_encoders_and_embeddings.md`).

These text embeddings become part of the profile embedding input.

---

## 4. Profile Embedding Model

### 4.1 Goals

- Map `structured` features + text embeddings into a compact vector `profile_embedding(O, t)`.
- Capture medium/long-horizon characteristics relevant to:
  - fragility (for Stability & Soft-Target and Fragility Alpha),
  - expected return and quality (for Assessment),
  - robustness and investability (for Universe selection).

### 4.2 Architecture

- Inputs:
  - Numeric vector from structured fundamentals (scaled/standardized).
  - One or more text embeddings (e.g. concatenated summary embeddings).
- Model:
  - MLP that takes concatenated inputs and outputs a vector in `R^d`.
  - Optionally regularized or trained with contrastive objectives (e.g., good vs bad outcomes).

### 4.3 Training signals

Possible training objectives:
- Self-supervised:
  - Make profile embeddings predictive of future volatility, drawdowns, and returns.
  - Contrast stable vs distressed issuers.
- Supervised:
  - Use known labels (defaults, downgrades, crisis involvement) to separate robust vs fragile profiles.

Training details live in model registry `training_data_spec` and are not hard-coded in this spec.

---

## 5. Profile Service API

Module: `prometheus/profiles/service.py`

```python
from datetime import date
from typing import Optional
import numpy as np

class ProfileService:
    """Builds and serves issuer profile snapshots and embeddings."""

    def get_snapshot(self, issuer_id: str, as_of_date: date) -> ProfileSnapshot:
        """Return the profile snapshot for an issuer at a given date.

        The snapshot is built from stored data in `profiles` if present; otherwise
        it is constructed on the fly from fundamentals and textual sources and 
        optionally persisted.
        """

    def embed_profile(
        self,
        issuer_id: str,
        as_of_date: date,
        model_id: str | None = None,
    ) -> np.ndarray:
        """Return the profile embedding for use by downstream engines.

        Args:
            issuer_id: Issuer ID.
            as_of_date: Date as of which to build/embed the profile.
            model_id: Optional specific embedding model; if None, a default
                configured model is used.
        """
```

### 5.1 Caching & storage

- `get_snapshot` should first check `profiles` table:
  - if snapshot for (`issuer_id`, `as_of_date`) exists, load and return.
  - else, build from fundamentals and text, then persist.

- `embed_profile` should:
  - compute `profile_embedding` if not present,
  - store embedding reference in `profiles.embedding_vector_ref` or separate `profile_embeddings` store.

---

## 6. Risk Flags

Risk flags are scalar scores derived from `structured` and, optionally, text:

Examples for companies:
- `leverage_score` ∈ [0, 1].
- `earnings_quality_score`.
- `governance_risk_score`.

Examples for sovereigns:
- `debt_sustainability_score`.
- `external_vulnerability_score`.

These are used directly by:
- Stability & Soft-Target Engine.
- Fragility Alpha (as part of `WeakProfile(O,t)`).
- Universe selection filters.

Risk flag computation logic should be implemented in `prometheus/profiles/risk_flags.py` and be deterministic given structured inputs.

---

## 7. LLM Integration (Explanatory Only)

LLMs may be used to:
- Summarize filings/calls/news into concise `business_description` and `risk_summary` fields.
- Generate human-readable profile narratives for analysts.

Constraints:
- LLM outputs are **not** the canonical source of truth.
- Structured fields come from data ingestion; numeric flags come from deterministic computations.
- If LLM summaries are used as model inputs, their encoder model `model_id` must be versioned and stable.

---

## 8. Integration with Other Engines

- **Stability & Soft-Target Engine**:
  - Uses structured profile data and risk flags as part of stability/fragility features.
- **Fragility Alpha (Assessment)**:
  - Uses `profile_embedding(O, t)` and risk flags to compute `WeakProfile(O,t)`.
- **Universe Selection**:
  - Uses profiles to impose quality and robustness screens.
- **Meta-Orchestrator**:
  - May analyze profile evolution vs realized performance for meta-learning.

The Profile Subsystem thus provides a consistent, time-indexed structural view of entities that all higher-level engines can rely on.