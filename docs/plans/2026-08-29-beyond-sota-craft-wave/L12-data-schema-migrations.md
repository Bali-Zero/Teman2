---
date: 2026-08-29
domain: operations
plan: beyond-sota-craft-wave
lane: "12 - Data, schema & migrations"
source_report: /Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828/research/operations/2026-08-28-beyond-sota-data-schema-migrations.md
status: SPEC-FINAL
---

# L12 - Data, schema & migrations

## Mission

Make database behavior provable at the application boundary: the panel measured 97.7% rollback coverage, but also 22 production tables not owned by the app role, five incidents in 20 days from one broken role assumption, and a JSONB defect that passed 10/10 integration tests. This lane closes those specific gaps without weakening the runtime-role boundary or treating a syntactically successful restore as recovery.

## Ground to load (orchestrator first reads)

- [exists] `/Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828/research/operations/2026-08-28-beyond-sota-data-schema-migrations.md` — panel findings, scars, recommendations, roadmap, and rulings.
- [exists] `apps/backend-rag/backend/app/core/database.py` — application pool and current JSONB codec registration.
- [exists] `apps/backend-rag/backend/app/setup/service_initializer.py` — service-startup pool registrations that must use the same codec object.
- [exists] `apps/backend-rag/backend/tests/fixtures/prod_shaped_pool.py` — current production-shaped test pool fixture; it presently duplicates codec setup.
- [exists] `apps/backend-rag/backend/db/migration_manager.py` — migration execution and `_schema_versions` recording.
- [exists] `apps/backend-rag/backend/db/schema_audit.py` — current schema audit, which does not verify stored migration checksums.
- [exists] `apps/backend-rag/backend/tests/db/test_post_d1_migrations_guard_ledger_owned_ddl.py` — runtime-role ownership guard for ledger-owned DDL.
- [exists] `.github/workflows/restore-drill.yml` — current restore drill; application-level verification is incomplete.
- [exists] `apps/backend-rag/backend/db/migrations_v2/297_wa_outbox_fall_off_reason_finalize_sub_reasons.sql` — highest migration present; `298` was the verified next free number WHEN THIS SPEC WAS WRITTEN; `298_garuda_payment_inbox_quarantine_reason.sql` landed since, so **299** is the next free number (measured on disk 2026-08-31, `ls migrations_v2 | sort -n | tail`). Corrected here rather than in a separate docs PR, per the wave-2 rule that spec corrections ride inside the lane PR.

## PR-1: feat(db): jsonb codec default=str + shared prod-shaped pool fixture + bare-create_pool lint

**Files:**

- [exists] `apps/backend-rag/backend/app/core/database.py`
- [exists] `apps/backend-rag/backend/app/setup/service_initializer.py`
- [exists] `apps/backend-rag/backend/tests/fixtures/prod_shaped_pool.py`
- [proposed] `apps/backend-rag/backend/tests/db/test_jsonb_codec_parity.py`
- [proposed] `scripts/lint_test_pool_codec_parity.py`
- [proposed] `scripts/tests/test_lint_test_pool_codec_parity.py`

**Gear:** Gear 2.

**Build:**

- Define one importable JSONB encoder using `functools.partial(json.dumps, default=str)` and one canonical asyncpg connection initializer in `database.py`.
- Register the canonical initializer in every full and light pool path in `service_initializer.py`; leave no local `json.dumps` registration behind.
- Import that same initializer object from `prod_shaped_pool.py` so tests cannot approximate production codec behavior.
- Preserve caller-side native Python containers; remove any serialization added solely to appease the old codec.
- Add a live round-trip test that inserts a Python array through the pool and asserts `jsonb_typeof(payload) = 'array'` and structural equality after retrieval.
- Add a contrasting scar assertion proving that pre-serialized input still becomes a JSONB string; `$N::jsonb` must not be treated as a bypass.
- Implement an AST-based lint that rejects test-side `asyncpg.create_pool` calls lacking `init=` and identifies file and line.
- Give the lint a temporary guilt tree with a bare pool and an innocence tree using the canonical initializer; scan the real test tree in CI.
- Run the named GARUDA database suites with the canonical codec and require zero JSONB shape regressions.

