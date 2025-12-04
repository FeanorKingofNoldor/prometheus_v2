# Developer Workflows

This directory contains operational workflows and procedures for developing and running Prometheus v2 components.

## Overview
The `dev_workflows_README.md` file provides a comprehensive overview of all workflows.

## Workflow Categories

### Joint Embedding Space Workflows
Workflows for combined embedding spaces that integrate multiple encoder types:
- `dev_workflows_joint_assessment_context.md` - Assessment context (profile + regime + stability/fragility + text)
- `dev_workflows_joint_episodes.md` - Episode tracking (regime + text)
- `dev_workflows_joint_meta_config_env.md` - Meta configuration (config + env + outcome)
- `dev_workflows_joint_portfolios.md` - Portfolio workflows
- `dev_workflows_joint_profiles.md` - Profile workflows (profile + text + regime)
- `dev_workflows_joint_regime_context.md` - Regime context (regime + text)
- `dev_workflows_joint_regime_macro_context.md` - Macro regime context (regime + macro text)
- `dev_workflows_joint_stab_fragility.md` - Stability/fragility workflows (stability + scenario + profile)

### Numeric Embedding Workflows
Workflows for numeric encoders:
- `dev_workflows_numeric_embeddings.md` - General numeric embeddings
- `dev_workflows_numeric_portfolio_embeddings.md` - Portfolio-specific numeric embeddings
- `dev_workflows_numeric_profile_embeddings.md` - Profile-specific numeric embeddings
- `dev_workflows_numeric_scenario_embeddings.md` - Scenario numeric embeddings
- `dev_workflows_numeric_stab_embeddings.md` - Stability numeric embeddings

### Text Embedding Workflows
Workflows for text encoders:
- `dev_workflows_text_embeddings.md` - General text embeddings
- `dev_workflows_text_macro_embeddings.md` - Macro-focused text embeddings
- `dev_workflows_text_profile_embeddings.md` - Profile text embeddings

### Engine & System Workflows
Core operational workflows:
- `dev_workflows_regime_numeric.md` - Regime numeric processing
- `dev_workflows_regime_prototypes.md` - Regime prototype generation
- `dev_workflows_engine_runs_orchestration.md` - Engine orchestration
- `dev_workflows_portfolio_stab_scenarios.md` - Portfolio stability scenarios
- `dev_workflows_execution_bridge.md` - Execution bridge workflows
- `dev_workflows_backtest_and_risk.md` - Backtesting and risk workflows
- `dev_workflows_full_day_core_pipeline.md` - Complete daily pipeline

## Usage

Each workflow document typically includes:
1. **Purpose**: What the workflow accomplishes
2. **Prerequisites**: Required setup and dependencies
3. **Steps**: Detailed step-by-step procedures
4. **Expected Outputs**: What results to expect
5. **Troubleshooting**: Common issues and solutions
6. **Related Workflows**: Links to related procedures

## Quick Start

For a typical development session:
1. Read `dev_workflows_README.md` for an overview
2. Identify the component you're working on
3. Follow the relevant workflow(s)
4. Check the corresponding spec in `../specs/` for technical details
5. Refer to `../guides/` for implementation patterns

## Contributing

When adding new workflows:
- Use the `dev_workflows_` prefix
- Follow the existing structure and format
- Update `dev_workflows_README.md` with a summary
- Update this README with appropriate categorization
- Link to related specs and guides
