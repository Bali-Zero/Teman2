---
date: 2026-08-24
domain: visa
adversarial_review: codex
client_case: Second Home Studio — country comparator feature (E33 vs. MM2H / LTR / D7-GV / SRRV)
sources:
  - https://ltr.boi.go.th/ (fetched live 2026-08-24, primary — confirmed)
  - https://www.motac.gov.my/en/mm2h (WebFetch attempt 2026-08-24, primary — page reachable, no financial figures on it)
  - https://www.mm2h.gov.my/ (WebFetch attempt 2026-08-24 — HTTP 403, unreachable to WebFetch)
  - https://aima.gov.pt/en/immigration/aria-golden-visa (WebFetch attempt 2026-08-24 — TLS certificate error, unreachable to WebFetch)
  - https://vistos.mne.gov.pt/... (WebFetch attempt 2026-08-24 — HTTP 404, wrong/stale path)
  - https://pra.gov.ph/ (WebFetch attempt 2026-08-24, primary — page reachable, no tier figures on homepage)
  - secondary/legal-aggregator consensus (Emerhub, Zagdim, Bratuca, Golden Visa Map, Bright!Tax, Bitizenship, Connaught Law, Belzuz, ACCRALAW, Chambers and Partners) — searched 2026-08-24, used only where primary fetch failed
  - research/secondhome/e33-fact-registry.json (E33 column SSOT — not re-verified, per mandate)
  - "UPGRADE PASS 2026-08-24 (browser lane, reaching the pages WebFetch could not) — sources below"
  - "https://www.mm2h.gov.my/category/overview, /platinum, /gold, /silver, /sez (Ministry of Tourism, Arts and Culture, browser-fetched live 2026-08-24, primary, confirmed; each page footer-stamped Last Update 10/02/2026)"
  - "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2007-34544675 (Lei n.º 23/2007, consolidated text, Art. 3.º and Art. 52.º; browser-fetched live 2026-08-24, primary, official gazette, confirmed; current to its last amendment, Lei n.º 9/2025 of 2025-02-13 on Art. 3.º, Lei n.º 61/2025 of 2025-10-22 on Art. 52.º)"
  - "https://diariodarepublica.pt/dr (Portaria n.º 1563/2007, 11 December 2007; browser-fetched live 2026-08-24, primary, official gazette, confirmed, still in force)"
  - "https://diariodarepublica.pt/dr (Decreto-Lei n.º 29-A/2026, 30 January 2026; browser-fetched live 2026-08-24, primary, official gazette, confirmed; recital cites the RMMG-setting instrument, Decreto-Lei n.º 139/2025 of 29 December 2025)"
  - "https://aima.gov.pt/en (site search for golden visa; browser-fetched live 2026-08-24; zero search results, screenshotted; plus direct URL probes for golden-visa and D7 paths, both page-not-found)"
  - "https://pra.gov.ph/SRRVisa (browser-fetched live 2026-08-24, primary, confirmed; page renders the live Philippine clock at capture time)"
---

# Second Home Studio — Country Comparator: Graded Fact Sheet

**Grader:** Claude (Opus, this session). **Author:** Gemini 3.1 Pro (live web search), scratchpad
artifact `country-comparator-facts.md`, ~36 KB, dated 2026-08-24. This document is the graded,
demoted, and annotated output of that artifact — it is not a straight copy. Long verbatim passages
were not carried over; figures are restated with attribution and a verification tag.

**UPGRADE PASS 2026-08-24 (same day, later in the session):** the first grading pass below used
`WebFetch`, which hit a 403 (mm2h.gov.my), a TLS certificate error (aima.gov.pt), a 404 (a stale
MNE path), and a JS-rendered page it couldn't execute (diariodarepublica.pt's consolidated-text
viewer) — so Malaysia, Portugal, and the Philippines' 50+ SRRV tier were demoted to 🟡/🔴. A
browser-automation lane, run separately the same day, reached all four of those pages directly:
five `mm2h.gov.my` category pages (Ministry of Tourism, Arts and Culture, each footer-stamped "Last
Update: 10/02/2026"), the official gazette `diariodarepublica.pt` for Lei 23/2007 (consolidated),
Portaria 1563/2007, and Decreto-Lei 29-A/2026, plus `pra.gov.ph/SRRVisa` live. Every tag below that
changed from 🟡/🔴 to ✅ is upgraded on that new evidence — screenshots and full-text captures in
`country-comparison-research/` (session scratchpad, referenced by filename below), not on a second
guess at the same unreachable page. Three things did **not** upgrade and are called out explicitly
in §2: SRRV Smile's discontinuation stays an inference from absence (no PRA statement exists to
cite), the SRRV Courtesy table remains ambiguous, and the AIMA checks found no "golden visa" page
through the search and paths tested.

**Tagging key used throughout:**
- ✅ **PRIMARY-CONFIRMED** — I fetched the government/authority URL myself this session and the
  figure matches.
- 🟡 **SECONDARY-CONSENSUS** — the government URL was unreachable to me (403 / TLS error / 404 /
  no content), so the figure is corroborated only by independent secondary sources (law firms,
  relocation aggregators) that agree with each other and with the generator's claim. Plausible,
  not primary-verified.
- 🔴 **UNVERIFIED** — I did not independently check this figure at all this session. Carried from
  the generator's draft as-is, flagged, not to be treated as fact.
