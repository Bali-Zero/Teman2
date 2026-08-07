---
name: visaoracle
description: "Corner for Visa Oracle v2 — the immigration Decision Tree rebuild (Bali Zero flagship). Load FIRST on any Visa Oracle / visa funnel work. Holds live state, established truths, research log, loop protocol."
---

# VISA ORACLE v2 — Decision Tree (corner /visaoracle)

> **CURRENT HANDOFF (read first):** `CURRENT_STATE.md` contains the canonical
> 2026-08-07 repository/production state, reviewed SHAs, gate matrix, evidence,
> open operational blockers and safe resume sequence. Its production verdict is
> **NO-GO / SHADOW** even though repository G0–G6 passed on the frozen baseline.

## Mission

Rebuild the Visa Oracle immigration funnel as Bali Zero's flagship public tool: an interactive
decision tree guiding foreigners to the correct Indonesian visa/stay-permit path. Bar: (a) stunning
interactive aesthetics ("immediatezza estetica"), (b) simple, impeccable content — zero wrong
answers, (c) authoritative enough to demo to Ditjen Imigrasi Jakarta, (d) a true expat guide.
Mandate: Zero, 2026-07-17. Working mode: multi-LLM deep-research ↔ brainstorm loop (unlimited
rounds), all work in worktree `mouth-visa-oracle` until final draft for operator analysis. This is
Subhi's surface (`apps/mouth`) — verification per CLAUDE.md §13 (CI + AI review, generator≠grader).

## ENFORCE-GATE (Zero pre-authorized the flip, Legge 5 exercised 2026-07-19 — OBJECTIVE gate, never early)

**Firebreak change (durable).** The ENFORCE flip on the public Visa Oracle surface was previously
"Zero's decision only" (Legge 5). Zero has now PRE-EXERCISED that decision (2026-07-19, genuine message):
the SESSION may execute the ENFORCE flip itself **without returning to ask** — but ONLY when the objective
gate below is ALL-GREEN, and NEVER a flip in anticipation. If any criterion is red/unmeasured, ENFORCE stays
OFF; the session keeps the engine in SHADOW and keeps collecting evidence. This authorization is conditional
on the gate, not a blanket unlock. (Any change to the engine's legal _content/logic_ still re-opens the
gate — a green gate certifies the engine as it was measured, not future edits.)

**Prerequisites (both must hold before the gate can even be evaluated):**

- PR4 #2804 merged to main ✅ (2026-07-19, squash `4f8f40ee48` — bitemporal substrate live on main).
- SHADOW wiring LIVE on the real surface (STEP-6c): engine runs on real end-user requests, output written to
  the audit log / `visa_decisions` ONLY, never rendered to the client. Until this is live there is no
  evidence to measure, so the gate is trivially red.

**The four criteria (ALL must be objectively green, measured from the SHADOW audit log):**

