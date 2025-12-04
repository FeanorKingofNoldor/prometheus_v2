# Prometheus v2 - Production Deployment Guide

## Overview

This guide covers deploying Prometheus v2 on a Linux server with GUI for production use. The deployment includes:
- Backend FastAPI services
- PostgreSQL databases
- Godot C2 UI (desktop application)
- Monitoring and logging
- Automated startup
- Backup and recovery

## Server Requirements

### Hardware
- **CPU**: 16+ cores recommended (for parallel backtest execution)
- **RAM**: 32GB+ recommended (16GB minimum)
- **Storage**: 500GB+ SSD (database + market data)
- **GPU**: Optional (for future 3D ANT_HILL rendering)

### Operating System
- **Distribution**: Ubuntu 22.04 LTS or Debian 12 (recommended)
- **Display Server**: X11 or Wayland (for GUI)
- **Desktop Environment**: GNOME, KDE, or XFCE (lightweight)

### Software Stack
- **Python**: 3.11+
- **PostgreSQL**: 15+
- **Godot**: 4.2+ (runtime for UI)
- **Nginx**: For reverse proxy (optional)
- **Systemd**: For service management

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LINUX SERVER                              │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  GUI Session (X11/Wayland)                         │    │
│  │  • Godot C2 UI (desktop app)                       │    │
│  │  • Auto-start on login                             │    │
│  │  • Full screen or windowed                         │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼ HTTP (localhost:8000)            │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Backend Services (systemd)                        │    │
│  │  • prometheus-api.service (FastAPI)                │    │
│  │  • prometheus-worker.service (backtest executor)   │    │
│  │  • prometheus-scheduler.service (DAG orchestrator) │    │
│  └────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼ PostgreSQL                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Databases                                         │    │
│  │  • prometheus_runtime (operational data)           │    │
│  │  • prometheus_historical (market data)             │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Deployment Steps

### 1. Server Setup

#### Install Base System
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    build-essential \
    git \
    curl \
    wget \
    vim \
    htop \
    tmux \
    postgresql-15 \
    postgresql-contrib \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nginx \
    certbot \
    lsof \
    net-tools

# Install Godot 4 (for UI runtime)
wget https://github.com/godotengine/godot/releases/download/4.2.2-stable/Godot_v4.2.2-stable_linux.x86_64.zip
unzip Godot_v4.2.2-stable_linux.x86_64.zip
sudo mv Godot_v4.2.2-stable_linux.x86_64 /usr/local/bin/godot
sudo chmod +x /usr/local/bin/godot
```

### 2. User and Directory Setup

```bash
# Create prometheus user
sudo useradd -m -s /bin/bash prometheus
sudo usermod -aG sudo prometheus

# Create directory structure
sudo mkdir -p /opt/prometheus
sudo mkdir -p /var/log/prometheus
sudo mkdir -p /var/lib/prometheus/{data,backups}
sudo chown -R prometheus:prometheus /opt/prometheus
sudo chown -R prometheus:prometheus /var/log/prometheus
sudo chown -R prometheus:prometheus /var/lib/prometheus

# Switch to prometheus user
sudo su - prometheus
```

### 3. Clone and Setup Project

```bash
# Clone repository
cd /opt/prometheus
git clone <your-repo-url> prometheus_v2
cd prometheus_v2

# Create Python virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -e .

# Install additional production packages
pip install gunicorn supervisor psycopg2-binary
```

### 4. Database Setup

```bash
# Switch to postgres user
sudo su - postgres

# Create databases
createdb prometheus_runtime
createdb prometheus_historical

# Create prometheus database user
psql -c "CREATE USER prometheus WITH PASSWORD 'YOUR_SECURE_PASSWORD';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE prometheus_runtime TO prometheus;"
psql -c "GRANT ALL PRIVILEGES ON DATABASE prometheus_historical TO prometheus;"

