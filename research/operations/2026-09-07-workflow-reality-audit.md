# Nuzantara workflow — what is actually in force (reality audit)

Date: 2026-09-07. Host: Air-M5 (`balizero`). Author: Fable 5.1, owner-opened interactive session,
Claude Code 2.1.263. Lane: `.worktrees/docs-workflow-reality-audit` on
`agent/air-m5/docs/workflow-reality-audit`, base `1bdadc5f28` (= `origin/main` at start).
Mandate: analysis only. No workflow, subagent, external LLM call, settings/hook/roster/skill/code
change, merge, deploy, install, process stop or restart was performed. Per-agent transcripts were
opened only to sum `usage` counters; no content was read or copied.

Evidence labels: **DISK** = read from a file this session (path + line where it matters);
**RUN** = command executed this session; **DOC** = official Claude Code documentation fetched
this session (`code.claude.com/docs/en/workflows`, `/sub-agents`); **INF** = inference.
Revisions matter: the main checkout is `5f64f2c2e7` (11 behind `origin/main` `1bdadc5f28`); the
design worktree `docs-army-command-map` is `b3fe0e3abe` (8 behind) and every dual-consul design file
this audit reads there is **untracked** — none of `workflow-spec.md`, `workflow-baseline.json`,
`implementation-plan.md`, `pilot-runbook.md`, `workflow-acceptance.md`, `context-by-level.md`,
`workflow-review-resolution.md` or `pilot/*` exists on `origin/main` (RUN: `git ls-tree origin/main`).
The three listed files that differ between main and origin/main are `PENDING-ARMS.md` (+2 lines),
`AGENTS.md` (+18, Damar publishing protocol) and `worker-plane-review-tests.yml`; nothing in the
routing/gate doctrine moved (RUN: `git diff --stat HEAD origin/main -- <listed paths>`).

---

## 1. Executive verdict

**We already own a complete, running, mostly-enforced workflow. Its rules are more current than
its consumers, and its consumers are more current than its defaults.** Concretely:

1. The loop exists and is live: `modus` (9 stages, Gear 1/2/3, budget-as-router, council gate,
   generator≠grader, prove-live, ledgers) is loaded by every non-trivial mandate; the `/workflow`
   skill and four versioned templates are its fan-out arm; the Workflow tool is enabled on this seat
   and has been used 17 times since 2026-08-28 on this machine alone (RUN: 17 `wf_*.json` records).
2. The Gear floor is enforced by CI as a required check (`Harness floor recompute`,
   `harness-floor.yml`, DISK) and recomputed from the diff; declared gear below the floor fails.
   The Gear ceiling, lane diversity, council quorum and appetite are lint rules inside
   `scripts/evidence_pack_lint.py` and run only on a Gear-3 pack, most as NOTICE, one (appetite,
   rule 14) as FAIL, all **ex post** — no rule limits consumption while work runs.
3. **The rule Fable's report proposes already exists twice** (`.claude/skills/workflow/SKILL.md`
   §1.1 since 2026-08-21; `~/.claude/hooks/model_routing_gate.py` Rule 1 since 2026-07-14) and is
   enforced preventively for the `Agent` tool only: the hook checks `tool_use.name == "Agent"`
   (DISK, line 495) and never sees a Workflow `agent()` call. A 35-agent run on 2026-09-05 inherited
   Fable 5.1 on all 35 agents (RUN, §5). The 113-agent run Fable cited did **not**: all 226 of its
   agent records ran on `claude-opus-5` because its script pinned `model:'opus'` on every call (RUN).
4. **The hierarchy pilot has already run** (2026-09-06 23:03Z → 2026-09-07 03:16Z): an Opus Dux, a
   Sol general, Fable and Astra checkpoints, W1 validator verified at fixture level F, W2
   (reviewer independence) built and unverified, a usage collector accepted at F — all in
   `.worktrees/ops-army-opus-general`, `ops-army-w1-assignment`, `ops-sol-usage-collector` and the
   design worktree's `pilot/` directory. **No PR exists for any of it** (RUN: `gh pr list --head`).
   The implementation plan's "Status: not started" and the mandate's "baseline documentale" are both
   stale by one night.
