# Subagent workflow discussion — 9 September 2026

Status: consultation complete after three rounds; no installed controls changed.

## Final agreed position

Fable 5.1 and Codex reached the following position after source review,
synthetic counterexamples, objections and two revisions. Runtime records
confirm `claude-fable-5-1` and `xhigh` in all three rounds of the same session.
The later corrections below supersede the initial suggestions in the discussion
transcript. In particular, parent-transcript fallback, warning-only enforcement
after repeated denials, unconditional survival of accepted continuations, and
classification by absence of Edit/Write calls were rejected.

| Point            | Agreed decision                                                                                                                                                                                             |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Child mandate    | Keep a small explicit contract: objective, write scope, expected result, relevant constraints and meaningful checks. Observe actual identity/model/effort; assign task role within the coordinator's scope. |
| Context budget   | Keep current 20/40 policy pending measurement. Resolve identity, transcript and window for the child; missing evidence is UNKNOWN, never the parent's state.                                                |
| Continuation     | Workers return checkpoints to their parent; they never trigger a parent jump or silently start their own replacement chain. Top-level continuation retains a separate lifecycle.                            |
| Concurrent edits | Coordinator obtains supported worktree isolation through the existing broker, or serializes writers. All mutation channels count. Unknown/read-only workers never clean another worker's files.             |
| Completion       | Distinguish transport completion, claimed mandate completion and independent verification acceptance. Evidence must cover the expected result and exact artifact; unfinished work survives replacement.     |
| Execution limits | Account for attempts, retries, replacements, depth, deadline and concurrency under the parent mandate. Cancellation has a verified owner; inactivity alone is not death.                                    |

### Proposed order — not installed

1. **Claude child isolation:** repair child-specific anti-loop markers and intent
   handling; prevent child activity from creating parent jump/handoff artifacts;
   resolve child context and role without inherited-parent shortcuts. Keep the
   dirty-state reminder separate from verification acceptance.
2. **Codex child and continuation lifecycle:** capture native child payloads in
   a plain session and inside a continuation, then implement the needed identity
   adapter. Replace the idle-timeout assumption with owned, deadline-aware
   liveness/cancellation. Record incomplete transfers as needs_attention.
3. **Shared coordinator contract:** reuse the existing policy, broker and
   coordinator artifacts for mandates, budget accounting and independent result
   verification. No new daemon or orchestration framework is proposed.

Shared rules should guide the patches from the start even though their durable
coordinator package is listed third. Missing child identity, incomplete logs,
unreadable transcripts and unknown windows must remain visibly unverified.

### Verification needed before declaring coverage

- Synthetic guilt/innocence tests plus actual native payload captures; a test
  must distinguish a child from its parent and from every sibling.
- A child reaching its budget must return incomplete work without overwriting
  parent artifacts, starting an autonomous replacement, or weakening a deny.
- Timing tests with injected short intervals and a bounded real canary; verify
  cancellation, failed transfer, incomplete checkpoint and stale receipts.
- Parent -> child -> verification -> return must succeed separately for both
  harnesses on Air-M5, Pro and Mini, and in new Codex app tasks. Check source,
  installed copy and actually executed hook parity. Existing tasks are not
  retroactively covered by a new configuration.

No universal subagent coverage claim is justified today. The earlier Codex
installation remains a verified set of specified top-level paths; this review
does not extend that evidence to every native child or profile.

Only this discussion artifact was added to the prepared adapter worktree.
No hook, policy, setting, tracked implementation file, merge or deployment was
changed during the consultation.

## Mandate and scope

Antonello requested an actual discussion with **Fable 5.1, xhigh effort** before
acting on the six proposals below. This is an independent architecture review,
not implementation, deployment, or a request for agreement. Challenge the proposals
against the existing workflow. Keep a distinction between observed runtime,
source evidence, documented platform behavior, and untested inference.

The fleet is Air-M5 (thin client), Pro, and Mini. The existing workflow assigns
orchestration to Fable/Astra and uses independent builders and verifiers. Do not
invent a permanent privileged model as final grader: generator must differ from
grader, and capability/role must be distinguished from vendor identity.

Do not edit files, execute commands, delegate, install, merge, deploy, or send
messages. Read the scoped adapter and hook sources if useful, and return your
review in English. The caller will append the discussion to this artifact.

## Current evidence

The Codex adapter is in this directory. Read `ROLLOUT.md`, `README.md`, and
`context_bridge.py` for the implementation and its verification limits.

- Commit `471a0cb32d` installed six events on three hosts / seven profiles:
  SessionStart, PreToolUse, PostToolUse, PreCompact, PostCompact, Stop.
- The primary profile on each host exercised a real Astra session and two
  consecutive fresh-session continuations, plus failed-launch source retention.
  Eighteen regression tests pass. The final added unacknowledged-child guard has
  regression and installed-hash evidence; positive live probes preceded that
  final guard. Secondary profiles have configuration/trust checks only.
- A continuation carries mandate, steering, checkpoint and source/destination
  nonce binding. The source stops only after destination acknowledgement and an
  actual model/tool event. It preserves model, effort and permissions. Maximum
  continuation hops: three; acknowledgement timeout: 45 seconds.
- Verification receipts bind executed checks to file fingerprints. They are not
  semantic review or proof of deployment. Stop blocks once then warns.
- New sessions load these hooks. Existing sessions, including this Codex app
  task, were not restarted. Isolated nightly autofix ignores user configuration
  and remains outside this installation. Other memory-writing hooks are not
  serialized by this adapter.
- **This validates fresh-session continuation, not ordinary spawned workers.**
  The adapter registers neither SubagentStart nor SubagentStop, keys state by
  `session_id`, reads `transcript_path`, and takes role from inherited environment
  (`CODEX_CONTEXT_ROLE`, then `CONTEXT_GUARD_ROLE`). It does not handle `agent_id`
  or `agent_transcript_path` explicitly.
