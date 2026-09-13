---
date: 2026-09-12
domain: visa
client_case: none (public editorial corpus of the E33 Second Home family)
adversarial_review: codex
adversarial_review_seats: codex-sol (PRE-review BLOCK with 5 conditions, then POST refuter BLOCK with 16 findings on the frozen head) + gemini-3.1-pro (claim table over the 5 sources vs the fact registry) + claude-sonnet-5 spalla-review (second reader, 6 findings) + tp1-qwen3.8-max (adversarial language re-read of .id against .en, BLOCK)
sources:
  - research/secondhome/e33-fact-registry.json
  - apps/mouth/src/lib/blog/categories.ts
  - https://balizero.com/visas/second-home-visa-indonesia
  - https://balizero.com/sitemap.xml
  - https://balizero.com/llms-full.txt
---

# E33 / Second Home — editorial census on canonical URLs, 12 September 2026

Window `SHWEB-20260911 / W3-SH-EDITORIAL`, base `70b43c5459`. The machine-readable half of
this census is [`editorial-disposition.json`](editorial-disposition.json) — one row per
family, with the evidence lines that justify its disposition. This file is the reading of it.

**128 families / 498 files** mention E33 or Second Home. All
**128** canonical URLs return HTTP 200 and serve a canonical
equal to the URL requested; **121** are `index, follow` and in the
sitemap, **7** serve `noindex, nofollow` and are absent from it (19
files across those 7 families).

The URL rule matters more than it looks: an article's public URL is
`/<normalized category>/<slug>`, computed from the CONTENT FOLDER, not the frontmatter —
`immigration/` is served at `/visas/`. **`/blog/<slug>` is not an article URL.** It answers
HTTP 200 with a not-found page, so any probe that reads only the status code passes on it.
Every URL in this census is an `articleUrl()`.

## Dispositions

| Disposition                    | Families |
| ------------------------------ | -------- |
| `blocked-on-zero-ruling`       | 4        |
| `census-only-no-defect-found`  | 104      |
| `corrected-in-pr1`             | 1        |
| `lexical-hit-not-an-e33-claim` | 3        |
| `noindex-registered`           | 2        |
| `queued-pr2`                   | 14       |

### corrected-in-pr1 — the canonical family

| Canonical URL                                           | Locales            | robots        | sitemap | amount lines | why                                                                                                  |
| ------------------------------------------------------- | ------------------ | ------------- | ------- | ------------ | ---------------------------------------------------------------------------------------------------- |
| `https://balizero.com/visas/second-home-visa-indonesia` | en, fr, id, it, ru | index, follow | yes     | 0            | Rewritten in all five locales against the fact registry. probe --sources 68->0, --claims 0 failures. |

Its five sources went from 68 lines carrying the superseded threshold to 0, and the
correction is not a substitution: the property route, the invented fee tables and every claim
the registry marks `pending` were disposed of individually. See the commit body.

### queued-pr2 — the superseded threshold, stated as the Second Home requirement

One PR, one concern: these are corrected in a separate PR from a fresh `origin/main`, line by
line, each with its before/after in the ledger. They are NOT swept.

