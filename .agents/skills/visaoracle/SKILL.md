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
