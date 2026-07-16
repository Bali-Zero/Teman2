# Visa Oracle v2 — The Decision Tree (Product Design, draft for owner analysis)

> One-line: the diagnostic front door Indonesia's immigration ecosystem doesn't have — a deterministic, signed, government-demoable eligibility engine wrapped in a living-decision-tree experience.

---

## 0. Provenance

This document synthesizes a 3-round multi-LLM research panel run in worktree `mouth-visa-oracle` between
2026-07-17 03:14 and 04:54 WITA, under Zero's mandate: rebuild Visa Oracle as Bali Zero's flagship public
tool — stunning interactive aesthetics, simple/impeccable content (zero wrong answers), authoritative
enough to demo to Ditjen Imigrasi Jakarta, a true expat guide.

Panel: **Gemini 3.1 Pro (High)** — global UX survey (R1) and Indonesian regulatory delta (R2). **GPT-5.6-sol
(ultra)** via Codex — architecture + adversarial red-team (R1) and full engine concretization (R2, ~110KB
spec). **GLM 5.2** — design-language (R1) and behavioral-interview design (R2). **Sonnet, web-grounded** —
live-fetched verification of government wizards (R1) and reuse-first OSS survey (R2). **Opus 4.8 (xhigh,
fresh context)** — R3 arbiter on the one open architecture question (custom evaluator vs. GoRules ZEN),
generator≠grader. **DeepSeek V4 Pro** — seat was DEAD throughout (balance -0.04 USD); substitute was the
house Sonnet web-grounded lane; not consulted, open item in §10.

Eleven research artifacts live under `research/visa/2026-07-17-*` in this worktree (index in §12). Every
load-bearing claim below is either a direct synthesis of those files or a fact the orchestrator
spot-verified on disk in this same session. This is a **draft for owner analysis**, not a final spec — per
the corner mandate (`.claude/skills/visaoracle/SKILL.md`), work stays worktree-only until Zero reviews it.
That is a deliberate firebreak (business-shape/sequencing = Legge 5), not a stalled ship-lifecycle.

---

## 1. Product thesis & positioning

**The gap is measured, not assumed.** The web-grounded lane live-fetched
`imigrasi.go.id/wna/permohonan-visa-republik-indonesia` and found **zero wizard**: a flat alphabetical list
of 100+ text links, no filter, no search — in either language. GOV.UK, Canada IRCC, and Australia Home
Affairs all ship a wizard; Indonesia ships none.

**The official ecosystem is a processing engine; Visa Oracle is the diagnostic engine.** evisa.imigrasi.go.id,
Molina, and M-Paspor assume you already know which visa you want. Positioned correctly, Visa Oracle is the
**front door that serves clean applications to their system** — not a competitor. _"We guide them
perfectly, so your system receives perfect data."_

**This aligns with, not against, Ditjen Imigrasi's own posture.** Its 2026 framing is explicitly "digital
immigration ecosystem" + digitalization-as-anti-corruption (live-fetched, R1). A live signal of appetite: the
official visa-list URL supports an undocumented `?golden_visa=1` filter — category-filtering backend already
exists, never exposed as UI. If a partnership ever happens, the ask is "expose this," not "build new infra."

**The moat is visible honesty, not the quiz.** GLM R1: _"the product's moat is the visible, citable
separation of official truth from agency service. No one in this market does that cleanly."_ Concretely:
fees always shown split (official PNBP vs. Bali Zero fee, never blended); every skip surfaces its
conservative assumption on a dated honesty receipt; every fact carries a pinpoint citation and effective
date; the system visibly abstains rather than guesses.

**The contract is narrower than "zero wrong answers."** In a system that regulatorily moves every 3-4
months (§6), that guarantee isn't honest. The Codex R1 contract, verbatim: **"Zero unsupported
recommendations."** Deterministic and reproducible; every decisive condition sourced; unknown/conflicting/
stale facts produce abstention, never a guess; an LLM may explain an approved result but never select, add,
remove, or rank paths.

**Three concepts the engine must never collapse:** (1) **Legal eligibility** — what regulations permit; (2)
**Operational availability** — what eVisa/an office can currently process; (3) **Bali Zero service
availability** — what Bali Zero is willing/able to handle commercially. A path can be legally possible but
operationally unavailable, or legal while Bali Zero simply doesn't offer it.

---

## 2. What exists (v1) and what survives

**v1 is live, not missing** — `www.balizero.com/visa`, last commit 2026-07-14, 29 commits/90d. "Rebuild"
targets the experience + content + correctness layer, not a greenfield build
(`round1-repo-map.md`).

**Frontend** (`apps/mouth`, Next.js 16/React 19, Subhi's surface): branch-selector → `/visa/clock` (expiry
countdown) or `/visa/match` (4-step wizard, decision tree in `quiz-logic.ts`, 84 lines/7 purposes); AI chat
layer `VisaChat.tsx` on top; hash-shareable results; Playwright E2E exists.

**Backend** (FastAPI, `router_registration.py`): `visa_check.py` (`/api/visa`), `visa_oracle.py`
(`/visa-oracle`), `knowledge_visa.py` (catalog CRUD, backs MCP tools). Services: `match_tree.py`
(deterministic tree), `visa_oracle_service.py` (keyword scoring), `visa_unified/bridge.py`. Full pytest
coverage exists — it tests the wrong contract.

**Data:** `migrations_v2/124_visa_checks.sql` (hash URLs); seed script carries **114 visa codes** as the
current canonical catalog; Qdrant `visa_oracle` collection ~90 curated points.

