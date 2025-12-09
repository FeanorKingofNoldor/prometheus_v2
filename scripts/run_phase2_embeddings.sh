#!/bin/bash
# Phase 2: Comprehensive Embedding Backfill Orchestration
# This script coordinates all embedding generation for 2014-2024 with progress tracking

set -e  # Exit on error

# Configuration
START_DATE="2014-01-01"
END_DATE="2024-12-31"
BATCH_SIZE=64
LOG_DIR="logs/phase2"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create log directory
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1" | tee -a "$LOG_DIR/phase2_${TIMESTAMP}.log"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $1" | tee -a "$LOG_DIR/phase2_${TIMESTAMP}.log"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $1" | tee -a "$LOG_DIR/phase2_${TIMESTAMP}.log"
}

log_section() {
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo "" | tee -a "$LOG_DIR/phase2_${TIMESTAMP}.log"
}

# Check prerequisites
check_prerequisites() {
    log_section "Phase 2: Checking Prerequisites"
    
    # Check virtualenv is activated
    if [ -z "$VIRTUAL_ENV" ]; then
        log_error "Virtualenv not activated. Run: source venv/bin/activate"
        exit 1
    fi
    log_success "Virtualenv activated: $VIRTUAL_ENV"
    
    # Check database connectivity
    if ! python -c "from prometheus.core.database import get_db_manager; get_db_manager()" 2>/dev/null; then
        log_error "Cannot connect to databases. Check .env configuration"
        exit 1
    fi
    log_success "Database connectivity verified"
    
    # Check GPU availability (optional)
    if python -c "import torch; print(torch.cuda.is_available())" 2>/dev/null | grep -q "True"; then
        GPU_INFO=$(python -c "import torch; print(torch.cuda.get_device_name(0))" 2>/dev/null)
        log_success "GPU available: $GPU_INFO"
        DEVICE="cuda"
    else
        log "No GPU detected, will use CPU (slower)"
        DEVICE="cpu"
    fi
    
    echo ""
}

# Phase 2.1: Text Embeddings
run_text_embeddings() {
    log_section "Phase 2.1: Text Embeddings (News Articles)"
    log "Model: text-fin-general-v1 (384-dim)"
    log "Date range: $START_DATE to $END_DATE"
    log "Device: $DEVICE"
    
    START_TIME=$(date +%s)
    
    python -m prometheus.scripts.backfill_text_embeddings \
        --date-range "$START_DATE" "$END_DATE" \
        --model-id text-fin-general-v1 \
        --hf-model-name sentence-transformers/all-MiniLM-L6-v2 \
        --batch-size $BATCH_SIZE \
        --device $DEVICE \
        2>&1 | tee -a "$LOG_DIR/text_embeddings_${TIMESTAMP}.log"
    
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Text embeddings completed in ${ELAPSED}s"
    else
        log_error "Text embeddings failed with exit code $EXIT_CODE"
        return $EXIT_CODE
    fi
}

# Phase 2.2: Numeric Window Embeddings
run_numeric_embeddings() {
    log_section "Phase 2.2: Numeric Window Embeddings"
    log "Models: num-regime-core-v1, num-stab-core-v1, num-profile-core-v1"
    log "Date range: $START_DATE to $END_DATE"
    log "Window: 63 trading days"
    
    START_TIME=$(date +%s)
    
    python -m prometheus.scripts.backfill_numeric_embeddings_comprehensive \
        --date-range "$START_DATE" "$END_DATE" \
        --market-id US_EQ \
        --window-days 63 \
        --skip-existing \
        2>&1 | tee -a "$LOG_DIR/numeric_embeddings_${TIMESTAMP}.log"
    
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Numeric embeddings completed in ${ELAPSED}s"
    else
        log_error "Numeric embeddings failed with exit code $EXIT_CODE"
        return $EXIT_CODE
    fi
}

# Phase 2.4: Joint Profile Embeddings
run_joint_profiles() {
    log_section "Phase 2.4: Joint Profile Embeddings"
    log "Model: joint-profile-core-v1"
    log "Combining: numeric profile + text profile"
    
    START_TIME=$(date +%s)
    
    python -m prometheus.scripts.backfill_joint_profiles \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --market-id US_EQ \
        --profile-model-id num-profile-core-v1 \
        --text-model-id text-profile-v1 \
        --joint-model-id joint-profile-core-v1 \
        2>&1 | tee -a "$LOG_DIR/joint_profiles_${TIMESTAMP}.log"
    
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Joint profile embeddings completed in ${ELAPSED}s"
    else
        log_error "Joint profile embeddings failed with exit code $EXIT_CODE"
        return $EXIT_CODE
    fi
}

# Phase 2.5: Joint Regime Context Embeddings
run_joint_regime_context() {
    log_section "Phase 2.5: Joint Regime Context Embeddings"
    log "Model: joint-regime-core-v1"
    log "Proxy instrument: SPY.US"
    
    START_TIME=$(date +%s)
    
    python -m prometheus.scripts.backfill_joint_regime_context \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --region US \
        --instrument-id SPY.US \
        --regime-model-id num-regime-core-v1 \
        --text-model-id text-fin-general-v1 \
        --joint-model-id joint-regime-core-v1 \
        --text-window-days 7 \
        2>&1 | tee -a "$LOG_DIR/joint_regime_${TIMESTAMP}.log"
    
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Joint regime context completed in ${ELAPSED}s"
    else
        log_error "Joint regime context failed with exit code $EXIT_CODE"
        return $EXIT_CODE
    fi
}

