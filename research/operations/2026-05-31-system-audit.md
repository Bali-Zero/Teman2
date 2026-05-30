---
date: 2026-05-31
domain: operations
client_case: none
sources:
  - "curl https://nuzantara-rag.fly.dev/health (5 probes, all HTTP 200)"
  - "mcp__nuzantara-mcp-advanced__check_fly_status (live Fly machine state)"
  - "mcp__nuzantara-mcp-advanced__analyze_fly_health (risk_score 0)"
  - "mcp__nuzantara-mcp__check_health_detailed (api process group)"
  - "mcp__postgres-nuzantara__query (nuzantara_readonly, PG live counts)"
  - "git / git fsck / git worktree (local repo state)"
  - "gh run list --branch main (CI status)"
  - "grep golden-rule compliance scan over apps/backend-rag/backend/"
auditor: "Claude Opus 4.8 (1M ctx) — autonomous L2 subagent"
companion_frozen: "research/operations/2026-05-31-system-audit-FROZEN.json"
---

# Nuzantara System Audit — 2026-05-31 (empirical, read-only FASE A)

> Verdict: **GREEN.** Production healthy and consistent, data invariants intact,
> golden rules clean, CI green, recent critical scars (W60/W61) confirmed closed
> in live state. No P0/P1 broken code path found. Outstanding items are
> **structural debt requiring operator decisions**, not safe one-shot code fixes.

The audit prompt arrived empty (`undefined`), so this was run as a comprehensive
empirical health sweep under the L2 hard rules: FASE A is read-only on prod, only
the local `FROZEN.json` is written; FASE B ships only additive/idempotent/
reversible/blast-radius-≤1 fixes. Every number here is tool-derived in the audit
turn (anti-hallucination discipline) — see the companion FROZEN.json for raw
values.

---

## 1. Production backend — HEALTHY

- `GET https://nuzantara-rag.fly.dev/health` → **HTTP 200, 0.12s**, body
  `status=healthy`, `database=connected (postgresql)`,
  `embeddings=text-embedding-3-small / 1536 dims operational`. **5/5 probes
  identical.**
