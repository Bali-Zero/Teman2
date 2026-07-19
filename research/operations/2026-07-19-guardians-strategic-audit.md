---
date: 2026-07-19
domain: operations
adversarial_review: kimi-k3
client_case: none — infrastructure strategic audit (TRACK GUARDIANI, Twin-Fable Pro leg)
sources:
  - "Workflow run wf_7574ebc1-893: 20 agents, 5 domains, 2,417,907 subagent tokens, 510 tool calls, 0 agent errors (~17.5 min wall)"
  - "Cross-family verify: Kimi K3 (kimi-code/k3) refuter on 15 top findings (12 in-run + 3 re-run by the final gate after placeholder detection)"
  - "Live same-day confirmation: 4 weekly launchd jobs SIGKILL/CODESIGNING-killed at their 08:00 Sunday fire, classified severity=info by sentinel-aggregate, recovered via kickstart at 17:20 with content-proven output"
---

# TRACK GUARDIANI — strategic audit of the organism's guardians

> Twin-Fable claim: `TRACK GUARDIANI claimed by Pro/2026-07-19` (ledger:
> `.claude/skills/modus/PENDING-ARMS.md`). The M5 twin owns the disjoint TRACK
> PRODOTTO; handoff is merged artifacts only.

## Mandate & method

Map every guardian/monitor/sentinel of the organism, classify each one's
**judgment basis** (proxy vs content vs mixed), estimate its **lie risk**
(false-green / false-red / coverage gap) with `file:line` evidence, and refute
the top findings cross-family (W100: same-family agreement certified 7
false-clean of 8 in the KBLI program — never again).

Fan-out: 5 domain lanes (launchd-organs, proprioception, ci-gates,
arsenal-seats, cron-sentinels), each lane = Sonnet readers with mandatory
on-disk evidence, top-3 findings per domain refuted by Kimi K3 on fresh
context. Final gate (this document): every load-bearing citation re-executed
on disk by Fable before signing; 4 verify-lane placeholders detected and
re-verified by hand (see §Run defects).

**Census: ~46 guardians classified.** Verdict distribution: the organism's
monitoring plane is overwhelmingly **proxy-based** where it matters most
(launchd), with genuine content verification existing but opt-in and almost
unadopted (3 of 127 launchd organs declare `output_artifact`).

## The lived proof (same day, same disease)

The audit's headline was confirmed **empirically during the audit itself**:

- 08:00 Sunday fire: `com.matagaruda.weekly-digest`, `nlm-expander.weekly`,
  `wr2.reflexion.weekly`, `wr2.voyager.weekly` all SIGKILL-killed at spawn
  (OS_REASON_CODESIGNING wave — brew python upgrade invalidated launchd LWCR).
- `sentinel-aggregate.py` classified all four as `status=exit_drift,
  severity=info` (`scripts/sentinel-aggregate.py:439-456`) — **no escalation**
  (`_ESCALATE_STATUSES = ("dead","starved")`, line 532).
- No guardian anywhere in the codebase could name the kill reason: **zero**
  `log show` / OS_REASON readers exist (repo-wide grep, verified in-run).
- Cure: manual `launchctl kickstart` at 17:20 → all four exit 0 **with
  content-proven output** (digest sent `tg_ok=True` 80 items; nlm-expander
  `sent=True`; reflexion/voyager honest empty runs). The lost weekly run was
  recovered ~9.5h late, found only because this audit was running.

## Findings by domain

Severity legend: **H** = structural false-green/false-red on a live surface;
M = coverage/latency gap; L = documented tradeoff or positive control.

### 1. launchd-organs (11 guardians, 6H) — the deepest blindness

