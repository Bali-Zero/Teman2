---
date: 2026-08-24
domain: visa
client_case: Second Home Studio — country comparator feature (E33 vs. MM2H / LTR / D7-GV / SRRV)
sources:
  - https://ltr.boi.go.th/ (fetched live 2026-08-24, primary — confirmed)
  - https://www.motac.gov.my/en/mm2h (fetched live 2026-08-24, primary — page reachable, no financial figures on it)
  - https://www.mm2h.gov.my/ (fetched live 2026-08-24, primary — HTTP 403, unreachable)
  - https://aima.gov.pt/en/immigration/aria-golden-visa (fetch attempted 2026-08-24, primary — TLS certificate error, unreachable)
  - https://vistos.mne.gov.pt/... (fetch attempted 2026-08-24, primary — HTTP 404, wrong/stale path)
  - https://pra.gov.ph/ (fetched live 2026-08-24, primary — page reachable, no tier figures on homepage)
  - secondary/legal-aggregator consensus (Emerhub, Zagdim, Bratuca, Golden Visa Map, Bright!Tax, Bitizenship, Connaught Law, Belzuz, ACCRALAW, Chambers and Partners) — searched 2026-08-24, used only where primary fetch failed
  - research/secondhome/e33-fact-registry.json (E33 column SSOT — not re-verified, per mandate)
---

# Second Home Studio — Country Comparator: Graded Fact Sheet

**Grader:** Claude (Opus, this session). **Author:** Gemini 3.1 Pro (live web search), scratchpad
artifact `country-comparator-facts.md`, ~36 KB, dated 2026-08-24. This document is the graded,
demoted, and annotated output of that artifact — it is not a straight copy. Long verbatim passages
were not carried over; figures are restated with attribution and a verification tag.

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
Philippines). Result: **only one reached and confirmed the cited figures** —
Thailand's `ltr.boi.go.th`. The other four failed or lacked the content on this attempt:

- `www.mm2h.gov.my` → **HTTP 403 Forbidden**. `www.motac.gov.my/en/mm2h` loaded but is a checklist
  page with no financial figures — neither government URL the sheet cites actually surfaces the
  Silver/Gold/Platinum deposit numbers to a live fetch.
- `aima.gov.pt/en/immigration/aria-golden-visa` → TLS certificate error, unreachable.
- `vistos.mne.gov.pt/...` (D7 page) → **HTTP 404**. The path may simply be stale, but as cited it
  does not resolve.
- `pra.gov.ph` → loads (200), but the homepage carries no SRRV deposit-tier table.

This does not mean the sheet's Malaysia/Portugal/Philippines figures are *wrong* — cross-checking
against multiple independent secondary sources (relocation-law aggregators, and for the
Philippines two actual law-firm publications, ACCRALAW and Chambers and Partners) found the same
numbers repeated consistently. But the sheet's own "Confidence, Staleness & Verification Limits"
section states flatly that "Federal 2024 tier metrics verified via MOTAC and Immigration
Department circulars" and "AIMA procedures verified via official Portuguese legislation" — **that
is a stronger claim than I could reproduce**. The sheet presents primary-source confidence for
figures I could only corroborate secondarily. I have retagged every financial figure below with
the honest verification tier, not the sheet's claimed one.