| Canonical URL                                                                                               | Locales            | robots            | sitemap | amount lines | why                                                                                                                                                                                                    |
| ----------------------------------------------------------------------------------------------------------- | ------------------ | ----------------- | ------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `https://balizero.com/living/bali-digital-nomad-complete-guide`                                             | en, fr, id, it, ru | index, follow     | yes     | 3            | RE-CORRECTED 2026-09-12 (second reader, finding 7 — this cell was wrong TWICE). It briefly said these 3 lines carry `IDR 2 billion` as a parenthetical conversion of USD 130,000. They do not: `digital-nomad/bali-digital-nomad-complete-guide{,.fr,.ru}.mdx:59` read *"Second Home Visa (5-year first grant, renewable up to a 10-year cumulative maximum, with IDR 2B savings)"* and contain no `130,000` on that line at all. The superseded figure stands alone AS the savings requirement, which is what the first classification said. Queued for PR-2, line by line.                                              |
| `https://balizero.com/living/living-in-bali-honest-guide`                                                   | en, fr, id, it, ru | noindex, nofollow | no      | 4            | 4 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/taxes/southeast-asias-digital-nomad-visa-race-who-wins-in-2026`                       | en, id, it         | index, follow     | yes     | 3            | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/visas/bali-immigration-law-what-expats-need-to-know-in-2026`                          | en, id, it         | index, follow     | yes     | 3            | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/visas/balis-visa-crackdown-reaches-digital-nomads-as-australia-raises-alert`          | en, fr, id, it, ru | index, follow     | yes     | 5            | 5 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/visas/e31-student-visa-indonesia`                                                     | en, fr, id, it, ru | index, follow     | yes     | 4            | 4 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/visas/e311a-retirement-visa-kitas-guide`                                              | en, fr, id, it, ru | index, follow     | yes     | 3            | Read by hand, not by the line check: the amount is the body row of a table whose column header reads 'Second Home Visa (B211)' — which also mislabels the visa index and calls it non-renewable. PR-2. |
| `https://balizero.com/visas/family-reunification-indonesia`                                                 | en, fr, id, it, ru | index, follow     | yes     | 8            | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/visas/indonesia-visa-landscape-what-every-foreign-visitor-and-investor-needs-to-know` | en, fr, id, it     | index, follow     | yes     | 4            | 4 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/visas/indonesia-visa-timeline-comparison`                                             | en, fr, id, it, ru | index, follow     | yes     | 3            | Read by hand, not by the line check: the amount sits in a Second Home document checklist under its own section heading. PR-2.                                                                          |
| `https://balizero.com/visas/indonesias-digital-nomad-visa-what-remote-workers-need-to-know`                 | en, id, it         | index, follow     | yes     | 3            | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/visas/indonesias-global-citizen-visa-pitch-competitiveness-play-or-pr-move`           | en, id, it         | index, follow     | yes     | 3            | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/visas/kitas-2026-the-complete-indonesia-work-stay-permit-roadmap`                     | en, id, it         | index, follow     | yes     | 6            | 6 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line.                                              |
| `https://balizero.com/visas/kitas-for-digital-nomads-reality`                                               | en, fr, id, it, ru | index, follow     | yes     | 9            | Read by hand, not by the line check: the amount is under the heading 'The Second Home Visa (SHV)' and in the SHV column of the comparison table. PR-2.                                                 |

Three of them were classified by HAND, not by the probe, and that is the most useful thing
this census found — see Adversarial review below.

### blocked-on-zero-ruling — the four noIndex E33 families

Rewrite-or-delete is Zero's call. This window censuses them and stops. They keep the claims
they have; they are out of the index and out of the sitemap, which is containment, not
correction.

| Canonical URL                                                                                             | Locales            | robots            | sitemap | amount lines | why                                                                                                                                                                                                           |
| --------------------------------------------------------------------------------------------------------- | ------------------ | ----------------- | ------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `https://balizero.com/visas/indonesia-second-home-visa-2026-what-wealthy-expats-need-to-know-now`         | en, fr, id, it, ru | noindex, nofollow | no      | 5            | noIndex E33 family. Rewrite-or-delete is Zero's ruling to give; this window censuses it and stops. It keeps whatever claims it has until then — it is out of the index and out of the sitemap, not corrected. |
| `https://balizero.com/visas/indonesias-second-home-visa-kitas-e33-the-complete-2025-framework`            | en, id, it         | noindex, nofollow | no      | 3            | noIndex E33 family. Rewrite-or-delete is Zero's ruling to give; this window censuses it and stops. It keeps whatever claims it has until then — it is out of the index and out of the sitemap, not corrected. |
| `https://balizero.com/visas/indonesias-second-home-visa-the-5-year-and-10-year-kitas-fully-decoded`       | en, id, it         | noindex, nofollow | no      | 6            | noIndex E33 family. Rewrite-or-delete is Zero's ruling to give; this window censuses it and stops. It keeps whatever claims it has until then — it is out of the index and out of the sitemap, not corrected. |
| `https://balizero.com/visas/live-long-term-in-indonesia-second-home-golden-visa-pnb-immigration-law-firm` | en, fr, id, it, ru | noindex, nofollow | no      | 0            | noIndex E33 family. Rewrite-or-delete is Zero's ruling to give; this window censuses it and stops. It keeps whatever claims it has until then — it is out of the index and out of the sitemap, not corrected. |

### lexical-hit-not-an-e33-claim — deliberately untouched

The amount appears; the claim is about something else. Correcting these would publish a false
correction, which is the exact failure this window was told to avoid.

