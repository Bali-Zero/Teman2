---
date: 2026-05-27
domain: wr2
phase: A.3 (architecture spec pre-FASE B)
sources:
  - empirical CLI tests on Pro (M4 Pro, Claude Code v2.1.150)
  - claude --print --help output
  - ~/.claude/agents/wr2-*.md (8 agent files inspected)
verdict: CLI_DISPATCH_OK
machine: Nuzantara (Pro)
cli_version: 2.1.150
oauth_slot: kaiser198719871987@gmail.com (MAX)
---

## Verdict

**CLI_DISPATCH_OK** — `claude --print --agent <name>` carica `~/.claude/agents/<name>.md` direttamente. Spec FASE B può chainare subagent senza Python orchestrator complesso (è sufficiente subprocess wrapper).

## Test 1 — basic `--print` smoke (JSON)

**Comando**:

```bash
cd /tmp && echo "Reply with exact text: HEALTH_OK_TEST" | claude --print --model claude-haiku-4-5 --output-format json
```

**Output (excerpt)**:

```json
{"type":"result","subtype":"success","is_error":false,"duration_ms":2693,"duration_api_ms":2568,"ttft_ms":2617,"num_turns":1,"result":"HEALTH_OK_TEST","stop_reason":"end_turn","session_id":"a526bb5b-...","total_cost_usd":0.11938325,"usage":{"input_tokens":2,"cache_creation_input_tokens":95469,"cache_read_input_tokens":0,"output_tokens":9,...}}
```

**Exit**: 0 · **Latency wall-clock**: 12.1s · **Cost**: $0.119 (95.5k cache_creation = system prompt + tools)

**Response schema top-level keys**: `type`, `subtype`, `is_error`, `api_error_status`, `duration_ms`, `duration_api_ms`, `ttft_ms`, `num_turns`, `result` (string content), `stop_reason`, `session_id`, `total_cost_usd`, `usage` (input/output/cache breakdown), `modelUsage`, `permission_denials`, `terminal_reason`, `fast_mode_state`, `uuid`.

**Conclusion**: Working. JSON schema rich. `result` is the assistant text; `usage` ha cache hit/miss + token counts; `total_cost_usd` exposes cost del singolo turn.

**GOTCHA primo run**: invocato da `/Users/nuzantara/Desktop/nuzantara/.worktrees/...` ha ritornato `"Prompt is too long"` (api_error 400) perché CLAUDE.md auto-discovery + memory load (~200k token combined) supera context. **Fix**: invoca da `/tmp` (no CLAUDE.md ancestor) o usa `--bare` (ma `--bare` disabilita OAuth keychain → "Not logged in"). Spec FASE B: subprocess.run con `cwd="/tmp"` o working dir senza CLAUDE.md.

## Test 2 — `text` vs `json` output

**Text format**:

```bash
cd /tmp && echo "Reply with exact text: OK_TEXT" | claude --print --model claude-haiku-4-5 --output-format text
# Output: OK_TEXT
# Latency: 11.2s · Exit: 0
```

**JSON format**: come Test 1.

**Conclusion**: `text` = solo l'assistant response stripped (più compatto per pipeline shell). `json` = wrapper schema completo (necessario per orchestrator che vuole `total_cost_usd`, `usage`, `is_error`, `session_id` per chain tracking). **Per FASE B usare `--output-format json` + Python `json.loads()` + assert `is_error=false` + estrai `result`.**

## Test 3 — agent dispatch via CLI (CRITICAL)

**Test 3a — `--agent <name>` con wr2-brief-interpreter**:

```bash
cd /tmp && claude --print --agent wr2-brief-interpreter "test prompt"
```

**Output** (live, excerpt): `I'm the **WR2 Brief Interpreter** — online and operational. ... Agent system prompt ✅ Loaded ... Bilingual lexicon discipline (R3a) ✅ Ready ... Pass a topic (free text) and I'll return a structured brief JSON...`

**Exit**: 0 · **VERDICT**: Agent system prompt da `~/.claude/agents/wr2-brief-interpreter.md` **caricato verbatim**. Tutti i WR2 subagent disponibili via CLI senza modifiche.

**Test 3b — `--agent wr2-storyboarder` + JSON**:

