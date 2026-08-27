---
date: 2026-08-27
domain: design
client_case: none
round: R7 — doctrine and loop closure (Design Study Loop, Zero mandate 2026-08-27)
sources:
  - R4 identity law, THE design SSOT this file cites and never restates — research/design/2026-08-27-r4-identity-merah-putih-token-spec.md (PR #5078)
  - the loop's rounds — R0 census (#5058), R1 psychology (#5060), R2 SOTA (#5064), R3 autopsy (#5074), R5 mockups (#5079), R5b prototype (#5087), R6 walkthrough/panel/runtime (#5090), ENG lane (#5077)
  - each round's adversarial record — R5b and R6 in their in-repo mockup dirs; R3/R4/R5 in the artifact sections and archived in this round's dossier (research/design/mockups/r7-doctrine/)
  - this round's panel dossier — research/design/mockups/r7-doctrine/ (prompts, raw seat outputs, adversarial.json, archived R3/R4/R5 adversarial records)
  - Zero's rulings — Q1-Q9, Q-R3.1/2/3, the 2026-08-27 STANDING pre-confirmation and its loop mandate (panel roster: conductor's family excluded), and the 2026-08-20 Fable ruling that shaped which families remain available
adversarial_review: codex
adversarial_review_detail: lead/filesystem seat codex gpt-5.6-sol xhigh (21 findings) + kimi-k3 (18) + agy gemini-3.1-pro (8) + qwen3.8-max minimal payload (6) = 53; row-by-row dispositions in mockups/r7-doctrine/adversarial.json; contested quotes conductor-verified against the round sources before disposal
---

# R7 — The doctrine: how this identity is governed, verified, and allowed to change

**What this file is.** The loop's terminal round. It does NOT restate the design law — that
lives in R4 (one SSOT) with R5's component set, R5b's behavioral contracts and R6's
declarations layered on top by reference. R7 fixes the four things a terminal round owes the
organism: the AMENDMENT REGISTER R4 absorbs at its next touch (§2), the VERIFICATION DOCTRINE
the loop learned the hard way (§3), the ADOPTION PATH and build backlog for product lanes
(§4), and the consolidated OPEN-QUESTIONS REGISTER for Zero plus the honesty register of what
this loop never established (§5-§6). Scope: no product code, and nothing here ships, files or
prices anything — what this file DOES bind is doctrine: the register, the verification rules
and the adoption path. Like every round, it takes effect only through the loop's own order:
panel → row-by-row dispositions applied → commit → async veto open (§7 records that this
order was followed for this file too).

## §1 The loop in one paragraph

Eight rounds and one ENG side-lane, 2026-08-27, all under Zero's standing pre-confirmation:
R0 measured what actually ships (the de-facto design system, screenshot-anchored); R1 built
the psychology baseline (three personas, Fogg×commitment, the emotion map); R2 imported the
state of the art with tags that travel; R3 performed the autopsy (27 defects, measured
contrast floors); R4 wrote the identity LAW (Merah Putih token set, contrast law, restraint
budget, component contracts); R5 rendered ten mockups of the worst screens by R3's autopsy
(two of them panel-forced splits of a single page); R5b made the tree a testable interactive
journey (counter law, delegate flow, dark set, node selftest + runtime smoke); R6 walked the
redesign under the personas, ran the loop's only blind perception panel and the runtime a11y
floor — and took what R6's own record calls the loop's harshest refuter round against the
author's claims. Every round shipped: a repo report behind the adversarial-review CI gate
(the harness's "R1 gate" — a workflow name, unrelated to the loop's R1 round), an adversarial
record with row-by-row dispositions, and an Italian section on the single artifact URL.

## §2 Amendment register — what R4 absorbs at its next touch

R4 is the SSOT and this register is a POINTER TABLE, not a second authority: the text of
record for every amendment is its round's own §8 declaration (cited below as "§8 item N" —
the rounds number their declarations as list items, not subsections). Each row quotes the
declaration verbatim where marked "Verbatim:", and anything under "Gloss:" is this file's
non-binding annotation. The amendments are binding by their ROUNDS' completed declarations
(standing pre-confirmation, veto open) — not by this file — and land in R4's text the first
time a lane touches that file after the loop's PRs merge. A veto reopens the round's
declaration AND strikes the corresponding row here, so the register can never outlive its
source.

