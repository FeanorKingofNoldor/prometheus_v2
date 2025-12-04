#!/bin/bash
# Prometheus v2 - Production Deployment Script
# Automated setup for Linux server with GUI

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Prometheus v2 - Production Deployment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}ERROR: Do not run as root. Run as normal user with sudo access.${NC}"
    exit 1
fi

# Get configuration
read -p "PostgreSQL password for prometheus user: " -s PG_PASSWORD
echo ""
read -p "API secret key (leave empty to generate): " SECRET_KEY
if [ -z "$SECRET_KEY" ]; then
    SECRET_KEY=$(openssl rand -hex 32)
    echo "Generated secret key: $SECRET_KEY"
fi
echo ""

read -p "Deploy to /opt/prometheus? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "Deployment cancelled."
    exit 0
fi

DEPLOY_DIR="/opt/prometheus/prometheus_v2"
LOG_DIR="/var/log/prometheus"
DATA_DIR="/var/lib/prometheus"

echo -e "${YELLOW}Starting deployment...${NC}"
echo ""

# 1. Create directories
echo -e "${YELLOW}[1/10] Creating directories...${NC}"
sudo mkdir -p $DEPLOY_DIR
sudo mkdir -p $LOG_DIR
sudo mkdir -p $DATA_DIR/{data,backups,cache}
sudo chown -R $USER:$USER $DEPLOY_DIR
sudo chown -R $USER:$USER $LOG_DIR
sudo chown -R $USER:$USER $DATA_DIR

# 2. Clone/copy project
echo -e "${YELLOW}[2/10] Setting up project files...${NC}"
if [ ! -d "$DEPLOY_DIR/.git" ]; then
    # Copy current directory
    rsync -av --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
        $(pwd)/ $DEPLOY_DIR/
else
    echo "Project already exists, pulling latest changes..."
    cd $DEPLOY_DIR
    git pull origin main || true
fi

cd $DEPLOY_DIR

# 3. Setup Python environment
echo -e "${YELLOW}[3/10] Setting up Python environment...${NC}"
if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e . -q
pip install gunicorn psycopg2-binary -q

# 4. Setup PostgreSQL databases
echo -e "${YELLOW}[4/10] Setting up databases...${NC}"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='prometheus_runtime'" | grep -q 1 || \
    sudo -u postgres createdb prometheus_runtime

sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='prometheus_historical'" | grep -q 1 || \
    sudo -u postgres createdb prometheus_historical

sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='prometheus'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER prometheus WITH PASSWORD '$PG_PASSWORD';"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE prometheus_runtime TO prometheus;" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE prometheus_historical TO prometheus;" || true

# 5. Create configuration
echo -e "${YELLOW}[5/10] Creating configuration...${NC}"
mkdir -p config
cat > config/production.env <<EOF
# Database
PGHOST=localhost
PGPORT=5432
PGUSER=prometheus
PGPASSWORD=$PG_PASSWORD
PGDATABASE_RUNTIME=prometheus_runtime
PGDATABASE_HISTORICAL=prometheus_historical

# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_RELOAD=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=$LOG_DIR/api.log

# Security
SECRET_KEY=$SECRET_KEY
ALLOWED_HOSTS=localhost,127.0.0.1

# Market Data
DATA_DIR=$DATA_DIR/data

# Backtest
BACKTEST_CACHE_DIR=$DATA_DIR/cache
BACKTEST_MAX_WORKERS=8
EOF

# 6. Apply migrations
echo -e "${YELLOW}[6/10] Applying database migrations...${NC}"
export PGHOST=localhost
export PGUSER=prometheus
export PGPASSWORD=$PG_PASSWORD
export PGDATABASE_RUNTIME=prometheus_runtime
export PGDATABASE_HISTORICAL=prometheus_historical

cd prometheus
python -m core.migrations.apply_all
cd ..

# 7. Create systemd services
echo -e "${YELLOW}[7/10] Creating systemd services...${NC}"
sudo tee /etc/systemd/system/prometheus-api.service > /dev/null <<EOF
[Unit]
Description=Prometheus v2 API Server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$DEPLOY_DIR
EnvironmentFile=$DEPLOY_DIR/config/production.env

ExecStart=$DEPLOY_DIR/.venv/bin/gunicorn \\
    --bind 0.0.0.0:8000 \\
    --workers 4 \\
    --worker-class uvicorn.workers.UvicornWorker \\
    --timeout 300 \\
    --access-logfile $LOG_DIR/api-access.log \\
    --error-logfile $LOG_DIR/api-error.log \\
    prometheus.monitoring.server:app

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 8. Configure log rotation
echo -e "${YELLOW}[8/10] Configuring log rotation...${NC}"
sudo tee /etc/logrotate.d/prometheus > /dev/null <<EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0640 $USER $USER
    sharedscripts
    postrotate
        systemctl reload prometheus-api.service > /dev/null 2>&1 || true
    endscript
}
EOF

# 9. Create backup script
echo -e "${YELLOW}[9/10] Creating backup script...${NC}"
mkdir -p scripts
cat > scripts/backup_databases.sh <<'EOF'
#!/bin/bash
BACKUP_DIR=/var/lib/prometheus/backups
DATE=$(date +%Y%m%d_%H%M%S)

# Runtime database
pg_dump -U prometheus -d prometheus_runtime \
    -F c -f $BACKUP_DIR/runtime_$DATE.backup

# Keep last 30 days
find $BACKUP_DIR -name "*.backup" -mtime +30 -delete

echo "Backup completed: $DATE"
EOF

chmod +x scripts/backup_databases.sh

# Add to crontab
(crontab -l 2>/dev/null | grep -v backup_databases.sh; echo "0 2 * * * $DEPLOY_DIR/scripts/backup_databases.sh >> $LOG_DIR/backup.log 2>&1") | crontab -

# 10. Enable and start services
echo -e "${YELLOW}[10/10] Starting services...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable prometheus-api.service
sudo systemctl restart prometheus-api.service

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Deployment Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check service status
sleep 2
if sudo systemctl is-active --quiet prometheus-api.service; then
    echo -e "${GREEN}✓ API server is running${NC}"
    echo "  URL: http://localhost:8000"
    echo "  Docs: http://localhost:8000/docs"
else
    echo -e "${RED}✗ API server failed to start${NC}"
    echo "  Check logs: sudo journalctl -u prometheus-api.service -n 50"
fi

echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Export Godot UI: cd prometheus_c2 && godot4 --export 'Linux/X11' ../prometheus_c2.x86_64"
echo "  2. Copy UI to server: scp prometheus_c2.x86_64 $USER@server:/opt/prometheus/"
echo "  3. Setup auto-start: create ~/.config/autostart/prometheus-ui.desktop"
echo "  4. Test connection: curl http://localhost:8000/api/status/overview"
echo "  5. Run first backtest via UI Terminal panel"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Project: $DEPLOY_DIR"
echo "  Logs: $LOG_DIR"
echo "  Data: $DATA_DIR"
echo "  Config: $DEPLOY_DIR/config/production.env"
echo ""
echo -e "${YELLOW}Service management:${NC}"
echo "  Start:   sudo systemctl start prometheus-api.service"
echo "  Stop:    sudo systemctl stop prometheus-api.service"
echo "  Restart: sudo systemctl restart prometheus-api.service"
echo "  Status:  sudo systemctl status prometheus-api.service"
echo "  Logs:    sudo journalctl -u prometheus-api.service -f"
echo ""
echo -e "${GREEN}Deployment successful!${NC}"