- ❌ **CORRECTED / DEMOTED** — I found the generator's claim to be wrong, overstated, or
  unsupported by the source it cited, and have corrected or removed it.

---

## 1. Grading verdict, by axis

### Axis 1 — Source quality per claim

The sheet's own "Cited Primary & Government Sources" section lists nine government URLs and dates
every claim "Retrieved: August 24, 2026." I attempted to fetch **five** of those government pages
directly this session (BOI Thailand, MOTAC/mm2h.gov.my Malaysia, AIMA Portugal, MNE Portugal, PRA
Philippines) via `WebFetch`. Result: **only one reached and confirmed the cited figures on that
attempt** — Thailand's `ltr.boi.go.th`. The other four failed or lacked the content on that attempt:

- `www.mm2h.gov.my` → **HTTP 403 Forbidden**. `www.motac.gov.my/en/mm2h` loaded but is a checklist
  page with no financial figures — neither government URL the sheet cites actually surfaced the
  Silver/Gold/Platinum deposit numbers to `WebFetch`.
- `aima.gov.pt/en/immigration/aria-golden-visa` → TLS certificate error, unreachable.
- `vistos.mne.gov.pt/...` (D7 page) → **HTTP 404**. The path may simply be stale, but as cited it
  does not resolve.
- `pra.gov.ph` → loads (200), but the homepage carries no SRRV deposit-tier table.

**Upgrade, same day:** a browser-automation lane, unlike `WebFetch`, can execute JavaScript and
carry session state, and it reached all four of those pages directly. `www.mm2h.gov.my`'s 403 to
`WebFetch` was not a dead source — it is a live government site (Ministry of Tourism, Arts and
Culture) that simply blocks the fetch tool; its five category pages (`/category/overview`,
`/platinum`, `/gold`, `/silver`, `/sez`) all loaded, each carrying a full financial-requirements
table and each footer-stamped "Last Update: 10/02/2026". `aima.gov.pt/en/immigration/aria-golden-
visa`'s TLS error turned out to describe a page that doesn't exist at all — AIMA's own site search
for "golden visa" returns "0 Search results" (screenshotted), and direct probes of both a
golden-visa-shaped and a D7-shaped URL path both return "Page not found." So the TLS error was
incidental; the substantive finding is that **this review found no AIMA Golden Visa or D7 content
through its search or the paths tested** — the primary source used for both programmes is the
official gazette, `diariodarepublica.pt`, which the browser lane reached directly: the consolidated text of
Lei n.º 23/2007 (Art. 3.º governing Golden Visa investment routes, Art. 52.º governing the general
subsistence-means requirement that D7 inherits), Portaria n.º 1563/2007 (the subsistence-means
formula), and Decreto-Lei n.º 29-A/2026 (whose recital states the 2026 RMMG figure). `pra.gov.ph`'s
homepage genuinely carries no tier table — but `pra.gov.ph/SRRVisa`, a different path the original
sheet didn't cite, does, and it loaded live with the Philippine clock rendering the capture moment.

The sheet's financial-figure claims for Malaysia, Portugal (both Golden Visa and D7), and SRRV
Classic in the Philippines are now **primary-confirmed** against a government page or the gazette
(Axis 5, below)
— not merely corroborated by secondary consensus. The sheet's own "Confidence, Staleness & Verification Limits"
section states flatly that "Federal 2024 tier metrics verified via MOTAC and Immigration
Department circulars" and "AIMA procedures verified via official Portuguese legislation" — the
first grading pass called that a stronger claim than it could reproduce; this pass reproduces it,
though via `mm2h.gov.my` rather than the MOTAC checklist page, and via the gazette rather than
AIMA. The financial figures upgraded below are retagged with the now-primary verification tier.

