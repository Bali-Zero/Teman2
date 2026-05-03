# Mata Garuda — AutoAgent Patterns Extracted

> Data: 2026-04-09 | Sessione S04 (cont.)
> Riferimento: [40c-AUTOAGENT-EVAL.md](40c-AUTOAGENT-EVAL.md)
> Scopo: estrarre 4 pattern pregevoli da HKUDS/AutoAgent e adattarli ai vincoli Mata Garuda (CLI-only, OSINT blindato, no Docker, no chromadb)

---

## Pattern 1 — Registry recursive con decorator

### Originale (HKUDS/AutoAgent)

`autoagent/registry.py` + `autoagent/agents/__init__.py`

**Idea:** singleton globale `Registry` con dizionari per `tools`, `agents`, `workflows`. Decoratori `@register_agent` / `@register_tool` registrano funzioni nel singleton. All'import del package, `os.walk` ricorsivo importa tutti i `.py` sotto `agents/` triggering i decoratori.

**Risultato:** drop a file → l'agente è disponibile globalmente. Zero config.

### Codice estratto (semplificato)

```python
# registry.py — versione minimale
from typing import Callable, Dict, Literal, Optional
from dataclasses import dataclass, asdict
import inspect, os, importlib

@dataclass
class FunctionInfo:
    name: str
    func_name: str
    func: Callable
    args: list
    docstring: Optional[str]
    file_path: Optional[str]

class Registry:
    _instance = None
    _registry: Dict[str, Dict[str, Callable]] = {
        "tools": {}, "agents": {}, "workflows": {}
    }
    _registry_info: Dict[str, Dict[str, FunctionInfo]] = {
        "tools": {}, "agents": {}, "workflows": {}
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, type: Literal["tool", "agent", "workflow"],
                 name: str = None, func_name: str = None):
        def decorator(func: Callable):
            nonlocal name
            if name is None:
                name = func.__name__
            try:
                file_path = os.path.abspath(inspect.getfile(func))
            except Exception:
                file_path = "Unknown"
            sig = inspect.signature(func)
            info = FunctionInfo(
                name=name,
                func_name=func_name or name,
                func=func,
                args=list(sig.parameters.keys()),
                docstring=inspect.getdoc(func),
                file_path=file_path,
            )
            self._registry[f"{type}s"][func_name or name] = func
            self._registry_info[f"{type}s"][name] = info
            return func
        return decorator

    @property
    def agents(self): return self._registry["agents"]
    @property
    def tools(self): return self._registry["tools"]

registry = Registry()

def register_agent(name=None, func_name=None):
    return registry.register("agent", name=name, func_name=func_name)

def register_tool(name=None, func_name=None):
    return registry.register("tool", name=name, func_name=func_name)
```

```python
# agents/__init__.py — auto-walk
import os, importlib
from mata_garuda.registry import registry

def _import_all_recursively(base_dir: str, base_package: str):
    for root, dirs, files in os.walk(base_dir):
        rel = os.path.relpath(root, base_dir)
        for f in files:
            if f.endswith('.py') and not f.startswith('__'):
                if rel == '.':
                    mod = f"{base_package}.{f[:-3]}"
                else:
                    pkg = rel.replace(os.path.sep, '.')
                    mod = f"{base_package}.{pkg}.{f[:-3]}"
                try:
                    importlib.import_module(mod)
                except Exception as e:
                    print(f"[registry] failed to import {mod}: {e}")

_import_all_recursively(os.path.dirname(__file__), 'mata_garuda.agents')
globals().update(registry.agents)
__all__ = list(registry.agents.keys())
```

### Adattamento Mata Garuda

- Rimuove dipendenza `tiktoken` (era usata solo per `truncate_output`, opzionale)
- Rimuove distinzione `plugin_*` (sovra-design per noi)
- Mantiene singleton + recursive walk (essenza del pattern)
- ~70 LOC vs 200 originali

---

## Pattern 2 — Meta-agent (Agent Editor)

