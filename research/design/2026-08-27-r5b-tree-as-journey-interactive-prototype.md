---
date: 2026-08-27
domain: design
client_case: none
round: R5b — tree-as-journey interactive prototype (Design Study Loop, Zero mandate 2026-08-27)
sources:
  - R5 mockups + §6 declared deviations — research/design/2026-08-27-r5-merah-putih-mockups-worst-screens.md (PR #5079)
  - R4 identity contract — research/design/2026-08-27-r4-identity-merah-putih-token-spec.md (PR #5078; tokens, D4, counter law)
  - R3 defect inventory (D-V4/D-V5/D-V11/D-V12, sponsor persona OPEN) — research/design/2026-08-27-r3-heuristic-autopsy-defect-inventory-axis-gap.md (PR #5074)
  - live tree ground (verified this round on the r5b worktree @ origin/main) — apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/tree.ts (53 questions counted), flow.ts (traversal + the offshore gate-first decision, ~471), i18n.ts (real option labels), ThemeToggle.tsx + layout.tsx (live dark pattern)
  - Zero's rulings + STANDING pre-confirmation — loop memory project_design_study_loop_garuda_visa_oracle_2026_08_27.md
adversarial_review: codex
adversarial_review_detail: gpt-5.6-sol xhigh (15, read the live repo and falsified three 'audited' claims) + kimi-k3 (10, all dark pairs recomputed) + agy gemini-3.1-pro (11) + qwen3.8-max TP1 (6 — SEAT RECOVERED after two failed rounds)
---

# R5b — The tree as a journey: an interactive study prototype

**Deliverable**: `research/design/mockups/r5b-tree-as-journey/journey.html` — one self-contained
interactive prototype (no dependencies, node-testable engine) + `check.py` (executes the engine's
selftest under node, then 40+ falsifiable static checks incl. a structural D4 parser) +
`checks.json` (the run's output) + `adversarial.json` (42 findings, row-by-row dispositions).
Study only: no product code, nothing here files, prices, or decides anything.

## §1 What the prototype proves (and how it can go red)

The round's center is the **counter law on a variable-length tree**. The live product has no
"question X of Y" at all — only a binary paths counter (10 before `category`, 1 after;
`flow.ts:950-953`). Ruling Q8 demands "domanda X di Y". On a branching tree Y is not a constant,
so the prototype implements and TESTS the honest version:

| Behavior | Proven by | Goes red when |
|---|---|---|
| Y recomputed on EVERY answer, both directions (qwen 5 corrected the wording) | node selftest: Y grows on `in_indonesia=yes`, on `holds_stay_permit=yes`, per-branch totals exact | arithmetic drifts from the tree data |
| Pre-fork honesty: "Question X of Y or more", Y = shared trunk + SHORTEST branch | selftest asserts `{n:9, exact:false}` | the inexact flag or the min() dies |
| The fork is announced even when Y is unchanged — "Your path is confirmed: 9 questions" | selftest asserts the inexact→exact announcement (codex 1) | the announcement returns null on the flip |
| No penalty arithmetic in announcements — the number is stated, the reason is scoping, never a cost (agy 3) | selftest asserts `/\+\d/` absent | a "+N" re-enters the string |
| ONE atomic utterance per transition (answer + path change + next question) — two `say()` calls 50ms apart killed each other (codex 2) | code shape + runtime smoke | a second say() reappears in answer() |
| D-V11: sponsor sub-flow is EXACTLY 6 ids in order, sub-progress traverses 1..6, branch announced before entry | selftest asserts the ordered array and the traversal (codex 3) | any id, order or count changes |
| Branch switch and resume never keep hidden facts — `pruneOrphans` at the fork and on restore | selftest asserts family→tourism drops sponsor facts; qwen derived the same 4 contradictions independently | an orphan fact survives |
| Delegate mode has an authorization checkpoint (`delegate_confirm`, delegate path only) | selftest asserts the meta-path difference (agy 6) | the step leaks into self mode or vanishes |

Selftest: **15/15 under node** (`node -e <engine>` — the checker extracts and executes it).
Static checks: **all green** (`FAILS: none`), including the structural D4 parser that rejects
`#ff2d4c` in any dark-block property except text colors and the one declared exception.

## §2 The journey shape (audited ground, declared reductions)

Ids and labels come from the live tree; the shown 5 permit options are **real keys with their real
EN i18n labels** (E23 Working, E28A Investor, E31A Spouse of an Indonesian citizen, E33 Second
Home, E33G Remote Worker) — the first draft's C312/C313/C317 were invented and panel-caught
(codex 6): the live 29 are all E-codes. **Declared reductions, visible in the UI itself** (codex
7): 17 of the 53 live questions (53 counted this round — the earlier ~47 ground map was wrong), 2
of 10 categories, 5 of 29 permit options, 3/6 relations, 3/5 marital options, a 22-country study
list. **Order caveat, also visible**: the live traversal is `flow.ts`'s state machine — onshore
asks `permit_expiry` BEFORE the permit gate; offshore asks `holds_stay_permit` first (a measured
product decision: one gate question instead of a 3-question flat cost for every offshore
applicant of every product). The prototype's sequence matches the offshore gate-first shape.
**Value caveat** (codex 5): several live facts take other value shapes (integers, multi-codes,
different enums) — the study options are behavior-shaped; nothing from this prototype may ever
reach a fact mapper.

**D-V4 sequencing is closed by documentation, not proposal**: the product already sequences
`holds_stay_permit` deliberately (the flow.ts comment records the team-lead cost measurement).
The defect's residue was the belief that sequencing was unowned; it is owned and reasoned.

## §3 Runtime smoke (what static checks cannot see)

A browser subagent (Playwright/chromium) ran a 10-probe smoke on the built prototype at
360×640: boot, tourism path end-to-end, counter text + announcements, focus-after-render,
roving tabindex + arrows, dark toggle computed styles (CTA measured `#D01033`, not-sure
button `#ff5f74` — the D4 split verified live), sponsor sub-progress, delegate pronouns +
banner, save/resume, horizontal overflow (scrollWidth 360 = no blowout). **It earned its
place immediately: 9/10 passed and probe 3 caught a real contract bug the 14-green selftest
could not see** — the announcer read `{n}` from a `{y}`-shaped counterState, so every
on-screen "Your path is now N questions" rendered "undefined"; the selftest passed on
hand-built objects. Cured with one shape everywhere plus an integration test that feeds
counterState's real output to the announcer, then re-verified live by the same agent.
Results ship in `smoke-runtime.json` next to the prototype. The FULL
runtime a11y suite — live-region timing under VoiceOver, keyboard-only traversal, storage
corruption, device fold with dynamic toolbars and the soft-keyboard occlusion agy flagged —
is R6's mandate and is listed as such (codex 15, agy 2).

## §4 Dark component set (kimi's round)

The dark set now exists as a structural discipline, not a color swap: `--action-fill` NEVER
leaves the `#D01033` class in dark (white text 5.52; a `#ff5f74` border carries the SC 1.4.11
boundary at 5.53), `--link` dark is `#ff5f74` (5.53 on panel — measured after kimi caught
`#ff2d4c` failing 4.5 on panel at 4.44), and the checker PARSES the dark block, rejecting
`#ff2d4c` outside text properties. The focus ring was redesigned (text outline + offset + single
accent ring) after kimi measured the old middle ring invisible (1.13) on panel surfaces.
`color-scheme` is declared per theme so native chrome follows. The ONE open item is a declared
**D4 amendment**: the dark progress fill keeps `#ff2d4c` as a graphical, non-action fill (4.44 vs
the 3.0 bar of 1.4.11) — D4's risk is text legibility, and the amendment text goes to R4 at its
next touch together with R5's nesting-law amendment.

## §5 Proposals raised to other lanes (not implemented here)

- **D-V12 / age band (ENG rule-check)**: the engine consumes `person.birth_date`
  (fact-mapper.ts:575) and the UI already labels the screen "Age check". The proposal: enumerate
  which live rules read more than an age comparison; if none do, an age-band question satisfies
  data minimisation and the tree swaps one question. Until that check exists, the honest screen
  asks the real question and says why — which the prototype does.
- **Sponsor custody split (tree content, ENG)**: agy's strongest applied insight — the sponsor
  usually HOLDS the documents these questions ask about. A custody question ("do you have the
  sponsor's documents with you?") would route to the delegate/sponsor flow instead of forcing a
  traveller to guess. Raised as tree-content, NOT added to the prototype (inventing tree
  questions would break the audited-ids rule). His statute citations were not transcribed —
  unaudited.
- **Delegate flow as a product surface**: no on-behalf flow exists anywhere in the live funnel
  (verified: zero hits outside fact-vocabulary). The prototype's shape — who-answers gate,
  authorization checkpoint, pronoun layer, check-with-the-traveller escapes — is the design
  proposal for the R3-OPEN sponsor/assistant persona.

## §6 What this round deliberately does not do — declared

- **No mock verdicts**: the journey stops at a "verdict boundary" that says the engine would
  decide and that today it runs in shadow (no visitor has seen a verdict — the loop's own
  discovery). Mock verdicts train false expectations; R5's M4a/M4b/M5 show the designed states.
- **No live i18n strings**: question wording is study copy (the ID toggle is visibly
  aria-disabled). Bilingual behavior — including agy's point that an Indonesian sponsor cannot
  read an EN-only delegate flow — is real and belongs to the product lane with the real i18n.
- **No engine-shaped values** (§2 value caveat) and **no new tree questions** (§5).
- **Runtime a11y depth** → R6 (§3 list).

## Adversarial review (§7)

Four seats, generator≠grader, 42 findings, every disposition row in `adversarial.json`:
**codex 15** (14 applied, 1 open — the R6 runtime suite; he read the live repo and falsified
three "audited" claims: invented permit codes, a stale 47-vs-53 count, the order-of-tree claim) ·
**kimi 10** (9 applied, 1 open — the declared D4 progress amendment; he caught the prototype
violating its own D4 twice and forced the structural token split) · **agy 11** (9 applied, 2
rejected with reasons — both rejections defend standing rulings: Q2 carta+rosso with R4's
institutional-perception clause as the governed mitigation, and the live product's own theme
toggle) · **qwen 6** (6 applied — 4 were independent derivations of the same orphan-state bugs
codex found: cross-family confirmation; SEAT RECOVERED after two failed rounds). The conductor
verified every contested fact against the worktree before disposing (53 counted; the 29 E-code
options read from tree.ts:215; flow.ts order read directly).

## §8 Ruling declarations (adopted under the standing pre-confirmation, async veto open)

1. **Counter on a variable tree**: "Question X of Y" with Y recomputed on every answer and every
   change announced without penalty arithmetic; pre-fork "Y or more" with Y = trunk + shortest
   branch; the fork announces its confirmation. Alternative (agy): section chunks — not adopted,
   it would contradict ruling Q8's X-of-Y.
2. **Delegate flow**: who-answers gate + authorization checkpoint + pronoun layer + traveller
   escapes, proposed as the product answer to the OPEN sponsor persona. Alternative: no delegate
   surface (status quo).
3. **D4 amendment (to be absorbed by R4 at next touch)**: #ff2d4c in dark = text, plus graphical
   non-action fills that clear SC 1.4.11; action FILLS stay in the #D01033 class in both themes.
   Alternative: absolute text-only (then the dark progress fill needs a new color).

## §Meta

The round's lesson repeats R5's at higher stakes: the panel's value concentrated where a refuter
could reach GROUND the author summarized from memory — codex found every invented fact by
reading the repo the prototype claimed to audit. And one guard-family-#3 case landed in our own
checker: the guarantee-language scan flagged "guarantee letter" (a document's name, not a
promise) — the innocence test earned its keep.

## §Solo-operatore

One person reviews this loop asynchronously. Everything load-bearing is therefore executable:
the engine selftest runs under node with no browser, the checker exits non-zero on any red, and
the dispositions log pairs every claim with what would falsify it.
