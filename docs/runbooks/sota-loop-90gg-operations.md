# SOTA Social Loop 90gg — Operations Runbook

> **Status:** LIVE (activated 2026-04-24)
> **Maintainer:** Bali Zero AI Team
> **Companion docs:** `grafana-sota-setup.md` (dashboard), `competitor-scrape-manual.md` (Vino IG scrape procedure)
> **Design spec:** `docs/superpowers/specs/2026-04-22-bali-zero-social-sota-research-design.md`

## What is Loop 90gg?

A **90-day closed-loop** that turns the Bali Zero social output into a self-calibrating system:

1. **WR2 publishes** a post (existing pipeline — trend-hunter → oracle → dossier → ToneCouncil → draft → review → publisher). Row lands in `war_room_posts`.
2. **m13-collect** (cron every 6h, Pro) pulls IG Graph insights for that post at horizons +24h/+72h/+168h. Writes time-series rows in `post_metrics_history`.
3. **m13-weekly** (cron Sun 06:00 WITA, Pro) computes delta vs baseline across 5 channels × 3 pillars. Breach >20% → auto-toggles `wr2_publisher_enabled_<channel>=false` + Telegram alert. Delta >10% → triggers Consiglio retrain.
4. **m13-monthly** (cron 1st 04:30 WITA, Pro) — full retrain: re-ingest competitor corpus, re-infer personas, run Consiglio v1 (4 LLM), write new `09_wr2_weights.json`, archive `09_wr2_weights_YYYY-MM.json`.
5. **m13-checkpoint** (cron daily 09:00 WITA, Pro) — if loop day ∈ {30,60,90}, sends Telegram asking Zero for formal Go/Pivot/Kill decision per channel.

The loop closes because `09_wr2_weights.json` is read by WR2 when producing next batch of posts (through `EditorialConfig.load()`). So next week's output reflects last week's performance.

## Architecture map

```
                ┌─── war_room_posts (Fly.io Postgres) ◄─┐
                │        INSERT on publish              │
                ▼                                        │
   WR2 editorial pipeline                               │
   (Pro launchd + Fly backend)                          │
                                                        │ reads weights
   ┌────────────────────────────────────────────────────┤
   │                                                    │
   │  SOTA LOOP 90gg (Pro launchd, this runbook)        │
   │                                                    │
   │   m13-collect     every 6h       ── INSERT ──▶ post_metrics_history
   │   m13-weekly      Sun 06:00      ── SELECT ──▶ delta calc + digest
   │   m13-monthly     1st 04:30      ── retrain ──▶ 09_wr2_weights.json
   │   m13-checkpoint  daily 09:00    ── IF day ∈ {30,60,90} ──▶ Telegram
   │                                                    │
   └────────────────────────────────────────────────────┘
```

## Where things live

| Component | Location | Notes |
|---|---|---|
| Cron schedulers | `~/Library/LaunchAgents/com.balizero.sota.m13-*.plist` (Pro) | Install: `cp infra/launchagents/com.balizero.sota.m13-*.plist ~/Library/LaunchAgents/` |
| Plist source-of-truth | `infra/launchagents/com.balizero.sota.m13-*.plist` (repo) | Git-tracked |
| Cron Python modules | `apps/backend-rag/backend/services/sota_loop/` (both Pro + Fly) | Package: `backend.services.sota_loop.{m13_collect,m13_weekly,m13_monthly,m13_checkpoint}` |
| Wrapper (glue) | `/Users/nuzantara/.openclaw/bin/wr2/wr2-cron-wrapper.sh` (also mirrored at `scripts/wr2-cron-wrapper.sh`) | Sources secrets, maps DATABASE_URL_LOCAL→DATABASE_URL, verifies pg-proxy, activates venv, execs `python -m <module>` |
| Kill-switch router | `apps/backend-rag/backend/app/routers/research_control.py` (Fly) | 4 endpoints under `/api/research/control/*` — writes to `system_settings` |
| DB tables | `nuzantara-postgres.flycast` (Fly.io) | Migration 128: `war_room_posts`, `post_metrics_history`, `m13_retrain_log` |
| Grafana dashboard | `infra/grafana/social-sota-dashboard.json` | Import separately, see `grafana-sota-setup.md` |
| Loop start marker | `research/sota-social-2026-v1/.loop_start_date` (Pro) | ISO date, triggers checkpoint at day 30/60/90 |

