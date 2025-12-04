# 015 – Execution and Backtesting Infrastructure

## 1. Purpose

This document specifies the **execution layer** and **backtesting infrastructure** for Prometheus v2, covering:
- Live/paper trading via IBKR Gateway/TWS API.
- Unified broker interface that works identically in LIVE, PAPER, and BACKTEST modes.
- Market simulator for backtesting with realistic fill modeling and time-travel data access.
- Position tracking, reconciliation, and execution logging.

The execution layer is the bridge between Portfolio & Risk Engine decisions and actual market orders (or simulated orders in backtesting).

---

## 2. Design Principles

1. **Mode-agnostic interface**
   - Portfolio & Risk Engine and other clients interact with a unified `BrokerInterface` that abstracts LIVE/PAPER/BACKTEST modes.
   - Same API calls in all modes ensure backtests are representative of live behavior.

2. **No look-ahead bias in backtesting**
   - Backtesting mode uses a `TimeMachine` that gates all data access by `as_of_date`.
   - Engines see exactly the data available at that historical moment, no more.

3. **Realistic fill simulation**
   - In BACKTEST mode, fills respect:
     - historical volume and liquidity,
     - bid-ask spreads,
     - slippage and impact models,
     - market/limit/stop order semantics.

4. **Audit trail and reproducibility**
   - All orders, fills, and position changes logged to `runtime_db` with timestamps and mode indicators.
   - Backtests are deterministic given seeds and historical data.

---

## 3. Architecture Overview

```
                    ┌──────────────────────────────────┐
                    │  Portfolio & Risk Engine (150)   │
                    └────────────┬─────────────────────┘
                                 │
                                 │ proposed_positions
                                 ▼
                    ┌──────────────────────────────────┐
                    │       Order Planner / Router     │
                    │  - Computes orders (deltas)      │
                    │  - Routes to BrokerInterface     │
                    └────────────┬─────────────────────┘
                                 │
                                 │ Order objects
                                 ▼
        ┌────────────────────────────────────────────────┐
        │           BrokerInterface (abstract)           │
        │  - submit_order(order)                         │
        │  - get_positions()                             │
        │  - get_account_state()                         │
        └─────┬──────────────┬───────────────┬───────────┘
              │              │               │
     ┌────────▼─────┐  ┌────▼─────┐  ┌──────▼──────┐
     │ LiveBroker   │  │PaperBroker│  │ BacktestBroker│
     │ (IBKR TWS)   │  │ (IBKR Paper)│ │ (Simulator) │
     └──────────────┘  └───────────┘  └──────┬──────┘
                                              │
                                              │ uses
                                              ▼
                                    ┌──────────────────┐
                                    │  MarketSimulator │
                                    │  + TimeMachine   │
                                    └──────────────────┘
```

---

## 4. BrokerInterface API

Module: `prometheus/execution/broker_interface.py`

### 4.1 Abstract interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass
class Order:
    order_id: str  # unique ID
    instrument_id: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    metadata: Dict = None

@dataclass
class Fill:
    fill_id: str
    order_id: str
    instrument_id: str
    side: OrderSide
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0
    metadata: Dict = None

@dataclass
class Position:
    instrument_id: str
    quantity: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float

