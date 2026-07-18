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
- 2026-07-18: TRACK A PR1 foundations pushed (M5) — merge commits against origin/main resolved by regenerating docs_sync markers (README/AI_ONBOARDING quick-numbers) rather than picking a side; PR #2654 open, automerge armed.

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
