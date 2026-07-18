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
