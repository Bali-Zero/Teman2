---
date: 2026-08-19
domain: visa
client_case: none — engine doctrine work (E5 increment 4, seq-10 cure rationale)
sources:
  - research/visa/doctrine-factory/e5/inc4-pack-edits/freshness-restamp-2026-08-19.md
  - research/visa/doctrine-factory/claims/inc4-c2-e31c-claim-ledger.md
  - research/visa/doctrine-factory/e5/2026-08-19-e5-increment4-spec.md
discovered_by: agent.air-m5.backend-rag.visa-e5-seq10
adversarial_review: codex
---

# Cure rationale — el.c2.corporate-sponsor-type / el.e31c-mixed-marriage-parents (seq-10)

Companion prose for `cure-c2-e31c.json` + `inc4-rule-manifest.json` (the machine-applied
edits). The disease in both rules is the e33g class CP3 named: an outer `all(X, X)` with
byte-identical children (VACUOUS-RULE lint) whose `reason_code` promises a check the
condition never performs.

## C2 — retired, not tightened (grounding attempt refuted)

CP3's assignment was to ATTEMPT a grounding batch for a `sponsor.type` tightening.
Executed 2026-08-19; outcome:

- The live C2 page states no sponsor is needed by default (verbatim in the freshness
  doc §"C2 grounding probe") — the exceptions are applicant-status-driven, never
  entity-type-driven, and no corporate-sponsor language exists on the page.
- The production catalog says `sponsor_required: false` / `invitation_required: true`.
- `CL-C2-03` (VERIFIED-WITH-CAVEAT) reads Permenkumham 11/2024 Pasal 1(18) as
  penjamin-mandatory. Product metadata says `sponsor_types: ["EMPLOYER"]`
  (not evaluator-consumed).

Three-way conflict → **CF-17** (claims ledger, OPEN). No compilable claim can name a
`sponsor.type` value, so tightening would be fabrication — the exact thing the CP3
stop-rule forbids. The remaining honest cure: the rule's deduplicated subtree is
**canonical-JSON-identical to `el.c2.business`'s entire `when`** (asserted live by the
fold's `_apply_retirement` gate, not assumed from authoring time), both effects are
SUPPORT over the same `covered_purposes`, so removal is behavior-preserving by
construction. Witness pair in `test_seq10_pack.py::TestC2RetirementPreservesBehavior`:
the same facts SUPPORT on both packs; seq-9's proof carries the false-promise rule,
seq-10's does not. `el.c2.business`'s own `family.sponsor_confirmed` gate is
deliberately KEPT (conservative — the engine asks for more, never grants on less);
re-opening it is CF-17's future doctrine question, not this increment's.

## E31C — tightened + paired HARD_FILTER (grounding succeeded)

The live E31C page (full Persyaratan transcribed in the freshness doc §8) grounds both
predicates the doctrine card said were missing:

- `family.marriage_registered == true` ← item 8 (proof of the parents' legally
  registered marriage, two routes) — claim **CL-E31C-02** (VERIFIED).
- `family.sponsor_nationalities ∩ {ID}` ← items 1+9 (application letter from the
  ayah/ibu WNI + the WNI parent's Kartu Keluarga) — claim **CL-E31C-03** (VERIFIED).

Two edits, both compiled through `compile_claims` against the inc4 ledger (all four
hard lints, VERIFIED-only binding):

1. `el.e31c-mixed-marriage-parents` deduped and tightened to the E31A spouse-rule
   pattern (4 conjuncts). `reason_code REQ_MIXED_MARRIAGE_PARENTS` kept — it finally
   tests what it names.
2. NEW `hf.e31c-marriage-not-registered` (EXCLUDE on `marriage_registered == false`,
   `on_unknown: NEEDS_INPUT`, `safety_critical: true` — the `hf.e31e-adult-excluded`
   shape). Without it the tightening is cosmetic: sibling rule
   `el.e31c-child-mixed-marriage-support` still grants SUPPORT on FAMILY+PARENT alone,
   which is precisely how the CP3 probe reached SUPPORTED with an unregistered
   marriage. The E33G cure precedent shipped the same pairing (cured rule + paired
   enforcement rule).

Witnesses (all against the REAL evaluator, per-product proofs):
guilt (marriage=false → EXCLUDED with `REQ_PARENTS_MARRIAGE_REGISTERED`) · seq-9
defect pinned (same facts → SUPPORTED on seq-9) · innocence (marriage=true + WNI
parent → SUPPORTED via the tightened rule) · tri-state (marriage UNKNOWN →
BLOCKED_UNKNOWN, never EXCLUDED).

## What deliberately did NOT change

- `el.e31c-child-mixed-marriage-support` (not a lint residual, not in the mandate; its
  breadth is now bounded by the HARD_FILTER).
- `el.c2.business` (see CF-17 above).
- Product `sponsor_types` metadata (not evaluator-consumed).
- E30A's `review.minor-without-guardian` sole-source defect (declared residual —
  PENDING-ARMS row, E31E re-sourcing pattern is the known cure shape).

