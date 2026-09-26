---
date: 2026-06-05
domain: operations
subject: wr2-remediation-squads
status: CHARTER — 4 squads for the WR2 autopsy remediation roadmap
author: orchestrator (Opus 4.8)
sources:
  - research/operations/2026-06-04-wr2-autopsy-report.md
  - research/operations/W66-wr2-autopsy-deferred-spec.md
  - research/operations/P4-topic-type-log-plan.md
---

# WR2 Remediation — 4-Squad Charter

The autopsy prescribed 6 fixes. Batch 1 (P-2b/P-5/P-3/P-6-honesty) shipped in PR
#1125. The remaining heavy work is organized into **3 execution squads + 1
coordinator**. A "squad" here = an orchestrator agent + its named specialist
subagents + a mandate + entry/exit criteria + blockers. Each squad runs the same
disciplines: dedicated worktree, 4-LLM panel before any prod-touching change,
adversarial verify before merge, atomic PR + auto-merge, post-merge re-verify on
live main.

Precedence of laws (cross-cutting): anti-hallucination (re-verify every claim) >
Legge 5 (never auto-publish to IG) > worktree isolation > high-traffic merge
discipline.

---

## SQUAD 1 — P-4 · topic_type_log (anti-sameness data + enforcement)  ▶ EXECUTING

**Status:** IN PROGRESS (launched 2026-06-05). Plan rev2 (4-LLM-reviewed) =
`research/operations/P4-topic-type-log-plan.md`.

**Mandate:** Persist a Postgres `topic_type_log` row at the `rendered` transition
(domain + register + dominant image-mode + layout_family), emit `image_mode` from
the generator (gating prereq), and make Art 10.6 anti-sameness enforceable
(EITHER-differ collision rule, unknown-domain exempt, hard-reject behind
`WR2_ANTIMONOTONE_ENFORCE` until the table fills with real data).

**Lead:** orchestrator → executor subagent (general-purpose) `a20103e997b8beeb2`.
**Specialists used:** Explore (recon), devils-advocate (DeepSeek panel),
general-purpose×2 (Gemini agy + Codex panel), executor (impl→merge).

**Entry criteria (met):** autopsy P-4 prescription + W66 spec + verified recon +
4-LLM panel applied (6 defects fixed in plan rev2).
**Exit criteria:** migration 206 merged to main; `image_mode` emitted AND survives
`_normalise_slides`; topic_type_log writing at `rendered`; tests green; verified on
live origin/main. Hard-reject may ship dormant behind env flag (documented).
**Blockers:** none (cold-start safe — empty table = no constraint).
**Risk owner note:** prod Postgres migration (additive, idempotent, Squawk-linted,
rollback marker). Best-effort write — never fails the render path.

---

## SQUAD 2 — P-2a · Canva master templates (break structural sameness)  ⛔ BLOCKED (asset work)

**Status:** ARMED, NOT STARTED. Needs human/design input — cannot be 100% code.

**Mandate:** Replace the single hardcoded Canva master (`DAHJSqJOIO8`) with 3-5
distinct masters (different backgrounds/grids, same brand palette), wire
`build_canva_pending` to select one per carousel by archetype/register, add a
startup reconcile check for stale design IDs.

**Lead (when unblocked):** orchestrator → wr2-design-architect + a Canva-MCP
operator subagent.
**Specialists:** bali-zero-brand skill (palette/layout families), Canva MCP
(`mcp__claude_ai_Canva__*` create-design-from-brand-template / get-design),
frontend-browser (visual QA of rendered output), devils-advocate (brand-fit check).

**Entry criteria (NOT yet met):**
1. **Operator decision/asset:** the 3-5 master designs must be PRODUCED in Canva
   (a design task). Either Antonello/Damar produce them, OR authorize the
   Canva-MCP operator to generate-from-brand-template + you approve the look.
2. Layout-family specs for the missing families (swiss-grid-asymmetry,
   stat-card-hero, thin-red-rule-divider, monospace-evidence-block) — these are
   named in tokens.json but have no skill `.md` / no Canva backing.

**Exit criteria:** ≥3 masters live + selectable by archetype; verified that two
different-archetype carousels render structurally different; design IDs reconciled
on startup; merged.
**Blockers:** (a) the actual Canva designs (manual/design), (b) operator sign-off
on brand fit. **Unblock trigger:** Antonello says "go P-2a" + provides/authorizes
the masters.

---

## SQUAD 3 — P-1 · Consolidate the two pipelines (the 60%-of-the-problem fix)  ⛔ BLOCKED (panel + operator)

