from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from core.plugins.plugin import Plugin, PluginCategory, PluginInput, PluginMetadata, PluginOutput
from core.plugins.registry import PluginRegistry


class RegistryInput(PluginInput):
    value: str


class RegistryOutput(PluginOutput):
    pass


class RegistryPlugin(Plugin):
    def __init__(self, config=None):
        self._metadata = PluginMetadata(
            name="registry.plugin",
            version="1.0.0",
            description="Registry plugin",
            category=PluginCategory.SYSTEM,
            tags=["alpha", "beta"],
            allowed_models=["haiku", "sonnet"],
            legacy_handler_key="legacy.registry",
        )
        super().__init__(config)

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    @property
    def input_schema(self) -> type[PluginInput]:
        return RegistryInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return RegistryOutput

    async def execute(self, _input_data: PluginInput) -> PluginOutput:
        return RegistryOutput(success=True, data={"ok": True})


class RegistryPluginV2(RegistryPlugin):
    def __init__(self, config=None):
        super().__init__(config)
        self._metadata = PluginMetadata(
            name="registry.plugin",
            version="2.0.0",
            description="Registry plugin v2",
            category=PluginCategory.SYSTEM,
            tags=["alpha"],
            allowed_models=["sonnet"],
            legacy_handler_key="legacy.registry",
        )


class RegistryOtherPlugin(RegistryPlugin):
    def __init__(self, config=None):
        self._metadata = PluginMetadata(
            name="other.plugin",
            version="1.0.0",
            description="Other plugin",
            category=PluginCategory.AI_SERVICES,
            tags=["gamma"],
            allowed_models=["sonnet"],
        )
        Plugin.__init__(self, config)


class FailingOnLoadPlugin(RegistryPlugin):
    def __init__(self, config=None):
        self._metadata = PluginMetadata(
            name="failing.plugin",
            version="1.0.0",
            description="Failing plugin",
            category=PluginCategory.SYSTEM,
        )
        Plugin.__init__(self, config)

    async def on_load(self):
        raise RuntimeError("load fail")


class FailingOnUnloadPlugin(RegistryPlugin):
    async def on_unload(self):
        raise RuntimeError("unload fail")


@pytest.mark.asyncio
async def test_register_and_get_with_alias():
    registry = PluginRegistry()
    plugin = await registry.register(RegistryPlugin)
    assert registry.get("registry.plugin") is plugin
    assert registry.get("legacy.registry") is plugin
    assert registry.get_metadata("registry.plugin") == plugin.metadata

    stats = registry.get_statistics()
    assert stats["total_plugins"] == 1
    assert stats["aliases"] == 1
    assert stats["total_versions"] == 1

    results = registry.search("alpha")
    assert results


@pytest.mark.asyncio
async def test_register_duplicate_version_returns_existing():
    registry = PluginRegistry()
    first = await registry.register(RegistryPlugin)
    second = await registry.register(RegistryPlugin)
    assert first is second
    assert registry.get_statistics()["total_versions"] == 1


@pytest.mark.asyncio
async def test_register_version_conflict_tracks_versions():
    registry = PluginRegistry()
    first = await registry.register(RegistryPlugin)
    second = await registry.register(RegistryPluginV2)
    assert first is not second
    assert registry.get("registry.plugin") is second
    assert registry.get_statistics()["total_versions"] == 2


@pytest.mark.asyncio
async def test_register_on_load_failure_rolls_back():
    registry = PluginRegistry()
    with pytest.raises(RuntimeError):
        await registry.register(FailingOnLoadPlugin)
    assert registry.get("failing.plugin") is None


@pytest.mark.asyncio
async def test_register_batch_continues_on_error():
    registry = PluginRegistry()
    plugins = await registry.register_batch([RegistryPlugin, FailingOnLoadPlugin])
    assert len(plugins) == 1
    assert registry.get("registry.plugin") is not None


@pytest.mark.asyncio
async def test_unregister_removes_alias_and_calls_unload():
    registry = PluginRegistry()
    await registry.register(FailingOnUnloadPlugin)
    await registry.unregister("registry.plugin")
    assert registry.get("registry.plugin") is None
    assert registry.get("legacy.registry") is None


@pytest.mark.asyncio
async def test_list_plugins_filters_and_sorting():
    registry = PluginRegistry()
    await registry.register(RegistryPlugin)
    await registry.register(RegistryOtherPlugin)

    all_plugins = registry.list_plugins()
    assert [m.name for m in all_plugins] == ["other.plugin", "registry.plugin"]

    system_only = registry.list_plugins(category=PluginCategory.SYSTEM)
    assert [m.name for m in system_only] == ["registry.plugin"]

    tagged = registry.list_plugins(tags=["gamma"])
    assert [m.name for m in tagged] == ["other.plugin"]

    allowed = registry.list_plugins(allowed_models=["haiku"])
    assert [m.name for m in allowed] == ["registry.plugin"]