```bash
cd /tmp && claude --print --agent wr2-storyboarder --model claude-haiku-4-5 --output-format json 'Return JSON {"status":"AGENT_LOADED"}'
```

Output (excerpt): `"status": "AGENT_LOADED", "context": {"role": "WR2 Storyboarder", "primary_task": "Convert wr2-brief-interpreter JSON → slide-by-slide narrative specification (slides.json)", "guardrails_active": [...]}`

**Latency**: 19.8s · **Conclusion**: Agent JSON output parseable. Storyboarder self-identified correttamente + ha citato skill applicable.

**Test 3c — agent inesistente (error path)**:

```bash
cd /tmp && claude --print --agent nonexistent-agent-foo "test"
# Output: "Test ricevuto. Ambiente carico: Opus 4.7, machine Pro..."
# Exit: 0 — SILENT FALLBACK to default agent
```

**GOTCHA CRITICO**: `--agent` con nome inesistente NON errora — fallback silenzioso al default Opus 4.7. **Python orchestrator DEVE validate agent name esiste in `~/.claude/agents/<name>.md` PRIMA di subprocess** o l'intero chain produrrà output sbagliato senza accorgersene.

## Test 4 — system-prompt workaround

**Test 4a — `--system-prompt <string>`**:

```bash
cd /tmp && echo "test user prompt" | claude --print --system-prompt "You are a test bot. Reply with TEST_OK only." --model claude-haiku-4-5 --output-format text
# Output: TEST_OK · Latency: 11.5s · Exit: 0
```

**Test 4b — `--system-prompt-file <path>`** (verified exists via `--help`):

```bash
cd /tmp && echo "say hi" | claude --print --system-prompt-file /Users/nuzantara/.claude/agents/wr2-brief-interpreter.md --model claude-haiku-4-5 --output-format text
# Output: "Ciao, Antonello! 👋 I'm **wr2-brief-interpreter** ..."
# Exit: 0
```

**Test 4c — `--agents '<JSON>' --agent <name>`** (inline agent def):

```bash
cd /tmp && claude --print --agents '{"testbot":{"description":"test","prompt":"You are a test bot. Reply ONLY with INLINE_AGENT_OK."}}' --agent testbot --model claude-haiku-4-5 --output-format text "hi"
# Output: INLINE_AGENT_OK · Exit: 0
```

**Conclusion**: 4 workaround layered redundant disponibili:

1. `--agent <name>` (canonical, carica `~/.claude/agents/<name>.md` con frontmatter rispettato)
2. `--system-prompt-file <path>` (loadare qualsiasi file md come system prompt — utile per agent ad-hoc)
3. `--system-prompt <inline>` (per system prompt corti)
4. `--agents '<json>' --agent <name>` (definire agent inline in JSON — utile per orchestrator che genera prompt dinamici)

## Test 5 — `--max-budget-usd` enforcement

```bash
cd /tmp && echo "Reply with TEST_OK" | claude --print --max-budget-usd 0.001 --model claude-haiku-4-5 --output-format json
```

**Output**:

```json
{"type":"result","subtype":"error_max_budget_usd","is_error":true,"errors":["Reached maximum budget ($0.001)"],"total_cost_usd":0.0291,...}
```

**Conclusion**: HARD STOP appena costo supera budget (qui $0.029 vs cap $0.001). `is_error=true` + `subtype=error_max_budget_usd` + `errors[0]` machine-parseable. **Per FASE B spec budget per chain step → orchestrator può fallire fast su over-budget**. Cost overshooting di ~30x perché la stima è post-fact (dopo il primo invio LLM, non pre-flight).

## Test 6 — auth + version

```bash
claude --version  # → 2.1.150 (Claude Code)
claude auth status
# → {"loggedIn":true,"authMethod":"claude.ai","apiProvider":"firstParty","email":"kaiser198719871987@gmail.com","orgId":"522e759f-...","orgName":"...","subscriptionType":"max"}
```

