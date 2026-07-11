---
date: 2026-07-11
domain: ops
client_case: n/a
sources: PENDING-ARMS ledger lines ~47/~56/~61/~68/~75-78, live SSH probes on Pro+Mini, PR #2263
---

# Lane S5 (FLEET-LEDGER) burndown — 2026-07-11

Session ran under `.worktrees/ops-fleet-ledger` (branch `agent/air-m5/ops/fleet-ledger`), M5-based,
`ssh pro`/`ssh mini` both live, `pro-lan` dead per mandate. Six ledger items assigned; all six
closed-or-decided this session with fresh evidence (no line taken on the ledger's word alone —
every claim re-probed).

## 1. Ledger line ~61 — 3 exit-127 crons on Pro

**DONE, already resolved before this session started — verified, not re-fixed.**

All 3 plists (`com.balizero.autonomous-lab`, `com.balizero.autonomous-lab-runner`,
`com.nuzantara.intake-proposal-health-sentinel`) are no longer in the active
`~/Library/LaunchAgents/` on Pro — a prior session archived them to
`~/Library/LaunchAgents/.disabled-codex-cleanup-20260708/` on 2026-07-08 (folder mtime confirmed).
`launchctl print` on all 3 labels returns "Could not find service in domain" — they are genuinely
unloaded, not just failing.