# Exit postgres user
exit
```

#### Configure PostgreSQL for Production

Edit `/etc/postgresql/15/main/postgresql.conf`:
```ini
# Memory settings (adjust based on your RAM)
shared_buffers = 8GB
effective_cache_size = 24GB
work_mem = 64MB
maintenance_work_mem = 2GB

# Performance
max_connections = 200
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1  # For SSD

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_min_duration_statement = 1000  # Log slow queries (>1s)
```

Edit `/etc/postgresql/15/main/pg_hba.conf`:
```
# Add local connections
local   prometheus_runtime    prometheus                    md5
local   prometheus_historical prometheus                    md5
host    prometheus_runtime    prometheus    127.0.0.1/32   md5
host    prometheus_historical prometheus    127.0.0.1/32   md5
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

### 5. Apply Database Migrations

```bash
cd /opt/prometheus/prometheus_v2

# Set environment variables
export PGHOST=localhost
export PGUSER=prometheus
export PGPASSWORD='YOUR_SECURE_PASSWORD'
export PGDATABASE_RUNTIME=prometheus_runtime
export PGDATABASE_HISTORICAL=prometheus_historical

# Apply migrations
cd prometheus
python -m core.migrations.apply_all

# Verify
psql -U prometheus -d prometheus_runtime -c "\dt"
```

### 6. Configuration Files

#### Create Production Config
Create `/opt/prometheus/prometheus_v2/config/production.env`:
```bash
# Database
PGHOST=localhost
PGPORT=5432
PGUSER=prometheus
PGPASSWORD=YOUR_SECURE_PASSWORD
PGDATABASE_RUNTIME=prometheus_runtime
PGDATABASE_HISTORICAL=prometheus_historical

# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_RELOAD=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/prometheus/api.log

# Security
SECRET_KEY=YOUR_SECRET_KEY_HERE
ALLOWED_HOSTS=localhost,127.0.0.1

# Market Data
DATA_DIR=/var/lib/prometheus/data

# Backtest
BACKTEST_CACHE_DIR=/var/lib/prometheus/data/cache
BACKTEST_MAX_WORKERS=8
```

#### Create Systemd Service Files

**API Service**: `/etc/systemd/system/prometheus-api.service`
```ini
[Unit]
Description=Prometheus v2 API Server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=prometheus
Group=prometheus
WorkingDirectory=/opt/prometheus/prometheus_v2
EnvironmentFile=/opt/prometheus/prometheus_v2/config/production.env

ExecStart=/opt/prometheus/prometheus_v2/.venv/bin/gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 300 \
    --access-logfile /var/log/prometheus/api-access.log \
    --error-logfile /var/log/prometheus/api-error.log \
    prometheus.monitoring.server:app

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Worker Service** (for background jobs): `/etc/systemd/system/prometheus-worker.service`
```ini
[Unit]
Description=Prometheus v2 Background Worker
After=network.target postgresql.service prometheus-api.service
Requires=postgresql.service

[Service]
Type=simple
User=prometheus
Group=prometheus
WorkingDirectory=/opt/prometheus/prometheus_v2
EnvironmentFile=/opt/prometheus/prometheus_v2/config/production.env

# Placeholder for future worker implementation
ExecStart=/opt/prometheus/prometheus_v2/.venv/bin/python \
    -m prometheus.orchestration.worker

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable prometheus-api.service
sudo systemctl start prometheus-api.service
sudo systemctl status prometheus-api.service

