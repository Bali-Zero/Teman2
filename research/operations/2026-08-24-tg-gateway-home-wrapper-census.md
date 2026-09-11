---
date: 2026-08-24
domain: operations
client_case: none
sources:
  - "live probe: grep -rlE \"api\\.telegram\\.org|sendMessage\" ~/scripts/ on Pro and Mini"
  - infra/home-fork/declared-pairs.json
  - .claude/skills/modus/PENDING-ARMS.md (row opened 2026-07-06)
adversarial_review: codex
---

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

## Adversarial review

Reviewed 2026-08-30 by **Codex GPT-5.6 `sol`** (`codex exec -m gpt-5.6-sol`, reasoning effort
xhigh) — a seat outside the Anthropic family that produced this census, which is the whole point
of the R1 gate. The refuter got the document verbatim plus a set of re-measurements taken the same
day on Pro and Mini by an M5 session (also not the author), and was asked to attack, not to
summarise. It raised 8 objections. **7 survive. 1 was settled against it by a measurement made
after it spoke.** Nothing below was rewritten into the census above: the body stays the record of
what was believed on 2026-08-24, and this section is the record of what it does not support.

**What re-measuring confirmed (the census is not fiction):**

- The Pro list holds exactly 38 entries, no duplicates, and every one of them is still a live hit
  today — the list contains no phantom path.
- All 3 Mini pairs are in `declared-pairs.json` on `origin/main` with exactly the repo paths named
  here and `machines: ["mini"]`; 0 of the 38 Pro paths appear as a declared pair. Both headline
  claims — "Mini complete", "Pro 0 declared" — reproduce.

**Objections that SURVIVE:**

1. **The stated method does not yield the stated number.** Re-running this document's own command
   with this document's own exclusions on Pro returns **61** files, not 38. The 23 extras are 11
   dated backup copies (`.pre-*`, `.patched-*`, `.homefork-bak-*`), 3 non-executable docs/prompts,
   1 vendored SDK payload, and 8 genuine live scripts. Some second-stage judgment was applied and
   never written down; "re-measured this tick, not recalled" is true of the act and false of the
   reproducibility.
2. **38 is an undercount of at least 8, and not because of drift.** Missing from the Pro list:
   `codex/automation-lib.sh`, `dropbox-intake-sync.sh`, `eventbus/meta_dispatcher.py`,
   `eventbus/research_sentinel.py`, `intel-lake-nb-pusher-standalone.py`,
   `intel-lake-outbox-drain.py`, `regulatory-watcher-run.sh`, `wr2-external-bench-run.sh`. Their
   mtimes on Pro run 2026-05-09 → 2026-08-21 — all **before** the census date, so they were there
   to be found. (mtime is a last-write proxy, not a creation date; a `cp -p` could in principle
   forge it. `regulatory-watcher-run.sh` is cited as the reference cascade wrapper in `CLAUDE.md`
   long before August, which makes the forged-mtime reading implausible for at least that one.)
3. **The `.bak*` exclusion does not remove what the reader will assume it removes.** 11 dated
   backup copies survive it; whatever dropped them was a human reading of the filename, not the
   filter as documented.
4. **"Mini — COMPLETE / 3 live candidates" is likewise not reproducible from the stated method.**
   The same command on Mini returns **6**: the 3 named, plus `mini-git-pull.sh.pre-healer-sync-20260812`,
   `mini-git-pull.sh.pre-w120-bak`, and `backups/automation-migration-20260505_042936/cron-agent-python/agent_job.py`.
   Classifying those 3 as not-live is defensible; the document's filter is not what did it.
5. **"No arming step remains for Mini" outruns a grep.** A wrapper that assembles the Telegram URL
   from parts, or calls it through a library, matches neither literal and is invisible to this
   census. The claim is "no arming step *that this search can see*".
6. **The "repo-pair or orphan" dichotomy is false by the document's own admission.** It names at
   least two further outcomes: the canonical gateway `tg_notify.py` (nothing to do) and the
   non-Telegram `sendMessage` false positives the method note itself predicts (also nothing to do).
7. **Therefore "closes the measurement half" does not hold.** Neither published number follows from
   the recorded procedure. What the row can honestly claim is a *partial, non-reproducible* census —
   the successor pass must re-run the enumeration with a written filter before doing any per-file
   work on top of it.

**Objection that FALLS:**

8. The refuter argued that "all 3 already cmp-paired" proves only that declaration metadata exists,
   with no content comparison recorded — correct as a criticism of the write-up. It was then
   settled empirically: on the Mini, each of the 3 live files hashes **identical to
   `git show origin/main:<repo path>`** (compared against `origin/main`, not the local checkout,
   which is the W106b trap). The pairs are genuinely converged today. The document still never
   showed this; the reader had to take it on faith.

**A defect the refuter found in the review itself:** the re-measurement handed to it broke the 23
Pro extras down as 10 backups and mis-added the categories to 22. The correct split is **11**
backups (`10 + 3 + 1 + 8 = 22 ≠ 23`). Corrected above. Worth recording because it is the same class
of error the census made — a count asserted faster than it was re-added — caught here only because
a seat that had not produced the number checked the arithmetic.

**Still open after this review:** the per-file pass over the Pro list (now known to be ≥46 files,
not 38), and a written, reproducible filter to replace the unstated one. Both remain what this
document says they are — work for a session with write access on Pro.
