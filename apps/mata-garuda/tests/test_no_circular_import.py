"""Tests that mata_garuda.notebook_registry has no circular import with config."""
from __future__ import annotations

import importlib
import sys


def test_registry_data_imports_alone():
    """_registry_data.py is pure data, must import without dragging config in."""
    # Drop both modules from sys.modules to simulate a cold import.
    for mod in ("mata_garuda._registry_data", "mata_garuda.config", "mata_garuda.notebook_registry"):
        sys.modules.pop(mod, None)
    importlib.import_module("mata_garuda._registry_data")
    assert "mata_garuda.config" not in sys.modules, (
        "_registry_data must not import config (circular import risk)"
    )


def test_notebook_registry_imports_alone():
    """notebook_registry.py imports _registry_data but NOT config."""
    for mod in ("mata_garuda._registry_data", "mata_garuda.config", "mata_garuda.notebook_registry"):
        sys.modules.pop(mod, None)
    importlib.import_module("mata_garuda.notebook_registry")
    assert "mata_garuda.config" not in sys.modules, (
        "notebook_registry must not import config (circular import risk)"
    )


def test_config_imports_after_registry():
    """config imports notebook_registry — that's the one allowed direction."""
    for mod in ("mata_garuda._registry_data", "mata_garuda.config", "mata_garuda.notebook_registry"):
        sys.modules.pop(mod, None)
    importlib.import_module("mata_garuda.config")
    assert "mata_garuda.notebook_registry" in sys.modules
    assert "mata_garuda._registry_data" in sys.modules