- **G-a — VOLUME (threshold proposed + set by the session, per Zero's instruction).** ≥ **1,000** distinct
  real end-user requests processed end-to-end by the engine in SHADOW (each producing a tri-state verdict +
  an audit record), accumulated over a window of **≥ 7 consecutive days** (not a single-day burst — catches
  day-boundary / regulatory-delta edges), AND with breadth ≥ **all 7 interview categories** exercised and
  **≥ 30 distinct visa codes** hit (so the volume is not concentrated on 2–3 popular paths). Rationale: 1k
  real requests over a week across ≥30 codes exercises the decision tree's live branches well beyond the 20
  gold personas' designed cases, surfacing the long tail before any client sees an ENFORCE verdict.
- **G-b — GOLD PERSONAS.** 20/20 gold personas replay through the engine with **zero unexplained
  divergences** (any divergence from the expected verdict must have a written, accepted explanation — a
  regulation change, a deliberate design correction — never an unexplained mismatch).
- **G-c — GROUNDING.** Every SHADOW verdict in the window carries **valid citations** and **zero ungrounded
  claims** (no verdict asserts a rule/number/eligibility without a resolvable, in-force source; abstention
  where evidence is thin is a PASS, not a divergence).
- **G-d — ROLLBACK PROVEN.** The ENFORCE→OFF rollback flag is **drilled and proven instantaneous** (a
  recorded drill: flip ENFORCE, then flip back to OFF, confirm the public surface stops consulting the
  engine immediately — no redeploy, no cache lag). ENFORCE is never armed without a proven kill-switch.

**GATE STATUS: 🔴 RED (2026-07-28 — collection is LIVE and MEASURED; NEITHER of the two counted lanes can
currently mature G-a, for two different reasons).** Receipt: `research/visa/2026-07-28-shadow-gate-measurement.md`
(re-runnable SQL inline). Measured on prod `visa_decisions`: **1,483 rows / 14 distinct fingerprints /
4 days / 3 categories / 0 distinct visa codes**, every row `HUMAN_REVIEW_REQUIRED` with an EMPTY
`candidate_summary` — G-a red on every component.
**The finding is a LANE ASYMMETRY, not a dead end.** On **RECOMMEND** (the `noindex` `/visa-oracle`, source
of all 1,483 rows) `fact-mapper.ts:360` sends `person.nationalities: NOT_ASKED`, and the pack's GLOBAL rule
`review.calling-visa` carries `on_unknown: HUMAN_REVIEW` (`rulepack-prod-001.source.json:1826-1845`) — a
correct fail-safe meeting an interview that never asks. So that lane abstains by construction and its rows
are worthless as breadth evidence. On **MATCH** (STEP-6c, the `/visa` funnel that HAS organic traffic) all
three blockers are absent: it sets nationality from the 4-field submission (`shadow.py:242-268`), its
fingerprint is `SHA-256` of a per-submission RANDOM token (`shadow.py:399`, `repository.py:115` — so its
1,000-distinct threshold is traffic-bounded, NOT interview-bounded), and the collector counts it
(`EVIDENCE_ENGINE_SURFACES={"MATCH","RECOMMEND"}`). It has ZERO rows because it is off: `fly secrets list`
(run 07-28) shows TRUST_STORE / DRIVER_TOKEN / EVALUATE_MODE / FINGERPRINT_KEYS deployed and **no
`VISA_ENGINE_MATCH_MODE`**, which defaults OFF (`shadow.py:207`). **⇒ BUT DO NOT JUST ARM IT — see the
07-28 correction below: the MATCH writer does not label its rows, so they would land `traffic_source
IS NULL` = legacy = counted toward NEITHER G-a gate. Arming alone is a **G-a** no-op (those rows DO
still feed G-c, which is deliberately not split by provenance).** Also: 1,464 rows are THREE byte-identical payloads at 3-4s cadence, all labelled
`traffic_source='real'` (the 07-27 contamination defect, 3 orders of magnitude larger) — G-a-vol is not
measuring adoption until that label is split. **On ENFORCE, correcting a wrong first reading:** the
authoritative render IS unbuilt (`resolve_response_mode()` returns literal `CURATED`,
`evaluate_path.py:197`) and that is an unnamed prerequisite of the flip — but the **kill-switch is NOT
inert** (OFF short-circuits before engine/pack/DB, `evaluate_path.py:554-556`; ENFORCE evaluates and
persists), so **G-d is drillable TODAY**. G-b's replay still targets the gold FIXTURE pack
(`gold_replay.py:160-170`), not the ACTIVE `446ee4ee`. The session updates
this line as criteria go green,
with the evidence pointer (audit-log query + gold-persona replay report + rollback-drill capture) for each.
Evidence is collected from the SHADOW audit substrate; nothing here is self-attested — each green needs a
re-runnable measurement (generator≠grader on G-b/G-c: the grader is not the engine).

**Flip procedure (when GATE STATUS goes 🟢 all-green):** the session executes the flip itself, captures the
before/after (flag state, a live ENFORCE verdict on a real request, the audit record), and reports the
outcome to Zero — flip done + evidence, not a request for permission. Then it stands ready to execute the
G-d rollback on any anomaly.

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

- 2026-08-07 (Mini, Visa Oracle V2 completion): **REPOSITORY CANDIDATE G0–G6 PASS;
  PRODUCTION REMAINS NO-GO/SHADOW.** Exact independently reviewed delivery
  `e15fc1b84501cbdc2e023497b3e1af298f51034f`, baseline `cd343655c`, verdict
  0 BLOCKER / 0 MEDIUM. Migration 267 closes atomic complete-set legal-period
  correction; `activate_pack` now binds separation to real `session_user` and
  rejects the same-login/two-`SET ROLE` attack. Privacy Policy V1, exact
  PricingTool, retention scheduler artifacts, official Calling Visa archive,
  five-state UI and real backend authority are repository-ready. Mini/Pro were
  out of sync at handoff and the branch was behind later `main`; do not merge or
  ENFORCE before sync/rebase, impacted G5/G6, role/migration provisioning,
  analytics TTL proof, DPIA, production smoke and kill-switch drill. Full state:
  `.agents/skills/visaoracle/CURRENT_STATE.md`.

- 2026-08-08 (Mini, night 07→08, operational gates executed): **ONLINE IN
  SHADOW — every operational blocker from the prior entry now proven green
  in real production, except the 2 that stay Zero-only (DPIA, analytics TTL)
  and ENFORCE itself.** PR #3732 merged to `main` (`63234a12a`). D1 roles
  provisioned; P0 outage (D1 broke `FOR SHARE` in 3 migration-264 triggers)
  diagnosed and hand-cured same night, PR #3766 open to codify as migration
  268 (idempotent catch-up, not a new prod change). Privacy Policy V1
  registered; retention scheduler installed on Mini and later flipped
  `APPLY=true` (real deletions, confirmed healthy from 16:01:37Z). Cell
  sensor + Telegram P0-on-failure alerting both confirmed armed (a benign
  false page fired once during a DSN test bug, worth mentioning to Zero, not
  a real incident).

  Cameroon/Guinea Calling Visa fix activated as `rulepack-prod-003` (seq 3,
  version `2026.8.8`, `rule_pack_id 37be33e4-8fbb-55bc-8fe2-7dcb23eab979`,
  activation `783f5fcc-d7cd-4cc5-ba22-c6724d4a3bf1`, reason
  `g1-calling-visa-retroactive-fix`, 16:34:34Z). `rulepack-prod-002` (the
  first attempt, seq 2, `valid_period.from=2026-08-06`) was signed and
  inserted but the bitemporal guard refused activation twice — its
  legal_period did not fully cover `prod-001`'s still-open
  `[2026-07-25, ∞)`; its row is now permanently inert (append-only, sequence
  unique per env/jurisdiction/domain). Fix: re-signed identical content as
  seq 3 with `valid_period.from=2026-07-25` (retroactive — the official
  CM/GN removal sources predate the whole contested window). New
  `rule_pack_id` convention adopted (historical one not reconstructable from
  2 samples): `uuid5(NAMESPACE_URL,
"https://balizero.com/visa-oracle/rule-pack/<ENV>/<JURISDICTION>/<DOMAIN>/<sequence>")`.
  A mandatory pre-activation semantic diff caught one change outside the
  expected CM/GN/NE scope (`LIMITED_STAY.extension_policy.allowed
true→false`) — verified deliberate (G1 packet point 9, fail-closed
  `UNKNOWN` invariant), Zero-approved, not a defect.

  Live smoke 3/3 (16:37:16–16:37:37Z), all citing `sequence=3/version
2026.8.8`: Cameroon → normal document path, no more `CALLING_VISA_REVIEW`
  (the fix); **Nigeria → still `CALLING_VISA_REVIEW` only** (positive
  control, mechanism stays armed); Italy → unchanged baseline. Freshness gap
  closed: all 28 sources now `CURRENT` (19 portal @ 7d, 9 primary-law @
  365d) vs the previously-active pack's `freshness_policy=null` on every
  source. Independent post-activation DB re-verification (separate
  operator): 2 activation rows, seq 3 current, seq 1 closed with no gap.

  Kill-switch drill executed both directions and proven (not just
  rehearsed): `SHADOW→OFF` 16:10:50Z, verified `EVALUATE_SURFACE_DISABLED`
  by 16:12:28Z; `OFF→SHADOW` 16:12:43Z, verified restored by 16:13:44Z, all
  4 machines consistent — this doubles as the rollback proof. Engine
  confirmed live `VISA_ENGINE_EVALUATE_MODE=SHADOW`; ENFORCE was never
  requested or flipped, remains blocked on the DPIA/analytics-TTL items.
  Full evidence: `.agents/skills/visaoracle/CURRENT_STATE.md` §"Production
  operational verification"; memory
  `ops_visa_oracle_pack003_gates_proven_2026_08_08.md`.

- 2026-08-08 (Mini, second entry same day — 0%-conclusive-rate diagnosis): **ROOT
  CAUSE FOUND for the prod ledger's 6,610/6,610 `HUMAN_REVIEW_REQUIRED` (0%
  conclusive).** Not a fact-collection gap — a live SHADOW `evaluate` call
  (`mode:CURATED`, innocuous) with ALL 40 facts supplied (IT/TOURISM/10d/valid
  passport) still returned `HUMAN_REVIEW_REQUIRED`, citing 15 review reasons, all
  `hr.d1-*`/`hr.d2-*`/`hr.d12-*` (consular-visa siblings), zero mention of B1.
  Mechanism: 31/63 `PRODUCTS`-scoped `HUMAN_REVIEW` rules in the active pack (seq 3,
  content = `rulepack-prod-002.source.json`) are keyed on `intent.purposes` alone
  (± `stay_days`) — always TRUE for the declared purpose, regardless of which
  product route the applicant actually wants (D1/D2/D12 don't even check
  `intent.entry_pattern`/purpose-specificity) — and `evaluator.py:1391-1397`'s
  documented precedence ("REVIEW beats SUPPORTED unconditionally", `enums.py:41-47`)
  lets ANY one reviewed sibling product mask a fully-eligible B1 candidate in the
  same purpose-set. Systemic, not TOURISM-specific — the 31-rule pattern spans
  EMPLOYMENT/STUDY/FAMILY/TOURISM/BUSINESS/INVESTMENT categories, explaining the
  ledger's near-100% abstention across all purposes, not just tourism. Full
  root-cause write-up + ordered fix list (RulePack seq-4: narrow D1/D2/D12 scope +
  add VOA-eligible-nationality gate to `el.b1.tourism`, currently absent) in
  `.agents/skills/visaoracle/HANDOFF-2026-08-08-voa-conclusive-rate.md`. Deploy
  pipeline note (unrelated to this diagnosis, found while checking state): PR #3766
  (migration 268, retention-binding `SECURITY DEFINER`) merged to main
  (`9d27f0f84`), but its post-merge Fly deploy **failed** — `must be owner of
function public.bind_visa_evaluate_idempotency_retention_policy` (least-privilege
  ownership gap on the release-command role) — no fix PR open yet as of this commit;
  does not block the RulePack-only fix above (pack changes go through
  `activate_pack.py`, not a schema migration). GATE STATUS (ENFORCE) unchanged: 🔴
  RED, DPIA/analytics-TTL still Zero-only.

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
- 2026-07-19: TRACK A key ceremony DONE — 2 kids minted (`2026-07-test-1`/TEST, `2026-07-prod-1`/PRODUCTION); private-key custody M5 `~/.config/nuzantara/visa-signing/` (0600/0700, not in Keychain, not on Pro/Mini); Fly secret `VISA_ENGINE_TRUST_STORE_KEYS_JSON` staged on `nuzantara-rag` (digest `a68f076bc9993f0c`) — inert until SHADOW wiring. Runbook: `docs/runbooks/visa-engine-key-ceremony.md`. Engine chain complete on main: PR1 #2654, PR1b #2745 (+residual #2795), PR2b #2757, PR3 #2773. Next: RulePack legal authoring + SHADOW wiring.
- 2026-07-19: TRACK A **AUTHORING claimed by M5** — RulePack authoring+signing pipeline is bound to M5 by key custody (private Ed25519 keys exist only on M5); next increment: offline authoring/signing tool + first signed TEST pack from the bonified catalog. S3/other lanes: coordinate here before touching authoring.
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
- 2026-07-19: GOLD HARNESS (G-b) shipped by M5 (`backend/tests/services/visa_engine/gold_harness/`)
  — 20 self-authored personas + hand-designed rule pack + a Decision-agnostic thin adapter (built
  because PR5 was OPEN, not merged, at task launch) + 3 real metamorphic property tests
  (monotonicity, fact-order invariance, rule-order invariance, fixed seeded shuffles) + a
  replay-report JSON evidence-artifact CLI.