- The final guard rejects PreToolUse/Stop when CODEX_CONTEXT_FROM_SESSION is set
  but the current state has no matching from_session. Effects on native workers
  spawned inside continuations are untested; do not assert a reproduced failure.
- Air-M5 installed Claude hook:
  `/Users/balizero/.claude/hooks/subagent_stop_verify.py`, lines 168 onward,
  obtains `payload.transcript_path`, derives its one-shot anti-loop marker from
  that path, and searches the same transcript for intentional-dirty exemptions.
  It does not use `agent_id` or `agent_transcript_path`. Thus the source appears
  to share parent-based exemption/marker state across siblings under the
  documented SubagentStop payload; this has not been reproduced live yet.
- Air-M5 installed Claude context hook:
  `/Users/balizero/.claude/hooks/context_window_guard.py`, lines 421 and 537 onward,
  uses inherited CONTEXT_GUARD_ROLE and payload.transcript_path, with no explicit
  child identity. Per-child context measurement remains to be tested. Repository
  hook source differs from the installed copy; do not assume source parity.
- These Claude observations cover Air-M5, not a fresh fleet-wide Claude audit.

Official documentation retrieved for this review:

- https://learn.chatgpt.com/docs/agent-configuration/subagents
- https://learn.chatgpt.com/docs/hooks
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/hooks

Both platforms document SubagentStart and SubagentStop. A SubagentStop payload
distinguishes the parent session/transcript from agent_id and
agent_transcript_path. Start cannot block; Stop can request child continuation.
Inheritance of settings or permissions is not proof that our adapter correctly
handles child identity, transcript accounting, or lifecycle events.

## Six proposals to challenge

1. **Explicit child mandate:** objective, assigned files, expected output, role,
   effective model and relevant constraints. What is the minimum enforceable
   contract, and which fields should be observed rather than self-declared?
2. **Individual context budget:** current local policy is 20% for imperators and
   40% for other roles. A child must not inherit imperator rank accidentally.
   Challenge whether these thresholds are justified for workers; distinguish
   current policy from evidence-based tuning and account for real model windows.
3. **Controlled continuation:** a worker at its threshold checkpoints and returns
   to the coordinator, which decides replacement. Avoid autonomous reproduction,
   orphan workers and loss of parent-child relation. Distinguish ordinary spawn
   from a continuation of the same mandate. Address parent unavailability and
   whether a blocked Stop could cause a context-exhaustion loop.
4. **Concurrent editing:** explicit file ownership; separate worktrees where
   actual isolation is necessary. Read-only workers should not need worktrees.
   Prevent sibling-state contamination and accidental undo of others' changes.
5. **Evidence-based completion:** diff, actual checks, remaining issues and an
   independent verifier. Neither a child saying done nor a clean working tree
   proves correctness. Keep operational gate semantics separate from advisory
   reminders and respect the external-builder ship restrictions.
6. **Bounded execution:** explicit concurrency, depth, retries and cancellation
   ownership; inherit the parent's remaining budget rather than resetting it at
   every child/replacement. Reuse native controls where available.

## Questions for Fable — round one

For EACH point, give KEEP / REVISE / REJECT and a concrete reason tied to this
setup. Identify the highest-risk missing cases and weak assumptions in my
proposal. Recommend the smallest ordered changes, specifying which belong in
shared policy, Claude hooks, Codex hooks, and coordinator instructions.

Define a minimal parent -> worker -> verification -> return test matrix for
both runtimes, with failure cases that would falsify coverage. Explain what
must pass before rolling out to all three machines. Avoid a new orchestration
framework, universal threshold claims, or treating all children as independent
imperators. Mark uncertainties and what must be measured.

Your response will be followed by a second round in this same consultation.

## Evidence added while round one was running

Consultation identity: Claude Code 2.1.266 on Air-M5, session
`f46bded4-0f74-4b46-b30b-ef8e98611c00`. The runtime initialization and assistant
message model fields both report `claude-fable-5-1`; assistant records in the
native session transcript report `effort: xhigh`. The process was launched with
the existing OAuth setup, no paid API key, read-only tools (Read/Grep/Glob), plan
permission mode, and no MCP servers. No fallback model was configured.

Codex ran a synthetic-payload counterexample against the **installed** Air-M5
Claude `subagent_stop_verify.py`. Git status was mocked to one dirty synthetic
file; transcripts and marker files lived in a disposable temporary directory.
No installed hook or repository source was modified.

1. Two payloads shared a parent session/transcript but had distinct agent IDs
   and distinct child transcript paths. Both had `stop_hook_active: false`.
   First child returned exit 2 (blocked), second returned exit 0 (allowed).
2. After removing the temporary markers, the parent transcript alone mentioned
   an unrelated checkpoint. The child transcript contained no intent marker.
   That child returned exit 0 (allowed).

These reproduce source behavior under the documented payload shape. They are
**not a native-runtime parent/worker integration probe**, and do not establish
fleet-wide Claude parity.

## Fable — round one response

[M5] Review done. Sources read this turn: `context_bridge.py`, `test_context_bridge.py`, `ROLLOUT.md`, `README.md`, the live `hooks.json` and policy file under `~/.codex`, the live `subagent_stop_verify.py`, `context_window_guard.py`, `orchestrate_gate.py`, and the live `settings.json` SubagentStop block. Tags: [runtime] observed on disk now, [source] read in code, [docs] platform documentation as cited in your brief, [inference] untested reasoning.

## Verdicts

