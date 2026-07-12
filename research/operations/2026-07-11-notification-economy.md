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
adversarial_review: gpt-5.5
---

# Notification economy — lane S1 (NOTIF-ECONOMY) findings, 2026-07-11

**Mandate**: ECONOMIA-NOTIFICHE (PENDING-ARMS opened 2026-07-06, Zero: "sessione dedicata,
problema serio e out of control"). The opening ledger line cites "206 senders" as the scale of
the problem — as this report's own §Meta-pattern section shows below, that figure is an
unverified rough grep with no readership measurement behind it, not a proven count of ignored
messages. Doctrine v1 stands regardless: disk state is the store, chat is a view, nothing may
exist ONLY as a Telegram message.

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

**These are two different populations, not addable into one total.** The 162 repo-canon count
is a deliberately over-matched textual census (`lint_tg_direct_senders.py:32-36`: any file
containing the literal string `api.telegram.org` counts as a hit, including comments,
docstrings, and test fixtures — "the safe direction" per that file's own comment). The 26
Pro HOME-only + Mini's remainder are a DIFFERENT kind of surface: live, cron/plist-armed
copies verified to actually execute, found by grep + `crontab -l`/`LaunchAgents` cross-check,
not a textual-mention census. Summing 162+26+Mini into ">190" mixes "files that mention the
string" with "processes confirmed armed" — the sum is not a meaningful count of anything.
What IS established: the repo-canon census is HOME-fork-blind by construction (superscar #1 —
it walks `git ls-files`, which has zero visibility into `~/scripts/`), so 162 undercounts the
organism's true direct-sender surface by at least the 26+Mini verified above. The "206"
figure in the original ledger predates this session and was never reconciled against either
count — it is neither confirmed nor refuted by this analysis, just not comparable to 162.

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

All 3 code migrations chose **p0 tier** deliberately: each routes every alert it produces
through the same tier, not only its most urgent one. **Correction**: drive-watchdog's gate is
NOT limited to URGENT/CRITICAL — `classify_tier()` (`drive_token_watchdog.py:91-152`) also
fires INFO at 30 days and WARNING at 14 days, and both flow through the identical
`_send_telegram(message, ...)` → `tg_notify.py --tier p0` call at line 471; connection
failures and `expires_at` parse errors (lines 398-434) bypass the tier system entirely and
always alert via the same p0 path. job_health's dead+critical filter and wa-liveness's 4-AND
gate (DB-connected + process-dead + past-grace + business-hours) remain accurately
high-signal-only. None of the three are digest-worthy *volume* noise — they were already
low-frequency sends going out the wrong way (direct HTTP instead of through the gateway's
dedup/budget/relay machinery) — but "low-frequency" is a property of the underlying event
rate, not proof every message the gate emits is CRITICAL-grade.

The migration's real, verified gains: these P0s now land in the same
`archive-p0.jsonl`/`pending.jsonl` audit trail as every other P0 instead of vanishing into
Telegram-only history, and gain the M5 relay path — **but only when a local Telegram bot
token IS present**. Both `drive_token_watchdog.py:_send_telegram()` (line ~250) and
`wa_mirror_bridge_liveness_alarm.py:_send_telegram()` (line 180-183) early-exit with
`return False` before ever invoking the gateway or the M5 relay if `bot_token`/`token` is
empty — the "no token" case in these two adopters is a silent no-op, not a relay-covered
path. (The gateway's own M5-relay-without-token capability, referenced at the top of this
report, is real — it just isn't reached by these two callers when they have no token, since
they never call into `tg_notify.py` in that case.)

**Dedup caveat (not previously stated)**: the gateway derives its dedup key from
`source + text[:160]` by default when no explicit `--dedup-key` is passed
(`tg_notify.py:206`) — none of the 3 migrated adopters here pass one. Drive-watchdog's alert
header embeds a timestamp (`f"🔔 <b>Drive Watchdog</b> — {timestamp}\n\n"`), so two alerts
for the *same* underlying condition sent minutes apart hash to different keys and will NOT
dedup against each other on flapping. job_health and wa-liveness were not checked for the
same pattern in this session — flagged as a follow-up, not fixed here (out of scope for a
report-only pass).

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

## Adversarial review

- Seat: gpt-5.5 (Codex CLI, fresh context, read-only sandbox) — 2026-07-12
- Verdict as returned: REFUTED (5 findings)
- (a) CONFIRMED → softened the mandate line: "206 senders" is now stated as an unverified
  figure from the ledger, not asserted as fact; the report's own §Meta-pattern already
  disclosed this, the mandate framing didn't match it.
- (b) CONFIRMED → rewrote the ">190, likely closer to 206" sum: 162 (textual mention census,
  deliberately over-matched per `lint_tg_direct_senders.py:32-36`) and 26+Mini (live
  armed-process census) are different populations and are not addable; replaced with an
  explicit statement that 162 undercounts by at least 26+Mini, without inventing a combined
  total.
- (c) CONFIRMED → corrected: `drive_token_watchdog.py` and `wa_mirror_bridge_liveness_alarm.py`
  both early-exit with `return False` before reaching the gateway/M5-relay when no local
  bot token is present — "works even without a local token" was false for these two adopters.
- (d) CONFIRMED → corrected: drive-watchdog routes INFO (30d) and WARNING (14d) tiers, plus
  connection/parse errors, through the same p0 send path as URGENT/CRITICAL — the report
  had implied only URGENT/CRITICAL reached Telegram.
- (e) CONFIRMED → softened "dedup impedisce doppio firing sul flapping" to an explicit caveat:
  none of the 3 adopters pass a stable `--dedup-key`, and drive-watchdog's message includes a
  variable timestamp that defeats the default text-derived dedup key on repeated firings.
  **Follow-up lead (not fixed tonight, report-only mandate)**: give drive_token_watchdog.py
  (and audit job_health.py/wa_mirror_bridge_liveness_alarm.py) a stable `--dedup-key` derived
  from tier+source instead of the default text-hash, so repeated alerts for the same
  underlying condition actually dedup across a flapping window.
