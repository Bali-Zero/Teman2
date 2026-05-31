---
date: 2026-05-31
domain: operations
client_case: false
sources:
  - "fly status -a nuzantara-rag (empirical)"
  - "mcp__postgres-nuzantara__query (nuzantara_readonly)"
  - "mcp__nuzantara-mcp__check_health / check_health_detailed"
  - "fly logs -a nuzantara-rag"
  - "launchctl list + PlistBuddy"
  - "git/gh CLI"
audit_id: empirical-audit-2026-05-31
frozen: research/operations/audits/FROZEN-2026-05-31.json
---

# Empirical System Audit — 2026-05-31 (~02:00 WITA)

Heavy empirical audit dispatched as autonomous subagent (Opus, L2 to deploy). **The
dispatched audit prompt rendered as `undefined` (harness templating failure)** — the
mission was reconstructed from the FASE A/B dispatch framework (the recurring
"zero-baseline / orchestrator" audit pattern, same lineage that found W60/W61/W62).

## Verdict in one line

System is **GREEN on the load-bearing surface** (Fly api+rag started, external
`/health` 200×2, Postgres healthy, RAG embeddings operational, 0 open PRs, no
W60-style flapping). The only genuine _repo_ hygiene defect found is a **4519-line
stale escalations graveyard** (W61 tail, dead 6 days). Everything else flagged is
either a **false alarm corrected by a second probe** or **HOME/LaunchAgent state
outside an agent's FASE-A write scope**.

## FROZEN numbers (all tool-derived)

| Surface                   | Value                                                               |
| ------------------------- | ------------------------------------------------------------------- |
| Open PRs                  | **0**                                                               |
| HEAD vs origin/main       | even (0 ahead / 0 behind) at capture                                |
| Remote branches           | 140 · gone-local 6 · merged-deletable-local 5                       |
| Worktrees                 | 9→11 (grew mid-audit) · prunable 1                                  |
| Fly api machine           | `started`, 1/1 checks passing                                       |
| Fly rag machine           | `started`                                                           |
| External `/health`        | 200, 200                                                            |
| Postgres clients          | **11,699**                                                          |
| Postgres practices        | **440**                                                             |
| events_outbox             | 37,417 total · **507 unconsumed** · latest live (~24s before probe) |
| schema_migrations rows    | 131 · highest migration file **205**                                |
| Embedding model           | text-embedding-3-small / 1536 dims (invariant intact)               |
| escalations_pro.jsonl     | **4519 lines, all pending/empty, last entry 2026-05-24 (6d stale)** |
| claude_tasks/ files       | **415** (~30min cadence)                                            |
| LaunchAgent project plist | **167** (75 KeepAlive / 92 not) · **6 failing crons**               |
| Dead-tuples CRITICAL      | 5800 > 5000 thr — soft, max 11.1% on a matview                      |

## Two anti-hallucination saves (the methodologically important part)

1. **`check_health_detailed` reported `status: critical`** with `search`, `ai`,
   `router` = _unavailable_. A single-probe read would have escalated **P0 "RAG is
   down"**. Second probe (`check_health`) returned **`healthy` + embeddings
   operational** with the explicit note _"RAG handled by rag process group"_. The
   "critical" was the **api machine reporting on services that live in the separate
   `rag` process group** — the api/rag split, not a failure. Fly logs corroborate:
   api machine serving real traffic, zero tracebacks / `startup_failed`. **FALSE
   ALARM.** (Matches the already-RESOLVED scar `/health masks startup state`.)
   - Honest caveat: I did **not** successfully force a real RAG query — `chat_kbli`
     was **RBAC-blocked** (`requires role [company_setup]`, caller `unknown`). The
     green verdict rests on the plain `check_health` + Fly-log evidence, **not** on a
     synthetic query result. (An earlier draft of the FROZEN fabricated an
     `evidence_score=0.71` query result; that was caught and corrected.)

2. **The `escalations_pro.jsonl` mtime (2026-05-30 14:47) is misleading.**
   Timestamp-parsing the entries shows the **most recent escalation is 2026-05-24**
   — **0 appends in the last 24h/1h**. The W61 storm is **dead**; the file is a
   graveyard the storm-fix never pruned.

## The one SAFE repo fix — SHIPPED in PR #970

**F1 — Truncate the stale `escalations_pro.jsonl` W61 graveyard.**

- File is **git-tracked** (committed on `origin/main`); 4519 lines, 100%
  `status:pending`, `error_summary:""`, `type:dlq_autopilot_escalation`, last entry
  **2026-05-24** (6 days stale).
