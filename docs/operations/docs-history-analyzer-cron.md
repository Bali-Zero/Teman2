# docs-history-analyzer Cron

**Host:** Pro (`nuzantara@Nuzantara`)
**Schedule:** 1st of the month at 06:00 WITA (= last day of prev month 22:00 UTC)
**Script:** `/Users/nuzantara/Desktop/nuzantara/scripts/docs_history_analyzer.py`
**Output:** `docs/DOCS_TRENDS.md` (auto-generated, committed by git-guardian or ignored)
**Log:** `~/logs/docs-history-analyzer.log`

Monthly companion to weekly docs-guardian. Mines git log over the last 6 months of `docs/**/*.md` to surface evolutionary patterns:

- Birth/death rates
- Rename activity (directory restructuring phases)
- Top-touched docs (central / evolving)
- Quiet-but-alive docs (future orphan candidates)

Orthogonal to `docs/DOCS_INVENTORY.md`:
- **DOCS_INVENTORY.md**: state snapshot (which docs are LIVE/STALE/ARCHIVED right now)
- **DOCS_TRENDS.md**: evolution (how the corpus is changing over time)

## Install

```bash
mkdir -p ~/logs
( crontab -l 2>/dev/null; echo "0 6 1 * * /Users/nuzantara/Desktop/nuzantara/scripts/docs_history_analyzer.py --quiet >> $HOME/logs/docs-history-analyzer.log 2>&1" ) | crontab -
crontab -l | grep docs-history-analyzer
```

## Verify

```bash
# Run manually any time (idempotent):
python /Users/nuzantara/Desktop/nuzantara/scripts/docs_history_analyzer.py --months 6
cat ~/Desktop/nuzantara/docs/DOCS_TRENDS.md
```

## Uninstall

```bash
crontab -l | grep -v docs-history-analyzer | crontab -
```

## Related

- Weekly: `scripts/docs_guardian.sh` → `docs/DOCS_INVENTORY.md` (state)
- Monthly: `scripts/docs_history_analyzer.py` → `docs/DOCS_TRENDS.md` (trends)
- Design: `docs/superpowers/specs/2026-04-24-docs-hygiene-design.md`
