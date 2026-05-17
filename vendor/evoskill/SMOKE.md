# SMOKE.md — Phase 0 smoke test verification

**Date**: 2026-05-18 04:42 WITA
**Machine**: `nuzantara@Nuzantara` (Pro, M4 Pro 48GB)
**Branch**: `feat/agent-library-evoskill-2026-05-17`
**Vendored EvoSkill SHA**: `5ae91616b36ebbe2ea7ee90e8a66393aa8d5e8e4` (tag v1.1.0)
**Spec**: `docs/superpowers/specs/2026-05-17-agent-library-evoskill-design.md`
**Reproducer**: anyone with `uv` installed can run the gates below.

## Gate 1 — `uv run evoskill --help` returns OK

After physical strip of `claude-agent-sdk` + `openai-codex-sdk` + `anthropic` from `pyproject.toml` and the source tree, the CLI must still load successfully.

```bash
cd vendor/evoskill && uv run evoskill --help
```

**Output (verbatim, 2026-05-18 04:41 WITA):**

```
Usage: evoskill [OPTIONS] COMMAND [ARGS]...

  EvoSkill CLI.

Options:
  --help  Show this message and exit.

Commands:
  diff    Diff baseline vs best, or between two specific iterations.
  eval    Evaluate the best skills on the validation set.
  init    Initialize a new EvoSkill project in the current directory.
  logs    Show recent run history.
  remote  Manage remote EvoSkill runs.
  reset   Delete all program branches and frontier tags for a clean slate.
  run     Run the self-improvement loop.
  skills  List all skills learned so far.
```

**Verdict**: PASS — exit 0, no `ModuleNotFoundError: anthropic`, no `ImportError: claude_agent_sdk`.

## Gate 2 — AST scan: 0 anthropic / claude_agent_sdk imports anywhere in src/

```bash
cd vendor/evoskill && python3 -c "
import ast, pathlib, sys
violations = []
for py in pathlib.Path('src').rglob('*.py'):
    tree = ast.parse(py.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ('anthropic', 'claude_agent_sdk'):
                    violations.append(f'{py}:{node.lineno}')
        elif isinstance(node, ast.ImportFrom):
            if (node.module or '') in ('anthropic', 'claude_agent_sdk'):
                violations.append(f'{py}:{node.lineno}')
print('AST scan PASS — 0 violations' if not violations else 'FAIL:\n' + '\n'.join(violations))
sys.exit(0 if not violations else 1)
"
```

**Output (verbatim, 2026-05-18 04:42 WITA):**

```
AST scan PASS — 0 violations
```

