---
date: 2026-07-21
domain: visa
client_case: none
adversarial_review: kimi-k3
sources:
  - apps/backend-rag/backend/db/migrations_v2/255_visa_shadow_evidence.sql
  - apps/backend-rag/backend/services/visa_engine/shadow_evidence.py
  - apps/backend-rag/scripts/visa_shadow_evidence.py
  - apps/backend-rag/backend/tests/services/visa_engine/test_shadow_evidence.py
  - apps/backend-rag/backend/tests/scripts/test_visa_shadow_evidence.py
---

# Visa Oracle v2 — SHADOW evidence collection receipt

**Date:** 2026-07-21
**Lane:** `backend-rag-visa-oracle-shadow-evidence`
**Scope:** prepare re-runnable, PII-free evidence for G-a and G-c. This work does not
activate SHADOW or ENFORCE, change Fly secrets, merge, or deploy.

## Current production observation

- PR #2916 (STEP-6c Match SHADOW wiring) merged at `8b28ac418481`.
- PR #2930 (HMAC facts-fingerprint identity provider) merged at `09f7cd2273c9`.
- PR #2952 (finite activation-system-period guard) merged at `60c6f348c9a4`.
- Fly release 3888 is deployed.
- The only deployed `VISA_ENGINE_*` secret is
  `VISA_ENGINE_TRUST_STORE_KEYS_JSON` (digest `a68f076bc9993f0c`).
  `VISA_ENGINE_MATCH_MODE` and `VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON` are absent.
  Because the code defaults the Match mode to OFF and the identity provider fails closed
  without a fingerprint key, real production SHADOW collection is currently dark.
- The read-only production query was not run: the local Keychain has no password for
  `nuzantara_readonly`, and `psql` rejected the connection with
  `fe_sendauth: no password supplied`. No broader/write-capable credential was used.

Therefore the objective gate remains **RED**. The absence of runtime prerequisites is
enough to prove that no new STEP-6c SHADOW evidence can currently be produced, but the
database row count and active PRODUCTION pack remain unverified until read-only access is
restored.

## Why migration 252 is insufficient for the gate

The existing audit row has a new `decision_id` on a later evaluation of the same Match
request and does not store the Match category, candidate-code breadth, or a claim-to-source
map. It therefore cannot objectively prove distinct-request volume, the seven-category
coverage, 30-code breadth, or zero ungrounded claims.

Migration 255 adds only non-PII audit metadata:

- `request_fingerprint`: SHA-256 of the random 16-character Match token, never the token or
  applicant facts;
- `request_category`: the closed Match `Purpose` enum;
- `candidate_summary`: product/rule/reason/source identifiers only;
- `grounding_summary`: verdict/claim codes mapped to source-record UUIDs.

Historical rows remain valid but fail the collector closed because their new correlators
and grounding projection are absent. Every new writer row also carries the exact
`ruleset_activation_id` selected by the bitemporal resolver.

## Collector semantics

`backend.services.visa_engine.shadow_evidence` reads only the PII-free SHADOW projection and
emits aggregate counts/dates/categories/product codes. It returns no decision IDs, Match
tokens, request fingerprints, or facts.

- **G-a** is green only with at least 1,000 distinct request fingerprints, a seven-day
  minimum report window plus a seven-day consecutive UTC streak, all seven substantive Match
  categories, at least 30 distinct product codes, no malformed metadata, and every counted
  product-version/code pair present in the persisted signed rule pack.
- **G-c** is green only when every row has an activation binding and persisted pack digest,
  every substantive claim has at least one citation, claimed and flattened citation sets
  match exactly, every cited source exists in the persisted pack, has `VERIFIED` status and
  a canonical URL, and contains the decision's legal and recorded timestamps. An explicit
  `NEEDS_INPUT` verdict may carry no citations only when its sole verdict claim is an
  abstention with no source references; this implements the gate's rule that abstaining on
  thin evidence is a pass, without granting the exception to any substantive verdict,
  outage, or reason claim.
- **G-b** and **G-d** are always `UNMEASURED` in this collector. Consequently its top-level
  `enforce_ready` is hard-coded `false` and `gate_status` remains `RED`, even when the
  synthetic G-a/G-c proof is green.

Re-runnable command after migration 255 is reviewed/deployed, SHADOW prerequisites are
provisioned, and the read-only DB credential is restored:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. python scripts/visa_shadow_evidence.py \
  --start 2026-07-21T00:00:00Z \
  --end 2026-07-28T00:00:00Z \
  --environment PRODUCTION
```

The database URL must be supplied via a read-only environment variable. The CLI also sets
`default_transaction_read_only=on` on every PostgreSQL connection.

## Verification receipt

- `ruff format` + `ruff check`: pass.
- `mypy` on the three changed production Python modules: pass.
- Python compileall: pass.
- Migration-number lint: 138 files, unique prefixes.
- `test_shadow_evidence.py`: 5/5 pass, including a 1,000-request all-breadth synthetic proof
  that still cannot arm ENFORCE.
- `test_shadow_match.py`: 31/31 pass, including migration 252→255, activation-bound write,
  idempotency, and end-to-end Match SHADOW persistence.
- Full `backend/tests/services/visa_engine`: 1,070 collected; 0 failures, 0 errors, and one
  pre-existing operational skip because `visa_activation_executor` is not provisioned.
- `git diff --check`: pass.

## Adversarial review

Kimi independently re-reviewed the four-commit SHADOW evidence series. The final verdict was
`READY_FOR_DRAFT_PR`, with no high- or medium-severity findings. The re-review recorded M1, M2,
L1, and L2 as closed.

## Gate snapshot

| Gate | State | Evidence / blocker |
| --- | --- | --- |
| G-a | RED / unmeasured | Production Match mode is OFF; no compatible seven-day audit window exists yet. |
| G-b | UNMEASURED | Canonical persona tests pass locally, but this collector intentionally does not grade or certify the independent replay. |
| G-c | RED / unmeasured | No production SHADOW window; active pack and persisted citations could not be queried read-only. |
| G-d | UNMEASURED | Live ENFORCE→OFF drill is deliberately not attempted before the other gates are green. |

**Decision:** keep ENFORCE OFF. Next safe sequence is independent review of this diff, then
migration/runtime provisioning through the normal PR/deploy process, seven-day SHADOW
collection, independent G-b evidence, and only then the G-d drill.