One outright error surfaced during source-checking (see Axis 5, claim #5): the "Where the
Alternatives Beat Indonesia" section attributes a 17% flat personal-income-tax rate to the
Thailand LTR programme generally, when in fact that rate is exclusive to the *Highly-Skilled
Professional* category — the Wealthy Pensioner/Wealthy Global Citizen categories this sheet
actually compares get foreign-source-income tax **exemption**, a different benefit. This is a
confident, specific, and wrong citation — the exact failure mode the mandate asked me to hunt for.

### Axis 2 — Recency: does it reflect current rules or a superseded regime?

Largely current, with one gap the sheet itself does not flag clearly enough:

- **Malaysia MM2H**: the sheet correctly describes the mid-2024 restructure (mandatory property
  purchase for Silver/Gold/Platinum — a real, material change from the pre-2024 single-tier
  scheme). ✅ **PRIMARY-CONFIRMED, current as of the source's own stamp.** `mm2h.gov.my`'s five
  category pages, fetched directly 2026-08-24, are each footer-stamped "Last Update: 10/02/2026" —
  a page-level freshness date this session can cite, not merely infer. The USD-denominated deposit
  figures (Platinum 1,000,000 / Gold 500,000 / Silver 150,000 / SEZ-SFZ 65,000 age 21–49 / SEZ-SFZ
  32,000 age 50+) and RM-denominated compulsory property purchase (2,000,000 / 1,000,000 / 600,000
  / SEZ-priced-as-set) sit on the same official table — resolving the confusion the first pass
  flagged: the RM-denominated *deposit* figures a first search pass found circulating in aggregator
  guides describe either the pre-2024 legacy scheme or the unrelated Sarawak programme, not the
  current federal one, which the government's own page states plainly.
- **Portugal Golden Visa**: sheet correctly reflects Lei 56/2023 (Mais Habitação, effective 7
  October 2023) eliminating the real-estate and capital-transfer routes — this is the single
  biggest and most-reported change to any of these four programmes, and the sheet gets it right,
  including the grandfathering caveat being *absent* from its own text (worth adding before
  publication).
- **Philippines SRRV**: the sheet's narrative ("late 2024/2025, PRA restored eligibility for ages
  40–49 at elevated deposit rates") undersells what actually happened. My search of ACCRALAW and
  Chambers and Partners publications (law-firm sources, not blogs) report that the change was
  **larger and more recent than the sheet implies**: revised guidelines **effective 1 September
  2025** (a) standardised the minimum age at 40 for *all* applicants regardless of pension status
  (the sheet says this but buries the "effective Sept 2025" date), and (b) reportedly discontinued
  the SRRV Smile sub-category entirely (the old USD 10,000–20,000 entry tier for ages 35–49).
  The sheet never mentions SRRV Smile existed or was killed — it simply never lists it, which
  produces a correct end-state table by omission rather than by explaining the change. For a page
  aimed at readers who may have seen older SRRV marketing quoting "USD 10,000," this is a recency gap
  worth closing. **Upgrade:** `pra.gov.ph/SRRVisa`, fetched live 2026-08-24 (the page renders the
  Philippine clock at capture time), states plainly "Principal/s: 40 years old and above" as a
  blanket qualification and lists **exactly three** options — SRRV Classic, SRRV Courtesy (Foreign
  Nationals), SRRV Courtesy (Former Filipinos) — with no SRRV Smile row anywhere. This
  primary-confirms the age-40 standardisation and the absence of SRRV Smile from today's official
  offering. It does **not** confirm the discontinuation *event* itself — PRA's own Advisories page
  (also fetched live, five entries spanning 2024-11-12 to 2026-03-05) carries no announcement of
  Smile's retirement — so "no longer on the authoritative tier page today" is as far as this
  session can honestly go; see §2 for why the stronger claim stays out.
- **Thailand LTR**: launched September 2022, no material restructure since — the sheet's "Active"
  framing is fine. 🔴 **UNVERIFIED**
- **Indonesia E33**: not re-graded per mandate (SSOT already governs it) — but for context, the
  sheet's age-55-vs-60 ambiguity note matches `e33-fact-registry.json`'s
  `age_55_59_ambiguity_e33e` entry exactly, so this column is at least internally consistent with
  the repo's own ground truth.

### Axis 3 — The custody field

This is the underlying generator sheet's strongest section, and it does not evade the question.
Every one of the five programme families gets an explicit "Custody & Liquidity of Funds"
paragraph, and its summary table has a dedicated "Capital Custody" row and a separate "Capital
Locked?" row — this is exactly the load-bearing comparison the feature is built to answer.

Content check: it claims **every** competitor deposit/investment sits in the applicant's own name
(Malaysia FD, Sarawak FD, Thailand's Thai-registered investments, Portugal's fund units, Philippines'
Special Time Deposit) — none are claimed to be pooled, held by an agent, or held by the state. I
was not able to independently primary-source-verify the "own name" wording for Malaysia, Thailand,
Portugal, or the Philippines this session (time-boxed to the five WebFetch/WebSearch passes above,
none of which specifically targeted custody wording) — 🔴 **UNVERIFIED as a literal claim**, though
it is consistent with how fixed-deposit and fund-unit products conventionally work (an account or
unit registration is opened in the account-holder's name almost by definition), so I am not
flagging it as *suspect*, only as *not independently confirmed*.

The place the sheet's custody framing needed a caveat it didn't carry: **Malaysia's
50%-withdrawal clause** was stated as fact ("up to 50% of the principal may be withdrawn after 1
year strictly for approved property acquisition, medical expenses, or children's education")
without a source tag, and the first pass could not verify it. **Upgrade: ✅ PRIMARY-CONFIRMED**,
`mm2h.gov.my` (all five category pages, fetched live 2026-08-24) — the sheet's date detail was
close but not exact. The government page states: "Maximum withdrawal of 50% is allowed on the
principal FD value **after the approval as MM2H participant has been obtained**" (not "after 1
year") for four purposes — "purchasing a residence, education, medical and tourism activities in
Malaysia." Tourism is a fourth approved purpose the sheet omitted. This also surfaces a structural
fact the first pass didn't have: **Malaysia's deposit is not just partially withdrawable, it sits
alongside a *compulsory* property purchase** (Platinum RM 2M / Gold RM 1M / Silver RM 600k,
unsellable for 10 years) that the applicant must make *in addition to* the fixed deposit — a real
structural difference from Indonesia's E33, where the full deposit stays in the applicant's own
name with no mandatory secondary purchase.

**Indonesia's own claim — 100% locked, zero partial-withdrawal exception, for the full visa term —
is the sharpest structural contrast the comparator has**, and it survives this review: nothing in
the four competitor descriptions claims a comparably absolute lock. That contrast is real and
safe to lead with on the public page.

### Axis 4 — Fairness ("Where the Alternatives Beat Indonesia")

The underlying generator sheet's section exists, is five numbered points, and is substantive —
not a token paragraph. It
names specific programmes for specific advantages (Portugal for citizenship/mobility, Portugal+
Thailand for zero lockup, Philippines/Thailand/Malaysia for lifetime permanence vs. Indonesia's
hard cap, Portugal/Thailand/Philippines for work rights, Philippines for lower entry capital) and
backs each with a regulation citation (Pasal 113 for the Indonesian cap) or a specific number. This
is a real attempt at "a sceptical reader should not be able to catch this flattering its author."

The one defect found under scrutiny is factual, not structural: point 4's "17% personal income tax
caps" claim for Thailand LTR is wrong as applied to the Wealthy Pensioner category — see Axis 1
and Axis 5 claim #5. I have corrected this in §3 below rather than dropping the point, because the
underlying point (Thailand LTR gives real domestic work/tax benefits Indonesia does not) is true;
only the specific mechanism named was wrong.

### Axis 5 — Hallucination sweep: what I fetched, and what the sources actually said

Five spot-checks (exceeds the four-minimum), plus one further check triggered by a suspicious
claim found during the sweep (Thailand's 17% tax figure).

1. **Thailand LTR, Wealthy Pensioner passive-income floor.** Sheet claims USD 80,000/year (or
   USD 40,000–80,000/year + USD 250,000 Thai investment). Fetched `https://ltr.boi.go.th/`
   directly: confirms **USD 80,000/year**, and the USD 40,000–80,000/year + USD 250,000-investment
   alternative, verbatim. Also confirms the "10 years total (5+5 renewable)" validity structure
   and the health-insurance-or-bank-deposit alternative (USD 50,000 minimum insurance coverage /
   USD 100,000 bank-account alternative). The sheet says "USD 100,000 in escrow," while the source
   described here says only bank account; escrow or lockup is therefore not confirmed. **✅
   PRIMARY-CONFIRMED for the thresholds; custody condition not confirmed.**

2. **Malaysia MM2H tier deposits (Silver USD 150,000 / Gold USD 500,000 / Platinum USD 1,000,000,
   with RM 600k / RM 1,000k / RM 2,000k mandatory property).** Both government URLs the sheet
   cites failed to serve this content to `WebFetch` (403 / no-content page — see Axis 1). **Upgrade:
   ✅ PRIMARY-CONFIRMED.** `mm2h.gov.my/category/{platinum,gold,silver}`, browser-fetched live
   2026-08-24, footer-stamped "Last Update: 10/02/2026." Every figure matches the sheet exactly,
   plus detail the sheet didn't carry: minimum age 25 for all three tiers (a fourth and fifth tier
   exist too — SEZ/SFZ, age 50+ USD 32,000 / age 21–49 USD 65,000, tied to Forest City, Johor
   property — outside the sheet's three-tier framing but on the same official table); MM2H term
   20/15/5 years respectively, renewable; a one-off participating fee (RM 200,000 / 3,000 / 1,000)
   separate from the deposit and property purchase; a 90-days-per-year cumulative presence
   requirement for ages 25–49 (waived entirely at 50+); and the purchased residence cannot be sold
   for 10 years. Source: `mm2h.gov.my`, Ministry of Tourism, Arts and Culture, captured 2026-08-24.

3. **Portugal Golden Visa — real-estate route eliminated 7 October 2023 (Lei 56/2023), remaining
   routes capped at €500,000 (funds/research) and €250,000 (cultural heritage).**
   Multiple independent legal/relocation sources (Bright!Tax, Bitizenship, Connaught Law, Belzuz —
   the last three specifically wrote "law 56/2023 real estate eliminated 2026" pieces) agree on
   the date, the mechanism (Mais Habitação), and the surviving routes and thresholds, matching the
   sheet's figures exactly. AIMA's own page could not be fetched (TLS error) — and, per the Axis 1
   upgrade, this review found no AIMA page through the search and paths tested. **Upgrade: ✅ PRIMARY-CONFIRMED**
   against the actual primary source, the gazette itself: `diariodarepublica.pt`'s consolidated
   text of Lei n.º 23/2007, Art. 3.º(1)(d), browser-fetched live 2026-08-24. Three of the original
   five real-estate-linked subalíneas — i), iii), iv) — are marked "(Revogada.)" in the consolidated
   text. N.º 5 of the same article states, verbatim: *"As atividades de investimento previstas nas
   subalíneas referidas no número anterior não se podem destinar, direta ou indiretamente, ao
   investimento imobiliário"* ("...may not be directed, directly or indirectly, at real-estate
   investment") — the legislative text of the ban, not a paraphrase. The surviving routes, all
   confirmed on the same page: ii) creation of ≥10 jobs; v) ≥€500,000 to scientific research; vi)
   ≥€250,000 to artistic production / cultural-heritage support; vii) ≥€500,000 into non-real-estate
   fund units (≥5-year maturity, ≥60% invested in Portuguese-domiciled companies); viii) ≥€500,000
   company incorporation with 5 permanent jobs (or capital reinforcement creating 5 jobs / retaining
   10, min. 5 permanent, over a 3-year minimum). Consolidated text current to Art. 3.º's last
   amendment, Lei n.º 9/2025 (2025-02-13) — one amendment more recent than the sheet's Lei 56/2023
   citation, though it did not change the real-estate ban.

