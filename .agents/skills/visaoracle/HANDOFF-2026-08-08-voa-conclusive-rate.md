# HANDOFF 2026-08-08 — Why the Visa Oracle engine never closes (0% conclusive-rate)

> Investigator: Mini lane `laneE1-voa-diag`, dispatched by the session running task #20
> (PR #3766 migration 268) after the prod ledger showed 6,610/6,610 decisions since
> 2026-07-25 landing `HUMAN_REVIEW_REQUIRED` — never a single `SUPPORTED_CANDIDATES`
> or `NO_SUPPORTED_PATH`. Read-only + one SHADOW `evaluate` call (innocuous — does not
> touch real users, mode=CURATED). No edit/commit/push happened during the
> investigation itself; this file is the write-up.

## Mission for next session

**Goal: raise the engine's conclusive-rate from 0% (6,610/6,610 abstentions) to >60%
on real traffic**, starting from the concrete case this handoff proves broken:
`IT / TOURISM / 10 days / all facts supplied → should return SUPPORTED_CANDIDATES
with B1_VOA_ELIGIBLE, currently returns HUMAN_REVIEW_REQUIRED`.

- **First deliverable: RulePack seq-4.** Scope: items 1-4 in §4 below (narrow
  D1/D2/D12 eligibility + human-review conditions so they stop firing for every
  tourism-purpose applicant regardless of route, and add a VOA-eligible-nationality
  gate to `el.b1.tourism` — needs primary-source research: the official VOA-eligible
  country list, ~90+ countries, Kepmen/Permenkumham — distinct from the 19-country
  BVK list already present for A1).
- **Signing ceremony**: already proven, reuse as-is (M5 key custody,
  `activate_pack.py`, `rule_pack_id` convention
  `uuid5(NAMESPACE_URL, "https://balizero.com/visa-oracle/rule-pack/<ENV>/<JURISDICTION>/<DOMAIN>/<sequence>")`,
  pre-activation semantic diff, bitemporal legal_period discipline — see the
  2026-08-08 "night 07→08" LIVE STATE entry for the seq-2→seq-3 walkthrough that
  already exercised this pipeline once).
- **Item 7 (the REVIEW>SUPPORTED precedence in the evaluator) is an architectural
  decision, not a bug fix — route it through the 4-LLM panel (CLAUDE.md §6) before
  touching `evaluator.py`. Do not casually reopen it.**
- Verification loop: after activating seq-4, replay the exact payload in §2 below —
  must return `SUPPORTED_CANDIDATES` / `B1_VOA_ELIGIBLE`. Then repeat the same
  purpose-only-HR-rule audit (§3) for the other 6 interview categories
  (EMPLOYMENT/STUDY/FAMILY/INVESTMENT/REMOTE_WORK/RETIREMENT) — the defect is
  systemic, not tourism-specific (31/63 PRODUCTS-scoped HUMAN_REVIEW rules pack-wide
  are purpose-keyed-only), so fixing only D1/D2/D12 will not move the ledger's
  aggregate conclusive-rate much past the TOURISM slice.

---

## 1. Fact trace: UI form → engine (verified file:line)

Live path (Track C, the shipped `/visa-oracle` experience):

```
apps/mouth/.../(visa-oracle)/visa-oracle/_lib/tree.ts        (interview, 28 questions, 34/40 FactPath asked)
  → _lib/fact-mapper.ts :: mapOracleFactsToApplicantFacts()  (UI answers → 40-key ApplicantFacts wire shape)
  → _lib/shadow-client.ts:41  SHADOW_EVALUATE_URL = `${API_BASE}/api/visa-oracle/evaluate`  (fire-and-forget POST)
  → backend/app/routers/visa_oracle_evaluate.py :: evaluate_applicant()
  → backend/services/visa_engine/evaluate_path.py :: run_evaluation()
  → backend/services/visa_engine/evaluator.py :: evaluate_with_trace()
```

- The interview asks 34/40 `FactPath` values. 5 are hardcoded `UNKNOWN(NOT_ASKED)` in
  `fact-mapper.ts` regardless of user input (lines 415/420/422/493/494):
  `immigration.last_entry_date`, `intent.desired_entry_date`,
  `intent.requested_product_code`, `commercial.service_fee_budget_idr`,
  `commercial.wants_quote`. None of these are `required_facts` of `el.b1.tourism` —
  this gap is **not** the cause of the abstention proven below.
- `person.nationalities` **is** asked (`tree.ts:246-262`). A stale 2026-07-28 LIVE
  STATE note about `fact-mapper.ts:360` sending `NOT_ASKED` for nationalities refers
  to a different, older "RECOMMEND" quiz surface, superseded by Track C. Confirmed by
  the live test below: nationality `KNOWN=IT` does not change the outcome.
- **No `FactPath` exists for documents** (CV, proof of funds, itinerary, passport
  validity, support letter) — the engine's closed 40-field vocabulary
  (`enums.py:388-459`) has no such fields. The reason codes `CV_REQUIRED` /
  `PASSPORT_VALIDITY_INSUFFICIENT` / etc. seen in prod are **not** "fact missing" —
  they are fixed business flags (see §3).

## 2. Live evaluate call — verbatim

`POST https://nuzantara-rag.fly.dev/api/visa-oracle/evaluate` (SHADOW, `mode:CURATED`
— innocuous, does not affect real users or ENFORCE).

Payload: all 40 facts supplied — `person.nationalities=["IT"]`,
`intent.purposes=["TOURISM"]`, `intent.stay_days=10`, `intent.entry_pattern="SINGLE"`,
`immigration.currently_in_indonesia=false`, everything else `KNOWN`/`NOT_APPLICABLE`
as appropriate (no `NOT_ASKED` except `commercial.*`, which the engine itself
documents as "never usable in a legal stage").

Response (HTTP 200):

```json
{
  "mode": "CURATED",
  "decision": {
    "state": "HUMAN_REVIEW_REQUIRED",
    "rule_pack": {
      "rule_pack_id": "37be33e4-8fbb-55bc-8fe2-7dcb23eab979",
      "sequence": 3,
      "version": "2026.8.8"
    },
    "candidates": [],
    "review_reasons": [
      { "code": "CV_REQUIRED", "rule_ids": ["hr.d1-cv-required"] },
      { "code": "PROOF_OF_FUNDS_D1", "rule_ids": ["hr.d1-funds-usd-2000"] },
      {
        "code": "ITINERARY_REQUIRED",
        "rule_ids": ["hr.d1-itinerary-required"]
      },
      {
        "code": "PASSPORT_VALIDITY_INSUFFICIENT",
        "rule_ids": ["hr.d1-passport-validity"]
      },
      {
        "code": "SUPPORT_LETTER_REQUIRED",
        "rule_ids": ["hr.d1-support-letter"]
      },
      "... same 5 repeated for hr.d2-* and hr.d12-*  (15 review_reasons total)"
    ]
  }
}
```

Zero mention of B1 / `el.b1.tourism`. This reproduces exactly last night's prod smoke
(same review reason codes: `CV_REQUIRED`, `PROOF_OF_FUNDS_D1`, `ITINERARY_REQUIRED`,
`PASSPORT_VALIDITY_INSUFFICIENT`, `SUPPORT_LETTER_REQUIRED`) — deterministic, not a
test artifact.

## 3. Exact mechanism (file:line)

**Root cause = RulePack content defect + a documented architectural precedence,
together.**

**Step A — the RulePack** (`contracts/packs/rulepack-prod-002.source.json`, content
re-activated as seq 3) has 5 `HUMAN_REVIEW`-stage rules each for D1/D2/D12 (15
total), e.g.:

```json
{
  "rule_id": "hr.d1-cv-required",
  "stage": "HUMAN_REVIEW",
  "scope": "PRODUCTS",
  "when": {
    "fact": "intent.purposes",
    "op": "intersects",
    "values": ["TOURISM", "FAMILY", "TRANSIT", "BUSINESS_MEETINGS"]
  },
  "effect": { "type": "REQUIRE_REVIEW", "reason_code": "CV_REQUIRED" },
  "required_facts": ["intent.purposes"],
  "product_version_ids": ["374e79e0-f0bf-5291-8cba-974e794e210a"]
}
```

This condition is **TRUE** (not "unknown") for any tourism-purpose applicant. It does
not require `intent.entry_pattern == MULTIPLE` (even though D1 is literally
"multi-entry visit visa" — verified live: my payload had `entry_pattern="SINGLE"` and
all 5 D1 rules still fired). D2 ("Visa Kunjungan Bisnis" — business) and D12 ("Visa
Kunjungan Pra-Investasi" — pre-investment) rules match on `TOURISM`/`FAMILY` too, not
just their own domain purpose (`BUSINESS_MEETINGS`/`INVESTMENT`). None of the three
discriminate "applicant actually wants this multiple-entry route" from "applicant is
eligible for the simpler automated product (B1) in the same purpose-set".

Meanwhile `el.b1.tourism` (ELIGIBILITY, on B1 = VOA) is:

```json
{
  "rule_id": "el.b1.tourism",
  "stage": "ELIGIBILITY",
  "scope": "PRODUCTS",
  "when": {
    "op": "all",
    "args": [
      { "op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"] },
      { "op": "lte", "fact": "intent.stay_days", "value": 30 }
    ]
  },
  "effect": {
    "type": "SUPPORT",
    "reason_code": "B1_VOA_ELIGIBLE",
    "covered_purposes": ["TOURISM"]
  },
  "product_version_ids": ["4e30cbe0-c4bf-59be-9bf8-513e66946e44"]
}
```

No nationality condition at all — a genuine content gap (see §4 item 4).

**Step B** — per-product stage order (`enums.py:99-106`, `STAGE_ORDER`):
`HARD_FILTER → HUMAN_REVIEW → ELIGIBILITY → RANKING`. D1/D2/D12's own
`evaluate_product()` resolves to `REVIEW` before their `ELIGIBILITY` stage is ever
reached.

**Step C — the decisive point**, `evaluator.py:1381-1397`:

```python
# P0-B fix ... frozen precedence ranks HUMAN_REVIEW_REQUIRED above
# SUPPORTED_CANDIDATES unconditionally
if global_review_reasons: return HUMAN_REVIEW_REQUIRED(...)
review = [proof for proof in proofs if proof.status is ProductProofStatus.REVIEW]
if review:                                              # line 1391-1394
    return assemble(state=HUMAN_REVIEW_REQUIRED, review_reasons=...)  # ← returns HERE
supported = [proof for proof in proofs if proof.status is ProductProofStatus.SUPPORTED]  # line 1396 — B1 never reached
```

Deliberate, documented design (`enums.py:41-47` `DecisionState` docstring:
"HUMAN_REVIEW_REQUIRED > SUPPORTED_CANDIDATES unconditionally"; `evaluator.py:42-53`,
"P0-B", verified by 2 cross-family seats in gate round 1). Not an implementation bug —
an architectural precedence that lets **any** sibling product in review mask a fully
eligible candidate evaluated in the same purpose-set.

**Systemic severity (not tourism-specific)**: counted all `HUMAN_REVIEW` rules in the
active pack — 65 total (2 GLOBAL + 63 PRODUCTS). **31/63 (≈half) are keyed on
`intent.purposes` alone (± `stay_days`)** — spanning every interview category: `e23`
(EMPLOYMENT/KITAS work), `e30` (STUDY), `e31` (FAMILY/sponsor), `d1/d2/d12`
(TOURISM/BUSINESS/INVESTMENT via multiple-entry e-visas). This is why the prod ledger is
100% `HUMAN_REVIEW_REQUIRED` across 6,610 decisions — it is not TOURISM-specific, it
is the default shape of **any** category that has a "sibling" product with
always-review-required policy in the same purpose-set.

**Excluded by evidence**: not "missing facts" (all 40 supplied, zero `missing_facts`
in the response, every review reason is a `TRUE`-condition `REQUIRE_REVIEW`, not an
`on_unknown` escalation). Not an `engine_mode`/surface gate (SHADOW ran the engine
end-to-end correctly; `mode:CURATED` is a display flag only).

## 4. Ordered minimal fix list

**NECESSARY** (without these, `IT/TOURISM/10d/all-facts` can never close as B1):

1. **[PACK — new signature]** Restrict `el.d1-multi-entry-support` to
   `intent.entry_pattern == MULTIPLE` (D1 is literally multi-entry — currently
   ignores the fact), and align the 5 `hr.d1-*` rules to the same condition (today
   keyed on purpose alone, independent of D1's real scope).
2. **[PACK — same signature]** Restrict `el.d2-multi-entry-support` (BUSINESS visa)
   to purposes intersecting only `BUSINESS_MEETINGS` (today also matches
   TOURISM/FAMILY — a pure tourist should never touch the business visa), align the 5
   `hr.d2-*` rules.
3. **[PACK — same signature]** Restrict `el.d12-multi-entry-support` (PRE-INVESTMENT
   visa) to purposes intersecting only `INVESTMENT` (today also matches
   TOURISM/FAMILY), align the 5 `hr.d12-*` rules.
4. **[PACK — new content, not just code]** Add a VOA-eligible-nationality condition
   to `el.b1.tourism` (currently absent — B1 would support any nationality, which is
   legally wrong: VOA has an official ~90+-country list distinct from the 19-country
   BVK list already present for A1). Requires primary-source regulatory research
   (Kepmen/Permenkumham VOA list) — not purely technical.
5. **[OPERATIONAL]** Items 1-4 go into a **new** RulePack (new `sequence`, new
   `rule_pack_id`), signed and activated via the already-proven `activate_pack.py`
   pipeline (M5 key custody). Stays in SHADOW — does not touch ENFORCE (still blocked
   on DPIA/analytics-TTL, unchanged).
6. **[VERIFICATION]** After activation, re-run the exact payload from §2: must return
   `SUPPORTED_CANDIDATES` / `B1_VOA_ELIGIBLE`. Then repeat the pattern-audit (§3,
   the 31-rule count) for at least one gold case per remaining interview category —
   without this second pass the ledger stays near-100%-abstention on everything
   except TOURISM.

**NICE TO HAVE** (not blocking the IT/TOURISM case):

7. **[ARCHITECTURE — decision, not a fix]** Re-evaluate whether "REVIEW always beats
   SUPPORTED, decision-wide" (`evaluator.py:1391-1397`, `enums.py:41-47`) is the
   right long-term semantics vs. one that could express "you auto-qualify for B1, or
   you can pursue D1 which needs review" as two distinct outcomes in the same
   response. This is a spec change already gate-approved once (P0-B, 2 cross-family
   seats) — re-open with the same rigor (4-LLM panel per CLAUDE.md §6), not lightly.
8. **[SCHEMA — future]** If Bali Zero wants CV/proof-of-funds/itinerary/passport
   validity to become _real_ checks (rather than always-true flags), the
   corresponding `FactPath` entries need to be added to the closed vocabulary
   (`enums.py` `FactPath` + contract migration). Today D1/D2/D12 human review is
   review-by-design, so this only matters if the goal is to automate those multiple-entry
   routes too, not just B1.

No changes to `evaluate_path.py`, the router, or `fact-mapper.ts` are needed for the
requested case — the defect is entirely in the active RulePack's **content**, not in
the engine's code (the code behaves exactly as documented and already
cross-family-reviewed).

## Evidence provenance

- Live evaluate call: SHADOW, `mode:CURATED`, run 2026-08-07 from Mini against
  `https://nuzantara-rag.fly.dev/api/visa-oracle/evaluate`, rule pack sequence 3
  (`2026.8.8`) — the pack active in prod at the time of this investigation.
- Rule definitions: `apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-002.source.json`
  (content identical to the active seq-3 pack per the 2026-08-08 "night 07→08" LIVE
  STATE entry, which re-signed prod-002's content as seq 3 with a retroactive
  `valid_period.from`).
- Code citations: `evaluator.py:1-135` (module docstring, P0-A/B/C design notes),
  `evaluator.py:1275-1430` (`evaluate_with_trace`), `enums.py:41-119`
  (`DecisionState`, `RuleStage`, `STAGE_ORDER`), `evaluate_path.py` (router
  orchestration), `visa_oracle_evaluate.py` (HTTP shell),
  `apps/mouth/.../_lib/{tree,fact-mapper,shadow-client}.ts`.
