---
panel: beyond-sota-xfamily
lane: 03-architecture-decision-making
seat: tp1-qwen3.8-max
model: "qwen3.8-max · enable_thinking · TP1 API, no tools, ground pack"
started: 2026-08-28T16:40:05Z
finished: 2026-08-28T16:49:12Z
duration_s: 547
exit: 0
words: 4788
prompt_sha256_16: 7060fae0b829da58
prompt_chars: 162581
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 3/13 — Architecture & design decision-making
model: Qwen3.8 Max (pinned lane)
sources: 18
repo_files_verified: 13
status: complete
sections_done: [0,1,2,3,4,5,6,7,8,9]
---

*Returned as FINAL MESSAGE per lane instructions (no file/shell access in this lane). Target path if persisted: `research/operations/2026-08-28-beyond-sota-architecture-decision-making.md`. "Verified" here = present in the appended GROUND PACK excerpt; several pack files are truncated (noted inline). No shell, web, or MEM access: `MEM:` files `feedback_always_review_spec_with_4_llm.md` and `MEMORY_METHOD_LESSONS.md` were NOT FOUND in the snapshot — claims depending on them are labelled ASSUMED. Estimated length ≈4,300 words (wc not runnable here).*

---

## 0. TL;DR

**Position:** AHEAD of SOTA on decision *moments* (grounded triage, council gates, asymmetric adversarial review, living organ anatomy); BEHIND on decision *lifecycles* (recording, outcome-tracking, supersession, revisit).
**Biggest gap:** decisions have no genome. Organs get 10 CI-enforced genes (G1–G10), heartbeats, kill switches, ledger lines and cicatrix refs; decisions get written once and rot — `docs/ARCHITECTURE_DECISION_RECORDS.md` is frozen at "Last Updated: 2026-02-26" while 364 research files accumulated with no status, no supersession graph, no outcome scored.
**Top-3 moves:**
1. **Decision genome:** revive ADRs as a linted graph (status, one-way/two-way door, falsifiable metric, `supersedes`/`superseded_by`, outcome-due date) with a CI lint and monthly decay report.
2. **Architecture genes:** extend the proven `infra/organ-conformance/genes.json` pattern to structural invariants (PII boundary, reversible migrations, decision-metric-present) as CI fitness functions with a shrinking grandfathered baseline.
3. **Council telemetry + scar-conditioned pre-mortems:** measure the organism's own conformity/outcome-change rates instead of citing external 7–8B numbers; pre-mortem conditioned on the scar corpus.

## 1. How Nuzantara does it today

*Every claim below is grounded in the pack; truncated files noted. Files verified in pack: 13 (see frontmatter).*

**The decision loop.** `.claude/skills/sota-architecture-loop/SKILL.md` defines an 8-step loop — `FRAME → GROUND → REASON → COUNCIL → DECISION → EXECUTE → VERIFY → CAPTURE` — derived from three rules: *"Eterogeneità batte numerosità · Adversarialità calibrata batte consenso · Verifica esterna batte autodichiarazione."* Two structural choices matter:
- **GROUND before REASON** is mandatory and domain-typed: normative facts → NotebookLM + deep research; internal facts → *disk state* (`ls`/Read/grep/git/launchctl/log). The skill records the empirical payoff: W62 (2026-05-30) "questo step ha ucciso una feature fantasma in 3 tool call" — a cicatrix said a fix was NOT shipped, the disk said shipped-but-disarmed-by-a-missing-flag.
- **DECISION is a kill gate**: "go / no-go / defer + 1 metrica falsificabile", explicitly bound to SYMBIOSIS Law 7 (mapping table, STEP 4: "Symbiosis L7").

**Council economics and gating.** The same skill states the council costs "~15× i token" (attributed to Anthropic) and may be convened **only if all three hold**: (1) divergent priors can change the answer, (2) the error costs more than 15× tokens, (3) the work is genuinely parallel/breadth. It ships a decision table (irreversible architecture → council; known-cause bugfix → no council; mechanical task → "esegui e basta") and names anti-patterns with numbers: N-clones of one model collapse into groupthink ("sycophancy fino 85.5%, abbandona risposte corrette fino 70%" on 7–8B debate; a single agent with 10× budget beats it at ⅓ cost); large panels and many rounds raise conformity ("shrink maggioranza 6→3 dimezza il conformity; 1→5 round lo alza") → 3 panelists, capped rounds, never "discutete finché concordate".

**Asymmetric adversarial review.** The skill bans consensus closure ("'Siete tutti d'accordo?' … non nasconde solo l'errore: ne genera di nuovi") and splits review on two axes: *role* asymmetry (Proponente / Red-team / Costruttivo, each on a **different model**, proposer never judges itself) and *incentive* asymmetry (red-team rewarded for finding flaws — "Default a 'difettoso' se hai dubbi"; constructive rewarded for saving the idea). Closure is an **empirical gate** (`pytest`, sandbox, verify skill, curl 200), never the author's self-report.

