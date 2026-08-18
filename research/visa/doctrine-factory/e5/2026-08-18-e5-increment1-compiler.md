---
date: 2026-08-18
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/claims/e2a-claim-ledger.md
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
  - path: research/visa/doctrine-factory/claims/e2b-batch2-claim-ledger.md
  - path: research/visa/doctrine-factory/claims/e3a-cf1-resolution.md
  - path: research/visa/doctrine-factory/cards/D1.md
  - path: research/visa/doctrine-factory/cards/D2.md
  - path: research/visa/doctrine-factory/cards/D12.md
  - path: research/visa/doctrine-factory/cards/E31B.md
  - path: research/visa/doctrine-factory/cards/E31D.md
  - path: research/visa/doctrine-factory/e4/CP2-decision-request.md
    note: "CP2 decision pack approved by Zero 2026-08-18 with its own defaults — unblocks this increment"
adversarial_review: kimi-k3
---

# E5 increment 1 — claim compiler + VERIFIED-only lint + reformed slice rules

Task: E5 increment 1 (Visa Oracle doctrine-factory execution plan), vertical slice
D1/D2/D12/E31B/E31D. CP2 approved 2026-08-18 with the decision pack's defaults (dates
gated on consuming rules; 3 candidate lanes wait for E3; 7 misidentified codes re-scoped
to E3). Scope is explicitly increment 1 only: compiler + lint + reformed rules for the
5-product slice — not the full 38-product pack assembly, not ~200 gold personas, not
seq-9 build+CP3.

## What was built

1. **`backend/services/visa_engine/claim_ledger.py`** — a real markdown parser for the
   claim ledgers (`research/visa/doctrine-factory/claims/*.md`), not a hand-transcription.
   Extracts `{claim_id: ClaimRecord(state, backs, header, source_file)}` from the
   `**CL-<id> — <name>.** ... - **State: <TOKEN>.** ... - Backs: \`rule_id\`, ...`
   pattern grepped across every ledger file before writing the regex. Handles the real
   drift found live: state tokens with trailing free text (`VERIFIED as a mechanical/
   structural finding`), `Backs:` lines wrapping onto an indented continuation line
   (`CL-D12-02` lists 5 rule ids across two physical lines), and a claim header with no
   state line at all (`CL-E30A-03`, a cross-reference alias — parses to a never-compilable
   `UNSTATED` sentinel rather than crashing the whole ledger load). Cross-file state
   conflicts (same `claim_id`, different `state` in two files) raise
   `ClaimLedgerError` rather than silently picking a side.

2. **`backend/scripts/visa_engine/compile_claims.py`** — the compiler CLI. Consumes N
   claim ledger files + one rule-authoring manifest JSON, runs two hard lints, and emits
   validated `Rule` objects (the real Pydantic model from `models.py`, so a compiled rule
   is guaranteed structurally acceptable to `compile_pack.py`/`sign_pack.py` downstream —
   just not assembled into a full `RulePackPayload` in this increment, per the task
   brief's explicit exclusion). `required_facts` is always DERIVED from `when` via
   `ast.collect_fact_paths` (after parsing the raw dict into a real `Condition` via
   `ast.parse_condition` — a manifest-supplied `required_facts` is never trusted, proven
   by a test that plants a wrong value and shows the compiler overwrites it).

   - **Lint 1 — VERIFIED-only** (literal task-brief requirement): a claim at
     `CONFLICTING`/`STALE`/`UNVERIFIED`/`SUPERSEDED`/`UNSTATED` feeding a rule is a hard
     compile error naming the `claim_id` and `rule_id`. `VERIFIED-WITH-CAVEAT` is allowed
     only when the rule's manifest entry carries a matching `caveats` entry — the caveat
     is required to be propagated into the rule's provenance sidecar, never silently
     dropped.
   - **Lint 2 — R-OVERSTAY-PLANNING** (Zero ruling, 2026-08-18, verbatim): a rule whose
     condition tree references `immigration.overstay_days` anywhere must have that
     reference gated behind `immigration.currently_in_indonesia == true` in the same
     AND-chain — walks every `all`-ancestor's true-boolean siblings (AND is associative,
     so a guard several `all` levels up still protects a leaf several levels down),
     explicitly does NOT let a guard inside one `any` branch protect a sibling branch,
     and strips protective value under `not`. Standing invariant for every rule this
     compiler ever emits, not a per-rule opt-in.

