---
adversarial_review: kimi-k3, codex-gpt-5.6-sol, gemini-3.1-pro
---

# Freeze-change proposal 002 — the two validators disagree on one spelling, and 001's cost premise has expired

- **From**: R1 DESIGN battle window (Research OS tranche, P06 slice 2), branch
  `agent/nuzantara/backend-rag/r1-research-os-design`
- **To**: S9-C0 (Conductor), via the staff room
- **Date**: 2026-09-11
- **State**: `awaiting_conductor_decision` — R1 does not edit `packages/research-os-core/**`; this
  proposal is filed instead, per the mandate's D9 ("a contradiction becomes
  `evidence/p04/freeze-change-proposal-002.md`") and R1 §2 ("a needed change is a freeze-change
  proposal, not an edit").
- **Measured at**: 2026-09-11, worktree `.worktrees/backend-rag-r1-research-os-design`, base
  `9304392d1a`, against `packages/research-os-core` byte-identical to `origin/main`.
- **Relationship to 001**: 001 is still `awaiting_conductor_decision` and PR #4615 is still
  suspended unarmed. **This proposal does not re-litigate 001 and does not depend on its outcome.**
  It adds one axis 001 does not cover, and reports that one of 001's own stated premises has since
  expired. If the Conductor decides 001 by narrowing the pattern to a single spelling, §1 here is
  answered as a side effect — that is noted in §4, not assumed.

## 0. How this was found, and how it was nearly reported wrong

`kimi-code/k3`, reviewing this window's candidate, asked a question it could not settle from the
bytes it had been given: the reference reader accepts a lowercase `z` terminator — does the
published schema? That is a question, not a finding, and it was treated as one.

The first measurement taken to answer it **was wrong, and its error is worth recording because it
is the error this document exists to avoid**. Rewriting `time/valid_from` inside a real canonical
Claim and re-validating produced three apparent splits (`z`, `.1Z`, `.1234567Z`). Two of them were
artefacts of the measurement: the rewrite changed the bytes without recomputing `object_hash`, so
`model_validate` was rejecting a **hash mismatch** and the result was being read as a verdict on
the **spelling**. Reported as-is, this proposal would have asserted that pydantic rejects `.1Z` —
which is false. The measurement below separates the two effects deliberately.

## 1. The finding (EFFECT 1 — spelling admissibility, `object_hash` out of the picture)

`_UTC_OFFSET_PATTERN` (`primitives.py:84`) is `r"(?:Z|\+00:00)$"` and is published into every
exported JSON Schema through `WithJsonSchema` on `UtcDateTime` (`primitives.py:362`). The pydantic
validator and that published pattern disagree on exactly one admitted spelling:

```
spelling                          json-schema pattern   pydantic UtcDateTime
2026-01-01T00:00:00Z                           ADMITS                 ADMITS
2026-01-01t00:00:00Z                           ADMITS                 ADMITS
2026-01-01T00:00:00z                          REJECTS                 ADMITS   <-- SPLIT
2026-01-01T00:00:00+00:00                      ADMITS                 ADMITS
2026-01-01T00:00:00.000000Z                    ADMITS                 ADMITS
2026-01-01T00:00:00.1Z                         ADMITS                 ADMITS
2026-01-01T00:00:00.1234567Z                   ADMITS                 ADMITS
```

One instant, one contract version, two validators, two verdicts. Note the asymmetry with the
lowercase **`t`**, which both admit: the pattern is anchored only at the end of the string, so it
never constrains the separator, while it does constrain the terminator's case.

**This is not theoretical for this tranche.** The P06 fixture bundle's guard module
(`test_research_os_p06_fixture_bundle.py`, added by this window) validates every canonical object
with `jsonschema.Draft202012Validator` **and** with its pydantic model, side by side, on the same
bytes. A fixture carrying a lowercase `z` would pass one and fail the other in the same test.
Measured on a real canonical Claim from the seed cohort: jsonschema REJECTS, pydantic ADMITS.

