---
name: visaoracle
description: "Corner for Visa Oracle v2 — the immigration Decision Tree rebuild (Bali Zero flagship). Load FIRST on any Visa Oracle / visa funnel work."
---

## Notes (moved from description 2026-09-02)

Holds: live state, established truths, research log, loop protocol.

Split 2026-09-09 (context budget — this file was 145 KB/1,689 lines, and being a mandatory
corner skill it exhausted a Codex session's context before work started): the LIVE STATE
chronology and the two superseded snapshots moved into `.agents/skills/visaoracle/references/` —
`live-state-log.md` (full dated log), `CURRENT_STATE.md` (2026-08-15 archaeology snapshot),
`HANDOFF-2026-08-08-voa-conclusive-rate.md` (2026-08-08 diagnosis writeup). This file is now an
index; read `references/live-state-log.md` before claiming a track.

# VISA ORACLE v2 — Decision Tree (corner /visaoracle)

> **CURRENT HANDOFF (read first):** read **LIVE STATE — CURRENT POSITION** below FIRST — it is
> the current summary, refreshed on every state change. Full chronology:
> `.agents/skills/visaoracle/references/live-state-log.md` (read the newest entries before
> claiming a track). `references/CURRENT_STATE.md` is a SUPERSEDED 2026-08-15 snapshot (reviewed
> SHAs, gate matrix, evidence, safe resume sequence as of that date) kept as archaeology; many
> pack activations have shipped since it was last touched.

## Mission

Rebuild the Visa Oracle immigration funnel as Bali Zero's flagship public tool: an interactive
decision tree guiding foreigners to the correct Indonesian visa/stay-permit path. Bar: (a) stunning
interactive aesthetics ("immediatezza estetica"), (b) simple, impeccable content — zero wrong
answers, (c) authoritative enough to demo to Ditjen Imigrasi Jakarta, (d) a true expat guide.
Mandate: Zero, 2026-07-17. Working mode: multi-LLM deep-research ↔ brainstorm loop (unlimited
rounds), all work in worktree `mouth-visa-oracle` until final draft for operator analysis. This is
Subhi's surface (`apps/mouth`) — verification per CLAUDE.md §13 (CI + AI review, generator≠grader).

## ENFORCE-GATE (canonical ruling as of 2026-08-08 — NO-GO / SHADOW)

**The 2026-08-08 Zero ruling supersedes the 2026-07-19 gate proposal.** There
is no automated traffic-volume threshold for ENFORCE: no 1,000 sessions/7d,
no 100 real sessions/14d fallback and no Wilson lower-bound test. Organic
traffic measurements remain useful diagnostic evidence, but they neither
authorize nor mechanically block the mode change. The business-validation
gate is Bali Zero team heavy-testing and verification against the engine in
SHADOW. See
`research/visa/2026-08-08-decision-tree-v2-full-index-design.md` §4.

ENFORCE remains a distinct, explicit Zero-gated action. A session must not
infer pre-authorization from operational checks, a RulePack activation,
traffic counts or this skill. It must keep `VISA_ENGINE_EVALUATE_MODE=SHADOW`
until all of the following are true:

- the Bali Zero team has completed heavy manual SHADOW testing and signed off
  the observed outcomes;
- the current gold-persona replay has zero unexplained divergences;
- current decisions carry valid, in-force citations and no ungrounded claims;
- the kill switch has a current, independently reproducible rollback proof —
  **SATISFIED 2026-08-23**, see LIVE STATE below and
  `research/visa/2026-08-23-killswitch-rollback-proof.md` (this bullet alone; the other six are
  untouched and this does not authorize ENFORCE);
- the DPIA is complete, signed and its residual privacy risks are accepted;
- the real analytics destination/provider is identified and a fresh,
  closed-schema **365-day (12-month)** TTL proof has been independently
  reproduced (corrected 2026-08-23 — Zero's 2026-08-20 retention ruling,
  DPIA V2 §A, superseded the old 90-day provisional; §8 signed 2026-08-23,
  `docs/audits/2026-08-20-visa-oracle-dpia-v2.md`; still unsatisfiable
  today — the destination itself remains unidentified, see LIVE STATE
  below); and
- Zero explicitly authorizes the ENFORCE flip after the preceding blockers
  close.

**Current status: 🟢 ENFORCE IN PRODUCTION since 2026-09-06T01:1xZ — OWNER
OVERRIDE.** Zero flipped `VISA_ENGINE_EVALUATE_MODE=ENFORCE` on Fly
(`nuzantara-rag`) by his own explicit instruction ("accendi tutto",
2026-09-06, after being told the DPIA v2 §8 text still reads "DO NOT
ENFORCE" with two High residual risks open — analytics destination,
cross-border processor register — and that gold-persona divergences were
not re-measured on seq-19). The seven preconditions below remain the
documented standard; the ones still open are now RESIDUAL RISKS to close
in production, not blockers. Rollback is one command:
`fly secrets set VISA_ENGINE_EVALUATE_MODE=SHADOW -a nuzantara-rag`.

Traffic provenance must stay explicit while evidence is collected. Only
requests deliberately labelled `traffic_source=real` are organic evidence;
synthetic lanes stay separate and legacy/NULL rows are not silently promoted
to real traffic. This classification is diagnostic under the current ruling,
not an automated ENFORCE threshold.

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
- GLM 5.2 via TP1 seat `tp1-glm-5.2` (OpenAI-compatible base `https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`, key loaded by `load_tp1_settings_key()` from `~/.qwen/settings.json`) — ARMED (PONG). TP1 seats are roster lines, not CLIs.
- DeepSeek V4 — **DEAD** (balance -0.04 USD, is_available:false). Operator-only top-up. Declared
  substitute: house Sonnet web-grounded lane (live WebSearch, URL-verified).
- Harness scar (2026-07-17): Agent spawns WITH `name:` can be born dead (mailbox never delivered) —
  spawn anonymous for fan-out.

## Loop protocol (the pallegiamento)

Round N = 4-lane parallel deep research (Gemini width / Codex architecture+red-team / GLM design /
web-grounded verification) → orchestrator reports ALL content faithfully to Zero → brainstorm →
interesting points spawn round N+1 research. No round limit. Opus 5 orchestrates only (no hands,
hook-enforced — RULED 2026-08-20: Fable is out of the workflow, CLAUDE.md §5); Sonnet implements; research outputs persisted under `research/visa/` in the worktree
as `2026-07-17-visa-oracle-v2-round<N>-<lane>.md`.

## LIVE STATE — CURRENT POSITION (updated 2026-09-11; update on every state change)

- **Active production pack: seq-20**, version `2026.9.6`, `rule_pack_id ac0a792d-a38d-512e-9ead-54a5d008fb68`,
  109 rules, signed on M5 (`sign_pack.py`, kid `prod-2026-07-1`, `signed_at 2026-09-06T14:59:27Z`)
  and activated (`activation_id e08ebea9-d50f-48a6-989e-b7e4698f96ad`). Prod answers
  `sequence=20 version=2026.9.6`, re-proven by synthetic API + public-browser probes on
  2026-09-11 (Mini). The **21 dead ends / 22 answers over 43 walks is historical**.
- **Fresh walk census (2026-09-11, 67 scenarios, current repo + signed seq-20, offline):**
  without disclosure flags, **55 SUPPORTED / 10 NO_SUPPORTED_PATH / 2 NEEDS_INPUT**;
  with the actual frontend flags, **31 SUPPORTED / 7 NO_SUPPORTED_PATH / 29 HUMAN_REVIEW**.
  Same results at the pack's signing instant and the current clock. This is a synthetic
  sample, not organic traffic or exhaustive answer-combination coverage.
- **Review explanations reach the public UI, but coverage is incomplete:** 13/29 sampled
  reviews have a `REVIEW_REASON_COPY` entry; 16/29 use the generic fallback (ambiguous sponsor).
  `DISCLOSED_UNCERTAINTY_REVIEW` also uses that fallback, proven on the public site.
  The existing test admits 25 unmapped codes and misses three additional, reproduced
  `BRIDGING_*` review codes from `on_unknown=HUMAN_REVIEW` hard filters. A fourth omitted
  code (`VOA_NATIONALITY_ONLY`) is structurally eligible but not witnessed by this probe.
  Full audit, evidence, reproducible scripts and proposed success bar:
  `research/visa/2026-09-11-review-reason-audit/README.md`. Audit only; no runtime/copy changes.
- **Evaluate mode: ENGINE, under ENFORCE since 2026-09-06T01:1xZ** — OWNER OVERRIDE by Zero
  ("accendi tutto"), not a session-inferred authorization. Visitors of `/visa-oracle` now see
  real verdicts (SHADOW previously withheld every decision).
- **GARUDA VOA public funnel is LIVE** at `/visa/voa` (`GARUDA_PUBLIC_ENABLED=true` on both the
  Fly backend and the Vercel `mouth` Production env).
- **Rollback commands:**
  - evaluate mode: `fly secrets set VISA_ENGINE_EVALUATE_MODE=SHADOW -a nuzantara-rag`
  - VOA public: `vercel env rm GARUDA_PUBLIC_ENABLED production` + redeploy/promote
- **Open residual risks** (documented ENFORCE preconditions, now open in production not
  blockers): DPIA v2 two High rows (analytics destination, cross-border processor register)
  still unclosed; gold-persona replay not re-measured on seq-20; Bali Zero team manual sign-off
  still outstanding.
- **TRACK C claimed by mini-pro2/2026-09-11 — W-ORACLE window (SHWEB-20260911).** Binding spec:
  `research/visa/2026-09-11-oracle-final-window-spec.md` (v6.2). Chain, one PR each from fresh
  main: PR-O0 docs (this capture) → PR-O1 census with real disclosure flags + AST-derived
  review-code inventory → PR-O2 dedicated EN/ID copy for every known review code → PR-O3
  interview Δ1 (`family_sponsor_confirmed` on retirement/property + undecided) → PR-O4
  review-cause explanation Δ2 + neutral contact fallback. Owner decisions D1/D5/D6 recorded on
  the Mini desk 2026-09-11. Released in PR-O4.

Full chronology: `references/live-state-log.md` (read the newest entries before claiming a track).

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
- Final on-disk gate = an Opus 5 xhigh-effort session per track (RULED 2026-08-20, was Fable — CLAUDE.md §5); never delegated to the implementer.
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
