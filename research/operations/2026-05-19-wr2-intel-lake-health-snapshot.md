# Intel Lake + WR2 Health Snapshot — 2026-05-19 ~09:55 WITA

## ✅ FIXED THIS SESSION

| Component                   | Issue                                      | Fix                                                             |
| --------------------------- | ------------------------------------------ | --------------------------------------------------------------- |
| WR2 supervisor              | 84h crashloop (154 restart) — missing venv | `python -m venv` + `pip install -r requirements-prod.txt`       |
| events_outbox replay        | 7 unconsumed events                        | Auto-replayed on supervisor restart                             |
| 2 draft `briefed` stuck 4gg | reconcile sweep                            | Kicked → draft-generator pickup, Claude Opus 11 slides composed |

## 🔴 REMAINING RED FLAGS

### 1. com.balizero.wr2.canva-renderer plist — re-bootstrapped despite cicatrix scar 2026-05-13

- **Status**: LOADED in launchd (last exit 1, runs=17)
- **DB kill-switch**: `wr2_canva_renderer_enabled=false` (set 2026-05-15 20:07)
- **Script invoked**: `/Users/nuzantara/Desktop/nuzantara/scripts/wr2_canva_apply.py` (LEGACY, decommissioned per cicatrix)
- **Plist runs every 5min** (`StartInterval=300`) BYPASSING `wr2-script-wrapper.sh`
- **Result**: asyncpg `gaierror` on `DATABASE_URL=postgres://...flycast` (Fly internal hostname, irrisolvibile da Pro)
- **Damage**: 4.1 MB error log, **1122 traceback** since first crash, no actual canva work done (DB kill-switch was already true)
- **Cicatrix scar 2026-05-13**: documenta "production cron disabled 2026-05-13: kill switch + launchctl bootout. Plist preserved on disk for reload after orchestrator refactor". Quindi qualcuno HA RIATTIVATO il plist post-cicatrix.

### 2. WR2 launchd jobs with non-zero exit code (snapshot now)

| Label                                     | Last exit                                              |
| ----------------------------------------- | ------------------------------------------------------ |
| com.nuzantara.federation-alert-dispatcher | 1                                                      |
| com.balizero.wr2.canva-token-watchdog     | 1                                                      |
| com.balizero.wr2.supervisor-watchdog      | 1 (era 6.3MB err log, post-fix dovrebbe stabilizzarsi) |
| com.balizero.wr2.image-generator          | **2**                                                  |
| com.nuzantara.cost-advisor-daily-cap      | 1                                                      |
| com.balizero.wr2.plist-watchdog           | 1                                                      |
| com.balizero.wr2.canva-renderer           | 1 (vedi #1)                                            |

### 3. intel-lake-router-cron — transient errors

- 177 ERROR over ~6 days (most are transient asyncpg pool failures, auto-recovered next tick)
- Currently healthy (last 10 ticks `exit=0`, `route_batch ok: selected=0`)
- **Trend**: 1 fail / ~60 min — acceptable but tracked

### 4. intel-lake-outbox-drain — appears healthy but...

- 752 KB stderr log dominated by `INFO [outbox-drain] idle (pending=0)` lines every minute since 2026-05-12 23:53
- These should be INFO not stderr — log routing misconfig
- **Trend**: stable, idle 24/7

### 5. system_settings sanity check

| Key                             | Value                           | Updated    |
| ------------------------------- | ------------------------------- | ---------- |
| wr2_canva_desktop_apply_enabled | true                            | 2026-04-24 |
| wr2_canva_renderer_enabled      | **false** (correct kill-switch) | 2026-05-15 |
| wr2_fact_extractor_enabled      | true                            | 2026-05-08 |
| wr2_fact_checker_enabled        | true                            | 2026-05-08 |

The kill-switch in DB is correctly OFF, but the plist doesn't read it before crashing.

## 🟢 HEALTHY

- intel-lake-nb-pusher: auth_ok=true, 0 pending
- regulatory-watcher: 07:00 daily run ok stamattina, 0 deltas
- bali-intel-scraper: published_articles.json updated
- canva-oauth-watchdog: 6-hour probes all OK (35-38 MCP tools visible >=30)
- supervisor: NOW running pid 83762, exit 0, draft pipeline active

## 🟡 ARCHITECTURAL ISSUES (need plan)

1. **Venv missing on deploy worktree** — happened spontaneously 2026-05-16; no watchdog detected it, supervisor crashloop for 84h before human noticed. **Need**: venv-presence watchdog OR wrapper auto-recreates if missing.

2. **Legacy script still wired in launchd** — `wr2_canva_apply.py` declared decommissioned 2026-05-13 (cicatrix) but `canva-renderer.plist` re-loaded post-decommission. **Need**: clean separation between "deprecated, kill-switched in DB" and "actually removed from launchd". Cicatrix antibody must be `launchctl bootout` AND plist removal AND script archival, otherwise drift recurs.

3. **Sibling agent branch hijack** of `~/Desktop/nuzantara` worktree (documented 3 occurrences today: feat/wr3-room-genesis → feat/docker-buildkit → feat/wr3-anchor-embedding). Risks: untracked file loss, commit on wrong branch, branch state confusion.

4. **No proactive surveillance of cron error-log size** — 6.3MB, 4.1MB, 754KB error logs grew silently. **Need**: log-size watchdog with Telegram alert if any `~/logs/*.err*.log > 1MB`.