4. **Portugal D7 — 2026 minimum-wage-linked income floor €920/month.** Multiple sources (including
   the D7Visa specialist site and immigration-law aggregators) independently confirm €920/month as
   the 2026 figure, up from €870/month in 2025 — consistent with Portugal's annual statutory
   minimum-wage increase pattern. The sheet's number is correct, but **the sheet frames it as a
   published D7 threshold, and that framing is wrong** — this is the most important correction in
   the batch. **Upgrade: ✅ PRIMARY-CONFIRMED, with a structural correction.** `diariodarepublica.pt`,
   browser-fetched live 2026-08-24 (Lei n.º 23/2007 Art. 52.º(1)(d), Portaria n.º 1563/2007, and
   Decreto-Lei n.º 29-A/2026, all still "Em vigor"): **there is no fixed euro figure for D7 anywhere
   in the law.** Art. 52.º(1)(d) requires only that the applicant "disponha de meios de
   subsistência, definidos por portaria" — the specific figure is delegated to Portaria 1563/2007
   (11 December 2007, still in force, unrepealed), whose Art. 2.º(2) sets a *formula*, not an
   amount: 100% of the RMMG (statutory minimum wage) for the principal applicant, 50% per
   additional adult, 30% per child under 18 or dependent. The RMMG itself is set annually by a
   separate instrument; for 2026 it is €920.00/month, confirmed via the recital of Decreto-Lei n.º
   29-A/2026 (30 January 2026, Diário da República n.º 21/2026, Suplemento), which states verbatim
   that the government "determinou... o aumento da Remuneração Mínima Mensal Garantida (RMMG) para
   o setor privado, no valor de 920,00 €, com efeitos a partir de 1 de janeiro de 2026" — citing
   Decreto-Lei n.º 139/2025 (29 December 2025) as the instrument that actually fixed the figure.
   So "€920/month" is arithmetically correct (100% × €920 RMMG = €920 for a single applicant) but
   is a **derived** figure three steps removed from a fixed legal number, not something a reader
   can cite as "the D7 threshold is €X in the law" — it changes every year the RMMG changes, by a
   formula, not a re-legislated amount.

