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

## Gate 4b — call_llm("anthropic") raises ImportError BEFORE auth lookup

Panel round 3 Codex BLOCKING #2: the upstream `call_llm()` called
`ensure_provider_api_key("anthropic")` BEFORE the `if provider ==
"anthropic": raise` branch, so first failure was `RuntimeError: Set
ANTHROPIC_API_KEY` — a misleading message suggesting setting the key
is the fix. Fix moves the raise FIRST.

```bash
cd vendor/evoskill && uv run python -c "
import asyncio, os
from src.cli.shared import call_llm
os.environ.pop('ANTHROPIC_API_KEY', None)
try:
    asyncio.run(call_llm('anthropic', 'claude-sonnet-4-6', 'test'))
    raise RuntimeError('FAIL: should have raised')
except ImportError as e:
    assert 'Set ANTHROPIC_API_KEY' not in str(e), 'still suggests setting the key'
    assert 'CLAUDE.md hard rule' in str(e)
    print('call_llm anthropic raise BEFORE auth: OK')

# Defense in depth: even direct call to ensure_provider_api_key must hard-deny
from src.harness.provider_auth import ensure_provider_api_key
try:
    ensure_provider_api_key('anthropic')
    raise RuntimeError('FAIL: should have raised')
except ImportError as e:
    assert 'BANNED' in str(e) or 'CLAUDE.md hard rule' in str(e)
    print('provider_auth.ensure_provider_api_key hard-denies anthropic: OK')
"
```

Expected: both checks pass.

## Gate 4c (Phase 1 Task #22) — DeepSeek branch in call_llm + infer_provider

Verifies the `deepseek` branch added to `cli/shared.py` routes correctly,
the `infer_provider("deepseek-v4-pro")` no longer falls through to the
anthropic fallback, and `make_scorer` default model is `deepseek-v4-pro`.

```bash
cd /Users/nuzantara/Desktop/nuzantara-wt-evoskill-phase1 && \
  python3 -m pytest scripts/test_call_llm_deepseek.py -v --tb=short | tail -25
```

Expected: `14 passed in <2s`. Tests cover:

- `infer_provider("deepseek-v4-pro") == "deepseek"` (no fallback to
  anthropic — was the L9 silent-trap bug)
- `_normalize_provider_model("deepseek", "deepseek/v4-pro") == "v4-pro"`
- `call_llm("deepseek", ...)` constructs
  `openai.AsyncOpenAI(base_url="https://api.deepseek.com/v1", api_key=...)`
  and forwards model + max_tokens + messages
- `DEEPSEEK_API_KEY` unset → `RuntimeError("API key not configured")`
- `make_scorer({type:"llm"})` default model is now `deepseek-v4-pro`
- No regression: `call_llm("anthropic", ...)` still raises ImportError
  with "BANNED"/"CLAUDE.md hard rule" message
- No regression: `infer_provider` claude/gpt/gemini/anthropic-prefix
  routes preserved
- `infer_provider(scorer.model)` from the actual evolver.toml matches
  `scorer.provider` (belt-and-suspenders cross-check)

Quick CLI smoke (requires real `DEEPSEEK_API_KEY` in env — skip if not
available, the unit tests above are sufficient):

```bash
DEEPSEEK_API_KEY="sk-..." cd vendor/evoskill && uv run python -c "
import asyncio
from src.cli.shared import call_llm
result = asyncio.run(call_llm('deepseek', 'deepseek-v4-pro', 'Reply with the single digit 7.'))
print(f'live call OK: {result!r}')
"
```

Expected (if key set): `live call OK: '7'` or similar single-digit
response. If key unset: `RuntimeError: deepseek API key not configured`.

## Gate 5 — No `anthropic` PyPI package in vendor venv (no transitive)

Panel round 3 Codex BLOCKING #1: previous `uv sync` resolved
`anthropic 0.94.0` transitively via `openhands-tools` →
`browser-use` → `anthropic`. AST scan was clean but the dependency tree
still pulled the banned package, violating "no anthropic anywhere"
CLAUDE.md posture. Fix: remove `openhands-tools` from `pyproject.toml`
(harness/openhands/ stays for opt-in, falls back to ImportError at
runtime if anyone invokes OpenHands SDK in Phase 1).

```bash
cd vendor/evoskill && uv pip list 2>/dev/null | grep -iE "^anthropic|^claude-agent-sdk|^browser-use" | wc -l
```

Expected: `0` (no anthropic / claude-agent-sdk / browser-use installed).

## Gate 6 (Phase 0) — superseded by Gate 6b (Phase 1 Task #23)