**Reuse-first candidate #1: `packages/core/` (`@balizero/core`)** — `AppFrame`/`AppWizard`/
`AppBranchSelector`/`useFunnelApp`, proven across visa/property/tax funnels. Needs hardening (§5.6), not
replacement. Also reusable: `DecisionTree.tsx` (553 lines, generic tree primitive).

**Why "rifatto daccapo" on the engine, not the frontend:** the orchestrator spot-verified 5 Codex P0 claims
directly on disk (`round1-verification-note.md`), all CONFIRMED:

1. `match_tree.py`: literal `del nationality  # reserved for future visa-waiver rules` — nationality
   collected then discarded.
2. `visa_oracle.py` (~L699): an ABSTAIN state is promoted to a recommendation via model pretraining +
   system prompt for obsolete-code mentions.
3. `pricing_bridge.py`'s `_SEARCH_HINTS` fuzzy-matches a D2 fee onto the D12 price row via substring.
4. `ConsentBanner.tsx`: single "By continuing... Got it" acknowledgement, not purpose-specific consent.
5. `migration_080a_visa_oracle_sessions.py` header claims "No PII stored" while storing nationality/family
   data (personal data under UU PDP).

Consequence adopted here: the rebuild is not aesthetics-only. The deterministic core must be rebuilt for
"content impeccabile" to be an honest claim.

**Delete list** (full file-by-file verdicts in §5.6 / Codex R2 §8): `match_tree.py`, `pricing_bridge.py`,
`visa_oracle_service.py`, `quiz-logic.ts`+test, `ConsentBanner.tsx`, `seed_visa_types_complete_2026.py`
(retired from ops, kept as historical migration). Nothing deletes until `rg` confirms zero imports (Gate 4).

---

## 3. The experience

**Metaphor trio** (GLM R1 design-language): (1) **PRIMARY = the living decision tree** — the product _is_
a tree; showing it as the thing is honest, scales to ~110 visa types, reads as rigorous to a government
audience, stacks vertically on mobile, gives the "tree breathes/prunes" interaction for free. (2)
**SECONDARY atmosphere = restrained constellation/star-map** — carries the "Oracle" theme without
fortune-telling risk; mood only, never the data structure. (3) **TERTIARY tile = the card**, reserved for
the outcome, never navigation. A **3D overworld** (an earlier memory-surfaced concept) was explicitly
**rejected** — poor mobile perf, gimmick, gov-credibility liability. "Oracle" = wise guide, not fortune
teller.

**GOV.UK is the credibility skeleton** (live-fetched, R1): "Check a service is suitable" (intro → simple
questions → auto eligibility → results, never dead-ends) + "Question pages" (one per page, mandatory Back
link, hint = one short sentence). GOV.UK also ships `/visualise` — the whole tree as a diagram; steal
directly for internal QA and the Ditjen demo (§7, xyflow+elkjs).

**Hybrid flow: discovery → confirmation → verdict.** One-question-per-screen for branching discovery, then
a **grouped, editable "your answers" confirmation card** before any verdict (stolen from Stripe onboarding
— gives government-credibility transparency, kills the Typeform "I can't see what I said" trap). No fake
linear % bar on a variable-depth tree. Instead: a **"paths remaining" counter** ("12 → 3 → 1"), paired with
the tree-prune animation (dual visual+numeric encoding, an accessibility win too), plus a branch-aware
breadcrumb. Progress is hidden through Q1-Q2, revealed once the user is committed.

**"Why we ask"** on every sensitive question — a disclosure glyph revealing one sentence + the mapped
regulation. The panel calls this the government-demo armor.

**Skip-with-assumptions → the honesty receipt.** A "Not sure?" affordance takes the conservative branch and
visibly flags the assumption on the outcome page — momentum without hidden uncertainty.

**Ten signature interactions** (feasibility in parens): tree breathes — ineligible branches fade/curl
(medium, FLIP); paths-remaining counter (easy); "why we ask" whisper (easy); "Oracle deals your card" —
verdict node detaches into a hero card (medium, shared-element transition); honest ledger — fees slide
apart to a total (easy-medium); rewritable path minimap, tap any past answer, never "start over" (medium);
timeline anchored to today (easy); QR handoff to WhatsApp with session pre-loaded (easy); assumptions
surfaced as a dated receipt (easy); regulation-verified watermark (easy to render; the freshness pipeline
behind it is medium ops, §5.8). Throughline: interactions 3/5/9/10 all express **visible honesty**, the
product's real moat; 1/2 are a paired narrowing-encoding; 4/6 are craft flexes; 7/8 are the business bridge.

**Outcome-page anatomy, top to bottom:** verdict headline (single strongest path, or "3 paths fit — here's
the strongest"); eligibility card, never binary — 4 states (Eligible/Likely/Conditional/Likely not), color+
icon+text never color-alone; visa comparison table when ≥2 fit; personalized timeline anchored to TODAY,
honest ranges never false precision; **the honesty ledger** — official vs. agency fees, two columns, never
blended, cited; document checklist, checkable, downloadable; "your next 3 steps," concrete and time-bound;
share/print/PDF; **QR → WhatsApp**, session pre-loaded; assumptions & caveats footer, dated, with
"regulations verified as of \<date\>" and the mandatory Ditjen-decides disclaimer.

**Motion: encode navigation, never decorate.** Test: if removing a motion makes the app harder to
understand, it earned its place. Earns it: FLIP branch prune, ticking paths-remaining count, spring-staged
verdict reveal, skeleton states (never spinners). Cut: parallax, auto-rotating testimonials,
cursor-chasing particles ("reads as a 2010 portfolio site and kills gov credibility"). Stack: View
Transitions API for cross-question nav, a motion library for springs, shared-element tree-to-card morph,
subtle haptics on 1-2 key commits only, full `prefers-reduced-motion` everywhere.

**EN/ID co-first-class**, never ID-as-translation — ID uses Imigrasi's own terminology natively (a
deliberate credibility signal). Answers persist in a language-agnostic shape (keys, never localized
strings) so a mid-funnel language switch is instant, no lost history.