5. **Thailand LTR "17% personal income tax caps" (in the "Where the Alternatives Beat Indonesia"
   section, point 4).** This is the one claim that did **not** survive the check. I searched
   specifically for which LTR category qualifies for the 17% flat rate: **it is the Highly-Skilled
   Professional category only**, taxing employment income in BOI-targeted industries. The
   **Wealthy Pensioner** and **Wealthy Global Citizen** categories — the ones this entire sheet
   uses for the HNW/retiree comparison — instead get a **full exemption from Thai tax on
   foreign-sourced income**, a different tax treatment from the 17% rate on Thai employment
   income. The sheet's sentence conflates two different LTR sub-categories and states the
   wrong mechanism as if it applied to the category under comparison. **❌ CORRECTED** in §3.

6. **Philippines SRRV age-40 standardisation and the SRRV Classic deposit-tier table (40–49 AND
   50+; pension-income floor), plus a Courtesy-table capture.** ACCRALAW and Chambers and Partners
   (regional law-firm/legal-publisher sources, materially higher quality than a relocation blog)
   confirmed age standardised to 40 for
   all applicants effective 1 September 2025, and the 40–49 deposit figures. **Upgrade: ✅
   PRIMARY-CONFIRMED for SRRV Classic, including the 50+ tier and the income floor the first pass
   could not reach; not confirmed for the Courtesy table.** `pra.gov.ph/SRRVisa`, browser-fetched
   live 2026-08-24 (the page renders "Monday August 24, 2026" via a live Philippine clock at
   capture time, unlike the homepage the first pass
   loaded): **SRRV Classic** — Pensioner USD 15,000 (age 50+) / USD 25,000 (age 40–49); Non-Pensioner
   USD 30,000 (50+) / USD 50,000 (40–49); pensioner applicants additionally require proof of a
   lifetime pension of ≥USD 800/month (single) or ≥USD 1,000/month (with dependents). **SRRV
   Courtesy (Foreign Nationals)** — for retired diplomats, accredited international-organisation
   officers, retired military from bilateral-relation countries, and recognised high achievers:
   USD 1,500 (50+) / Pensioner USD 3,000, Non-Pensioner USD 6,000 (40–49) — the page's own table
   markup is garbled at this row (column labels and values don't align cleanly in the rendered
   text), so treat these Courtesy figures as directionally right but re-screenshot before quoting
   them client-facing. **SRRV Courtesy (Former Filipinos)** — USD 1,500 (50+) / USD 3,000 (40–49).
   The page lists **exactly these three options** and no fourth — no SRRV Smile row anywhere.

---

## 2. What is safe to publish

**Upgraded 2026-08-24, same day as the first grading pass.** A browser-automation lane reached the
government/gazette pages `WebFetch` could not, and the picture below supersedes §2 as it stood
after the first pass. Four rows that were previously gated on a working primary-source fetch —
Malaysia's full tier table, Portugal's Golden Visa legal basis, Portugal's D7 threshold mechanism,
and the Philippines' 50+ SRRV Classic tier — are now primary-confirmed. Three things stay gated,
and stay gated for a structural reason, not a fetch failure: see "Still cannot publish" below.

### Safe to publish now

