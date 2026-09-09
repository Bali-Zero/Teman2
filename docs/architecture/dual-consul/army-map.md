# Army map — the hierarchy Fable 5.1 and Astra use when they choose an army

**Status:** doctrine map, 2026-09-08. Rebuilt from the surviving sources after the 2026-09-06 design
worktree (`docs-army-command-map`) was pruned with its untracked `army-map.md`, `context-by-level.md`
and `workflow-spec.md`. Sources: Zero's 2026-09-06 Astra session (the ruling turns are quoted in
`research/operations/2026-09-08-hierarchy-workflow-sessions-study-it.md`), the 2026-09-07 Astra audit
(`research/operations/2026-09-07-astra-operative-workflow-audit.md`), the 2026-09-08 operating
contract (`research/operations/2026-09-08-nuzantara-operating-workflow-v1.md`, role mapping 1.1).
**This map does not grant permissions.** The Builder Contract in `CLAUDE.md`, the Gear floor, the
PII boundary and the external-builder shipping fence bind every rank on it.

Zero, 2026-09-06 12:59: _"disegna il grafico delle gerarchie, dei flussi, dei compiti, che potranno
usare Fable e Astra come mappa quando dovranno scegliere le armate."_ This is that map.

## 1. Ranks

| Rank                                                      | Seats                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Talks to                                           | Owns                                                                                                                                                                                                                                            | Never                                                                                                                                                         |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Imperators** (two, equal)                               | Fable 5.1 (Claude window opened by Zero with `--model`, effort `xhigh`) · Astra (Codex window, `gpt-6-astra`, effort `xhigh`)                                                                                                                                                                                                                                                                                                                                    | Each other; the generals                           | Strategic direction, constraints, appointment of the Dux, material _technical_ decisions and exceptions. Business decisions, credentials, consents and physical/GUI actions stay with the human (Builder Contract 5)                            | Fan-out, implementation, day-to-day traffic, self-selection by a session, auto-routing by any doctrine/cron/script                                            |
| **Generals** (two, equal)                                 | Opus 5 (Claude-native base) · Sol (Codex-native base, `gpt-5.6-sol`)                                                                                                                                                                                                                                                                                                                                                                                             | Up: imperators. Down: own specialists and builders | The mission when appointed **Dux**: plan, assignments, integration, evidence, ledger, and the release. Which general is eligible is fixed by the mission's COLOUR (§1bis). The other general takes a separate front or an eligible verification | A permanent reviewer title. Grading its own contribution                                                                                                      |
| **Specialists** (optional)                                | Opus 5 / Sol / Gemini deepthink / Qwen 3.8 Max (`strategy_panel`), NotebookLM for ground truth                                                                                                                                                                                                                                                                                                                                                                   | Own general; own builders                          | A domain or an interface contract                                                                                                                                                                                                               | Shipping                                                                                                                                                      |
| **Builders**                                              | Sonnet 5 (default) · Codex terra · Kimi 2.7 · GLM 5.2 (counter-builder)                                                                                                                                                                                                                                                                                                                                                                                          | Assigned general or specialist; own supports       | Bounded file ownership + proof criteria, one worktree each                                                                                                                                                                                      | Merging, arming, deploying (external seats); touching files outside ownership                                                                                 |
| **Supports**                                              | Haiku 4.5 · Codex luna · Kimi highspeed · Gemini Flash · local Ollama (PII lanes only)                                                                                                                                                                                                                                                                                                                                                                           | Own builder only                                   | One narrow task with a return contract: tests, fixtures, cleanup, mechanical checks                                                                                                                                                             | Weakening tests to make them pass; fixing someone else's code                                                                                                 |
| **Independent reviewer** (assignment, not rank)           | A qualified seat OUTSIDE the contribution chain; on Gear 2 its family ≠ the main builder's (fleet-order spec §3.2). Default seat per colour in §1bis: an independent Codex on BLUE, an independent Claude via `claude` CLI OAuth on ORANGE                                                                                                                                                                                                                       | The Dux                                            | PRE-review of the plan, POST-review of the frozen revision: a quality opinion                                                                                                                                                                   | Editing what it grades                                                                                                                                        |
| **Final on-disk gate** (assignment, distinct from review) | A **fresh session on the mission colour's gate seat** (§1bis): Opus 5 `xhigh` on BLUE, Sol `xhigh` on ORANGE (RULINGS.md 2026-08-20/21, colour-parameterised by RULED 2026-09-10). No substitution without a ruling; never cascades; **no cross-colour fallback** — a dead gate seat SUSPENDS the mission, it does not change colour. Outside the contribution chain. Work built by a seat that is not the appointed Dux always passes here (Builder Contract 5) | The Dux                                            | The last empirical disk/live check before release: the work by content, not by report. It SIGNS, and the receipt carries mission id, colour, HEAD sha, gate thread id, commands with exit codes, verdict                                        | Arming, merging or altering the candidate; being the reviewer of the same artifact when the Gear-2 family rule would exclude it; grading its own contribution |
| **Release owner**                                         | **The Dux of the mission**, on the colour's general seat (§1bis): an authorized Claude session on BLUE, the appointed Dux Sol session on ORANGE (RULED 2026-09-10)                                                                                                                                                                                                                                                                                               | The imperators                                     | Push, PR-open with auto-merge armed at once, queue merge, deploy, prove-live through the existing gates                                                                                                                                         | Hand-merging around checks; substituting its own verdict for the gate's                                                                                       |

