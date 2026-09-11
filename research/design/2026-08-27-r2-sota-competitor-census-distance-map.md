---
date: 2026-08-27
domain: design
client_case: none
round: R2 — SOTA & competitors (Design Study Loop, Zero mandate 2026-08-27)
sources:
  - Pattern census 2026-08-27 (17 targets, 15 captured ×2 viewports, Chrome headless 1280×900 / 390×844; scratchpad r2/pattern-census.json + notes.md + measure_all.json)
  - evisa.imigrasi.go.id/front/info/evoa — official e-VOA guidance page (fetched first-hand by the Kimi research lane)
  - Kemlu User Manual E-Visa Indonesia (kemlu.go.id PDF, 2024 vintage — different product version than the current account-first flow)
  - GOV.UK Design System — question pages / one thing per page; GDS blog — check-answers completion 70.5%→79.5%
  - Stripe — Testing the conversion impact of 50+ global payment methods (vendor-run experiment, +7.4% conversion)
  - Airbnb Newsroom 2025 — total price display now standard globally (rollout, no preference inference)
  - Atlys, iVisa, VisaHQ, Lets Move Indonesia, Emerhub, Flado — landing/product pages as captured (attribution in census)
  - R0 census — research/design/2026-08-27-r0-censimento-superfici-design-system-di-fatto.md (PR #5058)
  - R1 report — research/design/2026-08-27-r1-psicologia-utente-personas-mappa-emotiva.md (PR #5060)
adversarial_review: kimi-k3
mandate: Design Study Loop (Zero, 2026-08-27) — research + doctrine + mockups only; no product code, no deploy, flags stay OFF
lanes: L1 Kimi K3 (published rationale + official flow, web research) · L2 Gemini 3.1 Pro via agy (distance map) · L3 Qwen 3.8 Max via TP1 (borrow/avoid census table) · red-team Codex gpt-5.6-sol xhigh
---

# R2 — SOTA & competitors: what the reference set actually shows, and how far we are from it

## UNKNOWNS — declared up front

1. **The official e-Visa/e-VOA application FORM was never captured.** evoa.imigrasi.go.id does not resolve (NXDOMAIN); evisa.imigrasi.go.id answers HTTP 400 from a CloudFront/WAF edge to headless Chrome; visa.imigrasi.go.id times out at TLS. The PUBLIC info page was fetched first-hand by the research lane (§4); everything behind the login is secondary-source only. Reaching it needs a human browser session (`operator[gui]`).
2. **Aggregator application flows (iVisa, Atlys, VisaHQ) beyond the landing page were not driven.** Fee breakout at checkout, refund/denial-protection upsells, actual wizard behaviour: not observed. "Absent in our captures" therefore never means "absent in the product" — the red-team enforced this framing on every count in this report.
3. **Mobile behaviour is unmeasured.** Mobile screenshots were captured for every reached site, but no mobile-specific interaction notes exist (`mobile_notes` empty on all 14 reached records). Mobile funnel decisions remain ungrounded in this census.
4. **No live form validation or error state was observed anywhere** except the official portal's bare framework error. Error-recovery patterns inside reference funnels are unknown.
5. **Independent review scores are mostly unreached.** Trustpilot product pages answered 403 to the research lane; Google rating aggregates are not crawlable. The only independent figure retrieved is Atlys 4.1/6,015 reviews — read by the research lane from Atlys's Trustpilot page on 2026-08-27, secondary and not pixel-verified (the vendor claims 4.91). The others need a dated human read.
6. **Price accuracy and fee attribution are unverified.** VisaHQ publishes $34/$59/$93 tiers, but the census records the amounts without embassy/service attribution — their meaning is unknown. iVisa's "eVOA from $84.99" (research-lane finding) is NOT pixel-verified: the capture shows an Arrival Card from IDR 1,303,250 and the eVOA value is unreadable.
7. **Peytchev 2006 (paging vs scrolling) attribution is UNVERIFIED** — the DOI did not resolve for the refuter; the claim stays quarantined until the primary paper is read.
8. **Return-ticket upload on the official portal is UNRESOLVED**: official guidance discusses only border inspection; a secondary walkthrough reports a portal PDF upload. Neither "required" nor "not required" can be stated.

## §1 Method

Seventeen targets in four categories — official (imigrasi.go.id home, Ngurah Rai WNA directory, 3 e-Visa hosts), aggregators (iVisa ×2, Atlys, VisaHQ), Bali competitors (Lets Move, Emerhub, Flado), best-in-class outside the domain (Stripe checkout demo, Airbnb, Typeform, GOV.UK visa page, GOV.UK Design System) — captured at two viewports and measured into a closed-schema census (palette, type, CTA, trust signals, price disclosure, step pattern, error pattern, language switch, one verbatim observation per site). 14 reached with HTTP 200; 3 official e-Visa hosts unreached (declared, with causes); flado.co is broken (TLS cert mismatch + Cloudflare 403) — flado.id was captured as the separate live domain.

Three analysis lanes ran on the census: **L1 Kimi K3** (web research: the published rationale behind each reference pattern + the official Indonesian flow from primary/secondary sources), **L2 Gemini 3.1 Pro** (distance map: each R0 incoherence and R1 hypothesis paired with a reference fact that would resolve it), **L3 Qwen 3.8 Max** (BORROW/AVOID/NEUTRAL verdict table from census facts only). **Codex gpt-5.6-sol (xhigh)** then red-teamed all three against the census ground truth: 27 findings, 24 applied, 3 open. L2 came out worst — 7 of its 15 pairings were refuted as forced or reversed; L3's verdicts were categorical where only hypotheses are licensed; L1 lost three numeric claims to citation audit. Everything below is post-disposition.

## §2 The census — what the captures show

The measured rows that carry weight — 14 reached sites plus the official error page (full data: `pattern-census.json`):

- **imigrasi.go.id (official home)** — declares itself in words: «Situs Web Resmi Imigrasi Republik Indonesia». EN/ID switch. No prices, no funnel entry above the fold.
- **Ngurah Rai WNA directory (official)** — the only official surface showing the fee before any form (IDR schedule in page), plus a static edge warning: «Lakukan perpanjangan izin tinggal sebelum masa izin tinggal berakhir».
- **iVisa** — teal accent `rgb(0,160,172)` used consistently for CTAs and links (the one thing in the set that resolves our accent drift); «Apply now» in the Indonesia page's hero (the home hero says «Get started»); numbered marketing narrative of its steps (NOT an observed wizard); «Auto-saved — pick up where you left off» as persuasion copy (no resume behaviour tested). Its home is near-white and its Indonesia page white — it REPRODUCES our home→funnel background mismatch rather than resolving it.
- **Atlys** — «Guaranteed Visa On 4 Sep 2026, 12:53 AM»: a promised date at decision time (the only reference device addressing our B13 timeline-uncertainty moment). Many product cards, no single isolable primary CTA. Publishing its own service-fee markup and charging the service fee only on approval are research-lane findings — neither appears in the census or notes, both unverified in pixels.
- **VisaHQ** — publishes a three-figure price tier ($34 / $59 / $93) with labels the capture cannot attribute; embedded form directly on the landing page.
- **Lets Move Indonesia** — no prices anywhere; WhatsApp-first; award claim («Winner of Best Visa & Business Consultancy in Indonesia Award») with no checkable source in the capture; single long contact form.
- **Emerhub** — quote-only for visas; prices behind a conversation.
- **Flado** — the only Bali competitor publishing a price table (e-VOA B1 600k IDR service line) AND a checkable company identifier (PT name + Tax ID) AND a client portal claim, alongside WhatsApp.
- **GOV.UK visa page** — numbered 1-5 static step overview; GOV.UK green `rgb(15,122,82)` as the one semantic token.
- **GOV.UK Design System** — the only surface in the set documenting one-question-per-screen, and the pattern documentation itself is public (our R0.12 finding — no doctrine covers our funnels — has an external model here).
- **Stripe checkout demo** — a three-card integration chooser («No code / Low code / More code») sharing ONE lavender card colour on a neutral ground: one treatment, not four near-identical ones.
- **Airbnb** — one type family (Airbnb Cereal VF) everywhere; one red accent; uniform pill CTAs (radius 20px). Three of our R0 incoherences have their cleanest external model on this single page.
- **Typeform** — one-question rhythm as marketing; its published completion numbers are vendor claims and stay quarantined.
- **evisa.imigrasi.go.id (`reached: false` — this is the 15th record, the captured ERROR, not a reached site)** — «Oops! An Error Occurred»: a bare framework error with no recovery path, served by the edge to an automated probe (cause — geo/session/bot — undiagnosed).

## §3 What none of them do (counts are descriptive, not causal)

Over the 14 reached captures — a mix of visa funnels, articles, government pages and out-of-domain references, so these counts qualify candidates for testing, nothing more:

| Pattern | Observed |
|---|---|
| Price shown before the form | 7/14 |
| Government fee separated from the service fee | **0/14** |
| One question per screen | 1/14 (the design-system doc itself) |
| Numbered progress indicator | 5/14 |
| EN/ID (or broader) language switch | 4/14 (3 observed + 1 inferred from Atlys's `/en-ID` URL segment — no switcher UI captured) |

"0/14" means zero OBSERVED in reached captures — the official application screens, where PNBP appears at the card step, all failed to capture. Still: no reached reference separates government fee from service fee, and no reached reference shows an itemised total before the form. Both are open ground.

## §4 The official flow (first-hand info page + secondary walkthroughs, kept apart)

The research lane fetched `evisa.imigrasi.go.id/front/info/evoa` directly. What the OFFICIAL page states: individual account required (current flow); three stages (register → apply → pay); base fee **IDR 500,000** plus a card surcharge shown only at the payment step (~IDR 19,500 reported by secondary sources — unverified); document upload limit 200 KB per file; a **120-minute payment window**; 3-D Secure card payment; **no refunds**; instant PDF issuance on approval. A separate Kemlu manual describes five applicants under one submission WITHOUT individual accounts — the red-team's correction: that manual documents a DIFFERENT product version; the two flows must never be presented as one.

What this means for the study (hypotheses, to be tested in R5/R6): the official funnel concentrates its cost disclosure at the last step, imposes a hard time-box on payment, and — as an edge-robustness observation, measured against an automated probe rather than a user in the funnel — answers rejection with a bare framework 400. The cost concentration and the time-box are fragile moments our R1 emotion map already carries on our own side; the official portal does not model the fix for any of them.

## §5 Reference evidence that survived the red-team

- **GDS one-thing-per-page**: official design-system guidance with published rationale — design-system evidence, not outcome data for visa funnels.
- **GDS/DWP service iteration**: overall completion rose 70.5%→79.5% across «lots of changes» — the post does not attribute the rise to check-answers (which it credits with reduced completion TIMES), and the "41% reduction" figure does not exist in it at all. Both mis-attributions removed.
- **GDS on progress indicators**: permits simple question counts, advises against complex clickable indicators; the underlying trial was not an A/B.
- **Stripe**: +7.4% conversion (and +12% revenue) from payment-method coverage — vendor-run controlled experiment, labelled as such.
- **Airbnb**: total-price display made globally standard in 2025 — a rollout fact; no preference claim attaches to it.
- **Atlys guarantee-date**: captured proposition, relevant only to the B13 handoff moment.
- **Base e-VOA fee IDR 500,000**: official, with the card-fee limitation above.

## §6 Distance map — post-refutation

Of R0's twelve incoherences, eight have an external model in the set (R0.1, R0.2, R0.3, R0.4, R0.5, R0.7, R0.10, R0.12), three have NONE (R0.6, R0.8, R0.9 — declared, not forced), and one is downgraded to an adjacent hypothesis (R0.11):

- **Airbnb resolves three** (R0.1 type fragmentation → one variable family; R0.2 five reds → one accent; R0.7 radius chaos → uniform pill).
- **GOV.UK resolves two** (R0.4 un-tokenized greens → one semantic green; R0.12 no public doctrine → the pattern doc itself is the artifact).
- **Stripe resolves R0.3** (four near-identical card backgrounds → one card colour across its integration chooser).
- **iVisa resolves one** (R0.5 accent drift → one teal everywhere).
- **imigrasi/Ngurah Rai resolve R0.10** (EN/ID switch).
- **R0.6 (funnels don't inherit the home's background pair): NO reference resolves it — iVisa reproduces the same defect.** The lane's pairing was reversed by the red-team, and this is the honest state: our background-inheritance problem has no external model in this set.
- **R0.9 (contradictory indexing posture and product counts): NO reference resolves it** — the iVisa product-card pairing was forced (card counts say nothing about indexing) and was removed.
- **R0.8 (no identity on the flagship Oracle): NO reference resolves it** — the iVisa "disclaimer" pairing was forced; no captured reference shows persistent organizational identity inside a funnel. Stays open for R4.
- **R0.11 (1,100px preamble before questions)**: GDS one-thing-per-page governs question composition, not pre-question content — adjacent hypothesis only.
- **R1 hypotheses**: A6→A7 (passport upload before identity earned) has no external resolution (the Flado pairing was forced — it is a price article, no upload flow captured). B13 keeps the Atlys guarantee-date as its one reference device. B2 (whole tree visible) keeps nothing — the GOV.UK capture is a static overview, not a disclosure experiment.

**Corrected ranking** (pairings surviving refutation / originally claimed): Airbnb 3/3 · GOV.UK 2/4 · iVisa 1/4. The raw pre-refutation counts (iVisa 4, GOV.UK 4, Airbnb 3 — first place tied) SURVIVE as counts, per the red-team; what died was the strict ordering built on them, because the forced mappings dissolve under refutation.

**"Already ours" — reframed.** The R1 thesis credited our funnels with honesty devices "no reference shows". The red-team killed the exclusivity: GDS documents both «why we ask» patterns and «I don't know / not sure» options. What survives is narrower and stronger: these devices are MEASURED in our funnels, and in the *captured* reference set no live funnel shows them — but capture absence is not product absence, and the differentiator claim must now rest on execution quality, not exclusivity.

## §7 Borrow / avoid — as hypotheses

The full table (14 rows, each with the census fact, the behavioural reason, and the funnel it applies to) ships in the artifact's R2 section. The shape after refutation: 6 borrow-candidates (declared identity, checkable company identifier, price before form, EN/ID switch, static expiry warning, one-question-per-screen), 4 avoid-candidates (bundled price with no fee separation, many-field single-form lead capture, bare framework errors, award claims unverified in capture — checkability was never tested, only absent from the pixels), 4 neutral-until-tested (numbered progress, hero-CTA vs cards, wizard forms, autosave claims). Every verdict is a test candidate with named metrics — none is a design decision.

## Adversarial review (§8)

Seats: codex gpt-5.6-sol xhigh (read-only sandbox, 27 findings over L1+L2+L3, 26 applied / 1 open) + kimi-k3 (pass 2 on this report — the frontmatter token names this pass); details below.

**Codex gpt-5.6-sol xhigh, read-only, over L1+L2+L3 (27 findings: 10 L1, 9 L2, 8 L3).** RT-codex.md itself carries no applied/open bookkeeping — the disposition log is the conductor's, and it ships row-by-row in the artifact's R2 adversarial section: 26 applied, 1 open (the Peytchev 2006 attribution). The heaviest dispositions: L2's two claimed differentiators deleted (GDS covers both); L2's iVisa pairings for R0.6/R0.8/R0.9 removed or reversed; L1's DWP 41% removed, VisaHQ fee attribution voided, iVisa eVOA price de-verified; L1's double-payment cluster retained only as anecdotal reports (personal walkthrough + comments, no rates inferred); L3's whole verdict table reframed as hypotheses; "0/14" recoded as "zero observed in reached captures". The return-ticket question was dispositioned by DECLARING it unresolved (UNKNOWNS #8); the card surcharge amount is a study UNKNOWN, not a red-team finding.

**Kimi K3 refutation of this report** (pass 2, reply-only): 15 findings (4 high, 8 med, 3 low), ALL applied to this text before commit. The high four: the GDS check-answers causal attribution still stood in §5 (now decoupled); the surviving raw 4-4-3 counts had been erased instead of kept-as-counts (§6 restored); the twelve-incoherence enumeration silently covered ten (now enumerates all twelve); and the "24 applied, 3 open" figure was unverifiable precision attributed to a source that carries no such bookkeeping (now attributed to the conductor's own disposition log). The rest: flado.co redirect corrected to cert-failure+403, the evisa error record moved out of the "reached" frame, Stripe's three-card chooser named, two research-lane Atlys claims layer-tagged, the Trustpilot figure dated, the EN/ID count split observed/inferred, the §9.3 recommendation re-grounded off the 7/14 count, the double-payment disposition made visible, the iVisa CTA verbatim re-attributed, "unsourced awards" reworded to "unverified in capture", and the bare-400 reframed as an edge observation.

## §9 Questions for Zero's R2 ruling (max 3, with recommendations)

1. **PNBP / service-fee separation in displayed prices?** (a) bundle like every competitor; **(b) explicit separation as an honesty device — recommendation**, already a GARUDA charter guardrail («PNBP ≠ biaya jasa»), 0/14 observed doing it, with the red-team's warning that users have no market baseline for separated fees: test in R5/R6, don't assume.
2. **Progress indicator?** (a) numbered steps like iVisa/VisaHQ/GOV.UK-visa; **(b) simple "question X of Y" count, no clickable indicator — recommendation** (GDS-consistent; our Oracle branches, so a fixed numbered indicator would lie).
3. **Price before the form?** **(a) shown before data entry — recommendation**, resting on R1's felt-trust thesis and on the official portal concentrating its cost disclosure at the last step (its most fragile moment); the 7/14 count is descriptive context only — it mixes government pages, a B2B incorporation page and Airbnb, so it qualifies the pattern for testing without supporting causality; (b) after qualification.

## §Meta-pattern

One defective belief generated most of what the red-team had to kill, in all three lanes at once: **"what a capture shows is what the product does — and what a capture lacks, the product lacks."** L2 turned marketing narratives into resolved incoherences; L3 turned page copy into behavioural verdicts; L1 turned secondary walkthroughs into official requirements; and our own R1 thesis had already done the same in reverse, claiming exclusivity for devices whose references we simply hadn't read. The second-order rule this round hands to R3-R7: **a claim about a reference is only as strong as the layer it was measured at** (pixels < page copy < published guidance < controlled experiment), and every borrow/avoid this study emits must carry its layer explicitly.

## §Solo-operatore

Actions only the operator can take, parked without blocking the loop:

- `operator[gui]` — a human browser session through the official e-Visa registration → application → payment screens with synthetic data (stop before payment), to capture the one funnel that matters most and that every automated probe failed to reach.
- `operator[gui]` — dated reads of the four review surfaces (Trustpilot iVisa, Flado TrustScore, Lets Move / Emerhub Google ratings).
- `operator[gui]` — driving one aggregator application (iVisa or Atlys) with synthetic data to the fee-breakout screen.
- Business ruling (Legge 5) — the three §9 questions.