- **Indonesia E33's 100% capital lock, own-name custody, and hard 6/10-year cumulative cap** — SSOT
  facts, unchanged by this review, and the sharpest true differentiator against every competitor.
- **Thailand LTR Wealthy Pensioner: USD 80,000/year passive income (or USD
  40,000–80,000/year + USD 250,000 investment), 5+5 = 10-year validity.** The income test itself
  creates no investment requirement; the separate insurance-or-bank-account condition still
  applies. Primary-source confirmed, `ltr.boi.go.th`.
- **Malaysia MM2H — the full five-tier table, primary-confirmed against `mm2h.gov.my`** (each page
  footer-stamped "Last Update: 10/02/2026"): Platinum (USD 1,000,000 deposit, 20-year renewable,
  RM 2,000,000 compulsory property), Gold (USD 500,000 / 15 years / RM 1,000,000), Silver
  (USD 150,000 / 5 years / RM 600,000), and two SEZ/SFZ tiers tied to Forest City, Johor
  (age 21–49: USD 65,000 deposit / age 50+: USD 32,000, both 10-year renewable). All five require
  90 cumulative days/year in Malaysia for applicants aged 25–49 (waived at 50+), cap withdrawal at
  50% of the deposit — and only after MM2H approval, for property/medical/education/tourism — and
  the purchased property cannot be sold for 10 years. This is a genuine structural contrast worth
  publishing explicitly: **Malaysia requires capital split across a partly-withdrawable deposit
  plus a compulsory, separately-owned property purchase; Indonesia's E33 requires only the one
  wholly-locked, wholly-owned deposit.** Neither structure is objectively better — Malaysia's
  buyer ends up owning real property, Indonesia's applicant keeps 100% liquidity-free but as cash —
  but the page should state the difference, not flatten it.
- **Portugal Golden Visa: real-estate route permanently eliminated since 7 October 2023 (Lei
  56/2023); current routes are job creation (≥10 posts), scientific research (€500,000), cultural
  heritage (€250,000), non-real-estate fund units (€500,000), and company incorporation with jobs
  (€500,000 + 5 permanent posts).** Primary-confirmed against the actual legal text —
  `diariodarepublica.pt`, Lei n.º 23/2007 Art. 3.º(1)(d), consolidated to its last relevant
  amendment (Lei n.º 9/2025, 2025-02-13) — including the statutory ban's own wording (Art. 3.º n.º
  5: investment routes "não se podem destinar, direta ou indiretamente, ao investimento
  imobiliário"). Cite the gazette; this review did not locate an AIMA page for this content (see
  below).
- **Portugal D7: zero capital lockup, full domestic work rights, and an income floor of ~€920/month
  for a single applicant** — but publish it as a **formula**, not a fixed figure: 100% of the RMMG
  (statutory minimum wage) for the principal, +50% per additional adult, +30% per dependent child,
  per Portaria n.º 1563/2007 Art. 2.º(2) (still in force), with the RMMG itself set annually
  (€920.00/month for 2026, confirmed by the recital of Decreto-Lei n.º 29-A/2026, which cites
  Decreto-Lei n.º 139/2025 as the instrument setting the figure). A page that states "€920/month"
  without the formula will read as wrong the next time the RMMG changes; a page that states the
  formula plus "€920/month for 2026" is accurate and durable. Primary-confirmed against the gazette.
- **The "Where the Alternatives Beat Indonesia" section, minus point 4's tax-rate sentence**, which
  must be rewritten to say Thailand LTR's Wealthy Pensioner/Wealthy Global Citizen categories get
  **exemption from tax on foreign-sourced income** (not a "17% cap") before this page goes live —
  see §3 for the corrected wording. Now **strengthened** with a second, opposite-direction point:
  Portugal D7's ~€920/month income requirement and the Philippines SRRV pensioner tier's
  USD 15,000 deposit are dramatically *below* Indonesia's combined USD 50,000 deposit + USD
  3,000/month senior-income requirement — publish both the "alternatives beat Indonesia" cases
  (mobility, work rights, zero/partial lockup, lower entry capital in some programmes) and the
  places Indonesia's structure is the outlier the other direction (Malaysia's compulsory property
  purchase; the income-threshold gap against Portugal D7 and the entry-deposit gap against the
  Philippines Classic pensioner tier) —
  see the strengthened analysis below.
- **The core "Capital Locked?" comparison framing** — the structural argument (Indonesia locks
  100% with no mandatory secondary purchase; Malaysia offers partial withdrawal but requires a
  compulsory separate property purchase; Thailand and Portugal offer no lockup for the routes
  described) is sound. The broader literal claim that every competitor asset is held in the
  applicant's own name remains 🔴 **UNVERIFIED** under Axis 3 and must not be presented as verified.
- **Philippines SRRV Classic — the full deposit-tier table**, primary-confirmed against
  `pra.gov.ph/SRRVisa` fetched live: Pensioner USD 15,000 age 50+ / USD 25,000 age 40–49;
  Non-Pensioner USD 30,000 / USD 50,000; pensioner applicants also need a lifetime pension of
  ≥USD 800/month single or ≥USD 1,000/month with dependents. Age
  standardised to 40+ for all principal applicants. This is the sharpest low-end contrast against
  Indonesia in the entire comparator: Philippines' pensioner-with-pension entry point (USD 15,000 +
  a modest monthly pension) sits at exactly **30% of Indonesia E33E's USD 50,000 deposit alone**,
  before Indonesia's separate USD 3,000/month senior-income requirement is even added.

