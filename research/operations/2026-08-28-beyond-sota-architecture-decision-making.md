---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 3/13 — Architecture & design decision-making
model: claude-fable-5 (pinned lane)
sources: 15
repo_files_verified: 34
status: complete
sections_done: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
---

# 3/13 — Architecture & design decision-making

## 0. TL;DR

- **Position in one sentence:** ahead of every surveyed system on how a decision is *argued* —
  measured grounding, cross-family asymmetric councils, a CI lint that rejects unwarranted
  deliberation, per-finding adversarial dispositions — and behind Nygard's 2011 baseline on
  everything that happens to the decision *afterwards*.
- **Biggest gap — the decision's afterlife:** the ADR organ died in March 2026; decisions live in
  ≥6 locations with no status/supersedes/revisit; the governing skill cites an evidence file that
  never existed; over-convening is uncountable; Law 5 and CLAUDE.md §2 disagree on who decides
  structure.
- **Top-3 moves:** (1) **R1** decision registry as a living organ — status machine + revisit
  receptor; findability 6 locations → 1 query. (2) **R2** council-yield instrument — make
  over-convening a number (today: only "70% of dispatches are graders"). (3) **R4**
  blind-judge protocol — strip seat labels before the gate reads (the one place the argument
  trails research; W100: 7/8 false-clean).
- **Quick-win:** R3 doctrine citation-integrity lint (≤150 lines) — zero phantom sources in the
  law, held by CI. **Meta-pattern (§8):** "a well-argued decision keeps itself" is
  superscar family #2 at the record layer — decisions are the last unmonitored organ.

## 1. How Nuzantara does it today

Every path below was verified on disk in this session with `ls`/`grep`/`sed -n`/`git -C` against the
panel worktree (`agent/nuzantara/research/beyond-sota-0828`, HEAD `11a3c89a2`).

### 1.1 The decision loop: `sota-architecture-loop` inside `modus` DESIGN