**WCAG AA target, AAA aspiration on the critical path** — full keyboard nav, live-regions announcing the
paths-remaining count and verdict reveal, a non-visual equivalent for the tree (nested list/SR-only path
description), plain language (~grade 8).

**Theming: dark + light, default light for the Jakarta demo** — dark reads premium/oracle, light reads
clean/government; both fully contrast-compliant.

**Anti-patterns:** no fake linear progress bar; never blend official/agency fees; no literal
tarot/fortune-telling visuals; no 3D overworld/parallax/cursor-chasing particles; no forced login to see a
result; no autoplay; never hide assumptions or caveats — they're the credential.

---

## 4. The interview

Source: `round2-glm-interview-design.md`. **Note: every ⚑-flagged code/threshold predates the 110-index
reclassification (§6) and needs one NB-INTEL Immigration grounding pass before content finals.** The
deliverable here is interview _logic and copy_, deliberately decoupled from exact codes.

**Framing card, before Q1:** _"Visa Oracle is a map, not an application. Answer honestly, including 'I
don't know' — nothing here is filed, nothing decided for you."_ Lowers the stakes so people answer
truthfully (the TurboTax insight: if it feels like a test, people cheat).

**Q0 stays the master branch, but a date drives onshore lanes, not a bare yes/no.** "Are you in Indonesia
right now?" carries more downstream weight than any other question — offshore, a visa is a plan; onshore,
it's a countdown, and the catalog itself narrows to what's convertible. A "yes" is immediately followed by
"When does your current stay permit expire?" (date picker), routing four lanes:

| Days remaining  | Lane                       | UI tone                                             |
| --------------- | -------------------------- | --------------------------------------------------- |
| Already expired | Overstay-help              | Reassuring, straight to human review, no alarm copy |
| 1-7 days        | Bridging / urgent extend   | Amber, expiry tile prominent                        |
| 8-60 days       | Extend or Convert          | Neutral, full choice                                |
| 60+ days        | Convert / Extend (planned) | Neutral planning                                    |

**Bridging Visa** (60-day onshore transition, Permenkumham 11/2024) is flagged as **the under-marketed lane
Bali Zero should own** — live, active, under-covered by every competitor reviewed. Overstay-help is never
algorithmic — always human-review, statutory fine stated as information, with the reassurance "Overstay is
fixable. It is not the end of your story here." Three honest escape valves off Q0 (dual citizen / just left
and need to return / on a visa run) surface a clarifier and, if unresolved, route to human-review — never
forced into a clean onshore/offshore box.

**Ten categories, category-first, narrowed from Australia's model:** Tourism & short visit · Business (no
work) · Work & employment · Invest & golden · Remote worker · Family & marriage · Retirement & second home
· Study · Diaspora & ex-WNI · Something else (mandatory, same tile weight — GOV.UK's "never dead-end" at
the top of the funnel). Category is a **soft** router — narrows but never kills cross-category candidates
until the behavioral tree confirms.

**Behavioral doctrine (TurboTax, not the DMV):** never ask "do you need a D13"; ask "will an
Indonesian-registered company employ and pay you here?" Three drafted trees:

- **Work & employment (5q modal).** Splitter: who pays you, is the payer Indonesian? Role class refines the
  fee band; the passport question doubles as the calling-visa screen; a shared review-gate (criminal
  record, health, prior refusal, overstay, blacklist — any non-"None" forces `HUMAN_REVIEW_REQUIRED`, no
  verdict); duration; optional shared family question.
- **Invest & golden (6q modal).** Splitter: capital / merit / family-link / property-backed; investment
  vehicle; amount band (below floor → `NO_SUPPORTED_PATH` for Golden specifically, but the outcome offers
  Second-Home/Retirement/business/Remote alternatives — never a dead end); active-involvement (passive
  assumed on skip); an investor-tuned enhanced-due-diligence gate (source-of-funds, PEP, sanctions, dual
  citizenship — any flag → review); duration tier. **The villa-leasehold honesty note lives here** —
  directly translating Bali Zero's own scar (cicatrix family #3, W68 zoning): a residence permit tied to
  property does not confer land ownership; foreigners cannot hold freehold, only leasehold/use-right. The
  panel frames this as turning an internal scar into a design feature: "we tell you the truth your villa
  broker won't."
- **Remote worker (5q modal).** Splitter: where clients/employer sit — foreign clients+pay+Indonesia
  presence = tolerance; Indonesian clients/pay = employed here, a different lane. Income floor (below floor
  → downgraded honestly, not killed). A genuinely novel move: a **tax question asked as a courtesy, not a
  gate** — "Crossing about 183 days can change your tax status. That's not a gate — it's something you
  deserve to know before you choose." Nothing disqualified; surfaced as a consequence on the outcome.