- 2026-07-20 (CORRECTION, discovered on merge — read this before citing G-b evidence): **PR5
  merged overnight** (`c26211da2e`, #2841, "Decision evaluator — pure tri-state orchestrator") and
  it ships its OWN canonical 20-gold-persona acceptance suite (spec §7's literal persona table,
  `backend/tests/services/visa_engine/test_evaluator_gold.py` + `_gold_fixtures.py`) run directly
  against the REAL `evaluator.evaluate()` — that suite, not M5's harness, is the stronger/primary
  G-b evidence (real engine, not a stand-in adapter). M5's harness predates the merge and uses its
  own non-canonical persona set + rule pack against its own adapter, so it should be read as
  COMPLEMENTARY evidence, not the G-b primary satisfier: it adds two things PR5's suite does not
  have — per-product proof-state assertions (PR5 asserts global `DecisionState` only) and genuine
  input-order metamorphic invariance (PR5's `test_evaluator_determinism.py` proves repeat-call
  purity, not fact-dict-order/rule-declaration-order invariance). Follow-up owed: port the
  fact-order/rule-order metamorphic properties onto the real `evaluator.evaluate()` directly (the
  highest-value reconciliation) and settle G-b's canonical evidence pointer — likely PR5's suite
  plus a ported property-test file, with M5's `gold_harness/` package retired or kept only as
  design reference. Do not cite M5's harness alone as "G-b satisfied."
- 2026-07-20 (M5, overnight coordinator sweep): ceremony runbook **#2861 MERGED** (`1f16223335`),
  gold-harness package **#2876 MERGED** (`1606f7af25`); RulePack authoring pipeline
  (`compile_pack.py` + offline `sign_pack.py` + first signed TEST fixture) **PR #2869 in flight**
  (mergeable, CI running, 2 Codex adversarial rounds cured, round-3 confirm died on network —
  shipped under authorized fallback with a transparent PR-body note). Both PRs fought the same
  DOCSYNC conflict (`docs/DOCS_INVENTORY.md`) four times overnight as main advanced ~15 commits —
  cured each time by regenerating via `scripts/docs_inventory_regen.sh`, never side-picking. A
  **Kimi session** was independently reconciling the same two PR branches in parallel from
  `/tmp/wt-2876-gold` — its commits carry the SAME git author identity as this machine's session
  (Kimi inherits the global `git config user.name/email`, has no committer identity of its own),
  which caused two pushes to be rejected as "behind" before the pattern was recognized; resolved
  by fetch+legal-merge each time, never force-push, no work lost on either side. Detail:
  memory `discovery_kimi_parallel_worktree_pr2876_2026_07_20`. SHADOW-wiring prerequisite for the
  ENFORCE-GATE (STEP-6c) still not live — S3/Pro's PR #2824 (migration 252 SHADOW substrate)
  remains the actual blocker for evaluating any gate criterion, G-b included.
- 2026-07-21 (Pro, SHADOW evidence lane): prior blocker superseded — **#2916 MERGED**
  (`8b28ac418481`, STEP-6c Match wiring), **#2930 MERGED** (`09f7cd2273c9`, real HMAC
  facts-fingerprint provider), and **#2952 MERGED** (`60c6f348c9a4`, finite activation-system-period
  guard). Production release 3888 is deployed, but collection remains dark: Fly has only the Visa trust
  store, while Match mode and the facts-fingerprint key are absent. Read-only DB proof is separately
  blocked because the `nuzantara_readonly` Keychain password is absent; no write-capable fallback used.
  Worktree `backend-rag-visa-oracle-shadow-evidence` now prepares migration 255 plus a PII-free,
  fail-closed G-a/G-c collector and CLI; 1,070 Visa-engine tests collected with all runnable tests green
  (one pre-existing executor-role skip). **No PR, merge, deploy, secret change, SHADOW activation, or
  ENFORCE activation performed.** Receipt:
  `research/visa/2026-07-21-shadow-evidence-collection.md`.