**Gear triage and mechanized ceremony sizing.** `.claude/skills/modus/SKILL.md` (STAGE 0) classifies every mandate into Gear 1/2/3 and repeats the anti-sperpero rule: "Council is NOT automatic at Gear 3. Convene it only if ALL THREE…" Crucially, ceremony size is **mechanically enforced**, not just advised: "The FLOOR is enforced by `harness-floor.yml`; the CEILING is enforced too (`compute_ceiling()` in `scripts/evidence_pack_lint.py`, PR #4474)" — a docs-only or ≤2-file/≤60-net-line diff outside hot zones is "Gear-1-shaped by construction" and declaring it Gear 3 with a council fails the lint unless `evidence/pack.yml` carries `gear_override:`; hot-zone hits floor at Gear 3 regardless of diff size. Gear 3 carries a mandatory "§Meta-pattern" section and stop-loss budget declarations.

**Grounded specimen of the practice.** `research/design/2026-08-28-case-code-design.md` shows the loop working: §1 Ground is file:line-measured (e.g., `284:36-38`, `repository.py:164-197`, live ownership measured "via the readonly proxy"); a two-seat cross-family adversarial pass ("codex gpt-5.6-sol xhigh with in-repo verification, kimi k3") "reshaped" the dossier — it "killed the naive 'column on garuda_orders' design twice over" and refuted the first draft's declared R4 deviation "as a false dilemma, and the refuted design is withdrawn." Decisions are recorded with their refutations, including honest failure semantics (rolled-back creations reuse numbers; committed-then-abandoned orders keep codes) and an accepted risk ("volume signal … accepted-by-format — Zero's ruling").

**Anatomy as architecture.** `apps/organism/organism/organs_registry.yaml` is a machine-readable organ atlas. Each organ carries: `id`, `runtime` (fly_machine / pro_launchd / air_launchd), `type` (daemon/webhook/cron), `expected_hb_seconds`, `owner_module`, `dependencies`, `recovery_action` + `recovery_params`, `severity_on_silence`, `cicatrix_refs`, optional `bridge_source`, and — notably for decision-making — `enabled`/`disabled_reason` (e.g., `backend.crm.drive_poll`: "DISABLED 2026-04-29 in crontab after drive_poll saturated PG; keep registered as disabled"). **Organ census: UNMEASURED** (pack truncates at ~12K of 87,334 chars; 26 organs visible in excerpt). Command: `grep -c "^- id:" apps/organism/organism/organs_registry.yaml`.

**Organ-conformance genes.** `infra/organ-conformance/genes.json` defines 10 genes every launchd/cron organ must inherit (G1 registry entry, G2 heartbeat, G3 declared HOME pair, G4 node guard, G5 kill switch, G6 hardened headless spawn, G7 PENDING-ARMS ledger line at birth, G8 KeepAlive sanity, G9 fail-visible, G10 single-instance), consumed by `check_organ_conformance.py` (CI gate) and `scripts/organ_birth.py` (generator) so "gate and generator can never diverge." Its grandfathered baseline is report-only and regresses on growth: "shrinking the baseline is the cure metric; growing it requires a PR reviewer's eyes." ~52 grandfathered plists visible in the truncated excerpt.

**Atlas and doctrine layering.** `INDEX.md` ("Ultima revisione manuale: 2026-07-02") maps needs→books, with the 5-book doctrine (SYMBIOSIS=why, VADEMECUM=how, INDEX=where, CLAUDE.md=rules, cicatrix-scars=wounds) and the closure rule: if a question finds no answer there + MOS + NLM NB-14, "c'è un gap — aggiorna il libro giusto." Quantitative state is deliberately derived, not stored ("`python3 scripts/docs_sync.py --json`", CI artifact `docs-inventory-refresh.yml`). `SYMBIOSIS.md` supplies the constitutional constraints: structural decisions "passano sempre da Zero" (Pilastro 8 — "il sistema immunitario"), the Consiglio requires "diversità strutturale" across models ("Un devil's advocate LLM e' meno efficace di un autentico dissenziente"), and Law 1 (CLI-only) / Law 2 (PII output boundary) bound every design.

**Routing as architecture.** `scripts/federation_orchestrator.py` (docstring + visible code): LangGraph pipeline `CLASSIFY → CHECKPOINT → DISPATCH (parallel) → ASSEMBLE → REVIEW → OUTPUT`; classification by **local** Ollama `qwen3.5:9b` ("$0, fast classification") with keyword fallback; `run_dispatch` is a deliberate Law-2 chokepoint — "the single chokepoint that previously passed RAW prompts to the cloud (the Law-2 finding, spec §1)" — running `privacy_preflight` and refusing cloud dispatch on PII. `CLAUDE.md` adds static triggers (KBLI/visa→Gemini search; 3+ app refactor→Gemini explore; migration→Codex sandbox; pre-deploy Fly→Gemini redteam) and Preflight SDD tiers L1/L2/L3.

