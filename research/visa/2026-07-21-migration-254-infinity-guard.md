---
date: 2026-07-21
domain: visa
client_case: none (engine correctness hardening — Visa Oracle decision engine)
adversarial_review: kimi
sources:
  - apps/backend-rag/backend/db/migrations_v2/252_visa_engine_write_substrate.sql (proven mirror pattern — reject_visa_source_records_mutation + recorded_period CHECK)
  - apps/backend-rag/backend/db/migrations_v2/250_visa_engine_core.sql (legal_period lower '-infinity' guard, live on prod)
  - apps/backend-rag/backend/db/migrations_v2/253_visa_activation_writer_hardening.sql (latest reject_visa_activation_mutation body + NOT VALID/VALIDATE precedent)
  - prod read-only query (pg_constraint on visa_ruleset_activations / visa_source_records)
  - .claude/skills/modus/PENDING-ARMS.md line 396 (the ENFORCE-prereq gap)
---

# Migration 254 — visa_ruleset_activations system_period sentinel-timestamp guard

## What

Roll-forward migration 254 closes a temporal-integrity gap in the Visa Oracle activation ledger
(`visa_ruleset_activations`, bitemporal append-only-with-close). It is an ENFORCE-prereq
(modus PENDING-ARMS line 396) — a wrong-answer / corruption vector once ENFORCE flips.

Two guards on the `system_period` (transaction-time) range, closing the full ±infinity sentinel
family on that column:

1. **Upper `'infinity'` close guard.** `reject_visa_activation_mutation()` previously validated
   closing an open `system_period` with only `upper(NEW.system_period) IS NULL`. Postgres treats an
   upper bound explicitly set to `'infinity'::timestamptz` as a present (non-NULL) value distinct
   from an unbounded range end (`upper()` returns `'infinity'`, `upper_inf()` stays false), so such
   an UPDATE slipped past the NULL-only guard while never really closing the period — a supersession
   dead-end (the "already closed" guard only fires on a non-NULL upper; the GiST EXCLUDE constraint
   would still treat the row as overlapping any new activation over the same scope/legal_period,
   silently blocking every future supersession). Widened to reject `IS NULL OR = 'infinity'`, plus a
   table CHECK `visa_ruleset_activations_system_period_not_infinite`.

2. **Lower `'-infinity'` start guard** (class-audit sibling, surfaced by the cross-family review).
   `system_period` had NO lower-bound sentinel guard, unlike `legal_period` (migration 250) and
   `recorded_period` (migration 252), which both guard `lower(...) <> '-infinity'::timestamptz`.
   system_period is transaction-time and must always have a finite real start. Added table CHECK
   `visa_ruleset_activations_system_period_lower_finite`, mirroring legal_period's live-on-prod guard.

## Design

- **Roll-forward, never an in-place edit** (cicatrix #9 / W88 extended to migration files): 250/251/253
  are already applied to prod and immutable on disk. 254's forward `reject_visa_activation_mutation()`
  is byte-identical to **253's** current body (the latest declaration) except the widened close IF;
  254's rollback restores that exact 253 body and drops only its own two CHECKs.
- Mirrors migration 252's already-reviewed identical fix for the sibling `visa_source_records` table.
- CHECKs added `NOT VALID` + separate `VALIDATE CONSTRAINT` (253's own ALTER-on-this-table precedent),
  single transaction (migration_base.py wraps forward SQL in one tx); both tables 0 rows on prod, so
  VALIDATE is instant. A poisoned pre-254 row would fail VALIDATE loudly → whole migration rolls back
  (fail-closed, no corruption).
- Firebreak unchanged: SHADOW-only, no HTTP surface consults this writer yet; ENFORCE flip stays a
  Legge-5 operator decision gated on the operator provisioning bundle.

## Adversarial review — cross-family gate outcomes (2026-07-21, R1 record)

Generator = Sonnet 5 (implementer). Graders = Fable 5 (final on-disk gate) + two cross-family seats.
Codex (all gpt-5.x → 400 on this ChatGPT account) and GLM (Keychain token absent) declared DEAD.

- **Gemini 3.1 Pro (agy)** — **NO MATERIAL FINDINGS.** Confirmed: guard has no bypass (value-based
  comparison; `-infinity` upper → empty range → rejected by existing `NOT isempty`); CHECK correct under
  three-valued logic; rollback a byte-for-byte restore of 253; trigger pointer intact; tests real
  (specific exception types, both trigger-UPDATE and CHECK-INSERT paths); NOT VALID+VALIDATE in one tx
  safe on a 0-row table.
- **Kimi K3 (Moonshot)** — **NO MATERIAL FINDINGS**, verified against actual git history (byte-diffed
  254-forward vs 253-forward; 254-rollback == 253 body identical; confirmed the BEFORE-INSERT trigger
  never inspects system_period, so the INSERT-path rejection is attributable to the new CHECK alone;
  inspected the conftest change and found it legitimate — applies 254's real forward SQL, no
  reward-hacking). Its one substantive theoretical concern (is `'infinity'::timestamptz` immutable
  enough for a CHECK?) it resolved itself (the literal cast folds to a Const at parse time — no stable
  function survives in the stored expression). It surfaced two minor test nits (INSERT test should
  assert constraint_name; finite-close innocence had a 5ms clock-skew flake) and one class-audit
  observation (the missing lower `'-infinity'` guard). ALL THREE were then folded into the same commit.
- **Fable (this session) — empirical prod verification** (read-only): `visa_source_records_recorded_period_check1`
  = `CHECK (upper(recorded_period) IS NULL OR upper(recorded_period) <> 'infinity'::timestamptz)` is
  LIVE on prod — proving Postgres accepts this exact CHECK shape in production (refutes Kimi's
  immutability concern empirically) and that migration 252's identical fix applied. `legal_period`'s
  `lower(...) <> '-infinity'` guard is also live on prod (proves the lower-guard pattern). And
  `visa_ruleset_activations` had NEITHER a system_period infinity guard NOR a lower guard — confirming
  the gap 254 closes is real and still open on prod.

Verdicts are LEADS (W65): every claim above was re-verified on disk / against prod in-turn, not taken
on the graders' word.

## Tests & verification

- 5 tests in `test_activation_writer.py`: 3 guilt (upper-close UPDATE → RaiseError match "finite
  system_period"; upper INSERT → CheckViolationError on `..._not_infinite`; lower INSERT →
  CheckViolationError on `..._lower_finite`) + 2 innocence (legitimate finite close still succeeds,
  clock-skew-proof; normal open/NULL-upper bootstrap insert still succeeds).
- Guilt-fails-without-guard proven for BOTH new guards (disable the guard → the matching guilt test
  DID NOT RAISE; restore → green).
- Full `visa_engine` suite: 1064 passed, 1 skipped. Squawk migration-lint: 0 issues.
- conftest `visa_schema` fixture wires 254 into the chain (250→251→253→254, reverse-order rollback),
  so the guards are actually present when the tests run (not a green-but-testing-nothing trap).

## Follow-up (not this migration)

None from this migration's own scope. The larger ENFORCE-prereq `replace_activation_set` (atomic
legal_period-narrowing writer, PENDING-ARMS line 378) remains a separate, still-open increment
needing its own design pass.
