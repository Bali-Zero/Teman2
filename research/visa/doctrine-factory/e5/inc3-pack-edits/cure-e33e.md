---
adversarial_review: codex
date: 2026-08-19
domain: visa
client_case: none
sources:
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
    note: "el.e33e.deposit-income-basis (defective, UNSATISFIABLE) and el.e33e.retirement (working sibling, same product)"
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
    note: "CL-E33-04, the sole claim backing the E33E deposit/income floor — VERIFIED, states AND ('plus'), not OR"
  - path: research/visa/doctrine-factory/claims/e2b-batch2-conflict-report.md
    note: "CF-7 UPDATE (RESOLVED) — confirmed this resolves ONLY the age-55-vs-60 question, nothing about deposit/income basis"
  - path: research/visa/doctrine-factory/cards/E33E.md
    note: "§3.8/§4/§6 — names the rule UNSAT but does not itself assert an OR reading"
discovered_by: agent.air-m5.backend-rag.visa-e5-seq9-implementer-b
adversarial_review: none (STOP-and-flag finding, no cure authored — nothing to adversarially review yet)
---

# E33E cure — STOPPED per spec's own explicit clause (no `cure-e33e.json` produced)

## What the spec asked for

Spec Step 3a (`research/visa/doctrine-factory/e5/2026-08-19-e5-increment3-spec.md`) instructs:
replace `el.e33e.deposit-income-basis`'s `when` with
`all(purpose=RETIREMENT, age>=55, ANY(deposit-conjunct, income-condition))` — an OR/either-basis
reading — and explicitly says: *"Ground the OR reading on the E33E claims (CF-7 resolution /
e2b-batch2 ledger; card `cards/E33E.md`) and cite the claim id... If the claims support
BOTH-required instead of OR, stop and flag — do not guess (the cure choice is doctrinal; current
evidence says OR...)."*

## What this session actually found, grepped fresh this turn

1. **CF-7 (RESOLVED) is entirely about the AGE threshold (55 vs 60), not about deposit/income
   OR/AND.** Read in full from `e2b-batch2-conflict-report.md` lines 137-165 — every sentence of
   the RESOLVED disposition concerns `Permenkumham No. 11 Tahun 2024` Pasal 33(2)(j)(4) /
   61(1) / 62(1) / 101(2)(f)(4) and the 55-vs-60 age figure. It never mentions the deposit or
   income facts at all. There is no "e2b-batch2 ledger" entry (`e2b-batch2-claim-ledger.md`) that
   discusses E33E's deposit/income basis either (grepped `-i 'e33e\|CL-E33'` across that file:
   zero matches).
2. **The only claim that backs the deposit/income floor is `CL-E33-04`** (`e2b-batch1-claim-ledger.md:187-194`), state **VERIFIED**, text verbatim: *"E33E ('Silver Hair') requires a
   minimum blocked deposit of USD 50,000 in an Indonesian state-owned bank, **plus** proof of
   monthly income/pension of at least USD 3,000."* — "plus" is conjunctive (AND), not disjunctive
   (OR). No claim anywhere in the 10 ledger files under `research/visa/doctrine-factory/claims/`
   states or implies an either/or basis (grepped `-i 'deposit.*income\|income.*deposit\|either.*
   deposit\|either.*income\|deposit.*or\|xor'` across every claim ledger: zero matches).
3. **The sibling rule `el.e33e.retirement`** (same product, `rulepack-prod-007.source.json`
   lines 3211-3280) already encodes the AND-basis correctly and is a genuinely working
   ELIGIBILITY→SUPPORT rule (`E33E_RETIREMENT_ELIGIBLE`): `all(purpose=RETIREMENT, age>=55,
   deposit-conjunct-of-3, income>=3000)`. This is the exact AND semantics CL-E33-04 describes,
   already live and reachable for E33E — the "full path" coverage is not missing.
4. **`E33E.md` §3.8** (the doctrine card, written this same session by an earlier pass) names the
   rule UNSAT and calls the XOR/AND mixture "a copy-paste error from a template" but does **not**
   itself assert that OR is the doctrinally-intended reading — it only diagnoses the
   contradiction, it does not resolve which side (OR or AND) was meant.

## Verified guilt (proof, this turn — see `prove_cures.py` output below)

```
[PASS] GUILT: original el.e33e.deposit-income-basis is UNSATISFIABLE — expect_clean=False, findings=1
    - el.e33e.deposit-income-basis: condition is UNSATISFIABLE — brute-force over 6 distinct leaf
      condition(s) (each treated as an independent boolean atom) finds zero of 64 assignments that
      satisfy `when`; this rule can never fire. NOTE: this check is sound for UNSAT-by-structure but
      blind to arithmetic contradictions between different leaves...
```

(full run captured in `cure-e33g.md`'s proof section too — same script, same invocation, one run)

## Disposition: STOP, per the spec's own fallback clause

The spec's premise ("current evidence says OR") does not hold up against the actual claim
ledgers: the ONLY relevant claim (`CL-E33-04`, VERIFIED) states AND, and the pack's own working
sibling rule for the same product already encodes AND. Per the spec's explicit instruction, this
session is **not guessing** and is **not authoring `cure-e33e.json`**. This is the STOP-and-flag
outcome the spec itself names as the correct move when the claims support BOTH-required.

**This is an OPEN CP3 ITEM.** Two ways forward, neither decided here (doctrinal call, not a
compiler-lint call):

- **(a) Retire the rule.** `el.e33e.deposit-income-basis`'s only claimed function
  (`E33E_DEPOSIT_INCOME_BASIS_ADVISOR_CHECK`, an "advisor check" SUPPORT effect) adds no reachable
  coverage beyond what `el.e33e.retirement` already provides — if the correct semantics really is
  AND, a fixed version of this rule would be a **literal duplicate** of `el.e33e.retirement`'s
  `when` (same 4 facts, same AND structure, same effect type). Simplest honest cure: drop
  `el.e33e.deposit-income-basis` from seq-9 entirely, since `el.e33e.retirement` already covers
  its intended ground.
- **(b) Author a new claim before authoring a new rule.** If the OR-basis "advisor check for
  partial qualification" concept is doctrinally desired (i.e. someone meeting only ONE of
  {deposit, income} should get a SOFT advisor-check SUPPORT rather than silently falling through
  to NEEDS_INPUT/no-match), that is a genuinely different eligibility path than CL-E33-04 covers
  and needs its own claim, sourced and VERIFIED, before any rule cites it — per this compiler's
  own VERIFIED-only lint (`compile_claims.py` Lint 1), a rule with no backing claim is itself a
  compile error, and inventing an OR claim here would violate the exact anti-hallucination
  discipline this task operates under.

**For reference only — NOT authored, NOT a deliverable, NOT adversarially reviewed** — if CP3
rules for option (a) (retire), no JSON is needed at all: seq-9 simply omits
`el.e33e.deposit-income-basis` from the folded rule set. If CP3 rules for option (b) and later
grounds an OR claim, the AND-only reading (mirroring `el.e33e.retirement` structurally, which
this session confirmed does compile clean and satisfiable) would be the fallback repair — but
authoring that now, without a grounding claim, would just be a second guess dressed as a fix. Not
done.

## Adversarial review

Reviewed 2026-08-19 by two cross-family refuter seats (Codex GPT-5.6 high; Kimi K3) as part
of the whole seq-9 fold working tree — both DROVE the real evaluator rather than reading the
diff. Findings touching this artifact and their dispositions are consolidated in
`../2026-08-19-e5-increment3-fold.md` §Adversarial review (fold doc); no finding against this
artifact survived undisposed.
