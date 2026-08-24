# V2 WIZARD SPEC — measured baseline and rebuild acceptance

> Lane V2 / unit 1, mandate `docs/plans/2026-08-24-visa-oracle-live/MANDATE.md`. This document is
> the spec the rebuild is built from — it does not restyle or rewire anything. Every claim below
> was produced by reading the file cited or running the command shown, on `origin/main` @
> `04a29fe13` (the same base the orchestrator's `feature/visa-oracle` integration branch was cut
> from), inside worktree `mouth-visa-v2-spec`, 2026-08-24. No browser MCP was available in this
> session (`mcp__claude-in-chrome__*` did not resolve via `ToolSearch`) — the "LIVE experience"
> requirement in the brief could only be partially honored: `WebFetch` confirms the route is live,
> 200, and matches the SSR loading state the code predicts, but no interactive/JS-rendered walkthrough
> was performed. This is disclosed, not glossed over — see the note at the end of Part A.

## Part A — what the wizard is today, measured

### A.0 — a fact the brief and the mandate do not mention: there are TWO live visa funnels

Before anything else: `apps/mouth/src/app/visa/**` is a **second, separate, live production
funnel**, distinct from `(visa-oracle)/visa-oracle` and not addressed anywhere in `MANDATE.md`,
`GROUND.md`, or `FROZEN.md` (all read this session, in the orchestrator's own integration
worktree `.worktrees/visa-oracle-integration`).

- `apps/mouth/src/app/visa/page.tsx` is a live entry page — headline **"24 visa types. One fits
  you."**, trust strip **"5,021 visas filed since 2019 · 24+ visa categories supported"** — built
  on the shared `@balizero/core` `AppFrame`/`AppBranchSelector` funnel framework, branching to
  `/visa/clock` (expiry countdown) and `/visa/match` (the OLD 4-step wizard:
  nationality→purpose→duration→budget, backed by `apps/mouth/src/lib/visa-oracle/quiz-logic.ts`,
  84 lines, 7 purposes — a completely different decision structure from the tree analyzed below).
  Also live under the same parent: `/visa/second-home`, `/visa/voa` (tombstoned 404 per GARUDA's
  own 2026-08-24 fleet report, unrelated to this lane), `/visa/terms`, `/visa/privacy`.
- `apps/mouth/src/components/visa/VisaChat.tsx` (the old AI-chat escape hatch) is still wired
  through `ChatAccordion.tsx` and imports the same old `lib/visa-oracle/{types,api,storage}.ts` —
  live, not dead code.
- No `noindex` was found on `/visa/page.tsx` in this pass (unlike `(visa-oracle)/visa-oracle`,
  which explicitly restores `robots: { index: false, follow: false }` — see A.7). This v1 surface
  is plausibly indexable today while the "real" v2 wizard sits in shadow.
- `ZantaraWidget.tsx:53` gates its own behavior on `path.includes("/visa")` — a substring match
  that fires on **both** `/visa/...` and `/visa-oracle/...` alike, i.e. the two surfaces are not
  even cleanly distinguished by the one component that already tries to special-case "the visa
  funnel."

**Why this matters for the rebuild, not just as trivia**: the mandate's Definition of Done says
"every visa sale at Bali Zero enters through one door." Today there are two doors, and nothing in
this mandate's own artifacts proposes retiring, redirecting, or merging `/visa/match` into
`/visa-oracle`. Recommend the orchestrator add an explicit V2 (or V4) acceptance item: **decide
and execute the fate of `apps/mouth/src/app/visa/**`** (redirect to `/visa-oracle`, or an explicit
kill date) — otherwise "one door" ships as two doors, one of them un-audited by this whole
program.

The rest of Part A is scoped to `(visa-oracle)/visa-oracle`, per the brief's explicit target.

### A.1 — file map (what exists, who owns what)

