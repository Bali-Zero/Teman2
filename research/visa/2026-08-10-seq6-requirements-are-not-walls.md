---
date: 2026-08-10
domain: visa
adversarial_review: codex
adversarial_review_candidate_sha256: a973d69a8bbfdc880ef905c2c15dfaf69938741c30f0d3137f0a7391b517e63c
adversarial_review_note: "TWO independent Codex reviews, different scopes, different verdicts. (a) Current-diff red-team on candidate a973d69a…: PASS, zero blockers. (b) gpt-5.6-sol at xhigh pointed at the PACK SEMANTICS of a parallel draft: DO-NOT-SHIP, 8 findings, 2 CRITICAL — one of which (E33F offered to an under-55 applicant) is present in the diff that (a) passed, because it is not something the diff introduced. A review scoped to what changed cannot see a defect that was already there. One of (b)'s findings, a rule_pack_id said to be off-convention, was rechecked and DOES NOT HOLD."
client_case: none (Visa Oracle V2 rule pack seq-6)
sources:
  - rulepack-prod-005.source.json (seq-5)
  - rulepack-prod-006.source.json (seq-6, unsigned and unactivated)
  - evaluator.py (review precedence and union coverage)
  - backend/tests/services/visa_engine/test_prod_sequence6_semantics.py
  - backend/tests/services/visa_engine/test_seq6_refuter_witnesses.py
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

7. A rule that reads a fact which genuinely DISQUALIFIES one product belongs in
   `HARD_FILTER`, which is a third box the first drafts did not use. As
   `HUMAN_REVIEW` it deletes every candidate; as `SUPPORT` it asserts an
   eligibility the fact denies. E33E already had `hf.e33e.age-below-55`; E33F did
   not, so `el.e33f.age-under-55` — support, true exactly when the applicant is
   UNDER the statutory 55 — offered the retirement KITAS to a 46-year-old, and
   with the age unestablished offered it without asking. `hf.e33f.age-below-55`
   mirrors the E33E filter, `on_unknown` included, so a missing age produces a
   question.
8. Three rules are deleted because none of them can do what its id claims.
   `el.d12-long-stay-review` conjoins `stay_days > 365` with the D12 gate's
   `stay_days <= 180` and is therefore unsatisfiable; the product was already
   unreachable for such a request, so what was lost is the explicit signal, and
   dead code carries no signal. `hr.e30a-minor-consent` fires on STUDY plus being
   a minor and tests neither consent nor a guardian, so it blanked the answer for
   a 16-year-old with admission, a study sponsor and a confirmed guardian;
   `review.minor-without-guardian`, which tests the thing, stays.

The final source pack contains 104 rules, including 15 `HUMAN_REVIEW` rules. It
remains unsigned and unactivated.

Points 1-6 and the E23U/E23V and E30E/E30F removals come from the M5 lane
(PR #3954); points 7-8 from the Mini lane. The two were written in the same
window against the same file and neither contained the other — each closed
something the other missed. This section is the union, and both lanes' focused
suites pass against it (`test_prod_sequence6_semantics.py` 3 passed,
`test_seq6_refuter_witnesses.py` 8 passed).

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

### Second review, different scope, opposite verdict

A second Codex seat (`gpt-5.6-sol`, `xhigh`, read-only) was pointed not at the
diff but at the PACK SEMANTICS of a parallel draft, with instructions to refute
and cite file:line. It returned **DO-NOT-SHIP**, 8 findings. Two were CRITICAL
and both were reproduced against the real evaluator before anything was changed:

- **E23U/E23V were gated by `EMPLOYMENT` plus any confirmed Indonesian sponsor**,
  which every ordinary employee satisfies. The M5 lane had already reached the
  same conclusion independently; the two cures agree.
- **A requirement that reads a disqualifying threshold is not a requirement.**
  `el.e33f.age-under-55` is support and is true exactly when the applicant is
  under the statutory 55, so a 46-year-old was offered the retirement KITAS.
  **This finding survived the diff-scoped review above** — not because that
  review was careless, but because the defect was not introduced by the diff it
  read. Its `PASS` and this `DO-NOT-SHIP` are both correct answers to different
  questions, and only one of the two questions is "is the artifact right".

One HIGH (`hr.e30a-minor-consent` walls a compliant minor) is cured in point 8.
Two MEDIUM concerned withdrawn numbers and are addressed in *Evidence boundary*.
One LOW claimed the `rule_pack_id` violates the UUIDv5-from-canonical-URL
convention; recomputing it reproduces the stored id exactly, so it is
**rejected**. A refuter is a lead, not a verdict.

Worth recording beyond this pack: the review that passed the draft on which the
CRITICAL was found was the in-house `devils-advocate` agent, which is pinned
`model: sonnet` — the same family as the generator, and its description still
advertises a different model than its pin. The seat named in a research file's
frontmatter is load-bearing, and so is its scope.

## Residual boundaries

- E23U/E23V and E30E/E30F are intentionally fail-closed until the interview
  schema carries the facts that distinguish them and the rule pack cites the
  authority needed for each legal claim.
- **An ABSENT fact and an UNKNOWN one are answered differently, and only one of
  them asks.** With the age declared unknown the engine returns `NEEDS_INPUT`
  naming `person.birth_date`; with the key simply not present it returns
  `NO_SUPPORTED_PATH` and asks nothing. Neither produces a false offer, but an
  applicant the interview never asked about age gets a blank answer rather than
  a question. Pinned, not fixed, by
  `test_deleting_the_age_key_is_not_the_same_as_declaring_it_unknown`.
- **A product removed by a `HARD_FILTER` carries no client-facing reason.**
  `SUPPORT_REASON_COPY` covers reasons that appear ON an offer, so a 46-year-old
  is correctly not offered E33F and is told nothing about why.
- **`el.e33e.age-55-59-disputed-band` and `el.e31j-dependency-age` remain
  support**, i.e. they assert eligibility in a band the source calls disputed
  and for an adult sibling. Both are the M5 lane's deliberate advisor-check
  framing and were left as authored rather than overridden from a parallel lane;
  they are named here so the choice is visible rather than inherited.
- This pack does not decide employer-side labour compliance. A later change
  must add explicit facts and current authoritative labour sources before it
  can claim RPTKA, job-title, KBLI, or restricted-role verification.
- Historical packs remain immutable. The frontend keeps the old spouse-work
  and KITAP reason keys as aliases, but renders the corrected, non-categorical
  copy for persisted decisions.

## Activation prerequisite

The pack is source-only. Signing and activation are separate operator steps;
this correction neither signs nor activates seq-6.