| Canonical URL                                                                               | Locales            | robots        | sitemap | amount lines | why                                                                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------- | ------------------ | ------------- | ------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `https://balizero.com/business/kbli-2025-professional-services-consulting-design-bali-2026` | en, fr, id, it, ru | index, follow | yes     | 7            | Verified by reading the surrounding section: the amount is interior-design project values (IDR 200 juta to IDR 2 miliar per project). Left untouched deliberately — sweeping it would publish a false correction.                    |
| `https://balizero.com/living/why-bali-keeps-drawing-the-worlds-most-restless-minds`         | en, id, it         | index, follow | yes     | 1            | Verified by reading the surrounding section: the amount is PT PMA minimum paid-up capital of Rp 2,500,000,000. Left untouched deliberately — sweeping it would publish a false correction.                                           |
| `https://balizero.com/property/buying-property-bali-foreigners-guide`                       | en, fr, id, it     | index, follow | yes     | 8            | Verified by reading the surrounding section: the amount is regional property-price thresholds in a property table (Bali 5 miliar, other areas 2 miliar). Left untouched deliberately — sweeping it would publish a false correction. |

### noindex-registered and census-only

| Canonical URL                                               | Locales            | robots            | sitemap | amount lines | why                                                                                                                 |
| ----------------------------------------------------------- | ------------------ | ----------------- | ------- | ------------ | ------------------------------------------------------------------------------------------------------------------- |
| `https://balizero.com/living/education-expat-children`      | en, fr, id, it, ru | noindex, nofollow | no      | 0            | Serves noindex,nofollow and is absent from the sitemap; not an E33-core family and carries no superseded threshold. |
| `https://balizero.com/living/freelancing-legally-indonesia` | en, fr, id, it, ru | noindex, nofollow | no      | 0            | Serves noindex,nofollow and is absent from the sitemap; not an E33-core family and carries no superseded threshold. |

The remaining **104** families mention E33 or Second Home
and carry no superseded threshold in any locale. They are listed in the JSON with their served
robots, sitemap membership and canonical agreement. This is an inventory with a live probe per
URL, not a legal audit of their contents: a family with no superseded THRESHOLD may still carry
another stale claim, and nothing here says otherwise.

## Adversarial review

**Codex Sol, PRE-review before any diff: BLOCK, five conditions.** All five were met before the
first file was edited, and two of them changed the work materially.

1. _The probe measured tokens, not claims._ It over-matched `IDR 20B` (`2[.,]?0*` accepts a
   trailing zero) and under-matched `IDR 2 000 000 000`, `2 à 5 milliards IDR`, `two billion`,
   `due miliardi`, `два миллиарда`, `Rp2M`. Two of those omissions were REAL and French: they
   are why the spec believed the French source was already clean. Cured, with a `--selftest`
   carrying both guilt and innocence cases — innocence matters as much, because a probe that
   flags another product's figure is what produces a blind sweep.
2. _The property route confused buying property with qualifying for E33._ `Hak Pakai`, a PT PMA
   majority holding and a province-varying IDR 2B-5B threshold were all asserted;
   `e33_base_property_title_type` is an `unknown` fact, so naming any qualifying title resolves
   it by assertion. The rewrite names none and says which questions stay open.
3. _Prices._ Delete the decomposition and the five-year totals, point at the service page, and
   introduce no price — the contract-lock forbids this window touching a price value.
4. _Zeros are not proof._ Positive per-locale assertions were added (`--claims`): every locale
   must SAY USD 130,000, own name, BUMN, USD 1,000,000, completed strata and Pasal 113, and must
   NOT name a qualifying title or a decomposed fee range. That check caught two residual
   `Hak Pakai` mentions in the Indonesian and Russian sources after the amount check read 0.
5. _Define the mutant on the real sort._ Done — see the test note below.

**The blind spot Codex predicted, measured.** Its counterexample was a page that keeps the false
requirement while passing the zero check, by putting the product name and the amount on
different lines. Three families do exactly that: `e311a-retirement-visa-kitas-guide` (the amount
is a body row under a column header reading "Second Home Visa (B211)" — which also mislabels the
visa index and calls the permit non-renewable), `indonesia-visa-timeline-comparison` (a Second
Home document checklist under its own heading) and `kitas-for-digital-nomads-reality` (under the
heading "The Second Home Visa (SHV)", and in the SHV column of a table). The line-scoped check
called all three clean. `probe-superseded-threshold.py --attribute` now prints each amount with
the nearest product mention above it, and the three are queued for PR-2.

