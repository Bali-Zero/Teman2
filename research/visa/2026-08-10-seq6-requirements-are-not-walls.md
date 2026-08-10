---
date: 2026-08-10
domain: visa
adversarial_review: codex
adversarial_review_candidate_sha256: a973d69a8bbfdc880ef905c2c15dfaf69938741c30f0d3137f0a7391b517e63c
adversarial_review_note: "Independent current-diff red-team PASS: zero blockers, P0/P1 findings, or other findings; formatter-only final candidate independently rehashed and confirmed."
client_case: none (Visa Oracle V2 rule pack seq-6)
sources:
  - rulepack-prod-005.source.json (seq-5)
  - rulepack-prod-006.source.json (seq-6, unsigned and unactivated)
  - evaluator.py (review precedence and union coverage)
  - backend/tests/services/visa_engine/test_prod_sequence6_semantics.py
  - https://peraturan.bpk.go.id/Home/Download/28550/UU%206%20Tahun%202011.pdf
---

# seq-6 — a requirement is a condition, not a proof

Seq-5 can return `HUMAN_REVIEW_REQUIRED` with no candidates as soon as a review
rule fires. Several such rules select only an audience (for example, a stated
purpose); they do not test the requirement named by their reason code. Turning
all of those rules into support is also unsafe: eligibility coverage is a union,
so a purpose-only condition can manufacture a route when no genuine eligibility
gate passed.

## Evidence boundary

An earlier draft of this note reported a 4,000-applicant fuzz run, exact
reachability ratios, and a 23-persona gold result. No checked-in harness or
current-head report reproduces those figures. They are withdrawn and are not
merge evidence for seq-6.

The evidence retained here is deliberately smaller and reproducible: the
sanctioned compiler, real evaluator counterexamples, and focused frontend copy
tests. This correction does not claim corpus-scale fuzz or gold coverage.

## What the corrected seq-6 does

1. A converted requirement may add a candidate reason only when it is conjoined
   with that product's genuine eligibility gate. It cannot supply coverage on
   its own.
2. A generic employee can receive the base E23 route, but not E23U or E23V.
   Seq-6 does not claim that job title, KBLI, RPTKA, or Kepmenaker restrictions
   were checked because the interview has no facts that prove those checks and
   the affected rules had no authoritative labour source.
3. A generic student can receive the generic/higher-education routes supported
   by their facts, but not the KEK-only E30E or exchange-only E30F routes. Those
   specialisations remain unavailable until mutually exclusive discriminator
   facts exist.
4. Mixed-marriage KITAP copy follows Article 60(2) of UU 6/2011: two years of
   marriage plus a signed `Pernyataan Integrasi`. It does not infer two years on
   an immigration status and explicitly says those prerequisites were not
   verified.
5. Spouse-work copy follows Article 61 without erasing the statutory right to
   work and/or conduct business. It separates the assessment scope for
   employment and self-employment/business and makes no categorical Kemenaker
   denial.
6. The Article 60(2)/61 rules cite an append-only `PRIMARY_LAW` record for the
   official BPK PDF. The verified PDF SHA-256 is
   `63708ca9b50ac067834a50c395385fdc6abda22e6e51def88983cd1ad685edc4`.

The final source pack contains 106 rules, including 16 `HUMAN_REVIEW` rules. It
remains unsigned and unactivated.

## Reproducible regression evidence

The focused evaluator suite executes the canonical source through
`load_rule_pack_payload`, `build_compiled_pack`, and `evaluate`; it does not scan
JSON strings. It proves these counterexamples:

- generic `EMPLOYMENT` + Indonesian entity + sponsor: E23 is present; E23U/E23V
  and the unverified labour reason codes are absent;
- generic undergraduate + admission + sponsor: E30/E30B are present; E30E/E30F
  are absent;
- E31A onshore-conversion assessment: the two corrected reason codes are
  emitted and both resolve only to the primary UU 6/2011 record with Article
  60(2) and Article 61 locators.

Local focused results on 2026-08-10:

- canonical compiler: zero errors;
- evaluator regression file: 3 passed;
- Ruff on the evaluator regression file: passed;
- adapter Vitest file: 21 passed.

These results are focused regression evidence, not a claim of whole-suite,
fuzz, gold, or production behaviour.

## Adversarial review

An independent Codex red-team reviewed composite candidate
`a973d69a8bbfdc880ef905c2c15dfaf69938741c30f0d3137f0a7391b517e63c`
and returned `PASS`: zero blockers, P0/P1 findings, or other findings.

The reviewer independently confirmed the net rule delta (-15), the fail-closed
absence of E23U/E23V/E30E/E30F rules, and preservation of generic E23 and
E30/E30A/E30B support. They downloaded the official BPK PDF, reproduced its
SHA-256, verified the Article 60(2)/61 text and locators, and checked that the
relevant amendment sections in UU 11/2020 and UU 63/2024 do not amend those
articles. They also verified the old-key UI aliases and corrected caveated
copy.

On the reviewed bytes, the canonical compiler reported zero errors; the
evaluator suite passed 3/3; the adapter Vitest suite passed 21/21; Ruff,
Prettier, and `git diff --check` passed; and the post-gate composite rehash was
unchanged. The surviving residual risk is deliberate: the special routes stay
dormant until explicit discriminator facts and sourced eligibility rules are
added in a new reviewed pack.

## Residual boundaries

- E23U/E23V and E30E/E30F are intentionally fail-closed until the interview
  schema carries the facts that distinguish them and the rule pack cites the
  authority needed for each legal claim.
- This pack does not decide employer-side labour compliance. A later change
  must add explicit facts and current authoritative labour sources before it
  can claim RPTKA, job-title, KBLI, or restricted-role verification.
- Historical packs remain immutable. The frontend keeps the old spouse-work
  and KITAP reason keys as aliases, but renders the corrected, non-categorical
  copy for persisted decisions.

## Activation prerequisite

The pack is source-only. Signing and activation are separate operator steps;
this correction neither signs nor activates seq-6.
