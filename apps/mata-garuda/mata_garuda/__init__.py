"""
Mata Garuda — Intelligence Super Hub.

Package root. Esporta il registry singleton e i tipi core.
"""
__version__ = "0.1.0"

from mata_garuda.registry import registry, register_agent, register_tool, register_workflow
from mata_garuda.types import Agent, Response, Result, RunOutcome

__all__ = [
    "__version__",
    "registry",
    "register_agent",
    "register_tool",
    "register_workflow",
    "Agent",
    "Response",
    "Result",
    "RunOutcome",
]