- 2026-07-22 (Pro, SHADOW evidence lane): Kimi review follow-up adds direct G-c,
  collector, CLI, and legacy fail-closed coverage; `duplicate_evaluations` now counts only
  repeated valid 32-byte fingerprints. The focused local-test-DB suite is green (57 tests;
  SHADOW evidence module 85.30% branch coverage). **L3/L4 remain deferred; ENFORCE remains OFF.**
- 2026-07-23 (M5, Kimi architect session): full state-analysis + 4-seat adversarial panel
  (gemini/codex/design-house/web-grounded — GLM seat degraded, Keychain token absent via SSH)
  synthesized into the definitive correction+completion plan:
  `research/visa/2026-07-23-architect-review-synthesis.md` (analysis + 4 lane files alongside).
  Verified discoveries: (1) **v1 funnel dead since 2026-04-25** — the auth floor (PR #108)
  never registered `/api/visa/*` in `public_endpoints.py`; POST 401s through the catch-all
  proxy; 28 `visa_checks` rows total, all ≤2026-04-21; sibling endpoints clock/match-hash
  equally dead. (2) **SHADOW-on-v1 feeds only 3/35 FactPaths** — weak gate evidence; plan
  moves SHADOW to a new full-fact evaluate read-path API (gate-blocking, Track A). (3) Gate
  "7 categories" matches no vocabulary (255 enum=8 incl. `other`; v2 interview=10; business/
  diaspora uninstrumented). (4) Kepmen M.IP-08.GR.01.01/2025 **effective 2025-06-01** (dictum
  KELIMA, primary source; B211\* death = dictum KEEMPAT); "Permenkumham 10/2026 Second Home"
  REFUTED (notary PMPJ — the parked round-4 recheck note must be corrected before re-landing);
  BVK = 19 states/SARs + 1 entity (Permen Imipas 10/2026, effective 2026-07-09). Plan forks on
  **owner decisions D1 (G-a semantics/threshold vs ~7/day organic traffic) / D2 (110-code pack
  for ENFORCE) / D3 (adopt 9 E-gates)**. GATE STATUS unchanged: 🔴 RED.
- 2026-07-23: correction+completion plan lands as PR (research/docs-only, no automerge);
  next executable items: P0-1 registry fix `/api/visa/*` + telemetry, P0-3 read-path API,
  P0-4 RulePack first slice (E28/E33/BVK/Bridging mandated), P1-1 G-b independent replay.
- 2026-07-23 (late): **FABLE 5 FINAL GATE on the plan** (seat `zero@balizero.com`, requested
  by Zero) — verdict **FIX-FIRST**: plan adopted with **7 deltas** (full report
  `research/visa/2026-07-23-architect-review-fable5.md`, addendum in the synthesis). Headline
  blind spot: under D1(c) as written **G-a and G-b collapse into the same test** (facts
  collectible for only 3/10 interview categories + no synthetic marker → breadth could only
  come from the same corpus G-b replays). Deltas adopted: migration 256 `is_synthetic`/
  `traffic_source` column; G-a split into `G-a-vol` (real, owner-set) + `G-a-breadth`
  (corpus, labeled); P0-3 must emit `request_category` + 10-tile→8-enum mapping + explicit
  business/diaspora ruling; DAG names the window's traffic source; D2 coupled with Track B
  FASE 2 (110 codes AND behavioral trees per launched category); NEEDS_INPUT disclaimer fix
  (`OutcomeSheet.tsx:455`, Law-2-adjacent) promoted into the P0-1 batch; DB/Fly facts marked
  receipt-owed for the D1 threshold decision. Fable D-recs: D1(c) split as above / D2 adopt
  with FASE-2 coupling / D3 adopt with tiers (E-a/E-e/E-g blocking; E-b/E-f fast-follow).
  Conflict adjudicated: Gemini's deadlock claim WRONG (evaluate endpoint ≠ UI launch),
  Codex/design/orchestrator RIGHT. GATE STATUS unchanged: 🔴 RED.
- 2026-07-24 (M5, Kimi orchestrator): **WAVE 0 + W1a LANDED on main.** Merged: #3032
  (`8875b95ad35b`, `/api/visa/*` public — **v1 funnel resurrected**, live smoke 201 + row 29
  in `visa_checks` after 3 months dead), #3033 (`0185dc5c9c24`, disclaimer all-5-states +
  PII-free `app_form_submit_failed`), #3038 (`6e88b24b6773`, next-steps gated on
  SUPPORTED_CANDIDATES — Fable MEDIUM, owner call "fai tu"), #3046 (`7f99e570147d`,
  migration 256 `traffic_source` + collector G-a-vol/G-a-breadth split). All Fable-gated
  SHIP, all merged by the **delegated Opus verifier** (new pattern per Zero: "io non faccio
  review, chiedi a opus" — build=agents, gate=Fable, merge=Opus seat `claude-zero-team`;
  note the seat caps ~4:20 WITA reset and acct2/3/4 are NOT logged in). **Codex CLI auth
  DEAD on M5** (401, operator re-login needed — graders fall back to Opus per Zero).
  **W1b in flight** (evaluate read-path API, agent lane `visa-evaluate-endpoint`).
  #3034 (G-b) still open on the docsync treadmill (3rd regen pushed; content SHIP-verified
  twice). #3028 (this corpus) R1-green but blocked by a **main-side npm-audit failure**
  (find-my-way/hono/prisma, 3 high — infra-lane fix needed on main, not the visa lane).
  R1-gate lesson recorded: `adversarial_review:` accepts only gate seats
  (agy/codex/gemini/glm/gpt-5.5/grok/kimi*/nlm) + `human-*`/`exempt-\*`, and every research
