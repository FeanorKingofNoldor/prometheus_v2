"""
Prometheus v2: Core Type Definitions

This module defines common type aliases and lightweight shared types used
across the Prometheus v2 codebase. It exists to centralise frequently
used type definitions and avoid circular imports between higher-level
modules.

Key responsibilities:
- Provide canonical aliases for common dict/metadata types
- Improve readability of function signatures
- Reduce duplication of complex type declarations

External dependencies:
- typing: Standard library typing primitives only

Database tables accessed:
- None (pure type definitions)

Thread safety: Thread-safe (no mutable global state)

Author: Prometheus Team
Created: 2025-11-24
Last Modified: 2025-11-24
Status: Development
Version: v0.1.0
"""

# ============================================================================
# Imports
# ============================================================================

from __future__ import annotations

from typing import Any, Dict, Mapping, MutableMapping, TypeAlias

# ============================================================================
# Type Aliases
# ============================================================================

# Generic configuration mapping used for parsed YAML/JSON configuration
ConfigDict: TypeAlias = Dict[str, Any]

# Read-only configuration mapping (for function parameters that should not mutate)
ReadonlyConfig: TypeAlias = Mapping[str, Any]

# Generic metadata mapping for attaching arbitrary structured data to records
MetadataDict: TypeAlias = Dict[str, Any]

# Mutable metadata mapping (used when functions intentionally mutate metadata)
MutableMetadata: TypeAlias = MutableMapping[str, Any]
