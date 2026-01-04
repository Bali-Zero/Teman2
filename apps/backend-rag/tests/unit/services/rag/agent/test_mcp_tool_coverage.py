import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

module_name = "services.rag.agent.mcp_tool"


def _load_module(monkeypatch, session_result=None, session_error=None, stdio_error=None):
    captured = {}

    class _StdioParams:
        def __init__(self, command, args, env=None):
            self.command = command
            self.args = args
            self.env = env
            captured["params"] = self

    class _Session:
        def __init__(self, read, write):
            self.read = read
            self.write = write
            self.initialized = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def initialize(self):
            self.initialized = True

        async def call_tool(self, tool_name, arguments):
            if session_error:
                raise session_error
            return session_result

    class _StdioCtx:
        async def __aenter__(self):
            if stdio_error:
                raise stdio_error
            return ("read", "write")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def _stdio_client(params):
        captured["stdio_params"] = params
        return _StdioCtx()

    structures_stub = types.SimpleNamespace(BaseTool=object)
    monkeypatch.setitem(sys.modules, "services.rag.agent.structures", structures_stub)

    mcp_stub = types.SimpleNamespace(ClientSession=_Session, StdioServerParameters=_StdioParams)
    monkeypatch.setitem(sys.modules, "mcp", mcp_stub)
    monkeypatch.setitem(sys.modules, "mcp.client", types.SimpleNamespace())
    monkeypatch.setitem(
        sys.modules, "mcp.client.stdio", types.SimpleNamespace(stdio_client=_stdio_client)
    )

    if module_name in sys.modules:
        del sys.modules[module_name]

    module_path = (
        Path(__file__).resolve().parents[5]
        / "backend"
        / "services"
        / "rag"
        / "agent"
        / "mcp_tool.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module, captured


def test_is_mcp_admin(monkeypatch):
    module, _ = _load_module(monkeypatch)
    assert module.is_mcp_admin("zero@balizero.com") is True
    assert module.is_mcp_admin("ZERO@BALIZERO.COM") is True
    assert module.is_mcp_admin("user@example.com") is False
    assert module.is_mcp_admin(None) is False


@pytest.mark.asyncio
async def test_execute_denies_non_admin(monkeypatch):
    module, _ = _load_module(monkeypatch)
    tool = module.MCPSuperTool()

    result = await tool.execute(action="web_search", query="hi", _user_email="user@example.com")

    assert result.startswith("ERROR: This tool is only available for admin users")


@pytest.mark.asyncio
async def test_execute_unknown_action(monkeypatch):
    module, _ = _load_module(monkeypatch)
    tool = module.MCPSuperTool()

    result = await tool.execute(action="unknown", _user_email="zero@balizero.com")

    assert "Unknown action" in result


@pytest.mark.asyncio
async def test_execute_admin_web_search(monkeypatch):
    module, _ = _load_module(monkeypatch)
    tool = module.MCPSuperTool()
    tool._web_search = types.MethodType(AsyncMock(return_value="ok"), tool)

    result = await tool.execute(action="web_search", query="q", _user_email="zero@balizero.com")

    assert result == "ok"


@pytest.mark.asyncio
async def test_call_mcp_missing_server(monkeypatch):
    module, _ = _load_module(monkeypatch)
    tool = module.MCPSuperTool()

    result = await tool._call_mcp("missing", "tool", {})

    assert "not configured" in result


@pytest.mark.asyncio
async def test_call_mcp_success_with_content(monkeypatch):
    content = [types.SimpleNamespace(text="one"), types.SimpleNamespace(text="two")]
    result_obj = types.SimpleNamespace(content=content)
    module, captured = _load_module(monkeypatch, session_result=result_obj)
    tool = module.MCPSuperTool()

    monkeypatch.setenv("BRAVE_API_KEY", "secret")
    result = await tool._call_mcp("brave_search", "brave_web_search", {"query": "q"})

    assert result == "one\ntwo"
    assert captured["params"].env["BRAVE_API_KEY"] == "secret"


@pytest.mark.asyncio
async def test_call_mcp_error(monkeypatch):
    module, _ = _load_module(monkeypatch, stdio_error=RuntimeError("boom"))
    tool = module.MCPSuperTool()

    result = await tool._call_mcp("brave_search", "brave_web_search", {"query": "q"})

    assert result.startswith("ERROR calling MCP: boom")


@pytest.mark.asyncio
async def test_web_search_requires_query(monkeypatch):
    module, _ = _load_module(monkeypatch)
    tool = module.MCPSuperTool()

    result = await tool._web_search("")

    assert result == "ERROR: query is required for web_search"


@pytest.mark.asyncio
async def test_read_write_memory_validation(monkeypatch):
    module, _ = _load_module(monkeypatch)
    tool = module.MCPSuperTool()

    assert await tool._read_file("") == "ERROR: path is required for read_file"
    assert await tool._write_file("", "x") == "ERROR: path and content are required for write_file"
    assert (
        await tool._write_file("file.txt", "")
        == "ERROR: path and content are required for write_file"
    )
    assert (
        await tool._save_memory("", "v")
        == "ERROR: query (key) and content (value) are required for save_memory"
    )
    assert (
        await tool._save_memory("k", "")
        == "ERROR: query (key) and content (value) are required for save_memory"
    )
    assert await tool._recall_memory("") == "ERROR: query (key) is required for recall_memory"


@pytest.mark.asyncio
async def test_action_wrappers(monkeypatch):
    module, _ = _load_module(monkeypatch)
    tool = module.MCPSuperTool()
    tool._call_mcp = AsyncMock(return_value="ok")

    assert await tool._read_file("file.txt") == "Content of file.txt:\nok"
    assert await tool._write_file("file.txt", "data") == "File written to file.txt: ok"
    assert await tool._save_memory("k", "v") == "Memory saved with key 'k': ok"
    assert await tool._recall_memory("k") == "Memory for 'k': ok"
