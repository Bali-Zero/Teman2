# ResearchOS business slice: record obligation completion

## Mandate

ROS-OBLIGATION-CLOSURE-1017, BLUE, Gear 2. Zero explicitly requested one
useful slice completed and deployed. The existing obligations register can
propose, approve and reject work but cannot record its completion. Add that
last step to the existing desk; this is a bounded compliance adoption slice,
not completion of ResearchOS P19 or the canonical Action Inbox.

Worktree: `.worktrees/backend-rag-ros-obligation-closure-1017`.
Base: `4b2808bb8902abd5ad396a01ac217912f5fe725d`.

## Owned perimeter and reuse

Own the obligations/alerts routers, obligations repository, their focused
tests, the existing obligations page/components/tests, and redaction of the
new evidence reference. No migration, outbound delivery, scheduler, new
queue, pricing or regulatory-rule change. Existing approval records survive.
Reuse AlertRepository, ObligationsRepository, alert_outcomes (including its
metadata column), the authenticated API client and the existing status view.
External reuse check: asyncpg's existing transaction context manager supplies
commit/rollback; no new library or copied external code is needed.
Reference: https://magicstack.github.io/asyncpg/current/api/index.html#transactions

## Contract

Admin-only `POST /api/compliance/obligations/{id}/complete` accepts a trimmed
1–500 character `evidence_ref` and strict boolean `declaration: true`.
The declaration records the operator's statement, not independent legal
verification. Lock obligation, then its linked alert; verify client, category
and dedup identity; atomically transition alerted to done, resolve the alert,
and append one acted outcome with completion metadata, actor and timestamp.
Missing records return 404; invalid state/link and repeats return 409.
Generic acknowledgment, dismissal and acted events cannot complete an obligation
or change an alert after its linked obligation has been completed.
UI: separate evidence input and declaration, Record completion on alerted rows,
refresh after success or a concurrent completion, and a done counter/filter.

## Acceptance

- Authorization, strict declaration, blank/oversized references and wrong states fail.
- Exact linked alert required; wrong client/category/dedup writes nothing.
- Approval provenance is preserved; one completion produces one audit outcome.
- Real PostgreSQL tests prove atomic rollback, duplicate/retry behavior and races.
- Generic outcomes cannot reopen completed work; unrelated alerts retain behavior.
- UI tests prove the submitted body, disabled controls, counters and refresh.
- No evidence reference in logs/telemetry; synthetic fixtures only.
- Production: deployed revision, route/schema, auth refusal and safe read probes;
  never complete a real client's obligation merely to test the release.

## Team and release

Codex implements; the BLUE Opus 5.5 xhigh Dux verifies and owns release;
a fresh Opus 5.5 xhigh session outside the contribution chain signs the final
gate. Initial design session `c7c02d41-2f72-4f4e-95a6-4dcd3670ab88` approved
the scope with explicit concurrency and acknowledgment safeguards.
One branch, no concurrent writer. Existing sibling paths remain untouched.
At most one corrective iteration before narrowing or revising the contract.
Both backend and frontend revisions must be live before completion is declared;
rollback the release if authorization or the atomic completion proof fails. No data backfill.