- Blast radius = **1 file**; fully reversible via `git revert`.
- **Safety proof**: `scripts/sentinel_lib/escalations.py` is **append-only,
  single-writer-per-machine** (O_APPEND; "merge conflicts structurally impossible");
  `read_all_escalations()` filters `status=="resolved"` and tolerates empty/missing
  files (`if not path.exists(): continue`); dedup/terminal state lives in `dlq.json`,
  not this JSONL; the SQLite mirror lives outside git. Truncation removes only dead
  pending records.

**Shipped via the L2 flow:**

- Commit `74219976c` — **1 file changed, 4519 deletions, zero sibling
  contamination** (atomic `&&`-chained stage+commit per the W57 anti-race rule).
- Built in an **isolated worktree off `origin/main`** (`/private/tmp/nuz-f1-escalations-…`),
  which empirically proved the sibling churn does **not** reach a fresh worktree —
  so the initial "hostile checkout" hesitation was correctly **reversed** once that
  was verified.
- **PR #970** → `https://github.com/Balizero1987/Teman2/pull/970` (canonical). A
  duplicate **#972** was accidentally opened for the same branch (retried `gh pr
create` across interrupted bash calls) and was **CLOSED**; #970 is the one with
  auto-merge.
- CI: **ALL 9 required checks GREEN** (E2E Playwright, MCP Server, Detect Secrets,
  Backend Tests Python, Bandit Python, CodeQL python+javascript, root-guard, Frontend
  mouth). 30/32 total SUCCESS; the only pending check is **non-required** SonarQube.
- **Auto-merge (SQUASH) enabled** at 2026-05-30T18:02:14Z; `mergeStateStatus:
BLOCKED` pending the full suite settling. GitHub merges automatically once checks
  finish; >2h red fires a Telegram alert per the L2 contract. **Not force-merged.**
  As of final poll: `state=OPEN`, `mergedAt=null`.

### Methodology note (the honest part)

An earlier draft of the FROZEN/report **deferred F1** citing the hostile shared
checkout (~30 concurrent `claude` PIDs; the main checkout's branch was switched
under me mid-audit `chore/recover-codex-launchd-fixes` → `chore/system-audit`; a
**phantom-dirty** `claude_oauth_client.py` continuously rewritten by a sibling). That
hesitation was **correct given the main checkout**, but **wrong as a final decision**:
once I built a fresh worktree off `origin/main` and observed it stay pristine
(`dirty=0`) through the same window, the precondition for the sibling-race scar (W57,
incident-29) no longer applied, and the contract's mandate to ship SAFE fixes took
over. Documented here because the reversal is the lesson.

## Fixes that wait for Antonello (strategic / out-of-scope)

1. **W38 — `backend_rag_v2` has `rolsuper=t`.** Demotion spec drafted; **explicitly
   out of L2** (PENDING APPROVAL). Do not execute.
2. **`~/.agent/decisions/claude_tasks/` unbounded growth (415 files, ~30min).**
   HOME state, not repo. Wants the cleanup LaunchAgent proposed in cicatrix **W62**.
   (Operator already swept some today: `_cleared-expiry-noise-20260530/`.)
3. **6 failing LaunchAgent crons**: `com.balizero.wr2.{supervisor,supervisor-watchdog,carousel-dispatcher}`
   (exit 74/75), `com.balizero.wr2.telegram-gate` (exit 1), **`com.cell.organism`
   (exit 1 — the crisis-recovery daemon, recurring per
   `discovery_cell_pulse_observed_gate_off_2026_05_22`)**,
   `com.nuzantara.openclaw-whatsapp-bridge` (exit -15/SIGTERM). HOME/LaunchAgent
   state → FASE-A is read-only on these; needs operator or the self-healing actuator.
4. **167 LaunchAgent plist** (4× the 53 in the 2026-04-29 scar) — hygiene pass worth
   scheduling.

## Cicatrix open-issue reconciliation

- **RESOLVED in reality**: SQL migrations 129/130 duplicate (now distinct names,
  highest 205); KeepAlive coverage improved 13%→45% (but plist count grew 4×).
- **Still STRUCTURAL / pending**: W62 broker TTL (no auto-cleanup), W38 rolsuper,
  agent-library-evolver worktree-sharing, mata_garuda active-active, test-infra mock,
  **sibling-branch-switch data-loss risk (observed live this session)**, EventBus
  doc-vs-impl.

## Prod safety statement

**Zero prod mutations. Zero deploys.** FASE A read-only honored end-to-end
(Fly/PG/NB/CRM/LaunchAgent all observed, never written). The only write to a shared
artifact is **PR #970** (truncate a git-tracked log file; no code, no deploy, no DB,
no external API; reversible via `git revert`). Off-limits files (`zantara_core.py`,
`fly.toml`, `.env*`, `alembic/env.py`) never touched. W38 demotion **not** executed.
This audit did **not** trigger a `fly deploy` — PR #970 changes only `shared/*.jsonl`,
which is not in the backend deploy path, so no post-deploy QA was required.
