# Prometheus v2 Documentation

This directory contains all documentation for the Prometheus v2 trading system.

## Directory Structure

```
docs/
├── README.md                    # This file - documentation index
├── architecture/                # System architecture and design
│   ├── plantuml/               # PlantUML diagrams and generated SVGs
│   ├── generated/              # Auto-generated architecture docs
│   └── *.md                    # Architecture documentation
├── specs/                       # Technical specifications (numbered)
│   ├── 0xx_*.md                # Foundation specs (data, orchestration, execution)
│   ├── 1xx_*.md                # Engine specs (regime, stability, assessment, etc.)
│   └── 2xx_*.md                # Infrastructure specs (monitoring, testing, security)
├── plans/                       # Implementation and project plans
│   └── *_plan.md               # Service-specific implementation plans
├── workflows/                   # Developer workflows and procedures
│   ├── dev_workflows_README.md # Workflows overview
│   ├── dev_workflows_joint_*.md    # Joint embedding space workflows
│   ├── dev_workflows_numeric_*.md  # Numeric embedding workflows
│   ├── dev_workflows_text_*.md     # Text embedding workflows
│   └── dev_workflows_*.md          # Other operational workflows
├── guides/                      # Implementation guides and patterns
│   ├── backtesting_and_books_pipeline.md
│   ├── encoders_joint_use_cases_plan.md
│   ├── external_platform_patterns.md
│   └── pattern_discovery_principles.md
├── joint_spaces/                # Joint embedding space documentation
│   └── [space_name]/           # Each joint space has its own directory with README
└── ui/                          # UI documentation and mockups
    ├── PLAN_prometheus_c2_ui.md
    ├── C2_UI_PROGRESS.md
    └── ui_c2_mock/             # UI mockup files
```

## Quick Navigation

### Getting Started
- **System Overview**: [architecture/00_overview.md](architecture/00_overview.md)
- **Master Architecture**: [architecture/99_master_architecture.md](architecture/99_master_architecture.md)
- **Workflow Overview**: [workflows/dev_workflows_README.md](workflows/dev_workflows_README.md)

### Core Specifications
1. **Foundations** (000-020): Repository setup, data model, calendars, orchestration
2. **Embeddings & Data** (030-045): Encoders, profiles, data sources, crisis patterns
3. **Engines** (100-170): Regime, stability, assessment, universe, portfolio, orchestrator, scenarios
4. **Infrastructure** (180-210): Testing, migration, monitoring, security

### Key Documentation

#### Architecture
- [Complete System Components](architecture/00_overview.md)
- [Engine Architecture](architecture/20_engines.md)
- [Database Schema](architecture/30_database_schema.md)

#### Specifications (Ordered)
- [000 - Repo Audit and Reuse](specs/000_repo_audit_and_reuse.md)
- [010 - Foundations](specs/010_foundations.md)
- [012 - Calendars and Scheduling](specs/012_calendars_and_scheduling.md)
- [013 - Orchestration and DAGs](specs/013_orchestration_and_dags.md)
- [015 - Execution and Backtesting](specs/015_execution_and_backtesting.md)
- [020 - Data Model](specs/020_data_model.md)
- [030 - Encoders and Embeddings](specs/030_encoders_and_embeddings.md)
- [035 - Profiles](specs/035_profiles.md)
- [040 - Data Sources and Ingestion](specs/040_data_sources_and_ingestion.md)
- [040 - Latent State Message Passing](specs/040_latent_state_message_passing_plan.md)
- [041 - Latent State Spaces and Math](specs/041_latent_state_spaces_and_math.md)
- [042 - EODHD Data Catalog](specs/042_eodhd_data_catalog.md)
- [045 - Crisis Patterns from Economics of War](specs/045_crisis_patterns_from_economics_of_war.md)
- [100 - Regime Engine](specs/100_regime_engine.md)
- [110 - Stability/Soft-Target Engine](specs/110_stability_softtarget_engine.md)
- [130 - Assessment Engine](specs/130_assessment_engine.md)
- [135 - Fragility Alpha](specs/135_fragility_alpha.md)
- [140 - Universe Engine](specs/140_universe_engine.md)
- [150 - Portfolio and Risk Engine](specs/150_portfolio_and_risk_engine.md)
- [160 - Meta Orchestrator](specs/160_meta_orchestrator.md)
- [170 - Synthetic Scenarios](specs/170_synthetic_scenarios.md)
- [180 - Testing and Validation](specs/180_testing_and_validation.md)
- [190 - Migration Plan](specs/190_migration_plan.md)
- [200 - Monitoring and UI](specs/200_monitoring_and_ui.md)
- [200 - Threat Model (Defensive)](specs/200_threat_model_defensive.md)
- [210 - Threat Model (Offensive)](specs/210_threat_model_offensive_perspectives.md)

