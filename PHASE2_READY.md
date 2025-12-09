# Phase 2: Ready to Execute

## Summary
Phase 2 orchestration script is ready. This script will coordinate all embedding backfills with:
- ✅ Color-coded progress output
- ✅ Detailed logging to `logs/phase2/`
- ✅ Time tracking for each sub-phase
- ✅ GPU detection and auto-configuration
- ✅ Database summary on completion
- ✅ Options for partial runs and custom date ranges

## Quick Start

```bash
# 1. Activate environment
cd /home/feanor/coding_projects/prometheus_v2
source venv/bin/activate

# 2. Test (dry run)
./scripts/run_phase2_embeddings.sh --dry-run

# 3. Run full Phase 2 (2014-2024)
./scripts/run_phase2_embeddings.sh
```

## What Phase 2 Does

Backfills all embeddings in dependency order:

1. **Text embeddings** (news → 384-dim vectors via transformer)
2. **Numeric embeddings** (price/vol/factors → 384-dim vectors)
3. **Joint profile** (combine numeric + text profiles)
4. **Joint regime context** (combine numeric regime + macro text)
5. **Joint stability/fragility** (combine numeric STAB + scenarios)
6. **Joint assessment context** (master embedding = profile + regime + STAB + recent text)

The final joint assessment context is what feeds the Assessment Engine for scoring.

## Files Created

- `scripts/run_phase2_embeddings.sh` - Master orchestration script (executable)
- `PHASE2_HOWTO.md` - Detailed usage guide
- `PHASE2_READY.md` - This file

## Monitoring Options

**Live terminal output** with colored progress bars and timing

**Log files** in `logs/phase2/`:
- `phase2_<timestamp>.log` - Main log
- `text_embeddings_<timestamp>.log` - Text phase log
- `numeric_embeddings_<timestamp>.log` - Numeric phase log
- `joint_*_<timestamp>.log` - Joint embedding logs

**Database queries** - Check progress in separate terminal:
```bash
python -c "from prometheus.core.database import get_db_manager; ..."
```

## Performance Considerations

**Estimated total time:** 28-92 hours
- Varies greatly based on:
  - GPU availability (massive speedup for text embeddings)
  - Number of news articles to encode
  - CPU cores (numeric embeddings benefit from multicore)
  - Disk I/O speed (heavy writes to PostgreSQL)

**Parallelization options:**
- Run Phase 2.1 (text) and 2.2 (numeric) in parallel (they're independent)
- Split date ranges across multiple machines
- Use `--skip-*` flags to resume after interruptions

**Resource usage:**
- High CPU (especially numeric embeddings)
- High disk I/O (writing millions of rows)
- Moderate memory (batched processing)
- GPU highly recommended for text embeddings

## Next Steps After Phase 2

Once Phase 2 completes:
1. ✅ Verify embedding counts in database summary
2. Move to **Phase 3:** Regime Classification
3. Then **Phase 4:** Backtest Campaigns

## Troubleshooting

See `PHASE2_HOWTO.md` for detailed troubleshooting.

Common issues:
- Missing PyTorch/transformers → `pip install torch transformers sentence-transformers`
- Out of memory → Reduce BATCH_SIZE in script
- Disk space → Embeddings are large, ensure 50GB+ free

## Options Reference

```bash
--dry-run           # Check prerequisites only
--skip-text         # Skip text embedding phase
--skip-numeric      # Skip numeric embedding phase
--skip-joint        # Skip all joint embedding phases
--start-date DATE   # Custom start (default: 2014-01-01)
--end-date DATE     # Custom end (default: 2024-12-31)
--help              # Show help
```

## Ready to Execute

Everything is set up. When ready:

```bash
source venv/bin/activate
./scripts/run_phase2_embeddings.sh
```

Or for long-running execution:

```bash
source venv/bin/activate
screen -S phase2
./scripts/run_phase2_embeddings.sh
# Detach: Ctrl+A, D
# Reattach: screen -r phase2
```
