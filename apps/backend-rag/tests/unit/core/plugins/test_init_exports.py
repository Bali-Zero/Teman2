import importlib

import backend.core.plugins.plugin as plugin_module
from backend.core.plugins import (
    Plugin,
    PluginCategory,
    PluginExecutor,
    PluginInput,
    PluginMetadata,
    PluginOutput,
    PluginRegistry,
    executor,
    registry,
)
from backend.core.plugins.executor import PluginExecutor as ExecutorClass


def test_plugins_init_exports():
    import backend.core.plugins as plugins

    expected = {
        "Plugin",
        "PluginMetadata",
        "PluginInput",
        "PluginOutput",
        "PluginCategory",
        "PluginRegistry",
        "registry",
        "PluginExecutor",
        "executor",
    }

    assert set(plugins.__all__) == expected
    for name in expected:
        assert hasattr(plugins, name)


def test_plugins_init_reexports_identity():
    registry_module = importlib.import_module("backend.core.plugins.registry")
    assert Plugin is plugin_module.Plugin
    assert PluginMetadata is plugin_module.PluginMetadata
    assert PluginInput is plugin_module.PluginInput
    assert PluginOutput is plugin_module.PluginOutput
    assert PluginCategory is plugin_module.PluginCategory

    assert PluginRegistry is registry_module.PluginRegistry
    assert registry is registry_module.registry

    assert PluginExecutor is ExecutorClass
    assert executor.__class__ is ExecutorClass
