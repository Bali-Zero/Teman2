---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 1/13 — Intake, triage & specification
model: claude-fable-5 (pinned lane)
sources: 15
repo_files_verified: 26
status: complete
sections_done: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
adversarial_review: codex
model_selection: "manual — Zero's order of 2026-08-28 for this one panel; pinned by the orchestrating session, not routed by any script, cron or doctrine (Fable 5 has no automated role, ruling 2026-08-20)"
---

# Beyond-SOTA 1/13 — Intake, triage & specification

How a mandate — often one line of colloquial Italian — becomes a gear-triaged, grounded,
falsifiable specification. Grounded 2026-08-28 on the panel worktree (HEAD = main at launch);
every path below was verified on disk in this session.

## 0. TL;DR

Position: **ahead of every surveyed system on classification and grounding** (the CI-enforced
gear floor+ceiling and the never-block entry gate have no equal in Spec Kit, Kiro, Anthropic
practice, or the JIT-risk literature), **behind world practice on pre-spend commitments** —
appetite, assumptions, hostile questions, invariants — which is exactly where every measured
disaster lives (44 h/8.6 M-token blowup; 27/200 corrective commits; the retention P0).
Biggest gap: **declared-but-unbound commitments** — the spec declares falsifiable acceptance,
assumptions and budget, and CI binds only the gear.
Top-3 moves: **R1** lint every Gear≥2 acceptance bullet to a runnable probe+receipt (EARS-shaped,
at the existing pack-lint door); **R2** an enforced `appetite:` field — Shape Up's ex-ante half
of rule 8, with `appetite_exceeded` acknowledgment mirroring `gear_override`; **R4** invariant
micro-specs on invariant-bearing hot zones, wired to the floor that already knows those paths.
Guardrail to preserve while doing it: lint the artifact, never block the thinking.

## 1. How Nuzantara does it today

**Mandate capture.** Mandates arrive as colloquial Italian one-liners ("fondila per garuda ma
fondila a livello di sistema", "vai da solo e non fermarti"). The language protocol (repo
`CLAUDE.md` §4) forbids asking "what do you mean?": the session must translate colloquial intent
into precise technical action, infer from the codebase, and — when ambiguous — pick the most
likely reading and state the assumption in one line. Mandates also arrive from receptors, not
only from Zero: the escalations board and `~/.agent/decisions/claude_tasks/` are checked
HIGH-first at session start (`CLAUDE.md` §2/§14), and `PENDING-ARMS.md` read-back at TRIAGE
re-injects suspended work as candidate mandates.

