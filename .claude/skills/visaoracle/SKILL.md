---
name: visaoracle
description: "Corner for Visa Oracle v2 — the immigration Decision Tree rebuild (Bali Zero flagship). Load FIRST on any Visa Oracle / visa funnel work. Holds live state, established truths, research log, loop protocol."
---

# VISA ORACLE v2 — Decision Tree (corner /visaoracle)

## Mission

Rebuild the Visa Oracle immigration funnel as Bali Zero's flagship public tool: an interactive
decision tree guiding foreigners to the correct Indonesian visa/stay-permit path. Bar: (a) stunning
interactive aesthetics ("immediatezza estetica"), (b) simple, impeccable content — zero wrong
answers, (c) authoritative enough to demo to Ditjen Imigrasi Jakarta, (d) a true expat guide.
Mandate: Zero, 2026-07-17. Working mode: multi-LLM deep-research ↔ brainstorm loop (unlimited
rounds), all work in worktree `mouth-visa-oracle` until final draft for operator analysis. This is
Subhi's surface (`apps/mouth`) — verification per CLAUDE.md §13 (CI + AI review, generator≠grader).

## Established truths (GROUND 2026-07-17, scout-verified file:line)

- **v1 is LIVE, not missing** — www.balizero.com/visa, last touched 2026-07-14, 29 commits/90d.
  "Rebuild" = experience + content layer, NOT greenfield.
- Frontend: `apps/mouth/src/app/visa/` — entry branch-selector ("Already in Indonesia?") →
  `/visa/clock` (expiry countdown, 133 lines) | `/visa/match` (4-step wizard:
  nationality→purpose→duration→budget, 315 lines); decision tree logic in
  `apps/mouth/src/lib/visa-oracle/quiz-logic.ts` (84 lines, 7 purposes); AI chat layer
  `apps/mouth/src/components/visa/VisaChat.tsx` (341 lines → `/visa-oracle/chat`); shareable hash
  result URLs; Playwright E2E `apps/mouth/e2e/visa-funnel-fusion.spec.ts`.
- Shared funnel framework: `packages/core/` (`@balizero/core`) — AppFrame / AppWizard /
  AppBranchSelector / useFunnelApp — proven across visa + property-eligibility + tax-calendar.
  REUSE-FIRST candidate #1.
- Also reusable: `apps/mouth/src/components/blog/interactive/DecisionTree.tsx` (553 lines, generic
  tree primitive).
- Backend (FastAPI, all registered in `router_registration.py`): `routers/visa_check.py` (346 l.,
  `/api/visa`: clock+match), `routers/visa_oracle.py` (928 l., `/visa-oracle`:
  recommend/chat/handoff/visa-types), `routers/knowledge_visa.py` (CRUD catalog, backs MCP
  list_visa_types/get_visa_details); services `visa_check/match_tree.py` (the real tree logic),
  `visa_oracle/visa_oracle_service.py` (471 l., scoring), `visa_unified/bridge.py`. Full pytest
  coverage exists.
- Data: `migrations_v2/124_visa_checks.sql` (visa_checks table, hash URLs); seed
  `seed_visa_types_complete_2026.py` = **114 visa codes** (A1→F4, incl. E28A investor, E33A-G
  digital-nomad/retirement family) — the canonical catalog; Qdrant `visa_oracle` collection ~90
  curated points.