### What the checked AIMA paths showed

- **No AIMA Golden Visa or D7 page was located by the checks described here.** AIMA's own site
  search returns "0 Search results" for "golden visa"
  (screenshotted, 2026-08-24), and direct URL probes for both a golden-visa-shaped and a
  D7-shaped path return "Page not found." The primary source used above is the official gazette,
  `diariodarepublica.pt`; the finite checks made here do not prove that AIMA publishes nothing
  anywhere on either programme.

### Still cannot publish as settled fact

- **SRRV Smile's discontinuation is an inference from absence, not a government statement**, and
  should ship labelled that way if it ships at all — e.g. "Smile no longer appears on PRA's
  authoritative tier page as of 2026-08-24" is honest; "SRRV Smile was discontinued [date]" is a
  claim this research cannot source. No PRA announcement exists on the Advisories page (five
  entries, 2024-11-12 through 2026-03-05) or anywhere else checked this session.
- **The SRRV Courtesy (Foreign Nationals) deposit table's markup was garbled** on PRA's live page —
  the figures above are directionally captured but the column/value alignment in the rendered text
  is not clean. Re-screenshot and re-transcribe before quoting the Courtesy row anywhere
  client-facing; this caveat carries forward unchanged from the first pass.
- **The Malaysia "no naturalisation pathway despite 2024 policy ambiguity" claim** in the original
  sheet is unrelated to anything checked this session (visa mechanics, not citizenship policy) and
  remains unverified — do not publish it without a dedicated check.

**Bottom line for the feature team:** the principal entry thresholds cleared in this review —
Indonesia's SSOT, Thailand's, Malaysia's full five-tier table, Portugal's Golden Visa legal basis
and D7 formula, and the Philippines' SRRV Classic table — are primary-source-confirmed. What
remains gated is named: SRRV Smile's discontinuation stays inference-labelled, the Courtesy row
needs a cleaner re-capture, and the Malaysia naturalisation claim is simply out of scope for what
was checked.

---

## 3. Corrected excerpt — "Where the Alternatives Beat Indonesia," point 4

Original (do not use): *"Domestic Work and Remote Employment Rights (Portugal, Thailand LTR,
Philippines Beat Indonesia): Indonesia E33 strictly bans the holder from earning domestic income.
Portugal permits open employment and business establishment; Thailand LTR grants a streamlined
Digital Work Permit and 17% personal income tax caps; the Philippines permits domestic employment
under DOLE Alien Employment Permits."*

Corrected: Indonesia's E33 strictly bans domestic income. Portugal (D7 and Golden Visa) permits
open employment and business establishment. Thailand's LTR grants Wealthy Pensioner and Wealthy
Global Citizen holders a Digital Work Permit route via the Board of Investment's One-Stop Service
Center, and — separately — an exemption from Thai tax on foreign-sourced income (the 17% flat
personal-income-tax rate is a distinct benefit limited to the LTR's Highly-Skilled Professional
category, not the pensioner/wealthy-citizen categories this comparison uses). The Philippines
permits domestic employment for SRRV holders who obtain a DOLE Alien Employment Permit.

---

## 4. Notes for the country-comparator feature build

