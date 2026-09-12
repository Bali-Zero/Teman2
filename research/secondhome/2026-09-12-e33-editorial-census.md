---
date: 2026-09-12
domain: visa
client_case: none (public editorial corpus of the E33 Second Home family)
adversarial_review: codex-sol (PRE-review, BLOCK with 5 conditions) + gemini-3.1-pro (claim table over the 5 sources vs the fact registry)
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

| Disposition | Families |
| --- | --- |
| `blocked-on-zero-ruling` | 4 |
| `census-only-no-defect-found` | 104 |
| `corrected-in-pr1` | 1 |
| `lexical-hit-not-an-e33-claim` | 3 |
| `noindex-registered` | 2 |
| `queued-pr2` | 14 |

### corrected-in-pr1 — the canonical family

| Canonical URL | Locales | robots | sitemap | amount lines | why |
| --- | --- | --- | --- | --- | --- |
| `https://balizero.com/visas/second-home-visa-indonesia` | en, fr, id, it, ru | index, follow | yes | 0 | Rewritten in all five locales against the fact registry. probe --sources 68->0, --claims 0 failures. |

Its five sources went from 68 lines carrying the superseded threshold to 0, and the
correction is not a substitution: the property route, the invented fee tables and every claim
the registry marks `pending` were disposed of individually. See the commit body.

### queued-pr2 — the superseded threshold, stated as the Second Home requirement

One PR, one concern: these are corrected in a separate PR from a fresh `origin/main`, line by
line, each with its before/after in the ledger. They are NOT swept.

| Canonical URL | Locales | robots | sitemap | amount lines | why |
| --- | --- | --- | --- | --- | --- |
| `https://balizero.com/living/bali-digital-nomad-complete-guide` | en, fr, id, it, ru | index, follow | yes | 3 | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/living/living-in-bali-honest-guide` | en, fr, id, it, ru | noindex, nofollow | no | 4 | 4 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/taxes/southeast-asias-digital-nomad-visa-race-who-wins-in-2026` | en, id, it | index, follow | yes | 3 | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/visas/bali-immigration-law-what-expats-need-to-know-in-2026` | en, id, it | index, follow | yes | 3 | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/visas/balis-visa-crackdown-reaches-digital-nomads-as-australia-raises-alert` | en, fr, id, it, ru | index, follow | yes | 5 | 5 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/visas/e31-student-visa-indonesia` | en, fr, id, it, ru | index, follow | yes | 4 | 4 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/visas/e311a-retirement-visa-kitas-guide` | en, fr, id, it, ru | index, follow | yes | 3 | Read by hand, not by the line check: the amount is the body row of a table whose column header reads 'Second Home Visa (B211)' — which also mislabels the visa index and calls it non-renewable. PR-2. |
| `https://balizero.com/visas/family-reunification-indonesia` | en, fr, id, it, ru | index, follow | yes | 8 | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/visas/indonesia-visa-landscape-what-every-foreign-visitor-and-investor-needs-to-know` | en, fr, id, it | index, follow | yes | 4 | 4 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/visas/indonesia-visa-timeline-comparison` | en, fr, id, it, ru | index, follow | yes | 3 | Read by hand, not by the line check: the amount sits in a Second Home document checklist under its own section heading. PR-2. |
| `https://balizero.com/visas/indonesias-digital-nomad-visa-what-remote-workers-need-to-know` | en, id, it | index, follow | yes | 3 | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/visas/indonesias-global-citizen-visa-pitch-competitiveness-play-or-pr-move` | en, id, it | index, follow | yes | 3 | 3 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/visas/kitas-2026-the-complete-indonesia-work-stay-permit-roadmap` | en, id, it | index, follow | yes | 6 | 6 line(s) state the superseded threshold AS the Second Home requirement, on the amount's own line. One PR = one concern: PR-2 corrects them line by line. |
| `https://balizero.com/visas/kitas-for-digital-nomads-reality` | en, fr, id, it, ru | index, follow | yes | 9 | Read by hand, not by the line check: the amount is under the heading 'The Second Home Visa (SHV)' and in the SHV column of the comparison table. PR-2. |

Three of them were classified by HAND, not by the probe, and that is the most useful thing
this census found — see Adversarial review below.

### blocked-on-zero-ruling — the four noIndex E33 families

Rewrite-or-delete is Zero's call. This window censuses them and stops. They keep the claims
they have; they are out of the index and out of the sitemap, which is containment, not
correction.