- **autonomous-lab / -runner**: root cause confirmed via the archived plist's own
  `WorkingDirectory`/`ProgramArguments` — both pointed into
  `.worktrees/ops-autonomous-runner/apps/autonomous-lab/`, a worktree reaped >10 days before the
  archive date (superscar #1 HOME-fork × #5 sibling-race). This matches a SEPARATE still-open
  ledger line (~87, "Lab repoint") which is a deliberate Zero decision (2026-07-06) to leave the
  Autonomous Lab dormant until a Pro-resident session rebuilds it as a simulation chamber — NOT
  re-armed here, that decision stands.
- **intake-proposal-health-sentinel**: different, more serious root cause than a stale worktree —
  its target script `scripts/intake_proposal_health_sentinel_run.sh` **was never committed to the
  repo at all** (confirmed: zero git history, zero file on Pro's checkout). It's a genuinely
  HOME-only artifact that got deleted (Pro-08-07 archive or earlier), and I cannot resurrect it
  without fabricating logic I never saw (family #6 phantom-citation risk).
  - **Live finding, not yet acted on**: the surviving `~/logs/intake-proposal-health-sentinel.out`
    (last write 2026-06-26, before the plist died) shows the sentinel DID detect a real invariant
    violation before dying: `"3436 done-rows with only superseded proposals (dead in /review)"` —
    i.e. up to 3436 client documents (KTP/passport/akta candidates per the sentinel's own header
    comment) potentially silently lost in the intake pipeline, unmonitored for 15+ days because
    (a) the sentinel died and (b) its Telegram alerting was ALSO broken (DNS/network errors in the
    same log, so even while alive it likely never reached anyone). **This needs operator[business]
    visibility** — it's PII-adjacent client-document data, not something I fix mid-mandate.

**Verdict**: 2 of 3 plists correctly stay retired (Lab is a deliberate firebreak); the 3rd genuinely
needs either (a) a rewritten sentinel script committed to canon this time, or (b) an explicit
decision that PR #1587's SSOT/anti-deadlock fix already covers the invariant well enough that the
sentinel isn't needed — but the 3436-row finding from its last live run should be checked against
current `intake_queue` state before either path.

## 2. Ledger line ~68 (W89 class-audit) — 5 HOME-only wrapper reverse-promotion

**DONE — PR #2263, auto-merge armed, CI running (no failures at write-time).**

Read all 5 HOME wrappers on Pro fresh; discovered 2 of them (`competitor-monitor-run.sh`,
`yield-optimizer-run.sh`) don't call `claude` directly at all — they route through
`~/scripts/claude-cascade.sh`, itself a 6th undeclared HOME-only file never in repo canon. Reverse-
promoted all 6:

| File | Fix applied |
|---|---|
| `infra/launchagents/wrappers/claude-cascade.sh` (new canon) | BG-ceiling env set once at the shared Claude-tier choke point |
| `competitor-monitor-run.sh` | anti-background prompt sentence + provenance grep of cascade's own log line |
| `yield-optimizer-run.sh` | same |
| `run-nb-curator-mode-c.sh` | BG-ceiling env + anti-background directive + explicit `used: tier1-<model>` log line (direct `claude -p` caller, wr2-ig-metrics precedent pattern); model bumped 4-6→sonnet-5 to match its sibling's 2026-07-03 migration |
| `wr2-contract-test.sh` | same pattern (direct `--print` caller, dormant manual harness, was undeclared) |
| `cron-agent.sh` | BG-ceiling env + anti-background directive + provenance line in `run_agent()` — this one is genuinely LIVE, confirmed via `crontab -l`: 5 real jobs (weekly-dep-audit, seo-guardian-weekly, conversation-cleanup, indexing-daily, learning-pipeline) route through its `agent` tier |

All 6 declared in `infra/home-fork/declared-pairs.json` (machines=[pro]). `bash -n` clean on all 6,
pre-commit hooks (lease-check, secrets scan, prettier, typecheck, python lint, off-limits) all
green. PR #2263 opened + auto-merge armed (`gh pr merge --auto --squash`).

**PENDING-ALIGN (not done this session — read-only investigation confirmed live HOME state, but
sync must happen AFTER merge per mandate)**: once #2263 merges, Pro's `~/scripts/{claude-cascade,
competitor-monitor-run,yield-optimizer-run,run-nb-curator-mode-c,wr2-contract-test,cron-agent}.sh`
need `cp` from the merged canon + `git hash-object` blob-proof. This is the actual arming step —
the code exists on main (soon) but the live cron still runs the pre-fix HOME copy until synced.

## 3. Ledger line ~56 — Mini fly-pg-tunnel architecture decision

**DECIDED + EXECUTED live — RETIRE, not extend.**

Investigated the 2 legacy plists (`com.nuzantara.fly-pg-tunnel`, `.local` variant) still churning
on Mini against `~/.local/bin/fly-pg-tunnel-from-config`. Confirmed a THREE-layer blocker, not a
"just wire it up" gap — extending `install_fly_pg_tunnel.sh`'s `whoami==balizero` guard to Mini
would have armed a supervisor that fails forever:

1. **Mini's `fly` CLI has NO access token at all** — `fly auth whoami` / `fly orgs list` both return
   `"Error: no access token available. Please login with 'flyctl auth login'"`. This is an
   interactive OAuth device-flow, cannot be scripted — hard operator[secret] gate.
2. **Mini's Keychain has no `nuzantara-postgres-readonly` entry** — `security find-generic-password`
   returns `SecKeychainSearchCopyNext: item could not be found`.
3. **Even seeded, headless SSH cannot read a GUI-session Keychain item on macOS** — the exact wall
   already documented in ledger line ~50 (W87 family) for direct Postgres access from Mini.

The `.local` plist was actively churning (`runs=4`, exit code 1, live log spam every cycle:
`"Not authorized to show this organization"` / `"tunnel unavailable for organization personal"`).

**Action taken**: booted out + archived both plists on Mini to
`~/Library/LaunchAgents/.retired-20260711/` (moved, not deleted — verified independently post-move:
file absent from active dir, `launchctl print` returns "Could not find service" for both labels).
Documented the decision + the 3-layer evidence inline in `install_fly_pg_tunnel.sh`'s own header
comment (committed, PR #2263 second commit) so the next reader doesn't re-derive this.

**If Mini access is ever wanted**: needs an operator to run `fly auth login` interactively on Mini
GUI + seed the Keychain entry via a GUI-unlocked session — only then does relaxing the
`whoami==balizero` guard make sense. Not before.

## 4. Ledger lines ~75-78 — mata_garuda Mini instrumentation

**3 organs CONFIRMED still healthy (fresh re-check, not trusting the ledger's old proof) — 1
remains a genuine ARM/RETIRE decision for Zero, evidence gathered, not decided unilaterally.**

Fresh `healer_receptor_registry.py --node mini` run this session: `checked=7 ok=6 never_armed=1`.
The 6 ok include `sentinel_daily`/`intel_bridge_daily`/`normalizer_hourly` — the PR #2090/#2107/#2109
fixes from 2026-07-07/08 are holding, confirmed independently, not re-derived from the ledger's
claim.

The 1 never-armed is `mata_garuda.ner_worker_hourly.mini`. Investigated fresh (the ledger flagged it
as "genuinely unloaded, decide ARM/RETIRE" but hadn't gathered the fuller evidence):

- Its plist has `Disabled: true` **explicitly baked into the XML** (mtime Jun 29) — a deliberate
  flag, not an accidental unload.
- The underlying module IS real and IS registered: `apps/organism/organism/organs_registry.yaml:687`
  declares `mata_garuda.ner_worker_hourly.mini`, and `mata_garuda/workers/ner_worker.py` has a full
  test suite (`test_ner_worker.py`, entity-extraction + coercion tests). This is not orphaned debt.
- Its downstream consumer, `run_kg_linker.py`, has an error path that explicitly anticipates NER
  being dead: `"Upstream entity extractor missing or broken — investigate ner_worker pipeline."` —
  BUT `kg-linker`'s own plist was archived back in May (`.archive-2026-05-09/`), predating
  ner-worker's June 29 disable — so nothing is CURRENTLY consuming NER output, softening urgency.
- Historical run stats (before disable): 1126 total runs logged, mostly `processed:0` (empty
  upstream stream) with occasional real extraction (`processed:50, extracted:13`).

**Recommendation, not decision**: this is a real, tested, tracked component sitting dormant since
2026-06-29 with no current consumer. The ARM/RETIRE call hinges on a roadmap question I can't
answer — is mata_garuda entity-extraction/KG-linking still wanted? — so I'm surfacing the evidence
rather than picking a side.

## 5. Boot-report silences — both FALSE ALARMS, root-caused, no cure needed

**m5.arsenal_probe "silent 31h+"**: Confirmed the heartbeat file genuinely is stale
(`ts: 2026-07-10T05:24:23Z`, ~38h old at check time) — but this is architecturally EXPECTED, not a
failure. `scripts/proprioception.py:435` explicitly scopes the healer-armed arsenal_probe check to
`"machines": ["mini"]` only; `HEALER-MANDATE.md` explicitly says the tool should be read via
`--read-last --json`, never re-launched live, because "the heavy probe is healer-armed on Mini."
M5 has **no LaunchAgent for arsenal_probe at all** — the M5 heartbeat file only exists from a stray
manual session invocation at some point. Confirmed Mini's own heartbeat IS fresh (~19h old,
`2026-07-11T02:23:56Z`), proving the design works as intended on its real target. **No cure
applied — the boot-report's classifier doesn't distinguish "expected staleness on a
non-scheduled machine" from "broken automation."**

**pro.agent_worktree_cleanup "silent 126h"**: Also false. `~/logs/agent-worktree-cleanup.log` on
Pro shows continuous fresh activity through `2026-07-11T00:15:13+0800` — running on its ~16h
schedule as designed, actively reaping expired worktrees (`removed expired worktree
2026-07-10-regulatory`) and correctly protecting 3 unmerged ones (W80 discipline, "protecting
checkout" lines for `regulatory-2026-07-06`, `-pass4`, `watcher-20260706`). Whatever generated the
"126h silent" claim in the boot-report was reading stale or wrong data — the actual log
contradicts it directly.

## 6. Ledger line ~47 — WR2 legacy Canva lane on Pro — evidence report ONLY (as mandated)

Fresh evidence gathered on all 5 Canva launchd labels on Pro (the ledger only named 3; found 2
more). **Nothing booted out, nothing fixed — per mandate, this is a retire-vs-fix matrix for
operator[business] to decide lane scope, not an action.**

| Label | State | Evidence |
|---|---|---|
| `canva-oauth-watchdog` | **HEALTHY** (was broken, now fixed) | `last exit code = 0` — matches the ledger's own line ~68 note that this was "CURATO in questa sessione" (2026-07-07); confirmed independently, still green |
| `canva-renderer` | **ACTIVELY FAILING**, high-confidence 1-line root cause | `last exit code = 2`, churning every 5min (log timestamps 20:03→21:38 same evening). Root cause identified precisely: its `zsh -lc` invocation does `source ~/.nuzantara-secrets.env; exec ...` **without `set -a`/`set +a`** around the source — unlike every other wrapper I read this session (regulatory-watcher, competitor-monitor, etc. all bracket with `set -a ... set +a`). `DATABASE_URL=...` in the secrets file is a bare assignment (not `export DATABASE_URL=...`), so `source`-ing it without `set -a` sets a local zsh variable that never reaches the `exec`'d Python child — explaining `CRITICAL DATABASE_URL not set` exactly. This is a 1-line fix (`source` → `set -a; source ...; set +a`) but I did NOT apply it — Canva lane scope is operator[business] per mandate fence. |
| `canva-apply` | **Never fired since load** (`job state = uninitialized`, log files don't exist) | Plist has NO schedule keys at all (no `StartInterval`/`StartCalendarInterval`/`WatchPaths`) and no `Disabled` key either — it's loaded but has no trigger mechanism visible in the plist itself; something else (eventbus? manual kickstart?) must be its intended invocation path, undetermined this session. |
| `canva-gc.weekly` | **HEALTHY**, working as designed | Weekly Monday 04:30, last fired 2026-07-06. Its "error log" content is actually its own dry-run report format (writes findings to stderr by design) — correctly identified 5 orphan + 10 unpublished-30d+ Canva designs, `[DRY-RUN] pass --apply to actually trash the candidates` — awaiting an operator `--apply` decision (separate matter, not broken). |
| `canva-lease-watchdog` | **HEALTHY** | 299 runs, exit 0 — not part of the "zombie" family the ledger described at all. |

**Matrix for operator decision**: 2 of 5 labels are genuinely healthy zombies-in-name-only
(oauth-watchdog, lease-watchdog); 1 is healthy-and-working-as-designed (gc.weekly, separate
`--apply` decision pending); 1 has a precise, low-risk, single-line fix identified but withheld
per lane-scope fence (renderer); 1 has an undetermined trigger mechanism worth a follow-up look
(apply). The lane is NOT uniformly dead — the ledger's framing ("legacy Canva lane zombies") was
accurate for only 1 of 5 labels at write time (renderer), and even that one is a known, fixable
1-liner, not architectural debt.

## Fleet alignment status

- **Repo**: PR #2263 (2 commits: wrapper reverse-promotion + fly-pg-tunnel decision doc), branch
  `agent/air-m5/ops/fleet-ledger`, auto-merge armed, CI running with zero failures at write-time.
- **Mini**: 2 plists retired live this session (fly-pg-tunnel × 2) — this IS the final state, no
  further sync needed (retirement, not a code change requiring HOME sync).
  `healer_receptor_registry.py --node mini` re-run fresh: 6 ok / 1 never_armed (ner-worker,
  unchanged, awaiting Zero's call).
- **Pro**: NOT yet synced — PR #2263 hasn't merged yet at write-time. Once merged, the 6 wrapper
  files need `cp` from repo canon to `~/scripts/` + `git hash-object` blob-proof (tracked as
  PENDING-ALIGN below).
- **fleet HEAD parity**: not verified post-merge (PR still in flight) — orchestrator should
  re-check `git rev-parse HEAD` across M5/Pro/Mini after #2263 lands.

## LEDGER-DELTA (exact replacement text for orchestrator to reconcile)

Replace ledger line ~61 with:

> - closed 2026-07-11 | 3 exit-127 crons on Pro (`com.balizero.autonomous-lab`, `-runner`,
>   `com.nuzantara.intake-proposal-health-sentinel`) | VERIFIED already retired by a prior session
>   2026-07-08 (archived to `.disabled-codex-cleanup-20260708/`, not by this session) — autonomous-lab
>   pair stays dormant per the separate deliberate ~87 Lab-repoint decision; intake-sentinel's script
>   was NEVER committed to repo canon (genuinely deleted HOME-only artifact) and its resurrection
>   would fabricate logic never seen — NOT re-armed. LIVE FINDING surfaced instead: its last surviving
>   log (2026-06-26) shows it detected `3436 done-rows with only superseded proposals (dead in
>   /review)` before dying, with Telegram alerting ALSO broken (DNS errors) — likely never reached
>   anyone for 15+ days. This is PII-adjacent client-document data (KTP/passport/akta candidates) |
>   operator[business] decides: rewrite+recommit the sentinel, or confirm PR #1587's SSOT fix
>   supersedes it — either way, check current `intake_queue` superseded-orphan count against the
>   3436 baseline first | PROVEN retirement: `launchctl print` on all 3 labels = "Could not find
>   service"; UNRESOLVED: the 3436-row finding

Replace ledger line ~68 with:

> - closed 2026-07-11 | CLASS-AUDIT W89 remaining 5 (competitor-monitor / cron-agent /
>   run-nb-curator-mode-c / wr2-contract-test / yield-optimizer) + 1 newly-discovered
>   (claude-cascade.sh, shared choke-point for 2 of the 5) | ALL 6 reverse-promoted to
>   `infra/launchagents/wrappers/`, declared in `declared-pairs.json` (machines=[pro]), PR #2263
>   (auto-merge armed) | me (sessione M5 worktree) | PENDING-ALIGN:Pro once #2263 merges — `cp`
>   6 files from canon to `~/scripts/` + `git hash-object` blob-proof; cron-agent.sh is LIVE
>   (5 crontab consumers confirmed), the other 5 are mixed live/dormant

Replace ledger line ~56 with:

> - closed 2026-07-11 | Mini fly-pg-tunnel architecture decision | RETIRE, not extend — confirmed
>   3-layer blocker (no fly auth token at all on Mini, no Keychain RO entry, headless-SSH can't
>   read GUI Keychain even if seeded — same W87 wall). Both legacy plists booted out + archived to
>   `~/Library/LaunchAgents/.retired-20260711/` on Mini this session; decision documented inline in
>   `install_fly_pg_tunnel.sh` header (PR #2263 commit 2) | me (sessione M5, live SSH to Mini) |
>   PROVEN: `launchctl print` both labels = "Could not find service"; plists absent from active
>   LaunchAgents dir (independently re-verified post-move)

Replace ledger lines ~75-78 (the still-open tail) with:

> - opened 2026-07-11 | `mata_garuda.ner_worker_hourly.mini` ARM/RETIRE — re-derived fresh
>   evidence (not just re-citing prior session): plist `Disabled:true` explicit (Jun 29), module
>   IS registered in `organs_registry.yaml:687` + has a full test suite (not orphaned code), its
>   downstream consumer `run_kg_linker.py` has an error path anticipating exactly this state but
>   that consumer's OWN plist was archived back in May (predates ner-worker's disable) so nothing
>   currently needs its output. 1126 historical runs, mostly empty-stream, occasional real
>   extraction (50 processed/13 extracted). This is real, tested, tracked, dormant work — the
>   ARM/RETIRE call hinges on whether entity-extraction/KG-linking is still roadmap | operator[business] |
>   decision recorded + either re-enable (`Disabled:false` + `launchctl bootstrap`) or drop from
>   organs_registry.yaml

Add new line (boot-report false-alarms, closed same session they were flagged):

> - closed 2026-07-11 | boot-report silences `m5.arsenal_probe` (31h+) + `pro.agent_worktree_cleanup`
>   (126h) — BOTH FALSE ALARMS | m5.arsenal_probe: no LaunchAgent exists for it on M5 by design
>   (`proprioception.py` scopes the healer-armed probe to `machines:["mini"]` only; M5's heartbeat
>   file is a stray manual-run artifact, staleness between sessions is expected, not broken) —
>   Mini's own heartbeat confirmed fresh (~19h), proving the design works as intended.
>   pro.agent_worktree_cleanup: log shows continuous fresh activity through 2026-07-11T00:15,
>   correctly reaping+protecting worktrees on schedule — whatever generated the "126h silent" claim
>   read stale/wrong data | me (sessione M5, fresh SSH probes both) | PROVEN: log content
>   contradicts the alert directly on both counts; no code cure needed, the alerting classifier
>   itself needs a fix if it's to stop crying wolf (out of this lane's scope, flagging for whoever
>   owns the boot-report generator)

Ledger line ~47 (Canva) stays OPEN as an evidence-only update — replace with the 5-row matrix in
§6 above; no retire/fix action taken (operator[business] fence honored).

## MEM-NOTES

- The `intake-proposal-health-sentinel`'s 3436-row PII-adjacent finding is the single highest-
  priority discovery of this session — surfaced but NOT actioned (correctly, per PII boundary +
  scope). Recommend a dedicated follow-up session cross-checks current `intake_queue` state.
- `claude-cascade.sh` being entirely undeclared HOME-only, despite being a load-bearing shared
  dependency for 2+ wrappers, suggests other "reverse-promote wrapper X" mandates should always
  check X's own `source`/`exec` chain for further undeclared dependencies before considering the
  promotion complete — this session nearly missed it (the ledger line only named the 5 top-level
  scripts, not their shared library).
- `canva-renderer`'s bug (bare secrets sourced without `set -a`/`set +a`) is a distinct, nameable
  pattern worth a scar entry if it recurs elsewhere: "secrets sourced but not exported" — silent
  because `source` succeeds (exit 0) and the failure only surfaces downstream in the child process
  reading `os.environ`. Grep target for a future sweep: `source.*secrets\.env` NOT preceded by
  `set -a` within the same invocation.

## FILES-TOUCHED

- `/Users/balizero/Desktop/nuzantara/.worktrees/ops-fleet-ledger/infra/launchagents/wrappers/claude-cascade.sh` (new)
- `/Users/balizero/Desktop/nuzantara/.worktrees/ops-fleet-ledger/infra/launchagents/wrappers/competitor-monitor-run.sh` (new)
- `/Users/balizero/Desktop/nuzantara/.worktrees/ops-fleet-ledger/infra/launchagents/wrappers/yield-optimizer-run.sh` (new)
- `/Users/balizero/Desktop/nuzantara/.worktrees/ops-fleet-ledger/infra/launchagents/wrappers/run-nb-curator-mode-c.sh` (new)
- `/Users/balizero/Desktop/nuzantara/.worktrees/ops-fleet-ledger/infra/launchagents/wrappers/wr2-contract-test.sh` (new)
- `/Users/balizero/Desktop/nuzantara/.worktrees/ops-fleet-ledger/infra/launchagents/wrappers/cron-agent.sh` (new)
- `/Users/balizero/Desktop/nuzantara/.worktrees/ops-fleet-ledger/infra/home-fork/declared-pairs.json` (edited, 6 new entries)
- `/Users/balizero/Desktop/nuzantara/.worktrees/ops-fleet-ledger/infra/launchagents/install_fly_pg_tunnel.sh` (edited, decision doc)
- `/Users/balizero/Desktop/nuzantara/.worktrees/ops-fleet-ledger/research/operations/2026-07-11-fleet-ledger-burndown.md` (this file)
- Live on Mini: `~/Library/LaunchAgents/com.nuzantara.fly-pg-tunnel.plist` +
  `.local.plist` moved to `~/Library/LaunchAgents/.retired-20260711/`
- PR: https://github.com/Balizero1987/Teman2/pull/2263 (auto-merge armed)