file needs a `## Adversarial review` body section with surviving-objection dispositions.
  GATE STATUS unchanged: 🔴 RED.
- 2026-07-24 (M5, Kimi orchestrator, evening): **WAVE 1 100% on main + W2 KICKED OFF** (Zero:
  "parti ora"). Wave 0+1 all merged: #3032 (funnel resurrected, live-smoked 201), #3033,
  #3038, #3046 (mig 256), #3028 (corpus), #3060 (mig 257, owner-merged), #3061 (**evaluate
  read-path API live on Fly** — prod smoke: strict no-echo validation, fail-closed
  TEMP/`CURATED`, 0 rows), #3034 (G-b metamorphic+replay), #3079 (runbook+reports). Gemini
  adversarial pass on W1b caught 5 real findings (chunked-OOM, rollback rows, synthetic
  abuse, param echo, blind hint) — all cured and Opus-verified SOLID pre-merge; Opus is the
  delegated merger (Zero: "io non faccio review"); codex CLI still dead; Opus seat caps
  ~4-5h cadence; prettier-3.8.4-vs-main skew and docsync/inventory date-drift are the two
  recurring repo-wide friction points (both flagged for infra). **W2 RulePack factory
  started**: 4 research lanes in flight (E28+ BVK via Gemini/agy; E33 + Bridging via house
  seats) producing per-code fact-bases (`research/visa/2026-07-24-w2-factbase-*.md`) for the
  30-priority-code pack; signing stays M5 (Track A), FASE 2 trees stay Mini (Track B).
  Next: rule authoring → sign → activate → arm SHADOW per
  `research/visa/2026-07-24-shadow-arming-runbook.md`. GATE STATUS unchanged: 🔴 RED.