| Guardian | Basis | Finding (evidence) | Sev | Verify |
| --- | --- | --- | --- | --- |
| `launchagent-state-bridge.py` | proxy | `build_receipt()` derives status purely from `{pid, exit_code}` (`:601-616`, `HEALTHY_EXIT_CODES={0}` `:24`); never opens a log. DEAD-GREEN (exit 0, worker never ran) written `status=ok`. | H | Kimi FLAWED→sharpened: daemon branch `ok iff pid is not None` (:612), non-daemon `ok iff exit==0` (:615), interval_job `ok iff pid OR exit==0` (:604-608) — the corrected per-branch claim stands; original "all three branches identically" overreached. |
| `organism_stale_detector.py` | proxy | Freshness-only + echoes payload `status` (`:232-310`, `:313-368`); self-declared "reads the breath, not the pulse" (`:16-17`). A fresh+ok sidecar written by the bridge's proxy lie is 100% invisible → the compound mechanism by which DEAD-GREEN reaches the SessionStart board with zero alarms. | H | Kimi SOUND (conditional on upstream bridge lie — which is confirmed). |
| `launchd_liveness_detector.py` | mixed | The purpose-built W84 cure has (1) residual false-green: `marker=None` + exit 0 → OK (`_classify()` `:404-450`; a plist without StandardOut/ErrorPath makes markers permanently None); (2) **distribution silo**: `_send_telegram` only (`:562-584`) — never writes `~/.organism/alerts/open.jsonl`, so even a caught DEAD-GREEN misses the board every session reads. | H | Kimi SOUND. |
| `audit_launchd_crons.py` | mixed | `REAL_ERROR_PATTERNS` (`:33-45`) contains **no TCC/codesigning marker**; the literal W84 phrase matches neither real-error nor noise lists. Blind spot propagates as *trusted* silence (stale-detector treats its exit-1 as "a true report"). | H | in-run evidence, cited lines re-read at gate |
| `verify_connectome.py` launchd probe | proxy | Label-loaded grep only (`:237-247`); exit-code check opt-in (`bad_exit_ok` default true). The "guardian of guardians" is weaker than the bridge — and is a self-documented prior W84 corpse. | H | in-run evidence |
| **repo-wide** | — | **NO guardian reads launchd's kill reason.** Zero `log show`/`OS_REASON`/`LastExitReason` consumers in `scripts/*`. Every parser reduces launchd state to a bare exit int. A spawn-time CODESIGNING kill writes nothing → reason categorically unrecoverable by the organism today. | H | grep verified in-run + lived proof above |
| `sentinel-aggregate.py` A2 | mixed | The one genuine content check (`_progress_value` sha256 of `output_artifact`, `:125-162`) is **opt-in: 3/127** launchd organs declare it, 0 declare `progress_field`. 97.6% fall back to proxy. | M | in-run evidence |
| `cron-wrapper.sh` | proxy | `STATUS=ok iff exit==0`; output content inspected only on the failure branch (`:192-195`, `:207-250`) — W74 cron-theater shape on every wrapped job's success path. | M | in-run evidence |
| `job_health.py` | proxy | Inherits cron-wrapper's proxy one layer removed (`:100-133`). | M | — |
| `wr2_plist_watchdog.sh` | proxy | file-exists + `launchctl print` success only (`:119-144`); loaded-but-dead reads healthy. | M | — |
| `fly-restart-loop-detector.sh` | mixed | **Positive control**: judges monitored apps via real Fly API JSON (`:103-120`); own-health/findings channels deliberately separated (`:11-16`). Template for the bridge cure. | L | — |

### 2. proprioception (10 probes, 3H) — whitelists that contradict the wrapped tools

