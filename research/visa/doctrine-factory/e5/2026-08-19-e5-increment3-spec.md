---
date: 2026-08-19
domain: visa
client_case: none
adversarial_review: codex
sources:
  - path: .agents/skills/visaoracle/SKILL.md
    note: "LIVE STATE 2026-08-18 NEXT line — the scope authority for this increment"
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.signed.json
    note: "chain anchor: payload_sha256 verified on bytes this session"
---

# E5 increment 3 — BUILD SPEC: seq-9 fold (ledger wiring → rule authoring → pack assembly)

Date: 2026-08-19 · Lane: `backend-rag-visa-e5-seq9` (M5) · Base: origin/main `86d4696c0`
Scope authority: `.agents/skills/visaoracle/SKILL.md` LIVE STATE 2026-08-18 NEXT line + OD-2/OD-4
rulings (Zero, 2026-08-16/18). CP3 (= blueprint gate G4: owner approves the seq-9 diff
rule-by-rule, claim-cited) follows this increment; signing/activation (CP4) is NOT in scope here.

## Anchors (verified on origin/main bytes this session — do not re-derive from memory)

- Active pack: seq-7, `rulepack-prod-007.signed.json` `payload_sha256 =`
  `3d068aef2dca40f1efb74bdd3f8859e767c000282ab8299ac7f277b0b9719f82` → this exact value goes in
  seq-9 `previous_payload_sha256`.