**Gemini 3.1 Pro** read the five sources against the registry and returned a claim table
(`evidence/2026-09/.../prereview/gemini-3.1-pro-claim-table.txt`). Its load-bearing findings:
the two senior routes E33E and E33F were missing entirely from a guide that calls itself
complete; the processing times contradicted `processing_time_4wd`; the dependent, ITAP,
entry-window and annual-proof claims were stated as settled while the registry has them
`pending`; and two locale divergences (the KITAP closing sentence missing in it/id, the fit-memo
CTA missing in ru/fr). All are corrected.

**A measurement trap worth keeping.** The first version of the live census called a page "not
found" when its body contained the string `Article not found`, and reported 128 of 128. Every
served page carries that string in its client bundle. The sound test is whether the SERVED
canonical equals the requested URL — by which all 128 resolve correctly.

**Codex Sol again, POST refuter on the frozen head `65850ec8a6`: BLOCK, 16 findings.** It read
read-only, verified the HEAD itself, and reproduced three defects in my own guards using my own
`scan` function — which is the part worth keeping, because the guards were reporting zero while
the defects stood:

- `--sources` MISSED `IDR 2000000000` (nine zeros, no separator) and `2.000.000.000 IDR` (amount
  before currency, the order Italian and Indonesian prose actually use), and CONVICTED
  `IDR 2,000,000,000,000` on its own prefix — a figure a thousand times larger.
- `--claims` convicted the sentence _"Whether Hak Pakai qualifies for E33 remains unknown"_: it
  searched for the title's NAME and ignored the assertion of uncertainty around it. Scar
  family #3, on the guard I built to avoid scar family #3.
- The freshness test could not kill a tie-break that compares only the category segment
  (`a.url.split("/")[3]`): all six fixtures sat in six different categories, so that mutant never
  had a real tie to break and V8's stable sort preserved the order the fixtures already wanted.

All three are cured, each with guilt AND innocence cases: the retired-figure sentence is now
acquitted while _"you do not need a sponsor, you need IDR 2 billion in the bank"_ still convicts,
and a marker in a NEIGHBOURING sentence does not reach across into this one. The freshness suite
gained a same-category pair (`/visas/alpha` and `/visas/zulu`, same date, different folders that
both normalize to `/visas/`), and the category-only mutant now fails 3 of 5.

> **SUPERSEDED 2026-09-12 (round 3).** The two paragraphs above describe the marker-based acquittal — `SUPERSEDED_MARKER`, the clause window, the uncertainty vocabulary — as if it were current. It is not: that whole mechanism was DELETED. Every occurrence of the threshold is now convicted, and the only acquittal is an explicit entry in `research/secondhome/superseded-threshold-allowlist.json`. The sentences described as acquitted here would be convicted by the probe that ships. Kept as the record of what was tried and why it failed, not as a description of the code.

Six content findings were accepted and cured in a second round: the property alternative was
published in `description`, `excerpt`, `seoDescription` and the comparison table WITHOUT the
completed-unit condition that `e33_base_property_alternative` (confirmed / BERSYARAT) attaches to
it; the duration was stated flat where `e33_first_grant_duration` says _up to_ five years; the
10-year cumulative cap was quoted without the first-grant condition that `pasal_113_cumulative_caps`
puts on it; a property-validation method ("verification with BPN records") was prescribed while
`property_validation_standard` is `unknown`; joint accounts were excluded outright, which is
stricter than the registry's own-name condition; and the bank-proof list was headed "what counts
as proof" three paragraphs above a sentence saying the accepted document is not settled.

**The seventh cross-locale divergence, and it took a third seat to find.** The Russian source asked
for a criminal-record certificate from the country of RESIDENCE where English, Italian, Indonesian
and French all say country of ORIGIN — for anyone living outside their own country those are two
different documents. The Italian excluded _diritti di superficie_ on top of leasehold, resolving by
assertion part of the `unknown` fact `e33_base_property_title_type`, three lines above the sentence
that declares that same title unresolved. Both are cured.