- **`.claude/skills/sota-architecture-loop/SKILL.md`** (13 KB, 1,528 words) is the canonical loop:
  8 steps `FRAME → GROUND → REASON → COUNCIL → DECISION → EXECUTE → VERIFY → CAPTURE`, three axioms
  ("eterogeneità batte numerosità · adversarialità calibrata batte consenso · verifica esterna batte
  autodichiarazione"), a **council gate** that fires only when *all three* hold — divergent priors can
  change the answer ∧ error costs > ~15× tokens ∧ genuinely parallel breadth — and a two-axis
  **asymmetric review** (roles proponent / red-team / costruttivo on three model families; incentives
  inverted per role). Closure is "gate empirico, non autodichiarazione".
- The skill has exactly **one commit in its history** (`cc5c1627f`, 2026-07-17, the vendoring PR) —
  never amended since, although the council composition it describes (Claude/Gemini/DeepSeek/Codex)
  was superseded twice (DeepSeek retired 2026-07-19; Kimi K3 now the fixed refuter per `modus`).
- **Its only evidence citation is a phantom.** Line 11-12 cites
  `research/operations/2026-05-30-sota-ai-architecture-methodology.md` — no hit anywhere in the
  tree, and `git log --all` on the path returns nothing: never committed. The loop that governs
  every architectural decision rests on a source nobody can open — the family-#6 defect the loop
  exists to prevent, at doctrine level.
- **`.claude/skills/modus/SKILL.md`** (66 KB) hosts the loop as stage 2 **DESIGN** (line 77):
  "`sota-architecture-loop` steps 0-4 … **Output = a durable spec artifact on disk** … Council verdicts
  are LEADS — re-verify what they attack AND what they bless (W65)". STAGE 0 TRIAGE (lines 33-68)
  turns budget into a router: Gear 1/2/3, and the **anti-sperpero rules** (lines 48-68): "Council is
  NOT automatic at Gear 3", fan-out only for ≥3 independent reads, "1 agent with 10× budget beats
  homogeneous debate at ⅓ cost", stop-loss declared up front, floor enforced by `harness-floor.yml`
  and **ceiling** by `scripts/evidence_pack_lint.py::compute_ceiling` (line 657): a ≤2-file/≤60-net-line
  diff outside hot zones that declares Gear 3 *and* a `council` (or ≥3 grader dispatches) is
  REJECTED unless `evidence/pack.yml` carries a reasoned `gear_override:` — the header (643-645)
  records why: "nothing stopped the opposite — a Gear-1-shaped diff paying for a council … 70% of
  Agent dispatches are graders".
- **Council composition when the gate fires** (`modus` lines 185-196): exactly three external seats —
  costruttivo = Gemini, red-team = Codex GPT-5.6, refuter = Kimi K3 — then a sequential **Opus 5
  xhigh final on-disk gate** over candidate bytes, reviews and disposition; "rounds are capped and
  NEVER consensus-seeking"; gate-seat unavailable ⇒ SUSPEND.

### 1.2 The panel pre-approval and its executable form

- **`CLAUDE.md` §6**: 4-LLM panel mandatory pre-approval for "spec architetturale, quote cliente,
  pre-deploy critical path" — Gemini agy + Codex sol + Kimi K3 + optional NB-1; runnable default
  **`infra/workflows/verify-template.js`** (7.7 KB): gather N angles → adversarially refute each on
  fresh context → synthesize survivors; `skeptics: 1` default, `3` for high-stakes; header states the
  principle: a finding survives ONLY if an INDEPENDENT grader on FRESH context could not refute
  it; six research files reference it.
- **`CLAUDE.md` §2 Federation Orchestrator triggers** (6-row table) → `scripts/federation_orchestrator.py`
  (LangGraph classify→dispatch→assemble→review; Gemini `search`/`explore`/`redteam`, Codex `sandbox`);
  its docstring loads env from a `Desktop/…` path — a HOME-fork-shaped dependency (family #1) inside
  the decision router itself.
- **Origin of the practice**: memory `feedback_always_review_spec_with_4_llm.md` (2026-05-13) — the
  OAuth flaw Claude missed and 3/3 sibling LLMs caught; encodes the convergence rule (3/3 →
  CRITICAL, 2/3 → SIGNIFICANT, 1/3 → flag).
- **Red-team prompt cortex**: `infra/redteam-cortex/{quote,research,slide}.md` — three artifact-typed
  red-team briefs (no `architecture.md` / `spec.md` variant exists).
- **`docs/decisions/2026-05-03-codex-spalla-architecture.md`** is the only decision memo with a real
  header (`Status: accepted (user, 2026-05-03)` / `Supersedes` / `Related`) and it *decided against*
  bolting Codex into the Consiglio v1 orchestrator as a 4th voice.

### 1.3 Constraints: SYMBIOSIS laws, the atlas, the anatomy

- **`SYMBIOSIS.md`** (38 KB) — *Pilastro 4: Confronto* (lines 109-123): "diversità strutturale …
  un devil's advocate LLM è meno efficace di un autentico dissenziente … se tutti concordano troppo in
  fretta, il moderatore deve cercare la falla". **LE LEGGI** (line 174 ff.): 1 CLI-only · 2 PII never
  in clear · 3 event-driven ("nessun orchestratore centrale") · 4 graceful degradation · **5 "Zero
  come ultima istanza … l'organismo propone, non decide"** · 6 local sovereignty · 7 "Numeri prima".
  Law 5 as written contradicts `CLAUDE.md` §2 ("io sono te", 2026-07-06; ship-lifecycle ownership,
  2026-07-16 — the codeowner keeps *only* business decisions). The two constitutional texts disagree
  on **who decides structure**; every session resolves the conflict ad hoc.
- **`INDEX.md`** (12 KB, "ultima revisione manuale 2026-07-02"): the atlas of 5 sacred books, a
  "Se stai per…" pre-action table, and `DOCSYNC` markers that *deliberately* store no live state.
- **`docs/LIVING_ARCHITECTURE.md`** (297 KB, 1,502 headings) is an auto-generated **endpoint
  catalogue** — not an architecture document; the name promises the C4/arc42 artifact the repo
  does not have.
- **`apps/organism/organism/organs_registry.yaml`** (87 KB, sha256 checksum at top): **170 organs**
  (`^- id:`), runtimes 144 `pro_launchd` / 14 `mini_launchd` / 10 `fly_machine` / **2 `air_launchd`**
  (Air decommissioned 2026-05-05 — dead tissue still registered); types 131 cron / 33 daemon /
  6 webhook; 21 `severity_on_silence: critical`; fields incl. `expected_hb_seconds`,
  `recovery_action`, `severity_on_silence`, `cicatrix_refs`. Only **10/170 organs carry a non-empty
  `cicatrix_refs`** — the scar↔organ link the schema was designed for is 94% unused.
- **`infra/organ-conformance/genes.json`** (23 KB): the "organ genome" — **10 genes** G1 registry
  entry · G2 heartbeat · G3 declared HOME pair · G4 node guard · G5 kill switch · G6 hardened
  headless spawn · G7 PENDING-ARMS line at birth · G8 KeepAlive matches payload · G9 fail-visible ·
  G10 single instance — with a grandfathered baseline ("shrinking the baseline is the cure metric"),
  consumed by `check_organ_conformance.py` (CI `organ-conformance.yml`) and `scripts/organ_birth.py`.
  A real, executable **architecture fitness function** — for one organ class (launchd/cron); its
  research source `2026-07-06-dna-self-healing-genome.md` exists (21 KB).
- **`infra/guard-conformance/{check_guard_conformance.py,registry.json}`** + `guard-conformance.yml`:
  the family-#3 antidote as a CI gene (every censused guard needs guilt+innocence tests).

### 1.4 Where decisions are actually recorded (measured)

| Location | Count (this tree) | Freshness |
|---|---|---|
| `docs/ARCHITECTURE_DECISION_RECORDS.md` | **11 ADRs** (ADR-001…011) | "Last Updated 2026-02-26"; last commit 2026-03-22; **0 commits since 2026-06-01** |
| `docs/adr/` | **1 file** (`ADR-006-nb-mitochondrial-monitor…`, 2026-05-07) | number **collides** with ADR-006 "Abstract Channel Pattern" in the main doc |
| `docs/decisions/` | 1 memo (2026-05-03) | — |
| `docs/specs/` | 5 specs | — |
| files named `*decision*`/`*adr*` under `docs/` + `research/` | 26, scattered across 9 directories | — |
| `research/operations/` | **350 files**; 20 with "panel", 14 with "design" in the name; **318 commits since 2026-06-01** | the live decision organ |
| `research/design/` | 16 dossiers | live (specimen below) |
| memory `decision_*` / `discovery_*` / `feedback_*` | **161 / 545 / 57** of 1,708 files | live, but per-machine and index-capped (~17 KB) |
| `CLAUDE.md` inline `RULED` blocks | 6 | live; the highest-authority rulings live *inside the context file* |
| `.claude/skills/modus/PENDING-ARMS.md` | 2.2 MB, 1,495 lines; "panel" 12 · "council" 6 · "ADR" 1 | — |

Ratio: ~30 research-file and ~15 memory decisions per ADR-formatted one. The formal ADR organ is
**dead since March**; the living organ is the dated research dossier with its adversarial
disposition table.

### 1.5 The specimen — how we decide when we decide well

`research/design/2026-08-28-case-code-design.md` (2,585 words): measured ground with 13 verified
`file:line` citations, the unit named (a journey, not an order), the contract, "open questions
deliberately NOT decided here"; then **§Adversarial review**: two cross-family seats on the first
draft (Codex sol xhigh, 13 findings; Kimi K3, 11) → **20 unique findings, 17 APPLIED / 3
REJECTED-with-reason**, one disposition row each — findings that *reshaped* the design (killed the
naive first design twice over; a self-declared deviation withdrawn as a false dilemma).
The same shape appears in `research/operations/2026-08-24-product-factory-procedure-5-seat-panel.md`
(5 cross-family seats, then a fresh-context Kimi K3 review of the capture itself, whose finding #1
caught an unsourced LLM figure being promoted into doctrine to *reduce* review coverage), in
`2026-08-21-universal-conductor-control-plane-design.md` (§1 Decision, §3.2 Hard invariants, §9
Semantic mutation gate) and in `2026-05-24-sota-multi-agent-repo-architecture-synthesis.md` (final
devils-advocate of Codex on Codex itself, live scars *during* the wave, a 2026-05-28 postscript
validating the decision against W58→W63).

### 1.6 Reuse-first as a design constraint

`.claude/skills/reuse-first/SKILL.md` (8.4 KB): 7-step procedure (decompose into bricks → double
search internal+GitHub → classify copy/fork/study-pattern/install/write-new → **license gate**),
born from the 70%-already-written intake case. Prose-only: no lint, no `pack.yml` field, no
receptor records whether the search happened.

## 2. Scars & ledger evidence in this area

**The dominant line is superscar family #6 (anti-hallucination blindness) applied to the
decision process itself** — `cicatrix-superscar.md` line 149-153: "Anche il refuter allucina (W65)",
members W65 → W90 → W100 → W113:

| Scar | What bit | Recurred? |
|---|---|---|
| **W65** refuter falso-refuta | the grader hallucinated a refutation | yes — line continues |
| **W90** (2026-07-02) | ground-truth verifier (NB-3) "confirmed" pre-resolution numbers from a stale snapshot — *the verifier is also a lead* | yes |
| **W100** (2026-07-18) | same-family blind agreement certified **7 FALSE-clean of 8 (54%)**; antibody: cross-family mandatory, never cite an IAA without declaring seat kinship | yes — the 2026-08-24 panel finding #1 is the same shape (an LLM number promoted to doctrine) |
| **W113** | "la frase che scrivo MENTRE ritratto è un claim nuovo, e nessun round adversariale la guarda" — the disposition step is itself ungraded | open by nature |

**AMENDMENTS.md** (52 KB, **42 entries over 17 dates**, only **2 mention "council"**) — the
loop's own misfire log for the DESIGN stage:

- 2026-07-02 — refuter seat brittle (DeepSeek 402, GLM permission-denied) ⇒ council ran
  **2 seats**; codified "acceptable-degraded, MUST be declared"; a dead seat is an un-armed
  artifact ⇒ PENDING-ARMS line, not narrative.
- 2026-07-05 — **red-team verdict landed AFTER auto-merge** (#1963): the gate ran, the decision
  had already shipped; the fix branch then went permanently CONFLICTING (W88).
- 2026-08-22 — two "cut waste" sessions ran 44+31 h, **180 PRs, 8.6 M output tokens, ~10 business
  commits**; PR #4547 = 14 commits / 11 adversarial rounds for a 1-file regex. Verdict recorded
  there: such a mandate "should gear it 2 with a stop-loss, **never Gear 3 with an open council**"
  — over-convening by the loop's own admission.
- 2026-08-23 — a refuter pointed at a **live worktree** returned a fabricated CRITICAL from a torn
  snapshot ⇒ freshness clause: refute an immutable `git archive <sha>`, never a cwd.
- 2026-08-26 — the file recorded **zero entries for three days, the second time after naming the
  identical gap**; the 11-agent workflow that measured it found the surviving gate proposals share
  one shape — *convert an existing prose rule into a check at a door that already exists* — plus
  PreToolUse hooks **failing OPEN** under load and a blind seat "measuring" the wrong tree.

**Measured: how often is a council convened when the anti-sperpero gate says it should not?** The
honest answer is *the organism cannot count it*: AMENDMENTS has 2 council entries in 42, the
ledger tallies "council" 6 times in 1,495 lines, and no `pack.yml` field records *why* a council
fired. The only hard number is the one the ceiling lint was built on — **70% of Agent dispatches
were graders** (`evidence_pack_lint.py:645`). A process that cannot count its own over-convening
cannot tune its gate.

**Memory lessons that bite the decision step** (`MEMORY_METHOD_LESSONS.md`, 32 KB): *"«Verificato su
disco» controlla il VALORE, non il REFERENTE"* — a 40-minute review dispatched against the wrong
artifact, cured by sha256 identity before any gate; *"due sonde che CONCORDANO possono condividere
la cecità"* (independence lives in the failure cause); *"cinque modi in cui una verifica concorda
senza provare nulla"* — the citation is real, what it *claims to authorize* is invented.

**Structural drift found in this pass, not yet a scar:** (a) the loop's evidence file never existed
(§1.1); (b) two ADR-006s — the W40/W128 numbering-collision family has reached the decision records;
(c) Law 5 vs CLAUDE.md §2 on who decides structure (§1.3); (d) 2 organs registered on the
decommissioned Air runtime; (e) `LIVING_ARCHITECTURE.md` is an endpoint dump under an architecture
name.

**What did NOT recur:** the two-seat cross-family disposition table (§1.5) produced, in every
specimen read, at least one CRITICAL that reshaped the design before build (case-code #1-#3;
product-factory #1; conductor §3.2). The practice works where applied; the scars are about *when
it is skipped, who grades the grader, and whether anyone can find the decision afterwards*.

## 3. World SOTA survey

Accessed 2026-08-28. Sources marked ⚠ were not fetched this session (HTTP 404/403 or budget) and are
cited from their canonical location only; the numbers attached to them are widely reproduced but
were *not* re-verified here.

| # | System / practice | Source (date) | Mechanism | Measured effect | Transfers to this organism? |
|---|---|---|---|---|---|
| 1 | Orchestrator-worker research system | Anthropic Engineering (2025-06-13) [S1] | lead agent plans, spawns parallel subagents, synthesizes; end-state evaluation + LLM-judge rubric; ~20 real queries as first eval set | +90.2% vs single Opus 4; token use explains 80% of variance; ≈**15×** chat tokens; "most coding tasks involve fewer truly parallelizable tasks" | **Direct** — the 15× gate and "coding barely parallelizes" in `modus` come from here; the *measurement* (token variance per decision) is what is missing |
| 2 | MAST failure taxonomy | Cemri et al., arXiv 2503.13657 (v1 2025-03, v3 2025-10) [S2] | 14 failure modes / 3 classes: system design · inter-agent misalignment · **task verification**; 1,600+ traces, 7 frameworks, κ=0.88 | "performance gains on popular benchmarks are often minimal"; failures need structural redesign, not prompts | **High** — AMENDMENTS is an unstructured MAST; a per-council failure-class tag would make misfires countable |
| 3 | Debate judged by a weaker, independent judge | Khan et al., arXiv 2402.06782 (2024-02/07) [S3] | strong "expert" debaters argue opposite answers; weaker non-expert judges pick | judge accuracy **76% / 88%** vs 48% / 60% naive; optimizing debaters for *persuasiveness* still raises truth-finding | **High** — validates asymmetric adversarial seats; also says the *judge* must be independent of both debaters, which the Opus-judges-Opus gate is not |
| 4 | LLM-as-judge bias | Zheng et al., arXiv 2306.05685 (2023) [S4] | position bias, verbosity bias, **self-enhancement bias**, limited reasoning; >80% human agreement when mitigated | mitigations: swap positions, reference-guided grading | **High** — the final on-disk gate is an LLM judge with no position swap and same-family self-enhancement exposure |
| 5 | Conformity / identity bias in multi-agent debate | arXiv 2509.05396; 2510.07517; 2604.02668; 2602.09341 [S5-S8] (search-surfaced) | conformity grows with rounds; majority flips better-supported minorities; **sycophancy far more common than self-bias**; masking seat identity restores content-based reasoning | agreement measures pressure, not truth (cf. W100) | **High** — rounds already capped, consensus banned; **seat anonymization is absent** |
| 6 | ADR (Nygard) | cognitect.com (2011-11-15) [S9] | Title · Context · Decision · **Status** (proposed/accepted/deprecated/superseded) · Consequences; monotonic numbers never reused; superseded, never deleted | qualitative: new members neither "blindly accept" nor "blindly change" | **High** — the ADR organ is dead; dossiers have no Status/Supersedes; ADR-006 reused |
| 7 | Design docs at Google | Ubl (2020-07-06) [S10] | context/scope · goals **and non-goals** · trade-offs · **alternatives considered**; write only if ≥3 of 5 uncertainty criteria; "if it just says how we'll implement it, write the program" | qualitative; lifecycle creation→review→implementation→learning | **High** — the ≥3-of-5 rule is a triage gate for *writing*; non-goals/alternatives missing from most dossiers |
| 8 | Rust RFC process | rust-lang/rfcs README [S11] | "substantial" trigger list; PR-based text; **final comment period** with disposition **merge/close/postpone**; tracking issue | qualitative; thousands of RFCs | **Medium** — FCP+disposition transfers as a closure protocol for one-way doors; human consensus does not (solo owner) |
| 9 | Architectural fitness functions | Thoughtworks, Paul & Wang (2019-01-11) [S12]; book ⚠ | tests per "-ility" run in delivery pipelines as "continuous feedback for architectural conformance" | qualitative; "objectively measure technical debt" | **Already partly AHEAD** — `genes.json` + organ/guard conformance are fitness functions with a cure metric; missing for laws and decisions |
| 10 | Project premortem | Klein, HBR (2007-09) [S13] | "assume the project has failed" → each member writes reasons → round-robin | prospective hindsight **+30%** reasons identified; reduces overconfidence, legitimizes dissent | **High** — a different elicitation than "find the flaw"; costs one low-effort call |
| 11 | One-way / two-way doors ⚠ | Bezos 2015 shareholder letter (aboutamazon.com, fetch 404) [S14] | Type 1 irreversible → slow, deliberate; Type 2 reversible → fast, individuals/small groups; danger of heavyweight process on Type 2 | qualitative | **High** — the gear gate encodes this implicitly ("rollback è gratis → non serve"); reversibility is not a recorded field |
| 12 | Lightweight formal methods ⚠ | Newcombe et al., CACM 2015 (fetch 403) [S15]; Alloy ⚠ | TLA+ specs of S3/DynamoDB/EBS found design bugs needing >30-step traces; "exhaustively testable pseudocode" | qualitative + bug counts in paper | **Low-Medium** — full TLA+ is heavy; exhaustive state-table tests bound to a decision record capture the contract-widening class |
| 13 | Architecture as code ⚠ | C4/Structurizr; arc42; MADR; Team Topologies; Larson; Kahneman *Noise* | model-first diagrams; templated ADR with Considered Options; independent judgments *before* discussion | qualitative | **Medium** — the organs registry already *is* the model; Kahneman's "independent before joint" is the parallel-not-sequential panel rule in `feedback_always_review_spec_with_4_llm.md` |

### The five that matter most

**(a) The debate literature has turned, and it agrees with the organism's doctrine — then goes one
step further.** MAST [S2] finds multi-agent gains "often minimal" and locates a third of failures in
*verification*; the 2025-26 conformity papers [S5-S8] show that agreement in a debate measures social
pressure (rounds, majority size, visible identity), not truth — the exact lesson of W100, and
rules the loop already has (§1.1). What it does **not** do is the mitigation those papers and
Zheng [S4] converge on: **hide seat identity and randomize order before the judge reads**, and
keep the judge independent of the debaters [S3]. Today the final gate is Opus 5 reading three labelled reviews of a design an Opus 5
orchestrator wrote — self-enhancement bias with a label on every finding.

**(b) Records are a lifecycle, not a document.** Nygard's ADR [S9] is 60% *status machinery*
(status flow, numbers never reused, nothing deleted); Rust's RFC
[S11] adds a **closure protocol** (FCP, disposition merge/close/postpone, tracking issue); Google's
design doc [S10] adds **non-goals, alternatives considered** and a *write-only-if* gate. The
organism's living decision organ (dated research dossier + disposition table, §1.5) is richer than
any of these in *evidence* and poorer than all of them in *lifecycle*: no status, no supersedes, no
postponed, no revisit date, and a number that was reused.

**(c) Fitness functions are the decision that keeps deciding.** Thoughtworks [S12] frames
architecture tests as continuous conformance in the pipeline. `genes.json` (§1.3) is a
better-than-textbook instance — genome + grandfathered baseline whose shrinkage is the cure metric —
but it covers one organ class. The seven SYMBIOSIS laws — the repo's highest constraints — have no
conformance map: nobody can say which law is enforced, advisory, or prose-only.

**(d) Premortems and door classes are the cheapest decision-quality levers in the literature.**
Klein's +30% [S13] comes from a *different question* than red-teaming; Bezos's door classes [S14]
are the reversibility axis the gear gate uses implicitly. Both
are one field and one low-effort call away, and the scar corpus gives the premortem a prior no other
organization has.

**(e) Anthropic's own evidence [S1] says measure tokens per decision, not per session.** 80% of
performance variance was token usage; the organism's 2026-08-22 misfire (8.6 M tokens, ~10 business
commits) is what happens when the loop optimizes *itself* without a per-decision yield number. Council
yield is the missing instrument.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| **Grounding before reasoning** (disk-state / NB ground truth, file:line) | **AHEAD** | `sota-architecture-loop` step 1 + W62 test; specimen §1 with 13 verified `file:line` citations; no surveyed design-doc culture *forces* measured grounding before the design section [S10 lists context, not proof] |
| **Council composition** (heterogeneity, incentive inversion, capped rounds, no consensus, family exclusion) | **AHEAD** | `modus` lines 185-196; `sota-architecture-loop` §STEP 3/6; `verify-template.js`; FLEET_TOPOLOGY family-exclusion — the 2025-26 debate literature [S2, S5-S8] is only now converging on these rules |
| **Judge independence / seat anonymity** | **BEHIND** | gate = Opus 5 reading *labelled* reviews of an Opus-orchestrated design (`modus` 190-193); no position swap or masking [S3, S4, S6]; W100 already bit (7/8 false-clean) |
| **Convening gate + cost ceiling** | **AHEAD** (unique) | CI-recomputed gear floor (`harness-floor.yml`) + `compute_ceiling` rejecting "Gear 3 + council" on ≤60-line diffs (`evidence_pack_lint.py:657-767`); no surveyed system lints *whether a deliberation was warranted* |
| **Measuring the gate** (over-convening, council yield) | **BEHIND** | only number on record: "70% of Agent dispatches are graders" (`evidence_pack_lint.py:645`); AMENDMENTS 2/42 entries mention council; the misfire log was silent twice while misfiring (2026-08-22, 08-26) |
| **Framing fields** (non-goals, alternatives, reversibility/door class) | **BEHIND** | specimen has "open questions not decided" but no non-goals/alternatives sections; no `door:`/reversibility field in `pack.yml`/dossiers [S10, S14] |
| **Decision record lifecycle** (status, supersedes, postponed, revisit) | **BEHIND** | ADR doc frozen since 2026-02-26 / commit 2026-03-22; 1 file in `docs/adr/` with a **reused number**; decisions in ≥6 locations (§1.4 table); highest rulings inline in `CLAUDE.md` (6 `RULED`) |
| **Adversarial disposition on the record** | **AHEAD** | per-finding APPLIED/REJECTED-with-reason table, 17/20 applied on the specimen; the 2026-08-24 fresh-context review of a *panel capture* caught an LLM number promoted to doctrine — no surveyed ADR/RFC culture grades its own record adversarially |
| **Evidence hygiene of the doctrine itself** | **BEHIND** | the loop's only cited evidence file never existed (`git log --all` empty); its conformity numbers (85.5% / 70% / 6→3) are unverifiable; skill unchanged since its one commit (2026-07-17) while its roster went stale twice |
| **Constraints as executable fitness functions** | **AHEAD** for launchd organs, **BEHIND** for the constitution | `genes.json` 10 genes + grandfathered baseline + `organ-conformance.yml`; `guard-conformance`; zero conformance map for SYMBIOSIS Laws 1-7 [S12] |
| **Constitutional coherence** | **BEHIND** | Law 5 "le decisioni strutturali passano da Zero … l'organismo propone, non decide" vs `CLAUDE.md` §2 "sessions ARE the operator" — two live texts, opposite answers on who decides structure |
| **Anatomy / atlas** (organs registry, INDEX) | **AHEAD** in design, **BEHIND** in upkeep | registry = model + healer input + scar link + checksum (Structurizr-class "architecture as code" that is also *consumed*); but 10/170 scar refs, 2 `air_launchd` organs, `LIVING_ARCHITECTURE.md` is an endpoint dump, INDEX manual since 2026-07-02 |
| **Reuse-first** | **AT** | 7-step skill with license gate, prose-only, no receptor (no `pack.yml` field, no lint) — same as SOTA (nobody enforces it either) |
| **Revisiting decisions** | **BEHIND** | no revisit dates, no superseded chain; ADR-001 ("Gemini primary LLM") contradicts the current routing doctrine and is still `Status: Active` |

Net: the organism is **ahead of every surveyed system on how a decision is argued** (grounding,
heterogeneous asymmetric council, CI-gated convening, adversarial disposition) and **behind the
2011-era baseline on what happens to the decision afterwards** (status, supersession, revisit,
findability, citation integrity). The judge/anonymity gap is the one place the argument itself is
weaker than current research.

## 5. Beyond-SOTA recommendations

Ranked by (impact × confidence) / cost. All run on flat-sub seats, CLI-only; none auto-routes
Fable or moves a business decision away from Zero.

### R1 — Decision Registry as a living organ (the record that heartbeats)
**What:** one machine-readable registry (`docs/decisions/registry.yaml`): monotonic `D-NNN` ·
`status: proposed|accepted|superseded-by|postponed(revisit_by)` · `door: one-way|two-way` ·
`evidence:` (path to the dossier + disposition table) · `contradicts:`. Plus a CI lint (reused
numbers forbidden — the W40/W128 antidote; a row required from every Gear-3 dossier) and a
proprioception receptor that flags expired `revisit_by` like a stale heartbeat.
**Why beyond SOTA:** ADR/MADR/RFC records are documents humans remember to maintain [S9-S11];
no surveyed system *pages* when a decision goes stale or is contradicted — the 2011 lifecycle
composed with receptors only this organism has.
**Cost/gear/risk:** ~1 Gear-2 session, lint ≤200 lines; risk family #2 (an unfilled registry is
cron theater — rows lint-forced for Gear-3 only) and #9 (registry/dossier drift).
**Metric:** findability — steps to locate the governing decision for a named surface (6 locations
today, §1.4 → 1 query); % Gear-3 decisions with live status (0% → ≥90%); contradictions surfaced
(≥1 known: ADR-001 still "Active" vs current routing).
**Kill:** <50% of new Gear-3 decisions registered after 30 days → narrow to RULED-class only.

### R2 — Council-yield instrument (make over-convening countable)
**What:** structured `council:` block in `evidence/pack.yml` (seats, family mix, findings,
applied, rejected, est. tokens), auto-extracted from the disposition tables dossiers already
produce; `council_yield_report.py` aggregates design-changing findings per seat; a 0-APPLIED
council auto-emits an AMENDMENTS candidate row.
**Why beyond SOTA:** Anthropic measures token variance per task [S1], MAST classifies failures
post-hoc [S2]; nobody instruments *deliberation yield* as a live pipeline metric — and §2 showed
the organism cannot count its own over-convening while already producing the raw data.
**Cost/gear/risk:** ≤1 session, Gear 2; risk family #2 (field never parsed), Goodhart on
"applied" (bounded: dispositions are cross-family graded).
**Metric:** unmeasurable today → median yield per gear; % councils with 0 applied; grader share
re-measured vs the recorded 70% (`evidence_pack_lint.py:645`).
**Kill:** <70% of councils auto-produce the block after 20 runs → extraction broken; fix or drop.

### R3 — Doctrine citation-integrity lint (no phantom sources in the law)
**What:** a lint that resolves every `research/...`/`docs/...` path cited in skills, CLAUDE.md,
SYMBIOSIS.md against `git ls-tree origin/main`; unresolved → CI red. First cure: the loop's own
phantom source (§1.1, re-verified this session at `sota-architecture-loop/SKILL.md:11-12`).
**Why beyond SOTA:** no surveyed culture lints its doctrine's citations — the family-#6 antidote
at the constitutional layer, where one phantom poisons every future session.
**Cost/gear/risk:** ≤150 lines, Gear 1-2; risk family #3 over-match — guilt+innocence fixtures
per the guard-conformance rule.
**Metric:** phantom citations in doctrine: ≥1 today → 0, held by CI. **Kill:** false-positive
rate >5% → tighten matcher; run cost ~0, no sunset.

### R4 — Blind-judge protocol for the final gate and councils
**What:** deterministic pre-gate step: strip seat/model labels from reviews, randomize order,
present findings as numbered claims; the gate reads blind; identities unblind only in the
recorded disposition. Family *mix* stays declared (W100 antibody) — only *who said what* is
hidden.
**Why beyond SOTA:** 2024-26 debate research converged on judge independence and identity masking
[S3-S8]; no agentic pipeline implements it. Today's gate is Opus judging labelled reviews of an
Opus-orchestrated design — same-family blindness already cost 7/8 false-clean (W100).
**Cost/gear/risk:** ≤1 session (`verify-template.js` + a `modus` gate step), Gear 2; risk family
#3 (stripping mangles content — fixture-tested) and #6 (blinding hides a seat's known failure
mode — family mix stays visible).
**Metric:** verdict-flip rate on A/B replay of ≥10 archived gate decisions; any flip proves live
bias; overhead <30 s/gate.
**Kill:** 0 flips and 0 rank changes after 20 decisions → blind mode for Gear 3 only.

### R5 — Premortem seeded by the scar taxonomy + door field
**What:** the dossier template gains `non-goals`, `alternatives considered`,
`door: one-way|two-way` [S10, S14]; plus a one-call premortem seat (cheap model): "this decision
failed within 90 days — which of the 10 superscar families killed it, and how?", before the
council round.
**Why beyond SOTA:** Klein's premortem gains +30% failure reasons from a blank page [S13];
seeding it with a taxonomized, measured failure corpus (~99 scars → 10 families) is a prior no
surveyed organization possesses.
**Cost/gear/risk:** template edit + 1 cheap call per dossier, Gear 1-2; risk family #6 (the
premortem hallucinates — it is a lead, graded like any finding).
**Metric:** % dossiers with door+premortem (0% today); hit-rate vs realized failures at +90 days.
**Kill:** hit-rate <10% over 10 shipped decisions → drop the seat, keep the fields.

