# Prometheus v2 - Coding Standards Guide

**Version**: 1.0  
**Last Updated**: 2024-11-24  
**Status**: MANDATORY - All code must follow these standards

---

## Table of Contents

1. [File Headers](#file-headers)
2. [Module Documentation](#module-documentation)
3. [Function/Method Documentation](#functionmethod-documentation)
4. [Class Documentation](#class-documentation)
5. [Inline Comments](#inline-comments)
6. [Code Organization](#code-organization)
7. [Type Hints](#type-hints)
8. [Naming Conventions](#naming-conventions)
9. [Import Organization](#import-organization)
10. [Error Handling](#error-handling)
11. [Testing Standards](#testing-standards)
12. [Examples](#examples)

---

## 1. File Headers

**EVERY** Python file must start with this header:

```python
"""
Prometheus v2: [Brief one-line description]

This module [detailed description of what this module does, its purpose,
and how it fits into the overall system].

Key responsibilities:
- [Responsibility 1]
- [Responsibility 2]
- [Responsibility 3]

External dependencies:
- [Dependency 1]: [Why it's needed]
- [Dependency 2]: [Why it's needed]

Database tables accessed:
- [Table 1]: [Read/Write/Both]
- [Table 2]: [Read/Write/Both]

Thread safety: [Thread-safe/Not thread-safe/Conditionally thread-safe]

Author: Prometheus Team
Created: YYYY-MM-DD
Last Modified: YYYY-MM-DD
Status: [Development/Testing/Production]
Version: [Iteration number, e.g., v0.1.0]
"""
```

### Required Sections

| Section | When to Include |
|---------|----------------|
| Key responsibilities | Always |
| External dependencies | If module imports non-stdlib packages |
| Database tables accessed | If module reads/writes to database |
| Thread safety | If module might be used concurrently |
| Author | Always |
| Created | Always |
| Last Modified | Always (update on changes) |
| Status | Always |
| Version | Always |

### Example - Core Module

```python
"""
Prometheus v2: Configuration Management

This module provides centralized configuration management for the entire
Prometheus system. It loads configuration from YAML files and environment
variables, with environment variables taking precedence. Uses Pydantic for
type validation and immutable configuration objects.

Key responsibilities:
- Load and validate configuration from multiple sources
- Provide type-safe config objects to all subsystems
- Support environment-specific overrides (dev/staging/prod)
- Expose singleton config instance for global access

External dependencies:
- pydantic: Type validation and settings management
- pydantic-settings: Environment variable integration
- PyYAML: YAML file parsing

Database tables accessed:
- None (configuration only)

Thread safety: Thread-safe (immutable config, lazy-loaded singleton)

Author: Prometheus Team
Created: 2024-11-24
Last Modified: 2024-11-24
Status: Development
Version: v0.1.0
"""
```

### Example - Engine Module

```python
"""
Prometheus v2: Regime Engine

This module implements the market regime detection engine, which classifies
the current macro/credit environment into discrete regimes (CRISIS, CARRY,
RECOVERY, etc.). Uses a combination of rule-based logic and embedding-based
classification to determine regime state.

Key responsibilities:
- Compute regime state for a given date and region
- Maintain historical regime series in database
- Provide transition probabilities between regimes
- Log all regime changes with metadata and confidence scores

External dependencies:
- numpy: Numerical operations for embedding distances
- pandas: Time-series data manipulation

Database tables accessed:
- regimes (Write): Store regime classifications
- regime_transitions (Write): Log regime state changes
- indicator_readings (Write): Store raw indicator values
- prices_daily (Read): Market data for indicator calculation

Thread safety: Not thread-safe (maintains internal state during computation)

Author: Prometheus Team
Created: 2024-11-24
Last Modified: 2024-11-24
Status: Development
Version: v0.4.0
"""
```

---

## 2. Module Documentation

Immediately after file header, before imports:

```python
"""
[Brief module summary from header - repeated for docstring parsers]
"""

# Standard library imports
import os
from datetime import date, datetime
from typing import Dict, List, Optional

# Third-party imports
import numpy as np
import pandas as pd
from pydantic import BaseModel

# Internal imports
from prometheus.core.config import get_config
from prometheus.core.logging import get_logger

# Module-level logger
logger = get_logger(__name__)

# Module-level constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
VALID_REGIMES = ["CRISIS", "CARRY", "RECOVERY", "NEUTRAL"]
```

### Module-Level Constants

```python
# Configuration constants
DEFAULT_POOL_SIZE: int = 5
MAX_CONNECTIONS: int = 20
CONNECTION_TIMEOUT_SECONDS: int = 30

# Business logic constants
MIN_REGIME_CONFIDENCE: float = 0.7  # Minimum confidence to classify regime
REGIME_WINDOW_DAYS: int = 63  # Trading days for regime window
TRANSITION_HYSTERESIS_DAYS: int = 5  # Days to confirm regime change

# Database constants
BATCH_SIZE: int = 1000  # Records per batch insert
MAX_QUERY_RESULTS: int = 10000  # Limit for unbounded queries
```

**Rules for Constants**:
- SCREAMING_SNAKE_CASE for all module constants
- Type hint every constant
- Inline comment explaining the constant's purpose
- Group related constants together with section comments

---

## 3. Function/Method Documentation

**Google-style docstrings** for all public functions:

```python
def calculate_regime_embedding(
    market_data: pd.DataFrame,
    window_days: int,
    as_of_date: date,
) -> np.ndarray:
    """Calculate regime embedding vector for a given market window.
    
    Computes a high-dimensional embedding representing the market state over
    a rolling window. The embedding captures cross-asset correlations, volatility
    patterns, and factor behavior. Used as input to regime classification.
    
    Algorithm:
    1. Extract OHLCV data for window [as_of_date - window_days, as_of_date]
    2. Compute returns, volatilities, and correlations
    3. Pass through NumericWindowEncoder to get embedding
    4. Normalize embedding to unit length
    
    Args:
        market_data: DataFrame with columns [date, instrument_id, close, volume]
            Must contain at least window_days of history before as_of_date.
        window_days: Number of trading days in the rolling window.
            Typical values: 21 (month), 63 (quarter), 252 (year).
        as_of_date: Date for which to compute embedding. Data after this
            date is excluded (prevents look-ahead bias in backtests).
    
    Returns:
        Embedding vector of shape (embedding_dim,) where embedding_dim is
        determined by the encoder configuration (typically 128 or 256).
        Returns normalized vector (L2 norm = 1.0).
    
    Raises:
        ValueError: If market_data has insufficient history (< window_days).
        ValueError: If window_days < 1 or > 500 (unreasonable values).
        RuntimeError: If encoder fails to produce embedding.
    
    Example:
        >>> market_data = load_prices(start_date=date(2023, 1, 1))
        >>> embedding = calculate_regime_embedding(
        ...     market_data=market_data,
        ...     window_days=63,
        ...     as_of_date=date(2023, 6, 1),
        ... )
        >>> embedding.shape
        (128,)
        >>> np.linalg.norm(embedding)
        1.0
    
    Notes:
        - This function is deterministic for the same inputs
        - Encoder weights must be loaded before calling
        - Performance: ~50ms for 63-day window on typical hardware
    
    See Also:
        - NumericWindowEncoder: The encoder used internally
        - classify_regime: Uses this embedding to determine regime
    """
    # Validate inputs
    if window_days < 1 or window_days > 500:
        raise ValueError(f"Invalid window_days: {window_days}. Must be in [1, 500].")
    
    # Extract window data (implementation continues...)
```

### Required Docstring Sections

| Section | Always Required? | When to Include |
|---------|-----------------|-----------------|
| Brief summary (one line) | Yes | Always |
| Detailed description | Yes | Always |
| Algorithm (if non-trivial) | No | For complex logic |
| Args | If function has params | Always |
| Returns | If function returns value | Always |
| Raises | If function can raise | Always (list all exceptions) |
| Example | No | For public API functions |
| Notes | No | For important caveats |
| See Also | No | For related functions |

### Private Function Documentation

```python
def _validate_market_data(data: pd.DataFrame) -> None:
    """Validate market data DataFrame has required columns and types.
    
    Internal validation helper. Raises ValueError if data is invalid.
    
    Args:
        data: Market data DataFrame to validate
    
    Raises:
        ValueError: If required columns missing or types incorrect
    """
    required_cols = ["date", "instrument_id", "close", "volume"]
    missing = set(required_cols) - set(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
```

**Private functions** (starting with `_`):
- Shorter docstrings acceptable
- Must still document Args, Raises
- Can skip Examples/Notes unless critical

---

## 4. Class Documentation

```python
class RegimeEngine:
    """Market regime detection and classification engine.
    
    The RegimeEngine is responsible for determining the current macro/credit
    market regime based on a combination of indicators and embeddings. It
    maintains a historical time-series of regime states and provides regime
    classification for any historical date.
    
    The engine operates in two modes:
    1. Online mode: Classify current market regime
    2. Backtest mode: Classify historical regimes for backtesting
    
    Regime classification is deterministic given the same input data and
    configuration, ensuring reproducible backtests.
    
    Attributes:
        config: RegimeEngineConfig with hyperparameters and thresholds
        encoder: NumericWindowEncoder instance for computing embeddings
        classifier: RegimeClassifier for mapping embeddings to regime labels
        storage: RegimeStorage for database operations
        _regime_cache: Dict mapping (date, region) -> RegimeState for caching
    
    Example:
        >>> engine = RegimeEngine(config=config)
        >>> regime = engine.get_regime(
        ...     as_of_date=date(2024, 1, 15),
        ...     region="US"
        ... )
        >>> print(regime.regime_label)
        'CARRY'
        >>> print(regime.confidence)
        0.87
    
    Thread Safety:
        Not thread-safe. Create separate instances for concurrent use.
    
    See Also:
        - RegimeState: Output data structure
        - RegimeEngineConfig: Configuration object
        - specs/100_regime_engine.md: Full specification
    """
    
    def __init__(
        self,
        config: RegimeEngineConfig,
        encoder: Optional[NumericWindowEncoder] = None,
    ) -> None:
        """Initialize RegimeEngine with configuration.
        
        Args:
            config: Configuration object with hyperparameters
            encoder: Optional encoder instance (creates default if None)
        
        Raises:
            ValueError: If config validation fails
            RuntimeError: If encoder cannot be initialized
        """
        self.config = config
        self.encoder = encoder or self._create_default_encoder()
        self.classifier = RegimeClassifier(config)
        self.storage = RegimeStorage(get_db_manager())
        self._regime_cache: Dict[tuple[date, str], RegimeState] = {}
        
        logger.info(f"RegimeEngine initialized with config version {config.version}")
```

### Class-Level Comments

```python
class RegimeEngine:
    """[Docstring as above]"""
    
    # ============================================================================
    # Public API Methods
    # ============================================================================
    
    def get_regime(self, as_of_date: date, region: str) -> RegimeState:
        """[Docstring]..."""
        pass
    
    def get_history(
        self,
        start_date: date,
        end_date: date,
        region: str,
    ) -> List[RegimeState]:
        """[Docstring]..."""
        pass
    
    # ============================================================================
    # Internal Computation Methods
    # ============================================================================
    
    def _compute_embedding(self, date: date, region: str) -> np.ndarray:
        """[Docstring]..."""
        pass
    
    def _classify_regime(self, embedding: np.ndarray) -> str:
        """[Docstring]..."""
        pass
    
    # ============================================================================
    # Helper Methods
    # ============================================================================
    
    def _validate_inputs(self, as_of_date: date, region: str) -> None:
        """[Docstring]..."""
        pass
```

**Class Organization Order**:
1. Public API methods (what users call)
2. Internal computation methods (core logic)
3. Helper/utility methods (validation, formatting)
4. Properties (if any)
5. Class methods (if any)
6. Static methods (if any)

---

## 5. Inline Comments

### When to Use Inline Comments

**DO comment**:
- Non-obvious business logic
- Performance optimizations
- Workarounds for library bugs
- Complex algorithms
- Magic numbers (even if also constants)

**DON'T comment**:
- Obvious code (`i += 1  # increment i`)
- Restating what the code does
- Commented-out code (delete it, use git)

### Good Inline Comments

```python
def calculate_slippage(order: Order, market_depth: MarketDepth) -> float:
    """Calculate realistic slippage for order execution."""
    
    # Use square-root market impact model (Kyle 1985)
    # Impact scales with sqrt(order_size / daily_volume)
    base_impact = np.sqrt(order.quantity / market_depth.avg_daily_volume)
    
    # Add spread component (always pay half-spread at minimum)
    spread_cost = market_depth.bid_ask_spread / 2.0
    
    # Apply urgency multiplier (aggressive orders pay more)
    if order.urgency == Urgency.IMMEDIATE:
        urgency_multiplier = 2.0  # 2x impact for immediate fills
    else:
        urgency_multiplier = 1.0  # Normal impact for patient orders
    
    # Total slippage in basis points
    slippage_bps = (base_impact + spread_cost) * urgency_multiplier * 10000
    
    # Cap at 50bps to handle illiquid edge cases
    return min(slippage_bps, 50.0)
```

### Comment Blocks for Complex Logic

```python
def optimize_portfolio(
    scores: Dict[str, float],
    constraints: ConstraintSet,
) -> Dict[str, float]:
    """Optimize portfolio weights using quadratic programming."""
    
    # ========================================================================
    # PHASE 1: Construct optimization problem
    # ========================================================================
    # We solve: minimize (1/2 * w^T * Sigma * w - lambda * mu^T * w)
    # subject to: sum(w) = 1, w >= 0, sector constraints
    #
    # Where:
    # - w: weight vector (what we're solving for)
    # - Sigma: covariance matrix (risk)
    # - mu: expected returns (from scores)
    # - lambda: risk aversion parameter
    # ========================================================================
    
    n_assets = len(scores)
    
    # Build expected return vector from scores
    # Scores are in [0, 1], convert to annualized returns in [-10%, +30%]
    mu = np.array([
        -0.10 + 0.40 * score  # Linear mapping: 0->-10%, 1->+30%
        for score in scores.values()
    ])
    
    # Build covariance matrix from historical returns
    # Use exponentially-weighted moving average (decay = 0.94)
    returns = get_historical_returns(list(scores.keys()))
    Sigma = calculate_ewma_covariance(returns, decay=0.94)
    
    # Risk aversion: higher = more conservative
    lambda_risk = 1.0  # Standard risk aversion
    
    # ========================================================================
    # PHASE 2: Add constraints
    # ========================================================================
    
    # (Implementation continues...)
```

### TODO/FIXME/NOTE Comments

```python
# TODO(username, 2024-11-24): Implement caching for regime embeddings
# Currently recomputes on every call, could cache by date+region key.
# Expected performance improvement: 10x faster for repeated queries.

# FIXME(username, 2024-11-24): Handle market holidays correctly
# Currently assumes all weekdays are trading days. Need to integrate
# TradingCalendar to skip holidays. Affects ~5 days/year.

# NOTE: This approximation assumes normal distribution of returns
# May underestimate tail risk in crisis regimes. Consider using
# t-distribution or EVT for risk_off_panic regime.

# HACK: psycopg2 doesn't support JSONB array contains operator directly
# Using raw SQL string interpolation here. Safe because no user input.
# Alternative would be to use SQLAlchemy Core expressions.
```

**Format**: `# TAG(author, date): Description`

---

## 6. Code Organization

### File Structure

Every module should follow this order:

```python
"""
[File header with metadata]
"""

# ============================================================================
# Imports
# ============================================================================

# Standard library
import os
from datetime import date
from typing import Dict, List

# Third-party
import numpy as np
import pandas as pd

# Internal
from prometheus.core.config import get_config
from prometheus.core.logging import get_logger

# ============================================================================
# Module Constants
# ============================================================================

logger = get_logger(__name__)

DEFAULT_WINDOW = 63
MAX_RETRIES = 3

# ============================================================================
# Type Definitions
# ============================================================================

# Type aliases
RegimeLabel = Literal["CRISIS", "CARRY", "RECOVERY", "NEUTRAL"]
RegionCode = str  # ISO 3166 alpha-2 country code

# ============================================================================
# Data Classes / Models
# ============================================================================

@dataclass
class RegimeState:
    """[Docstring]"""
    as_of_date: date
    region: str
    regime_label: RegimeLabel
    confidence: float

# ============================================================================
# Main Classes
# ============================================================================

class RegimeEngine:
    """[Docstring]"""
    pass

# ============================================================================
# Helper Functions
# ============================================================================

def parse_region_code(region: str) -> str:
    """[Docstring]"""
    pass

# ============================================================================
# Module-Level Functions (if public API)
# ============================================================================

def get_current_regime(region: str = "US") -> RegimeState:
    """[Docstring]"""
    pass
```

### Function Length Guidelines

- **Maximum 50 lines** per function (including docstring)
- If longer, split into smaller functions
- Exception: Generated code, complex but linear flows

### Function Organization Within File

```python
# ============================================================================
# Public API
# ============================================================================

def public_function_1():
    """User-facing function."""
    pass

def public_function_2():
    """User-facing function."""
    pass

# ============================================================================
# Internal Implementation
# ============================================================================

def _internal_helper_1():
    """Internal helper."""
    pass

def _internal_helper_2():
    """Internal helper."""
    pass

# ============================================================================
# Validation & Error Handling
# ============================================================================

def _validate_input(data):
    """Input validation."""
    pass

def _handle_database_error(error):
    """Error recovery."""
    pass
```

---

## 7. Type Hints

**ALL** functions must have complete type hints:

```python
from typing import Dict, List, Optional, Union, Literal, TypeAlias

# Good: Complete type hints
def calculate_score(
    prices: pd.DataFrame,
    window: int,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """[Docstring]"""
    pass

# Bad: Missing types
def calculate_score(prices, window, threshold=0.5):
    """[Docstring]"""
    pass

# Good: Type aliases for complex types
InstrumentScores: TypeAlias = Dict[str, float]
PriceHistory: TypeAlias = pd.DataFrame

def calculate_score(
    prices: PriceHistory,
    window: int,
) -> InstrumentScores:
    """[Docstring]"""
    pass
```

### Type Hint Guidelines

```python
# Use Optional for nullable values
def get_regime(date: date, region: str) -> Optional[RegimeState]:
    """May return None if no regime computed for date."""
    pass

# Use Union for multiple possible types
def parse_value(value: Union[int, float, str]) -> float:
    """Accepts int, float, or numeric string."""
    pass

# Use Literal for constrained strings
def set_mode(mode: Literal["LIVE", "PAPER", "BACKTEST"]) -> None:
    """Mode must be one of three values."""
    pass

# Use TypeAlias for repeated complex types
ConnectionPool: TypeAlias = Dict[str, List[Connection]]

# Use generics for containers
def process_batch(items: List[RegimeState]) -> Dict[str, List[float]]:
    """Process list of states, return dict of lists."""
    pass
```

---

## 8. Naming Conventions

### Files and Modules

```
# Good
prometheus/core/config.py
prometheus/regime/engine.py
prometheus/assessment/context_builder.py

# Bad (capitalized, spaces, special chars)
prometheus/core/Config.py
prometheus/regime/Regime_Engine.py
prometheus/assessment/context builder.py
```

### Classes

```python
# Good: PascalCase, descriptive
class RegimeEngine:
    pass

class MarketDataReader:
    pass

class StabilityVectorBuilder:
    pass

# Bad: snake_case, abbreviations
class regime_engine:
    pass

class MktDataRdr:
    pass
```

### Functions and Methods

```python
# Good: snake_case, verb-based
def calculate_regime():
    pass

def get_market_data():
    pass

def validate_inputs():
    pass

# Bad: camelCase, unclear
def calculateRegime():
    pass

def data():
    pass

def check():
    pass
```

### Variables

```python
# Good: snake_case, descriptive
regime_state = get_regime()
market_data = load_prices()
embedding_vector = compute_embedding()

# Bad: single letters (except loop counters), abbreviations
rs = get_regime()
mkt_dat = load_prices()
emb_vec = compute_embedding()

# Exception: OK for loop counters
for i in range(10):
    pass

for idx, item in enumerate(items):
    pass
```

### Constants

```python
# Good: SCREAMING_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
API_BASE_URL = "https://api.example.com"

# Bad: lowercase, camelCase
max_retries = 3
defaultTimeout = 30
```

### Private Members

```python
class Engine:
    def __init__(self):
        # Public attribute
        self.config = load_config()
        
        # Private attribute (single underscore)
        self._cache: Dict[str, Any] = {}
        
        # Name-mangled private (double underscore, rare)
        self.__secret_key = generate_key()
    
    # Public method
    def get_regime(self):
        pass
    
    # Private method
    def _compute_embedding(self):
        pass
```

---

## 9. Import Organization

**Order** (with blank lines between sections):

```python
"""
[File header]
"""

# ============================================================================
# Standard Library Imports (alphabetical)
# ============================================================================
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================================
# Third-Party Imports (alphabetical by package)
# ============================================================================
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
import yaml

# ============================================================================
# Internal Imports (by module, then alphabetical)
# ============================================================================
# Core
from prometheus.core.config import PrometheusConfig, get_config
from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger
from prometheus.core.types import ConfigDict, MetadataDict

# Data
from prometheus.data.reader import DataReader
from prometheus.data.types import PriceBar

# Regime (if in different module)
from prometheus.regime.types import RegimeState
```

### Import Guidelines

```python
# Good: Explicit imports
from prometheus.core.config import PrometheusConfig, get_config
from prometheus.core.database import get_db_manager

# Bad: Star imports
from prometheus.core.config import *
from prometheus.core.database import *

# Good: Aliasing for long names
from prometheus.assessment.context_builder import DecisionContextBuilder as ContextBuilder

# Bad: Unnecessary aliasing
from prometheus.core.config import PrometheusConfig as PC

# Good: Relative imports within package
from .types import RegimeState
from .storage import RegimeStorage

# Only use relative imports within same top-level package
```

---

## 10. Error Handling

### Exception Documentation

```python
class ConfigurationError(Exception):
    """Raised when configuration is invalid or incomplete.
    
    Attributes:
        config_key: The configuration key that failed validation
        reason: Human-readable explanation of the failure
    """
    
    def __init__(self, config_key: str, reason: str) -> None:
        self.config_key = config_key
        self.reason = reason
        super().__init__(f"Invalid config for '{config_key}': {reason}")
```

### Exception Handling Patterns

```python
def load_market_data(instrument_id: str, date: date) -> pd.DataFrame:
    """Load market data with comprehensive error handling.
    
    Raises:
        ValueError: If instrument_id is invalid format
        DatabaseError: If database connection fails
        DataNotFoundError: If no data exists for given date
    """
    # Validate inputs early
    if not instrument_id or len(instrument_id) < 3:
        raise ValueError(f"Invalid instrument_id: '{instrument_id}'")
    
    try:
        # Attempt database operation
        data = _query_database(instrument_id, date)
    except psycopg2.OperationalError as e:
        # Database connection issue - log and re-raise as custom exception
        logger.error(f"Database connection failed: {e}")
        raise DatabaseError("Failed to connect to historical_db") from e
    except psycopg2.DataError as e:
        # Data integrity issue - log and re-raise
        logger.error(f"Data integrity error for {instrument_id}: {e}")
        raise DataIntegrityError(f"Corrupt data for {instrument_id}") from e
    
    # Validate returned data
    if data.empty:
        raise DataNotFoundError(
            f"No data found for instrument_id={instrument_id}, date={date}"
        )
    
    return data
```

### Logging with Exceptions

```python
def process_regime_computation(date: date) -> RegimeState:
    """Process regime computation with detailed logging."""
    
    logger.info(f"Starting regime computation for {date}")
    
    try:
        # Attempt computation
        regime = _compute_regime(date)
        logger.info(
            f"Regime computation successful: {regime.regime_label} "
            f"(confidence={regime.confidence:.2f})"
        )
        return regime
        
    except InsufficientDataError as e:
        # Expected error - log as warning
        logger.warning(f"Insufficient data for regime computation: {e}")
        raise
        
    except Exception as e:
        # Unexpected error - log with full traceback
        logger.exception(f"Unexpected error in regime computation: {e}")
        raise RuntimeError("Regime computation failed") from e
```

---

## 11. Testing Standards

### Test File Headers

```python
"""
Prometheus v2: Tests for [Module Name]

Test suite for [module path]. Covers [brief description of what's tested].

Test coverage:
- [Component 1]: [What's tested]
- [Component 2]: [What's tested]

Test fixtures used:
- [Fixture 1]: [What it provides]
- [Fixture 2]: [What it provides]

Author: Prometheus Team
Created: YYYY-MM-DD
Last Modified: YYYY-MM-DD
"""
```

### Test Function Documentation

```python
def test_regime_classification_with_high_volatility() -> None:
    """Test regime classification correctly identifies CRISIS during high vol.
    
    Scenario:
        Given market data with VIX > 40 and HY spreads > 600bp
        When regime classification is run
        Then regime should be CRISIS
        And confidence should be > 0.9
    
    This test validates the crisis detection threshold and ensures
    high-volatility periods are not misclassified as other regimes.
    """
    # Arrange: Create high volatility scenario
    market_data = create_mock_data(vix=45.0, hy_spread=650.0)
    engine = RegimeEngine(config=test_config)
    
    # Act: Classify regime
    regime = engine.get_regime(
        as_of_date=date(2024, 1, 15),
        region="US",
    )
    
    # Assert: Verify crisis detection
    assert regime.regime_label == "CRISIS"
    assert regime.confidence > 0.9
    assert regime.metadata["vix"] > 40.0
```

---

## 12. Examples

### Complete Module Example

```python
"""
Prometheus v2: Regime Storage Layer

This module handles all database operations for the Regime Engine. It provides
a clean abstraction over the database, handling connection management, query
construction, and result parsing.

Key responsibilities:
- Store regime state classifications to regimes table
- Store indicator readings to indicator_readings table
- Query historical regime series by date range
- Log regime transitions with metadata

External dependencies:
- psycopg2: PostgreSQL database adapter

Database tables accessed:
- regimes (Write): Insert/update regime classifications
- indicator_readings (Write): Store raw indicator values
- regime_transitions (Write): Log state changes
- regimes (Read): Query historical regime series

Thread safety: Not thread-safe (uses shared connection pool)

Author: Prometheus Team
Created: 2024-11-24
Last Modified: 2024-11-24
Status: Development
Version: v0.4.0
"""

# ============================================================================
# Imports
# ============================================================================

# Standard library
from datetime import date
from typing import Dict, List, Optional

# Third-party
import psycopg2
from psycopg2.extensions import connection as Connection

# Internal
from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.regime.types import RegimeState

# ============================================================================
# Module Setup
# ============================================================================

logger = get_logger(__name__)

# SQL query templates (avoid string formatting in execute calls)
INSERT_REGIME_SQL = """
    INSERT INTO regimes (
        regime_record_id, as_of_date, region, regime_label,
        confidence, metadata, created_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, NOW()
    )
    ON CONFLICT (as_of_date, region) DO UPDATE SET
        regime_label = EXCLUDED.regime_label,
        confidence = EXCLUDED.confidence,
        metadata = EXCLUDED.metadata
"""

# ============================================================================
# Main Classes
# ============================================================================

class RegimeStorage:
    """Handles database operations for Regime Engine.
    
    Provides methods to store and retrieve regime states, ensuring all
    database interactions are properly logged and error-handled.
    
    Attributes:
        db_manager: DatabaseManager instance for connection pooling
    
    Example:
        >>> storage = RegimeStorage(get_db_manager())
        >>> regime = RegimeState(...)
        >>> storage.insert_regime(regime)
    """
    
    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize storage with database manager.
        
        Args:
            db_manager: DatabaseManager for connection pooling
        """
        self.db_manager = db_manager
        logger.info("RegimeStorage initialized")
    
    # ========================================================================
    # Public API: Write Operations
    # ========================================================================
    
    def insert_regime(self, regime: RegimeState) -> None:
        """Insert regime state into database.
        
        Inserts the regime classification for a given date and region.
        If a record already exists for this (date, region), it will be
        updated with the new values.
        
        Args:
            regime: RegimeState object to store
        
        Raises:
            DatabaseError: If insert fails due to database issue
            
        Example:
            >>> regime = RegimeState(
            ...     as_of_date=date(2024, 1, 15),
            ...     region="US",
            ...     regime_label="CARRY",
            ...     confidence=0.87,
            ... )
            >>> storage.insert_regime(regime)
        """
        with self.db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Execute insert with upsert semantics
                cursor.execute(
                    INSERT_REGIME_SQL,
                    (
                        regime.regime_record_id,
                        regime.as_of_date,
                        regime.region,
                        regime.regime_label,
                        regime.confidence,
                        regime.metadata,  # psycopg2 handles dict -> jsonb
                    )
                )
                conn.commit()
                
                logger.info(
                    f"Inserted regime: date={regime.as_of_date}, "
                    f"region={regime.region}, label={regime.regime_label}"
                )
                
            except psycopg2.Error as e:
                # Rollback on error
                conn.rollback()
                logger.error(f"Failed to insert regime: {e}")
                raise DatabaseError("Regime insert failed") from e
            
            finally:
                cursor.close()
    
    # ========================================================================
    # Public API: Read Operations
    # ========================================================================
    
    def get_regime_history(
        self,
        start_date: date,
        end_date: date,
        region: str,
    ) -> List[RegimeState]:
        """Retrieve historical regime states for a date range.
        
        Queries the regimes table for all regime classifications between
        start_date and end_date (inclusive) for the specified region.
        Results are ordered chronologically.
        
        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            region: Region code (e.g., "US", "EU", "JP")
        
        Returns:
            List of RegimeState objects, ordered by date ascending.
            Returns empty list if no regimes found in range.
        
        Raises:
            ValueError: If start_date > end_date
            DatabaseError: If query fails
        
        Example:
            >>> history = storage.get_regime_history(
            ...     start_date=date(2023, 1, 1),
            ...     end_date=date(2023, 12, 31),
            ...     region="US",
            ... )
            >>> len(history)
            252  # One per trading day
        """
        # Validate date range
        if start_date > end_date:
            raise ValueError(
                f"Invalid date range: start_date ({start_date}) > "
                f"end_date ({end_date})"
            )
        
        with self.db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            
            try:
                # Query regime history
                cursor.execute(
                    """
                    SELECT
                        regime_record_id, as_of_date, region,
                        regime_label, confidence, metadata
                    FROM regimes
                    WHERE as_of_date BETWEEN %s AND %s
                        AND region = %s
                    ORDER BY as_of_date ASC
                    """,
                    (start_date, end_date, region)
                )
                
                rows = cursor.fetchall()
                
                # Parse rows into RegimeState objects
                regimes = [
                    RegimeState(
                        regime_record_id=row[0],
                        as_of_date=row[1],
                        region=row[2],
                        regime_label=row[3],
                        confidence=row[4],
                        metadata=row[5],
                    )
                    for row in rows
                ]
                
                logger.info(
                    f"Retrieved {len(regimes)} regime records for "
                    f"region={region}, date_range=[{start_date}, {end_date}]"
                )
                
                return regimes
                
            except psycopg2.Error as e:
                logger.error(f"Failed to query regime history: {e}")
                raise DatabaseError("Regime history query failed") from e
            
            finally:
                cursor.close()
    
    # ========================================================================
    # Internal Helper Methods
    # ========================================================================
    
    def _validate_regime_state(self, regime: RegimeState) -> None:
        """Validate RegimeState before database insertion.
        
        Internal validation helper. Checks that all required fields are
        present and have valid values.
        
        Args:
            regime: RegimeState to validate
        
        Raises:
            ValueError: If any validation check fails
        """
        if regime.confidence < 0.0 or regime.confidence > 1.0:
            raise ValueError(
                f"Invalid confidence: {regime.confidence}. Must be in [0, 1]."
            )
        
        if regime.regime_label not in VALID_REGIME_LABELS:
            raise ValueError(
                f"Invalid regime_label: {regime.regime_label}. "
                f"Must be one of {VALID_REGIME_LABELS}."
            )


# ============================================================================
# Module-Level Helper Functions
# ============================================================================

def create_regime_storage() -> RegimeStorage:
    """Create RegimeStorage instance with default database manager.
    
    Convenience function for creating storage without manually passing
    database manager.
    
    Returns:
        Initialized RegimeStorage instance
    
    Example:
        >>> storage = create_regime_storage()
        >>> storage.insert_regime(regime)
    """
    from prometheus.core.database import get_db_manager
    return RegimeStorage(get_db_manager())
```

---

## Quick Reference Checklist

Before committing any Python file, verify:

- [ ] File header with all required metadata
- [ ] Module docstring present
- [ ] Imports organized correctly (stdlib → third-party → internal)
- [ ] Module constants defined with type hints and comments
- [ ] All functions have Google-style docstrings
- [ ] All functions have complete type hints
- [ ] Complex logic has inline comments explaining "why"
- [ ] Classes organized: public methods → private methods → helpers
- [ ] Section dividers used for class organization
- [ ] Error handling includes logging
- [ ] Test files follow testing standards
- [ ] mypy --strict passes
- [ ] ruff check passes

---

## Tools for Enforcement

```bash
# Type checking (must pass)
mypy prometheus/ --strict

# Linting (must pass)
ruff check prometheus/

# Docstring coverage (aim for 100%)
pydocstyle prometheus/

# Code formatting (auto-fix)
ruff format prometheus/
```

---

**This guide is MANDATORY. All code reviews will check compliance.**

Save this file and refer to it before writing any code. Consistent standards make the codebase maintainable and professional.