Phase 0 stub raised `NotImplementedError` on `execute_query()`. Phase 1
Task #23 replaces the stub with a real DeepSeek V4 Pro adapter. The
new gate is below.

## Gate 6b (Phase 1 Task #23) — DeepSeek executor real impl

`execute_query()` no longer raises `NotImplementedError`. Instead it
either (a) raises `RuntimeError` if `DEEPSEEK_API_KEY` env var is
unset (loud-fail, clear message), or (b) makes a live POST to
`https://api.deepseek.com/v1/chat/completions` and returns the parsed
JSON.

```bash
cd /Users/nuzantara/Desktop/nuzantara-wt-evoskill-phase1 && \
  python3 -m pytest scripts/test_deepseek_executor.py -q --tb=short | tail -10
```

Expected: `21 passed in <0.1s`. Tests cover:

- Happy path: 200 OK, choices[0].message.content parses as JSON,
  Pydantic model validates, AgentTrace fields populated
- Auth: `DEEPSEEK_API_KEY` missing → `RuntimeError` with clear message
- 401 Unauthorized → `DeepSeekAPIError` (non-retryable, propagates)
- 500 Internal Server Error → `DeepSeekTransientError` after 4
  attempts (initial + 3 retries: 30s → 60s → 120s — backoffs mocked)
- 429 Too Many Requests → retryable (same path as 500)
- 408 Request Timeout → retryable
- 400 Bad Request → `DeepSeekAPIError` non-retryable
- Network errors (`httpx.ConnectError`, `ReadTimeout`) → retryable
- JSON code-fence stripping (` ```json ... ``` ` block extracted)
- Pydantic `ValidationError` captured into `parse_error`, NOT raised
- Empty `messages` list / non-dict response → `_empty_trace_fields`
- Cost math: prompt_cache_hit + prompt_cache_miss + completion against
  pricing snapshot for `deepseek-v4-pro`
- Fuzzy model prefix match: `deepseek-v4-pro-2024-Q3` → pricing for
  `deepseek-v4-pro`
- `response_format = {"type": "json_object"}` builder when schema
  non-empty
- `reasoning_effort` forwarded conditionally
- End-to-end round trip via `parse_response()`

Optional live smoke (requires real `DEEPSEEK_API_KEY`):

```bash
DEEPSEEK_API_KEY="sk-..." cd vendor/evoskill && uv run python -c "
import asyncio
from src.harness.deepseek import build_deepseek_options, execute_query, parse_response

opts = build_deepseek_options(system='You are a calculator. Output JSON {\"answer\": <int>} only.')
opts['schema'] = {'answer': {'type': 'integer'}}
opts['max_tokens'] = 100

messages = asyncio.run(execute_query(opts, 'What is 7 * 6?'))
print(f'raw response: {messages[0][\"choices\"][0][\"message\"][\"content\"][:200]}')

fields = parse_response(messages, response_model=None, get_options=lambda: opts)
print(f'total_cost_usd: {fields[\"total_cost_usd\"]}')
print(f'usage: {fields[\"usage\"]}')
print(f'is_error: {fields[\"is_error\"]}')
"
```

Expected (if key set): non-zero `total_cost_usd`, usage dict populated,
`is_error=False`. Without key: `RuntimeError: DEEPSEEK_API_KEY env var not set`.

## Gate 7 (Phase 1 Task #21) — load real agent-library evolver config

Verifies the Phase 1 `agent-library/.evoskill/config.toml` is
schema-correct (matches upstream `load_config()` dataclass shape), the
seed dataset CSV is parsable, `task.md` is split into description +
constraints, and the `cli/main.py` Click entry-point loads.

```bash
cd vendor/evoskill && uv run evoskill --help | head -3
```

Expected: 3 lines starting with `Usage: evoskill [OPTIONS] COMMAND...`.
This sub-gate exercises the upstream `src/cli/main.py` re-add (UPSTREAM.md
§8 — Phase 0 dropped it; Phase 1 restored verbatim).

