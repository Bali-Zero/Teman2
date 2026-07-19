# Task 8 Report — Guarded Operations Room

## Outcome

Implemented the internal Operations room as a read-only observability surface
for Reader, Analyst, and Operator roles, with a strictly bounded intent control
plane available only to current Operators. Sites records, displays, leases, and
audits intents; it never executes operational effects. No production deploy,
outward publication, client-data access, collector mutation, paid API call, or
arbitrary command execution occurred.

## Security Model

- Exactly five intent kinds are accepted: `rerun_collector`,
  `rebuild_edition`, `quarantine_story`, `release_story`, and
  `refresh_research_job`.
- Arbitrary commands, URLs, paths, shell fragments, free-form reasons, unknown
  keys, and unbounded target values are rejected at the HTTP and repository
  boundaries.
- Intent creation is actor-scoped and idempotent, with policy evidence captured
  in metadata-only audit records. Current Operator membership is revalidated at
  insert, claim, and immediately before effect.
- The D1 state machine is explicit and terminally fenced:
  `queued -> claimed -> running -> succeeded | failed | cancelled_revoked |
  outcome_unknown`.
- Machine claim, start, heartbeat, pre-effect attestation, and result routes use
  signed HMAC/SIWC envelopes and `no-store` responses. Lease ownership,
  deadlines, monotonic fencing, and execution phase are checked by server-side
  compare-and-set mutations.
- The Pro worker uses a durable SQLite outcome journal, per-target `flock`,
  heartbeats through terminal acknowledgement, and a final membership
  attestation. Ambiguous terminal delivery is recorded as `outcome_unknown` and
  is not blindly retried.

## Delivered Components

- Operations health page and board covering collector freshness/latest success,
  current edition, Breaking queue, Research queue, failed intents, audit anchor,
  and sanitized status codes.
- Reader/Analyst/Operator read access with Operator-only action controls.
- D1 migration, schema, repository, audit events, intent receipts, leases, and
  the complete state-transition contract.
- Human intent APIs and signed machine APIs for claim, start, heartbeat,
  pre-effect attestation, and terminal results.
- Persistent Python transport, durable journal, fenced worker loop, fixed
  operation factory, and bounded CLI entry point.
- The production factory currently maps all five operations to explicit
  fail-closed unavailable handlers. Repository inspection found no audited local
  mutation capability that could safely be wired without broadening Task 8;
  therefore activation cannot silently improvise an effect.

## TDD Evidence

- TypeScript tests cover the closed intent vocabulary, payload rejection,
  role-gated creation, actor-scoped idempotency, current-membership checks,
  health projection, signed machine routes, lease fencing, pre-effect
  attestation, and terminal state semantics.
- Python tests cover the durable journal, replay behavior, per-target locking,
  monotonic fence/phase enforcement, heartbeat lifetime, revoked membership,
  terminal acknowledgement, `outcome_unknown`, signed transport calls, fixed
  factory behavior, and the bounded CLI surface.
- Regression work included a TypeScript strip-only compatibility fix and a
  connection-lifetime fix for the SQLite journal; both are protected by the
  final suites.

## Final Gates

From `apps/bali-zero-magazine`:

```text
npm run test:unit
150 passed, 0 failed

npm run lint
exit 0

npm run typecheck
exit 0

npm run build
exit 0; Operations page and all human/machine routes included

npx prettier --check <Task 8 TypeScript/JavaScript files>
All matched files use Prettier code style!
```

From `apps/zantara-media`:

```text
.venv/bin/python -m pytest tests/magazine/test_operations_worker.py -q
9 passed

.venv/bin/python -m pytest tests/magazine -x -vv
112 passed

.venv/bin/ruff check <Task 8 Python files>
All checks passed!

.venv/bin/ruff format --check <Task 8 Python files>
5 files already formatted

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
PII. The worker can execute only fixed factory handlers after all three
membership gates and the final signed attestation. Wiring a real mutation
handler remains a separate reviewed task and must preserve the same closed
capability and fencing contracts.