**Status:** ARMED, NOT STARTED. Architectural, touches the live IG-publishing path.

**Mandate:** Make the path that ships brand-cortex-aware. Route 1A (recommended):
port Pipeline A's organs (archetype selection, register reasoning, NB ground-truth
query, a critic gate) INTO Pipeline B (`wr2_draft_generator`), and formally
decommission the dead Pipeline A (carousel-dispatcher + telegram-gate, both
crash-looping exit 75 on phantom channel `topic_ready`). Route 1B (alt): wire B to
NOTIFY topic_ready and resurrect the orchestrator — higher risk, rejected unless
1A proves infeasible.

**Lead (when unblocked):** orchestrator → wr2-design-architect (multi-step,
multi-PR) + the WR2 specialist subagents (brief-interpreter, storyboarder, critic,
layout-composer) ported as Python helpers.
**Specialists:** sota-architecture-loop skill (the 8-step design loop), full 4-LLM
council (Gemini+Codex+DeepSeek+NB-1), devils-advocate + spalla-review per PR,
backend-verifier (health), frontend-browser (post-deploy QA).

**Entry criteria (NOT yet met):**
1. **4-LLM panel on the chosen route** (CLAUDE.md §6, mandatory for architectural
   spec) — and Gemini must be re-authed on the Pro first (it's OAuth-logged-out;
   the P-4 panel ran 2-deep without it).
2. **Operator go** — this changes what reaches Instagram. Not autonomous-eligible
   without an explicit "go P-1".
3. P-4 merged first (topic_type_log is a dependency: the consolidated pipeline's
   critic needs the anti-monotony data source).

**Exit criteria:** ONE canonical pipeline that runs archetype + register reasoning
+ NB ground-truth + critic on the path that ships; dead dispatcher/gate
decommissioned (no crash-loop); E2E carousel produced through the consolidated
path; verified on live main + post-deploy QA.
**Blockers:** (a) Gemini re-auth, (b) 4-LLM panel, (c) operator go, (d) P-4 merged.
**Decomposition (when unblocked):** ~4-6 atomic PRs — (1) archetype+register
selector, (2) NB ground-truth → research_json, (3) critic gate on live path, (4)
decommission dispatcher+gate, (5) E2E wiring, (6) cleanup. 4-LLM panel before #1.

---

## SQUAD 4 — Coordinator (sequencing, gates, cross-squad invariants)  ▶ ACTIVE (this orchestrator)

**Status:** ACTIVE — this is the orchestrator role.

**Mandate:** Own sequencing + the gates between squads. Enforce the cross-cutting
laws (anti-hallucination re-verify, Legge 5, worktree isolation, high-traffic
merge). Hold the blockers and surface them to Antonello. Run/queue the 4-LLM
panels. Keep the squads non-overlapping (no two squads editing the same file
concurrently — esp. wr2_draft_generator.py, touched by both P-4 and future P-1).

**Sequencing (dependency-ordered):**
1. **P-4** (SQUAD 1) — executing now. Ships the anti-monotony data source. ← P-1 depends on this.
2. **P-2a** (SQUAD 2) — parallel-eligible (no code dep on P-4/P-1), gated on Canva assets + operator.
3. **P-1** (SQUAD 3) — after P-4 merged + Gemini re-auth + 4-LLM panel + operator go.
4. **P-6-full** (commercial_target) — after P-1 settles where "publish" lives (out of these 3 squads; tracked in W66).

**Standing gates the coordinator enforces:**
- No prod-touching change without a 4-LLM panel (or documented 2-deep if a panelist is down).
- No merge without adversarial verify (devils-advocate/spalla) + tests green + post-merge re-verify on live main.
- File-collision guard: P-1 and P-4 both touch `wr2_draft_generator.py` → P-1 must rebase onto P-4's merged state, never run concurrently on that file.
- Legge 5: no squad adds an auto-publish-to-IG path. Ever.

**Open coordinator items right now:**
- [ ] P-4 executing (SQUAD 1) — awaiting completion notification.
- [ ] Constitution 5.8/13.4 defer-to-10.6 edit (HOME fork Pro+M5) — coordinator does after P-4 merges.
- [ ] Cicatrix entry: autopsy hallucinated `_state-schema.sql`/`_voyager-curriculum.py`/`topic_type_log` file:line — write so no future agent trusts them.
- [ ] Surface to Antonello: P-2a needs Canva assets; P-1 needs his go + Gemini re-auth.