**tp1-qwen3.8-max, adversarial language re-read of the Indonesian against the English: BLOCK.**
Never an author — it objects and does not rewrite. Six meaning drifts, of which four were mine and
are cured: the custody sentence narrowed "them" (deposit AND property) to _dana klien_, funds only;
the FAQ dropped the two named counterparties ("Ditjen Imigrasi and the bank") the English names;
"at which exchange rate" became "at which date's rate", narrowing an open question; and the
retirement-account category collapsed into pension funds. Three defects in the pre-existing
translation are cured because they change meaning: the eligibility section was headed _Persyaratan
Kepatuhan_ (compliance) over content about who qualifies, _menyuarakan_ ("to voice an opinion")
stood where "to vote" was meant, and _berkecayaan_ is not a word. The remainder are registered
below and NOT swept in this PR.

**Round 2, and the acquittals had to be fenced twice.** The cures above introduced two
acquittals — a sentence that RETIRES the superseded figure is not a defect, and a title named
as unresolved is not a claim — and an acquittal is an evasion route until someone tries to walk
through it. Three seats did.

A second reader executed the module rather than reading the regex, and got two sentences past
the guard:

- *"The rules used to be simpler, but today the Second Home Visa still requires IDR 2 billion in
  the bank."* — "used to be" is a supersession marker, and it governed a clause that asserts the
  figure as current.
- *"The bank letter format is not confirmed, but the qualifying title for the E33 property route
  is Hak Pakai."* — the hedge belongs to `bank_confirmation_letter_format_and_timing`, a
  different pending fact, and it acquitted an assertion about the title.

The POST refuter then walked through a third: *"The processing time remains unknown! Hak Pakai
qualifies for E33."* — `!` was not a clause boundary. And it found the symmetric error, a FALSE
conviction: *"Whether Hak Pakai qualifies for E33 is unclear"* was convicted because `unclear`
was not in the uncertainty vocabulary while `unknown` was.

The cure is that the marker now governs a CLAUSE, not a sentence: the window breaks on `.`, `!`,
`?`, newline, `;`, `:`, the comma, and the adversative conjunctions of all five languages. All
four sentences are `--selftest` cases now, two guilty and two innocent, so the fence is measured
in both directions rather than asserted.

> **SUPERSEDED 2026-09-12 (round 3).** The two paragraphs above describe the marker-based acquittal — `SUPERSEDED_MARKER`, the clause window, the uncertainty vocabulary — as if it were current. It is not: that whole mechanism was DELETED. Every occurrence of the threshold is now convicted, and the only acquittal is an explicit entry in `research/secondhome/superseded-threshold-allowlist.json`. The sentences described as acquitted here would be convicted by the probe that ships. Kept as the record of what was tried and why it failed, not as a description of the code.

**tp1-qwen3.8-max, round 2: CONCERNS** (from BLOCK). It confirmed the eight cured sentences read
naturally in Indonesian and named three remaining items that would mislead a reader rather than
merely read stiffly: the tax section was headed *Kepemilikan Pajak* ("tax ownership"), the SPT
gloss called the annual RETURN an annual TAX, and the file used *perbaruan* in headings and
*perpanjangan* in running text for the same act. All three are cured, plus two it found in
passing: *kode penyerta* / *tanggungan* named dependents two ways inside one file, and the Golden
Visa cell read *5 tahun lebih* ("more than 5 years") where "5 more years" was meant. The rest of
its list is translation register, not meaning, and is registered below.

### Registered, deliberately not swept in PR-1

| What                                                                                                                                                                                                                                                            | Where                                | Why it waits                                                                                                        |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `melaporkan ke` for `melapor ke`, `pembebasan catatan kriminal` / `sertifikat catatan kriminal` for the same document, `disodorkan`'s register | `.id`, lines outside this PR's hunks | Pre-existing translation quality, no claim against the registry. A language pass is its own concern and its own PR. **Corrected 2026-09-12 (second reader, finding 8):** this row also listed `ketiadaan` and `SPT (pajak tahunan)`. Both were GONE at the head this row describes — they were cured by the mirror commit after the census text was written, so the row registered as "deliberately not swept" two things that had already been swept. |
| Untranslated "Indonesia" in Russian (17) and French (13, counting `Bahasa Indonesia`) body prose — counts re-measured by the second reader on 2026-09-12; this row previously said "~14" and "8"                                                                                                                                                                                           | `.ru`, `.fr`                         | Same: pre-existing, lexical, not a claim.                                                                           |
| Russian tax-table number formatting inconsistency                                                                                                                                                                                                               | `.ru`                                | Same.                                                                                                               |
| The inert `canonicalUrl` frontmatter still reading `/immigration/`                                                                                                                                                                                              | all five                             | Moves in PR-2 with the proof that no consumer reads it.                                                             |

