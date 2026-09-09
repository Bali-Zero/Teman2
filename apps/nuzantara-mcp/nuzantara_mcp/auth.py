"""Per-tool authorization for the Nuzantara MCP server.

Defense-in-depth over the team-agent mcp-wrapper (``apps/team-agent/mcp-wrapper``),
which already filters ``tools/list`` and blocks unauthorized ``tools/call`` at the
JSON-RPC proxy layer. That wrapper is the primary gate — every production client
(OpenClaw, Gemini CLI) is expected to go through it.

This module adds a second, in-process gate so that a client that *bypasses* the
wrapper (debug, dev, direct stdio) is still constrained to the same role/tool
mapping. Think of it as the lock on the door behind the receptionist: neither
alone is sufficient, but together they fail closed on wrapper misconfiguration
or a missing ``AGENT_ROLE`` env var.

Identity source:
    The wrapper forwards its ``AGENT_ROLE`` via subprocess env, so we read the
    same variable. A missing or empty value is treated as the ``unknown`` role,
    which only has access to tools explicitly decorated with :func:`public_tool`.

Source of truth for role → tools mapping:
    ``apps/team-agent/mcp-wrapper/config/roles.yaml``. The taxonomy is loaded
    once at import time. The wrapper already validates the mapping at runtime;
    the decorators here reuse the same file so drift is impossible.

Legge 2 (OSINT blindato):
    Denied calls log the tool name and caller role but never the arguments —
    the payload may contain OSINT/PII. Allowed calls are not logged by this
    module (the wrapper already emits an audit record).

Legge 4 (Graceful degradation):
    If ``roles.yaml`` cannot be loaded, the taxonomy is empty and every
    non-``admin``, non-``public_tool`` call is denied. The MCP server still
    starts — individual tools fail closed rather than taking down the organ.
"""

from __future__ import annotations

import logging
import os
from functools import wraps
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger("nuzantara-mcp.auth")

_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])

UNKNOWN_ROLE = "unknown"
ADMIN_ROLE = "admin"
AGENT_ROLE_ENV = "AGENT_ROLE"

# Override point for tests and alternative deployments.
ROLES_YAML_PATH_ENV = "NUZANTARA_MCP_ROLES_YAML"

_DEFAULT_ROLES_YAML = (
    Path(__file__).resolve().parents[2]
    / "team-agent"
    / "mcp-wrapper"
    / "config"
    / "roles.yaml"
)


class MCPAccessDenied(Exception):
    """Raised when a caller's role is not in the tool's allowed set.

    The message includes the tool name, the allowed roles, and the caller role
    so an MCP client can present a meaningful error without having to parse a
    free-form string. Arguments passed to the tool are deliberately omitted —
    they may contain OSINT or PII (Legge 2).
    """

    def __init__(
        self,
        tool: str,
        required: tuple[str, ...],
        caller: str,
    ) -> None:
        required_display = ", ".join(required) if required else "(none — config error)"
        super().__init__(
            f"Tool '{tool}' requires role in [{required_display}]; caller has '{caller}'."
        )
        self.tool = tool
        self.required = required
        self.caller = caller