## Verification state (at authoring)

Fold: deterministic, idempotent (two runs byte-identical,
`9f668aa190c7467b14022ab47ff05f6a5e857e46ab50480285d5c20bfa6f7996`), RC 0.
`compile_pack` on seq-10: `rule_pack_id=d390c8eb-926d-5c37-9bbb-83e4a8601195
sequence=10`, zero compilation errors. `test_seq10_pack.py`: 17/17 (chain recomputed
from bytes; 17 re-stamps + drop verified; zero lint findings; zero stale sources at
the fold date; witnesses above). Adjacent suites green (chain/pricing seq-9 residuals
test still pins seq-9's true state; seq-9/seq-7 witnesses; gold replay driver; mouth
engine-adapter 25/25 — the REVIEW-code map now reads seq-10, the SUPPORT-copy glob
covers both files, the new EXCLUDE code needs no copy by construction).
Reachability: 29/38 reachable, blocked set unchanged vs seq-9.

## Adversarial review

Shared round for the whole inc4 edit set (this file,
`freshness-restamp-2026-08-19.md`, `inc4-c2-e31c-claim-ledger.md`,
`cure-c2-e31c.json`, `source-restamp-edits.json`, `inc4-rule-manifest.json`,
`fold_pack_seq10.py`, `test_seq10_pack.py`, the assembled
`rulepack-prod-010.source.json`). Seats: **Codex GPT-5.6-sol (xhigh)** and
**Kimi K3** — both cross-family, both ordered to REFUTE, neither the author.
Executed 2026-08-19 against the FIRST draft of the fold; every finding below
was independently re-verified by the orchestrator before disposition (W65),
and the cures were applied and the pack RE-FOLDED (final hash
`1ff7383f5b3c2e2a…`, still idempotent). Findings and dispositions:

**Codex — verdict REJECT on the first draft (2 BLOCKER / 1 MAJOR / 2 MINOR / 1 NOTE):**

1. *BLOCKER — the single-leaf HARD_FILTER contaminated non-family paths.*
   Reproduced empirically by the orchestrator: a STUDY applicant with
   marriage UNKNOWN got E31C proof `BLOCKED_UNKNOWN` demanding
   `family.marriage_registered` where seq-9 was silently UNSUPPORTED.
   **FIXED**: the filter's `when` is now scoped
   `all(purposes ∩ FAMILY, relation == PARENT, marriage == false)` — strong-Kleene
   FALSE (silent) outside the E31C shape; regression pinned by
   `test_non_family_applicant_is_not_contaminated` (asserts UNSUPPORTED on BOTH packs
   and the marriage fact absent from missing_facts).
2. *BLOCKER — the E30A re-stamp lends fresh-looking authority to the
   unsupported `review.minor-without-guardian` citation.* **ACCEPTED-PARTIAL**:
   the re-stamp stands — it attests the RECORD (whose facts for E30A's own
   eligibility rules are verbatim-supported; the exception is disclosed in the
   freshness doc §18), and the rule itself is conservative-direction
   (`REQUIRE_REVIEW` for minors without confirmed guardians, `on_unknown:
   NEEDS_INPUT`). The citation defect is PRE-EXISTING (seq-7) and needs a
   grounded re-sourcing (E31E pattern), which no current claim supports —
   escalated from a footnote to its own PENDING-ARMS row rather than folded
   into this increment un-grounded.
