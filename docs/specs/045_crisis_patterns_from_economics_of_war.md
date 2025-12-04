# 045 – Crisis Patterns and Elite Extraction Signals (Economics of War Integration)

## 1. Purpose

This spec distills the user’s "Economics of War" research corpus into **quantifiable patterns, indicators, and scenario templates** that Prometheus v2 can use.

Goals:
- Translate historical crisis/heist narratives into **features, thresholds, and scenarios**.
- Integrate these into Regime, Stability & Soft-Target, Fragility Alpha, Universe, Portfolio & Risk, Synthetic Scenarios, and Meta-Orchestrator.
- Ensure Prometheus explicitly models **man-made extraction patterns**, not just "random" market crashes.

This is not a trading playbook; it is a **pattern library and risk-awareness layer**.

---

## 2. Source Material

Primary inputs (paths on local system):

- `RESEARCH/file_dump/crash_indicators_complete_reference.md`
- `RESEARCH/file_dump/first_domino_collapse_patterns.md`
- `RESEARCH/file_dump/elite_exit_indicators_2025.md`
- `RESEARCH/file_dump/BAILOUT_RECIPIENTS_COMPLETE_ANALYSIS.md`
- `RESEARCH/file_dump/bank_consolidation_crisis_pattern.md`
- `RESEARCH/file_dump/bank_consolidation_detailed_financials.md`
- `RESEARCH/file_dump/bubble_profit_strategy.md`
- `RESEARCH/file_dump/COMPLETE_CASH_FLOW_ANALYSIS_FED_LTRO.md`
- `RESEARCH/file_dump/BANKING_HEIST_TIMELINE_2000-2025.md`
- `RESEARCH/file_dump/complete_crisis_extraction_timeline_1913_2025.md`
- `RESEARCH/file_dump/COMPREHENSIVE_INSTITUTIONAL_CRISIS_POSITIONING_MERGED.md`

Case-study narratives:
- `MAIN_BOOK/Part_6_resource-wars-1980-2010/Chapter_29_thailand-beta-test-1997/020-narrative.md`
- `Chapter_30_south-korea-chaebols-1997-1998/020-narrative.md`
- `Chapter_31_indonesia-suharto-1997-1998/020-narrative.md`
- `Chapter_32_russia-oligarch-heist-1998/020-narrative.md`
- `Chapter_33_argentina-middle-class-2001/020-narrative.md`

This document references them conceptually; the raw files remain the detailed ground truth.

---

## 3. Pattern Taxonomy (Narrative Level)

At a high level, the research describes a recurring **extraction machine**:

1. **Bubble creation via cheap credit**
   - External banks/central banks push credit (often in foreign currency), especially to periphery countries/sectors.
2. **Elite positioning / early exit**
   - Insiders, major institutions, and elite investors quietly derisk or go net short.
3. **Trigger & liquidity withdrawal**
   - Rates raised / credit lines not rolled / targeted currency or sector attacked.
4. **Crash & crisis headlines**
   - Currency collapse, bank runs, asset price collapses.
5. **IMF/central bank "rescue" with harsh conditions**
   - High rates, austerity, forced liberalization, privatizations.
6. **Consolidation & asset strip**
   - Large foreign (or domestic-elite) institutions buy banks, real assets, strategic companies at 80–95% discounts.
7. **Bailouts & carry trades**
   - Major banks use cheap public funding (TARP, Fed swap lines, ECB LTRO) for profits and acquisitions, not for lending.
8. **System emerges larger and more concentrated**
   - Fewer, bigger banks; more centralization; higher systemic leverage.

Prometheus will **not** attempt to assign moral labels, but it will treat these patterns as:
- **Distinct regimes** (Regime Engine),
- **Sources of instability/fragility** (Stability, Fragility Alpha),
- **Scenario templates** (Synthetic Scenario Engine),
- **Meta-risk contexts** (Meta-Orchestrator, Portfolio & Risk).

---

## 4. Indicator Library (Quantitative Hooks)

This section enumerates key indicators from the research and maps them to Prometheus features.

### 4.1 Systemic leverage & debt

