# SMOKE.md — vendor strip + DeepSeek harness wiring verification

**Date**: 2026-05-18
**Branch**: `feat/agent-library-evoskill-skeleton-v2-2026-05-18`
**Vendored EvoSkill SHA**: `5ae91616b36ebbe2ea7ee90e8a66393aa8d5e8e4` (tag v1.1.0)
**Spec**: `docs/superpowers/specs/2026-05-17-agent-library-evoskill-design.md`
**Scope**: vendor strip + DeepSeek harness wiring ONLY. Wrapper scripts,
config skeleton, LaunchAgent plist, redaction rules, and known-limit
checklist are deferred to a separate Phase 1 PR — round-2 panel
(2026-05-18) flagged the broader Phase 0 surface as INSUFFICIENT
without the actual `_redact_pii.py` redactor implementation.

## Gate 1 — `uv run evoskill --help` returns OK

```bash
cd vendor/evoskill && uv run evoskill --help
```

Expected: CLI help with 8 subcommands (diff/eval/init/logs/remote/
reset/run/skills). Exit 0. No `ModuleNotFoundError: anthropic` or
`ImportError: claude_agent_sdk` from the physical strip.

## Gate 2 — AST scan: 0 anthropic / claude_agent_sdk imports

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

Expected: `AST scan PASS — 0 violations`. The 5 original sites
(harness/**init**.py top-level import, harness/agent.py TYPE_CHECKING

- 2 lazy dispatchers in \_execute_query AND run(), registry/sdk_utils.py
  TYPE_CHECKING, cli/shared.py call_llm anthropic branch, harness/utils.py
  build_options claude+codex branches) are all physically rewritten.

## Gate 3 — Claude + Codex stubs raise loud ImportError on import

```bash
cd vendor/evoskill && uv run python -c "
try:
    from src.harness.claude import executor
    raise RuntimeError('FAIL: claude stub did not raise')
except ImportError as e:
    print(f'claude stub OK: {str(e)[:60]}...')
try:
    from src.harness.codex import executor
    raise RuntimeError('FAIL: codex stub did not raise')
except ImportError as e:
    print(f'codex stub OK: {str(e)[:60]}...')
"
```

Expected: both stubs raise `ImportError` at first import (loud, NOT
silent `ModuleNotFoundError` that downstream code could except-swallow).

## Gate 4 — DeepSeek harness stub: set_sdk accepted + execute raises

```bash
cd vendor/evoskill && uv run python -c "
import asyncio
from src.harness.deepseek import build_deepseek_options, execute_query, parse_response
from src.harness import set_sdk, get_sdk, is_deepseek_sdk

set_sdk('deepseek')
assert get_sdk() == 'deepseek'
assert is_deepseek_sdk()

opts = build_deepseek_options(system='test')
assert opts['sdk'] == 'deepseek'

try:
    asyncio.run(execute_query(opts, 'q'))
    raise RuntimeError('FAIL: should have raised NotImplementedError')
except NotImplementedError as e:
    print('deepseek stub raises NotImplementedError OK')
"
```

Expected: `deepseek stub raises NotImplementedError OK`. Round-2 panel
(2026-05-18) found CRITICAL convergent that `evolver.toml provider=deepseek`
was load-bearing for Phase 1 but the SDK dispatcher was missing in 5
upstream surfaces. This gate verifies all 5 are now wired.

## Known limitations (intentional — Phase 1 scope)

| Limitation                                                                                 | Why deferred                                                                                                                                                                                                                                       | Phase that addresses it |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| `_redact_pii.py` not implemented                                                           | Round-2 panel found YAML-only redaction patterns INSUFFICIENT — gate is the Python code that applies them                                                                                                                                          | Phase 1                 |
| `agent-library/config/{evolver,evidence-rules,redaction-rules}.{toml,yaml}` not in this PR | Round-2 Codex caught `evolver.toml` config schema mismatch vs upstream EvoSkill `load_config()` which requires `[harness][evolution][dataset][scorer]` sections, NOT `[provider][loop][budget]`. Defer config writing until the schema is correct. | Phase 1                 |
| `scripts/agent-library-evolver-run.sh` wrapper not in this PR                              | Without redactor + config, the wrapper has nothing useful to invoke                                                                                                                                                                                | Phase 1                 |
| LaunchAgent plist not in this PR                                                           | Cron has nothing to run until wrapper exists                                                                                                                                                                                                       | Phase 1                 |
| `BUDGET_USD` per-iter check                                                                | EvoSkill internal T=10 loop runs in ONE blocking command — bash can NOT enforce mid-run. Phase 1 decides: patch upstream OR document post-run-only                                                                                                 | Phase 1                 |
| `call_llm` provider=deepseek + `infer_provider` no fallback                                | `cli/shared.py:call_llm()` still supports only anthropic/openai/openrouter/google. Phase 1 adds the deepseek branch.                                                                                                                               | Phase 1                 |

## Files modified vs upstream v1.1.0

Per `vendor/evoskill/UPSTREAM.md`:

- `pyproject.toml` — 2 lines deleted (`claude-agent-sdk` + `openai-codex-sdk`)
- `src/harness/__init__.py` — drop 2 claude/codex imports, add deepseek import + is_deepseek_sdk export
- `src/harness/agent.py` — TYPE_CHECKING deleted; claude+codex raise in BOTH `_execute_query` AND `run()`; deepseek branches ADDED to both
- `src/harness/utils.py` — claude+codex branches raise; deepseek branch ADDED (third dispatcher)
- `src/harness/sdk_config.py` — deepseek in SDKType + \_VALID_SDKS + new is_deepseek_sdk()
- `src/cli/shared.py` — `if provider == "anthropic"` block replaced by raise
- `src/registry/sdk_utils.py` — TYPE_CHECKING deleted; deepseek branch in options_to_config
- `src/harness/claude/` — physical rm + stub raising ImportError
- `src/harness/codex/` — physical rm + stub raising ImportError
- `src/harness/deepseek/` — NEW: Phase 0 stubs raising NotImplementedError

Everything else in `vendor/evoskill/` is byte-identical to upstream v1.1.0.

## Next step

Phase 1 wiring PR (separate from this one):

1. Write `scripts/_redact_pii.py` Python module implementing 2-pass
   logic + dynamic CRM name loading + NPWP context-aware substitution
2. Write `agent-library/config/evolver.toml` with correct EvoSkill
   `[harness][evolution][dataset][scorer]` sections (NOT the v5-spec
   `[provider][loop][budget]` which is incompatible)
3. Patch `cli/shared.py:call_llm()` to support `provider == "deepseek"`
4. Implement real `vendor/evoskill/src/harness/deepseek/executor.py`
   (DeepSeek V4 Pro Chat Completions HTTP adapter)
5. Run 3-LLM panel review before merge