class BrokerInterface(ABC):
    """Abstract interface for broker interactions (live, paper, backtest)."""

    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """Submit an order and return order_id."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get current status of an order."""

    @abstractmethod
    def get_fills(self, since: datetime | None = None) -> List[Fill]:
        """Retrieve fills since a timestamp."""

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Get current positions keyed by instrument_id."""

    @abstractmethod
    def get_account_state(self) -> Dict:
        """Get account-level info: cash, equity, margin, etc."""

    @abstractmethod
    def sync(self):
        """Sync state with broker (fetch latest positions, fills, etc.)."""
```

---

## 5. Implementation: LiveBroker (IBKR Gateway/TWS)

Module: `prometheus/execution/live_broker.py`

### 5.1 IBKR Integration

Uses **ib_insync** or **ibapi** (official Interactive Brokers API) to connect to:
- **IBKR Gateway** (headless) or **TWS** (desktop app)
- Runs on localhost:4001 (paper) or localhost:7496 (live) by default

### 5.2 Key responsibilities

- Translate Prometheus `Order` objects to IBKR `Contract` + `Order` objects.
- Handle connection lifecycle (connect, reconnect, error recovery).
- Subscribe to order status updates and fill notifications.
- Map IBKR instrument identifiers to Prometheus `instrument_id`.
- Log all orders and fills to `runtime_db.executed_actions` and `runtime_db.fills`.

### 5.3 Config

```yaml
# configs/execution/live.yaml
mode: LIVE
ibkr:
  host: 127.0.0.1
  port: 7496  # live TWS; use 4001 for paper
  client_id: 1
  timeout_sec: 60
logging:
  log_all_orders: true
  log_all_fills: true
```

---

## 6. Implementation: PaperBroker (IBKR Paper Trading)

Module: `prometheus/execution/paper_broker.py`

### 6.1 Purpose

Identical to LiveBroker but connects to IBKR's paper trading environment.
- Port 4001 (Gateway) or paper TWS.
- Uses simulated fills from IBKR's paper trading backend.

### 6.2 Differences from live

- No real money at risk.
- Fill quality may differ from live (IBKR's paper fill logic is simplified).
- Useful for integration testing and strategy dry-runs.

---

## 7. Implementation: BacktestBroker (Market Simulator)

Module: `prometheus/execution/backtest_broker.py`

### 7.1 Purpose

Provides a broker-like interface for backtesting, using historical data and a market simulator.

### 7.2 Components

**TimeMachine** (`prometheus/execution/time_machine.py`)
- Maintains current backtest date/time: `as_of_date`.
- Gates all data access: only returns data available up to `as_of_date`.
- Advances time step-by-step (e.g., day-by-day or intraday).

**MarketSimulator** (`prometheus/execution/market_simulator.py`)
- Accepts orders from BacktestBroker.
- Simulates fills using historical prices, volumes, and spreads from `historical_db`.
- Models:
  - **Market orders**: fill at open/close/VWAP depending on config, with slippage.
  - **Limit orders**: fill only if price crosses limit, respecting volume constraints.
  - **Stop orders**: trigger when price crosses stop, then fill as market.
- Tracks simulated positions and cash.
- Logs simulated fills to in-memory or temporary tables (for backtest replay).

### 7.3 Fill modeling

```python
@dataclass
class FillConfig:
    market_slippage_bps: float = 5.0  # basis points
    limit_fill_prob: float = 0.9  # probability of limit fill when price crosses
    use_volume_constraints: bool = True  # respect daily volume
    max_participation_rate: float = 0.10  # max % of daily volume
```

For a market buy order:
1. Fetch `prices_daily` for `as_of_date`.
2. Fill price = `close * (1 + market_slippage_bps / 10000)`.
3. Check volume: if `order_quantity > daily_volume * max_participation_rate`, partial fill or reject.
4. Record fill with timestamp = `session_close(as_of_date)`.

For limit orders, check if `low <= limit_price <= high` on `as_of_date`; if yes, fill at `limit_price` (possibly with probability adjustment).

### 7.4 API example

```python
from datetime import date

# Initialize backtest broker
backtest_broker = BacktestBroker(
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
    initial_cash=1_000_000,
    fill_config=FillConfig()
)

# Step through time
for as_of_date in backtest_broker.time_machine.iter_trading_days():
    # Set current date
    backtest_broker.time_machine.set_date(as_of_date)
    
    # Portfolio engine computes target positions (only using data up to as_of_date)
    target_positions = portfolio_engine.compute_targets(as_of_date)
    
    # Generate orders
    orders = order_planner.plan_orders(
        current_positions=backtest_broker.get_positions(),
        target_positions=target_positions
    )
    
    # Submit orders
    for order in orders:
        backtest_broker.submit_order(order)
    
    # Process fills at end of day
    backtest_broker.process_fills(as_of_date)
    
    # Log performance
    portfolio_value = backtest_broker.get_account_state()['equity']
    print(f"{as_of_date}: Portfolio value = {portfolio_value}")
```

---

## 8. Order Planner / Router

Module: `prometheus/execution/order_planner.py`

### 8.1 Purpose

Converts target positions from Portfolio & Risk Engine into executable orders.

### 8.2 Logic

```python
def plan_orders(
    current_positions: Dict[str, Position],
    target_positions: Dict[str, float],  # instrument_id -> target_quantity
    order_type: OrderType = OrderType.MARKET
) -> List[Order]:
    """Compute orders needed to move from current to target positions."""
    
    orders = []
    all_instruments = set(current_positions.keys()) | set(target_positions.keys())
    
    for instrument_id in all_instruments:
        current_qty = current_positions.get(instrument_id, Position(...)).quantity
        target_qty = target_positions.get(instrument_id, 0.0)
        delta = target_qty - current_qty
        
        if abs(delta) < MIN_ORDER_SIZE:
            continue
        
        side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        orders.append(Order(
            order_id=generate_order_id(),
            instrument_id=instrument_id,
            side=side,
            order_type=order_type,
            quantity=abs(delta)
        ))
    
    return orders
```

---

## 9. Storage and Logging

All execution activity is logged to `runtime_db` for audit and analysis.

### 9.1 Tables (extensions to 020)

**Table: `orders`**
- `order_id` (PK, text)
- `timestamp` (timestamptz)
- `instrument_id` (text)
- `side` (text: BUY/SELL)
- `order_type` (text: MARKET/LIMIT/STOP/STOP_LIMIT)
- `quantity` (numeric)
- `limit_price` (numeric, nullable)
- `stop_price` (numeric, nullable)
- `status` (text: PENDING/SUBMITTED/FILLED/CANCELLED/REJECTED)
- `mode` (text: LIVE/PAPER/BACKTEST)
- `portfolio_id` (text, nullable)
- `decision_id` (uuid, FK → engine_decisions, nullable)
- `metadata` (jsonb)

**Table: `fills`**
- `fill_id` (PK, text)
- `order_id` (FK → orders)
- `timestamp` (timestamptz)
- `instrument_id` (text)
- `side` (text)
- `quantity` (numeric)
- `price` (numeric)
- `commission` (numeric)
- `mode` (text: LIVE/PAPER/BACKTEST)
- `metadata` (jsonb)

**Table: `positions_snapshots`**
- `snapshot_id` (PK, bigserial)
- `portfolio_id` (text)
- `timestamp` (timestamptz)
- `as_of_date` (date)
- `instrument_id` (text)
- `quantity` (numeric)
- `avg_cost` (numeric)
- `market_value` (numeric)
- `unrealized_pnl` (numeric)
- `mode` (text)

These tables support both live trading and backtesting; `mode` field distinguishes them.

---

## 10. Integration with Portfolio & Risk Engine

Portfolio & Risk Engine (150) produces target positions via optimization.

**Workflow:**

1. Portfolio & Risk Engine calls its optimizer and generates `target_portfolios` entry in DB.
2. An orchestration task (DAG: `{market}_execution_{date}`) runs after portfolio optimization:
   - Reads current positions from `BrokerInterface.get_positions()`.
   - Reads target positions from `target_portfolios` table.
   - Calls `OrderPlanner.plan_orders()`.
   - Submits orders via `BrokerInterface.submit_order()`.
3. In LIVE/PAPER mode:
   - Orders go to IBKR Gateway.
   - Fills arrive asynchronously; logged to `fills` table.
4. In BACKTEST mode:
   - Orders processed by MarketSimulator at EOD.
   - Fills logged to backtest-specific tables or in-memory.

---

## 11. Backtesting Workflow

### 11.1 High-level flow

```python
# Initialize backtest environment
backtest = BacktestEnvironment(
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
    initial_cash=1_000_000,
    universe_ids=["EQUITY:AAPL", "EQUITY:MSFT", ...],
    config=BacktestConfig(...)
)

# Run backtest
for as_of_date in backtest.trading_days():
    # All engines operate at as_of_date
    regime_state = regime_engine.get_regime(as_of_date, region="US")
    stability = stability_engine.compute(as_of_date)
    scores = assessment_engine.score_universe(strategy_id, market_id, universe, as_of_date)
    universe = universe_engine.select(strategy_id, market_id, as_of_date)
    target_positions = portfolio_engine.optimize(strategy_id, as_of_date, universe, scores)
    
    # Execute orders
    orders = order_planner.plan_orders(backtest.broker.get_positions(), target_positions)
    for order in orders:
        backtest.broker.submit_order(order)
    
    # Process fills at EOD
    backtest.broker.process_fills(as_of_date)
    
    # Log performance
    backtest.log_snapshot(as_of_date)

# Analyze results
performance = backtest.get_performance_report()
```

### 11.2 TimeMachine guarantees

`TimeMachine` wraps data access to ensure no look-ahead:
- Intercepts calls to `historical_db` and filters by `date <= as_of_date`.
- Caches data per date to avoid redundant queries.
- In strict mode, raises exceptions if future data is requested.

---

## 12. IBKR Gateway Setup (Operational Notes)

### 12.1 Installation

- Download IBKR Gateway from Interactive Brokers website.
- Install on local machine or dedicated server.
- Configure to allow API connections (enable API in settings, set port).

### 12.2 Connection

```python
# Example using ib_insync
from ib_insync import IB

ib = IB()
ib.connect('127.0.0.1', 7496, clientId=1)  # live TWS
# or
ib.connect('127.0.0.1', 4001, clientId=1)  # paper trading

# Check connection
print(ib.accountSummary())
```

### 12.3 Security

- API connections limited to localhost by default.
- Use VPN or SSH tunnel if Gateway runs on remote server.
- Never expose Gateway ports to public internet.

---

## 13. Configuration per Mode

### 13.1 Live mode

```yaml
# configs/execution/live.yaml
mode: LIVE
broker:
  type: ibkr
  host: 127.0.0.1
  port: 7496
  client_id: 1
order_defaults:
  order_type: LIMIT
  limit_offset_bps: 10  # offset from mid for limit orders
risk_checks:
  max_order_size_usd: 100000
  max_portfolio_leverage: 2.0
```

### 13.2 Paper mode

```yaml
# configs/execution/paper.yaml
mode: PAPER
broker:
  type: ibkr
  host: 127.0.0.1
  port: 4001
  client_id: 1
# ... similar to live
```

### 13.3 Backtest mode

```yaml
# configs/execution/backtest.yaml
mode: BACKTEST
simulator:
  fill_model: realistic  # or simple
  slippage_bps: 5.0
  use_volume_constraints: true
  max_participation_rate: 0.10
time_machine:
  strict_mode: true  # raise exceptions on look-ahead attempts
```

---

## 14. Open Questions / Future Work

1. **Intraday execution**
   - Current design assumes EOD execution; extend to intraday by adding `as_of_time`.

2. **Multi-broker support**
   - Add adapters for other brokers (Alpaca, Tradier, etc.) as needed.

3. **Advanced order types**
   - Bracket orders, trailing stops, iceberg orders.

4. **Execution cost analysis**
   - Track slippage, market impact, and compare to pre-trade expectations.

5. **Execution algorithms**
   - VWAP, TWAP, POV (percentage of volume) execution strategies.

---

## 15. Summary

This spec defines:
- **Unified BrokerInterface** for LIVE, PAPER, and BACKTEST modes.
- **IBKR Gateway integration** for live and paper trading.
- **BacktestBroker + MarketSimulator** for realistic backtesting with time-travel data access.
- **Order planning and routing** from Portfolio & Risk to broker.
- **Comprehensive logging** to support audit, reconciliation, and Kronos analysis.

With this infrastructure, the same codebase powers both live trading and backtesting, ensuring that backtest results are representative of live performance.