**Acceptance:**

- Guilt must turn RED: the temporary bare-`create_pool` fixture exits nonzero and names the offending line; a pre-serialized array probe reports `jsonb_typeof = 'string'`.
- Innocence must stay GREEN: the live test tree has no bare pool, and a native Python array round-trips with `jsonb_typeof = 'array'`.
- Suite paths the commands below invoke, verified against `origin/main`: `apps/backend-rag/backend/tests/db/test_jsonb_codec_parity.py` [proposed — this PR's new test]; `apps/backend-rag/backend/tests/db/test_jsonb_double_encoding_class_guard.py` [exists — already carries the double-encoding guard coverage, not a new file]; `apps/backend-rag/backend/tests/services/garuda_orders`, `garuda_portal`, `garuda_documents`, `garuda_ops` [exist — test directories].
- Exact commands from repository root:

```bash
source apps/backend-rag/.venv/bin/activate
python scripts/lint_test_pool_codec_parity.py --root apps/backend-rag/backend/tests
PYTHONPATH=apps/backend-rag pytest scripts/tests/test_lint_test_pool_codec_parity.py apps/backend-rag/backend/tests/db/test_jsonb_codec_parity.py apps/backend-rag/backend/tests/db/test_jsonb_double_encoding_class_guard.py
PYTHONPATH=apps/backend-rag pytest apps/backend-rag/backend/tests/services/garuda_orders apps/backend-rag/backend/tests/services/garuda_portal apps/backend-rag/backend/tests/services/garuda_documents apps/backend-rag/backend/tests/services/garuda_ops
```

**Seats:** Implementer = Sonnet 5 subagent. Refuter = Kimi K3. Family exclusion binds the DIFF BUILDER's family, not the spec drafter's: builder is Anthropic (Sonnet 5 implementer under an Opus 5 orchestrator); the refuter must be a non-Anthropic family (Kimi K3 default, Codex GPT-5.6 sol for security-class diffs); a diff built by a non-Anthropic seat is refuted by a different family. Final gate = orchestrator Opus 5 xhigh.

**Arming / prove-live:** After independent review and merge, a Claude deployment session performs the Fly deploy and an application-pool temporary-table probe. Proof is a timestamped, non-PII result showing `jsonb_typeof = 'array'`; until both deploy and probe exist, record one PENDING-ARMS row.

**Conflicts / order:** Merge before any consumer begins relying on `default=str`. Do not auto-merge. Caller fixes and the shared fixture land atomically so no green interval can hide the defect.

## PR-2: feat(db): migration provenance columns + checksum verification in schema_audit

**Files:**

- [proposed] `apps/backend-rag/backend/db/migrations_v2/299_schema_versions_provenance.sql`
- [exists] `apps/backend-rag/backend/db/migration_manager.py`
- [exists] `apps/backend-rag/backend/db/schema_audit.py`
- [exists] `apps/backend-rag/backend/tests/db/test_migrations.py`; [exists] `apps/backend-rag/backend/tests/db/test_schema_audit.py`; [exists] `apps/backend-rag/backend/tests/db/test_post_d1_migrations_guard_ledger_owned_ddl.py`

**Gear:** Gear 2.

**Build:**

- Add `applied_as`, `applied_via`, and `runner_version` to `_schema_versions` with an explicit rollback section and no reference to ledger-owned objects.
- Populate `applied_as` from PostgreSQL `current_user`, never from a claimed environment value.
- Normalize `applied_via` to `release_command`, `manual`, or `ci`, and make the runner supply it deterministically.
- Store a non-secret runner version for every fresh application while preserving readable legacy rows.
- Recompute each applied migration checksum from the on-disk migration and make `schema_audit` fail with the migration number on mismatch.
- Permit `legacy_fake_checksum` only through an explicit migration-number allowlist whose entries carry written reasons.
- Add fresh-apply, legacy-row, allowed-sentinel, and post-apply-tamper tests.
- Run Squawk against the new SQL and retain the runtime-role ownership guard.
- Preflight object ownership before apply; if `_schema_versions` is not runtime-role-owned, stop rather than broadening grants.

**Acceptance:**

- Guilt must turn RED: modify the bytes of an already recorded fixture migration, run the audit, and require a nonzero result naming migration `299`.
- Innocence must stay GREEN: a fresh apply records the actual database role in `applied_as`, the selected origin in `applied_via`, a nonempty runner version, and an untampered audit passes.
- Exact commands from `apps/backend-rag`:

```bash
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/db/test_migrations.py backend/tests/db/test_schema_audit.py backend/tests/db/test_post_d1_migrations_guard_ledger_owned_ddl.py
PYTHONPATH=. python -m backend.db.schema_audit
```

**Seats:** Implementer = Sonnet 5 subagent. A Codex sandbox verifier must run upgrade, provenance assertions, downgrade, and post-downgrade assertions against a disposable database. Refuter = Kimi K3. Family exclusion binds the DIFF BUILDER's family, not the spec drafter's: builder is Anthropic (Sonnet 5 implementer under an Opus 5 orchestrator); the refuter must be a non-Anthropic family (Kimi K3 default, Codex GPT-5.6 sol for security-class diffs); a diff built by a non-Anthropic seat is refuted by a different family. Final gate = orchestrator Opus 5 xhigh.

**Arming / prove-live:** Apply only through the normal release command after manual gate approval, then run `schema_audit` and query only migration `299` metadata. Proof records role name, origin, runner version, and checksum verdict without credentials or PII.

**Conflicts / order:** Migrations execute as the runtime role. Any DDL touching objects owned by `visa_ledger_owner` aborts the deploy. This migration must avoid those objects; if ownership preflight contradicts that assumption, suspend and require the temporary-GRANT operator[secret] ceremony. Squawk is mandatory, migration PRs are auto-merge-OFF, and the orchestrator merges manually after every gate.

## PR-3: feat(ci): restore drill level-5 application verification

**Files:**

- [exists] `.github/workflows/restore-drill.yml`
- [proposed] `scripts/ci/restore_drill_verify.py`
- [proposed] `scripts/tests/test_restore_drill_verify.py`
- [proposed] `scripts/tests/fixtures/restore_drill/healthy.json`
- [proposed] `scripts/tests/fixtures/restore_drill/degenerate.json`

**Gear:** Gear 1.

**Build:**

- Replace table-count success with Level-5 application verification after restore.
- Query golden invariants for `conversations`, `clients`, `visa_decisions`, `events_outbox`, and `visa_decision_retention_policies`.
- Define a non-degenerate result shape for every invariant: required columns, bounded counts, expected JSON/container type, and relational consistency where applicable.
- Emit one machine-readable verdict per invariant and one aggregate verdict; redact row data.
- Make any missing relation, SQL error, empty required shape, or malformed result fail the drill.
- Execute psql with `ON_ERROR_STOP=1` and shell steps with `set -euo pipefail`.
- Remove every `|| true` from the workflow, including restore, log-tail, query, and notification steps.
- Add recorded healthy and degenerate fixtures so the verifier is testable without production data.

**Acceptance:**

- Guilt must turn RED: the degenerate fixture returns nonzero and names every failed invariant rather than reporting aggregate success.
- Innocence must stay GREEN: the healthy fixture returns zero with five explicit PASS verdicts, and the workflow contains no `|| true`.
- Exact commands from repository root:

```bash
apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_restore_drill_verify.py
apps/backend-rag/.venv/bin/python scripts/ci/restore_drill_verify.py --fixture scripts/tests/fixtures/restore_drill/healthy.json
apps/backend-rag/.venv/bin/python -c "from pathlib import Path; assert '|| true' not in Path('.github/workflows/restore-drill.yml').read_text()"
```

**Seats:** Implementer = Sonnet 5 subagent. Refuter = Kimi K3. Family exclusion binds the DIFF BUILDER's family, not the spec drafter's: builder is Anthropic (Sonnet 5 implementer under an Opus 5 orchestrator); the refuter must be a non-Anthropic family (Kimi K3 default, Codex GPT-5.6 sol for security-class diffs); a diff built by a non-Anthropic seat is refuted by a different family. Final gate = orchestrator Opus 5 xhigh.

**Arming / prove-live:** After merge, manually dispatch one restore drill against the approved isolated target. Close the PENDING-ARMS row only when all five per-invariant verdicts and the aggregate verdict are PASS.

**Conflicts / order:** Land after PR-2 so restored schemas are checksum-audited. This PR does not authorize a production restore or relax notification failures.

## Spec corrections applied in-lane (2026-08-31, Squad D')

- **Every `pytest ... -q` above was unrunnable as written.** `main` now carries
  `scripts/pytest_guards/pytest_verbosity_guard.py`, which exits **RC=4** under
  `apps/backend-rag/pytest.ini` (whose `addopts` already lower verbosity) with
  *"effective verbosity is -2: pytest would print no pass/fail tally, so this
  run cannot be read as evidence that anything ran."* The `-q` flags are
  removed above. Measured, not reasoned: the first acceptance run of PR-1 died
  on exactly this.
- **`298` -> `299`.** See PR-2's file list.
- **PR-1's caller-fix scope was incomplete and the spec's own A/B requirement is
  what exposed it.** Converting the four writers to native containers breaks any
  test whose pool is bare. Two such files existed outside the spec's stated file
  list (`services/garuda_portal/test_practice.py`,
  `app/routers/test_garuda_orders_ownership.py`) and both are converted in PR-1,
  because the spec's own ordering rule requires the caller fixes and the fixture
  to land atomically. A third defect class was found by the blind refutation: a
  FOURTH codec-registering pool (`backend/scripts/kg_staging_promotion.py`) that
  the spec's three-file list did not name.

## Needs-ruling carried (Zero only)

1. **Crypto-shredding scope (R7):** which data classes get per-subject keys, and whether erased-subjects-persist-in-backups is acceptable as documented risk instead. Business/legal stance under UU PDP, not engineering.
2. **Qdrant estate disposition:** the 14 dead definitions and 8 undefined live collections include client-serving surfaces; deleting/renaming live collections is a product decision (which corpora are load-bearing for balizero.com answers).
3. **Standing authorization for the temporary-GRANT ceremony:** each ledger-owned DDL currently needs a superuser session (`GRANT visa_ledger_owner TO backend_rag_v2` → apply → revoke → re-measure). Until R1 makes this rare, Zero should ratify the ceremony as a standing operator[credential] procedure with its own ledger line — today it exists only as a guard-test docstring precedent.

## Suspend & ledger rules

- Three RED results from the same cause mean SUSPEND: do not attempt a fourth round.
- On suspension, append one PENDING-ARMS line naming the artifact, repeated cause, owner class, missing arming action, and falsifiable proof required to close it.
- Every built-but-not-armed deploy, migration apply, live probe, or restore drill gets exactly one PENDING-ARMS row.
- A suspended migration remains auto-merge-OFF; no grant, apply, deploy, or re-run may substitute for the missing ruling or owner action.

## Out of scope

- Declarative catalog contracts, consumer-reference lint, Qdrant alias migration, and crypto-shredding design.
- Deleting or renaming Qdrant collections, executing operator[secret] grants, production restore, and any deployment outside the stated prove-live handoffs.
