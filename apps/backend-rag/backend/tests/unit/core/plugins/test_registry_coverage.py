"""
Unit tests for backend/core/plugins/registry.py
Covers: PluginRegistry — register, unregister, get, list, search, discover, stats, tools
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.plugins.plugin import (
    Plugin,
    PluginCategory,
    PluginInput,
    PluginMetadata,
    PluginOutput,
)
from backend.core.plugins.registry import PluginRegistry


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — concrete plugin implementations for tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_plugin_class(
    name: str,
    version: str = "1.0.0",
    category: PluginCategory = PluginCategory.GENERAL,
    tags: list[str] | None = None,
    allowed_models: list[str] | None = None,
    requires_auth: bool = False,
    legacy_handler_key: str | None = None,
    rate_limit: int | None = None,
):
    """Factory: create a concrete Plugin subclass dynamically."""
    meta = PluginMetadata(
        name=name,
        version=version,
        description=f"Test plugin {name}",
        category=category,
        tags=tags or [],
        allowed_models=allowed_models or ["gemini-flash", "gemini-pro"],
        requires_auth=requires_auth,
        legacy_handler_key=legacy_handler_key,
        rate_limit=rate_limit,
    )

    class ConcretePlugin(Plugin):
        @property
        def metadata(self) -> PluginMetadata:
            return meta

        @property
        def input_schema(self) -> type[PluginInput]:
            return PluginInput

        @property
        def output_schema(self) -> type[PluginOutput]:
            return PluginOutput

        async def execute(self, input_data: PluginInput) -> PluginOutput:
            return PluginOutput(success=True)

    ConcretePlugin.__name__ = name.replace(".", "_")
    return ConcretePlugin


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def registry():
    """Fresh PluginRegistry for each test."""
    return PluginRegistry()


# ─────────────────────────────────────────────────────────────────────────────
# __init__
# ─────────────────────────────────────────────────────────────────────────────

def test_registry_init_empty(registry):
    assert len(registry._plugins) == 0
    assert len(registry._metadata) == 0
    assert len(registry._aliases) == 0


# ─────────────────────────────────────────────────────────────────────────────
# register
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_basic(registry):
    cls = _make_plugin_class("test.basic")
    plugin = await registry.register(cls)
    assert plugin is not None
    assert "test.basic" in registry._plugins
    assert "test.basic" in registry._metadata


@pytest.mark.asyncio
async def test_register_returns_existing_on_same_version(registry):
    cls = _make_plugin_class("test.dup")
    p1 = await registry.register(cls)
    p2 = await registry.register(cls)
    assert p1 is p2
    assert len(registry._plugins) == 1


@pytest.mark.asyncio
async def test_register_version_conflict_replaces(registry):
    cls_v1 = _make_plugin_class("test.conflict", version="1.0.0")
    cls_v2 = _make_plugin_class("test.conflict", version="2.0.0")
    await registry.register(cls_v1)
    await registry.register(cls_v2)
    # Newer version replaces
    assert registry._metadata["test.conflict"].version == "2.0.0"


@pytest.mark.asyncio
async def test_register_legacy_alias(registry):
    cls = _make_plugin_class("test.alias", legacy_handler_key="legacy.key")
    await registry.register(cls)
    assert "legacy.key" in registry._aliases
    assert registry._aliases["legacy.key"] == "test.alias"


@pytest.mark.asyncio
async def test_register_on_load_failure_rolls_back(registry):
    cls = _make_plugin_class("test.failing")

    # Patch on_load to raise
    original_on_load = cls.on_load
    async def _bad_on_load(self):
        raise RuntimeError("load failed")
    cls.on_load = _bad_on_load

    with pytest.raises(RuntimeError, match="load failed"):
        await registry.register(cls)

    assert "test.failing" not in registry._plugins
    assert "test.failing" not in registry._metadata


@pytest.mark.asyncio
async def test_register_tracks_versions(registry):
    cls = _make_plugin_class("test.versions", version="1.0.0")
    await registry.register(cls)
    assert "1.0.0" in registry._versions["test.versions"]


@pytest.mark.asyncio
async def test_register_with_config(registry):
    cls = _make_plugin_class("test.config")
    plugin = await registry.register(cls, config={"key": "value"})
    assert plugin.config == {"key": "value"}


# ─────────────────────────────────────────────────────────────────────────────
# register_batch
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_batch(registry):
    classes = [
        _make_plugin_class("batch.one"),
        _make_plugin_class("batch.two"),
        _make_plugin_class("batch.three"),
    ]
    plugins = await registry.register_batch(classes)
    assert len(plugins) == 3


@pytest.mark.asyncio
async def test_register_batch_partial_failure(registry):
    """Batch continues even if one plugin fails."""
    good_cls = _make_plugin_class("batch.good")
    bad_cls = _make_plugin_class("batch.bad")

    async def _bad_on_load(self):
        raise RuntimeError("fail")
    bad_cls.on_load = _bad_on_load

    plugins = await registry.register_batch([good_cls, bad_cls])
    # Only the good one is returned
    assert len(plugins) == 1
    assert "batch.good" in registry._plugins


# ─────────────────────────────────────────────────────────────────────────────
# unregister
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unregister_removes_plugin(registry):
    cls = _make_plugin_class("test.unregister")
    await registry.register(cls)
    await registry.unregister("test.unregister")
    assert "test.unregister" not in registry._plugins


@pytest.mark.asyncio
async def test_unregister_removes_alias(registry):
    cls = _make_plugin_class("test.alias_remove", legacy_handler_key="alias.remove")
    await registry.register(cls)
    await registry.unregister("test.alias_remove")
    assert "alias.remove" not in registry._aliases


@pytest.mark.asyncio
async def test_unregister_nonexistent_noop(registry):
    # Should not raise
    await registry.unregister("does.not.exist")


@pytest.mark.asyncio
async def test_unregister_on_unload_failure_still_removes(registry):
    cls = _make_plugin_class("test.unload_fail")

    async def _bad_on_unload(self):
        raise RuntimeError("unload error")
    cls.on_unload = _bad_on_unload

    await registry.register(cls)
    # Should not raise even if on_unload fails
    await registry.unregister("test.unload_fail")
    assert "test.unload_fail" not in registry._plugins


# ─────────────────────────────────────────────────────────────────────────────
# get
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_by_name(registry):
    cls = _make_plugin_class("test.get")
    await registry.register(cls)
    plugin = registry.get("test.get")
    assert plugin is not None
    assert plugin.metadata.name == "test.get"


@pytest.mark.asyncio
async def test_get_by_alias(registry):
    cls = _make_plugin_class("test.get_alias", legacy_handler_key="legacy.get")
    await registry.register(cls)
    plugin = registry.get("legacy.get")
    assert plugin is not None
    assert plugin.metadata.name == "test.get_alias"


def test_get_nonexistent_returns_none(registry):
    result = registry.get("nonexistent")
    assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# get_metadata
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_metadata_returns_metadata(registry):
    cls = _make_plugin_class("test.meta")
    await registry.register(cls)
    meta = registry.get_metadata("test.meta")
    assert meta is not None
    assert meta.name == "test.meta"


def test_get_metadata_nonexistent_returns_none(registry):
    assert registry.get_metadata("nonexistent") is None


# ─────────────────────────────────────────────────────────────────────────────
# list_plugins
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_plugins_all(registry):
    await registry.register(_make_plugin_class("list.one"))
    await registry.register(_make_plugin_class("list.two"))
    result = registry.list_plugins()
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_plugins_filter_category(registry):
    cls_ai = _make_plugin_class("list.ai", category=PluginCategory.AI_SERVICES)
    cls_gen = _make_plugin_class("list.gen", category=PluginCategory.GENERAL)
    await registry.register(cls_ai)
    await registry.register(cls_gen)
    result = registry.list_plugins(category=PluginCategory.AI_SERVICES)
    assert len(result) == 1
    assert result[0].name == "list.ai"


@pytest.mark.asyncio
async def test_list_plugins_filter_tags(registry):
    cls_tagged = _make_plugin_class("list.tagged", tags=["email", "send"])
    cls_plain = _make_plugin_class("list.plain", tags=["sms"])
    await registry.register(cls_tagged)
    await registry.register(cls_plain)
    result = registry.list_plugins(tags=["email"])
    assert len(result) == 1
    assert result[0].name == "list.tagged"


@pytest.mark.asyncio
async def test_list_plugins_filter_allowed_models(registry):
    cls_haiku = _make_plugin_class("list.haiku", allowed_models=["haiku", "gemini-flash"])
    cls_pro = _make_plugin_class("list.pro", allowed_models=["gemini-pro"])
    await registry.register(cls_haiku)
    await registry.register(cls_pro)
    result = registry.list_plugins(allowed_models=["haiku"])
    assert len(result) == 1
    assert result[0].name == "list.haiku"


@pytest.mark.asyncio
async def test_list_plugins_sorted(registry):
    # Registers in reverse order — should sort by (category, name)
    await registry.register(_make_plugin_class("zzz.plugin", category=PluginCategory.GENERAL))
    await registry.register(_make_plugin_class("aaa.plugin", category=PluginCategory.GENERAL))
    result = registry.list_plugins()
    names = [m.name for m in result]
    assert names == sorted(names)


# ─────────────────────────────────────────────────────────────────────────────
# search
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_by_name(registry):
    await registry.register(_make_plugin_class("gmail.send"))
    await registry.register(_make_plugin_class("sms.send"))
    result = registry.search("gmail")
    assert len(result) == 1
    assert result[0].name == "gmail.send"


@pytest.mark.asyncio
async def test_search_by_tag(registry):
    cls = _make_plugin_class("search.tag", tags=["invoice", "pdf"])
    await registry.register(cls)
    result = registry.search("invoice")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_search_case_insensitive(registry):
    cls = _make_plugin_class("Search.Case")
    await registry.register(cls)
    result = registry.search("search.case")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_search_no_match_returns_empty(registry):
    await registry.register(_make_plugin_class("test.nope"))
    result = registry.search("xxxxxxxxxx")
    assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# get_statistics
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_statistics_empty(registry):
    stats = registry.get_statistics()
    assert stats["total_plugins"] == 0
    assert stats["categories"] == 0


@pytest.mark.asyncio
async def test_get_statistics_with_plugins(registry):
    await registry.register(_make_plugin_class("stats.one", category=PluginCategory.GENERAL))
    await registry.register(_make_plugin_class("stats.two", category=PluginCategory.AI_SERVICES))
    stats = registry.get_statistics()
    assert stats["total_plugins"] == 2
    assert stats["categories"] == 2


@pytest.mark.asyncio
async def test_get_statistics_aliases(registry):
    cls = _make_plugin_class("stats.alias", legacy_handler_key="stats.leg")
    await registry.register(cls)
    stats = registry.get_statistics()
    assert stats["aliases"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# get_all_anthropic_tools
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_all_anthropic_tools(registry):
    await registry.register(_make_plugin_class("tool.one"))
    await registry.register(_make_plugin_class("tool.two"))
    tools = registry.get_all_anthropic_tools()
    assert len(tools) == 2
    assert all("name" in t and "description" in t for t in tools)


@pytest.mark.asyncio
async def test_get_all_anthropic_tools_error_skipped(registry):
    """If to_anthropic_tool_definition raises, plugin is skipped."""
    cls = _make_plugin_class("tool.error")
    await registry.register(cls)
    plugin = registry.get("tool.error")
    plugin.to_anthropic_tool_definition = MagicMock(side_effect=RuntimeError("bad"))
    tools = registry.get_all_anthropic_tools()
    assert len(tools) == 0


# ─────────────────────────────────────────────────────────────────────────────
# get_haiku_allowed_tools
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_haiku_allowed_tools(registry):
    cls_haiku = _make_plugin_class("haiku.tool", allowed_models=["haiku", "gemini-flash"])
    cls_pro = _make_plugin_class("pro.only", allowed_models=["gemini-pro"])
    await registry.register(cls_haiku)
    await registry.register(cls_pro)
    tools = registry.get_haiku_allowed_tools()
    assert len(tools) == 1
    # haiku.tool has haiku in allowed_models
    assert any("haiku" in t.get("name", "") or "haiku" in t.get("description", "") for t in tools)


# ─────────────────────────────────────────────────────────────────────────────
# reload_plugin
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reload_plugin(registry):
    cls = _make_plugin_class("reload.me")
    await registry.register(cls)
    # Reload should not raise
    await registry.reload_plugin("reload.me")
    assert "reload.me" in registry._plugins


@pytest.mark.asyncio
async def test_reload_plugin_not_found_raises(registry):
    with pytest.raises(ValueError, match="not found"):
        await registry.reload_plugin("does.not.exist")


# ─────────────────────────────────────────────────────────────────────────────
# discover_plugins
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_discover_plugins_missing_dir_non_strict(registry, tmp_path):
    missing = tmp_path / "nonexistent"
    result = await registry.discover_plugins(missing)
    assert result["discovered"] == 0
    assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_discover_plugins_missing_dir_strict_raises(registry, tmp_path):
    missing = tmp_path / "nonexistent"
    with pytest.raises(FileNotFoundError):
        await registry.discover_plugins(missing, strict=True)


@pytest.mark.asyncio
async def test_discover_plugins_invalid_prefix_non_strict(registry, tmp_path):
    result = await registry.discover_plugins(tmp_path, package_prefix="123-invalid")
    assert result["discovered"] == 0
    assert len(result["errors"]) == 1


@pytest.mark.asyncio
async def test_discover_plugins_invalid_prefix_strict_raises(registry, tmp_path):
    with pytest.raises(ValueError):
        await registry.discover_plugins(tmp_path, package_prefix="123-invalid", strict=True)


@pytest.mark.asyncio
async def test_discover_plugins_skips_underscore_files(registry, tmp_path):
    """Files starting with _ should be skipped."""
    (tmp_path / "_private_plugin.py").write_text("# private")
    result = await registry.discover_plugins(tmp_path)
    assert result["discovered"] == 0
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_discover_plugins_import_failure_non_strict(registry, tmp_path):
    """Files that fail to import are collected as errors, don't crash."""
    plugin_file = tmp_path / "bad_plugin.py"
    plugin_file.write_text("raise ImportError('cannot import')\n")
    result = await registry.discover_plugins(tmp_path)
    # May have errors, but discovered = 0
    assert result["discovered"] == 0


@pytest.mark.asyncio
async def test_discover_plugins_empty_dir(registry, tmp_path):
    result = await registry.discover_plugins(tmp_path)
    assert result["discovered"] == 0
    assert result["errors"] == []
