"""Smoke tests: verify all tool modules import and register correctly."""

import importlib

import pytest


ALL_TOOL_MODULES = [
    "nuzantara_mcp.tools.crm",
    "nuzantara_mcp.tools.portal",
    "nuzantara_mcp.tools.intel",
    "nuzantara_mcp.tools.content",
    "nuzantara_mcp.tools.analytics",
    "nuzantara_mcp.tools.knowledge",
    "nuzantara_mcp.tools.comms",
    "nuzantara_mcp.tools.drive",
    "nuzantara_mcp.tools.sheets",
    "nuzantara_mcp.tools.workflows",
    "nuzantara_mcp.tools.admin",
    "nuzantara_mcp.tools.health",
    "nuzantara_mcp.tools.google_bridge",
    "nuzantara_mcp.tools.journey",
    "nuzantara_mcp.tools.pricing",
    "nuzantara_mcp.tools.invoicing",
    "nuzantara_mcp.tools.compliance",
    "nuzantara_mcp.tools.memory",
    "nuzantara_mcp.tools.langsmith",
    "nuzantara_mcp.tools.legal",
    "nuzantara_mcp.tools.prime",
    "nuzantara_mcp.tools.federation",
    "nuzantara_mcp.tools.naga",
    "nuzantara_mcp.tools.kg_intel",
]

OTHER_MODULES = [
    "nuzantara_mcp.prompts.templates",
    "nuzantara_mcp.resources.config",
    "nuzantara_mcp.workflows.chains",
    "nuzantara_mcp.workflows.heartbeat",
]


@pytest.mark.parametrize("module_name", ALL_TOOL_MODULES)
def test_tool_module_imports(module_name: str) -> None:
    """Each tool module should import without errors."""
    mod = importlib.import_module(module_name)
    assert hasattr(mod, "register"), f"{module_name} missing register() function"


@pytest.mark.parametrize("module_name", OTHER_MODULES)
def test_other_module_imports(module_name: str) -> None:
    """Prompts, resources, and workflow modules should import cleanly."""
    mod = importlib.import_module(module_name)
    assert hasattr(mod, "register"), f"{module_name} missing register() function"


@pytest.mark.parametrize("module_name", ALL_TOOL_MODULES)
def test_tool_module_register_callable(module_name: str) -> None:
    """Each register() function should accept (mcp, _call, _call_safe)."""
    mod = importlib.import_module(module_name)
    register_fn = getattr(mod, "register")
    assert callable(register_fn)
    # Check it accepts at least 3 arguments
    import inspect
    sig = inspect.signature(register_fn)
    assert len(sig.parameters) >= 3, (
        f"{module_name}.register() should accept (mcp, _call, _call_safe), "
        f"got {list(sig.parameters.keys())}"
    )


def test_server_module_imports() -> None:
    """The main server module should import without errors."""
    # This triggers all register() calls
    mod = importlib.import_module("nuzantara_mcp.server")
    assert hasattr(mod, "mcp")
    assert hasattr(mod, "main")
