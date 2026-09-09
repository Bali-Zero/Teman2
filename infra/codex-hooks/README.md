# Codex workflow bridge

This is the Codex adapter for Nuzantara's context and verification workflow. It
uses Codex lifecycle hooks, native rollout accounting, and the official Codex
CLI for fresh continuations. It does not modify the Claude/Fable hook files.

## Installed behavior

- Eight additive events: SessionStart, PreToolUse, PostToolUse, PreCompact,
  PostCompact, Stop, SubagentStart, SubagentStop. Existing hook definitions and their ordering are retained.
- Context usage is `last_token_usage.total_tokens / model_context_window` from
  the current Codex rollout, never cumulative lifetime tokens or a guessed 1M
  window. The policy is 20% for imperator and 40% for other roles. The role is
  read from CODEX_CONTEXT_ROLE, falling back to the existing CONTEXT_GUARD_ROLE.
- Threshold crossing asks for an operational checkpoint and restricts further
  tools to the exact bridge helpers. Compaction discards stale token readings.
- A continuation is bound to a source session ID and a single-use nonce, within
  the same CODEX_HOME and working directory. It retains the source model,
  reasoning effort, approval policy and supported sandbox settings. Original
  text instructions and later steering are read transiently from native
  rollouts; generated continuation wrappers are not added again on each hop.
- A destination must acknowledge that exact source: its own SessionStart hook
  claims the source under the launch nonce, and that claim is the acceptance
  (1.2.0). Creating a thread alone is insufficient; a model or tool event
  without a claim still rejects the destination. The supervisor waits up to 240
  seconds for the claim, while one Stop hook blocks at most 45 seconds and then
  leaves the launch `starting` rather than cancelling it — the next Stop
  re-checks. A failed launch parks the source as needs_attention; transient
  failures (timeout, destination exit, unconfirmed) are retried by the next
  Stop up to three launch attempts, other failures wait for the operator
  (`retry` re-arms, `release` unfreezes the source over threshold). The
  maximum chain length is three hops. No GUI automation is involved.
- Verification executes real argv commands, records exit codes and hashes, and
  binds the receipt to HEAD, tracked changes and untracked contents. Any later
  edit invalidates it. Stop requests verification when changes lack a current
  passing receipt; a second Stop warns instead of looping indefinitely.

The receipt proves that the recorded commands passed on that file state. It
is not an independent review, semantic proof of adequate test coverage, a
production deployment check, or a global gate on other hooks' memory writes.
Codex executes matching hooks concurrently, so this adapter does not claim to
serialize unrelated Stop hooks.

Version 1.1 adds native child identity, child-local checkpoints, bounded stop
reminders, shared dispatch accounting and owned continuation cancellation.
Children use their own measured context and return to their parent. A separate
Claude adapter wraps the installed legacy guards without replacing them.
See [the child rollout record](CHILD-ROLLOUT-2026-09-09.md) for enforcement limits,
Fable review, fleet evidence and the distinction between installation and
observed native execution.

The capacity follow-up adds expiring, host/profile/model/version-specific Claude
calibration from a successful native CLI result. Claude interactive sessions
observe token, tool, time and concurrency limits without denying tools. Explicit
mandates enforce eight concurrent children, 120 tools per child, 3,600 active
seconds and 40% of a measured window. Unknown capacity emits a warning per tool;
strict mode retains time/tool limits and a 400,000 measured-token emergency
ceiling, without claiming a percentage. A fresh Air-M5 desktop task also proved
native Codex parent and child hook consumption; its evidence is linked in the
rollout record.

SubagentStop releases dispatch accounting and pauses the child's clock before
any verification recovery flag is checked. Resume retains spent time and attempts.
After 30 minutes without transcript or hook activity, a known transcript's child
becomes `suspect_zombie`: its slot is reclaimable but its record remains. A recent
transcript keeps its slot even without recent tools; an unavailable transcript
retains the slot as UNKNOWN. A returning suspect child must reacquire capacity
before an ordinary tool can execute. This does not terminate or fence a process
or a previously started command. Leaf ownership and independent review still apply.

