---
date: 2026-08-27
domain: design
client_case: none
round: R6 — walkthrough, blind perception panel, runtime floor (Design Study Loop, Zero mandate 2026-08-27)
sources:
  - R5 mockups (the 10 walked pages) — research/design/2026-08-27-r5-merah-putih-mockups-worst-screens.md (PR #5079)
  - R5b interactive prototype + its declared R6 handoff (§3/§6) — research/design/2026-08-27-r5b-tree-as-journey-interactive-prototype.md (PR #5087)
  - R1 personas, Fogg×commitment table, emotion map (the OLD-surface baseline this round walks AGAINST) — research/design/2026-08-27-r1-psicologia-utente-personas-mappa-emotiva.md (PR #5060 — the refuter caught the first draft crediting #5064, which is R2)
  - R4 identity contract (tokens, D4, institutional-perception clause) — research/design/2026-08-27-r4-identity-merah-putih-token-spec.md (PR #5078)
  - blind perception panel raw outputs + tabulation — research/design/mockups/r6-walkthrough/ (PERC-*-raw.txt, perception.json, blind-mapping.json, the blinded prompts)
  - runtime a11y suite + results — research/design/mockups/r6-walkthrough/ (a11y_suite.py, a11y-runtime.json, a11y-runtime.pre-rerun.json)
  - GARUDA→portal weld, verified live on this worktree @ origin/main — apps/backend-rag/backend/app/main_api.py:127 (_run_garuda_outbox_scheduler) + services/garuda_orders/outbox_handlers.py (PortalInviteHandler → ensure_portal_profile); supersedes the 2026-08-26 zero-weld audit memory
adversarial_review: codex
adversarial_review_detail: gpt-5.6-sol xhigh (11 — read the live tree and falsified the report's zero-welds premise, the probe-5 verdict and three tabulation claims) + kimi-k3 (7 — re-verified every number on disk, killed the invented unanimity) + agy gemini-3.1-pro (10 — method: order n=2, proxy slide, EN-only Wharton contradiction) + qwen3.8-max TP1 (8, minimal payload) — 36 findings, all disposed row-by-row in adversarial.json
---

# R6 — Walking the redesigned journey: three personas, a blind perception panel, and the runtime floor

**Deliverable**: this report + `research/design/mockups/r6-walkthrough/` (perception panel prompts,
raw seat outputs, `perception.json` tabulation, `blind-mapping.json`, runtime a11y suite +
results). Study only: no product code, nothing here files, prices, or decides anything.

## §1 Method — three instruments, honestly bounded

R1 mapped the LIVE surfaces (its emotion map and Fogg table are the baseline). R6 walks the
REDESIGNED surfaces — the 10 R5 mockups plus the R5b interactive prototype — and asks whether
the redesign answers R1's fragile moments and R3's defects, with three instruments:

1. **Cognitive walkthrough** (conductor, §2): the four Wharton questions per step (right goal?
   action visible? action↔intent? feedback?) along three persona journeys. Evidence class:
   expert walkthrough, hypothesis-grade — the same class R1's emotion map declared.
2. **Blind perception panel** (§3-§4): cross-family seats judged M4a (named human) vs M4b
   (team control), then the red palette on both landings. THREE seats (codex, kimi, agy) read
   FULL pages — markup, copy, declared tokens; the FOURTH (qwen) read a copy-only minimal
   payload and only the variant comparison, not the landings — a deliberately different,
   weaker stimulus (the seat's recovery constraint), so qwen's vote counts as copy-level
   evidence only and never aggregates as a fourth full-page judgment. Variant blinding held
   (study comments stripped, pages relabeled, order counterbalanced 2+2). **Two declared
   limits**: (a) this is LLM-proxy judgment, NOT user data — it can find convergent structure,
   it cannot license a production commitment (R7 gates that on real users); (b) the rubric was
   label-blind but not frame-blind — it named the institutional-vs-scam dichotomy and supplied
   the palette's own mechanism lines, so TASK B convergence is evidence of coherence with the
   frame, not independent discovery (the refuter's demand-characteristics point, adopted).
3. **Runtime a11y suite** (§5): Playwright probes on the R5b prototype covering what R5b's
   static checker declared unreachable. Headless limits stay declared: real VoiceOver timing,
   soft-keyboard occlusion and device folds are `unmeasurable_headless` and remain open.

## §2 Cognitive walkthrough — the redesign against R1's fragile moments

### P1 · First-time tourist — GARUDA VOA: M1 → M2a → M2b → (checkout) → M8

- **M1 landing.** R1-A1 asked for the all-inclusive promise to be a named guarantee repeated at
  price and pay; M1 leads with `from IDR 1.5XX.XXX — all-inclusive · One price. No surprises at
  checkout`, and M5's payment contract repeats the number to the rupiah. Wharton Q1-Q3 pass: one
  primary CTA (`Start your application`), the "How it works" secondary, the what-you-get list
  with `Eligibility checked before you pay`. The trust block carries both convergent mitigators
  (§4). Residual: the panel's most scam-adjacent block on either landing is M1's own
  "Prefer to talk first?" WhatsApp card sitting near the price (kimi) — kept, but it belongs
  BELOW the trust block, not above it; and a visible physical address is missing (codex).
- **M2a question.** Cures R1-A2/A3-class doubt structurally: prior answer visible with `edit`,
  `Why we ask` with the rule date, `Not sure? Ask a person — asking doesn't decide your case`.
  Counter `Question 4 of 9` + progress fill = Wharton Q4 feedback on every step.
- **M2b upload — R1's fragile A6 answered.** The old screen asked for a passport photo with
  a near-invisible heading and zero custody information; M2b shows custody (`Who sees this
  photo · Kept for`), retake-any-time, a real error contract (`aria-invalid` +
  `aria-describedby`, message with a next action, never color alone), and the counter keeps
  running. This is the walkthrough's clearest fragile-moment cure.
- **⚠️ GARUDA checkout — the A7 gap is still open.** R1 rated A7 the highest-risk moment in
  either funnel (level-4 commitment, 5 = quits) and the live screen is a guard dead-end. Among
  the ten R5 mockups there is NO GARUDA checkout page — M5 is the VISA-ORACLE payment verdict.
  The redesign therefore has a payment CONTRACT (M5: price verbatim in three renderings, local
  rails, named follow-up, review-before-pay) but no GARUDA page that carries it. Declared as
  R6's largest open surface; the contract inheritance goes to the product lane, the missing
  mockup to R7's backlog.
- **M8 recovery.** R1-A8's dead-end (error + red retry + anonymous WhatsApp) is answered with
  saved-state under the case code, `Try again`, a named person who `can pick your case up where
  it stopped`, system status and back-to-answers. Wharton Q4 passes in the failure path — the
  only place R1 found it absent.
- **Not mocked, still open from R1:** the consent placement (A4 asked for "why and who sees
  it" BEFORE the fields) has no R5 mockup; it rides the product lane with the M2b custody
  pattern as its template.
- **P1 walkthrough verdict, stated plainly** (refuter-forced): P1's journey is NOT walkable
  end-to-end in the redesign. Of R1's four P1-relevant fragile moments: A6 upload ANSWERED
  (M2b), A8 recovery ANSWERED (M8), A7 checkout OPEN (no mockup exists), A4 consent NOT
  MOCKED. Two of four, with the highest-risk step among the open two.

### P3 · Spouse/family — Visa Oracle: M7 → R5b prototype → M4a/M4b

- **M7 landing.** R1-B1's "who is behind this?" is answered by the identity header + trust
  block; the pre-form floor (`from IDR 1.5XX.XXX all-inclusive` + "your exact price appears
  with your result — the same number again at payment") answers D-V8. The interview promise
  ("about 10, more only if your case branches, and we tell you when it does") is the counter
  law stated as landing copy — the same law the prototype proves.
- **R5b family branch.** R1's fragile moment for P3 was the sponsor branch itself. The
  prototype answers it mechanically: the fork announces scope before entry ("Your sponsor —
  6 questions"), the sub-progress badges 1..6, and the delegate flow (who-answers gate →
  authorization checkpoint → pronoun layer) is the first surface that even ACKNOWLEDGES the
  sponsor operating the screen. The not-sure→human escape on marriage registration belongs to
  the LIVE tree (R1's capture) — the prototype's reduced options (Yes/No/Doesn't apply,
  journey.html:215) do not model it, so that credit is the product's, not the prototype's
  (refuter-caught). **Scope limit on the Wharton pass**: it holds for an EN-reading operator;
  for the Indonesian sponsor persona the delegate flow is EN-only with the ID toggle honestly
  disabled, so Wharton Q1-Q3 CANNOT pass for her until the product i18n lands — the §6
  language line is the same finding, and the pass is scoped accordingly.
- **M4a/M4b verdict.** The walkthrough hands this pair to the perception panel (§3): the
  three full-rubric seats scored status clarity 5/5 on both variants (qwen's minimal rubric
  had no clarity field — the first draft's "all four" was refuter-caught) — the Wharton
  questions pass on either; what splits them is trust anatomy, which is §3's subject.

### P2 · Long-stayer — M7 → R5b (declared reduction) → M5 → M6

- **R5b onshore caveat, restated and WIDENED** (refuter-forced): the prototype models the
  offshore gate-first order while P2 is by definition ONSHORE (in-country extension, live tree
  asks `permit_expiry` first). So P2's tree-portion walkthrough is not representative of her
  actual decision friction — this round's P2 walkthrough carries evidential weight on the
  LANDING, VERDICT and TRACKER surfaces only; the onshore tree walk needs the live tree or an
  onshore-shaped prototype and is left open.
- **M5 supported+payment.** Wharton passes: verdict, price, rails, named follow-up, and
  review-before-pay in one page, price verbatim three times. **One real tension found:** R1's
  P2 trust trigger is "professional fee separate from the government fee (PNBP ≠ Bali Zero
  fee)"; ruling Q7 made pricing bundle-only. M5 says "one bundle covers everything: our
  service, government charges, and follow-up" — which names the components but not the split.
  §8.2 proposes the best move available INSIDE ruling Q7 (composition line + itemized
  receipt) — and declares honestly that it answers the trigger only PARTIALLY: R1-P2 wants to
  verify PNBP against markup BEFORE paying, and a post-payment itemization does not give her
  that (refuter-adopted). The Q7-vs-P2 tension is surfaced as an open ruling question, not
  silently resolved.
- **M6 tracker.** P2's "passport held hostage" fear is met with the four-step timeline
  (current step = red dot + ink label, `Typical wait here: {IMMIGRATION_WAIT}`, "We chase it —
  you don't have to"), a named agent, and the case-code-only WhatsApp link. Document custody
  during the immigration-office step (where the passport physically IS) is not stated — one
  line ("your passport is at the office / with us / with you") would close P2's exact fear;
  raised to the product lane.
- **Wayfinding note, CORRECTED in-round (§6):** the first draft carried the 2026-08-26
  audit's "zero welds from GARUDA to portal account creation" as a live blocker — the refuter
  read the current tree and falsified it, and the conductor verified: `main_api.py:127` now
  runs the garuda-outbox scheduler and `PortalInviteHandler` turns a paid order into a portal
  account (`ensure_portal_profile`), the handler's own docstring recording the history ("THIS
  IS THE THING THAT WAS MISSING"). The weld EXISTS on main as of this round; what this study
  cannot attest is its prove-live state in production — that attestation is the product
  lane's.

## §3 People vs seals — the blind panel on M4a/M4b (LLM-proxy, declared)

Full tabulation in `perception.json`; mapping in `blind-mapping.json`; raw outputs archived.
Design: pages stripped of study comments, relabeled, counterbalanced 2+2. The three
full-rubric seats scored status CLARITY 5/5 on both variants (qwen's minimal rubric carried
no clarity field) — the honest-human copy survives either anatomy.

**Split: 3-1 for the NAMED variant** (codex, agy, qwen vs kimi) — a plurality of judgments,
not a verdict. **Order is NOT ruled out** (three refuters, adopted): both named-first seats
chose named (2/2) while control-first split 1-1; agy's cross-over shows order is not the sole
deterministic cause of the dissent, but with n=2 per condition — and qwen on a different
stimulus — the design cannot estimate, let alone exclude, an order effect.

- **codex** (named first): named T5/S-risk-2 vs control T4/S-risk-3 — "the sensitive exception
  is visibly assigned to an accountable human rather than an anonymous team". Dark-pattern
  flag: **WhatsApp as the only prominent FORWARD action** pressures toward off-page chat; the
  review link only partially offsets.
- **agy** (control first): named T4.5 vs control T3.5 — naming "removes the fear of sending
  sensitive immigration infractions into an anonymous WhatsApp inbox" (verbatim); his formal
  dark-pattern audit returned "None" (price withheld honestly, editable answers, PII-free
  link payloads).
- **qwen** (named first, copy-only minimal payload): named, "a named human taking
  responsibility reassures the anxious applicant" — with the same caveat as everyone.
- **kimi — the dissent** (control first): for the overstay population specifically, burned by
  calo/broker culture, "the strongest trust signal is institutional verifiability, not a
  friendly face": a named person + photo + continue-on-WhatsApp "is the classic
  romance/agent-scam trust prop" (verbatim), and the control's case-file framing anchors the
  case to the state, "not to a person" (verbatim). Watch-item (verbatim): the named module
  "would become deceptive *if* the photo were stock or the agent fictional — it's only clean
  if real".

**The condition matters more than the winner — stated at its true weight** (the first draft
claimed unanimity here and two refuters killed it): the verifiability condition is stated by
TWO seats (kimi's watch-item; qwen's "fake/stock agent authority" risk) — codex never
conditions the named person (his genuine-profiles caveat is about review links), and agy
attaches no condition at all. No seat scored an unverifiable-named scenario, so "scores below
control" has no tabulated basis; kimi's "T=4 at best, 3 for the skeptical" is the only
sub-control data point. §8.1 therefore rests on the two-seat condition PLUS the refuter
round's independent calo-pattern attack — a design judgment, not a panel unanimity. The
WhatsApp-forward-action residual, at its true weight: codex names it a dark-pattern risk;
kimi and agy flag it inside their scam-risk rationales; qwen calls the handoff a risk if
unclear; agy's formal dark-pattern audit still returns "None" — three risk-rationale flags
plus one dark-pattern flag, not a unanimous finding.

## §4 The red, tested against R4's institutional-perception clause

TASK B (codex, kimi, agy on the two full landings): **3/3 INSTITUTIONAL** — with graded
scam-adjacency, not none: codex's verdict on M1 is verbatim "institutional-leaning, but with
greater scam adjacency than LAND-1" (the first draft's "none scam-adjacent" gloss was the
report's own addition, refuter-killed). kimi's mechanism, verbatim: red "as structure, not as
alarm — is the Merah Putih / state-document register", while the urgency-scam register
"floods backgrounds, banners, and countdowns with red"; errors here are "wine, never bright
red". agy: "official administrative stationery".

**Weight limit, adopted from the refuter round**: the rubric itself named the
institutional-vs-scam dichotomy and handed the seats the palette's mechanism lines (red for
structure, wine for errors) — so this 3/3 is a structured adversarial READING that found the
frame coherent and found real residuals; it is not an independent discovery of
institutionality, and it is not human perception. The Q2 ruling (carta+rosso) survives this
proxy test; the human test is R7's.

Convergent mitigators — the two lines that carry the perception, on every page:
1. the role-separation line "We prepare your application; Ditjen Imigrasi decides and issues"
   (kimi: "explicitly disclaims the power scammers claim — the loudest anti-scam signal
   available in this category");
2. the identity line PT + NPWP + registry link ("precisely what scam pages omit").

Residuals, all actionable: a visible physical office address near the first CTA is missing
(codex — goes to the identity contract, §8.3); M1's "Prefer to talk first?" card is the most
scam-adjacent block on either landing and sits near the price (kimi — move below the trust
block); the masked study price `IDR 1.5XX.XXX` "reads slightly teaser" (kimi) — a study-only
artifact that dies in production where real PricingTool numbers render, noted so nobody ships
a masked numeral.

The Q2 ruling (carta+rosso) therefore survives its first structured perception test — with the
institutional-perception clause of R4 doing exactly the work it was written for: the
mitigating marks are not decoration, they are the license for the red.

## §5 Runtime floor — the a11y suite on the R5b prototype

Eight Playwright/chromium probes at 360×640 (suite + results ship in the mockup dir;
`a11y-runtime.pre-rerun.json` preserves the pre-rerun state). **Final, after the refuter
round re-verdicted probe 5: 7 PASS · 1 FAIL · 0 PARTIAL.**

- **Keyboard-only full traversal — PASS.** Boot → tourism verdict boundary with Tab/arrows/
  Enter/Space only, all 10 steps, including the country search input and the date field.
- **Live-region sequence — PASS at human pace.** 13 non-empty announcements for 13 transitions
  on the family+sponsor path, zero `undefined`/`null`/`NaN`, zero silent transitions, zero
  distinct-message collisions <100ms once answers arrive ≥800ms apart. (The prototype's
  intentional clear+set idiom — empty then text at ~50ms, forcing re-announcement of repeated
  strings — is documented as by-design.)
- **Storage corruption — PASS.** Malformed JSON, wrong version, nonexistent question id and
  orphaned-facts payloads all degrade to a clean state: no crash, no phantom review rows, zero
  console errors.
- **Reduced motion — PASS, exhaustively.** The stylesheet declares exactly one `transition`
  (progress fill) and no keyframes, so the single computed-style check (0.25s → 0s under
  `prefers-reduced-motion`) is full coverage, not a sample.
- **Delegate keyboard — PASS.** The who-answers gate, authorization checkpoint and
  post-checkpoint hop complete keyboard-only; the banner carries real perceivable text
  ("You're answering for someone else. Their case, their facts…"), and the question wording is
  actually rewritten ("Is the traveller in Indonesia right now?").
- **Focus traps — PASS** (18×Tab + 18×Shift+Tab, no stuck repeats, no invisible landings).
  **Console hygiene — PASS** (zero errors across every probe).
- **⚠️ Zoom/reflow — FAIL, re-verdicted by the refuter round** (the suite had reported
  PARTIAL; two refuters attacked the score, one against the suite's own contract): the suite's
  declared `would_fail_if` includes the [5b] overflow condition, which DID trigger
  (scrollWidth 1108 > 360), and the code's hollow-first branch returned PARTIAL before ever
  evaluating it — by the suite's own contract this is a FAIL, and the prototype defect
  underneath is real regardless of the proxy: **text-only zoom does NOTHING here.** Root
  font-size 200% produces zero visual change because `.jr{font-size:16px}` islands the
  subtree in fixed pixels and no rule uses rem/em from the root — a text-only-zoom user gets
  no larger text at all (SC 1.4.4 territory). The [5b] overflow evidence itself stays
  proxy-grade (a third refuter is right that SC 1.4.10 is properly tested at a 320px viewport
  with real zoom, not the non-standard CSS `zoom:4`) — the FAIL rests on the solid
  text-zoom-inert defect, not on the weak proxy. Consequence: §8.4 (rem type tokens). Final
  summary after re-verdict: **7 PASS · 1 FAIL · 0 PARTIAL.**

Still outside headless reach and still open (the R5b §3 list stands): real VoiceOver/SR timing
of the live region, soft-keyboard occlusion, device folds. Those need a device pass — R7
doctrine's real-user gate is the natural home. And a scope line the refuter round asked for:
the keyboard-only PASS is a keyboard result — it does not imply the untested screen-reader
experience passes.

## §6 Wayfinding across surfaces

- **The case code is the spine.** BZ-code continuity is the redesign's strongest wayfinding
  invention: within each study case the code survives verdicts, failures, WhatsApp handoffs
  and the tracker (the mockups deliberately show two CASES — BZ-7Q4K for the human-review
  journey, BZ-3M8A for the supported one — not a continuity break). Precision the refuter
  forced on the "no PII" line: the LINK payload carries only the code; the WhatsApp channel
  itself, once opened, necessarily reveals the user's phone number and profile to the business
  — a channel property, now declared rather than glossed. Product lane: the code must also
  appear on the payment receipt and in the first WhatsApp message, or the spine breaks exactly
  at the channel switch it was built for.
- **The weld — corrected in-round (see §2-P2).** The first draft called the GARUDA→portal weld
  absent on the strength of the 2026-08-26 audit; the refuter falsified it against the current
  tree and the conductor verified: scheduler + PortalInviteHandler exist on main. The study's
  residual is narrower and real: prove-live in production is unattested here, and the
  designed journey's dependence on that weld is now a product-lane verification item, not a
  design gap.
- **Cross-funnel identity is now coherent.** One header contract (wordmark, EN/ID toggle,
  WA entry), one trust block, one palette across GARUDA, VO and my — R3's cross-surface
  identity defect is answered in the mockups; the live my portal migration is ruled (Q-R3.1)
  and rides its own lane.
- **Language reality check stands.** The EN/ID toggle is present on every mocked header; the
  R5b prototype's ID toggle is honestly disabled (study); agy's R5b point holds — an
  Indonesian sponsor cannot read an EN-only delegate flow — and stays with the product i18n
  lane.

## Adversarial review (§7)

Four seats, generator≠grader, **36 findings**, row-by-row dispositions in `adversarial.json`
(mockup dir). This was the loop's harshest round on the AUTHOR, and the report above is the
post-disposition text: **codex 11** (10 applied, 1 applied-via-archive — with filesystem
access he falsified the "zero welds" premise against the current tree, caught the R1 PR
number, the invented qwen clarity scores, the probe-5 PARTIAL that masked its own triggered
fail condition, the prototype-vs-live-tree notSure conflation, and named the
demand-contamination in TASK B) · **kimi 7** (7 applied — he re-verified every number on disk
and killed the "unanimous verifiability" claim: two seats stated it, not four, and "below
control for every seat" had zero tabulated basis; plus the spliced quotes now marked or
restored verbatim) · **agy 10** (8 applied, 2 partial — the P3 Wharton-pass-on-EN-only
contradiction, the n=2-per-condition order argument, the proxy→perception semantic slide, the
P2 offshore-path invalidity, the PNBP partial-answer honesty, and the Western-bias attack
that co-produced §8.1's flipped production default; partial: the PII wording — the LINK
payload claim was true, the channel property is now declared — and the case-code
"continuity failure", rejected in part: two codes are two study cases by design) · **qwen 8**
(7 applied via convergence — checkout contradiction, verification-gated default, zoom-FAIL
scoring, spine, order, keyboard-scope — 1 partial: the missing-address undercut is carried as
residual, the 3/3 verdict stands at its declared demand-limited weight). The conductor
verified every contested fact against source before disposing: the weld (main_api.py:127
read), the R1 PR (git log), probe 5's hollow-first branch (suite source read), the marriage
options (journey.html:215 read), and kimi's F1 against the two raw outputs it accused.

## §8 Ruling declarations (adopted under the standing pre-confirmation, async veto open)

1. **The named-human module becomes a verifiability CONTRACT — and the PRODUCTION default
   flips to control until real users decide.** (Amended in-round: the first draft kept named
   as default on a "unanimous condition" the refuters killed; and both kimi's dissent and an
   independent refuter attack converge on the same regional fact — the calo/broker scam
   pattern in Indonesia is precisely a friendly named face + WhatsApp.) The ruling: the STUDY
   default stays named (R5's declaration, unchanged, 3-1 plurality); the PRODUCTION default is
   the team control until an R7-gated real-user A/B decides; the named variant may only enter
   that A/B under the verifiability contract — a real, employed person; a consistent identity
   a client can find on the team page/registry surface; a real photo or no photo, never stock;
   a fictional name is worse than no name. The gate is structural (the module renders only
   when a verified staff record backs it), not a copy promise.
   Alternative kept alive: named-by-default with the contract (the panel plurality's
   position, adoptable the day the A/B says so).
2. **Bundle price, disclosed composition — declared a PARTIAL answer, with the residual
   surfaced to Zero.** The bundle stays THE price (ruling Q7 untouched); one line names what
   is inside (our service + government charges + follow-up) and the receipt itemizes. This is
   the best move INSIDE Q7 — and the refuter is right that it does not fully satisfy R1-P2's
   trigger, which is verifying PNBP against markup BEFORE paying. Open ruling question for
   Zero (async, non-blocking): does Q7 admit a pre-payment "government charges: IDR X (PNBP,
   set by the state)" line — one state-set number, not a fee breakdown — or does bundle-only
   stay absolute? Alternative: visible full split at quote (rejected: breaks Q7 outright).
3. **The funnel identity contract gains two marks.** No funnel page ships without the
   role-separation line + the PT/NPWP/registry line (already law), PLUS a visible physical
   office address in the trust block (codex's missing mark), and M1's talk-first card moves
   below the trust block (kimi's most-scam-adjacent block).
   Alternative: address only in footer legal page (rejected: the mark must sit where the scam
   comparison happens — near the first CTA).
4. **Type tokens move to rem (amendment to R4 at next touch,** alongside the D4 and
   nesting-law amendments). The runtime floor proved px-fixed type is invisible to text-only
   zoom (§5). The px VALUES stay identical at default zoom; only the unit changes.
   Alternative: keep px and declare full-page zoom the only supported path (rejected: it
   silently excludes the text-only-zoom population for zero benefit).

## §Meta

The round's lesson: the panel is most valuable where it can DISSENT from the author's frame —
kimi's minority report reframed "which variant wins" into "what condition makes either variant
safe", and the refuter round then did the same to the author: the "unanimous" verifiability
condition was the conductor's overreach (two seats stated it), the quotes had been spliced,
and the counterbalance — worth running — still cannot de-confound a 3-1 with n=2 per
condition (both named-first seats chose named; the first draft claimed more than the design
can carry). The durable output survives at its true weight: a two-seat condition, an
independent refuter attack on the same regional scam pattern, and a production default that
now waits for real users.

A second lesson from the runtime lane: the conductor read a live subagent's results file
MID-FLIGHT and diagnosed a "matcher bug" that the agent's own final version had already fixed
— the pre-rerun backup proved the file changed between the read and the diagnosis. Two real
instrument bugs did exist (an earlier raw-textContent matcher iteration, and a robot-pace
squash criterion that flagged answers landing 15-64ms apart as screen-reader collisions), and
both were cured in the instrument, never in the prototype: every probe that failed was
re-run, and the untouched entries were verified byte-identical against the backup. A
sibling's file is not ground truth until the sibling is done writing it. The refuter round
then found the inverse instrument sin: probe 5's hollow-first branch returned PARTIAL before
evaluating its own triggered fail condition — the verdict was corrected against the suite's
own contract, not softened by it.

And the round's sharpest single event: the report's "zero welds" blocker — carried from a
one-day-old audit memory — was FALSE against the tree the report itself sat on. A refuter
with filesystem access read the current main and found the weld shipped. Memory claims about
a fast-moving tree expire in hours; they are cite-time re-verify material, like everything
else.

## §Solo-operatore

One person reviews this loop asynchronously. Everything load-bearing is executable or
archived: the panel raw outputs and the unblinding map ship beside the report, the tabulation
is one JSON, the a11y suite runs headless with no browser UI, and every §8 declaration names
its alternative for the veto.