**1. Explicit child mandate: REVISE.** Keep the contract, but split it into two halves. Coordinator-authored and self-declared: objective, write set, verification argv list, return shape, hop number. Observed and never trusted from the child: model and effort from the child's own transcript, paths actually changed by git, receipts, token usage. The minimum enforceable contract today is small: a fixed header in the spawn prompt plus a SubagentStop comparison of changed paths against the declared write set. Role must be observed, not declared or inherited. `orchestrate_gate.py:126-136` already derives "inside a subagent" from `agent_id` or a `subagents/` path component [source, with live evidence dated 2026-08-21 in its docstring]. Reuse that helper; do not add a second detector.

**2. Individual context budget: REVISE.** The 20/40 split is policy from the 2026-09-09 mandate, not measurement, and both runtimes state it as such [source: `context_window_guard.py:37-43`, `nuzantara-context-policy.json`]. The inheritance problem is real at source level in both runtimes: the Codex adapter reads the role from environment at SessionStart (`context_bridge.py:431-438`) and the Claude guard reads it from environment on every call (`context_window_guard.py:420-429`). A hook process inherits the harness process environment, so a child of an imperator seat is measured at 20% [inference, not reproduced]. Two further defects matter more than the number:

- The Claude guard never fires before 30 assistant turns (`GRACE_TURNS`, line 123). A worker that reads large files can cross 40% in a handful of turns, so most workers are never measured at all [inference].
- The window comes first from `CONTEXT_WINDOW_TOKENS` (line 381). The fleet message today says the escape one-liner writes that override into the seat's settings. A 200K child under a 1M seat is then measured against 1M and is never gated [source + inference].
  Codex measures the real reported window (`context_bridge.py:139-149`), which is the right shape. Do not tune thresholds yet. Measure child usage first: the `subagents/*.jsonl` transcripts are on disk on M5 and give a distribution per model.

**3. Controlled continuation: REVISE, and it is the highest-risk item.** The distinction you want is correct: a continuation replaces a session on the same mandate; a spawn creates a child under a parent. The current hooks conflate them:

- In the Claude guard, the pending-jump file and the handoff artifact are keyed by `session_id` (lines 200-203, 176-178, 273, 460). If a child's PreToolUse payload carries the parent's `session_id` as documented [docs], a child crossing its threshold writes the parent's handoff, raises a jump for the parent, and on a Ghostty seat spawns `window_jump.sh` against the parent's window (lines 304-311). The mandate it records is the child's first prompt, not the parent's. This is source-level inference, not reproduced, and it is the one case I would test before anything else, with `CONTEXT_JUMP_NO_SPAWN=1` set.
- In the Codex adapter, an accepted destination is killed by the bridge's own idle timeout: after acceptance the reader waits 600 seconds for any event (line 681-685), raises, marks `needs_attention`, and the `finally` block terminates the destination (lines 717-731). A verify call may legally run eight commands at 300 seconds each. By then the source has already stopped. Result: both sessions gone, state says needs_attention, nobody reads it. This is the concrete orphan case [source].
- The unacknowledged-child guard (lines 346-355) denies every tool to any session whose state lacks a matching `from_session` while `CODEX_CONTEXT_FROM_SESSION` is inherited. A native worker spawned inside a continuation with its own `session_id` would be walled [inference]. Until measured, coordinator instruction: no native subagents inside a continuation.
- Blocked-Stop loop: bounded in both runtimes via `stop_hook_active` (`context_bridge.py:477-482, 503-505`; `subagent_stop_verify.py:165-171`). The unbounded phase is before Stop: every denied PreToolUse returns the instruction text and the model may retry indefinitely. Count denies in state and downgrade to warn after a small N.
- Stop hook timeout is 60 seconds live, above the 45-second handshake [runtime: `hooks.json:187`]. Fine.

**4. Concurrent editing: KEEP.** The receipt design proves your point for you: the fingerprint hashes HEAD, the full diff, and every untracked file's contents (`context_bridge.py:87-107`). In a shared checkout, any sibling edit invalidates a passing receipt and Stop blocks the innocent child (lines 495-505). Writers therefore need their own worktree; read-only workers do not change the fingerprint and can share. Two contamination paths are in the Claude SubagentStop hook: the once-only marker is derived from `transcript_path` (lines 64-68), and the intent-marker search reads the same transcript (lines 93-104). Under the documented payload that is the parent's transcript [docs], so the first blocked child spends the block for every sibling for 24 hours, and one sibling's "wip:" exempts all. Not reproduced live. Reuse the broker for isolation: `scripts/agent_start.py` already refuses nested worktrees and has RAM admission (`_refuse_if_nested`, `check_ram_admission`).

**5. Evidence-based completion: KEEP.** Codex has an operational gate: Stop blocks once without a current passing receipt. Claude has no receipt at all: the live SubagentStop registration holds only `subagent_stop_verify.py` [runtime: `settings.json:546-556`], which checks dirtiness and nothing else. `session_budget.py` in the repo writes a diff-stat handoff on SubagentStop but is not registered live on M5 [runtime]. That is scar #2, Esiste≠Armato. Keep gate semantics where they are: exit 2 on SubagentStop is the gate, systemMessage and additionalContext are advisory. Independent verification must be a different seat re-running the declared commands, not a privileged model. The Codex continuation wrapper already forbids merge and deploy (lines 638-643); keep receipts as work evidence, never as a ship gate.

**6. Bounded execution: REVISE.** Native controls cover more than the proposal assumes. Claude depth is 1 by harness construction per the 2026-08-21 note in `orchestrate_gate.py:38-41`, to be rechecked on the current version. Both chains cap at 3 hops (`JUMP_MAX_HOPS`, `max_hops`). The reset you describe is real: a Codex worker starts a fresh chain at hop 0 while a continuation inherits hops (`context_bridge.py:428`). In Claude, if the child sees the parent's `session_id`, `_chain_link` already returns the parent's chain [inference], so hop inheritance is accidentally right and jump writing is wrong. Cancellation: Claude parent owns it through TaskStop. Codex has no cancel path for an accepted destination; the bridge does not even record the `continue` process pid. Record it, and document that killing that process ends the destination through the broken pipe.

