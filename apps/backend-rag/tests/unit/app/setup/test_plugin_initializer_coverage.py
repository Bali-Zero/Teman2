import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


class DummyRegistry:
    def __init__(self, stats=None, error=None):
        self.stats = stats or {"total_plugins": 2, "categories": 1}
        self.error = error
        self.discover_calls = []

    async def discover_plugins(self, plugins_dir, package_prefix=""):
        if self.error:
            raise self.error
        self.discover_calls.append((plugins_dir, package_prefix))

    def get_statistics(self):
        return self.stats


class DummyApp:
    def __init__(self):
        self.state = SimpleNamespace()


@pytest.mark.asyncio
async def test_initialize_plugins_success(monkeypatch):
    registry = DummyRegistry()
    core_module = ModuleType("core")
    plugins_module = ModuleType("backend.core.plugins")
    plugins_module.registry = registry
    monkeypatch.setitem(sys.modules, "core", core_module)
    monkeypatch.setitem(sys.modules, "backend.core.plugins", plugins_module)

    module_path = (
        Path(__file__).resolve().parents[4] / "backend" / "app" / "setup" / "plugin_initializer.py"
    )
    spec = importlib.util.spec_from_file_location("backend.app.setup.plugin_initializer", module_path)
    plugin_initializer = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, plugin_initializer)
    spec.loader.exec_module(plugin_initializer)

    app = DummyApp()

    backend_root = Path(plugin_initializer.__file__).parent.parent.parent
    backend_parent = backend_root.parent
    monkeypatch.setattr(sys, "path", [])

    await plugin_initializer.initialize_plugins(app)

    assert registry.discover_calls
    plugins_dir, prefix = registry.discover_calls[0]
    assert plugins_dir == backend_root / "plugins"
    assert prefix == "plugins"
    assert app.state.plugin_registry is registry
    assert str(backend_parent) in sys.path


@pytest.mark.asyncio
async def test_initialize_plugins_error(monkeypatch):
    registry = DummyRegistry(error=RuntimeError("boom"))
    core_module = ModuleType("core")
    plugins_module = ModuleType("backend.core.plugins")
    plugins_module.registry = registry
    monkeypatch.setitem(sys.modules, "core", core_module)
    monkeypatch.setitem(sys.modules, "backend.core.plugins", plugins_module)

    module_path = (
        Path(__file__).resolve().parents[4] / "backend" / "app" / "setup" / "plugin_initializer.py"
    )
    spec = importlib.util.spec_from_file_location("backend.app.setup.plugin_initializer", module_path)
    plugin_initializer = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, plugin_initializer)
    spec.loader.exec_module(plugin_initializer)

    app = DummyApp()
    monkeypatch.setattr(sys, "path", [])

    await plugin_initializer.initialize_plugins(app)

    assert app.state.plugin_registry is None