**Reuse-first as design constraint.** `.claude/skills/reuse-first/SKILL.md`: decompose into bricks → double search (internal repo, then GitHub) → classify (`[COPIA-DIRETTO]`/`[FORKA-E-ADATTA]`/`[STUDIA-PATTERN-RISCRIVI]`/`[INSTALLA-LIB]`/`[SCRIVI-NUOVO]`) → **license gate** (copyleft ⇒ pattern-only rewrite; no-LICENSE ⇒ all-rights-reserved) → maturity check → adapt to organism constraints (PII-local, no paid API) → provenance record. Founding measurement: "~70% già scritto da altri" on the document-intake system.

**Decision capture today (measured locations).** ADR: `docs/ARCHITECTURE_DECISION_RECORDS.md` — format Date/Status/Decision/Context/Rationale/Implementation/Consequences, **Last Updated 2026-02-26**, ≥10 ADRs visible in excerpt (file 13,944 chars, pack truncated near ADR-010 — assume 1–3 more possible, **ASSUMED**). Research dossiers: `research/operations/` listing shows **364 entries**. Memory: `mem save decision (importance 8-10)` is mandatory per `CLAUDE.md` §3 — count **UNMEASURED** (MEM absent from snapshot; command: `ls /Users/nuzantara/.claude/projects/-Users-nuzantara-nuzantara/memory/ | wc -l`). Also `docs/LIVING_ARCHITECTURE.md`: "Auto-generated by The Scribe on 2026-02-02 02:57:08 … Do not edit manually" — a generated atlas, ~7 months stale at panel date. **4-LLM spec pre-approval**: referenced by the lane brief and implied by the missing MEM file `feedback_always_review_spec_with_4_llm.md`; its rule text is not in the pack — **ASSUMED** as practice.

## 2. Scars & ledger evidence in this area

Scar greps were not executable in this lane (no shell; greps not in pack). Evidence below is everything scar/ledger-shaped the pack itself carries:

| Evidence | Source (pack) | What it says about decision-making |
|---|---|---|
| **W62** — GROUND step "killed a phantom feature in 3 tool calls"; cicatrix said fix not shipped, disk said shipped-but-flag-disarmed | `.claude/skills/sota-architecture-loop/SKILL.md` | Designing on memory/stale scars produces ghost architecture; disk-state grounding is a measured fix |
| **W81** — "built is not armed"; PENDING-ARMS ledger; G7 requires a ledger line at organ birth | `CLAUDE.md` (master loop line), `infra/organ-conformance/genes.json` | Completion claims lie; decision state must be visible from minute zero |
| **W111** — `gh run rerun` replays a stale merge ref; blanket rerun prohibition "deadlocked two PRs on 2026-08-21" | `CLAUDE.md` PR contract rule 3 | Rules must carry cause-diagnostics; decision gates that don't distinguish failure causes create deadlocks |
| **W84** — `2026-06-16-W84-tcc-green-dead` cited as cicatrix_ref on `m5.auth_sentinel`, `pro.claude_settings_watcher` | `apps/organism/organism/organs_registry.yaml` | Registry already links organs to wounds (pattern to copy onto decisions) |
| **Superscar families #1, #2, #7, #10** — HOME-fork drift; Esiste≠Armato/green lies; daemon-vs-cron misconfig; active-active split-brain | `infra/organ-conformance/genes.json` `_doc`/`why` fields | Anatomy genes exist *because* these families bit; each gene is a decision encoded |
| **2026-07-06 panel findings** — kill switch must write a `disabled` heartbeat; restart without idempotency "is a cure that wounds" | `genes.json` G5/G10 why | Panels previously corrected healing/decision mechanics |
| **PR #4547** — 1-file hook fix: 14 commits, 11 adversarial rounds, ~6h; 44h session spent 3.9M output tokens; **27 of 200** commits landing 2026-08-20..22 existed only to correct a previous claim | `CLAUDE.md` PR contract rule 8 | Fix-of-fix chains are upstream *decision* failures → rule: "write the spec, do not open the third PR"; three-rounds-then-suspend |
| **drive_poll saturated PG** — disabled 2026-04-29, kept registered with reason | `organs_registry.yaml` | Good: decision + rationale recorded in the live registry |
| **Case-code dossier** — adversarial pass killed naive design twice; withdrew a declared deviation as false dilemma | `research/design/2026-08-28-case-code-design.md` | Cross-family adversarial review measurably changes structural outcomes |

