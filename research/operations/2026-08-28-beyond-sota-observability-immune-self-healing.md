---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 8/13 — Observability, immune system & self-healing
model: claude-fable-5 (pinned lane)
sources: 12
repo_files_verified: 31
status: complete
sections_done: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
---

# Beyond-SOTA 8/13 — Observability, immune system & self-healing

## §0 — TL;DR

- **Position:** AHEAD of SOTA on failure *semantics* (DEAD-GREEN taxonomy, guardian-of-guardians,
  alarm↔cure CI linting — some of it unique), BEHIND on *signal economics* and *actuation*: the
  receptors are saturated (81.2% of ledger rows overdue, escalations median 30 days, 100% of
  strict PENDING-ARMS rows past the 48h horizon) and self-healing covers a sliver of 170 organs.
- **Biggest gap:** the organism cannot compute its own MTTD/MTTR — ten disjoint state formats,
  no incident carries both timestamps; and its alarms are unpriced (34.6% of a month's Telegram
  was ONE unactionable alarm; 28% of Sentry errors dropped for quota; a stale seat snapshot
  injected as live panic).
- **Top-3 moves:** (R1) burn-rate + dual-window math on the receptor surfaces — error-budget
  calculus applied to a debt ledger, which no surveyed system does; (R2) CI schema-handshake
  between every health emitter and its consumers — kills the W120 class structurally; (R4+R5)
  OTP restart budgets for a `supervised` organ class plus one wide-event stream, making FBAR-94%
  autonomy measurable and MTTR computable for the first time.
- **Meta:** the defective belief is *"a signal, once emitted, is information"* — every scar here
  is a consumption contract that silently didn't hold. Price the signal, verify the consumer.

## §1 — How Nuzantara does it today

The organism's health model is built as **sense → judge → act → escalate → enforce**, with a
deliberate asymmetry: sensing is rich and everywhere, actuation is scarce and caged.

**Sensing: proprioception.** `scripts/proprioception.py` (runbook
`docs/runbooks/proprioception-boundary-recon.md`, spec
`docs/specs/proprioception-boundary-recon-v1.md`) is the reconciler-of-reconcilers born from the
2026-07-02 full-system TAC meta-pattern "unreconciled boundaries": every recurring trauma reduces
to a signal emitted on ONE side of a boundary (repo↔$HOME, launchd-exit↔log-content,
produced↔promoted, checkout↔origin) trusted as truth for both sides. It runs the existing
per-boundary reconcilers plus builtins, and its live report
(`~/.nuzantara-proprioception/last.md`, verified 2026-08-28T20:32 on Pro) shows the design at
work: **11 probes, 6 DIVERGED, 0 unprobeable**, every report stamped with `runner_version`,
`config_sha`, `repo_head` and expected-vs-actual probe counts, and — the genuinely unusual part —
**UNWATCHED boundary classes are printed in every report** (`defined<->live`,
`process<->process`, `tunnel<->reachable`): absence is visible, never silent. Three more design
choices worth naming: it is a **signaler, never an actuator** (W33/W81); `guardian_freshness`
makes a stale guardian itself a DIVERGED finding (guardian-of-guardians); and wrapped output that
doesn't match its declared parse schema is classified UNPROBEABLE, never RECONCILED — schema
drift must not normalize into calm. Its consumption point is a SessionStart receptor
(`scripts/hooks/proprioception_sessionstart.sh`) that is **never silent**: fresh+clean → one-line
heartbeat, divergence → copy-pasteable fixes, stale >48h → loud alarm, so silence proves exactly
one thing (hook not registered).