One outright error surfaced during source-checking (see Axis 5, claim #4): the "Where the
Alternatives Beat Indonesia" section attributes a 17% flat personal-income-tax rate to the
Thailand LTR programme generally, when in fact that rate is exclusive to the *Highly-Skilled
Professional* category — the Wealthy Pensioner/Wealthy Global Citizen categories this sheet
actually compares get foreign-source-income tax **exemption**, a different (and, for most retiree
profiles, more valuable) benefit. This is a confident, specific, and wrong citation — the exact
failure mode the mandate asked me to hunt for.

### Axis 2 — Recency: does it reflect current rules or a superseded regime?

Largely current, with one gap the sheet itself does not flag clearly enough:

- **Malaysia MM2H**: the sheet correctly describes the mid-2024 restructure (mandatory property
  purchase for Silver/Gold/Platinum — a real, material change from the pre-2024 single-tier
  scheme). ✅ directionally current. One live risk not in the sheet: during my search pass,
  several 2025/2026-dated aggregator articles quoted a *different* set of numbers for the same
  tiers — RM-denominated (RM 500k/1M/5M) instead of USD-denominated (USD 150k/500k/1M) — before a
  separate source clarified the RM figures were either legacy pre-2024 numbers or a conflation
  with the unrelated Sarawak state programme. The sheet does not mention this confusion exists at
  all, which is itself a gap: a live public page should warn a reader who searches further that
  they may hit stale RM-denominated guides.
- **Portugal Golden Visa**: sheet correctly reflects Lei 56/2023 (Mais Habitação, effective 7
  October 2023) eliminating the real-estate and capital-transfer routes — this is the single
  biggest and most-reported change to any of these four programmes, and the sheet gets it right,
  including the grandfathering caveat being *absent* from its own text (worth adding — see §3
  below).
- **Philippines SRRV**: the sheet's narrative ("late 2024/2025, PRA restored eligibility for ages
  40–49 at elevated deposit rates") undersells what actually happened. My search of ACCRALAW and
  Chambers and Partners publications (law-firm sources, not blogs) found the change was **larger
  and more recent than the sheet implies**: PRA issued revised guidelines **effective 1 September
  2025** that (a) standardised the minimum age at 40 for *all* applicants regardless of pension
  status (the sheet says this but buries the "effective Sept 2025" date), and (b) **discontinued
  the SRRV Smile sub-category entirely** (the old USD 10,000–20,000 entry tier for ages 35–49).
  The sheet never mentions SRRV Smile existed or was killed — it simply never lists it, which
  produces a correct end-state table by omission rather than by explaining the change. For a page
  aimed at readers who may have seen older SRRV marketing quoting "$10,000," this is a recency gap
  worth closing.
- **Thailand LTR**: launched September 2022, no material restructure since — the sheet's "Active"
  framing is fine. 🟡
- **Indonesia E33**: not re-graded per mandate (SSOT already governs it) — but for context, the
  sheet's age-55-vs-60 ambiguity note matches `e33-fact-registry.json`'s
  `age_55_59_ambiguity_e33e` entry exactly, so this column is at least internally consistent with
  the repo's own ground truth.

### Axis 3 — The custody field

This is the sheet's strongest section, and it does not evade the question. Every one of the five
programme families gets an explicit "Custody & Liquidity of Funds" paragraph, and the summary
table has a dedicated "Capital Custody" row and a separate "Capital Locked?" row — this is exactly
the load-bearing comparison the feature is built to answer, and the sheet does not go vague on it
anywhere.

Content check: it claims **every** competitor deposit/investment sits in the applicant's own name
(Malaysia FD, Sarawak FD, Thailand's Thai-registered investments, Portugal's fund units, Philippines'
Special Time Deposit) — none are claimed to be pooled, held by an agent, or held by the state. I
was not able to independently primary-source-verify the "own name" wording for Malaysia, Thailand,
Portugal, or the Philippines this session (time-boxed to the five WebFetch/WebSearch passes above,
none of which specifically targeted custody wording) — 🔴 **UNVERIFIED as a literal claim**, though
it is consistent with how fixed-deposit and fund-unit products conventionally work (an account or
unit registration is opened in the account-holder's name almost by definition), so I am not
flagging it as *suspect*, only as *not independently confirmed*.

The one place the sheet's custody framing needs a caveat it doesn't carry: **Malaysia's and
Sarawak's 50%-withdrawable-after-1-year clause** is stated as fact ("up to 50% of the principal
may be withdrawn after 1 year strictly for approved property acquisition, medical expenses, or
children's education") without a source tag, and I did not verify it this session. 🔴 UNVERIFIED —
flagged inline in §3 below.

**Indonesia's own claim — 100% locked, zero partial-withdrawal exception, for the full visa term —
is the sharpest structural contrast the comparator has**, and it survives this review: nothing in
the four competitor descriptions claims a comparably absolute lock. That contrast is real and
safe to lead with on the public page.

### Axis 4 — Fairness ("Where the Alternatives Beat Indonesia")

The section exists, is five numbered points, and is substantive — not a token paragraph. It
names specific programmes for specific advantages (Portugal for citizenship/mobility, Portugal+
Thailand for zero lockup, Philippines/Thailand/Malaysia for lifetime permanence vs. Indonesia's
hard cap, Portugal/Thailand/Philippines for work rights, Philippines for lower entry capital) and
backs each with a regulation citation (Pasal 113 for the Indonesian cap) or a specific number. This
is a real attempt at "a sceptical reader should not be able to catch this flattering its author."

The one defect found under scrutiny is factual, not structural: point 4's "17% personal income tax
caps" claim for Thailand LTR is wrong as applied to the Wealthy Pensioner category — see Axis 1
and Axis 5 claim #4. I have corrected this in §3 below rather than dropping the point, because the
underlying point (Thailand LTR gives real domestic work/tax benefits Indonesia does not) is true;
only the specific mechanism named was wrong.

### Axis 5 — Hallucination sweep: what I fetched, and what the sources actually said

Five spot-checks (exceeds the four-minimum), plus one further check triggered by a suspicious
claim found during the sweep (Thailand's 17% tax figure).

1. **Thailand LTR, Wealthy Pensioner passive-income floor.** Sheet claims USD 80,000/year (or
   USD 40,000–80,000/year + USD 250,000 Thai investment). Fetched `https://ltr.boi.go.th/`
   directly: confirms **USD 80,000/year**, and the USD 40k–80k + USD 250,000-investment
   alternative, verbatim. Also confirms the "10 years total (5+5 renewable)" validity structure
   and the health-insurance-or-bank-deposit alternative (USD 50,000 insurance / USD 100,000
   deposit — sheet says "USD 100,000 in escrow," source just says bank account; immaterial
   wording difference). **✅ PRIMARY-CONFIRMED, accurate.**

2. **Malaysia MM2H tier deposits (Silver USD 150,000 / Gold USD 500,000 / Platinum USD 1,000,000,
   with RM 600k / RM 1,000k / RM 2,000k mandatory property).** Both government URLs the sheet
   cites failed to serve this content live (403 / no-content page — see Axis 1). A first
   secondary-source search surfaced a *conflicting* set of numbers (RM-denominated tiers,
   RM 500k/1M/5M) from several relocation-agency blogs; a second, more targeted search resolved
   the conflict — the USD-denominated figures the sheet uses are the current federal scheme, and
   the RM figures either describe the pre-2024 legacy programme or conflate it with the unrelated
   Sarawak state scheme. **🟡 SECONDARY-CONSENSUS, plausible and probably accurate, but this
   session could not pin it to a government source, and I personally watched two different
   secondary sources disagree with each other before a third resolved it** — a caution the sheet's
   confident "verified via MOTAC... circulars" framing does not carry.

3. **Portugal Golden Visa — real-estate route eliminated 7 October 2023 (Lei 56/2023), remaining
   routes capped at €500,000 (funds/research) and €250,000/€200,000 (cultural heritage).**
   Multiple independent legal/relocation sources (Bright!Tax, Bitizenship, Connaught Law, Belzuz —
   the last three specifically wrote "law 56/2023 real estate eliminated 2026" pieces) agree on
   the date, the mechanism (Mais Habitação), and the surviving routes and thresholds, matching the
   sheet's figures exactly. AIMA's own page could not be fetched (TLS error). **🟡
   SECONDARY-CONSENSUS, high confidence — multiple independent legal sources converge on identical
   figures** — but still not primary-confirmed by me this session.

4. **Portugal D7 — 2026 minimum-wage-linked income floor €920/month.** Multiple sources (including
   the D7Visa specialist site and immigration-law aggregators) independently confirm €920/month as
   the 2026 figure, up from €870/month in 2025 — consistent with Portugal's annual statutory
   minimum-wage increase pattern. The sheet's number is correct. **🟡 SECONDARY-CONSENSUS** (the
   official MNE visa page 404'd for me; I did not reach Diário da República directly this
   session — the sheet cites it but I could not independently confirm the legislative-text
   citation itself, only the resulting number via aggregators).

5. **Thailand LTR "17% personal income tax caps" (in the "Where the Alternatives Beat Indonesia"
   section, point 4).** This is the one claim that did **not** survive the check. I searched
   specifically for which LTR category qualifies for the 17% flat rate: **it is the Highly-Skilled
   Professional category only**, taxing employment income in BOI-targeted industries. The
   **Wealthy Pensioner** and **Wealthy Global Citizen** categories — the ones this entire sheet
   uses for the HNW/retiree comparison — instead get a **full exemption from Thai tax on
   foreign-sourced income**, a different and, for a retiree living on foreign pension/investment
   income, generally more valuable benefit than a 17% rate on Thai employment income they likely
   don't have. The sheet's sentence conflates two different LTR sub-categories and states the
   wrong mechanism as if it applied to the category under comparison. **❌ CORRECTED** in §3.

6. **Philippines SRRV age-40 standardisation and 40–49 deposit tiers (USD 25,000 w/ pension, USD
   50,000 without).** ACCRALAW and Chambers and Partners (regional law-firm/legal-publisher
   sources, materially higher quality than a relocation blog) both confirm: age standardised to 40
   for all applicants effective 1 September 2025 (superseding the old 35-with-pension / 50-without
   split), and the 40–49 deposit figures match the sheet exactly. They also confirm SRRV Smile
   (the old USD 10,000–20,000 tier) was **discontinued**, which the sheet is silent on (see Axis
   2). **🟡 SECONDARY-CONSENSUS from stronger-than-average secondary sources for the 40–49 tier
   figures; 🔴 UNVERIFIED for the 50+ tier figures (USD 15,000/USD 30,000) and the pension-income
   floor (USD 800/1,000 per month)** — I did not find independent confirmation of those specific
   numbers in this pass; PRA's own site (pra.gov.ph) loaded but its homepage carried no tier table.

---

## 2. What is safe to publish

This is the actual deliverable — the subset solid enough to appear on a public-facing comparator
page today, versus what must stay internal until re-grounded.

### Safe to publish now

- **Indonesia E33's 100% capital lock, own-name custody, and hard 6/10-year cumulative cap** — SSOT
  facts, unchanged by this review, and the sharpest true differentiator against every competitor.
- **Thailand LTR Wealthy Pensioner: USD 80,000/year passive income (or USD 40k–80k + USD 250,000
  investment), 5+5 = 10-year validity, zero capital lockup for the passive-income route.**
  Primary-source confirmed this session.
- **Portugal Golden Visa: real-estate route permanently eliminated since 7 October 2023; current
  routes are funds (€500,000), scientific research (€500,000), cultural heritage
  (€250,000/€200,000), job creation.** High-confidence secondary consensus across independent
  legal sources; this is also the single most publicly reported fact about the GV programme, so
  the risk of it being wrong is low even though I couldn't reach AIMA directly.
- **Portugal D7: 2026 income floor €920/month, zero capital lockup, full domestic work rights.**
  Secondary-consensus confirmed; low-controversy figure (tracks the published statutory minimum
  wage, which is itself widely reported).
- **The "Where the Alternatives Beat Indonesia" section, minus point 4's tax-rate sentence**, which
  must be rewritten to say Thailand LTR's Wealthy Pensioner/Wealthy Global Citizen categories get
  **exemption from tax on foreign-sourced income** (not a "17% cap") before this page goes live. Do
  not publish the sheet's original wording of point 4.
- **The core "Capital Custody" / "Capital Locked?" comparison framing** — the structural argument
  (Indonesia locks 100%, everyone else offers some liquidity or no lockup at all) is sound and is
  the section that makes this page worth building.

### Must stay internal / needs re-grounding before publishing

- **Every Malaysia MM2H figure** (Silver/Gold/Platinum deposit + property amounts, the 50%
  post-1-year withdrawal clause, the 90-day physical presence rule). Directionally
  plausible and probably correct, but I could not reach a government source this session and
  personally observed conflicting numbers circulating among secondary sources before a resolving
  search. Before this goes on a public page, get one MOTAC/Immigration Department PDF or circular
  URL that actually loads and states the USD-denominated tiers, or route it through an agent with
  browser tooling that can get past the 403.
- **Philippines SRRV 50-and-above deposit tier (USD 15,000/USD 30,000) and pension-income floor
  (USD 800/1,000 per month).** Unverified this session — the 40–49 tier is solid (two law-firm
  sources), the 50+ tier and income floors are carried from the generator's draft only.
- **SRRV Smile's September 2025 discontinuation** should be added to whatever ships, not left
  implicit — a reader who has seen older "$10,000 SRRV" marketing will otherwise think the page is
  out of date rather than correct.
- **The Malaysia/Sarawak "50% withdrawable after 1 year" custody detail** and the Malaysia
  "no naturalisation pathway despite 2024 policy ambiguity" claim — both stated as settled fact in
  the sheet with no source tag; neither was checked this session.
- **Portugal D7's Diário da República legislative citations** (Lei 23/2007, Lei Orgânica 1/2024) —
  the resulting numbers check out via secondary sources, but the specific legal-article citations
  in the sheet (e.g. "Article 98 of Law 23/2007") were not independently verified against the
  gazette text and should not be presented as gazette-verified until someone does.
- **All SRRV pension-income floors and the SRRV Courtesy deposit figures** — carried verbatim from
  the draft, zero independent checking this session.

**Bottom line for the feature team:** the sheet is good enough to build the page's *skeleton and
argument* from (the custody/lock framing, the fairness section once point 4 is fixed, the Thailand
and Portugal-GV figures), but at least two rows — Malaysia's tier table and the Philippines' 50+
tier — need either a working primary-source fetch or a second independent pass before they carry a
number a client will make a six-figure decision against.

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

- Treat every 🟡/🔴 tag above as a build blocker for that specific cell, not for the page as a
  whole — ship the ✅/high-confidence 🟡 rows, gray out or omit the 🔴 rows until re-grounded.
- The custody/lock comparison (Axis 3) is the page's actual differentiator; lead with it.
- Do not carry over the sheet's "Confidence, Staleness & Verification Limits" section as-is — it
  overstates primary-source verification for Malaysia, Portugal, and the Philippines relative to
  what this grading pass could reproduce. Use this document's tagging instead.