1. **D4 graphical exception** (R5b §8 item 3, PR #5087).
   Verbatim: "#ff2d4c in dark = text, plus graphical non-action fills that clear SC 1.4.11;
   action FILLS stay in the #D01033 class in both themes."
   Gloss: the current dark-theme instance is the progress bar (R5b §4 measures its fill at
   4.44 vs SC 1.4.11's 3.0 bar); D4's risk is text legibility, which a non-action fill does
   not carry. The exception is plural by its own text — it is not scoped to one component.
2. **Nesting-law floor** (R5 §6, PR #5079).
   Verbatim: "«inner radius = outer − padding» yields negative radii for realistic paddings;
   the CSS uses a declared floor (`--radius-nested: 8px` = max(8, outer−padding)) — R4 should
   absorb this amendment at the next touch."
3. **Type tokens in rem** (R6 §8 item 4, PR #5090).
   Verbatim: "Type tokens move to rem (amendment to R4 at next touch, alongside the D4 and
   nesting-law amendments). The runtime floor proved px-fixed type is invisible to text-only
   zoom (§5). The px VALUES stay identical at default zoom; only the unit changes."
4. **Funnel identity contract: physical-address mark + M1 talk-first move** (R6 §8 item 3).
   Verbatim: "No funnel page ships without the role-separation line + the PT/NPWP/registry
   line (already law), PLUS a visible physical office address in the trust block (codex's
   missing mark), and M1's talk-first card moves below the trust block (kimi's
   most-scam-adjacent block)."
   Gloss: the address mark is funnel-wide by the declaration's own text; the talk-first move
   is scoped to M1's card. R6 §4's residual ("the card sits too close to the price")
   motivated the move but no general never-beside-price rule was declared — this register
   does not add one.
5. **The honest-human module is verification-gated** (R6 §8 item 1).
   Verbatim: "the STUDY default stays named (R5's declaration, unchanged, 3-1 plurality); the
   PRODUCTION default is the team control until an R7-gated real-user A/B decides; the named
   variant may only enter that A/B under the verifiability contract — a real, employed
   person; a consistent identity a client can find on the team page/registry surface; a real
   photo or no photo, never stock; a fictional name is worse than no name. The gate is
   structural (the module renders only when a verified staff record backs it), not a copy
   promise."
   Gloss: R4's Q5-PROVISIONAL module text absorbs this full contract — the four conditions
   are load-bearing, not the structural gate alone. On the default flip see §3.3's
   least-claim rule.
6. **Bundle composition line + itemized receipt** (R6 §8 item 2).
   Verbatim: "The bundle stays THE price (ruling Q7 untouched); one line names what is inside
   (our service + government charges + follow-up) and the receipt itemizes."
   Gloss: the composition line names categories, never figures — compatible with R4's charter
   guardrail ("The bundle never names the PNBP figure"), which governs the pre-payment bundle
   surfaces; the receipt itemizes POST-payment, outside those surfaces. R4's absorption must
   state this scope explicitly, or the guardrail and the receipt read as a conflict. The
   pre-payment PNBP question stays open in §5.1.

**Cross-reference, not an amendment**: R5b §8 item 1's counter refinements ("Question X of Y"
with Y recomputed on every answer; pre-fork "Y or more" with Y = trunk + shortest branch; the
fork announces its confirmation) REMAIN in R5b's behavioral-contract layer per this loop's
layering. But R4's own counter-law line today says "recomputed at every branch entry" — at
next touch R4 gains a one-line cross-reference to R5b §8 item 1 so the two texts cannot
silently diverge.

Nothing else in R4 changes at this absorption. An amendment not on this register is a new
declaration owed to its own round's process, not a silent edit.

## §3 Verification doctrine — what the loop actually learned

The loop's deepest output is not a palette; it is a discipline for what may be claimed.
Adopted as doctrine for every future design round in this repo (product-lane scope: §8.2):

**3.1 The evidence ladder.** Every load-bearing claim in a round report carries its class —
marked inline "(class a)" … "(class e)" or in its section header; an unclassed load-bearing
claim is challengeable on that ground alone, which is what makes the rule enforceable. The
class bounds what a claim can license: (a) MEASURED on the live tree/DB/screens this round
(strongest — licenses contracts); (b) EXECUTABLE — a selftest or runtime probe that can go
red (licenses behavioral claims; a probe without a stated `would_fail_if` is not evidence);
(c) EXPERT WALKTHROUGH (hypothesis-grade — licenses design direction, never production
defaults); (d) LLM-PROXY PANEL (structured judgment — licenses coherence findings and
residual lists, NEVER perception truth); (e) CITED MEMORY/AUDIT — expires: on a fast-moving
tree it is stale in HOURS and must be re-verified at cite time (R6's "zero welds" was
falsified within a day of its audit). Two closure rules: a measurement is class (a) only in
the round that made it — cited by a later round it decays to (e) and must be re-verified; and
a DERIVED claim (arithmetic or logical consequence of declared inputs) inherits the weakest
class among its inputs. Rung (e) never outranks an earlier-lettered rung read fresh.

**3.2 The panel protocol** (now standard for design rounds): generator≠grader always; four
cross-family seats with the conductor's own family excluded from the panel — the loop
mandate's rule (Zero, 2026-08-27), with the 2026-08-20 Fable ruling shaping which families
remain available; when comparing VARIANTS, blind the stimulus and counterbalance the order —
and state the design's limits honestly (n=2 per condition cannot exclude order effects; a
rubric that names the dichotomy is label-blind, not hypothesis-blind); at least one refuter
seat gets FILESYSTEM ACCESS on any report whose claims cite live tree/DB/filesystem state —
R6 and R7 both proved that seat carries the most weight; every finding gets a row-by-row
disposition, contested findings get conductor verification AGAINST SOURCE before disposal
(the refuter also hallucinates — and the conductor too: R6's instrument record is two real
instrument bugs plus one CONDUCTOR misdiagnosis from reading a live sibling's file
mid-flight; when two seats contradict each other, the source decides); a failed seat is
recorded honestly with zero findings, and a recovered seat gets a minimal payload before a
full one. A round's panel is valid at three or more delivering seats with the failure
recorded; below three, contested findings may not be disposed that round.