## Activation ritual (how the loop was turned ON)

### Step 1 — Write loop start date

```bash
echo "$(date +%Y-%m-%d)" > ~/Desktop/nuzantara/research/sota-social-2026-v1/.loop_start_date
cat ~/Desktop/nuzantara/research/sota-social-2026-v1/.loop_start_date
```

Content: one line, ISO date, e.g. `2026-04-24`.

### Step 2 — Install + load launchagents

```bash
cp ~/Desktop/nuzantara/infra/launchagents/com.balizero.sota.m13-*.plist ~/Library/LaunchAgents/
for p in collect weekly monthly checkpoint; do
  launchctl unload ~/Library/LaunchAgents/com.balizero.sota.m13-${p}.plist 2>/dev/null
  launchctl load ~/Library/LaunchAgents/com.balizero.sota.m13-${p}.plist
done
launchctl list | grep balizero.sota
```

Expected output: 4 lines, format `-  0  com.balizero.sota.m13-<name>`. `-` = not running (scheduled), `0` = exit code OK.

### Step 3 — Flip kill-switches ON (DB direct)

The router `/api/research/control/*` covers 4 switches (research/retrain/playbook/publisher) but does NOT cover the 3 `sota_m13_*_enabled` switches used by the cron scripts. They must be flipped via SQL.

```bash
# All 5 SOTA kill-switches in one go, idempotent upsert
/Users/nuzantara/.openclaw/bin/wr2/wr2-cron-wrapper.sh backend.services.sota_loop._seed_killswitch
```

If `_seed_killswitch.py` helper is not present in your checkout, drop this file at `apps/backend-rag/backend/services/sota_loop/_seed_killswitch.py`:

```python
"""One-shot helper — flip SOTA kill-switches ON."""
import asyncio, os, asyncpg
async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        for k, v in [
            ("sota_m13_collect_enabled", "true"),
            ("sota_m13_weekly_enabled", "true"),
            ("sota_m13_monthly_enabled", "true"),
            ("sota_research_enabled", "true"),
            ("sota_retrain_enabled", "true"),
        ]:
            await conn.execute(
                "INSERT INTO system_settings(key, value, updated_at) VALUES ($1, $2, NOW()) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
                k, v,
            )
        for r in await conn.fetch("SELECT key, value FROM system_settings WHERE key LIKE 'sota_%' ORDER BY key"):
            print(f"  {r['key']:42s} = {r['value']}")
    finally:
        await conn.close()
asyncio.run(main())
```

### Step 4 — Verify end-to-end

```bash
# Smoke run (safe: checkpoint exits 0 if day not in {30,60,90}):
launchctl start com.balizero.sota.m13-checkpoint
sleep 2
tail -5 ~/.openclaw/workspace/logs/war-room-v2/sota-m13-checkpoint.error.log
# Expected: "... loop not started yet" (day 0) or "Loop day N — triggering checkpoint" (day 30/60/90)

# Status reader:
/Users/nuzantara/.openclaw/bin/wr2/wr2-cron-wrapper.sh backend.services.sota_loop._status
```

`_status` module (see `apps/backend-rag/backend/services/sota_loop/_status.py`) prints loop file, kill-switch rows, and SOTA table row counts in one go.

## Daily ops — what to watch

### Telegram

The bot `@Balizerobot` sends to chat `1125336968` (hardcoded in cron scripts, overridable via `TELEGRAM_OWNER_CHAT_ID` env):

| When | Sender | Content |
|---|---|---|
| Sun 06:00+ WITA | `m13-weekly` | `[SOTA weekly] OK` or `[SOTA weekly] BREACHES` + per-channel delta summary |
| Day 30/60/90, 09:00 WITA | `m13-checkpoint` | `[SOTA Checkpoint Day N]` + file path + "Reply GO/PIVOT/KILL per channel" |
| Immediate (on deploy-failure-alert) | `fly-deploy.yml` | Deploy crash notification |

### Logs

All cron logs live at `~/.openclaw/workspace/logs/war-room-v2/sota-m13-*.{log,error.log}`.

