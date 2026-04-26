# Daily Google Search Console Indexing Sweep

## Overview

Automated daily submission of articles and KBLI pages to Google's Indexing API with quota tracking and Telegram reporting.

**Schedule:** Every day at 00:30 WITA (17:30 UTC previous day)

### Phases

| Phase | Type     | Daily Limit | Details |
|-------|----------|-------------|---------|
| 1     | Articles | 200 URLs    | Prioritized by GSC impressions (28-day window) |
| 2     | KBLI     | 600 URLs    | Via 3 Service Accounts × 200 each (Gold pages first) |

---

## Scripts

### Main Orchestrator
- **Script:** `scripts/daily_indexing_sweep.py`
- **Type:** Python (async)
- **Function:** Runs Phase 1 (articles) → Phase 2 (KBLI) sequentially
- **Outputs:**
  - Logs: `logs/daily_indexing_sweep.log`
  - Telegram summary (if configured)

### Cron Wrapper
- **Script:** `scripts/daily_indexing_cron.sh`
- **Type:** Bash
- **Function:** Sets up logging, activates venv, calls main orchestrator
- **Location:** Run on **Air machine only** (handles async Telegram)

### Phase-Specific Scripts
- `apps/evaluator/articles_indexing_submit.py` — Phase 1 worker
- `apps/evaluator/kbli_indexing_submit.py` — Phase 2 worker

---

## Setup (Air Machine)

### 1. Verify Dependencies

```bash
# Check venv exists
ls -la apps/backend-rag/.venv/bin/python

# Test imports
.venv/bin/python -c "from google.oauth2 import service_account; print('OK')"
```

### 2. Service Account Credentials

**Articles Phase:** Requires 1 SA
```
.secrets/google-credentials.json (SA-1)
```

**KBLI Phase:** Requires 3 SAs
```
.secrets/google-credentials.json       (SA-1)
.secrets/kbli-indexer-2.json          (SA-2)
.secrets/kbli-indexer-3.json          (SA-3)
```

**Verification:**
```bash
# Check files exist
ls -la .secrets/{google-credentials.json,kbli-indexer-2.json,kbli-indexer-3.json}

# Verify GSC ownership (for each SA):
# https://search.google.com/search-console/users?resource_id=https://balizero.com/
# (All 3 SAs must be OWNER, not just user)
```

### 3. Telegram Integration

Sweep sends summary via OpenClaw bridge:

```bash
# Test bridge (from Air)
curl -s -X POST http://localhost:18789/telegram/send \
  -H "Content-Type: application/json" \
  -d '{"text":"🔧 Test from indexing sweep"}'
```

If bridge unavailable, Telegram sends are skipped (logged but non-fatal).

### 4. Add Cron Job

**Option A: Crontab (Air)**
```bash
# Edit crontab
crontab -e

# Add line (00:30 WITA = 17:30 UTC previous day)
30 0 * * * /Users/antonellosiano/Projects/nuzantara/scripts/daily_indexing_cron.sh
```

**Option B: Verify via launchd (macOS)**
```bash
# Check if launchd plist exists
ls -la ~/Library/LaunchAgents/com.balizero.daily-indexing-sweep.plist
```

---

## Manual Execution

### Full Sweep
```bash
cd ~/Projects/nuzantara
.venv/bin/python scripts/daily_indexing_sweep.py
```

### Dry-Run (Preview)
```bash
.venv/bin/python scripts/daily_indexing_sweep.py --dry-run
```

### Status Only
```bash
.venv/bin/python scripts/daily_indexing_sweep.py --status
```

### Phase 1 Only (Articles)
```bash
cd ~/Projects/nuzantara
.venv/bin/python apps/evaluator/articles_indexing_submit.py --batch 200
```

### Phase 2 Only (KBLI)
```bash
cd ~/Projects/nuzantara
.venv/bin/python apps/evaluator/kbli_indexing_submit.py --batch 600
```

---

## Quota & Rate Limits

### Google Indexing API Limits

