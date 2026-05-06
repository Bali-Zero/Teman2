# NB Mitochondrial Value Monitor — Operational Runbook

## What it is

Daily cron at 02:30 WITA that records per-NB metrics to SQLite and sends
Telegram alerts on tier regressions. See spec
[`docs/superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md`](../superpowers/specs/2026-05-07-nb-mitochondrial-monitor-design.md)
for the full design.

## Files and paths

| Artefact           | Path                                                                        |
| ------------------ | --------------------------------------------------------------------------- |
| Bootstrap registry | `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json`            |
| SQLite metrics     | `~/.agent/nb-mitochondrial/metrics.db`                                      |
| Run log            | `~/.agent/nb-mitochondrial/logs/nb-monitor.log`                             |
| Run error log      | `~/.agent/nb-mitochondrial/logs/nb-monitor.error.log`                       |
| LaunchAgent plist  | `~/Library/LaunchAgents/com.nuzantara.nb-mitochondrial-monitor.daily.plist` |
| Repo plist source  | `infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist`     |
| Weekly reports     | `~/Desktop/nuzantara/research/nb-monitor/report-YYYY-Www.md`                |
| CLI dashboard      | `scripts/nb-monitor/show.py`                                                |

## Initial deploy

```bash
# 1. Install plist (copy from repo)
cp infra/launchagents/com.nuzantara.nb-mitochondrial-monitor.daily.plist \
   ~/Library/LaunchAgents/

# 2. Verify lint
plutil -lint ~/Library/LaunchAgents/com.nuzantara.nb-mitochondrial-monitor.daily.plist

# 3. Smoke test (no LaunchAgent involved)
cd apps/mata-garuda && .venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once --no-telegram

# 4. Inspect output
sqlite3 ~/.agent/nb-mitochondrial/metrics.db \
  "SELECT uuid, tier, read_freq_7d FROM nb_metrics ORDER BY ts_capture DESC LIMIT 24;"
python scripts/nb-monitor/show.py

# 5. Bootstrap into launchd
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.nb-mitochondrial-monitor.daily.plist
launchctl print gui/$(id -u)/com.nuzantara.nb-mitochondrial-monitor.daily | head -20
```

## Force a one-off run

```bash
launchctl kickstart -k gui/$(id -u)/com.nuzantara.nb-mitochondrial-monitor.daily
# OR direct (bypasses launchd)
cd apps/mata-garuda && .venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once
```

## Tail logs

```bash
tail -f ~/.agent/nb-mitochondrial/logs/nb-monitor.log
tail -f ~/.agent/nb-mitochondrial/logs/nb-monitor.error.log
```

## Force a weekly report

```bash
cd apps/mata-garuda && .venv/bin/python -m mata_garuda.scripts.nb_monitor.run --once --report
```

Report appears at `~/Desktop/nuzantara/research/nb-monitor/report-YYYY-Www.md`.

## Troubleshooting

### Symptom: cron run completed but `metrics.db` empty

- Check `~/.agent/nb-mitochondrial/logs/nb-monitor.error.log` — is `RegistryLoadError` logged? → fix bootstrap JSON.
- Check `ls ~/.claude/projects/-Users-nuzantara/*.jsonl` — empty? Pro session dir may have moved → update `PRIMARY_PATHS` in `collectors/log_scraper.py`.

### Symptom: too many Telegram alerts

- Cooldowns: 24h for top5/tier-transition, 7d for dying-no-action. If duplicate firings, inspect:
  ```
  sqlite3 ~/.agent/nb-mitochondrial/metrics.db \
    "SELECT uuid, condition, datetime(sent_at,'unixepoch') FROM alerts_sent ORDER BY sent_at DESC LIMIT 10;"
  ```
- Set `TELEGRAM_BOT_TOKEN=` empty in plist `EnvironmentVariables` to fully suppress dispatch (the plist will need to be reloaded).

### Symptom: `cookie_refresh_pending` in `instrumentation_status`

- nlm CLI cookie has expired (5min TTL). Run `nlm login --clear` interactively to refresh, then rerun.

### Symptom: `parse_failure` in `instrumentation_status`

- Means the JSONL scraper found zero NLM events across all session files. Either the user has not used NotebookLM in the window OR the JSONL schema changed. Check a recent `~/.claude/projects/-Users-nuzantara/*.jsonl` and grep for `mcp__notebooklm-mcp__notebook_query` — if absent, no real issue; if present and parser missed it, regression in `log_scraper.py`.

### Disable the cron

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.nb-mitochondrial-monitor.daily.plist
```

## Future-work pointers

When FASE 1 (Qdrant local skills) merges:

- Wire `collectors/skill_derivation.py::count_skills_for_uuid` to query `bali_zero_skills_local`.
- Tests in `test_skill_derivation.py` (new file) for the wiring.

When FASE 2 (`notebook_registry.py`) merges:

- Update `registry.py::load_registry` to prefer `notebook_registry.NB_REGISTRY` if importable.
- Delete `~/.agent/nb-monitor/active_notebooks_bootstrap_2026-05-07.json` after one full week of clean runs.

When FASE 4 (Oracle citation logging) merges:

- Wire `collectors/cite_rate.py::compute_rate_for_uuid` to query the citation log.