```bash
cd vendor/evoskill && uv run python3 -c "
import sys
sys.path.insert(0, '.')
from pathlib import Path
from src.cli.config import load_config
import pandas as pd

cfg_path = Path('/Users/nuzantara/Desktop/nuzantara-wt-evoskill-phase1/agent-library/.evoskill/config.toml')
cfg = load_config(config_path=cfg_path)

assert cfg.harness.name == 'deepseek', f'harness.name={cfg.harness.name}'
assert cfg.harness.model == 'deepseek-v4-pro', f'harness.model={cfg.harness.model}'
assert cfg.evolution.mode == 'skill_only'
assert cfg.evolution.iterations == 10
assert cfg.evolution.frontier_size == 3
assert cfg.dataset.question_column == 'question'
assert cfg.dataset.ground_truth_column == 'ground_truth'
assert cfg.scorer.type == 'llm'
assert cfg.scorer.provider == 'deepseek'
assert cfg.execution == 'local'

df = pd.read_csv(cfg.dataset_path)
assert len(df) == 5, f'expected 5 seed rows, got {len(df)}'
assert list(df.columns) == ['question', 'ground_truth', 'category']

assert 'Agent Library Evolver' in cfg.task_description
assert 'must be one of the 9 pattern names' in cfg.task_constraints.lower()

print('Gate 7 PASS — Phase 1 evolver.toml schema + dataset + task.md valid')
"
```

Expected: `Gate 7 PASS — Phase 1 evolver.toml schema + dataset + task.md valid`.

Note: `harness.model = "deepseek-v4-pro"` MUST be set explicitly in the
TOML. Upstream `model_aliases.HarnessName` Literal does NOT include
`"deepseek"`; if `model` is omitted, `normalize_harness_model("deepseek",
None)` falls through to `default_model_for_harness("deepseek")` which
raises `KeyError` because `_DEFAULT_MODELS` lacks the key. Documented
inline in `agent-library/.evoskill/config.toml` header.

## Gate 8 (Phase 1 Task #26) — LaunchAgent plist + wrapper smoke

The plist `infra/launchd/com.balizero.agent-library-evolver.weekly.plist`
is the git-tracked source of truth per cicatrix scar 2026-04-29 (plist
corruption — the only safe reload is to overwrite from repo).

```bash
# 1) Plist syntax valid
plutil -lint infra/launchd/com.balizero.agent-library-evolver.weekly.plist
# Expected: ... OK

# 2) Install + bootstrap (only after this PR merges to main)
cp infra/launchd/com.balizero.agent-library-evolver.weekly.plist \
   ~/Library/LaunchAgents/
# (if previously loaded — Phase 0 had a stub plist already loaded —
# bootout first to pick up the new env vars REPO_ROOT + TELEMETRY_DIR)
launchctl bootout gui/$(id -u) \
   ~/Library/LaunchAgents/com.balizero.agent-library-evolver.weekly.plist \
   2>/dev/null || true
launchctl bootstrap gui/$(id -u) \
   ~/Library/LaunchAgents/com.balizero.agent-library-evolver.weekly.plist

# 3) Verify loaded
launchctl list | grep agent-library-evolver
# Expected: "-  0  com.balizero.agent-library-evolver.weekly"
#           (status 0 = never run yet; will populate after first kickstart)

# 4) Smoke first run with BUDGET cap $0.10 (no real DeepSeek call yet —
# the wrapper exits dry-run-style if EVOSKILL_DRY_RUN=1 OR if --dry-run
# flag is passed via wrapper args — see scripts/agent-library-evolver-run.sh).
# To smoke against real DeepSeek API at low budget:
launchctl setenv BUDGET_USD 0.10
launchctl kickstart -k gui/$(id -u)/com.balizero.agent-library-evolver.weekly
# Then watch:
tail -f ~/logs/agent-library-evolver.err.log
# Expected: secrets validated → context gathered → redacted → evoskill
# run → telemetry parsed → ≤ $0.10 → evidence/entailment gates → Telegram
# alert. Exit 0 if 0 proposals (clean), exit 5 if budget exceeded.

# 5) Dry-run smoke (no real API call, no $) — preferred for PR review
bash scripts/agent-library-evolver-run.sh --dry-run
# Expected: ~1s exit 0 with context gathered + redacted, evoskill run +
# gates skipped.
```

**Verified on this branch 2026-05-19:**

- `plutil -lint`: OK
- `bash -n scripts/agent-library-evolver-run.sh`: syntax OK
- `--dry-run` end-to-end: ~1s, 49893 bytes context-raw, 49942 bytes
  redacted, 3/3 fail-closed gates verified (`/dev/null` rejected,
  missing file rejected, missing `DEEPSEEK_API_KEY` rejected).
- `launchctl kickstart` real-budget smoke: DEFERRED to post-merge
  bootstrap (Phase 1 PR ships the source of truth; bootstrap on Pro
  happens after `gh pr merge`).

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

- `pyproject.toml` — 3 lines deleted (`claude-agent-sdk` + `openai-codex-sdk` + `openhands-tools` — the last one added 2026-05-18 panel round 3 Codex BLOCKING #1 because it pulled `browser-use → anthropic` transitively)
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
