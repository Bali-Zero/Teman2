import pytest
from backend.core.plugins.plugin import (
    Plugin,
    PluginCategory,
    PluginInput,
    PluginMetadata,
    PluginOutput,
)
from pydantic import ValidationError


class ExampleInput(PluginInput):
    name: str


class ExampleOutput(PluginOutput):
    pass


class ExamplePlugin(Plugin):
    def __init__(self, *, legacy_handler_key=None, config_schema=None):
        self._metadata = PluginMetadata(
            name="example.plugin",
            description="Example plugin",
            category=PluginCategory.SYSTEM,
            legacy_handler_key=legacy_handler_key,
            config_schema=config_schema,
        )
        super().__init__()

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    @property
    def input_schema(self) -> type[PluginInput]:
        return ExampleInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return ExampleOutput

    async def execute(self, _input_data: PluginInput) -> PluginOutput:
        return ExampleOutput(success=True, data={"ok": True})


class BadPlugin(Plugin):
    @property
    def metadata(self) -> PluginMetadata:
        raise AttributeError("missing")

    @property
    def input_schema(self) -> type[PluginInput]:
        return ExampleInput

    @property
    def output_schema(self) -> type[PluginOutput]:
        return ExampleOutput

    async def execute(self, _input_data: PluginInput) -> PluginOutput:
        return ExampleOutput(success=True)


def test_plugin_metadata_version_validation():
    PluginMetadata(
        name="valid.plugin",
        description="ok",
        category=PluginCategory.SYSTEM,
        version="1.2.3",
    )
    with pytest.raises(ValidationError):
        PluginMetadata(
            name="bad.plugin",
            description="bad",
            category=PluginCategory.SYSTEM,
            version="1.0",
        )
    with pytest.raises(ValidationError):
        PluginMetadata(
            name="bad.plugin",
            description="bad",
            category=PluginCategory.SYSTEM,
            version="1.x.0",
        )


def test_plugin_output_ok_field_behavior():
    output = PluginOutput(success=True, data="ok")
    assert output.ok is True

    output_with_ok = PluginOutput(success=True, ok=False)
    assert output_with_ok.ok is False


def test_plugin_input_allows_extra_fields():
    data = ExampleInput(name="test", extra_field="extra")
    assert data.name == "test"
    assert data.extra_field == "extra"


def test_plugin_init_validates_metadata_and_config():
    plugin = ExamplePlugin(config_schema={"type": "object"})
    assert plugin.metadata.name == "example.plugin"


def test_plugin_init_missing_metadata_raises():
    with pytest.raises(NotImplementedError):
        BadPlugin()


@pytest.mark.asyncio
async def test_plugin_on_load_and_unload():
    plugin = ExamplePlugin()
    await plugin.on_load()
    await plugin.on_unload()


def test_plugin_to_anthropic_tool_definition():
    plugin = ExamplePlugin()
    definition = plugin.to_anthropic_tool_definition()
    assert definition["name"] == "example_plugin"
    assert definition["description"] == "Example plugin"
    assert "input_schema" in definition


def test_plugin_to_handler_format_legacy_key():
    plugin = ExamplePlugin(legacy_handler_key="legacy.key")
    handler = plugin.to_handler_format()
    assert handler["key"] == "legacy.key"
    assert handler["requiresAuth"] is False
    assert handler["requiresAdmin"] is False
