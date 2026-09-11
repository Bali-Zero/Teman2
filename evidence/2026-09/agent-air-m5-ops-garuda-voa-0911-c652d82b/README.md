# GARUDA VOA option D: preparation and independent database proof

Date: 2026-09-11 WITA. Zero selected D in this session. BLUE, external prepare-only;
mandate `garuda-voa-0911`, branch `agent/air-m5/ops/garuda-voa-0911`.
No production writes, secret changes, merge, arming or deployment were performed.

## Result and ownership of the work

The dedicated migrator design works for the full 304 migration on the observed
production prerequisites. **50 targeted tests passed**, including real PostgreSQL
execution, with two inherited asyncio-marker warnings. The disposable PG17 cluster
was stopped after each run; no operational dev database was used.

The implementation already belongs to the sibling branch
`agent/air-m5/db/voa-migrator-role`. This window did not edit that worktree or open a
competing PR. Instead it copied a stable working-tree snapshot into the broker-created
Pro worktree `db-voa-d-proof-0911`, tested it, and prepared two follow-ups:

- `runner-selection-followup.patch`: bind the selected URL and dedicated/legacy mode
  together for pool setup and migration application. Explicit alternate dedicated
  URLs can set `dedicated=True`; a different explicit legacy URL keeps legacy behavior.
  Corrects the adjacent inaccurate RESET ALL comment and updates one test double.
- `migration-304-owner-bracket.patch`: exactly two statements around the existing
  owner-transfer block. Applies to the 304 SQL in #5526, head
  `6ea6eb9adec597646300fe8d10f8be870dcfb9bd`.

`runner-baseline-manifest.json` pins the six sibling source/test files, read from the
working tree at base `be45266252f4e1ccbaf19d2b81c73f03af676e05`. These are not claims
about the sibling's later edits. `tested-candidate-hashes.json` pins the resulting
runner/test files and the bracketed SQL. Do not apply a patch to changed bytes blindly.
The runner patch is supplementary to that sibling implementation, not a standalone
patch against main. The SQL patch is supplementary to #5526, not all of #5526.

## Evidence

The original snapshot failed the explicit-override regression while the three full
304 tests passed: **1 failed, 3 passed in 0.97s**. A globally configured migration DSN
incorrectly imposed dedicated-role checks on an explicitly selected legacy URL.
After the follow-up: **50 passed, 2 warnings in 1.73s** across:

```text
test_option_d_304.py                                       6 independent cases
backend/tests/db/test_migration_runner_dedicated_role.py
backend/tests/db/test_migration_base_tracking.py
backend/tests/db/test_migration_advisory_lock.py
backend/tests/db/test_migration_apply_strips_rollback.py
backend/tests/unit/app/test_config.py
```

The independent cases execute the complete 304 forward SQL, not a dummy binder:

1. Original SQL fails owner transfer and leaves neither document tables nor a 304
   entry in either ledger.
2. Bracketed SQL through the manager and standalone runner leaves both document
   tables and tracking tables owned by `backend_rag_v2`, the SECURITY DEFINER binder
   owned by `visa_ledger_owner`, and other new functions owned by runtime.
3. Both ledgers contain exactly one 304 entry after runner replay; provenance is
   `backend_rag_v2 (session_user=backend_rag_migrator)`.
4. Runtime still lacks ledger membership and cannot itself lock the policy table
   FOR SHARE. The binder can insert synthetic document metadata with a test-only
   policy; without one it rejects the insert. No passport image or extracted value
   is used or stored by the test.
5. An explicit legacy connection remains legacy despite a globally configured
   dedicated DSN; a manager freezes URL and mode together if settings later change.
6. Pool checkout restores runtime after a borrower explicitly RESETs its role.

The existing tests also cover dedicated superuser rejection, role membership,
connection cleanup, locking and rollback separation. They do not prove that every
historical migration can bootstrap a blank production installation under D.