**Dux** is a temporary appointment per mission, made by the imperators, taken by one general. It is
not a model, a rank or a piece of software. _"Opus e Sol sono uguali"_ (Zero, 2026-09-06 12:56):
Opus holds no permanent _reviewer_ title. Two stages stay distinct: independent **review** (any
qualified non-contributing seat, cross-family on Gear 2) and the final **on-disk gate** (a Claude
session on the Opus 5 `xhigh` seat on BLUE, a fresh Sol session on ORANGE — RULINGS.md
2026-08-20/21 and 2026-09-10; mandatory, not a default). The doctrine PR named in §5 rewrites the
_title_, not the gate seat.

## 1bis. The colour of the mission (PARABELLUM, RULED 2026-09-10)

Zero picks the colour with Fable and Astra at mission start, before the first assignment. It is the
ONLY axis on which the loop differs; everything else on this map is colour-blind. Ruling and
supersession detail: `docs/rules/RULINGS.md`, RULED 2026-09-10.

| Assignment                              | BLUE                                             | ORANGE                                                                         |
| --------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------ |
| Dux (general)                           | Opus 5 `xhigh`                                   | Sol (`gpt-5.6-sol`) `xhigh`                                                    |
| Default implementer                     | Sonnet 5                                         | Terra (`gpt-5.6-terra`); Sol implements small work directly                    |
| Adversarial reviewer (≠ builder family) | an independent Codex seat                        | an independent Claude seat via the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` |
| Final on-disk gate                      | a FRESH Opus 5 `xhigh` session outside the chain | a FRESH Sol `xhigh` session outside the chain                                  |
| Release owner                           | the Dux Opus 5                                   | the Dux Sol; the gate Sol only signs                                           |
| Transport                               | Claude-native work, Codex review                 | Codex-native work, Claude OAuth review                                         |

**No automatic colour fallback.** A dead seat SUSPENDS the mission. A colour is never changed
mid-mission and no session declares its own. An undeclared mission is BLUE.

**One window = one mandate = one organ = one worktree**, never two windows on the same path, two or
three at a time at most. Each window opens against the seven-section spec
(`.claude/skills/modus/battle-window-spec.md`) and states colour, Dux role, mandate id and worktree
before executing. The staff room (Fable 5.1 + Astra, with Zero only) fixes the windows, the teams
and the specs; it never fans out and never implements.

## 2. Communication: strictly along the chain

Zero, 2026-09-06 12:33: _"anche la comunicazione è gerarchica ... il supporto operativo parla solo
con il builder. I builder solo con specialisti o generali. Gli specialisti solo con i generali e i
generali con gli imperatori."_

```
Imperator ⇄ Imperator
   ⇅
 General ⇄ General          (peer channel: fronts, blockers, verification requests)
   ⇅