## Ordered smallest changes

1. **Shared policy** (`docs/rules/operations.md`): role is observed from child identity, never inherited; a child never raises a jump or writes a parent artifact; a child at threshold returns a checkpoint and the coordinator decides replacement; hops carry across replacement; writers get worktrees, readers share; completion is diff plus receipt plus re-run by a different seat.
2. **Claude hooks**, both with guilt and innocence tests in `infra/claude-hooks` and live==repo parity: in `context_window_guard.py`, key handoff and jump on `agent_id or session_id`, skip jump and parent handoff when `agent_id` is present, ignore the env window override for children, and use a lower grace for children only after measurement. In `subagent_stop_verify.py`, use `agent_transcript_path or transcript_path` for marker and intent scan.
3. **Codex hooks**: never terminate an accepted destination; record `continue_pid`; count denies; add a read-only listing of `needs_attention` states to `installation_status.py` rather than a daemon.
4. **Coordinator instructions**: mandate header template, checkpoint-only returns, no native subagents inside continuations until C1 and C2 below are measured, verification by a different seat.

## Test matrix, rollout gate, and open measurements

Claude, on M5 first, with `CONTEXT_JUMP_NO_SPAWN=1`:

- T1 identity: one Haiku worker runs one Bash. Capture PreToolUse `session_id`, `agent_id`, `transcript_path`. Falsified if `agent_id` is absent or the path is the parent's.
- T2 stop payload: capture `transcript_path` versus `agent_transcript_path` on SubagentStop. Falsified if the agent path is missing.
- T3 siblings: worker A leaves dirty state in a shared cwd, worker B is read-only. Falsified if B is blocked for A's files or if A's marker exempts B.
- T4 threshold: a worker with more than 30 turns and a low `CONTEXT_GUARD_PCT`. Falsified if a pending-jump for the parent or a parent handoff appears.
- T5 return and replacement: child returns a checkpoint, parent respawns at hop plus one, hop four refused.
- T6 verification: child reports done with a failing test. Falsified if the coordinator accepts without re-running.

Codex, on M5 first:

- C1 identity: spawn a native subagent in a plain session and count new files in the bridge state directory. A new file means a distinct `session_id`.
- C2 continuation plus subagent: expect deny under the current guard if C1 shows a distinct id.
- C3 role: parent imperator, child state role. Currently expected to inherit imperator.
- C4 long command: destination runs a 700-second verify. Currently expected to be killed at 600 seconds idle.
- C5 receipt in a shared checkout: sibling touch after a passing receipt. Expected block, which confirms the worktree rule.

Before rollout to Pro and Mini: T1, T2, and C1 measured and recorded in the evidence JSON; new tests green with the existing 18; parity green for the touched Claude pairs; T4 and C4 passing live on M5. Pro carries 176 daemons and existing sessions are not restarted, so it goes second, Mini last.

Unknowns to measure rather than assume: the exact subagent payload shapes on both runtimes and Codex 0.153.4 in particular; the `message.model` string inside child transcripts; child token distribution per model; whether Codex subagents inherit the parent role environment; the current Claude nesting rule; and whether any of the four sibling and parent contamination cases above reproduce live.

## Codex — round two objections

# Round two — challenge and convergence

Continue our same read-only consultation, with no implementation or delegation.
Your model and effort were verified in native records as claude-fable-5-1 / xhigh.
Thank you for the source-based critique. I agree that child identity and
parent-artifact isolation come first. Please address the objections below and
conclude with the final six decisions and the minimum ordered implementation
scope. Aim for at most 1,200 words; do not re-audit all sources unnecessarily.

## New evidence

I ran synthetic payloads against the installed Air-M5 subagent_stop_verify.py,
with mock dirty git status and disposable transcripts/marker files. Two workers
shared a parent session/transcript but had distinct agent_id and
agent_transcript_path; both had stop_hook_active=false. Worker A returned exit 2,
worker B exit 0. After removing the temporary markers, adding an unrelated
"checkpoint" only to the parent transcript also made the child return exit 0.
This reproduces the two source defects under documented payload semantics. It
is not yet a native-runtime integration test or proof of all-host parity.

## Objections and requested corrections

1. **Identity and role.** I agree with reusing Claude's existing detector, but
   topology is not the full role. Observe child identity and actual model/effort
   from runtime; assign the task role explicitly within the parent's allowed
   scope. Never infer rank from model family. On Codex, do not port a Claude
   transcript-path heuristic: measure and normalize the actual Codex payload.
   Scope the state key by profile + parent session + agent ID (plus attempt if
   IDs can be reused); keep fresh continuation state distinct. Is that the
   minimum necessary distinction without a new coordinator?

2. **Missing data must not silently use the parent.** Your suggested
   agent_transcript_path-or-transcript_path fallback is unsafe when a payload
   explicitly identifies a child but its child transcript is absent. That
   would recreate sibling contamination. Use a documented child-specific
   resolver; if measurement is unavailable, record UNKNOWN and return a
   bounded incomplete result. Do not call it measured, verified or complete.
   Keep 20/40 unchanged as current policy until evidence supports tuning; do
   not silently lower grace or invent a child's window. Agree?

3. **Do not replace a loop with fail-open work.** Counting PreToolUse denials is
   sensible, but simply downgrading to warnings after N denials allows ordinary
   work beyond the boundary. Likewise the exact-source authorization guard
   must never become advisory. Prefer permitting only checkpoint/return actions,
   then terminating this attempt as incomplete/needs_attention and handing
   responsibility to its parent. A stop marker is not authorization. What is
   feasible with these native hook semantics without deadlocking Stop?

