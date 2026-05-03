"""Per-tool authorization decorator — defense-in-depth over wrapper filter.

The team-agent mcp-wrapper filters tools at the server level (tools/list +
tools/call). The decorator tested here is a belt-and-braces layer: even if a
client bypasses the wrapper and talks to the MCP server directly via stdio,
@require_role(...) enforces the same role→tool mapping.

Identity source: env var AGENT_ROLE (matches the wrapper's env name). Missing
or unknown role → "unknown" → only tools explicitly tagged as public pass.
"""

import os
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_auth():
    """Re-import auth so ROLES_YAML_PATH overrides take effect."""
    import importlib
    from nuzantara_mcp import auth  # type: ignore[import-not-found]
    importlib.reload(auth)
    return auth


@pytest.fixture
def clear_agent_role():
    """Ensure tests start without AGENT_ROLE leaked from the caller."""
    original = os.environ.pop("AGENT_ROLE", None)
    yield
    if original is not None:
        os.environ["AGENT_ROLE"] = original


# ---------------------------------------------------------------------------
# MCPAccessDenied exception surface
# ---------------------------------------------------------------------------

def test_mcp_access_denied_is_exception() -> None:
    auth = _import_auth()
    assert issubclass(auth.MCPAccessDenied, Exception)


def test_mcp_access_denied_message_mentions_tool_and_role() -> None:
    auth = _import_auth()
    exc = auth.MCPAccessDenied(tool="ask_legal", required=("visa_specialist",), caller="unknown")
    msg = str(exc)
    assert "ask_legal" in msg
    assert "visa_specialist" in msg
    assert "unknown" in msg


# ---------------------------------------------------------------------------
# get_caller_role — identity resolution
# ---------------------------------------------------------------------------

def test_get_caller_role_reads_agent_role_env(clear_agent_role) -> None:
    auth = _import_auth()
    os.environ["AGENT_ROLE"] = "visa_specialist"
    assert auth.get_caller_role() == "visa_specialist"


def test_get_caller_role_defaults_to_unknown(clear_agent_role) -> None:
    auth = _import_auth()
    assert auth.get_caller_role() == "unknown"


def test_get_caller_role_empty_string_is_unknown(clear_agent_role) -> None:
    auth = _import_auth()
    os.environ["AGENT_ROLE"] = ""
    assert auth.get_caller_role() == "unknown"


# ---------------------------------------------------------------------------
# @require_role decorator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_role_allows_matching_caller(clear_agent_role) -> None:
    auth = _import_auth()
    os.environ["AGENT_ROLE"] = "visa_specialist"

    @auth.require_role("visa_specialist", "admin")
    async def protected_tool(x: int) -> int:
        return x * 2

    assert await protected_tool(3) == 6


@pytest.mark.asyncio
async def test_require_role_admin_always_passes(clear_agent_role) -> None:
    """Admin bypasses per-tool restrictions (matches roles.yaml '*' wildcard)."""
    auth = _import_auth()
    os.environ["AGENT_ROLE"] = "admin"

    @auth.require_role("visa_specialist")  # admin not explicitly listed
    async def protected_tool() -> str:
        return "ok"

    assert await protected_tool() == "ok"


@pytest.mark.asyncio
async def test_require_role_denies_wrong_role(clear_agent_role) -> None:
    auth = _import_auth()
    os.environ["AGENT_ROLE"] = "tax_consultant"

    @auth.require_role("visa_specialist")
    async def visa_only() -> str:
        return "secret"

    with pytest.raises(auth.MCPAccessDenied) as exc_info:
        await visa_only()
    assert "visa_only" in str(exc_info.value)
    assert "tax_consultant" in str(exc_info.value)


@pytest.mark.asyncio
async def test_require_role_unknown_caller_denied(clear_agent_role) -> None:
    auth = _import_auth()
    # No AGENT_ROLE env set

    @auth.require_role("visa_specialist", "tax_consultant")
    async def protected() -> str:
        return "secret"

    with pytest.raises(auth.MCPAccessDenied):
        await protected()