Specialist ⇄ Builder ⇄ Support
```

Two things travel outside the chain and must: **original evidence** (a reviewer reads the artifact,
never a summary of it) and **escalations to the human** (question, options, recommendation, blocked
part). Everything else that skips a level is a violation. **Today no code rejects a message edge:**
`orchestrate_gate.py` checks dispatch activity, `army_assignment.py` (W1, pilot branch) validates
that every node has exactly one parent in the assignment graph, and neither has an executing
consumer on `main`. The chain is enforced by review of the assignment record, not by transport.

Transport is not the hierarchy. Claude↔Claude peers use `SendMessage`; Claude↔Codex have no native
channel and use the shared folder + ledger. A file written is _published_, not _delivered_: the
pilot lost an afternoon because _"la cartella condivisa conserva i messaggi, non sveglia le
sessioni"_ (Astra, 2026-09-06 15:51). Delivery procedure, binding on the Dux: (1) the sender
records `sent` with the envelope hash; (2) the **sender** owns the wake-up (`SendMessage` to a
Claude peer; for a Codex peer, the human or the imperator that opened that window is told which
file to point it at); (3) the receiver records `received` against the same hash within the
mission's ack deadline (default 15 minutes of wall clock while the receiver is live); (4) no ack →
one retry with the same hash, then `BLOCKED: undelivered` in the ledger, never a silent wait; (5) a
dead session is recovered by a fresh window from the ledger, and the envelope's generation counter
rejects the stale copy. The deadline, the retry and the recovery step are **this map's** rule, written
from the pilot's failure; the hash and generation fields reuse the pilot's message envelope
(`docs/army-pilot/w1-message-envelope.md` on the local branch `agent/air-m5/ops/army-opus-general`),
which is itself marked PROPOSED / not frozen / authority none. Neither is enforced by code today.

## 3. W0 — choosing the army (the imperators' protocol)

1. **Nominate the Dux** between Opus and Sol; record it (`pilot/appointment` shape: mission id, Dux,
   both imperator approvals on the same packet hash).
2. **Size the mission by two axes, not one.** Risk of the change → the Gear floor (CI recomputes it
   from the diff; nobody argues with it). Parallelizable volume → how many builders. A delicate
   one-file fix is Gear 3 with one builder; a 300-item batch is Gear 2 with eight supports.
3. **Pick the operational base**: Claude-native (Agent/Workflow tools, worktrees, hooks) or
   Codex-native (collaboration tasks). One base per mission.
4. **Assign fronts** to the other general only if there is a second independent front or an
   eligible verification; otherwise it stays idle. Idle is cheaper than ceremony.
5. **Staff builders** for concrete need only, each with file ownership, proof criteria, model pinned.
   Multi-PR campaigns route at least one lane through a non-Anthropic builder (routing floor).
6. **Staff supports** only where a builder has a bounded sub-task with a return contract.
7. **Appoint two assignments, not one**: the independent reviewer (outside the contribution chain;
   family ≠ main builder on Gear 2) and the final on-disk gate (a fresh session on the colour's gate
   seat, §1bis, outside the chain). On a Gear-2 diff built in the Dux's own family these cannot be
   the same seat.
8. **Name the release owner** before the first commit: the Dux of the colour (§1bis).
9. **Open the ledger row** (Todoist for the Zero/Subhi pilot; `PENDING-ARMS.md` for harness work).

Small mission = Dux (also implementing) + independent reviewer + the colour's final gate; on a
Gear-2 diff built in the Dux's own family the reviewer is cross-family and the gate is a second,
separate session on the same colour's seat. _"Nessun obbligo di occupare tutti i gradi"_ (contract v1). Five nested levels are a
ceiling, not a target.

## 4. Context by level (what each window boots with)

Zero, 2026-09-06 12:43: _"Luna, Haiku o Kimi 2.7 non devono avere lo stesso contesto che hanno
Fable e Astra. Più focalizzato, più operaio."_

| Rank          | Boot packet                                                                                                                                                                                 | Size target                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Imperator     | Mission objective, material evidence, trade-offs, the decisions that need it. Compact or restart at every mission checkpoint: the packet rebuilds from the ledger, the transcript does not. | Short window; ≤150k tokens (the tokenaudit S1 threshold)        |
| General / Dux | Mission constraints, acceptance criteria, interfaces, capacity, artifact refs, `CLAUDE.md` Builder Contract, modus loop                                                                     | The repo's normal session boot                                  |
| Specialist    | Front objective, interface contract, selected evidence                                                                                                                                      | Normal boot minus unrelated corners                             |
| Builder       | File ownership, required context, test/acceptance criteria, worktree path, model pinned                                                                                                     | Normal boot; no corner skills unless the front needs them       |
| Support       | One task, minimum inputs, return contract                                                                                                                                                   | The prompt only; no doctrine tour                               |
| Verifier      | The frozen artifact, base/head SHA, contribution roster, the review template of contract v1                                                                                                 | Isolated; tools as the review needs, never the author's session |

Boot cost per Claude child is the `CLAUDE.md` hierarchy plus definition (≈5.6k content tokens, as
reported by the 2026-09-07 reality audit, PR #5872, from the now-lost `context-by-level.md` §1; the
150k figure is the tokenaudit hook's S1 threshold, printed by the hook itself), paid as cache write
once per distinct prefix. Do not change model, tool list or system prompt mid-mission: every change
is a new prefix.

The "short window" language in the table above is enforced (once the operator wires it into
`~/.claude/settings.json` — see §5's row for it) by `infra/claude-hooks/context_window_guard.py`, a
PreToolUse hard-gate on the estimated-context percent of the model's own window: an Imperator window
is capped at 20 %, every other rank (General/Dux, Specialist, Builder, Support, Verifier) at 40 % —
the same 40 % Zero's 2026-09-09 mandate states directly ("sopra il 40 % di contesto il modello si
indebolisce"). Past the threshold the gate denies every tool call except a memory save, a write to
the session's own handoff artifact, or a delegation (`SendMessage`/`TaskStop`), forcing the session to
open a fresh window, `/resume` from the handoff, and continue there rather than keep working inside a
context the mandate holds is already too big to reason well in.

## 5. What the machine enforces today, and where

Three states, kept apart on purpose: **LIVE** = runs on `main` or in the HOME hook set and can say
no; **PR** = code exists, PR open on 2026-09-08, not yet merged; **PROMISE** = nothing executes it.

| Rule on this map                                                  | Enforcer                                                                               | State (2026-09-08)                                                                                                                                                                                                                                                                                                                                                                                                        |
| ----------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Every `Agent` child pins `model:` (Zero 2026-07-14)               | `infra/claude-hooks/model_routing_gate.py`, PreToolUse matcher `Agent` (HOME settings) | LIVE. Known holes: `subagent_type: "fork"` is exempt by design; a frontmatter-pinned definition counts as explicit                                                                                                                                                                                                                                                                                                        |
| Every `Workflow` `agent()` pins `model:` (skill `/workflow` §1.1) | same hook, `Workflow` branch                                                           | PR (`feat(hooks): model_routing_gate inspects Workflow scripts`); the HOME matcher must also be widened to `Workflow` by the operator, else the code never runs                                                                                                                                                                                                                                                           |
| Non-Anthropic build lane on campaigns                             | same hook, Rule 2                                                                      | LIVE                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Delegation counts as orchestration; no role exemption             | `infra/claude-hooks/orchestrate_gate.py`                                               | PR #5940                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Short window per rank (Imperator 20 %, else 40 % of context)      | `infra/claude-hooks/context_window_guard.py`, PreToolUse matcher `*` (HOME settings)   | LIVE on M5, Pro, Mini since 2026-09-09 (registered by the shipping session per Ruling Zero 2026-09-09; first real deny observed on the M5 Fable session running that mandate). Window per seat: `CONTEXT_WINDOW_TOKENS` in the seat's `settings.json` env (1M seats), else inferred; `CONTEXT_GUARD_ROLE=imperator` not yet provisioned on any seat — all run the 40 % default until the two-imperator hierarchy is armed |
| Assignment graph: one parent per node, one Dux                    | `scripts/conductor/army_assignment.py` (W1)                                            | PR #5942 — validator + tests only; **no executing consumer** calls it yet (PROMISE for enforcement)                                                                                                                                                                                                                                                                                                                       |
| Reviewer outside the contribution chain                           | `scripts/conductor/review_eligibility.py` (W2) → `scripts/evidence_pack_lint.py`       | PR #5943 (validator) + a follow-up PR for the lint consumer; on the pilot branch the consumer is NOTICE-only until 2026-09-21 (`docs/army-pilot/CHECKPOINT.md`)                                                                                                                                                                                                                                                           |
| Gear floor from the diff; Gear-2 needs a brief                    | `harness-floor.yml` (required check)                                                   | LIVE                                                                                                                                                                                                                                                                                                                                                                                                                      |
| R1 generator≠grader on research docs                              | `scripts/check_adversarial_review.py`                                                  | LIVE, but it checks a recognised seat token and a heading; it cannot see whether findings exist or whether the seat was independent                                                                                                                                                                                                                                                                                       |
| Quorum and appetite on Gear-3 packs                               | `scripts/evidence_pack_lint.py`                                                        | LIVE, ex-post. Family exclusion is **not** computed: the lint counts qualifying seats without comparing families against contributors (`evidence_pack_lint.py` ~2647-2671)                                                                                                                                                                                                                                                |
| Executable `Bites:`                                               | `scripts/ci/bites_parse.py` (exists, tested in `immune-enforcement.yml`)               | parser LIVE; the caller that reads PR bodies is PR #5734 (BLOCKED); observation execution is PROMISE                                                                                                                                                                                                                                                                                                                      |
| Shipping fence (only the mission's own Dux merges, §1bis)         | Builder Contract 5, `FLEET_TOPOLOGY.json` `_invariants`, door-canon parity probe       | LIVE as doctrine + parity check; no runtime check on who pressed merge                                                                                                                                                                                                                                                                                                                                                    |
| Seat consumption per window                                       | `scripts/usage/seat_usage_collector.py`                                                | PR #5944                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Reservation of seats/slots                                        | —                                                                                      | PROMISE. The pilot's race (§8) has no code behind it                                                                                                                                                                                                                                                                                                                                                                      |

Nothing on this map is an in-flight budget breaker. The only in-flight limits are the runtime's
own (concurrency, depth, per-run agent count) and a `budget` a Workflow script declares.

## 6. Bootstrap prompts

**Imperator window (Zero opens it; `claude --model claude-fable-5-1 --effort xhigh` or the Astra
Codex task):**

> You are one of the two imperators. Read `docs/architecture/dual-consul/army-map.md` and the
> operating contract. With the other imperator, nominate the Dux for mission `<id>` between Opus and
> Sol, size it on both axes, and record the appointment. You do not fan out, you do not implement,
> you intervene on material decisions and exceptions only. Keep this window short: checkpoint to the
> ledger, then compact or restart.

**General / Dux window:**

> You are the Dux of mission `<id>` (appointment `<hash>`). One operational base. Reconcile the
> ledger, write the plan, staff builders with pinned models and file ownership, freeze the revision,
> obtain independent review, pass the colour's final on-disk gate (§1bis), release it yourself —
> push, open the PR and arm auto-merge at once, let the queue merge — prove live, close the ledger
> with a read-back. Escalate strategic
> questions to the imperators; business questions to Zero/Subhi with question, options,
> recommendation, blocked part. _Subhi's pilot only (contract v1; Zero 2026-09-09: "lascia questa dottrina per
> Subhi"): PRE-review of the plan and an explicit human scope decision before the first edit, four
> PRs per day, Todoist ledger. Not harness doctrine: under modus these are the conductor's judgment,
> not a gate._

**Builder:** the file set you own, the proof criteria, the worktree path, `model:` pinned, report to
`<general|specialist>`; never touch outside your ownership; never merge.

**Support:** one task, inputs, return contract, report to `<builder>`; never weaken a test.

**Verifier:** use the "Independent reviewer handoff template" in the operating contract v1, verbatim.

## 7. Invariants (bans stated as entities)

- No imperator fan-out. Five Fable lanes in parallel exhausted a MAX seat in 2–3 minutes (Fable's
  own report to Astra, 2026-09-06 13:44, quoted in the study §2); the 35-agent inherited run of
  2026-09-05 (`wf_6d2c6245`, 3.52M `totalTokens`) is documented in the reality audit §5 (PR #5872).
  Parallelism lives at builder/support level, mostly on non-Anthropic doors.
- Every `Agent`/`Workflow` child pins a model. Inheritance is the defect, whatever the parent.
  Pinning removes inheritance for the calls the hook sees; `fork` children and named/builtin
  workflows still inherit by design, so the imperator window itself must stay short and fan-out-free.
- Ceremony has a budget: a mission may add coordination only while the measured overhead (wait +
  rework + human interventions, captured per the operating contract v1 §"Capacity and pilot
  measurements") stays below the time it saves. Baseline for the comparison: the same Gear-2 task run
  as a plain modus loop (one conductor, one builder, one verifier). No baseline recorded yet.
- No external seat (Astra, Sol, Kimi, Qwen, GLM, Gemini) merges, arms or deploys. Parity between the
  imperators does not widen Astra's permissions.
- Generator is never grader, in either direction; changing skills inside a session does not create
  independence.
- PII never leaves the output boundary in cleartext, at any rank.
- Ceremony is a cost: a role that is named is not a role that exists. A rank is filled when its
  assignment, its evidence and its consumer are all observable.

## 8. Falsifiable pilot

One frozen Gear-2 task, non-PII, one Dux, ≤4 non-imperial seats, models pinned, reservations in the
ledger. Falsified by: one agent record without `model`; a closure declared without a `bites:`
observation at exit 0; and the reservation test below failing.

**Reservation test (the pilot's race, made detectable):** a slot is a row `{slot, owner, acquired_at,
expires_at, generation}` acquired by an atomic create-if-absent (a `mkdir`-style or `O_EXCL` write,
never read-then-write). Two actors attempt the same slot within the same second; exactly one row
exists afterwards and the loser's record says `denied`. Revocation is a new generation by the owner
only; a use recorded with an older generation, or after `expires_at`, or by a non-owner, falsifies
the run. "Nobody else was using it" is not evidence. The complementary hypothesis (no aggregate
capacity service needed) is judged on the ledger, not on rate limits: it is falsified if any slot
has two owners with **overlapping validity intervals** (sequential reassignment after release or
expiry is legitimate).
