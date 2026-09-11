---
panel: beyond-sota-xfamily
lane: 01-intake-triage-specification
seat: tp1-qwen3.8-max
model: "qwen3.8-max · enable_thinking · TP1 API, no tools, ground pack"
started: 2026-08-28T16:39:51Z
finished: 2026-08-28T16:47:58Z
duration_s: 487
exit: 0
words: 5513
prompt_sha256_16: cfa53d2c9506feda
prompt_chars: 169778
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 1/13 — Intake, triage & specification
model: Qwen3.8 Max (pinned lane)
sources: 14
repo_files_verified: 19 (via the lane's redacted GROUND PACK — this lane is API-only with no shell/file access; every pack excerpt below was read in-session; paths omitted from the pack by the cap are marked ASSUMED/UNMEASURED)
status: complete
sections_done: [0,1,2,3,4,5,6,7,8,9]
---

_Execution note: the protocol's "write the file, then `ls -la` + `wc -w`" probe is not executable in this lane (no tools). Per lane instructions the deliverable is this message. MEM: references are unavailable — `MEMORY_METHOD_LESSONS.md` was NOT FOUND in the snapshot and the memory bodies under `~/.claude/projects/…/memory/` are not in the pack; all memory-corpus queries below are UNMEASURED with the exact command I would run._

---

## 0. TL;DR

Position: Nuzantara's intake is **AT or AHEAD of world SOTA on deterministic gear triage, grounding-before-building, and gate-consumed spec artifacts; BEHIND on measuring its own intake** (triage misfire rate, fix-of-fix chains, assumption contradictions are all UNMEASURED today).
Biggest gap: intake-time *declarations* (gear, assumptions, acceptance criteria, ambiguity) are prose, while output-time evidence is receipts — the organism built a verification machine for outputs and left the front door verbal.
Top-3 moves:
1. **Triage ledger with CI-computed misfire rate** — close the loop between STAGE 0's provisional gear and the CI-recomputed floor.
2. **`spec_lint.py` — a falsifiability gate at intake** (T-GATE): acceptance criteria must be executable-shaped and cite paths that exist; assumptions must be declared artifacts (anti-superscar-#6).
3. **Settling receipt + ambiguity probe** — codify the GARUDA refuter-on-live-writer scar as a pack field; turn the language protocol's "infer, state the assumption" into a gate-consumed `assumptions:` block.

---

## 1. How Nuzantara does it today

Every claim below is grounded in the GROUND PACK. Files omitted by the pack cap are flagged.

**1.1 STAGE 0 TRIAGE — gear as a falsifiable provisional.** `.claude/skills/modus/SKILL.md` (65,902 chars; pack shows STAGE 0 + stage table header) classifies every non-trivial mandate into **Gear 1 liscio / 2 standard / 3 profondo**, announced in one line: `GEAR <n>: <mandate> — <why this gear>`. The gear is explicitly "falsifiable, not a vow — blast-radius is often unknowable before reading, and under-gearing tasks that merely look small is the systematic failure mode"; GROUND confirms or RE-GEARS. Gears bind effort (`medium` for G1, `xhigh` for G2, `xhigh` default for G3 with `max` opt-in only on declared adjudication) and ceremony (G3 adds Workflow-tool orchestration, TAC patterns, mandatory §Meta-pattern section).

**1.2 Budget as router (anti-sperpero).** Same file: council only if divergent priors ∧ error costs >15× tokens ∧ genuinely parallel breadth; fan-out only ≥3 independent items; "fan-out for READS, funnel-in for WRITES"; cache-aware waiting (≤270s or ≥1200s, never ~300s); stop-loss budget shape declared up front at Gear 3; "Escalate gear mid-flight if the terrain grows (RECONCILE); NEVER de-escalate silently."

**1.3 Deterministic gear floor AND ceiling in CI.** This is the organism's most distinctive intake mechanism:
- `scripts/evidence_pack_lint.py` (121,859 chars) rule 6: declared `gear >= floor`, where the floor is "the DETERMINISTIC FLOOR computed from the diff … never the conductor's choice." Path signal: hot-zone path → floor 3; everything else → floor 1 (path alone never asserts 2); size term S1 (2026-08-27) — a diff past the ~400-net-line PR target asserts floor 2 even on cold paths. Gear must be a genuine int (bool/float tricks rejected — adversarial-review finding 2026-08-10).
- Rule 7 (`compute_ceiling()`): a docs/ledger-only diff, or ≤2 files / ≤60 net lines outside hot zones, may NOT declare Gear 3 with a council or ≥3 grader dispatches unless `gear_override:` carries a reason (then NOTICE, not fail). "Floor always wins when the two conflict."
- `.github/workflows/harness-floor.yml` (67,971 chars — doctrine sedimented into YAML): floor computed once, unconditionally; a hot-zone diff with no `evidence/brief.yml` FAILS outright (adversarial finding 2026-08-10 closed the "no brief → default success" hole); sentinel pattern makes it a safe required check; the 2026-08-21 redesign documents the synthetic-SHA relay fix and CASE A/B rerun discipline.

**1.4 STADIO-0 — the entry gate.** `.claude/commands/stadio-zero.md`: before the first Edit/Write of any non-trivial task, four falsifiable sections: (1) **Memory-hits** (`mem query` if present, else the versioned scar corpus via grep); (2) **Hot-files VERIFICATI on disk** — "Mai fidarsi di un path citato" — every cited file:line re-checked with `ls`/`sed -n`/`grep`, citing the scar "autopsy phantom file:line: 3 file:line allucinati con precisione che _leggeva_ come ground-truth"; (3) **PII-risk scope** under Law 2 — "Scope-vuoto è una risposta valida, ma va detta, non assunta"; (4) **Criteri-accettazione FALSIFICABILI** — binary/objective (✅ "exit 0 di `pytest <file>`"; ❌ "il codice è pulito"); "Se non riesci a scrivere un criterio falsificabile, il task è mal-formato → riformulalo finché lo è." Skip only for true one-liners, declared in one line. The output is a chat block, not a file — "un file vuoto creato per sbloccare è reward-hacking, non studio."

**1.5 Phase-aware hooks that nudge/enforce grounding.** `infra/claude-hooks/` (49 entries):
- `stadio_zero_nudge.py`: PreToolUse soft nudge, fires once per young session (<400 lines) on first Edit/Write/MultiEdit when no STUDY marker is present. Deliberately never blocks: "a blocking gate on a judgment act invites empty STUDYs to unblock (reward-hacking, the exact failure P1 warns about)."
- `premise_gate.py`: the brain's L1 detector of the malattia-madre "green != working" — warns when an Edit touches a product file with zero in-turn read of that file (anti-hallucination rule #2 made mechanical). Warn-only, product files only, one warn per file per session, scope narrowed by "the W83/84/85/86 lesson."
- `orchestrate_gate.py`: the one HARD gate in this area — blocks Bash/Edit/Write when transcript >800 lines with zero subagent dispatch in the last 300 lines; carries DISARM AUDIBILITY ("a disarmed gate is mute", 2026-08-12), subagent exemption, and a transcript-shape guard: "cannot-verify is not a verdict" (W106b).
- `_phase.py`: plan-phase detection; fail-safe to False (guardrails STAY ON); kill switch + manual escape; host-boundary protected.
- `session_budget.py`: visibility only ("Deliberately NO real budget enforcement"), artifact-on-death handoff — intake continuity across dead sessions.

**1.6 ASSEMBLY-LINE — the 5-artifact product spec.** `docs/factory/ASSEMBLY-LINE.md` (RULED 2026-08-24): the inversion "**An artifact exists only if a gate consumes it**"; unit of done = "a customer journey working in production, meeting its SLO, producing its business outcome"; 5 permanent artifacts (`product.yaml` with kill criterion + ≤3 guardrails; `journeys/`; `contracts/`; code+tests; `ops/`); 8 stages G0–G7. Spec-critical gates: **G0 (owner)** — specific user, falsifiable metric, kill criterion; **G2** — journey/state-machine specs written BEFORE code, by a different family than the builder, "specs fail RED cleanly against empty endpoints; every sad path … is named and test-owned"; **G3** — contract FREEZE. Deliberately NOT adopted: sprints, story points, PRD/design-doc chains, narrative retros, human code review.

**1.7 The MANDATE.md pattern.** Two exemplars in the pack:
- `docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`: owner-framed product, `product.yaml` seed, **owner switchboard** (6 decisions, each with prepared proposal + owner gesture; "NOTHING blocks on these — build dark, collect signatures at the end"), 7 lanes with disjoint file scopes and per-lane builder+refuter, contracts to freeze, journey specs list, gates tightened per-product, constraints carried from scars (verified 2026-08-24), definition of done = full self-purchase journey in prod behind a flag.
- `docs/mandates/2026-08-22-arsenal-routing-mandate.md`: ground-truth table measured from transcripts (Sonnet 355 build-shaped dispatches vs ~7 non-Anthropic builds), hard non-goals, 4 deliverables each with CLI contract, tests (guilt+innocence), and acceptance; honesty clause: "What this buys (be honest in the report) … not fewer tokens."

**1.8 karpathy-discipline.** `.claude/skills/karpathy-discipline/SKILL.md` (vendored, canonical): Think Before Coding (state assumptions; don't pick silently), Simplicity First, Surgical Changes, Goal-Driven Execution ("weak criteria ('make it work') require constant clarification").

**1.9 Rules-as-harness tiers.** `docs/specs/rules-as-harness-and-simulation-chamber-v1.md`: T-BLOCK / T-GATE / T-NUDGE; "a new rule ships ONLY as the weakest tier that still bites (W83-W85 lesson)"; every T-BLOCK needs guilt AND innocence tests + Lab dry-run; every rule has a kill switch; rules fire on thresholds. This is the intake system's own constitution for adding intake rules.

**1.10 Brief + Evidence Pack as the gear-3 spec envelope.** `evidence/brief.yml` (real example, PR #5059): `gear: 3`, `l_level: L2`, `gate_class: opus`, objective, constraints ("Fix the FAMILY, not the instance"), acceptance (falsifiable), `consumer_map` (every consumer cited with path:line, "Verified, not assumed"), risks, grader (generator≠grader named). `evidence/pack.yml`: lanes with seats, receipts `{claim, cmd, result, exit, ts, seat}`, mandatory non-empty `dissent` at Gear 3, `pii_scan: clean`, ≤30k-token cap on raw bytes. Lint rules 1–9 in `scripts/evidence_pack_lint.py`, including phased NOTICE→FAIL flips with the date **in code** (2026-08-24 lanes rule; 2026-09-02 seat-rules date) and `gear_override:`/`seat_override:` escapes that are reported, never silent.

**1.11 Rule 8, language protocol, preflight levels.** CLAUDE.md is omitted from the pack; from cross-references I can support: rule 8 suspension semantics ("three reds same cause → suspend (rule 8)", `docs/plans/2026-08-24-garuda-voa-live/MANDATE.md` §5; "regola 8 attiva" in the arsenal mandate header). The "fix-of-fix depth 1 → write the spec" clause and CLAUDE.md §4 language protocol ("never ask 'what do you mean' — infer + state the assumption") come from the lane brief; exact wording **ASSUMED**. Preflight autonomy levels: `AUTONOMOUS_OPS.md` omitted, but `l_level: L2` + `gate_class: opus` in `evidence/brief.yml` is direct evidence L-levels are live fields.

---

## 2. Scars & ledger evidence in this area

What actually bit, from pack-verifiable citations:

| Evidence | Where verified | Intake lesson |
|---|---|---|
| Superscar #6 "phantom file:line" — 3 hallucinated file:line "che leggeva come ground-truth" | `.claude/commands/stadio-zero.md` (cicatrix-superscar.md itself omitted by cap — the corpus exists per cross-ref; full grep UNMEASURED) | Why STADIO-0 exists: a plan built on a nonexistent file:line costs six downstream pieces |
| Wrong scar propagation: W111's hazard was narrated onto the wrong event type and "propagated … into a header every session reads" (superscar #6 / W78) | `.github/workflows/harness-floor.yml` header | Scars are intake inputs; an unverified scar is a poisoned spec |
| A disarmed gate is mute: ~6,400-line session, zero dispatch, never blocked — `ORCHESTRATE_GATE_OFF=1` inherited, written in no file (lesson `lesson_a_disarmed_gate_is_mute_2026_08_12`, cicatrix family #2) | `infra/claude-hooks/orchestrate_gate.py` docstring | Gates decay silently; intake must make disarm states auditable |
| Over-eager guard: W83/84/85/86 "three consecutive over-matches from ONE over-eager guard" | `infra/claude-hooks/premise_gate.py`; `docs/specs/rules-as-harness-and-simulation-chamber-v1.md` | New intake rules must start at weakest tier with guilt+innocence |
| Reward-hacking of entry gates (P1): empty STUDY / token Read to unblock | `stadio_zero_nudge.py`, `premise_gate.py` docstrings | Blocking judgment acts corrupts the spec artifact itself |
| Cannot-verify is not a verdict (W106b); never a two-dot diff (W102) | `orchestrate_gate.py`, `scripts/evidence_pack_lint.py` | Intake classifiers must distinguish "unproven" from "false" |
| Doc-only merge rot: **39/100 last merged PRs touched no product**; panel had been briefed "56%" which "nothing in this repo reproduces" | `docs/factory/ASSEMBLY-LINE.md` (with the reproducible `gh` query) | Artifacts without consumers = intake that produced spec-shaped noise; also: doctrine citing non-re-derivable numbers is itself an intake failure |
| Refuter over a live writer: contract hash changed twice under the reviewer; 3 findings stale; independently re-hit by the Visa Oracle lane the same day → "property of the process" | `docs/factory/ASSEMBLY-LINE.md` §Verification economics | Artifact settling is a spec-gate precondition, not etiquette |
| Prose floors are ignored: routing doctrine "unmeasured, unfollowed (7 vs 355)" | `docs/mandates/2026-08-22-arsenal-routing-mandate.md` §1 | An intake rule that never becomes mechanism has a measured compliance of ~2% |
| Dissent that worked: a refuter subagent "killed the timeline claim" | `evidence/brief.yml` grader field; `evidence/pack.yml` dissent | The intake envelope's dissent field is not theater on this PR |

**UNMEASURED (pack cap / no shell) — exact commands I would run:**
- AMENDMENTS triage/gear misfire share: `grep -n "^## " .claude/skills/modus/AMENDMENTS.md | wc -l` (total) and `grep -n "^## " .claude/skills/modus/AMENDMENTS.md | grep -icE "gear|triage|under-gear|spec|mandate"` (misfire-shaped). AMENDMENTS.md was omitted from the pack.
- PENDING-ARMS intake-related suspensions: `grep -n "^## " .claude/skills/modus/PENDING-ARMS.md | grep -icE "gear|triage|spec|mandate|stadio"` (2.2 MB file — grep only). Not in pack.
- Fix-of-fix chains, last 14 days: `gh pr list --state merged --limit 200 --json number,title,mergedAt`; heuristic: title matches `fix|cure|ripara|regression` AND references a merged PR number ≤14 days older whose diff overlaps the same paths (`gh pr view <n> --json files`); chain = depth ≥1.
- Gear-3 packs carrying `gear_override`: `git log -S gear_override --oneline -- evidence/pack.yml | wc -l` vs `git log -S "gear: 3" --oneline -- evidence/brief.yml | wc -l`.
- Memory corpus: `grep -il "gear\|triage\|acceptance\|mandate" $MEM/*.md | head -30` — **MEM unavailable** (`MEMORY_METHOD_LESSONS.md` not in snapshot); the lessons `feedback_no_operator_lane`, `feedback_session_owns_full_ship_lifecycle` cannot be read here.

---

## 3. World SOTA survey

No web access in this lane — sources are from model knowledge, dated as accessed 2026-08-28 from memory; uncertain URLs marked `(unverified)`.

| # | System / practice | Source | Mechanism that makes it best-in-class | Measured effect (published) | Transferability to this organism |
|---|---|---|---|---|---|
| 1 | GitHub Spec Kit (spec-driven dev) | https://github.com/github/spec-kit (2025) | `/specify → /plan → /tasks → /implement`; constitution file constrains generation; spec is the source of truth, code is derived | n/a (tooling, no published study) | High: organism already contract-first; Spec Kit's constitution ≈ CLAUDE.md; its weakness — specs are unverified prose — is exactly what the organism's receipt grammar cures |
| 2 | AWS Kiro specs | https://kiro.dev/docs/specs/ (2025) | requirements.md in EARS user stories → design.md → tasks.md; steering docs; hooks | none published | High for EARS grammar; Kiro assumes an interactive user who answers questions — Zero's one-line Italian mandates need inference-as-artifact instead (§5.R3) |
| 3 | EARS notation | Mavin et al., "EARS (Easy Approach to Requirements Syntax)", IEEE RE 2009; DOI https://doi.org/10.1109/RE.2009.32 `(unverified)` | 5 controlled-NL patterns (ubiquitous/event-driven/unwanted/optional/complex) cut ambiguity in aerospace requirements | defect reduction reported in Boeing/NASA case studies (numbers vary by paper) | Direct: falsifiable-acceptance criteria are EARS's spiritual child; EARS shapes are lintable — feeds `spec_lint` |
| 4 | Amazon Working Backwards / PR-FAQ | https://www.aboutamazon.com/about-us/working-backwards-how-amazon-works-backwards `(unverified)`; Bryar & Carr, *Working Backwards* (2021) | press release written first forces customer outcome; FAQ surfaces risks before build | none published (internal) | Partial: organism's `product.yaml` (specific user, falsifiable metric, kill criterion) is a stricter, machine-consumed PR-FAQ; the owner-signs-at-G0 switchboard is a better fit than narrative PRs for a solo owner |
| 5 | Shape Up | https://basecamp.com/shapeup (2019, free book) | appetite (fixed time-box) instead of estimate; pitches; betting table; circuit breaker (no rollover) | none published | High: gear declaration ≈ appetite; kill criterion ≈ circuit breaker; missing piece here is a mandate-level circuit breaker (recommendation R1/R5) |
| 6 | Google design docs + eng practices | https://google.github.io/eng-practices/ (review docs confident); "Design Docs at Google" PDF `(unverified)` | design doc as async review artifact, living doc, alternatives section | none published | Deliberately rejected here (ASSEMBLY-LINE bans "PRD/design-doc chains") — but the alternatives-section discipline survives in council dissent; noted as contrast |
| 7 | Anthropic — Claude Code best practices | https://www.anthropic.com/engineering/claude-code-best-practices (2025) | CLAUDE.md as living context; plan mode before writes; explicit task decomposition | none published | Already absorbed (modus, plan-phase hooks); validates organism's direction; adds nothing new to intake |
| 8 | Anthropic — building effective agents | https://www.anthropic.com/engineering/building-effective-agents (2024) `(URL path unverified)` | simplest-workflow-first; fan-out degrades on sequential tasks; prompt-chained vs orchestrator tradeoffs | internal evals cited qualitatively | Confirms anti-sperpero fan-out rules; intake consequence: triage must decide parallelizability BEFORE ceremony — modus already does |
| 9 | AWS TLA+ on critical paths | Newcombe et al., "How Amazon Web Services Uses Formal Methods", CACM 58(4), 2015; https://www.allthingsdistributed.com/2015/03/amazon-web-services-tla-plus.html `(unverified)` | lightweight formal specs on S3/Dynamo/EBS found 35 subtle bugs; one required a 35-step interleaving | published: 35 bugs, several previously unreachable | Targeted: payment/order/retention state machines (P0 tier) are exactly this class; transfer as property-level specs + model-based tests, not full TLA+ toolchain (§5.R4) |
| 10 | BDD/Gherkin + Specification by Example | https://cucumber.io/docs/gherkin/; https://specbyexample.com `(unverified)` (Adzic, 2011) | executable living documentation; red-first acceptance; examples as requirements | case-study level only | Already adopted at G2 (journey specs red-first); organism exceeds it: specs written by a DIFFERENT family than the builder — surveyed systems assume one team |
| 11 | Kubernetes triage automation (prow) | https://github.com/kubernetes/test-infra (prow plugins: /kind /priority /triage, stale, sig-routing) | deterministic label commands + owner routing + SLA bots at 1000s of issues/day | scale is the evidence | Low direct need (solo owner, no issue queue), but the principle — deterministic classification before human attention — is the same one compute_floor applies to diffs; PENDING-ARMS is the organism's analogue |
| 12 | Cynefin triage framework | Snowden & Kurtz, "A Leader's Framework for Decision Making", HBR 2003 `(URL unverified)`; https://en.wikipedia.org/wiki/Cynefin_framework | simple/complicated/complex/chaotic + "disorder"; probe-sense-respond vs categorize-respond | none (framework) | Gears 1/2/3 are proto-Cynefin; the named failure "tasks that merely look small" = Cynefin's *disorder*. Transfer: record re-gear events as domain re-classification receipts (§5.R1) |
| 13 | LLM ambiguity detection in RE | e.g. arXiv line of work on QuARS/LLM requirement ambiguity, 2023–2026; representative search: https://arxiv.org/list/cs.SE/recent `(specific paper unverified)` | classifiers flag ambiguous/vague requirement sentences; recent work uses LLM judges with controlled-NL references | lab F1s only | Feeds R3 as the mechanism; the organism's differentiator is what happens AFTER detection (infer + state, never interrogate) |
| 14 | Tessl / OpenSpec (spec-first frameworks) | https://tessl.io (2025); https://github.com/Fission-AI/OpenSpec `(unverified)` | spec is the maintained artifact; code regenerated; spec diffs reviewed instead of code diffs | none published | Directionally validates "contract freeze at G3"; organism's version is stronger because the freeze is gate-enforced, not convention |

**The 4 that matter most.**
**EARS/Kiro (rows 2–3):** the world's best answer to "how do you make requirements unambiguous" is a controlled grammar plus interactive clarification. Organism asymmetry blocks the interactive half (one-line colloquial mandates, no interrogation allowed by the language protocol); the transferable core is the grammar and its lintability. **Shape Up (5):** appetite + circuit breaker is the best small-team intake economics; organism has appetite (gear/budget shape) and product-level kill criteria, but no mandate-level circuit breaker tied to measured misfire. **AWS TLA+ (9):** proves that on state-machine-critical paths, property-level specification finds bugs no amount of review finds — and the organism's own retention-scope pack (`evidence/pack.yml`: structural tripwire red on origin/main) is a homegrown instance of exactly this. **Kubernetes prow (11):** the lesson is not the bots but the invariant — *classification must be deterministic and precede attention*; `compute_floor` already applies this to diffs; nothing yet applies it to mandate text.

---

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Deterministic risk triage bound to ceremony | **AHEAD** | No surveyed system computes a risk floor from the diff and forces gate ceremony to match. `scripts/evidence_pack_lint.py` rules 6–7 + `.github/workflows/harness-floor.yml` (floor, ceiling, override audibility, phased flips with dates in code). K8s triage is label-based; Google/Meta diff-risk scoring (from general knowledge, no public primary URL I can stand behind) scores merges, not spec ceremony |
| Grounding-before-building | **AHEAD** | STADIO-0 + `stadio_zero_nudge.py` + `premise_gate.py` mechanically enforce verify-before-edit while deliberately staying non-blocking to avoid reward-hacking (P1). Surveyed best practice *advises* context grounding (Anthropic #7); none enforces it with phase-aware hooks |
| Spec artifacts consumed by gates | **AHEAD (young)** | ASSEMBLY-LINE's inversion ("An artifact exists only if a gate consumes it") + G0–G7 + kill criterion. Spec Kit/Kiro generate specs nothing verifies; here `evidence/pack.yml` receipts/dissent are lint-enforced. Caveat: first product on the line (GARUDA) — unproven at volume |
| Contract-first, red-first journeys, generator≠grader specs | **AT/AHEAD** | G2 specs red-first by a non-builder family + G3 freeze + settling lesson. BDD world has red-first; nobody surveyed mandates author≠builder family at spec time |
| Ambiguity handling at mandate intake | **BEHIND** | Language protocol + karpathy "state assumptions" are conversational norms (CLAUDE.md §4 omitted; ASSUMED). No mechanical ambiguity detection, no assumptions artifact, no contradiction tracking. EARS/Kiro/RE research all have mechanisms; here assumptions vanish into session prose |
| Appetite & circuit breakers | **AT** | Budget shape stop-loss + kill criterion in `product.yaml` (GARUDA MANDATE §2). Missing: mandate-level circuit breaker on fix-chains and misfire telemetry (Shape Up has the breaker concept; organism lacks the measurement behind it) |
| Formal specification on P0 paths | **BEHIND** | Hot-zone floor 3 buys ceremony, not properties. No property-level spec of payment/order/retention state machines; journey tests are behavioral. AWS TLA+ evidence (35 subtle bugs) applies squarely; `evidence/pack.yml`'s tripwire is a prototype, not a practice |
| Measurement of intake itself | **BEHIND** | Misfire rate, fix-of-fix depth, gear_override share, assumption contradictions: all UNMEASURED (§2 commands). ASSEMBLY-LINE's own 39/100 vs "56%" episode shows even doctrine numbers were not re-derivable until challenged |
| Definition of ready / preflight levels | **AT** | STADIO-0 block + brief schema (objective/constraints/acceptance/consumer_map/risks/grader) + `l_level: L2`/`gate_class: opus` live in `evidence/brief.yml`; AUTONOMOUS_OPS.md L1/L2/L3 detail not in pack (ASSUMED) |
| Intake continuity across session death | **AT/AHEAD** | `session_budget.py` artifact-on-death handoff; surveyed systems mostly assume session continuity |

---

## 5. Beyond-SOTA recommendations

Ranked by (impact × confidence) / cost. All respect hard constraints: flat subscriptions, CLI-only seats, no paid Anthropic API, PII boundary intact, Fable never auto-routed, Zero decides business matters. Scar-family references use only families verifiable from the pack: #1 reward-hacking (P1), #2 mute/disarmed gate, #3 guards & decision procedures, #6 phantom file:line.

**R1 — Triage ledger with CI-computed misfire rate.**
- **What:** append-only ledger rows per mandate (`evidence/triage-ledger/*.yml`): provisional gear + one-line why, every RE-GEAR event with reason, final gear, `gear_override` used, rule-8 suspensions, fix-of-fix depth. `evidence_pack_lint.py` requires the row whenever `evidence/brief.yml` exists; `harness-floor.yml` computes and prints misfire rate (provisional ≠ final / total; floor-violation count).
- **Why it beats SOTA:** no surveyed system treats its own triage decisions as telemetry; Cynefin names re-classification but nobody measures it. This composes two pieces only this organism has: the provisional gear announcement (modus STAGE 0) and the deterministic CI floor.
- **Cost:** ~1 Gear-2 session (flat-sub tokens); zero ongoing tokens.
- **Gear:** 2.
- **Risk:** ledger rot = scar family #2 (mute artifact); mitigated because harness-floor *consumes* it (fails on missing row). Fake rows = family #1; mitigated by cross-checking row fields against brief/pack values.
- **Metric + method:** under-gear misfire rate (floor violations / PRs) — baseline today UNMEASURED; target visible number in 30 days, floor violations → 0. Method: the CI job prints it; AMENDMENTS cites it.
- **Kill criterion:** if after 60 days no pack/AMENDMENT cites the computed number, delete the ledger.
- **First PR:** schema + row-presence lint (NOTICE phase) — see §6 PR-1.

**R2 — `spec_lint.py`: falsifiability gate at intake (T-GATE).**
- **What:** stdlib linter over `evidence/brief.yml`, `docs/mandates/**`, `docs/plans/*/MANDATE.md`: (a) each acceptance criterion must be executable-shaped (names a command/test/exit/grep) or is flagged; (b) `assumptions:` list present, each tagged `inferred|asked|owner`; (c) every path in `consumer_map` existence-checked (`ls` at lint time) — superscar #6 made impossible at spec time; (d) kill criterion present for product briefs. Phased NOTICE→FAIL with the flip date in code (the repo's own established pattern).
- **Why it beats SOTA:** Kiro/Spec Kit generate specs; nothing surveyed verifies a spec's acceptance criteria are falsifiable against the actual repo, or that cited paths exist. The organism already invented the receipt grammar (`claim/cmd/exit/ts/seat`) for outputs; this applies it to inputs.
- **Cost:** ~1 Gear-2 session; zero ongoing.
- **Gear:** 2.
- **Risk:** over-eager guard — scar family #3 (W83–85). Mitigation per `docs/specs/rules-as-harness-and-simulation-chamber-v1.md`: guilt+innocence tests, guard-conformance entry, kill-switch env, Lab dry-run on recorded specs before FAIL.
- **Metric:** % new briefs with 100% mechanically falsifiable acceptance (baseline UNMEASURED: run R2-lint in NOTICE mode over the last 20 briefs for 2 weeks); rule-8 suspensions/month from AMENDMENTS grep (§2 command).
- **Kill criterion:** >15% of notices overridden with legitimate reasons in first 30 days → demote to T-NUDGE permanently.
- **First PR:** §6 PR-2.

**R3 — Settling receipt for reviewed artifacts (quick win).**
- **What:** `evidence/pack.yml` gains `settling:` (writer process dead / artifact hashes stable across a settling window / or "extracted at fixed commit") — required non-empty for Gear 3. Lint rule in `evidence_pack_lint.py`.
- **Why it beats SOTA:** every surveyed review practice assumes artifact stability; none receipts it. Scar-backed twice in one day (GARUDA contract freeze + Visa Oracle extraction, `docs/factory/ASSEMBLY-LINE.md`).
- **Cost:** trivial (~40 lines + tests). **Gear:** 1.
- **Risk:** family #1 (bureaucratic one-liner receipts); mitigated by requiring the hash/window values, not a claim.
- **Metric:** stale-finding incidents on live writers → 0 (baseline: 2 in one day, 2026-08-24).
- **Kill criterion:** never fires as a real catch in 90 days AND everyone resents it → drop the requirement, keep the field optional.
- **First PR:** §6 PR-3.

**R4 — Ambiguity probe: cross-family assumptions artifact at STAGE 0.**
- **What:** at STAGE 0 for Gear ≥ 2, one flat-sub non-Anthropic CLI seat runs an EARS-shaped ambiguity pass over the mandate text; the orchestrator resolves each hit BY INFERENCE (language protocol: never interrogate) and writes the results into the brief's `assumptions:` block (consumed by R2). Each assumption later verified or contradicted gets a receipt/scar link at CAPTURE.
- **Why it beats SOTA:** surveyed systems either ask (Kiro) or rewrite (RE tools); neither fits a solo owner issuing one-line mandates. Inference-as-audited-artifact + contradiction-recidiva tracking composes pieces no surveyed system has, exploiting the cross-family fleet on flat subs.
- **Cost:** one cheap CLI seat per Gear ≥ 2 mandate (minutes, flat subscription).
- **Gear:** 2.
- **Risk:** noise = family #3 → start T-NUDGE, Lab dry-run first (rules-as-harness discipline).
- **Metric:** assumptions/brief; % assumptions later contradicted (recidiva) — target <10%, then <5%.
- **Kill criterion:** contradiction rate <5% AND Zero reports friction → retire to optional.
- **First PR:** hook the probe as a `stadio-zero` companion script + brief schema field (NOTICE phase).

**R5 — Fix-of-fix depth receipt (circuit breaker at intake).**
- **What:** if a mandate is a fix of a fix (depth ≥1, detected from referenced PR numbers + path overlap), the brief must carry a root-cause receipt: which PR introduced the regression, which gate missed it, what now consumes the lesson. Absent receipt → auto re-gear ≥2 and flag. Feeds R1's ledger.
- **Why it beats SOTA:** no surveyed intake system ties a fix mandate to its predecessor's gate failure; the organism uniquely has scar corpus + full merge history + full-lifecycle session ownership to compute it.
- **Cost:** low (heuristic in lint + schema field).
- **Gear:** 2.
- **Risk:** detection false positives → keep advisory in wave 2.
- **Metric:** fix-of-fix share baseline UNMEASURED (§2 gh command) → target <10%.
- **Kill criterion:** depth heuristic false-positive rate >20% on manual audit → drop detection, keep voluntary field.

**R6 — Tripwire-as-spec for P0 state machines (property-level specs).**
- **What:** extend G2/G3: journey/state-machine specs compile to BOTH red-first tests AND a standing structural tripwire (the retention-scope tripwire pattern evidenced in `evidence/pack.yml`: "red on origin/main and green here", guilt+innocence, earned exemptions). Tripwires run on hot-zone PRs + nightly on main. For payment/order machines, add property-level invariants (Hypothesis-stateful-class, not TLA+ toolchain) consumed by refuter seats.
- **Why it beats SOTA:** ATDD gives living tests; AWS formal methods give design-time proofs; nothing surveyed continuously enforces spec-derived invariants against main. The organism's hot-zone floor already marks WHERE; this adds WHAT.
- **Cost:** Gear 2–3 per product family; medium token-hours.
- **Gear:** 3 (pilot one family).
- **Risk:** tripwire over-match = family #3 (guilt/innocence mandatory per doctrine); false reds on main (machine-saturation scar territory) — run tripwires as checks, not blockers, in wave 3.
- **Metric:** P0 state-machine regressions caught pre-merge vs post-deploy; target ratio ≥3:1 within 90 days of pilot.
- **Kill criterion:** false reds outnumber true catches over the pilot window → retire tripwire, keep property tests.

---

## 6. 90-day roadmap + first PRs

**Wave 1 (days 0–30): intake becomes measurable.**
Execute §2 UNMEASURED baselines (AMENDMENTS misfire grep, fix-of-fix gh audit, gear_override history). Ship PR-1 (triage ledger, NOTICE), PR-3 (settling receipt). Run R2 linter in NOTICE-only mode over new briefs to collect the falsifiability baseline.

**Wave 2 (days 30–60): intake becomes checked.**
PR-2 (`spec_lint`) lands with guilt/innocence + guard-conformance entry + Lab dry-run on the last 20 specs; extend to `docs/mandates/**` and `docs/plans/*/MANDATE.md`; set the NOTICE→FAIL flip date in code. R4 ambiguity probe pilot (T-NUDGE) on Gear ≥ 2 mandates. R5 fix-of-fix detection advisory.

**Wave 3 (days 60–90): intake becomes predictive.**
R6 tripwire-as-spec pilot on one hot-zone family (payment/order or retention). Promote ledger row to FAIL; print misfire rate in `harness-floor.yml` summary. Retro: grep AMENDMENTS for new intake misfires vs baseline; feed the delta into the superscar corpus. Decide R4/R5 promotions on their kill criteria.

| First PR | Title | Files | Net lines | Gear | Acceptance test |
|---|---|---|---|---|---|
| PR-1 | `triage-ledger: schema + row-presence lint (NOTICE)` | `evidence/triage-ledger/SCHEMA.yml` (new), `scripts/evidence_pack_lint.py` (+~70), `scripts/tests/test_evidence_pack_lint_triage_row.py` (new) | ≤300 | 2 | Guilt: brief with no ledger row → NOTICE line, exit 0. Innocence: a real `evidence/brief.yml` shape (the #5059 retention pack) with row → clean. Single-lane/ Gear-1 packs exempt. |
| PR-2 | `spec_lint: falsifiable-acceptance + path-existence linter` | `scripts/spec_lint.py` (new, stdlib), `scripts/tests/test_spec_lint.py` (new), guard-conformance registry entry | ≤400 | 2 | Guilt: synthetic brief with acceptance "il codice è pulito" + consumer path `foo.py:63` that doesn't exist → both flagged. Innocence: `evidence/brief.yml` (PR #5059, all paths real, all acceptance executable-shaped) passes. Kill switch `SPEC_LINT_OFF=1`. |
| PR-3 | `evidence pack: settling receipt field for Gear 3` | `scripts/evidence_pack_lint.py` (+~40), `scripts/tests/test_evidence_pack_lint_settling.py` (new) | ≤150 | 1 | Guilt: Gear-3 pack with empty/missing `settling:` → NOTICE (pre-flip). Innocence: Gear <3 pack without field passes; Gear-3 with hash+window values passes. |

---

## 7. Needs-ruling

True Legge-5 items only:

1. **Hard gates on the owner's writing surface.** Should `spec_lint` FAIL-phase apply to `docs/mandates/**` and `docs/plans/*/MANDATE.md` — files Zero himself authors — or stay NOTICE-only there? Mechanism-vs-authority over the owner's own documents is his call.
2. **Ledger content boundary.** Triage ledger rows would carry mandate summaries; the repo is public (lane 13's territory). Ruling: verbatim mandate text in the ledger — allowed with internal-only phrasing, or hashes/ids only?
3. _(Advisory, not blocking)_ Wave-3 property-spec investment on payment paths: confirm appetite when wave 2 metrics land.

No credentials, consents, GUI or physical actions required by any recommendation.

---

## 8. §Meta-pattern

What repeats across every finding in this lane — under-gearing, phantom file:line plans, doc-only merge rot, the mute disarmed gate, the wrong scar propagated into a header (W78), the "56%" briefed number nothing could re-derive, the stale refuter findings, the prose routing floor ignored 7-to-355 — is one defective belief:

> **"A declaration is a verification."**

Every intake failure here is an instance of accepting a *stated* thing — declared gear, cited path, written rule, briefed number, stable-looking file, asserted acceptance — as if it were a *checked* thing. The organism already discovered the antidote and industrialized it for outputs: "an artifact exists only if a gate consumes it", receipts `{claim, cmd, exit, ts, seat}`, deterministic floors, dissent as a mandatory non-empty field, override audibility. The defect persists only where intake itself remains verbal: the gear announcement, the assumption, the acceptance sentence, the ambiguity, the artifact's stillness. The beyond-SOTA move for this part is therefore not a new framework but a completion: **turn every intake declaration into a receipt that a gate consumes.** The verification machine exists; the front door is the last prose.

---

## 9. Sources

All accessed 2026-08-28 from model knowledge (no web tools in lane); confidence noted.

1. GitHub Spec Kit — https://github.com/github/spec-kit — 2025 — canonical spec-driven-dev toolchain (spec→plan→tasks→implement + constitution).
2. AWS Kiro specs documentation — https://kiro.dev/docs/specs/ — 2025 — EARS requirements → design → tasks as productized workflow.
3. Mavin et al., *EARS (Easy Approach to Requirements Syntax)*, IEEE RE 2009 — https://doi.org/10.1109/RE.2009.32 `(unverified)` — controlled-NL requirements grammar from aerospace practice.
4. Amazon "Working Backwards" — https://www.aboutamazon.com/about-us/working-backwards-how-amazon-works-backwards `(unverified)`; Bryar & Carr, *Working Backwards*, 2021 — outcome-first intake (PR/FAQ).
5. Basecamp *Shape Up* — https://basecamp.com/shapeup — 2019 — appetite, pitches, circuit breaker; best small-team intake economics.
6. Google Engineering Practices — https://google.github.io/eng-practices/ — ongoing — async review culture; design-doc contrast case.
7. Anthropic, *Claude Code: Best practices for agentic coding* — https://www.anthropic.com/engineering/claude-code-best-practices — 2025 — grounding/context doctrine from the harness vendor itself.
8. Anthropic, *Building effective agents* — https://www.anthropic.com/engineering/building-effective-agents — 2024 `(path unverified)` — fan-out limits that justify triage-before-ceremony.
9. Newcombe et al., *How Amazon Web Services Uses Formal Methods*, CACM 58(4) — 2015; https://www.allthingsdistributed.com/2015/03/amazon-web-services-tla-plus.html `(unverified)` — measured payoff of property-level specs on critical paths (35 subtle bugs).
10. Cucumber/Gherkin docs — https://cucumber.io/docs/gherkin/ — ongoing — executable-spec baseline the organism's G2 extends.
11. Gojko Adzic, *Specification by Example* — https://specbyexample.com `(unverified)` — 2011 — living documentation from examples.
12. Kubernetes test-infra (prow triage plugins) — https://github.com/kubernetes/test-infra — ongoing — deterministic classification preceding human attention at scale.
13. Snowden & Kurtz, *A Leader's Framework for Decision Making*, HBR 2003 + https://en.wikipedia.org/wiki/Cynefin_framework — Cynefin domains and "disorder", the theory behind gear re-classification.
14. LLM-based requirement ambiguity detection (RE literature 2023–2026, e.g. via https://arxiv.org/list/cs.SE/recent) `(specific papers unverified)` — feasibility evidence for R4's probe.

Repo paths verified via ground pack: `.claude/skills/modus/SKILL.md` · `.claude/commands/stadio-zero.md` · `.claude/skills/karpathy-discipline/SKILL.md` · `infra/claude-hooks/` (listing, 49 entries) · `infra/claude-hooks/stadio_zero_nudge.py` · `infra/claude-hooks/premise_gate.py` · `infra/claude-hooks/orchestrate_gate.py` · `infra/claude-hooks/session_budget.py` · `infra/claude-hooks/_phase.py` · `infra/claude-hooks/README.md` · `docs/factory/ASSEMBLY-LINE.md` · `docs/plans/2026-08-24-garuda-voa-live/MANDATE.md` · `docs/mandates/2026-08-22-arsenal-routing-mandate.md` · `docs/specs/rules-as-harness-and-simulation-chamber-v1.md` · `scripts/evidence_pack_lint.py` · `.github/workflows/harness-floor.yml` · `evidence/brief.yml` · `evidence/pack.yml` · `research/operations/` (listing, 364 entries). Omitted by pack cap and therefore not verified: `AUTONOMOUS_OPS.md`, `CLAUDE.md`, `VADEMECUM.md`, `.claude/skills/modus/AMENDMENTS.md`, `.claude/rules/cicatrix-superscar.md`, `MEMORY_METHOD_LESSONS.md`, six `research/operations/*.md` files — claims about these are marked ASSUMED/UNMEASURED in §1–§2.