- 2026-07-25 (M5, Kimi orchestrator, ~04:00 WITA): **W2 FIRST PACK SIGNED + ON MAIN.**
  `#3092` (`c33c183ad8ea`, 12 fact-bases corpus) and `#3090` (`3c412c96b085`, first signed
  PRODUCTION RulePack: **38 products / 110 rules / 28 sources**, `compile_pack` zero errors,
  kid `prod-2026-07-1`, `payload_sha256 47a97c32…`, Fable gate SHIP with adversarial
  counter-probe) both merged. Chain: 8 fact-bases (live primary sources 2026-07-24, 2
  Gemini grade rounds with dispositions) → 2 authoring agents (A1 18p/47r, A2 20p/63r, zero
  overlap) → assemble → compile → sign → verify. **Kid-pattern bug found+fixed at first
  signing** (ceremony kids start with a digit, fail the engine's `IDENTIFIER_PATTERN`;
  relabeled `test-2026-07-1`/`prod-2026-07-1` same key material; Fly trust store re-staged
  digest `ab319439ecf92a0f`; errata in `docs/runbooks/visa-engine-key-ceremony.md`).
  **Detect-secrets cure**: pack hashes audited in baseline + naming-scoped triage rule
  (`contracts/packs/rulepack-*.json`). **Next: activation addendum
  (`research/visa/2026-07-25-activation-addendum.md`)** — provision `visa_activation_executor`
  (one-time, operator), build the small `activate_pack.py` ops tool, activate, then the 3
  SHADOW secrets + smoke per the arming runbook. GATE STATUS unchanged: 🔴 RED.
- 2026-07-25 (M5, Kimi orchestrator, ~12:30 WITA): **SHADOW IS LIVE IN PRODUCTION — first
  real evidence row.** The full activation arc is done: `activate_pack.py` ops CLI built
  (PR #3101, 8/8 tests, dry-run verified); fingerprint HMAC key store minted (kid
  `fp-2026-07-1`, M5 custody) + 3 secrets set on Fly (`VISA_ENGINE_EVALUATE_MODE=SHADOW`,
  `VISA_ENGINE_FACTS_FINGERPRINT_KEYS_JSON`, `VISA_ENGINE_DRIVER_TOKEN`); roles provisioned
  on prod PG (`visa_activation_executor` NOLOGIN + grants on `nuzantara_rag`, ops role
  `visa_activation_operator` LOGIN granted executor — Fly PG is 2-machine HA, primary
  `5683e090f3d228`, `OPERATOR_PASSWORD` from keeper environ; `fly pg connect` hangs on
  wireguard — use `fly ssh console -C` + `fly ssh sftp put` with `--machine` pinning, sftp
  never overwrites); **pack ACTIVATED** (`activation_id bb35cb81-276d-4a6e-8570-e46a2c692777`,
  actor token `operator.zero-2026-07`). **Smoke green end-to-end:**
  `POST /api/visa-oracle/evaluate` now returns a real engine verdict
  (`HUMAN_REVIEW_REQUIRED` + `BRIDGING_FROM_VISIT_ITK_PROHIBITED`, `mode:CURATED`,
  `rule_pack 446ee4ee seq 1`, HMAC fingerprint `fp-2026-07-1`) and the FIRST row landed in
  `visa_decisions` (`RECOMMEND`/`SHADOW`, `long_tourism`, 32-byte fingerprint,
  `ruleset_activation_id` set). The collection window is accumulating from real traffic.
  GATE STATUS unchanged: 🔴 RED (volume/breadth = 1 row so far).