From `crash_indicators_complete_reference` and `complete_crisis_extraction_timeline_1913_2025`:

- **Derivatives-to-GDP ratio**
  - Historical: 2008 ≈ 10:1; current ~25:1.
  - Use as a **slow-moving systemic risk scalar** in Regime & Stability engines.
  - Implementation: external macro data feed; stored in `macro_time_series` as `derivatives_notional_to_global_gdp`.

- **Debt-to-GDP levels and slope**
  - Crashes historically precede at 200–280%; current ≈ 350%.
  - Feature: `global_debt_to_gdp` (level) and `d/dt debt_to_gdp` (trend).
  - Engines: Regime (macro stress), Portfolio & Risk (global leverage cap hints), Synthetic Scenarios (baseline leverage).

### 4.2 Credit flow & commercial real estate / "first domino" metrics

From `crash_indicators_complete_reference` and `first_domino_collapse_patterns`:

**Tier 1 – Credit Flow Indicators** (mostly US, but generalizable):
- C&I loan growth (YoY)
- Bank credit growth (YoY)
- Senior Loan Officer Opinion Survey (net tightening %)
- Commercial paper spreads vs T-bills
- SOFR spread vs Fed Funds

Use these as:
- `CreditStressVector` inputs to Regime and Stability.
- Early-warning features for Fragility Alpha **at system level**.

**Tier 2 – Commercial Real Estate (first domino)**:
- CMBS delinquency rates (overall and by sector: office, retail, lodging, multifamily).
- Office and mall vacancy rates (national + key cities).
- CMBX.6 BBB and similar indices.
- CRE loan maturity walls per year (2025–2027 etc.).

Use as:
- Features in **Stability & Soft-Target Engine (110)** for real estate, banks, REITs.
- Drivers of **soft-target classification** for:
  - Regional/small banks with high CRE exposure.
  - Highly levered REITs and property developers.
- Scenario drivers in Synthetic Scenario Engine (e.g. "CRE collapse" scenarios).

**First-domino cascades** (from `first_domino_collapse_patterns`):
- Sector order: **CRE → subprime/high-risk lending → shadow banking → regional banks → major banks.**
- Country order: **peripheral/weak** (new PIIGS, France/Austria, etc.) → **core** (Germany, US).

Use as:
- Templates for **Regime labels** (e.g. `CRE_CRACKING`, `REGIONAL_BANK_STRESS`, `CORE_SOVEREIGN_STRESS`).
- **Causal sequencing** inside Synthetic Scenario Engine (scenario timelines).
- Features for **Fragility Alpha** when assessing entities in those sectors/countries.

### 4.3 Elite positioning & exit indicators

From `elite_exit_indicators_2025`, `crash_indicators_complete_reference`, `COMPREHENSIVE_INSTITUTIONAL_CRISIS_POSITIONING_MERGED`:

Key indicators:
- Insider buy/sell ratios (sector-specific, especially financials).
- Insider sell velocity vs historical averages.
- Form 144 clustering (advance intent to sell).
- 13F-based institutional positioning/hedging:
  - Massive SPY/QQQ/XLF puts (Citadel, Elliott, etc.).
  - Net reduction in risk assets despite headline long positions.
- Buffett/Berkshire cash position and net stock sales streak.
- Private equity / RE funds **suspending redemptions or gating liquidity**.

In Prometheus:

- Define an **Elite Exit Score** per region/sector:
  - Inputs: normalized insider selling, institutional put/call positioning, PE redemption behavior, cash build-ups of known "smart money".
  - Stored in `macro_time_series` / `factors_daily` as `elite_exit_score_{region}`.
- Engines using this:
  - **Regime Engine**: mark phases like `ELITE_EXIT_ACCELERATING` (12–18 months pre-crisis window).
  - **Stability & Soft-Target**: treat high Elite Exit Score as an amplifying factor for fragility.
  - **Fragility Alpha**: add a penalty to long exposure in entities/sectors where elite exit is concentrated, and consider short/hedge ideas.
  - **Meta-Orchestrator**: monitor whether our configs are long where elites are clearly exiting.

### 4.4 Market stress & credit spreads

