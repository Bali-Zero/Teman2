# Kimi council: CI bootstrap cure

Actual subscription CLI kimi-code/k3; new stateless CI-only review with initial report and prior gate adjudication supplied as context. No runtime re-review claimed.

• **Verdict: PASS**

Static review only of the supplied delta and full bootstrap file. I executed no tests, ran no commands, and read nothing beyond this prompt; I did not re-review any runtime source.

**Scope checked:** the 36-line `portal_messages` block added to `apps/backend-rag/scripts/ci_bootstrap_schema.py` (delta hunk at ~line 400).

**P0 blockers:** none.

**P1 blockers:** none.

Verified statically:

1. **DDL fidelity** — The CREATE TABLE and three CREATE INDEX statements are character-identical to the supplied canonical legacy DDL: same columns, types, nullability, `CHECK (direction IN (...))`, FK actions (`ON DELETE CASCADE` on `client_id`, `ON DELETE SET NULL` on `practice_id`), `DEFAULT NOW()`, and both partial-index predicates (`WHERE practice_id IS NOT NULL`, `WHERE read_at IS NULL`). `id SERIAL` gives the integer PK that 321's `REFERENCES portal_messages(id)` requires.
2. **Ordering/FKs** — The block sits after `SQLModel.metadata.create_all(engine)`, which materializes `clients` and `practices`; both FK targets therefore exist before execution. The whole bootstrap still runs before `apply-all`, so 321 sees the table. Placement ahead of the `documents` block is harmless (no interdependency).
3. **Idempotency** — Every statement uses `IF NOT EXISTS`; reruns against a non-empty DB are no-ops. `text()` is already imported in the earlier `from sqlalchemy import ... text` line, so no NameError.
4. **Production isolation / strict321** — The cure touches only the CI-only script (docstring: "NOT for prod"); `321_portal_reply_and_email.sql` is unmodified, so sha256 `aa2a9402…ae38be` stands and no re-hash/re-ledger is triggered (cure spec point 2 is conditional and its condition is not met). No guard, no skip — 321 still fails loudly if the table is absent, as required.

**P2 (non-blocking):**

- **P2-1 — Silent drift risk.** The mirrored DDL is a hand copy of `migration_031_client_portal.py`. Because `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` succeed on name match alone, any future divergence between the legacy file and this mirror is masked. Suggest a pinned comment cross-reference (as done for `lkpm_reports` ↔ migration_063) or a CI schema assertion. Reference: new block, `ci_bootstrap_schema.py` ~lines 403–436.
- **P2-2 — Observability nit.** Unlike the `documents`, `team_members`, and `lkpm_reports` blocks, the new block emits no `[bootstrap] ... ensured` print, and the earlier summary print ("legacy tables ensured in DB (...)") was not extended to mention `portal_messages`. CI logs won't show the step; cosmetic only.

No tests were executed by this seat; CI-green remains unverified here.