**Shared review-gate ★ and family ★** are identical across lanes by design — built once, composed
everywhere. Human-review fires non-negotiably on: dual citizenship, calling-visa nationality, minors, mixed
marriage/divorce, diaspora complexity, overstay/refusal/blacklist, criminal/health flags, diplomatic
passports, ambiguous sponsors, activity-boundary cases, multi-purpose trips, onshore conversion, investor
PEP/sanctions flags. Load-bearing rule: **on "not sure," never guess on money, payer, or clients — hold for
a human.**

**Handoff-screen principles:** no fabricated urgency, no alarm color beyond warm amber, no penalty mention
unless the user surfaced an overstay themselves (and even then, informational), reassurance always present
("you're not in trouble, and you're not starting over"). ID leads with the body, not the head — formal ID
register reads headline-assertions as bureaucratic, a genuine structural divergence, not just vocabulary.

**Confirmation card** — the honesty receipt made visible: "Here's what you told us" (grouped, editable);
"Assumptions we made" (only if skips occurred, each with inline Edit); a two-line preview that fees will
show split, never blended; the final paths-remaining count; CTA "See my options."

**Five outcome-copy skeletons**, one per decision state — single winner, 2-3 trade-offs (no fake
"recommended" badge without a real stated reason), `HUMAN_REVIEW_REQUIRED`, `NO_SUPPORTED_PATH` (three
mandatory "what instead" blocks, never a bare "no results"), `TEMPORARILY_UNAVAILABLE` (no invented dates,
no "coming soon" theatre).

**Ten microcopy rules:** name the situation not the code in headlines; state what a permit does _and_
doesn't; never blend fees, anywhere; make "I don't know" first-class and rewarded; explain consequences,
never threaten penalties; plain verbs over bureaucratese; no gamification/scores/badges — the counter is a
fact, not a celebration; reassure before redirecting; say plainly when a regulation is unclear/changing;
address the reader directly and warmly (_Anda_, never _kamu_).

---

## 5. The engine

Source: `round2-codex-engine-concretization.md` (~110KB spec) and `round3-opus-arbitration.md`.

### 5.1 Build vs. buy, closed

R2's reuse survey found GoRules ZEN (MIT, Rust core) could save an estimated 25-30% of the evaluator-core
build, flagged unresolved because ZEN's hit policies are `first`/`collect` only with no documented
three-valued semantics. Opus 4.8 (xhigh, fresh context, generator≠grader) arbitrated in R3, independently
re-confirming from primary sources that ZEN supports only `first`/`collect` and evaluates unary tests to
plain boolean, no tri-state. **Verdict: build the custom Python evaluator (confidence 0.85).** Core
reasoning: the two semantics this product needs — **UNKNOWN as first-class tri-state** and
**COVER_ALL_DECLARED_PURPOSES as a native hit policy** — don't exist in ZEN, so wrapping it still means
writing both in a Python layer around it: the dangerous logic ends up in the wrapper anyway while ZEN
degrades to a table-matcher — a second-truth-layer, one seam to get wrong. For a government-auditable
product, a single-artifact chain (signed RulePack → AST → canonical trace → source ref, all Python/JSON)
beats forcing an auditor to trust a JDM-graph-plus-wrapper seam and a Rust binary's undocumented semantics.
The claimed 25-30% saving is real only on the cheapest module and roughly zero-to-negative once
JDM-compile/tri-state-glue/trace-reconciliation are counted. ZEN as core executor is the highest-lock-in
option on the table; as authoring-only, near-zero.

**Disposition: ZEN demoted to authoring/visualization only**, never a runtime dependency. Kept: the JDM
visual graph, rendered _from_ the signed RulePack for the Jakarta demo/internal review; optionally, the JDM
editor as an authoring aid compiling _to_ a signed RulePack, never a runtime source of truth. The arbiter
names its own strongest counter-argument honestly — a hand-rolled evaluator is exactly the class of bug
that becomes a wrong legal answer with no upstream users to catch it first — and answers it with **test
investment**, not reconsideration: metamorphic + property-based tests over the truth tables and set-cover,
on top of the gold harness (§5.7).

### 5.2 Module layout and core types

`apps/backend-rag/backend/services/visa_engine/` becomes the **only recommendation authority** — Qdrant and
LLMs may explain a persisted decision, never determine eligibility, candidates, rank, or price. Modules:
`enums.py` (TruthValue, DecisionState, RuleStage, EngineMode, EngineSurface), `models.py` (frozen Pydantic
v2, `extra="forbid"`), `fact_registry.py`, `ast.py`, `bundle.py` (signing/verification), `compiler.py`,
`evaluator.py`, `trace.py`, `pricing.py`, `catalog.py`, `clock.py`, `repository.py`, `crypto.py`,
`consent.py`, `retention.py`, `flags.py`, `compat.py` (v1 adapters), `service.py`, plus JSON Schema 2020-12
contracts per core object.

**`ApplicantFacts`** types every fact as `KNOWN` or `UNKNOWN{reason}` — no silent "not provided" hiding
outside the type system. **The condition AST** supports 15 operators (`all`/`any`/`not`/`known`/`unknown`/
`eq`/`neq`/`lt`/`lte`/`gt`/`gte`/`in`/`not_in`/`between`/`intersects`/`contains_all`) — no arbitrary
Python/JS/regex/LLM predicates inside a RulePack; a closed, audited vocabulary by design.

### 5.3 Four stages, decision states, precedence

