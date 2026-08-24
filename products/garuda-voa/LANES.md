# GARUDA VOA — lane graph and file ownership

> Orchestrator-owned. This is the artifact that makes the parallel build safe: **file ownership is
> disjoint by construction**, so two lanes can never edit the same file and no lane needs to stash,
> rebase around, or negotiate with a sibling. A lane that needs a file it does not own does not take
> it — it asks the orchestrator, who either moves the boundary or sequences the two lanes.
>
> Integration branch: `feature/garuda-voa` (local-first, pushed nightly as backup, **no PR**).
> Only the orchestrator merges into it. Lanes branch FROM it and merge back INTO it.
> Landing is a separate, later train of 4-6 reviewable PRs from the integration branch to `main`.

## Status legend

`blocked` — a prerequisite is unmet · `ready` — contract frozen, may be dispatched ·
`building` — a lane session holds it · `merged` — merged into the integration branch

## Prerequisite chain (this ordering is not negotiable)

```
G1 ground verdict ──┐
                    ├──> CONTRACT FREEZE ──> L2 L3 L4 L5 L6 L7 (parallel)
journeys (red) ─────┘         │
                              └──> L1 retention  (must MERGE before any lane persists a row)
```

L1 is first by construction, not by preference: the binding persistence design
(`research/visa/2026-08-23-voa-public-funnel-persistence-design.md` §4.3) rules that the retention
primitive must cover `garuda_voa_checks` **before the public funnel persists anything**, on the same
fail-closed philosophy the Visa Oracle precedent already enforces. A lane that writes a row before
L1 merges has built a table nobody may legally keep.

## Lanes

| Lane                       | Scope                                                                                                                                                                                                                                                                              | Builder                   | Refuter                                                           | Risk tier                    | Status                                |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | ----------------------------------------------------------------- | ---------------------------- | ------------------------------------- |
| **L1** retention + archive | extend the retention primitive to garuda tables, purge, coarse aggregates, self-service deletion                                                                                                                                                                                   | Sonnet 5                  | Codex Sol                                                         | full adversarial             | blocked (contract)                    |
| **L2** public API          | `POST /evaluate` + result `GET`, opaque id ≥128 bit, rate limit, full headers, allowlisted reason codes only, behind the flag                                                                                                                                                      | Sonnet 5                  | Kimi K3                                                           | full adversarial             | blocked (contract)                    |
| **L3** checkout + orders   | order model, provider-agnostic payment port (sandbox), idempotency keys, signed webhooks + inbox dedup, transactional outbox, append-only payment journal, reconciliation job                                                                                                      | Sonnet 5 or Codex Terra   | DeepSeek V4 Pro (re-derives every money/date figure from scratch) | full adversarial             | blocked (contract + owner decision 1) |
| **L4** account + portal    | magic-link auth from the website, portal practice view + tracker, visa delivery page. **Prerequisite inside the lane**: cure the open kita↔my audit findings (`verify_client_access` skipped, `get_current_client` ignoring `deleted_at`) before adding any surface on top of them | Codex Terra               | Codex Sol                                                         | full adversarial             | blocked (contract)                    |
| **L5** documents + OCR     | upload UX, local qwen2.5vl read, quality feedback loop, checklist, field pre-fill                                                                                                                                                                                                  | Kimi-for-coding           | Gemini (visual QA)                                                | full adversarial (PII)       | blocked (contract)                    |
| **L6** frontend + design   | `/visa/voa` pages restored then redesigned, tracker UI, Brevo emails from `zantara@`, imagegen assets                                                                                                                                                                              | Codex Terra + Haiku grunt | Opus 5 critic gate (screenshots, mobile-first, WCAG AA)           | contract tests + visual diff | blocked (contract + owner decision 5) |
| **L7** control tower       | practice→CRM handoff with zero re-typing, SLA timer, state-change emails, funnel dashboard, business-invariant alerts, daily synthetic purchase probe with dead-man switch                                                                                                         | Sonnet 5                  | Kimi K3                                                           | full adversarial             | blocked (contract)                    |

Refuter rule (ASSEMBLY-LINE verification economics): **one** cross-family refuter per PR, never two.
The family that built a lane is excluded from its own refuter chain. Multi-seat panels are reserved
for architecture and for the integrated product at the gauntlet, never per-PR.

## File ownership — disjoint by construction

A lane owns these paths exclusively. Anything not listed belongs to nobody yet and must be claimed
through the orchestrator before it is touched.

| Lane | Owns                                                                                                                                                                                      |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| L1   | `apps/backend-rag/backend/db/migrations_v2/` (garuda-scoped migrations only) · `apps/backend-rag/backend/services/garuda_flow/retention*.py` · `products/garuda-voa/ops/retention/**`     |
| L2   | `apps/backend-rag/backend/app/routers/garuda_voa*.py` · `apps/backend-rag/backend/services/garuda_flow/public_api*.py` · `apps/backend-rag/backend/tests/app/routers/test_garuda_voa*.py` |
| L3   | `apps/backend-rag/backend/services/garuda_orders/**` · `apps/backend-rag/backend/app/routers/garuda_orders*.py` · `apps/backend-rag/backend/services/payments/**`                         |
| L4   | `apps/backend-rag/backend/services/garuda_portal/**` · `apps/mouth/src/app/(portal)/**` · the two kita↔my audit call sites it is cleared to cure                                          |
| L5   | `apps/backend-rag/backend/services/garuda_documents/**` · `apps/mouth/src/app/visa/voa/upload/**`                                                                                         |
| L6   | `apps/mouth/src/app/visa/voa/**` (except `upload/`, owned by L5) · `apps/mouth/src/components/garuda/**` · `products/garuda-voa/ops/design/**`                                            |
| L7   | `apps/backend-rag/backend/services/garuda_ops/**` · `products/garuda-voa/ops/**` (except `retention/` and `design/`) · the synthetic-probe cron                                           |

**Orchestrator-only, never edited by a lane**: `products/garuda-voa/product.yaml`,
`products/garuda-voa/contracts/**` (frozen — changes go through the orchestrator, and
business-visible changes go through the owner), `products/garuda-voa/LANES.md`, and the integration
branch's merge commits.

**Shared and therefore forbidden to lanes**: the flag's registration site, `CLAUDE.md`,
`.github/workflows/**`, `CODEOWNERS`. A lane that believes it needs one of these has found a
sequencing problem, not a file to edit.

## Working agreement per lane session

1. One worktree, created off `feature/garuda-voa` via `scripts/agent_start.py`.
2. WIP ≤2 PRs per lane. A lane blocked more than 2h is split or re-scoped by the orchestrator —
   never pushed harder.
3. PRs at landing time ≤~200 logic lines (≤500 for pure UI).
4. The contract version a lane builds against is frozen at dispatch. If the contract must change,
   the lane stops and the orchestrator re-freezes; a lane never edits the contract to fit its code.
5. Three reds for the same cause ⇒ suspend the lane, one PENDING-ARMS line naming the cause, move on.
6. No status PRs, no handoff prose, no ledger commits. If no gate consumes it, it does not get
   written — the merge queue and the tests are the work-state.
