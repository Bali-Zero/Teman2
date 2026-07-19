---
date: 2026-07-19
domain: visa
client_case: none
sources:
  - apps/backend-rag/backend/services/visa_engine/{enums,models}.py (on-disk read)
  - apps/mouth/src/app/(visa-oracle)/** + src/lib/visa-oracle/{types,api}.ts
  - docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md
  - .claude/skills/visaoracle/SKILL.md (ENFORCE-GATE)
author: Kimi K3 (kimi-code/k3, UI/UX titolare per decisione Zero 2026-07-19) — orchestrated by S3 session
status: LEAD (W65) — headline claim RecommendState==DecisionState spot-verified on disk by orchestrator; full field-level verification due at implementation
---

# Visa Oracle v2 — UI/UX Adaptation Spec (design-only pass, zero writes)

**Author:** Kimi K3, UI/UX design lead · **Date:** 2026-07-19 · **Repo state:** worktree `mouth-visa-engine-pr1-0718`, HEAD `6419ed16cb` (PR4 bitemporal substrate + ENFORCE-GATE record)
**Mandate honored:** the UI adapts to the engine, never the reverse. Every engine identifier below was read on disk, not invented: `apps/backend-rag/backend/services/visa_engine/{enums,models,ast,fact_registry,bundle,compiler,repository,schema_export}.py`, `apps/mouth/src/app/(visa-oracle)/visa-oracle/**`, `apps/mouth/src/lib/visa-oracle/{types,api}.ts`, `research/visa/*`, `docs/plans/2026-07-17-visa-oracle-v2/*`, `.claude/skills/visaoracle/SKILL.md`.

**One-line architecture:** the shipped living-tree experience already speaks the engine's five-state vocabulary (`RecommendState` in `apps/mouth/src/lib/visa-oracle/types.ts:28-33` is byte-identical to `DecisionState` in `enums.py:41-53` — that was the PR0 freeze doing its job). The adaptation is therefore a **source swap behind a stable rendering contract**, not a redesign: same screens, same states, new provenance (citations, quotes, fingerprints) rendered first-class.

---

## A. VERDICT PRESENTATION

### A.1 The engine's truth model (what the UI is allowed to say)

The UI's rendering contract is the frozen `Decision` model (`models.py:1102-1207`, exported as `contracts/decision.schema.json`). Load-bearing facts for design:

- `Decision.state` is exactly one of `NEEDS_INPUT | SUPPORTED_CANDIDATES | HUMAN_REVIEW_REQUIRED | NO_SUPPORTED_PATH | TEMPORARILY_UNAVAILABLE` (`enums.py:41-53`), with per-state field invariants enforced at the model layer (`models.py:1148-1207`): `SUPPORTED_CANDIDATES` ⇒ `candidates ≥ 1` and empty `missing_facts/review_reasons/no_path_reasons`; `NEEDS_INPUT` ⇒ `missing_facts ≥ 1`; `HUMAN_REVIEW_REQUIRED` ⇒ `review_reasons ≥ 1`; `NO_SUPPORTED_PATH` ⇒ `no_path_reasons ≥ 1`; `TEMPORARILY_UNAVAILABLE` ⇒ non-null `outage{code, retryable}` and identity fields allowed null.
- The tri-state (`TruthValue.TRUE/FALSE/UNKNOWN`, `enums.py:29-38`) never reaches the UI per-condition. **"Unknown can't increase eligibility" is structural** (round-3 arbitration): UNKNOWN only blocks or defers. Therefore the UI never renders "unknown helped you," and per-candidate there is no such thing as "maybe eligible" — a product is either in `candidates` (SUPPORTED) or absent. Abstention is a **global Decision state**, not a per-card badge.
- Every `Candidate` (`models.py:1034-1058`) carries `rank`, `product_code`, `score`, `covered_purposes`, `support_rule_ids`, `reason_codes`, and **`source_refs` (≥1, always)** — every candidate is born citable. Every `Reason` (`models.py:1010-1031`) carries `code` + `rule_ids` + `source_refs`.
- `Decision.notices` (`models.py:1126`) is unrestricted by state — the engine's channel for non-blocking information (e.g. `OBSOLETE_PRODUCT_CODE` remap). The current UI has no concept of it → NEW element (A.7).
- `PriceQuote` (`models.py:958-1007`) is tri-state: `status: AVAILABLE | CONTACT_REQUIRED | UNAVAILABLE`, single `amount` in IDR, null unless AVAILABLE. **Pricing failure never changes legal state** (spec §5.3) — perfectly aligned with owner ruling R1: one all-inclusive number, never an anatomy.
- Provenance for the freshness watermark: `Decision.rule_pack: RulePackRef{rule_pack_id, sequence, version, payload_sha256}` + `evaluated_at` + the resolved `SourceRecord.verified_at` set. The public surface gets `trace_sha256` only as an opaque integrity anchor — the full trace is encrypted/internal (spec §1); **never render a "trace viewer" on the public surface.** Ditjen-demo tenant only.
- `Decision.public_id` (`^[a-z0-9]{16,20}$`) is the shareable, PII-free pointer to a persisted public snapshot. It replaces any facts-in-URL pattern.

### A.2 State-mapping table (engine → UI)

| Engine `Decision.state` (+ discriminating fields) | UI verdict state (`RecommendState`) | Headline component | Body composition | Gap flags |
|---|---|---|---|---|
| `SUPPORTED_CANDIDATES`, `candidates.length == 1` | `SUPPORTED_CANDIDATES` (single winner) | `VerdictReveal` (KEEP — state icon+headline already keyed by state) | `OutcomeSheet`: single verdict tile, what-it-gives/what-it-doesn't, `CitationList` from `candidates[0].source_refs` + `support_rule_ids`, quote block (A.8), checklist, next-3-steps, QR handoff, assumptions receipt, freshness stamp, 4-line disclaimer | none — mock already renders this shape |
| `SUPPORTED_CANDIDATES`, `candidates.length ≥ 2` | same, trade-off variant | `VerdictReveal` | `OutcomeSheet` comparison table (KEEP — exists) ordered by `rank`; **no "recommended" badge unless a `reason_codes` entry maps to a real stated reason** (GLM rule, engine-compatible); `score` is **never rendered** (microcopy rule 7 — no scores; RANKING uses commercial facts only, so score ≠ legal strength) | current mock ranks by 4-tier eligibility — engine mode ranks by `rank` only (A.7 #2) |
| `NEEDS_INPUT`, `missing_facts: FactPath[]` | `NEEDS_INPUT` | `VerdictReveal` | NEW `NeedsInputPanel` (A.3.2) — GLM shipped no skeleton for this state | **skeleton missing in research lanes — designed here** |
| `HUMAN_REVIEW_REQUIRED`, `review_reasons: Reason[]` | `HUMAN_REVIEW_REQUIRED` | `VerdictReveal` | GLM handoff master template (KEEP copy): head *"A person should look at this with you."*; dynamic "what we'll need" list; each `review_reasons[i]` rendered as plain-language block via reason-code copy map (A.4.3) **with its citations tappable**; WhatsApp CTA primary; no price (premature) | mock renders generic body only — reason blocks + citations are NEW |
| `NO_SUPPORTED_PATH`, `no_path_reasons: Reason[]` | `NO_SUPPORTED_PATH` | `VerdictReveal` | GLM skeleton (KEEP): "useful to know before you spend anything" + three what-instead blocks; `no_path_reasons` rendered as honest "why not" lines **with citations** (e.g. `INVESTMENT_CAPITAL_BELOW_FIXTURE_MINIMUM` → cited floor); adviser CTA | engine supplies **no `alternativeCategories`** — the mock's client-side alternative tiles don't exist in engine mode (A.7 #4) |
| `TEMPORARILY_UNAVAILABLE`, `outage{code, retryable}` | `TEMPORARILY_UNAVAILABLE` | `VerdictReveal` | GLM skeleton (KEEP): "we're updating, not guessing," no invented dates; **retry affordance only when `outage.retryable == true`** (NEW micro-state); adviser CTA always | mock has static copy, no retryable distinction |
| (client-side) engine unreachable / invalid response at ENFORCE | `TEMPORARILY_UNAVAILABLE` (synthesized) | `VerdictReveal` | Same skeleton with `outage.retryable=true` semantics | NEW: client-synthesized outage DTO (B.4) — never crash, never fabricate |

### A.3 Per-state presentation specs

**A.3.1 SUPPORTED_CANDIDATES.** Verdict headline names the **situation, not the code** (microcopy rule 1): product code is a small secondary chip (`visa.<CODE>.name` i18n pattern already exists). "What it gives you" / "What it doesn't" bullets stay content-owned (FASE content), engine-validated only for consistency with `covered_purposes`. Timeline stays anchored to TODAY (KEEP `frozenToday` discipline from `OracleShell`). The single all-inclusive price renders per A.8. The comparison table columns: name · eligibility chip (uniform "Eligible — engine-verified", see A.7 #2) · stay/entry summary · timeline range · price · best-for tag (content-curated, only when a `reason_codes` entry justifies it).

**A.3.2 NEEDS_INPUT — the missing skeleton (NEW, designed here).** The engine returns `missing_facts: tuple[FactPath, ...]` — dotted paths from the closed 35-path vocabulary (`enums.py:387-446`). This state is **abstention-as-continuation**, and it must be rare by design (the interview collects facts before evaluate is ever called) but possible (server-side rules may require facts the interview didn't gather — e.g. a regulation delta adding a requirement mid-flight). Presentation:

- Headline: *"A few more details and we can say properly."* / ID equivalent (body-first). Never an error tone — this is the engine being careful, framed as a virtue (microcopy rule 4).
- Body: group `missing_facts` by their dotted prefix (`person.*` → "About you", `immigration.*` → "Your current stay", `work.*` → "Your work", etc. — the 9 registry groups from `fact_registry.py`). Each missing fact renders as a **tappable row that deep-links back into the interview**: a static `FactPath → questionId` registry (NEW, `_lib/fact-questions.ts`) maps each of the 35 paths to the question that collects it; tapping dispatches the existing `EDIT` action (the history-truncation + `pruneFacts()` machinery already handles re-answering safely — KEEP).
- If a `missing_fact` has **no interview question** (shouldn't happen; guarded by the registry's unit test asserting every one of the 35 paths has a question or an explicit `not-collected` marker), the row falls back to "an adviser will confirm this with you" and the primary CTA switches to handoff. The test makes the fallback unreachable in CI.
- CTA hierarchy: *"Answer these"* (primary, scrolls to first mapped question) · *"Talk to an adviser instead"* (secondary — the escape hatch is always present).
- **Never** render NEEDS_INPUT as a dead end or as a form-error page. It is the fifth first-class outcome.

**A.3.3 HUMAN_REVIEW_REQUIRED — dignified abstention.** This is the moat made visible: the system visibly refuses to guess. GLM master template is kept verbatim (head/body/what-we-need/what-happens-next/reassurance/CTA), with three engine-driven upgrades: (1) the "why" section renders `review_reasons` as plain-language blocks from the reason-code copy map (A.4.3), each with tappable citations; (2) the reassurance line is lane-aware — overstay lane appends the existing `outcome.overstay_reassurance` (KEEP: *"Overstay is fixable…"*); (3) the handoff payload carries `decision_id`/`public_id` (B.2), not raw facts. Copy rules enforced: no fabricated urgency, no alarm color beyond warm amber (`--oracle-state-conditional` family), penalties mentioned only if the user surfaced an overstay themselves, "trouble" only in reassurance. ID renders body-first (`BODY_FIRST` mechanism, KEEP).

**A.3.4 NO_SUPPORTED_PATH.** KEEP the GLM skeleton (three what-instead blocks, never a bare dead end). Engine upgrade: the "why" line per `no_path_reasons[i]` with citations — this is where "the rule you're hoping for may not exist" becomes *citable* (microcopy rule 9). The third block's honest reality-check stays content-curated. Alternative-category tiles: in engine mode there is no engine-supplied list (A.7 #4) — the forward actions are: revisit answers (existing `EDIT`), talk to an adviser (WhatsApp), browse categories (existing `onSelectCategory`).

**A.3.5 TEMPORARILY_UNAVAILABLE.** KEEP the GLM skeleton. Add the retryable branch: `outage.retryable=true` → *"Try again"* button re-issues the evaluate call (skeleton state during retry, never a spinner); `retryable=false` → only the adviser CTA and the save-answers path. No invented dates, no "coming soon."

### A.4 Citations as first-class UI — the visible-honesty moat

**A.4.1 Data path.** `Decision` carries only UUID refs (`source_refs`). The wire DTO must resolve them server-side: the recommend/evaluate response embeds `sources: SourceRecordDTO[]` (projection of `SourceRecord`, `models.py:187-223`: `source_key`, `title`, `publisher`, `authority_type`, `status`, `document_number`, `canonical_url`, `locators[{kind, value}]`, `legal_period.from`, `verified_at`). Rationale: one roundtrip, cacheable, and the backend already owns the pack's `source_records` — the UI never does UUID-join gymnastics. This is an API-contract requirement handed to the engine lane (B.2).

**A.4.2 New components (presentation spec).**

- **`CitationChip`** — a tappable pill rendered inline wherever a claim is made: per candidate (from `candidates[i].source_refs`), per reason block (from `Reason.source_refs`), and inside the assumptions receipt. Visual: small superscript-style marker with source glyph, `aria-label` from `citation.trigger.aria {{title}}`; keyboard-focusable; activates a bottom-sheet/popover (mobile-first) reusing the `WhyWeAsk` disclosure mechanics (KEEP pattern: `useId` + `AnimatePresence` + reduced-motion aware). Never color-alone; icon + text.
- **`CitationList`** — the expanded view: one row per source showing `title` · `publisher` · `document_number` (when present) · pinpoint `locators` rendered as "Pasal 45" / "Article 45" style strings (`kind: ARTICLE|SECTION|PAGE|PARAGRAPH|ANCHOR` + `value`) · authority badge from `authority_type` (`PRIMARY_LAW`, `IMPLEMENTING_REGULATION`, `OFFICIAL_PORTAL`, `OFFICIAL_CIRCULAR`, `BALI_ZERO_POLICY`, `PRICING_CATALOG` — six badges, text+icon, never color-alone) · "in force since `legal_period.from`" · `canonical_url` external link. **Honesty rule:** a `SourceRecord` with `status != VERIFIED` (`SUPERSEDED | REVOKED | UNAVAILABLE`) renders visibly marked as such — a pack should never ship one, but if it does, the UI tells the truth rather than hiding it.
- **Placement:** verdict tile (top candidate), each comparison-table row, each reason block, the assumptions receipt footer, and a "Sources" section in the print recap (A.4.4). The `WhyWeAsk` component's `regulation: string` prop is the prototype of this chip — at ENFORCE it upgrades to carry a resolved `SourceRecordDTO` (D-section details).

**A.4.3 Reason-code → copy map.** Reason codes (`^[A-Z][A-Z0-9_]{0,127}$`) are engine vocabulary; the UI owns their human rendering as i18n keys `reason.<CODE>` EN/ID, seeded with the codes already exercised by the gold-persona corpus (spec §7): `APPLICANT_IS_INDONESIAN_CITIZEN`, `CITIZENSHIP_EVIDENCE_CONFLICT`, `CALLING_VISA_REVIEW`, `ACTIVE_OVERSTAY`, `MINOR_WITHOUT_CONFIRMED_GUARDIAN`, `DIRECT_ONSHORE_CONVERSION_UNSUPPORTED`, `STATUS_BRIDGING_REVIEW`, `LOCAL_MARKET_ACTIVITY_REVIEW`, `INVESTMENT_CAPITAL_BELOW_FIXTURE_MINIMUM`, `OBSOLETE_PRODUCT_CODE`. Unknown codes fall back to a generic honest line + the citations (never render the raw code to end users; codes are audit vocabulary). New codes ship as content PRs — the i18n parity test (KEEP) forces both languages.

**A.4.4 Print & non-visual.** Citations print: the existing `@media print` block (`oracle.css:1025-1062`) extends to reveal a print-only "Sources & verification" section (source titles, document numbers, ruleset version, `public_id`). Screen readers get the citation as inline text within the announcement of the verdict (live-region pattern already used by `PathsCounter` / `VerdictReveal` focus-to-heading — KEEP).

### A.5 Assumptions surfaced explicitly

The engine types every uncollected fact as `UnknownFact{reason: UnknownReason}` with five reasons (`enums.py:147-158`): `NOT_ASKED`, `NOT_PROVIDED`, `UNVERIFIED`, `CONFLICTING`, `NOT_APPLICABLE`. The current mock collapses all of these into one `"unsure"` + one `assumption.<questionId>` string. Upgrade (engine mode): the assumptions receipt groups by reason with reason-specific copy — NEW keys `unknown_reason.{NOT_ASKED,NOT_PROVIDED,UNVERIFIED,CONFLICTING,NOT_APPLICABLE}` — e.g. `CONFLICTING` → *"Your answers conflicted here, so we treated it as unknown rather than picking one."* Each assumption keeps its one-tap Edit (KEEP `ConfirmationCard` behavior; the honesty receipt is the trust anchor). `NOT_APPLICABLE` never renders as a user fault — it's informational only (usually hidden from the receipt, visible in the demo tenant).

### A.6 The escape-hatch hierarchy (chat stays demoted)

1. **Primary: WhatsApp handoff** — QR + wa.me link (KEEP `qrcode` npm SVG implementation, `OutcomeSheet.tsx:97-136`). At ENFORCE the payload changes: the pre-filled message references `public_id` + the verdict headline + the user's chosen language — **never the raw Q:A fact dump** the mock currently builds (`buildWhatsAppSummary` embeds facts in the URL text today; under the engine that contradicts the PII-minimization split and spec §6.2's "handoff accepts `decision_id`; client-supplied facts ignored"). The consultant opens the persisted snapshot server-side.
2. **Secondary: save & resume** — *"Save my answers and come back later"* (GLM template) via `public_id` share link (NEW route, D).
3. **Tertiary: chat as explainer** — the existing chat entry stays available but demoted: it may explain a persisted `Decision` (capability-gated per spec §6.2) and **can never create, upgrade, or rank candidates**. UI rule: chat affordance copy is always "Ask about this result," never "Get a second opinion."

### A.7 Engine↔UI expression gaps (explicit flags for the implementation lane)

**Engine states/aspects the current UI cannot express (all resolved by this spec):**

1. **Per-product proof outcomes** (`EXCLUDED | REVIEW | BLOCKED_UNKNOWN | SUPPORTED | UNSUPPORTED`, spec §4.2 pseudocode) exist only inside evaluation; the `Decision` exposes no per-product failure list. The UI must **not** invent "why did visa X disappear" rows from nothing — that question routes to the chat explainer (post-decision, capability-gated). Intentional, recorded.
2. **Per-candidate confidence tiers.** The mock's `EligibilityState = "eligible" | "likely" | "conditional" | "likely-not"` (`tree.ts:48`) has **no engine counterpart** — a candidate is SUPPORTED or absent. At ENFORCE the 4-tier chip is **retired** and replaced by a single "Eligible — engine-verified" chip (icon+text); the 4-state colors (`--oracle-state-*` tokens) remain for the curated/mock mode and for the lane-urgency semantics where they're honest (A.3.3 amber). *This is the mandate in action: the engine's truth model deletes a UI concept.*
3. **`UnknownReason` granularity** — one "unsure" today vs five typed reasons (A.5).
4. **No engine-supplied `alternativeCategories`** for NO_SUPPORTED_PATH (mock computes them client-side) — engine mode uses reasons + adviser + category browse instead (A.3.4).
5. **`outage.retryable`** — retry-aware unavailable screen (A.3.5).
6. **Quote tri-state** — mock always shows a price (A.8).
7. **`notices`** — NEW global notices strip below the verdict headline (informational, e.g. obsolete-code remap), dismissible, printed too.
8. **Provenance fields** (`rule_pack`, `public_id`, `evaluated_at`) — NEW dynamic freshness stamp replacing the mock's static "Sample ruleset 2026.07-prototype" string (A.9).

**Interview answers with no `FactPath` (vocabulary gaps — flagged, not papered over):** the review-gate items `criminal_record`, `health_flag`, `prior_refusal` (mock `REVIEW_GATE_ITEMS`, `tree.ts:229-237`) have no engine fact path (the engine sees only `immigration.violation_history: {OVERSTAY, DEPORTATION, BLACKLIST, IMMIGRATION_INVESTIGATION, OTHER}`); the remote-lane **income-floor** question has no fact path either. Design ruling (adapts to engine): these remain **UI-side force-review triggers** — any non-"none" review-gate answer forces `HUMAN_REVIEW_REQUIRED` locally, exactly as `reviewGateFlagged` does today (KEEP), and the engine's own HUMAN_REVIEW rules independently catch what they can see. Belt and braces; never submit un-mappable answers as facts. The FASE-2/engine lanes should reconcile this vocabulary before ENFORCE (recorded as a dependency, E).

### A.8 Price presentation (owner ruling R1, engine-shaped)

One number, always IDR, from `PriceQuote` only — the mock's `allInclusivePriceIDR` discipline (KEEP) maps onto `PriceQuote.amount`. Three render states:

- `AVAILABLE` → the number + `valid_until` microcopy ("price held until {{date}}" when present) + `PRICING_CATALOG`-typed citation chip.
- `CONTACT_REQUIRED` → no number; *"We'll confirm the exact all-inclusive price with you"* + handoff CTA. The legal verdict stands untouched.
- `UNAVAILABLE` → price block omitted entirely, verdict untouched, one neutral line: *"Pricing for this path is being updated — the eligibility answer above stands."* Never a fake estimate, never a breakdown, never PNBP-vs-fee anatomy anywhere in the UI.

### A.9 Freshness stamp & provenance

Replace the mock's static stamp with the engine's: *"Evaluated with ruleset `{{version}}` (#{{sequence}}), sources verified {{verified_at}}. Result `{{public_id}}`."* (product-design §5.8 format), rendered in the assumptions & caveats footer and in print. The 4-line disclaimer block (`outcome.disclaimer.{not_government,based_on_facts,not_approval,complex_to_human}`) is KEEP verbatim — it already encodes the spec §8 hierarchy.

---

## B. SHADOW vs ENFORCE

### B.1 SHADOW — confirmed invisible by design

During SHADOW the UI **does not change at all** — zero visual, behavioral, or performance delta:

- The rendered verdict source remains `evaluate()` in `_lib/mock-engine.ts` (pure, synchronous, bundled). No new component mounts, no flag UI, no badge changes, no copy changes.
- The only SHADOW-era code is an **invisible fire-and-forget call**: on verdict computation, the shell POSTs the mapped `ApplicantFacts` to the shadow endpoint (step6c Option C) with `keepalive`/`sendBeacon` semantics, **response ignored, errors swallowed, never awaited by any render path**. If the endpoint 404s (pre-deployment), nothing happens. This call is the G-a volume generator and must carry no UI-observable side effect — unit test asserts the render tree is byte-identical with the endpoint reachable vs. black-holed.
- All six `VISA_ENGINE_*_MODE` flags and the DB-mode lever are **backend-only** (they don't exist yet — step6c §2/§4b). The frontend never reads them directly (B.3).

### B.2 What switches at ENFORCE (exact enumeration)

At ENFORCE, five data sources switch inside the `/visa-oracle` route — and nothing else on the page moves:

| # | Switches | From (SHADOW/curated) | To (ENFORCE) |
|---|---|---|---|
| 1 | Verdict computation | `evaluate()` in `_lib/mock-engine.ts` (sync, local) | `POST /api/v1/visa-oracle/recommend` (canonical-facts payload; per spec §6.2 it gains `state`, `decision_id`, `missing_facts`, `review_reasons`; `visas=[]` unless SUPPORTED) via NEW `_lib/engine-client.ts` + response adaptation via NEW `_lib/decision-adapter.ts` |
| 2 | Fact assembly | implicit (mock reads `OracleFacts` directly) | NEW `_lib/fact-mapper.ts`: `OracleFacts → ApplicantFacts` (35-key wire shape, `KNOWN`/`UNKNOWN{reason}` per fact, `assessment_id` per session, `collected_at` at submit) |
| 3 | Catalog display data | inline `MOCK_CATALOG` (12 cards, `tree.ts:239-434`) | pack-backed product data in the recommend response (candidates + resolved product names/policies; `GET /visa-types` becomes pack-backed per spec §6.2) |
| 4 | Price | mock static `allInclusivePriceIDR` | `Decision.quotes` (tri-state, A.8) |
| 5 | Provenance/honesty | static sample stamp + string `regulation` props | `rule_pack` + `sources[]` + `public_id` (A.4, A.9) |

**The tell:** `decision_id` present ⇒ engine-produced; absent ⇒ curated. The shared rendering contract (superset DTO, B.3) means every downstream component consumes one shape.

### B.3 Mode discovery — per-response, never build-time

Rollback must be instant with **no redeploy** (G-d), so the UI's engine/curated mode can never be a `NEXT_PUBLIC_*` build-time flag. Design:

```text
type VerdictSource =
  | { kind: "engine";  decision: DecisionDTO; sources: SourceRecordDTO[] }
  | { kind: "curated"; result: EvaluateResult }              // today's mock shape

resolveVerdict(facts, today): Promise<VerdictSource>
  SHADOW era  → curated (mock evaluate) + fire-and-forget shadow POST
  ENFORCE era → engine-client POST (timeout ~4s, one retry)
      200 + decision_id          → engine
      200 + mode:"CURATED"       → curated   (DB lever already flipped — instant rollback observed)
      network/5xx/timeout        → synthesized TEMPORARILY_UNAVAILABLE (outage.retryable=true)
```

The backend enforces `min(env_ceiling, db_mode)` per request (step6c §4b) — so the **DB flip takes effect on the very next call**, and the client learns the mode from each response. No client cache of mode across calls (the DTO is re-derived per evaluation; `useOracleFlow`'s memoization already re-runs on every state change — KEEP).

### B.4 Instant-rollback degradation path (the drill the G-d criterion exercises)

Flip matrix — every cell must render without error, without redeploy:

| Moment of flip | User state | What happens |
|---|---|---|
| ENFORCE→OFF, between sessions | none (fresh load) | Interview is client-side regardless; verdict call returns curated → mock renders with prototype badge + sample stamp. Zero delta vs. today. |
| ENFORCE→OFF, mid-interview | answers in progress | Next state change recomputes → curated response → mock verdict. Facts are language-agnostic keys, so `fact-mapper` vs. mock both consume them — no loss. |
| ENFORCE→OFF, on verdict screen | engine verdict visible | An explicit re-evaluation (edit an answer, change language, retry) swaps to curated; the stale engine verdict is never *re-rendered* as current (no client-side verdict persistence beyond the session; refresh = fresh evaluate). |
| OFF→ENFORCE, mid-session | mock/curated flow | Next compute calls the engine with already-collected facts via `fact-mapper` — seamless upgrade to cited verdicts. |
| Engine disappears mid-session (outage) | any | Synthesized `TEMPORARILY_UNAVAILABLE` (B.3) — dignified skeleton + retry + WhatsApp. **Never** a silent fallthrough to mock verdicts presented as engine truth, and never a crashed tree (the mock-as-real failure mode is the one thing R1 + "zero unsupported recommendations" forbid). |

Labeling invariant that makes rollback honest: the **prototype badge + "sample ruleset" stamp render iff `VerdictSource.kind === "curated"`** — so after a rollback the page re-asserts its curated identity automatically. The demo-to-Ditjen posture is preserved: at ENFORCE those labels disappear because the verdicts are real.

### B.5 noindex & SEO timing

`layout.tsx` currently sets `robots: {index:false, follow:false}` (KEEP until ENFORCE). The robots flip to index ships **in the ENFORCE PR** (deploy-time is acceptable — indexing is inherently not instant, unlike the verdict source which is runtime). On rollback, the page stays reachable as the curated experience; a follow-up PR may restore noindex if Zero wants the surface re-hidden. Recorded honestly: robots is the one surface that cannot flip at DB speed, and it doesn't need to.

---

## C. INTERVIEW UX

### C.1 Architecture — KEEP the skeleton, it's already right

The shipped flow already implements the panel canon: framing card → one-question-per-screen (GOV.UK) → grouped editable confirmation card → verdict; paths-remaining counter (hidden through Q1–Q2 via `HIDE_COUNTER_ON`); branch-aware living tree with tap-to-edit; history stack with `pruneFacts()` so abandoned branches never leak into the engine; language-agnostic answer keys so mid-funnel EN↔ID switch loses nothing. All KEEP. The `AppWizard`-class concerns (async persistence, double-submit) don't apply here — the route is deliberately sessionless until the evaluate call.

### C.2 Question → `FactPath` binding (the interview is a fact collector for the 35-path registry)

NEW `_lib/fact-mapper.ts` owns this table (each binding unit-tested against `ApplicantFactsData`'s 35 required keys):

| Question (current `QUESTIONS`, `tree.ts:105-220`) | Engine `FactPath`(s) | Mapping rule |
|---|---|---|
| `in_indonesia` (branch) | `immigration.currently_in_indonesia` | yes/no→KNOWN bool; `unsure`→conservative "yes" (KEEP existing policy) |
| `permit_expiry` (date) | `immigration.current_status_expiry`; derived-mapping `immigration.overstay_days` = `max(0, today−expiry)` (pure date arithmetic, documented as mapping not evaluation) | ISO date→KNOWN; skipped/expired→lane policy (review) |
| `category` (tiles) | soft-router → `intent.purposes` seed (1:1 category→purpose map, e.g. work→`EMPLOYMENT`, remote→`REMOTE_WORK`) + **never kills cross-category candidates** (GLM soft-router rule; the engine's `COVER_ALL_DECLARED_PURPOSES` does the real pruning) |
| `work_payer` | `work.employer_is_indonesian_entity`, `work.employer_country_code` (foreign employer branch) | option key→bool/country; `unsure`→force-review (KEEP) |
| `remote_clients` | `work.serves_indonesian_clients`, `work.indonesia_source_compensation` | foreign/mixed/local→bool pair; `unsure`→force-review |
| `remote_income` | **no FactPath exists** (A.7) | UI-side downgrade/review hint only until engine vocabulary grows — flagged dependency |
| `tourism_duration` | `intent.stay_days` | band→canonical days mapping, documented |
| `review_gate` (CSV) | `immigration.violation_history` for `overstay_or_blacklist`→{`OVERSTAY`} etc.; `criminal_record`/`health_flag`/`prior_refusal`/`not_certain` → UI-side force-review only (A.7) | sorted CSV already deterministic (KEEP) |
| (implicit, from desired travel timing — NEW, C.3) | `intent.desired_entry_date`, `intent.entry_pattern` | per-lane questions |
| **NEW `nationality`** (C.3) | `person.nationalities` | ISO alpha-2 set (≤4 per model); dual-passport option→force-review (calling-visa overlay is the engine's rule, not UI logic) |
| **NEW `birth_date`** (C.3) | `person.birth_date` → engine derives `derived.age_years`/`derived.is_minor` | strict ISO date; why-we-ask required (SENSITIVE-adjacent) |
| everything never asked | remaining 35−n paths | `UnknownFact{reason: NOT_ASKED}` — legal, expected, the tri-state's job to absorb |

Unasked/skipped/conflicting mapping: never-asked ⇒ `NOT_ASKED`; user skipped ⇒ `NOT_PROVIDED`; user said "not sure" on a verified-only fact ⇒ `UNVERIFIED`; contradictory re-answers (EDIT churn producing inconsistency) ⇒ `CONFLICTING`. This is the wire-level honesty the `UnknownReason` vocabulary exists for.

### C.3 Hosting the 7 FASE-2 categories (EN/ID)

Ten tiles exist today (`CATEGORY_KEYS`, `tree.ts:82-93`); three lanes have behavioral trees in the mock (`BEHAVIORAL_CATEGORIES = {"work","remote","tourism"}`, `tree.ts:99` — tourism simplified); GLM's drafted trees cover Work (W1–W6), Invest (I1–I6), Remote (R1–R6). The **7 lanes awaiting FASE-2 content**: `invest` (drafted, unimplemented), `business`, `family`, `retirement`, `study`, `diaspora`, `other` (+ tourism depth). Hosting plan, identical architecture per lane:

1. **Lane shape:** each lane = ≤6 questions (GLM modal budget), composed as: lane splitter → lane refiners → shared `review_gate` ★ → optional shared `family` ★ (the two shared questions are built once and composed — KEEP that doctrine; the mock already has the shared review-gate).
2. **Question kinds stay closed:** `branch | date | tiles | choice | review-gate` (`tree.ts:34`) is sufficient for all drafted trees; FASE-2 content must fit these kinds (UI adapts content to the same five primitives — no new widget types per lane).
3. **Honest placeholder until content lands (KEEP current behavior):** unimplemented lanes force `HUMAN_REVIEW_REQUIRED` (`categoryForcesReview` in the mock) — that *is* the dignified-abstain pattern at the lane level, and it's correct to keep shipping it per lane until that lane's tree passes content review. As each FASE-2 lane lands, its tile flips from force-review to behavioral with **zero layout change** (same `QuestionScreen`, same tree fan-out).
4. **New shared questions required by the engine vocabulary** (NEW, blocking ENFORCE, not blocking SHADOW): `nationality` (full ISO list + dual/diplomatic options — the engine's calling-visa overlay and BVK nationality-only rules are un-evaluable without it; the old `nationalities.ts` ISO list exists unwired in `src/lib/visa-oracle/` — REUSE), and `birth_date` (retirement 55+, minors). Both are `sensitive: true` ⇒ mandatory `WhyWeAsk` glyph (KEEP pattern) and both slots exist in the tree projection already (`getTreeSteps` renders any question on the path).
5. **Progressive disclosure rules (KEEP + formalize):** counter hidden until committed; lane-expiry tile prominent only in bridging/urgent lanes (`lane.<lane>.notice` keys exist); `NotSure` affordance on every question carrying `notSure` policy; WhyWeAsk on every `sensitive` question; no question ever shows a visa code.

### C.4 Q0 date-driven onshore lanes — KEEP, already arbitrated-correct

The mock's `getLane()` (`tree.ts:437-539`) implements exactly the corrected table: expired (<0) → overstay-help (always human review, reassurance copy exists); 1–2 days → urgent human review (never bridging — the Permenkumham 11/2024 ≥3-day correction); 3–7 → bridging-urgent (amber, expiry tile); 8–60 → extend/convert (neutral); 60+ → planned. The three Q0 escape valves (dual citizen / just left / visa run) route to review — currently via `unsure` handling; FASE-2 may add a dedicated clarifier step using the existing `branch` kind. No change needed.

### C.5 Error & edge microcopy (consistent with the 10 rules, R1-amended)

- Rule 3 is **superseded by owner ruling R1** everywhere: *"one all-inclusive price, never a fee breakdown, anywhere"* (product-design §4 wording replaces GLM's fee-split version; the GLM adversarial note already records this).
- Date edges: impossible calendar dates rejected at input (strict parsing exists — `parseIsoDateUtc` rejects 2026-02-30, KEEP); expiry in the past is a *lane*, not an error (reassuring copy, no alarm); expiry >1 year out gets a gentle "that seems far — check the date?" hint (plain verbs, rule 6).
- Validation tone: no red error theatre; hint text under the field (GOV.UK pattern already in `QuestionScreen`); the word "trouble" appears only inside reassurance (GLM handoff rule).
- "I don't know" is always first-class and rewarded with honesty (rule 4): `NotSure` copy never apologizes.
- Paths counter is a fact, not a celebration (rule 7): no animation on decrement beyond the existing subtle tick; reduced-motion gets instant swap (already implemented).
- Every edge routes somewhere: no dead-ends anywhere in the 10 lanes (rule 8 + GOV.UK canon).

### C.6 EN/ID parity mechanics

KEEP: flat dotted keys, `Record<Keys, string>` compile-time parity, `i18n.test.ts` runtime parity + `\bkamu\b` ban + no-empty-value, `BODY_FIRST` ID body-before-headline, `translate()` `{{var}}` interpolation, missing-key-renders-key (loud, never silent). NEW keys for this spec (citations, notices, `unknown_reason.*`, `reason.<CODE>` seed set, quote states, outage retry, `nationality`/`birth_date` questions) follow the same discipline; ID uses Imigrasi-native terminology, native-speaker review before ENFORCE (GLM flag). **Gap fix (NEW, small):** the root layout hardcodes `lang="en"` — add a client effect in `OracleShell` syncing `document.documentElement.lang` with the toggle (a11y + correct hyphenation/voiceover); keep it route-scoped.

---

## D. COMPONENT DELTA MAP (file-by-file)

Route root: `apps/mouth/src/app/(visa-oracle)/visa-oracle/`. KEEP = no change needed (rationale given, no redesign for its own sake) · MODIFY = scoped delta · NEW = to be created.

| File | Verdict | One-line rationale |
|---|---|---|
| `page.tsx` | **KEEP** | 5-line shell mounting `OracleShell`; nothing engine-specific belongs here. |
| `layout.tsx` | **KEEP until ENFORCE PR, then MODIFY** | `robots: noindex,nofollow` stays through SHADOW; the ENFORCE PR flips index + drops "Prototype" from the title (B.5). |
| `oracle.css` | **MODIFY (additive)** | Add styles for `CitationChip`/`CitationList`, notices strip, `NeedsInputPanel` rows, retryable-unavailable button; extend `@media print` for the Sources & verification section; reuse existing `--oracle-state-*` + core tokens — no new token families. |
| `_lib/flow.ts` | **MODIFY** | `useOracleFlow` currently memoizes a **sync** `evaluate()`; verdict resolution becomes async at ENFORCE — fire `resolveVerdict` at `REVIEW_ANSWERS` (confirmation CTA), hold a pending state, reveal via the existing morph (skeleton, never spinner); history/EDIT/prune machinery untouched (KEEP semantics). |
| `_lib/tree.ts` | **MODIFY** | Add `nationality` + `birth_date` (+ FASE-2 lane questions as content lands) to `QUESTIONS`; `MOCK_CATALOG` stays as the curated-mode catalog (explicitly labeled sample, as now); no change to lane helpers or `EligibilityState` (used by curated mode only after ENFORCE). |
| `_lib/mock-engine.ts` | **KEEP (role change)** | Remains the curated/SHADOW renderer and the rollback target verbatim — do not "improve" it into an engine emulator; its mock identity is the honest OFF state. |
| `_lib/i18n.ts` | **MODIFY** | Add key groups: `citation.*`, `notice.*`, `unknown_reason.{5}`, `reason.<CODE>` seed set, `outcome.price_{available,contact,unavailable}`, `outcome.retry_cta`, `needs_input.*`, `q.nationality.*`, `q.birth_date.*` — parity tests unchanged and binding. |
| `_lib/fact-mapper.ts` | **NEW** | `OracleFacts → ApplicantFacts` (35-key wire, KNOWN/UNKNOWN{reason}, C.2/C.3 table; `assessment_id`, `collected_at`); pure + fully unit-tested (every path mapped or explicitly `not-collected`). |
| `_lib/fact-questions.ts` | **NEW** | `FactPath → questionId` registry driving the NEEDS_INPUT deep-links; unit test asserts coverage of all 35 paths. |
| `_lib/engine-client.ts` | **NEW** | The only network code in the route: POST recommend with canonical facts, 4s timeout + single retry, runtime response validation mirroring `parseRecommendResponse`'s defensive discipline (never blind-cast); also owns the SHADOW fire-and-forget call. |
| `_lib/decision-adapter.ts` | **NEW** | `Decision wire DTO → VerdictSource` superset (B.3): validates per-state invariants client-side (defense-in-depth — an invalid engine response degrades to synthesized `TEMPORARILY_UNAVAILABLE`, never renders), resolves citations/quotes/notices into render models. |
| `_components/OracleShell.tsx` | **MODIFY** | Owns `resolveVerdict` + `VerdictSource` state, mid-session mode flip handling (B.4), pending/skeleton at reveal, `documentElement.lang` sync; keeps theme/frozenToday/counter visibility logic untouched. |
| `_components/LivingTree.tsx` | **KEEP** | Tree projection, tap-to-edit, SR-only nav equivalent, prune animation, morph source — all engine-agnostic (it renders flow state, not verdicts). |
| `_components/QuestionScreen.tsx` | **KEEP** | GOV.UK skeleton + per-kind renderers + focus management already correct; new questions (nationality/date) reuse existing kinds. |
| `_components/ConfirmationCard.tsx` | **MODIFY** | Assumptions group gains `UnknownReason`-specific copy (A.5); add the two-line provenance preview (ruleset version replaces the R1-superseded "fee split" preview line from GLM §5). |
| `_components/VerdictReveal.tsx` | **MODIFY** | State icons/headlines KEEP; in engine mode the per-candidate 4-tier eligibility chip becomes the single "Eligible — engine-verified" chip (A.7 #2); notices strip mounts below headline when `notices` non-empty. |
| `_components/OutcomeSheet.tsx` | **MODIFY (the biggest delta)** | Mount `CitationList` per candidate/reason (A.4); tri-state price block (A.8); `NeedsInputPanel` host for NEEDS_INPUT; retryable-aware unavailable body; dynamic freshness stamp + `public_id` (A.9); WhatsApp payload switches to `public_id` reference (A.6); print recap gains Sources section. |
| `_components/NotSure.tsx` | **KEEP** | It *is* the abstention affordance — engine mode reuses it unchanged; the reason vocabulary lives in the mapper, not the button. |
| `_components/WhyWeAsk.tsx` | **MODIFY (narrow)** | `regulation: string` prop widens to `string | SourceRecordDTO` — question-time citations render with the same chip mechanics as verdict-time citations (A.4.2). |
| `_components/PathsCounter.tsx` | **KEEP** | Engine-agnostic count display; live-region pattern is the a11y template for the new components. |
| `_components/LanguageToggle.tsx` | **KEEP** | Facts are keys, switch is lossless — exactly what the engine needs. |
| `_components/ThemeToggle.tsx` | **KEEP** | Route-local theming; light default stands (Jakarta demo). |
| `_components/CitationChip.tsx` + `CitationList.tsx` | **NEW** | A.4.2 spec; keyboard + SR + print + reduced-motion per house canon. |
| `_components/NeedsInputPanel.tsx` | **NEW** | A.3.2 spec; consumes `fact-questions.ts`; dispatches existing `EDIT`. |
| `_components/NoticesStrip.tsx` | **NEW** | A.7 #7; renders `notices` via reason-code copy map; dismissible; printed. |
| `_lib/{flow,mock-engine,tree,i18n}.test.ts` | **MODIFY** | Existing suites KEEP passing against curated mode (they are the rollback's regression net); add suites for `fact-mapper`, `decision-adapter` (all 5 states + invalid-payload degradation), `fact-questions` coverage, SHADOW invisibility (B.1). |
| `apps/mouth/src/lib/visa-oracle/types.ts` | **MODIFY** | Add `DecisionDTO`/`SourceRecordDTO`/`VerdictSource` types — ideally generated from `backend/services/visa_engine/contracts/decision.schema.json` + `source-record.schema.json` (schema_export exists precisely for this); `RecommendState` untouched. |
| `apps/mouth/src/lib/visa-oracle/api.ts` | **MODIFY** | Add `evaluateFacts()` (canonical facts POST) + `parseDecisionResponse()` with the same safety invariants as `parseRecommendResponse` (KEEP it as the legacy/v1 validator); `API_BASE` env pattern reused as-is. |
| `(visa-oracle)/visa-oracle/r/[public_id]/page.tsx` | **NEW (post-ENFORCE, same flag)** | Public result snapshot route (spec §6.2: persisted snapshot, never re-evaluates, no raw PII facts, no JWT) — the share/resume target behind QR and "save my answers." Server-fetched; renders the same OutcomeSheet in read-only mode. |

---

## E. CONSTRAINTS HONORED

- **GOV.UK skeleton + TurboTax behavioral canon** — already shipped and kept: one question per screen, mandatory Back, hint-one-sentence, never-dead-end, framing card before Q1, behavioral splitters ("who pays you") never code-questions. Every new element (NEEDS_INPUT panel, citations) follows the same one-thing-per-screen discipline.
- **Living-tree design language** — untouched: tree = primary/data, constellation = mood, card = outcome only. No 3D, no parallax, no tarot. The tree→card View Transitions morph (feature-detected, reduced-motion-safe) remains the verdict reveal.
- **vo2 design tokens** — all new UI consumes the existing `--oracle-*` tier (`oracle.css:17-111`) + shared core tokens from `packages/core/tokens/` (`--space-*`, `--motion-*`, `--accent-funnel` via `data-funnel="visa"`); no new token families, no hardcoded hex; light default, dark override, both AA.
- **WCAG AA** — new components inherit the house mechanics: live-region announcements (PathsCounter pattern), focus-to-heading on state change, icon+text never color-alone (citation/authority badges included), keyboard-operable disclosures, SR-only equivalents, ~grade-8 plain language; AAA aspiration on the verdict path.
- **Reduced motion** — citation/disclosure animations use the existing `useReducedMotion` gating + the CSS kill-switch (`oracle.css:1006-1020`); print and VT names already stripped under reduced motion.
- **Print stylesheet** — extended, not replaced: answers recap + checklist (existing) + Sources & verification + freshness stamp + `public_id` (new); interactive controls stay `.oracle-no-print`.
- **EN/ID parity** — compile-time + runtime parity, `kamu` ban, `BODY_FIRST`, Imigrasi-native ID terminology, native review pre-ENFORCE; new `lang` attribute sync (C.6).
- **noindex until ENFORCE** — kept; flip rides the ENFORCE PR (B.5).
- **No paid third-party libraries** — everything specified uses what's already in `apps/mouth/package.json` (framer-motion, lucide-react, qrcode — all free licenses) or hand-rolled code; zero new dependencies required by this spec.
- **Single all-inclusive price everywhere** — A.8; no PNBP/fee anatomy in any UI, receipt, print, or handoff payload; pricing failure never alters the legal verdict presentation.
- **UI adapts to the engine** — demonstrated concretely: the 4-tier eligibility chip is retired (A.7 #2), rank replaces score display, NEEDS_INPUT gets its missing skeleton, un-mappable answers stay UI-side review triggers instead of being smuggled into facts (A.7).

**Dependencies handed to other lanes (recorded, not designed around):** (1) recommend endpoint must embed resolved `sources: SourceRecordDTO[]` + pack-backed product display data (A.4.1/B.2); (2) fact-vocabulary gaps — review-gate items beyond `violation_history`, remote income floor (A.7); (3) DB-mode lever + shadow endpoint (STEP-6b/6c) — the UI contract above is stable regardless of their landing order; (4) FASE-2 content for the 7 pending lanes (C.3).

**Verification posture for this spec:** every claim above was read on disk in this worktree (HEAD `6419ed16cb`); where the engine is spec-only (evaluator PR5, flags, endpoints), the spec says so and binds the UI to the frozen JSON contracts in `backend/services/visa_engine/contracts/`, never to hoped-for fields. Nothing was written to disk.