### R6 — Constitution conformance map (laws as fitness functions)
**What:** `SYMBIOSIS-CONFORMANCE.yaml`: each Law 1-7 → enforcement pointer (test/lint/hook) |
`advisory` | `prose-only`, pointers executed in CI — extending the `lint_symbiosis_promises.py`
precedent (Laws 3/4 already require `Test:` citations). The map turns the Law-5-vs-§2
contradiction into a lintable open item.
**Why beyond SOTA:** fitness functions exist per "-ility" [S12]; a *constitution* with a per-law
enforcement map and "shrinking prose-only set" as cure metric exists nowhere surveyed.
`genes.json` proves the pattern at organ level.
**Cost/gear/risk:** 1 session, Gear 2; risk family #2 (map claims enforcement that is not armed —
pointers must run, not merely resolve).
**Metric:** laws with executable enforcement (≈2/7 partial today → 5/7); open contradictions
1 → 0 (after the §7 ruling). **Kill:** a law resisting executable form after 2 attempts is
labelled `advisory`, and the attempt stops.

## 6. 90-day roadmap + first PRs

**Wave 1 (days 0-30) — make decisions findable and the doctrine honest.**
- **W1-PR1** `docs(decisions): decision registry v0 — schema, backfill, collision+coverage lint`.
  Files: `docs/decisions/registry.yaml` (backfill: 6 `RULED` blocks, 11 legacy ADRs with the
  double ADR-006 renumbered, the 2026-05-03 memo, the case-code dossier),
  `scripts/lint_decision_registry.py` + test. ~350 net lines, Gear 2. Acceptance: reused number →
  red (fixture); every `evidence:` path resolves; ADR-001 marked `superseded-by`.