### Outside-registry operative facts (imperator ruling B, 2026-09-12)

The fact registry settles 34 E33 facts (`jq '.facts | length'`; this line said 33 until the second reader counted it on 2026-09-12). It is not a whitelist of everything an article may say —
but every NUMERIC or deadline requirement outside it has to name a source, and where there is
none the claim is hedged or removed rather than published.

| Claim                                                     | Source                                                                                                                                                               | Disposition                                                                                                                                                |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Wajib Lapor within 7 days; annual reporting               | **UNSUPPORTED.** POST refuter round 2, finding 9: `multiple-kitas-indonesia.fr.mdx:194` states Wajib Lapor per COMPANY and names no 7-day deadline; the second reference is about photographs. The ANNUAL obligation is supported; the 7-day figure is not.                   | **FIGURE REMOVED** in all five locales — the registration duty stays, now worded as "within the deadline immigration states on the permit"                                                                                                                                                      |
| SKTT domicile registration within 14 days, annual renewal | **UNSUPPORTED.** Finding 9: `kitas-extension-renewal-guide.ru.mdx:194` lists the SKTT among the documents and establishes neither 14 days nor an annual renewal.                                                               | **FIGURE REMOVED** in all five locales — the domicile registration stays, worded as "within the deadline the kelurahan states"                                                                                                                                                      |
| 183 days as the tax-residency threshold                   | UU PPh 36/2008, named in the article itself alongside the figure                                                                | Stays — a statute the text cites by name                                                                                                                                                      |
| Apostilled criminal-record certificate; 2-6 weeks         | **UNSUPPORTED for the DURATION.** Finding 9: neither reference documents a mandatory E33 criminal-record certificate processed in 2-6 weeks. The apostille step itself is corpus-wide practice. | **FIGURE REMOVED** in all five locales — the apostille step stays, the estimate is now attributed to the issuing authority                                                                                                                                                      |
| Passport-size photographs 4x6 cm                          | `immigration/e-voa-electronic-visa-on-arrival-guide.id.mdx:257`                                                                                                      | Stays                                                                                                                                                      |
| KITAP after 3 consecutive years on a KITAS                | `immigration/investor-kitas-guide.mdx`, `immigration/e28a-investor-kitas-guide.mdx`, `immigration/shareholder-kitas-requirements.mdx`                                | Stays                                                                                                                                                      |
| **Passport valid for at least 60 months (5 years)**       | None found in the corpus or the registry                                                                                                                             | **REPLACED 2026-09-12** — the official E33 page requires "a valid national passport with a minimum validity of 6 (six) months before expiry". The 60-month rule is gone in all five locales and the six-month rule is stated with its source. Fetched HTTP 200 this session through the kanwilpapuabarat service-proxy; the article cites only the canonical `https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33` |
| **IDR 5,000,000 fine for a missed Wajib Lapor**           | None found in the corpus or the registry                                                                                                                             | **REMOVED** in all five locales — the obligation stays, the unsourced amount does not                                                                      |
| **SPT annual filing by 31 March**                         | **NONE FETCHED.** `pajak.go.id` answered HTTP 403 and 404 to this session on 2026-09-12; the deadline was never quoted verbatim from an official page                 | **FIGURE REMOVED** in all five locales — the filing duty stays, worded as the statutory deadline for individual taxpayers. Listed below as a registry proposal |
| **180+ consecutive days of absence triggering a review**  | None found in the corpus or the registry                                                                                                                             | **FIGURE REMOVED** in all five locales — the risk statement stays and now says plainly that no public rule states the number of days |
| Free fit memo                                             | Owner decision, 2026-07-23 (`/secondhome` §3)                                                                                                                        | Stays — a ruled decision, not an invented price                                                                                                            |

### i18n claim ratchet — the baseline delta, hit by hit

`src/i18n/secondhome-article-claims.baseline.json` pins every lexical hit of the E33 claim guards
by `path | pattern | sha256(line)`. Rewriting a line that carries a hit rotates its hash, so the
delta is mechanical and every entry has to be traced rather than regenerated. Measured on the final
tree: the five canonical family files are the ONLY paths in the delta; the other nine families are
untouched.

