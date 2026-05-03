"""
Mata Garuda — Registry singleton + decorator.

Pattern estratto da HKUDS/AutoAgent autoagent/registry.py (~200 LOC originale)
e semplificato per i vincoli Mata Garuda:
- Rimossa dipendenza tiktoken (truncate_output non necessario per noi)
- Rimossa distinzione plugin_tools/plugin_agents (sovra-design)
- Mantenuto: singleton, dataclass FunctionInfo, decorator @register_*

Riferimento doc: docs/mata-garuda/40d-AUTOAGENT-PATTERNS.md Pattern 1
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Literal, Optional
import importlib
import inspect
import os


@dataclass
class FunctionInfo:
    """Metadati di una funzione registrata (agent o tool)."""

    name: str
    func_name: str
    func: Callable
    args: List[str]
    docstring: Optional[str]
    file_path: Optional[str]
    return_type: Optional[str]

    def to_dict(self) -> dict:
        """Serializza escludendo func (non picklable)."""
        d = asdict(self)
        d.pop("func", None)
        return d


class Registry:
    """Singleton globale per agents + tools registrati via decorator."""

    _instance: Optional["Registry"] = None
    _registry: Dict[str, Dict[str, Callable]] = {
        "tools": {},
        "agents": {},
        "workflows": {},
    }
    _registry_info: Dict[str, Dict[str, FunctionInfo]] = {
        "tools": {},
        "agents": {},
        "workflows": {},
    }

    def __new__(cls) -> "Registry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(
        self,
        type: Literal["tool", "agent", "workflow"],
        name: Optional[str] = None,
        func_name: Optional[str] = None,
    ):
        """
        Decorator factory. Registra una funzione nel registry.

        Args:
            type: kind of object ("tool", "agent", "workflow")
            name: display name (default: func.__name__)
            func_name: callable key in registry (default: name)

        Usage:
            @registry.register("agent", name="Dummy Agent", func_name="get_dummy_agent")
            def get_dummy_agent(model: str) -> Agent: ...
        """

        def decorator(func: Callable) -> Callable:
            display_name = name or func.__name__
            callable_key = func_name or display_name

            try:
                file_path = os.path.abspath(inspect.getfile(func))
            except (TypeError, OSError):
                file_path = "Unknown"

            sig = inspect.signature(func)
            return_type = (
                str(sig.return_annotation)
                if sig.return_annotation is not inspect.Signature.empty
                else None
            )

            info = FunctionInfo(
                name=display_name,
                func_name=callable_key,
                func=func,
                args=list(sig.parameters.keys()),
                docstring=inspect.getdoc(func),
                file_path=file_path,
                return_type=return_type,
            )

            registry_type = f"{type}s"
            self._registry[registry_type][callable_key] = func
            self._registry_info[registry_type][display_name] = info
            return func

        return decorator

    @property
    def agents(self) -> Dict[str, Callable]:
        return self._registry["agents"]

    @property
    def tools(self) -> Dict[str, Callable]:
        return self._registry["tools"]

    @property
    def workflows(self) -> Dict[str, Callable]:
        return self._registry["workflows"]

    @property
    def agents_info(self) -> Dict[str, FunctionInfo]:
        return self._registry_info["agents"]

    @property
    def tools_info(self) -> Dict[str, FunctionInfo]:
        return self._registry_info["tools"]

    def display_agents_info(self) -> dict:
        """Versione serializable per JSON dump (usata da list_agents tool)."""
        return {n: i.to_dict() for n, i in self.agents_info.items()}


# Singleton globale — i moduli importano questo
registry = Registry()


# Convenience decorators (API pubblica)
def register_agent(name: Optional[str] = None, func_name: Optional[str] = None):
    return registry.register("agent", name=name, func_name=func_name)


def register_tool(name: Optional[str] = None, func_name: Optional[str] = None):
    return registry.register("tool", name=name, func_name=func_name)


def register_workflow(name: Optional[str] = None, func_name: Optional[str] = None):
    return registry.register("workflow", name=name, func_name=func_name)


def get_agent(display_name: str) -> Optional[object]:
    """Retrieve an instantiated Agent by its display name.

    Looks up the agent factory in the registry, calls it, and returns
    the Agent instance. Returns None if not found.

    Args:
        display_name: The agent's display name (e.g. "Regulation Watcher")

    Returns:
        Agent instance or None
    """
    info = registry.agents_info.get(display_name)
    if info is None:
        return None
    return info.func()


# ─── Recursive auto-import (chiamato da agents/__init__.py) ──────────────────


def import_all_recursively(base_dir: str, base_package: str) -> None:
    """
    Cammina ricorsivamente sotto base_dir e importa tutti i .py.
    Triggera i decorator @register_* che popolano il singleton.

    Args:
        base_dir: filesystem path della directory radice
        base_package: nome del package Python (es. "mata_garuda.agents")

    Errori di import vengono loggati ma non bloccano l'avvio.
    """
    for root, _dirs, files in os.walk(base_dir):
        rel = os.path.relpath(root, base_dir)
        for file in files:
            if not file.endswith(".py") or file.startswith("__"):
                continue
            if rel == ".":
                module_path = f"{base_package}.{file[:-3]}"
            else:
                pkg_path = rel.replace(os.path.sep, ".")
                module_path = f"{base_package}.{pkg_path}.{file[:-3]}"
            try:
                importlib.import_module(module_path)
            except Exception as e:
                # Don't crash boot — log and continue
                print(f"[mata_garuda.registry] failed to import {module_path}: {e}")
