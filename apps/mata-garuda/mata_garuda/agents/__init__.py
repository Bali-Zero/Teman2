"""
Mata Garuda — Agents package.

Auto-import ricorsivo di tutti i .py sotto questa directory.
Triggera i @register_agent decorator che popolano il registry singleton.
"""
import os

from mata_garuda.registry import import_all_recursively, registry

_current_dir = os.path.dirname(__file__)
import_all_recursively(_current_dir, "mata_garuda.agents")

# Export tutti gli agenti registrati come attributi del modulo
globals().update(registry.agents)

__all__ = list(registry.agents.keys())
