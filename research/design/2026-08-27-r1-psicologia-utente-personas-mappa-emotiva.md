---
date: 2026-08-27
domain: design
client_case: none
round: R1 — user psychology (Design Study Loop, Zero mandate 2026-08-27)
sources:
  - Local recapture 2026-08-27 (48 screens, scratchpad r0/local/index.json) — GARUDA VOA idle/error states, Visa Oracle offshore family path to HUMAN_REVIEW_REQUIRED
  - R0 census — research/design/2026-08-27-r0-censimento-superfici-design-system-di-fatto.md (PR #5058)
  - apps/mouth/src/app/visa/voa/page.tsx:25-55 (case types, purposes, nationality list); apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/i18n.ts:559-564 («Human context only» banner)
  - Sherwin, NN/g 2016 — Hierarchy of Trust (nngroup.com/articles/commitment-levels)
  - Harley, NN/g 2016 — Trustworthiness in Web Design (nngroup.com/articles/trustworthy-design)
  - Fogg 2009 — A Behavior Model for Persuasive Design (doi 10.1145/1541948.1541999); behaviormodel.org (B=MAP)
  - Gibbons, NN/g 2018 — Journey Mapping 101
  - Baymard Institute — cart-abandonment reasons (baymard.com/lists/cart-abandonment-rate); perceived security of payment forms; checkout form-field averages
  - GOV.UK Service Manual — form structure / one thing per page; GOV.UK Design System — question pages (progress-indicator evidence)
  - Blake, Moshary, Sweeney & Tadelis 2021, Marketing Science — drip pricing field experiment; ACM 2021 full-price experiment (via OECD OPSI — weak, not fetched); Airbnb total-price display (toggle 2022, later made the global default — year not verified)
  - Morwitz, Greenleaf & Johnson 1998, JMR — partitioned pricing; Kahneman & Tversky 1979 — prospect theory
  - Evil, Shaver & Wogalter 2003 (HFES) — fictitious seals; Baymard 2013 — site-seal trust survey; Ert, Fleischer & Magen 2016, Tourism Management — trustworthy faces on Airbnb
  - Mohan, Buell & John 2020, Marketing Science 39(6) (doi 10.1287/mksc.2019.1200) — cost transparency, +21.1% units
  - ACUS 2023 report on administrative burden (byline «Herd, Moynihan & Widman» not verified — the burden taxonomy is what is used) (learning / compliance / psychological costs); Government of Canada — Indonesia travel advisory; VFS Global — «Do not fall for fraud» guidance
  - Stanford Web Credibility Guidelines (Fogg 2002)
  - CSA Research 2020 — Can't Read, Won't Buy (B2C, n=8,709); EF EPI 2025 Indonesia
  - Kivetz, Urminsky & Zheng 2006, JMR — goal-gradient; Nunes & Drèze 2006, JCR — endowed progress
  - BPS Bali 2026-02-02 — 2025 foreign arrivals; Ditjen Imigrasi 2025 stay-permit total; Ditjen Imigrasi visa reclassification press release (June 2025)
adversarial_review: kimi-k3
mandate: Zero 2026-08-27 — design study, no product code, flags OFF, research before opinion, multi-LLM per heavy round, generator≠grader
lanes: L1 Kimi K3 (web research, 2 independent runs) · L2 Gemini 3.1 Pro via agy (personas, Fogg×trust) · L3 Qwen 3.8 Max via TP1 (emotion map) · local recapture + R2 capture via Sonnet subagents · conductor Opus 5
---

# R1 — Chi compra un visto, cosa sente, dove molla

> Round 1 of the Design Study Loop. R0 measured the surfaces; R1 asks who stands in front of them and what each screen does to that person. Everything here is a **hypothesis with a source**, never a measurement: neither funnel has per-question analytics yet. The annotated gallery lives in the loop artifact (section R1); this file is the durable record.

## UNKNOWNS (declared first)

1. **No abandonment data exists for either funnel.** GARUDA VOA is 404 in production by flag; Visa Oracle is live but its analytics destination is unidentified (visaoracle corner, ENFORCE-gate blocker). Every risk score in §5 is an expert hypothesis. The only cure is instrumenting the live Oracle — out of this study's scope.
2. **The commercial peak of both funnels was never seen.** GARUDA's result (stamp reveal + all-inclusive price), the post-OCR passport review, the priced checkout, the live order tracker, and the Oracle's `SUPPORTED_CANDIDATES` verdict with a priced option all need a backend session — and for the Oracle specifically, PREVIEW mode cannot produce a supported verdict by construction (its adapter only ever returns human-review or unavailable), so no local run will ever show it. The local recapture reached only their idle, guard or error states — declared per screen in §7, never mocked.
3. **No behavioural research on Indonesian VOA/e-VOA buyers exists** (two independent Kimi runs, both GAPS sections agree). All buyer psychology here is extrapolated from adjacent domains: e-commerce checkout (Baymard), government forms (GDS, UK Home Office), ticketing and lodging price experiments (StubHub, ACM, Airbnb), localisation surveys (CSA).
4. **The device split of Bali-bound visa buyers is unsourced.** L2's «68% smartphone» figure had no source and was refuted; «mobile-first tourist / desktop long-stayer» is an assumption on the persona cards, labelled as such.
5. **The official e-Visa form (evisa.imigrasi.go.id) could not be captured** (WAF 400 to headless Chrome; evoa.imigrasi.go.id does not resolve; visa.imigrasi.go.id times out at TLS). The reference the buyer compares us against is described from secondary sources until a human browser session captures it (`operator[gui]`).
6. **The seven-state emotion legend is analyst-defined**, not a validated taxonomy (Codex, low). It is a labelling convention for the gallery, not a claim.
7. **No Indonesian verification path for a visa agent was established.** The personas' «a licence that can be checked» presumes a public registry (the UK has one — GOV.UK «Find an immigration adviser»); whether an Indonesian equivalent exists, and which authority governs passport handling by agents, was not verified (Codex pass 2, gap). Until it is, «checkable licence» is a principle, not a feature.
8. **Passport-upload privacy, retention and breach duties (UU PDP) were not audited.** A passport scan is a higher-risk datum than any checkout field; the study's fixes for A6 («who sees it, for how long») name the question without answering it. Carried to R3 as a legal/accessibility line, not answered here.

## 1. Method

Three cross-family lanes ran in parallel from the same brief, then a Codex red-team tried to break each before the conductor synthesised:

| Lane | Seat | Delivered | Refuted by |
|---|---|---|---|
| L1 web research (six questions: buyer psychology, trust signals, cognitive load, price framing, language, frameworks) | Kimi K3, `kimi -p`, two independent runs (the first run's stdout capture collided with its own file write and lost Q1; the second, reply-only, is the reference — the two runs agree on every shared source) | ~40 findings, each `finding (source, year, URL) → application`, plus an honest GAPS section | Codex gpt-5.6-sol xhigh, second pass (§8) |
| L2 personas + Fogg × trust hierarchy | Gemini 3.1 Pro via `agy` | 4 personas, 9-moment table, 7-state emotion legend | Codex, first pass — 14 findings, 6 high |
| L3 screen-by-screen emotion map | Qwen 3.8 Max via TP1 | 22 screens, emotion / trigger / risk / basis / fix | Codex, first pass — 13 findings, 4 high |
| Local recapture of unreached screens | Sonnet subagent, dev server on a throwaway port, flags on locally, synthetic ids | 48 JPEGs + `index.json` with the honest state of each (idle / guard / error / reached) | Conductor, against `index.json` notes |

Generator ≠ grader throughout: no seat graded its own output; the conductor's synthesis (this file) is itself refuted by Kimi K3 before publication (§8).

## 2. The buyer, in one paragraph

A person buying a visa is doing something they do rarely, cannot verify, and that has been publicly branded as scam territory by their own government (Canada's Indonesia advisory: «an increase in visa scams in Indonesia, including in Bali» — never hand your passport to an agency). Administrative-burden research (ACUS 2023 report; the byline the lane gave is unverified) names three costs — learning («which visa?»), compliance («which documents?») and psychological (stress, loss of autonomy) — and finds the third suppresses take-up on its own. Both Bali Zero funnels attack the first two; neither yet names and defuses the third. The buyer's first question is therefore not «what does it cost» but **«is this the real thing, and who is behind it»** — and only then «what does it cost, in total».

## 3. Personas (three carried, one parked)

Behaviour-defined, not demographic. Each grounding line carries a status chip in the artifact — verified · weak · refuted — set after the Codex passes.

**P1 · The first-time tourist (Visa on Arrival).** Fixed date, short session, has read that scams exist. Wants the answer and the total in one screen; fears fake e-VOA sites, a fee after paying, being turned back at Ngurah Rai. Trust triggers: one all-inclusive price before any form, the relationship to the official portal explained, a checkable licence, a visible human exit. Fragile moment (hypothesis): passport upload followed by payment — two level-4 commitments back to back. Verified grounding: Bali 6.95M foreign arrivals 2025, Australia 23.44% (BPS). Weak: Canada advisory (official risk signal, survives), VFS Global's own anti-fraud guidance («no intermediary can expedite or guarantee a decision» — the Tempo article the lane cited could not be verified and is dropped), time pressure = faster and shallower decisions (Zhou et al. 2024, n=69 young adults, a financial-loss task — nothing more than that is claimed). Refuted: «68% smartphone bookings».

**P2 · The long-stayer (extension or conversion).** In-country, deadline-driven, will not hand the passport to a stranger. Fears overstay penalties, a passport «held hostage», a missed biometrics appointment, months lost on the wrong permit. Trust triggers: tracking with a named handler, professional fee separate from the government fee (PNBP ≠ Bali Zero fee — GARUDA charter rule), **current vocabulary** (B1/C1 and E-codes; B211A is a stale index since the June 2025 reclassification). Fragile moment (hypothesis): releasing documents. Verified grounding: 1,369,012 stay permits issued in 2025 (full year — L2 had wrongly said «by May»; Ditjen Imigrasi), E33G USD 60,000 threshold (official visa information page, bontang.imigrasi.go.id — the lane's EvolveColiving citation was replaced). Refuted: the «Russian surge creates extension demand» inference.

**P3 · The spouse (family & marriage route).** Married to an Indonesian; does not know whether the marriage «counts». This is the only Oracle branch driven end-to-end in the recapture (six sponsor questions, «Not sure» on marriage registration → `HUMAN_REVIEW_REQUIRED`) and it is GARUDA's own «Visiting family» purpose. Trust triggers: «Not sure?» that leads to a person, every fact editable before the verdict, Bahasa Indonesia for the sponsor and English for the applicant (CSA 2020: 88% of Indonesian consumers prefer their own language; EF EPI 2025 Indonesia «low»). Fragile moment: the sponsor branch itself.

**P4 · PARKED — the B2B agent / villa manager.** Delivered by L2; its entire grounding («65% of tourists book via agents», «Industry Reports 2025») was refuted. Kept visible on the card so the gap is not forgotten; not carried into R2–R5 unless Zero rules otherwise (ruling Q1).

The remote-worker persona from L2 is folded into P2 as a variant: its one verified fact (E33G threshold) is a long-stayer fact, and no remote-worker branch was captured.

## 4. Fogg × trust hierarchy on our two funnels

Fogg 2009: a behaviour happens when motivation, ability and a trigger converge (the live statement is B=MAP). Sherwin 2016: five commitment levels — relevance · preference · personal info · sensitive/financial · ongoing relationship — and «don't make demands at higher levels until the lower ones are addressed». Applied as a lens, not as proof:

| Moment | Motivation | Ability | Prompt | Level asked | Fragile |
|---|---|---|---|---|---|
| Landing A1 / B1 | high | high | Start / case cards | L1 | — |
| First question A2 / B2 | high | high | the question | L1 | — |
| Nationality A3 / B5 | high | high | eligibility feedback | L2 | — |
| Price reveal A5 (unreached) | moderate | high | total price | L2 | — |
| Consent A4 | moderate | high | checkbox | **L3** | — |
| Passport upload A6 | moderate, privacy fear | **low** | «Take or choose a photo» | **L4** | ✔ |
| Payment A7 (guard reached, priced form unreached) | moderate, scam fear | low | pay button | **L4** | ✔ |
| Order tracking A8 | high | high | link / WhatsApp | L5 | — |
| Verdict «needs a human» B13 | high | low (wait, handoff) | WhatsApp / advisor | L5 | ✔ |

Reading: GARUDA asks L3 (passport expiry, consent) on its fourth screen and L4 twice within the unreached tail (upload, then payment — with the unreached price screen between consent and upload), having earned L1–L2 with a trust strip and a logo but nothing verifiable — no people, no licence, no «why we ask». The Oracle earns L1–L2 slowly (15 question screens on the captured path, vo-02…vo-16), asks L3 at the end (safety check) and L5 at the verdict — the sequencing is right, the anonymity at the top is not.

## 5. Emotion map — what each screen does (summary; full annotations in the artifact)

State legend (corrected after pass 3 — every JPEG in this study is a LOCAL build; the production DOM was measured in R0, never screenshotted here): **local** (local build, flag on — the 26–27/8 gallery and the 27/8 recapture) · **local-idle / local-error** (only that state reachable) · **unreached** (declared, no image). Risk 1–5 = hypothesis. Counts in the trigger column (4 options, 9 nationalities, 4-point checklist, 10 tiles, 13 checkboxes) were counted on the cited code line or by the conductor on the capture named in the artifact card — they are not in R0.

**Funnel A — GARUDA VOA**

| # | Screen | State | Emotion (hyp.) | Risk | The trigger, measured | Fix hypothesis |
|---|---|---|---|---|---|---|
| A1 | Landing | local | curiosity, then hurried | 2 lost | trust strip «4 · 1 · 0», tempo line, two case cards; panel navy gradient #24406e→#1e3863 over the site shell #1d273b, red #ff3344 accent | keep the numbers; make «all-inclusive» a named guarantee repeated at price and pay |
| A2 | Purpose | local | doubt — does it change anything? | 3 lost | 4 options, no consequence, no «not sure» (page.tsx:38-43) | one line per option on what it changes; «not sure» |
| A3 | Who you are | local | fear of error | 3 scared | 9 nationalities + Other (page.tsx:45-55) | searchable list; «Other» answers at once |
| A4 | Dates + consent | local | suspicion | 4 distrusts | passport expiry + storage consent after the fields | say why and who sees it, before the fields |
| A5 | Result + price | **unreached** | relief / alarm | 4 quits | never rendered | carried to R5 |
| A5e | Submit failure | local-error | dropped | 4 quits | red error under a red CTA | one meaning for red |
| A6 | Upload (idle) | local-idle | exposed | 3 scared | 4-point checklist, one button; heading dark serif on navy, near-invisible (read by the conductor on garuda-05-voa-upload-desktop.jpg; not in the index note, contrast not measured) | who sees it, how long, retake; live feedback on the photo |
| A7 | Checkout | local-error (guard) | committed but hesitant | 5 quits | only «We need your reviewed passport details first» reachable | carried to R5: total, inclusions, refund, time above the pay button |
| A8 | Order tracker | local-error | doubt | 4 distrusts | «We couldn't reach the server», red Try again + green WhatsApp | status inside the flow, named person, one action |

**Funnel B — Visa Oracle**

| # | Screen | State | Emotion (hyp.) | Risk | The trigger, measured | Fix hypothesis |
|---|---|---|---|---|---|---|
| B1 | Framing | local (gallery 26/8) | calm, then «who is behind this?» | 3 distrusts | paper, serif, EN/ID, no logo, disclaimer | name the organisation and the humans; keep the disclaimer |
| B2 | Where you are | local (gallery 26/8) | impatience — the whole road first | 4 quits | rail with 10–14 nodes beside the question on desktop; mobile collapses to «Your path so far» | **test before building** — GDS found removing a 12-step indicator changed nothing |
| B3 | Stay permit | local (gallery 26/8) | doubt — why ask? | 3 lost | banner «Human context only — this answer cannot select, rank, add, or remove a visa path» (i18n.ts:564); the E-code catalogue is on the R0 gallery capture vo-03-mobile (onshore lane), not on the 27/8 recapture | drop or defer inert questions; examples over codes |
| B4 | Active overstay | local | fear of error | 4 scared | bare number field | say what overstay does (human review) before the field |
| B5 | Passports | local | relief — dual nationality allowed | 2 lost | picker + Add country | type-ahead |
| B6 | Age check | local | suspicion — why my birthday? | 2 lost | full date of birth | age band unless a rule needs the date (data minimisation) |
| B7 | Category | local | impatience — too many doors | 4 quits | 10 tiles | three intents, second level on choice |
| B8 | Trip scope | local | doubt — «purpose overlap» | 3 lost | single vs multi purpose | two examples per option |
| B9 | Sponsor branch | local | interrogated | 4 quits | six consecutive sponsor questions, no sub-progress | announce the branch once, 1/5…5/5 |
| B10 | Length of stay | local | fear of committing a number | 3 scared | number input | presets, «approximate is fine» |
| B11 | Safety check | local | apprehension, softened | 3 scared | 13 checkboxes, «None of these apply» first, «a feature, not a penalty» | keep; group into four |
| B12 | Your answers | local | relief, in control | 1 | every fact editable, assumptions declared | keep; fix «1 branches» |
| B13 | Verdict HRR | local (light + dark) | deflated but respected | 4 quits | «This needs a human, not an algorithm», 3 next steps, «WhatsApp handoff is not configured» (read on vo-18-verdict-light-desktop.jpg — a local-env state, not in the index note) | named advisor, timeframe, one action; SUPPORTED verdict unreached |

### The three abandonment hypotheses (to test, in this order)

1. **A6→A7 — upload then pay, with identity shown but nothing verifiable earned.** Two level-4 asks in a row from a brand that has shown a logo and a trust strip but no people, no licence, no «why we ask». Baymard 2025: 19% abandon over card distrust, 12% because the total was not visible up front. Cheapest test: instrument A6 entry vs A7 entry once the backend exists.
2. **B13 — the verdict hands off to «not configured».** The funnel's last screen (peak-end is the untested lens here, nothing more) ends in a handoff that, in the captured environment, does not exist. Even live, the handoff is a channel, not a person. Test: named advisor + timeframe vs generic WhatsApp.
3. **B2 — the tree visible in full before the first answer (beside the question on desktop, above it on mobile).** Goal-gradient (Kivetz et al. 2006) and endowed progress (Nunes & Drèze 2006) predict cost; GDS's Carer's Allowance evidence predicts none. Genuinely unknown — A/B the rail hidden-until-first-answer.

### The felt-trust difference, restricted to captured facts

GARUDA shows an organisation (logo, nav, WhatsApp button), a price promise and a progress hairline; the Oracle shows none of those but shows honesty devices GARUDA lacks — «Why we ask» on every question, «Not sure?», a full editable review, dated caveats, EN/ID. Codex is right that «A feels like a transaction, B like unofficial advice» was built on unseen screens; what the captured screens support is narrower: **GARUDA has identity without honesty devices; the Oracle has honesty devices without identity.** The single identity of R4 must carry both.

## 6. What survives the refuters — the evidence R2–R5 may build on

Only findings the two Codex passes could not refute, each with its strongest citation and its evidence class. «Single Kimi run (v1 only)» marks a source the first research run cited that the second run did not repeat and pass 2 therefore never examined — held as weak, not as verified.

- **Prices hidden = site dismissed in seconds; external reviews beat on-site testimonials.** Harley, NN/g 2016 — qualitative usability study; verified by both Kimi runs, not contested by Codex.
- **Card distrust 19%, extra costs 40%, total not visible 12%, checkout too long 17%, forced account 18%** — Baymard cart-abandonment list (n=1,026 for the 2025 trust figure). Industry benchmark, US-weighted, e-commerce not visas; the 40% and 12% are separate categories and are never summed here (Codex pass 2 caught the lane doing so).
- **Field count, not step count, drives perceived effort** (avg 5.1 steps / 11.3 fields; degradation past ~8 steps) — Baymard 2024. Benchmark; the e-commerce→visa transfer is untested, so it licenses «cut fields», not «10–14 steps are fine».
- **One thing per page; eligibility questions first; a question protocol justifying every question** — GOV.UK Service Manual / GDS 2015. Government design guidance; no controlled effect size.
- **Removing a 12-step progress indicator changed nothing** (Carer's Allowance) — GOV.UK Design System, question pages. One government case; enough to demand a test before building a tree, not enough to remove one.
- **Inline validation on blur: +22% success, −22% errors, −42% time** (n=22, 6 versions) — Wroblewski, A List Apart 2009. Practitioner study, single Kimi run (v1 only); the NN/g 2019 error guidelines (both runs, Codex-verified) carry the same recommendation without the numbers.
- **Drip pricing lifts spend ~21%** — Blake, Moshary, Sweeney & Tadelis, Marketing Science 2021 (doi 10.1287/mksc.2020.1261), verified; purchase behaviour only, trust was not measured. The FTC Unfair or Deceptive Fees Rule (2025) covers US lodging and live-event tickets — an analogy for the «total above itemisation» layout, not governing evidence.
- **Incomplete prices feel misleading and cut re-booking; the full-price site won on every dimension** (n=1,000 — **weak**: single Kimi run, secondary source, never fetched) — ACM 2021 via OECD OPSI. Santana, Dallas & Morwitz 2020 (six studies, verified) adds: dripped fees produce costlier, dissatisfying choices.
- **Voluntary cost itemisation under a clear total raises purchase (+21.1% units in the published field study; the lane quoted the working paper's 44%) unless the markup is flagrant** — Mohan, Buell & John, Marketing Science 2019/2020. This is the one finding that argues *for* showing the government-fee / service-fee split — under the total, never instead of it.
- **Recognised brands, not mechanisms, earn seal trust** — Baymard 2013 seal survey, verified: Norton (itself an SSL seal) 36%, McAfee 23%, 49% expressed no preference — the lane's «SSL seals scored 3%» was a misreading. **Fictitious seals rated as trustworthy as real ones; VeriSign ~53%** (n=247) — Evil, Shaver & Wogalter 2003, single Kimi run (v1 only), held as weak. The «many seals backfire» claim (López Jiménez et al. 2021) is literature-based, not measured — dropped as evidence.
- **Trustworthy-looking host photos raise price and bookings on Airbnb** — Ert, Fleischer & Magen 2016, single Kimi run (v1 only), held as weak. **Real photo vs stock: +35% sign-ups** — CXL 2023: one customer photo vs one stock image, a secondary marketing article — weak; named-staff imagery must be tested directly.
- **Stanford credibility guidelines: real organisation, address, people, verifiable claims; typos destroy credibility** — Fogg 2002, single Kimi run (v1 only); guidelines distilled from 4,500+ participants, not an experiment on this shape.
- **76% prefer buying in their own language; Indonesia 88%; 65% even with poor quality** — CSA Research 2020 (n=8,709): stated preference of Indonesian consumers, not conversion, not foreigners in-country — directional only. **Indonesia EF EPI 471, «low»** — EF 2025: a self-selected test-taker index; says nothing about any individual partner's English.
- **Language-concordant contact raises trust** (48.7 vs 45.5, p=0.009, healthcare) — Patel et al. 2023, adjacent domain, single Kimi run (v1 only), held as weak.
- **Fogg 2009 (M·A·T), B=MAP live statement; Sherwin 2016 five levels; Gibbons 2018 journey map with one actor per map and emotions from research, not invention; Lemon & Verhoef 2016 pre/purchase/post stages; Herd, Moynihan & Widman 2023 three burden costs.** Confirmed at the abstract level by both Codex passes — lenses, not proof; every visa-specific mapping built on them in this file is conjecture.

**Evidence-quality classes used above** (Codex pass 2 asked for this table): *peer-reviewed field or lab* — Blake 2021, Mohan 2019, Morwitz 1998, Santana 2020, Kahneman & Tversky 1979, Kivetz 2006, Nunes & Drèze 2006, Ert 2016, Evil 2003, Zhou 2024, Patel 2023, Seckler 2014 · *government guidance* — GDS/GOV.UK, UK Home Office anxiety guidance, Canada advisory, FTC (US, analogy) · *industry benchmark* — Baymard (US-weighted panels) · *stated-preference survey* — CSA 2020, EF EPI 2025 · *practitioner / vendor* — Wroblewski 2009, CXL 2023, and (cited only as weak chips on persona/artifact cards, no finding rests on them) the iVisa report and IndoIndians. Nothing in the first class is about visas.
- **Screen facts confirmed against R0 and code:** the «4 · 1 · 0» strip; 4 purposes; 9 nationalities + Other; A4 dates/consent copy; the error-state WhatsApp CTA; the Oracle's EN/ID toggle, disclaimer, missing logo, ~1,100 px mobile accordion, «Human context only» banner, «Not sure?» routing to human review.

## 7. Not reached — declared

| Screen | Why | Needs |
|---|---|---|
| A5 GARUDA result — stamp reveal + price | every submit fails cleanly without the eligibility API | backend session or recorded fixture |
| A6b GARUDA post-OCR review (ReadyReview / LowConfidenceReview) | needs a live OCR response | OCR backend or fixture |
| A7 GARUDA priced checkout + payment | CheckoutFlow guards on a completed upload handoff | upload in session + payment sandbox |
| A8 GARUDA live tracker statuses | orders fetch fails locally | orders API or per-status fixture |
| A9 GARUDA payment return page | no UI by design (posts an observation, redirects) | nothing — not a gap |
| Oracle verdicts other than HUMAN_REVIEW_REQUIRED (SUPPORTED_CANDIDATES with price, NEEDS_INPUT, NO_SUPPORTED_PATH) | PREVIEW mode is structurally incapable of them: `_lib/preview-adapter.ts` never calls the rules engine — it matches the answers against two gold personas (`gold-oracle-baseline.ts`) and returns HUMAN_REVIEW_REQUIRED or TEMPORARILY_UNAVAILABLE; the captured path is the documented «family-spouse-marriage-registered-unsure» persona | the real backend in ENGINE mode (SHADOW is the production posture; no flag was touched) |
| Oracle onshore lane beyond its first nodes | only the offshore lane was driven | one more local run |
| Official e-Visa form (evisa.imigrasi.go.id) | WAF 400 / NXDOMAIN / TLS timeout | `operator[gui]` browser session or archived capture |

## Adversarial review (§8)

Seats: codex gpt-5.6-sol xhigh (two passes on the lane inputs) + kimi-k3 (one pass on this file — the frontmatter token names this pass); dispositions below.

**Pass 1 — Codex gpt-5.6-sol xhigh on L2 + L3 (27 findings: 10 high, 15 med, 2 low).** Applied 22, rejected 2, open 3. The high findings and their dispositions: the four unsourced L2 numbers («65% via agents», «68% smartphone», «1.36M by May», «Industry Reports») removed or corrected to official figures; B211A vocabulary replaced by B1/C1 + E-codes; every downstream GARUDA moment relabelled hypothesis and given its capture state on the card; personas rebuilt behaviour-first with a status chip on every grounding line; L3's «recall» diagnosis on B3 reframed as a vocabulary (real-world match) failure; risk scores kept but labelled hypotheses in the legend; the felt-trust comparison restricted to captured facts; Hick's law dropped everywhere except the ten-tile screen; Kivetz et al. redated to 2006 and the living-tree inference paired with GDS's counter-evidence. Rejected (kept as labelled hypotheses in the artifact's emotion-map cards — Fogg 2003 and Kurosu & Kashimura on B1, Sweller on B8 — and not cited in this file): source-credibility on the missing logo; cognitive-load / mental-model lenses. Open: abandonment rankings without analytics (true until the Oracle is instrumented); a sourced device split; a taxonomy source for the seven-state legend.

**Pass 2 — Codex gpt-5.6-sol xhigh on L1 (Kimi K3 web research, v2): 18 refuted or weakened (11 high, 7 med), 5 gaps, 19 survive.** Applied in full. What changed in this file: Mohan's «+44%» → the published +21.1%; Baymard's seal survey re-read (Norton 36%, 49% no preference — the «SSL seals 3%» line was wrong); the Tempo/VFS article replaced by VFS Global's own anti-fraud guidance; the «40% + 12% = over half» sum un-summed; the FTC rule demoted to US analogy; CSA and EF demoted to directional stated-preference indices; Zhou 2024 restricted to «faster, shallower decisions»; the «many seals backfire» claim dropped (literature-based); the «no flags on language switchers» claim never entered this file. Findings the lane made that this file never uses (NN/g wizards 2017, Alcántara-Pilar 2018, Wu et al. loss-aversion EDA, Welsh toolkit, Zuko, Mathur 2020) are not cited. The five gaps became UNKNOWNS 7–8 and the evidence-quality table in §6; the «segments researched interchangeably» gap is exactly ruling Q1; «no causal evidence for licence / WhatsApp / photos / price design in visas» is restated as the study's standing caveat — every fix in §5 is a hypothesis to test on the live funnel.

**Pass 3 — Kimi K3 on this file (24 findings: 2 high, 12 med, 10 low; 5 «survives»).** Applied 22, rejected 0, open 2. High: A1's hex corrected (the panel is the editorial navy gradient #24406e→#1e3863; #1d273b is the site shell — both were measured, the card named the wrong one); §4's «no organisation identity» contradicted §5's thesis and R0 §5.8 — rewritten as «identity shown, nothing verifiable earned», and hypothesis 1 with it. Med: the «live» label was wrong for every JPEG in this study (R0 §1: the gallery is a local build) — legend and B1–B3 relabelled local, «live» reserved for R0's DOM measurements; the Oracle path has 15 question screens, not 14; B13's «not configured» and A6's near-invisible heading now cite the capture the conductor read rather than an index note; A5e is sourced to the R0 gallery (garuda-05, local build 26/8); A7's two labels aligned; peak-end demoted to an untested lens in hypothesis 2; hypothesis 3 restated by viewport; ruling Q2 marked provisional (its shelf is weak) and Q3's floor marked design judgement beyond the evidence; pass-1 «rejected» items now traceable to the artifact cards; E33G given its official citation; the Airbnb year and the ACUS byline marked unverified; ACM's n carries its weak chip inline. Open: the counts on the trigger column (4 / 9 / 4 / 10 / 13) rest on code lines and the conductor's reading of named captures — declared, not independently re-counted; the B3 E-code catalogue is attested by the R0 gallery caption only.

## 9. Ruling questions for Zero (max 3, closed, with recommendation)

1. **Persona set for R2–R5?** (a) the four from L2 · **(b) three behaviour-grounded — tourist / long-stayer / spouse — with the B2B agent parked** until a real batch-buyer signal exists. Recommendation **b**: the B2B grounding was refuted end to end; the family route is the one branch we drove to a verdict.
2. **The emotional promise of the single identity** (fixes R4's axis): (a) official-adjacent authority — seals, portal-like restraint · **(b) the honest human who knows the rules — named people, dated sources, one all-inclusive price, human review as a feature.** Recommendation **b, provisional**: the evidence for it is this file's weakest shelf (Evil 2003, Ert 2016, Stanford 2002 — all single-run, held as weak; Baymard 2013 on seals is the one verified piece), so R6's walkthrough must test named-people vs seals directly before R7 writes it into doctrine. What is not weak: looking like the portal collides with the disclaimer both funnels carry and with the GARUDA charter's forbidden claims («mitra resmi», «dijamin»).
3. **When does the price appear in GARUDA VOA?** (Legge 5.) (a) exact price on the landing · (b) promise on the landing, number at the result (current) · **(c) a «from … all-inclusive» floor on the landing, exact number at the result, repeated verbatim at the pay button.** Recommendation **c** — design judgement beyond the evidence: NN/g and Baymard support showing the *total*, and no cited study tests a «from …» floor; the floor is the conductor's compromise between a trust cue and a false promise, offered as such.

Parked, not asked: whether the government-fee / service-fee split is shown under the total (Mohan 2020 says yes when fair; the GARUDA charter says never mix PNBP and Bali Zero fee in one line — compatible, but a copy decision for R5).

## §Meta-pattern

Across the three lanes the same defect repeated: **a plausible number or a real framework stood in for an observation** — «65% via agents», «10 options», «asks for recall», «Hick's law», «peak-end» on a mid-funnel screen. None was malicious; each filled a gap the lane could not see (no analytics, no screen). The antidote that worked was mechanical: every card carries its capture state, every grounding line carries a status chip, every basis is written as a hypothesis. The single belief generating the defects — «a framework applied is evidence produced» — is the one R3's heuristic autopsy must not inherit.

## §Solo-operatore

- `operator[gui]` — a human browser session on evisa.imigrasi.go.id to capture the official form the buyer compares us against.
- `operator[business]` (Legge 5) — ruling Q3 (price display) and the fee-split copy decision.
- Nothing else: the remaining unreached screens need a backend fixture, which a session can produce.