@pytest.mark.asyncio
async def test_discover_plugins_missing_dir(tmp_path):
    registry = PluginRegistry()
    missing = tmp_path / "missing"
    result = await registry.discover_plugins(missing)
    assert result["discovered"] == 0
    assert result["errors"]

    with pytest.raises(FileNotFoundError):
        await registry.discover_plugins(missing, strict=True)


@pytest.mark.asyncio
async def test_discover_plugins_invalid_prefix(tmp_path):
    registry = PluginRegistry()
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    result = await registry.discover_plugins(plugins_dir, package_prefix="bad-prefix")
    assert result["discovered"] == 0
    assert result["errors"]

    with pytest.raises(ValueError):
        await registry.discover_plugins(plugins_dir, package_prefix="bad-prefix", strict=True)


@pytest.mark.asyncio
async def test_discover_plugins_invalid_module_segment(tmp_path):
    registry = PluginRegistry()
    bad_dir = tmp_path / "1bad"
    bad_dir.mkdir()
    (bad_dir / "plugin.py").write_text("x = 1", encoding="utf-8")
    result = await registry.discover_plugins(tmp_path)
    assert result["discovered"] == 0
    assert result["errors"]


@pytest.mark.asyncio
async def test_discover_plugins_import_failure(tmp_path):
    import importlib

    registry = PluginRegistry()
    plugin_file = tmp_path / "demo.py"
    plugin_file.write_text("x = 1", encoding="utf-8")
    registry_module = importlib.import_module("core.plugins.registry")

    with patch.object(registry_module.importlib, "import_module", side_effect=ImportError("no")):
        result = await registry.discover_plugins(tmp_path)
    assert result["discovered"] == 0
    assert result["errors"]


@pytest.mark.asyncio
async def test_discover_plugins_register_failure(tmp_path):
    import importlib

    registry = PluginRegistry()
    plugin_file = tmp_path / "demo.py"
    plugin_file.write_text("x = 1", encoding="utf-8")
    module = SimpleNamespace()
    registry_module = importlib.import_module("core.plugins.registry")

    with patch.object(registry_module.importlib, "import_module", return_value=module):
        with patch.object(
            registry_module.inspect,
            "getmembers",
            return_value=[("RegistryPlugin", RegistryPlugin)],
        ):
            registry.register = AsyncMock(side_effect=RuntimeError("boom"))
            result = await registry.discover_plugins(tmp_path)
    assert result["discovered"] == 0
    assert result["errors"]


@pytest.mark.asyncio
async def test_discover_plugins_success(tmp_path):
    import importlib

    registry = PluginRegistry()
    plugin_file = tmp_path / "demo.py"
    plugin_file.write_text("x = 1", encoding="utf-8")
    module = SimpleNamespace()
    registry_module = importlib.import_module("core.plugins.registry")

    with patch.object(registry_module.importlib, "import_module", return_value=module):
        with patch.object(
            registry_module.inspect,
            "getmembers",
            return_value=[("RegistryPlugin", RegistryPlugin)],
        ):
            result = await registry.discover_plugins(tmp_path, package_prefix="plugins")
    assert result["discovered"] == 1
    assert result["errors"] == []


def test_search_by_name_description_tags():
    registry = PluginRegistry()
    registry._metadata["registry.plugin"] = RegistryPlugin().metadata
    assert registry.search("registry")
    assert registry.search("registry plugin")
    assert registry.search("alpha")


def test_get_all_anthropic_tools_and_haiku():
    registry = PluginRegistry()
    plugin = RegistryPlugin()
    registry._plugins[plugin.metadata.name] = plugin
    tools = registry.get_all_anthropic_tools()
    assert tools

    plugin.to_anthropic_tool_definition = lambda: (_ for _ in ()).throw(RuntimeError("fail"))
    tools_with_error = registry.get_all_anthropic_tools()
    assert tools_with_error == []

    registry._plugins[plugin.metadata.name] = RegistryPlugin()
    haiku_tools = registry.get_haiku_allowed_tools()
    assert haiku_tools


@pytest.mark.asyncio
async def test_reload_plugin_not_found():
    registry = PluginRegistry()
    with pytest.raises(ValueError):
        await registry.reload_plugin("missing.plugin")


@pytest.mark.asyncio
async def test_reload_plugin_success():
    registry = PluginRegistry()
    plugin = await registry.register(RegistryPlugin, config={"key": "value"})
    with patch.object(registry, "unregister", AsyncMock()) as unregister:
        with patch.object(registry, "register", AsyncMock()) as register:
            await registry.reload_plugin(plugin.metadata.name)
    unregister.assert_awaited_once_with(plugin.metadata.name)
    register.assert_awaited_once_with(type(plugin), plugin.config)
