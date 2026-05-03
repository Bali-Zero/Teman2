# Google Search Console Indexing Sweep — Quick Start

## What It Does

Automatically submits new articles and KBLI pages to Google's Indexing API every day at 00:30 WITA:
- **Phase 1 (Articles):** Up to 200 URLs/day, prioritized by GSC impressions
- **Phase 2 (KBLI):** Up to 600 URLs/day via 3 service accounts
- Posts a daily summary to Telegram

## Files

- **Main Script:** `scripts/daily_indexing_sweep.py` — orchestrator (Python)
- **Cron Wrapper:** `scripts/daily_indexing_cron.sh` — runs on Air at 00:30 WITA
- **Setup Guide:** `docs/INDEXING_SWEEP_SETUP.md` — detailed configuration
- **Phase 1 Worker:** `apps/evaluator/articles_indexing_submit.py`
- **Phase 2 Worker:** `apps/evaluator/kbli_indexing_submit.py`

## Quick Commands

```bash
# See what would be submitted (no API calls)
python3 scripts/daily_indexing_sweep.py --dry-run

# Show current progress
python3 scripts/daily_indexing_sweep.py --status

# Run full sweep (articles → KBLI)
python3 scripts/daily_indexing_sweep.py
```

## Setup on Air

1. Verify credentials exist: `.secrets/{google-credentials.json,kbli-indexer-2.json,kbli-indexer-3.json}`
2. Add cron job:
   ```bash
   crontab -e
   # Add: 30 0 * * * /Users/antonellosiano/Projects/nuzantara/scripts/daily_indexing_cron.sh
   ```
3. Test: `python3 scripts/daily_indexing_sweep.py --dry-run`

## Logs & Monitoring

- **Log file:** `logs/daily_indexing_sweep.log` (on Air)
- **Telegram:** Automatic summary each day (via OpenClaw bridge)
- **Status:** `python3 scripts/daily_indexing_sweep.py --status`

## State Files

Progress is saved in:
- `apps/evaluator/articles_indexing_state.json` — tracks article submissions
- `apps/evaluator/indexing_state.json` — tracks KBLI submissions

If something goes wrong, reset state with:
```bash
# Reset articles
python3 apps/evaluator/articles_indexing_submit.py --reset

# Reset KBLI
python3 apps/evaluator/kbli_indexing_submit.py --reset
```

## See Also

- Full documentation: [`docs/INDEXING_SWEEP_SETUP.md`](INDEXING_SWEEP_SETUP.md)
- CLAUDE.md § "Cron Air" — daily schedule table
