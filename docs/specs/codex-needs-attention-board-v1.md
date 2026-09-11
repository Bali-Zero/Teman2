# SPEC — codex `needs_attention` → escalations board, and the cascade waits for the codex chain (v1)

date: 2026-09-09 · owner: Fable Pro (session 0f66a43f, lane `docs/codex-needs-attention-spec`) · status: normative, pre-implementation
origin: Astra's proposal of 2026-09-09 (the two sister lanes opened after #6002's gate), handoff memories 15619/15624.
Builder Contract §1 routes an under-specified surface to a specification rather than to a fix-of-a-fix.

**Status: normative.** The two implementing PRs may be built from this file without inference. Where an
implementation and this file disagree, one of them is wrong — say which, in a PR, rather than resolving it
silently in code.

Constrains two surfaces: the Codex context bridge (`infra/codex-hooks/context_bridge.py`, today only on
`agent/air-m5/infra/codex-context-bridge`, reviewed NOT MERGEABLE at `1e73a58d` with three live blockers —
memory 15648) and the subscription cascade (`infra/launchagents/wrappers/claude-cascade.sh`, `codex_attempt()`).
Consumes the board contract of `scripts/sentinel_lib/escalations.py` (readers hardened in #6025, writer fixed
in #6012) and the headless-cap receptor shape shipped in #6002.

**Implementation is separate from this spec, and comes after the bridge lands on `main`.** Landing the writer
inside the bridge branch as it stands would merge it under the blockers the review named.

## Why this file exists

A headless `codex exec` run driven by the cascade has two ways to end INCOMPLETE with exit 0 and non-empty
stdout — the exact shape superscar #2 (Esiste≠Armato) names, and the exact class #6002 closed for the Claude seats:

1. **The bridge parks the session in `needs_attention`.** Either `rollover = needs_attention` (failure one of
   `continuation_not_confirmed`, `checkpoint_missing`, `mandate_cancelled_or_expired`, `mandate_dispatch_budget`,
   `destination_<status>`, `verification_missing_or_stale`) or `completion_status = needs_attention` (a `Stop`
   with `return_required` and no checkpoint, or no transcript at all).
2. **The bridge hands off (`rollover = accepted`, `to_session` set).** The work continues in another Codex task;
   `codex exec` returns the partial output of the first one, and the cascade prints it as the answer.

Today the only surface for either is `context_bridge.py attention` — a pull verb nobody calls. Nothing pushes to
the board, and `codex_attempt()` treats exit 0 + non-empty stdout as success. The Claude seats already have the
push (`cascade_headless_cap`, HIGH line, SessionStart receptor pages it); the codex seats have nothing.

## Surface 1 — the board line (producer: the bridge)

- **Trigger.** Any transition INTO `needs_attention` (either field), at the moment the bridge persists it. Never on
  `attention` reads, never on an unchanged state.
- **One pending line per session.** Dedupe by `type` + `session` on the board before appending, as
  `cascade_headless_cap` does; a second transition for the same session appends nothing.
- **Resolution.** When the same session later persists `rollover = accepted` or a complete verification, append
  the `mark_resolved` shape: `{"job": <same job>, "status": "resolved", "resolved_at": <float>, "ts": <float>}`.
  The pending line is never rewritten (immutable log, superscar #9).
- **Record shape** (mirror of the cap receptor; every field below is required):

  | field                                                                | value                                                                                                                                                                                                                                          |
  | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | `job`                                                                | `codex-needs-attention-<seat>-<sid[:8]>` — `seat` = basename of `CODEX_HOME`                                                                                                                                                                   |
  | `type`                                                               | `codex_needs_attention`                                                                                                                                                                                                                        |
  | `priority` / `status`                                                | `HIGH` / `pending`                                                                                                                                                                                                                             |
  | `error_summary`                                                      | `<failure> on codex seat <seat> session <sid[:8]>: <one-line meaning of the failure>; checkpoint <state path or none>`                                                                                                                         |
  | `seat`, `session`, `failure`, `to_session`, `checkpoint_path`, `cwd` | identifiers only                                                                                                                                                                                                                               |
  | `cure_lane`                                                          | `{"owner": "session", "note": "read the bridge state first; resume with context_bridge.py continue <sid> or a fresh seat run with the checkpoint as its first context; then mark this job resolved; never rerun blind (Builder Contract §1)"}` |
  | `machine`, `_writer`                                                 | short hostname                                                                                                                                                                                                                                 |
  | `ts`                                                                 | `time.time()` — a **float**. #6025 makes readers tolerate a string; the writer still owes a number                                                                                                                                             |

- **PII boundary (Builder Contract §4).** The line carries identifiers and enums only: no prompt text, no command
  output, no transcript excerpt. The bridge already refuses to copy those into its state; the board is a shared
  artifact and holds them to the same rule.
- **Board path.** `ESCALATIONS_BOARD_FILE` when set; else `$NUZANTARA_ROOT/shared/escalations_pro.jsonl`; else
  `~/nuzantara/shared/escalations_pro.jsonl`. No `~/Desktop` candidate (W84 TCC). Single-line `O_APPEND` write.
- **Never fails the hook.** A missing or unwritable board is one stderr warning; the hook's decision is unchanged.
- **Kill switch.** `CODEX_ATTENTION_ESCALATION_OFF=1` silences the write, not the state transition.

## Surface 2 — the cascade waits for the codex chain (consumer: `codex_attempt()`)

- **Run identity.** The cascade exports `NUZANTARA_CASCADE_RUN=<uuid4>` into the `codex exec` environment; the
  bridge copies it into state at `SessionStart` as `run_tag`. After exec returns, the cascade reads the state files
  under `$CODEX_HOME/state/nuzantara-context/` and takes the one whose `run_tag` matches. The tag is a uuid and
  nothing else: external seats inherit the session environment (memory 2026-08-18), so no secret may ride on it.
- **Bridge absent** (no state file carries the tag — the seat has no bridge installed, or Q1 below is answered
  "hooks do not fire under exec"): today's behaviour, plus one stderr line
  `[codex-chain] bridge absent on seat <seat>: chain outcome unknown`. Silence would be #2 again.
- **Outcomes, by the run's final state:**
  - stopped, `claimed_complete`, no `needs_attention` → the output is the answer, as today;
  - `rollover = accepted` → poll the `to_session` state every 2 s up to `CASCADE_CODEX_CHAIN_WAIT_S` (default 900,
    the bridge's own active-time cap); print `[codex-chain] hop N → <to_session[:8]>` per hop; when the continuation
    reaches a terminal state, emit its last message (`codex exec -o` of the continuation when the cascade launched
    it, else the bridge checkpoint) as the answer. Hop cap `CASCADE_CODEX_CHAIN_MAX_HOPS` (default 3, the same cap
    the Claude seats have). At the cap or at the wait deadline: `[codex-chain] INCOMPLETE` on stderr, a Surface-1
    line if the bridge did not already write one (same dedupe), and **return 0 with the partial output** — the
    emitted hops are real work, the same policy #6002 set for the Claude cap;
  - `needs_attention` → `[codex-chain] INCOMPLETE (<failure>)` on stderr, the Surface-1 line ensured, return 0 with
    the partial output. The `[claude-cascade] used: <label>` line is still printed so consumers know which seat spoke.
- **Never rotate to the next seat on `needs_attention`.** Part of the work is done; replaying the prompt on another
  seat is the blind rerun Builder Contract §1 forbids.
- **Kill switch.** `CASCADE_CODEX_CHAIN_WAIT=0` restores today's behaviour and keeps the stderr detection: the
  operator turns off the wait, not the report (codex finding #4 on #6002).

## Acceptance criteria (falsifiable — each is a test that must fail before the PR and pass after)

Surface 1, in `infra/codex-hooks/test_context_bridge.py`, temp `CODEX_HOME` + temp board via `ESCALATIONS_BOARD_FILE`:

- **A1 guilt.** A `Stop` with `return_required` and no checkpoint → exactly one line; `type == codex_needs_attention`,
  `priority == HIGH`, `isinstance(ts, float)`, `failure` set; the fixture's prompt string is absent from the line.
- **A2 dedupe.** Two transitions for the same session → still one pending line.
- **A3 innocence.** A run that stops with `remaining == []` → zero lines.
- **A4 resolve.** `needs_attention` then `accepted` for the same session → one resolved line;
  `escalations.is_job_open(job)` is `False`.
- **A5 fail-open.** `ESCALATIONS_BOARD_FILE` inside an unwritable directory → hook output identical, one stderr warning.
- **A6 read.** `read_all_escalations()` on the temp board returns the line, sorted by its float `ts`.

Surface 2, in `scripts/tests/test_claude_cascade_shell.py`, with a fake `codex` binary that writes a state file:

- **B1** `accepted` → the cascade waits, emits the continuation's output, prints `[codex-chain] hop 1`.
- **B2** `needs_attention` → `[codex-chain] INCOMPLETE`, board line, exit 0, partial stdout preserved.
- **B3** no state file → today's path, one `bridge absent` stderr line, exit 0.
- **B4** `CASCADE_CODEX_CHAIN_WAIT=0` → no wait, marker still printed.
- **B5** hops beyond `CASCADE_CODEX_CHAIN_MAX_HOPS` → INCOMPLETE at the cap, not an unbounded wait.

Live (the `Bites:` line of each implementing PR, observed before reporting done):

- **L1** On Pro, cancel a running exec through the bridge (`context_bridge.py cancel <sid>`) → one HIGH
  `codex_needs_attention` line on the real `shared/escalations_pro.jsonl`, read back through `read_all_escalations()`
  and surfaced by the next SessionStart receptor; then `mark_resolved`.
- **L2** The same run driven through `claude-cascade.sh` prints `[codex-chain] INCOMPLETE` and still exits 0 with
  the partial output.

## Sequencing and ownership

1. The bridge lands on `main` at a new SHA with the M5 proof the review asked for (memory 15648). Astra prepares,
   a Claude session verifies — generator is never grader (Builder Contract §5).
2. PR-1: Surface 1, in `infra/codex-hooks/`, same owner as the bridge.
3. PR-2: Surface 2, in `claude-cascade.sh` (+ `scripts/lib/codex_seat.sh` if the seat loop needs the tag). May be
   prepared before step 1 behind `CASCADE_CODEX_CHAIN_WAIT` defaulting to `0`; flipped to `1` only after L1.
4. Ledger: a PENDING-ARMS row is opened with this spec and closed only when L1 is observed.

## Non-goals

- Changing what `needs_attention` means — the bridge's semantics stay with its owner.
- Paging Telegram: the board is the surface, and the SessionStart receptor already pages HIGH lines (Legge 5).
- Touching the Claude-seat jump logic (#6002) or the reader hardening (#6025).

## Open questions — answered in the implementing PR, not by editing this file silently

- **Q1** Do the bridge's hooks fire under non-interactive `codex exec` on the installed Codex? Probe:
  `CODEX_HOME=<seat> codex exec 'say hi'` then `ls $CODEX_HOME/state/nuzantara-context/`. If they do not, Surface 2
  reduces to the "bridge absent" branch and Surface 1 is the whole deliverable.
- **Q2** `escalations.py`'s docstring says the Pro board is "written exclusively by Pro"; the cap receptor and this
  writer append from any host, tagging `_writer`. Either the D2.3 docstring is updated, or Mini/M5 writes are routed
  to the Pro board through the fleet mailbox. Decision belongs to the D2.3 owner.
- **Q3** `run_tag` propagation into the hook process must be verified per seat home (`~/.codex`, `~/.codex-o2`,
  `~/.codex-acct2`), not assumed from one.