## Reproduction on Pro

Copy the manifest-pinned sibling files and the pinned 304 SQL to a dedicated
worktree, together with this evidence directory. Save the manifest also as
`voa-d-candidate-manifest.json` at that worktree's root. Then:

```bash
python3 evidence/2026-09/agent-air-m5-ops-garuda-voa-0911-c652d82b/prepare_followup_patch.py
cd apps/backend-rag
~/nuzantara/apps/backend-rag/.venv/bin/python \
  ../../evidence/2026-09/agent-air-m5-ops-garuda-voa-0911-c652d82b/run_disposable_pg.py \
  ../../evidence/2026-09/agent-air-m5-ops-garuda-voa-0911-c652d82b/test_option_d_304.py \
  backend/tests/db/test_migration_runner_dedicated_role.py \
  backend/tests/db/test_migration_base_tracking.py \
  backend/tests/db/test_migration_advisory_lock.py \
  backend/tests/db/test_migration_apply_strips_rollback.py \
  backend/tests/unit/app/test_config.py
```

The driver uses the installed PG17 binaries, binds a new temporary cluster to
127.0.0.1 on an allocated port, overrides all test DSNs, and stops it in `finally`.
This is a local trust-authenticated test cluster, never a production credential.

## Production read-back in this session

SELECT only via `ssh pro` and `scripts/pg.sh`, role `nuzantara_readonly`:

| Observation | Result |
| --- | --- |
| Runtime SELECT on the policy table | true |
| Runtime REFERENCES on the policy table | true |
| Policy scope enum already contains GARUDA_DOCUMENT | true |
| Policy-table owner | visa_ledger_owner |
| backend_rag_migrator role exists | false |
| garuda_documents exists | false |
| Active PRODUCTION GARUDA_DOCUMENT policy count | 0 |

These explain why the two-line 304 patch is sufficient for the measured schema.
A fresh split-owner schema without the widened scope or REFERENCES grant needs
separate preparation; this patch does not silently grant new runtime privileges.
The role's memberships and PostgreSQL SET ROLE semantics are described in the
[PostgreSQL 17 reference](https://www.postgresql.org/docs/17/sql-set-role.html).

## Meta-pattern

The recurring defect is treating a selected credential, its effective role, object
ownership and the tracking database as if one implied all the others. They must be
verified together at execution: URL/mode are bound once, server identity determines
ownership and provenance, and actual SQL tests both success and atomic failure.

## Solo-operatore and release boundary

The exact owner-run provisioning and read-back are in `OPERATOR-D.md`. This is the
existing operator boundary in `docs/runbooks/prod-db-writes.md`, not another D/E vote.
The independent BLUE release owner must review/integrate the sibling runner plus
follow-ups, verify the provisioned prerequisites, and release through the normal
runner. Do not apply 304 with naked psql; it would bypass both migration ledgers.

**The missing retention policy is a separate observed prerequisite.** Zero's D
decision does not choose an interval. The initial mandate proposed 90 days after
delivery; this document-outcome binder requires CREATED_AT and does not persist
passport images or OCR field values. Prepare/sign the appropriate policy through
the existing policy authority before claiming persisted intake. No policy was seeded.

The two-line forward patch does not repair 304's existing rollback under split
ownership: the runtime cannot drop a ledger-owned binder or narrow a ledger-owned
scope constraint. Normal production release is forward-only; if rollback is required,
prepare and independently test its ownership choreography first.

Independent final review: **no verdict returned**. The earlier read-only OAuth CLI
attempt timed out after 150 seconds. A fresh restricted read-only invocation on
OAuth slot 2, requested `claude-opus-5` / `xhigh`, also timed out after 180 seconds.
`independent-review.json` records this second attempt. Neither effective model nor
quota cause was confirmed; no claim that all review seats are unavailable is made.
Test success is not an independent release gate. The prepared patches require that
gate before the BLUE release owner integrates and releases them.