### Originale (HKUDS/AutoAgent)

`autoagent/agents/meta_agent/agent_editor.py` (40 righe!) + `tools/meta/edit_agents.py` (5 tool: list/create/delete/run/orchestrator).

**Idea:** un agente è semplicemente un loop con 5 tool che operano sul registry stesso:
1. `list_agents` — query del registry
2. `create_agent` — scrive un nuovo `.py` sotto `agents/`, lo esegue per validare
3. `delete_agent` — `rm` del file
4. `run_agent` — invoca un agente per nome con query
5. `execute_command` — fallback shell

L'instructions del meta-agent contiene il **template letterale** (`dummy_agent.py` letto via `read_file()`) — il modello impara per esempio.

### Codice estratto (semplificato + adattato CLI)

```python
# mata_garuda/agents/meta_agent.py
from mata_garuda.registry import register_agent
from mata_garuda.types import Agent
from mata_garuda.tools.meta_tools import (
    list_agents, create_agent, delete_agent, run_agent, execute_command
)

def _read(path: str) -> str:
    with open(path) as f:
        return f.read()

@register_agent(name="Meta Agent", func_name="get_meta_agent")
def get_meta_agent(model: str) -> Agent:
    """Meta-agent che crea/modifica/esegue altri agenti Mata Garuda."""
    def instructions(ctx):
        return f"""You are the Meta Agent for Mata Garuda intelligence hub.
Your responsibility is to create, edit, run, and delete agents in the Mata Garuda agent registry.

Existing agents:
{list_agents(ctx)}

To create a new agent, follow this template (from agents/dummy_agent.py):
```python
{_read('mata_garuda/agents/dummy_agent.py')}
```

CRITICAL RULES (Mata Garuda specific):
1. New agents MUST be registered with @register_agent decorator
2. New agents MUST use CLI runtime (subprocess to claude/gemini/codex), NOT API
3. After creating, you MUST run the agent via run_agent() to verify it works
4. If validation fails (case_not_resolved), iterate: read GENOME.md, propose mutation
5. NEVER create agents that touch frontend/clients/team channels (OSINT blindato)
"""
    return Agent(
        name="Meta Agent",
        model=model,
        instructions=instructions,
        functions=[list_agents, create_agent, delete_agent, run_agent, execute_command],
        tool_choice="required",
        parallel_tool_calls=False,
    )
```

### Differenze chiave vs originale

| Aspetto | HKUDS/AutoAgent | Mata Garuda |
|---|---|---|
| Esegue agenti via | `mc agent --model=... --agent_func=...` (subprocess) | Stessa idea, ma il modello è CLI-wrapped |
| Validazione | Esegue `python autoagent/agents/{name}.py` per check sintassi | Stesso pattern |
| Storage | File system sotto `autoagent/agents/` | File system sotto `mata_garuda/agents/` |
| Registry | Singleton in-process | Stesso |
| Tool list | 5 + execute_command | Stessi 5, identici |
| Vincolo OSINT | Nessuno | Aggiunto in instructions: NEVER touch frontend |

### Tool `create_agent` (codice essenziale)