5. The fresh-session truth about roles is: RULINGS.md, modus, AGENTS.md §17.1, MODEL_ROSTER,
   FLEET_TOPOLOGY and the HOME hook all say **Opus 5 is the final on-disk gate for every gear and
   Fable is out of the workflow** (RULED 2026-08-20). The 2026-09-06 decisions (two equal generals,
   temporary Dux, no permanent Opus reviewer, Fable/Astra as imperators) live only in untracked
   design files and in draft PR #5821 — a fresh session loads none of them.
6. Cost is dominated by cache reads, which the workflow ledger does not count: the 113-agent run
   shows 11.77M `totalTokens` in its run record but 345.7M cache-read + 12.0M cache-write + 0.28M
   output tokens in its agents' native counters (RUN, §7).

**Answer to the closing question: realign and enforce what we have. Do not build a second
workflow.** The missing pieces are three small consumers and one settings correction, not a new
orchestrator (§8).

---

## 2. Map of the workflow in force — request → verified delivery

Each step: rule → caller → implementation → proof available → gap. "Active" means a consumer
executed it this session or CI/hook evidence shows it firing; "prose" means it exists only as text.

| # | Step | Rule (where) | Caller | Implementation | Proof | Gap |
|---|---|---|---|---|---|---|
| 0 | Session boot | `~/.claude/CLAUDE.md`, repo `CLAUDE.md` (Builder Contract), `cicatrix-superscar.md`, memory index; 4 project SessionStart hooks | harness | DISK `.claude/settings.json` hooks; `~/.claude/settings.json` `model=claude-fable-5-1[1m]`, `effortLevel=medium`, `modelSettings.claude-fable-5-1=high` | RUN (this session booted this way) | **M5 default model is Fable 5.1**, contradicting RULINGS "interactive default Opus 5" and memory 2026-09-02 that set `opus[1m]` fleet-wide. Any session opened without `--model`, and any child without a pin, is Fable. |
| 1 | Triage / Gear | modus STAGE 0; floor = `compute_floor()` from diff; ceiling = `compute_ceiling()` | session (provisional) + CI (deterministic) | `scripts/evidence_pack_lint.py:958-1111`; `harness-floor.yml` required check | DISK; branch protection has the job required (file header, measured 2026-08-27) | Ceiling/appetite only judged on Gear-3 packs; Gear 1/2 have no pack. |
| 2 | Ground | `/stadio-zero`, `reuse-first`, scar query; hook `stadio_zero_nudge.py`, `premise_gate.py` | session | HOME hooks (DISK list) | RUN (hooks listed) | Nudges, not blocks. |
| 3 | Design | `sota-architecture-loop`; council gate (3 external seats) only if divergent-priors ∧ cost>15× ∧ breadth | session | `COUNCIL_REVIEW_SEATS` (`evidence_pack_lint.py:2592`: codex-gpt-5.6-sol, kimi-code/k3, tp1-qwen3.8-max) via `council_journal.py:160` | DISK | Quorum only counted on Gear-3; seat availability: codex `UNKNOWN_ERR`, codex-spark `QUOTA_DEAD` (SessionStart digest, 22h-old probe). |
| 4 | Build isolated | worktree via `scripts/agent_start.py`; hooks `worktree_isolation.py`, `worktree_file_write_check.py` | session | RUN (this lane created by the broker) | RUN | — |
| 5 | Delegation | model pin mandatory: `/workflow` §1.1, hook Rule 1; routing floor Rule 2 | session | `model_routing_gate.py` (HOME == repo copy, RUN `cmp`) | RUN | **Gates only `Agent`.** Workflow `agent()` and `SendMessage` unguarded. Repo templates `verify-template.js` and `modus-bench.js` have 0 pins on 3 `agent()` calls each (RUN grep). |
| 6 | Verify (independent) | generator≠grader; Opus 5 xhigh final on-disk gate (modus VERIFY, RULINGS 08-20); Gear≥2 lanes + non-Anthropic builder when ≥2 build lanes | session | `check_lanes_build_seat_diversity` (`:2076`), enforcement date 2026-08-24; reviewer-independence: **only on the unmerged W2 branch**, NOTICE until 2026-09-21 | DISK | Independence of the reviewer from the author is not checked on main. |
| 7 | Ship + arm | Builder Contract 5; `mq arm`; CI required checks (11 contexts) | session | `harness-floor.yml` reads `harness/fable-gate` status posted by `scripts/harness_fable_gate.py` | DISK | Verdict **provenance** unchecked (any `statuses:write` token can post PASS) — open in PENDING-ARMS since 2026-08-10. |
| 8 | Prove-live / Bites | Contract 2 (`Bites:` line); `operations.md` §1bis executable `bites:` | session | 66 % of PR bodies carry it; **nothing reads any of them** (DISK `operations.md:52-55`); parser not on main | DISK | Closure proof is prose. |
| 9 | Continuity | PENDING-ARMS ledger, SessionStart receptors, Workflow replay | session/hooks | DOC: replay same-session or `claude --resume`; fresh session starts over | DOC + DISK | Cross-process durability = ledger + worktree, not runtime. |
| 10 | Capture | `mem save`, AMENDMENTS, scar | session | RUN (memory dir) | — | AMENDMENTS self-reports zero entries in the weeks it mattered most (`AMENDMENTS.md:90,96`). |

