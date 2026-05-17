# EvoSkill — Bali Zero Nuzantara vendored fork

## Provenance

| Field                | Value                                                                                                                                                                                   |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Upstream source      | https://github.com/sentient-agi/EvoSkill                                                                                                                                                |
| Upstream tag         | `v1.1.0`                                                                                                                                                                                |
| Upstream commit SHA  | `5ae91616b36ebbe2ea7ee90e8a66393aa8d5e8e4`                                                                                                                                              |
| Vendored date        | 2026-05-18                                                                                                                                                                              |
| Vendored by          | Antonello Siano (`zero@balizero.com`)                                                                                                                                                   |
| License              | Apache 2.0 (kept verbatim — see `LICENSE`)                                                                                                                                              |
| Reason for vendoring | CLAUDE.md hard rule: no paid Anthropic API ever; physical strip of `claude-agent-sdk` + `anthropic` + `openai-codex-sdk`. Upstream is `pip install`-ready but ships Claude SDK in deps. |

## Why a vendored fork (not a submodule)

- **Auditable** — every byte of the dependency tree is visible in `git diff`. CI can grep for `anthropic|claude_agent_sdk` and fail the build if anything reappears.
- **No submodule fragility** — submodules silently drift on `git checkout` of sibling branches; an in-tree copy stays put.
- **Apache 2.0 permissive license** allows vendoring + modification without contagion.
- **Quarterly upstream refresh policy** documented below.

## Diff list vs upstream tag v1.1.0

### 1. `pyproject.toml`

**Removed dependencies:**

```diff
-    "openai-codex-sdk>=0.1.11",
-    "claude-agent-sdk>=0.1.16",
```

**Rationale:**

- `claude-agent-sdk` — pulls in `anthropic` Python SDK transitively. CLAUDE.md
  hard rule: no `ANTHROPIC_API_KEY` ever (Antonello holds 2 Claude MAX x20
  OAuth plans — per-token paid API would duplicate flat fee).
- `openai-codex-sdk` — used by upstream `src/harness/codex/` to drive
  ChatGPT Pro Codex CLI. Autonomous loops (this is exactly our use case)
  trigger Cloudflare protections + 500-msg/3h quota cap, which would lock
  Antonello's daily Pro access. v2 Codex panel finding #2 HIGH. We use
  DeepSeek V4 Pro API (~$0.10-0.30/run) as cheap insurance instead.

### 2. `src/harness/__init__.py`

```diff
-from .claude.options import build_claudecode_options
-from .codex.options import build_codex_options
```

Top-level imports of the now-deleted claude/codex options modules would
fail with `ImportError` at first `import evoskill.harness`. The
`is_claude_sdk` / `is_codex_sdk` feature flags stay in `sdk_config` for
backwards-compatible call sites (they return `False` deterministically),
but executors raise `ImportError` on actual invocation (see stubs §6).

`__all__` updated accordingly: `build_claudecode_options` and
`build_codex_options` no longer exported.

### 3. `src/harness/agent.py`

**Lines 25-30** — TYPE_CHECKING block deleted:

```diff
-# Import ClaudeAgentOptions only for type hints (not at runtime).
-# This allows the module to load even if claude-agent-sdk is not installed.
-if TYPE_CHECKING:
-    from claude_agent_sdk import ClaudeAgentOptions as ClaudeAgentOptionsType
-else:
-    ClaudeAgentOptionsType = Any
+# Bali Zero Nuzantara vendor strip (CLAUDE.md hard rule):
+# the upstream TYPE_CHECKING import of `claude_agent_sdk` was physically
+# removed. Type hint becomes Any (no runtime change — TYPE_CHECKING is
+# always False at runtime).
+ClaudeAgentOptionsType = Any
```

`TYPE_CHECKING` blocks never execute at runtime in CPython, but grep would
still match the line — which would fail the CI gate that asserts no
`anthropic|claude_agent_sdk` references anywhere.

**Lines 164-167** — `claude` branch in `_execute_query` replaced with
raise:

```diff
-        if sdk == "claude":
-            from .claude import executor as _claude_executor
-            return await _claude_executor.execute_query(options, query)
+        if sdk == "claude":
+            raise ImportError(
+                "Claude SDK disabled per Bali Zero Nuzantara CLAUDE.md "
+                "hard rule (no Anthropic API ever). Configure provider="
+                "deepseek in agent-library/config/evolver.toml instead."
+            )
```

**Lines 173-176** — `codex` branch in `_execute_query` replaced with
raise:

```diff
-        if sdk == "codex":
-            from .codex import executor as _codex_executor
-            return await _codex_executor.execute_query(options, query)
+        if sdk == "codex":
+            raise ImportError(
+                "Codex SDK removed from Bali Zero Nuzantara vendored "
+                "fork (panel finding: ChatGPT Pro rate-limit risk on "
+                "autonomous loops). Configure provider=deepseek instead."
+            )
```

### 4. `src/cli/shared.py`

**Lines 85-94** — `import anthropic` + `AsyncAnthropic` block deleted:

```diff
     if provider == "anthropic":
-        import anthropic
-
-        client = anthropic.AsyncAnthropic(api_key=api_key)
-        response = await client.messages.create(
-            model=normalized_model,
-            max_tokens=16,
-            messages=[{"role": "user", "content": prompt}],
-        )
-        return response.content[0].text
+        raise ImportError(
+            "Anthropic provider disabled per Bali Zero Nuzantara "
+            "CLAUDE.md hard rule (no paid Anthropic API ever). "
+            "Switch to provider=deepseek (DeepSeek V4 Pro API) or "
+            "provider=google (Gemini 3.1 Pro free OAuth)."
+        )
```