- **W1-PR2** `chore(doctrine): citation-integrity lint + cure the sota-architecture-loop phantom`.
  Files: `scripts/lint_doctrine_citations.py` + test, one edit to the skill's line 11-12 (cite
  this report). ~200 lines, Gear 1-2. Acceptance: red on the phantom pre-cure, green post-cure;
  innocence fixture (a path in a code block ≠ citation).

**Wave 2 (days 31-60) — instrument the council, blind the judge.**
- **W2-PR1** `feat(evidence): council block in pack.yml + council_yield_report.py`. ~300 lines,
  Gear 2. Acceptance: report runs on ≥5 historical packs; a 0-applied council emits the
  AMENDMENTS line.
- **W2-PR2** `feat(workflows): blind mode in verify-template.js`. ~250 lines, Gear 2. Acceptance:
  unit test proves no seat label survives blinding; A/B replay harness runs on 3 archived
  decisions.
- **W2-PR3** `docs(skills): amend sota-architecture-loop` — stale roster (DeepSeek→Kimi), blind
  step, premortem seat, dossier template fields; first amendment since its single 2026-07-17
  commit. Gear 2. Acceptance: citation lint green; seats match `FLEET_TOPOLOGY.json`.

**Wave 3 (days 61-90) — constitutional conformance + revisit heartbeat + numbers.**
- **W3-PR1** `docs(symbiosis): SYMBIOSIS-CONFORMANCE.yaml v0 + pointer check`. Gear 2; the Law-5
  row carries `needs-ruling` (§7.1). Acceptance: every pointer executes in CI; prose-only laws
  labelled as such.