---

## 3. Matrix — preserve / correct / verify / add only if necessary

| Item | Disposition | Why (evidence) |
|---|---|---|
| modus loop, Gear floor in CI, evidence pack lint, worktree broker, PENDING-ARMS ledger, generator≠grader, prove-live | **Preserve** | Live, consumed, tested; the design package itself lists them as its reuse map. |
| `/workflow` §1.1 model-pin rule + `model_routing_gate.py` Rule 1 | **Preserve, extend consumer** | Rule and hook exist; the gap is coverage (Workflow tool), not doctrine. |
| Native Workflow runtime as the field fan-out arm | **Preserve** | Used 17× since 08-28, ledgered per run, resumable in-session (DOC). |
| M5 `~/.claude/settings.json` `model: claude-fable-5-1[1m]` | **Correct (owner)** | Contradicts RULINGS interactive default and the 2026-09-02 fleet-wide `opus[1m]` order; makes Fable the inherited default for every unpinned child. HOME file → operator action. |
| `workflowSizeGuideline: unrestricted` (`~/.claude.json`) | **Correct (owner)** | DOC default is `medium` since 2.1.219; `unrestricted` removes the size advice and the 25-agent warning replacement. |
| `modelSettings.claude-fable-5-1.effortLevel: high` while the imperator is "requested xhigh" | **Verify, then owner decides** | Transcript of the imperial session `3901f1be` records `effort: xhigh` on its assistant records (RUN) — so the live imperial window is xhigh despite the saved `high`; a *new* Fable window would boot at `high`. |
| "Opus 5 final on-disk gate, all gears" in RULINGS/modus/AGENTS/MODEL_ROSTER/FLEET/hook docstring | **Correct together, one PR, with the consumer tests** | Zero eliminated "Opus revisore finale permanente"; six doctrine surfaces still load it into every fresh session. `test_gate_seat_conformance.py:83` anchors `retired_model()=="claude-fable-5"` on RULINGS — migrate doctrine and test atomically. |
| `max` vs `xhigh` for the gate | **Correct** | RULINGS line 20 and FLEET `gear3_final_gate.effort` say `max`; RULINGS line 32, modus, MODEL_ROSTER line 261 say `xhigh`. Same file disagrees with itself. |
| `harness/fable-gate` status name + `check_worker_plane_review.py` "sequential Fable 5 final gate" docstring | **Verify → rename or annotate** | Name is historical (documented); the worker-plane validator still describes a Fable gate as the thing to implement. |
| Reviewer-independence check (`review_eligibility.py`, W2 branch) | **Verify by a non-contributor, then land** | Built, consumer wired (`evidence_pack_lint` +181), NOTICE-only until 2026-09-21, no eligible verifier on the pilot's front. |
| W1 assignment-graph validator (`army_assignment.py`) | **Land as fixture-level F; do not call it active** | No consumer executes plans. |
| `seat_usage_collector.py` streaming-usage fix (ops-sol-usage-collector) | **Land** | Accepted at F by Astra; the 852 vs 14,931 output-token defect is real (RUN-equivalent in Astra's record). |
| Two-consul ruling (PR #5821, draft) | **Owner decision first** | Grants Fable + Astra "merge, deploy, every authorization"; the ledger row says doctrine-only and asks Zero whether the Opus gate stays mandatory. It also conflicts with the imperator model (few interventions) unless "consul" ≠ "imperator" is stated. |
| Aggregate cross-window capacity account, admission with reservation/expiry, message ack semantics, PII class per packet | **Add only if the pilot proves the gap** | Nothing native provides them (DOC); the pilot already observed one reservation race and one stale-delivery-as-delivered case — both were *discipline* failures a file-based ledger would have caught. |
| LangGraph / Agent Framework coordinator | **Do not add now** | §9 below. |

---

## 4. Contradictions, ordered by impact (file:line verified this session)

1. **Fresh sessions load the eliminated rule.** `docs/rules/RULINGS.md:13-14,20,32`; `.claude/skills/modus/SKILL.md:88,134,164-166`; `AGENTS.md:822,836`; `MODEL_ROSTER.md:31-32,261-263`; `FLEET_TOPOLOGY.json._invariants[0]`, `role_chains.gear3_final_gate`; `~/.claude/hooks/model_routing_gate.py:6-12` — all: "Opus 5 final on-disk gate, all gears; Fable out of the workflow." Zero's 2026-09-06 decisions exist in untracked files (`workflow-spec.md` §2 precedence table) and draft PR #5821. Impact: every general, builder and grader booted today follows the old hierarchy by default.
2. **The interactive default on M5 is Fable 5.1** (`~/.claude/settings.json` `model`, RUN), against RULINGS.md:20 ("interactive sessions = Opus 5") and the memory record of the 2026-09-02 fleet-wide reset. Every unpinned child inherits it; the 35-agent 3.5M-token inherit run on 2026-09-05 is the measured consequence.
3. **The model-pin rule has no consumer on the tool that fans out.** `model_routing_gate.py:495` (`if name != "Agent": continue`) vs `/workflow` SKILL §1.1 ("PIN model on EVERY agent() call"). The repo's own `infra/workflows/verify-template.js` and `modus-bench.js` violate the rule (0 pins / 3 calls each, RUN).
4. **Two-consul ruling vs imperator model vs shipping fence.** PR #5821 (`AGENTS.md` §17.1a draft): Fable 5.1 and Astra "full and equal powers: merge, deploy, every authorization"; `workflow-spec.md` §3: imperators "do not run builder/support fan-out … or implement the mission"; Builder Contract 5 / FLEET `_invariants[5]`: "No external seat ever merges or deploys." Three texts, three answers about who ships. Only the Builder Contract is on main and machine-compared.
5. **`max` vs `xhigh` for the final gate** inside one file: `RULINGS.md:20` ("effort `max`") vs `RULINGS.md:32` ("`xhigh` … `max` is opt-in"); `FLEET_TOPOLOGY.json` chain says `max`; modus and MODEL_ROSTER:261 say `xhigh`.
6. **Implementation plan says "not started"; the pilot ran.** `implementation-plan.md:3` vs `docs/army-pilot/CHECKPOINT.md` (24 commits, 2026-09-06 23:03Z → 09-07 03:16Z) and `pilot/appointment.md` (`w0-nomination/1`, Dux = Opus, both imperator approvals recorded by Astra). The baseline manifest `319ab909…` was frozen and used; `workflow-baseline.json` `runtime_activation:false` is still true, but "documentary" understates it: W1 is fixture-verified code.
7. **Budget language.** modus `SKILL.md:40-49` is explicit that appetite is "EX-POST … NEVER AN IN-FLIGHT BREAKER"; `workflow-spec.md` §4 speaks of "atomic reservation of the whole descendant tree". The only in-flight limits that exist are the runtime's own (16 concurrent, 1,000/run, 20 subagents/session, depth 3 — DOC) and a `budget.total` directive if a script declares one (DOC via `/workflow-authoring`). The pilot's "cap 4 non-imperial seats" was a written convention that the Dux itself violated once (reservation race, `astra-recovery-handoff.md`).
8. **Bites is a sentence.** `operations.md:52-55`: 66 % of bodies carry a `Bites:` line and no file reads them; the executable form's parser is not on main. Closure proof at step 8 is therefore whatever the session writes.
9. **Verdict provenance.** `harness-floor.yml` header ("STILL OPEN … any credential with `statuses: write` can post PASS on any SHA") — the required check trusts an unauthenticated commit status for Gear-3 merges.
10. **HOME hook ahead of main.** `~/.claude/hooks/orchestrate_gate.py` == the `ops-army-w1-assignment` copy (2026-09-07 SendMessage fix) ≠ `infra/claude-hooks/orchestrate_gate.py` on main (35 diff lines, RUN). Correct if the PR lands; scar #1 shape if it does not.
11. **Fable's report counts 4 runs; the ledger holds 17**, and the run it treats as the imperial fan-out was launched by a *separate* Zero-opened field session (§5).

---

## 5. Critical review of Fable's 2026-09-07 report (`2026-09-07-dynamic-workflows-fable.md`)

Verified as correct (RUN/DOC): the runtime primitives, no shell/FS from the script, per-call model
and effort, the model-precedence order, 16-concurrent / 1,000-per-run / 4,096-per-list limits,
5-minute cache TTL with `subagentPromptCacheTtl`, the 5,000 ms stagger, the same-session resume rule
including "fresh session starts over", the 25-agent / 1.5M advisory warning, `tengu_workflows_enabled`,
`workflowSizeGuideline: unrestricted`, `hasExtraUsageEnabled: false`, `modelSettings` values, and the
absence of `.claude/workflows/`.

Corrections, in the order the mandate lists them:

- **"Not durable across a crash" is half right.** DOC: saved results live under the session directory and a session resumed with `claude --resume` "can replay them"; a *fresh* session starts over. Replay is order-based, not content-addressed. So durability = the session directory, and recovery cost = everything after the first failed/changed agent. LangGraph's checkpointer changes the granularity (per node) and the process boundary, not the exactly-once problem.
- **`defaultModel` ≠ effective model — Fable stated the caveat, then inferred past it.** RUN: `defaultModel` is the session model in all 17 records; per-agent `.meta.json` carries the effective `model`. The 113-agent run (`wf_475589ee`) has 226 agent records, all `opus`; its script pins `model:'opus'` on all 3 `agent()` calls. The "imperial fan-out on the imperial model" happened on a different run: `wf_6d2c6245` (session `d74dbe13`, 2026-09-05 00:01Z, 35 agents, 70 records with no `model` key = inherited `claude-fable-5-1`, 3.52M `totalTokens`). Fable's §3.3 risk ranking is right for the wrong run.
- **Which session, and was it imperial?** RUN: `7561e9d7` (15 runs) began with Zero's own mandate "tu in questa sessione e codex astra ultra in altra window collaborate per completare le oper /garuda_voa /secondhome /visaoracle…". That is an owner-opened Fable session acting as a *field conductor* with Astra, one day before the imperator/general split was written. Not a violation of a rule that did not yet exist; a violation of the 2026-08-20 "Fable out of the workflow" rule by the owner's own choice, which the rule permits. The imperial session is `3901f1be` (79 responses, 130k output tokens, RUN), separate.
- **Cumulative agent count vs concurrency.** `agentCount` (113) is cumulative `agent()` resolutions; runtime concurrency on M5 is capped at min(16, CPUs−2) = 8 (Fable's own OBS). The 113 agents ran over 199 minutes; the run never had more than 8 live. Astra's "hard cap on descendants" and Fable's "113-agent fan-out" describe different quantities.
- **Two ledgers summed ≠ admission.** Fable's Q2 to Astra ("two file readers and a sum") would give an *after-the-fact* total; the spec's admission needs reservation before spawn, release on close and expiry. The pilot's own reservation race shows the difference is not academic.
- **Delivered vs received vs accepted vs completed.** DOC: `SendMessage` is acknowledged only as "sent to inbox"; the pilot recorded "a published file was treated as delivered" (`astra-recovery-handoff.md`, Failures table). Fable's mapping table is right that nothing native records ack; the runbook's "file prepared / delivery unconfirmed" wording is the current control.
- **Cache reuse conditions.** DOC confirms the six-field prefix rule (model, effort, agent type, tools, output schema, working directory) and that `isolation: 'worktree'` breaks sharing. Fable's INF is correct. What the report did not say: cache *reads* are where the tokens are (§7), so a pin change or worktree isolation that breaks sharing costs far more than the output it protects.
- **Effort discrepancy.** Fable's own report session showed `high`; the imperial session `3901f1be` shows `xhigh` on every assistant record (RUN). Both can be true (different windows). The saved `modelSettings` value governs *new* windows; `/effort` in a live window governs that window. The runbook's rule (record a named source, else `unverified`) is the right one; Fable's N1 retraction ("transcript effort field is a same-session observation") is correct.
- **§7 proposal is a rewrite of an existing rule.** The rule is `/workflow` §1.1 (2026-08-21) plus hook Rule 1 (2026-07-14). What is missing is the consumer for the Workflow tool and a lint over `wf_*.json` / `agent-*.meta.json`. Fable's report says so in §10 ("has no consumer until someone writes it") but presents it as new.

---

## 6. Meta-pattern — the setup error that generates most of the problems

**Decisions are written where only a reader can evaluate them, and defaults are set where only a
machine does.** Every contradiction in §4 has this shape: the hierarchy lives in prose (untracked
files, a draft PR, a spec that says "specified, not activated"), while the thing that actually
selects a model, an effort or a reviewer is a default in `~/.claude/settings.json`, a hook that
matches one tool name, a lint that runs only on Gear-3 packs, or a commit status anyone can post.
The organism already named this disease — modus's Qwen row ("A conditional written where only a
reader can evaluate it does not update itself"), superscar #2 (exists ≠ armed), the Bites finding
(66 % prose, 0 readers) — and the design package repeats it: nine documents, one manifest of hashes,
`authority: none`, and a pilot that then ran under "declared working convention" and hit exactly the
failures a machine would have refused (reservation before spawn, delivery ≠ receipt, rc=66 on a dirty
tree treated as a result). The corrective is not more doctrine: it is to move each rule to the
single place where the thing it governs is chosen, and delete the copies.

---

## 7. What the structure costs — native counters, no conversions

All figures RUN this session from `message.usage`, deduplicated on `(message.id, requestId)`,
summed per file. Token volumes, not prices; subscription burn is not inferable from them.

| Surface (session / run) | Responses | Uncached input | Cache write | Cache read | Output |
|---|---|---|---|---|---|
| `7561e9d7` main window (field Fable, 15 workflows launched) | 523 | 12,308 | 3,211,493 | 146,259,248 | 583,101 |
| `wf_475589ee` 113 agents, all `claude-opus-5` | 4,911 | 9,822 | 11,956,163 | 345,717,059 | 278,450 |
| `d74dbe13` main window (Fable) | 219 | 5,684 | 1,261,865 | 44,486,389 | 287,419 |
| `wf_6d2c6245` 35 agents, all inherited `claude-fable-5-1` | 643 | 19,398 | 3,409,621 | 41,771,824 | 10,359 |
| `3901f1be` imperial Fable window | 79 | 1,666 | 619,176 | 19,009,193 | 130,755 |

Readings:

- The run record's `totalTokens` (11,768,195 for the 113-agent run) is close to cache-write + output
  (12.23M) and **excludes the 345.7M cache-read tokens**. Its exact formula is not documented; treat it
  as a relative size signal, never as consumption.
- Coordination and waiting are visible as cache reads: each agent turn re-reads its whole prefix. An
  orchestration that keeps agents alive for many short turns pays in cache reads; one that gives
  each agent one long task pays in cache writes. Neither shows in `totalTokens`.
- Boot cost per Claude child is the CLAUDE.md hierarchy plus definition (DOC; measured ≈5.6k content
  tokens in `context-by-level.md` §1) — paid as cache write once per distinct prefix, then as cache
  read per turn.
- Retries: not separable from these counters. The Workflow journal (`journal.jsonl`) and
  `agent-*.meta.json` record results and models, not attempts.
- Reasoning: Claude Code `usage` does not split thinking from output; RULINGS.md:32 cites an
  audit measuring ~86 % of Opus 5 output as thinking — a separate measurement, not this one.
- Per-model share on this machine is a collector job (`seat_usage_collector.py`, whose streaming
  fix is accepted at F on `ops-sol-usage-collector` and not merged).

---

## 8. Minimum realignment plan (not executed)

Ordered by leverage; each item names its consumer, because that is the point.

1. **Owner, HOME:** set `~/.claude/settings.json` `model` to the intended interactive default on
   M5 (RULINGS says Opus 5; if Zero wants Fable for imperial windows, open them with `--model`), and
   `workflowSizeGuideline` back to `medium` or `small` in `~/.claude.json`. Two values, no PR.
2. **One doctrine PR:** replace "Opus 5 final on-disk gate, all gears / Fable out of the workflow" in
   RULINGS, modus, AGENTS §17.1, MODEL_ROSTER, FLEET_TOPOLOGY and the hook docstring with the settled
   statement (independent verification is an assignment; the seat is chosen by the general with
   recorded non-authorship; no model holds it by title), resolve `max`/`xhigh` once, and update
   `test_gate_seat_conformance.py` in the same diff. Fold PR #5821's consul text in only after Zero
   answers the open question in its ledger row.
3. **Extend the existing consumer, not a new one:** `model_routing_gate.py` also matches `Workflow`
   tool calls and refuses a script whose `agent(` calls lack `model:` (static regex over the script
   text, same fail-open discipline); pin `model` in `verify-template.js` and `modus-bench.js`. Add a
   ledger lint over `~/.claude/projects/**/subagents/workflows/*/agent-*.meta.json` that reports
   records with no `model` key (= inherited) — the file the runtime already writes.
4. **Land the pilot's three artifacts at their real level:** W1 validator (F), usage collector (F),
   W2 reviewer-independence (needs one non-contributor verification first; Sol is named). Open the
   PRs from the existing worktrees; do not re-derive them.
5. **Close the two "nobody reads it" gaps that already have specs:** verdict provenance on
   `harness/fable-gate` (ledger 2026-08-10 gap b) and the `bites:` parser (operations.md §1bis).
6. **Only then** decide whether an admission/reservation service is needed — after the pilot rerun
   in §9 shows whether a file-ledger discipline suffices.

Not in the plan: LangGraph, Agent Framework, CrewAI, a second scheduler, a new "army" runtime. The
backend's LangGraph dependency (`kg_langgraph_orchestrator.py`, `checkpointer.py`) stays a backend
concern.

---

## 9. A falsifiable pilot — limits and criteria fixed before the test

**Hypothesis H1:** with items 1–3 of §8 in place, a Claude-first shallow field team (one general,
≤4 non-imperial seats, pinned models, file-ledger reservations) completes a frozen Gear-2 task with
zero inherited-model agents, zero reservation violations and a closure observation a script reads.
**H1 is falsified if** any agent record lacks `model`, or the ledger shows a slot used before its
reservation line, or closure is asserted without the `bites:` observation exiting 0.

**Hypothesis H2:** an aggregate-capacity/admission service is unnecessary at this scale.
**H2 is falsified if**, over the same task, two windows on one account each hit a provider limit
that a shared reservation would have prevented (evidence: `429`/limit lines in both transcripts
within the same minute).

Fixed before the run: task = one non-PII, non-hot-zone Gear-2 fix with an existing failing test;
base revision frozen; ceiling 4 seats; effort per seat recorded from `effort` transcript fields;
`workflowSizeGuideline` recorded; cache TTL default; no `isolation: 'worktree'` for siblings that
should share a prefix; interruption fixture = stop one agent, relaunch with `resumeFromRunId`, count
rerun agents from `journal.jsonl`; orphan fixture = agent starts `sleep 300 &`, session exits with
"Exit and stop tasks", `pgrep` after. Record: native counters per surface (as §7), wall time,
retries, residual processes, operator interventions. One run is a feasibility observation.

---

## 10. Decisions that stay with Zero, and open questions

1. Interactive default on M5: Opus 5 (doctrine) or Fable 5.1 (current file)? And the same on Pro/Mini.
2. PR #5821: does the Opus 5 xhigh on-disk gate stay mandatory for consul-shipped work, or does the
   cross-consul review replace it? (Its own ledger row asks this.) And is a "consul" the same seat as
   an "imperator" — if yes, "merge, deploy, every authorization" contradicts "few interventions".
3. The 2026-09-06 Sol window widening to `danger-full-access` (`fable-checkpoint-3.md`): was it a
   manual selection in the Codex window? Until answered, Sol's effectful work stays on the child path.
4. Effort for imperial windows: `xhigh` requested; `modelSettings.claude-fable-5-1` saved as `high`.
   Change the saved value or launch with `--effort`?
5. Whether the 2026-09-05/06 Fable field sessions (17 runs, ~12M cache-write tokens) are the
   intended use of the seat — the 2026-08-20 ruling allows it, the 2026-09-06 spec discourages it.
6. Owner-only: the PENDING-ARMS `operator[business]` rows this audit touched are unchanged.

---

## 11. Conclusion

**Riallineare e far rispettare quello che abbiamo.** The loop, the gears, the isolation, the
independent verification, the ledgers and the native fan-out all exist and mostly work; the pilot
has already run once under them. What does not exist is one place per rule. Three consumers
(Workflow-tool model check, reviewer independence, bites parser), one doctrine PR and two HOME
values close the measured gaps. A new workflow would inherit every one of them.

## 12. Not done, not claimed

No test was run; no acceptance row A01–A30 is passed; no route is qualified; no percentage or
currency figure is derived; Pro and Mini were not read (Pro unreachable per the 2026-09-06 healer
tick); per-agent transcript content was not read. The `wf_*.json` `totalTokens` formula is unknown.
`seat_usage_collector.py` was not executed. Fable's report and the design package were not modified.