```bash
# Last fire of each cron:
for p in collect weekly monthly checkpoint; do
  echo "=== sota-m13-${p} ==="
  tail -10 ~/.openclaw/workspace/logs/war-room-v2/sota-m13-${p}.error.log 2>/dev/null
done
```

Common patterns:

| Log line | Meaning | Action |
|---|---|---|
| `kill switch OFF — exiting` | `sota_m13_<X>_enabled != 'true'` | Flip with seed script if intentional OFF |
| `collected <uuid> @ T_<N>H` | Insights fetch OK | Normal |
| `IG creds missing, skipping post` | `IG_GRAPH_API_TOKEN` or `IG_BUSINESS_ACCOUNT_ID` unset in `~/.nuzantara-secrets.env` | Add keys |
| `insights fetch failed for <uuid>: HTTP 401` | IG token expired | Refresh `IG_GRAPH_API_TOKEN` |
| `cannot reach 127.0.0.1:15432` | pg-proxy down | `launchctl start com.balizero.wr2.pg-proxy` |
| `auto-toggled publisher OFF for <channel>` | Weekly cron found pillar breach >20% | Check Telegram, review post history, decide pivot |
| `retrain triggered` | Delta crossed threshold in weekly | Consiglio v1 runs, new weights overwrite `09_wr2_weights.json` |

### Grafana dashboard

Read-only view of the same data. See `grafana-sota-setup.md`.

## Kill-switch reference (the 4 levers)

You control the loop via `system_settings` rows. Flip any time:

### Via Telegram bot (when router auth is fixed)

```bash
NUZ_API_KEY=$(grep '^export NUZANTARA_API_KEY=' ~/.nuzantara-secrets.env | cut -d= -f2)

# Pause entire research pipeline (stops *some* Loop activity — see note):
curl -X POST "https://nuzantara-rag.fly.dev/api/research/control/research" \
  -H "X-API-Key: ${NUZ_API_KEY}" -H "Content-Type: application/json" \
  -d '{"action":"pause"}'   # or "resume"

# Stop monthly retrain (e.g. if Consiglio token cost spikes):
curl -X POST "https://nuzantara-rag.fly.dev/api/research/control/retrain" \
  -H "X-API-Key: ${NUZ_API_KEY}" -H "Content-Type: application/json" \
  -d '{"action":"off"}'    # or "on"

# Freeze playbook (prevent auto-updates to 09_wr2_weights.json):
curl -X POST "https://nuzantara-rag.fly.dev/api/research/control/playbook" \
  -H "X-API-Key: ${NUZ_API_KEY}" -H "Content-Type: application/json" \
  -d '{"action":"freeze"}' # or "unfreeze"

# Disable publisher for one channel (e.g. pause IG while LinkedIn keeps going):
curl -X POST "https://nuzantara-rag.fly.dev/api/research/control/publisher" \
  -H "X-API-Key: ${NUZ_API_KEY}" -H "Content-Type: application/json" \
  -d '{"channel":"instagram","action":"off"}'  # or "on"
```

> **Known gap (2026-04-24):** `NUZANTARA_API_KEY` is NOT currently set as a Fly secret on `nuzantara-rag`, so the router returns 401 even with valid key from `~/.nuzantara-secrets.env`. To fix: `fly secrets set NUZANTARA_API_KEY=<value> -a nuzantara-rag`. Until then, use SQL direct (below).

### Via SQL direct (always works)

```bash
/Users/nuzantara/.openclaw/bin/wr2/wr2-cron-wrapper.sh backend.services.sota_loop._seed_killswitch
# (edit the key list inside _seed_killswitch.py to flip specific switches)
```

Or with raw psql (Pro with pg-proxy up):