```python
# mata_garuda/tools/meta_tools.py — versione semplificata
from string import Formatter
from mata_garuda.registry import register_tool

def _has_format_keys(s: str) -> bool:
    return any(t[1] is not None for t in Formatter().parse(s))

def _extract_format_keys(s: str) -> list:
    out = []
    for t in Formatter().parse(s):
        if t[1] is not None and t[1] not in out:
            out.append(t[1])
    return out

@register_tool("create_agent")
def create_agent(agent_name: str, agent_description: str,
                 agent_tools: list, agent_instructions: str,
                 context_variables: dict):
    """Creates a new Mata Garuda agent file from natural language spec."""
    agent_func = f"get_{agent_name.lower().replace(' ', '_')}"
    tools_imports = "\n".join(f"from mata_garuda.tools import {t}" for t in agent_tools)

    if _has_format_keys(agent_instructions):
        keys = _extract_format_keys(agent_instructions)
        kvals = ", ".join(f"{k}=context_variables.get('{k}', '')" for k in keys)
        instr = f"""def instructions(context_variables):
    return {repr(agent_instructions)}.format({kvals})"""
    else:
        instr = f"instructions = {repr(agent_instructions)}"

    code = f'''\
from mata_garuda.types import Agent
from mata_garuda.registry import register_agent
{tools_imports}

@register_agent(name="{agent_name}", func_name="{agent_func}")
def {agent_func}(model: str):
    """{agent_description}"""
    {instr}
    return Agent(
        name="{agent_name}",
        model=model,
        instructions=instructions,
        functions=[{', '.join(agent_tools)}],
    )
'''
    target = f"mata_garuda/agents/{agent_name.lower().replace(' ', '_')}.py"
    with open(target, 'w') as f:
        f.write(code)

    # validate by importing
    import subprocess
    result = subprocess.run(
        ['python', '-c', f'import mata_garuda.agents.{agent_name.lower().replace(" ", "_")}'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return f"[ERROR] Validation failed: {result.stderr}"
    return f"[SUCCESS] Created {target}"
```

---

## Pattern 3 — case_resolved / case_not_resolved (fitness signal)

### Originale (HKUDS/AutoAgent)

`autoagent/main.py` definisce due tool che gli agenti DEVONO chiamare per terminare:

```python
def case_resolved(result: str):
    """Use this tool when the case IS resolved.
    Encapsulate final answer in <solution></solution>."""
    return f"Case resolved. The result is: {result}"

def case_not_resolved(failure_reason: str, take_away_message: str):
    """Use this when ALL agents tried their best and failed."""
    return f"Case not resolved. Reason: {failure_reason}. Insight: {take_away_message}"
```

E il loop in `run_in_client`:
```python
for i in range(MAX_RETRY):  # MAX_RETRY = 3
    response = await client.run_async(agent, messages, ...)
    if 'Case resolved' in response.messages[-1]['content']:
        break
    elif 'Case not resolved' in response.messages[-1]['content']:
        # ... retry with hint, escalate to meta_agent if i >= 2
```

### Perché è importante per Mata Garuda Lamarckian

Questo è **letteralmente il fitness signal** per il pattern Lamarckian descritto in [40b-AGENT-TAXONOMY.md](40b-AGENT-TAXONOMY.md):

```
agent runs → case_resolved → success → reinforce GENOME.md
                                          (no mutation)
agent runs → case_not_resolved → failure → log to feedback.md
                                            → trigger meta_agent
                                            → propose GENOME.md mutation
                                            → human review → keep/revert
```

**AutoAgent ha il scaffold gratis. Bisogna solo wireare l'output verso GENOME.md.**

### Codice estratto (versione Mata Garuda con GENOME hook)

