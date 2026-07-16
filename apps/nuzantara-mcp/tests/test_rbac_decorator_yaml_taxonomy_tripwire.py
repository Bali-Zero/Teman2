"""RBAC decorator <-> roles.yaml consistency tripwire.

PENDING-ARMS ledger (opened 2026-07-12): ``require_role()`` checks hardcoded
string-literal roles per call-site and never reads ``roles.yaml`` at runtime.
Exact-match was verified by hand for 2 call-sites (crm.py:231, compliance.py:83)
but nothing caught future divergence in either direction — a call-site could
drift from the YAML taxonomy (over-permissive or under-permissive) and no test
would notice.

This test extracts every ``@require_role(...)`` decorator literally present in
``nuzantara_mcp/tools/*.py`` (via AST, so it can't be fooled by a stale grep)
and asserts its role set matches ``auth.roles_for(tool_name)`` for every
call-site in the package — not just the 2 spot-checked in the ledger.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from nuzantara_mcp import auth

TOOLS_DIR = Path(__file__).resolve().parents[1] / "nuzantara_mcp" / "tools"

# admin is a wildcard in roles.yaml ("*") — require_role() always lets admin
# through regardless of whether "admin" is spelled out in the decorator args,
# and roles_for() deliberately excludes admin from its per-tool return value
# (see auth.py docstring). Strip it before comparing so it never causes a
# false-positive divergence.
_IMPLICIT_ADMIN = "admin"


def _extract_require_role_call_sites(source: str) -> dict[str, set[str]]:
    """Return {function_name: {literal role args}} for every @require_role(...)
    decorator found in ``source``, minus the implicit "admin" wildcard.

    Raises ValueError if a decorator argument isn't a plain string literal —
    a non-literal arg would silently defeat this tripwire, so treat it as a
    hard failure rather than skipping it.
    """
    tree = ast.parse(source)
    found: dict[str, set[str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name)
                    and dec.func.id == "require_role"):
                continue
            roles: set[str] = set()
            for arg in dec.args:
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    raise ValueError(
                        f"non-literal @require_role arg on {node.name}: {ast.dump(arg)}"
                    )
                roles.add(arg.value)
            found[node.name] = roles - {_IMPLICIT_ADMIN}

    return found


def _find_divergences(
    call_sites: dict[str, set[str]], roles_for
) -> list[str]:
    """Compare each call-site's decorator roles against roles_for(tool).

    Returns a list of human-readable mismatch descriptions (empty = in sync).
    """
    mismatches = []
    for tool_name, decorator_roles in call_sites.items():
        yaml_roles = set(roles_for(tool_name))
        if decorator_roles != yaml_roles:
            mismatches.append(
                f"{tool_name}: decorator={sorted(decorator_roles)} "
                f"yaml={sorted(yaml_roles)}"
            )
    return mismatches


# ---------------------------------------------------------------------------
# Synthetic drift — guilt test (proves the tripwire actually catches drift)
# ---------------------------------------------------------------------------


def test_synthetic_divergence_is_detected() -> None:
    """A decorator role set that doesn't match the YAML taxonomy must be flagged."""
    fake_source = textwrap.dedent(
        """
        from nuzantara_mcp.auth import require_role

        def register(mcp, _call, _call_safe):
            @mcp.tool()
            @require_role("tax_consultant")
            async def drifted_tool():
                return await _call("/api/whatever")
        """
    )
    call_sites = _extract_require_role_call_sites(fake_source)
    assert call_sites == {"drifted_tool": {"tax_consultant"}}

    # roles.yaml (simulated) actually grants a DIFFERENT role to this tool —
    # this is the divergence the real production bug would look like.
    fake_roles_for = lambda tool_name: ["visa_specialist"] if tool_name == "drifted_tool" else []

    mismatches = _find_divergences(call_sites, fake_roles_for)
    assert mismatches == ["drifted_tool: decorator=['tax_consultant'] yaml=['visa_specialist']"]


def test_synthetic_agreement_is_not_flagged() -> None:
    """Innocence companion: a decorator that DOES match the YAML must pass clean."""
    fake_source = textwrap.dedent(
        """
        from nuzantara_mcp.auth import require_role

        def register(mcp, _call, _call_safe):
            @mcp.tool()
            @require_role("tax_consultant")
            async def in_sync_tool():
                return await _call("/api/whatever")
        """
    )
    call_sites = _extract_require_role_call_sites(fake_source)
    fake_roles_for = lambda tool_name: ["tax_consultant"] if tool_name == "in_sync_tool" else []

    assert _find_divergences(call_sites, fake_roles_for) == []


def test_admin_in_decorator_args_is_stripped_before_comparison() -> None:
    """admin is a YAML wildcard ("*"), never enumerated per-tool by roles_for —
    a decorator spelling it out explicitly must not cause a false divergence.
    """
    fake_source = textwrap.dedent(
        """
        from nuzantara_mcp.auth import require_role

        def register(mcp, _call, _call_safe):
            @mcp.tool()
            @require_role("admin", "tax_consultant")
            async def admin_plus_tax():
                return await _call("/api/whatever")
        """
    )
    call_sites = _extract_require_role_call_sites(fake_source)
    assert call_sites == {"admin_plus_tax": {"tax_consultant"}}


def test_non_literal_decorator_arg_raises_instead_of_silently_passing() -> None:
    """A non-string-literal arg (e.g. a variable) would defeat this AST-based
    tripwire silently — must raise instead of being skipped.
    """
    fake_source = textwrap.dedent(
        """
        from nuzantara_mcp.auth import require_role

        SOME_ROLE = "tax_consultant"

        def register(mcp, _call, _call_safe):
            @mcp.tool()
            @require_role(SOME_ROLE)
            async def indirect_role_tool():
                return await _call("/api/whatever")
        """
    )
    with pytest.raises(ValueError):
        _extract_require_role_call_sites(fake_source)


# ---------------------------------------------------------------------------
# Real codebase — every @require_role(...) call-site in nuzantara_mcp/tools/
# ---------------------------------------------------------------------------


def test_all_require_role_call_sites_match_roles_yaml() -> None:
    """The real tripwire: every decorated tool in the codebase, not just the
    2 spot-checked in the ledger (crm.py:231, compliance.py:83).
    """
    py_files = sorted(TOOLS_DIR.glob("*.py"))
    assert py_files, f"no tool files found under {TOOLS_DIR}"

    all_call_sites: dict[str, set[str]] = {}
    for path in py_files:
        all_call_sites.update(_extract_require_role_call_sites(path.read_text()))

    # Sanity: this repo has 40+ decorated call-sites as of 2026-07-12 audit —
    # if extraction finds far fewer, the AST walk itself is broken.
    assert len(all_call_sites) >= 30, (
        f"only found {len(all_call_sites)} @require_role call-sites — "
        "extraction may be broken, not the codebase being clean"
    )

    mismatches = _find_divergences(all_call_sites, auth.roles_for)
    assert mismatches == [], "decorator/YAML drift found:\n" + "\n".join(mismatches)
