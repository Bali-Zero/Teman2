# Independent review disposition

Reviewer: Claude Opus 5.5 xhigh, fresh OAuth CLI session
`ce4cc118-9a72-4d2a-9141-0626d06ba775`. Read-only cross-family review.
Initial verdict: REWORK; implementation logic accepted, missing retry regression.

- M1 fixed: the Stop regression now uses actual transient `TimeoutError` and
  covers both `requested` and `needs_attention` with a live supervisor.
- L1/L2 fixed: native guidance names the verify command and never promises a retry.
- L3 fixed: installation status handles missing config and active profile overrides.
- L4 fixed: rollback documentation explicitly states reinstall selects native mode.
- L5 fixed: preserve blank lines and CRLF; refuse symlink replacement before mutation.
- I1 acknowledged: existing supervisor-finished/PID semantics are unchanged; starting
  and accepted ownership remains unconditionally frozen through compaction.

Final acceptance is delegated to a separate fresh Opus 5.5 xhigh session on the
committed candidate. This document is a disposition, not the final gate receipt.

Fixed panel (all three completed via subscription routes):

- Codex Sol xhigh: REWORK. Fixed symlink validation order before _any_ backup
  creation/copy; tests now assert no backup or hook directories exist on refusal.
  Fixed native-default status for absent config and added root/active/inactive
  profile probes. Both medium findings resolved in the candidate.
- Kimi K3: PASS; 99 focused tests independently passed. Its symlink backup
  observation is resolved by the Codex finding above. PID reuse semantics are
  inherited; no new process termination or identity fallback is introduced.
- Gemini 3.1 Pro constructive: REWORK lead rejected on code evidence, subject
  to final gate adjudication. `await_acceptance` does NOT change `starting` at
  the 45-second wait limit: it returns a message without a state write. Existing
  `test_stop_wait_expiry_keeps_launch_starting` proves this. A Stop ends a turn;
  it does not delete source state or kill the detached supervisor. Source tools
  remain frozen while ownership is live, including parked phases. Adopting the
  proposed extra Stop block would reintroduce unwanted context-only stop loops.

Meta-pattern: review dispositions must cite observed failure-side effects,
not infer them from a preserved target. Operator-only actions: none.