```bash
source ~/.nuzantara-secrets.env
# Map LOCAL -> standard URL, normalize dbname:
DSN=$(echo "$DATABASE_URL_LOCAL" | sed -E 's|/nuzantara(\?\|$)|/nuzantara_rag\1|')

psql "$DSN" <<'SQL'
-- All 8 SOTA-related kill-switches in one transaction
INSERT INTO system_settings(key, value, updated_at) VALUES
  ('sota_m13_collect_enabled', 'true', NOW()),
  ('sota_m13_weekly_enabled',  'true', NOW()),
  ('sota_m13_monthly_enabled', 'true', NOW()),
  ('sota_research_enabled',    'true', NOW()),
  ('sota_retrain_enabled',     'true', NOW()),
  ('sota_playbook_frozen',     'false', NOW())
ON CONFLICT (key) DO UPDATE
  SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at;

SELECT key, value, updated_at
  FROM system_settings
 WHERE key LIKE 'sota_%' OR key LIKE 'wr2_publisher_%'
 ORDER BY key;
SQL
```

## Checkpoint flow (days 30, 60, 90)

At `09:00 WITA` on any day where `(today - .loop_start_date).days ∈ {30, 60, 90}`, `m13-checkpoint` will:

1. Write `research/sota-social-2026-v1/checkpoint_day_{N}.md` with decision deliverables
2. Send Telegram to Zero: `[SOTA Checkpoint Day N] formal review needed. File: ... Reply GO/PIVOT/KILL per channel`
3. **Exit** — the cron does NOT take any action on channels. You must reply.

Reply convention (not yet wired to automation — for future Sprint):
```
/checkpoint day30 decision=GO channel=instagram
/checkpoint day30 decision=PIVOT channel=linkedin
/checkpoint day30 decision=KILL channel=tiktok
```

Until the reply handler exists, treat the checkpoint as a **human reminder to review and manually update `09_wr2_weights.json` or flip `wr2_publisher_enabled_<channel>`**.

## Shutdown / pause procedures

### Soft pause (recommended — data preserved)

```bash
source ~/.nuzantara-secrets.env
DSN=$(echo "$DATABASE_URL_LOCAL" | sed -E 's|/nuzantara(\?\|$)|/nuzantara_rag\1|')
psql "$DSN" -c "UPDATE system_settings SET value='false' WHERE key LIKE 'sota_m13_%_enabled'"
```

Effect: the 3 cron modules will exit early on next fire. No data loss. Resume with `value='true'`.

### Hard pause (unload launchagents)

```bash
for p in collect weekly monthly checkpoint; do
  launchctl unload ~/Library/LaunchAgents/com.balizero.sota.m13-${p}.plist
done
launchctl list | grep balizero.sota   # Should print nothing
```

Effect: cron no longer fires at all. Files still in `~/Library/LaunchAgents/` but not registered. Reload with `launchctl load ...`.

### Nuclear (delete everything)

```bash
for p in collect weekly monthly checkpoint; do
  launchctl unload ~/Library/LaunchAgents/com.balizero.sota.m13-${p}.plist 2>/dev/null
  rm ~/Library/LaunchAgents/com.balizero.sota.m13-${p}.plist
done
rm ~/Desktop/nuzantara/research/sota-social-2026-v1/.loop_start_date
# Data in post_metrics_history stays — decide separately
```

Not recommended unless abandoning Loop entirely. Post_metrics_history retains history for forensic analysis.

## Troubleshooting

### "kill switch OFF — exiting" but you set it to `'true'`

Check the exact row key and value:

```bash
psql "$DSN" -c "SELECT key, value FROM system_settings WHERE key LIKE 'sota_m13_%_enabled'"
```

Common mistakes:
- Value `'True'` instead of `'true'` (Python bool vs string — script checks `value == "true"` exact match, case-sensitive)
- Missing row — `fetchval` returns `None`, comparison fails → behaves as OFF (safe default)

### Cron fires but "cannot reach 127.0.0.1:15432"

pg-proxy launchagent is down:

```bash
launchctl list | grep pg-proxy
# If absent: launchctl load ~/Library/LaunchAgents/com.balizero.wr2.pg-proxy.plist
# If present but exit != 0: launchctl unload + load to reset
```

### "ModuleNotFoundError: No module named 'backend.services.sota_loop'"

Pro repo is stuck on an old commit. Pull main:

```bash
cd ~/Desktop/nuzantara
git fetch origin main
git merge --ff-only origin/main   # or: git rebase origin/main on a feature branch
```

The `sota_loop/` package lives under `apps/backend-rag/backend/services/` since 2026-04-24. Verify present:

```bash
ls ~/Desktop/nuzantara/apps/backend-rag/backend/services/sota_loop/
# Expected: __init__.py, m13_checkpoint.py, m13_collect.py, m13_monthly.py, m13_weekly.py
```

### "connection closed in the middle of operation"

pg-proxy has a short idle timeout. For diagnostic scripts that hold a connection a long time, add a retry or split into multiple short connections. The production cron modules already do this (connection per operation).

### Telegram digest missing

Check:
1. `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_CHAT_ID` are in `~/.nuzantara-secrets.env` (both with `export` prefix).
2. Bot `@Balizerobot` has been started by Zero (must hit `/start` at least once).
3. Weekly/checkpoint cron actually fired (check `launchctl list` + logs).
4. No `parse_mode` was introduced — plain text only (Markdown with emoji + nested backticks triggers HTTP 400 per Fase 0 lesson #8).

### Router `/api/research/control/*` returns 401

`NUZANTARA_API_KEY` Fly secret missing. Set it once:

```bash
KEY=$(grep '^export NUZANTARA_API_KEY=' ~/.nuzantara-secrets.env | cut -d= -f2)
fly secrets set NUZANTARA_API_KEY="$KEY" -a nuzantara-rag
```

Deploy rolls automatically after secret change.

## Storage growth estimate

Per post, ~4 metrics (likes, reach, saves, click_through) × 3 horizons (24h, 72h, 168h) = 12 rows in `post_metrics_history`.

With WR2 posting ~5/week across all channels:
- 5 posts × 12 rows = **60 rows/week**
- 90-day loop = **~770 rows** total

Effectively zero storage concern. Index `ix_post_metrics_history_post_horizon` (created by migration 128) keeps the query-side fast.

## Monthly retrain cost

Each `m13-monthly` run invokes `scripts/sota_consiglio_playbook.py --wave=final` which:

- **Claude Max** — free under subscription (OAuth, not API key). No per-token cost.
- **Gemini OAuth** — free tier.
- **DeepSeek Reasoner** — ~$0.01–0.05 per deliberation (paid, per Golden Rule #13 carve-out).
- **Ollama local** — free, runs on Pro.

Total monthly cost: **< $0.10**. Triggered by weekly when delta > 10% (so possibly more than 1×/month if market shifts fast).

## Related files

- `research/sota-social-2026-v1/` — all Fase 0 artifacts + rolling Loop outputs (kpi_timeline.csv, weekly_report_*.md, checkpoint_day_*.md, 09_wr2_weights_YYYY-MM.json archives, retrain_log.jsonl)
- `apps/backend-rag/backend/services/measurer/m13_feedback_loop.py` — core logic class
- `apps/backend-rag/backend/services/war_room/editorial_config.py` — reader for `09_wr2_weights.json` (how WR2 consumes the Loop output)
- `apps/backend-rag/backend/db/migrations_v2/128_m13_feedback.sql` — DB schema

## Change log

| Date | Who | What |
|---|---|---|
| 2026-04-22 | Claude Opus 4.7 + Zero | PR #218 — Fase 0 artifacts + Fase 1 scaffold (M13FeedbackLoop, 4 cron scripts, EditorialConfig, Council v2, router, Grafana, smoke) |
| 2026-04-23 | Claude Opus 4.7 | PR #223 hotfix Dockerfile placeholder (unrelated, was breaking deploy) |
| 2026-04-24 | Claude Opus 4.7 | PR #225 — refactor scripts/m13_*.py → `backend.services.sota_loop` package + plist rewire to `wr2-cron-wrapper.sh` |
| 2026-04-24 | Claude Opus 4.7 + Zero | Loop activated: `.loop_start_date=2026-04-24`, 4 launchagents loaded, 5 kill-switches flipped ON via SQL direct |

## Next sprint ideas

- Wire the Telegram `/checkpoint day30 decision=GO channel=X` reply handler (currently humans act on the alert manually)
- Fix `NUZANTARA_API_KEY` fly secret so router `/api/research/control/*` authenticates
- Add a `_status` Telegram command so Zero can query loop state from phone
- Implement Task 13 — `sota_ingest_competitors.py` (Vino scrape → competitor_posts table). Currently `m13-monthly` soft-skips because script missing.
- Add Telegram digest screenshot attachment (Grafana PNG export)
