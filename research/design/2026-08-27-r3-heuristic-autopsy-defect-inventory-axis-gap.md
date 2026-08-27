---
date: 2026-08-27
domain: design
client_case: none
round: R3 — heuristic autopsy (Design Study Loop, Zero mandate 2026-08-27)
sources:
  - R0 census — research/design/2026-08-27-r0-censimento-superfici-design-system-di-fatto.md (PR #5058; six design systems, 12 incoherence facts, DOM measurements)
  - R1 psychology — research/design/2026-08-27-r1-psicologia-utente-personas-mappa-emotiva.md (PR #5060; 22-moment emotion map A1-A8 / B1-B13)
  - R2 SOTA census — research/design/2026-08-27-r2-sota-competitor-census-distance-map.md (PR #5064; pattern counts, borrow/avoid hypotheses)
  - Local recapture 2026-08-27 (48 screens, scratchpad r0/local/index.json) — the same corpus R1 annotated
  - Zero's nine rulings of 2026-08-27 ~03:35 WITA — recorded VERBATIM in the loop state memory `~/.claude/projects/-Users-nuzantara-nuzantara/memory/project_design_study_loop_garuda_visa_oracle_2026_08_27.md` §"RULING ZERO 27/8". Q2 verbatim: «lo sfondo di un bianco caldo e al posto del navy un bel rosso (sia in Bali Zero e sia il Merah Putih)» — SUPERSEDES R0 §7.2's navy-as-structure recommendation. Q7: prezzo BUNDLE — a declared override of R2 §9.1's separation recommendation (the charter guardrail «PNBP ≠ biaya jasa» survives: it binds any material that CITES the PNBP figure, and the bundle never names it)
  - WCAG 2.x contrast computations run by the conductor on 2026-08-27 (tables in §3)
  - Nielsen — 10 Usability Heuristics (nngroup.com/articles/ten-usability-heuristics); Stanford/Fogg credibility and GDS form principles as grounded in R1/R2
adversarial_review: kimi-k3
---

# R3 — Heuristic autopsy: defect inventory and axis gap

**What this round is.** R0 measured what exists; R1 mapped what a buyer feels; R2 mapped what the market does. R3 is the autopsy: a systematic defect inventory of our own funnels — GARUDA VOA, Visa Oracle, and the my.balizero.com seam — against four declared frameworks, with every defect severity-rated, anchored to a capture or a measurement, and routed to the round that must cure it (R4 identity / R5 mockups / R5b journey / ENG hand-off outside the loop). No product code is touched (loop mandate).

**The axis.** Zero's nine rulings closed at ~03:35 WITA are treated as the design intent. The autopsy therefore answers two questions per surface: *what is broken by general standards* (Nielsen, Stanford, GDS) and *how far the surface stands from the ruled identity* (warm paper + Merah Putih red as structure, the honest human who knows the rules, floor price "from … all-inclusive" in the landing, exact price at result and payment, bundle pricing, "question X of Y" progress).

## UNKNOWNS — declared up front

1. Every severity is expert judgment (Nielsen scale 0-4), not analytics: the funnels still have no per-question analytics (unchanged from R1). A severity-4 here means "worst class by rubric", not "measured abandonment".
2. Every screen judged is the LOCAL build recapture of 2026-08-27 (R0's declared corpus); production DOM was measured in R0 but not re-photographed. GARUDA money-path states (real price, post-OCR review, live tracking) and VO `SUPPORTED_CANDIDATES` remain unreachable without backend — defects on those screens are inherited requirements, not observations.
3. my.balizero.com: the **public login page WAS measured in R0** (`my/login-upgraded` row of the DOM table); what was never observed is the **logged-in portal** and the paid transition into it. The two my defects rest on R0's login-page and code-level measurements; the seam itself is a declared hypothesis.
4. The contrast table in §3 is computed (WCAG 2.x relative luminance), not rendered-and-sampled; sub-pixel rendering and font smoothing can shift perceived contrast but not the pass/fail bands at these distances.

## §1 Method

Four frameworks, declared: (1) Nielsen's 10 heuristics; (2) Stanford/Fogg web-credibility (the R1-grounded subset: named humans, verifiable identity, honest limits); (3) GDS form principles (one thing per page, check answers, question justification — grounded in R2); (4) the nine rulings as brand-fit axes, which for my.balizero.com include Q1's journey-continuity rationale. In the machine inventory (`autopsy.json`, shipped in the artifact's R3 section) every defect carries id, surface, screen(s), heuristic, severity 0-4, evidence and the R1 moment it extends; the §4 tables render the id / severity / heuristic / finding / route subset — the evidence column lives in the inventory. Contract id used below: **C1** is the Visa Oracle client contract "no price may render without a resolved quote" (corner visaoracle).

## §2 The shape of the estate, in one paragraph

The purchase journey crosses three design systems in one session: a buyer lands on warm paper with a navy band (home, S1+S2), enters either a dark-navy/red wizard (GARUDA, S6) or a cream/green oracle (VO, S3), and — if they pay — exits into a copper/anthracite portal (my, S4). None of the three inherits the home's pair; neither funnel uses the logo's red; the flagship (VO) carries no logo — its only mark is the "N" FAB. The ruled identity (Q2: warm paper, red structure) is closest to VO's ground and farthest from GARUDA's — the funnel that was built to sell (GARUDA is flag-off/404 in production today, so no money "flows" anywhere yet — R0 fact, not a measurement of loss).

## §3 Measured today — the red that can and cannot carry the identity

WCAG 2.x contrast, computed 2026-08-27 by the conductor:

| red | on carta `#f7f6f2` | on crema VO `#f7f5ef` | on carta my `#f4f1ea` | white text on it |
|---|---|---|---|---|
| logo `#C8102E` | **5.44** | 5.40 | 5.22 | **5.88** |
| home CTA `#D01033` | **5.11** | 5.06 | 4.89 | **5.52** |
| core `#ff2d4c` | 3.39 | 3.36 | 3.25 | 3.66 |
| visa funnel `#ff3344` | 3.34 | 3.32 | 3.20 | 3.62 |
| red-700 `#c40020` | **5.77** | 5.72 | 5.53 | **6.24** |
| VO state red `#a83a44` (semantic, likely-not) | 5.74 (on crema) | — | — | 6.26 |

Reference: ink `#16213a` on carta = 14.79; white on the current navy band `#1e3863` = 11.66.

Reading, qualified per the red-team: **the reds both funnels actually use fail AA for NORMAL-size text on warm paper (≈3.3:1) and under white normal-size button text (≈3.6:1)** — both still clear the 3.0 large-text/UI band, so button font size and weight decide the verdict there; **the logo family passes normal-text AA in every cell (5.1–6.2:1)**, so white text on those reds needs no large-size concession. A red structural band keeps AA with a ratio roughly half the navy's — but the *headroom above the 4.5 threshold* is a small fraction of the navy's, so dense long-form white-on-red stays out. This is the empirical floor under ruling question Q-R3.2 — a constraint over the six reds measured, not a proof that no other accessible red exists.

## §4 Defect inventory (load-bearing subset; full set in autopsy.json)

Severity: 1 cosmetic · 2 minor · 3 major · 4 worst-class (full-rebuild axis gap or blocking defect) — all severities are rubric judgments (UNKNOWN 1). Severity is also capped by evidence class: a hypothesis-anchored defect cannot exceed 2 (applied: D-M2), and a carried-not-remeasured observation keeps a lower class than a defect measured today (D-G10 vs D-X1). "Extends" names the R1 moment; evidence per defect lives in the machine inventory.

**GARUDA VOA**

| id | sev | heuristic | finding | route |
|---|---|---|---|---|
| D-G1 | 4 | axis Q2 (carta calda + rosso) | the whole funnel sits on the S1 dark-navy ground; the ruled identity is warm paper with red structure - the largest rebuild-scope gap in the estate (severity marks rebuild scope, not measured conversion loss) | R4+R5 |
| D-G2 | 3 | H4 consistency + H9 error visibility | red carries three meanings at once (brand CTA, selected state, error state); under the ruled red-structure identity this collision worsens - errors need a non-red signal *(extends A5e)* | R4+R5 |
| D-G3 | 3 | H1 visibility of status; ruling Q8 | progress is a 2px hairline; no 'question X of Y' counter anywhere - Q8 ruled the counter in (axis Q8=2, not 3: the hairline is a real if weak progress signal) | R5 |
| D-G4 | 3 | H5 error prevention / H9 recovery | checkout-without-handoff dead-ends ('We need you...') in the captured build; the return route's silent replace is a declared design decision (R1) and does not contribute to this severity *(extends A7/A8)* | R5+ENG |
| D-G5 | 3 | H10 help + Stanford credibility | upload idle offers a checklist but never says who sees the passport photo, how long it is kept, or that it can be retaken *(extends A6)* | R5 |
| D-G7 | 3 | axis Q5 (honest human) + Stanford | zero named humans across the funnel; the tracker error shows 'we couldn't reach the server' with no person and no timeline *(extends A8)* | R5 |
| D-G9 | 3 | axis Q6 (floor price in landing) | the trust strip promises '1 all-inclusive price' but no floor number appears before the result - Q6 ruled 'from ... all-inclusive' into the landing (axis Q6=2: the promise STRUCTURE exists, only the number is missing) *(extends A1)* | R5 |
| D-G6 | 2 | H4 consistency (typography) | Montserrat body forced by the /visa layout while every non-funnel surface reads Inter | R4 |
| D-G8 | 2 | H4 (language) | EN-only with no toggle (declared source constraint 5a) while VO ships EN/ID - the two halves of the same estate disagree | R5 (shell component) + ENG (agy routing pass) |
| D-G10 | 2 | WCAG contrast (carried observation) | the upload screen's dark serif heading on navy was recorded near-invisible in R1 - carried as an unresolved contrast defect, not re-measured here (codex finding 15) *(extends A6)* | R4+R5 |

**Visa Oracle**

| id | sev | heuristic | finding | route |
|---|---|---|---|---|
| D-V1 | 3 | Stanford credibility + axis Q5 | no Bali Zero logo and no nav to home - the only mark is the 'N' FAB: the flagship is anonymous on all 19 captured VO screens *(extends B1)* | R4+R5 |
| D-V2 | 3 | axis Q2 | structure color is canopy green on cream; the ruled identity is red structure on warm white - green survives only as a semantic state color, if at all | R4 |
| D-V3 | 3 | H8 aesthetic & minimalist (mobile) | 'Your path so far' accordion occupies ~1,100px above the question at 390px - the question is below the fold on mobile (device split for our funnels is UNSOURCED, declared in R1) *(extends B2)* | R5 (layout) with R5b consulted (agy routing pass) |
| D-V4 | 3 | GDS question justification (inert question) | an inert question (holds_stay_permit) is asked though nothing downstream changes - engine lane owns the cure (corner visaoracle) *(extends B3)* | ENG (engine lane) + R5b sequencing |
| D-V6 | 3 | Stanford transparency + H5 error prevention | overstay numeric field asks for a self-incriminating number before saying what the answer changes (human review, not exclusion) *(extends B4)* | R5b (question sequencing - agy routing pass) |
| D-V8 | 3 | axis Q6+Q9 (pricing) | no price exists anywhere before the verdict; contract C1 (the VO client contract: no price may render without a resolved quote - corner visaoracle) is honoured, but the ruled floor-in-landing (Q6) and price-before-form (Q9) are absent | R5 |
| D-V9 | 3 | axis Q5 + H1 (the money screen) | in the captured preview build the HUMAN_REVIEW_REQUIRED verdict shows a heading and three next steps, but none is a PRIMARY action bound to a named person or a timeline, and the WhatsApp handoff was unconfigured - the moment of highest intent has no owned next step; R5 requirement: a wa.me handoff carrying the case state *(extends B13)* | R5 |
| D-V11 | 3 | H1 + ruling Q8 | the sponsor branch asks six consecutive questions with no sub-progress and no branch announcement - the corpus records it and no defect carried it (codex finding 13; axis Q8=2: 'Your path so far' gives coarse journey-level progress) *(extends B9)* | R5b |
| D-V5 | 2 | H7 flexibility & efficiency | nationality selector without predictive search *(extends B5)* | R5+ENG |
| D-V7 | 2 | H2 match with the real world | 'purpose overlap' jargon; '1 interview branches' plural bug on the review gate *(extends B8/B12)* | ENG |
| D-V10 | 2 | H4 consistency (shape) | radius scale drift: VO 20px vs GARUDA 4px vs home 12/9999 - three shape languages in one purchase journey | R4 |
| D-V12 | 2 | GDS question justification (data minimisation) | full date of birth requested where an age band may satisfy the rules - the question's necessity is never justified on screen (sev 2 vs D-G5/D-V6 sev 3 by stakes: lower than an unexplained passport upload or a self-incriminating question) *(extends B6)* | R5 + ENG (rule check) |

**my.balizero.com (the seam)**

| id | sev | heuristic | finding | route |
|---|---|---|---|---|
| D-M1 | 3 | doctrine collision Q1×Q2 vs GARUDA OS plan | my is S4 copper/anthracite under the ratified GARUDA OS plan; Q1 pulls my into the public identity and Q2 colors that identity - whether my migrates (with kita/prime/zantara staying copper) is exactly ruling Q-R3.1, not a settled conclusion | R4 + ruling |
| D-M2 | 2 | axis Q1 (journey continuity) | HYPOTHESIS on the seam: R0 measured the public my login (Cormorant-uppercase copper carta) and the tracker's S6 styling; the paid transition itself and the logged-in portal were never observed - severity capped by evidence class (qwen finding 1) *(extends A8)* | R5b |

**Cross-surface**

| id | sev | heuristic | finding | route |
|---|---|---|---|---|
| D-X1 | 3 | H4 + WCAG (measured today) | five reds live in the estate and neither funnel uses the logo red; the /visa-funnel reds fail normal-text AA on warm paper - the ruled red must come from the LOGO family (5.1-6.2:1) | R4 |
| D-X2 | 2 | H4 | four papers within four hex points (home f7f6f2, VO f7f5ef, my f4f1ea, kita f8f6f2) - one carta must win | R4 |
| D-X3 | 2 | H4 | four sans families across public surfaces (Inter, Montserrat, IBM Plex Mono, JetBrains Mono + Arial Black declared) | R4 |

Declared measurement gaps (agy pass — classes the corpus could not measure, carried as R5 acceptance criteria + a measurement task): focus order / focus-visible / aria-live step announcements (WCAG 2.2); touch-target sizes and thumb-zone placement at 390px; inputmode/autocomplete and unambiguous date format (a date-ambiguity error on a visa form is a rejection-class risk); client-side compression and resumable upload on SEA mobile networks; multi-currency display and local 3DS/FX failure modes at payment.

Declared risks of the red structure (agy pass — R4 requirements, not a relitigation of Q2): with red as structure the field-error red loses salience, so the error signal must leave red (ties D-G2); in bureaucratic SEA contexts a red-dominant page sits next to warning/sanction and scam-landing associations — mitigation is generous carta ground, restrained red, formal marks; saturated red fields against dark ink can vibrate on OLED (chromostereopsis) — keep large red fields in the dark family and no red-ground long text.

Index-posture inversion (/visa v1 public and over-promising vs VO noindex) is real and stays parked with TWO-DOORS per ruling Q3 — out of this loop's scope.

One item stays OPEN to R4 (agy finding 7): the sponsor/executive-assistant compiler persona (an Indonesian partner or employer filling the form on the applicant's behalf) appears in neither the corpus nor ruling Q4's three personas — carried as a persona-scope question for R4, not silently adopted.

## §5 Organs to protect (the autopsy's second job)

Six things the redesign must NOT lose: (P1) GARUDA's "0 extra to pay the government after" *promise* — Q7-shaped and charter-compliant (PNBP never named); whether delivery honours it is unassessable until a priced checkout is reachable (the Q7 cell in §6 stays "—"); (P2) VO's "Why we ask" + "Not sure?" on every question; (P3) VO's check-answers review screen; (P4) VO's footer disclaimer — the honest foundation of the Q5 axis; (P5) GARUDA's stacked-context wizard (prior answer as a summary line — recognition over recall done right); (P6) VO's EN/ID toggle, the estate's only one.

## §6 Axis gap, per surface

Scale: 0 aligned · 3 full rebuild · — unassessable on the captured corpus (declared). Q5 caveat: the ruling is in force but R1 §9.2 marks its evidence shelf provisional — R6 must test named-people vs seals before R7 doctrine; the column scores the gap to the RULED axis, not the axis's own certainty.

| surface | Q2 carta+rosso | Q5 umano onesto | Q6 floor in landing | Q7 bundle | Q8 X di Y | Q9 prezzo prima del form | note |
|---|---|---|---|---|---|---|---|
| GARUDA VOA | 3 | 3 | 2 | — | 2 | 3 | ground+type rebuild; the pricing PROMISE is Q7-shaped but delivery is unreached (Q7 unassessable); Q6=2 (promise structure without the number); Q8=2 not 3 (hairline progress exists, the ruled counter is absent); no price before the form |
| Visa Oracle | 2 | 2 | 3 | — | 2 | 3 | paper is nearly there - the swap is green→red structure; disclaimer+why-we-ask are real Q5 partial alignment (gap 2, not 3); Q8=2 ('Your path so far' gives coarse progress; no counter, no branch sub-progress); Q7 unassessable pre-checkout |
| my.balizero.com | 2 | — | — | — | — | — | copper→red migration is ruling Q-R3.1; the pricing and wizard axes do not apply to a portal, and Q5 is unassessable - the logged-in portal was never captured |

Reading: GARUDA needs a ground-and-type rebuild and its Q7 cell is unassessable until a priced checkout is reachable (the *promise* is Q7-shaped — P1); VO needs identity (logo, humans) and a pricing surface, while its paper is nearly there and its disclaimer earns real partial credit on Q5. The heavy work R4/R5 inherit is concentrated in six cells: GARUDA Q2/Q5/Q9, VO Q5/Q6/Q9.

## §7 ENG hand-off (outside the loop, no product code here)

Five items are cure-ready independently of the redesign: the review-gate plural ("1 interview branches"), the "purpose overlap" copy, predictive search on the nationality selector, the inert `holds_stay_permit` question (engine lane, corner visaoracle), and a minimal transition state for GARUDA's silent return-route replace. A sixth — the "24+" vs "24" trust-strip mismatch on /visa v1 — is recorded in the inventory but stays parked with TWO-DOORS per ruling Q3, outside this hand-off. Timing for the five is ruling question Q-R3.3.

## Adversarial review (§8)

Seats: codex gpt-5.6-sol xhigh (red-team on the defect inventory and axis-gap table) + kimi-k3 (refutation of this file — the frontmatter token names this pass) + agy gemini-3.1-pro (constructive width: what the autopsy misses) + qwen3.8-max (TP1; first pass timed out at 420s, reduced-scope retry delivered a severity/axis consistency audit).

Findings and dispositions (row-by-row log in the artifact's `adversarial.json`): **codex 32** (31 applied, 1 confirmation — the contrast arithmetic recomputes correctly) · **kimi 23** (22 applied, 1 rejected — the 19-screen count IS sourced, from the declared local recapture index; kimi also recomputed all 22 contrast values and found them exact) · **agy 14** (13 applied, 1 OPEN — the sponsor/EA compiler persona, carried to R4 as a persona-scope question under ruling Q4) · **qwen 10** (7 applied, 3 rejected — each rejection already carries its stated reason in the inventory). The heaviest accepted findings reshaped this file: four severity-4 demotions to one, UNKNOWN 3 corrected, the ruling source cited verbatim with both declared overrides, Q7 cells set to unassessable, three missed defects added (D-V11/D-V12/D-G10), D-M2 capped by evidence class, and the Meta-pattern and Solo-operatore sections rewritten after both made claims their own tables contradicted.

## §9 Questions for Zero's R3 ruling (max 3, with recommendations)

1. **Q-R3.1 — my.balizero.com migrates?** (a) **yes**: Q1 already put my inside the public identity, Q2 colors that identity — my goes carta+rosso, the GARUDA OS copper plan stays for kita/prime/zantara where it was scoped. **Recommendation: a.** (b) my stays copper and the Q1 perimeter shrinks to the funnels alone.
2. **Q-R3.2 — which red is THE red?** (a) **the logo family** — `#C8102E` with dark variant `#c40020` and AA-on-white `#D01033` (5.1–6.2:1 measured today); the bright funnel reds `#ff3344`/`#ff2d4c` never for text, at most as signals. **Recommendation: a** — the numbers in §3 leave no second option for text. (b) keep the bright funnel reds as primary (fails AA on warm paper).
3. **Q-R3.3 — ENG hand-off timing?** (a) **now**, as a separate engineering lane — the five in-scope items (§7; the sixth stays parked per Q3) are independent of the redesign and already mature. **Recommendation: a.** (b) after R5, to avoid touching surfaces that will change anyway.

## §Meta-pattern

An autopsy against rulings is a different instrument from an autopsy against standards — but not because the rulings invent defects the standards cannot see. The one worst-class defect (D-G1, the dark-navy ground vs the ruled carta+rosso) exists only relative to the ruled identity; most of the severity-3 findings carry BOTH tags — D-V1 is a Stanford credibility defect that Q5 raises to mission-critical, D-V9 is a Nielsen H1 defect that Q5 turns into the funnel's most expensive screen. The standards find the friction; the rulings decide which friction is existential. That is why the axis-gap table (§6) and the defect tables (§4) are separate instruments and neither substitutes for the other.

## §Solo-operatore

Everything here is reproducible by one person with the artifact open: the evidence anchor for every defect lives in the machine inventory (`autopsy.json`, artifact R3 section), the contrast table is four lines of python re-runnable from the hex values printed in §3, and the axis-gap cells are declared expert judgments against the ruled axes (UNKNOWN 1) on a 0-3 scale with "—" wherever the captured corpus cannot support a score. Nothing requires analytics we do not have — and where analytics would upgrade a judgment to a measurement, UNKNOWN 1 says so.