**UNMEASURED (requested by brief):** councils convened against the anti-sperpero gate — `grep -n "council" .claude/skills/modus/AMENDMENTS.md | head -30`; council/groupthink scar lines — `grep -n "council\|groupthink\|blind agreement\|W65\|W100" .claude/rules/cicatrix-superscar.md .claude/rules/cicatrix-scars.md | head -40`. Both greps unavailable in this lane.

## 3. World SOTA survey

*Caveat: this lane had NO web access (no ToolSearch/WebFetch). Sources below are cited from model knowledge with dates; URLs I am not confident in are marked `(unverified)`. None were fetched this session.*

| # | System / practice | Source | Mechanism | Measured effect | Transferability here |
|---|---|---|---|---|---|
| 1 | ADRs (Nygard, 2011-11-15) | cognitect.com/blog/2011/11/15/documenting-architecture-decisions | Short immutable records; status lifecycle; explicit supersession | Qualitative; industry default | Direct — revives our frozen ADR file |
| 2 | MADR (adr.github.io, ongoing) | adr.github.io/madr/ | Decision *log* template: options considered + rejection reasons, YAML frontmatter | Qualitative | Template for R1's machine-readable ADRs |
| 3 | C4 + Structurizr (Brown, 2018→) | c4model.com · structurizr.com | Architecture-as-code model; diagrams regenerated from model | Qualitative | Pairs with our `docs_sync`/LIVING_ARCHITECTURE regen |
| 4 | Rust RFCs (2014→) | rust-lang.github.io/rfcs/ | Written prior-art, unresolved questions, drawbacks, final-comment-period | Qualitative (project velocity) | Panel dossiers ≈ RFCs; add prior-art/drawbacks fields |
| 5 | Google design docs (Ubl, 2023-07) | industrialempathy.com/posts/design-docs-at-google/ | Doc as parallel artifact; early alternatives review; feedback before code | Qualitative | We already do dossiers; missing lifecycle + outcomes |
| 6 | Amazon Type 1/Type 2 doors (Bezos 2015 letter) | aboutamazon.com/news/company-news/2015-letter-to-shareholders `(unverified)` | Classify decisions by reversibility; speed for two-way | Qualitative | One field added to DECISION step |
| 7 | PR/FAQ / Working Backwards (Bryar & Carr, 2021) | workingbackwards.com | Write the press release first | Qualitative | ASSEMBLY-LINE's contract-first already covers most |
| 8 | Fitness functions / evolutionary architecture (Ford, Parsons, Kua, 2017) | thoughtworks.com/en-us/insights/books/building-evolutionary-architectures | Objective functions over architecture characteristics, run continuously | Case-study qualitative | Direct: our genes.json is one; generalize to decisions |
| 9 | Team Topologies (Skelton & Pais, 2019) | teamtopologies.com | Conway's law; cognitive load as first-class design constraint | Qualitative | Maps onto organs/lanes; lower priority |
| 10 | AWS Well-Architected reviews (2015→) | docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html | Pillar questionnaires + periodic structured review | Qualitative risk reduction | Cadence idea for quarterly decision audits |
| 11 | Pre-mortem (Klein, HBR 2007-09) | hbr.org/2007/09/performing-a-project-premortem `(unverified)` | Prospective hindsight | ~30% better identification of future-outcome reasons (Russo & Schoemaker, as cited) | Cheap; scar-conditioned variant is novel (R5) |
| 12 | *Noise* — decision hygiene (Kahneman/Sibony/Sunstein, 2021) | book | Independent judgments before aggregation; structured process | Qualitative | Council already separates roles; add independent-first verdicts |
| 13 | Multi-agent debate (Du et al., 2023-05) | arxiv.org/abs/2305.14325 | Debate rounds improve factuality/reasoning vs single model | Benchmark gains vs single agent | We apply it heterogeneously, unlike most setups |
| 14 | Persuasive debate (Khan et al., 2023/24) | arxiv.org/abs/2305.14763 | Accuracy rises with argument persuasiveness — and judges are swayable | Accuracy gains over direct answering | Justifies red-team incentive prompts; warns of persuasion bias |
| 15 | Mixture-of-Agents (Wang et al., 2024-06) | arxiv.org/abs/2406.04692 | Layered proposer/aggregator ensembles | Open-model MoA beat GPT-4o on AlpacaEval 2.0 | Aggregation pattern for panel synthesis |
| 16 | Anthropic multi-agent research system (2025-06) | anthropic.com/engineering/built-multi-agent-research-system `(unverified)` | Orchestrator-worker breadth; parallel subagents | ~90.2% improvement vs single-agent on internal research eval; ~15× token cost for multi-agent | Our 15× council cost model cites exactly this |
| 17 | MAST — Why Multi-Agent LLM Systems Fail (Mastroianni et al., 2025-03) | arxiv.org/abs/2503.13657 | 14-mode failure taxonomy (specification / inter-agent misalignment / verification) over 7 frameworks | Taxonomy over ~200 incidents | Checklist schema for council telemetry (R4) |
| 18 | LLM-as-judge bias / MT-Bench (Zheng et al., 2023-06) | arxiv.org/abs/2306.05685 | Judges agree with humans ~80% but show position/verbosity/self-enhancement bias | Biases quantified | Warns our Opus final on-disk gate; rotate judge position |