```
apps/mouth/src/app/(visa-oracle)/visa-oracle/
  layout.tsx            route metadata (title, robots), pre-paint theme bootstrap script
  page.tsx               server component: reads signed vo_internal cookie, renders OracleShell
  oracle.css              1,620 lines — all visual design lives here (no CSS-in-JS)
  privacy/, unlock/       privacy policy page; internal-PIN unlock route
  _components/            17 .tsx components (OracleShell, LivingTree, QuestionScreen,
                           ConfirmationCard, VerdictReveal, OutcomeSheet, ConsentHandoff,
                           PathsCounter, ThemeToggle, LanguageToggle, NotSure, WhyWeAsk)
  _lib/                   30 modules — the actual engine: flow.ts (state machine), tree.ts
                           (question registry, 53 question definitions total across every
                           branch), i18n.ts (1,663 lines, flat EN/ID dictionary,
                           key-parity-tested), engine-adapter.ts (backend response → view model,
                           ~886 lines incl. the full per-reason-code copy library),
                           fact-mapper.ts, evaluation-client.ts, shadow-client.ts,
                           runtime-mode.ts, outcome-fallbacks.ts, resume-store.ts,
                           consent-store.ts, telemetry.ts, gold-oracle-baseline.ts, and 18 more
```

`apps/mouth/src/lib/visa-oracle/` (`quiz-logic.ts`, `api.ts`, `storage.ts`, `types.ts`) belongs to
the OLD `/visa/match` funnel above, not to this wizard. There is no code sharing between the two
trees beyond a stray docstring comment in `shadow-client.ts` ("mirrors `lib/visa-oracle/api.ts`'s
existing pattern") — not an import, just a comment.

### A.2 — how many questions, in what order, driven by what

**Driven by `_lib/flow.ts`**, a pure reducer (`flowReducer`) wrapping `computeNextNode` — a single
function that is the sole source of truth for "what comes next," consumed identically by the live
UI, by `getTreeSteps` (the LivingTree projection), and by the test suite. **Not** `quiz-logic.ts`
(that file belongs to the other, older funnel — see A.0) and not a hardcoded array: the path is
computed live from the accumulated `OracleFacts` object after every answer.

The registry (`_lib/tree.ts`) declares **53 distinct question definitions** across every possible
branch. No single applicant sees all 53 — the real path is a linear spine plus one
category-specific detour, roughly:

1. **Spine (always asked, in this order, with two owner-ruled 2026-08-24 branch points):**
   `in_indonesia` → (onshore: `permit_expiry`→`holds_stay_permit`→one of
   `stay_permit_code`/`current_status_code`[→`renewal_paid` if expired/unknown] | offshore:
   `holds_stay_permit` first, expanding into the same chain only on "yes") → `overstay_days` →
   (onshore only: `wants_onshore_conversion`→`application_channel`) → `nationalities` →
   `birth_date` → `category` → `trip_scope` → **[category-specific block]** → `review_gate` →
   confirmation → verdict.
2. **Category block** (one of 10: tourism / business / work / remote / invest / family /
   retirement / study / diaspora / other), selected at the `category` question and expanded by
   `getCategoryQuestionIds(facts)` — e.g. `family` alone conditionally asks up to 8 further
   sub-questions (relation, marital status, sponsor nationalities, sponsor status/permit-basis
   gated on non-Indonesian sponsor, marriage-registration for SPOUSE/PARENT, two stepchild
   evidence questions for STEPCHILD) — genuinely behavioral branching, not a flat form.
3. A realistic onshore-family path runs to roughly **14–18 questions**; a realistic offshore-tourism
   path to roughly **8–10**. This is materially more than the old v1 4-step wizard (A.0), and
   reads as a real interview rather than a form — the code's own framing ("THE centerpiece … the
   product's data structure, rendered honestly, not decoration" — `LivingTree.tsx:28`) matches
   what is actually built.

**One question per screen, confirmed by construction**: `OracleShellRuntime` renders exactly one
of `{framing | question | confirmation | verdict}` per `current.kind`
(`OracleShell.tsx:784–924`) — there is no code path that shows two questions at once.

### A.3 — how the path narrows (or fails to)

Two separate visual mechanisms exist, and they narrow **two different things**:

1. **`LivingTree`** (`_components/LivingTree.tsx`) renders a vertical trunk of every step so far
   (done/current/pending/pruned) plus, from the `category` question onward, 10 **category
   leaves** that visually prune from 10 down to 1 the moment a category is chosen
   (`categoryLeaves.status: "pruned"` for the unchosen nine, animated exit via Framer Motion,
   `AnimatePresence`). This is real and well-built — collapsible on mobile, sticky sidebar on
   desktop (≥1024px), a screen-reader-only path list independent of the visual tree, tap-to-edit
   on completed steps.
2. **`PathsCounter`** (`_components/PathsCounter.tsx`) shows a numeric "N remaining," explicitly
   documented as narrowing from **`CATEGORY_KEYS.length` (10) down to 1`** the instant a category
is chosen (`flow.ts`'s `interviewBranchesRemaining`) — **not** from 38 (the product count) down
   to 1.

**This is the single most important finding for the rebuild.** The owner's "magia decisionale" —
watching the path narrow from 38 products to theirs — has no counterpart in the current build. What
exists narrows across **10 interview categories**, a UX-only classification with no eligibility
meaning (`tree.ts:107-109`: "This set describes UI coverage only; it never means a visa path is
legally supported"). The actual product space is not visually represented anywhere in the
interview — a user cannot see "31 candidates possible → 4 after nationality → 1 after your
sponsor's status" because the frontend never has that number: it is computed once, at the very
end, by the engine's single evaluate call, and today (per `GROUND.md`, verified this session) that
call is genuinely honest about how few of the 38 it can conclude on — **34 of 38 products are
never any gold persona's `expected_candidates`**, and the dynamic gold replay against the real
signed pack matches only 4/20 personas with 16 untriaged divergences. A rebuild that fakes a
38→1 live-narrowing meter without the engine's real per-question elimination behind it would be
decorating a number the product does not have. The honest version of "magic": narrow what is
actually knowable (facts collected, categories eliminated, and — new — a running characterization
of the T1/T2/T3 tier the case is heading toward), and let the exact-N product count appear only at
verdict time, sourced from the real response, never estimated mid-interview.

### A.4 — the verdict screen: five states, genuinely distinct (not one fallback)

This is a second finding that runs against the brief's framing, and needs to be reported as
found: **the current build does NOT collapse the four non-`SUPPORTED_CANDIDATES` outcomes into one
"something went wrong" screen.** `OutcomeSheet.tsx` (`_components/OutcomeSheet.tsx:495-600`)
branches explicitly on `outcome.state` with a dedicated section per state — `NEEDS_INPUT` lists
missing facts with per-item "Edit" jumps back into the tree; `HUMAN_REVIEW_REQUIRED` shows the
review reasons with source citations; `NO_SUPPORTED_PATH` shows the exclusion reasons plus
"alternatives" (jump to a different category); `TEMPORARILY_UNAVAILABLE` shows the outage message
and a conditional retry button; `SUPPORTED_CANDIDATES` shows the full candidate cards. `VerdictReveal.tsx`
picks a distinct headline/icon/description per state too, and deliberately separates "the state the
server actually decided" from "the provenance of the response" (`VerdictReveal.tsx:64-73`) — a
degraded client-side guard still reports its most specific honest state rather than a generic
error. `outcome-fallbacks.ts` (134 lines) exists specifically to keep this honest under failure:
client guards, network failures, and shadow-mode all resolve to typed `OutcomeViewModel` states,
never a raw exception rendered to the user. **This code-level finding should not be read as "V2 is
done"** — see Part B for what remains genuinely wrong even though the states are distinct
(dead-code copy paths, unresolved defects upstream in the engine that this UI faithfully — perhaps
too faithfully — surfaces, and the consultant-control gap below).

### A.5 — EN/ID coverage

`_lib/i18n.ts` is a single 1,663-line flat dictionary keyed by language (`en`/`id`), consumed
through one `translate(language, key, params?)` function everywhere in the tree — no component
hardcodes English strings for engine-facing copy. **EN/ID key parity is CI-enforced**:
`i18n.test.ts` asserts `Object.keys(dict.en).sort()` equals `Object.keys(dict.id).sort()`. Body-
first vs. headline-first render order is itself localized (`BODY_FIRST[language]`,
`VerdictReveal.tsx:128-141`, citing "design doc §3's ID register is body-first"). One rough edge
found: `i18n.ts` still carries `outcome.whatsapp_summary_header` / `outcome.whatsapp_cta` /
`outcome.whatsapp_qr` keys in both languages that **nothing renders** — `ConsentHandoff.tsx`
(the component that actually owns the WhatsApp handoff) hardcodes its own separate `COPY` object
instead of calling `translate()`. Minor, but it means the wizard has two parallel, divergent
copy-authoring mechanisms for the same feature — worth folding into one before the rebuild adds a
third screen that needs WhatsApp copy.

### A.6 — mobile-first?

Yes, by construction, not by assertion. `oracle.css`'s base `.oracle-main` layout is a
single-column grid (`grid-template-columns: minmax(0, 1fr)`); the two-column desktop split (18rem
sticky tree sidebar + content) is added only inside `@media (min-width: 1024px)`
(`oracle.css:225-243`) — the mobile-first direction, not a max-width override bolted onto a
desktop-first base. `LivingTree` ships an explicit mobile pattern independent of the CSS media
query: a collapsible "minimap trigger" button (`oracle-tree-minimap-trigger`) that expands/
collapses the full tree panel below the breadcrumb on small viewports, plus an always-present
screen-reader-only path list independent of viewport. The footer accounts for iOS safe-area
(`env(safe-area-inset-bottom)`, `oracle.css:257-259`). Additional media handling present:
`prefers-color-scheme: dark`, `prefers-reduced-motion: reduce` (twice — CSS and JS, both gating
Framer Motion transitions), `forced-colors: active`, and a dedicated `@media print` block feeding
the `.oracle-print-only` / `.oracle-no-print` class pair used throughout for the printable
verdict summary. This is a materially more complete responsive/accessibility surface than a
typical first pass — the rebuild should treat this CSS layer as largely reusable, not
throwaway.

### A.7 — the live site (partial verification — see the caveat in the header)

No browser-automation MCP resolved via `ToolSearch` in this session (`mcp__claude-in-chrome__*`
was not found, unlike what the brief expected to be available). What could be independently
confirmed via `WebFetch` (`https://balizero.com/visa-oracle`): the route answers, and its
server-rendered content is exactly the English loading string
`"Restoring your private browser session…"` — which matches `OracleShell`'s documented
`hydrated === null` SSR branch (`OracleShell.tsx:163-171`) byte-for-byte, i.e. the deployed build
matches the source read in this pass. `layout.tsx` restores `robots: { index: false, follow: false }`
(re-added 2026-08-23 per the code comment, after an accidental drop in the 2026-08-07 G0–G6
rebuild) — this matches `GROUND.md`'s independent live measurement the same day
(`<meta name="robots" content="noindex, nofollow"/>` present in the served HTML). **Not verified
in this pass**: the actual interactive experience beyond the loading screen — transitions,
question-by-question feel, whether the tree genuinely reads as "crafted" rather than merely
correct. The orchestrator or a follow-on session with browser access should do a real click-through
before signing off on any "elegant, never gaudy" judgment; this document's Part A is a structural,
not an aesthetic, audit.

---

## Part B — the gap against the FROZEN contract

**Correction, narrowed 2026-08-24 after the orchestrator re-checked**: an earlier draft of this
note claimed `docs/plans/2026-08-24-visa-oracle-live/contracts/FROZEN.md` was not on any pushed
branch — that was wrong; a stale/failed `git ls-remote` was over-generalized into a broader claim
than the evidence supported. The true, narrower fact is only: **it is not on `origin/main`** —
correctly so, since `feature/visa-oracle` is a deliberate integration branch that lands as a train
at the end (mandate §3). It **is** pushed to `origin/feature/visa-oracle` and has been since before
this unit started; the path given in the brief was live and this section was read from the real
file. No fix to the mandate is needed here — only to this note.

### The five outcomes, verdict per outcome

| Outcome                   | Designed screen exists?                                                                                                                                                                                                                                                                                                                                | Honest?                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Evidence                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `TEMPORARILY_UNAVAILABLE` | **Yes.** Dedicated section, outage message + conditional retry.                                                                                                                                                                                                                                                                                        | **Yes — never dressed as a result.** `VerdictReveal` uses generic _provenance_ copy only for this state from a non-ENGINE origin (network failure / shadow / preview / client guard) — the one case the code's own comment says "state itself carries no information" (`VerdictReveal.tsx:66-73`). It is visually and textually distinct from a real answer: icon `Info`, headline from `verdict.provenance_headline.<provenance>`, no candidate content anywhere near it.                                                                                                                                                             | `OutcomeSheet.tsx:565-577`, `VerdictReveal.tsx:62-79`, `outcome-fallbacks.ts` |
| `HUMAN_REVIEW_REQUIRED`   | **Yes.** Body copy + full `ReasonList` with per-reason source citations.                                                                                                                                                                                                                                                                               | **Mostly yes, with one real gap.** The copy is honest ("a person's judgment," never invented specifics) and every review-reason code either has curated copy or an honest generic fallback (`GENERIC_REVIEW_REASON`, never a raw code dump) — enforced by an exhaustiveness test per the code comment. But **this is exactly the state where the product most needs a consultant hand-off, and the control is only reachable from the bottom of this same screen** (see the consultant-control table below) — no distinct "we will call you" CTA above the fold.                                                                       | `OutcomeSheet.tsx:517-526`, `engine-adapter.ts:385-421`                       |
| `SUPPORTED_CANDIDATES`    | **Yes, the most complete of the five.** Per-candidate card: legal/operational/service-availability axis badges (never color-alone, per the code's own accessibility comment), reasons with source links, timeline, price (all-inclusive, explicit "no PNBP split" framing matching the owner's R1 pricing ruling), and a checkable document checklist. | **Yes**, and additionally self-defending: `buildValidatedOutcome` throws `RESPONSE_INVARIANT` rather than render if a claimed source is not decisively fresh/primary/verified — the UI cannot show a citation the backend has not actually earned.                                                                                                                                                                                                                                                                                                                                                                                     | `engine-adapter.ts:656-773`, `OutcomeSheet.tsx:266-390`                       |
| `NEEDS_INPUT`             | **Yes.** Lists each missing fact with a message and, where mappable, a direct "Edit" jump back to the exact question.                                                                                                                                                                                                                                  | **Honest but currently closer to theoretical than real** — per `GROUND.md`'s measurement this session, the one reachable user path to a missing fact (the SKIP/"Not sure" affordance) is unconditionally overridden by the backend's disclosed-review-flags adapter into `HUMAN_REVIEW_REQUIRED` before the response ever leaves the server (`gold-oracle-baseline.ts`'s own extensive comment documents this precisely). So the screen is well-built for a state real end-user traffic may never actually reach today — worth confirming with the backend/V1 lane rather than assuming the frontend screen alone closes this outcome. | `OutcomeSheet.tsx:495-515`, `_lib/gold-oracle-baseline.ts:1-45`               |
| `NO_SUPPORTED_PATH`       | **Yes.** Exclusion reasons plus an "alternatives" list that jumps back to a _different_ category (`SELECT_CATEGORY`, never a dead end — this was itself a finding from a prior adversarial review, `flow.ts:836-861`).                                                                                                                                 | **Honest**, and the one state where the interview visibly offers forward motion rather than a stop.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `OutcomeSheet.tsx:528-563`                                                    |

**Overall C1 verdict**: contrary to what a from-scratch rebuild brief would assume, the frozen
clause's failure mode — "renders only `SUPPORTED_CANDIDATES` well and degrades the other four into
one 'something went wrong' screen" — **is not what exists today**. The five states are genuinely,
distinctly, and mostly honestly rendered at the code level. What the rebuild must still add is not
five new screens; it is (a) the honest 38→N narrowing described in A.3, which none of the five
screens currently participate in mid-interview, and (b) the consultant control described next.

### The consultant thread — measured, not assumed

`ConsentHandoff` (`_components/ConsentHandoff.tsx`) is a real, carefully built component: consent-
gated (no WhatsApp destination rendered without an explicit checkbox), minor/guardian-aware
(blocks the handoff behind a second confirmation when `isMinorForHandoff` fires), sends **zero
interview answers** in the WhatsApp message (only state + an opaque assessment reference, matching
the Law 2 boundary FROZEN.md's C3 states for the backend event), and offers both a deep link and a
scannable QR code for a phone-to-desktop handoff. It is good, ready-to-reuse work.

**But it exists on exactly one screen: the verdict screen**, passed in as `OutcomeSheet`'s
`handoffSlot` prop only inside the `current.kind === "verdict"` branch of `OracleShellRuntime`
(`OracleShell.tsx:866-887`). Confirmed by direct grep — there is exactly one import site and one
usage site of `ConsentHandoff` in the whole tree.

**Screens missing the consultant control, checked directly against C3's "every screen — wizard,
verdict, checkout, portal" wording**:

| Screen                               | Has the control?                                                                                                                                                                                | Evidence                                                                                                                        |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Framing (landing / "Start")          | **No.**                                                                                                                                                                                         | `OracleShell.tsx:795-824` — only a resume-opt-in checkbox and the Start button.                                                 |
| Question screens (all ~53)           | **No.**                                                                                                                                                                                         | `QuestionScreen.tsx` renders only the question, options, back/skip — no handoff affordance passed in from `OracleShellRuntime`. |
| Confirmation ("review your answers") | **No.**                                                                                                                                                                                         | `ConfirmationCard.tsx` invocation (`OracleShell.tsx:844-854`) passes no handoff slot.                                           |
| Verdict                              | **Yes**, but bottom-of-page, below the full outcome body, sources, and receipt — not above the fold, not a persistent element.                                                                  | `OracleShell.tsx:873-886`                                                                                                       |
| Checkout                             | **Does not exist yet** (confirmed this session: no `checkout` route anywhere under `apps/mouth/src/app`, and per `GROUND.md`, GARUDA's commerce rails are not on `main` either — V3's premise). | —                                                                                                                               |
| Portal                               | **Does not exist yet** for this product (the existing `apps/mouth/src/app/portal/` is the unrelated client-onboarding portal, not a Visa Oracle screen).                                        | —                                                                                                                               |

**Net**: today's consultant control satisfies zero of the four named screens as an _ever-present_
control. It satisfies one of four screens as a _reachable-eventually_ control, and even there it is
positioned as an afterthought (last section before sources/print/share), not as the standing,
always-visible presence the owner's words ("invokable at ANY moment, including before buying")
call for. This is the single largest, most concrete gap between what exists and what C3 requires,
and the rebuild's #1 structural addition should be: **lift the control (or a persistent, low-key
trigger for it) into the shared shell chrome** — e.g. beside the language/theme toggles in
`oracle-topbar`, which already renders on every `current.kind` — rather than reinventing it once
per screen type.

---

## Part C — the three tiers, and what the UX owes each

Per `TIER-MAP.md` (same integration worktree, prepared for owner switchboard item #4, derived from
the signed `rulepack-prod-013`): **7 products proposed T1, 19 proposed T2, 12 T3** (of which 3 —
E33A/B/C — are _structurally_ T3 forever, not merely unfinished: a self-declared claim to "world
figure" or "special expertise" status cannot be grounded by an interview question). The honest
automatable ceiling of the 38-product catalogue is **31 + 7 consultant-routed**, not 38.

**T1 (self-purchase puro).** What exists today already matches this tier's shape reasonably well:
`SUPPORTED_CANDIDATES` renders price/timeline/documents with no forced human step. What it does
NOT yet do: nothing in the current UI _labels_ a candidate as T1 vs. T2 vs. T3, and there is no
`tier` field anywhere in `visa-oracle-contract.ts` or `outcome-view-model.ts` read in this pass —
the tier map is a document, not yet a wire field. The rebuild needs the tier to arrive on the
candidate itself (or be derivable client-side from a field that does), because tier determines
whether the "buy now" CTA and the consultant CTA are peers or whether one leads.

**T2 (self-purchase + consultant included).** This is the biggest content gap. Nothing on the
current verdict screen distinguishes "you can buy this, and someone will also call you" from plain
T1 self-service — `NEXT_STEPS` (`engine-adapter.ts:47-69`) is a flat, tier-agnostic 3-item list
("Review the decision," "Prepare documents," "Choose whether to contact an advisor") that treats
consultant contact as the applicant's OPTION on every product alike. For T2 the copy must instead
say, plainly, that the consultant contact is _automatic and included_, not a choice — currently
false-neutral framing for 19 of the catalogue's most significant products (D12, E23, E28A, E30A/B,
the whole E31 family, E33/E33E/E33F/E33G, BRIDGING).

**T3 (assisted-only).** The current build has **no dedicated T3 screen at all.** A T3 product
today either (a) never appears as a candidate because it has zero eligibility rules and the engine
can only ever exclude/abstain on it, surfacing as `NO_SUPPORTED_PATH` or `HUMAN_REVIEW_REQUIRED`
with generic copy, or (b), for E28B/C/D/F specifically, is actively **invisible** — per `GROUND.md`,
their sole rule reads a fact (`intent.requested_product_code`) the interview hard-codes to
`NOT_ASKED`, which demotes the product to `BLOCKED_UNKNOWN`, losing to any `SUPPORTED` candidate
rather than surfacing as a recognized, named "this needs a person" case. **The rebuild must add a
genuine T3 outcome shape** — something the current five-state contract does not name: not
"nothing supported" (which reads as a dead end) but "we recognize this case; it goes straight to a
consultant" (which is a _positive_, named result, matching the owner's own words: "the Oracle
recognizes them and routes straight to the consultant. Never an invented answer."). Whether this
is a sixth UI-level state layered on top of `HUMAN_REVIEW_REQUIRED`/`NO_SUPPORTED_PATH` (cheapest:
UI-only, keyed on tier) or a genuine sixth engine state (correct long-term, but reopens the frozen
C1 wire contract) is a design decision for the orchestrator, not this document — flagged here as
the one place where "just build the UI" is not enough; it needs a ruling.

---

## Part D — the rebuild's acceptance, written so it can go red

Falsifiable, runnable statements. Each names what makes it fail, not just what makes it pass.

1. **Five-outcome coverage, adversarially checked.** For each of `NEEDS_INPUT`,
   `SUPPORTED_CANDIDATES`, `HUMAN_REVIEW_REQUIRED`, `NO_SUPPORTED_PATH`, `TEMPORARILY_UNAVAILABLE`:
   a Playwright test drives a real (or fixture-injected) response of that exact state and asserts
   (a) a state-specific heading/body distinct from every other state's copy, (b) zero shared
   generic "error" string across more than one state, (c) for `TEMPORARILY_UNAVAILABLE`
   specifically, no candidate/price/timeline DOM node is present anywhere on the page. **Fails
   if** two states render byte-identical bodies, or if `TEMPORARILY_UNAVAILABLE` ever contains a
   price.
2. **Consultant control, ever-present, mechanically counted.** A single Playwright pass visits
   framing → every question kind at least once → confirmation → verdict (for at least one run per
   outcome state) and asserts a `[data-oracle-consultant-trigger]` (or equivalent stable selector)
   is present and clickable on **every** screen visited, before any purchase-equivalent action.
   **Fails if** the count of screens-with-control is less than the count of distinct screens
   visited — today that ratio is 1/6 minimum (verdict only; checkout/portal don't exist to count).
3. **Tier is a wire fact, not a document.** `visa-oracle-contract.ts`'s generated candidate type
   carries a `tier` (or equivalent, generated — never hand-mirrored per C1's own "no hand-written
   mirror" clause) field, and a snapshot test asserts the UI's CTA copy differs across T1/T2/T3 for
   the same otherwise-identical candidate fixture. **Fails if** T1 and T2 candidates render
   identical next-steps copy.
4. **T3 is a named, positive result — not a dead end.** A fixture representing a structurally-T3
   product (e.g. an E33A/B/C-shaped case, or any product with zero eligibility rules) renders copy
   that says "this route is handled by a consultant" rather than generic "no path found" or
   "review required" text shared with unrelated states. **Fails if** the T3 fixture and a genuine
   `NO_SUPPORTED_PATH` fixture (nothing at all can help this applicant) render the same body copy —
   they must read as different situations to the applicant, because they are.
5. **38 vs. reachable is never conflated in copy.** No user-facing string anywhere in `i18n.ts` (or
   its rebuild successor) states or implies "38 visa types" as something the engine can currently
   conclude on for a given applicant; any product-count language is either exact-and-scoped
   ("N candidates for you," sourced from the real response) or absent. **Fails if** a static "38
   products" claim appears anywhere the interview or verdict screen renders — grep-checkable.
6. **Mobile-first, verified not asserted.** Lighthouse or Playwright viewport tests at 375px width
   (not just "does not break") for: framing, one question of each `kind` (branch/date/number/
   country-codes/status-code/tiles/choice/review-gate), confirmation, and each of the five verdict
   states. **Fails if** any screen requires horizontal scroll, or if the LivingTree's mobile
   minimap trigger is not reachable without scrolling past the primary content.
7. **WCAG AA.** `axe-core` (or equivalent) zero violations at `serious`/`critical` level across the
   same screen set as (6), specifically checking: color is never the sole signal for legal-support
   status (already partially true today via icon+text, per `VerdictReveal.tsx`'s own comment — the
   test should pin this, not just hope it survives a redesign); every interactive tree node has an
   accessible name; focus moves to the verdict heading on reveal (already implemented,
   `VerdictReveal.tsx:58-60` — pin it); `prefers-reduced-motion` removes all non-essential motion
   (already implemented — pin it, do not regress it in the rebuild).
8. **Critic gate PASS on the full journey, on a phone.** Per the mandate's own V2 acceptance
   line: an Opus 5 critic session walks framing → interview → confirmation → verdict for at least
   one T1, one T2, and one recognized-T3 case, on a real or emulated phone viewport, and returns a
   binary PASS/FAIL with named reasons. **Fails if** the critic cannot complete a full journey
   without the reviewer needing implementation knowledge to understand what is happening on
   screen — the bar is a first-time applicant's comprehension, not a developer's.
9. **The two-funnels question is closed, not silently left open.** Either `apps/mouth/src/app/visa/**`
   redirects into `(visa-oracle)/visa-oracle` (with old URLs preserved via redirect, not 404), or an
   explicit, dated decision is recorded that the old funnel is retired on its own timeline and why.
   **Fails if** ignition happens with both funnels still independently reachable and un-reconciled.
10. **`NEEDS_INPUT` is reachable, or it is removed.** `gold-oracle-baseline.ts`'s own header
    documents that the one user-facing path to this state (the SKIP/"Not sure" affordance) is
    unconditionally overridden server-side into `HUMAN_REVIEW_REQUIRED` by the disclosed-review-flags
    adapter before the response ever leaves the backend — a finding independently corroborated the
    same day by a cross-family refuter working the engine side. A CI-runnable test drives the real
    backend path that is supposed to produce `NEEDS_INPUT` (not a hand-built fixture injected past
    the adapter) and asserts the response actually carries that state at least once. **Fails if** no
    such path exists, in which case the rebuild must either wire one (a genuine, reachable
    "we need more from you before we can answer" branch distinct from `HUMAN_REVIEW_REQUIRED`) or
    delete the screen and the state from the five-outcome contract rather than ship a well-built UI
    for an outcome production traffic can never actually produce.

---

## Report

- **Spec path**: `docs/plans/2026-08-24-visa-oracle-live/V2-WIZARD-SPEC.md` (this file), worktree
  `mouth-visa-v2-spec`, branch `agent/nuzantara/mouth/visa-v2-spec`.
- **Five-outcome verdict**: all five have a designed, honest screen today (Part B table) —
  contrary to the brief's working assumption. The real V2 gap is not outcome coverage; it is (1)
  no genuine 38→N narrowing mid-interview (only a 10-category counter), and (2) the consultant
  control's near-total absence outside the verdict screen.
- **Screens missing the consultant control**: framing, every question screen (~53), confirmation —
  3 of the 4 screen types C3 names, plus checkout and portal, which do not exist yet at all.
  Verdict has it, but positioned as an afterthought rather than a persistent presence.
- **Findings that correct the brief**: (a) `contracts/FROZEN.md` is not on `origin/main` (it lands
  with the `feature/visa-oracle` integration train, per mandate §3) — a prior version of this note
  said it was unpushed entirely, which was wrong (a stale `git ls-remote` result, over-generalized);
  it has in fact been on `origin/feature/visa-oracle` since before this unit started, and the path
  the brief gave was live. (b) A second, live, un-audited
  `/visa` funnel (old 4-step wizard + clock + chat) coexists with `/visa-oracle` and is not
  addressed by this mandate anywhere — recommend an explicit consolidation decision before
  ignition (Part D, item 9). (c) No `mcp__claude-in-chrome__*` tool resolved in this session, so
  the live interactive walkthrough the brief asked for is only partially done (route liveness +
  SSR-content match confirmed via `WebFetch`; the actual click-through experience was not
  observed). (d) The mandate's ground-truth numbers (38 products/111 rules, 29/9 reachable-split,
  34/38-never-a-gold-persona) were independently re-confirmed against the orchestrator's own
  `GROUND.md`, not just taken on report.