4. **Continuation liveness and cancellation.** I agree that 600 seconds without
   an event is not proof the destination is dead. I reject the blanket rule
   "never terminate an accepted destination": user cancellation, an expired
   authorized total budget, or a verified stalled process still need cleanup.
   Record lifecycle ownership and completion destination. Use native task
   status/cancel APIs where supported; a PID alone and an assumed broken pipe
   are not sufficient identity or cancellation proof (PID reuse, transport
   buffering). A source being stopped after first progress is not proof its
   mandate has completed. Define the smallest realistic correction now.

5. **Isolation and evidence.** Agree writers need isolation under the current
   whole-worktree fingerprint. But a native child shares the parent cwd unless
   the harness supports isolation or a safe dispatch entrypoint supplies it.
   Existing agent_start refuses nested worktrees; don't instruct children to
   blindly run the broker inside the current worktree. Resolve via the existing
   repository/broker entrypoint, or serialize writers when safe isolation is
   unavailable. Read-only children should not fail for someone else's dirty
   files. Claimed intent must be child-scoped and explicitly allowed, not any
   occurrence of 'checkpoint' in raw text. Should the patch keep the existing
   dirty-state reminder separate from the actual verification acceptance gate?

6. **Test design and budgets.** A single 700-second verify command is invalid:
   verify bounds each command at 300 seconds. A sequence of commands can
   exceed 600 seconds, so the source concern remains, but prove the exact
   event/timeout behavior using short injected timing tests and a bounded
   real-runtime canary instead of an eleven-minute sleep. Count child attempts,
   retries, replacements, depth, deadline and concurrency together under the
   parent mandate. Do not rely on the historical 'Claude depth is one' note;
   that must be checked against today's runtime before choosing a control.
   If the parent disappears, stop/checkpoint at the next safe boundary without
   autonomous spawn; do not assume a particular stale heartbeat means death.

## Required final outcome

Reply point by point: accept/reject my objections with reasons. Then give the
final decision for each of our original six proposals and three ordered work
packages at most, plus explicit rollout gates. Distinguish proposed changes
from already installed behavior. No blanket 'all subagents are covered' claim
until parent -> child -> verification -> return succeeds for both harnesses on
Air-M5, Pro and Mini, and in the actual Codex app for new tasks.

## Fable — round two response

[M5] Round two. Your synthetic result is now the strongest evidence in this file: it upgrades the two SubagentStop defects from source inference to reproduced behaviour under documented payloads, on one host, outside the native runtime.

## Objections

**1. Identity and role: accept.** Role has two parts and they must never be mixed. Identity, model and effort are observed from the runtime. Task role is assigned by the coordinator inside its own scope and travels in the mandate header, because neither harness lets a parent set per-child environment. The hook default for any child is "worker"; "imperator" is never derivable for a child, from model family or from anything else. On Codex, do not port the Claude path heuristic. Capture the real payload first with a logging-only hook, then normalise. Your state key is the minimum: profile is already scoped by `CODEX_HOME`, so add parent session plus agent id, plus attempt only if a capture shows an agent id can repeat. Continuation state stays keyed by fresh session with `from_session`, as installed.

**2. Missing data: accept, and I withdraw the fallback.** The resolver is child-specific or nothing. On SubagentStop that means `agent_transcript_path` only; on PreToolUse inside a child, the child's own transcript only. If an `agent_id` is present and the child transcript is absent or unreadable, the result is UNKNOWN, recorded through the existing `gate_coverage.record` as exempt with a reason, and the bounded incomplete outcome is one block with a message asking for declared intent in the return text, never a parent-derived exemption. 20/40 stays as policy. Grace stays. No window is invented for a child: an unknown window is UNKNOWN and the gate does not fire.

**3. No fail-open work: accept.** The denial counter changes only the message, never the verdict. What native semantics allow without deadlock:

- Claude child at threshold: deny every tool. A child returns by ending its turn, so it needs no tool to comply. If it is dirty, SubagentStop blocks exactly once, keyed by agent id, and the second pass carries `stop_hook_active` and is allowed. One extra cycle, bounded.
- Codex: PreToolUse deny except the helper stays as installed. The second Stop with `stop_hook_active` and no checkpoint should write `rollover=needs_attention` with `failure=checkpoint_missing` and then allow the stop. That is "terminate this attempt as incomplete and hand it to the parent"; today the warn path leaves state at `requested` with no owner. The exact-source guard stays a hard deny in all cases.

**4. Liveness and cancellation: accept the rejection.** Smallest correction: separate idle from liveness. After acceptance the bridge polls the process it owns and waits up to an authorised deadline recorded in state and inherited from the source. Termination happens only on deadline expiry, on an explicit `cancel` verb that sets a state flag the bridge honours through its own process handle, or on process exit. Record `owner` as bridge pid plus launch nonce plus start time, `to_session`, and a `completion` field written only from `turn.completed` with either an empty `remaining` list or a passing receipt. `accepted` means handed over, not completed. Whether app-server exposes turn interrupt for a thread id is unverified; use it if it does, else the handle.

**5. Isolation and evidence: accept.** The coordinator, not the child, obtains isolation through the broker entrypoint and passes the path in the mandate; whether the broker accepts invocation from inside a worktree is unverified, and where it does not, writers are serialised. A child with no Edit or Write records in its own transcript is read-only and is never blocked for anyone's dirty files. Intent is explicit and child-scoped: a fixed token in the SubagentStop `last_assistant_message`, not a substring scan of raw text. Yes, keep the dirty-state reminder separate from acceptance. The reminder is the installed hook; acceptance is the coordinator re-running the declared commands on a different seat.

**6. Tests and budgets: accept.** The eleven-minute test is withdrawn. The 600-second literal becomes a module constant so it can be patched; prove the timer with injected event streams and a canary of two short commands under a policy that sets the constant to a few seconds. One attempt ledger per parent mandate holds attempts, retries, replacements, depth, deadline and max parallel; the coordinator writes it, hooks only read it. Depth is checked live by having a child attempt a spawn. A child that loses its parent checkpoints at Stop and never spawns; a stale heartbeat is display only.