**3.3 The human gate.** Three question classes in this loop are answerable ONLY by real
users: (1) named-human vs team-control (the A/B the R6 default flip waits for); (2)
red-institutional vs scam-adjacent perception in the SEA context (proxy-tested at R6 with
declared demand contamination; the human test is open); (3) the assistive-tech floor (real
VoiceOver timing, soft keyboard, device folds — a device pass, not headless). The rule has
two halves: a proxy result may never PROMOTE a contested variant on these questions — and
pending the gate, production holds the LEAST-CLAIM arm, the variant that asserts nothing
unverified (R6's flip to the team control is an instance of this rule, not a proxy-decided
promotion). A production commitment to a contested variant before its human gate is a
doctrine violation, whatever any panel says.

**3.4 Instrument discipline.** Every probe states what would make it red; a pass whose
technique demonstrably did nothing is a FAIL of the instrument, not a PASS of the world;
verdict logic may never short-circuit its own declared fail conditions (R6 probe 5: a
triggered `would_fail_if` masked by a hollow-first branch); a live sibling's output file is
not ground truth until the sibling is done writing it; and when two sondes measuring the SAME
quantity under the same conditions disagree, one of them is broken — find it before
concluding (sondes with different stimuli, scopes or evidence classes may legitimately
disagree; that is triangulation, not breakage).

## §4 Adoption path — the product-lane backlog, ordered

The loop binds design; lanes build. The backlog, ordered by the walkthrough's own risk
findings (each item cites its round). Ownership is Zero's assignment (Legge 5, capacity) —
§5 is the handoff instrument; the ORDER below is the risk order, not a schedule, and items
may proceed in parallel where capacity allows:

1. **GARUDA checkout page** — the funnel's highest-risk step has NO mockup (R6-P1's open
   half); it inherits M5's price contract (verbatim ×3, local rails, review-before-pay) and
   the §2.4 trust marks. First build item because R1 rated its live state 5-quits.
2. **Consent placement** (R1-A4, unmocked): why-and-who-sees-it BEFORE the fields, M2b's
   custody pattern as template — plus the custody-line AUDIT that unlocks M2b's own
   placeholders (R4 §5's honesty constraint stands: no audited facts, no reassurance copy).
3. **Portal weld prove-live** — the weld exists on main (R6-corrected); what is owed is the
   production attestation: a paid GARUDA order observably creating a portal account, and the
   case code surviving onto the receipt and the first WhatsApp message (the spine's two
   missing links).
4. **Delegate flow as product surface** (R5b §8 item 2): who-answers gate, authorization
   checkpoint, pronoun layer, check-with-the-traveller escapes — the design answer to the
   sponsor persona, now needing an owner lane. (The custody split is a separate R5b §5 tree
   proposal, already in the ENG lane's remit.)
5. **i18n for the sponsor** — the delegate flow cannot pass Wharton for an Indonesian sponsor
   until it speaks Bahasa (R6-P3's blocking scope limit); i18n presupposes item 4's surface
   and also covers the wider funnel.
6. **rem migration** (§2.3) and the **A/B + device-pass infrastructure** — these unblock
   human gates 1 and 3 (§3.3); the perception study (gate 2) needs the same real-user
   recruitment but its own protocol. Last in RISK order, not in time — it can start today.

## §5 Open-questions register — consolidated for Zero (async, non-blocking)

1. **PNBP pre-payment line** (R6 §8 item 2): may a single state-set "government charges:
   IDR X (PNBP, set by the state)" line appear before payment inside ruling Q7's bundle-only
   frame — or is bundle-only absolute? (P2's trust trigger is only partially answered
   without it.)
2. **The R4 amendment register** (§2): six amendments plus one cross-reference, adopted under
   standing pre-confirmation — any veto reopens its round's declaration and strikes the
   register row (§2's own rule); the veto window runs until the amendment lands in R4, and
   after landing a reversal is a new round-grade amendment.
3. **M3-dark static mockup** (R5's declared veto point): rendered on request; the dark
   component set otherwise lives in R5b's prototype.
4. **Q-R3.1 my-migration timing** — ruled yes, lane unscheduled (capacity).
5. **The human-gate budget** (§3.3): the A/B, the perception study and the device pass need
   real users and a device — operational spends only Zero can commit.

## §6 Honesty register — what this loop did NOT establish

No real-user data of any kind (every perception result is LLM-proxy, declared); no production
code (flag stays OFF; the Visa Oracle engine ran 100% shadow with no visitor ever shown a
verdict per the 2026-08-26 audit — class (e), re-verify at consumption); no live A/B; no
assistive-tech device pass; no custody audit (M2b's custody line still renders placeholders);
no KBLI/tax/property conformance (declared debt, Legge 5); the institutional-perception
question remains HUMAN-open. Adversarial volume per round, from each round's own declared
seat counts: R3 79 (32/23/14/10) · R4 63 (30/18/15/0 — qwen seat failed) · R5 63 (25/18/20/0
— qwen failed again) · R5b 42 panel findings (15/10/11/6 — qwen recovered on a minimal
payload) + 1 separately-sourced runtime bug · R6 36 (11/7/10/8) · R7 53 (21/18/8/6). The
arithmetic sum R3-R7 is 284 + 53 = 337 — a derived value on the declared counts (§3.1's
derived rule), not a loop total: R0-R2 volumes live in their own records and are not restated
here. Where these records live, honestly: R5b's and R6's adversarial.json are in-repo in
their mockup dirs; R3/R4/R5's records were published in the artifact sections and are now
archived in-repo in this round's dossier (mockups/r7-doctrine/); R3's worktree itself is
gone. This round's panel re-verified the per-round counts from those records (kimi: every sum
and per-seat split matches; codex: one framing correction on R5b's 42+1, applied above).

## Adversarial review (§7)

Four seats refuted this file under its own §3 protocol — the terminal round eats its own
cooking: codex gpt-5.6-sol xhigh with FILESYSTEM ACCESS (21 findings — the lead seat again:
verbatim payload verification against the round sources, two register omissions, the ruling
misattribution), kimi-k3 agentic on the worktrees (18 — splice detection, tally and citation
exactness, enforceability holes), agy gemini-3.1-pro (8 — doctrine-coherence: the §3.3/§2.5
tension, ladder completeness, backlog ordering), qwen3.8-max on a minimal claim-set payload
(6 — contradiction audit). 53 findings, zero seats failed. Every contested quote was
conductor-verified against the round sources before disposal (a dedicated read-only agent
extracted the §8 declarations of R5b/R5/R4/R6 verbatim with line numbers; where kimi's
clean-list and codex's findings contradicted each other on two payloads, the source sided
with codex). Row-by-row dispositions: `research/design/mockups/r7-doctrine/adversarial.json`
— applied 49, partial 4, rejected 0. The register was redesigned from "verbatim copies" to a
pointer table with source-verified quotes; the §3.3 rule gained its least-claim half; the
closure clause gained its sequencing (this file landed only AFTER these dispositions were
applied — the panel's verdict preceded the commit, as the loop's order requires).

## §8 Final declarations (adopted under the standing pre-confirmation, async veto open)

1. **The doctrine's adoption rule**: product lanes CITE R4 + this register; a deviation is a
   declared amendment through a round-grade process (report, panel, dispositions, veto
   window as defined in §5.2) — never a silent edit. Alternative: doctrine-as-guideline
   (rejected: the loop's whole record shows undeclared drift is how the pre-loop incoherence
   grew).
2. **The verification doctrine (§3) binds future DESIGN rounds in full**; design-adjacent
   product claims carry the evidence ladder (§3.1) and the human gates (§3.3), with review at
   ASSEMBLY-LINE grade (one cross-family refuter per PR, risk-tiered) — the full four-seat
   panel is reserved for round-grade declarations, so the doctrine stays executable at
   product-lane capacity (Legge 5). Alternative: per-round improvisation (rejected: §3 is
   the distilled cost of this loop's own failures — R6's corrections table alone killed three
   headline claims of its first draft, and more were caught besides).
3. **The loop CLOSES with this round.** Closure is a mandate boundary, not a completeness
   claim: two design surfaces transfer to build lanes unmocked (checkout §4.1, consent
   placement §4.2) and carry the method with them — R4 law, the §3 doctrine, and §8.1's
   round-grade process for their design decisions. Continuation happens as product lanes
   (§4) and as the human-gate studies (§3.3), each under its own mandate — not as an R8.
   Alternative: a standing design loop (rejected: without new ground truth — real users,
   shipped surfaces — further rounds would iterate on the same evidence and manufacture
   confidence).

## §Meta

A doctrine round's temptation is grandeur; its duty is the opposite — to say what may NOT be
claimed. The loop's most valuable artifacts, in hindsight: R0's screenshot-anchored census
(every later round stood on it), R3's measured contrast floors (they ended every color
argument), kimi's R6 dissent (it turned a winner question into a condition question), and
the refuter-with-filesystem pattern (in R6 it falsified the author's premise, his unanimity
and his clean verdict; in R7 it caught the register misquoting the very declarations it
registers). The identity is carta and logo-red; the method is: measure, declare the class,
let a hostile reader at the ground, and keep the human questions for humans.

## §Solo-operatore

One person reviews this loop asynchronously. This file is the entry point: R4 for the law,
the §2 register for what changes, §4 for what to build, §5 for what awaits a ruling. The
audit trail: eight round PRs plus the ENG side-lane PR before this file (nine shipped), this
round's PR closing the set at ten, the per-round adversarial records at the locations §6
names, and one artifact URL.
