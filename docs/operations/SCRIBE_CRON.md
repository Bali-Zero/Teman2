# Scribe Auto-Documentation Cron Job

**Last Updated:** 2026-01-18 · **Status:** ⚠️ ARCHIVED 2026-04-25

> Scribe (`apps/core/scribe.py`) è stato **rimosso** dal commit `0c60050e8`
> (massive repo cleanup — dormant systems). Questo doc descrive un sistema
> non più attivo. Per la generazione documentazione attuale vedi
> `scripts/docs_sync.py` (DOCSYNC markers).

## Overview

Scribe automatically generates and updates system documentation daily via cron job.

## Setup

### Install Cron Job

```bash
cd /Users/antonellosiano/Projects/nuzantara
./scripts/setup_scribe_cron.sh
```

This will:

- Install cron job to run daily at 2:00 AM
- Log output to `logs/scribe_cron.log`

### Manual Execution

```bash
# Run Scribe manually
python apps/core/scribe.py

# Or use the cron script directly
./scripts/scribe_cron.sh
```

## Schedule

**Default:** Daily at 2:00 AM (`0 2 * * *`)

To change schedule, edit `scripts/setup_scribe_cron.sh` and re-run setup.

## Output Files

Scribe generates/updates:

- `docs/LIVING_ARCHITECTURE.md` - Complete API and module documentation
- `docs/SYSTEM_OVERVIEW.md` - System overview and statistics
- `docs/SYSTEM_MAP_4D.md` - 4D system consciousness map

## Logs

Logs are written to: `logs/scribe_cron.log`

View recent logs:

```bash
tail -f logs/scribe_cron.log
```

## Management

### View Cron Jobs

```bash
crontab -l
```

### Remove Cron Job

```bash
crontab -e
# Delete the line with scribe_cron.sh
```

### Test Cron Script

```bash
./scripts/scribe_cron.sh
```

## Troubleshooting

### Cron Job Not Running

1. Check cron service: `sudo service cron status`
2. Check logs: `tail logs/scribe_cron.log`
3. Verify script permissions: `ls -l scripts/scribe_cron.sh`

### Permission Errors

```bash
chmod +x scripts/scribe_cron.sh
chmod +x scripts/setup_scribe_cron.sh
```

### Python Path Issues

Ensure Python 3.11+ is in PATH:

```bash
which python3
python3 --version
```

## Enhanced Features

Scribe now includes:

- ✅ Accurate test file counting (`backend/tests/`)
- ✅ Accurate migration counting (excludes `scripts/`)
- ✅ Accurate API endpoint counting
- ✅ Dynamic conftest file counting
- ✅ Execution timestamps
- ✅ Error handling and logging

## Future Enhancements

Potential improvements:

- [ ] Git auto-commit option
- [ ] Slack/Telegram notifications on completion
- [ ] Diff reporting (what changed)
- [ ] Performance metrics
- [ ] Multi-environment support
