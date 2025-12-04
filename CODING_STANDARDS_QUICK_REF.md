# Coding Standards - Quick Reference Card

**Print this or keep it visible while coding**

---

## File Header Template (Copy-Paste)

```python
"""
Prometheus v2: [One-line description]

This module [detailed description].

Key responsibilities:
- [Responsibility 1]
- [Responsibility 2]

External dependencies:
- [Package]: [Why needed]

Database tables accessed:
- [Table]: [Read/Write/Both]

Thread safety: [Thread-safe/Not thread-safe/Conditionally thread-safe]

Author: Prometheus Team
Created: 2024-11-24
Last Modified: 2024-11-24
Status: Development
Version: v0.1.0
"""
```

---

## Function Docstring Template

```python
def function_name(arg1: Type1, arg2: Type2) -> ReturnType:
    """Brief one-line summary.
    
    Detailed description of what this function does and why it exists.
    
    Args:
        arg1: Description of arg1
        arg2: Description of arg2
    
    Returns:
        Description of return value
    
    Raises:
        ExceptionType: When this exception occurs
    
    Example:
        >>> result = function_name(val1, val2)
        >>> result
        expected_output
    """
```

---

## Import Order Template

```python
# ============================================================================
# Standard Library Imports
# ============================================================================
import os
from datetime import date
from typing import Dict, List

# ============================================================================
# Third-Party Imports
# ============================================================================
import numpy as np
import pandas as pd

# ============================================================================
# Internal Imports
# ============================================================================
from prometheus.core.config import get_config
from prometheus.core.logging import get_logger
```

---

## Class Organization Template

```python
class ClassName:
    """Class docstring."""
    
    # ========================================================================
    # Public API Methods
    # ========================================================================
    
    def public_method(self):
        """Docstring."""
        pass
    
    # ========================================================================
    # Internal Computation Methods
    # ========================================================================
    
    def _internal_method(self):
        """Docstring."""
        pass
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _helper_method(self):
        """Docstring."""
        pass
```

---

## Naming Conventions Cheat Sheet

| Item | Convention | Example |
|------|-----------|---------|
| Files/Modules | snake_case | `regime_engine.py` |
| Classes | PascalCase | `RegimeEngine` |
| Functions | snake_case (verb) | `calculate_regime()` |
| Variables | snake_case | `regime_state` |
| Constants | SCREAMING_SNAKE_CASE | `MAX_RETRIES` |
| Private | _leading_underscore | `_internal_cache` |

---

## Type Hints Quick Reference

```python
# Basic types
def func(x: int, y: str) -> float:
    pass

# Optional (may be None)
def func(x: Optional[int]) -> str:
    pass

# Union (multiple types)
def func(x: Union[int, float]) -> str:
    pass

# Literal (constrained values)
def func(mode: Literal["LIVE", "PAPER"]) -> None:
    pass

# Collections
def func(items: List[str]) -> Dict[str, float]:
    pass

# Type alias
InstrumentScores: TypeAlias = Dict[str, float]
```

---

## Comment Tags

```python
# TODO(username, 2024-11-24): Description of what needs to be done
# FIXME(username, 2024-11-24): Description of bug to fix
# NOTE: Important information about implementation
# HACK: Explanation of workaround and why needed
```

---

## Error Handling Pattern

```python
def function() -> Result:
    """Function with error handling."""
    
    # Validate inputs early
    if not valid_input:
        raise ValueError(f"Invalid input: {input}")
    
    try:
        result = risky_operation()
    except SpecificError as e:
        logger.error(f"Operation failed: {e}")
        raise CustomError("Meaningful message") from e
    
    # Validate output
    if not valid_result(result):
        raise ResultError("Invalid result")
    
    return result
```

---

## Pre-Commit Checklist

Before `git commit`:

```bash
# 1. Type check
mypy prometheus/ --strict

# 2. Lint
ruff check prometheus/

# 3. Format
ruff format prometheus/

# 4. Tests
pytest -v

# 5. Coverage
pytest --cov=prometheus --cov-report=term-missing
```

---

## Section Dividers

Use these consistently:

```python
# ============================================================================
# Section Name
# ============================================================================

# ========================================================================
# Subsection Name
# ========================================================================
```

---

## Common Patterns

### Module Setup
```python
# At top of every module
logger = get_logger(__name__)

# Constants with type hints and comments
MAX_RETRIES: int = 3  # Maximum retry attempts
```

### Database Operations
```python
with db_manager.get_connection() as conn:
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        conn.commit()
        logger.info("Operation successful")
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise DatabaseError("Operation failed") from e
    finally:
        cursor.close()
```

### Configuration Access
```python
from prometheus.core.config import get_config

config = get_config()
value = config.some_setting
```

---

## Function Length Guidelines

- **Maximum 50 lines** per function (including docstring)
- If longer, split into smaller functions
- Public functions: comprehensive docstrings
- Private functions: shorter docstrings OK

---

## When to Comment

**DO comment:**
- Why, not what
- Non-obvious business logic
- Performance optimizations
- Workarounds
- Complex algorithms
- Magic numbers

**DON'T comment:**
- Obvious code
- Restating what code does
- Commented-out code (delete it)

---

**Keep this visible while coding. Check CODING_STANDARDS.md for details.**