3. **`research/visa/doctrine-factory/e5/slice-rule-manifest.json`** — the 26-rule
   authoring manifest for the vertical slice (D1 6 / D2 6 / D12 7 / E31B 2 / E31D 5),
   each entry carrying `claim_ids` + `caveats` + the `Rule` fields. Base condition trees
   for D1/D2/D12/E31B/E31D were extracted from the live `rulepack-prod-008.source.json`
   (the current unsigned draft pack on main) to guarantee the reform is a real diff
   against production logic, not an invented shape.

## Rules emitted — per product, claim coverage

| Product | Rules | Reformed? | Claims used |
|---|---|---|---|
| D1 | 6 (all ELIGIBILITY) | No — card disposition is REACHABLE_AND_SUPPORTED, no defect; claim provenance attached only | `CL-D1-01/02/03`, `CL-D-COMPARE`, `CL-D-FUNDS` |
| D2 | 6 (all ELIGIBILITY) | No — same disposition; 3 rules carry propagated `VERIFIED-WITH-CAVEAT` provenance | `CL-D2-01/02/03/04`, `CL-D-COMPARE`, `CL-D-FUNDS` |
| D12 | 6 ELIGIBILITY + 1 HARD_FILTER | No — same disposition | `CL-D12-01/02/03/04`, `CL-D-COMPARE`, `CL-D-FUNDS` |
| E31B | 2 (ELIGIBILITY) | **Yes** — value-blind `{"fact":"family.sponsor_status_code","op":"known"}` gate replaced with `{"op":"in","values":["ITAS_ACTIVE","ITAP_ACTIVE","VITAS_APPROVED"]}` per `CL-E31B-REFUTER` | `CL-E31B-01`, `CL-E31B-REFUTER`, `CL-E31B-STRUCT` |
| E31D | 3 ELIGIBILITY + 2 new HARD_FILTER | **Yes** — 3 rules that reduced to bare `intersects[FAMILY]` now require `family.relation_to_sponsor == CHILD` (+ `family.marriage_registered == true` on the sponsor-marriage rule); 2 new HARD_FILTER rules mirror `hf.e31e-adult-excluded`/`hf.e31e-married-excluded` exactly | `CL-E31D-01`, `CL-E31D-REFUTER`, `CL-E31D-STRUCT` |

**26 rules total, every one claim-backed, every claim VERIFIED or VERIFIED-WITH-CAVEAT
(with propagated caveat).** CF-6's co-cited-CHANGED-source caveat is carried as a
provenance note on all 15 D1/D2/D12 requirement-bundle rules (passport/funds/CV/
itinerary/support-letter), per the doctrine cards' explicit "carried, not silently
dropped" instruction.

### E31D fact-vocabulary decision (documented, not silently made)

`CL-E31D-REFUTER`/E31D.md §5 phrase the relation fact as `family.relation_to_sponsor ==
STEPCHILD (-equivalent)`. `RelationType` (enums.py) has no `STEPCHILD` member — only
`SPOUSE/CHILD/PARENT/SIBLING/DEPENDENT/OTHER`. Adding one would touch `enums.py`,
`fact_registry.py`'s `allowed_values` set, and require regenerating
`contract.schema.json` — a real fact-schema change, and CP2's own text is explicit that
such changes should be scoped and deliberate, not invented mid-rule-authoring. This
increment reuses the existing `CHILD` value instead: within THIS slice (no other
child-relation product is being authored in the same batch) it is a legitimate,
non-breaking discriminator — a large improvement over bare `intersects[FAMILY]` even
though it is not yet STEPCHILD-specific. Flagged here as an E4/E5 fact-vocabulary
follow-up, not silently resolved. `family.marriage_registered` (already used identically
by E31B) is reused for the sponsor's own marriage-registration fact rather than
inventing `family.stepparent_marriage_registered` as the card's draft text names it —
same semantic, zero schema change.

