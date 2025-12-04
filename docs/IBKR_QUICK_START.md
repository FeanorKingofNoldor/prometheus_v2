# IBKR Integration - Quick Start Guide

A 5-minute guide to get started with IBKR paper trading in Prometheus.

## Prerequisites

```bash
# Install dependencies
poetry install

# Ensure instruments are loaded
python -m prometheus.scripts.ingest_eodhd_sp500_instruments
```

## Paper Trading (Recommended for First Use)

### 1. Start IB Gateway

```bash
# Download and install IB Gateway from:
# https://www.interactivebrokers.com/en/trading/ibgateway-stable.php

# Launch IB Gateway for paper trading
# Log in with paper credentials (default: xubtmn245 / DUN807925)
```

### 2. Run Test Script

```bash
python -m prometheus.scripts.test_ibkr_paper
```

This will connect, retrieve account info, and optionally submit a test order.

### 3. Use in Code

```python
from prometheus.execution.broker_factory import create_paper_broker
from prometheus.execution.broker_interface import Order, OrderSide, OrderType
from prometheus.core.ids import generate_uuid

# Create and connect
broker = create_paper_broker(auto_connect=True)

# Get account state
account = broker.get_account_state()
print(f"Equity: {account.get('equity')}")

# Get positions
positions = broker.get_positions()
for instrument_id, position in positions.items():
    print(f"{instrument_id}: {position.quantity} shares")

# Submit order
order = Order(
    order_id=generate_uuid(),
    instrument_id="AAPL.US",
    side=OrderSide.BUY,
    order_type=OrderType.MARKET,
    quantity=1,
)

broker.submit_order(order)

# Get fills
fills = broker.get_fills()
print(f"Fills: {len(fills)}")

# Disconnect
broker.client.disconnect()
```

## Live Trading (Use with Caution)

### 1. Set Environment Variables

```bash
# Optional - defaults are provided
export IBKR_LIVE_USERNAME="maximilianhuethmayr"
export IBKR_LIVE_ACCOUNT="U22014992"
```

### 2. Start with Readonly Mode

```python
from prometheus.execution.broker_factory import create_live_broker

# Connect in readonly mode (no order submission)
broker = create_live_broker(readonly=True, auto_connect=True)

# Verify connection
health = broker.client.get_connection_health()
print(f"Connected: {health['connected']}")

# Check account
account = broker.get_account_state()
positions = broker.get_positions()
```

### 3. Enable Order Submission

```python
# Only after testing readonly mode!
broker = create_live_broker(readonly=False, auto_connect=True)

# Now you can submit orders
broker.submit_order(order)
```

## Common Patterns

### Connection Health Check

```python
health = broker.client.get_connection_health()

if health['connected']:
    print("✓ Connected")
    print(f"Last heartbeat: {health['last_heartbeat']}")
else:
    print("✗ Disconnected")
    print(f"Reconnect attempts: {health['reconnect_attempts']}")
```

### Sync Positions

```python
# Force refresh from IBKR
broker.sync()

# Get updated positions
positions = broker.get_positions()
```

### Error Handling

```python
try:
    broker.submit_order(order)
except RuntimeError as e:
    if "Not connected" in str(e):
        broker.client.connect()
        broker.submit_order(order)
    else:
        raise
```

## Configuration

### Environment Variables

```bash
# Paper Trading
IBKR_PAPER_USERNAME="xubtmn245"        # Default
IBKR_PAPER_ACCOUNT="DUN807925"         # Default
IBKR_PAPER_PASSWORD=""                 # Optional

# Live Trading  
IBKR_LIVE_USERNAME="maximilianhuethmayr"  # Default
IBKR_LIVE_ACCOUNT="U22014992"             # Default
IBKR_LIVE_PASSWORD=""                     # Optional
```

### Gateway Type

```python
from prometheus.execution.ibkr_config import IbkrGatewayType

# Use IB Gateway (recommended)
broker = create_paper_broker(
    gateway_type=IbkrGatewayType.GATEWAY,  # Port 4002
)

# Or use TWS
broker = create_paper_broker(
    gateway_type=IbkrGatewayType.TWS,  # Port 7497
)
```

## Troubleshooting

### Connection Failed

```bash
# Check Gateway is running
ps aux | grep ibgateway

# Check port
netstat -an | grep 4002  # Paper Gateway
netstat -an | grep 4001  # Live Gateway

# Review logs
tail -f ~/.ibgateway/logs/ibgateway.*.log
```

### Instrument Not Found

```bash
# Load instruments
python -m prometheus.scripts.ingest_eodhd_sp500_instruments

# Or check in Python
from prometheus.execution.instrument_mapper import get_instrument_mapper

mapper = get_instrument_mapper()
mapper.load_instruments()
print(f"Loaded: {mapper.get_instrument_count()} instruments")

# Check specific instrument
metadata = mapper.get_metadata("AAPL.US")
print(metadata)
```

### Order Rejected

Common reasons:
- Market closed → Check trading hours
- Invalid instrument → Verify in database
- Contract not found → Check symbol/exchange
- Insufficient funds → Check account balance

## Next Steps

- Read full deployment guide: `docs/IBKR_DEPLOYMENT.md`
- Review implementation: `prometheus/execution/ibkr_client_impl.py`
- See all features: `docs/IBKR_INTEGRATION_SUMMARY.md`

## Safety Reminders

✅ **Always test with paper trading first**  
✅ **Use readonly mode to verify connectivity**  
✅ **Start with small order sizes**  
✅ **Monitor connection health**  
✅ **Set position limits in your strategy**

---

**Questions?** Check `docs/IBKR_DEPLOYMENT.md` for comprehensive documentation.
