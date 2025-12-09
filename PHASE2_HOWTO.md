# Phase 2: Embedding Backfill - How To Run

## Overview
Phase 2 backfills all encoder embeddings (text, numeric, and joint) for the full 2014-2024 period. This is the most compute-intensive phase.

**Estimated Time:** 28-92 hours of compute (varies based on hardware, news volume, and GPU availability)

## Prerequisites

1. **Activate virtualenv:**
   ```bash
   cd /home/feanor/coding_projects/prometheus_v2
   source venv/bin/activate
   ```

2. **Verify database connectivity:**
   ```bash
   python -c "from prometheus.core.database import get_db_manager; get_db_manager()"
   ```

3. **Check GPU availability (optional but highly recommended for text embeddings):**
   ```bash
   python -c "import torch; print('GPU:', torch.cuda.is_available())"
   ```

## Running Phase 2

### Dry Run (Test Prerequisites)
```bash
./scripts/run_phase2_embeddings.sh --dry-run
```

### Full Run (2014-2024)
```bash
./scripts/run_phase2_embeddings.sh
```

This will run all 6 sub-phases sequentially:
1. **Phase 2.1:** Text embeddings (news articles)
2. **Phase 2.2:** Numeric window embeddings (price/vol/factors)
3. **Phase 2.4:** Joint profile embeddings
4. **Phase 2.5:** Joint regime context embeddings
5. **Phase 2.6:** Joint stability/fragility embeddings
6. **Phase 2.7:** Joint assessment context embeddings (master embedding)

### Partial Runs

Skip specific phases if already complete:

```bash
# Skip text embeddings (if already done)
./scripts/run_phase2_embeddings.sh --skip-text

# Skip numeric embeddings (if already done)
./scripts/run_phase2_embeddings.sh --skip-numeric

# Skip all joint embeddings (if already done)
./scripts/run_phase2_embeddings.sh --skip-joint
```

### Custom Date Range

Run for a subset of dates (useful for testing):

```bash
# Test run: January 2014 only
./scripts/run_phase2_embeddings.sh --start-date 2014-01-01 --end-date 2014-01-31
```

## Monitoring Progress

### Real-Time Logs
The script outputs colored progress to the terminal and logs to `logs/phase2/`.

### Log Files
```bash
# View main log
tail -f logs/phase2/phase2_<timestamp>.log

# View specific phase logs
tail -f logs/phase2/text_embeddings_<timestamp>.log
tail -f logs/phase2/numeric_embeddings_<timestamp>.log
tail -f logs/phase2/joint_assessment_<timestamp>.log
```

### Check Database Progress

While running, you can check progress in another terminal:

```bash
source venv/bin/activate

# Text embeddings count
python -c "from prometheus.core.database import get_db_manager; dm = get_db_manager(); conn = dm.get_historical_connection(); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM text_embeddings'); print('Text embeddings:', cur.fetchone()[0])"

# Numeric embeddings count
python -c "from prometheus.core.database import get_db_manager; dm = get_db_manager(); conn = dm.get_historical_connection(); cur = conn.cursor(); cur.execute('SELECT model_id, COUNT(*) FROM numeric_window_embeddings GROUP BY model_id'); print('\\n'.join([f'{r[0]}: {r[1]:,}' for r in cur.fetchall()]))"

# Joint embeddings count
python -c "from prometheus.core.database import get_db_manager; dm = get_db_manager(); conn = dm.get_historical_connection(); cur = conn.cursor(); cur.execute('SELECT joint_type, COUNT(*) FROM joint_embeddings GROUP BY joint_type'); print('\\n'.join([f'{r[0]}: {r[1]:,}' for r in cur.fetchall()]))"
```

## Running in Background

For long-running jobs, use `screen` or `tmux`:

```bash
# Using screen
screen -S phase2
source venv/bin/activate
./scripts/run_phase2_embeddings.sh
# Detach with Ctrl+A, D
# Reattach with: screen -r phase2

# Using tmux
tmux new -s phase2
source venv/bin/activate
./scripts/run_phase2_embeddings.sh
# Detach with Ctrl+B, D
# Reattach with: tmux attach -t phase2
```

## Performance Tips

1. **GPU Acceleration:**
   - Text embeddings (Phase 2.1) benefit massively from GPU
   - If you have a remote V100, run Phase 2.1 on that server
   - Transfer the `text_embeddings` table data afterward

2. **Parallelization:**
   - Phases 2.1 and 2.2 can run in parallel (they don't depend on each other)
   - Split date ranges: e.g., 2014-2018 on one machine, 2019-2024 on another
   - Use `--start-date` and `--end-date` to split work

3. **Database Optimization:**
   - Ensure PostgreSQL has adequate `shared_buffers` and `work_mem`
   - Consider temporarily disabling indexes during bulk insert, then rebuild
   - Monitor disk I/O - this is write-heavy

## Troubleshooting

### Script Fails Early
- Check logs in `logs/phase2/`
- Verify database connectivity
- Ensure sufficient disk space (embeddings are large)

### Out of Memory
- Reduce `BATCH_SIZE` in the script (default: 64)
- For text embeddings, reduce to 32 or 16

### GPU Out of Memory
- Reduce batch size for text embeddings
- Or fall back to CPU (set `DEVICE="cpu"` in script)

### Missing Dependencies
```bash
pip install -e ".[dev]"
pip install torch transformers sentence-transformers
```

## After Phase 2 Completes

The script will print a summary of all embeddings created. Verify counts are reasonable:

**Expected scale (approximate):**
- Text embeddings: 100K-1M+ (depends on news volume)
- Numeric embeddings: 800K-5M per model (794 instruments × ~2,500 trading days × models)
- Joint embeddings: Similar scale to numeric

Then proceed to **Phase 3: Regime Classification**.

## Help
```bash
./scripts/run_phase2_embeddings.sh --help
```
