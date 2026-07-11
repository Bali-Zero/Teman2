"""
Mata Garuda — Intelligence Super Hub.

Package root. Esporta il registry singleton e i tipi core.
"""
__version__ = "0.1.0"

# Load LaunchAgent secrets (~/.nuzantara-secrets.env) + canonical Redis
# defaults into os.environ BEFORE any submodule reads env. This replaces the
# ~/scripts shell wrapper (W84 TCC + cicatrix #1 HOME-fork, 2026-07-01):
# launchd now calls the venv python directly and this fills missing env.
from mata_garuda import _bootstrap_env  # noqa: F401  (import side-effect)

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