- 2026-07-25 (M5, Kimi orchestrator, consolidation): **FINAL LEDGER of the two-day run.**
  **12 PRs merged**: #3032 `8875b95a` (funnel v1 resurrected, live-smoked 201 + DB row),
  #3033 `0185dc5c` (disclaimer all-5-states + PII-free submit-failure telemetry), #3038
  `6e88b24b` (next-steps gated on SUPPORTED_CANDIDATES), #3046 `7f99e570` (mig 256
  traffic_source + G-a-vol/breadth split), #3028 `8b5dffbd` (architect corpus + definitive
  plan), #3060 `35da9284` (mig 257 business/diaspora categories), #3061 `726dbc93`
  (**evaluate read-path API**), #3034 `dbb31e4d` (G-b metamorphic + canonical replay CLI),
  #3079 `f43f04c1` (SHADOW arming runbook), #3092 `c33c183a` (12 W2 fact-bases), #3090
  `3c412c96` (**first signed PRODUCTION RulePack** 38p/110r/28s, kid prod-2026-07-1),
  #3101 `6893ea5d` (activate_pack ops CLI). **Production state**: endpoint live serving
  real verdicts in SHADOW+CURATED; pack `446ee4ee` seq 1 ACTIVE (activation bb35cb81);
  secrets staged: trust store (relabeled kids), EVALUATE_MODE=SHADOW, FINGERPRINT_KEYS,
  DRIVER_TOKEN; roles: visa_activation_executor (NOLOGIN, grants on nuzantara_rag),
  visa_activation_operator (LOGIN, custody M5); `visa_decisions` accumulating.
  **Standing bugs fixed en route**: key-ceremony digit-start kids (errata + relabel),
  detect-secrets pack-hash baseline (+ triage rule), docsync/inventory date-drift pattern,
  prettier-3.8.4-vs-main skew (3 files, flagged for infra), `fly pg connect` wireguard
  hang (use fly ssh console -C + sftp put --machine). **Open items**: D1/D2/D3 owner
  decisions (pack in `research/visa/2026-07-23-d1-decision-pack.md`); W1c persona breadth
  extension (after window data); Track C wiring 4a/4b (Pro, briefed); Track B FASE 2
  (Mini, briefed); G-d drill + flip only at all-green. Seat status: codex CLI dead on M5,
  GLM Keychain-only, Opus caps ~4-5h — graders fall back to Opus/Fable per Zero.