```python
# mata_garuda/runtime/loop.py
import asyncio
from datetime import datetime
from pathlib import Path

GENOME_PATH = Path("mata_garuda/agents/{agent_name}/GENOME.md")
FEEDBACK_PATH = Path("mata_garuda/agents/{agent_name}/feedback.md")

def case_resolved(result: str):
    """Use this tool when the case IS resolved.
    Encapsulate final answer in <solution></solution>."""
    return f"Case resolved. The result is: {result}"

def case_not_resolved(failure_reason: str, take_away_message: str):
    """Use this when ALL agents tried their best and failed.
    The failure_reason and take_away will be appended to feedback.md
    and may trigger a GENOME.md mutation review."""
    return (f"Case not resolved. Reason: {failure_reason}. "
            f"Insight: {take_away_message}")

async def run_with_lamarckian_feedback(
    agent, messages: list, ctx: dict,
    runtime, max_retry: int = 3
):
    """Run agent loop with case_resolved/not_resolved + GENOME hook."""
    agent_name = agent.name.lower().replace(' ', '_')
    feedback_file = FEEDBACK_PATH.with_name('feedback.md').with_suffix('.md')
    feedback_file.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(max_retry):
        response = await runtime.run(agent, messages, ctx)
        last = response.messages[-1].get('content', '')

        if 'Case resolved' in last:
            # success — reinforce, no mutation
            return response

        if 'Case not resolved' in last:
            # failure — log to feedback.md (Lamarckian)
            ts = datetime.now().isoformat()
            with open(feedback_file, 'a') as f:
                f.write(f"\n\n## {ts} (attempt {attempt+1})\n{last}\n")

            messages.extend(response.messages)
            if attempt >= max_retry - 1:
                # last attempt — escalate to meta_agent for GENOME mutation
                return await _escalate_to_meta_agent(
                    agent, messages, ctx, runtime, feedback_file
                )
            messages.append({
                'role': 'user',
                'content': "Try again. Read your GENOME.md constraints. "
                           "Approach the problem differently."
            })

    return response

async def _escalate_to_meta_agent(agent, messages, ctx, runtime, feedback_file):
    """When agent gives up, meta_agent reads feedback.md and proposes mutation."""
    from mata_garuda.agents.meta_agent import get_meta_agent
    meta = get_meta_agent(model=agent.model)
    messages.append({
        'role': 'user',
        'content': f"""The agent {agent.name} failed after multiple attempts.
Read the failure log at {feedback_file}.
Propose a mutation to {agent.name}/GENOME.md that addresses the root cause.
Then re-run the agent with the mutated genome."""
    })
    return await runtime.run(meta, messages, ctx)
```

### Cosa abbiamo aggiunto vs originale

- ✅ `feedback.md` per ogni agente (Lamarckian: il fallimento si materializza in un file)
- ✅ Escalation al meta-agent invece di semplice retry
- ✅ Il meta-agent ha accesso al feedback log per proporre mutazioni a GENOME.md
- ✅ Pattern allineato con `failure → rule → habit → identity` di agent-taxonomy

---

## Pattern 4 — Browser environment standalone

### Originale (HKUDS/AutoAgent)

`autoagent/environment/browser_env.py` (28KB) — wrapper sopra `browsergym==0.13.0` + `playwright==1.39.0`.

**Cosa fa:** istanza Chromium/Firefox controllata via accessibility tree, observation strutturata (DOM + screenshot + AX tree), action space (click/type/scroll/navigate/upload), gestione di iframe/popup/cookies.

### Verdetto per Mata Garuda

**Riusabile come ispirazione, NON come dependency.**

Motivi:
- `browsergym==0.13.0` è pinned vecchio, conflitti con altri stack del nostro monorepo
- Il nostro `apps/bali-intel-scraper/` già usa Playwright direttamente (più recente)
- Il pattern interessante è l'**observation space** (DOM + AX tree + screenshot) che potremmo adottare nel nostro scraper esistente

### Cosa estrarre come idea (non codice)

1. **Observation triple**: ogni page state = (DOM HTML, accessibility tree, screenshot base64)
2. **Action grammar**: limit action space a un insieme finito di verbi (`click(elem_id)`, `type(elem_id, text)`, `scroll(dir)`, `navigate(url)`)
3. **Element IDs stabili**: assegna ID numerici agli elementi interagibili → il modello LLM li referenzia per nome, non per CSS selector

Questi 3 pattern li possiamo aggiungere al nostro `bali-intel-scraper` esistente, NON serve forkare browser_env.py.

---

## Open question risolta — `local_env.py`

Letto integralmente. **NON è first-class.**

```python
class LocalEnv:
    def __init__(self, docker_config: DockerConfig = None):
        if docker_config is None:
            self.docker_workplace = os.getcwd()  # ← finge di essere docker
            self.local_workplace = self.docker_workplace
        else:
            # se passato docker_config, lavora sotto local_root/workplace_name
        self.conda_sh = self._find_conda_sh()  # ← richiede conda installato

    def run_command(self, command, stream_callback=None):
        assert self.conda_sh is not None, "Conda.sh not found"
        modified_command = (
            f"/bin/bash -c 'source {self.conda_sh} && "
            f"conda activate auto && cd {self.docker_workplace} && {command}'"
        )
        process = subprocess.Popen(modified_command, shell=True, ...)
```

