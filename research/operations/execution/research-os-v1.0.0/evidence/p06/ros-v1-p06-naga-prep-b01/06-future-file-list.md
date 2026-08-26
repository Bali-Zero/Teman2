# Exact future file list (for whoever builds P06)

None of these files exist in this branch. Paths are proposed, following the existing repo
conventions verified in `01-naga-baseline-inventory.md` (mirrors NAGA's own
`services/naga/**` / `core/claims/**` / `tests/services/naga/**` layout).

## Migration

- `apps/backend-rag/backend/db/migrations_v2/NNN_research_os_naga_claims.sql` — real integer
  bound at creation time, per `03-migration-design-notes.md`. Includes `-- === ROLLBACK ===`
  section per this repo's own migration-runner convention (`apps/backend-rag/CLAUDE.md`'s
  documented scar on that exact marker).

## Canonical adapter and service layer (additive, does not touch existing `services/naga/**`)

- `apps/backend-rag/backend/services/research_os/naga_claim_adapter.py` — reads `naga_claims` +
  `naga_claim_evidence` + `naga_sources` rows, produces canonical `Claim`/`Evidence` objects per
  `02-p04-adapter-mapping.md`. Owns the abstention logic (refuse to write when G-STATEMENT/G2
  cannot be satisfied — see fixture `abstention/01_high_confidence_no_source_span.json`).
- `apps/backend-rag/backend/services/research_os/naga_bitemporal_store.py` — read/write for the
  canonical store (whichever of the two shapes `03-migration-design-notes.md` §"What this
  migration creates" point 1 resolves to), including the time-travel query functions.
- `apps/backend-rag/backend/services/research_os/naga_transition_service.py` — writes
  `ObjectSuccessorEdge`-shaped records on supersession/contradiction, with the
  reconstruct-from-claim fallback described in `02-p04-adapter-mapping.md` §3.
- `apps/backend-rag/backend/services/research_os/naga_invalidation_service.py` — emits
  `OperationalReceipt`-shaped invalidation events (deliverable #7), idempotent on trigger natural
  key (see `05-test-matrix.md` invalidation-replay row).
- `apps/backend-rag/backend/services/research_os/naga_review_queue.py` — deliverable #8's human
  review queue, built on `OperationalReceipt` rather than `ApprovalReceipt` per gap G7 — unless
  the Conductor widens `ApprovalSubjectKind` first, in which case this should be revisited.
- `apps/backend-rag/backend/services/research_os/naga_evidence_independence.py` — deliverable #4,
  the original/syndicated/translated/derived classifier referenced in the
  `evidence_independence/*` fixtures. Genuinely new logic, not an adapter.

## Migration/atomization support (resolves gaps G-STATEMENT and G2 together — they share one root cause: no structured extraction exists yet)

- `apps/backend-rag/backend/services/research_os/naga_statement_atomizer.py` — the "human/rule-
  assisted" safe-incumbent atomizer the packet mandates (deliverable #3), producing
  `statement.{subject_ref, predicate, object_ref_or_value}` + a real `source_span` together, since
  both require the same underlying "read the actual quoted text" step. Automated-extraction
  variant, if built later, is a **separate, `MetricProfile`-gated candidate** per the packet's own
  instruction — do not fold it into this file as a default path.

## Tests (see `05-test-matrix.md` for the full table; paths repeated here for a single-glance list)

```
apps/backend-rag/backend/tests/migrations/test_migration_research_os_naga_claims.py
apps/backend-rag/backend/tests/services/research_os/naga/test_bitemporal_queries.py
apps/backend-rag/backend/tests/services/research_os/naga/test_transitions.py
apps/backend-rag/backend/tests/services/research_os/naga/test_source_span.py
apps/backend-rag/backend/tests/services/research_os/naga/test_contradiction_status.py
apps/backend-rag/backend/tests/services/research_os/naga/test_time_travel.py
apps/backend-rag/backend/tests/services/research_os/naga/test_invalidation_replay.py
apps/backend-rag/backend/tests/services/research_os/naga/test_sensitivity_boundary.py
apps/backend-rag/backend/tests/services/research_os/naga/test_review_authorization.py
```

## Consumer-facing wiring (explicitly LAST — packet Non-goal forbids doing this before shadow parity)

- `apps/backend-rag/backend/app/routers/naga.py` — add a shadow-read path behind a feature flag,
  comparing canonical-store answers to legacy `naga_claims` answers without changing the response
  the caller sees (packet: "Legacy readers remain authoritative until parity is demonstrated").
- `apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py` — same shadow-read treatment, once the router
  path is proven.

Neither of the two files immediately above should be touched until the shadow-read parity
measurement (packet Implementation sequence step 8: "Review mismatches and calibrate thresholds
before expanding") has run and been reviewed by someone with the authority this preparation lane
does not have.
