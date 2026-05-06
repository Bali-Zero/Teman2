"""Tests that mata_garuda.notebook_registry has no circular import with config."""
from __future__ import annotations

import importlib
import sys


# Modules that participate in the import-direction invariant
# (config → notebook_registry → _registry_data, no back-edges).
# Listed together so all three tests reset them consistently.
_CIRCULAR_IMPORT_MODULES = (
    "mata_garuda",
    "mata_garuda._registry_data",
    "mata_garuda.config",
    "mata_garuda.notebook_registry",
)


def test_registry_data_imports_alone():
    """_registry_data.py is pure data, must import without dragging config in."""
    for mod in _CIRCULAR_IMPORT_MODULES:
        sys.modules.pop(mod, None)
    importlib.import_module("mata_garuda._registry_data")
    assert "mata_garuda.config" not in sys.modules, (
        "_registry_data must not import config (circular import risk)"
    )


def test_notebook_registry_imports_alone():
    """notebook_registry.py imports _registry_data but NOT config."""
    for mod in _CIRCULAR_IMPORT_MODULES:
        sys.modules.pop(mod, None)
    importlib.import_module("mata_garuda.notebook_registry")
    assert "mata_garuda.config" not in sys.modules, (
        "notebook_registry must not import config (circular import risk)"
    )


def test_config_imports_after_registry():
    """config imports notebook_registry — that's the one allowed direction."""
    for mod in _CIRCULAR_IMPORT_MODULES:
        sys.modules.pop(mod, None)
    importlib.import_module("mata_garuda.config")
    assert "mata_garuda.notebook_registry" in sys.modules, (
        "config must import notebook_registry (shim dependency)"
    )
    assert "mata_garuda._registry_data" in sys.modules, (
        "config must transitively import _registry_data via notebook_registry"
    )
