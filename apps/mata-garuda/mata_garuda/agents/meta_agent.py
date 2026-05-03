"""
Mata Garuda — Meta-Agent.

L'agente che crea, modifica, esegue e cancella altri agenti.
Legge dummy_agent.py come template letterale (pattern AutoAgent).

Riferimento: docs/mata-garuda/40d-AUTOAGENT-PATTERNS.md Pattern 2
"""
from __future__ import annotations

from pathlib import Path

from mata_garuda.registry import register_agent
from mata_garuda.runtime.case_status import case_not_resolved, case_resolved
from mata_garuda.tools.meta_tools import (
    create_agent,
    delete_agent,
    execute_command,
    list_agents,
    run_agent,
)
from mata_garuda.types import Agent

GENOME_FILE = str(Path(__file__).parent / "meta_agent_GENOME.md")
DUMMY_AGENT_FILE = Path(__file__).parent / "dummy_agent.py"


def _read_template() -> str:
    """Read dummy_agent.py as literal template for the LLM."""
    try:
        return DUMMY_AGENT_FILE.read_text()
    except FileNotFoundError:
        return "(template file not found)"


@register_agent(name="Meta Agent", func_name="get_meta_agent")
def get_meta_agent(model: str = "claude") -> Agent:
    """Meta-agent that creates, edits, runs, and deletes Mata Garuda agents."""

    def instructions(context_variables: dict) -> str:
        agents_list = list_agents()
        template = _read_template()

        return f"""You are the Meta Agent for Mata Garuda intelligence hub.
Your responsibility is to create, run, and delete agents in the Mata Garuda registry.

{agents_list}

To create a new agent, use the create_agent tool. Follow this template as reference:
```python
{template}
```

CRITICAL RULES (Mata Garuda):
1. New agents MUST be registered with @register_agent decorator
2. New agents MUST use CLI runtime (subprocess to claude/gemini/codex), NOT API HTTP
3. After creating, ALWAYS run the agent via run_agent to verify it works
4. If validation fails, iterate: fix the agent, retry
5. NEVER create agents that touch frontend/clients/team channels (OSINT blindato)
6. Agent instructions should be clear, specific, and include constraints from GENOME.md
7. Always terminate with case_resolved (success) or case_not_resolved (failure)

WORKFLOW for creating an agent:
1. Call list_agents to see what exists
2. Call create_agent with name, description, instructions, and tools
3. Call run_agent to verify it works
4. Report case_resolved with the result

WORKFLOW for deleting an agent:
1. Call list_agents to confirm it exists
2. Call delete_agent with the agent name
3. Call list_agents to verify deletion
4. Report case_resolved
"""

    return Agent(
        name="Meta Agent",
        model=model,
        instructions=instructions,
        functions=[
            list_agents, create_agent, delete_agent, run_agent,
            execute_command, case_resolved, case_not_resolved,
        ],
        tool_choice=None,
        parallel_tool_calls=False,
        genome_path=GENOME_FILE,
        layer="meta",
    )
