---
adversarial_review: codex
adversarial_review_date: 2026-07-21
---

# Task 8 Report — Guarded Operations Room

## Outcome

Implemented and remediated the internal Operations room as a read-only
observability surface for Reader, Analyst, and Operator roles, with a strictly
bounded intent control plane available only to current Operators. Sites records,
displays, leases, audits, and authorizes intents; the Pro worker remains the only
effect executor. No production deploy, outward publication, client-data access,
collector mutation, paid API call, or arbitrary command execution occurred.

The final review's Critical and Important findings, plus both suggested UI
hardening items, are closed in this branch. The remediation adds a code-owned
five-operation dispatcher, immutable launchd capability labels, an authenticated
effect endpoint, full effect-receipt authority binding, guarded D1 transition
edges, active-running claim exclusion, signed single-use release attestations,
atomic release visibility mutation, action-specific target eligibility, and a
two-step review/confirm interaction.

## Security Model

- Exactly five intent kinds are accepted: `rerun_collector`,
  `rebuild_edition`, `quarantine_story`, `release_story`, and
  `refresh_research_job`.
- Arbitrary commands, URLs, paths, shell fragments, free-form reasons, unknown
  keys, and unbounded target values are rejected at the HTTP, worker, and
  adapter boundaries. No deployment command is present in the dispatcher.
- Intent creation is actor-scoped and idempotent, with policy evidence captured
  in metadata-only audit records. Current Operator membership is revalidated at
  insert, claim, and immediately before effect.
- The original intent expiry is checked both during claim and in the same
  compare-and-set that issues pre-effect authority. Authorized attestations live
  for at most 30 seconds and bind intent, request hash, actor, target, intent
  fence, target fence, policy version, and expiry.
- The D1 state machine is explicit and terminally fenced:
  `queued -> claimed -> running -> succeeded | failed | cancelled_revoked |
  outcome_unknown`. A database guard table rejects transitions outside the
  declared graph, and transition/audit uniqueness prevents duplicate start
  events.
- Claiming skips a target while another non-expired intent for that target is
  already running. Every zero-row guarded compare-and-set aborts the surrounding
  D1 batch rather than allowing a partial audit or receipt.
- Machine claim, start, heartbeat, pre-effect attestation, effect, and result
  routes use signed HMAC/SIWC envelopes and `no-store` responses. These small
  JSON routes reject bodies above 4 KiB while the separate asset allowance
  remains unchanged.
- Effect receipts bind schema, code, intent kind, target identity, claim fence,
  target fence, and effect token. Completion rejects a receipt that does not
  match the exact authority tuple.
- Release additionally requires a canonical Ed25519 attestation from the closed
  runtime key registry. The attestation is version-bound, short-lived, and
  single-use. Its consumption, canonical audit-chain append, and story
  visibility event are committed in one D1 batch. Exact replays are idempotent;
  stale or mismatched releases fail closed.
- The Pro worker uses a durable SQLite outcome journal, per-target `flock`, a
  durable target-fence/effect-token CAS, heartbeats through terminal
  acknowledgement, and final membership attestation. Ambiguous terminal
  delivery is recorded as `outcome_unknown` and is not blindly retried.

## Delivered Components

- Operations health page and board covering collector freshness/latest success,
  current edition, Breaking queue, Research queue, failed intents, audit anchor,
  and sanitized status codes.
- Reader/Analyst/Operator read access with Operator-only action controls.
- D1 migration, schema, repository, transition guards, audit events, intent
  receipts, target fences, release attestations, leases, and the complete
  state-transition contract.
- Human intent APIs and signed machine APIs for claim, start, heartbeat,
  pre-effect attestation, effect application, and terminal results.
- Persistent Python transport, durable journal, fenced worker loop, code-owned
  operation dispatcher, and bounded CLI entry point.
- Immutable launchd adapters for Intel Lake, MATA GARUDA, Regulatory Watcher,
  NotebookLM, Magazine Publisher, and Magazine Research Worker. Quarantine and
  release are applied only through the signed Sites effect route; no intent can
  inject or replace a label, executable, argument, URL, or environment value.
- Action-specific targets from current D1 state: quarantine exposes only visible
  stories, while release exposes only quarantined stories with a matching,
  unexpired, unconsumed release attestation for the current version.
- A two-step Operations UI that first shows the exact action, target, and reason
  for review, then requires an explicit `Confirm and queue` submission. Changing
  any selection invalidates the pending confirmation.

## TDD Evidence

The remediation was driven through observed red tests before implementation:

- Active-running claim regression: expected one claimable intent, observed two;
  fixed by target-level running exclusion and guarded claim CAS.
- Duplicate-start regression: expected one transition audit, observed two;
  fixed by transition/audit uniqueness and idempotent start handling.
- Adapter contract test initially failed because the code-owned dispatcher did
  not exist; implementation then passed all five operation mappings.
- Release test initially failed because the signed release-attestation contract
  did not exist; implementation then passed signature, expiry, version,
  single-use, visibility-CAS, audit-chain, and replay checks.
- Action-eligibility test exposed an invalid `stories.updated_at` reference;
  ordering was corrected to a real schema column before the test passed.

TypeScript coverage now includes the closed vocabulary, payload rejection,
role-gated creation, actor-scoped idempotency, current-membership checks, signed
machine lifecycle, lease and target fencing, full receipt binding, release
authorization/consumption, guarded transitions, atomic rollback, all five
lifecycle-route 4 KiB caps, action-specific UI targets, review/confirm behavior,
and terminal semantics. The effect route uses the same capped signed ingress.
Python coverage includes the durable journal, replay behavior,
per-target locking, monotonic fencing, every attestation binding, expiry,
heartbeat lifetime, revoked membership, terminal acknowledgement,
`outcome_unknown`, signed transport, and all five dispatcher paths.

## Final Gates

From `apps/bali-zero-magazine`:

```text
npm run test:unit
160 passed, 0 failed

npm run lint
exit 0

npm run typecheck
exit 0

npm run build
exit 0; Operations page and all human/machine routes included, including
/api/machine/operations/effects

npx prettier --check <Task 8 TypeScript/JavaScript files>
All matched files use Prettier code style!
```

From `apps/zantara-media`:

```text
.venv/bin/python -m pytest tests/magazine -q
114 passed

.venv/bin/ruff check <Task 8 Python files>
All checks passed!

.venv/bin/ruff format --check <Task 8 Python files>
4 files already formatted

.venv/bin/python -m compileall -q zantara_media
exit 0

.venv/bin/python -m zantara_media.cli.magazine_operations_worker --help
exit 0; only bounded backoff options are exposed
```

Repository hygiene:

```text
git diff --check
exit 0
```

## Operational Boundary

The Operations room is internal, metadata-only, and deny-by-default. It cannot
accept a shell command, filesystem path, URL, credential, raw OSINT, or client
PII. The worker can execute only the code-owned adapters after all membership
gates, a fresh signed authority, and durable target-fence authorization. Runtime
keys and immutable capability labels are operator-controlled and cannot be
supplied by an intent. This work prepared the branch only; it did not push,
merge, deploy, publish, or execute any production capability.

## Release Story Remediation — 2026-07-20

The second independent Task 8 review found one blocker: Sites emitted
`release_story` claims with `release_attestation_id`, while the Python worker
still accepted only the quarantine-shaped story parameter set. The worker
validator now keeps `quarantine_story` and `release_story` as separate closed
schemas, requires a valid `release-attestation-*` identifier for release, and
continues to reject missing, invalid, generic, or extra attestation fields.

Additional coverage proves that a Sites-valid `release_story` claim passes
validation and runs through the worker effect path with the full receipt target
binding. The signed HTTP lifecycle route test now runs claim/start/heartbeat/
pre-effect-attest/result for all five operation kinds, and the 4 KiB machine
body cap covers the signed `/api/machine/operations/effects` route directly.

Verification:

```text
cd apps/zantara-media && .venv/bin/python -m pytest tests/magazine/test_operations_worker.py -q
13 passed

cd apps/bali-zero-magazine && npm run test:unit -- --test-name-pattern='operations'
160 passed


## Adversarial review

Codex challenged whether the Operations room could execute arbitrary effects or
bypass review through a forged lifecycle transition. The five-kind dispatcher,
role checks, transition guards, single-use attestations, and effect receipts
answer those objections. Live effect execution remains outside Sites and is not
proven until the protected Pro worker bindings are configured.
cd apps/zantara-media && .venv/bin/ruff check zantara_media/magazine/operations_worker.py tests/magazine/test_operations_worker.py
All checks passed!

cd apps/zantara-media && .venv/bin/ruff format --check zantara_media/magazine/operations_worker.py tests/magazine/test_operations_worker.py
2 files already formatted

cd apps/bali-zero-magazine && npx prettier --check tests/operations.test.mjs
All matched files use Prettier code style!

git diff --check
exit 0
```