Provider detection logic (`infer_provider`) kept intact — model names
starting with `claude` still map to `provider="anthropic"`, but the
actual `call_llm("anthropic", ...)` call now raises rather than silently
attempting to import the SDK. Failing-loud preferred over failing-quiet
per CLAUDE.md anti-hallucination rule.

### 5. `src/registry/sdk_utils.py`

**Lines 11-14** — TYPE_CHECKING block deleted (same pattern as agent.py):

```diff
-if TYPE_CHECKING:
-    from claude_agent_sdk import ClaudeAgentOptions
-else:
-    ClaudeAgentOptions = Any
+ClaudeAgentOptions = Any
```

Caught by AST scan post-edit — the upstream spec missed this one (it only
listed `agent.py` and `shared.py`). Documented for future upstream
refresh.

### 6. `src/harness/claude/` and `src/harness/codex/` — physical deletion + stub

Both directories had upstream content:

- `claude/__init__.py`, `executor.py`, `options.py` — Claude SDK glue
- `codex/__init__.py`, `executor.py`, `options.py`, `skill_discovery.py` — Codex CLI glue

**All upstream files in these two dirs were physically deleted** (`rm -rf`).
Each dir was then recreated with a single `__init__.py` stub that raises
`ImportError` on import. This makes accidental `from src.harness.claude
import ...` calls fail LOUDLY at import time rather than silently with
`ModuleNotFoundError` that downstream code could `try/except` swallow.

## Verification post-edit (CI gates)

These checks MUST pass before any commit on this fork:

1. **AST scan** — no top-level `import anthropic` or `import claude_agent_sdk` anywhere in `vendor/evoskill/src/`:

   ```bash
   python3 -c "
   import ast, pathlib, sys
   violations = []
   for py in pathlib.Path('vendor/evoskill/src').rglob('*.py'):
       tree = ast.parse(py.read_text())
       for node in ast.walk(tree):
           if isinstance(node, ast.Import):
               for alias in node.names:
                   if alias.name in ('anthropic', 'claude_agent_sdk'): violations.append(str(py))
           elif isinstance(node, ast.ImportFrom):
               if (node.module or '') in ('anthropic', 'claude_agent_sdk'): violations.append(str(py))
   sys.exit(1 if violations else 0)
   "
   ```

2. **Grep (defense in depth)** — should return only comments and docstrings:

   ```bash
   grep -rn "^[^#\"']*\(import anthropic\|from anthropic\|import claude_agent_sdk\|from claude_agent_sdk\)" \
     vendor/evoskill/src/ | grep -v '__init__.py:.*Stub' || true
   ```

3. **Stub raise check** — importing the deleted modules must raise `ImportError`:

   ```bash
   cd vendor/evoskill && uv run python -c "
   try:
       from src.harness.claude import executor
       raise RuntimeError('STRIP FAILED: stub did not raise')
   except ImportError:
       print('claude stub raises OK')
   try:
       from src.harness.codex import executor
       raise RuntimeError('STRIP FAILED: codex stub did not raise')
   except ImportError:
       print('codex stub raises OK')
   "
   ```

## Upstream refresh policy

Manual quarterly review of `git diff upstream/main HEAD --stat` to decide:

1. **Cherry-pick fixes only** (typical case) — apply non-breaking bug fixes
   from upstream, re-apply this diff list on top.
2. **Re-vendor whole** — if upstream restructures `src/harness/` etc, drop
   the current vendor dir, clone the new tag, re-apply this diff list.
3. **Stay frozen** — if upstream takes a direction incompatible with our
   hard rules (e.g., removes `provider=` config), stay on the current
   pinned version indefinitely.

Anyone executing a refresh MUST re-run all 3 verification CI gates above,
and update the "Provenance" table with the new SHA + date.

## Optional dependencies left untouched

- `opencode-ai`, `openhands-sdk`, `openhands-tools`, `goose` — not banned;
  Bali Zero may opt-in later. Their executors remain functional in
  upstream form.
- `eval` extra (dspy, datasets, torch) — out of scope for v1, never installed.
- `notebooks` extra (jupyter stack) — out of scope, never installed.

## Files left identical to upstream

Every `src/**.py` not listed in §1-§6 above is byte-identical to upstream
v1.1.0. `assets/`, `docs/`, `examples/`, `notebooks/`, `scripts/`,
`tests/`, `LICENSE`, `evoskill_tech_report.pdf`, `Dockerfile`, `uv.lock`
are all upstream as-is.

If you find drift not documented in this file, that's a bug — open an
issue or restore from upstream.

## Known limitations carried over from upstream

These are NOT our additions — they are upstream behaviors we accept:

- `infer_provider("claude-something")` returns `"anthropic"` (line 52 of
  `src/cli/shared.py`). Downstream `call_llm("anthropic", ...)` will
  raise per §4 above. Loud failure is the intended behavior.
- `options_to_config()` in `sdk_utils.py:197` defaults `sdk: "claude"` as
  metadata fallback when no explicit SDK was set. This is metadata for
  round-tripping ProgramConfig YAML files — never reaches an executor
  unless something explicitly switches back to claude SDK, which would
  hit the ImportError gate in `agent.py`.
- `src/cache/__init__.py` and `src/cache/run_cache.py` reference
  `.claude/skills/**` paths — these are EvoSkill's _workspace_ convention
  (skills live under `.claude/` in the user's project), NOT SDK imports.
  Kept verbatim.