@pytest.mark.asyncio
async def test_require_role_preserves_function_metadata(clear_agent_role) -> None:
    """functools.wraps must preserve __name__ and __doc__ (fastmcp reads them)."""
    auth = _import_auth()

    @auth.require_role("visa_specialist")
    async def original_name() -> str:
        """Original docstring."""
        return "ok"

    assert original_name.__name__ == "original_name"
    assert original_name.__doc__ == "Original docstring."


@pytest.mark.asyncio
async def test_require_role_no_allowed_roles_denies_everyone(clear_agent_role) -> None:
    """Empty role list is a configuration error but must fail closed."""
    auth = _import_auth()
    os.environ["AGENT_ROLE"] = "admin"

    @auth.require_role()  # no allowed roles
    async def broken() -> str:
        return "ok"

    with pytest.raises(auth.MCPAccessDenied):
        await broken()


# ---------------------------------------------------------------------------
# @public_tool marker — explicit opt-in for unknown callers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_tool_works_without_role(clear_agent_role) -> None:
    """Tools explicitly marked @public_tool accept unknown callers."""
    auth = _import_auth()

    @auth.public_tool
    async def health_check() -> str:
        return "ok"

    assert await health_check() == "ok"


@pytest.mark.asyncio
async def test_public_tool_still_callable_with_role(clear_agent_role) -> None:
    auth = _import_auth()
    os.environ["AGENT_ROLE"] = "visa_specialist"

    @auth.public_tool
    async def health_check() -> str:
        return "ok"

    assert await health_check() == "ok"


# ---------------------------------------------------------------------------
# Audit logging — denied access is logged (Legge 2: no data in log)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_denied_access_is_logged_without_payload(clear_agent_role, caplog) -> None:
    """Denied calls log tool+caller role but NEVER the payload (OSINT blindato)."""
    auth = _import_auth()
    os.environ["AGENT_ROLE"] = "tax_consultant"

    @auth.require_role("visa_specialist")
    async def sensitive(secret_arg: str) -> str:
        return secret_arg

    import logging
    with caplog.at_level(logging.WARNING, logger="nuzantara-mcp.auth"):
        with pytest.raises(auth.MCPAccessDenied):
            await sensitive("CLIENT_PII_DONT_LOG_ME")

    assert any("sensitive" in r.message for r in caplog.records)
    assert any("tax_consultant" in r.message for r in caplog.records)
    # Legge 2: arguments never leak into logs
    for rec in caplog.records:
        assert "CLIENT_PII_DONT_LOG_ME" not in rec.message


# ---------------------------------------------------------------------------
# ROLE_TAXONOMY — loaded from roles.yaml (source of truth)
# ---------------------------------------------------------------------------

def test_role_taxonomy_loaded_from_yaml() -> None:
    auth = _import_auth()
    taxonomy = auth.ROLE_TAXONOMY
    assert "visa_specialist" in taxonomy
    assert "tax_consultant" in taxonomy
    assert "company_setup" in taxonomy
    assert "admin" in taxonomy
    # Spot-check a few tools per role (from apps/team-agent/mcp-wrapper/config/roles.yaml)
    assert "get_visa_details" in taxonomy["visa_specialist"]
    assert "ask_legal" in taxonomy["tax_consultant"]
    assert "search_kbli" in taxonomy["company_setup"]


def test_roles_for_helper() -> None:
    """roles_for(tool_name) returns the list of roles that may call it."""
    auth = _import_auth()
    roles = auth.roles_for("ask_legal")
    assert "visa_specialist" in roles
    assert "tax_consultant" in roles
    assert "company_setup" in roles
    # admin has wildcard but is always allowed, so it may or may not be listed explicitly;
    # the key invariant is that at least the three specialist roles surface.


def test_roles_for_unknown_tool_returns_empty() -> None:
    auth = _import_auth()
    assert auth.roles_for("nonexistent_tool_xyz") == []