- Fly app `nuzantara-rag` release **v3414**, image GH_SHA `be06d86ba` (#969).
  - api machine `7847d95ce257d8`: `started`, **shared 2cpu / 3072MB**,
    host_status `ok`, servicecheck **passing**.
  - rag machine `1781e5eda03438`: `started`, shared 2cpu / 2048MB, host_status `ok`.
  - `analyze_fly_health` **risk_score 0, zero issues**.

### The one "critical" reading that is NOT an incident

`check_health_detailed` returns `status=critical` with `search/ai/router =
unavailable`. This is the **api (light) process group** answering: those heavy
services live on the **rag process group** (`main_rag:app`), exactly as the
`/health` body states (`"RAG handled by rag process group"`). On the api process,
`database=healthy`, `redis=healthy (3.5ms)`, `rate_limiter=healthy (28 limits,
0 redis errors)`, `query_cache=healthy (redis)`. This is the documented
api/rag split (Sprint 1.B scar family) and the W60 "degraded ≠ down"
discrimination principle. **Reported here so future audits do not misclassify it
as an outage.**

---

## 2. Data invariants — INTACT

Via `postgres-nuzantara` read-only MCP:

| Metric | Value |
|---|---|
| clients | **11,699** |
| practices | **440** |
| public tables | **281** |
| events_outbox total | 37,419 |
| events_outbox unconsumed | **507** |

- Embedding model **`text-embedding-3-small` / 1536** confirmed both in prod
  `/health` and in `core/embeddings.py` + `migration_020` (the 93,283-vector
  freeze invariant is respected).

### events_outbox drain — broad multi-consumer gate-off (upgraded finding)

Per the mandatory "query MAX(created_at) age before interpreting drain" rule
(`discovery_cell_pulse_observed_gate_off`). Aggregate: **509 unconsumed, 345
stale (>24h), 8 distinct channels** (confirmed across 3 identical queries).
Per-channel:

| channel | unconsumed | newest age | verdict |
|---|---|---|---|
| `inbound_webhook_queued` | 164 | 1.8h | **healthy** live drain (long tail to 05-13 = slow) |
| `client_changed` | 178 | 215.7h | **gate-off** since 2026-05-21 |
| `practice_changed` | 78 | 38.4h | partial gate-off |
| `cell_pulse_sustained_red` | 50 | 64.0h | gate-off since 2026-05-28 |
| `intel_lake_event` | 24 | 377.9h | gate-off since 2026-05-14 |
| `whatsapp_message_received` | 8 | 151.9h | gate-off since 2026-05-24 — **expected** (wa-mirror local-only cutover) |
| `war_room_event` | 5 | 377.7h | gate-off since 2026-05-15 |

> **Correction (anti-hallucination):** an earlier transient query in this audit
> returned a different split (`cell_pulse_observed` 489 + `measurer_event` 18)
> that was not reproducible. The table above is the repeated, reliable result.
> The first FROZEN write captured the transient split; it has been corrected in
> the committed FROZEN.

This is a **broader event-consumer gate-off than a single dead daemon** —
several PG LISTEN/NOTIFY consumers stopped advancing in mid-May.
`inbound_webhook_queued` is the only clearly-healthy live drainer;
`whatsapp_message_received` gate-off is expected
(`decision_wa_mirror_local_only_cutover_2026_05_24`). **See finding F-2.**

---

## 3. Escalation storm — HISTORICAL and CONTAINED

- `shared/escalations_pro.jsonl` is **git-tracked**, **1.17 MB**, **4,519
  entries**, all `status=pending`.
- Content time span **2026-04-10 → 2026-05-24 08:34** (last *real* ts). The file
  mtime (2026-05-30 22:47) is a re-serialization, **not** new escalations.
- Top emitters ~103–107 each (zombie_hunter, articles_indexing_daily,
  daily_ops_autopilot, gdrive_pg_backup, …) — the classic W61 empty-`error_summary`
  storm fingerprint.
- **DLQ (`~/.agent/decisions/dlq.json`) is fully drained: all 13 jobs
  `TERMINAL`.** The W61 `add_to_dlq` attempts-preservation fix is working; there
  is **no live retry loop**.

So the storm is dead; what remains is a 1.17 MB tracked append-only log that was
never rotated — the documented "weekly digest / pruning" gap. **See finding F-1.**

---

## 4. Golden rules (backend) — CLEAN

- `print()` in `apps/backend-rag/backend/`: **0**.
- Paid Anthropic endpoint instantiation: **0** (all matches are the defensive
  `ANTHROPIC_API_KEY` strip-logic in `claude_oauth_client.py`, docstrings, tests).
- `httpx.AsyncClient()` rule-10 violations: **0 real** — `telegram_notifier.py:377`
  wraps the candidate loop in a single persistent client (correct).
- `import requests` in backend: **1** — `backend/verify_route.py` (25-line
  throwaway manual routing-test with bare excepts). **See finding F-3.**

---

## 5. Repo hygiene

- **CI on `main`: GREEN** (last 8 runs success). 0 open PRs. 33 local / 140
  remote branches (graveyard — remote branches show 0 merged because they were
  squash-merged; this is expected, not lost work).
- **8 worktrees, 7.0 G.** `nuzantara-deploy` marked `prunable`. Four agent
  worktrees are `ahead_of_main=0` (zero *committed* unique commits) BUT — **correction
  vs my first pass** — they carry **real uncommitted code WIP**, not formatting
  noise: `crm-guardian-audit` (8 modified .py incl. `drive_poll_service.py` +
  tests), `wa-nlm-validation-battery` (6 `openclaw_whatsapp_*` scripts),
  `docs-lab-clean-recreate` (16, **incl. NEW untracked feature files**:
  `routers/workspace_event_bridge.py`, 3 jobs, 3 tests, a LaunchAgent plist,
  `research/labs/`), `wr2-mouth-next16-lint` (4: eslint/package/Checklist/lock).
  This is the **"untracked-files-lost-on-branch-switch" danger zone** — unsaved
  work parked in stale worktrees, especially `docs-lab-clean-recreate`'s
  untracked new files (a `git stash` without `-u` would lose them). **See
  finding F-4 (upgraded).**
- `git fsck`: 607 dangling commits / 29 dangling blobs — normal for a heavy
  multi-worktree repo with no recent `gc`; no lost-work signature.
- Disk **31% used, 36 Gi free** — healthy, nowhere near the 94% intel-pipeline
  killer threshold.

---

## 6. Recent critical scars — confirmed closed in live state

| Scar | Live evidence |
|---|---|
| **W60** Fly api flapping (1cpu/2gb undersized) | api machine now **2cpu/3gb** (PR #903), host_status ok, risk_score 0 |
| **W61** DLQ retry storm (attempts stripped on re-add) | DLQ all-TERMINAL, no live escalations since 2026-05-24 |
| **#969** villa KBLI 55193→55203 mis-map | `services/whatsapp_kbli_guard.py` present, deployed as v3414 |

---

## 7. Findings (structural debt — operator decisions, not auto-fixed)

These were deliberately **not** auto-shipped: each either mutates prod/shared
state, has unverified blast radius, or could not be cleanly re-verified in-turn.
Per the hard rules they belong to "Fix che aspettano Antonello".

- **F-1 — `escalations_pro.jsonl` bloat (1.17 MB, git-tracked, dead since
  2026-05-24).** Recommend: add a rotation/prune step (e.g. archive entries
  older than N days to `escalations_pro.archive.jsonl`, keep file < ~200 KB) AND
  the long-proposed "weekly digest of cooldown-suppressed alerts" (W55/W61
  gotcha). NOT auto-pruned: sentinel/dlq tooling may parse this file — needs a
  read of the sentinel parser first.
- **F-2 (UPGRADED) — broad events_outbox consumer gate-off.** ~345/509
  unconsumed events are stale (>24h) across `client_changed` (215h),
  `practice_changed` (38h), `cell_pulse_sustained_red` (64h), `intel_lake_event`
  (378h), `war_room_event` (378h). Multiple PG LISTEN/NOTIFY consumers stopped
  advancing in mid-May. Recommend: operator triage of which consumers/daemons are
  intentionally off (e.g. wa-mirror cutover explains `whatsapp_message_received`)
  vs genuinely broken, then re-arm the broken ones. Prod-state mutation →
  operator-gated. NOTE: `events_outbox` is unbounded until the phase-3 pruning
  cron lands (per SYMBIOSIS Law 3 known limit) — the stale tail will keep
  accumulating.
- **F-3 (SHIPPED) — `backend/verify_route.py` orphan removed.** Re-verified
  in-turn: 0 importers, not in router_manifest/registration, provenance =
  leftover from the `main_cloud.py` refactor (`86ee1b71c`) only touched by lint
  sweeps since. Deleted in this audit's PR (additive/reversible/blast-radius-0).
- **F-4 (UPGRADED) — stale worktrees hold uncommitted WIP, not noise.** The four
  `ahead_of_main=0` worktrees each carry real uncommitted code (see §5), so they
  are **NOT** GC-safe and, more urgently, the work is at risk of loss on any
  sibling `git stash`/branch-switch (especially `docs-lab-clean-recreate`'s
  untracked new feature files). Three have mtimes within minutes of the audit
  (active sibling sessions). Recommend: (a) sibling agents **commit their WIP
  now**; (b) the long-proposed `com.nuzantara.agent-worktree-cleanup` daily
  LaunchAgent that skips recently-touched/dirty trees.

---

## 8. FASE B outcome

No P0/P1 broken code path was found. One genuinely-safe fix shipped:

- **Removed `backend/verify_route.py`** — orphan debug script (banned `requests`
  lib + bare excepts, 0 importers verified in-turn). Additive, reversible,
  blast-radius 0.

The other findings were deliberately **not** auto-shipped: prod-state mutations
(F-2), shared-state mutation with unverified blast radius (F-1), or blocked by
active sibling sessions holding uncommitted WIP (F-4). All shipped via the
isolated branch `chore/system-audit-2026-05-31` → **PR #970** (auto-merge squash,
CI-gated), staging only this audit's own files (W57 anti-sibling-race discipline:
the worktree's pre-staged sibling files were unstaged before commit and are NOT
in the PR).
