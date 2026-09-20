#!/usr/bin/env python3
"""The fastmcp major is bounded, and this is what keeps it bounded.

fastmcp 4.0.0 implements MCP spec 2026-07-28, which drops the `initialize`
handshake and `Mcp-Session-Id`, requires a new `server/discover`, and replaces
server-push with Multi Round-Trip. Under `fastmcp>=2.0.0` an ordinary
`pip install -U` crossed that protocol boundary with nothing in any diff to
show it.

The bound is not here because the migration is large — this server is stdio and
uses none of the deprecated primitives. It is here so that crossing a protocol
boundary is a decision that runs tests, not a side effect of an unrelated
upgrade. Raising it is a migration, not a version bump.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _constraint(pkg: str) -> str:
    deps = tomllib.loads(_PYPROJECT.read_text())["project"]["dependencies"]
    match = [d for d in deps if re.match(rf"^{re.escape(pkg)}\b", d)]
    assert len(match) == 1, f"expected exactly one {pkg} dependency, found {match}"
    return match[0]


def test_fastmcp_has_an_upper_bound():
    c = _constraint("fastmcp")
    assert "<" in c, (
        f"fastmcp constraint is {c!r}, with no upper bound. fastmcp 4.x speaks MCP "
        "2026-07-28, a different protocol: `pip install -U` would cross that line "
        "silently. Bound the major, and raise it deliberately with the migration."
    )


def test_the_installed_version_satisfies_the_declared_bound():
    """A bound nothing is checked against is a comment.

    Skipped, not failed, where fastmcp is absent: this file is reachable from
    environments that do not install it, and a red for "package missing" is a red
    for something other than the defect this test looks for.
    """
    import pytest
    from importlib.metadata import PackageNotFoundError, version
    try:
        installed = version("fastmcp")
    except PackageNotFoundError:
        pytest.skip("fastmcp not installed in this environment — the bound itself is asserted above")
    upper = re.search(r"<\s*(\d+)", _constraint("fastmcp"))
    assert upper, "upper bound present but unparseable"
    assert int(installed.split(".")[0]) < int(upper.group(1)), (
        f"fastmcp {installed} is installed but the declared bound is "
        f"<{upper.group(1)}.0 — the environment already crossed the boundary the "
        "constraint claims to hold."
    )


def test_the_reason_travels_with_the_bound():
    src = _PYPROJECT.read_text()
    head = src[: src.index('"fastmcp')]
    assert "2026-07-28" in head, (
        "the bound must carry the protocol version it is protecting, or the next "
        "person reads it as stale conservatism and widens it"
    )