- seq-8 (`rulepack-prod-008.source.json`): unsigned, chain broken (its `previous_payload_sha256`
  = seq-6's hash). OD-2: FOLD into seq-9, never sign standalone. Its only delta vs seq-7:
  non-null `pricing_key` on 11 products (E28A, E33, E33E, E33F, E33G, A1, B1, C1, C6, C2,
  BRIDGING). File stays on disk as history.
- seq-9 identity: `sequence: 9`, `version: "2026.8.19"`, `rule_pack_id:
  66eb0b4c-58ee-56c3-812c-2acc26fff8ce` (uuid5 convention verified: reproduces seq-7's id with
  domain `IMMIGRATION_VISA`).
- Baseline tests: `test_visa_engine_compile_claims.py` + `test_claim_ledger.py` = 77 passed in
  this worktree.
- Fact vocabulary is CLOSED (wire model `extra="forbid"`): no new FactPath in this increment.
  `sponsor.type` exists (enum NONE/INDIVIDUAL/EMPLOYER/EDUCATION/INVESTMENT/GOVERNMENT, W3
  factbase `research/visa/2026-08-11-w3-sponsor-rules-factbase.md` defines the mappings).
  There is NO work-income fact (`work.*` has only employer/clients/compensation booleans);
  `secondhome.passive_monthly_income_usd` is passive income, semantically wrong for a remote
  worker's salary — do NOT reuse it for E33G.

## Step 1 — Ledger hygiene (blocks everything downstream)

1a. `research/visa/doctrine-factory/claims/e2b-batch3-claim-ledger.md:362` — dual header
`**CL-E31C-01 / CL-E31F-01 — …**` mis-parses (`_HEADER_RE` accepts one id; CL-E31F-01 is never
created, CL-E31C-01 truncates to `CL-E31C`). Split into two full header blocks, preserving body
content under each (duplicate the shared body verbatim under both ids; add a one-line
cross-reference note). Content is NOT re-adjudicated — formatting only.

1b. `research/visa/doctrine-factory/claims/e2c-blocked5-claim-ledger.md:306-309` — CL-E33B-03's
state bullet `**State: VERIFIED** for the duration figure …; **UNVERIFIED** for …` accidentally
matches `_PRODUCT_STATE_CLAUSE_RE` and produces spurious `product_states={"the": "UNVERIFIED"}`.
Rewrite so the first `- **State: …**` bullet is a single plain state (`VERIFIED-WITH-CAVEAT`)
and the split reading moves to prose that cannot match the clause regex (no `**TOKEN** for`
shape). Meaning preserved: duration VERIFIED; the flat "sponsor always mandatory" reading stays
unverified in prose.

1c. Wire both ledgers into `_LEDGER_FILES`
(`backend/tests/scripts/test_visa_engine_compile_claims.py:43-48`) and add guilt+innocence
assertions: `CL-E31F-01` resolves post-fix (guilt: the unsplit shape must FAIL a new
regression assertion); `CL-E33B-03.product_states == {}` post-fix; `state_for_product("E33B")`
== VERIFIED-WITH-CAVEAT. e2c's SUPERSEDED record must stay non-compilable.

## Step 2 — Rule manifest for the 7 blocked products

New file `research/visa/doctrine-factory/e5/blocked7-rule-manifest.json`, same schema as
`slice-rule-manifest.json` (`{"slice": "...", "rules": [{product_code, claim_ids, caveats,
must_reference_facts?, rule}]}`), validated by
`PYTHONPATH=. python -m backend.scripts.visa_engine.compile_claims --claims <the 6 ledgers>
--manifest e5/blocked7-rule-manifest.json --out <artifact>` → **0 findings**.

House style: follow `slice-rule-manifest.json`'s reformed-rule shapes. Every rule carries
`source_refs` resolvable against pack `source_records` (add new source_records in Step 4 if a
claim cites a source the pack lacks). Every claim cited must be VERIFIED or
VERIFIED-WITH-CAVEAT-with-matching-caveat for that product. R-OVERSTAY-PLANNING and the other
lints must pass by construction.

Per-product design (doctrine per the cards + `e2c-blocked5-claim-ledger.md`; conflicts binding:
CF-15, CF-17, OD-4):

- **E30E** (KEK student): ELIGIBILITY on `intent.purposes ∋ STUDY` + `sponsor.type ∈
  {EDUCATION, INDIVIDUAL}` per CL-E30E-01/-02/-03/-05 (check the W3 factbase for the exact
  sponsor mapping of "KEK institution or WNI guarantor"). CF-15: author NOTHING that supports
  KITAP conversion (CL-E30E-04 is CONFLICTING — uncitable anyway).
- **E30F** (bilateral-exchange student): same shape per CL-E30F-01/-02/-03; -04/-05 are
  VERIFIED-WITH-CAVEAT → cite only with matching `caveats` entries, and only if needed.
- **E23U** (diplomat household staff): ELIGIBILITY per CL-E23U-01/-02/-03; sponsor is the
  embassy — map via W3 factbase (likely GOVERNMENT); RPTKA/KBLI facts do NOT apply (exempt per
  Kepmen M.IP-08.GR.01.01/2025).
- **E23V** (foreign chamber/trade office staff): ELIGIBILITY per CL-E23V-01/-02; CL-E23V-03 is
  VERIFIED-WITH-CAVEAT (PROSE_ONLY) → caveat entry required if cited. Sponsor mapping per W3
  factbase (the E23V government-vs-employer call is documented there — follow it, don't re-judge).
- **E33A** (govt-invited expert): ELIGIBILITY narrowing on purpose + `sponsor.type=GOVERNMENT`
  per CL-E33A-01/-02/-03. The invitation letter itself is un-modelable → the existing
  `review.e33a.central-government-invitation` rule STAYS (OD-1 pattern: HUMAN_REVIEW with
  explicit reason). CF-17: NEVER import property/deposit facts into E33A/B/C.
- **E33B** (collaborating expert, priority): ELIGIBILITY = ANY(sponsored path Pasal 57(2),
  self-sponsored path Pasal 58) on available facts per CL-E33B-01/-02/-04 — encode BOTH
  pathways, the sponsor-mandatory tension is unresolved by design. Expertise evidence
  (certificate / top-100 GPA≥3.5) is un-modelable → existing `review.e33b.expertise-qualification`
  stays as the document gate.
- **E33C** (World Figure): ELIGIBILITY on purpose + sponsor facts per CL-E33C-03 (+ caveats for
  -01/-02 PROSE_ONLY). Do NOT encode the USD 25M/50M guarantee tiers (flagged as plausibly
  conflated with the corporate Golden Visa — an unencoded flagged claim is a CP3 note, not a
  rule). Existing review rule stays.

Intended terminal states (document in the manifest header comment AND the CP3 package):
E30E/E30F/E23U/E23V become SUPPORTED-able; E33A/B/C remain review-gated by their existing
document-check review rules, but gain real eligibility narrowing (EXCLUDE the non-matching,
review the matching with explicit reason) — per OD-4 these are real rules, not E28-style blanket
REVIEW.

## Step 3 — Cure the two defective seq-7 rules (in the seq-9 source, never in-place on seq-7)

3a. `el.e33e.deposit-income-basis` (UNSAT): replace `when` with
`all(purpose=RETIREMENT, age≥55, ANY(deposit-conjunct, income-condition))` — at-least-one basis,
no negations, no BlockB. Ground the OR reading on the E33E claims (CF-7 resolution /
e2b-batch2 ledger; card `cards/E33E.md`) and cite the claim id in the inc-3 doc. Facts stay the
existing `secondhome.*` paths. If the claims support BOTH-required instead of OR, stop and flag
— do not guess (the cure choice is doctrinal; current evidence says OR: deposit path XOR/AND
confusion came from mixing two authorings).

3b. `el.e33g.income-60k-manual` (VACUOUS + mislabeled): dedupe the identical subtree; there is
NO income fact to reference, so make the rule honest: rename to
`el.e33g.remote-work-configuration` (id change is fine in a new pack), keep the 4
employer/clients/compensation facts, and ADD a product-scoped
`review.e33g.income-evidence` HUMAN_REVIEW rule (scope PRODUCTS=[E33G], conditioned on the same
remote-work facts being satisfied) so E33G can no longer reach SUPPORTED with zero income
evidence — OD-1 pattern (un-modelable statutory requirement → HUMAN_REVIEW with explicit
reason). Reason code: reuse an existing `REVIEW_REASON_COPY` key if one fits; if a new key is
needed, add copy or extend `KNOWN_UNMAPPED` per the QW-4a exhaustiveness test — do NOT let that
test go red. NOTE for CP3: this narrows E33G from (defectively) SUPPORTED-able to review-gated —
an explicit delta vs OD-3's 27-reachable count, with the missing work-income FactPath recorded
as a lead in `research/visa/2026-08-12-fact-vocabulary-extension-design.md` (already exists).

## Step 4 — Freshness (target 20/20, honestly or declared)

- `ecd22722` (E31E page): per QW-5 it no longer (or never) supported the 2 HARD_FILTER rules
  `hf.e31e-adult-excluded` / `hf.e31e-married-excluded`. Re-source those 2 rules against primary
  law: check `cards/E31E.md` + ledgers for a VERIFIED claim grounding under-18/unmarried
  (Indonesian dependent-child definition); add/point the source_record accordingly. If no
  VERIFIED claim exists, DO NOT invent one — flag as CP3 open item with the rules left citing
  primary law candidates as UNRESOLVED (and say so).
- `ecd22722` keeps backing `el.e31e-child-itas-support` / `el.e31e-sponsor-itas-itap` (QW-5
  confirms the page still supports the ITAS/ITAP-sponsor facts): re-verify the live page
  (public URL, no auth) and bump `verified_at` with the fetch evidence recorded in the inc-3 doc.
- `0497cb52` (evisa FAQ, 0 active refs): drop from `source_records` if truly 0 refs in seq-9
  (grep the assembled pack).
- `ee8fe5b8` (general landing page, 21 co-refs): re-verify live; if content still supports the
  co-cited facts, bump `verified_at` with evidence; if not, declare the residual in CP3 — do not
  silently carry it.

## Step 5 — Assemble seq-9 + chain/pricing gates

Assembly is DETERMINISTIC and scripted (new `backend/scripts/visa_engine/fold_pack.py`, small):
inputs = seq-7 source + seq-8 source + compiled blocked7 rules artifact + the Step-3 cures +
Step-4 source edits; output = `rulepack-prod-009.source.json`. The script must:
- copy seq-7 verbatim as base; apply pricing_key for exactly the 11 products from seq-8 (13
  products already priced in seq-7 untouched; assert the full pricing parity table);
- set sequence/version/rule_pack_id/previous_payload_sha256 per the Anchors above
  (previous read FROM `rulepack-prod-007.signed.json`'s `payload_sha256` at run time, never
  hardcoded);
- inject the Step-2 rules and Step-3 cures; apply Step-4 source_record edits.

New test `backend/tests/services/visa_engine/test_pack_chain_and_pricing.py`: (a) chain gate —
`rulepack-prod-009.source.json.previous_payload_sha256` equals the highest-signed pack's
`payload_sha256` (read both files; this also permanently pins the seq-8 broken-chain lesson:
assert seq-8's previous does NOT chain to seq-7 and that no seq-8 signed file exists);
(b) pricing-key parity — the 24 expected products carry non-null pricing_key, the rest null;
(c) the 2 defective rule ids are absent/cured in seq-9 (UNSAT/VACUOUS lints pass on the new
pack via the inc-2 lint functions applied to every seq-9 rule).

Gates that must be green before PR:
- `compile_pack.py rulepack-prod-009.source.json` → RC 0;
- `compile_claims.py` over all 6 ledgers + both manifests → 0 findings;
- full touched-area pytest (compile_claims + claim_ledger + new chain test + any pack-contract
  suite that reads source packs) — no regression vs the 77-passed baseline;
- QW-4a reason-copy exhaustiveness test green.

## Step 6 — Docs, ledger, CP3 package

- inc-3 doc `research/visa/doctrine-factory/e5/2026-08-19-e5-increment3-fold.md`: what was
  built, evidence (fetches, lint runs), claim citations for every new/cured rule.
- CP3 decision package `research/visa/doctrine-factory/e5/cp3-decision-package.md`: rule-by-rule
  semantic diff seq-7→seq-9, claim-cited, with the explicit deltas: (1) E33G review-gating vs
  OD-3 count; (2) E33C capital tiers not encoded; (3) freshness residuals if any; (4) the 26
  reformed slice rules (slice-rule-manifest.json) deliberately NOT folded — they belong to the
  HRR/flag-veto reform (post-seq-9), scope per the LIVE STATE NEXT line; (5) blueprint-F4
  residuals not in ledger scope (~200-persona gold set) declared, not smuggled.
- LIVE STATE entry in `.agents/skills/visaoracle/SKILL.md` (E5 inc-3 + seq-9 candidate ready,
  CP3 pending Zero).

## Assembly decisions (2026-08-19, orchestrator, post-Implementer-B — these OVERRIDE Step 3 above)

Implementer B's grounding refuted the spec's Step-3a OR assumption: `CL-E33-04` (VERIFIED,
`e2b-batch1-claim-ledger.md:187`) states deposit USD 50,000 **plus** USD 3,000/month income —
AND, not OR — and the healthy sibling rule `el.e33e.retirement` already encodes exactly that and
is reachable. Decisions binding on the assembler:

1. **E33E**: RETIRE (delete) `el.e33e.deposit-income-basis` from seq-9. No replacement — the
   doctrine lives in `el.e33e.retirement`. Behavior delta: zero (an UNSAT rule can never fire).
   CP3 presents this as retired-redundant-defective, with Implementer B's option trail
   (`inc3-pack-edits/cure-e33e.md`).
2. **E33G**: RETIRE (delete) `el.e33g.income-60k-manual`. Do NOT add the renamed
   `el.e33g.remote-work-configuration` (it would be byte-identical to the pre-existing healthy
   `el.e33g.remote-work`). DO add `review.e33g.income-evidence` from
   `inc3-pack-edits/cure-e33g.json` (reason_code `E33G_INCOME_EVIDENCE_REVIEW`), and apply the
   reason-code copy / `KNOWN_UNMAPPED` edit documented in `cure-e33g.md` in the SAME change so
   the QW-4a exhaustiveness test stays green.
3. **E31E**: apply `inc3-pack-edits/e31e-source-edits.json` — repoint `hf.e31e-adult-excluded`
   and `hf.e31e-married-excluded` to source `c9e6f0e4-…` (Permenkumham 22/2023, locator
   "Pasal 33"), keep `ecd22722` for the two `el.e31e-*` rules with the verified_at bump backed
   by `inc3-pack-edits/freshness-2026-08-19.md`.
4. **0497cb52**: drop from seq-9 `source_records` (0 active refs, grep-proven).
5. **ee8fe5b8** (CHANGED landing page): compute per-rule co-source coverage — for every rule
   citing it, if the rule retains ≥1 other in-force source, drop the stale co-ref; any rule
   that would be left with ZERO sources keeps the ref and the residual is DECLARED in CP3.
   Let the data decide; record the per-rule table in the inc-3 doc.

## Assembly decisions round 2 (2026-08-19, orchestrator, post-Implementer-A)

6. **E33A/B/C shape RATIFIED as delivered**: HARD_FILTER/EXCLUDE narrowing on sponsor.type
   (never SUPPORT — the W3 factbase + `2026-08-11-seq7-sponsor-semantics-…` note document the
   "manufactured offer" bug for the SUPPORT shape). The spec's earlier "eligibility narrowing"
   wording is superseded by this.
7. **E23U/E23V**: NO SUPPORT rule (W3 factbase: "no safe SUPPORT rule for E23U";
   sponsor.type+purpose don't discriminate the pair). Author instead one product-scoped
   HUMAN_REVIEW rule each, keyed on `intent.requested_product_code` (the same mechanism the
   existing `review.e33a/b/c.*` rules use), claim-cited (CL-E23U-01..03 / CL-E23V-01..02, with
   caveats where PROSE_ONLY), with explicit reason codes satisfying the QW-4a contract. Effect:
   someone explicitly pursuing E23U/E23V gets a named review path instead of silence; nobody
   gets a manufactured SUPPORT. These 2 rules are added to `blocked7-rule-manifest.json` and
   must compile clean through `compile_claims` with the rest.
8. The 5 claim-cited source ids absent from the pack (Kepmen/Permenkumham UUID variants + 2
   nb2 internal files) are NOT added as source_records: rules cite pack-native sources only, and
   the nb2 internal DB must never become a pack source (CF-17). Recorded for CP3.

## Non-goals (hard)

No signing, no activation, no Fly/secret/DB change, no ENFORCE-adjacent change, no new
FactPath, no frontend change, no slice-rule fold, no seq-8 signing. SHADOW posture unchanged.

## Adversarial review

The spec itself was falsified twice during execution and amended in place rather than defended:
(1) Step-3a's OR-basis assumption for E33E was REFUTED by Implementer B on claim evidence
(CL-E33-04 says AND) — superseded by Assembly decision #1 (retire, don't rewrite); (2) Step-2's
"E23U/E23V SUPPORTED-able" intent was REFUTED by the W3 sponsor factbase ("no safe SUPPORT rule")
— superseded by Assembly decision #7 (review-only). The final working tree built from this spec
was then adversarially reviewed by two cross-family refuter seats (Codex GPT-5.6 high: DO-NOT-SHIP
with 7 findings, all disposed in a fix round; Kimi K3: 3 P2 / 3 P3, disposed same round) — the
findings and dispositions live in `2026-08-19-e5-increment3-fold.md` §Adversarial review. No
objection against this spec survived undisposed; the two spec-level refutations are recorded
above as Assembly decisions, which override the refuted prose deliberately left in place as the
audit trail.