## Final decisions

1. Explicit child mandate: **KEEP.** Header fields assigned; identity, model, effort, changed paths and receipts observed.
2. Individual context budget: **KEEP 20/40, REVISE measurement.** Child-scoped or UNKNOWN. No tuning until child usage is measured.
3. Controlled continuation: **REVISE.** Children checkpoint and return; no jump, no parent artifact, no self-continuation. Fresh-session continuation stays a top-level mechanism.
4. Concurrent editing: **KEEP.** Coordinator-obtained worktrees or serialised writers; read-only children never blocked; explicit child-scoped intent.
5. Evidence-based completion: **KEEP.** Codex receipt gate as installed; Claude gains a return shape plus independent re-run; reminder and acceptance stay separate.
6. Bounded execution: **REVISE.** Single ledger per parent mandate, deadline-based liveness, explicit cancel, depth verified live.

## Work packages and rollout gates

Installed today and unchanged by this plan: six Codex events, the receipt gate, Stop block-once, the exact-source guard, the 20/40 policy, the Claude dirtiness gate, and the Claude context guard with window jump. Everything below is proposed.

**WP1, Claude child isolation.** `subagent_stop_verify.py`: marker keyed by agent id, child-only resolver, UNKNOWN path, read-only exemption from the child's own tool records, explicit intent token. `context_window_guard.py`: with an agent id present, no jump and no parent handoff, child-only measurement or UNKNOWN, worker default, "return with checkpoint" deny text. Guilt and innocence tests built from your synthetic payloads, in the repo copies. Gate: tests green, live equals repo for both pairs on M5, then one native run on M5 with the jump spawn disabled showing a child denied at threshold, no parent jump file, no parent handoff change, and sibling B unaffected by sibling A's block.

**WP2, Codex lifecycle.** First a capture-only run recording the real child payload in a plain session and inside a continuation. Then: patchable timer, deadline liveness, `cancel` verb, owner and completion fields, second-Stop handover to needs_attention, message-only denial counter, and a read-only listing of handed-over-but-incomplete states in `installation_status.py`. Gate: existing 18 tests plus timing tests green, canary passes on M5, and the child-payload capture decides whether the exact-source guard needs a parent link before any native child runs inside a continuation.

**WP3, policy, coordinator text and ledger.** Rules text in `docs/rules/operations.md`, the mandate header template, the ledger schema, the broker entrypoint rule, and the serialisation fallback. Gate: the depth check and the broker-from-worktree check are recorded as measured facts, not notes.

Fleet gate: M5 first for both packages, then Pro with the same "existing sessions not restarted" caveat, then Mini. The only acceptable completion statement is per host and per harness: parent to child to verification to return succeeded on M5, Pro and Mini, on both harnesses, and in the actual Codex app for new tasks. Until every cell is filled, the claim is "covered for the tested paths on the named hosts" and nothing broader.

## Codex — final semantic check

Final semantic check only. No tools, no research or implementation. Please answer in under 250 words, explicitly accepting or rejecting two last corrections to your round-two proposal.

1. Read-only classification cannot mean only absence of Edit/Write records. Bash, execution tools and MCP can mutate files too; incomplete logs are not innocence evidence. Require a genuinely enforced read-only capability/sandbox or a baseline + attributable diff and all relevant mutation channels. Otherwise classify UNKNOWN, and never tell a child to clean another worker's files.

2. turn.completed is transport completion only. Empty remaining OR a passing receipt is not sufficient acceptance: a child can incorrectly claim remaining=[] or run a trivial unrelated passing command. Separate transport outcome, mandate/work completion and independent verification acceptance. The coordinator validates the expected deliverable and meaningful check coverage on the exact artifact, with a different verifier where required; a stale/missing receipt or incomplete handoff cannot be silently accepted. Parent receipt acceptance for a replacement must not erase unresolved mandate work.

I accept the six high-level decisions and three work packages, subject to these two corrections and all your measured-runtime rollout gates. Confirm the final position and any remaining disagreement. Everything remains proposed; this consultation changes no installed controls.

## Fable — final semantic response

[M5] Both corrections accepted. Final position, no tools used.

**1. Read-only classification: accept.** Absence of Edit or Write records proves nothing: Bash, execution tools and MCP mutate files, and a partial log is not innocence. A child is read-only only under an enforced read-only sandbox or permission mode, or when a baseline fingerprint plus an attributable diff over every mutation channel shows no change. Anything else is UNKNOWN. An UNKNOWN or read-only child is never told to clean, commit or discard another worker's files; the dirty-state message names the files and asks only for declared intent on the child's own scope.

**2. Completion layering: accept.** Three separate outcomes, none implying the next: transport completion from `turn.completed`; mandate completion, which is a claim from the child; verification acceptance, which only the coordinator grants after validating the expected deliverable and meaningful check coverage on the exact artifact, re-run by a different verifier where required. An empty `remaining` list or a trivial passing command grants nothing. A stale or missing receipt or an incomplete handoff is recorded as needs_attention, never silently accepted. Accepting a replacement's receipt closes only the work that receipt covers; unresolved mandate items carry forward in the ledger.

Remaining disagreement: none. The six decisions, three work packages and per-host, per-harness rollout gates stand as amended. Everything remains proposed; no installed control changes from this consultation.

## Implementation reviews and installation gate

All three implementation reviews used `claude-fable-5-1` with an explicit `--effort xhigh` invocation, continuing session `f46bded4-0f74-4b46-b30b-ef8e98611c00`. Only final answers are included below; private reasoning and raw runtime outputs are excluded. The independent reviewer inspected source. The implementing session executed the tests and native probes.

### Implementation review 1

Source: `fable-child-implementation-review.jsonl`