def _load_role_taxonomy() -> dict[str, list[str]]:
    """Load the role → tool-list mapping from roles.yaml.

    Returns an empty dict on any failure (file missing, YAML parse error,
    unexpected shape). The server boots either way; individual decorated
    tools fail closed when the taxonomy is empty.
    """
    path_str = os.getenv(ROLES_YAML_PATH_ENV) or str(_DEFAULT_ROLES_YAML)
    path = Path(path_str)
    if not path.is_file():
        logger.warning("roles.yaml not found at %s — taxonomy empty, per-tool auth fails closed", path)
        return {}

    # roles.yaml decides which tools a role may call, so it is loaded STRICTLY.
    # PyYAML's safe_load lets a duplicate top-level key win in silence, and `roles:`
    # is a mapping keyed by role name: measured 2026-09-05 on a scratch copy of the
    # shipped file, appending five lines that repeat an existing role with
    # `tools: ["*"]` replaced that role's 11 named tools with a wildcard, and the
    # diff read as an appended block. Loaded by PATH because scripts/lib is not an
    # importable package — the same assumption about repo layout that
    # _DEFAULT_ROLES_YAML above already makes by reaching into a sibling app tree.
    # There is deliberately no fallback to yaml.safe_load: silently downgrading to
    # the permissive loader when the strict one is absent would restore the defect.
    try:
        import importlib.util

        # ONE canonical module name, shared with the sibling reader in
        # apps/team-agent/mcp-wrapper/permissions.py: loading the same file twice under
        # two names produces two distinct StrictYAMLError CLASSES, so an `except` in one
        # caller would not catch the error raised through the other.
        strict_path = Path(__file__).resolve().parents[3] / "scripts" / "lib" / "yaml_strict.py"
        yaml_strict = sys.modules.get("nuzantara_yaml_strict")
        if yaml_strict is None:
            spec = importlib.util.spec_from_file_location("nuzantara_yaml_strict", strict_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"not loadable: {strict_path}")
            yaml_strict = importlib.util.module_from_spec(spec)
            sys.modules["nuzantara_yaml_strict"] = yaml_strict
            spec.loader.exec_module(yaml_strict)
    except Exception as exc:  # noqa: BLE001 — missing loader must not boot a permissive server
        logger.warning(
            "strict policy loader unavailable (%s) — taxonomy empty, per-tool auth fails closed",
            exc,
        )
        return {}

    try:
        data: Any = yaml_strict.load_policy(path)
    except Exception as exc:  # noqa: BLE001 — we deliberately catch all parser errors
        # This branch now also fires on an AMBIGUOUS document, not only an unparseable
        # one. Logged at WARNING with the loader's own message, which names the
        # duplicate key and its line: an escalation attempt that fails closed and
        # leaves no legible trace is only half a control.
        logger.warning("Refused to load roles.yaml (%s) — taxonomy empty", exc)
        return {}

    roles = (data or {}).get("roles", {}) if isinstance(data, dict) else {}
    taxonomy: dict[str, list[str]] = {}
    for role, info in roles.items():
        if not isinstance(info, dict):
            continue
        tools = info.get("tools") or []
        if isinstance(tools, list):
            taxonomy[role] = [str(t) for t in tools]
    return taxonomy


ROLE_TAXONOMY: dict[str, list[str]] = _load_role_taxonomy()


def get_caller_role() -> str:
    """Return the AGENT_ROLE env var or ``unknown`` if absent/empty."""
    value = os.getenv(AGENT_ROLE_ENV) or ""
    return value if value else UNKNOWN_ROLE


def roles_for(tool_name: str) -> list[str]:
    """Return the non-wildcard roles that are allowed to call ``tool_name``.

    Used by :func:`require_role` call sites as a sanity-check and by audit
    scripts. ``admin`` is not listed explicitly because its entry in
    ``roles.yaml`` is the ``*`` wildcard — it is always allowed regardless.
    """
    matches: list[str] = []
    for role, tools in ROLE_TAXONOMY.items():
        if role == ADMIN_ROLE:
            continue
        if tool_name in tools:
            matches.append(role)
    return matches


def require_role(*allowed_roles: str) -> Callable[[_F], _F]:
    """Decorator that restricts an async MCP tool to the given roles.

    ``admin`` is always allowed (wildcard in roles.yaml). Callers without an
    ``AGENT_ROLE`` env var, or with one not in ``allowed_roles``, get
    :class:`MCPAccessDenied`.

    The decorator preserves ``__name__`` and ``__doc__`` (fastmcp reads them
    to build the tool schema).
    """

    def decorator(fn: _F) -> _F:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            caller = get_caller_role()
            # Empty allowed_roles is a developer error — fail closed even for admin.
            if allowed_roles:
                if caller == ADMIN_ROLE:
                    return await fn(*args, **kwargs)
                if caller in allowed_roles:
                    return await fn(*args, **kwargs)
            # Fail closed. Log tool + role only — never the payload (Legge 2).
            logger.warning(
                "mcp-auth DENIED tool=%s caller=%s required=%s",
                fn.__name__,
                caller,
                allowed_roles or "()",
            )
            raise MCPAccessDenied(
                tool=fn.__name__,
                required=tuple(allowed_roles),
                caller=caller,
            )

        return wrapper  # type: ignore[return-value]

    return decorator


def public_tool(fn: _F) -> _F:
    """Mark a tool as callable regardless of role.

    Reserved for genuinely public endpoints (health checks, version info).
    Explicit opt-in — the default posture is deny for ``unknown``.
    """

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        return await fn(*args, **kwargs)

    setattr(wrapper, "_nuzantara_public_tool", True)
    return wrapper  # type: ignore[return-value]


__all__ = [
    "ADMIN_ROLE",
    "AGENT_ROLE_ENV",
    "MCPAccessDenied",
    "ROLE_TAXONOMY",
    "UNKNOWN_ROLE",
    "get_caller_role",
    "public_tool",
    "require_role",
    "roles_for",
]