- 2026-07-27 (M5): **TRACK C claimed by M5/2026-07-27 — SHADOW WIRING BUILT AND LIVE-PROVEN.**
  Track C was free (no branch/PR/worktree; Pro was briefed 07-25 but never started). Per spec §B.1
  the SHADOW era changes the UI by NOTHING: the only new runtime behaviour is an invisible
  fire-and-forget POST. NEW `_lib/fact-mapper.ts` (pure, all 40 wire keys) + NEW `_lib/shadow-client.ts`
  (the route's only network code, `keepalive`, errors swallowed, never awaited) + MOD `OracleShell.tsx`
  (dedupe effect) + MOD `flow.ts` (`FlowState.attempt`). 147 tests / 9 files green, `tsc --noEmit`
  clean — both re-run by the orchestrator, not taken on report.
  **TWO SPEC-vs-REALITY CORRECTIONS (the spec is 2026-07-19 and predates its own dependencies):**
  (1) it says "35-key wire shape" — the live `ApplicantFactsData` has **40** required dotted-alias
  fields, `extra="forbid"`, so a 35-key mapper 422s on every call; the delta is the 5 `secondhome.*`
  fields the E33 vertical added on 07-23 (#3044). `FactPath` = 43 members (40 applicant + 3 `derived.*`,
  correctly absent from the wire). (2) it targets `POST /api/v1/visa-oracle/recommend`; the endpoint that
  actually shipped is **`POST /api/visa-oracle/evaluate`** (#3061, 07-24). Do not build from the spec's
  §B.2 table without re-grounding both.
  **LIVE PROOF (end-to-end, first time ever performed):** the mapper's real payload POSTed to prod
  returned **HTTP 200** with a genuine engine verdict (`HUMAN_REVIEW_REQUIRED` / `CALLING_VISA_REVIEW`
  — the calling-visa overlay firing because nationality is UNKNOWN), `mode:CURATED`, `rule_pack sequence 1`,
  `decision_id` present; row landed in `visa_decisions` at `2026-07-26T18:12:26Z` — `engine_mode SHADOW`,
  `request_category long_tourism` **derived server-side from the facts** (not the caller's hint), 32-byte
  HMAC fingerprint, `ruleset_activation_id` set.
  **THREE DEFECT ROUNDS, all found by DRIVING the component, none by reading it** — record this, it is the
  method: (R1) the one-shot ref latched at first verdict arrival, so `REVIEW_ANSWERS`/`SELECT_CATEGORY`
  sent the user's PRE-EDIT answers — a wrong audit row is worse than a missing one; (R2) the cure enumerated
  those two paths and missed **`RESTART`** (two honest interviews, one row) while keying on RAW UI facts
  instead of the wire payload (editing `remote_income`, which has no FactPath, produced a byte-identical
  duplicate row). Root cause of both: one key wrong in BOTH dimensions — content and lifetime.
  **CURE (final):** `flow.ts` gains `FlowState.attempt`, bumped ONLY by a new `resetFlow()` (the reducer's
  single reset primitive); `OracleShell` holds `{attempt, keys:Set<string>}` keyed on
  `stableFactsKey(mapOracleFactsToApplicantFacts(...).facts)` — the SAME transform the POST applies.
  Contract: exactly one POST per **(interview attempt × distinct wire payload)**. Any future action that
  returns to the verdict by TRUNCATING history is covered by construction — there is no path list to keep
  in sync. **Do not "simplify" this back to a boolean ref: that shape has now failed twice.**
  **W100 CONFIRMED AGAIN:** the external GLM seat reviewed R1's diff statically and returned **SHIP** while
  the defect was live; the house lane refused the verdict, drove the component, and falsified it. Static
  review is not acceptable evidence on this surface — a reviewer must RUN the tree.
  **NEW GATE FINDING (owner-relevant, unresolved):** our own verification POSTs persist with
  `traffic_source='real'` (3 such rows on 07-26). The probe/smoke label is NOT separated from organic
  traffic, so **G-a-vol currently counts our own tests as real end-user requests**. This must be fixed
  before the collection window means anything — it is the same defect class as the 11 bootstrap rows.
  **Infra facts established (re-usable):** endpoint is fully anonymous (exact-match in `public_endpoints.py`);
  CORS already allows `https://balizero.com`; `next.config.ts` CSP `connect-src` already allowlists
  `nuzantara-rag.fly.dev` (no CSP change needed); rate limit 30 req/60s per IP; `VISA_ENGINE_DRIVER_TOKEN`
  gates ONLY the synthetic traffic classes (header `X-Visa-Driver-Token`), never normal calls; an
  all-UNKNOWN payload is contract-VALID ("thin facts are NEVER rejected"). GATE STATUS unchanged: 🔴 RED.
- 2026-07-28 (M5): **FIRST MEASUREMENT OF THE LIVE SHADOW SUBSTRATE — we are collecting on the one lane
  that cannot pass.** Collection has been writing since 07-25 (the 07-21 "still dark" line was stale), so
  this is the first read of what it wrote rather than of the ledger's narration of it. Receipt with
  re-runnable SQL + Fly evidence: `research/visa/2026-07-28-shadow-gate-measurement.md`. Numbers in GATE
  STATUS above. The shape of the finding is a **lane asymmetry**: RECOMMEND abstains by construction
  (interview never asks nationality × pack's correct `on_unknown: HUMAN_REVIEW`), while MATCH — which sets
  nationality, mints per-request random fingerprints, is counted by the collector, and sits on the funnel
  that actually has users — is simply OFF (`VISA_ENGINE_MATCH_MODE` absent from `fly secrets list`).
  **Next step is therefore arming MATCH, not fixing the RECOMMEND interview first.**
  **METHOD NOTE — record this, it cost three refutations.** The first draft of this entry claimed (a) G-a
  volume is interview-bounded and (b) G-d is unfalsifiable because ENFORCE is unbuilt. **Both were WRONG**,
  killed by the Codex `sol` xhigh adversarial pass and then re-verified on disk by the author: the
  fingerprint semantics differ PER LANE (HMAC-over-facts on RECOMMEND, random-token on MATCH), and OFF
  genuinely short-circuits before the engine, so the kill-switch is real and G-d is drillable today — what
  is unbuilt is only the authoritative ENGINE render. The generalisable trap: **a property measured on one
  surface was carried to a gate that aggregates two surfaces.** Before saying "the gate cannot be reached",
  enumerate every surface the collector counts and check the property on each. W65 also held — the refuter
  itself was checked, and its `MATCH_MODE never set` objection was right on method (inference from a zero
  count) even though the conclusion survived once real Fly evidence replaced the inference.
  GATE STATUS updated above: 🔴 RED, now with numbers and with the right reason.
- 2026-07-28 (M5, same session, hours later): **CORRECTION TO THE ENTRY ABOVE — "arm MATCH" was wrong, and
  the 07-24 runbook was right.** Caught while executing it, before the `fly secrets set`. Two facts, both
  verified: (1) `shadow.py`'s MATCH writer does NOT include `traffic_source` in its INSERT column list
  (`shadow.py:538-547`) and the column has **no default and is nullable** (checked on the live prod schema,
  not just the migration) — so every MATCH row would land NULL = **legacy = counted toward NEITHER G-a
  gate** (`shadow_evidence.py:296-303`, fail-closed). Arming MATCH without first teaching the writer to
  label its rows is a **G-a no-op** — precisely: those rows cannot advance G-a-vol or G-a-breadth, but they
  DO flow into G-c, which is deliberately not split by provenance (`shadow_evidence.py:28-29`), so they can
  still move a criterion. **Why no test caught it:** the MATCH writer's fixtures layer only migrations
  252+255 (`test_shadow_match.py:505-518`) — 256 is never applied, so `traffic_source` is not even a column
  in the schema those tests assert against. (2) `research/visa/2026-07-24-shadow-arming-runbook.md:40`
  had already recorded "leave `VISA_ENGINE_MATCH_MODE` OFF" as a deliberate **plan decision** — the window's
  evidence is to be **full-fact only**, since MATCH carries 3 of 40 facts. That decision is not mine to flip
  unilaterally: a 3-fact corpus certifies a thinner engine than the one ENFORCE would arm. **So the fork is
  an owner call**: (A) keep MATCH dark and fix the RECOMMEND interview → slower, full-fact evidence, matches
  the plan; (B) label MATCH rows `real` + arm → faster volume, thin-fact evidence. Do NOT execute (B)
  without a ruling.
  **METHOD NOTE — the lesson that keeps costing:** I read the COLLECTOR's surface allow-list
  (`EVIDENCE_ENGINE_SURFACES={"MATCH","RECOMMEND"}`) and concluded MATCH rows would count. But **a row is
  counted only if the WRITER labels it** — reader-accepts-the-surface ≠ writer-emits-the-label. Check the
  INSERT column list and the column default on the LIVE schema, not the migration file, before calling any
  lane "evidence". Same shape as the earlier two refutations this session: a property verified at one end of
  a pipe, asserted about the whole pipe. And: **before executing a step, grep the runbooks for a recorded
  decision about it** — the 07-24 rationale was one file away.

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
