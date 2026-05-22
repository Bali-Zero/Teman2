---
date: 2026-05-22
domain: operations
client_case: internal — Antigravity CLI migration spec v2 post 4-LLM panel
sources: 4
status: DRAFT v2 — 4-LLM panel synthesized, awaiting Antonello sign-off
supersedes: gemini-to-agy-migration-spec-v1.md
---

# Spec v2: migrate `gemini` CLI → `agy` CLI across Nuzantara

## Changelog v1 → v2

- **3 NUOVI call-site scoperti empiricamente da Codex** — inventario v1 INCOMPLETO (51 → 54 file + 1 SYMBIOSIS violation)
- **Strategy C ridefinita**: Wave 3 deve installare ENTRAMBI agy + gemini legacy (Codex finding #2)
- **CRITICAL race scoperti**: `~/.gemini/oauth_creds.json` write race + `settings.json` schema compat untested (agy + DeepSeek + NB-1 convergent 3/3)
- **Pattern canonico v1 declassato**: `os.path.exists` + hardcoded paths sono anti-pattern Fly Linux + supply chain (agy + codex + deepseek convergent 3/3, NB-1 indipendente)
- **MCP chains.py viola SYMBIOSIS Law 1**: HTTP API call diretta scoperta da codex → fuori scope di questo spec ma documentata come debt
- **Wave 3 BLOCKED**: nessun URL ufficiale agy + nessun checksum — supply-chain risk inaccettabile per fresh install team

## Panel verdict matrix

4 panel: agy (Gemini 3.1 Pro via stesso agy CLI — meta), codex (GPT-5.5), DeepSeek V4 Pro, NB-1 (NotebookLM Codebase & Architecture).

### Convergenza 4/4 (consensus, ship-blocker)

| #   | Finding                                                                                     | agy         | codex           | deepseek    | NB-1                                                                    | Impact                     | Action v2                                                                         |
| --- | ------------------------------------------------------------------------------------------- | ----------- | --------------- | ----------- | ----------------------------------------------------------------------- | -------------------------- | --------------------------------------------------------------------------------- |
| C1  | Hardcoded paths `/Users/nuzantara/...` + `/opt/homebrew/...` break su Fly Linux + altri dev | CRITICAL #1 | implicit via #4 | CRITICAL #1 | scar `feedback_claude_cli_linux_hang.md`                                | P0 — outage prod garantito | usare `shutil.which("agy")` + env `GEMINI_BIN` override + `os.access(_, os.X_OK)` |
| C2  | Race condition `~/.gemini/oauth_creds.json` su refresh token concorrente                    | CRITICAL #2 | HIGH #7         | HIGH #3     | scar `runbook_nlm_auth_stability_fix.md` "Auth-token rotation conflict" | P0 — auth corruption       | file lock atomico O serialize via single canonical writer                         |

### Convergenza 3/4 (high confidence)

| #   | Finding                                               | Confirmers                                                                   | Impact                            | Action v2                                                                  |
| --- | ----------------------------------------------------- | ---------------------------------------------------------------------------- | --------------------------------- | -------------------------------------------------------------------------- |
| C3  | `settings.json` schema compat agy NON testata         | deepseek HIGH #4, codex HIGH #7, NB-1 (pattern HOME override per subprocess) | HIGH — primo agy run può crashare | integration test `agy -p "test"` con production settings.json PRIMA Wave 1 |
| C4  | Wave 1 audit per `-m`/`-o stream-json` incompleto     | codex CRITICAL #1, deepseek CRITICAL #2, agy MEDIUM #7 (model contamination) | CRITICAL — silent behavior change | aggiungere preflight audit per ogni Wave 1 file                            |
| C5  | Test pattern `GEMINI_BIN` env override = anti-pattern | NB-1 (test mocking via `@patch`), codex MEDIUM #9, agy MEDIUM #8             | MEDIUM — tech debt                | usare `@patch("subprocess.run")` in test suite, NON env var                |
| C6  | Wave 3 supply chain — URL TBD + no checksum           | codex CRITICAL #3, deepseek HIGH #5, agy implicit                            | P0 — supply-chain attack vector   | BLOCK Wave 3 finché Antonello fornisce URL ufficiale + SHA256              |

### Convergenza 2/4

| #   | Finding                                                         | Confirmers                     | Impact                                                         | Action v2                                |
| --- | --------------------------------------------------------------- | ------------------------------ | -------------------------------------------------------------- | ---------------------------------------- |
| C7  | `subprocess.run` no `check=True` + `TimeoutExpired` non gestito | agy HIGH #3+#4                 | HIGH — silent data corruption                                  | wrap try/except + `check=True` mandatory |
| C8  | Permission/sandbox semantics agy vs gemini diversi              | codex HIGH #6                  | HIGH — script con `--approval-mode yolo` perdono comportamento | restano legacy (Strategia C estesa)      |
| C9  | Timeout 310s Python vs 5m agy mismatch                          | agy LOW #9, deepseek MEDIUM #8 | LOW — edge case                                                | unify timeouts script-configurable       |

### Divergenze (1/4 only)

| #   | Finding                                          | Source                          | Verdict v2                                     |
| --- | ------------------------------------------------ | ------------------------------- | ---------------------------------------------- |
| D1  | `_IS_AGY` evaluated module-load only             | deepseek LOW #10, agy MEDIUM #8 | ACK — Low impact per cron short-lived. No fix. |
| D2  | `--print-timeout` flag rename risk               | deepseek LOW #11                | Pin agy version in CI, add smoke test          |
| D3  | E2BIG su legacy branch arg pass                  | agy HIGH #5                     | Fix: legacy branch usa stdin anche lui         |
| D4  | OOM da `capture_output=True` per stream infinito | agy LOW #10                     | Defer — non visto in prod, monitorare          |

### Inventory gaps (empirici, scoperti da codex via filesystem scan)

| #   | File                                                                      | Pattern                                                                                | Aggiunta v2 inventory                                 |
| --- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| G1  | `scripts/ai-dispatch.sh:45,49-51,315`                                     | `GEMINI_BIN="command gemini"` + 3 modelli (3.1-pro-preview/2.5-pro/2.5-flash) cascade  | NEW Tier 1 file #9                                    |
| G2  | `apps/backend-rag/backend/agents/services/multi_ai_adapter.py:84,103,462` | `GeminiAdapter` subprocess + `gemini --version` check                                  | NEW Tier 1 file #10                                   |
| G3  | `apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py:738,753`            | **HTTP API call diretto** `generativelanguage.googleapis.com` con `GOOGLE_API_KEY` env | ⚠️ FUORI SCOPE: viola SYMBIOSIS Law 1 → debt separato |
| G4  | `~/scripts/claude-cascade.sh:104+`                                        | **GIÀ agy-aware** — `scripts/claude-cascade.sh` (repo) NON esiste                      | T4 Wave 1 RIMOSSO                                     |

## Revised inventory: 51 → 53 file (G3 separato)

- Tier 1 hot-path: **8 → 10** (+ai-dispatch.sh, +multi_ai_adapter.py)
- Tier 2 cold-path: **17 → 16** (-claude-cascade.sh, già migrato)
- Tier 3 installer: 11 (unchanged)
- Tier 4 docs: **15 → 16** (+chains.py debt note)

## Updated canonical pattern (post-panel)

```python
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

# Discover binaries via PATH first (portable), fallback to known paths
def _resolve_binary(name: str, fallback_paths: list[str]) -> str | None:
    """Resolve binary via shutil.which → fallback paths → None."""
    found = shutil.which(name)
    if found and os.access(found, os.X_OK):
        return found
    for p in fallback_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None

_AGY_BIN = _resolve_binary("agy", ["/Users/nuzantara/.local/bin/agy"])
_LEGACY_GEMINI_BIN = _resolve_binary("gemini", ["/opt/homebrew/bin/gemini"])

# Explicit env override (for CI/test A/B)
_OVERRIDE = os.environ.get("GEMINI_BIN")
GEMINI_BIN = _OVERRIDE or _AGY_BIN or _LEGACY_GEMINI_BIN
if not GEMINI_BIN:
    raise RuntimeError("No gemini-compatible CLI found (agy/gemini)")

_IS_AGY = Path(GEMINI_BIN).name == "agy"

# If script requires explicit model NOT in settings.json default, force legacy
_REQUIRED_MODEL = os.environ.get("GEMINI_MODEL")
if _REQUIRED_MODEL and _IS_AGY:
    # agy reads settings.json — if script demands specific model via env, must use legacy
    if _LEGACY_GEMINI_BIN:
        GEMINI_BIN = _LEGACY_GEMINI_BIN
        _IS_AGY = False
    else:
        raise RuntimeError(
            f"GEMINI_MODEL={_REQUIRED_MODEL} requires legacy gemini (not installed)"
        )


def call_llm(prompt: str, timeout: int = 360, model: str | None = None) -> str:
    """Invoke configured LLM CLI. Raises on failure (no silent corruption)."""
    cmd: list[str] = [GEMINI_BIN]
    kwargs: dict = {
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "check": True,  # ← raise on non-zero exit (panel C7)
    }
    if _IS_AGY:
        # agy: stdin + explicit print-timeout
        cmd += ["-p", "--print-timeout", f"{timeout}s"]
        kwargs["input"] = prompt
    else:
        # legacy gemini: model flag + stdin (avoid E2BIG, panel D3)
        if model:
            cmd += ["-m", model]
        cmd += ["-p", "-"]
        kwargs["input"] = prompt

    try:
        result = subprocess.run(cmd, **kwargs)
        return result.stdout.strip()
    except subprocess.TimeoutExpired as exc:
        # graceful degradation, no zombie process (panel C7)
        raise RuntimeError(f"LLM call timeout {timeout}s: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"LLM call failed exit={exc.returncode}: {exc.stderr[:500]}"
        ) from exc
```

Improvements vs v1:

1. `shutil.which` + `os.access(_, os.X_OK)` (panel C1)
2. Explicit `GEMINI_BIN` env override only as escape hatch (NB-1: test mocking is `@patch`, not env)
3. Auto-fallback to legacy gemini when script demands specific model (panel C4 — silent model contamination)
4. `check=True` raises on non-zero exit (panel C7)
5. `TimeoutExpired` wrapped + re-raised cleanly (panel C7)
6. Legacy branch uses stdin too (panel D3 — E2BIG fix)
7. Timeout passed to `--print-timeout` (no mismatch, panel C9)

## Revised waves

### Wave 0 — PRE-FLIGHT (NEW, ship before Wave 1)

T0.1. **Integration test `agy` against current settings.json** (panel C3)
T0.2. **Audit Wave 1 files for `-m`, `-o`, `-y`, `--approval-mode` flags** (panel C4) — scriptato via `grep -rn "\\-[mony]\\b\\|--approval-mode"` su Tier 1 file
T0.3. **Add oauth_creds.json file lock** OR document "single agy/gemini process at a time" cron guarantee (panel C2)
T0.4. **Pin agy v1.0.0 in CI** + `agy --print-timeout 1s` smoke test (panel D2)

Acceptance Wave 0:

- 3 test files committed under `apps/backend-rag/backend/tests/llm/test_agy_compat.py`
- Audit JSON report `research/operations/2026-05-22/wave1-flag-audit.json` (per-file flag usage)
- 1 grep run on prod shows ZERO concurrent agy invocations during cron windows

### Wave 1 — Hot path produzione (10 file, era 8)

Aggiunte da panel codex:

- T9. `scripts/ai-dispatch.sh:45,315` — federation runner cascade (CRITICAL inventory miss)
- T10. `apps/backend-rag/backend/agents/services/multi_ai_adapter.py:84,103,462` — GeminiAdapter subprocess

Rimosso:

- ~~T4. `scripts/claude-cascade.sh`~~ — non esiste in repo, `~/scripts/claude-cascade.sh` già agy-aware (panel G4)

Modifiche:

- T5 (`_entailment_check.py`) + T7 (`naga_*.py`): se `GEMINI_MODEL` env set → forza legacy gemini (panel C4, "false safety" finding codex)
- T8 LaunchAgent plist: aggiungere `<key>EnvironmentVariables</key>` con `GEMINI_BIN` esplicito (panel C5)

### Wave 2 — Cold path (16 file, era 17)

Pattern uniforme `_resolve_binary` + `@patch` test coverage. Eccezione Strategia C estesa (panel C8):

- T17/T18 (extract_worker.sh, batch_extract_company_capital.py) — `--approval-mode yolo` resta legacy
- T21/T22 (zantara-gateway) — SSE resta legacy

### Wave 3 — BLOCKED

Cannot ship finché Antonello non fornisce:

1. **URL ufficiale Antigravity** per distribuzione binary (panel C6)
2. **SHA256 checksum** per ogni arch (darwin-arm64, darwin-x86_64, linux-arm64, linux-x86_64) — supply chain
3. **Signature verification** se disponibile
4. **Atomic install pattern**: `curl … -o agy.tmp && sha256sum -c expected.sha256 && mv agy.tmp ~/.local/bin/agy`

Aggiornamento da Codex finding #2: gli installer Wave 3 devono installare ENTRAMBI `agy` E `gemini` legacy (non solo agy) perché:

- zantara-gateway SSE richiede gemini
- 2.5-flash/2.5-pro scripts richiedono gemini
- ai-dispatch.sh cascade GEMINI_MODEL_FAST richiede gemini

### Wave 4 — Policy docs (16 file, era 15)

Aggiunto:

- **G3 debt note**: `apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py:738,753` viola SYMBIOSIS Law 1 (HTTP API call diretta `generativelanguage.googleapis.com` con `GOOGLE_API_KEY`). NON migrato in questo spec (scope diverso). Riferimento dedicato in `SYMBIOSIS.md` cicatrix da aggiungere.

## Risks aggiornati post-panel

| Risk                           | Severity          | Mitigation v2                                       |
| ------------------------------ | ----------------- | --------------------------------------------------- |
| Hardcoded path break Fly Linux | P0 → mitigated    | `shutil.which` + `os.access` (panel C1)             |
| oauth_creds race corruption    | P0 → mitigated    | Wave 0 T0.3 file lock OR single-writer cron         |
| settings.json schema incompat  | P1 → mitigated    | Wave 0 T0.1 integration test                        |
| Silent model contamination     | P1 → mitigated    | Auto-fallback to legacy when `GEMINI_MODEL` env set |
| Wave 3 supply chain            | P0 → BLOCKED      | Antonello sign-off required (URL + SHA256)          |
| `chains.py` HTTP API debt      | P2 → out of scope | Documentato come debt separato                      |

## Verification post-Wave (cross-wave)

1. `grep -rn "gemini -[mp]\b\|/opt/homebrew/bin/gemini" scripts apps --include='*.py' --include='*.sh'` — zero match in file migrati (escluso Strategia C carve-out files documentati)
2. `pytest apps/backend-rag/backend/tests/llm/test_agy_compat.py` — 0 fail
3. LaunchAgent `com.balizero.crm-guardian-cli-worker.plist` health post 4h
4. `scripts/ai-dispatch.sh help` mostra agy nel cascade chain
5. `apps/backend-rag/backend/agents/services/multi_ai_adapter.py` smoke test importable + `GeminiAdapter.available()` returns True

## Open questions per Antonello

1. **URL ufficiale agy binary** — dove scaricare per Wave 3 installer? Antigravity ha distribution channel pubblico o richiede auth Antigravity?
2. **`chains.py` HTTP API call** — è intenzionale (escape hatch valido per cost optimization $0.0001/article) o viola SYMBIOSIS Law 1 da rimuovere?
3. **Strategy C estesa**: confermi che installer Wave 3 devono mantenere ENTRAMBI agy + gemini?
4. **oauth_creds race**: file lock o single-writer cron constraint? Lock più sicuro, single-writer più semplice (current cron pattern).
5. **Wave 0 pre-flight test budget**: shippiamo Wave 0 come PR a sé (panel C3/C4 mandatory) o folded in Wave 1?

## References

- Inventario v1: `2026-05-22/gemini-to-agy-migration-inventory.md` (53 file post-panel)
- Spec v1: `2026-05-22/gemini-to-agy-migration-spec-v1.md` (superseded by this v2)
- Panel outputs:
  - agy: `/tmp/panel-agy.out` (4850 byte, 10 finding)
  - codex: `/tmp/panel-codex.out` (6963 byte, 11 finding)
  - deepseek: `/tmp/panel-deepseek.out` (9541 byte, 12 finding)
  - NB-1: conversation_id `20cd6007-21e6-42d3-8271-ec8edabf2e5c` (5 ground-truth verdict)
- Cicatrix references (NB-1):
  - `memory/runbook_nlm_auth_stability_fix.md` — auth-token rotation conflict scar
  - `memory/feedback_claude_cli_linux_hang.md` — subprocess CLI hang Fly container
- Pattern reference: `scripts/kbli_enrich_triage.py:11-79` (v1 — superseded by Wave 0 T0.x updated pattern)
