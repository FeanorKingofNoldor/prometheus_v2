# Configuration & Strategy Management – Detailed Plan

## 1. Purpose & Scope

Centralize all configurable aspects of the system: strategies, risk parameters, universe rules, prompt templates, LLM models, and other tunable parameters. Provide versioning and controlled updates.


## 2. High-Level Architecture

Modules under `config_mgmt/`:

- `models/` – config data models.
- `storage/` – read/write config tables.
- `api/` – accessors for other subsystems to load configs.
- `versioning/` – manage config versions and change history.


## 3. Data Contracts

### 3.1 Config Tables (Conceptual)

- `strategy_configs`
  - `strategy_id` (PK)
  - `name`, `description`
  - `parameters_json` (filters, scoring weights, etc.)
  - `version_id`

- `risk_configs`
  - `risk_config_id` (PK)
  - `scope` (GLOBAL, STRATEGY, ACCOUNT)
  - `scope_id` (e.g. strategy_id)
  - `parameters_json` (position caps, exposure limits, drawdown rules)
  - `version_id`

- `universe_rules`
  - `rule_id` (PK)
  - `strategy_id`
  - `regime_id` (or ALL)
  - `rules_json` (filters, sector caps, etc.)
  - `version_id`

- `prompt_templates`
  - `prompt_template_id` (PK)
  - `component` (PROFILE_BUILDER, ASSESSMENT_ENGINE, META_ORCHESTRATOR, BLACK_SWAN)
  - `template_text`
  - `variables_json` (allowed placeholders)
  - `model_name`
  - `version_id`

- `llm_config`
  - `llm_config_id` (PK)
  - `model_name`
  - `parameters_json` (temperature, max_tokens, etc.)

- `config_change_log`
  - `change_id` (PK)
  - `timestamp`
  - `user` or `process`
  - `target_table`
  - `target_id`
  - `old_version_id`, `new_version_id`
  - `change_summary`


## 4. Interactions with Other Players

- All subsystems (Profile, Macro Regime, Universe, Assessment, Risk, Black Swan, Meta Orchestrator) read their configs with explicit version IDs.
- Meta Orchestrator writes proposals targeting these config tables; human/auto processes apply changes, updating versions and logging changes.


## 5. Access Pattern

- At startup or at defined checkpoints, each subsystem loads its configs via `config_mgmt.api`.
- Each decision/trade/analysis record logs the relevant `version_id`s.


## 6. Safeguards

- No direct ad-hoc edits to config tables; all changes go through controlled APIs and are logged.
- Ability to roll back to previous versions if a change is harmful.