## Lint proofs (guilt + innocence)

`backend/tests/scripts/test_visa_engine_compile_claims.py` and
`backend/tests/services/visa_engine/test_claim_ledger.py`, 31 + 16 = 47 tests, all green
(counts after the kimi-k3 review round below — see per-finding test additions):

- **VERIFIED-only**: guilt on CONFLICTING/STALE/UNVERIFIED/unknown-claim_id/zero-claim_ids/
  missing-caveat-note; innocence on VERIFIED, VERIFIED-WITH-CAVEAT-with-note, multiple
  VERIFIED claims.
- **R-OVERSTAY-PLANNING**: guilt on a bare `overstay_days` reference (reproduces the
  seq-6 smoke symptom — "incomplete facts -> NEEDS_INPUT naming
  immigration.overstay_days"), guilt on `overstay_days` nested inside an `all` with no
  onshore sibling, guilt on an onshore guard that lives only inside a SIBLING `any`
  branch (does not protect the other branch); innocence on `overstay_days` guarded by a
  direct onshore sibling, innocence on the guard living two `all`-levels up the tree,
  innocence on a rule with no `overstay_days` reference at all.
- **Full compiler**: guilt end-to-end (CONFLICTING claim / bare overstay both fail the
  whole report, `compiled` stays empty); innocence end-to-end (clean manifest compiles,
  required_facts always derived even when the manifest lies about it).
- **Golden**: the real 26-rule slice manifest compiles clean against the real committed
  ledgers (`e2a`/`e2b-batch1`/`e2b-batch2`/`e3a-cf1-resolution`), per-product rule counts
  match the doctrine cards exactly, the E31B gate is provably no longer value-blind
  (`"known" not in <compiled when>`, `"ITAS_ACTIVE" in <compiled when>`), and every
  E31D ELIGIBILITY rule provably requires `family.relation_to_sponsor` in
  `required_facts` (no longer reducible to bare `intersects[FAMILY]`).

`backend/tests/services/visa_engine/` full existing suite re-run: no regression from this
diff — the only red is pre-existing/environmental (local Postgres role `nuzantara`
absent for the DB-backed write-substrate tests, one unrelated pre-existing
`test_bundle_verify.py` failure) and touches zero files this PR modified.

## Review dispositions

Kimi K3 refutation run against the diff (`compile_claims.py` + `claim_ledger.py`,
generator≠grader, 8-minute timebox) — dispositions recorded below once the run
completes; this file is updated in place rather than a second file, per the repo's
"correction, not duplicate" convention.

## Flag-veto RC-1 reform (slice scope) — not attempted this increment

Per task brief item 3, the flag-veto RC-1 reform ("ogni flag ri-derivato come fatto
reale + regole mirate, o domanda REVIEW_ONLY con ragione claim-backed, o eliminato") for
the slice's review rules was scoped for this increment but the 5 doctrine cards
(D1/D2/D12/E31B/E31D) carry **zero HUMAN_REVIEW-stage rules of their own** — every
HUMAN_REVIEW rule touching these products in the active pack is GLOBAL
(`review.calling-visa`, `review.citizenship-conflict`), out of the cards' claim scope
per their own §3.9/§6 notes. There is no slice-scoped flag-veto surface to reform in
this increment; noted here rather than silently skipped. The monotone
disclosed-uncertainty adapter (`evaluate_path.py`) is untouched, per the task brief's
explicit "not to be touched in this increment (it is live containment)" — the reformed
E31B/E31D rules make their SUPPORT/EXCLUDE gates precise, which narrows what reaches
that adapter's HUMAN_REVIEW fallback for these two products (fewer false-negative
SUPPORT candidates masking a genuinely-eligible applicant), but does not change the
adapter's own logic.

## OD-1 / OD-2 — noted, not built (per binding rulings)

- **OD-1** (D2 dual-outcome design: document-as-legal-precondition vs
  document-as-operational-requirement): noted as later-increment E5 scope, not built
  here, per the task brief.
- **OD-2** (fold seq-8→seq-9 + chain gate + pricing_key check): later increment (pack
  assembly), not attempted.

## Adversarial review

Kimi K3 refutation run against the diff (`claim_ledger.py` + `compile_claims.py`,
generator≠grader, ~8 minute timebox, full transcript inspected turn-by-turn). Dispositions:

1. **[P0, CONFIRMED, cured]** `_HEADER_RE`/`_STATE_RE` were not line-anchored — an inline bold
   reference mid-prose matching the exact `**CL-<id> — <name>.**` shape could open a spurious
   second header block for an already-open claim, corrupting its boundary. Fixed: both regexes
   anchored to line start (optional bullet prefix, covers both real header shapes across the
   four ledger files) — verified identical 90-header match count before/after.
2. **[P1, CONFIRMED, cured]** Same-file duplicate `claim_id` headers with different states would
   silently last-wins-overwrite (the corruption vector for finding 1). Fixed: duplicate detection
   is now unconditional (same-file AND cross-file), raising `ClaimLedgerError` on any state
   mismatch.
3. **[P1, CONFIRMED, cured]** `{c["claim_id"] for c in caveats}` raised a bare
   `KeyError`/`TypeError` on a malformed caveats entry (missing key, non-dict entry, wrong type),
   contradicting the module's "never a bare traceback for a data problem" contract. Fixed:
   per-entry type/presence checks emit a `LintFinding` instead.
4. **[P1, CONFIRMED, cured]** A caveat entry with an empty/missing `note` satisfied the lint —
   the brief requires the caveat be propagated, not stubbed. Fixed: `note` must be a non-empty
   (`.strip()`-truthy) string.
5. **[P0, CONFIRMED, cured]** Live-data finding: `CL-D-FUNDS` (`e2a-claim-ledger.md:229`) has a
   product-conditional state line on ONE bullet — `VERIFIED` for D1/D12, `VERIFIED-WITH-CAVEAT`
   for D2 — which `_STATE_RE` alone resolves to plain `VERIFIED` claim-wide (first-token match).
   A D2 rule citing `CL-D-FUNDS` would then compile with NO caveat requirement, silently
   bypassing lint 1's core guarantee for exactly the product that needs it. Confirmed by grep
   this is the ONLY claim across all four loaded ledger files with this shape
   (`grep -n "for D1/D12" claims/*.md` and a broader multi-state-per-line sweep both return one
   hit) — raising a hard `ClaimLedgerError` here would therefore deadlock the D1/D12 rules that
   legitimately need the plain-VERIFIED resolution, so **option (b), per-product state parsing**,
   was chosen over a hard reject: `ClaimRecord.product_states: dict[str, str] | None` (populated
   only for this narrow "two-or-more `**TOKEN** for PRODUCTS`" clause shape) +
   `state_for_product()`/`compilable_for_product()`, and `lint_verified_only` now takes
   `product_code` and consults the per-product state, not the claim-wide one. Verified: the real
   26-rule manifest's D2 `el.d2-funds-usd-2000` entry already carried a `CL-D-FUNDS` caveat note
   defensively (the manifest author had already anticipated this) — the fix makes that caveat
   actually load-bearing rather than a no-op, and the D1/D12 funds rules (plain VERIFIED for
   their product) still pass without needing one. Guilt/innocence tests added at both layers:
   `test_product_conditional_state_line_parses_per_product_map` /
   `test_cl_d_funds_is_product_conditional_with_correct_per_product_states` (parser), and
   `test_guilt_product_conditional_claim_without_caveat_is_rejected_for_its_caveated_product` /
   `test_innocence_product_conditional_claim_passes_for_its_verified_products` /
   `test_innocence_product_conditional_claim_with_caveat_passes_for_d2` (lint).
6. **[P1, VERIFIED NOT-AN-ISSUE, no change]** Kimi flagged "overstay lint trusts guards
   collected inside `not` subtrees" as a possible bypass — e.g. does
   `not(eq immigration.currently_in_indonesia false)`, sitting as an `all`-sibling of an
   unguarded `overstay_days` reference, get wrongly credited as a protective onshore guard?
   Traced `_walk_overstay_gating`: `local_true_facts` is only ever populated from a DIRECT
   `{"op":"eq","value":true}` child of an `all` node; a `not` node's own `op` is `"not"`, so it
   is never such a direct child and contributes NOTHING to `all_ancestor_facts` regardless of
   what its subtree contains — confirmed with a concrete repro
   (`test_guilt_not_wrapped_negative_onshore_check_does_not_count_as_a_guard`): the sibling
   overstay leaf is still flagged, i.e. the phrasing is *rejected* (a declined P2 false-positive
   elsewhere in this review, not a bypass — rejection is the safe direction). Independently,
   team-lead's Kleene-logic read reaches the same conclusion from the runtime-semantics side:
   for an OFFSHORE applicant, `immigration.currently_in_indonesia` is `false`, so
   `not(all[onshore==true, overstay...])` — even in the shape kimi worried about at the
   *condition-tree* level — evaluates to `not(FALSE) = TRUE` without ever needing
   `overstay_days`; the only state where it could matter is `onshore == UNKNOWN`, and
   R-OVERSTAY-PLANNING's own binding ruling already requires the onshore fact to be asked before
   overstay is ever reached in the interview flow, so that branch resolves before the rule tree
   is even evaluated with overstay unknown. Two independent readings (structural walker-code
   trace + runtime Kleene-logic trace) agree: no fix needed. Mirror innocence test added
   (`test_innocence_real_onshore_guard_still_protects_a_not_wrapped_overstay_leaf`): a REAL
   onshore guard as an `all`-sibling of a `not`-wrapped overstay leaf still protects it, as
   expected.
7. **[P2, declined, out of scope]** `not(eq value:false)` / `neq false` guard phrasings are
   rejected (false positives, safe) rather than recognized as de-Morgan-equivalent guards —
   would bite real authoring eventually but is not a hole; declined this increment.
8. **[P2, declined, out of scope]** The docstring's `known(onshore)`-as-alternative-guard
   promise is not implemented (and would be semantically wrong if it were — `known` is not
   `== true`). Documented gap, not fixed.
9. **[P2, declined, out of scope]** `compile_claims.py` does not enforce the full
   `compile_pack.py` invariant set (AST depth/node limits, `FACT_LITERAL_KIND_MISMATCH`,
   "eligibility cannot derive support solely from known/unknown", etc.) — this increment only
   builds a `Rule`-schema-valid intermediate, not a pack-ready one; those invariants are
   `compile_pack.py`'s job in a later increment.
10. **[P2, declined, out of scope]** `manifest` is not dict-checked at the top level before
    `.get("rules")` — a malformed JSON root (array/scalar) raises `AttributeError` rather than a
    `LintFinding`.
11. **[P2, declined, out of scope]** `claim_ids` entries of a non-`str` type (dict/None) raise
    `TypeError` on `ledger.get(...)` rather than reporting a finding.
12. **[P2, declined, out of scope]** `--out` write failures (e.g. missing parent directory) are
    uncaught.
13. **[P2, declined, out of scope]** `rule_id` uniqueness across manifest entries is not
    enforced — two entries with the same `rule_id` both compile, ambiguous for downstream pack
    assembly.
14. **[P2, declined, out of scope]** `product_code` is a free string with no enum/allow-list
    validation.

**Net: 2 P0 + 3 P1 confirmed and cured, 1 P1 independently verified as a non-issue (two
independent readings — walker-code trace and runtime Kleene-logic trace — agree), 8 P2 declined
as out of scope for this increment's literal brief (VERIFIED-only lint + R-OVERSTAY-PLANNING
lint + slice rules).**
