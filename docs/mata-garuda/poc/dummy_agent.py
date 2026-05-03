"""
Mata Garuda — Dummy Agent.

Template letterale che il meta-agent legge tramite read_file() per generare
nuovi agenti via natural language. La struttura DEVE essere fedele perché il
modello impara per esempio (pattern AutoAgent).

Pattern estratto da HKUDS/AutoAgent autoagent/agents/dummy_agent.py.
Differenze vs originale:
- Usa @register_agent (non @register_plugin_agent — distinzione rimossa)
- Default model = "claude" (CLI), non "gpt-4o"
- Aggiunto genome_path obbligatorio per Lamarckian
- Aggiunto layer="meta" per i dummy/template

Riferimento doc: docs/mata-garuda/40d-AUTOAGENT-PATTERNS.md
Status: POC reference code.
"""
from __future__ import annotations

from pathlib import Path

# Imports che SARANNO veri quando il package esisterà:
# from mata_garuda.types import Agent
# from mata_garuda.registry import register_agent
# from mata_garuda.tools.basic import echo  # esempio di tool minimale

# Per ora (POC) usiamo stub commentati:
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import Agent  # pragma: no cover


GENOME_FILE = str(Path(__file__).parent / "dummy_agent_GENOME.md")


# @register_agent(name="Dummy Agent", func_name="get_dummy_agent")
def get_dummy_agent(model: str = "claude") -> "Agent":
    """
    Dummy agent template usato dal meta-agent per generare nuovi agenti.

    Args:
        model: CLI runtime — "claude" | "gemini" | "codex" | "deepseek"

    Returns:
        Agent instance pronto da eseguire.

    Note:
        - Le instructions possono essere stringa o funzione che riceve context_variables
        - Le functions sono i tool che l'agente può chiamare
        - genome_path PUNTA al GENOME.md di questo agente (Lamarckian-ready)
    """
    def instructions(context_variables: dict) -> str:
        """
        Build system prompt dinamicamente. Il context_variables traccia
        variabili importanti dell'agente attraverso la conversazione.
        """
        user_name = context_variables.get("user_name", "Zero")
        return f"""You are the Dummy Agent for Mata Garuda.

Your job is to demonstrate the agent template for the meta-agent.
You greet the user and immediately call case_resolved.

User: {user_name}

CONSTRAINTS (from GENOME.md):
- You only handle greetings
- You NEVER make external API calls
- You ALWAYS terminate with case_resolved or case_not_resolved
"""

    # Quando il package esisterà, qui si importeranno tool reali, es:
    # from mata_garuda.tools.basic import echo
    # from mata_garuda.runtime.case_status import case_resolved, case_not_resolved
    tool_list: list = []  # POC: vuoto

    # POC: ritorno un dict invece dell'oggetto Agent reale (manca import)
    return {  # type: ignore
        "name": "Dummy Agent",
        "model": model,
        "instructions": instructions,
        "functions": tool_list,
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "genome_path": GENOME_FILE,
        "layer": "meta",
    }


# ─── Form spec per il meta-agent (letteralmente passato nel prompt) ───────
"""
Form to create an agent (read by meta-agent's create_agent tool):

agent_name = "Dummy Agent"
agent_description = "Template agent for the meta-agent. Greets user and resolves."
agent_instructions = "..." | "...{global_variables}..."
agent_tools = []  # nessun tool nel dummy
"""