| Canonical URL | Locales | robots | sitemap | amount lines | why |
| --- | --- | --- | --- | --- | --- |
| `https://balizero.com/visas/indonesia-second-home-visa-2026-what-wealthy-expats-need-to-know-now` | en, fr, id, it, ru | noindex, nofollow | no | 5 | noIndex E33 family. Rewrite-or-delete is Zero's ruling to give; this window censuses it and stops. It keeps whatever claims it has until then — it is out of the index and out of the sitemap, not corrected. |
| `https://balizero.com/visas/indonesias-second-home-visa-kitas-e33-the-complete-2025-framework` | en, id, it | noindex, nofollow | no | 3 | noIndex E33 family. Rewrite-or-delete is Zero's ruling to give; this window censuses it and stops. It keeps whatever claims it has until then — it is out of the index and out of the sitemap, not corrected. |
| `https://balizero.com/visas/indonesias-second-home-visa-the-5-year-and-10-year-kitas-fully-decoded` | en, id, it | noindex, nofollow | no | 6 | noIndex E33 family. Rewrite-or-delete is Zero's ruling to give; this window censuses it and stops. It keeps whatever claims it has until then — it is out of the index and out of the sitemap, not corrected. |
| `https://balizero.com/visas/live-long-term-in-indonesia-second-home-golden-visa-pnb-immigration-law-firm` | en, fr, id, it, ru | noindex, nofollow | no | 0 | noIndex E33 family. Rewrite-or-delete is Zero's ruling to give; this window censuses it and stops. It keeps whatever claims it has until then — it is out of the index and out of the sitemap, not corrected. |

### lexical-hit-not-an-e33-claim — deliberately untouched

The amount appears; the claim is about something else. Correcting these would publish a false
correction, which is the exact failure this window was told to avoid.

| Canonical URL | Locales | robots | sitemap | amount lines | why |
| --- | --- | --- | --- | --- | --- |
| `https://balizero.com/business/kbli-2025-professional-services-consulting-design-bali-2026` | en, fr, id, it, ru | index, follow | yes | 7 | Verified by reading the surrounding section: the amount is interior-design project values (IDR 200 juta to IDR 2 miliar per project). Left untouched deliberately — sweeping it would publish a false correction. |
| `https://balizero.com/living/why-bali-keeps-drawing-the-worlds-most-restless-minds` | en, id, it | index, follow | yes | 1 | Verified by reading the surrounding section: the amount is PT PMA minimum paid-up capital of Rp 2,500,000,000. Left untouched deliberately — sweeping it would publish a false correction. |
| `https://balizero.com/property/buying-property-bali-foreigners-guide` | en, fr, id, it | index, follow | yes | 8 | Verified by reading the surrounding section: the amount is regional property-price thresholds in a property table (Bali 5 miliar, other areas 2 miliar). Left untouched deliberately — sweeping it would publish a false correction. |

### noindex-registered and census-only

| Canonical URL | Locales | robots | sitemap | amount lines | why |
| --- | --- | --- | --- | --- | --- |
| `https://balizero.com/living/education-expat-children` | en, fr, id, it, ru | noindex, nofollow | no | 0 | Serves noindex,nofollow and is absent from the sitemap; not an E33-core family and carries no superseded threshold. |
| `https://balizero.com/living/freelancing-legally-indonesia` | en, fr, id, it, ru | noindex, nofollow | no | 0 | Serves noindex,nofollow and is absent from the sitemap; not an E33-core family and carries no superseded threshold. |

The remaining **104** families mention E33 or Second Home
and carry no superseded threshold in any locale. They are listed in the JSON with their served
robots, sitemap membership and canonical agreement. This is an inventory with a live probe per
URL, not a legal audit of their contents: a family with no superseded THRESHOLD may still carry
another stale claim, and nothing here says otherwise.

## Adversarial review

**Codex Sol, PRE-review before any diff: BLOCK, five conditions.** All five were met before the
first file was edited, and two of them changed the work materially.

1. *The probe measured tokens, not claims.* It over-matched `IDR 20B` (`2[.,]?0*` accepts a
   trailing zero) and under-matched `IDR 2 000 000 000`, `2 à 5 milliards IDR`, `two billion`,
   `due miliardi`, `два миллиарда`, `Rp2M`. Two of those omissions were REAL and French: they
   are why the spec believed the French source was already clean. Cured, with a `--selftest`
   carrying both guilt and innocence cases — innocence matters as much, because a probe that
   flags another product's figure is what produces a blind sweep.
2. *The property route confused buying property with qualifying for E33.* `Hak Pakai`, a PT PMA
   majority holding and a province-varying IDR 2B-5B threshold were all asserted;
   `e33_base_property_title_type` is an `unknown` fact, so naming any qualifying title resolves
   it by assertion. The rewrite names none and says which questions stay open.
3. *Prices.* Delete the decomposition and the five-year totals, point at the service page, and
   introduce no price — the contract-lock forbids this window touching a price value.
4. *Zeros are not proof.* Positive per-locale assertions were added (`--claims`): every locale
   must SAY USD 130,000, own name, BUMN, USD 1,000,000, completed strata and Pasal 113, and must
   NOT name a qualifying title or a decomposed fee range. That check caught two residual
   `Hak Pakai` mentions in the Indonesian and Russian sources after the amount check read 0.
5. *Define the mutant on the real sort.* Done — see the test note below.

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

## What stays open

- The 14 `queued-pr2` families still publish the superseded threshold. Until PR-2 is served,
  the built `llms-full.txt` still carries their lines; only this family's are gone.
- The four `blocked-on-zero-ruling` families wait on Zero.
- 16 facts on the letter tracker are still `pending`. Nothing here promoted one.
- This census is lexical in its SELECTION. A family it does not list is a family whose files
  never say E33, Second Home, Rumah Kedua or SHV — not a family certified correct.