#### Implementation Plans
See [plans/](plans/) directory for detailed implementation plans for each service:
- Assessment Engine
- Backtesting Engine
- Black Swan/Emergency Engine
- Data Ingestion
- Execution Service
- Joint Embedding Spaces
- Macro/Regime Service
- Meta Orchestrator
- Profile Service
- Risk Management
- Universe Selection

#### Developer Workflows
See [workflows/dev_workflows_README.md](workflows/dev_workflows_README.md) for:
- Joint embedding space workflows
- Numeric embedding workflows
- Text embedding workflows
- Engine orchestration workflows
- Execution and backtesting workflows
- Full day core pipeline

#### Guides
- [Backtesting and Books Pipeline](guides/backtesting_and_books_pipeline.md)
- [Encoders Joint Use Cases](guides/encoders_joint_use_cases_plan.md)
- [External Platform Patterns](guides/external_platform_patterns.md)
- [Pattern Discovery Principles](guides/pattern_discovery_principles.md)

#### Joint Embedding Spaces
Each joint space combines multiple embedding types for specific use cases:
- Assessment joint space (profile + regime + stability/fragility + text)
- Episode joint space (regime + text)
- Meta configuration joint space (config + environment + outcome)
- Portfolio joint space (portfolio embeddings)
- Profile joint space (profile + text + regime)
- Regime joint spaces (regime + text variations)
- Stability joint space (stability + scenario + profile)

See [joint_spaces/](joint_spaces/) for detailed documentation on each space.

#### UI Documentation
- [C2 UI Plan](ui/PLAN_prometheus_c2_ui.md)
- [C2 UI Progress](ui/C2_UI_PROGRESS.md)
- [UI Mockups](ui/ui_c2_mock/)

## Documentation Conventions

### Spec Numbering
Specifications use a numbered prefix system:
- **000-020**: Foundation and core infrastructure
- **030-099**: Data, embeddings, and inputs
- **100-179**: Engine implementations
- **180-299**: Testing, deployment, monitoring, security

### File Naming
- Specs: `NNN_description.md` (numbered)
- Plans: `*_plan.md` or `*_PLAN.md`
- Workflows: `dev_workflows_*.md`
- Architecture: Descriptive names with numbering for ordering

### Cross-References
When referencing other documents:
- Use relative paths from the docs/ directory
- Link to specific sections when applicable
- Keep links updated when moving files

## Maintenance

### Adding New Documentation
1. **Specs**: Add to `specs/` with appropriate number prefix
2. **Plans**: Add to `plans/` with `*_plan.md` naming
3. **Workflows**: Add to `workflows/` with `dev_workflows_*` prefix
4. **Architecture**: Add to `architecture/` with diagrams to `plantuml/`
5. Update this README with links to new documentation

### Updating Architecture Diagrams
1. Edit `.puml` files in `architecture/plantuml/`
2. Regenerate SVGs (automated or manual)
3. Update generated docs in `architecture/generated/`

### Joint Space Documentation
When adding new joint embedding spaces:
1. Create directory in `joint_spaces/[space_name]/`
2. Add README.md explaining purpose and components
3. Add corresponding workflow in `workflows/`
4. Update this README

## Contributing
When contributing documentation:
- Follow existing naming conventions
- Update this README when adding new sections
- Keep specs and plans in sync with implementation
- Use PlantUML for architecture diagrams
- Write clear, concise documentation
- Include examples where helpful
