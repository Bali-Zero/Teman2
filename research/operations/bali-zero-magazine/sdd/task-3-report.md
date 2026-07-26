---
date: 2026-07-21
adversarial_review: exempt-execution-report-umbrella-spot-check-in-sdd/REVIEW.md
---

# Task 3 report: atomic D1 publication model

## Outcome

Implemented the approved 25-entity D1 model, generated the core Drizzle
migration, added prepared-statement publication staging/finalization, and added
the per-stream byte-exact audit chain.

Publication finalization uses a single D1 batch per packet. CAS preconditions
are enforced inside the transaction, publication readers follow explicit heads
and require `publication_state = 'published'`, replay accepts only the same
packet ID plus manifest hash, and standalone Breaking advances its story and
Breaking heads together.

Audit events use RFC 8785 canonical JSON, NFC stream IDs, the
`BZM-AUDIT-EVENT-V1` domain separator, U32/U64 big-endian encoding, raw prior
hash bytes, lowercase SHA-256 storage, and one event-plus-head CAS batch.

## TDD evidence

- RED: publication tests initially failed because the schema exports,
  migration, and repository did not exist.
- GREEN: publication schema/replay/CAS/Breaking tests pass against an in-memory
  SQLite adapter that executes the generated migration and real transactions.
- RED: audit tests initially failed because `audit-chain.ts` did not exist.
- GREEN: canonical preimage, genesis/successor chaining, and forced concurrent
  CAS rollback tests pass.

## Verification

- `npm run db:generate`: pass, 25 tables, no schema drift after generation.
- `npm run test:unit -- --test-name-pattern='publication|audit'`: pass, 47/47.
- `npm run build`: pass.
- `npm run lint`: pass.
- `git diff --check`: pass.

`npx tsc --noEmit` remains blocked by pre-existing project configuration/type
issues (`cloudflare:workers`, global `Fetcher`/`D1Database`, and Task 2
`.ts`-extension suppressions). The only Task 3 diagnostic, Web Crypto's
`BufferSource` generic, was fixed; build and lint are clean.

## Preserved workspace state

The pre-existing `INDEX.md`, `README.md`, and `.husky/_` changes were neither
modified nor staged.

## Review remediation (2026-07-18)

Resolved all five Important findings and the exact-version Minor finding from
the Task 3 review.

- Publication packets now durably declare packet-scoped counts and reference
  manifests for story versions, claims, evidence links, edition/Breaking
  placements, and story asset references.
- Staging writes the complete graph in `building` state. Finalization runs a
  structural/count/head guard and promotes every graph table plus both relevant
  heads in one D1 batch; any mismatch rolls back the batch.
- Current and historical edition readers now require published entries and
  apply the latest quarantine overlay.
- The baseline migration seeds both singleton pointer rows, and D1 enforces
  `version = expected_current_version + 1`.
- Evidence IDs permit only byte-for-byte-equivalent persisted-field reuse;
  changed content fails atomically without mutating the original evidence.
- Concurrent identical staging resolves to one `staged` result and one
  `replay`; a concurrent hash mismatch remains fail closed.

### Remediation TDD and verification

- RED: 20 focused failures covered schema/migration invariants, clean bootstrap,
  exact story versioning, concurrent replay, immutable evidence, complete graph
  promotion/corruption, and edition quarantine behavior.
- GREEN: `npm run test:unit` passes 63/63.
- `npm run build`: pass.
- `npm run lint`: pass.
- `npm run db:generate`: pass, 26 tables, no schema drift.
- `git diff --check`: pass.

The unrelated `INDEX.md`, `README.md`, and `.husky/_` workspace changes remain
unstaged and untouched by this remediation.

## Second review remediation (2026-07-18)

Resolved both additional Important findings and implemented both suggested
hardening checks from the Task 3 re-review.

- Edition dimensions are orthogonal everywhere: `edition_kind` is
  `standard|quiet`, while `coverage_state` is `complete|partial`. The TypeScript
  contract, Drizzle schema, regenerated single baseline migration/snapshot, and
  fixtures now use the same vocabulary.
- `asset_status_events` now records independently constrained `status` and
  `rights_status` snapshots. Finalization's first statement atomically rejects
  a latest story quarantine, latest non-verified asset status, or latest
  non-approved asset rights overlay. When events exist, only the greatest
  per-entity sequence is authoritative; otherwise the verified/approved base
  asset row remains the fallback.
- A failed overlay guard leaves the packet, complete packet graph, story head,
  edition head, and Breaking head unchanged in `building` state.
- Concurrent duplicate edition and Breaking finalization now has explicit
  winner/loser semantics: one caller returns `published`; after its transaction
  loses and rolls back, the other re-reads the committed packet and returns
  `replay`.
- A late injected failure after all graph-promotion statements proves the D1
  transaction rolls the graph and heads back to their staged values.

### Second remediation TDD and verification

- RED: the new edition vocabulary test failed against `morning` and
  `full|partial|quiet`; repository fixtures then exposed the same stale schema
  vocabulary.
- RED: four focused failures proved concurrent duplicate finalization returned
  a CAS error and that latest quarantine/status/rights overlays were ignored.
- GREEN: focused overlay, replay, and late-fault tests pass.
- `npm test`: pass; production build and 71/71 unit tests pass.
- `npm run lint`: pass.
- `npm run db:generate -- --name schema_drift_check`: pass, 26 tables, no
  schema changes.
- `git diff --check`: pass.

The unrelated `INDEX.md`, `README.md`, and `.husky/_` workspace changes remain
unstaged and untouched by this second remediation.