**Prose — the five that matter most.**
**(a) ADR/MADR lifecycle.** Nygard's insight is that the *status field and supersession chain* are the technology, not the prose. Our ADR file has the prose format but zero lifecycle motion since 2026-02-26, while 364 research dossiers pile up unlinked. MADR's "options considered + why rejected" is precisely what the case-code dossier did narratively (killed designs recorded) — the gap is machine-readable capture.
**(b) Fitness functions.** Ford et al. argue architecture properties must be *tested*, not asserted. Nobody in the survey mechanizes this with a grandfathered baseline whose shrinkage is the cure metric — we already do, for organs (`genes.json`). The transfer is to lift the pattern to structural invariants.
**(c) Multi-agent debate research.** Du/Khan/MoA validate heterogeneous debate; MAST documents how such systems fail (sycophancy, verification gaps); MT-Bench documents judge bias. Our `sota-architecture-loop` encodes the literature's conclusions (heterogeneity, capped rounds, incentive-inverted roles, empirical closure) more completely than any published system description I know — but it cites *external* conformity numbers (85.5%/70% on 7–8B). The organism has never measured its own councils.
**(d) Design docs + one-way doors.** Google's practice and Bezos's reversibility split both reduce ceremony where reversibility is high. Our council gate already encodes this ("se rollback è gratis → non serve") but doesn't *record* the door class, so we can't audit whether councils were spent on one-way doors or wasted on two-way ones.
**(e) Formal methods (TLA+/Alloy).** AWS's CACM account (Newcombe et al. 2015, `dl.acm.org/doi/10.1145/2699417` `(unverified)`) shows model-checking pays on exactly the one-way doors (storage, consistency). No pack evidence of TLA+/Alloy here — **ASSUMED absent**. For a CLI-only flat-subscription organism, targeted Alloy models of migration/counter logic (the case-code one-clock rollover is a perfect candidate) are cheap and unexploited.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Decision triage & ceremony sizing | **AHEAD** | Gear 1/2/3 + anti-sperpero gate (`modus` SKILL); floor `harness-floor.yml` + ceiling `compute_ceiling()` (`scripts/evidence_pack_lint.py`, PR #4474). No surveyed system mechanizes ceremony size; Google/Rust cultures apply uniform ceremony |
| Grounding before reasoning | **AHEAD** | STEP 1 GROUND with disk-state-as-truth; W62 killed a phantom feature in 3 tool calls (`sota-architecture-loop/SKILL.md`). Design-doc cultures assume author knowledge; none enforces a ground step |
| Council composition & anti-consensus | **AHEAD in design / AT in measurement** | Heterogeneous role+incentive asymmetry, 3 panelists, capped rounds, consensus banned, proposer≠judge (`sota-architecture-loop`); but conformity numbers are cited from external 7–8B studies — own councils unmeasured |
| Decision gates (falsifiability) | **AT** | Doctrine strong: DECISION = "go/no-go/defer + 1 metrica falsificabile" + SYMBIOSIS L7; enforcement weak: nothing lints that a captured decision carries a metric |
| Decision recording & lifecycle | **BEHIND** | `docs/ARCHITECTURE_DECISION_RECORDS.md` Last Updated 2026-02-26, ≥10 ADRs; vs 364 files in `research/operations/`; no status transitions, no supersession links, no outcome field |
| Living anatomy (organs + genes) | **AHEAD** | `organs_registry.yaml` (recovery_action, severity_on_silence, cicatrix_refs, disabled_reason) + `genes.json` 10-gene CI conformance with shrinking-baseline cure metric; nothing comparable in the survey |
| Architecture documentation freshness | **BEHIND** | `LIVING_ARCHITECTURE.md` auto-generated 2026-02-02 and stale ~209 days at panel date; `INDEX.md` manual revision 2026-07-02; the regen machinery exists (`docs_sync.py`, `docs-inventory-refresh.yml` per INDEX) but cadence is broken |
| Reuse-first / build-vs-buy | **AHEAD (for a solo organism)** | 7-step procedure with hard license gate + provenance (`reuse-first/SKILL.md`); SOTA equivalent is platform teams, not an executable per-brick protocol |
| Revisit & supersession discipline | **BEHIND** | No fitness functions over decisions; no scheduled revisit; ADR/LIVING_ARCHITECTURE staleness is the symptom; scars capture failures but old decisions are never re-audited |
| Formal verification at one-way doors | **BEHIND (ASSUMED absent)** | No TLA+/Alloy evidence in pack; migrations get Codex sandbox testing (federation triggers) — empirical, not model-based |

