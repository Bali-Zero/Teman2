# Codex workflow bridge

This is the Codex adapter for Nuzantara's context and verification workflow. It
uses Codex lifecycle hooks, native rollout accounting, and the official Codex
CLI. Parent sessions use native automatic compaction (1.3.0). It does not
modify the Claude/Fable hook files.

## Installed behavior

- Eight additive events: SessionStart, PreToolUse, PostToolUse, PreCompact,
  PostCompact, Stop, SubagentStart, SubagentStop. Existing hook definitions and their ordering are retained.
- Context usage is `last_token_usage.total_tokens / model_context_window` from
  the current Codex rollout, never cumulative lifetime tokens or a guessed 1M
  window. Native children retain policy thresholds; legacy parent rollover is
  disabled by `parent_rollover_enabled=false`. `install.py` seeds 60% for imperator,
  builder and dux, and an undeclared role falls back to 40%. Fresh installs
  seeded 20% imperator / 40% builder until 2026-09-10. Existing keys are never
  overwritten, so a seat keeps a tuned value across reinstalls. The role is
  read from CODEX_CONTEXT_ROLE, falling back to the existing CONTEXT_GUARD_ROLE.
- Parent threshold crossings no longer freeze tools or create continuations.
  Codex compacts automatically at its model's native threshold and continues
  in the same session. Compaction discards stale token readings. Parked jumps
  without a live supervisor are retired lazily on the next hook. In-flight
  `starting`/`accepted` continuations remain protected, including after compact.
- Existing legacy continuations remain bound to a source session ID and a single-use nonce, within
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
  Stop up to three launch attempts only with legacy parent rollover enabled; other failures wait for the operator
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
seconds and the role's policy share of a measured window. Unknown capacity emits a warning per tool;
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
enables the hooks feature, and records trust for only the nine exact definitions
(eight bridge events plus the output guard below)
through Codex's own config API. It sets `parent_rollover_enabled=false` and
removes only the two top-level `model_auto_compact_token_limit` and
`model_auto_compact_token_limit_scope` overrides, restoring model defaults.
Named profiles remain untouched; check active profile overrides separately.
It never copies auth.json between machines and
never uses a hook-trust or sandbox bypass switch.

The manifest is CODEX_HOME/state/nuzantara-context-install.json. Its
original_backup points to the first pre-install backup; each update also has
its own backup. installation_status.py independently verifies persisted trust,
installed source hashes and preservation of the previous hooks.

To restore legacy parent jumps, set `parent_rollover_enabled=true` in
CODEX_HOME/nuzantara-context-policy.json; previously released sessions remain
released. Reinstalling explicitly enables native mode again. Restore the compact
overrides from this update's backup if required. Symlinked configuration is
rejected without modification; use a regular seat config for this installer.
Setting `enabled=false` disables the whole adapter, including child and
verification checks, so it is not the rollback for this migration.
To remove its definitions, restore the original hooks.json from original_backup
(or remove hooks.json only if it did not exist there). Restore config.toml only
when no later unrelated configuration edits would be lost. No restart or
termination of another session is performed by the installer.

New sessions consume the installation. Existing sessions are not restarted and
must not be assumed to have reloaded their hook snapshot.

### Output hygiene

