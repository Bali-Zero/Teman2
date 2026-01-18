# Scribe - Automated Documentation Generator

**Enhanced Version** - 2026-01-18

## Overview

Scribe automatically scans the codebase and generates comprehensive documentation:

- `docs/LIVING_ARCHITECTURE.md` - Complete API and module documentation
- `docs/SYSTEM_OVERVIEW.md` - System overview and statistics
- `docs/SYSTEM_MAP_4D.md` - 4D system consciousness map

## Quick Start

### Manual Execution

```bash
cd /Users/antonellosiano/Desktop/nuzantara
python apps/core/scribe.py
```

### Setup Cron Job (Auto-run daily)

```bash
./scripts/setup_scribe_cron.sh
```

This installs a cron job to run Scribe daily at 2:00 AM.

## Enhanced Features

### ✅ Accurate Counting

- **Test Files**: Counts from `backend/tests/` (excludes `tests/` root)
- **Test Cases**: Counts `def test_*` functions accurately
- **Migrations**: Excludes `scripts/` directory (only counts migration files)
- **API Endpoints**: Accurate regex matching for `@router.*` decorators
- **Conftest Files**: Dynamic counting

### ✅ Improved Error Handling

- Skips non-existent directories gracefully
- Handles import errors without crashing
- Detailed debug output

### ✅ Execution Tracking

- Start/end timestamps
- Success/failure logging
- Performance metrics (via enhanced runner)

## Files

| File                           | Purpose                      |
| ------------------------------ | ---------------------------- |
| `apps/core/scribe.py`          | Main Scribe script           |
| `scripts/scribe_cron.sh`       | Cron job wrapper script      |
| `scripts/setup_scribe_cron.sh` | Cron job installer           |
| `scripts/scribe_enhanced.py`   | Enhanced runner with metrics |
| `logs/scribe_cron.log`         | Cron execution logs          |

## Cron Job Details

**Schedule**: Daily at 2:00 AM (`0 2 * * *`)

**Logs**: `logs/scribe_cron.log`

**View Logs**:

```bash
tail -f logs/scribe_cron.log
```

**Remove Cron Job**:

```bash
crontab -e
# Delete the line with scribe_cron.sh
```

## Troubleshooting

### Scribe counts wrong numbers

- Check debug output: `python apps/core/scribe.py | grep Debug`
- Verify directory structure matches expectations
- Check for excluded patterns (scripts/, **init**.py)

### Cron job not running

1. Check cron service: `sudo service cron status` (Linux) or check macOS cron
2. Verify script permissions: `ls -l scripts/scribe_cron.sh`
3. Check logs: `cat logs/scribe_cron.log`

### Permission errors

```bash
chmod +x scripts/scribe_cron.sh
chmod +x scripts/setup_scribe_cron.sh
chmod +x scripts/scribe_enhanced.py
```

## Statistics Accuracy

Scribe now provides accurate counts:

- ✅ Test Files: 261 (was 407)
- ✅ Test Cases: 4,126 (was 6,383)
- ✅ Migrations: 48 (excludes scripts/)
- ✅ API Endpoints: ~381-387 (varies by counting method)

## Future Enhancements

Potential improvements:

- [ ] Git auto-commit option
- [ ] Slack/Telegram notifications
- [ ] Diff reporting (what changed since last run)
- [ ] Performance metrics dashboard
- [ ] Multi-environment support
- [ ] API endpoint method breakdown (GET/POST/etc.)

## Related Documentation

- `docs/operations/SCRIBE_CRON.md` - Detailed cron job documentation
- `docs/SYSTEM_MAP_4D.md` - Generated system map
- `docs/LIVING_ARCHITECTURE.md` - Complete API documentation