## 5. Beyond-SOTA recommendations

Ranked by (impact × confidence) / cost. All respect hard constraints (CLI-only, no paid Anthropic API, PII output boundary, Fable not auto-routed, flat subscriptions).

**R1 — Decision genome: linted ADR graph with outcomes and supersession.** *(biggest gap, highest leverage)*
- **What:** `docs/adr/` one file per structural decision, MADR-derived frontmatter: `id, date, status, door: one-way|two-way, gear, council_seats (families), metric, metric_target, supersedes, superseded_by, outcome_due, cicatrix_refs`. CI lint (new `scripts/adr_lint.py`) fails on dangling links, missing metric on one-way doors, and Gear-3 research reports lacking an `adr:` key; monthly decay report lists decisions past `outcome_due` with no recorded outcome.
- **Why it beats SOTA:** Nygard/MADR give format, not enforcement; no surveyed system links decisions to scars or scores outcomes. We transfer the `organs_registry.yaml` `cicatrix_refs` pattern onto decisions.
- **Cost:** ~2 flat-sub sessions + backfill tokens (top-20 decisions from `research/operations/`). **Gear:** 2.
- **Risk + scar family:** ledger bloat (PENDING-ARMS is 2.2 MB — size-budget it); fake outcomes would be family **#2** (Esiste≠Armato) — mitigated by requiring evidence links in outcome entries.
- **Metric:** before: 0 ADRs written since 2026-02-26; % decisions with outcome at 30d **UNMEASURED** (baseline: `grep -c "^## ADR-" docs/ARCHITECTURE_DECISION_RECORDS.md` + new-dir count, then weekly tally). After: ≥1 ADR/week on Gear-3 lanes; ≥60% outcomes recorded by `outcome_due`.
- **Kill criterion:** 4 consecutive weeks of lint waivers, or >1h author overhead per ADR.
- **First PR:** see §6 PR-A.

**R2 — Regenerate the living architecture weekly; badge staleness.**
- **What:** put `docs-inventory-refresh.yml` (name per `INDEX.md` artifact reference — **ASSUMED** exact file) and the LIVING_ARCHITECTURE regeneration on a weekly cron; stamp "generated-at" + staleness badge in `INDEX.md`; extend output with a decision census from R1 frontmatter.
- **Why it beats SOTA:** Structurizr regenerates diagrams on demand; we regenerate atlas + organ census + decision census as one linked artifact with scar refs — no surveyed org does.
- **Cost:** 1 session. **Gear:** 1–2.
- **Risk:** rerun/stale-ref traps adjacent to W111 (`CLAUDE.md` rule 3) — use `workflow_dispatch` correctly; **scar family #2** if the badge lies about freshness.
- **Metric:** before: LIVING_ARCHITECTURE 209 days stale, INDEX 57 days; after: ≤7 days.
- **Kill criterion:** two consecutive broken regenerations → revert to manual with an explicit staleness badge.
- **First PR:** see §6 PR-B.

