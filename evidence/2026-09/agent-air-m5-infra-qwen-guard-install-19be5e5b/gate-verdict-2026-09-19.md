# Gate verdict — agent/air-m5/infra/qwen-guard-install @ fea83b067a

**Verdict: REJECT (REWORK-BUILD).** BLUE gate, fresh Claude session on Air-M5, 2026-09-19.
Untracked on purpose: the gate signs, it does not enter the contribution chain.
Not pushed, no PR opened, nothing merged.

## The blocking finding — the Qwen hook is registered but INERT for shell and Read

Qwen Code 0.23.0 (the `qwen` binary this machine runs) passes the CANONICAL tool name
to PreToolUse hooks (`firePreToolUseHook(messageBus, canonicalName, ...)`) and matches the
`matcher` string in `HookPlanner.matchesToolName`: split on `|`, exact match of each
alternative against `getAliasSetForTool(tool)`, then a case-sensitive regex fallback.

Real alias sets (read from the bundle's exported ToolNames/ToolDisplayNames tables):
- `run_shell_command` -> {run_shell_command, Shell, ShellTool}   — "Bash" is NOT an alias
- `read_file`         -> {read_file, ReadFile, ReadFileTool}     — "Read" is NOT an alias
- `monitor`           -> {monitor, Monitor, MonitorTool}

Executed oracle (node import of chunk-XX7QFP34.js, `isToolEnabled` uses the real alias set):
```
alias-set has "Bash"  for run_shell_command -> false
alias-set has "Read"  for read_file         -> false
"Bash|Monitor|Read"  run_shell_command -> false
"Bash|Monitor|Read"  read_file         -> false
"Bash|Monitor|Read"  monitor           -> true
```
So the entry installed in `~/.qwen/settings.json` (matcher `Bash|Monitor|Read`) never fires
on a shell command or a file read. The guard itself is fine — invoked directly it DENIES
`run_shell_command`/`read_file` payloads (X2/X5) — the harness just never invokes it.
Superscar #2 (exists != armed) in its purest form; the builder's own "known limit" was
exactly where the defect lived. "Bash"/"Read" exist in Qwen only in the PERMISSIONS rule
parser (TOOL_NAME_ALIASES), not in the hook matcher.

## Rework items (all inside the branch's own files)

1. **MATCHER** must carry the canonical Qwen names. Verified to match all three:
   `Bash|Shell|run_shell_command|Read|ReadFile|read_file|Monitor|monitor`
   (oracle: run_shell_command -> true, read_file -> true, monitor -> true, glob -> false).
2. **`_add_hook` idempotency is a substring test on the file name** — an existing entry with
   a stale path or a wrong matcher (the live one on M5 right now) is reported "already
   registered" and left in place. It must compare command AND matcher and REPLACE a stale
   entry; otherwise re-running the fixed installer on M5 will not repair the live file.
3. **The installer's verification cannot prove the matcher.** State it in the docstring and
   add a test that pins MATCHER against the canonical Qwen names, so the next harness
   rename is caught by a red test, not by a leak.
4. P2: `test_install_qwen_secret_guard.py` runs in no workflow (no glob sweeps
   `infra/claude-hooks/`); wire it or say why not. P2: `test_never_prints_a_credential_value`
   asserts `value not in output` — on failure pytest's introspection would print the value;
   compute a boolean first.
5. Correct the claims: deterministic floor for this diff is **1** (`evidence_pack_lint.py
   --print-floor`, source none), not 2; the brief may still DECLARE gear 2. Commit message
   and PR body must not say the Qwen harness is protected until a live Qwen tool call is
   observed to be denied.

## What held (executed this session)

- pytest installer suite: 11 passed. ruff: clean. guard corpus: 14 passed (64 rows).
- `lint_home_fork.py --check`: exit 0, "clean — 46 live copy/copies match their repo twin".
  sha256 live == repo for guard (3c97cbfaf9d85657…) and registry (e57b661d0a9706c1…).
- `test_lint_home_fork.py`: 26 passed. guard-conformance: 0 violations. quickcheck: rc 0
  (scripts-coupling STALE is pre-existing, out of this diff).
- Installer re-run: "already registered; settings.json untouched", sha unchanged, 1 backup.
- Refusal path (`--repo-hooks-dir` empty dir): rc 3, settings.json sha unchanged.
- Stored command line invoked directly: 3/3 DENY (X2, X4, X5), 3/3 ALLOW as claimed; plus
  `run_shell_command` -> DENY X2 and `read_file`+file_path -> DENY X5.
