# Task 8 Report — Guarded Operations Room

## Outcome

Implemented the internal Operations room as a read-only observability surface
for Reader, Analyst, and Operator roles, with a strictly bounded intent control
plane available only to current Operators. Sites records, displays, leases, and
audits intents; it never executes operational effects. No production deploy,
outward publication, client-data access, collector mutation, paid API call, or
arbitrary command execution occurred.

The independent release review initially requested changes. This remediation
closes every Critical and Important finding: five executable production
capability adapters replace the unavailable stubs; effect attestations are
short-lived, single-use, and fully bound; target fencing is durable across
intents; exhausted/expired work is terminalized with a receipt and audit; state
transitions and audits are batched atomically; Operations JSON bodies have a
dedicated 4 KiB cap; and UI concurrency guards come from current read models.

## Security Model

- Exactly five intent kinds are accepted: `rerun_collector`,
  `rebuild_edition`, `quarantine_story`, `release_story`, and
  `refresh_research_job`.
- Arbitrary commands, URLs, paths, shell fragments, free-form reasons, unknown
  keys, and unbounded target values are rejected at the HTTP, worker, and
  capability-adapter boundaries.
- Intent creation is actor-scoped and idempotent, with policy evidence captured
  in metadata-only audit records. Current Operator membership is revalidated at
  insert, claim, and immediately before effect.
- The original intent expiry is checked both during claim and in the same
  compare-and-set that issues the pre-effect authority. Authorized attestations
  live for at most 30 seconds and bind intent, request hash, actor, target,
  intent fence, target fence, policy version, and expiry.
- The D1 state machine is explicit and terminally fenced:
  `queued -> claimed -> running -> succeeded | failed | cancelled_revoked |
  outcome_unknown`.
- Expired intents, revoked actors, stale running leases, and exhausted retry
  budgets receive an immutable server terminal receipt plus a metadata-only
  audit event in the same D1 batch as the terminal state.
- Machine claim, start, heartbeat, pre-effect attestation, and result routes use
  signed HMAC/SIWC envelopes and `no-store` responses. Lease ownership,
  deadlines, monotonic per-target fencing, and execution phase are checked by
  server-side compare-and-set mutations. These small JSON routes reject bodies
  above 4 KiB while the separate asset allowance remains unchanged.
- The Pro worker uses a durable SQLite outcome journal, per-target `flock`, a
  durable target-fence/effect-token CAS, heartbeats through terminal
  acknowledgement, and a final membership attestation. Every attestation field
  and expiry is validated immediately before the effect. Ambiguous terminal
  delivery is recorded as `outcome_unknown` and is not blindly retried.

## Delivered Components

- Operations health page and board covering collector freshness/latest success,
  current edition, Breaking queue, Research queue, failed intents, audit anchor,
  and sanitized status codes.
- Reader/Analyst/Operator read access with Operator-only action controls.
- D1 migration, schema, repository, audit events, intent receipts, target
  fences, leases, and the complete state-transition contract.
- Human intent APIs and signed machine APIs for claim, start, heartbeat,
  pre-effect attestation, and terminal results.
- Persistent Python transport, durable journal, fenced worker loop, fixed
  operation factory, and bounded CLI entry point.
- Five fixed JSON-command production adapters, one per exact intent kind. Their
  argv values are loaded from the closed
  `MAGAZINE_OPERATIONS_CAPABILITIES_JSON` map at startup; missing, extra,
  relative, non-executable, or malformed entries fail startup. The adapters use
  `create_subprocess_exec` without a shell, bounded JSON stdin/stdout, a minimal
  environment, a timeout, strict typed params, authority binding, and a closed
  target-bound receipt.
- Current action targets and exact edition/story revision guards are loaded from
  D1. The UI no longer fabricates expected revision or visibility values.

## TDD Evidence

- TypeScript tests cover the closed intent vocabulary, payload rejection,
  role-gated creation, actor-scoped idempotency, current-membership checks,
  health projection, signed machine routes, lease fencing, pre-effect
  attestation, full binding, expiry terminalization, retry exhaustion, shared
  target fencing, transition/audit rollback, route body caps, current UI
  preconditions, and terminal state semantics.
- Python tests cover the durable journal, replay behavior, per-target locking,
  monotonic target-fence/effect-token enforcement, every attestation binding,
  expiry, heartbeat lifetime, revoked membership, terminal acknowledgement,
  `outcome_unknown`, signed transport calls, all five independently executed
  fixed adapters, and the bounded CLI surface.

## Final Gates

From `apps/bali-zero-magazine`:

```text
npm run test:unit
155 passed, 0 failed

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
11 passed

.venv/bin/python -m pytest tests/magazine -q
114 passed

.venv/bin/ruff check <Task 8 Python files>
All checks passed!

.venv/bin/ruff format --check <Task 8 Python files>
3 files already formatted

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
PII. The worker can execute only the five preconfigured argv adapters after all
three membership gates, a fresh signed attestation, and durable target-fence
authorization. Runtime capability configuration is operator-controlled and
cannot be supplied by an intent. This work prepared the branch only; it did not
push, merge, deploy, or execute any production capability.
