# tg-gateway HOME wrapper census (Mini healer tick, 2026-08-24)

Closes the measurement half of the PENDING-ARMS row opened 2026-07-06 ("tg-gateway: HOME wrappers
vivi (`~/scripts/` Pro/Mini) che curl-ano Telegram direttamente ... censire con lint_home_fork e
migrare o cmp-pair"). Re-measured this tick, not recalled — `grep -rlE "api\.telegram\.org|sendMessage"
~/scripts/` run directly on both machines, filtered to live files (`.bak*`/`.pyc`/`__pycache__`
excluded), cross-checked against `infra/home-fork/declared-pairs.json`.

## Mini — COMPLETE

3 live candidates, all 3 already cmp-paired in `declared-pairs.json`:

- `~/scripts/heartbeat-watchdog.sh` → `scripts/mini-migration/heartbeat-watchdog.sh`
- `~/scripts/overlap-detector.sh` → `scripts/mini-migration/overlap-detector.sh`
- `~/scripts/mini-git-pull.sh` → `scripts/mini/mini-git-pull.sh`

No arming step remains for Mini.

## Pro — 38 live candidates, 0 declared (read-only ssh probe, no write made)

```
automap/automap_watchdog.py
automap/automap_telegram.py
nb-curator-daily.sh
dlq_autopilot.py
cpu-monitor.sh
wr2-probe-cron.sh
archive/db-backup.sh
archive/qwen-code-review.sh
archive/full-test-suite.sh
daily_indexing_sweep.sh
nb-intel-delta-watcher.sh
regulatory-watcher-fix-b-verify.sh
openclaw-children-watchdog.sh
crm-guardian-cli-worker.sh
deadman-heartbeat.sh
wr2-canva-oauth-watchdog.sh
codex/spalla-calibrate.sh
openclaw-cron/knowledge-graph-builder.sh
intel-lake-router-cron-standalone.py
claude-max-usage-watcher.py
l5-2-phase2b/l5_2_phase2b_auto_analyzer.py
intel-lake-shadow-validate.sh
qwen-code-review.sh
disk-monitor.sh
vector-reindex-check.py
gh-auth-healthcheck.sh
intel-lake-probe-cron.sh
gdrive-backup-all.sh
vercel-cost-reminder.sh
nextdns-weekly-digest.sh
sentinel_lib.old-20260411/alerter.py
nuz-sync/nuz-sync.sh
nuz-sync/nuz-sync-watchdog.sh
tg_notify.py
fly-cost-alert.sh
cert-monitor.sh
fly-health-check.sh
wr2-mark-published.sh
```

(paths relative to `~/scripts/` on Pro; `tg_notify.py` is the canonical gateway itself and is
expected to call Telegram directly — it is not a "wrapper", listed for completeness of the grep,
not as a defect.)

## What this does NOT resolve

Each of the 38 needs a per-file judgment call this tick did not make: does a matching repo path
already exist under `scripts/` (candidate for a `cmp`-verified `declared-pairs.json` entry,
`machines: ["pro"]`), or is it a genuinely orphaned HOME-only script (candidate for migration to
`tg_notify.py`, which is a code change — Gear 2, out of a healer tick's scope and out of the
Mini-local perimeter besides)? That per-file pass is real work — 38 files, most likely a mix of
both cases — and belongs to a session with write access on Pro, not a Mini-scoped healer tick
(Pro is read-only for this lane per its mandate).

## Method note (for whoever picks this up)

`grep -rlE "api\.telegram\.org|sendMessage" ~/scripts/` over-matches: `sendMessage` also appears
in non-Telegram contexts (WhatsApp/other messaging code) and the live-file filter above only
strips `.bak*`/`.pyc`/`__pycache__`, not those false positives. Re-verify each hit calls the
Telegram Bot API specifically before declaring or migrating it — do not trust this list's
membership blindly (superscar family #3, guard-over-match, applies to the *measurement* tool
here too, not just to production guards).