[M5] Verdict: **not ready for fleet installation.** Three P1 faults, two of which wall or fail-open real sessions. Native captures disprove three of my earlier suspicions, noted at the end.

## P1

**1. `needs_attention` re-opens ordinary tools on Codex.** The PreToolUse deny set is `requested/starting/accepted` only (`context_bridge.py:614-618`). Every new failure path lands in `needs_attention`: second Stop without checkpoint (637-641), deadline or cancel (749-756), budget exhaustion (771-774), failed handshake (804-807). Once there, `over` never re-requests because `rollover` is truthy (611), so the session works past its context boundary indefinitely. This is the fail-open you rejected in round two. Fix: add `needs_attention` to the helper-only deny set, and keep the Stop path as warn-once.

**2. The mandate ledger is keyed to the parent session's lifetime and never releases.** `mandate_budget.reserve` fixes `deadline = first reservation + 3600` (line 43), counts 24 attempts per session forever (59), and an unstarted reservation stays `reserved`, which counts as active (51-53); there is no release path. On Claude, `context_guard` applies this to every top-level `Agent` call (`child_workflow.py:92-101`) and the guard is registered with matcher `*` (`settings.json:442-447`). Consequence on M5: Zero's interactive session loses delegation after 60 minutes, or after 24 dispatches, or after three dispatches that never reached SubagentStart, such as user-declined permission prompts. `orchestrate_gate.py` meanwhile blocks direct work without dispatch, so a long session deadlocks. Same code path on Codex (`context_bridge.py:500-512`). Fixes: scope the ledger to a mandate epoch, reset on UserPromptSubmit or by coordinator declaration, or apply deadline and attempt caps only to autonomous seats; expire unbound reservations after a TTL as `expired_unstarted`, still counted as attempts but not active; add `MANDATE_BUDGET_OFF=1` like every sibling gate.

**3. UNKNOWN measurement blocks every short child once.** `child_hook` blocks SubagentStop when `not transcript or measurement == "UNKNOWN"` (`context_bridge.py:451-464`). Measurement becomes observed only if a `token_count` record with a timestamp is appended after the SubagentStart offset (422-430). A one-tool child plausibly has none, so every read-only worker pays a forced extra cycle. The native probe ran before the patch, so this is unproven either way. Round two agreed UNKNOWN measurement is recorded, not blocked. Fix: block only on UNKNOWN identity, on `return_required` without checkpoint, or on possible mutation without ownership evidence. Same on Claude: `_stop_guard` treats `pretool_count == 0` as UNKNOWN (`child_workflow.py:180`); a child that made no tool calls cannot have mutated and should be read-only.

## P2

- **Depth is decorative.** `reserve(depth=1)` always; child branches never check spawn tools (`context_guard` child path, `child_hook`), so a grandchild spawn bypasses the budget. Fix: children deny `Agent` and `collaborationspawn_agent` outright.
- **`collaborationfollowup_task` is an uncounted dispatch channel.** Capture lines 14-19 show it resumes the child with no new SubagentStart and a second SubagentStop. The ledger already marked the child returned, and `stop_reminded` is set, so the second stop never reminds. Fix: reserve on followup, re-activate the binding, clear `stop_reminded` on the first PreToolUse after `transport_status=stopped`.
- **`native_child` keys on top-level `parent_thread_id` alone** (361-363). Rollouts on disk carry `source.subagent.thread_spawn` and also `source.subagent.other`. Require `source.subagent` and decide `other` explicitly, or a future non-subagent fork becomes a walled child.
- **Checkpoint before cwd.** `child_hook` calls `checkpoint()` (408) before writing `cwd` (415); `checkpoint()` raises without cwd (699). A child whose first observed event is PreToolUse can never checkpoint.
- **Exit race in `continue_session`** (891-899). On `queue.Empty` with the process exited it raises "exited without completion" while the reader thread may still hold `turn.completed`. Drain the queue or join the reader for up to two seconds first. The test at `POLL_SECONDS=0.02` makes this race likelier, not rarer.
- **Writer children told never to commit** (`child_workflow.py:208-211`). The W80 cure was commit-own-paths-or-declare. Permit path-by-path commit of the declared write set; forbid touching others'.
- **SessionStart injects the contract into every top-level Claude session** (`install_claude_children.py:83`, `child_workflow.py:238-247`), about 700 characters per session against the context diet. Register SubagentStart only, after confirming additionalContext is honored there natively.
- **Installer semantics.** The Stop insert makes the whole legacy `_run()` body dead code: intent markers, once-marker, and the repo copy's `lane_check` wiring never run. "Preserved byte-for-byte" is textual. No check that `orchestrate_gate.py` exists in the hooks dir; its absence turns every PreToolUse into an exit-1 traceback.
- **Parity red by construction.** Repo copies carry the block over a different base than the live copies. Declare the pairs for `lint_home_fork.py` or reconcile bases before install.
- **Docs and smoke drift.** README and ROLLOUT say six events; `EVENTS` has eight; `smoke.py` required set omits the two new events.
- **Ledgers never pruned; `attention` verb ignores mandate ledgers.**
- **Tests.** 42 green predates the ledger changes: rerun. Missing cases: unstarted reservations exhausting `max_active`, deadline expiry mid-session, followup resume, child spawn denial, process exit without `turn.completed`.

## Disproven and gates

Disproven by the native captures: `collaborationspawn_agent` is the real tool name; `tool_use_id` is present on PreToolUse in both harnesses, so the identity-UNKNOWN deny does not fire natively; the Codex `agent_id` equals the child thread id and its first `session_meta`.

Before any host beyond M5: fix P1 1-3, rerun all tests, then a patched native probe per harness on M5 showing a one-tool read-only child returning with zero SubagentStop blocks; an interactive session surviving three declined dispatches plus a time-shifted ledger `created` without losing `Agent`; a child at threshold denied and returning with checkpoint while the parent state is byte-identical. Then Pro, then Mini, then the Codex app on a new task. Nothing here is permission to ship.

