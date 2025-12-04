# IBKR Integration Deployment Guide

This guide covers the setup and deployment of the Prometheus IBKR integration for both paper and live trading.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [IB Gateway Installation](#ib-gateway-installation)
3. [Configuration](#configuration)
4. [Testing with Paper Trading](#testing-with-paper-trading)
5. [Live Trading Deployment](#live-trading-deployment)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Software Requirements

- Python 3.11+
- PostgreSQL database with Prometheus schema
- IB Gateway (recommended) or TWS (Trader Workstation)
- Active IBKR account (paper or live)

### Python Dependencies

The IBKR integration requires the `ib_insync` library:

```bash
poetry install  # Will install ib_insync>=0.9.86
```

### Database Setup

Ensure the `instruments` table is populated with S&P 500 constituents:

```bash
python -m prometheus.scripts.ingest_eodhd_sp500_instruments
```

## IB Gateway Installation

### Download IB Gateway

1. Visit: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
2. Download the appropriate version for your OS (Linux/Mac/Windows)
3. Install following the platform-specific instructions

### IB Gateway vs TWS

**IB Gateway (Recommended):**
- Lightweight, headless API gateway
- Lower resource usage
- More stable for automation
- Ports: 4001 (live), 4002 (paper)

**TWS (Trader Workstation):**
- Full trading interface with charts
- Higher resource usage
- Ports: 7496 (live), 7497 (paper)

### Gateway Configuration

1. Launch IB Gateway
2. Configure API settings:
   - **Enable ActiveX and Socket Clients**: ✓
   - **Socket port**: 4001 (live) or 4002 (paper)
   - **Master API client ID**: Leave empty
   - **Read-Only API**: ✗ (unchecked)
   - **Create API message log file**: ✓ (recommended for debugging)
   - **Include market data in API log file**: ✓ (if needed)
   - **Trusted IP addresses**: Add 127.0.0.1 (localhost)

3. Auto-restart settings (optional):
   - **Auto restart**: ✓
   - **Auto restart time**: 23:55 EST (avoids market hours)
   - **Auto logoff time**: Leave empty

## Configuration

### Environment Variables

Create a `.env` file or export these variables:

```bash
# Paper Trading (default values shown)
export IBKR_PAPER_USERNAME="xubtmn245"
export IBKR_PAPER_ACCOUNT="DUN807925"
export IBKR_PAPER_PASSWORD=""  # Optional if Gateway already logged in

# Live Trading
export IBKR_LIVE_USERNAME="maximilianhuethmayr"
export IBKR_LIVE_ACCOUNT="U22014992"
export IBKR_LIVE_PASSWORD=""  # Optional if Gateway already logged in

# Database connection (if not using defaults)
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_DB="prometheus"
export POSTGRES_USER="prometheus"
export POSTGRES_PASSWORD=""
```

### Port Configuration

The integration automatically selects ports based on mode and gateway type:

| Gateway Type | Mode  | Port |
|--------------|-------|------|
| Gateway      | Paper | 4002 |
| Gateway      | Live  | 4001 |
| TWS          | Paper | 7497 |
| TWS          | Live  | 7496 |

## Testing with Paper Trading

### 1. Start IB Gateway

```bash
# Linux example (adjust path as needed)
/opt/ibgateway/paper/ibgateway &

# Or use TWS
/opt/tws/paper/tws &
```

Log in with your paper trading credentials:
- Username: xubtmn245
- Account: DUN807925

### 2. Run Integration Test

```bash
python -m prometheus.scripts.test_ibkr_paper
```

This test will:
1. Connect to IB Gateway paper account
2. Load instruments from database
3. Retrieve account state and positions
4. Optionally submit a test order (1 share of AAPL)
5. Monitor for fills
6. Test connection health monitoring
7. Disconnect cleanly

### 3. Expected Output

```
================================================================================
IBKR Paper Trading Integration Test
================================================================================

[1] Creating PaperBroker...
✓ PaperBroker created: account=DUN807925, port=4002

[2] Connecting to IBKR paper account...
✓ Connected successfully

[3] Checking connection health...
Connection health: {'connected': True, 'ib_connected': True, ...}

[4] Retrieving account state...
Account equity: 1000000.00
Account cash: 995234.56

[5] Retrieving positions...
Current positions: 2
  AAPL.US: qty=10.00, avg_cost=175.50, market_value=1850.00, pnl=105.00
  TSLA.US: qty=5.00, avg_cost=245.00, market_value=1220.00, pnl=-5.00

[6] Testing order submission...
Ready to submit test order: BUY 1 share of AAPL.US at MARKET
This is PAPER TRADING - no real money will be used

Submit test order? [y/N]: y
✓ Order submitted successfully: abc123...

...
```

### 4. Verify Order in IB Portal

After submitting test orders, verify them in the IBKR Account Management portal:
https://ndcdyn.interactivebrokers.com/sso/Login?RL=1

Navigate to: Performance & Reports → Transaction History

## Live Trading Deployment

### ⚠️ IMPORTANT SAFETY NOTES

- **Start with paper trading** to validate all workflows
- **Test all risk controls** before enabling live trading
- **Set position limits** in your strategy configuration
- **Enable max order size checks** in OrderPlanner
- **Monitor the system actively** during initial live deployment
- **Use readonly mode** first to verify connectivity without order submission

### 1. Readonly Mode Testing (Recommended)

Before submitting live orders, test connectivity in readonly mode:

```python
from prometheus.execution.broker_factory import create_live_broker

# Create broker in readonly mode
broker = create_live_broker(readonly=True)
broker.client.connect()

# Test data retrieval (no order submission)
positions = broker.get_positions()
account = broker.get_account_state()
health = broker.client.get_connection_health()

print(f"Positions: {len(positions)}")
print(f"Account equity: {account.get('equity')}")
print(f"Connection: {health}")
```

### 2. Start IB Gateway for Live Trading

```bash
# Launch live IB Gateway
/opt/ibgateway/live/ibgateway &
```

Log in with your live trading credentials:
- Username: maximilianhuethmayr
- Account: U22014992

### 3. Configure Production Broker

```python
from prometheus.execution.broker_factory import create_live_broker

# Create live broker with auto-connect
broker = create_live_broker(
    gateway_type=IbkrGatewayType.GATEWAY,
    client_id=1,
    readonly=False,  # Enable order submission
    auto_connect=True,
)

# Broker is now ready for trading
```

### 4. Production Systemd Service

Create `/etc/systemd/system/prometheus-trading.service`:

```ini
[Unit]
Description=Prometheus Trading System
After=network.target postgresql.service ibgateway.service
Requires=postgresql.service

[Service]
Type=simple
User=prometheus
Group=prometheus
WorkingDirectory=/opt/prometheus
EnvironmentFile=/opt/prometheus/.env

# Live trading configuration
ExecStart=/opt/prometheus/venv/bin/python -m prometheus.engine.runner \
    --mode=live \
    --broker-type=live

# Auto-restart on failure with exponential backoff
Restart=on-failure
RestartSec=10s

# Resource limits
LimitNOFILE=65536
MemoryMax=8G

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=prometheus-trading

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable prometheus-trading
sudo systemctl start prometheus-trading
sudo systemctl status prometheus-trading
```

## Monitoring and Maintenance

### Health Checks

The IBKR client includes automatic health monitoring:

```python
# Check connection health
health = broker.client.get_connection_health()

# {
#   'connected': True,
#   'ib_connected': True,
#   'last_heartbeat': '2024-01-15T10:30:00Z',
#   'reconnect_attempts': 0,
#   'max_reconnect_attempts': 5
# }
```

### Auto-Reconnection

The client automatically reconnects on connection loss:
- **Heartbeat interval**: 60 seconds
- **Max reconnect attempts**: 5
- **Reconnect delay**: 10 seconds
- **Exponential backoff**: No (constant delay)

### Logging

All IBKR operations are logged via Prometheus logging:

```bash
# View logs
tail -f /var/log/prometheus/trading.log

# Search for IBKR events
grep "IBKR" /var/log/prometheus/trading.log

# Check for errors
grep "ERROR.*ibkr" /var/log/prometheus/trading.log
```

### IB Gateway Restarts

Configure IB Gateway to auto-restart daily at off-market hours:
- **Recommended time**: 23:55 EST (after market close)
- **Prometheus will auto-reconnect** after Gateway restart
- **Monitor reconnection logs** after scheduled restarts

## Troubleshooting

### Connection Issues

**Problem**: `Failed to connect to IBKR`

**Solutions**:
1. Verify IB Gateway is running: `ps aux | grep ibgateway`
2. Check port is correct (4001 for live, 4002 for paper)
3. Verify API settings in Gateway configuration
4. Check firewall allows localhost connections
5. Review Gateway logs: `~/.ibgateway/logs/`

### Authentication Errors

**Problem**: `Authentication failed` or `Invalid credentials`

**Solutions**:
1. Verify environment variables are set correctly
2. Log in to IBKR Account Management to verify account is active
3. Check if account is funded (required for live trading)
4. Ensure 2FA is configured if required by your account

### Order Rejection

**Problem**: Orders rejected with error codes

**Common IBKR Error Codes**:
- **200**: No security definition (instrument not found)
- **201**: Order rejected - Exchange closed
- **202**: Order cancelled - order size exceeds maximum
- **321**: Error validating request - contract not found
- **10147**: OrderId not found

**Solutions**:
1. Verify instrument exists in database
2. Check market hours for the security
3. Verify order size is within limits
4. Check contract qualification in logs

### Position Sync Issues

**Problem**: Positions don't match IB Portal

**Solutions**:
1. Call `broker.sync()` to force refresh
2. Check last_heartbeat timestamp
3. Verify account_id matches between env and IB Gateway
4. Review fill events in logs

### Performance Issues

**Problem**: Slow order submissions or timeouts

**Solutions**:
1. Check network latency: `ping 127.0.0.1`
2. Reduce heartbeat interval if too aggressive
3. Monitor IB Gateway CPU/memory usage
4. Consider using IB Gateway instead of TWS (lighter)

### Database Connection

**Problem**: `InstrumentMapper` fails to load instruments

**Solutions**:
1. Verify PostgreSQL is running
2. Check database credentials in environment
3. Ensure `instruments` table is populated
4. Run ingestion script: `python -m prometheus.scripts.ingest_eodhd_sp500_instruments`

## Support and Resources

### IBKR Resources

- API Documentation: https://ibkr.github.io/tws-api/
- ib_insync Documentation: https://ib-insync.readthedocs.io/
- IBKR API Forum: https://groups.io/g/twsapi

### Prometheus Resources

- Implementation: `prometheus/execution/ibkr_client_impl.py`
- Configuration: `prometheus/execution/ibkr_config.py`
- Factory: `prometheus/execution/broker_factory.py`
- Test Script: `prometheus/scripts/test_ibkr_paper.py`

### Getting Help

1. Check logs first: `/var/log/prometheus/`
2. Run integration test: `python -m prometheus.scripts.test_ibkr_paper`
3. Review IBKR Gateway logs: `~/.ibgateway/logs/`
4. Contact IBKR support for API issues: https://www.interactivebrokers.com/en/support/

---

**Last Updated**: 2024-01-15  
**Version**: 1.0.0  
**Author**: Prometheus v2 Team