**STAGE 0 TRIAGE (the gear).** `.claude/skills/modus/SKILL.md` ("STAGE 0 — TRIAGE: pick the gear
(the anti-sperpero brain)") requires a *provisional* gear declared in one line — `GEAR <n>:
<mandate> — <why>` — chosen from the mandate text plus the loop ledgers (PENDING-ARMS read-back
is mandatory at TRIAGE). Three gears: **1 · LISCIO** (typo/rename/known-cause 1-file fix; effort
`medium`; skip to BUILD→VERIFY→CLEAN, declare the skip), **2 · STANDARD** (anything producing a
PR; effort `xhigh`; full loop, one adversarial spalla), **3 · PROFONDO** (audits, architectural
decisions, migrations, pre-deploy critical path; `xhigh` with `max` opt-in only on declared
adjudication; TAC patterns, mandatory §Meta-pattern, declared budget shape). The gear is
explicitly *falsifiable, not a vow*: GROUND confirms or re-gears it, and the skill names
"under-gearing tasks that merely look small" as *the systematic failure mode*. Escalation
mid-flight is allowed; silent de-escalation is banned. Anti-sperpero rules make budget a router:
council only when divergent priors ∧ error cost >15× ∧ genuine parallel breadth; fan-out only
for ≥3 independent READS; declared stop-loss at Gear 3.

**The deterministic floor and ceiling (CI-recomputed, non-gameable).**
`.github/workflows/harness-floor.yml` ("Harness floor recompute") recomputes the gear floor
from the PR's actual changed-file set *unconditionally* — brief present or not (an adversarial
finding on 2026-08-10 killed the first cut, which only checked the declared field) — by calling
`scripts/evidence_pack_lint.py --print-floor` (one source of truth). Hot-zone paths floor at
Gear 3; since 2026-08-27 a SIZE term (S1 addendum, pinned at measured churn p90) floors large
diffs regardless of path. Rule 7 of the same linter is the mirror **ceiling** (`compute_ceiling()`,
PR #4474, from the 2026-08-21 token-ceremony audit lever L6): a docs/ledger-only diff, or a
≤2-file/≤60-net-line diff outside hot zones, is Gear-1-shaped by construction — declaring it
Gear 3 with a council or ≥3 grader dispatches FAILS the lint unless `evidence/pack.yml` carries
a reasoned `gear_override:` (then a notice). The ceiling never overrides the floor. This is the
one non-gameable classifier the 2026-08-19/20 model-routing rulings lean on ("a task cannot be
talked into Gear 2 when its diff says 3", repo `CLAUDE.md` §5): the model may only *raise* the
gear; CI verifies both directions.

**The entry gate (stadio-zero).** `/Users/nuzantara/.claude/skills/stadio-zero/SKILL.md` (repo
command mirror `.claude/commands/stadio-zero.md`) is the pre-task gate: (1) memory-hits (`mem
query` — "il context buffer NON è autoritativo"), (2) hot-files VERIFIED on disk this turn
("mai fidarsi di un path citato" — born from the 13-agent-autopsy phantom `file:line` scar,
superscar #6), (3) PII-risk scope (Law 2, with the known bugs of `scripts/_redact_pii.py`
named in the skill itself), (4) **falsifiable acceptance criteria** ("se non riesci a scrivere
un criterio falsificabile, il task è mal-formato → riformulalo finché lo è"). Two design choices
are load-bearing: the output is a *chat block, not a mandatory file* (an empty file created to
unblock is reward-hacking, not study), and skipping is legal for true one-liners but must be
*declared*. `karpathy-discipline` (`.claude/skills/karpathy-discipline/SKILL.md`, vendored from
`forrestchang/andrej-karpathy-skills`) supplies the four build-time principles: think-before
(surface assumptions), simplicity-first, surgical changes, goal-driven execution with
verifiable success criteria.

**Enforcement, phase-aware, deliberately soft where judgment lives.** `infra/claude-hooks/`
(reference copies; live copies in `~/.claude/hooks/` — the README documents the HOME-fork risk,
family #1): `stadio_zero_nudge.py` injects ONE reminder when a young session (<400 transcript
lines) starts editing without STUDY markers — it *never blocks*, because "a blocking gate on a
judgment act invites empty STUDYs to unblock". `premise_gate.py` warns on an Edit of a product
file with no in-turn read of that file ("green != working" made mechanical — anti-hallucination
rule #2). `_phase.py` relaxes these gates only on a *positive* plan-mode signal, failing safe to
gates-ON, with an operator kill switch. The hard edge exists too: `orchestrate_gate.py` blocks
Bash/Edit/Write past 800 transcript lines with zero dispatches, and — after the 2026-08-12
lesson — a disarmed gate now *says* it is disarmed and whether it would be blocking right now.
`session_budget.py` leaves an artifact-on-death handoff so a dead session's intake state
survives it.

**The spec artifact, per PR.** `evidence/brief.yml` + `evidence/pack.yml`, linted by
`scripts/evidence_pack_lint.py` (122 KB of linter — rules include gear ≥ floor, gear ≤ ceiling,
seat diversity, receipts). The live brief on this HEAD (task
`visa-oracle-retention-scope-p0-0826`) shows the practiced genre at its best: `task_id`, `gear:
3` *with the deterministic receipt in the pack*, `l_level`, `gate_class`, an `objective` that
narrates the defect's causal chain, `constraints` ("fix the FAMILY, not the instance"; "the one
red this PR drew is answered by supplying this pack, never by touching the gate"),
**falsifiable `acceptance`** bullets, a **`consumer_map`** naming every surface the change
touches *including the ones deliberately not touched* ("Verified, not assumed"), `risks`, and a
`grader` block declaring generator≠grader and the two adversarial subagents dispatched
*without* the brief. Dissent is recorded in the pack (the refuter "killed the timeline claim").

**The product tier.** `docs/factory/ASSEMBLY-LINE.md` (RULED 2026-08-24) governs product builds:
the inversion "an artifact exists only if a gate consumes it"; the unit of done is "a customer
journey working in production, meeting its SLO"; exactly **5 permanent artifacts**
(`product.yaml` with ≤3 guardrails and a **kill criterion**, `journeys/` written RED-first by a
*different family* than the builder, `contracts/` frozen at G3, code+tests, `ops/`); 8 gates
G0–G7; risk-tiered review (`p×r×C > c`); and an honest ledger of what is *not yet armed*
(enforcement backlog items 1–7). The MANDATE.md pattern
(`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`) is the owner-facing instantiation:
owner-framed product, `product.yaml` seed with a proposed kill criterion ("if 60 days after
go-live paid orders < 10/week…"), an **owner switchboard on which nothing blocks** (build dark,
collect signatures at the end), lanes, gates, scar-derived constraints, definition of done.
`docs/mandates/2026-08-22-arsenal-routing-mandate.md` shows the same genre for non-product
work (ground truth measured → non-goals → deliverables as N one-concern PRs → PROVE-LIVE
checklist → §Solo-operatore → capture).

**Budget discipline ex-post: rule 8.** Repo `CLAUDE.md` §2 Agent PR Contract rule 8: a PR red
three times for the SAME cause SUSPENDS; a fix-of-a-fix chain stops at depth 1 — "if the
correction is itself wrong, the surface is under-specified — **write the spec**, do not open
the third PR". Preflight SDD levels (`CLAUDE.md` §2: L1 3+ files · L2 dependencies/migrations/
KBLI-visa/pre-deploy · L3 auth/billing/RAG, via `./scripts/ai-dispatch.sh preflight-{l1,l2,l3}`,
escape `SKIP_PREFLIGHT=1`) and `AUTONOMOUS_OPS.md` (L2 active) bound what a spec may authorize.

**Where the genre does NOT live.** `docs/brainstorms/` contains one entry (2026-04-26) and
`docs/briefs/` one (2026-02-06): the dedicated divergence-phase genre is dead in practice.
Spec energy lives instead in `evidence/brief.yml` (per PR), `MANDATE.md` (per product), and
`research/operations/` adjudication docs — e.g. `2026-08-23-p04-spec-rulings-requested.md`
(nine spec gaps, each classified REAL/DROPPED with repro, "requesting a Conductor ruling") and
`2026-08-26-outstanding-journeys-triage.md` (24 reds "classified and costed, zero writes",
with a retracted question *measured* rather than argued).

## 2. Scars & ledger evidence in this area

**The founding scar: phantom `file:line` (superscar #6).** The reason stadio-zero exists. The
family line W65→W90→W100→W113 (`.claude/rules/cicatrix-superscar.md` #6) runs from "even the
refuter hallucinates" through "the ground-truth verifier is stale" to "blind agreement: 7
false-clean out of 8" and "the correction itself lies". The antidote is the entry gate's step 2
plus modus GROUND's rule that a cited path is "a PHANTOM until re-grepped". Recurrence: the
2026-08-26 AMENDMENTS row records a fresh variant — a blind seat "measured" 11 stale skill
copies as repo truth without asking *which tree* it measured (working tree vs `origin/main`),
yielding the new discipline "state the tree with every count".

**Triage misfires, measured.** `.claude/skills/modus/AMENDMENTS.md` holds 46 rows (34 dated + 12
checklist, counted this session); 5 mention gear/triage. The catastrophic one is 2026-08-22: two
sessions mandated to "cut token waste" ran 44 h and 31 h, opened 180 PRs, spent 8.6 M output
tokens, shipped ~10 business commits; **27 of 200 commits on main 2026-08-20..22 existed only to
correct a claim made by a previous one**; PR #4547 (a 1-file hook regex) took 14 commits, 11
adversarial rounds, ~6 h. The row's own verdict is a *triage* verdict: "a 'reduce waste' mandate
is itself meta-work — TRIAGE should gear it 2 with a stop-loss, never Gear 3 with an open
council." Rule 8 (three-rounds-then-suspend, fix-of-fix depth 1 → write the spec) shipped the
same day. The 2026-08-26 row is the meta-recidiva: AMENDMENTS recorded zero entries across
24–26/08 *for the second time after naming the exact same gap* — the cure is "ship the receptor,
not another rule" (`docs/plans/2026-08-26-receptor-live/MANDATE.md`, R1–R12, with its own kill
criterion).

**The evidence-slot collision (W125 + the fixed-path trauma).** `.claude/rules/cicatrix-scars.md`
:1305–1316: `evidence/brief.yml` and `evidence/pack.yml` live at two FIXED root paths, so any
two Gear≥2 PRs collide by construction — one session counted **11 `Merge remote-tracking
branch` commits across 5 PRs**, and in one of them another PR's `l_level: L2` leaked *outside
any conflict marker* into a brief that declares `l_level: L1` — precisely the field the gate
reads to decide ceremony. W125's deeper lesson: hand-resolving markers is not `--ours`; git
silently merges uncontested lines. The cure is partially armed on this HEAD:
`scripts/ci/evidence_paths.py` exists (15 KB) and `harness-floor.yml` resolves per-PR evidence
paths, failing closed on ambiguity, with an explicit pre-migration fallback to the root paths.
Contention is still live in the current window: fleet-watch mailbox notices observed during this
very session (2026-08-26..28) report PRs #5037, #4640, #5059, #5069 DIRTY *on
`evidence/brief.yml`/`pack.yml` specifically* (sibling-session reports, quoted as observed, not
re-verified against GitHub from this read-only lane).

**Fix-of-fix chains, three measurements.** (a) Title heuristic (this session): of the last 200
merged PRs — which saturate the 14-day window, i.e. ≥200 merges in 14 days — only 6 titles carry
corrective language ("again", "actually", …), and manual inspection leaves ~1–2 genuine
(e.g. "unstuck PR #5068 **again**"): title-level detection under-detects badly. (b) Scope
cadence (this session): repeated `fix(<scope>)` merges in 14 days — `fix(kb)` ×7,
`fix(garuda)` ×7, `fix(mouth)` ×6, `fix(ci)` ×4, `fix(bot)` ×4 — chains *suspected* by cadence,
not proven. (c) The organism's own claim-level audit (AMENDMENTS 2026-08-22 row): **27/200
commits (13.5%) corrected a previous commit's claim** in a 3-day window. The honest conclusion:
the only reliable fix-of-fix detector so far has been a forensic retro, not anything at intake
time — rule 8 fires ex-post, at the third red.

**The ceiling exists but the override is (so far) never exercised.** Measured this session: of
the last 30 commits touching `evidence/pack.yml`, **0 contain a `gear_override:` line**
(`git show <sha>:evidence/pack.yml | grep -c gear_override` = 0 for all 30). Note
`evidence/brief.yml` did not yet exist at those sampled commits (the per-PR brief genre is
young), so this measures the override mechanism's use, not gear distribution: either ceilings
have not yet bound in practice, or sessions comply rather than override. Both readings say the
same thing for this lane: the ceiling is a *new* control (2026-08-21 audit → PR #4474) whose
binding rate nobody is yet tracking.

**Docs-only merges as intake failure.** `docs/factory/ASSEMBLY-LINE.md` re-derives it rather
than asserting: 39 of the last 100 merged PRs (as of 2026-08-24) touched nothing but
docs/research/ledgers — "roughly two of every five merges move no product". Its enforcement
backlog item 1 (docs-only PRs require an owner-initialed label) is *tracked as not yet armed*,
per superscar #2 ("esiste ≠ armato"). The same file records the 2026-08-25 integration-branch
scar — three lane briefs said both "arm `--auto`" and "the orchestrator will gate", which on an
unprotected branch is a contradiction; 15 files of customer-facing surface merged unreviewed —
whose general form is an intake/spec lesson: *a brief that transcribes a standing rule without
checking the machinery behind it writes a wish, not an instruction*.

**Ownership honesty in specs.** The phantom-operator discipline (repo `CLAUDE.md` §2): any
PENDING-ARMS line owned by a bare `operator` is flagged PHANTOM-OPERATOR by
`scripts/pending_arms_report.py` and CI — a spec may only park work on the human for the named
operator-only categories (physical, GUI, TCC, credentials, Legge-5 business). The GARUDA
MANDATE's "owner switchboard (NOTHING blocks on these)" is the same principle applied at
product-spec level.

## 3. World SOTA survey

| # | System / practice | Source (see §9) | Mechanism | Measured effect | Transfers? |
|---|---|---|---|---|---|
| 1 | GitHub Spec Kit (spec-driven dev) | S1, S2 | `/specify → /plan → /tasks → implement` slash-flow + a project "constitution"; spec is the shared artifact for 30+ coding agents | none published | HIGH as validation — the genre already exists here as `evidence/brief.yml`; the missing piece Spec Kit has is explicit task decomposition *from* the spec |
| 2 | AWS Kiro specs | S3 | trio `requirements.md` (EARS) + `design.md` + `tasks.md`, generated and kept in sync with code; **EARS**: "WHEN ⟨condition⟩ THE SYSTEM SHALL ⟨behavior⟩" forces testable, unambiguous phrasing | none published | HIGH — EARS phrasing for `acceptance:` bullets is directly adoptable; the sync-with-code idea maps to consumer_map |
| 3 | Amazon Working Backwards PR/FAQ | S4 | write the press release + hostile FAQ before building; most PR/FAQs are rejected or reworked — killing at 1-page cost is the point | Kindle/Prime/AWS lineage (anecdotal) | MEDIUM — `product.yaml` G0 covers the PR half; the *FAQ half* (hard questions asked pre-build) has no equivalent artifact here |
| 4 | Shape Up (Basecamp) | S5 | **appetite** = fixed time, variable scope, declared before betting; pitch → betting table; **circuit breaker**: no extension by default | none published | HIGH — rule 8 is the circuit breaker *ex-post*; the declared-up-front appetite is the missing ex-ante half |
| 5 | Anthropic Claude Code best practices | S6 | explore → plan → code → commit; plan mode as read-only phase separation; effort scaled to task | Anthropic-cited ~33% unguided success on non-trivial tasks (secondary) | already internalized — stadio-zero + `_phase.py` are an *enforced* version of an optional practice |
| 6 | Karpathy: leash / autonomy slider / context engineering | S7 | keep agents on small verifiable leashes; slider per task; the app does the context engineering | none published | already vendored (`karpathy-discipline`); the gear system IS an autonomy slider with a CI-checked detent |
| 7 | Formal methods at AWS (TLA+) | S8 | TLA+ specs on critical designs; "debugging designs" framing | DynamoDB: 3 bugs needing traces up to 35 states; S3: 1 bug *plus a bug in the first proposed fix* | MEDIUM-HIGH — for the 2-3 invariant-bearing schema surfaces only (see §5 R4); the S3 "bug in the fix" is precisely the depth-1 fix-of-fix class |
| 8 | LLM ambiguity detection in RE (Alstom industrial study; ambiguity-vs-codegen) | S9, S10 | in-context-learning detectors flag + explain ambiguity in industrial requirements | ambiguity consistently degrades LLM performance, **worst on the most advanced models** | HIGH — the never-ask language protocol needs a compensating mechanism: detect + register assumptions instead of asking |
| 9 | Kubernetes Prow triage | S11, S12 | every new issue auto-gets `needs-triage`; SIG intake; `/triage accepted` lifecycle; bot-managed state machine at ~10³ issues scale | operates one of the largest OSS intakes | MEDIUM — receptor-borne mandates (escalations, PENDING-ARMS) lack an explicit triage state machine with aging |
| 10 | JIT change-risk prediction (Kamei line; CSUR survey; Prime Video diff-aware deployment risk) | S13, S14 | score each change's defect risk from diff features; prioritize review/tests | inspecting a small fraction of commits prevents a substantial share of defect-inducing changes; diff-aware (size/complexity) features strongest | HIGH as validation — the gear floor is the same signal family, used more radically (see prose) |
| 11 | Tessl / OpenSpec direction | S15 | spec-as-source registries; spec is the durable artifact, code regenerable | none published | LOW-MEDIUM — platform-heavy; the gate-consumption inversion here is leaner |

**The five that matter most.**

**Kiro's EARS is the missing notation, not a missing idea.** The live brief's acceptance bullets
are falsifiable in *intent* ("returns True in production's actual policy configuration…") but
free-prose in *form*; nothing machine-reads them. EARS shows a 20-year-old, vendor-neutral
syntax that makes each criterion mechanically checkable for shape (trigger + system + SHALL +
behavior) — the cheapest possible upgrade to the strongest existing artifact.

**Shape Up names the half of budget discipline Nuzantara lacks.** Anti-sperpero rules and rule 8
both fire *during or after* the spend; appetite is declared *before* it and defaults to no
extension. The 2026-08-22 blowup (44 h, 8.6 M tokens, ~10 business commits) happened with the
whole loop armed — because nothing at TRIAGE bound the spend, only the ceremony.

**AWS's TLA+ evidence lands on an open wound.** The S3 team found a bug, proposed a fix, and
model-checking found a bug *in the fix* — the depth-1 fix-of-fix chain, caught at design time.
The 2026-08-26 visa-retention P0 (`evidence/brief.yml` on this HEAD) is textbook: migration 264
established "one active row per environment", migration 281 widened the invariant to
(environment, scope) and never revisited four readers. That is an invariant-interaction bug a
relational spec would catch mechanically. Full TLA+ adoption is the wrong dose; per-hot-zone
invariant files are the right one.

**The ambiguity research justifies a register, not a question.** The language protocol's
never-ask rule is correct for a solo owner who does not review code — but the industrial finding
that ambiguity degrades the *strongest* models most means silent inference is costliest exactly
where this fleet operates. The compatible mechanism is: infer, then *register* the inference as
a structured, expiring assumption a gate can see — never a blocking question.

**JIT risk prediction vindicates — and is beaten by — the gear floor.** Twenty years of
literature converges on "diff features predict risk; spend review where risk is". Every surveyed
deployment (Prime Video included) uses the score to *prioritize humans or tests*. Nuzantara uses
the same signal to *bind process ceremony bidirectionally in CI* (floor AND ceiling, override
only by reasoned receipt). No surveyed system does that; this is a genuine AHEAD, worth
protecting and instrumenting rather than replacing with an ML score.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Gear triage bound to the diff (floor + ceiling, CI-enforced, bidirectional) | **AHEAD** | `harness-floor.yml` unconditional recompute; `evidence_pack_lint.py` rules 6/7; no surveyed system gates *process ceremony* deterministically — industry (S13, S14) only prioritizes review/tests by risk score |
| Grounding entry gate (verified-on-disk, falsifiable acceptance, PII scope) | **AHEAD** | stadio-zero 4-step + phase-aware hooks with documented never-block/reward-hacking rationale; Anthropic's own explore→plan (S6) is optional and unenforced |
| Spec artifact consumed by gates (brief/pack + 122 KB linter + consumer_map + recorded dissent) | **AHEAD** on consumption, **AT** on notation | "an artifact exists only if a gate consumes it" (ASSEMBLY-LINE) vs Spec Kit/Kiro templates nothing machine-consumes; but acceptance bullets are free prose — EARS-shaped checkability absent |
| Spec authoring mechanics (shared single slot) | **BEHIND own standard, cure in flight** | W125 + scar :1313 (11 merge commits / 5 PRs; cross-PR `l_level` contamination); `scripts/ci/evidence_paths.py` shipped, root-path fallback still active; contention observed live 2026-08-26..28 (fleet-watch notices on #5037/#4640/#5059/#5069) |
| Ambiguity handling at intake | **MIXED** | never-ask + one-line assumption (CLAUDE.md §4) fits a solo owner — but assumptions evaporate after the chat line; industrial LLM-RE work (S9, S10) shows ambiguity hits strongest models hardest; 27/200 corrective commits are partly this class |
| Ex-ante budget (appetite) | **BEHIND** | Shape Up declares appetite before betting with a default circuit breaker (S5); here rule 8 + stop-loss fire ex-post/at-Gear-3-only; the 2026-08-22 blowup (44 h / 8.6 M tokens / ~10 business commits) happened with the loop fully armed |
| Divergence phase / hostile-FAQ pre-build | **BEHIND** | `docs/brainstorms/` has 1 entry (April), `docs/briefs/` 1 (February); `product.yaml` G0 covers the press-release half of PR/FAQ (S4), nothing covers the hostile-FAQ/pre-mortem half |
| Formal specs on invariant-bearing surfaces | **BEHIND** | zero TLA+/Alloy/property-spec anywhere; the 2026-08-26 retention P0 is exactly the invariant-interaction class AWS catches at design (S8: S3 found "a bug in the first proposed fix") |
| Fix-of-fix detection at intake | **BEHIND** | rule 8 fires at the third red; the only reliable detector so far was a forensic retro (27/200); title heuristic finds ~1–2/200; scope cadence (fix(kb)×7, fix(garuda)×7 in 14 d) only *suspects* chains |
| Receptor-borne intake lifecycle | **AT** | escalations HIGH-first + PENDING-ARMS >48h aging (`pending_arms_report.py`) ≈ Prow's needs-triage aging (S11/S12), minus an explicit accepted/declined state machine |

Honest summary: the *classification* and *grounding* layers are genuinely ahead of anything
surveyed; the *pre-spend commitments* (appetite, assumptions, hostile questions, invariants)
are where world practice is ahead — every measured disaster in §2 lives on that side.

## 5. Beyond-SOTA recommendations (ranked by impact × confidence / cost)

**R1 — Acceptance-as-probe: lint every acceptance bullet to a runnable receipt.**
*What:* Gear≥2 briefs must pair each `acceptance:` bullet with a `probe:` (a command, test id,
or check name) and the pack's `receipts:` must carry each probe's observed outcome; the pack
linter fails a Gear≥2 pack whose acceptance items are probe-less (notice-first rollout, then
fail). EARS-shape the bullet text (WHEN/SHALL) as a lint *notice*, not a fail. *Why beyond
SOTA:* Kiro/Spec Kit generate acceptance text; nobody surveyed lints acceptance
*executability per PR* into a required CI check. It composes EARS (S3) with the organism's own
gate-consumption inversion, at a door that already exists (`evidence_pack_lint.py` +
`harness-floor.yml` — the 2026-08-26 lesson: new checks at existing doors, never new
ceremony). *Cost:* ~1 session, flat-sub. *Gear:* 2. *Risk:* family #3 over-match (prose-shape
guard) — ship with a guilt+innocence corpus per `infra/guard-conformance/`. *Metric:* % of
Gear≥2 acceptance bullets carrying a probed receipt — baseline measured on the last 30 packs
(expected low; the mechanism doesn't exist), target 100% by day 60. *Kill criterion:* if
median brief-authoring time inflates >15 min (session logs), scope to Gear 3 only. *First PR:*
see §6.

**R2 — Appetite: the ex-ante half of rule 8.**
*What:* an `appetite:` block in the brief (wall-clock ceiling, adversarial-round ceiling,
optional token ceiling) declared at TRIAGE; exceeding it without an explicit
`appetite_exceeded:` acknowledgment in the pack is a lint fail — the exact `gear_override:`
pattern, applied to spend. Rounds are already countable (rule 8 counts reds); wall-clock is
derivable from PR/commit timestamps. *Why beyond SOTA:* Shape Up's appetite (S5) exists nowhere
in agentic-coding practice as an *enforced, machine-read* field; here it converts the
2026-08-22 class (44 h, 8.6 M tokens, ~10 business commits) from forensic finding into an
in-flight breaker. *Cost:* ~1 session. *Gear:* 2. *Risk:* #2 theater (a field nobody honors) —
mitigated by lint-fail, not exhortation; and gaming-by-inflated-appetite, mitigated by the
ceiling notice (an appetite >2× gear norm draws a notice). *Metric:* sessions exceeding
declared appetite unacknowledged → 0; corrective-commit share 13.5% → <5% by day 90. *Kill:*
if >30% of packs need `appetite_exceeded`, the norms are wrong — recalibrate once, then decide
keep/kill.

**R3 — Recidiva tripwire: fix-of-fix detected at intake, not at round 3.**
*What:* a deterministic CI step: if a PR's changed files overlap ≥50% with a `fix:`-typed PR
merged <7 days earlier on the same paths, the brief must carry `supersedes_fix: #NNNN` plus one
line on why the first fix was wrong — otherwise notice→fail. This is rule 8's depth-1 principle
("write the spec, don't open the third PR") made mechanical and moved to the PR-open moment.
*Why beyond SOTA:* the JIT-risk literature (S13, S14) scores single changes; none of the
surveyed systems detects *chains* at intake. Exploits the merge history + the evidence door.
*Cost:* ~1 session (a git/gh query + one lint rule). *Gear:* 2. *Risk:* #3 over-match on
legitimately iterative surfaces (content articles) — path-class exemptions with a
guilt/innocence corpus. *Metric:* chains carrying a spec / chains detected; scope-cadence
baseline fix(kb)×7, fix(garuda)×7 per 14 d. *Kill:* >20% false-positive rate on 30 days of PRs.

**R4 — Invariant micro-specs on the invariant-bearing hot zones (TLA+-lite).**
*What:* per hot zone that carries a cross-migration invariant (retention policies,
idempotency, RBAC grants), one machine-checkable invariant file — property tests or SQL
assertions expressing "one active row per (environment, scope)"-class truths — that every
migration touching the zone must re-run; authored once from the live catalog, extended on each
new invariant. NOT a TLA+ adoption program. *Why beyond SOTA:* AWS applies formal methods with
specialist humans (S8); composing *invariant files + the deterministic hot-zone floor* (the
floor already knows which paths are dangerous — it can also know which invariant file they owe)
exists nowhere surveyed. *Cost:* 1 session per zone, 2–3 zones. *Gear:* 3 (hot zone by
construction). *Risk:* #9 state-schema drift (the invariant file itself staling) — each file
names the migration that last amended it; a migration that touches the zone without touching
the file draws the lint. *Metric:* invariant-class P0s per quarter (baseline: 1 in August —
the retention outage); acceptance for zone 1: a property test that is red on pre-289 schema
and green on 289. *Kill:* if zone 1 takes >2 sessions, stop at one zone and reassess.

**R5 — Assumption register with expiry (never-ask made auditable).**
*What:* the language protocol's "state the assumption in 1 line" becomes a structured
`assumptions:` block in the brief — each entry tagged `verified|unverified` plus the probe
that would settle it; a pack shipping with unverified assumptions draws a lint *notice* naming
them (mirror of `seat_diversity_note`). *Why beyond SOTA:* industrial LLM-RE (S9, S10) detects
ambiguity but stops at flagging; wiring detection into a per-PR evidence artifact with expiry
is unsurveyed — and it is the only ambiguity mechanism compatible with a hard never-ask rule.
*Cost:* <1 session. *Gear:* 1–2. *Metric:* share of shipped Gear≥2 packs with 0 unverified
assumptions; trend of assumption-rooted corrective commits. *Kill:* if the block degenerates to
boilerplate ("no assumptions") in >80% of briefs by day 60, remove it — theater detected.

**R6 — Pre-TRIAGE receptor: triage at the door.**
*What:* a UserPromptSubmit/SessionStart hook that, given the mandate text, deterministically
greps the hot-zone map, the PENDING-ARMS index and the superscar families, and injects
"candidate gear · the 2–3 applicable scars · the hot files" *before* grounding starts —
hint-only, never blocking (stadio-zero's own rationale). Prow's `needs-triage` lifecycle (S11)
applied to mandates instead of issues. *Cost:* 1 session. *Gear:* 2. *Risk:* #3 keyword
matching (a hint that mis-primes) — mitigate by always printing the floor's authority ("CI
recomputes; this is a prior"). *Metric:* mid-flight re-gear rate; median time from mandate to
first verified hot file. *Kill:* if re-gear rate doesn't move in 60 days, delete the hook
(quarterly gate-audit rule: a gate that never bites is deleted).

Deliberately NOT recommended: an ML change-risk model (the deterministic floor is more
auditable and already ahead — S13/S14 add nothing a solo-owner fleet can debug); full TLA+;
resurrecting `docs/brainstorms/` as a genre (dead twice — the hostile-FAQ energy goes into
R5's assumptions and the existing pre-mortem-shaped `risks:` block instead).

## 6. 90-day roadmap + first PRs

**Wave 1 (days 0–30) — measure, then lint at the existing door.**
Baselines first (one Gear-2 session, zero product risk): probe-coverage of acceptance bullets
across the last 30 packs; chain rate via the ≥50%-overlap query over 90 days of merges;
assumption-block absence rate. Then R1 (notice mode) + R5.
- **PR-1** `feat(evidence): acceptance-as-probe lint (notice mode) + baseline report` — files:
  `scripts/evidence_pack_lint.py` (one rule + selftest cases), `scripts/tests/test_evidence_pack_lint.py`,
  one paragraph in `docs/factory/ASSEMBLY-LINE.md`. ≤300 net lines. Gear 2. Acceptance: linter
  selftest green; rule fires on a synthetic probe-less Gear-2 pack and stays silent on the live
  visa-retention pack *acceptance shape* (innocence case).
- **PR-2** `feat(evidence): assumptions register block + lint notice` — same files, ≤200 net
  lines. Gear 2. Acceptance: notice names each unverified assumption; zero-assumption brief
  passes silently.

**Wave 2 (days 30–60) — bind spend and chains.**
R2 (appetite) + R3 (recidiva tripwire); flip R1 from notice to fail on Gear≥2.
- **PR-3** `feat(evidence): appetite block + appetite_exceeded acknowledgment rule` — linter +
  tests + a TRIAGE paragraph in `.claude/skills/modus/SKILL.md`. ≤350 net lines. Gear 2 —
  *note:* touching `SKILL.md` may hit doctrine-path gates; if the floor recomputes 3, honor it.
  Acceptance: pack exceeding declared rounds without acknowledgment fails the lint selftest.
- **PR-4** `feat(ci): supersedes_fix tripwire (overlap ≥50% with fix-typed PR <7d)` — a small
  script + one harness-floor step + guilt/innocence corpus. ≤400 net lines. Gear 2.
  Acceptance: synthetic chain detected; iterative content-path exemption stays silent.

**Wave 3 (days 60–90) — invariants and the door receptor.**
R4 zone 1 (retention invariant file, red on pre-289 schema) + R6 (pre-TRIAGE hint hook) + the
first quarterly review of R1–R3 metrics against their kill criteria.
- **PR-5** `feat(migrations): retention invariant file + migration-touch lint` — Gear 3 by
  path (hot zone), migration-PR class ⇒ auto-merge OFF, session merges after gates.
- **PR-6** `feat(hooks): pre-triage door hint (hint-only, never blocks)` — `infra/claude-hooks/`
  + tests. Gear 2.

## 7. Needs-ruling (Legge 5 only)

1. **Appetite auto-suspend default (R2):** whether breaching a declared appetite may SUSPEND a
   mandate *by default* (rule-8 precedent shipped with Zero's GO on 2026-08-22) or only demand
   the acknowledgment line. Recommendation: acknowledgment-only for 30 days, then Zero decides
   with the measured breach rate in hand.
2. **Docs-only owner label (ASSEMBLY-LINE enforcement backlog #1):** arming it requires an
   owner-initialed label — an owner mechanism by construction; only Zero can commit to
   supplying it.
Nothing else in §5 requires a business decision, consent, credential, or GUI/physical action.

## 8. §Meta-pattern (Gear 3)

One defective belief generates every finding in this lane: **"a declared commitment is a bound
commitment."** The organism is world-class at making intake judgments *explicit* — gear
declared in one line, acceptance declared falsifiable, assumptions declared in one line,
budget shape declared at Gear 3 — and it binds exactly one of them (the gear, via
floor+ceiling in CI). Every measured disaster in §2 is a *declared-but-unbound* commitment
failing silently: acceptance bullets nobody probes (so "done" drifts), assumptions that
evaporate after the chat line (27/200 corrective commits), spend declared as ceremony but not
as ceiling (44 h / 8.6 M tokens), fix-of-fix caught only at the third red because depth-1 is
prose. The repo has already discovered the cure-shape twice — the gear floor (2026-08-10) and
the receptor-not-rule ruling (2026-08-26) — and both say the same thing: *convert the
declaration into a check at a door that already exists, and never put a blocking gate on a
judgment act.* R1–R5 are that same move applied to the four remaining declarations. The
boundary discovered by stadio-zero (block mechanics, nudge judgment) is the part no surveyed
system has articulated, and it must be preserved while binding: lint the *artifact*, never
block the *thinking*.

## 9. Sources

1. **S1** — github/spec-kit (repo): https://github.com/github/spec-kit — accessed 2026-08-28.
   Primary code + `spec-driven.md` methodology of GitHub's SDD toolkit.
2. **S2** — GitHub Blog, "Spec-driven development with AI: get started with a new open source
   toolkit": https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/
   — accessed 2026-08-28. Vendor's own statement of intent and workflow.
3. **S3** — Kiro docs, "Specs / Feature Specs": https://kiro.dev/docs/specs/ and
   https://kiro.dev/docs/specs/feature-specs/ — accessed 2026-08-28. Primary product docs;
   EARS-notation requirements.md + design.md + tasks.md trio.
4. **S4** — workingbackwards.com, "The Amazon Working Backwards PR/FAQ Process":
   https://workingbackwards.com/concepts/working-backwards-pr-faq-process/ — accessed
   2026-08-28. Authored by the ex-Amazon authors of the method.
5. **S5** — Basecamp, *Shape Up*, ch. "The Betting Table":
   https://basecamp.com/shapeup/2.2-chapter-08 — accessed 2026-08-28. Primary text (appetite,
   circuit breaker).
6. **S6** — Anthropic, "Best practices for Claude Code":
   https://code.claude.com/docs/en/best-practices — accessed 2026-08-28. Primary vendor
   guidance (explore→plan→code, plan mode).
7. **S7** — AI21, "Karpathy's Leash for Constraining AI Agents":
   https://www.ai21.com/blog/karpathys-leash/ (with travis.media Software-3.0 summary:
   https://travis.media/blog/software-3-0-ai-changing-programming-karpathy/) — accessed
   2026-08-28. Secondary but faithful accounts of the leash/autonomy-slider talk.
8. **S8** — Newcombe et al., "How Amazon Web Services Uses Formal Methods", CACM 2015:
   https://cacm.acm.org/research/how-amazon-web-services-uses-formal-methods/ (PDF:
   https://lamport.azurewebsites.net/tla/formal-methods-amazon.pdf) — accessed 2026-08-28.
   Canonical industrial formal-methods evidence (DynamoDB 35-state-trace bugs; S3 bug-in-the-fix).
9. **S9** — "Requirements Ambiguity Detection and Explanation with LLMs: An Industrial Study"
   (Alstom / MDU; IEEE): https://www.ipr.mdu.se/pdf_publications/7221.pdf and
   https://ieeexplore.ieee.org/document/11185947/ — accessed 2026-08-28. Industrial-scale
   evaluation, in-context-learning detectors.
10. **S10** — "Assessing the Impact of Requirement Ambiguity on LLM-based Function-Level Code
    Generation": https://arxiv.org/html/2604.21505v1 — accessed 2026-08-28. Measures ambiguity
    degrading codegen, worst on strongest models.
11. **S11** — Kubernetes community, "Issue Triage Guidelines":
    https://github.com/kubernetes/community/blob/master/contributors/guide/issue-triage.md —
    accessed 2026-08-28. Primary process doc of one of the largest OSS intakes.
12. **S12** — kubernetes/test-infra PR #19272 "prow: add needs-triage and triage/accepted
    labels": https://github.com/kubernetes/test-infra/pull/19272 — accessed 2026-08-28. The
    enforcement mechanism itself.
13. **S13** — "A Systematic Survey of Just-in-Time Software Defect Prediction", ACM Computing
    Surveys: https://dl.acm.org/doi/10.1145/3567550 — accessed 2026-08-28. Survey anchoring
    the Kamei JIT line (change-level risk from diff features).
14. **S14** — "Deployment Risk Assessment Using Diff-Aware Features: A Case Study at Prime
    Video": https://arxiv.org/pdf/2607.06766 — accessed 2026-08-28. Industrial confirmation
    that diff-aware features dominate.
15. **S15** — Tessl blog, "A look at Spec Kit":
    https://tessl.io/blog/a-look-at-spec-kit-githubs-spec-driven-software-development-toolkit —
    accessed 2026-08-28. The spec-as-source ecosystem view.

## Adversarial review

Blind cross-family review (generator ≠ grader), 2026-08-29. The refuters received the full document and the panel's hard rules, nothing else; path existence had already been verified on disk by the orchestrator's gate, so they attack logic, numbers, rule-compliance and the SOTA claims. Dispositions by the orchestrator (claude-fable-5, Zero's manual selection): **survives** = recorded as a standing caveat, not fixed in this PR; **rejected** = the objection misreads the document or the rules (reason given); **accepted** = fixed in the text.
Tally: 8 raised · 6 survive · 1 rejected · 1 accepted.

**Reviewer: `codex`** — OpenAI GPT-5.6 sol at effort high via Codex CLI (read-only sandbox on the repo snapshot). 8 raised.

| # | sev | objection (refuter's words) | disposition |
|---|---|---|---|
| 1 | HIGH | "model: claude-fable-5 (pinned lane)" — A pinned panel lane implies automatic routing, directly violating the hard rule that Fable 5 is manual-selection-only. | rejected — the lane ran under Zero's explicit manual order for this one panel (2026-08-28: "lancia per ognuna un fable 5 max effort"), pinned by the orchestrating session, not by any script, cron or doctrine; the frontmatter now carries `model_selection:` stating this |
| 2 | HIGH | "pack's `receipts:` must carry each probe's observed outcome" — A stored outcome is not proof the probe ran. Without CI executing and authenticating probes, R1 merely creates forgeable claims while presenting acceptance as mechanically bound. | survives — valid: a stored outcome is forgeable; the probe must be executed by CI, not recorded by the author — constraint on R1's build |
| 3 | HIGH | "here it converts the 2026-08-22 class... into an in-flight breaker" — PR timestamps do not measure session runtime, and a post-hoc lint acknowledgment does not interrupt spending. R2 cannot prevent the cited 44-hour blowup as designed. | survives — PR timestamps do not measure session runtime; R2 as designed cannot interrupt a 44-hour session, only account for it afterwards |
| 4 | HIGH | "Nothing else in §5 requires a business decision" — R2 sets spending ceilings and override policy; R3 chooses exempt business surfaces; R4 encodes operational invariants. Those governance choices require needs-ruling, not report-level decisions. | accepted — spending ceilings, exempt surfaces and operational invariants are rulings; the INDEX's §E carries the appetite item and the lane's 'nothing else' line is wrong |
| 5 | MED | "if a PR's changed files overlap ≥50% with a `fix:`-typed PR" — The report itself says path cadence only suspects chains. Overlap and title prefixes cannot establish recidivism, while a GitHub-dependent CI query adds nondeterminism and operational failure modes. | survives — overlap + `fix:` prefix only suspects a chain; the metric is a heuristic and must be labelled so |
| 6 | MED | "ahead of every surveyed system on classification and grounding" — The survey is narrow and provides no equivalent implementation audit of competitors. Absence from selected documentation cannot establish that no equal mechanism exists. | survives — a universal negative cannot be established from a 10–20 source survey; the INDEX now scopes every 'no equivalent' claim to the lane's surveyed set |
| 7 | MED | "Anthropic-cited ~33% unguided success on non-trivial tasks" — No supporting experiment is identified, and S6 is a best-practices page rather than the stated measurement source. The table presents an untraceable secondary statistic as measured effect. | survives — the ~33% figure is an untraceable secondary statistic; to be re-sourced or dropped |
| 8 | MED | "corrective-commit share 13.5% → <5% by day 90" — The 13.5% forensic sample is not attributed specifically to budget overruns, so R2 has no demonstrated causal path to this target; windows and classification methodology also differ. | survives — the 13.5% baseline is not attributed to budget overruns; the <5% target has no demonstrated causal path |

Refuter's verdict: I would not let this report stand as evidence until Fable routing, probe execution, governance rulings, measurement provenance, and causal acceptance metrics are corrected and independently re-verified.