- **W3-PR2** `feat(proprioception): revisit_by receptor` — registry rows past `revisit_by`
  surface in the boundary report. Gear 2. Acceptance: synthetic expired row appears in the
  fixture.
- **Measurement close-out:** first council-yield numbers; blind flip-rate; scripted findability
  probe (5 surfaces, 1 query each); before/after published in a follow-up dossier (Law 7).

## 7. Needs-ruling

1. **Who decides structure.** SYMBIOSIS Law 5 ("le decisioni strutturali passano da Zero …
   l'organismo propone, non decide") vs CLAUDE.md §2 ship-lifecycle ownership. One sentence from
   Zero settles which text governs *structural* decisions; W3-PR1 records it (Legge 5).
2. **Registry bindingness.** May a missing registry row BLOCK a Gear-3 merge, or stay advisory?
   A friction/business trade-off, not technical.
3. **Blind gate as default.** Changing the final on-disk gate's reading procedure touches a
   surface Zero personally ruled three times (2026-07-25 / 08-19 / 08-20); R4 ships dark behind a
   flag until ruled.

## 8. §Meta-pattern

One defective belief generates most findings of this lane: **"a well-argued decision keeps
itself."** The organism invests world-class machinery in the *moment* of deciding — grounding,
heterogeneous adversarial council, CI-gated convening, per-finding dispositions: every AHEAD in
§4 — and nothing in the decision's *afterlife*: status, supersession, revisit, findability,
citation integrity — every BEHIND in §4. This is superscar family #2 (esiste ≠ armato)
manifesting at the record layer: a decision without a status machine and receptor is a cron
without heartbeat — green because nobody looks. The same belief explains the ADR organ dead
since March while dossiers thrive, the never-amended skill resting on a phantom source, the
uncountable over-convening, the misfire log silent during the misfires, the 94%-empty
`cicatrix_refs`, and two constitutional texts answering "who decides" differently. Every
other tissue — organs, guards, scars — has already earned its receptor; **decisions are the last
unmonitored organ**. The cure is not more deliberation; it is giving the record the same immune
surface the argument already has (R1, R2, R3, R6).

## 9. Sources

Accessed 2026-08-28 (this lane's two attempts). ⚠ = canonical location cited, page not
successfully fetched (404/403/budget), numbers not re-verified. "search-surfaced" =
existence/abstract seen in search results only.

1. **[S1]** Anthropic Engineering, *How we built our multi-agent research system* (2025-06-13) —
   https://www.anthropic.com/engineering/multi-agent-research-system — primary account of a
   production orchestrator-worker system with published numbers; re-verified via search this
   session.
2. **[S2]** Cemri et al., *Why Do Multi-Agent LLM Systems Fail?* (MAST), arXiv 2503.13657
   (2025-03, v3 2025-10) — https://arxiv.org/abs/2503.13657 — the reference failure taxonomy for
   multi-agent systems (1,600+ traces, κ=0.88).
3. **[S3]** Khan et al., *Debating with More Persuasive LLMs Leads to More Truthful Answers*,
   arXiv 2402.06782 (2024) — https://arxiv.org/abs/2402.06782 — strongest empirical result on
   debate judged by an independent weaker judge.
4. **[S4]** Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, arXiv
   2306.05685 (2023) — https://arxiv.org/abs/2306.05685 — canonical catalogue of judge biases
   (position, verbosity, self-enhancement) and mitigations.
5. **[S5]** Wynn, Satija, Hadfield, *Talk Isn't Always Cheap: Understanding Failure Modes in
   Multi-Agent Debate*, arXiv 2509.05396 (2025-09) — https://arxiv.org/abs/2509.05396 — measured
   error-amplification and reflexive agreement in debate; verified this session.
6. **[S6]** arXiv 2510.07517 (2025-10) — https://arxiv.org/abs/2510.07517 — identity bias in
   debate, anonymization mitigation; search-surfaced (prior attempt).
7. **[S7]** arXiv 2604.02668, sycophancy propagation in multi-agent settings (2026-04) —
   https://arxiv.org/abs/2604.02668 — search-surfaced (prior attempt).
8. **[S8]** arXiv 2602.09341, auditing reasoning trees vs majority vote / LLM-judge aggregation
   (2026-02) — https://arxiv.org/abs/2602.09341 — search-surfaced (prior attempt).
9. **[S9]** Michael Nygard, *Documenting Architecture Decisions* (2011-11-15) —
   https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions — the origin ADR
   text; every later template inherits its lifecycle.
10. **[S10]** Malte Ubl, *Design Docs at Google* (2020-07-06) —
    https://www.industrialempathy.com/posts/design-docs-at-google/ — first-hand description of
    the culture: non-goals, alternatives, the write-only-if gate.
11. **[S11]** Rust RFC process, rust-lang/rfcs README —
    https://github.com/rust-lang/rfcs — a live RFC lifecycle at scale, with FCP and explicit
    dispositions.
12. **[S12]** Neal Ford / Thoughtworks, *Fitness function-driven development* (2019-01-11) —
    https://www.thoughtworks.com/insights/articles/fitness-function-driven-development — the
    architecture-fitness-function practice article; book *Building Evolutionary Architectures* ⚠.
13. **[S13]** Gary Klein, *Performing a Project Premortem*, HBR (2007-09) —
    https://hbr.org/2007/09/performing-a-project-premortem — origin of the premortem with the
    +30% prospective-hindsight figure.
14. **[S14]** ⚠ Jeff Bezos, 2015 Amazon shareholder letter (one-way/two-way doors) —
    https://www.aboutamazon.com/news/company-news/2015-letter-to-shareholders — fetch 404; cited
    from the letter's widely reproduced text.
15. **[S15]** ⚠ Newcombe et al., *How Amazon Web Services Uses Formal Methods*, CACM 58(4)
    (2015) — https://cacm.acm.org/research/how-amazon-web-services-uses-formal-methods/ — fetch
    403; the canonical industry formal-methods report (TLA+ at AWS).