From `crash_indicators_complete_reference`:

- VIX, SKEW, sector-specific put/call ratios (e.g. financials), HY and IG credit spreads, margin debt.

These are standard quant features; here they are **tiered** with explicit thresholds that can be encoded as:
- Discrete buckets (`NORMAL`, `WARNING`, `DANGER`, `CRISIS`) per indicator.
- Combined into a **MarketStressIndex** and **CreditStressIndex**.

Use in:
- Regime Engine (state classification).
- Portfolio & Risk Engine (dynamic leverage caps, risk aversion).
- Synthetic Scenarios (stress starting points and calibration of tail moves).

### 4.5 Bailout & consolidation pattern metrics

From `BAILOUT_RECIPIENTS_COMPLETE_ANALYSIS`, `bank_consolidation_crisis_pattern`, `bank_consolidation_detailed_financials`, `COMPLETE_CASH_FLOW_ANALYSIS_FED_LTRO`, `BANKING_HEIST_TIMELINE_2000-2025`:

Key structural observations:
- Bailout facilities (TARP, Fed emergency, ECB LTRO, swap lines) are **massive and opaque**, and:
  - Directed primarily to a few large institutions.
  - Often used for bonuses, acquisitions, carry trades, and liquidity hoarding—not for real-economy lending.
- Each crisis leads to:
  - **Consolidation** (large banks acquiring failed competitors at huge discounts).
  - **Negative goodwill gains** on acquirers’ balance sheets.
  - Socialization of losses, privatization of gains.

Quantifiable hooks:
- `bailout_intensity_index_{region}`:
  - Size of facilities relative to GDP or bank assets.
  - Concentration of support among top-N banks.
- `consolidation_ratio_{banking_system}`:
  - Share of assets held by top-3 or top-5 banks before vs after crisis.
- Event flags for **emergency weekend deals** (UBS-CS, JPM–First Republic etc.).

Use in:
- **Regime Engine**: special `BAILOUT_REGIME` tags.
- **Stability & Soft-Target**: 
  - Recognize that small/regional banks become soft targets; large acquirers benefit from crisis.
- **Fragility Alpha**:
  - Identify likely winners (acquirers with state backing) vs losers (to-be-sacrificed entities).
- **Meta-Orchestrator**:
  - Evaluate whether our configs implicitly bet on being on the wrong side of consolidation.

---

## 5. Scenario Templates from Historical Crises

Based on the country chapters and timelines, define **named scenario templates** for the Synthetic Scenario Engine (170). Each scenario is a **macro-structured pattern**, not just a one-day shock.

### 5.1 Template structure

For each scenario family, we define:
- **Name** (e.g. `THAILAND_1997_STYLE`, `KOREA_CHAEBOL_DISSOLUTION_1997_98`, `INDONESIA_SUHARTO_1997_98`, `RUSSIA_OLIGARCH_PRIVATIZATION_1998`, `ARGENTINA_MIDDLE_CLASS_ANNIHILATION_2001`, `US_SUBPRIME_2008`, `EURO_LTRO_2011_12`, `UBS_CS_CONSOLIDATION_2023`).
- **Preconditions**:
  - Credit growth profiles, external debt structure, FX regime, sectoral bubble structure, political setup.
- **Shock sequence**:
  - Stage 1: Currency or sector attack.
  - Stage 2: Policy response (rate hikes, capital controls removal, austerity).
  - Stage 3: Wave of defaults and bankruptcies.
  - Stage 4: Bailouts & forced consolidations.
  - Stage 5: Asset sales and foreign takeovers.
- **Affected entities**:
  - Local banks (esp. regional), state-owned enterprises, key sectors (CRE, autos, telcos, utilities, commodities).
- **Outcome metrics**:
  - Typical drawdowns by asset type, FX moves, sovereign yields, bank equity crashes.

These templates become:
- Parameterized inputs to ScenarioSet definitions in 170.
- Reference labels stored alongside ScenarioSets so engines know which historical script a synthetic scenario is emulating.

### 5.2 Example mappings

