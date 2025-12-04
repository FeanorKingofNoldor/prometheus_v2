# Implementation Guides

This directory contains implementation guides, patterns, and principles for building Prometheus v2.

## Overview
Guides provide conceptual frameworks, best practices, and cross-cutting concerns that apply across multiple components.

## Available Guides

### Pipeline & Execution
- **`backtesting_and_books_pipeline.md`**  
  Complete guide to the backtesting pipeline and order book management. Covers:
  - Backtesting workflow and data flow
  - Order book structures and updates
  - Position tracking and reconciliation
  - Performance calculation

### Encoders & Embeddings
- **`encoders_joint_use_cases_plan.md`**  
  Joint embedding use cases and patterns. Covers:
  - Joint space design principles
  - Cross-modal embedding strategies
  - Use case examples (regime+text, profile+regime+text, etc.)
  - Integration patterns

### External Integration
- **`external_platform_patterns.md`**  
  Patterns for integrating with external platforms and services. Covers:
  - API integration patterns
  - Data ingestion from external sources
  - Error handling and retries
  - Rate limiting and quotas
  - Authentication and security

### Pattern Discovery
- **`pattern_discovery_principles.md`**  
  Principles and approaches for discovering patterns in market data. Covers:
  - Pattern identification methodologies
  - Statistical significance testing
  - Regime change detection
  - Anomaly detection principles
  - Pattern validation strategies

## Guide vs. Spec vs. Plan

Understanding when to use each type of document:

| Document Type | Purpose | Example |
|--------------|---------|---------|
| **Guide** (this directory) | Cross-cutting concepts, patterns, principles | Pattern discovery principles |
| **Spec** (`../specs/`) | Technical specification of a component | 100_regime_engine.md |
| **Plan** (`../plans/`) | Implementation roadmap for a component | macro_regime_service_plan.md |
| **Workflow** (`../workflows/`) | Step-by-step operational procedures | dev_workflows_regime_numeric.md |

## Usage

### For Developers
1. **Starting a new feature**: Check guides for relevant patterns
2. **Designing integrations**: Refer to external_platform_patterns.md
3. **Working with embeddings**: Review encoders_joint_use_cases_plan.md
4. **Implementing backtesting**: Read backtesting_and_books_pipeline.md

### For Architects
- Guides inform high-level design decisions
- Use patterns from guides in specs and plans
- Reference guides when establishing conventions

### For Operators
- Guides provide context for system behavior
- Help troubleshoot issues by understanding principles
- Inform monitoring and alerting strategies

## Contributing

When adding new guides:
- Focus on cross-cutting concerns, not component-specific details
- Use descriptive names without the `*_guide.md` suffix (we infer it from the directory)
- Include practical examples
- Link to relevant specs, plans, and workflows
- Keep guides up-to-date as patterns evolve
- Document the "why" behind patterns, not just the "how"

### Writing Style
- Start with motivation and context
- Provide concrete examples
- Include anti-patterns (what not to do)
- Reference related documentation
- Use diagrams where helpful