**Conclusion**: MAX OAuth slot attivo. Quota consumption va su rolling 5h window MAX-plan (rate-limit cascade per cron — vedi pitfall #2). CLI version 2.1.150 baseline per spec FASE B.

## Available CLI flags rilevanti per FASE B

| Flag                                       | Scope                             | Use case FASE B                                                                           |
| ------------------------------------------ | --------------------------------- | ----------------------------------------------------------------------------------------- |
| `--print` (alias `-p`)                     | non-interactive                   | Mandatory per subprocess                                                                  |
| `--model <id>`                             | model select                      | `claude-haiku-4-5` cheap step, `claude-sonnet-4-6` storyboarder, `claude-opus-4-7` critic |
| `--agent <name>`                           | load `~/.claude/agents/<name>.md` | **PRIMARY** wiring per WR2 subagent chain                                                 |
| `--agents '<json>'`                        | inline agent def                  | Per orchestrator che genera prompt dinamici                                               |
| `--system-prompt <str>`                    | inline system prompt              | Override / quick test                                                                     |
| `--system-prompt-file <path>`              | load file as system               | Backup se `--agent` lookup fail                                                           |
| `--append-system-prompt[-file]`            | extend default                    | Inject contesto extra senza sovrascrivere agent                                           |
| `--output-format json\|text\|stream-json`  | output schema                     | `json` per orchestrator chain, `stream-json` per live SSE UI                              |
| `--max-budget-usd <amt>`                   | hard budget cap                   | Per-step budget guardrail                                                                 |
| `--json-schema '<schema>'`                 | structured output                 | Force JSON validation client-side — verified working, retorna `structured_output: {...}`  |
| `--max-turns <n>`                          | turn cap                          | Force single-turn per step                                                                |
| `--fallback-model <id>`                    | overload fallback                 | Solo con `--print`                                                                        |
| `--input-format text\|stream-json`         | input mode                        | `stream-json` per realtime                                                                |
| `--mcp-config <files>`                     | MCP servers                       | NotebookLM lookup per brief-interpreter                                                   |
| `--allowedTools "Bash(...)"`               | tool whitelist                    | Restringi per agent senza tool calls (critic)                                             |
| `--disallowedTools`                        | tool denylist                     | Mirror del denylist agent file                                                            |
| `--bare`                                   | minimal mode                      | NO — disabilita OAuth keychain. Use solo se passi env-explicit auth                       |
| `--add-dir <dirs>`                         | extra CLAUDE.md                   | NO per orchestrator — vogliamo cwd=`/tmp` per evitare context bloat                       |
| `--exclude-dynamic-system-prompt-sections` | cache reuse                       | Migliora cache hit (95k token sys prompt)                                                 |
| `--session-id <uuid>`                      | resume session                    | Per chain con context handoff                                                             |
| `--no-session-persistence`                 | volatile sessions                 | Per step usa-e-getta                                                                      |

## Recommended wiring pattern per spec FASE B

**Pattern canonico — Python orchestrator che chaina WR2 subagent**:

```python
import json
import subprocess
import os
from pathlib import Path

AGENT_DIR = Path.home() / ".claude" / "agents"
TMP_CWD = "/tmp"  # avoid CLAUDE.md context bloat

def call_subagent(
    agent_name: str,
    user_prompt: str,
    model: str = "claude-haiku-4-5",
    max_budget_usd: float = 0.50,
    json_schema: dict | None = None,
    timeout_s: int = 120,
) -> dict:
    """Run a WR2 subagent via `claude --print --agent`. Returns parsed JSON result."""
    # GOTCHA fix #1: validate agent file exists (silent fallback to default if missing)
    agent_file = AGENT_DIR / f"{agent_name}.md"
    if not agent_file.is_file():
        raise FileNotFoundError(
            f"Agent file not found: {agent_file}. "
            f"`--agent` would silently fall back to default. Aborting."
        )

    cmd = [
        "claude", "--print",
        "--agent", agent_name,
        "--model", model,
        "--output-format", "json",
        "--max-budget-usd", str(max_budget_usd),
        "--no-session-persistence",
        "--exclude-dynamic-system-prompt-sections",
    ]
    if json_schema:
        cmd += ["--json-schema", json.dumps(json_schema)]
    cmd.append(user_prompt)

    # GOTCHA fix #2: cwd=/tmp prevents CLAUDE.md auto-discovery overflowing context
    # GOTCHA fix #3: strip ANTHROPIC_API_KEY from env (defense-in-depth — banned paid endpoint)
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    result = subprocess.run(
        cmd,
        cwd=TMP_CWD,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )

    if result.returncode != 0:
        raise RuntimeError(f"claude CLI exit {result.returncode}: {result.stderr[:500]}")

    payload = json.loads(result.stdout)

    # GOTCHA fix #4: exit 0 anche su is_error=true (max_budget, prompt_too_long, etc.)
    if payload.get("is_error"):
        subtype = payload.get("subtype", "unknown")
        errors = payload.get("errors", [])
        raise RuntimeError(f"claude subagent error ({subtype}): {errors}")

    return {
        "text": payload["result"],
        "structured": payload.get("structured_output"),
        "cost_usd": payload["total_cost_usd"],
        "tokens": payload["usage"],
        "session_id": payload["session_id"],
        "duration_ms": payload["duration_ms"],
    }


# Esempio chain WR2 4-step
def wr2_pipeline(topic: str):
    brief = call_subagent(
        "wr2-brief-interpreter",
        f"topic: {topic}",
        model="claude-sonnet-4-6",
        max_budget_usd=0.30,
    )
    slides = call_subagent(
        "wr2-storyboarder",
        f"Convert this brief to slides.json:\n{brief['text']}",
        model="claude-sonnet-4-6",
        max_budget_usd=0.40,
    )
    images = call_subagent(
        "wr2-image-prompt-author",
        f"Generate image prompts for these slides:\n{slides['text']}",
        model="claude-sonnet-4-6",
        max_budget_usd=0.30,
    )
    critique = call_subagent(
        "wr2-critic",
        f"Score this carousel pre-publish:\nbrief={brief['text']}\nslides={slides['text']}\nimages={images['text']}",
        model="claude-opus-4-7",  # critic needs Opus per nuanced scoring
        max_budget_usd=0.80,
    )
    return {
        "brief": brief,
        "slides": slides,
        "images": images,
        "critique": critique,
        "total_cost_usd": sum(s["cost_usd"] for s in [brief, slides, images, critique]),
    }
```

## Pitfalls / gotchas (3 top, in priority)

1. **`--agent <invalid_name>` silent fallback** (CRITICAL). Se passi nome agent inesistente, CLI NON errora — fallback silenzioso a default Opus 4.7. Pipeline produrrà output non-WR2 senza accorgersene. **Mitigation**: orchestrator valida `Path(agent_file).is_file()` PRIMA del subprocess + raise FileNotFoundError. Cicatrix-style guard.

2. **CLAUDE.md auto-discovery overflowing context** (HIGH). Da `/Users/nuzantara/Desktop/nuzantara/...` → CLAUDE.md (project ~25k token) + global CLAUDE.md (~10k) + MEMORY.md (~20k) + memory loads → `Prompt is too long` 400 error (visto live in pre-test). **Mitigation**: orchestrator subprocess.run con `cwd="/tmp"`. Trade-off: perdi auto-CLAUDE.md (ma WR2 subagent ha già tutto necessario in agent .md frontmatter).

3. **MAX-plan rolling 5h window quota cascade** (MEDIUM). Cron WR2 produce 1-3 carousel/giorno × 4-6 step × ~10-20s/step + cache_creation ~95k token primo call (poi cache_read economico). Empirical primo turn: $0.119; turni successivi cache_read ~$0.02. **Mitigation**: spec wrapper cascade fallback (Claude → Gemini agy → Codex GPT-5.5) come da `~/scripts/regulatory-watcher-run.sh` pattern; grep stdout per `"is_error":true` AND (`out of extra usage|quota|rate.?limit|429|exhausted`) per fall-through.

**Bonus #4** (LOW): `--max-budget-usd` cap fa overshoot ~30x (cap $0.001 → actual $0.029 perché stima post-fact). Set cap con margine di sicurezza ≥10x del costo atteso, NON al limite stretto. **Bonus #5** (LOW): `output-format json` exit 0 anche su `is_error=true` — check `payload["is_error"]` esplicitamente, NON solo `returncode`.

---

**End of empirical capabilities probe** — `wr2-wr2-spec-2026-05-27/research/wr2/2026-05-27-claude-print-capabilities.md`