| Resource           | Daily Limit | Enforcement |
|--------------------|-------------|-------------|
| Per Service Account | 200 URLs    | Hard limit |
| Request Rate       | ~2 req/sec  | 429 backoff |
| Burst              | 100 tokens  | Sliding window |

**Sweep Handling:**
- Articles: 1 SA × 200 = 200 URLs/day
- KBLI: 3 SAs × 200 = 600 URLs/day
- Auto-retry on 429 (Rate Limit) — waits 60s, retries once per URL

### State Tracking

```json
// articles_indexing_state.json
{
  "submitted": ["slug1", "slug2", ...],
  "failed": ["slug3", ...],
  "last_run": "2026-04-26T00:30:45.123456",
  "total_submitted": 2500
}

// indexing_state.json (KBLI)
{
  "submitted": ["4711", "5411", ...],
  "failed": ["1234", ...],
  "last_run": "2026-04-26T00:32:10.654321",
  "total_submitted": 1450
}
```

**Resumption:** If cron fails mid-run, state is preserved. Next run resumes where it left off (skips already-submitted URLs).

---

## Monitoring & Alerts

### Logs

```bash
# Live tail
tail -f ~/Projects/nuzantara/logs/daily_indexing_sweep.log

# Yesterday's run
cat ~/Projects/nuzantara/logs/daily_indexing_sweep.log | grep "2026-04-25"
```

### Telegram Messages

Sample output:
```
📊 Daily Indexing Sweep Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Articles Phase
  OK:        152
  Failed:    2
  Remaining: 1847

📗 KBLI Phase (3 SAs)
  OK:        598
  Failed:    0
  Remaining: 963

⏱️  Duration: 234s
```

### Failure Modes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| "403 Ownership not verified" | SA not OWNER in GSC | Add all 3 SAs as Owner in GSC settings |
| "All URLs already submitted" | State file corrupted or very old backlog | `--reset` to clear, restart Phase 1 |
| Rate limit hits >5 per phase | Submitting too fast | Increase `BATCH_DELAY_SEC` in scripts |
| Telegram not sending | OpenClaw bridge down | Set `TELEGRAM_NOTIFY=False` in sweep.py (logs only) |
| Venv not found | Air machine setup incomplete | Reinstall: `python -m venv .venv && pip install -r requirements.txt` |

---

## Performance

**Typical Duration:**
- Phase 1 (Articles 200/day): 120–180s
- Phase 2 (KBLI 600/day): 300–420s
- Total: 7–10 minutes

**Breakdown:**
- API calls: 800 URLs × 0.5s = 400s
- Retry backoffs (429): +60s per hit (rare)
- State I/O: <1s
- Overhead: <5s

---

## Troubleshooting

### Test Dry-Run
```bash
.venv/bin/python scripts/daily_indexing_sweep.py --dry-run
```
Shows what would be submitted without calling API.

### Check State
```bash
.venv/bin/python scripts/daily_indexing_sweep.py --status
```

### Reset State (Start Fresh)
```bash
# Articles
cd ~/Projects/nuzantara
.venv/bin/python apps/evaluator/articles_indexing_submit.py --reset

# KBLI
.venv/bin/python apps/evaluator/kbli_indexing_submit.py --reset
```

### Manual Check GSC Ownership
```bash
# Visit https://search.google.com/search-console/users?resource_id=https://balizero.com/
# Verify all 3 SAs (SA-1, SA-2, SA-3) are listed as "Owner"
# If user, click "Change role" → Owner
```

---

## See Also

- [`scripts/daily_indexing_sweep.py`](../scripts/daily_indexing_sweep.py) — Main orchestrator
- [`scripts/daily_indexing_cron.sh`](../scripts/daily_indexing_cron.sh) — Cron wrapper
- [`apps/evaluator/articles_indexing_submit.py`](../apps/evaluator/articles_indexing_submit.py) — Phase 1
- [`apps/evaluator/kbli_indexing_submit.py`](../apps/evaluator/kbli_indexing_submit.py) — Phase 2
- **CLAUDE.md** § "Cron Air" — Full schedule table

---

**Last Updated:** 2026-04-26  
**Maintained by:** Bali Zero AI Team
