#!/bin/bash
# Prometheus v2 System Startup Script
# Starts backend API server and provides instructions for UI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Prometheus v2 - Quantitative Trading System${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: Must run from prometheus_v2 directory${NC}"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
else
    source .venv/bin/activate
fi

# Check database connection
echo -e "${YELLOW}Checking database connection...${NC}"
python -c "from prometheus.core.database import get_db_manager; db = get_db_manager(); print('✓ Database OK')" || {
    echo -e "${RED}✗ Database connection failed${NC}"
    echo -e "${YELLOW}Make sure PostgreSQL is running and databases exist:${NC}"
    echo "  - prometheus_runtime"
    echo "  - prometheus_historical"
    exit 1
}

# Check if migrations are applied
echo -e "${YELLOW}Checking database migrations...${NC}"
python -c "from prometheus.core.database import get_db_manager; db = get_db_manager(); conn = db.get_runtime_connection(); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM regimes'); print('✓ Migrations OK')" || {
    echo -e "${RED}✗ Migrations not applied${NC}"
    echo -e "${YELLOW}Run migrations:${NC}"
    echo "  cd prometheus && python -m core.migrations.apply_all"
    exit 1
}

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Start backend server
echo -e "${BLUE}Starting backend API server...${NC}"
echo -e "${YELLOW}API will be available at: http://localhost:8000${NC}"
echo -e "${YELLOW}API docs: http://localhost:8000/docs${NC}"
echo ""

# Check if port 8000 is already in use
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}Warning: Port 8000 already in use${NC}"
    echo -e "${YELLOW}Kill existing process? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        lsof -ti:8000 | xargs kill -9
        echo -e "${GREEN}✓ Killed existing process${NC}"
    else
        echo -e "${RED}Exiting${NC}"
        exit 1
    fi
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Backend Server Starting${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""
echo -e "${GREEN}To launch the UI:${NC}"
echo "  1. Open Godot 4"
echo "  2. Import project: $(pwd)/prometheus_c2"
echo "  3. Run MainShell.tscn"
echo ""
echo -e "${GREEN}To run your first backtest:${NC}"
echo "  1. Open Terminal panel in UI"
echo "  2. Run: backtest run US_CORE_LONG_EQ 2023-01-01 2024-01-01 US_EQ"
echo "  3. Wait for completion (~5-30 minutes depending on data)"
echo "  4. Refresh panels to see data"
echo ""

# Start uvicorn server
cd prometheus
exec uvicorn monitoring.server:app --host 0.0.0.0 --port 8000 --reload
