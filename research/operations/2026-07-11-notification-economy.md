---
date: 2026-07-11
domain: operations
client_case: none (internal ops — Telegram notification economy)
sources:
  - infra/tg-gateway/grandfathered.json (repo-canon census, frozen 2026-07-06)
  - scripts/tg_notify.py, scripts/tg_digest_flush.py, scripts/lint_tg_direct_senders.py
  - .claude/skills/modus/PENDING-ARMS.md line "ECONOMIA-NOTIFICHE" (opened 2026-07-06)
  - ssh pro / ssh mini live crontab + LaunchAgents (2026-07-11 session)
  - live smoke tests via TG_DRY_RUN (this session)
---

# Notification economy — lane S1 (NOTIF-ECONOMY) findings, 2026-07-11

**Mandate**: ECONOMIA-NOTIFICHE (PENDING-ARMS opened 2026-07-06, Zero: "sessione dedicata,
problema serio e out of control"). 206 senders write to Telegram that nobody reads. Doctrine
v1: disk state is the store, chat is a view, nothing may exist ONLY as a Telegram message.

## What already existed before this session

The gateway is not a proposal — it is live, CI-enforced infrastructure:

- `scripts/tg_notify.py` — the ONE gate (3 tiers: p0/digest/log), flock-serialized spool,
  dedup, daily P0 budget, relay-over-ssh for M5 (no token), NEVER fails the caller.
- `scripts/tg_digest_flush.py` — flushes spooled digest events, one grouped message per slot.
  Armed on both Pro (`gui/502/com.nuzantara.tg-digest-flush`) and Mini
  (`gui/501/com.nuzantara.mini.tg-digest-flush`), proven live end-to-end 2026-07-07.
- `scripts/lint_tg_direct_senders.py` — the enforcement lint the mandate asked me to build.
  It already exists, is registered in `infra/guard-conformance/registry.json`
  (guilt+innocence tested), and runs in CI (`.github/workflows/tg-gateway.yml`) on every PR
  touching `**/*.sh|py|js|mjs|ts|plist`. It fails a PR that adds a NEW direct
  `api.telegram.org` sender outside `infra/tg-gateway/grandfathered.json`, and separately
  fails if the grandfathered list GROWS vs origin/main (anti-bypass: can't add-and-grandfather
  in the same diff). This closes acceptance criterion 3 — no new lint was needed.
- **4 migration cohorts already landed** (2026-07-06/07): sentinel_lib.alerter (whole sentinel
  family), wa-mirror-attention-telegram, 6 watchdog shells, the wa-mirror TypeScript bridge
  (`apps/wa-mirror/bridge/telegram.ts`, first TS adopter).

The repo-canon count (`infra/tg-gateway/grandfathered.json`) stood at **162** at session start
(matches the ledger's "162 rimasti al 2026-07-07" note exactly).

## §Meta-pattern — the count everyone quotes is HALF the organism

The census that produced "206 senders" / "162 grandfathered" was built by
`lint_tg_direct_senders.py::tracked_files()`, which walks `git ls-files` — **repo-tracked files
only**. It has zero visibility into `~/scripts/` on Pro and Mini, which is exactly the HOME-fork
family (superscar #1 in `cicatrix-superscar.md`): a live, armed, cron-executed copy that has no
git-tracked twin at all.

I greped `~/scripts/` on both machines for `api.telegram.org`, filtered out `.bak*`/`.pyc`/
`__pycache__`/archived/backup noise, and cross-referenced the survivors against both the repo's
tracked-file basenames and `grandfathered.json`:

| Machine | Live `~/scripts/` direct senders (post-filter) | Repo-canon match (any path) | Already in grandfathered.json |
|---|---|---|---|
| Pro | 48 | 22 | 22 |
| Mini | 5 | 1 | 1 |

**26 of the 48 Pro-side live senders have NO repo-tracked file with a matching basename at
all** — they are HOME-only Telegram senders. Confirmed armed (not residue) via
`crontab -l` and `~/Library/LaunchAgents/*.plist` grep — e.g. `automap_watchdog.py`,
`automap_telegram.py`, `cpu-monitor.sh`, `login-healthcheck.sh`, `deadman-heartbeat.sh`,
`disk-monitor.sh`, `fly-health-check.sh`, `fly-cost-alert.sh`, `cert-monitor.sh`,
`gh-auth-healthcheck.sh`, `vercel-cost-reminder.sh`, `claude-max-usage-watcher.py` (live plist,
distinct from the `.disabled-20260514` copy), `wr2-canva-oauth-watchdog.sh`,
`wr2-external-bench-run.sh`, `nb-intel-delta-watcher.sh`, `crm-guardian-cli-worker.sh`,
`matagaruda-redis-split-brain-check.sh`, `dropbox-intake-sync.sh`, `daily_indexing_sweep.sh`,
`gdrive-backup-all.sh`, `nextdns-weekly-digest.sh` (this one's basename DOES exist in repo —
`scripts/nextdns-weekly-digest.sh` — but the live copy at `~/scripts/nextdns-weekly-digest.sh`
is a separate HOME payload, not declared in `infra/home-fork/declared-pairs.json`),
`openclaw-children-watchdog.sh`, `qwen-code-review.sh`, `wr2-mark-published.sh`,
`intel-lake-shadow-validate.sh`, `intel-lake-probe-cron.sh`, `audit-launchd-daily.sh`.

**Real number of distinct direct-Telegram-sender surfaces the organism carries: at minimum
162 (repo-canon) + 26 (Pro HOME-only, verified) + Mini's remainder = >190, likely closer to
the original "206" figure once you count what the repo-canon count was silently missing.**
The 206 in the ledger and the 162 in grandfathered.json were probably never the same set to
begin with — 206 was likely a rougher earlier grep, 162 is the CI-enforceable subset. Neither
was a HOME-fork-aware census.

This is not this lane's failure to close — extending `lint_tg_direct_senders.py`'s reach into
`~/scripts/` on Pro/Mini is a repo-lint-can't-see-HOME limitation by design (it runs in GitHub
Actions, which has no SSH access to Pro/Mini). The right tool for that gap already exists and
is registered under a DIFFERENT superscar: `scripts/lint_home_fork.py --discover` (superscar #1
antidote, IMMUNE FORGE 2026-07-05 #1970) finds undeclared HOME-executed payloads generically
(not Telegram-specific). A sibling session's task list (visible in this session, not mine —
"Item2: Reverse-promote 5 HOME-only claude wrappers on Pro") suggests this HOME-fork audit
angle is already being worked by another lane this same window. **Recommendation, not
executed here**: run `lint_home_fork.py --discover` on Pro/Mini and cross the undeclared
payload list against the `api.telegram.org` grep above — most of my 26 orphans should show up
there too, and the fix (declare-and-migrate, or promote-to-repo-then-migrate) is the same
HOME-fork antidote already built, just not yet pointed at this specific pattern.

## §Solo-operatore — what genuinely needs a human decision (none blocking this PR)

Nothing in this lane's changes required operator action — all 3 migrated files had no test
pinning the direct-send call site, so the migration was mechanical and independently
verifiable. Two things ARE operator-shaped, flagged not executed:

1. **HOME-only senders on Pro (26 files)**: these need either (a) promotion to repo canon +
   migration, or (b) explicit `infra/home-fork/declared-pairs.json` entries if they're
   deliberately HOME-only. That's an architectural call about which of these 26 scripts
   deserve to exist as tracked code at all (some, like `qwen-code-review.sh` or
   `automap_watchdog.py`, look like they may already have superseding repo-tracked
   equivalents under different names — needs eyes, not a mechanical grep).
2. **`claude-max-usage-watcher.plist`** is live on Pro while a `.disabled-20260514` copy of
   the SAME plist also exists — worth a human glance to confirm the live one is intentional
   and not a duplicate-armed instance (superscar #10 active-active pattern), though I found
   no evidence of dual firing in this session (only one plist file has no `.disabled` suffix).

## Cures delivered this session (5 total — repo-canon only, PR pending)

| # | File | Change | Verified |
|---|---|---|---|
| 1 | `scripts/cron-wrapper.sh` | pruned from grandfathered.json (already migrated in a prior cohort, never removed) | `lint --prune` confirmed zero `api.telegram.org` refs |
| 2 | `scripts/dlq_autopilot.py` | pruned from grandfathered.json (same — stale entry) | same |
| 3 | `scripts/drive_token_watchdog.py` | migrated `_send_telegram` to `tg_notify.py --tier p0` | 38/38 existing pytest pass (`test_drive_watchdog_tiers.py`) + live TG_DRY_RUN smoke: message reached gateway spool with `drive-token-watchdog@Air-M5` source tag |
| 4 | `scripts/job_health.py` | migrated `send_alert` to `tg_notify.py --tier p0` (dropped now-meaningless HTML markup — gateway sends plain text) | live TG_DRY_RUN smoke: `job-health@Air-M5` source tag, correct multi-line alert body |
| 5 | `scripts/wa_mirror_bridge_liveness_alarm.py` | migrated `_send_telegram` to `tg_notify.py --tier p0` | live TG_DRY_RUN smoke via backend venv (asyncpg dependency): `wa-mirror-bridge-liveness@Air-M5` source tag |

All 3 code migrations chose **p0 tier** deliberately: each only fires after its own internal
escalation gate already decided "actionable now" (drive-watchdog's URGENT/CRITICAL tier,
job_health's dead+critical filter, wa-liveness's 4-AND gate of DB-connected + process-dead +
past-grace + business-hours). None of these three are digest-worthy noise — they were already
low-frequency, high-signal P0s being sent the wrong way (direct HTTP instead of through the
gateway's dedup/budget/relay machinery). The gain isn't "fewer messages", it's that these 3
P0s now get the gateway's dedup (won't double-fire on flapping), the M5 relay path (works even
without a local token), and land in the same `archive-p0.jsonl`/`pending.jsonl` audit trail as
every other P0 instead of vanishing into Telegram-only history.

grandfathered.json: **162 → 157** (repo-canon only; the ~26 Pro HOME-only orphans found above
are a separate, uncounted surface — see §Meta-pattern).

Full gateway regression suite run against the migration (all green):
`tg_notify.py --selftest`, `tg_digest_flush.py --selftest`, `lint_tg_direct_senders.py`,
`lint_tg_direct_senders.py --selftest`, `pytest scripts/tests/test_tg_gateway.py` (6/6),
`pytest apps/backend-rag/backend/tests/unit/scripts/test_drive_watchdog_tiers.py` (38/38).

## Enforcement lint — status

Acceptance criterion 3 ("enforcement lint PR armed") is **already satisfied by prior work**,
not by this session: `scripts/lint_tg_direct_senders.py` + `.github/workflows/tg-gateway.yml`
are live, merged, and running on every PR since the gateway's birth PR. I verified it still
passes cleanly against my changes (monotone check: the list may only shrink vs origin/main —
mine does, 162→157). No new lint PR was opened because none was needed; opening a duplicate
would violate reuse-first.

## Next cohort candidates (not migrated this session — time-boxed out)

Two files DO have test coverage pinning behavior near the send site
(`scripts/nextdns_tamper_detect.py`, `scripts/expiry_alerter.py` — both have
`scripts/tests/test_*.py`) and were deliberately left for a future cohort rather than rushed:
migrating them correctly means updating their tests too, which is a bigger unit of work than
the 3 untested files I picked for a 2-hour box. Good cohort-6 candidates given they're both
digest/log-tier-shaped (nextdns weekly digest already digest-tier by name; expiry_alerter's
tiers likely mirror drive_token_watchdog's pattern).
