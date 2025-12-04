# Coding Standards - README

## Overview

This project has **strict coding standards** to ensure consistency, maintainability, and professionalism. All code must comply with these standards.

---

## Files in This Directory

### 1. **CODING_STANDARDS.md** (Main Guide)
- **Comprehensive guide** with detailed explanations
- **12 sections** covering every aspect of code style
- **Complete examples** for every pattern
- **Read this FIRST** before writing any code

**When to use**: Initial reading, detailed reference, code reviews

### 2. **CODING_STANDARDS_QUICK_REF.md** (Quick Reference)
- **One-page cheat sheet** for fast lookups
- **Copy-paste templates** for common patterns
- **Keep visible while coding**

**When to use**: While actively coding, need quick answer

### 3. **.editorconfig** (Editor Configuration)
- **Automatic formatting rules** for editors
- Enforces: indentation, line endings, charset
- Works with VSCode, Vim, Emacs, IntelliJ, etc.

**When to use**: Automatically applied by your editor

---

## Quick Start

### For New Developers

1. **Read CODING_STANDARDS.md** (30 minutes)
   - Understand the philosophy
   - See complete examples
   - Learn the patterns

2. **Print/bookmark CODING_STANDARDS_QUICK_REF.md**
   - Keep visible while coding
   - Use templates for new files
   - Quick lookups

3. **Install EditorConfig plugin** (if needed)
   - VSCode: Install "EditorConfig for VS Code"
   - Vim: Install editorconfig-vim
   - Most editors: Auto-detected

4. **Start coding!**
   - Use templates from quick ref
   - Check standards when unsure
   - Run validation before commit

---

## Enforcement

### Automated Checks

```bash
# Type checking (must pass)
mypy prometheus/ --strict

# Linting (must pass)
ruff check prometheus/

# Code formatting (auto-fix)
ruff format prometheus/

# Docstring coverage
pydocstyle prometheus/
```

### Manual Checks

Before every commit, verify:
- [ ] File header present with all metadata
- [ ] All functions have docstrings
- [ ] All functions have type hints
- [ ] Complex logic has comments
- [ ] Classes organized with section dividers
- [ ] Error handling includes logging

### Code Review

All PRs will be checked for:
- Compliance with naming conventions
- Proper documentation
- Consistent organization
- Type safety
- Test coverage

---

## Examples

### Minimal Complete File

```python
"""
Prometheus v2: Simple Utility Module

This module provides basic utility functions for string manipulation.

Key responsibilities:
- String validation and sanitization
- Format conversion helpers

External dependencies:
- None (stdlib only)

Database tables accessed:
- None

Thread safety: Thread-safe (pure functions, no shared state)

Author: Prometheus Team
Created: 2024-11-24
Last Modified: 2024-11-24
Status: Development
Version: v0.1.0
"""

# ============================================================================
# Imports
# ============================================================================

# Standard library
from typing import Optional

# ============================================================================
# Module Constants
# ============================================================================

MAX_LENGTH: int = 256  # Maximum allowed string length

# ============================================================================
# Public API
# ============================================================================

def sanitize_string(input_str: str, max_length: int = MAX_LENGTH) -> str:
    """Sanitize input string by removing special characters and truncating.
    
    Removes all non-alphanumeric characters except spaces and truncates
    to maximum length. Useful for user input validation.
    
    Args:
        input_str: String to sanitize
        max_length: Maximum length (defaults to MAX_LENGTH constant)
    
    Returns:
        Sanitized string with only alphanumeric chars and spaces
    
    Raises:
        ValueError: If input_str is None or empty
    
    Example:
        >>> sanitize_string("Hello! @World#", max_length=10)
        'Hello Worl'
    """
    # Validate input
    if not input_str:
        raise ValueError("input_str cannot be None or empty")
    
    # Remove special characters (keep alphanumeric and spaces)
    cleaned = ''.join(c for c in input_str if c.isalnum() or c.isspace())
    
    # Truncate to max_length
    return cleaned[:max_length]
```

---

## Philosophy

### Why These Standards?

1. **Consistency** → Easy to navigate codebase
2. **Documentation** → Self-explanatory code
3. **Type Safety** → Catch bugs at development time
4. **Maintainability** → Easy to modify years later
5. **Professionalism** → Production-ready quality

### Core Principles

- **Explicit over implicit**: Type hints, docstrings, comments
- **Organized over ad-hoc**: Section dividers, clear structure
- **Safe over fast**: Validation, error handling, logging
- **Readable over clever**: Clear names, simple logic, comments

---

## FAQs

### Q: Do I really need file headers on EVERY file?
**A**: Yes. They provide critical context for anyone reading the code.

### Q: Can I skip docstrings for simple functions?
**A**: No. Even simple functions need brief docstrings. Private functions can have shorter ones.

### Q: What if mypy --strict is too strict?
**A**: That's the point. Fix the type issues or use proper `# type: ignore` with explanation.

### Q: Can I use a different comment style?
**A**: No. Consistency is critical. Use the prescribed formats.

### Q: What if I disagree with a standard?
**A**: Propose a change in a team discussion. Until then, follow the standard.

---

## Tools & Setup

### VSCode Setup

Install extensions:
- Python (Microsoft)
- Pylance (Microsoft)
- Ruff (Astral)
- EditorConfig for VS Code

Settings (`.vscode/settings.json`):
```json
{
  "python.linting.mypyEnabled": true,
  "python.linting.enabled": true,
  "editor.formatOnSave": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

### Pre-commit Hook (Optional)

Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Prometheus v2 pre-commit hook

echo "Running pre-commit checks..."

# Type checking
echo "1. Type checking..."
mypy prometheus/ --strict
if [ $? -ne 0 ]; then
    echo "❌ Type checking failed"
    exit 1
fi

# Linting
echo "2. Linting..."
ruff check prometheus/
if [ $? -ne 0 ]; then
    echo "❌ Linting failed"
    exit 1
fi

# Tests
echo "3. Running tests..."
pytest tests/unit/ -v
if [ $? -ne 0 ]; then
    echo "❌ Tests failed"
    exit 1
fi

echo "✅ All checks passed"
exit 0
```

Make executable: `chmod +x .git/hooks/pre-commit`

---

## Summary

- **Read**: CODING_STANDARDS.md
- **Reference**: CODING_STANDARDS_QUICK_REF.md
- **Enforce**: mypy + ruff + pytest
- **Check**: Before every commit
- **Follow**: Always, no exceptions

**Consistent standards = Professional codebase = Successful project**