- **Thailand 1997 – Beta Test**
  - Preconditions: large foreign currency corporate debt, fixed/managed FX, rapid credit inflows, real estate boom.
  - Shocks: FX devaluation, rate hikes, bank failures, IMF conditionality → forced asset sales.
  - Use for: Emerging market FX/debt stress testing; fragility of corporates with FX mismatch.

- **Korea 1997–98 – Chaebol dismantling**
  - Preconditions: highly successful national conglomerates with some external debt.
  - Shocks: won devaluation, credit cutoff, IMF structural adjustment demanding foreign bank entry and chaebol breakup.
  - Use for: Testing corporates/sovereigns following a Korea-like dev model; stability of concentrated industrial champions.

- **Indonesia 1997–98 – Regime change via crisis**
  - Preconditions: resource-rich economy, family-controlled conglomerates, limited foreign penetration.
  - Shocks: massive FX collapse, IMF conditions, engineered social unrest, regime change, subsequent asset liquidation.
  - Use for: Tail-risk scenarios where financial + political crises interact.

- **Russia 1998 – Oligarch privatization & bond crisis**
  - Preconditions: large state asset base, IMF "shock therapy", GKO bond ponzi schemes.
  - Shocks: bond default, ruble collapse, banking crisis, privatization at giveaway prices.
  - Use for: Stress tests on sovereigns with large commodity bases and fragile fiscal structures.

- **Argentina 2001 – Middle class annihilation**
  - Preconditions: currency peg, external debt build-up, privatizations, import flood, weakened industry.
  - Shocks: peg break, default, bank freezes, deep devaluation, prolonged depression.
  - Use for: Scenarios targeting domestic middle-class economies with pegs and IMF programs.

- **US 2008 & Euro LTRO 2011–12 – Modern Western heists**
  - Preconditions: high derivatives & debt-to-GDP, housing/CRE bubbles, structured credit.
  - Shocks: asset price collapse, emergency lending, regulatory theater, bank consolidation.
  - Use for: Current developed-market fragility stress (US/EU banking & sovereigns).

---

## 6. Engine Integration Map

### 6.0 Sovereign reaction & contagion patterns (for Stability/Soft-Target)

Across Thailand, Korea, Indonesia, Russia, Argentina, Euro crisis, and modern banking episodes, the research highlights **how sovereign and policy reactions shape contagion**:
- FX regime choices (peg vs float) and policy responses (rate hikes, capital controls, bank closures, IMF programs).
- Sequencing of bailouts, restructurings, and privatizations.
- Differential impacts on:
  - local vs foreign banks,
  - domestic middle classes vs external creditors,
  - neighboring sovereigns and currencies.

Prometheus should not assume these narratives are ground truth, but use them as **labels for backtesting**:
- Mark historical windows where specific sovereign reaction patterns occurred.
- During research/backtests, learn empirically how those reactions affected:
  - issuer-level losses and defaults,
  - bank failures and consolidations,
  - regional contagion.

The Stability & Soft-Target Engine (110) then uses this as a training set to build contagion-aware components, rather than embedding the narratives as fixed rules.

### 6.1 Regime Engine (100)

### 6.1 Regime Engine (100)

Add regime concepts:
- `EXTRACTION_SETUP`: credit expansion + external-debt-heavy bubbles + rising Elite Exit Score, but before visible stress.
- `EXTRACTION_TRIGGERED`: early dominoes falling (CRE/first-periphery sectors or countries), credit tightening.
- `EXTRACTION_CONSOLIDATION`: bailouts & forced M&A phase, markets rally for acquirers while broad economy suffers.

Inputs from this spec:
- Elite Exit Score.
- Credit Flow & CRE stress tiers.
- Bailout Intensity Index and Consolidation Ratios.
- Scenario template tags for recent history.

### 6.2 Stability & Soft-Target Engine (110)

Incorporate:
- **Systemic features**:
  - CreditStressVector, MarketStressIndex, EliteExitScore.
- **Entity-level soft-target tags**, e.g.:
  - Regional banks with high CRE exposure, high funding fragility.
  - Sovereigns matching "periphery" patterns (high debt, external dependency, political instability).
  - Sectors historically used as first dominoes (CRE, small banks, high-yield lending, shadow banking).