**Judging launchd truthfully.** The `launchd_liveness` probe (W84 family) refuses to read exit
codes as health and classifies each of the 23 current findings with a verdict taxonomy:
`EXPECTED-NONZERO`, `FAILING-HONESTLY`, `DEAD-GREEN`, `ARMED-TO-NOTHING` — i.e., the vocabulary
distinguishes "red and honest" from "green and lying". `launchagent_canon` (#1926) reconciles
three-way (`~/Library/LaunchAgents` ↔ `launchctl` ↔ repo canon): currently 55 findings — 50
`home_fork_target`, 4 `repo_divergent`, 1 broken. The measured surface: **255 live plists on Pro**
(108 `com.nuzantara.*`, 103 `com.balizero.*`, 25 `com.matagaruda.*`, rest third-party) against
**156 committed under `infra/launchagents/`** — roughly 100 live jobs have no repo canon, which is
exactly the family-#1 exposure the probe exists to count.

**Heartbeats, two generations.** Daemons beat into Redis (`infra/eventbus/heartbeat.py`: key
`bz:heartbeat:<daemon>`, TTL 120s, 30s throttle, watchdog Telegrams on >5min silence); organs
beat into JSON sidecars under `~/.organism/last_seen/` — **169 sidecar files** against **170
organs** declared in `apps/organism/organism/organs_registry.yaml` (verified: exactly 170 `- id:`
entries; runtimes 144 `pro_launchd`, 14 `mini_launchd`, 10 `fly_machine`, 2 `air_launchd`; each
organ declares `expected_hb_seconds`, `recovery_action`, `severity_on_silence`, `cicatrix_refs`,
and the file is checksummed). The `organs_heartbeat` probe distinguishes `stale` (frozen sidecar)
from `unhealthy` (breathing but `status=degraded/failed`) — 7 findings today — and its fix hint
encodes doctrine: "read the organ's own log — restart is NOT the cure". `infra/eventbus/cron_log_sentinel.py`
adds zero-touch instrumentation: it tails cron logs for completion markers and emits events
without modifying the cron scripts. Organ *birth* is gated by conformance genes
(`infra/organ-conformance/genes.json`: 10 genes — registry entry, heartbeat sidecar, kill switch,
single-instance, node guard…) with **135 grandfathered** legacy organs and a **one-way ratchet**
(`check_baseline_ratchet.py`: a new organ must be born conformant; a missing-set may only shrink;
"cannot compare" exits 2 because an uncomparable ratchet is not a passing ratchet).

**Acting: the healer, split on an inverted axis.** `docs/runbooks/healer-organ.md` +
`infra/healer/` define two node-scoped healers. The **Mini healer** (launchd every 4h) is the only
autonomous repo writer: a deterministic pre-check (`pending_arms_report.py --strict` +
`proprioception.py --json --no-fetch` + escalations hook) costs zero LLM tokens when healthy;
only actionable findings spawn a headless Sonnet-5 session that cures in-perimeter items
(worktree → PR → auto-merge → prove-live → ledger), max 3 PRs/tick, pidfile anti-overlap,
3300s wall-clock watchdog, kill switch, and a **cure-quality floor**: if the Claude tier is
degraded it does NOT cascade cures to weaker models — it heartbeats `degraded` and exits. The
**Pro healer** (`infra/healer/HEALER-PRO-MANDATE.md`) is constitutionally inverted: it **never
writes the repo** — no worktree, no PR, no `gh` — and cures only local runtime (kickstart of
already-installed LaunchAgents whose sidecar is DEAD, HOME←canon refresh for pairs declared in
`infra/home-fork/declared-pairs.json`), max 3 actions/tick from a whitelist, with registry
semantics that encode intent: `dead`=curable, `never_armed`=arming debt (never resuscitate),
`disabled`=intentional (never touch). Every cure must be **proven by content** (sidecar
refreshed, cmp clean) — never by exit code (W88).

**Escalating.** Three receptors inject state at session boot (escalations board, proprioception,
organism digest — `docs/runbooks/organism-digest.md`, a ≤15-line reader over state that already
exists on disk, migrating none of the ~206 Telegram-sending producers). The board itself
(`shared/escalations_pro.jsonl`) currently holds **14 rows, 0 HIGH, all NORMAL — ages 16.1 to
51.6 days, median ~30 days, zero younger than 7 days** (measured this session from epoch
timestamps; the field is even case-inconsistent, 12 `"NORMAL"` vs 2 `"normal"`). Outbound alerting
is centralized in the Telegram gateway (`docs/runbooks/telegram-notification-gateway.md`), born
2026-07-06 from Zero's "600 messages/day" crisis after a census found **171 tracked executables
calling api.telegram.org directly**: three tiers (`p0` immediate, budget 12/day/machine, 6h dedup;
`digest` spooled to 2 flushes/day; `log` disk-only), fail-visible spooling, and a CI lint
(`lint_tg_direct_senders.py`) that lets the direct-sender family only shrink.
`infra/launchagents/chronic_failure_digest.py` complements delta-only alerting with weekly
consecutive-red streak detection (the W55 suppression-family fix: a job red for many days produces
zero delta after day 1). Sentry exists on the error path but with real holes measured 2026-08-28
(`MEMORY_SENTRY.md`): **28% of errors reaching Sentry are dropped for quota** (753 rate_limited of
2,705 accepted+limited over 7 days on `bali-zero-7p`), while the fleet credential points at
`bali-zero-cf` — an org receiving **zero events**, so any quota probe against it measures zero
forever; and `SENTRY_PROJECT=mouth` was wrong for 205 days, so the frontend build **never uploaded
a sourcemap** (cured per ledger commit 11a3c89a2).

**Seat liveness.** `scripts/arsenal_probe.py` (`docs/runbooks/arsenal-probe.md`) live-probes every
AI seat and classifies **by output content, never exit code** into 11 states (LIVE, AUTH_DEAD,
QUOTA_DEAD, TIMEOUT, …), computes transitions against `prev.json`, writes a healer-compatible
sidecar, and deliberately has no daemon ("no 177th daemon" — W84). Its weakness showed at this
session's boot: 5 seats (`claude`, `agy`, `codex`, `codex-spark`, `qwen-cloud-code`) reported
TIMEOUT from a probe **22h old** — a stale panic snapshot injected as if current.

**Enforcing in CI.** Eight immune workflows verified in `.github/workflows/`:
`immune-enforcement.yml` (executable antidotes for families #1/#2/#4; runs on every PR so it is
"required-safe by construction", with in-job path detection), `watcher-coverage.yml` (set-equality
between every workflow's `name:` and the main-push watcher's declared list),
`alarm-cure-alignment.yml` (an alarm threshold must not sit below its cure's threshold),
`catB-daemon-cron-xor.yml` (hard-fails only the W67 crash-loop signature: bare `KeepAlive=true` +
a schedule key), `organ-conformance.yml`, `main-push-failure-watch.yml`,
`telegram-secret-healthcheck.yml`, `cron-sentry-quota-check.yml`. Executable antidotes exist per
superscar family: `scripts/lint_home_fork.py` (#1, sha-compare of 97 declared pairs),
`scripts/lint_plist_keepalive.py` (#7), `scripts/pending_arms_report.py` (#2 — a pure signaler
over the ledger with PHANTOM-OPERATOR and NATURAL-WAIT classes and a 48h day-precision overdue
rule, declared in-file).

**The receptor that is drowning.** `.claude/skills/modus/PENDING-ARMS.md` is now **2,202,762
bytes**. Measured this session: 594 lines start `- opened`, of which only **244 parse under the
strict canonical grammar** `- opened YYYY-MM-DD | artifact | step | owner | proof` — 366 carry
free-form parentheticals after the date (lane annotations) that the tolerant parser must chase;
452 `- closed` proof lines interleave. Of the 244 strict rows: **244/244 are older than 48h**
(min/median/max age = 3/33/57 days); owners split 45 `me`, 27 `operator[<cat>]`, 4 bare
`operator` (PHANTOM class), 168 other/free-form. The 2026-08-26 retrospective
(`project_receptor_live_mandate_2026_08_26.md`) measured the honest combined number: **476/586
rows overdue = 81.2%** (tech-debt 307 + operator-gated 169). A receptor in which four of five
rows alarm is a receptor no one feels.

**What observability doctrine exists but isn't load-bearing.** `docs/SLO.md` defines availability
targets (99.5% backend), latency percentiles, MTTR <15min, deploy-frequency ≥1/day — **last
updated 2026-04-06** with a "monthly" review cadence, i.e. 4+ months stale, and its "Current"
column self-reports targets already missed (deploy ~2-3/week; backup RTO "Untested" at the time).
`docs/observability/README.md` + `grafana-chains.json` define a Prometheus-textfile export for the
8 MCP workflow chains with cardinality-bounded labels and an explicit Legge-2 rule (error
arguments never become labels) — well-designed, but scoped to one subsystem, and no evidence in
this lane's grounding that a Grafana instance consumes it continuously. Meanwhile
`~/.claude/hooks/` — the control plane every session depends on — carries **35 `.bak` files out
of 64 entries**, and today's proprioception shows 4 of its live hooks DIVERGED from repo canon
(the live copy stale versus `infra/claude-hooks/`).

## §2 — Scars & ledger evidence in this area

This lane's families are #2 (Esiste≠Armato / cron theater — **the largest family in the corpus,
~28 members**), #7 (KeepAlive misconfig), #8 (network flap), #10 (split-brain), plus the alarm-
economics scars. What actually bit, with numbers:

**Family #2 — green ≠ working.** The founding pathology: exit 0 and a loaded plist mask dead
workers. The single richest specimen is **W108** (body verified at `cicatrix-scars.md:876`,
2026-07-28, CURED PR #3420): of twenty NLM cron wrappers, **nineteen failed mute**, for two
*independent* causes — (1) sixteen had `job | tee` under `set -euo pipefail`, so errexit aborted
on the pipeline and the entire alarm branch was dead code on the only path it existed for;
(2) eighteen sent alerts via `curl … >/dev/null 2>&1 || true` inside a token-guard, so in
launchd's token-poor env "didn't fire" and "didn't pass here" were indistinguishable. The
twentieth could not report either: its alarm ran `python3` resolved from PATH *after* sourcing
the venv — **the signaler dies of the disease it signals**. The scar's method GOTCHAs are as
valuable as the trauma: the fake test world first *measured itself* (17/20 mute was wrong — most
wrappers died before reaching the point under test until the fake world got a working venv); the
dev machine was structurally incapable of reproducing the red (a Homebrew python shadowed the
broken venv); and the guard forbidding the Telegram URL string *became* the string it forbade,
resolved by importing the constant from the lint (SSOT, not evasion). The family kept producing:
**W110** (heartbeat wired to the wrong organ), **W118** (`cicatrix-scars.md:59`, P0 STRUCTURAL:
the repo frozen **11 hours** by two causes hiding each other, with **no red check anywhere** —
three merge-queue proxies all lying), **W120** (`cicatrix-scars.md:1166`, 2026-08-21: the probe
watching THIS family read a different JSON key than `pending_arms_report.py --json` emits — **the
family's own sentinel was disarmed and its silence read as good news**), **W104** (`redis-cli`
exits 0 with NOAUTH on stdout), **W74** (reflexion cron-theater), **W81** (built ≠ armed as a
suspended state), **W123** (a `success` run ≠ it armed anything). **W84-tcc-dead** adds the OS
dimension: launchd loses its TCC grant to `~/Desktop`, Unix perms intact — jobs die in a way no
exit code explains; its recidiva (2026-07-08, verified in corpus) is a session running
`tccutil reset All` as "diagnostics", an OS-wide grant wipe that answered "Successfully reset"
— the probe and the nuke share a surface.

**Family #7 — KeepAlive.** W67/W67b: `exec <one-shot>` under `KeepAlive=true` made launchd
SIGTERM-kill healthy children every ~22s (restart storm read as liveness). The 2026-04-29 audit
found 53 LaunchAgents with only 13% correct KeepAlive semantics. Antidotes are now structural:
`lint_plist_keepalive.py` + `catB-daemon-cron-xor.yml`, whose header records the honest residue —
**52 live plists carry BOTH KeepAlive and a schedule** (structurally ambiguous daemon-vs-cron),
93 committed templates of which 45 ambiguous; CI hard-fails only the one proven-deadly signature.

**Family #8 — flap fragility.** W49 (canva watchdog: 98 TimeoutErrors from unretried single
calls), W55 (single-attempt Telegram send drops the alert exactly when the network blips), W32
(InterfaceError uncaught). W55's deeper form became the *suppression family*: delta-only alerting
goes quiet after day 1 of a chronic failure — which is why `chronic_failure_digest.py` exists
(its header names the 32h evolver drift and the 6 stale worktrees this masked).

**Family #10 — split-brain.** W67c (wa-mirror alerting from Mini while Pro ran it), the
mata_garuda 12+1 active-active incident, the NLM feeder split-brain. Antidote settled as
DB-side SSOT (`expected_status`/`assigned_node`) + graceful exit when `node≠hostname` — the organs
registry's `runtime:` field is that antidote generalized.

**Alarm economics — the scars that price signals.** The `alarm-cure-alignment.yml` header records
the canonical incident (2026-08-06): `log_size_watchdog.sh` alarmed at 1 MB, the rotator cured at
10 MB; the *entire observed population* (11 files, 1.1–7.1 MB) lived in the dead zone —
permanently loud, permanently ineligible for the cure. That single script produced **1,798 of
5,202 Telegram events in 29.5 days (34.6%), none actionable**. Half the gap had been found and
fixed once (2026-07-20), and *nothing detected the half left* — the workflow is the missing link
between two files that must agree. Same economics on the Sentry side (2026-08-27/28 memories):
**28% of errors rate-limited for quota** in 7 days; a frontend `logger.warn` shipping an event
per visitor in prod (cured #5096); the fleet quota probe aimed at an org with zero traffic; and
`SENTRY_PROJECT` misnamed for 205 days so sourcemaps never uploaded — every one a variant of
"the meter exists but measures the wrong thing, so its silence or its noise carries no
information".

**Ledger evidence of receptor saturation.** Measured this session (§1): PENDING-ARMS at 2.2 MB;
100% of strict-format open rows overdue (median 33 days); the retro's corrected 81.2% combined
overdue; the escalations board's youngest row 16 days old — against a receptor design whose
premise is a 48h alarm horizon. The receptor-live drain of 2026-08-28 (memory: ~40 PRs merged in
one burst) proves the debt is *drainable* when a mandate targets it — and that nothing structural
yet prevents it re-accumulating. Recurrence verdict for the area: family #2 keeps minting new
members (W104→W108→W110→W118→W120→W123→W126 span 2026-07→08), but the *class* antidotes
(gateway `_alert.sh` with absolute interpreter, guard-pins pytest on every diff, alarm-cure
alignment, watcher-coverage set-equality) each ended their specific sub-class — the recidive land
one abstraction level up each time: from "the cron is mute" to "the alarm's transport is mute" to
"the alarm's *meaning* is wrong" (W120: right outcome watched, wrong key read).

## §3 — World SOTA survey

| System / practice | Source (date acc. 2026-08-28) | Mechanism | Measured effect | Transfers? |
|---|---|---|---|---|
| Google SRE — symptom alerting, golden signals | sre.google/sre-book/monitoring-distributed-systems/ | Page on symptoms not causes; every page urgent+actionable+novel; black-box catches "broken NOW" | "Rote, algorithmic responses should be a red flag" — pages/day bounded by cognitive fatigue | YES — the receptor channel is the pager; same economics apply to injected lines |
| Google SRE Workbook — SLO burn-rate alerts | sre.google/workbook/alerting-on-slos/ | Error-budget burn rate, multiwindow (14.4x over 1h+5m pages; 6x/6h; 1x/3d tickets); short window governs reset | High precision + recall, detection in minutes, reset in ~1/12 of long window | YES — directly, and (beyond) to non-request surfaces: ledgers, heartbeats |
| Kubernetes controllers | kubernetes.io/docs/concepts/architecture/controller/ | Level-based reconciliation: idempotent "if current≠desired make it so"; independent small controllers; API server as truth | Self-heals without history; survives missed events, controller crashes | PARTIALLY — the organs registry IS a desired-state store; the continuous controller is missing |
| Erlang/OTP supervision | erlang.org/doc/system/sup_princ.html | Restart strategies (one_for_one…), restart intensity MaxR/MaxT, escalation upward on budget exhaustion, let-it-crash | Restart loops structurally bounded; failure escalates instead of storming | YES — as a `restart_class` gene + per-organ restart budget in the healer |
| Meta FBAR | engineering.fb.com (2011→2020), atscaleconference.com | Daemons execute remediation workflows off monitoring signals; humans only touch physical parts | **94% of alarms cleared without human intervention**; serves hundreds of internal customers | YES in shape — the healer is FBAR-with-an-LLM; coverage is the gap |
| Netflix chaos engineering | principlesofchaos.org | Steady-state hypothesis, real-event injection, in production, minimized blast radius, **automated continuously** | Confidence in resilience before outages find it | PARTIALLY — CI-side fault injection of the ALARM path (W108 method) is the practical port |
| systemd watchdog | man7.org systemd.service(5) | `WatchdogSec=` + sd_notify WATCHDOG=1; miss → SIGABRT + `Restart=on-watchdog`; `StartLimitBurst` rate-limits | Hang detection (not just crash), kernel-grade | YES conceptually — launchd has no watchdog; the sidecar-freshness probe is the hand-rolled equivalent, minus auto-restart |
| Dead-man switch | healthchecks.io/docs/ | Per-job period+grace; success/start/fail signals; missing ping → alert | "Up" is proven by pings, never assumed | ALREADY re-invented internally (sidecars + `expected_hb_seconds`); the per-job *grace* and duration signals are the missing refinements |
| Observability 2.0 / wide events | charity.wtf/2024/11/19/…, jeremymorrell.dev practitioner's guide, honeycomb.io | ONE arbitrarily-wide structured event per unit of work, single store, query-time analysis (vs 3-pillars) | Cost/query drops; unknown-unknowns debuggable | YES — the organism has ~10 narrow state formats and cannot compute its own MTTR |
| Sentry dynamic sampling | docs.sentry.io/organization/dynamic-sampling/ | Server-side retention priorities: deprioritize health-checks/noise, protect low-volume; metrics computed on ALL events | Quota spent on informative events | YES as strategy (edge-side), given quota is a purchase (Legge 5) |
| PagerDuty SRE Agent (2025) | pagerduty.com/eng/pagerduty-for-ai-…, blog H2-2025 | Agentic loop on AIOps: pulls monitor state, ranks next steps, human approves remediation | Vendor-claimed MTTR cuts 40-70% for LLM triage class | The healer already EXCEEDS this on autonomy (cure-by-PR); behind on data plumbed in |
| incident.io Investigations (2025) | incident.io/blog/5-best-ai-powered-incident-management-platforms-2026 | "AI SRE" teammate auto-investigates, drafts root cause | Claimed ~80% of response automated | Same as above — the differentiator is their unified incident timeline, which we lack |

**The five that matter most.** (1) **Burn-rate alerting** is the only surveyed mechanism that solves
the exact disease measured in §2: a saturated threshold alarm (81.2% of ledger rows "overdue")
carries zero bits; a burn rate re-derives signal from the *derivative* and the dual window gives
fast detection AND fast reset. Google applies it to request SLOs only — porting it to receptor
surfaces (ledger-row-days, heartbeat-silence-days) is unclaimed territory. (2) **Level-based
reconciliation** (K8s) is the philosophical opposite of the organism's edge-based receptors
("what changed since boot?") — and the scars (W118: two causes hiding each other, no red check)
are textbook edge-trigger failures: a missed transition is silence. The organs registry already
stores desired state (`recovery_action`, `expected_hb_seconds`); no loop drives current→desired
continuously. (3) **OTP restart budgets** answer the one fear that keeps the healer's hands tied
(blind-heal loops, W81b's 14 DLQ corpses): MaxR/MaxT converts a restart storm into a bounded
escalation — you get FBAR's 94% autonomy *with* a structural cap. (4) **Wide events** name the
organism's data-model debt: ten narrow sidecar formats mean no query can join detection to
recovery, so MTTD/MTTR are literally uncomputable today (verified: no incident record carries
both timestamps). (5) **FBAR's 94%** is the honest benchmark for "how much of the alarm stream
should ever reach the owner": today's equivalent number is unmeasured, and the one measured slice
(34.6% of a month's Telegram from one unactionable alarm) suggests it is far below.

## §4 — Position vs SOTA

| Sub-dimension | Verdict | Evidence |
|---|---|---|
| Silent-failure semantics (green≠working) | **AHEAD** | `launchd_liveness` verdict taxonomy (DEAD-GREEN / FAILING-HONESTLY / ARMED-TO-NOTHING / EXPECTED-NONZERO) is richer than healthchecks.io's Up/Late/Down — it names *lying-green*, which dead-man switches cannot see (they trust the ping). "Proof by content, never exit code" (HEALER-PRO-MANDATE, arsenal_probe 11-state output classification) is doctrine, not aspiration. |
| Meta-monitoring (guardian-of-guardians) | **AHEAD** | `guardian_freshness` probe; UNWATCHED classes printed in every report; `watcher-coverage.yml` set-equality; ratchet "uncomparable ≠ passing" (`check_baseline_ratchet.py`); provenance-stamped reports (`config_sha`, `repo_head`). No surveyed public system self-accounts absence this systematically. Residual: W120 proved the meta-layer can still read the wrong key. |
| Alert-threshold coherence | **AHEAD (unique)** | `alarm-cure-alignment.yml` — a CI link between an alarm's threshold and its cure's threshold. Born from the 34.6% incident; no surveyed system lints alarm↔remediation agreement. Currently guards ONE pair. |
| Self-healing actuation coverage | **BEHIND** | FBAR: 94% auto-cleared; K8s: continuous idempotent loops. Here: Mini healer max 3 PRs/4h-tick, Pro healer max 3 runtime actions/6h, both fire only on receptor findings (edge, not level); 170 declared organs, `recovery_action` present but unconsumed by any continuous loop; W118 = 11h frozen with zero red checks; wa_mirror sidecar frozen 13d in this morning's report. |
| Restart discipline | **AT (by abstinence)** | "Restart is NOT the cure — read the log" avoids #7 storms, but there is no OTP-style budgeted-restart class either — safe-to-restart organs wait for a session. `catB-daemon-cron-xor` hard-fails only the W67 signature; 52 live plists remain daemon/cron-ambiguous. |
| Alert economics / paging | **AT on plumbing, BEHIND on measurement** | Gateway tiers + P0 budget (12/day) + dedup + 2×digest operationalize "every page actionable"; but precision is unmeasured (acted/ignored untracked), no burn-rate math anywhere, and the 28% Sentry quota drop + zero-traffic-org probe show the meters aren't audited. |
| SLOs / error budgets | **BEHIND** | `docs/SLO.md` last updated 2026-04-06 (monthly cadence promised); no error budget, no burn-rate alert, real SLIs (heartbeat freshness, ledger overdue-days, seat liveness) never formalized. |
| Observability data model | **BEHIND** | ~10 disjoint state formats (`last_seen/*.json`, `arsenal/last.json`, proprioception `last.json`, escalations JSONL, PENDING-ARMS md, tg spool, audit snapshots, DLQ, breakers); MTTD/MTTR uncomputable; the only unified read is the ≤15-line digest. Obs-2.0 says one wide store. |
| Receptor consumption model | **AHEAD (sui generis)** | Session-boot injection (3 receptors, never-silent contract, copy-pasteable fixes) has no SOTA analogue because no surveyed system has an LLM session as its operator console. It converts "dashboard nobody opens" into "context the operator cannot avoid". Its failure mode is saturation — see next row. |
| Receptor signal quality | **BEHIND (own design goals)** | 2.2 MB ledger; 244/244 strict rows >48h (median 33d); retro-corrected 81.2% combined overdue; escalations youngest row 16d against a 48h alarm horizon; arsenal snapshot 22h stale injected as current TIMEOUT panic. Saturated threshold = zero bits. |
| Chaos validation of the immune path | **BEHIND, with a proven local method** | No continuous injection (Netflix principle 4). But W108's fake-world method + `test_nlm_alarm_gateway.py` chaos-test the alarm path of 20 wrappers in CI — ~13% of the 156-plist fleet, done once per autopsy instead of continuously. |
| Hygiene of the control plane | **BEHIND** | 35/64 `.bak` files in `~/.claude/hooks/`; 4 live hooks DIVERGED from repo canon today; ~100 live plists (255 live vs 156 canon) with no tracked source — family #1's standing exposure, counted daily but not shrinking. |

## §5 — Beyond-SOTA recommendations (ranked by impact × confidence / cost)

**R1 — Burn-rate receptors: error-budget math on non-request surfaces (ledger, heartbeats, escalations).**
*What:* give each saturated receptor an explicit budget and alarm on **burn rate with dual
windows**, not on absolute thresholds. PENDING-ARMS: budget in *overdue-row-days per week*;
alarm fires when the fast window (this session vs last) burns >X row-days or the slow window
(14d) trends up — not when the standing stock (476 rows, red for months) merely exists.
Escalations: same, on open-row-days. Organ heartbeats: budget of silence-hours per organ class.
*Why beyond SOTA:* Google's burn-rate machinery (14.4x/6x/1x multiwindow) exists only for request
SLOs; no surveyed system applies error-budget calculus to a tech-debt ledger or a fleet-liveness
surface. It solves the measured disease: a threshold alarm at 81.2% saturation carries zero bits,
while the *derivative* still carries all of them; the dual window gives the fast-reset property
the receptors lack (today a cured board still shows 30-day-old rows forever).
*Asymmetry exploited:* the receptor channel (session boot) is programmable — unlike a human
pager, its consumption behavior can be contract-tested.
*Cost:* ~2 sessions, 1 PR ≤350 lines (`pending_arms_report.py` gains `--budget` mode + hook
formatting; state = one small JSON of window counters). Gear 2.
*Risk:* family #3 (the burn formula is a guard → needs guilt+innocence fixtures both directions);
family #2 if the budget file itself goes stale (antidote already exists: `guardian_freshness`
watches receptor outputs — register the counter file).
*Metric:* signal-change ratio of injected receptor lines (lines that differ from previous
session / lines shown). Today ≈0 (same saturated block every boot, measured §1); target >0.5.
Secondary: median age of ledger rows the receptor *surfaces* (today 33d; target: surfaced set
median <7d).
*Kill criterion:* if after 30 days the burn alarm has fired <2 times while ≥1 real regression
slipped (found by autopsy), the budget constants are wrong — revert to threshold mode and re-tune.
*First PR:* `feat(immune): burn-rate mode for pending_arms_report + receptor` — files:
`scripts/pending_arms_report.py`, `scripts/hooks/*receptor*`, `scripts/tests/test_pending_arms_burnrate.py`.
Acceptance: replaying the ledger's git history through the burn model flags the three known
debt-spikes (2026-07-07 sweep, 2026-08-22 session, 2026-08-26 burst) and stays quiet on the
receptor-live drain day.

**R2 — Schema-handshake genes: CI set-inclusion between every health-state producer and its consumers (kills the W120 class).**
*What:* one registry (`infra/immune-contracts/contracts.json`) where each machine-readable health
emitter (`pending_arms_report --json`, proprioception `last.json`, `arsenal/last.json`, heartbeat
sidecars, escalations JSONL, tg spool) declares its schema (keys + enum domains), and each
consumer (receptor hooks, healer pre-check, digests, fleet-watch) declares the keys it reads. A
pure-python CI lint fails when a consumed key ∉ produced schema, or an enum literal is compared
outside the producer's domain (would have caught both W120 — probe reading a key the reporter
never emits — and this session's live find: `"priority"` values split `NORMAL`/`normal`).
*Why beyond SOTA:* schema registries exist for data pipelines (Avro/Protobuf), and
`alarm-cure-alignment.yml` already links ONE threshold pair; nobody CI-links the *internal
telemetry* handshake of their monitoring stack itself. This composes watcher-coverage's
set-equality + alarm-cure-alignment + genes.json into a general immune gene: **an alarm without a
schema-verified consumer is UNCONSUMED, and CI says so** — the same "absence is visible" move
proprioception made for probes, now made for contracts.
*Cost:* 2 PRs (~250 + ~150 lines), Gear 2. *Risk:* family #3 in the lint itself (over-match on
dynamically-built keys — scope v1 to static literals, declare the rest UNCHECKED, visibly).
*Metric:* consumer-key reads covered by a declared contract / total (baseline this session: ≥2
proven violations — W120, priority-case drift; target 100% of the 6 emitters, violations 0).
*Kill criterion:* if >20% of keys must be declared UNCHECKED (too dynamic), the lint is theater —
stop and redesign around typed emitter libraries instead.
*First PR:* `feat(immune): contracts.json + lint_immune_contracts.py` wired into
`immune-enforcement.yml` (sentinel pattern: every PR, in-job path detection). Acceptance: a
fixture reproducing W120 (probe reads `classification`, producer emits `class`) goes red;
current tree goes green only after the escalations case-drift is normalized.

**R3 — The mute-cron battery: chaos-inject the ALARM PATH of every wrapper class in CI.**
*What:* generalize W108's proven method — a fake world rich enough to reach the failure branch —
into a parameterized battery over `infra/launchagents/wrappers/`: for each wrapper, run it in a
tmp sandbox with a payload forced to exit nonzero and a spool-backed `TG_DRY_RUN=1` gateway, and
assert **the alarm artifact appears** (spool row with `rc` logged), not that strings exist.
Nightly on the fleet for live-env classes; per-PR for wrapper diffs (extend `guard-pins-pytest`).
*Why beyond SOTA:* Netflix injects faults into *production request paths*; healthchecks proves
liveness at runtime but can never prove the failure branch works *before* it is needed. Verified
red-path coverage of the alerting pipeline in CI — per wrapper, exhaustive, pre-deploy — is
practiced nowhere surveyed; W108 built it for one family (20/20 wrappers) and it immediately
found three latent defect classes.
*Asymmetry:* the scar corpus already documents every mute-alarm signature to assert against
(errexit-on-pipeline, `|| true` transports, PATH-resolved interpreters, unguarded `source`).
*Cost:* 2-3 PRs, Gear 2→3 (touches test infra). *Risk:* #3 (W108's own GOTCHAs: assertions must
strip comments, judge artifacts not string absence); #5 if the sandbox leaks into real HOME
(antidote: W96 scar — `Path.home()` must be overridden in the battery by construction).
*Metric:* wrappers with a CI-verified red path / total wrappers (today ≈20/156 ≈ 13%; target
>90%). *Kill criterion:* if a wrapper class needs >30 lines of bespoke fake-world per wrapper,
the wrapper is the problem — route it through the shared `_alert.sh` gateway instead of teaching
the battery its dialect.
*First PR:* `test(immune): parameterized mute-alarm battery for launchagent wrappers, tier 1` —
top-3 wrapper families by plist count. Acceptance: battery red on a fixture wrapper with the
W108 `tee`+errexit signature; green on `_alert.sh`-conformant wrappers.

**R4 — Supervised-restart gene: OTP restart budgets inside the healer for the provably-safe organ subset.**
*What:* add `restart_class: supervised | diagnose_first | never` to the organs registry schema.
For `supervised` organs (stateless, idempotent, scar-clean — start with ~20 of 170), the healers
apply Erlang semantics: sidecar DEAD → `launchctl kickstart` immediately (Pro healer already has
the verb), with a per-organ restart-intensity budget (MaxR=2/MaxT=24h); budget exhausted →
**escalate to diagnose_first** (Telegram P0 + escalation row), never a third restart. K8s-style
level loop: the healer tick reconciles *current sidecars vs registry*, not "what changed since
last tick".
*Why beyond SOTA:* it is not — FBAR and OTP are the SOTA — but the *composition* is: restart
budgets keyed to a scar-referenced registry (`cicatrix_refs` per organ decide the class), with
escalation into an LLM diagnosis session instead of a human queue. FBAR's 94% with OTP's
storm-cap and a brain at the escalation point. Resolves the standing doctrine tension ("restart
is NOT the cure" vs 13-day frozen sidecars) by making the doctrine per-organ instead of global.
*Cost:* 2 PRs (registry schema + healer diff), Gear 3 (healer is currently out-of-perimeter for
itself — the change ships via a normal session, not the healer). *Risk:* #7 (restart storms —
the budget IS the antidote); #10 (node guard gene already prevents cross-node kickstart); #2
(a `supervised` label on a non-idempotent organ — antidote: class requires a named prove-live
command in the registry, refused otherwise by `organ-conformance.yml`).
*Metric:* MTTR for supervised-organ silence — computable once R5 lands; interim proxy: max
sidecar-staleness among supervised organs (today: 13.0d observed on `pro.wa_mirror_freshness_liveness`;
target <12h = 2 healer ticks). *Kill criterion:* any supervised organ restarted twice in 24h
twice in a month gets demoted to `diagnose_first` automatically (the ratchet direction is
demotion-only without a session's PR).
*First PR:* `feat(organism): restart_class gene + healer supervised-kickstart with MaxR/MaxT` —
registry YAML (~20 organs), `infra/healer/*`, conformance test. Acceptance: simulated DEAD
sidecar for a supervised organ is kickstarted once and the third simulated death within MaxT
produces an escalation row, not a restart.

**R5 — The organism wide-event stream: one append-only JSONL that makes MTTD/MTTR computable.**
*What:* a 30-line stdlib helper (`organism_event()`) every immune emitter calls alongside its
existing output: one wide event per verdict/action — `ts, machine, emitter, organ, verdict,
severity, provenance_sha, action, budget_state` — appended to `~/.organism/events.jsonl`
(rotated; redacted via proprioception's existing `redact()`; Legge 2 fields structurally absent).
Consumers stay unchanged; the digest gains two lines it cannot produce today: **MTTD and MTTR per
incident**, joined from detection events and cure events over one stream.
*Why beyond SOTA:* the mechanism is pure observability-2.0 (wide events, single store) — the
beyond part is scope and cost: Honeycomb assumes a SaaS backend and request-shaped work; this is
wide events for a *sovereign, offline-capable immune system* (Law 6) where the query engine is
`python3 -c` and the operator console is a session. No surveyed system does wide-event
observability of its own watchdog layer.
*Cost:* 1 PR helper + 4 adoption PRs (one per emitter), each tiny. Gear 2. *Risk:* #9
(state-schema drift — R2's contract registry covers this stream from birth); #4 (never log
values — enum verdicts only).
*Metric:* % of receptor-visible incidents with computable MTTD+MTTR (today 0% — verified: no
incident record carries both timestamps; W118's "11h" exists only as scar prose; target 100%).
*Kill criterion:* if 60 days in, no decision has consumed the computed MTTR, freeze adoption at
the existing emitters (the stream keeps costing ~0 but earns no expansion).
*First PR:* `feat(immune): organism_event helper + adoption in proprioception` with rotation +
redaction tests.

**R6 — Alert-precision ledger: measure FBAR's 94% for THIS organism.**
*What:* every `p0` Telegram carries a dedup key already; add a weekly digest section listing each
p0 class with *acted / ignored / unknown* — where "acted" is inferred automatically when a
session, PR, cure, or escalation row references the dedup key within 72h (no human tap needed;
Zero may optionally reply a thumbs-down to mark noise). Classes under 50% acted for 4 consecutive
weeks are proposed for demotion to `digest` tier in a PR the Mini healer opens.
*Why beyond SOTA:* PagerDuty/incident.io track acknowledgment by humans; here the *actor is
mostly software*, so precision can be measured against repo/ledger side-effects instead of human
memory — closing the loop Google's "every page actionable" doctrine leaves manual. The 34.6%
incident was found by archaeology; this makes the next one a standing dashboard line.
*Cost:* 1 PR (~200 lines in `tg_digest_flush.py` + gateway key plumbing). Gear 2. *Risk:* #3
(the "acted" inference is a matcher — guilt+innocence fixtures; unknown ≠ ignored, three-valued
by design). *Metric:* the auto-clear/auto-act ratio itself — the organism's FBAR number, today
unmeasured; first honest baseline is the deliverable. *Kill criterion:* if >40% of p0s land in
"unknown" after tuning, the inference is guesswork — drop to manual monthly review of the raw
counts (still better than today's nothing).
*First PR:* `feat(tg-gateway): p0 outcome inference + weekly precision section`.

*Not promoted to headline recs (roadmap items instead):* Sentry probe repoint to the org with
traffic + edge deprioritization of known-noise (pure AT-SOTA adoption of dynamic-sampling
strategy; quota purchase stays Legge 5); hooks `.bak` purge + lint (35/64 today — family #1/#4
hygiene, one CLEAN pass + one guard line in `lint_home_fork.py --discover`); adopt-or-retire
ratchet for the ~100 canon-less live plists (family #1, the mechanism exists — 
`launchagent_reconcile.py` categories + a grandfather list that may only shrink, same pattern as
`check_baseline_ratchet.py`); `docs/SLO.md` refresh-or-demote (a stale SLO doc is negative
information).

## §6 — 90-day roadmap

**Wave 1 (day 0–30) — make the meters honest.**
1. `feat(immune): contracts.json + lint_immune_contracts.py` (R2 first PR) — ≤400 lines, Gear 2.
   Acceptance: W120 fixture red; escalations `NORMAL`/`normal` drift normalized to pass.
2. `fix(sentry): repoint fleet quota probe at the org with traffic; deprioritize known-noise at the edge`
   — config + probe diff, Gear 1-2. Acceptance: probe returns nonzero accepted-count; weekly
   rate_limited% appears in digest (baseline 28%).
3. `chore(hooks): purge .bak sprawl + guard` — delete 35 `.bak` under `~/.claude/hooks/` after
   sha-compare against repo canon (operator-visible list first — some may hold unported fixes,
   exactly the 4 DIVERGED pairs proprioception flags today), add `.bak` detection to
   `lint_home_fork.py --discover`. Gear 2, family #1/#4.
4. `docs(slo): refresh or demote SLO.md` — either re-measure the table or stamp it historical;
   a stale target sheet is anti-information. Gear 1.

**Wave 2 (day 30–60) — restore signal.**
5. `feat(immune): burn-rate mode for pending_arms_report + receptor` (R1 first PR) — Gear 2.
   Acceptance: history replay flags the 3 known spikes, quiet on drain day.
6. `feat(immune): organism_event helper + proprioception adoption` (R5) then 3 adoption PRs
   (healer, gateway, arsenal). Acceptance: digest prints first computed MTTD/MTTR.
7. `test(immune): mute-alarm battery tier 1` (R3) — top-3 wrapper families. Acceptance: W108
   signature fixture red; conformant wrappers green; coverage counter in CI output.

**Wave 3 (day 60–90) — act on it.**
8. `feat(organism): restart_class gene + supervised kickstart with MaxR/MaxT` (R4) — Gear 3,
   ~20 organs. Acceptance: simulated third death within MaxT escalates instead of restarting.
9. `feat(tg-gateway): p0 outcome inference + weekly precision section` (R6). Acceptance: 4-week
   baseline table renders; ≥1 class flagged for demotion or confirmed >50% acted.
10. `chore(launchd): adopt-or-retire ratchet for canon-less live plists` — grandfather the ~100,
    ratchet shrink-only, target −20 in the wave. Gear 2, family #1.

## §7 — Needs-ruling (Legge 5 / operator-only)

- **Sentry quota increase** is a purchase — already ruled owner-only (`MEMORY_SENTRY.md`). The
  roadmap assumes NO purchase; if 28% drop is deemed unacceptable after edge-deprioritization,
  that is Zero's call.
- **TCC re-grants** for DEAD-GREEN launchd jobs (`operator[tcc]`, physical/GUI) — no session can
  cure these; they stay explicitly out of R4's supervised class.
- **Retirement candidates among the ~100 canon-less live plists**: adopting into repo is
  session work; *deleting* live jobs that may embody unrecorded owner intent needs a per-batch
  Zero ack (proposed as a digest line, not a blocking gate).
- **R6's optional thumbs-down flow** asks a minimal behavior of Zero (reply to mark noise);
  works without it, better with it — flagged, not required.

## §8 — Meta-pattern (Gear 3)

The single defective belief generating this lane's findings: **"a signal, once emitted, is
information."** The organism is emitter-rich and contract-poor. Every scar in the area is a
consumption contract that silently didn't hold: the right *transport* (W108: alarm branch
unreachable, interpreter shared with the disease), the right *key* (W120: prober reads what the
reporter never emits), the right *threshold pair* (alarm-cure dead zone: loud forever, curable
never), the right *org* (Sentry probe aimed at zero-traffic `bali-zero-cf`), the right
*freshness* (a 22h-old TIMEOUT snapshot injected as current panic), the right *saturation* (a
ledger where 81.2% of rows alarm alarms for nothing). Each generation of antidote moved one level
up the same stack — transport → schema → meaning → economics — and the recidive followed it up.
The corrective principle, already latent in the best local designs (UNWATCHED lists,
`guardian_freshness`, alarm-cure-alignment) and generalized by R1/R2/R5/R6: **treat every signal
as a two-party contract with a priced budget, and make the absence of a verified consumer as
loud as the absence of a probe.** Second-order observation: classical SRE prices alerts in human
attention; here the scarce resource is *session context at boot* — the receptors re-discovered
alert fatigue in a new medium. The organism's structural advantage is that its "on-call
responder" is programmable: perfect acknowledgment, verification and action on every alert is
actually achievable — but only if signal volume respects the context budget, which is exactly
what burn-rate receptors and the precision ledger enforce.

## §9 — Sources

1. Google SRE Book, "Monitoring Distributed Systems" — https://sre.google/sre-book/monitoring-distributed-systems/ (acc. 2026-08-28). The canonical symptom-vs-cause, golden-signals, page-actionability doctrine.
2. Google SRE Workbook, "Alerting on SLOs" — https://sre.google/workbook/alerting-on-slos/ (acc. 2026-08-28). The multiwindow multi-burn-rate method with exact thresholds (14.4x/6x/1x).
3. Kubernetes docs, "Controllers" — https://kubernetes.io/docs/concepts/architecture/controller/ (acc. 2026-08-28). Level-based reconciliation as the reference self-healing model.
4. Erlang/OTP System Documentation, "Supervision Principles" — https://www.erlang.org/doc/system/sup_princ.html (acc. 2026-08-28). Restart strategies, MaxR/MaxT intensity, escalation-on-exhaustion.
5. Meta Engineering, "Making Facebook Self-Healing" (2011) + "How Facebook keeps its large-scale infrastructure hardware up and running" (2020) — https://engineering.fb.com/2011/09/15/data-center-engineering/making-facebook-self-healing/ · https://engineering.fb.com/2020/12/09/data-center-engineering/how-facebook-keeps-its-large-scale-infrastructure-hardware-up-and-running/ (acc. 2026-08-28). FBAR remediation-workflow architecture; the 94% auto-clear figure via Meta's At-Scale talk (https://atscaleconference.com/software-and-hardware-remediations-at-meta/).
6. Principles of Chaos Engineering — https://principlesofchaos.org/ (acc. 2026-08-28). Steady-state hypothesis, continuous automated experiments, blast-radius minimization.
7. systemd.service(5) man page — https://man7.org/linux/man-pages/man5/systemd.service.5.html (acc. 2026-08-28). `WatchdogSec`/sd_notify keep-alive, `Restart=` policies, `StartLimitBurst` restart rate-limiting.
8. Healthchecks.io documentation — https://healthchecks.io/docs/ (acc. 2026-08-28). The dead-man-switch model: period+grace, start/fail signals.
9. Charity Majors, "There Is Only One Key Difference Between Observability 1.0 and 2.0" (2024-11-19) — https://charity.wtf/2024/11/19/there-is-only-one-key-difference-between-observability-1-0-and-2-0/ ; with Jeremy Morrell, "A Practitioner's Guide to Wide Events" — https://jeremymorrell.dev/blog/a-practitioners-guide-to-wide-events/ (acc. 2026-08-28). Wide events / single-store doctrine from its originators.
10. Sentry docs, "Dynamic Sampling" — https://docs.sentry.io/organization/dynamic-sampling/ (acc. 2026-08-28). Server-side retention priorities; deprioritizing health-check noise; metrics computed on all received events.
11. PagerDuty, "PagerDuty for AI: How the SRE Agent Triages AI Incidents" + H2-2025 release notes — https://www.pagerduty.com/eng/pagerduty-for-ai-how-the-sre-agent-triages-ai-incidents/ · https://www.pagerduty.com/blog/product/product-launch-2025-h2/ (acc. 2026-08-28). The 2025 commercial state of agentic incident response.
12. incident.io, "5 best AI-powered incident management platforms" (2026 ed.) — https://incident.io/blog/5-best-ai-powered-incident-management-platforms-2026 (acc. 2026-08-28). Investigations ("~80% of response automated") — vendor-primary for the competing claim.
