# Guide — Family E30 (study)

Law: the five adjacent `<CODE>.json` cards, pinned to the official pages captured on 2026-10-17. Only E30A and E30B have substantive pages. E30, E30E and E30F are secondary `NOT_FOUND` cards, projected as `TO_VERIFY` and never offered by this Guide.

```text
Q1  At which level will you study in Indonesia?
    Secondary school or below ............. E30A
    Undergraduate / postgraduate / doctoral E30B

Q2  Have you been accepted by the educational institution?
    no  → NOT_COVERED

Q3  Who will sponsor your studies in Indonesia?
    Individual / the educational institution → continue
    Other / none ........................... NEEDS_SPONSOR

Q4  How many months do you need to study? (positive whole number)
    E30A: ≤12 → 1 YEAR; ≤24 → 2 YEAR; >24 → STAY_TOO_LONG
    E30B: ≤12 → 1 YEAR; ≤24 → 2 YEAR; ≤48 → 4 YEAR; >48 → STAY_TOO_LONG
    Fitting choice → OK + stay_option {value, unit}, in the original YEAR unit
```

One fact per question; no path asks more than four questions. Invalid or missing answers ask the same question again. YEAR means exactly 12 MONTHS in the Guide comparison (coordinator ruling, 2026-10-18). DAY options are not compared with months. These are initial-stay choices, not cumulative extension limits; no `OK_WITH_EXTENSION` is inferred.

| Question    | Verbatim condition in each code's Law card                                                                                                                                                                |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Study level | E30A `definition_verbatim`: “jenjang sekolah menengah atas dan jenjang di bawahnya”; E30B: “jenjang sarjana, pascasarjana hingga doktoral”                                                                |
| Admission   | Both `requirements_verbatim`, item 7: “Surat penerimaan dari institusi pendidikan yang mencantumkan lama masa pendidikan yang akan ditempuh orang asing.”                                                 |
| Sponsor     | Both `sponsor_required.verbatim` require a sponsor; special requirement 6 permits an individual or the institution where the foreign national studies. The institution is not the only permitted sponsor. |
| Duration    | E30A `stay_days` states 1 or 2 years; E30B states 1, 2 or 4 years. E30B's punctuation issue is retained; its PNBP headings separately list those three durations.                                         |

Passport validity, funds, bank statements, photo, CV, itinerary, sponsorship evidence and the admission letter belong to the result checklist in `requirements_verbatim`. No extra age threshold, vocational route, ministry study permit or work entitlement is inferred from older engine data. The complete conduct restrictions, including the qualification “terkecuali diperlukan dalam pekerjaannya”, remain in the Law card.

Prices are only the five exact `kitas_permits` keys in `family_e30.json`, checked against the official Bali Zero price list. PNBP amounts in the cards are reference material, never client prices. Being outside the price list does not prove a visa is not sold: `is_sold` for the three secondary codes is NULL.

ITAS → ITAP: [ITAP.json](ITAP.json) preserves the reviewed official text and per-code mapping verbatim. Every E30 code has `itas_to_itap_eligible_as_stated: null`, `status: TO_VERIFY`. Education is absent from the reviewed category list, which does not establish a code-specific prohibition. E30A/B's generic conversion wording identifies no ITAP target; the DB `itap` remains NULL for all five codes. No ITAP question is offered until verified.

TO_VERIFY: missing E30/E30E/E30F substantive pages; offshore/onshore application location for all codes; cumulative extension maxima; per-code ITAP eligibility; E30B stay punctuation. Vocational-only study is not explicitly covered by the E30B activity sentence and is not offered.