- **Upgraded 2026-08-24**: most cells that were 🟡/🔴 after the first pass are now ✅
  PRIMARY-CONFIRMED (Axis 5 items 2/3/4, the SRRV Classic portion of item 6, and the Axis 3
  Malaysia withdrawal clause) — the build blocker list has shrunk to three named items: SRRV
  Smile's discontinuation (ship inference-
  labelled, not as fact), the SRRV Courtesy deposit row (re-screenshot before quoting), and the
  Malaysia naturalisation-pathway claim (out of scope, don't publish). This list is not exhaustive;
  see the adversarial review for the additional open blockers.
- Treat these three named items as existing cell-level blockers, and resolve the additional open
  blockers in the adversarial review before publication.
- The custody/lock comparison (Axis 3) is the page's actual differentiator; lead with it, and now
  state Malaysia's compulsory-property-purchase structure alongside it explicitly rather than
  folding it into a generic "partial liquidity" label.
- Every cell on the comparator should carry its source URL and capture/last-updated date inline (or
  in a footnote) — for a residency programme, an undated figure is unusable, and this pass found
  that MOTAC's own pages carry a genuine "Last Update" stamp worth surfacing to the reader.
- Do not carry over the sheet's "Confidence, Staleness & Verification Limits" section as-is — it
  overstates primary-source verification for Malaysia, Portugal, and the Philippines relative to
  what the first grading pass could reproduce, even though this upgrade pass has since closed most
  of that gap independently. Use this document's tagging instead, including its citations.

## Adversarial review

**Verdict: NOT PUBLISHABLE.** Cross-family Codex review dated 2026-08-24, conducted without web
access and without new sources. The Indonesia E33 column was neither reopened nor modified; the
attack concerns only coherence, arithmetic, evidence quality, and the correctness of the
competitor comparison.

1. **Internal consistency — does not hold up as a standalone document.** This file is a grading
   memo, not the comparator it describes: the “Capital Custody / Capital Locked?” table is only
   referenced as part of the underlying generator sheet (L161–164), and the same applies to the
   complete five-point “Where the Alternatives Beat Indonesia” section (L196–204). Since they are
   not present here, it is not possible to verify the table-to-detail consistency required for
   publication. Furthermore, the captures supporting the ✅ upgrades are declared in a session
   scratchpad (L39–44), but neither that scratchpad nor `country-comparator-facts.md` is present in
   the worktree: the evidence file cannot be reproduced from the document. I corrected the
   resolvable internal contradictions: SRRV Courtesy is no longer simultaneously “safe” and “not
   publishable”; the count of items still gated is three, not two; competitors’ “own name” custody
   remains explicitly 🔴 and separate from the lock comparison (L375–379).

2. **Orphan figures — findings remain open.** The main MM2H, Golden Visa, D7, and SRRV Classic
   thresholds have currency, nature, source, and date in the text. What remains, however, is: the
   old SRRV Smile USD 10.000–20.000 (L133–142), which lacks a specific source with a publication
   date and is described only as an “entry tier”; the historical D7 comparison of €870/month in
   2025 (L261–264), attributed to “multiple sources” without a URL or specific date; the LTR
   requirement of USD 100.000 in an account (L217–224), whose threshold and source are given but
   not its maintenance duration or restriction, so it cannot be classified as free or locked
   capital; the 17% tax rate and Thai foreign-income exemption (L284–292, L430–435), without an
   identified source and date for the tax claim; the SRRV Courtesy figures (L305–311), for which
   the category-to-value mapping is expressly declared illegible.

3. **Arithmetic — holds up.** With the 2026 RMMG at €920, the formula at L271–279 produces
   €920/month for the applicant, €460/month for each additional adult, and €276/month for each
   child; therefore applicant + adult = €1.380/month and applicant + child = €1.196/month. The
   only published derived value, €920/month, is correct and is now stated as derived, not as a D7
   threshold fixed in euros. USD 15.000 / USD 50.000 = exactly 30% (L380–387), and 5+5 = 10 years
   (L328–331), also hold. I removed €200.000 from the Golden Visa summary because the quoted
   primary passage supported €250.000 but did not spell out either the formula or the condition
   that would have produced €200.000.

4. **Fairness of the comparison — the facts are there; the section is not.** The text clearly says
   that D7 requires about €920/month versus USD 3.000/month for the Indonesian senior and that
   SRRV Classic 50+ requires USD 15.000 versus USD 50.000 for E33E (L363–369 and L380–387). These
   two net disadvantages are not softened, and the numbers are correct. They are, however, buried
   inside “Safe to publish now”, while Axis 4 comments on an external section that is not included
   (L196–210). For a public document, this fails the substantive requirement: a true standalone
   section is needed to present those two points together with the other advantages of the
   alternatives. Placement and rewriting remain an open editorial decision, so I did not impose
   them.

5. **Categories — largely hold up after the corrections.** MM2H distinguishes a partially
   withdrawable deposit, compulsory property purchase, and a one-time fee; LTR distinguishes an
   income test, alternative investment, and insurance/account requirement; the Golden Visa is
   treated as an investment and D7 as an income formula; SRRV separates deposit and pension. I
   replaced “entry-capital gap against Portugal D7” with “income-threshold gap”, and clarified that
   the LTR income test does not in itself create an investment but does not remove the separate
   insurance/account requirement (L328–331). The Thai tax advantage is now attributed to the
   correct category, but it remains not publishable until the specific source identified in point
   2 is provided.

6. **Unsupported claims — boundaries respected, support still insufficient.** There are no
   personal data, approval promises, yield projections, or advice on where to invest. I removed
   the judgment that one tax regime would be “more advantageous” for the pensioner and reduced the
   universal statements about AIMA to what the finite checks demonstrate (L389–396). The document
   still lacks identified sources for Portugal/LTR/Philippines work rights and the tax claims in
   the corrected excerpt (L430–436); “own name” custody for all competitors is acknowledged as 🔴
   unverified (L166–174). These claims cannot enter a decision page until they are cited claim by
   claim.

**Specific corrections applied:** added `adversarial_review: codex`; corrected the two Axis 5
references from claim #4 to #5; downgraded Thailand LTR “no restructuring” from 🟡 to 🔴; removed
the two “generally more valuable” judgments; made the LTR USD 40.000–80.000 range annual;
distinguished insurance coverage, bank account, and escrow; removed the unsupported Golden Visa
€200.000; narrowed the SRRV upgrade to Classic, leaving Courtesy gated; corrected “two” to
“three” blocks; made explicit that the RMMG €920 is indirectly confirmed by the recital of
Decreto-Lei 29-A/2026, which cites 139/2025; separated the income test from entry capital;
corrected E33 to E33E in the pensioner comparison and “roughly 30%” to “exactly 30%”; separated
verified lock from unverified custody; reduced the absolute statements about AIMA; clarified that
the table and five-point section belong to the underlying sheet, not to this file.

**Findings open for decision:** incorporate the actual table and the complete fairness section;
make the evidentiary captures available in the repo; decide whether to remove or document the
orphan figures; add specific sources for tax/work/custody; add the Portuguese grandfathering
caveat already flagged at L128–132; keep SRRV Courtesy, the SRRV Smile discontinuation date, and
the Malaysian naturalization claim excluded until resolved.

**Publication decision: no.** The document becomes publishable only after the open findings above
are closed; the main thresholds and arithmetic, by themselves, withstood the attack.
