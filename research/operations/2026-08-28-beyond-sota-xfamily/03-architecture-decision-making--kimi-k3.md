---
panel: beyond-sota-xfamily
lane: 03-architecture-decision-making
seat: kimi-k3
model: "kimi-code/k3 · Kimi CLI print mode (tools)"
started: 2026-08-28T18:37:51Z
finished: 2026-08-28T18:48:44Z
duration_s: 653
exit: 0
words: 4684
prompt_sha256_16: 855f08d509174dd9
prompt_chars: 17581
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

• [Machine check] Then grounding on the hot files.

• [Pro] — now reading the two priority skill files and grepping modus for the DESIGN/council gate.

• Next: measuring the organs registry, decision-record locations, and scar/ledger evidence.

• Strong signal already: `docs/adr` holds exactly one ADR vs 514 research files. Continuing grounding.

• Rich ledger evidence captured. Now the doctrine files and prior decision artifacts.

• Repo grounding done. Moving to the SOTA survey — parallel searches for primary sources.

• Three more survey searches in parallel.

• Final survey batch, then I write the report.

• One last measurement pass, then the report.

• All evidence gathered. Here is the complete report, returned in-message per the lane instruction (no file written; the final `ls -la` probe is therefore not applicable — stated explicitly rather than claimed).

  ---

  ```
  ---
  date: 2026-08-28
  domain: operations
  panel: beyond-sota-2026-08-28
  part: 3/13 — Architecture & design decision-making
  model: Moonshot Kimi K3 (pinned lane, kimi-code/k3 via Kimi CLI)
  sources: 16
  repo_files_verified: 25
  ---
  ```

  # Architecture & design decision-making — beyond-SOTA lane report

  ## 0. TL;DR

  Nuzantara's decision *doctrine* is at or past the published state of the art — an evidence-grounded 8-step loop, a cost-aware council gate, asymmetric-adversarial roles, and falsifiable decision metrics — but its decision *capture and enforcement* is well behind: the ADR file is six months stale (11 records, last edit 2026-02-26, `docs/ARCHITECTURE_DECISION_RECORDS.md`), `docs/adr/` holds exactly one file, and the executable council configuration provably drifted from doctrine (PENDING-ARMS 2026-07-25, worker-plane v2 config still encoded while doctrine moved to v3). Biggest gap: decisions are debated rigorously and then evaporate into chat — no live decision index, no ex-ante calibration, no fitness function guarding the decision machinery itself. Top-3 moves: (1) a scar-linked, CI-enforced ADR-lite index emitted by the DESIGN stage with reversibility class and revisit date; (2) an ex-ante decision-calibration ledger (predicted outcome + confidence + revisit) scored by an existing cron — something no surveyed organization does; (3) an organ-conformance-style gene gate applied to the *council configuration itself*, so doctrine-vs-code drift in the decision apparatus fails CI instead of being discovered by a lane report four months later.

  ## 1. How Nuzantara does it today

  Every claim below was verified on disk in this session.

  **The decision loop.** `.claude/skills/sota-architecture-loop/SKILL.md` (158 lines, vendored 2026-07-17) defines an 8-step loop: FRAME → GROUND → REASON → COUNCIL → DECISION → EXECUTE → VERIFY → CAPTURE. Its three generating rules — *heterogeneity beats numerosity, calibrated adversariality beats consensus, external verification beats self-declaration* — are stated with measured evidence (homogeneous-debate sycophancy up to 85.5%, conformity rising with panel size and rounds). STEP 3 carries an explicit *negative* gate: convene the council only if all three of (a) divergent training priors can change the answer, (b) the error costs more than ~15× tokens, (c) the work is genuinely parallel — with a decision table that says NO for mechanical tasks, known-cause bugs, and easy rollbacks. This "when NOT to convene" discipline is rarer in industry than the council itself.

  **The master loop and the DESIGN stage.** `.claude/skills/modus/SKILL.md:33-84` triages every mandate into gears 1/2/3 (the "anti-sperpero brain"), and its stage 2 (DESIGN, line 77) delegates to sota-architecture-loop steps 0–4, requiring **a durable spec artifact on disk** — "BUILD consumes the file, not the chat memory" — plus operator GO for high-risk classes. The anti-sperpero rules (lines 48–67) repeat the three-condition council gate and add a **CI-computed ceiling**: `compute_ceiling()` in `scripts/evidence_pack_lint.py` (PR #4474) fails a lint if a docs-only or ≤2-file diff declares Gear 3 with a council, unless `evidence/pack.yml` carries a `gear_override:` reason. A floor *and* a ceiling on ceremony, both recomputed mechanically per diff — I found no surveyed system with this.

  **Councils and seats.** CLAUDE.md §6 mandates a **4-LLM panel pre-approval** for architectural specs, client quotes, and pre-deploy critical paths (Gemini agy + Codex GPT-5.6 + Kimi K3 + optional NotebookLM as ground-truth panelist), flat-subscription only, ~2min wall. The modus Arsenal table (SKILL.md:126-135) pins role-to-family assignments with a hard **family-exclusion rule**: a family that built or counter-built is excluded from its own refuter chain, and two refuters from two different families are required. Review is **asymmetric on two axes** — role (proponent/red-team/constructive on three *different* models) and incentive (red-team prompted "default to defective", constructive prompted to *save* the idea) — closing on an empirical gate (pytest/Codex sandbox/curl 200), never on consensus and never on the builder's self-report.

  **Specimen of the practice working.** `research/design/2026-08-28-case-code-design.md` (259 lines, today) is a design dossier whose §Adversarial review records a two-seat cross-family pass (Codex gpt-5.6-sol: 13 findings; Kimi K3: 11 findings), 20 unique findings after dedup, **17 APPLIED / 3 REJECTED-with-reason**, each disposition citing the section amended — including a finding where the red-team caught the author over-widening an owner's ruling (CC-D1, withdrawn entirely). This is decision hygiene most engineering orgs do not practice.

  **Decision capture — the weak flank.** `docs/ARCHITECTURE_DECISION_RECORDS.md` contains 11 ADRs (ADR-001…ADR-011), header says "Last Updated: 2026-02-26" — six months stale at snapshot time. `docs/adr/` holds one file (ADR-006-nb-mitochondrial-monitor, 2026-05-07 — a *second* numbering space, note: it collides numerically with the main file's ADR-006 "Abstract Channel Pattern"). `docs/decisions/` holds one file. `docs/specs/` holds five. Against that: **309** top-level files in `research/operations/`, 15 in `research/design/`, and the memory corpus (1,707 files per the lane brief — the `$MEM` paths themselves are **unavailable to me** in this snapshot, stated per protocol; I used the repo's own copies). Decisions are captured abundantly, but as *research dossiers, scars and memory notes* — not as a numbered, status-tracked, supersession-linked decision log.

  **Anatomy as decision substrate.** `apps/organism/organism/organs_registry.yaml` (87,418 bytes) registers **170 organs**, each with `runtime`, `type`, `expected_hb_seconds`, `owner_module`, `dependencies`, `recovery_action`, `severity_on_silence`, `cicatrix_refs` — an architectural inventory where every component carries its own failure semantics. `infra/organ-conformance/genes.json` defines a *genome* (G1 registry entry, G2 heartbeat sidecar, G3 declared HOME pair, G4 node guard, G5 kill switch…) consumed both by a CI gate (`check_organ_conformance.py`) and by the generator (`scripts/organ_birth.py`) — "a divergence is a failing test". This is Ford/Parsons **fitness functions in CI**, implemented, with a grandfathered-baseline mechanism whose shrink rate is the cure metric. `INDEX.md` is the atlas ("5 Libri sacri — 5 funzioni cognitive"). `packages/research-os-core/research_os/` holds pydantic contracts for an evidence-to-action spine (`DecisionPacket`, `Evidence`, `ApprovalReceipt`, `ExecutionAttempt`, frozen closed-enum registry v1.0.0) with a machine-readable validator CLI — decisions modeled as *typed, hashable objects*, which is ahead of anything in the surveyed literature.

  **Constraints as architecture.** `SYMBIOSIS.md` §LE LEGGI pins non-negotiables (Law 1 CLI-only LLMs; Law 2 PII output boundary, two-phase DEV/PROD; Law 7 no metric = not an improvement). These function as architectural constraints every DESIGN stage must satisfy — the reuse-first skill (`.claude/skills/reuse-first/SKILL.md`, 132 lines) operationalizes "who already wrote this brick" with a license gate (copyleft = study-pattern-rewrite, never copy) and PII/cloud constraint adaptation, i.e. a formalized buy-vs-build decision procedure.

  ## 2. Scars & ledger evidence in this area

  The scar corpus is the honest instrument here. `.claude/rules/cicatrix-superscar.md` defines 11 families + orphans; `.claude/rules/cicatrix-scars.md` carries 19 active W-scars (more in the 397KB archive). The decision-relevant lineage:

  - **Superscar #6 (anti-hallucination blindness)** is explicitly a *decision-process* failure line, stated in the superscar file itself: **W65** (the refuter hallucinates — a generator grading itself is strictly worse) → **W74** (phantom scorer) → **W78** (wrong scar propagated) → **W90** (ground-truth verifier went stale) → **W100** → **W113** (the correction itself lies).
  - **W100** (`.claude/rules/cicatrix-scars.md:760`, 2026-07-18) is the single most important measured result for this lane: a same-family extractor+verifier lane certified **8 clean verdicts of which 7 were FALSE-clean** on production-bound licensing payloads. Blind agreement measured 0.923 IAA — but between two seats of the *same* family it "measures fidelity of transcription, not truth". The antibody now codified: cross-family, image-grounded re-extraction, provenance pointers resolved against the corpus, and — decisively — the *signed report itself* must pass external red-team before shipping, because the red-team caught the conductor in a "picked verdict" against two cross-family seats. GOTCHA (a) states the metric lesson: "Never cite an IAA as evidence of truth without declaring the seats' kinship."
  - **AMENDMENTS** (`.claude/skills/modus/AMENDMENTS.md`) — the loop's own misfire log — shows the *council machinery* failing operationally: 2026-07-02, the refuter cascade discovered two dead seats mid-run (DeepSeek 402, GLM permission-denied) and the council ran degraded 2-seat; the fix added probe-then-cascade plus the rule that a seat failing its live probe is itself an un-armed artifact needing a PENDING-ARMS line. 2026-08-22 (the heaviest row): two "reduce token waste" sessions ran 44h/31h, opened 180 PRs, shipped ~10 business commits, and *this file got zero entries while it happened* — the loop optimized itself; remedy shipped same day including "a 'reduce waste' mandate is itself meta-work — gear it 2 with a stop-loss, never Gear 3 with an open council".
  - **PENDING-ARMS** (grep-only): the 2026-07-25 row documents that `scripts/check_worker_plane_review.py` *still encodes the retired v2 council architecture* (fable as co-equal panelist, glm-5.2 expected, codex/kimi absent, panel size hardcoded) months after doctrine moved to v3 — doctrine and executable config drifted apart with no gate between them. A 2026-08-17 row: an anti-forgery gate kept running green while its payload went structurally empty (family #2, esiste ≠ armato). A 2026-08-21 row: the deterministic gear floor had **no ceiling** — floor-1 diffs still paid council + cross-family refuters (cured by PR #4474's `compute_ceiling`). And the 2026-08-27 queue-shepherd row: a budgeted re-arm mechanism shipped *uninstalled* — decision made, artifact built, never armed.
  - **Recurrence check:** family #6's six-generation line (W65→W113) and the repeated "gate exists but does not run" pattern (`research/operations/2026-08-24-garuda-voa-the-defects-were-in-the-joint.md` §3 is literally titled "The gate that exists and does not run") show the failures recur *until encoded as executable checks*, and stop recurring when they are (W102's hot-zone gate now self-tests its own enumerator every run, PROVEN-LIVE).

  ## 3. World SOTA survey

  | # | System / practice | Source (date) | Mechanism that makes it best-in-class | Measured effect | Transferability here |
  |---|---|---|---|---|---|
  | 1 | Nygard ADRs | cognitect.com, 2011-11 | Small immutable records: context/decision/status/consequences; monotonic numbers, superseded-not-deleted | Became the default decision-capture unit across industry (Spotify, GitHub, Atlassian practice docs) | Directly; we have the *idea* but a stale 6-month-old file |
  | 2 | MADR + adr.github.io tooling | adr.github.io/madr (2018–) | ADR format tuned for "significant but not huge" decisions; markdown, PR-integrated | Community standard | Directly; our research/ dossiers are 10–50× heavier than MADR's intended unit |
  | 3 | Google design docs | industrialempathy.com (2020) | Informal 10–20pp doc, *before* coding; goals/non-goals, alternatives considered, cross-cutting concerns; doc as organizational memory | Institutional scale (every Google project) | Our case-code dossier matches the *form*; missing the *index* and the alternatives-considered discipline at small scale |
  | 4 | Amazon one-way/two-way doors | Bezos 2015 shareholder letter | Classify decisions by reversibility; Type-1 slow/deliberate, Type-2 fast/delegated; guard against Type-1 process applied to Type-2 decisions | Cultural (Amazon velocity doctrine) | Our council table uses "irreversible" as the YES trigger but never *records* the door type per decision |
  | 5 | Evolutionary Architecture fitness functions | Ford/Parsons/Kua, O'Reilly 2nd ed. 2022 | Architectural governance as automated checks in the delivery pipeline, versioned with the code | Industry-adopted (ArchUnit, ts-arch, netarchtest ecosystems) | We already do this for *organs* (genes.json) — the beyond-SOTA move is applying it to the *decision apparatus* |
  | 6 | AWS formal methods (TLA+) | Newcombe et al., CACM 58(4) 2015 | Model-check the *design* of distributed protocols before building; "found bugs in ambitious designs before a line of code" | 10+ production systems; bugs found at design stage | Our lease registry, worktree broker, queue-shepherd re-arm logic are exactly TLA+-shaped; currently test-verified only |
  | 7 | Multi-agent debate (Du et al.) | arXiv:2305.14325, ICML 2024 | Multiple LLM instances debate over rounds; improves factuality/reasoning | Significant gains on GSM8K/factuality vs single-model | Validates council *concept*; our heterogeneity+role asymmetry exceeds it (their setup is homogeneous clones) |
  | 8 | Debate for truthfulness (Khan et al.) | arXiv:2402.06782, ICML 2024 | Adversarial debate judged by a *weaker non-expert* judge yields more truthful answers than consultancy | Non-expert judges pick truth more reliably with debate | Validates generator≠grader with a judge weaker than the builder — matches our cross-family refuter quorum |
  | 9 | Mixture-of-Agents | arXiv:2406.04692, 2024-06 | Layered proposer→aggregator architecture exploits "collaborativeness" | 65.1% AlpacaEval 2.0 vs GPT-4o's 57.5% using only OSS models | Strong evidence *for* our heterogeneous panel; but MoA is same-task aggregation, not role-asymmetric — our design is ahead on decision tasks |
  | 10 | MAST failure taxonomy | arXiv:2503.13657 (Cemri et al., 2025-03) | 1,600+ annotated traces across 7 frameworks → 14 failure modes in 3 categories | First empirical MAS failure taxonomy; NeurIPS 2025 | Our superscar families already empirically cover several MAST modes (verification failure, role/termination errors) from production scars — mapping exercise recommended |
  | 11 | LLM-as-judge bias | arXiv:2306.05685 (Zheng et al., NeurIPS 2023) | Names position/verbosity/self-enhancement bias; swap-and-average mitigations | GPT-4 judge >80% human agreement when debiased | Our "never same-family judge" rule anticipates self-enhancement bias; position/verbosity debiasing is *not* systematically applied to our refuter outputs |
  | 12 | Anthropic multi-agent research system | anthropic.com/engineering, 2025-06-13 | Orchestrator-worker; multi-agent wins on breadth-first research; **~15× token cost vs chat**; subagent outputs passed back compressed | ~90% improvement on internal research eval; explicit "coding has fewer parallelizable tasks" caveat | Their 15× number *is* our anti-sperpero gate's cost constant — our doctrine cites it. Transferable: their eval-first small-sample discipline |
  | 13 | Debate failure modes | arXiv:2509.05396 ("Talk Isn't Always Cheap", 2025-09) | Systematic failure analysis of MAD: conformity, degeneration-of-thought, when debate underperforms single-agent | Debate can *hurt* vs single strong agent | Directly encoded in our skill already ("1→5 rounds raises conformity; single agent with 10× budget beats clones at 1/3 cost") |
  | 14 | Premortem | Klein, HBR 2007-09 | "Imagine the project has failed; write the story" — prospective hindsight | +30% ability to identify risks (Mitchell/Russo/Pennington lineage; Kahneman-endorsed) | Our red-team seat is premortem-adjacent but not framed as one; cheap to formalize |
  | 15 | Rust RFC process | github.com/rust-lang/rfcs | Text-file RFCs, numbered, final-comment-period, merged-file-as-record; decision lives in the repo | Decade-scale community governance | Model for our missing decision index |
  | 16 | Team Topologies / Conway | Skelton & Pais 2019 | Org structure determines architecture; stream-aligned team boundaries | Industry-standard org design | Partially relevant — our "teams" are model families; the fleet topology *is* our Conway surface |

  **The 3–5 that matter most.** (a) **AWS/TLA+** — because our hardest recurring scar families (#9 state-schema drift, #10 split-brain, #5 sibling-race) are *distributed-state design errors*, precisely the class model-checking kills at design time. (b) **Evolutionary architectures** — because we have already independently reinvented fitness functions for organs; the insight to steal is their *scope discipline*: every architectural principle should either be a check or admit it is folklore. (c) **Khan et al. debate** — because it supplies the missing theoretical grounding for why a *weaker* cross-family refuter can still gate a stronger builder (non-expert judge reliability), which our fleet economics depend on. (d) **MAST** — because its 14-mode taxonomy is the first external yardstick against which our 11 superscar families can be audited for coverage gaps. (e) **Nygard/Rust RFCs** — not for the format, but for the *monotonic numbered index with supersession links*: the one capture primitive we demonstrably lack (ADR file stale 6 months; two colliding ADR-006s).

  ## 4. Position vs SOTA

  | Sub-dimension | Position | Evidence |
  |---|---|---|
  | Ground-before-reason framing | **AHEAD** | sota-architecture-loop STEP 1 includes *disk-state as ground* for internal domains; measured kill of a phantom feature in 3 tool calls (W62, in-skill). No surveyed system grounds on live disk state |
  | Council composition (heterogeneity, role+incentive asymmetry) | **AHEAD (doctrine)** | Two-axis asymmetry + family-exclusion quorum (modus SKILL.md:126-135) exceeds Du et al. (homogeneous) and MoA (role-free). But doctrine-only in places → |
  | Council gate (when *not* to convene) | **AHEAD** | Three-condition negative gate + decision table + CI-recomputed ceiling (`compute_ceiling`, PR #4474). Anthropic publishes the 15× cost; nobody surveyed *enforces* the abstention in CI |
  | Decision gates (go/no-go + falsifiable metric) | **AT** | Law 7 + DESIGN-stage metric requirement; matches Well-Architected/Google rigor; not consistently *recorded* per decision |
  | Decision capture (ADR practice) | **BEHIND** | `docs/ARCHITECTURE_DECISION_RECORDS.md` stale since 2026-02-26; two colliding ADR-006s; 309 research files vs 11 ADRs; no supersession DAG, no index, no door-type field |
  | Reversibility discipline (doors) | **AT** | Used as council trigger; never recorded per decision |
  | Anatomy/fitness functions | **AHEAD** | genes.json genome with generator↔gate divergence = failing test; grandfathered baseline shrink as cure metric. This *is* evolutionary architecture, plus a birth-generator loop Ford et al. don't have |
  | Decisions as typed contracts (Research OS) | **AHEAD** | `DecisionPacket`/`ApprovalReceipt`/`Evidence` as hashed pydantic contracts with validator CLI — no surveyed system models decisions this way |
  | Lightweight formal methods | **BEHIND** | Zero TLA+/Alloy anywhere; distributed decision machinery (leases, re-arm budgets) is test-verified only |
  | Decision-quality measurement (calibration) | **BEHIND** (industry-wide: nobody does it) | No ex-ante predictions, no revisit dates, no calibration score; scars measure *failures*, not *forecast error* |
  | Council-config integrity | **BEHIND** | PENDING-ARMS 2026-07-25: executable council config drifted from doctrine for months, found by a lane report, still open |

  ## 5. Beyond-SOTA recommendations

  Ranked by (impact × confidence) / cost.

  **R1 — Decision Records v2: scar-linked ADR-lite index, CI-enforced.**
  *What:* every Gear-2/3 DESIGN stage appends one record to `docs/decisions/INDEX.jsonl` (monotonic id, one line): `{id, date, title, door_type(1|2), falsifiable_metric, revisit_date, scar_refs[], supersedes, council_seats[], verdict}`. A harness-floor-adjacent CI check (same pattern as `compute_ceiling`) flags architecture-shaped diffs (hot-zone paths, new organ, new router, migration, workflow) lacking a referenced decision id. *Why beyond SOTA:* composes Nygard + Bezos door-types + our scar corpus + CI-recomputed floors into a *living* decision log — the surveyed ADR practice is exactly what our stale file demonstrates dies: unenforced. Nobody runs ADR issuance as a CI-recomputed ceremony floor. *Cost:* ~150 lines script + workflow step; zero per-decision tokens (the DESIGN stage already writes the dossier — this is its header). *Gear:* 2. *Risk:* family #9 (index schema drifts from reader) — mitigated by a tripwire test; family #2 if the check ships unwired — the acceptance test *is* a red PR. *Metric:* % of architecture-shaped merged PRs carrying a decision id: before ≈ unmeasurable (11 ADRs in 8 months, 0 since Feb) → after ≥90%; measurement: weekly grep of the index vs hot-zone PR list. *Kill criterion:* 90 days with zero *reads* of the index in session artifacts → dead weight, fold back into research/ capture. *First PR:* `scripts/ci/decision_index_lint.py` + `.github/workflows/` step + 20 seed records backfilled from existing dossiers (~350 lines).

  **R2 — Ex-ante decision-calibration ledger.**
  *What:* each council decision records `predicted_outcome, confidence, revisit_date` in the index (R1 field); a weekly cron (the fleet already runs 224 daemons; one more line) re-opens due revisits and scores them against realized state (scar appeared? metric moved? reverted?). Output: a running Brier-style calibration score per *seat* and per *decision class*. *Why beyond SOTA:* Kahneman/Klein decision hygiene operationalized for an agent fleet — *no surveyed org measures whether its architecture council is calibrated*; we would be measuring whether the 4-LLM panel's confidence tracks reality, turning the council from ceremony into instrument. This exploits an asymmetry no company has: flat-subscription councils at zero marginal cost + an always-on daemon fleet + a scar corpus to score against. *Cost:* one cron + scoring script (~120 lines); ~0 tokens (revisit scoring is disk-state). *Gear:* 2. *Risk:* family #6 if revisit scoring is done by an LLM self-reporting — mitigate: scoring is mechanical (scar-exists? PR-reverted? metric-moved?), LLM only arbitrates ambiguous rows with a cross-family seat. *Metric:* calibration curve over N≥30 scored decisions; seat-level overconfidence deltas. *Kill:* after 30 decisions the score never changes any routing decision → the instrument is informative-but-useless; keep the journal, drop the score. *First PR:* `scripts/decision_ledger.py` (append + score + due-list) + one launchd plist (needs organ-birth genes, trivially satisfied via `organ_birth.py`).

  **R3 — Council-config gene gate (fitness functions for the decision apparatus).**
  *What:* an organ-conformance-style genome for decision machinery: one SSOT JSON (`infra/council-conformance/routes.json`) naming seats, family-exclusion rules, quorum, effort floors; a CI check that every script encoding council routes (`check_worker_plane_review.py`, `launch_worker_plane_review_panel.py`, `freeze_worker_plane_review.py`) parses against it — doctrine-vs-code divergence = failing test, exactly the genes.json contract. *Why beyond SOTA:* evolutionary-architecture fitness functions applied one level up, to the *meta-architecture that decides the architecture* — the surveyed practice (ArchUnit et al.) guards product architecture; nobody guards their review machinery's configuration drift in CI. Directly cures the open PENDING-ARMS 2026-07-25 wound. *Cost:* ~200 lines + refactor of the three scripts to import the SSOT. *Gear:* 2. *Risk:* family #2 (gate exists, doesn't run) — acceptance requires a deliberately-drifting test PR going red; family #9 if doctrine changes without the SSOT — SSOT edit requires the doctrine diff in the same PR (checked). *Metric:* council-config drift incidents/quarter: before = 1 known, open 4+ weeks → after = 0 undetected (detection time < 1 CI run). *Kill:* N/A — this is a gate; gates don't get kill criteria, they get W102-style self-tests. *First PR:* `infra/council-conformance/` + check + fix `check_worker_plane_review.py`'s retired v2 constants (closes the PENDING-ARMS row).

  **R4 — Premortem seat for one-way-door decisions.**
  *What:* in sota-architecture-loop STEP 3, when the decision table hits an irreversible row, the red-team prompt gains the Klein frame verbatim: "It is six months later and this decision failed. Write the failure story. Default to defective." Failure stories are recorded in the R1 index and *diffed against the scar corpus at revisit* (R2). *Why beyond SOTA:* premortem is human-culture practice; wiring its output into a mechanical scar-diff loop closes the foresight→hindsight circuit nobody closes. *Cost:* one prompt edit (~20 lines). *Gear:* 1. *Risk:* family #6 — a vivid premortem story later quoted as a real incident; mitigated by a mandatory `hypothetical: true` field in the index record. *Metric:* fraction of premortem failure modes that materialize as scars within 90 days (lower = better foresight or better decisions; either way informative). *Kill:* premortem stories show zero overlap with realized scars across 20 decisions → the seat is writing fiction; revert. *First PR:* prompt edit + index field (≤60 lines).

  **R5 — TLA+/Alloy spike on the distributed decision machinery.**
  *What:* one Gear-3 spike: model the lease registry + worktree-broker mutual exclusion (the #5 sibling-race surface) in PlusCal, run TLC locally on Pro (free, local, no cloud). *Why:* this is pure catch-up to AWS-2015, not beyond — listed because the *composition* is beyond: model-check the machinery that allocates work to LLM agents. *Cost:* one spike (~1 day, flat-sub). *Gear:* 3. *Risk:* low; worst case is a learned dead end, captured as research. *Metric:* bugs found at design stage (target ≥1 — AWS's experience says distributed designs always hide one). *Kill:* TLC finds nothing AND the model is trivially faithful → abandon formal methods, record the negative result. *First PR:* `research/design/<date>-lease-registry-tla.md` + the `.tla` file.

  ## 6. 90-day roadmap

  **Wave 1 (weeks 1–3) — stop the bleeding.** R3 first PR (council-config gene gate; closes the open PENDING-ARMS row — highest certainty, repairs a *live* drift). R4 prompt edit (trivial, immediate). R1 first PR: index + lint + 20-record backfill. *Acceptance:* a test PR touching `apps/backend-rag/backend/app/dependencies.py` without a decision id goes red; with one, green.

  **Wave 2 (weeks 4–8) — instrument the council.** R2 ledger + cron + first 30-day revisit batch scored. MAST-mapping exercise: audit the 11 superscar families against MAST's 14 modes, write the coverage-gap report (`research/operations/`), adopt any missing mode as a family candidate. *Acceptance:* calibration score computed over ≥30 scored decisions; MAST map published with per-mode verdicts.

  **Wave 3 (weeks 9–13) — design-time verification.** R5 TLA+ spike on the lease registry. Extend genes.json-style conformance from organs to *specs*: DESIGN-stage dossiers carry a machine-checkable header (the R1 index record) so the spec corpus becomes queryable. *Acceptance:* TLC run report in-repo; `research/design/` headers ≥80% index-compliant.

  ## 7. Needs-ruling

  None strictly required for R1–R5 (all are repo-internal, flat-cost, CLI-only). Two *optional* business calls surface for Zero's awareness, not blocking: (a) whether the decision index should ever be cited client-facing (Legge 5 surface — default: never); (b) whether seat-level calibration scores (R2) may feed future fleet-routing rulings — that re-weights seat economics, which is Zero's call per CLAUDE.md §5.

  ## 8. §Meta-pattern

  One defective belief generates nearly everything in sections 1–2: **"the rule being written down is the control being installed."** It is superscar #2 (*esiste ≠ armato*) lifted one level — from daemons and gates to *decision machinery*. It recurs as: the ADR file written then abandoned for six months while 300+ research dossiers carried the real decisions; the council retired in doctrine but still encoded in `check_worker_plane_review.py` (four months, discovered by accident); the re-arm budget mechanism built, tested, and never installed; the anti-forgery gate running green with an empty payload; and the loop's own misfire log receiving zero entries while the loop optimized itself for 44 hours. Every durable cure in the corpus has the same shape — the rule became *executable and self-probing* (genes.json's divergence-is-a-failing-test, W102's self-testing enumerator, the CI-recomputed ceiling). Accordingly, every recommendation above converts a decision *practice* into a decision *artifact with a gate* — R1/R2/R3 are the same antibody applied to capture, calibration, and configuration respectively. The beyond-SOTA claim of this lane reduces to one sentence: **apply the organism's own proven cure — nothing is true until a check runs — to the apparatus that makes decisions, not only to the systems the decisions are about.**

  ## 9. Sources

  1. Nygard, "Documenting Architecture Decisions" — cognitect.com/blog/2011/11/15/documenting-architecture-decisions (2011; accessed 2026-08-28). Foundational ADR practice; the superseded-not-deleted rule our capture lacks.
  2. MADR / ADR organization — adr.github.io/madr (accessed 2026-08-28). Community-standard lightweight ADR format and tooling.
  3. "Design Docs at Google" — industrialempathy.com/posts/design-docs-at-google/ (2020; accessed 2026-08-28). Primary practitioner account of the largest design-doc culture.
  4. Bezos, 2015 Letter to Shareholders — Amazon/SEC archive (2016-04; accessed 2026-08-28). Canonical one-way/two-way door source.
  5. Ford, Parsons, Kua, Sadalage, *Building Evolutionary Architectures*, 2nd ed., O'Reilly 2022 (accessed 2026-08-28). Fitness functions as CI-resident governance — the frame for R3.
  6. Newcombe et al., "How Amazon Web Services Uses Formal Methods", CACM 58(4):66–73 — cacm.acm.org/magazines/2015/4/184701 (2015; accessed 2026-08-28). Design-stage TLA+ verification with measured bug finds.
  7. Du et al., "Improving Factuality and Reasoning in Language Models through Multiagent Debate", ICML 2024 — arxiv.org/abs/2305.14325 (2023; accessed 2026-08-28). The debate baseline our asymmetric design exceeds.
  8. Khan et al., "Debating with More Persuasive LLMs Leads to More Truthful Answers", ICML 2024 — arxiv.org/abs/2402.06782 (2024; accessed 2026-08-28). Grounds the weak-judge/strong-builder pattern.
  9. Wang et al., "Mixture-of-Agents Enhances Large Language Model Capabilities" — arxiv.org/abs/2406.04692 (2024-06; accessed 2026-08-28). 65.1% vs 57.5% AlpacaEval 2.0; heterogeneity evidence.
  10. Cemri et al., "Why Do Multi-Agent LLM Systems Fail?" (MAST), NeurIPS 2025 — arxiv.org/abs/2503.13657 (2025-03; accessed 2026-08-28). 14-mode failure taxonomy over 1,600+ traces; the yardstick for our superscar coverage.
  11. Smit et al., "Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate" — arxiv.org/abs/2509.05396 (2025-09; accessed 2026-08-28). When debate underperforms; already encoded in our anti-sperpero gate.
  12. Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", NeurIPS 2023 — arxiv.org/abs/2306.05685 (2023; accessed 2026-08-28). Position/verbosity/self-enhancement bias taxonomy for judge seats.
  13. Anthropic, "How we built our multi-agent research system" — anthropic.com/engineering/multi-agent-research-system (2025-06-13; accessed 2026-08-28). ~15× token cost, breadth-first win, coding caveat — our council-gate cost constant.
  14. Klein, "Performing a Project Premortem", HBR — hbr.org/2007/09/performing-a-project-premortem (2007-09; accessed 2026-08-28). Prospective hindsight; +30% risk-identification lineage.
  15. Rust RFC process — github.com/rust-lang/rfcs (accessed 2026-08-28). Decade-scale numbered decision log as repo files.
  16. Spotify Engineering, "When Should I Write an Architecture Decision Record" — engineering.atspotify.com/2020/04 (2020; accessed 2026-08-28). Pragmatic ADR-trigger criteria from a scaled org.

  **Repo verification note:** 25 repo paths verified on disk this session (skills ×3, doctrine ×4, scars/ledger ×4, registry/genes/contracts ×4, decision artifacts ×6, prior panels ×4). The `$MEM`/`MEM:` references in the lane brief are **unavailable** in this read-only snapshot (no access outside it); the repo's own copies were used instead, and the two memory files named in the brief could not be read — their content is referenced only via the CLAUDE.md §6 citation, which was verified.

  status: complete