These become components of `StabilityVector` and `SoftTargetClass` for entities and sectors.

### 6.3 Fragility Alpha (135)

Use patterns to:
- Define **fragility archetypes**:
  - "Extraction Target Bank": regional bank with CRE, funding mismatch, in a country showing Elite Exit + early domino features.
  - "Privatization Target SOE": state-owned or quasi-national champion in a country under IMF/EU-like programs.
  - "Middle-Class Annihilation Candidate": economies with currency boards, heavy external debt, and structural deindustrialization tendencies.
- Make these archetypes generate:
  - Short/hedge **ideas and scenarios** (instruments on vulnerable entities).
  - Not just positions but **warnings**: where NOT to be structurally long.

### 6.4 Universe & Portfolio & Risk (140/150)

Universe Engine:
- Integrate soft-target & extraction archetypes into filters:
  - Bias against including entities that historically get sacrificed in heists for long-only strategies.
  - For long/short strategies, treat these as **short-only candidates** with strict risk caps.

Portfolio & Risk Engine:
- Use scenario templates and indicators to:
  - Dynamically reduce leverage when in `EXTRACTION_TRIGGERED` regimes.
  - Impose enhanced constraints on exposures to:
    - Regional banks, CRE-heavy structures.
    - Periphery sovereigns in the firing line.
    - State assets in IMF/EU programs.

### 6.5 Synthetic Scenario Engine (170)

- Codify scenarios from §5 as:
  - **Named ScenarioSets** with documented historical mapping and parameter ranges.
  - Part of the **standard scenario battery** used in 180 for gating configs.

- Add **extraction-specific scenario families**:
  - CRE crisis + regional bank cascade.
  - Sovereign debt restructuring with IMF conditionality.
  - Currency peg breaks + bank freezes + forced privatizations.

### 6.6 Meta-Orchestrator (160)

- Track whether our configs:
  - Systematically **lose** during extraction-pattern scenarios (bad).
  - Or only **profit** by being structurally long the same institutions orchestrating the heist (ethical judgment left to user, but at least visible).

- Use Elite Exit Score and institutional positioning info to:
  - Flag configs that ignore clear smart-money hedging and exit patterns.
  - Provide Kronos Chat explanations grounded in these patterns (e.g. "Your current bank-heavy strategy rhymes with pre-2008 regionals pattern").

---

## 7. Epistemic & Validation Principles

- The "Economics of War" materials are treated as a **source of hypotheses and labels**, not as ground truth rules.
- All indicators and features derived from them must:
  - be grounded in external, auditable data sources (macro, credit, market, filings, etc.),
  - be evaluated via backtests across multiple crises, regions, and out-of-sample periods,
  - be easily ablated so their incremental value can be measured.
- No engine should contain hard-coded logic of the form "because pattern X appeared in the book, always do Y"; instead:
  - the crisis patterns inform **which scenarios to test**,
  - **which features to try**, and
  - **which entities to examine**, with Kronos and the testing framework deciding whether those ideas earn their way into production.

---

## 8. Implementation Notes

- Many indicators require **external macro/market data feeds**:
  - Fed/ECB data, CMBS/CRE indices, insider trading feeds, 13F scraping.
  - These should be specified in `040_data_sources_and_ingestion.md` and mapped to concrete tables in `020_data_model.md`.

- Indicators should be surfaced as **normalized, versioned features**:
  - E.g. `elite_exit_score_us_eq`, `cre_stress_index_us_eq`, `periphery_sov_stress_score_eu`.

- Scenario templates should be integrated as:
  - `ScenarioSets` with `category = "HISTORICAL_TEMPLATE"` and `generator_spec` referencing this spec.

- Testing & Validation (180):
  - Include **extraction scenarios** and **first-domino patterns** in the standard scenario battery.
  - Use Negative Config Suite to ensure no config is accidentally judged "good" if it only wins by walking blind into obvious heist setups without proper risk awareness.

This spec is the bridge between the "Economics of War" qualitative research and Prometheus’ quantitative engines, ensuring that the system actively learns from and tests against the documented history of man-made crises and extraction schemes.