# Worker service (when implemented)
# sudo systemctl enable prometheus-worker.service
# sudo systemctl start prometheus-worker.service
```

### 7. Nginx Reverse Proxy (Optional)

If you want to expose the API externally:

Create `/etc/nginx/sites-available/prometheus`:
```nginx
upstream prometheus_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name prometheus.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name prometheus.yourdomain.com;

    # SSL certificates (use certbot)
    ssl_certificate /etc/letsencrypt/live/prometheus.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/prometheus.yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/prometheus-access.log;
    error_log /var/log/nginx/prometheus-error.log;

    # Proxy settings
    location / {
        proxy_pass http://prometheus_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts for long-running requests
        proxy_read_timeout 600s;
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

Enable and restart nginx:
```bash
sudo ln -s /etc/nginx/sites-available/prometheus /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Get SSL certificate (if external access needed)
sudo certbot --nginx -d prometheus.yourdomain.com
```

### 8. Godot UI Deployment

#### Export Godot Project
On your development machine:
```bash
# Open Godot Editor
cd /home/feanor/coding_projects/prometheus_v2/prometheus_c2
godot4 project.godot

# In Godot Editor:
# Project → Export → Linux/X11
# Export PCK/ZIP: OFF
# Export as: prometheus_c2.x86_64

# This creates a standalone executable
```

#### Deploy UI to Server
```bash
# Copy executable to server
scp prometheus_c2.x86_64 prometheus@your-server:/opt/prometheus/

# On server, make executable
ssh prometheus@your-server
cd /opt/prometheus
chmod +x prometheus_c2.x86_64

# Test run
./prometheus_c2.x86_64
```

#### Auto-Start UI on Login

Create desktop entry: `~/.config/autostart/prometheus-ui.desktop`
```ini
[Desktop Entry]
Type=Application
Name=Prometheus C2 UI
Exec=/opt/prometheus/prometheus_c2.x86_64
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
```

Or use systemd user service: `~/.config/systemd/user/prometheus-ui.service`
```ini
[Unit]
Description=Prometheus C2 UI
After=graphical.target

[Service]
Type=simple
ExecStart=/opt/prometheus/prometheus_c2.x86_64
Restart=always
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
```

Enable:
```bash
systemctl --user daemon-reload
systemctl --user enable prometheus-ui.service
systemctl --user start prometheus-ui.service
```

### 9. Logging and Monitoring

#### Configure Log Rotation

Create `/etc/logrotate.d/prometheus`:
```
/var/log/prometheus/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0640 prometheus prometheus
    sharedscripts
    postrotate
        systemctl reload prometheus-api.service > /dev/null 2>&1 || true
    endscript
}
```

#### System Monitoring

Install monitoring tools:
```bash
sudo apt install -y prometheus-node-exporter grafana

# Configure Grafana (optional)
sudo systemctl enable grafana-server
sudo systemctl start grafana-server
```

### 10. Backup Strategy

#### Database Backups

Create backup script: `/opt/prometheus/scripts/backup_databases.sh`
```bash
#!/bin/bash
BACKUP_DIR=/var/lib/prometheus/backups
DATE=$(date +%Y%m%d_%H%M%S)

# Runtime database
pg_dump -U prometheus -d prometheus_runtime \
    -F c -f $BACKUP_DIR/runtime_$DATE.backup

# Historical database (optional - large)
# pg_dump -U prometheus -d prometheus_historical \
#     -F c -f $BACKUP_DIR/historical_$DATE.backup

# Keep last 30 days
find $BACKUP_DIR -name "*.backup" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Add to crontab:
```bash
crontab -e

# Daily backup at 2 AM
0 2 * * * /opt/prometheus/scripts/backup_databases.sh >> /var/log/prometheus/backup.log 2>&1
```

#### Code Backups
```bash
# Git repository
cd /opt/prometheus/prometheus_v2
git remote add backup user@backup-server:/backups/prometheus.git

# Daily push
0 3 * * * cd /opt/prometheus/prometheus_v2 && git push backup main
```

### 11. Security Hardening

#### Firewall Configuration
```bash
# Install UFW
sudo apt install -y ufw

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow ssh

# Allow internal API (only if needed externally)
# sudo ufw allow 8000/tcp

# Allow Nginx (if using)
# sudo ufw allow 'Nginx Full'

# Enable firewall
sudo ufw enable
```

#### PostgreSQL Security
```bash
# Restrict PostgreSQL to local connections only
sudo vim /etc/postgresql/15/main/postgresql.conf
# Set: listen_addresses = 'localhost'

sudo systemctl restart postgresql
```

#### API Security
Edit `config/production.env`:
```bash
# Use strong secret key
SECRET_KEY=$(openssl rand -hex 32)

# Restrict allowed hosts
ALLOWED_HOSTS=localhost,127.0.0.1

# Enable authentication (when implemented)
AUTH_ENABLED=true
```

### 12. Performance Tuning

#### Python/Gunicorn
```bash
# Workers = (2 x CPU cores) + 1
# For 16 core server: 33 workers
# But cap at reasonable limit

API_WORKERS=16  # Adjust in production.env
```

#### PostgreSQL
See Section 4 for memory settings. Adjust based on your RAM:
- **32GB RAM**: shared_buffers=8GB, effective_cache_size=24GB
- **64GB RAM**: shared_buffers=16GB, effective_cache_size=48GB
- **128GB RAM**: shared_buffers=32GB, effective_cache_size=96GB

### 13. Health Checks

Create health check script: `/opt/prometheus/scripts/health_check.sh`
```bash
#!/bin/bash

# Check API server
curl -f http://localhost:8000/docs > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "API server is down!"
    systemctl restart prometheus-api.service
fi

# Check PostgreSQL
pg_isready -h localhost -U prometheus > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "PostgreSQL is down!"
    systemctl restart postgresql
fi

# Check disk space
DISK_USAGE=$(df -h /var/lib/prometheus | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "Disk usage is at ${DISK_USAGE}%"
fi
```

Add to crontab:
```bash
*/5 * * * * /opt/prometheus/scripts/health_check.sh >> /var/log/prometheus/health.log 2>&1
```

### 14. Deployment Checklist

- [ ] Server provisioned with sufficient resources
- [ ] Operating system installed and updated
- [ ] PostgreSQL installed and configured
- [ ] Databases created and migrations applied
- [ ] Python environment set up
- [ ] Backend services configured and running
- [ ] Godot UI exported and deployed
- [ ] Auto-start configured
- [ ] Logging configured
- [ ] Backup strategy implemented
- [ ] Firewall configured
- [ ] Health checks in place
- [ ] Documentation updated
- [ ] Team trained on operations

### 15. Operations

#### 15.1 Daily execution service (IBKR bridge)

Once you are comfortable with paper trading via
`run_execution_for_portfolio`, you can automate daily execution with a
systemd service + timer.

Template unit files are provided under `deploy/systemd/`:

- `deploy/systemd/prometheus-execution.service`
- `deploy/systemd/prometheus-execution.timer`

The service runs the existing CLI:

```bash
/opt/prometheus/prometheus_v2/.venv/bin/python \
  -m prometheus.scripts.run_execution_for_portfolio \
  --portfolio-id US_CORE_LONG_EQ \
  --mode PAPER \
  --notional 10000
```

Key points:

- `portfolio-id` should match your live/paper portfolio/book id.
- `mode` should be `PAPER` until you are ready for live trading.
- If `--as-of` is omitted, the script uses the latest `target_portfolios`
  row for the portfolio, so you can run it once per day after BOOKS.
- Configure IBKR and execution risk env in `production.env`:

  ```bash
  # IBKR paper/live
  IBKR_PAPER_USERNAME=...
  IBKR_PAPER_ACCOUNT=...
  IBKR_LIVE_USERNAME=...
  IBKR_LIVE_ACCOUNT=...

  # Software execution risk wrapper
  EXEC_RISK_ENABLED=true
  EXEC_RISK_MAX_ORDER_NOTIONAL=5000
  EXEC_RISK_MAX_POSITION_NOTIONAL=15000
  EXEC_RISK_MAX_LEVERAGE=1.5
  ```

Enable and start the timer on the server:

```bash
sudo cp deploy/systemd/prometheus-execution.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable prometheus-execution.timer
sudo systemctl start prometheus-execution.timer
sudo systemctl status prometheus-execution.timer
```

Use the existing operator CLIs to verify behaviour:

```bash
# Check limits
python -m prometheus.scripts.show_execution_risk

# Inspect orders/fills/positions
python -m prometheus.scripts.show_execution_status \
  --portfolio-id US_CORE_LONG_EQ \
  --mode PAPER
```

To perform a "kill switch" style stop for new orders at the software
layer, set `EXEC_RISK_ENABLED=false` in `production.env`, reload the env
(if you use a wrapper), and restart the execution service or any daemon
that creates brokers. New brokers will then bypass the
`RiskCheckingBroker` wrapper entirely.

### 15.2 Starting System

#### Starting System
```bash
# Start all services
sudo systemctl start postgresql
sudo systemctl start prometheus-api.service
# sudo systemctl start prometheus-worker.service  # When implemented

# Start UI (if not auto-started)
/opt/prometheus/prometheus_c2.x86_64 &
```

#### Stopping System
```bash
# Stop services
sudo systemctl stop prometheus-api.service
# sudo systemctl stop prometheus-worker.service

# Stop UI
pkill prometheus_c2
```

#### Restarting Services
```bash
# Restart API (for code updates)
sudo systemctl restart prometheus-api.service

# Reload API (graceful)
sudo systemctl reload prometheus-api.service
```

#### Viewing Logs
```bash
# API logs
sudo journalctl -u prometheus-api.service -f

# Application logs
tail -f /var/log/prometheus/api.log

# PostgreSQL logs
tail -f /var/log/postgresql/postgresql-*.log
```

#### Updating Code
```bash
cd /opt/prometheus/prometheus_v2

# Pull latest changes
git pull origin main

# Activate venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Apply migrations (if any)
cd prometheus
python -m core.migrations.apply_all

# Restart services
sudo systemctl restart prometheus-api.service
```

## Quick Start Guide (Production)

```bash
# 1. Clone and setup
git clone <repo> /opt/prometheus/prometheus_v2
cd /opt/prometheus/prometheus_v2
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. Setup databases
sudo -u postgres createdb prometheus_runtime
sudo -u postgres createdb prometheus_historical
cd prometheus && python -m core.migrations.apply_all

# 3. Configure environment
cp config/production.env.example config/production.env
vim config/production.env  # Edit passwords

# 4. Install services
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable prometheus-api.service
sudo systemctl start prometheus-api.service

# 5. Deploy UI
./deploy_ui.sh  # Exports and installs UI

# 6. Verify
curl http://localhost:8000/docs
./prometheus_c2.x86_64
```

## Troubleshooting

### API Server Won't Start
```bash
# Check logs
sudo journalctl -u prometheus-api.service -n 50

# Check port
sudo lsof -i :8000

# Check database connection
psql -U prometheus -d prometheus_runtime -c "SELECT 1;"
```

### UI Won't Connect
```bash
# Verify API is running
curl http://localhost:8000/api/status/overview

# Check firewall
sudo ufw status

# Check API logs for errors
tail -f /var/log/prometheus/api.log
```

### Database Performance Issues
```bash
# Check slow queries
sudo -u postgres psql -d prometheus_runtime -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;"

# Analyze tables
sudo -u postgres psql -d prometheus_runtime -c "
ANALYZE VERBOSE;"

# Reindex
sudo -u postgres psql -d prometheus_runtime -c "
REINDEX DATABASE prometheus_runtime;"
```

## Next Steps

- [ ] Set up external monitoring (Grafana/Prometheus)
- [ ] Implement alerting (email/Slack on errors)
- [ ] Configure remote backup to S3/cloud
- [ ] Set up staging environment
- [ ] Document runbooks for common issues
- [ ] Train team on operational procedures

---

**Production deployment complete!** Your Prometheus v2 system is now running reliably on your Linux server with full monitoring and UI capabilities.