**Verdict**: PASS — recursive walk of every `.py` under `src/` confirms no `import anthropic` or `import claude_agent_sdk` at module-top level. The original 4 sites (harness/**init**.py, harness/agent.py twice, registry/sdk_utils.py, cli/shared.py) are all physically rewritten.

## Gate 3 — Stub `__init__.py` raises ImportError on import

```bash
cd vendor/evoskill && uv run python -c "
import sys
sys.path.insert(0, '.')
try:
    from src.harness.claude import executor
    print('FAIL: claude stub did not raise')
    sys.exit(1)
except ImportError as e:
    print(f'claude stub raises OK: {str(e)[:60]}...')
try:
    from src.harness.codex import executor
    print('FAIL: codex stub did not raise')
    sys.exit(1)
except ImportError as e:
    print(f'codex stub raises OK: {str(e)[:60]}...')
print('All stubs raise OK')
"
```

**Output (verbatim, 2026-05-18 04:42 WITA):**

```
claude stub raises OK: src.harness.claude is disabled per Bali Zero Nuzantara CLAUD...
codex stub raises OK: src.harness.codex is disabled per Bali Zero Nuzantara panel ...
All stubs raise OK
```

**Verdict**: PASS — both deleted-package stubs raise loud `ImportError` at first import (no silent `ModuleNotFoundError`).

## Gate 4 — Wrapper script end-to-end (Phase 0 skeleton path)

```bash
BUDGET_USD=0.10 SECRETS_FILE=/dev/null \
    bash scripts/agent-library-evolver-run.sh
```

**Output (verbatim, 2026-05-18 04:42 WITA):**

```
[2026-05-18 04:42:14 WITA] Phase 0 smoke run — BUDGET_USD=0.10 (no LLM call expected)
[2026-05-18 04:42:14 WITA] Telemetry: /tmp/agent-library-evolver/2026-05-18
[2026-05-18 04:42:14 WITA] INFO: psql / PGURL unavailable — skipping advisory lock (Phase 0 OK)
[2026-05-18 04:42:15 WITA] Context raw: /tmp/agent-library-evolver/2026-05-18/context-raw.md (Phase 0 skeleton — no real content)
[2026-05-18 04:42:15 WITA] Context redacted: /tmp/agent-library-evolver/2026-05-18/context-redacted.md (Phase 0 no-op pass-through)
[2026-05-18 04:42:15 WITA] Phase 0 SMOKE: uv run evoskill --help OK
[2026-05-18 04:42:15 WITA] Telemetry: /tmp/agent-library-evolver/2026-05-18/telemetry.json
[2026-05-18 04:42:15 WITA] Phase 0 alert SKIPPED (skeleton — no proposals to announce)
[2026-05-18 04:42:15 WITA] DONE: Phase 0 smoke completed at 2026-05-18 04:42:15 WITA
```

**Verdict**: PASS — wrapper sources secrets, creates telemetry dir, attempts advisory lock, writes context skeleton, invokes `evoskill --help` for inner smoke, persists `telemetry.json`, logs DONE.

## Known Phase 0 limitations (intentional)

| Limitation                                                         | Reason                                                                                                                                   | Phase that addresses it |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| `_redact_pii.py` not implemented                                   | Skeleton only — Phase 1 wires real regex application                                                                                     | Phase 1                 |
| `_evidence_lint.py` not implemented                                | Phase 1 reads `agent-library/config/evidence-rules.yaml`                                                                                 | Phase 1                 |
| `_entailment_check.py` not implemented                             | Phase 1 wires Gemini OAuth + NB-1 fallback                                                                                               | Phase 1                 |
| `BUDGET_USD` per-iter check not enforced                           | Phase 0 has no LLM call; Phase 1 adds the loop                                                                                           | Phase 1                 |
| Wrapper accepts `/dev/null` as `SECRETS_FILE`                      | `[ ! -r ]` returns false for `/dev/null` (it IS readable). Phase 1 will add explicit `/dev/null` rejection plus required-var validation. | Phase 1                 |
| LaunchAgent plist not yet bootstrapped                             | Plist is written but `launchctl bootstrap` deferred to Phase 1 first-live-run                                                            | Phase 1                 |
| `agent-library/proposals/.known-limitations-v1.md` not yet written | Tracks v4 Codex LOW/MEDIUM findings (FTS5 BM25 threshold uncalibrated, etc.) per spec §"Known limitations v1"                            | Phase 1                 |

## Files modified vs upstream v1.1.0

Per `vendor/evoskill/UPSTREAM.md`:

- `pyproject.toml` — 2 lines deleted
- `src/harness/__init__.py` — 2 lines deleted, 9 lines comment added
- `src/harness/agent.py` — TYPE_CHECKING block (6 lines) replaced by 5; 2 lazy-import branches replaced by `raise ImportError` blocks
- `src/cli/shared.py` — `if provider == "anthropic"` 10-line block replaced by `raise ImportError`
- `src/registry/sdk_utils.py` — TYPE_CHECKING block (4 lines) replaced by 5
- `src/harness/claude/` — physically deleted; new `__init__.py` 23-line stub
- `src/harness/codex/` — physically deleted; new `__init__.py` 23-line stub

Everything else in `vendor/evoskill/` is byte-identical to upstream v1.1.0.

## Next step (Phase 1)

LaunchAgent plist + first live run (Sunday after merge) — see Task #5 in
the implementation task list, and spec §"Phase 1 — First live run".