# Phase 2.6: Joint Stability/Fragility Embeddings
run_joint_stab_fragility() {
    log_section "Phase 2.6: Joint Stability/Fragility Embeddings"
    log "Model: joint-stab-fragility-v1"
    
    START_TIME=$(date +%s)
    
    python -m prometheus.scripts.backfill_joint_stab_fragility_states \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --market-id US_EQ \
        --stab-model-id num-stab-core-v1 \
        --joint-model-id joint-stab-fragility-v1 \
        2>&1 | tee -a "$LOG_DIR/joint_stab_${TIMESTAMP}.log"
    
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Joint stability/fragility completed in ${ELAPSED}s"
    else
        log_error "Joint stability/fragility failed with exit code $EXIT_CODE"
        return $EXIT_CODE
    fi
}

# Phase 2.7: Joint Assessment Context Embeddings
run_joint_assessment_context() {
    log_section "Phase 2.7: Joint Assessment Context Embeddings"
    log "Model: joint-assessment-context-v1"
    log "This is the master embedding for assessment scoring"
    
    START_TIME=$(date +%s)
    
    python -m prometheus.scripts.backfill_joint_assessment_context \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --market-id US_EQ \
        --region US \
        --profile-joint-model-id joint-profile-core-v1 \
        --regime-joint-model-id joint-regime-core-v1 \
        --stab-joint-model-id joint-stab-fragility-v1 \
        --text-model-id text-fin-general-v1 \
        --text-window-days 7 \
        --joint-model-id joint-assessment-context-v1 \
        2>&1 | tee -a "$LOG_DIR/joint_assessment_${TIMESTAMP}.log"
    
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Joint assessment context completed in ${ELAPSED}s"
    else
        log_error "Joint assessment context failed with exit code $EXIT_CODE"
        return $EXIT_CODE
    fi
}

# Summary report
generate_summary() {
    log_section "Phase 2: Embedding Backfill Summary"
    
    # Query database for counts
    python << 'EOF'
from prometheus.core.database import get_db_manager

dm = get_db_manager()

with dm.get_historical_connection() as conn:
    cur = conn.cursor()
    
    # Text embeddings
    cur.execute("SELECT COUNT(*) FROM text_embeddings WHERE model_id = 'text-fin-general-v1'")
    text_count = cur.fetchone()[0]
    
    # Numeric embeddings
    cur.execute("SELECT model_id, COUNT(*) FROM numeric_window_embeddings GROUP BY model_id ORDER BY model_id")
    numeric_counts = cur.fetchall()
    
    # Joint embeddings
    cur.execute("SELECT joint_type, COUNT(*) FROM joint_embeddings GROUP BY joint_type ORDER BY joint_type")
    joint_counts = cur.fetchall()
    
    cur.close()

print(f"Text embeddings:     {text_count:>10,}")
print()
print("Numeric embeddings:")
for model_id, count in numeric_counts:
    print(f"  {model_id:30} {count:>10,}")
print()
print("Joint embeddings:")
for joint_type, count in joint_counts:
    print(f"  {joint_type:30} {count:>10,}")
EOF
}

# Main execution
main() {
    PHASE2_START=$(date +%s)
    
    log_section "Phase 2: Encoder Embeddings Backfill"
    log "Start time: $(date)"
    log "Date range: $START_DATE to $END_DATE"
    log "Logs: $LOG_DIR/"
    
    check_prerequisites
    
    # Run each phase
    # Note: Phases 2.1 and 2.2 can be run in parallel if desired
    # For now, running sequentially for simplicity
    
    run_text_embeddings || exit 1
    run_numeric_embeddings || exit 1
    
    # Joint embeddings depend on base embeddings being complete
    run_joint_profiles || exit 1
    run_joint_regime_context || exit 1
    run_joint_stab_fragility || exit 1
    run_joint_assessment_context || exit 1
    
    PHASE2_END=$(date +%s)
    TOTAL_ELAPSED=$((PHASE2_END - PHASE2_START))
    HOURS=$((TOTAL_ELAPSED / 3600))
    MINUTES=$(((TOTAL_ELAPSED % 3600) / 60))
    
    log_section "Phase 2: Complete"
    log "Total time: ${HOURS}h ${MINUTES}m"
    log "End time: $(date)"
    
    generate_summary
    
    log_success "Phase 2 embedding backfill complete!"
    log "Ready to proceed to Phase 3: Regime Classification"
}

# Parse arguments
DRY_RUN=false
SKIP_TEXT=false
SKIP_NUMERIC=false
SKIP_JOINT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-text)
            SKIP_TEXT=true
            shift
            ;;
        --skip-numeric)
            SKIP_NUMERIC=true
            shift
            ;;
        --skip-joint)
            SKIP_JOINT=true
            shift
            ;;
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run           Check prerequisites only, don't run backfill"
            echo "  --skip-text         Skip text embedding backfill"
            echo "  --skip-numeric      Skip numeric embedding backfill"
            echo "  --skip-joint        Skip joint embedding backfill"
            echo "  --start-date DATE   Override start date (default: 2014-01-01)"
            echo "  --end-date DATE     Override end date (default: 2024-12-31)"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage"
            exit 1
            ;;
    esac
done

if [ "$DRY_RUN" = true ]; then
    check_prerequisites
    log "Dry run complete. Run without --dry-run to execute backfill."
    exit 0
fi

main