### Implementation review 2

Source: `fable-child-implementation-review-2.jsonl`

[M5] Verdict: **FAIL for a bounded Air-M5 canary as-is, with three blockers, all small.** The P1s from the previous round are closed in code: `needs_attention` is helper-only (`context_bridge.py:662-667`, tested), UNKNOWN measurement no longer blocks a child stop (489, tested), zero-tool Claude children return clean (tested), nesting is denied on both harnesses, the reader is drained before declaring exit (950-956), unstarted reservations expire (`mandate_budget.py:59-63`), interactive counters are observation-only unless `NUZANTARA_MANDATE_ID` is set, mandate root follows exact jump links (`child_workflow.py:172-205`), and the installer asserts the three legacy guards are byte-identical before and after. Stop-reminder reset happens only on a PreToolUse after a real `stopped`, not after `stop_blocked`, in both adapters.

## Blockers

**1. Follow-up with an unrecognised target is a hard deny** (`mandate_budget.py:81-83`). The native child `session_meta` carries both `agent_path` and `agent_nickname`; only the path is hashed at SubagentStart (`context_bridge.py:416`). If the Codex app passes the nickname, or any value other than path or thread id, every native follow-up is denied and the parent's flow in the app breaks. The `tool_input` shape was never captured. Fix: hash nickname and id as aliases too, and on unknown target fall through to a fresh reservation with `status=needs_attention` as observation, never a deny.

**2. Canary boundary is not established.** `com.nuzantara.claude-config-sync` runs hourly on Pro (`docs/connectome/edges/launchd-pro.yaml:736-741`). Its scope and direction are not visible from this worktree. If it pulls settings from Pro, the routed M5 `settings.json` is silently reverted within an hour while `child_workflow.py` stays on disk, which is scar #2 exactly. If it pushes, the canary reaches Pro and Mini without an install. Verify the sync file list and direction, or pause it for the canary window, before running the installer.

**3. The router has no fail-open envelope.** `child_workflow.main()` (287-365) runs in the path of every tool call on the seat with no outer `try`. Any exception in `context_guard`, the ledger, or the legacy module load produces exit 1 on every call and the legacy context guard never executes: the top-level guard is disarmed while stderr floods. Fix: wrap the context mode so any router exception falls back to `legacy.main()`, and wrap the stop mode to exit 0 with one stderr line, matching the directory's fail-open discipline.

## P2, not blocking

- `NUZANTARA_MANDATE_ID` must be set per process for autonomous runs only. In a seat's settings env it would make every session share one strict 24-attempt, one-hour ledger.
- Codex `needs_attention` has no operator exit except `enabled=false`. Add a `release` verb later.
- `attention` in `context_bridge.py` ignores mandate ledgers; the Claude variant covers only Claude.
- Add a subprocess test that runs `child_workflow.py context` and `stop` against the repo legacy copies with top-level and child payloads, asserting exit codes and a single JSON object on stdout. That path is what runs on every M5 tool call and is currently tested only through the pure functions.
- SubagentStart `additionalContext` support in Claude 2.1.266 is unverified; harmless if ignored.

## Scope statement

The code enforces child identity isolation, nesting denial, concurrency of three, expiry of unstarted reservations, helper-only lockdown after failure, and bounded reminders. It does not enforce semantic mandate assignment, worktree isolation, or independent acceptance; the contract text is advisory and the code does not claim otherwise. Rerun the full suite after the three fixes. No authorization to merge or deploy is implied.

### Implementation review 3

Source: `fable-child-implementation-review-3.jsonl`

[M5] Verdict: **PASS for the bounded Air-M5 canary.** All three blockers are closed in source.

- **Blocker 1, unknown follow-up target.** `reserve` now falls through to a fresh reservation with `status=needs_attention` as observation (`mandate_budget.py:86-87`) instead of returning a deny. Matching covers the child id, the `/root/` path alias, and the raw target hash against `aliases_sha256` (75-81). `observe` hashes id, path and nickname (146-155), and the Codex SubagentStart call site passes both `agent_path` and `agent_nickname` (`context_bridge.py:416-417`). Test at `test_child_lifecycle.py:527` covers the unmapped nickname case.
- **Blocker 2, canary boundary.** Your live check on Pro shows the sync is Pro to Mini only. From M5 I can confirm independently that no config-sync LaunchAgent exists under `~/Library/LaunchAgents`. The M5 canary is isolated.
- **Blocker 3, fail-open envelope.** `entrypoint()` (`child_workflow.py:378-414`) buffers stdin, and on any router exception: a known child gets exit 2 with the incomplete-checkpoint instruction and no jump path; a parent falls back to the original installed guard as a subprocess with the raw payload and inherits its exit code; a Stop failure exits 0. `SystemExit` from `main()` passes through the `except Exception` correctly. Subprocess tests exist at lines 546 and 582.

Not verified by me: the 59-pass and Ruff results, since I cannot execute. The test functions are present at source level.

**One exact remaining item, for the Pro plus Mini phase only.** The SubagentStart handler is written with the installer's `sys.executable` (`install_claude_children.py:57`). Pro's repo lives under `~/Desktop/nuzantara` and Mini's under `~/nuzantara`, and the Pro to Mini sync copies `settings.json` with newest mtime winning. A venv interpreter path baked on one host will not exist on the other after sync, so that host's SubagentStart hook fails non-blocking, reservations never bind, and they expire as unstarted. Use the same interpreter token as the existing handlers, `python3`, or a path present on both hosts, and install Pro and Mini within one sync interval. This does not affect M5.

Gate unchanged: Pro and Mini only after the M5 real probes pass on both harnesses. No merge or deploy authorization is implied.
