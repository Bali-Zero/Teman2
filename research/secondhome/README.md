---
adversarial_review: gemini
---

# E33 Second Home Visa — corner

The **E33 vertical** is Bali Zero's Second Home Visa line: base E33 (USD 130k
BUMN-bank deposit **or** USD 1M completed strata-title property, up to 5-year
first grant), E33E (senior 55+, USD 50k deposit + USD 3,000/month, 5y), E33F
(senior 1y, USD 3,000/month income only), plus the government-sponsored
E33A/E33C and expertise E33B variants.

## Where the truth lives

- **`e33-fact-registry.json`** — the single source of truth for every E33
  claim: status (`confirmed|pending|disputed|unknown`) + confidence
  (`JELAS|BERSYARAT|BELUM_DIATUR_PUBLIK`) + source. Check it before writing
  any E33 content, code, or client answer.
- **`e33-letter-response-tracker.md`** — the 6 official letters sent
  2026-07-21 (Mandiri 001, BRI 002, BNI 003, BTN 004, BSI 005, Ditjen
  Imigrasi 006), question → fact-id → platform surface mapping, and the
  reply-intake procedure.
- Verified research base: `research/curated-qa-corrections-2026-07-21/`
  (esp. `visa-second-home-variants.jsonl`, `visa-golden-investor.jsonl`,
  `visa-catalog-sweep.jsonl`) and
  `research/visa/2026-07-21-e31j-e33f-kitap-verification.md`.

## FORBIDDEN to claim until the letters are answered

- **BSI (sharia) equivalence** — do not say a BSI deposit qualifies
  (`bsi_sharia_accepted`, letter 005).
- **Split deposits** — do not say the USD 130k may be split across banks
  (`split_deposit_accepted`, letter 006).
- **ITAP after 3 years** — do not market a permanent-stay conversion path
  (`itap_after_3y_criteria`, letter 006).
- **Any-bank placement** — the deposit is at a **state-owned (BUMN)** bank;
  do not generalize to "any Indonesian bank" (`bank_proof_format`, letter 006).

Also treat as unclaimed: mid-permit basis switch deposit↔property
(`basis_switch_deposit_property_mid_permit`, BELUM_DIATUR_PUBLIK), blocked vs
evidenced deposit, remote account opening, IDR equivalence/FX date, property
validation standard, E33F family inclusion and sponsor requirement — all
`unknown` in the registry.

Known dispute to disclose, never paper over: senior age is **55** per
Permenkumham 11/2024 Pasal 33(2)(j)(4) (and live imigrasi pages) but
Pasal 33(10)(d) still reads **60** — operate on 55, disclose the ambiguity
(`age_55_59_ambiguity_e33e`).

## Owner-decision list (Zero)

**DECIDED 2026-07-23:**

- **Fit Memo** → **FREE** (the E33 fit assessment is free; no paid Fit Memo).
- **Pricing** → **IDR 39,000,000 all-inclusive** for the base E33 (5y). Never
  decompose into PNBP + service fee in any client-facing material (org rule:
  single all-inclusive price; Fable-5 gate item 4.5).
- **Branch merge** → the content-freeze and fact-registry branches are
  approved for Claude-session review & merge (master list item 0.1).
- **Dependent pricing** → **start price-alignment work now** (no final number
  yet — owner wants the alignment drafted; add-on flat per person is the
  working model, to be sized against the dependent-code answer).
- **StayGuard** → **YES**, offered to E33 clients — but launched only after
  the Day-90 compliance tracker exists (master list 3.2), so the service is
  deliverable from day one.
- **Property-route module** → **YES** as a separate paid module (with due
  diligence); still blocked on `property_validation_standard` (addendum 007
  Q5) — do not build before the reply.
- **BSI conditional** → decide **when the letter-005 reply arrives**; BSI
  stays a forbidden claim until then.
- **Split-deposit planning** → **NEVER offered**. LPS-cap exposure may be
  explained to clients, but no split-placement strategy is sold or planned.
- **Age 55–59 (E33E)** → **BERSYARAT**: accept with a signed client
  disclosure of the Pasal 33 55-vs-60 ambiguity; no hard-block (addendum 007
  Q1 pending).
- **ITAP marketing** → **YES, only after** the written letter-006 Q7 reply,
  and only with its exact formulation ("may apply, subject to Immigration
  evaluation") — never "automatic conversion" or a guaranteed outcome.
- **noIndex articles** → add a **`getAllArticles()` noIndex filter** so the
  16 contradictory articles leave the /insights listing and /feed (reversible,
  keeps the files for the queued editorial rewrite).
- **Engine scope (2.2)** → **bank-route only**: FactPath + engine products
  for E33 / E33E / E33F (+ dependents). E33A/B/C deferred (no sales intent),
  E33D stays hidden (official stub).

## Adversarial review

Reviewed 2026-07-24 by seats != author (author: kimi) on the full branch diff:
**gemini** (verdict MERGE-WITH-NOTES — no factual/regulatory error introduced;
note on pricing-bridge key alignment at merge) and **glm-5.2** (no FIX-FIRST;
two of its findings refuted with evidence by the orchestrator, two valid merge
notes recorded on the PR). Review artifacts: PR #3042 comments +
`/tmp/secondhome_review/pr_review_gemini.md`, `pr_review_glm.md`.
