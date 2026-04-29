# Sentinel meta-watchdog (NB-A)

> Resolves "who watches the watcher?" from the [zero-crash audit
> 2026-04-29](audits/2026-04-29-zero-crash-audit/09_intervention_plan.md#nb-a-sentinel-itself-recursive-watchdog).

## Why

`~/scripts/nuzantara-sentinel.py` is the central monitor for ~58 jobs and
the Cell / Organism / NLM / fly-watcher / drive-watchdog chain. It writes
`~/.agent/decisions/sentinel_status.json` every ~5 minutes when alive.

If sentinel **crashes** and launchd silently fails to respawn, or
**hangs** (process alive but stuck), or its **status file disappears**,
nothing else in the stack notices. Every downstream alert depends on
sentinel running.

The existing `com.nuzantara.sentinel.plist` does NOT have `KeepAlive=true`
(captured under [P0-3 LaunchAgents
audit](audits/2026-04-29-zero-crash-audit/09_intervention_plan.md#p0-3-launchagents-mass-audit)).
Even after that fix lands, `KeepAlive=true` only handles crashes — it does
not detect hangs. We need a separate signal: **freshness of the status
file**.

## What

A separate, short-lived launchd job that runs every 10 minutes:

| File | Purpose |
| --- | --- |
| [`scripts/sentinel_meta_watchdog.sh`](../scripts/sentinel_meta_watchdog.sh) | The check + restart + alert logic |
| [`infra/launchagents/com.nuzantara.sentinel-meta-watchdog.plist`](../infra/launchagents/com.nuzantara.sentinel-meta-watchdog.plist) | launchd job definition (Pro-only, install manually) |

Each tick:

1. Stat `~/.agent/decisions/sentinel_status.json`
2. If missing → alert + `launchctl kickstart -k gui/$UID/com.nuzantara.sentinel`
3. If mtime older than `STALE_THRESHOLD_SEC` (15 min, 3× sentinel cadence) → same
4. Otherwise → log "OK" and exit
5. Cooldown of 1 h on alert/restart actions to prevent storm loops
6. Writes its own status to `~/.agent/decisions/state/sentinel_meta_watchdog.json`
   (mtime is the heartbeat — see "Mutual watch" below)

Telegram credentials come from `~/.nuzantara-secrets.env`
(`TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID`). Nothing is hardcoded in
the script or plist — VADEMECUM §11 + the Anthropic-key kill-switch
discipline both agree on this.

## Why this is NOT a new SPOF (recursion answer)

The standard objection to any watchdog: "fine, but what watches the
watchdog?" Three reasons it's safe here:

1. **Non-persistent execution.** The script does `stat → compare → maybe
   restart → exit`. Total wall time ~50ms-2s. It cannot hang
   indefinitely the way sentinel can — there is no event loop, no
   network call (other than the optional Telegram POST with `-m 10`
   timeout), no file lock.
2. **launchd is the ultimate scheduler.** If the watchdog process
   crashes mid-tick, the next `StartInterval` fires a fresh process
   anyway. If launchd itself fails, the entire Pro Mac is dead and
   that's caught by Air-side monitoring (lack of SSH reachability) and
   by Antonello losing interactive use of the machine.
3. **Mutual watch.** The watchdog writes
   `~/.agent/decisions/state/sentinel_meta_watchdog.json` each tick.
   Sentinel can be extended (separate task) to alert if THAT goes
   stale — closing the loop without infinite recursion. Each daemon
   watches the other's heartbeat file; if both die, the second-tier
   `login-healthcheck` probe (every 15 min, totally independent
   plist) is the catch-all.

## Install

The plist lives in the repo for review/diff but must be copied into
`~/Library/LaunchAgents/` to take effect — launchd does not load plists
from arbitrary paths.

```bash
cp infra/launchagents/com.nuzantara.sentinel-meta-watchdog.plist \
   ~/Library/LaunchAgents/
plutil -lint ~/Library/LaunchAgents/com.nuzantara.sentinel-meta-watchdog.plist
launchctl load -w ~/Library/LaunchAgents/com.nuzantara.sentinel-meta-watchdog.plist
launchctl list com.nuzantara.sentinel-meta-watchdog
```

`RunAtLoad=true` means the first tick fires immediately on load — useful
for verification.

## Verify

```bash
# Manual run, watching the log
tail -f ~/logs/sentinel-meta-watchdog.log &
bash ~/Desktop/nuzantara/scripts/sentinel_meta_watchdog.sh

# Inject synthetic stale state (sentinel hung simulation)
touch -r ~/.agent/decisions/sentinel_status.json /tmp/sentinel_mtime_backup
touch -t "$(date -j -v-30M +%Y%m%d%H%M)" ~/.agent/decisions/sentinel_status.json
bash ~/Desktop/nuzantara/scripts/sentinel_meta_watchdog.sh
# → expect: alert sent, sentinel kickstarted, cooldown file created

# Restore
touch -r /tmp/sentinel_mtime_backup ~/.agent/decisions/sentinel_status.json
rm -f /tmp/sentinel_mtime_backup ~/.agent/decisions/state/sentinel_meta_watchdog.cooldown
```

## Uninstall (fully reversible)

```bash
launchctl unload ~/Library/LaunchAgents/com.nuzantara.sentinel-meta-watchdog.plist
rm ~/Library/LaunchAgents/com.nuzantara.sentinel-meta-watchdog.plist
# Optional: clear state files
rm -f ~/.agent/decisions/state/sentinel_meta_watchdog.{json,cooldown}
```

The script in `scripts/` and the plist in `infra/launchagents/` stay in
the repo — uninstall only affects the running launchd job.

## Tunables

| Variable | Default | Notes |
| --- | --- | --- |
| `STALE_THRESHOLD_SEC` | 900 (15 min) | 3× sentinel's 5-min cadence. Lower → more false-positive restarts; higher → slower hang detection. |
| `COOLDOWN_SEC` | 3600 (1 h) | Time between alerts/restarts. Raise if sentinel takes >1h to fully recover (it shouldn't). |
| `StartInterval` (plist) | 600 (10 min) | Watchdog tick rate. Must be ≤ `STALE_THRESHOLD_SEC` to avoid missing hangs. |

## Cicatrix-scars correlation

This addresses the same class of bug as
`✅ RESOLVED: Backend prod down — drive_poll_service called missing method`
([cicatrix-scars.md](../.claude/rules/cicatrix-scars.md#-resolved-backend-prod-down--drive_poll_service-called-missing-method-on-serviceaccountdriveservice-2026-04-29)):
the system was deterministically broken and the only signal was a
downstream user-facing failure. Here we add an upstream signal so
sentinel breakage surfaces independently.