Problemi per Mata Garuda:
- Richiede `conda` installato (non l'abbiamo, usiamo `.venv`/`pyenv`)
- Richiede env conda chiamato `auto` (hard-coded)
- È pensato come mock di Docker, non come runtime alternativo
- Non implementa file copy local↔docker (fa pass-through)

**Conclusione:** anche scegliendo `local_env.py`, AutoAgent assume conda + working directory speciale. Non è una via d'uscita pulita dal vincolo Docker.

→ **Conferma decisione 40c:** reimplementare conviene.

---

## Riepilogo — cosa va dove

| Pattern AutoAgent | File Mata Garuda destinazione | LOC stima |
|---|---|---|
| Registry singleton + recursive walk | `mata_garuda/registry.py` + `agents/__init__.py` | ~100 |
| Meta-agent (`agent_editor.py`) | `mata_garuda/agents/meta_agent.py` | ~50 |
| Tool `create_agent` (template generation) | `mata_garuda/tools/meta_tools.py` | ~80 |
| Tool `list_agents` / `delete_agent` / `run_agent` | `mata_garuda/tools/meta_tools.py` | ~60 |
| `case_resolved` / `case_not_resolved` + Lamarckian loop | `mata_garuda/runtime/loop.py` | ~80 |
| GENOME.md hook + feedback escalation | `mata_garuda/runtime/lamarckian.py` | ~60 |
| Subprocess CLI runtime (claude/gemini/codex) | `mata_garuda/runtime/cli_runtime.py` | ~150 |
| **TOTALE STIMA** | | **~580 LOC** |

vs. AutoAgent: **~50.000 LOC** + dipendenze (chromadb, browsergym, faster_whisper, sentence_transformers, docling, litellm, ...).

**Rapporto: ~85x meno codice, zero dipendenze API, OSINT-compliant, allineato agent-taxonomy.**

---

## Prossimi micro-step

1. **02-ARCHITECTURE.md** — aggiornare il layer "meta-agent" con questi 4 pattern
2. **50-BUILD-ORDER.md** — sequenziare implementazione in 3 sprint:
   - Sprint 1: registry + types + 1 dummy agent (verifica registry funziona)
   - Sprint 2: meta-agent + create/list/run tools (test con Claude CLI)
   - Sprint 3: case_resolved/not_resolved + Lamarckian loop + GENOME.md hook
3. **POC reale**: scrivere `mata_garuda/registry.py` (~70 LOC) come primo file, validare con un dummy agent

---

## Fonti verificate (no hallucination)

- ✅ `autoagent/registry.py` letto integralmente (~200 LOC)
- ✅ `autoagent/agents/dummy_agent.py` letto integralmente
- ✅ `autoagent/agents/meta_agent/agent_editor.py` letto integralmente
- ✅ `autoagent/tools/meta/edit_agents.py` letto integralmente (~500 LOC, contiene anche `create_orchestrator_agent`)
- ✅ `autoagent/types.py` letto integralmente (Agent, Response, Result Pydantic models)
- ✅ `autoagent/main.py` letto integralmente (case_resolved, case_not_resolved, run_in_client loop)
- ✅ `autoagent/environment/local_env.py` letto integralmente — **NON è first-class** (richiede conda + mock di docker)
- ✅ Listato `autoagent/tools/meta/` (5 file: edit_agents, edit_tools, edit_workflow, search_tools, tool_retriever)
- ✅ Codice estratto in questo doc è semplificato/adattato MA fedele al pattern originale
- ⚠️ NON ancora clonato/eseguito localmente — solo lettura via GitHub MCP API

---

**Status:** patterns documentati 2026-04-09. Pronto per implementazione POC.