Every rule belongs to one of four stages in strict order: `HARD_FILTER` (any true excludes the product),
`HUMAN_REVIEW` (any true forces `HUMAN_REVIEW_REQUIRED`, no candidate emitted), `ELIGIBILITY` (support
rules' `covered_purposes` must union to a superset of declared purposes — `COVER_ALL_DECLARED_PURPOSES`),
`RANKING` (only on `SUPPORTED` products, integer points, commercial facts only, legal facts forbidden). No
short-circuit — all children evaluate so the trace stays complete.

Global result is exactly one of `NEEDS_INPUT`/`SUPPORTED_CANDIDATES`/`HUMAN_REVIEW_REQUIRED`/
`NO_SUPPORTED_PATH`/`TEMPORARILY_UNAVAILABLE`, in that precedence (unavailable-pack fails closed first;
review beats supported; supported beats needs-input; needs-input beats no-path). Pricing failure never
changes legal state — a distinct `UNAVAILABLE` quote status instead.

**"Unknown can't increase eligibility" is structural, not a rule that could be forgotten** — a support
rule's `covered_purposes` join the coverage union only when it evaluates `TRUE`; `UNKNOWN` is simply inert
for coverage, so it can only leave a purpose uncovered or block, never manufacture eligibility. No
sentinel, no coercion path.

### 5.4 Signed bitemporal RulePacks and the database

RulePacks are signed offline with **RFC 8785 canonicalization + Ed25519** — the private key never touches
the production process; the runtime holds a pinned public-key trust store; a pack cannot supply its own
trusted key. Activation rejects any sequence ≤ current, any `previous_payload_sha256` mismatch, or a
revoked/expired key — anti-rollback by construction. Rollback means signing a _new_, higher-sequence bundle
wrapping a previously-approved payload — never re-enabling an unsafe legacy path.

The schema is genuinely **bitemporal**: `legal_period` (when a rule was legally true) tracked separately
from `system_period` (when Visa Oracle knew it), via Postgres range types with `EXCLUDE USING gist`
constraints — overlap is structurally impossible, not just application-checked. Core tables:
`visa_rule_packs`, `visa_ruleset_activations`, `visa_source_records`, `visa_consent_receipts`,
`visa_decisions`, `visa_decision_payloads` (encrypted AES-256-GCM), `visa_price_quotes`,
`visa_clock_snapshots`, `visa_public_results`, `visa_session_exchanges`. Rule packs, decisions, quotes, and
consent receipts carry **append-only triggers** — `UPDATE`/`DELETE` raises at the database level, not just
in application code. `ApplicantFacts` payloads: encrypted, 90-day retention; minimized decision envelope:
24 months; runtime grants permit `INSERT` on decisions but never `UPDATE`/`DELETE`.

### 5.5 The evaluator algorithm and its trace

Product proof runs hard-filter → human-review → eligibility per product, returning one of `EXCLUDED` /
`REVIEW` / `BLOCKED_UNKNOWN` / `SUPPORTED` / `UNSUPPORTED`. The trace is not reconstructed after the fact —
it's a byproduct of the same evaluation pass that decides, ordered deterministically by
`(stage_order, priority, rule_id, product_version_id, signed_child_index)`; `trace_sha256` is computed over
the canonical JSON of that ordered structure. This is the arbiter's central win over any wrapped-engine
option: one code path produces both the decision and its faithful trace, so there is no seam where they
could diverge.

### 5.6 Strangler migration and the JWT-from-hash fix

Per-surface flags (`VISA_ENGINE_CLOCK_MODE`, `_MATCH_MODE`, `_RECOMMEND_MODE`, `_CATALOG_MODE`,
`_CHAT_CONTEXT_MODE`, `_HANDOFF_MODE`) each take `OFF | SHADOW | ENFORCE`; effective mode is the _minimum_
of the environment ceiling and the DB-controlled rollout — missing/invalid config always resolves to
`OFF`, never `ENFORCE`. Critically, `OFF` does not mean "run the unsafe legacy path unchanged": before Gate
1, v1 inputs must return a safe `NEEDS_INPUT` or review-only response — the safety freeze (PR0, §9) is
decoupled from the full rollout and ships first. Existing endpoints keep their paths; the strangler adds
fields rather than breaking contracts.

**A structural fix threads several endpoints: today, a public result hash issues a fresh chat JWT to
anyone holding it** (Codex R1 P0, `visa_check.py:314`, ironically covered by a passing test that treats the
bug as correct). Replacement: result creation returns a one-time `session_exchange_token`; the frontend
exchanges it once for a same-origin `HttpOnly`/`Secure`/`SameSite=Strict` capability cookie; public GET
never returns a token again, and the public DTO omits raw nationality/investment/family/status/overstay
facts — a hash becomes a read-only pointer, not a capability.

**Clock history needs an explicit backfill, not a silent cutover** — the current GET reconstructs results
with _current_ code against historical inputs (a subtle correctness bug: a past result can silently change
if the logic changes). Freeze as `legacy_clock_v1.py`, backfill every historical row into
`visa_clock_snapshots` with an explicit `algorithm_version` tag, diff old vs. backfilled output, switch the
GET to read the snapshot, delete only once zero rows are unresolved (retain indefinitely otherwise).

On the frontend, `AppWizard`'s `onComplete` is currently synchronous and clears storage _before_ an async
persistence request can succeed (verified on disk: `AppWizard.tsx:26`) — a real data-loss bug shared across
visa/property/tax funnels. The strangler hardens it to async `onComplete` with a pending/double-submit lock
and state cleared only after confirmed persistence.

### 5.7 Verification: gold harness + the arbiter's named mitigation

The harness starts with **20 personas** covering the load-bearing edges: an Indonesian citizen (no path);
conflicting-citizenship evidence (review); a calling-visa nationality (review); active overstay (review,
never a verdict); a minor without a confirmed guardian (review) vs. with one (supported); a spouse case
with unverified marriage registration (`NEEDS_INPUT`, not a guess); onshore-conversion attempts (review);
remote-work with Indonesian clients (review) vs. unknown client location (`NEEDS_INPUT`, not an
assumption); multi-purpose trips where adding a prohibited purpose never improves the result; an investment
amount just below the fixture minimum (`NO_SUPPORTED_PATH`, alternatives offered — never a bare dead end);
an obsolete product-code request that still resolves correctly with a notice. Every case asserts exact
state, candidate order, reason codes, and **deterministic trace equality across repeated runs**.

This is the concrete answer to the strongest argument the arbiter raised against its own verdict (§5.1): 20
gold personas alone wouldn't be enough evidence a hand-rolled tri-state evaluator is safe. The spec pairs
the harness with **metamorphic and property-based tests** over the truth tables and set-cover directly —
"unknown cannot increase eligibility," "a prohibited activity cannot improve a result," "a price change
cannot change legal eligibility," "same facts + ruleset always produce the same trace" — each tested across
generated inputs, not just 20 fixed cases. This is the test-investment mitigation the arbiter named as the
correct response, not a reconsideration of build-vs-buy.

### 5.8 The regulatory update pipeline

Because the regulatory landscape moves roughly every 3-4 months (§6), this pipeline is core product, not
maintenance overhead. Ten steps (Codex R1 §5.1): monitor sources separately (BPK/JDIH, Kemenimipas/
Imigrasi, eVisa, Kemenkeu) → snapshot every artifact (hash, signed PDF, retrieval time) → detected change
becomes a **quarantined candidate**, never auto-publishing → semantic diff → classify P0/P1/P2 impact → an
analyst authors the change, a **second, independent reviewer** verifies interpretation and citation
(four-eyes) → impact simulation over the full gold corpus → compile and sign (schema validation,
gap/overlap detection, full suite, reviewer signatures) → **activate atomically** — engine, API, UI, SEO,
translations, cache tags all switch to one ruleset ID in one transaction → verify in production, retain
one-click rollback. Immediately-effective P0 changes put affected routes into `TEMPORARILY_UNAVAILABLE` or
`HUMAN_REVIEW_REQUIRED` until reviewed — graceful degradation, never a confident stale answer.

Every result carries an explicit freshness stamp in substance: _"Evaluated with ruleset `2026.07.09-1`,
sources verified 17 July 2026 14:20 WITA. The controlling change became effective 9 July 2026."_ Vague
"up to date" badges with no timestamp/scope are disallowed.

---

## 6. Content plan

Source: `round2-gemini-regulatory-delta.md`. This is the **first content task**, prerequisite to any final
interview copy, because it changes which codes exist.

**The 110-index frame.** `Kepmen M.IP-08.GR.01.01/2025` (promulgated 2 May 2025, effective 2 June 2025)
revoked the old classification and consolidated 133→110 codes, keeping the alphabetical taxonomy: A=BVK,
B=30-day VoA, **C absorbs legacy `B211A/B/C` entirely** (C1 Tourism/Family/Medical, C2 Business), D=
multiple-entry visit, E=Limited Stay/ITAS (E28 Golden, E33 Second Home stay active), F=special/regional
VoA. **If the current 114-code seed still carries both `B211*` and its `C`-series replacements, it holds
~4 legacy overlaps needing reconciliation** — `VERIFIED-OFFICIAL` confidence.

**BVK is now nationality-only.** `Permen Imipas 10/2026` (effective 9 July 2026) removed the "holders of
certain stay permits" clause; added Turkey, Brazil, Peru, Kazakhstan, Macau, Belarus. Any rule still
allowing BVK via a held foreign permit needs stripping.

**The guarantor layer changed underneath sponsor questions** — `Permen Imipas 5/2025` revoked
`Permenkumham 36/2021`'s penjamin rules; legacy validation tied to the 2021 reg needs retiring, not
supplementing.

**The diaspora regime is live and distinct** — `Permen Imipas 3/2025` (effective 6 May 2025) covers ex-WNI,
descendants, foreign spouses, mixed-marriage children, with dedicated ITAS products graduating to
indefinite ITAP. Already its own interview category (#9, §4) rather than folded into ordinary routing.

**Bridging Visa (`Permenkumham 11/2024`) is active and under-covered by competitors** — 60-day onshore,
non-extendable, filed ≤3 days before expiry, voided if the holder leaves Indonesian territory. Recommended
as a first-class, well-marketed lane (echoed in §4).

**Calling-visa is an 8-nation procedural overlay, never a separate visa class** — Afghanistan, Guinea,
Israel, Cameroon, North Korea, Liberia, Nigeria, Somalia require onshore clearance layered on top of
whatever product they'd otherwise qualify for; the engine applies it as an overlay (§5.3), never invents it
as its own code.

**Golden Visa social proof is citable and dated — R1/R2 discrepancy arbitrated.** R1's web-verified lane
live-fetched **1,274 visas / Rp52.1T investment realized, as of 2026-05-18** (E28D alone Rp50.88T),
multi-source (imigrasi.go.id + Antara + CNN), marked `VERIFIED-OFFICIAL`. R2's regulatory-delta lane,
working a narrower search pass, flagged the same stats `[UNCERTAIN]`. Orchestrator ruling: R1's figures
stand — the R2 flag reflects search-pass narrowness, not a contradiction.

**Regulatory cadence is the real constraint.** Six confirmed events in ~24 months (Permen Imipas 10/2026,
Kepmen M.IP-08 2025, Permen Imipas 3/2025 and 5/2025, PP 45/2024, Permenkumham 11/2024) — a major event
roughly **every 3-4 months**. A static engine rots within a quarter; direct justification for building the
update pipeline (§5.8) as day-one infrastructure, not a "we'll get to it" task.

---

## 7. Reuse plan

Source: `round2-reuse-first-oss.md`, live-verified via GitHub API.

**ADOPT:** `@xyflow/react` (MIT, 37.7k stars) + `elkjs` (EPL-2.0, safe unmodified dep) — ~85-90% of the
`/visualise` ~110-node tree view. `jsonschema` (Python Draft 2020-12) — canon-mandated for the RulePack
contract. `react-jsonschema-form` (RJSF, Apache-2.0) — **internal tooling only**, never the client wizard.
GoRules JDM Editor (MIT) — optional authoring-only aid per the R3 arbitration carve-out; ZEN itself is
**not** adopted as a runtime dependency in any form.

**IMITATE (patterns, not deps):** `alphagov/smart-answers` — the Flow/Question/Outcome node model, frontend
walking the same graph the evaluator evaluates. `alphagov/govuk-frontend` — accessibility mechanics
(mandatory back-link, one-question-per-page markup). `red6/dmn-check` — the gap/overlap-detection
_algorithm_, ported over our own AST. OpenFisca/PolicyEngine's time-versioned parameter-tree concept — our
bitemporal model is already a superset. MyFriendBen — the clean pattern for consuming an AGPL engine over
HTTP, kept on file in case ever needed.

**SKIP:** OpenFisca/PolicyEngine as direct deps (AGPL, blocked); Blawx (stale 20mo); 18F
eligibility-rules-service (archived); `json-rules-engine`/`durable_rules` (JS-only/stale); XState wizard
libs (redundant vs. proven `AppWizard`); **Stepperize — 1,586 stars but no LICENSE, legally unusable
regardless of popularity**; `d3-hierarchy` (redundant vs. xyflow+elkjs); Mermaid for the live tree (caps
~30-40 nodes, fine only for small docs).

**Net:** ~30-40% of the combined engine+wizard build, concentrated in scaffolding (schema validation,
visualization), not in the tri-state/coverage/trace logic — consistent with R3's finding that the
regulatory-specific parts remain custom by necessity. The frontend wizard sees close to 0% external
reuse — `@balizero/core` already covers that ground.

---

## 8. Trust, privacy, and the government demo

Source: `round1-codex-architecture-redteam.md` §6. **Visa Oracle must never claim "no PII."** Under UU
27/2022, nationality and marital status are personal data; criminal/health/biometric/financial data get
heightened treatment; an IP address can identify combined with other data — this directly corrects the
current live claim (§2, P0 #5) with an honest one, not a smaller one.

**Anonymous evaluation by default** — no account/phone/email required to see or export a result; structured
answers preferred over free text; no passport number, scan, criminal narrative, or medical detail collected
in the public wizard.

**Purpose-specific consent, three separate unticked checkboxes, after the result** (fixing the current
single "By continuing... Got it," §2 P0 #6): share the case summary for consultant review; receive a
WhatsApp service message; receive marketing. Necessary technical processing is described under its actual
lawful basis, never disguised as marketing consent.

**Disclaimer hierarchy, four facts inline:** private decision-support tool, not a government service;
result based on facts entered + the cited ruleset at a stated date; not an approval or guarantee; complex
cases go to human review. Blanket "we accept no liability for anything" language is avoided — it signals
distrust in the product, undercutting §1's honesty thesis.

**The government demo runs as a separate tenant**, not a flagged production mode: synthetic personas only;
persistent `DEMO — NOT OFFICIAL` banner; no CRM/marketing/WhatsApp/session-replay/upload; no government
logo or implied endorsement; no search indexing; expiring access, isolated audit logs; a visible source
ledger with old/new ruleset replay; and, deliberately, an **"abstention demonstration"** — the system
refusing an unsafe case live, because a system that never says "I don't know" in front of regulators is
one nobody in that room should trust.

---

## 9. Delivery plan

Source: `round2-codex-engine-concretization.md` §9, cross-checked against R1's Gate 0-4 structure.

|  PR | Increment                                                                                        | Est. | Gate              |
| --: | ------------------------------------------------------------------------------------------------ | ---: | ----------------- |
|   0 | Safety freeze: 5-state responses; remove ABSTAIN promotion; stop trusting client-supplied prices | 3-4d | Gate 0            |
|   1 | Pydantic contracts, JSON Schema export, AST, fact registry, compiler limits                      | 4-5d | Gate 1 partial    |
|   2 | RFC8785/Ed25519 verification, trust store, anti-rollback, offline signing scripts                | 3-4d | Gate 1            |
|   3 | Pure evaluator, deterministic trace, first 20 gold cases, metamorphic tests                      | 5-7d | Gate 1 complete   |
|   4 | v2 SQL, bitemporal repo, encrypted payloads, consent receipts, migration tests                   | 5-7d | Gate 2 foundation |
|   5 | Exact `PricingTool` op, signed catalog, clock snapshots + historical backfill                    | 4-5d | Gate 2            |
|   6 | Shadow adapters (match/recommend/catalog); proof metrics, source validation                      | 4-5d | Gate 2 complete   |
|   7 | Complete-facts frontend, `AppWizard` hardening, same-origin capability cookie                    | 5-7d | Gate 3 prereq     |
|   8 | Enforce match/clock, then recommend/chat/handoff; canary + rollback bundle                       | 5-7d | Gate 3            |
|   9 | Retention worker, knowledge-write shutdown, import-graph cleanup, deletion                       | 3-5d | Gate 4            |

**Engineering total: ~41-56 engineer-days.** Legal-source review and RulePack authoring (§6) are a
**separate critical path** — the engine builds and gold-tests against synthetic fixture constants
(`GOLD_EFFECTIVE_AT`, `GOLD_CALLING_COUNTRIES`, `GOLD_INVESTOR_MIN_IDR`, explicitly not production legal
assertions) in parallel with the catalog bonifica.

**PR0 is independently shippable now** — it fixes the five live P0s (§2) without waiting on the bitemporal
database, signing pipeline, or gold harness, decoupling "stop the current system being unsafe" from "build
the full v2 engine." **Shadow-before-enforce is non-negotiable per surface** — each of the six surfaces
moves `OFF → SHADOW → ENFORCE` independently; effective mode is always the minimum of environment ceiling
and DB rollout mode, defaulting to `OFF` on any misconfiguration.

---

## 10. Open decisions for Zero (Legge 5)

1. **GO/NO-GO on the build, and sequencing** — ship PR0 (safety freeze) immediately regardless, or hold the
   entire program pending fuller review of this draft?
2. **Demo strategy and timeline toward Ditjen Imigrasi** — no date is proposed here; a business-relationship
   decision, not a technical one.
3. **DeepSeek seat policy** — dead throughout this research (balance -0.04 USD); the fleet-key
   burn-attribution hunt is unrelated root-cause and still in flight. Reinstate as a panel seat for this
   project regardless of that hunt's outcome, given the Sonnet web-grounded substitute performed adequately
   across two full rounds?
4. **Whether the interview's remaining 7 categories** (Family & marriage, Retirement & second home, Study,
   Diaspora & ex-WNI, plus Business/Tourism depth) get the GLM behavioral-tree treatment now, before build,
   or lane-by-lane during build.

---

## 11. §Solo-operatore

Per the ship-lifecycle mandate (CLAUDE.md §2), everything reviewable — code, config, content — stays with
the session once Zero gives GO on this draft. What's genuinely operator-only is narrower than it looks:

- **DeepSeek platform billing** — the burn-attribution hunt (~$48.75/30d) is a separate credential/billing
  investigation; any top-up decision is operator-gated by the existing "do NOT top up until attributed"
  hold in the corner's PENDING ledger, unrelated to this document.
- **Any future paid-key authorization** beyond what's already sanctioned (DeepSeek, Codex) — requires
  Zero's explicit yes with a cost estimate, never an autonomous "temporarily for testing" install.
- **The Ditjen Imigrasi relationship and demo scheduling** — a business decision, not a reviewable diff.
- **Final draft-PR approval on this document** — explicitly reserved by the mandate itself ("worktree-only
  until final draft for operator analysis"); the one deliverable here designed to wait on Zero's read by
  construction, not by default caution.

Everything else in §9 — including PR0's safety freeze, which fixes live production P0s — is session-owned:
review, merge (auto-merge armed at PR-open), deploy, prove-live, once §10.1's GO is given.

---

## 12. Source index

1. `round1-gemini-survey.md` — global UX survey: government exemplars, private visa-tech, cross-domain
   interview masters, Indonesian ecosystem gap, top-20 steal-list.
2. `round1-glm-design.md` — design language: living tree as primary metaphor, constellation atmosphere,
   outcome-page anatomy, motion rules, ten signature interactions.
3. `round1-codex-architecture-redteam.md` — architecture + adversarial red-team: NO-GO verdict on the
   current engine, P0 blocker table, regulatory data model, five-state contract, failure catalog, launch gates.
4. `round1-repo-map.md` — scout lane's file-by-file map of the live v1 funnel.
5. `round1-verification-note.md` — orchestrator's on-disk spot-check confirming 5 P0 claims verbatim.
6. `round1-web-verified.md` — live-fetched verification of government wizards + the Indonesian ecosystem,
   incl. the imigrasi.go.id zero-wizard finding and `?golden_visa=1` intel.
7. `round2-gemini-regulatory-delta.md` — regulatory delta vs. the 114-code baseline: 110-index
   reclassification, BVK rule, guarantor repeal, diaspora regime, Bridging Visa, update cadence.
8. `round2-glm-interview-design.md` — full behavioral-interview design: Q0 architecture, ten categories,
   three drafted trees, handoff templates, confirmation card, outcome skeletons, microcopy rules.
9. `round2-codex-engine-concretization.md` — full engine spec: module layout, JSON Schema contracts,
   bundle signing, evaluator algorithm, database schema, strangler migration, gold harness, salvage map, PR sizing.
10. `round2-reuse-first-oss.md` — live-verified OSS reuse survey: adopt/imitate/skip with license/maintenance checks.
11. `round3-opus-arbitration.md` — R3 arbiter verdict on custom-evaluator-vs-GoRules-ZEN, closing the one
    open architecture question from R2.

(All under `research/visa/2026-07-17-visa-oracle-v2-*` in this worktree.)
