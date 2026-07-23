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

**STILL OPEN:**

1. **Dependent pricing** — how dependent (E31B etc.) processing is priced
   alongside the main E33 application.
2. **StayGuard** — whether/how the deposit-monitoring product is offered to
   E33 clients (research band: USD 900–2,500/yr).
3. **BSI conditional** — whether to build a conditional BSI offering ahead of
   the letter-005 reply.
4. **Split-deposit planning** — whether to ever offer it (subject to letter
   006 Q4; Gemini seat advises never asking/planning it).
5. **ITAP marketing** — whether ITAP-after-3y may be mentioned in marketing
   once letter 006 Q7 is answered.
6. **Property-route module** — whether to build the USD 1M property-route
   product module (blocked on `property_validation_standard`).
7. **Age 55–59 handling** — `BERSYARAT` (conditional with disclosure) vs
   hard-block until Immigration confirms (addendum 007 Q1).
8. **noIndex articles disposition** — the 16 contradictory articles are
   noIndexed but still reachable: accept reachable / add a `getAllArticles()`
   noIndex filter / delete (master list item 0.5).
9. **Engine scope** — FactPath/products for bank-route only (E33/E33E/E33F,
   Codex recommendation) vs full E33A–F coverage (master list item 2.2).