| Probe | Basis | Finding (evidence) | Sev | Verify |
| --- | --- | --- | --- | --- |
| `launchd_liveness` wrap | mixed | **`ok_values` includes `NOT-LOADED`** (`proprioception.py:430`) while the wrapped tool's own `ALARM_VERDICTS` includes it (`launchd_liveness_detector.py:559`) and `_disabled_verdict` already converts operator-disabled → DISABLED first — any surviving NOT-LOADED is a genuine exists-but-not-loaded failure, silently absorbed at the drop-path `:353`. Contradiction present since the organ's first commit (808809e) and survived the targeted alignment fix #2763 whose own comment says "keep aligned with the detector's own alarm semantics". | H | Kimi SOUND (re-run by gate; in-run verdict was a placeholder) |
| `launchagent_canon` wrap | mixed | **`ok_categories` includes `present_not_loaded`** (`:441`) — the category `launchagent_reconcile.py:551` literally labels "(Esiste≠Armato)". Same real-world condition invisible through BOTH dedicated probes. | H | Kimi SOUND (same re-run) |
| `guardian_freshness` | proxy | mtime-only (`:301`), zero content sniff — contradicts the organ's own W88 docstring; **and** all 4 registry items lack `required: true` (`:409-414`), so a guardian that never produced output even once is silently skipped (`:296-299`) — the Esiste≠Armato blind spot inside the organ built to catch it. | H | Kimi SOUND (confirmed `required` flag exists but is never set anywhere) |
| `home_fork_scripts` | content | sha256 compare is sound; **coverage gap**: only declared pairs — never invokes `lint_home_fork.py --discover`, so a fresh undeclared HOME-fork is invisible (family #1's dominant shape). | M | in-run evidence (verdict placeholder; evidence lines re-read at gate) |
| `git_alignment` | content | fetch failure swallowed → behind-count vs stale origin can produce false RECONCILED offline (`:173-185`). | L | — |
| `docs_sync` wrap | proxy | `parse="exit_code"` discards the content diff docs_sync already computes; `--json` mode exists unused; findings hardcoded 0/1 (`:334-336`). | L | — |
| `arsenal_seats` wrap | content | Honest reader-not-prober (documented); QUOTA_DEAD/SHED/TIMEOUT whitelisted by design — extended quota-death visibility depends on healer Telegram only. | M | — |
| `organs_heartbeat` wrap | content | Sound wiring; residual risk lives in the wrapped tool's `KNOWN_BENIGN_FAILED` hand-list (see cron-sentinels). | M | — |
| SessionStart receptor | mixed | Pure reader, honest-loud staleness alarm (48h mtime gate); the organ's declared "v1 has NO cron" debt means freshness depends on manual runs. | M | — |

### 3. ci-gates (10 guardians, 2H) — the meta-verifiers miss their own surfaces

| Guardian | Basis | Finding (evidence) | Sev | Verify |
| --- | --- | --- | --- | --- |
| `check_guard_conformance.py` | mixed | (1) `main()` wires **5 of 6** registry surfaces — `tg-gateway-lint` never referenced anywhere in the 358-line checker (0 grep hits); (2) `is_armed()` ancestor-substring fallback (`:124-134`) reports `premise_gate` ARMED though its test filename appears in **zero** workflow files. | H | Kimi SOUND |
| `verify-the-verifiers.yml` sentinel | proxy | Hand-listed path regex (`:54-55`) omits `p3-sandbox-gates.yml` and `adversarial-review-gate.yml` — both registered `ci_workflow` targets in `verify_the_verifiers_gates.yaml` (`:156,169,482`). A PR editing only those two files gets `run=false` + "sentinel success" with the meta-verifier never invoked. | H | Kimi SOUND (re-run by gate; in-run finding field was a placeholder) + gate grep this turn: 0 hits in the sentinel regex |
| `check_lint_script` | proxy | `_consumer_runs_script()` = bare basename substring in consumer full text (`:213-241`) — a comment or dead branch reads ARMED. | M | Kimi SOUND |
| `check_ci_workflow` | mixed | Verifies the `continue-on-error` flag (declared intent), not the step's actual command; first-substring-match step anchor, no uniqueness guard (`:171-210`). | M | — |
| `immune-enforcement.yml` sentinel | proxy | Hardcoded case-list + separate test-loop list: a new antidote script not added to BOTH is silently skipped (self-acknowledged `:11-16`, unclosed). | M | — |
| Local dead-man's-switch cron | mixed | `com.nuzantara.verify-the-verifiers.plist` executes from the **undeclared HOME-fork checkout** `~/nuzantara-deploy` (byte-identical today, but absent from `declared-pairs.json` → `lint_home_fork.py` does not watch it). The "33/33 gates ARMED" log is sourced from an unmonitored fork. | M | — |
| `.husky/pre-commit` lease-check | mixed | fail-open on Redis outage (self-documented `:73`). | L | — |
| `prepush_classify.py` + pre-push | content | **Positive control**: fail-closed allowlist v2, errexit-immune RC capture (the exact W101 antidote), traversal rejection. Reference-quality. | L | — |
| PENDING-ARMS smoke/strict-phantom | proxy | Text-structure check of a hand-written ledger — cannot verify an ARMED claim against system state (by design; over-trust risk only). | L | — |
| pre-commit FastAPI import gate | mixed | `ModuleNotFoundError` substring downgrades to WARN — cannot distinguish "my venv lacks a dep" from "this commit broke the import". | M | — |

### 4. arsenal-seats (6 guardians, 1H) — the newest organ inherits old diseases

| Guardian | Basis | Finding (evidence) | Sev | Verify |
| --- | --- | --- | --- | --- |
| PONG live gate | mixed | `live = "PONG" in res.stdout` bare substring on **all four** CLI probes (`arsenal_probe.py:368,405,424,450`), computed first and unconditionally — PONG inside a CoT trace/refusal/prompt-echo classifies LIVE before any negative pattern runs. The file itself applies word-boundary discipline ("scar #3: match the entity, not the substring" `:174-176`) on the negative path only. | H | Kimi SOUND — fix all 4 sites uniformly, negative-patterns-first or last-line-exact |
| `compute_transitions()` | proxy | `if old is not None and old != status` (`:601-610`) — a seat **born dead** on its first-ever probe produces no transition → healer Receptors 5/D never alert. Kimi's first probe on each machine today had exactly this window. | M | Kimi SOUND |
| healer 20h age-throttle | proxy | up to ~20h death-to-detection latency; documented tradeoff. | L | — |
| M5 scope exclusion | proxy | `guardian_freshness` arsenal item + `arsenal_seats` wrap both scoped `["mini","pro"]` (`proprioception.py:413,472`) — **M5 has zero automated arsenal coverage while `agy` is REQUIRED only on M5** (`arsenal_probe.py:89`). Esiste (in taxonomy), mai Armato (never watched). | M | Kimi SOUND |
| deepseek retirement drift | content | deepseek still in `ALL_SEATS` + `REQUIRED_SEATS["pro"]` while the retirement research doc is landing — if policy lands without the atomic code change, seat settles at BALANCE_DEAD (not whitelisted) → permanent P1 noise on both machines → desensitization (family #9 shape). Not CI-gating (CI runs offline tests only). | M | in-run evidence |
| `write_heartbeat()` degraded field | content | **Verified sound**: probe-ran status vs seat-health `degraded` carried separately; stale-detector correctly never reads `degraded` — "a dead AI seat is a finding, not a monitor failure". | L | — |

### 5. cron-sentinels (9 guardians, 2H) — info-severity SIGKILL and fabricated events

| Guardian | Basis | Finding (evidence) | Sev | Verify |
| --- | --- | --- | --- | --- |
| `sentinel-aggregate.py` exit_drift | mixed | Any non-zero non-graceful `last_exit` **including -9/SIGKILL** on a cron/daemon organ with non-critical `severity_on_silence` → `status=exit_drift, severity=info` (`:439-456`); escalation fires only for dead/starved (`:532`). **Confirmed live**: today's 4 CODESIGNING-killed weeklies sat at severity=info, unescalated, logs frozen since 07-12. | H | Kimi SOUND (re-run by gate; in-run verdict was PENDING placeholder) + lived proof |
| `launchagent-state-bridge.py` | proxy | (cross-listed from domain 1 — the root that every sentinel downstream consumes as if it were content) | H | Kimi SOUND |
| `organism_stale_detector.py` 7d flat | proxy | `DEFAULT_STALE_DAYS=7` (`:66`) == weekly cadence → by-construction false-red on every weekly organ every Sunday scan (live: weekly_digest age 7.4d flagged stale while healthy). **Outlier**: both sibling guardians already do per-organ cadence (sentinel-aggregate `expected_hb_seconds`; nuzantara-sentinel `staleness_threshold_s`). | M | Kimi SOUND |
| `cron_log_sentinel.py` | proxy | Regex hit → publishes `content.draft.ready` with **hardcoded fabricated fields**: `slides_path=/tmp/none, slide_count=0, status=pass` (`:74-91`, patterns `:112-134`) — a synthetic "pass" regardless of what the log line said, plus family-#3 substring triggers. | M | in-run evidence |
| `dlq_autopilot.py` corpse-sweep | mixed | **Verified sound & live** (W81b antidote works): runs every 30 min, sweep unconditional first step, fail-closed freshness gate behaving correctly on all 16 live TERMINAL entries. | L | — |
| `auth_sentinel.py` | mixed | Most probes genuinely content-based (positive exception); but `probe_drive()` returns OK on **file-existence of the delegate watchdog script** (`:175-182`) — a dead watchdog cron + expiring Drive token sails through all auth layers. | M | in-run evidence |
| `sentinel_meta_watchdog.sh` | proxy | Ignorant of `HEALING_DISABLED_FILE` → would alert+kickstart against an intentional operator pause (latent). | L | — |
| `KNOWN_BENIGN_FAILED` allow-list | proxy | 8 organ_ids suppressed by bare id, not (id, expected-reason) — a NEW real failure on a suppressed organ hides behind the old exemption (self-warned `:170-173`). | M | — |
| `nuzantara-sentinel.py` | mixed | Sound on its own merits (per-job cadence, log-enriched errors); inherits the bridge's proxy lie for bridge-fed jobs. | L | — |

## §Meta-pattern (the malattia-delle-malattie)

**One defective belief generates nearly every finding: "launchd's opinion of a
job is the job."** The organism reduces launchd's rich state to `{pid,
exit_code}` at the bridge, then every downstream layer (stale-detector →
aggregate → proprioception → SessionStart board) **consumes that proxy as if
it were content**, adding freshness checks but never re-grounding in the job's
actual output. Three corollaries:

1. **Trust compounds down the chain.** Each guardian trusts the layer below
   ("its exit-1 is a true report", "the sidecar's status field is real"), so
   one proxy lie at the base propagates as *certified silence* to the one
   surface every session reads. The chain has no content re-entry point.
2. **The whitelists encode the disease.** `NOT-LOADED` and
   `present_not_loaded` — the wrapped tools' own alarm categories, one of them
   literally labeled "Esiste≠Armato" — are whitelisted by the reconciliation
   organ built to catch Esiste≠Armato. `KNOWN_BENIGN_FAILED` and info-severity
   SIGKILL are the same move: exceptions declared once, by id or by class,
   never re-verified against the reason they were granted.
3. **Content verification exists but is opt-in, and opt-in ≈ never.** The A2
   `output_artifact` mechanism (3/127 adopted), `docs_sync --json` (unused),
   `lint_home_fork --discover` (never invoked by proprioception),
   `bad_exit_ok:false` (default off) — every content pathway the organism
   built is behind a flag someone must remember. The proxy path is always the
   default. **The cure that isn't the default is Esiste≠Armato applied to
   cures.**

Second-order meta: **the guardians' own discipline (scar #3 guilt+innocence,
W88 content-over-proxy) is applied on the negative/blocking path but not the
positive/ok path** — arsenal_probe word-bounds its death patterns but
substring-matches its live signal; proprioception blob-compares the ledger but
mtime-checks its guardians. The organism guards against false alarms far more
rigorously than against false calm — and false calm is the fatal direction.

## Cure plan (3 waves, prioritized by rendimento/blast-radius)

**Wave 1 — surgical, high-yield, single-PR-sized (owner: next infra lane):**

1. `sentinel-aggregate.py`: negative-signal exits (SIGKILL et al.) become a
   distinct always-escalated status, never `exit_drift/info`.
2. `proprioception.py`: drop `NOT-LOADED` from ok_values (:430) and
   `present_not_loaded` from ok_categories (:441) in ONE PR with a regression
   test pinning both to the wrapped tools' alarm semantics.
3. `launchd_liveness_detector.py`: on `exit_code<0` with `marker=None`, probe
   `log show --predicate ... OS_REASON --last 1h` and surface the reason; also
   write findings to `~/.organism/alerts/open.jsonl` (kill the Telegram silo).
4. `arsenal_probe.py`: flip PONG precedence on all 4 sites (negative patterns
   veto live) + guilt/innocence tests for PONG-inside-refusal and
   PONG-inside-CoT.
5. `verify-the-verifiers.yml`: derive the sentinel path list from every
   `ci_workflow` target in gates.yaml (kills the hand-list drift class, not
   the instance).

**Wave 2 — structural alignments:**

6. `check_guard_conformance.py`: iterate `registry['surfaces'].keys()`
   generically (covers tg-gateway-lint); exact-path `is_armed()`.
7. `organism_stale_detector.py`: per-organ stale threshold (reuse
   `expected_hb_seconds`), retire the flat 7d.
8. `proprioception.py guardian_freshness`: content sniff (parses + expected
   key) + `required:true` on machine-scoped guardians.
9. Bridge: content cross-check for the ~90 bridged labels against
   liveness-detector verdicts (template: fly-restart-loop-detector's
   separation).
10. Declare `~/nuzantara-deploy` pair in `declared-pairs.json`;
    `compute_transitions` synthetic NEVER_PROBED baseline; deepseek retirement
    lands code+doc atomically.

**Wave 3 — adoption programs (bigger than one PR):**

11. `output_artifact`/`progress_field` adoption drive: 3/127 → the 5
    CORE_ORGANS + the ~90 bridged organs with structured logs.
12. `cron_log_sentinel.py` redesign: no fabricated event fields — real
    producers publish real events.
13. M5 arsenal coverage via SessionStart-hook path (no daemon needed).
14. `KNOWN_BENIGN_FAILED` → (organ_id, expected_reason) pairs.

## §Solo-operatore

- **TCC grants** (famiglia W84): any DEAD-GREEN whose root is a lost
  Full-Disk-Access grant needs System Settings by hand — the audit found the
  *visibility* gap curable in code, the *grant* itself is operator-only.
- **Business call on weekly-digest email leg**: today's recovered digest shows
  `email_ok: False` by config — whether the email leg should be armed is a
  Legge-5 product decision, not a bug.
- Everything else in the cure plan is session-executable (no phantom-operator
  lines; wave items carry owners in PENDING-ARMS).

## Adversarial review

Seat: **Kimi K3** (`kimi-code/k3`, Moonshot — cross-family vs the Claude-family
author and reader lanes, per W100). 15 top findings refuted on fresh context:
12 inside the workflow run (one per-domain verify lane, top-3 per domain) and
3 re-run by the final gate after placeholder detection (see §Run defects).
Outcome: 14 SOUND (several sharpened with additional evidence — e.g. the
proprioception drop-path `:353`, exact gates.yaml line ranges, `exit_drift`
appearing only in a summary counter at `:585`), **1 FLAWED** — the bridge
finding's "all three branches identically" claim was refuted and replaced with
the per-branch corrected version now in the table (daemon `ok iff pid`,
non-daemon `ok iff exit==0`, interval_job `ok iff pid OR exit==0`). One
honest scoping note on the SIGKILL finding (a killed job with heartbeat
tracking could still escalate later via the `starved` axis) is recorded in
the finding as-is. Verdicts were treated as leads: every line the review
attacked or blessed was re-read on disk by the author before signing (W65).

## Run defects (meta-honesty — the orchestration's own scars)

- **4 of 15 verify-lane verdicts came back as literal placeholders**
  (`"test"`, `"PENDING — awaiting Monitor notification"`): the verify stage
  for those items never actually ran its refuter. Detected at the final gate
  by reading the raw run output (never trust a verdict field you haven't
  read — W65 applied to the harness itself). All 3 HIGH-severity orphans were
  re-verified by a fresh Kimi K3 call at the gate (all SOUND); the 4th (M
  coverage-gap) ships on its re-read evidence lines. Amendment filed in
  `.claude/skills/modus/AMENDMENTS.md`: workflow verify lanes must
  schema-forbid placeholder verdicts (min-length + enum) so a skipped refuter
  is a visible error, not a quiet "SOUND"-shaped hole.
- One lane self-reported it could not verify a downstream consumer
  (cron_log_sentinel) — honest scope declaration, kept as-is.

## Twin handoff (TRACK PRODOTTO, M5)

Client-facing corners consuming organs whose guardians this audit found
blind: the WR2 queue (cron_log_sentinel fabricated `content.draft.ready`),
anything gated by the weekly organs (digest/reflexion/voyager — silent
SIGKILL class now proven), and Drive-token-dependent intake
(`probe_drive` file-existence lie). The PRODOTTO track should treat "organ is
green" claims about these surfaces as UNVERIFIED until Wave 1 lands. Meeting
point: merged artifacts only.