3. *MAJOR — `REQ_PARENTS_MARRIAGE_REGISTERED` renders raw in the mouth UI*
   (the `reasonMessage` fallback; the SUPPORT-copy tripwire deliberately skips
   non-SUPPORT effects). **FIXED**: curated EN/ID copy added to
   `SUPPORT_REASON_COPY` in `engine-adapter.ts` (additive; adapter suite
   green). The 22 pre-existing EXCLUDE codes share the raw-render design —
   noted, out of scope.
4. *MINOR — CL-E31C-03 stated stronger than its evidence* (penjamin-is-the-WNI-parent
   is an inference from the letter+KK items). **FIXED**: downgraded to
   VERIFIED-WITH-CAVEAT with the caveat text in the ledger AND a matching
   `caveats` entry in the manifest (the compiler's contract for that state).
5. *MINOR — fold ignored the cure file's declarative fields* (retirements /
   product_ref_removals / insertions were decorative). **FIXED**: all three are
   now consumed and drift-asserted (`_apply_retirement` reads `retirements`,
   `_apply_ee8fe5b8_drop` consumes `product_ref_removals` and cross-checks the
   actually-citing products, `_apply_e31c_cure` compares the cure insertion
   field-by-field against the manifest-compiled body).
6. *NOTE — the freshness test accepted future timestamps.* **FIXED**: the test
   now asserts `verified_at <= AT` for every policy-bearing record.

**Kimi — verdict: no BLOCKER; 1 MAJOR gating activation, 3 MINOR, 6 NOTE:**

1. *MAJOR — the mouth interview never ASKS `family_marriage_registered` for
   PARENT relation* (`flow.ts` gated it on SPOUSE only), so every real E31C
   interview would ship the fact UNKNOWN by construction and the seq-10
   HARD_FILTER would dead-end those applicants in NEEDS_INPUT — with the EDIT
   recovery button a no-op for a question never in history. **FIXED (companion
   mouth change)**: the question now fires for PARENT too (`flow.ts`), the
   EN/ID hint covers the parents'-marriage reading (`i18n.ts`), guilt+innocence
   flow tests added (PARENT asks, CHILD does not). The wider EDIT/truncateToNode
   off-path class remains Track C's (noted on the ledger row for the
   interview-experience lane, same class as the `intent.requested_product_code`
   NOT_ASKED row).
2. *MINOR — the tightened EL rule is verdict-invisible* (the broad sibling
   still SUPPORTs the same single purpose; the behavioral cure is entirely the
   HARD_FILTER). **ACCEPTED — framing corrected** here and in the spec: the EL
   edit is the honest-citation cure (reason_code finally tested), the HF is the
   behavioral cure.
3. *MINOR — CL-E31C-03 inference* — same as Codex 4, same fix.
4. *MINOR — E30A re-stamp* — same as Codex 2, same disposition.
5. *NOTE — two fold-gate gaps, neither live*: top-level payload keys unswept
   by `_assert_untouched`; retirement gate didn't assert priority/on_unknown/
   valid_period/product_version_ids equality. **BOTH FIXED** (top-level sweep
   added; retirement gate now asserts stage/scope/priority/on_unknown/
   valid_period/product_version_ids byte-equality with the sibling).
6. *NOTEs — not refuted*: C2 retirement at verdict level; ee8fe5b8 drop
   (exact 3 product refs, coverage preserved); chain triple-derivation and
   ledger-drift gates "live and correctly wired — no dead gates found"; tests
   16/16 with an honest clock; the stale seq-9 copy entry for the retired code
   is deliberately kept (persisted seq-9 decisions still render it).
   Kimi's nit on "two independent rechecks" wording — softened in the
   freshness doc to name the two rechecks explicitly rather than
   characterize them.

**Post-cure verification** (all re-run after the fixes): fold RC 0 +
idempotent (`1ff7383f5b3c2e2a…`); `compile_pack` RC 0; pytest 64/64 across
`test_seq10_pack.py` (now 18 tests) + chain/pricing + seq-9 witnesses; vitest
72/72 across `flow.test.ts` (new PARENT gate tests) + `engine-adapter.test.ts`
(copy coverage). The two BLOCKER scenarios were re-driven against the re-folded
pack: STUDY applicant now UNSUPPORTED-silent on both packs; FAMILY+PARENT with
marriage UNKNOWN still asks (BLOCKED_UNKNOWN), and the interview now collects
the answer.