**R3 — Architecture genes: organ-conformance pattern lifted to structural invariants.**
- **What:** `infra/arch-conformance/genes.json` v1, consumed by a checker+generator pair (mirroring `genes.json` `_doc`: "gate and generator can never diverge"), seed genes: **A1_pii_boundary** (PII paths must route through the `privacy_preflight` chokepoint pattern seen in `scripts/federation_orchestrator.py`), **A2_reversible_migration** (each migration declares down-path or explicit one-way door), **A3_decision_metric** (Gear-3 artifacts carry a falsifiable metric — R1 lint's cousin), **A4_registry_at_birth** for new organs/apps. Grandfathered baseline; "shrinking the baseline is the cure metric."
- **Why it beats SOTA:** fitness functions are advocated (Ford et al.) but rarely mechanized with baseline+regression semantics; we proved that exact mechanism in `infra/organ-conformance` — the composition is novel.
- **Cost:** 2–3 sessions. **Gear:** 3 (architecture).
- **Risk:** false-positive gate spawning fix-of-fix chains (the PR #4547 pattern; `CLAUDE.md` rule 8 three-round-suspend is the backstop); scar family **#2** if genes pass while behavior violates.
- **Metric:** invariant regressions/month (baseline **UNMEASURED** — set at adoption; command: checker run count on `main`); grandfathered count → 0.
- **Kill criterion:** >3 waivers in the first month.
- **First PR:** see §6 PR-C.

**R4 — Council telemetry: measure our own conformity instead of citing 7–8B numbers.**
- **What:** every convened council emits one structured JSONL row (`research/operations/council-ledger.jsonl`): which of the three gate conditions fired, seat families, round count, dissent count, red-team findings, findings that **changed the outcome**, unanimous-approval flag. Monthly aggregate; target bands: outcome-change rate 30–70% (below = theater, above = broken proposer), unanimous approvals <20%.
- **Why it beats SOTA:** MAST catalogs failure modes; nobody longitudinally measures their own councils. Asymmetry exploited: we already keep ledgers (PENDING-ARMS, AMENDMENTS) — the habit and tooling exist.
- **Cost:** ~zero per council (one structured block). **Gear:** 2.
- **Risk:** performative recording — family **#2** green lies; mitigate by having TRIAGE *read* the ledger (gear re-classification cites it).
- **Metric:** baseline month → outcome-change rate + unanimity rate; also councils-convened-against-gate (today **UNMEASURED**: `grep -n "council" .claude/skills/modus/AMENDMENTS.md | head -30`) → 0.
- **Kill criterion:** ledger unread by TRIAGE after 2 months.

**R5 — Scar-conditioned pre-mortems at Gear-3 FRAME.**
- **What:** auto-generate the pre-mortem from the superscar corpus + matching `cicatrix_refs`: "assume this decision failed in 6 months — which scar family was it?" Record predictions in the ADR (R1); score calibration at `outcome_due`.
- **Why it beats SOTA:** Klein's pre-mortem is generic; conditioning on a 296 KB+ measured-failure corpus is something no surveyed system can do — only we have the corpus.
- **Cost:** 1–2 sessions + modest per-Gear-3 tokens. **Gear:** 2–3.
- **Risk:** ritualism (scar families **#2/#3-style** ceremony without effect — family numbering beyond pack citations **ASSUMED**).
- **Metric:** superscar-family recurrence in new Gear-3 work (baseline from AMENDMENTS — **UNMEASURED**, command above): target −50% in 90 days; pre-mortem calibration = realized failures that were predicted.
- **Kill criterion:** calibration untracked for a quarter.

## 6. 90-day roadmap + first PRs

**Wave 1 (days 1–30): make decisions visible.** PR-A (ADR template + lint) and PR-B (weekly living-docs regen); backfill the 20 most-referenced decisions from `research/operations/` as ADRs with status. *Gate:* LIVING_ARCHITECTURE staleness ≤7 days; ≥10 new ADRs; lint green.
**Wave 2 (days 31–60): make invariants enforceable.** PR-C (arch genes A1–A3 with grandfathered baseline) and PR-D (council ledger schema + first monthly aggregate; wire ledger read into modus TRIAGE). *Gate:* genes green on 20 consecutive PRs; first council-telemetry month published.
**Wave 3 (days 61–90): make decisions accountable.** PR-E (scar-conditioned pre-mortem block in Gear-3 FRAME); first quarterly decision audit: `outcome_due` report + supersession sweep, retire/supersede ≥5 stale decisions; optional Alloy model of the case-code counter (one-clock rollover) as the first formal-method pilot. *Gate:* ≥60% of due decisions have recorded outcomes; superscar recurrence −25% vs baseline.

| First PR | Files | Net lines | Gear | Acceptance test |
|---|---|---|---|---|
| **PR-A** `adr: MADR template + adr_lint + CI hook` | `docs/adr/TEMPLATE.md`, `docs/adr/README.md`, `scripts/adr_lint.py`, one workflow edit | ≤300 | 2 | lint fails a fixture ADR with dangling `supersedes` and one missing metric on a one-way door; passes the backfilled ADR-011 |
| **PR-B** `docs: weekly living-architecture regen + staleness badge` | `infra/workflows/docs-inventory-refresh.yml` (**ASSUMED** name), `scripts/docs_sync.py` (badge flag), `INDEX.md` header | ≤150 | 1 | regenerated artifact carries generated-at ≤7 days old after cron fires |
| **PR-C** `arch-conformance: genes A1–A3 + baseline` | `infra/arch-conformance/genes.json`, `infra/arch-conformance/check_arch_conformance.py`, CI gate wiring | ≤400 | 3 | checker FAILs a fixture PR missing a migration down-declaration; grandfathered baseline lists current violators, shrinks-only policy documented |
| **PR-D** `council: telemetry ledger + monthly aggregate` | `scripts/council_ledger.py`, `research/operations/council-ledger.jsonl` (seed), modus SKILL pointer edit | ≤250 | 2 | emitting a council row and running the aggregator prints outcome-change rate + unanimity rate |
| **PR-E** `modus: scar-conditioned pre-mortem at Gear-3 FRAME` | `.claude/skills/modus/SKILL.md` (FRAME block), `.claude/scripts/premortem_from_scars.py` | ≤300 | 2 | running on a fixture mandate prints ≥3 scar-family hypotheses with corpus citations |

## 7. Needs-ruling

1. **Public visibility of decision records** (`needs-ruling`, Legge 5): ADRs/decisions will live in the public repo (the stated forcing function). Law 2 already bans PII in outputs, but decisions can carry *business* sensitivity beyond PII (pricing logic, kill criteria, product strategy). Zero decides whether decision corpus is public-verbatim, public-redacted, or private-with-public-hashes.
2. **Outcome authority on product decisions** (`needs-ruling`): R1 scores outcomes mechanically; for ASSEMBLY-LINE-governed product decisions (GARUDA VOA class), outcome judgment against business invariants remains Zero's — confirm the ledger marks those `outcome_by: operator[business]`.

## 8. §Meta-pattern

**Organs have a genome; decisions do not.** Every finding repeats one defective belief: *a good decision is a document written, not an organ kept alive.* The organism applies full lifecycle discipline to organs — registry entry at birth (G1), self-proven liveness (G2 heartbeat), kill switch (G5), ledger line at birth (G7), conformance genes with a shrinking grandfathered baseline, recovery actions, cicatrix refs — and applies none of it to decisions: no birth registry (decisions scatter across ADR file, 364 research dossiers, `mem save`, and registry notes), no heartbeat (metrics are declared at DECISION but never re-measured), no kill switch (no supersession mechanics — the ADR file froze on 2026-02-26 and nothing noticed for six months), no conformance gate (nothing fails when a decision lacks options-considered or outcomes). Even the grounding discipline is asymmetric: W62 taught *verify disk state before designing*, yet we never re-verify **decision state** before building on it — LIVING_ARCHITECTURE lay dead since 2026-02-02 while sessions designed on top of it. The fix is not a new document format; it is to treat each decision as an organ: born registered, heartbeating against its metric, killable by supersession, gene-checked at CI, scar-linked when it bites.

## 9. Sources

1. Nygard, *Documenting Architecture Decisions* — https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions — 2011-11-15 (accessed from knowledge 2026-08-28) — origin of ADR status/supersession lifecycle.
2. MADR — https://adr.github.io/madr/ — maintained 2023–2026 — machine-readable decision-log template with options/rejections.
3. C4 model / Structurizr — https://c4model.com/ · https://structurizr.com/ — 2018→ — architecture-as-code, regenerable views.
4. Rust RFC process — https://rust-lang.github.io/rfcs/ — 2014→ — prior-art/drawbacks/FCP discipline for written decisions.
5. Ubl, *Design Docs at Google* — https://www.industrialempathy.com/posts/design-docs-at-google/ — 2023-07 — design doc as parallel artifact with early alternatives review.
6. Bezos 2015 shareholder letter (Type 1/Type 2 doors) — https://www.aboutamazon.com/news/company-news/2015-letter-to-shareholders `(unverified)` — 2016 — reversibility-based decision speed.
7. Working Backwards / PR-FAQ — https://workingbackwards.com/ — 2021 — outcome-first specification.
8. Ford, Parsons, Kua, *Building Evolutionary Architectures* — https://www.thoughtworks.com/en-us/insights/books/building-evolutionary-architectures — 2017 — architectural fitness functions.
9. Skelton & Pais, *Team Topologies* — https://teamtopologies.com/ — 2019 — cognitive load & Conway-aware structure design.
10. AWS Well-Architected Framework — https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html — 2015→ — periodic structured architecture review.
11. Klein, *Performing a Project Premortem* — https://hbr.org/2007/09/performing-a-project-premortem `(unverified)` — HBR 2007-09 — prospective hindsight technique.
12. Kahneman, Sibony, Sunstein, *Noise* — 2021 (book) — decision hygiene, independent judgment before aggregation.
13. Du et al., *Improving Factuality and Reasoning through Multiagent Debate* — https://arxiv.org/abs/2305.14325 — 2023-05 — debate > single-model accuracy.
14. Khan et al., *Debating with More Persuasive LLMs Leads to More Accurate Answers* — https://arxiv.org/abs/2305.14763 — 2023/24 — persuasiveness drives accuracy; judge swayability.
15. Wang et al., *Mixture-of-Agents Enhances Large Language Model Capabilities* — https://arxiv.org/abs/2406.04692 — 2024-06 — layered aggregation surpasses frontier single models on AlpacaEval 2.0.
16. Anthropic Engineering, *How we built our multi-agent research system* — https://www.anthropic.com/engineering/built-multi-agent-research-system `(unverified)` — 2025-06 — ~90.2% improvement vs single agent; ~15× token cost (the number our council gate cites).
17. Mastroianni et al., *Why Do Multi-Agent LLM Systems Fail?* (MAST) — https://arxiv.org/abs/2503.13657 — 2025-03 — 14-mode failure taxonomy; telemetry schema basis.
18. Zheng et al., *Judging LLM-as-a-Judge* (MT-Bench) — https://arxiv.org/abs/2306.05685 — 2023-06 — judge agreement ~80% with quantified position/verbosity/self-enhancement biases.

*(Additional reference cited in prose: Newcombe et al., "How Amazon Web Services Uses Formal Methods," CACM 2015 — https://dl.acm.org/doi/10.1145/2699417 `(unverified)`.)*