Use the existing virtualenv to run `native_claude_child_probe.py --model opus
--warmup`, then repeat without `--warmup` to prove the calibrated consumer. The
model aliases are `haiku`, `sonnet`, and `opus`; the probe verifies the native
model identity. `--candidate` tests the branch adapter for this invocation while
preserving global rollback and normal recovery settings. `--children 4` verifies
one parallel dispatch. Set `CLAUDE_CHILD_PROBE_CWD` to the normal repository path
so the capacity binds to that routing scope. Each run keeps its own metadata and
reports UNKNOWN usage as an incomplete consumer proof. Warmup alone does not prove
tool enforcement. The calibration receptor remains the separately authorized D3
pilot; this correction does not implement or arm it.

## Installation and rollback

Run install.py using the host's existing project virtualenv, once per seat,
with --seat, one or more --root arguments, and --trust-reviewed-hooks. The
installer backs up the original config and hooks, copies only this adapter,
enables the hooks feature, and records trust for only the eight exact definitions
through Codex's own config API. It never copies auth.json between machines and
never uses a hook-trust or sandbox bypass switch.

The manifest is CODEX_HOME/state/nuzantara-context-install.json. Its
original_backup points to the first pre-install backup; each update also has
its own backup. installation_status.py independently verifies persisted trust,
installed source hashes and preservation of the previous hooks.

For immediate rollback, set enabled=false in
CODEX_HOME/nuzantara-context-policy.json. This disables only this adapter.
To remove its definitions, restore the original hooks.json from original_backup
(or remove hooks.json only if it did not exist there). Restore config.toml only
when no later unrelated configuration edits would be lost. No restart or
termination of another session is performed by the installer.

New sessions consume the installation. Existing sessions are not restarted and
must not be assumed to have reloaded their hook snapshot.

## Validation

- test_context_bridge.py: deterministic regression cases for token measurement,
  role thresholds, compaction, exact claims, helper recognition, permissions,
  failed checks, edits after checks, missing state and bounded chains.
- smoke.py: real native Codex session in an isolated empty Git repository,
  executing true and proving SessionStart -> PreToolUse -> PostToolUse -> Stop.
- handoff_smoke.py: two real native continuations, exact IDs, unchanged model and
  permissions, then an injected launch failure proving source retention.
- installation_status.py: read-only installation evidence for each account seat.
- test_child_lifecycle.py: child state, dispatch accounting, wrapper routing and
  continuation lifetime regression cases.
- native_child_probe.py and native_claude_child_probe.py: real read-only child
  execution followed by an independent parent check; Codex also resumes the
  same child once.

The native CLI is intentional: in this installation a custom app-server client
was rejected for Astra although the official CLI successfully used the same
model. App-server remains the supported read/config surface for hook discovery
and exact trust hashes. No model is silently substituted.

## Explicit boundaries

Only the configured Nuzantara roots and Codex worktrees are covered. An absent
or unrecognized transcript does not become an invented context percentage.
Oversized or non-text mandates and unsupported permission shapes stop the
handoff for attention rather than silently dropping context or widening access.
An unattended continuation cannot obtain new interactive consent.

The existing nightly CI autofix runner deliberately uses --ignore-user-config
and --ephemeral. Installing user hooks does not connect that isolated runner;
its repair scheduling and lifecycle remain separate. No new healer daemon or
outbound notification channel is installed by this change.

## Sandbox-safe helper transport

SessionStart provides the exact interpreter, installed helper path and session
ID. Pass the checkpoint or verification payload as a single shell-quoted JSON
argument. A quoted argument avoids temporary files that a shell heredoc may
need in a read-only sandbox.

PreToolUse stores only validated checkpoint metadata for the exact helper call.
The helper then reads that acknowledgement. Verification commands still execute
inside the caller's sandbox; the helper emits only its receipt and PostToolUse
stores that receipt. This does not grant the agent permission to write its home
directory or execute test commands from an unsandboxed hook. A checkpoint whose
remaining list is empty completes the mandate without spawning a continuation.