## 2. EFFECT 2 — the hash-identity axis, reported here only to keep it out of §1

With `object_hash` **recomputed** over the rewritten bytes, the picture is different and belongs to
001, not to this proposal:

```
spelling                          jsonschema   pydantic (hash recomputed)
2026-01-01T00:00:00Z                  ADMITS                      ADMITS
2026-01-01t00:00:00Z                  ADMITS                     REJECTS
2026-01-01T00:00:00z                 REJECTS                     REJECTS
2026-01-01T00:00:00+00:00             ADMITS                     REJECTS
2026-01-01T00:00:00.000000Z           ADMITS                     REJECTS
2026-01-01T00:00:00.1Z                ADMITS                     REJECTS
2026-01-01T00:00:00.1234567Z          ADMITS                     REJECTS
```

Every rejection here is 001 §2.1/§2.2 reproduced: the model path re-renders through
`model_dump(mode="json")` and the dict path hashes the wire bytes verbatim, so a schema-legal
document that is not already in the model's preferred rendering cannot carry a hash both paths
accept. **No decision is asked for on this axis here** — it is 001's, and it is listed only so that
a reader comparing the two tables does not mistake it for part of §1.

## 3. What has changed since 001 was written: its cost premise has expired

001 §2.6 states its "practical cost is zero" conclusion rests on a premise it verified and whose
expiry it named honestly: *"nothing outside `packages/research-os-core` imports `research_os` today
except its own tests, so the fixture universe genuinely is the whole universe"* — and *"names the
conclusion's expiry condition: the day a consumer is written."*

**That day has arrived.** Measured on this base sha, outside the core:

```
apps/backend-rag/backend/services/research_os/{action_intent_adapter,action_item_adapter,
    operational_receipt_adapter,synthesis,_core_path,__init__}.py
apps/backend-rag/backend/services/autonomous_lab/consul_native_broker.py
apps/backend-rag/backend/services/autonomous_lab/consul_executor.py
```

`consul_executor.py` is not a reader: it carries an executable `INSERT INTO research_os_objects`
with replay verification, and it hashes payloads before validation. It is inactive in production
today (0 rows), but it binds the contract. And R2 — the sibling window of this same tranche — is
building `services/research_os/naga_persistence.py` against `research_os_objects` now, under an
authority (Z2a) that expires 2026-09-25T00:00Z.

So the cost of deciding 001 is no longer "rewrite some fixtures". It is now also "agree with
whatever R2's persistence API and D2's SQL key do with these spellings" — and D2 specifies a key
grammar that normalises exactly this ground (separator uppercased to `T`, `+00:00` → `Z`, fraction
to six digits). A spelling the SQL key folds but one validator rejects is a row that can be written
and then fail validation on read-back.

## 4. What is asked

One decision, on §1 only:

- **(a) Narrow the published pattern** so it admits exactly what the validator admits — or
- **(b) Widen the validator** so it admits exactly what the pattern admits — or
- **(c) Rule that the published pattern is advisory** and name which validator is authoritative for
  the contract, so consumers stop having two answers.

R1 takes no position between them and has changed nothing: `git diff --stat origin/main --
packages/research-os-core` is empty on this branch, and stays empty. **(a) would be answered as a
side effect if the Conductor resolves 001 by narrowing to a single spelling** — if that happens,
this proposal needs no separate decision and should be closed against 001's.

## 5. What this proposal does NOT claim

- It does not claim pydantic rejects sub-six-digit fractions. It does not — see §0 and §2.
- It does not claim any fixture in the repository currently carries a lowercase `z`. None does; the
  seed cohort and the 218-fixture corpus validate clean under both validators today
  (`fixtures --check` → `{"checked": 218, "failures": [], "valid": true}` on this branch).
- It does not claim the split is reachable through the sanctioned serializer. It is reachable
  through a hand-written or externally-produced document, which is precisely what the admission
  path in D4 exists to receive.