| Direction | Hit                                         | Why it is lexical and not a new claim                                                                                                                                                                             |
| --------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| new       | `USD 1,500` in all five locales             | The line that carries it is the one RETIRING the figure: "USD 1,500 per month is a superseded pre-2024 figure and does not qualify anyone today."                                                                 |
| new       | `5-10 years` in `.mdx`                      | The Golden Visa's range in the comparison sentence, not the E33's. Same claim as before; the hash rotated because the sentence beside it changed from "a 5-year stay permit" to "a stay permit of up to 5 years". |
| new       | split-deposit patterns in en/it/fr          | The sentence denies it: "Bali Zero does not offer, and has never offered, a deposit split across several banks."                                                                                                  |
| new       | E33-work pattern in `.it` FAQ               | The FAQ answer states the opposite — the base E33 does not include work authorization. The pattern's negation lookbehinds are English-shaped and do not cover the Italian phrasing.                               |
| stale     | `IDR 2,000,000` pattern in en/it/id/ru      | Gone because the superseded threshold is gone. This is the cure landing in the ratchet.                                                                                                                           |
| stale     | rehashed en `5-10 years` and it FAQ entries | Same claims, rewritten lines.                                                                                                                                                                                     |
| rehash    | en `5-10 years`, successor round             | Measured after the round-3 content cures: the total is unchanged at **275**, with exactly ONE key rotated — the English comparison line that carries the Golden Visa's `5-10 years` range, because the naming sentence for `Special Residency Visa` was inserted into it. Zero keys outside the canonical family changed, in either direction. The comparison was computed by dumping the suite's own `actual` set and diffing it against the committed baseline; the dump and the delta live in the session scratchpad and are NOT committed, so the reproducible check in the tree is the suite itself — `npx vitest run src/i18n/secondhome-article-claims.test.ts`, 12 passed, which fails on any added or stale key. |

### Registry proposals (imperator ruling 4, 2026-09-12 — NOT applied here)

`e33-fact-registry.json` is untouched by this PR, by mandate. The official E33 page, fetched by
this session (HTTP 200, via the kanwilpapuabarat service-proxy; the canonical URL is
`https://www.imigrasi.go.id/wna/daftar-visa-indonesia/E33`), carries four things the registry
does not. They are proposals for Zero, listed so they are not lost:

| Proposed fact                                                                                  | Verbatim from the page                                                                                                                                              | Why it matters                                                                       |
| ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `passport_validity_e33`                                                                        | "a valid national passport with a minimum validity of 6 (six) months before expiry"                                                                                  | Used in this PR with the source named; it deserves a fact id                          |
| `bank_statement_usd_2000_last_3_months`                                                        | "a personal bank statement with a minimum balance of USD 2,000 ... covering the last 3 (three) months"                                                               | A documentary requirement in NO article and NO fact. NOT added to the article here    |
| `immigration_guarantee_within_90_days_of_itas`                                                 | "Applicants must fulfil the Immigration Guarantee requirement within a maximum period of 90 (ninety) days from the date the Temporary Stay Permit (ITAS) is granted" | Distinct from the entry window `entry_window_90d_and_force_majeure`, which stays pending |
| `stay_option_5_or_10_years` — **the two language versions of the page disagree**                | EN: "You may stay in Indonesia for 5 (five) or 10 (ten) years, depending on your selected option" (quoted verbatim from the English page fetched this session). The second reader fetched the same canonical URL and read the Indonesian "Masa tinggal": a first permit of at most 5 years, extendable to 10 years in TOTAL — which is the registry's confirmed fact, not a 10-year first grant. | The discrepancy is the finding. Nothing is written into the article either way, and the registry is untouched. For Zero: the English rendering of the official page reads as a 10-year OPTION and the Indonesian one does not. |

Also for Zero, from the round-2 rulings: a registry line stating that no working-day estimate
ships without a source, and the SPT filing deadline sourced from an official page that answers.

## What stays open

- The 14 `queued-pr2` families still publish the superseded threshold. Until PR-2 is served,
  the built `llms-full.txt` still carries their lines; only this family's are gone.
- The four `blocked-on-zero-ruling` families wait on Zero.
- 16 facts on the letter tracker are still `pending`. Nothing here promoted one.
- This census is lexical in its SELECTION. A family it does not list is a family whose files
  never say E33, Second Home, Rumah Kedua or SHV — not a family certified correct.