The installer also copies `infra/claude-hooks/output_hygiene_guard.py`
byte-for-byte and registers it once as a `PreToolUse` hook with matcher `Bash`,
trusted alongside the bridge. Codex reports shell calls to `PreToolUse` as
`tool_name: "Bash"` with `tool_input.command` (observed in this bridge's own state)
and documents exit 2 plus a stderr reason as a deny (unverified on this fleet until
the live proof below). Whether every exec path (unified
exec, nested code-mode calls) emits `PreToolUse` depends on the upstream version, so
each release proves the deny live in a fresh session per host; a path that emits no
event is simply not bounded by this guard. Ownership is the exact installed path of
this seat's copy, never a substring. The guard only decides: it never
runs or rewrites the command, fails open on anything it does not recognize, and
leaves a genuine command failure to surface with its own exit code. Its shapes
and corpus are the Claude guard's (`docs/specs/2026-09-18-output-hygiene-guard-shapes-spec.md`);
the Read and Skill shapes have no Codex tool and never fire here. Kill switch
for one session: `NUZ_OUTPUT_HYGIENE_OFF=1`. To remove it, delete its
`PreToolUse` group from hooks.json; `installation_status.py` reports
`output_guard_trusted` and counts it in `installed`.

## Seat profile

`install_seat_profile.py --seat ~/.codex` installs the reviewed seat profile kept in
`seat/`: the root `developer_instructions` (scoped reads, bounded tool output, the
code-mode `// @exec` output pragma, routine delegation) and four routine roles in
`agents/` (`mechanical` Luna low read-only, `routine-explorer` Terra medium
read-only, `routine-worker` Terra medium, `code-reviewer` Sol high read-only).
Each item that is absent is installed; an identical item is left untouched; a
different item is operator-owned drift and is reported, never overwritten. A
private backup precedes any write. The root key is validated absent in one
user-layer snapshot from Codex's own `config/read` (`includeLayers`) and written
with `config/batchWrite` pinned to that snapshot's `expectedVersion`: changes
arriving before Codex's internal version check are refused (`configVersionConflict`).
This is not a cross-process lock: another writer could still race the internal
check/write interval. Install only with no other Codex app or session on that seat.
Before writing, the installer
proves on a scratch seat that the Codex binary in use refuses a stale version;
a binary that does not is never used for the write. The version is semantic
(a comment-only edit does not change it; Codex preserves the file's other
lines). After the write the user layer is re-read: only that key may change,
otherwise the installer stops and names the backup (it does not restore on its
own). `--check` is read-only and exits 1 unless every item matches.
Roles are created with a hard link, so a file that appears first always wins.
On a refused config write, role files and the private backup may already exist;
the install manifest is saved only on success. Rerunning the reviewed installer
on an idle seat preserves matching files and completes the manifest. If recovering
manually, inspect the latest private `state/nuzantara-seat-profile-backups/` entry
and do not infer ownership of role files from a missing manifest.
There is deliberately no automatic removal. Rollback, with no Codex app or session
running on that seat (the only writer exclusion available): restore config.toml
from the backup the install reported (or delete its single `developer_instructions`
key) and delete the role files that the manifest
`state/nuzantara-seat-profile-install.json` lists as installed.
The roles and instructions are guidance: they tell a parent never to use a role in
place of a required cross-family review, an explicit model/effort assignment or a
mission-colour gate, and those stay enforced by the harness's required checks, not
by the roles. New sessions consume the
profile; running sessions keep what they loaded.

### Skills and NotebookLM loadout

Production skill-budget activation uses
`install_seat_profile.py --seat ~/.codex --skills-only` (or add `--check` for a
configuration read-only report). It applies the same absent/match/drift policy
to `skills.max_context_tokens = 3000`, leaving MCP choices unchanged.
Run it only with no other Codex app or session on that seat; it uses the same
version-pinned writer, which is not a cross-process lock.

The separate `--loadout` flag explicitly opts into a NotebookLM read/query filter
as well as the skill budget. It is not installed by default: the matched native
M5 startup experiment observed zero input-token reduction from that filter.
For an existing enabled `notebooklm-mcp`
server, it discovers the current tool inventory through native
`mcpServerStatus/list` and installs `disabled_tools` for everything except:
`notebook_list`, `notebook_get`, `notebook_describe`, `source_describe`,
`source_get_content`, `notebook_query`, `notebook_query_start`,
`notebook_query_status`, `cross_notebook_query`, `collection_list`.

The server inventory is not hard-coded. An absent server is not created, and an
operator-disabled server is not started. Existing different skill bounds,
allowlists and disabled-tool choices are preserved and reported as drift.
After an initial install, newly discovered tools that would require extending
the existing filter are likewise drift, requiring review. All config writes use
one snapshot captured before discovery and the existing version-pinned native
writer; only the requested keys may change. The install receipt,
`state/nuzantara-seat-loadout-install.json`, is updated only on success. A refused
write can leave a backup without a new receipt; retain that backup for inspection
and manual rollback
under the same exclusive-writer condition as the seat profile.

For a research session needing the full NotebookLM tool set, launch
`codex -c 'mcp_servers.notebooklm-mcp.disabled_tools=[]'` with the usual profile
and command arguments. This per-session override restores disabled tools without
editing the installed configuration. An operator's separate `enabled_tools` allowlist
still applies. New sessions consume configuration changes; auth, trust, assigned
models/effort and unrelated profile choices are untouched.

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