- Paper trail: `docs/plans/2026-04-19-4apps/01-visa-check.md` (the executed v1 spec);
  `docs/superpowers/plans/2026-04-04-visa-oracle-implementation.md` + specs;
  `2026-04-21-visa-funnel-fusion.md` (PR #165); `2026-04-21-visa-catalogue-rebuild.md`. Unexplored:
  `apps/mouth/src/app/(assessment)/`, `apps/kb/data/immigration`.
- Unrealized vision from memory: "3D FUNNELS: Waypoint 1.5 (Overworld)" (2026-04-12) — candidate
  inspiration for v2 metaphor.

## Arsenal & seat status (probed live 2026-07-17)

- Gemini 3.1 Pro (High) via `agy` v1.1.3 — ARMED. GOTCHA: flag order changed vs v1.0 — use
  `agy --print-timeout 15m --model "Gemini 3.1 Pro (High)" -p "<prompt>"`; the old
  `agy -p --print-timeout 5m` feeds the FLAGS as prompt (RC=0, garbage out).
- Codex GPT-5.6-sol ultra — ARMED (PONG).
- GLM 5.2 via `claude-glm` — ARMED (PONG).
- DeepSeek V4 — **DEAD** (balance -0.04 USD, is_available:false). Operator-only top-up. Declared
  substitute: house Sonnet web-grounded lane (live WebSearch, URL-verified).
- Harness scar (2026-07-17): Agent spawns WITH `name:` can be born dead (mailbox never delivered) —
  spawn anonymous for fan-out.

## Loop protocol (the pallegiamento)

Round N = 4-lane parallel deep research (Gemini width / Codex architecture+red-team / GLM design /
web-grounded verification) → orchestrator reports ALL content faithfully to Zero → brainstorm →
interesting points spawn round N+1 research. No round limit. Fable orchestrates only (no hands,
hook-enforced); Sonnet implements; research outputs persisted under `research/visa/` in the worktree
as `2026-07-17-visa-oracle-v2-round<N>-<lane>.md`.

## LIVE STATE (update on every state change — whoever changes state updates this section)

- 2026-07-17: corner created. Round 1 research lanes in flight (Gemini/Codex/GLM/web). Worktree
  `mouth-visa-oracle` active. No PR — worktree-only until operator-analyzed final draft.
- 2026-07-17 (late night): ROUND 1 COMPLETE — 4 lanes delivered (Gemini survey / GLM design / Codex
  sol-ultra architecture+red-team / Sonnet web-verified) + repo scout map. Corpus persisted in
  research/visa/2026-07-17-visa-oracle-v2-round1-\*.md. Codex verdict: v1 NO-GO as legal engine (9
  P0s, 5 spot-verified on disk by orchestrator — see round1-verification-note). Panel canon: GOV.UK
  skeleton + behavioral interview (TurboTax) + living-tree design language + deterministic
  rules-as-data engine + visible-honesty moat. Chat demoted to escape-hatch explainer. Round 2 lanes
  fired: Gemini regulatory-delta (catalog staleness vs Kepmen M.IP-08/2025 index reclassification
  133→110 + Permen Imipas 10/2026), Codex engine-concretization, GLM interview design, Sonnet
  reuse-first OSS survey.
- 2026-07-17 (pre-dawn): ROUND 2 COMPLETE — 4 lanes delivered and persisted (gemini
  regulatory-delta: catalog has DEAD B211\* codes since Kepmen M.IP-08/2025 effective 2026-06-02,
  133→110 indexes, BVK now nationality-only per Permen Imipas 10/2026 [+6 states: TR/BR/PE/KZ/MO/BY],
  Permenkumham 36/2021 guarantor rules revoked by Permen Imipas 5/2025, regulatory-event cadence
  ~every 3-4 months; glm interview-design: framing card + Q0 date-driven onshore lanes + 10
  categories EN/ID + full behavioral trees Work/Invest/Remote + 5-state outcome skeletons + 10
  microcopy rules; codex engine-concretization: 110KB spec — visa_engine module layout, complete
  JSON Schema 2020-12 contract, RFC8785+Ed25519 signed anti-rollback bundles, tri-state evaluator
  with purpose-coverage hit policy, bitemporal SQL with append-only triggers, strangler plan with
  per-surface OFF/SHADOW/ENFORCE flags, 20 gold personas, file-by-file salvage map, 10 PR increments
  ≈41-56 eng-days; reuse-first: ZEN Engine MIT found [arbitration pending], xyflow+elkjs for
  /visualise, AGPL blockers identified, Stepperize license trap caught). Golden-visa stats conflict
  ARBITRATED by orchestrator: 1,274 visas / Rp52.1T VERIFIED-OFFICIAL (imigrasi.go.id siaran pers +
  Antara + CNN, as-of 2026-05-18; E28D Rp50.88T). Codex R2 spot-checks verified on disk: AppWizard
  onComplete is synchronous (packages/core/components/apps/AppWizard.tsx), api.ts hardcodes Fly
  fallback URL. Round 3 fired: Opus 4.8 xhigh fresh-context arbitration ZEN-vs-custom-evaluator.
- 2026-07-17 (dawn): ROUND 3 verdict — custom Python evaluator (Opus 4.8 xhigh arbiter, confidence 0.85;
  ZEN → authoring/visual only). RESEARCH PHASE CLOSED. Final draft composed:
  docs/plans/2026-07-17-visa-oracle-v2/00-product-design.md — awaiting owner analysis (mandate firebreak:
  worktree-only until analyzed). DeepSeek burn hunt still in flight.
- 2026-07-17 (dawn): OWNER RULING R1 applied to draft — single client-facing price, no PNBP/fee split
  (honesty = citations/assumptions/abstention, not price anatomy). Draft review ongoing, further rulings
  expected.
- 2026-07-17: R1 cross-family reviews done (codex×7, gemini×4; 2 REFUTED handled with recorded
  dispositions). Calling-visa corrected 8→7 (live-verified). Bridging ≥3-day interview-lane correction
  recorded.
- 2026-07-17: TRACK B claimed by Mini/2026-07-17 — content program active in worktree `research-visa-content` (lane research). FASE 1 in flight: Bridging Visa branch profile + D7A/D7B close-out + diaspora-index coverage check (per PR #2602 bonifica report Table 2). FASE 2 (7 interview categories) gated on PR #2602 merge.
- 2026-07-17: TRACK C claimed by Pro/2026-07-17 — experience track active in worktree `mouth-visa-experience-c1` (lane mouth; relocated from `mouth-visa-experience` after a twin-session filesystem race — twin's untracked work at `apps/mouth/src/app/(visa-oracle)/` left intact, candidate salvage for PR C2 once that session ends). PR C1: vo2 design tokens + mock interview model + `/visa-v2` prototype route (noindex, mock-only; engine wiring deferred until PR1 engine contracts land on main). C1 diff passed independent Codex GPT-5.6-sol review (6 P1 findings, all fixed in-PR).
- 2026-07-17: FASE 1 COMPLETE — `research/visa/2026-07-17-bridging-visa-branch-d7ab-diaspora-closeout.md` closes all 3 open Table-2 items: D7A/D7B/D8A/D8B RESOLVED-EXIST (per-code body-content discriminator, 2 dead-code negative controls), Bridging Visa fact-base primary-grounded (Permenkumham 11/2024 + Permen Imipas 3/2025 Pasal 45 partial-revocation resolved), diaspora COVERED (product-level, Kepmen-gated). Real cross-family adversarial review: Codex (gpt-5.6 refused locally, ran codex-mini-latest), 3 passes — 2 REFUTED-and-fixed, final pass REFUTED only on 2 wording nits, ALL load-bearing claims explicitly not refuted. PR #2607 open, auto-merge armed (SQUASH), all 40 CI checks green except "Backend Tests (Python)" still running (docs-only diff, no code touched). FASE 2 (7 interview categories) STAYS GATED: PR #2602 (bonifica, branch `agent/air-m5/mouth/visa-catalog-bonifica`) is still OPEN and now shows `mergeable: CONFLICTING` / `mergeStateStatus: DIRTY` — out of this track's scope to resolve (different lane/owner), flagging as external blocker.
- 2026-07-17 (night): PR #2617 E2E red diagnosed (Pro): CI-only — Next 16 dev blocks cross-origin dev resources for 127.0.0.1 baseURL, React never hydrates; visa-oracle-v2.spec.ts is the only CI e2e exercising hydration (latent repo-wide CI blind spot). Fix: allowedDevOrigins in apps/mouth/next.config.ts, verified locally (5/5 on 127.0.0.1). Pushed to the same branch; automerge already armed.
- 2026-07-18: TRACK C increment C3 shipped (Pro, worktree `mouth-visa-experience`, branch `agent/nuzantara/mouth/visa-experience-c3`) — verdict tree→card morph (View Transitions API + FLIP-style shared `view-transition-name`, feature-detected, spring-reveal fallback, reduced-motion instant swap), tree tap-to-edit (completed trunk steps are real buttons dispatching the existing EDIT action, guarded by new `isEditableTreeStep`), a real scannable QR (`qrcode` npm, reuse-first from `apps/wa-mirror`, synchronous SSR-safe SVG render — no canvas/network) beside the still-visible wa.me link, and a checkable + printable document checklist (real checkboxes, `window.print()` + dedicated `@media print` stylesheet, copy-summary with visible confirmation). Mock-only, single all-inclusive price untouched, EN/ID both updated. 58 unit + 9 e2e passing.
- 2026-07-18: TRACK C SHIPPED — PR #2617 (C2, consolidated living-tree experience) merged 00:21 WITA and proven live: `https://www.balizero.com/visa-oracle` (200, noindex meta present) is now the single Track C foundation; `/visa-v2` 308-redirects there and C1 artifacts were removed in the consolidation. Experience is mock-only (5-state RecommendState, 12-card catalog, EN/ID, WCAG AA); real engine wiring stays gated on PR1 engine contracts landing on main. Worktree `mouth-visa-experience` intentionally kept alive for the sibling session's post-merge follow-up (widening CI e2e coverage back to the 4 interactive tests).
- 2026-07-18: PR #2602 (bonifica) MERGED 2026-07-17T15:51Z — FASE 2 gate OPEN. PR #2607 had gone DIRTY after the night's LIVE-STATE merges (#2602/#2606/#2627/#2628 touch the same skill files); resolved the legal way (merge of origin/main into the branch, LIVE STATE lines reconciled, no force-push), automerge still armed.
- 2026-07-18 (S3 engine lane): TWIN-PR COLLISION ADJUDICATED by Zero (Legge 5): **ADOPT_A** — PR #2654 (M5 tree "A") MERGED to main (f73cbb4a); S3's PR #2718 (tree "B") CLOSED, its branch `agent/nuzantara/mouth/visa-engine-pr1-0718` intentionally KEPT as the PR3 seed (strong-Kleene evaluator + truth-table tests). Binding order from Zero: (1) correctness HOTFIX first — Codex gaps confirmed live in A, fix+guilt+innocence same commit; (2) PR1b port-list from B (only proven incremental value); (3) PR2 signed-bundle re-adapted to A's API with REDONE 3-seat verify; (4) PR3 from seed. Comparative A-vs-B report: `research/visa/2026-07-18-visa-oracle-v2-pr1-a-vs-b-portlist.md`. Hotfix branch `agent/nuzantara/mouth/visa-engine-hotfix-0718` in flight: 4 live gaps (canonical-date-literal P0, ordering-ops-on-enum-strings P1, GLOBAL+explicit-null P1, country-code-format P1).
- 2026-07-18 (S3, STEP 1 SHIPPED): hotfix **PR #2739 MERGED** to main 12:44Z (`8ac3184ce`) — 4 gaps fixed TDD-style (date literals P0 / ordering fail-closed P1 / country-code shape P1 / KnownDate calendar P0, the last found by the GLM refutation pass); **Gap C (Codex #8 GLOBAL+explicit-null) REFUTED at implementation** — deliberate round-4/5 schema design, evidence re-verified on disk, recorded in the report's §Post-implementation correction. Suite 235→258. 4-stage generator≠grader chain held (Sonnet implementer → GLM report pass → Codex sol-xhigh diff SHIP → Fable final gate). STEP 2 (PR1b) in flight on branch `agent/nuzantara/mouth/visa-engine-pr1b-0718`: 7/8 port-list items done (item 1 product_code dedup SKIPPED with evidence — bitemporal multi-version per product_code is the evaluator's intended §4.3 pattern; the B port would have broken it), suite 258→293, GLM diff review pending.
- 2026-07-18 (S3, STEP 2 + STEP 3): **STEP 2 SHIPPED** — PR1b **#2745 MERGED** to main (`8ac3184ce`→squash) 14:17Z: 9 hardening commits (F6 quote↔candidate, StrictBool×5, alias-only wire, registry (kind,value_format) consistency, +2 GLM-prescribed P2: `_DATETIME_SHAPE` ASCII, duplicate-candidate-id guard); item-1 product_code dedup SKIPPED, skip **independently confirmed** by GLM (SKIP-RATIONALE CONFIRMED) — follow-up for PR3: enforce uniqueness of the effective+ACTIVE slice per product_code. Suite 258→300. **STEP 3 (PR2 signed bundle) in flight** on branch `agent/nuzantara/mouth/visa-engine-pr2b-clean-0718` (the `-pr2b-0718` branch was W88-rebased onto fresh main to drop the now-squashed PR1b commits): `bundle.py` re-adapted to A's API, **fresh 3-seat verify** (GLM SHIP / Codex FIX-FIRST(1,4,5,6) / Gemini FIX-FIRST) → 11 FIX-NOW hardening applied (TOCTOU, env-bound keys, future-skew on signed_at, unsigned-into-PROD refusal, …), **3 findings REFUTED on the real model** (Codex bootstrap-sequence — model already enforces it; Gemini env-defaults-to-PROD and hex-uppercase — both blocked upstream). FIREBREAK intact (no key ceremony, unsigned fail-closed behind flag, never PROD). Suite 300→385. rfc8785+rfc3339-validator declared, lock honors manifest (W98). Round-4 regulatory recheck persisted on the closed B branch (M.IP-08/2025 effective 2025-06-02 per dictum KELIMA; BVK Permenimipas 10/2026 adds Macau — 19-state official list; number-collision trap with Permenkumham 10/2026 Second Home) — to be re-landed with a later PR.
- 2026-07-18: TRACK A PR1 foundations pushed (M5) — merge commits against origin/main resolved by regenerating docs_sync markers (README/AI_ONBOARDING quick-numbers) rather than picking a side; PR #2654 open, automerge armed.
- 2026-07-18: TRACK A PR1 MERGED — dual-PR1 collision (M5 #2654 vs sibling S3 #2718, same
  visa_engine foundations scope) adjudicated ADOPT_A via independent cross-family comparative
  review (Codex sol xhigh; verdict with file:line evidence posted on #2718, now closed as
  superseded). #2654 merged to main, merge commit f73cbb4a7b. Branch
  `agent/nuzantara/mouth/visa-engine-pr1-0718` (the S3 tree) intentionally preserved, not deleted —
  its strong-Kleene evaluator + truth-table tests are the PR3 seed.
- 2026-07-18: TRACK A next — PR1b port-list BEFORE PR2: (1) canonical YYYY-MM-DD literal
  validation, (2) semantic STAGE_ORDER (WARNING: the two trees disagree on ELIGIBILITY vs
  HUMAN_REVIEW precedence — arbitrate against
  research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-concretization.md before porting),
  (3) StrictBool on wire-level booleans, (4) common residual: JSON Schema `integer` accepts 2.0
  while StrictInt rejects (schema-valid/model-invalid gap). Then PR2 signing (Ed25519, RFC8785,
  anti-rollback). CodeQL note: iterate enums via `list(Enum)` in tests —
  py/non-iterable-in-for-loop is a required-check failure class (S3 cured it on their tree in
  commit 1a4360dc1b; A-tree tests should adopt the same pattern in PR1b).

- 2026-07-19: **TRACK A PR1b ARBITRATION RESOLVED + STAGE_ORDER CORRECTED.** The 2026-07-18 line
  126-134 WARNING above ("the two trees disagree on ELIGIBILITY vs HUMAN_REVIEW precedence —
  arbitrate against the round-2 spec") was itself resolved WRONG the first time: the M5 lane's PR1b
  attempt (worktree `backend-rag-visa-engine-pr1b`) arbitrated to the enum-DECLARATION order
  (HARD_FILTER→ELIGIBILITY→HUMAN_REVIEW→RANKING, matching enums.py's literal source order + the
  spec's JSON Schema enum listing) — flagged **P0 by tri-LLM review on its own PR #2781** and
  independently re-verified by re-reading the spec's §4.2 `evaluate_product` ALGORITHM pseudocode
  directly: the correct order is **HARD_FILTER→HUMAN_REVIEW→ELIGIBILITY→RANKING**, exactly what
  sibling PR #2773 already shipped (commit message: "the prior docstring's 'evaluated in this strict
  order' claim was wrong"). Declaration order ≠ processing order — do not re-litigate this without
  re-reading §4.2 fresh. Meanwhile a sibling S3 lane had independently re-shipped the whole PR1b
  port-list as **PR #2745 MERGED 2026-07-18T14:17:49Z** (after hotfix #2739, before PR2b #2757 and
  PR3 #2773 — all 4 verified MERGED via `gh pr view` against `Balizero1987/Teman2`), making the M5
  lane's #2781 a twin-race casualty: **CLOSED 2026-07-19T02:33:58Z**, no merge attempted, full
  investigative writeup on the PR. Items 1 (canonical date literals) and 3 (StrictBool) were also
  redundant against #2745's more mature equivalents. Only 2 of the original 5 port-list items were
  genuinely still unclaimed after a fresh `origin/main` content grep (no merged commit, no open
  PR/branch): CodeQL `list(Enum)` pattern (7 sites) and the JSON-Schema-vs-StrictInt integer-parity
  documentation+pin (line 130-131's "common residual" above) — both shipped via branch
  `agent/air-m5/backend-rag/visa-engine-pr1b-residual` (commit `fc24dc7913`, 492/492 suite green,
  ruff clean, docs_sync clean).
- 2026-07-19: **LEDGER GAP FLAGGED (not backfilled here — respecting "whoever changes state updates
  this file")**: lines 116-118 above narrate Track A only through "STEP 3 (PR2 signed bundle) in
  flight" — PR2b (#2757, merged 2026-07-18T17:45:52Z) and PR3 (#2773, strong-Kleene evaluator +
  2-seat fixes, merged 2026-07-18T19:34:19Z) both already landed on main since then but have no
  LIVE STATE entry recording it. Track A's own next-lane session should backfill STEP 4/5 entries.
  **Verified standing blocker**: Ed25519 key ceremony remains explicitly operator-side and undone —
  `bundle.py:269`'s own comment ("the key ceremony (generating...") plus the STEP-2/3 entry's
  "FIREBREAK intact (no key ceremony, unsigned fail-closed behind flag, never PROD)" both confirm
  signing code ships unarmed pending real production keys. With PR1→PR3 all merged, "Track A next"
  is genuinely PR4-6 (undefined in this file) gated behind that ceremony — NOT "PR3 evaluator", which
  is done.

## TRACKS — parallel work groups (multi-session coordination)

The v2 program runs as separate tracks, one per surface, coordinated ONLY through this skill. Any
session on any machine: load /visaoracle → read LIVE STATE → claim a free track → work exclusively
inside that track's path scope. Scopes are disjoint by construction, so parallel tracks cannot
merge-conflict.

| Track               | Path scope (exclusive)                                | Home machine | Dependencies                                                                                                                                                                          |
| ------------------- | ----------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A — Engine**      | `apps/backend-rag/backend/services/visa_engine/**`    | M5           | Serial chain: PR1 → PR2 (signing) → PR3 (evaluator) → PR4-6. Never parallelize within the chain.                                                                                      |
| **B — Content**     | `research/visa/**` (later curated kb via its own PRs) | Mini         | Bridging Visa branch, D7A/D7B + diaspora gap research: free NOW. The 7 interview categories: only AFTER PR #2602 (catalog bonifica) merges.                                           |
| **C — Experience**  | `apps/mouth/**` visa-oracle surfaces                  | Pro          | Prototypes/design-system with mock data: free NOW. Wiring to the real engine contract: only AFTER PR1 merges (schemas in `apps/backend-rag/backend/services/visa_engine/contracts/`). |
| **D — Ditjen demo** | (defined later)                                       | —            | Blocked until green gold-harness.                                                                                                                                                     |

**Claim protocol**

1. A track with an open `TRACK <X> claimed by …` line in LIVE STATE is TAKEN — pick another or coordinate.
2. Claiming = adding `TRACK <X> claimed by <machine>/<date>` to LIVE STATE in your track's FIRST PR; release it in the PR that closes the track.
3. Every PR from a track updates its own LIVE STATE lines (standing rule: whoever changes state updates this file).

**Quality invariants (identical for every track — parallelism never relaxes them)**

- Own worktree via `scripts/agent_start.py`; the main checkout stays read-only.
- generator≠grader before every push: cross-family adversarial review (Codex or Gemini seat) of the track's diff; the author never grades its own work.
- Final on-disk gate = a Fable session per track; never delegated to the implementer.
- Pre-push runs on the track's own machine (3 machines = 3 independent push queues). On M5: quiet-window rule — first loadavg value < 8 and zero real pytest processes before pushing.
- All established truths in this skill bind every track — including the single all-inclusive client price ruling (never a PNBP-vs-fee split).

## PENDING (W81 ledger, project-scoped)

- SEAT-DEEPSEEK: DeepSeek V4 balance -0.04 USD (probed live 2026-07-17) — panel runs 3-external-seat and house web lane, DECLARED degraded. Arming step: operator
  top-up (Zero). Proof-of-armed: 1-token live probe HTTP 200 with is_available:true.
- R2-BROWSER-LANE deferred: 403-blocked gov wizards (IRCC / Australia / US Visa Wizard) +
  evisa.imigrasi.go.id SPA + Awwwards pixel-study need claude-in-chrome browser automation — run in
  an attended session.
- WORKTREE-REBASE: branch is behind origin/main (2+ commits at last check) — rebase before the final
  draft PR.
- DEEPSEEK-BURN-ATTRIBUTION: fleet key consumed ~$48.75/30d (~1,100 req/day bursts; $10 top-up of
  2026-07-15 burned in 48h). Eliminated: instrumented scripts (ledger=pennies), Fly backend
  (llm_cost_events=0 rows), CI, OpenClaw config, intel pipeline, devils-advocate. Hunt agent
  dispatched (leads: cognitive oracle, war-room-v2, healer, mata-garuda). Do NOT top up until
  attributed.
