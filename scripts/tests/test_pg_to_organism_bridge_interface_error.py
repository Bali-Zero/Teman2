"""W32 (2026-05-23) — verify pg-to-organism-bridge catches asyncpg.InterfaceError.

Background: during W27 live production test 2026-05-23 04:42-05:25 WITA, the
pg-bridge daemon process kept running (PID 2409, state=running, heartbeat
ticking) but had ZERO open TCP connections to PG. Empirical signature
identical to W29 watchdog burn: `asyncpg.InterfaceError` is a SIBLING of
`PostgresError`, not a subclass. When pg-proxy hiccups and the keep-alive
`SELECT 1` raises InterfaceError, the original except tuple did not catch
it → exception escaped → listener task crashed silently → 50min of
NOTIFY events dropped.

This test reads the source file textually and asserts:
1. The except tuple now lists `asyncpg.InterfaceError` explicitly
2. The W29 sibling reasoning is preserved in a comment (so a future
   linter/auto-format pass can't strip the "why" and reintroduce the bug)
"""
from __future__ import annotations

from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "pg-to-organism-bridge.py"


def test_script_exists():
    assert SCRIPT.is_file(), f"missing {SCRIPT}"


def test_except_tuple_includes_interface_error():
    """The keep-alive try/except in _run_listener must include
    asyncpg.InterfaceError or the W27 silent-death pattern recurs.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    assert "asyncpg.InterfaceError" in src, (
        "asyncpg.InterfaceError not in source — pg-bridge will silently die "
        "on pg-proxy hiccup (W27 / W29 pattern)"
    )


def test_w29_sibling_reasoning_comment_present():
    """The fix is fragile: a future contributor might reformat the except
    tuple alphabetically and not realize InterfaceError is a SIBLING not a
    subclass of PostgresError. The inline comment preserves the rationale.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    # Look for any explanation citing "sibling" / "NOT subclass" near the
    # InterfaceError line.
    assert any(
        marker in src
        for marker in (
            "sibling of PostgresError",
            "NOT subclass",
            "W32:",
            "W29:",
        )
    ), (
        "no inline 'sibling/NOT subclass' rationale near InterfaceError — "
        "a refactor could strip the entry without realizing why it's load-bearing"
    )


def test_channels_includes_cell_pulse_sustained_red():
    """W27 path A wired this channel — regression guard so a future
    cleanup doesn't accidentally drop it from CHANNELS.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    assert "cell_pulse_sustained_red" in src


def test_warning_channels_classifies_sustained_red():
    """sustained_red should be elevated to warning severity, not info."""
    src = SCRIPT.read_text(encoding="utf-8")
    # The line is: WARNING_CHANNELS = {"compliance_alert", "federation_alert", "cell_pulse_sustained_red"}
    assert "WARNING_CHANNELS" in src
    # Find the WARNING_CHANNELS block and verify membership
    import re
    m = re.search(r"WARNING_CHANNELS\s*=\s*\{([^}]+)\}", src)
    assert m, "could not find WARNING_CHANNELS literal"
    members = m.group(1)
    assert "cell_pulse_sustained_red" in members, (
        "cell_pulse_sustained_red must be in WARNING_CHANNELS (W27 path A) so "
        "downstream organism rules can match on severity=warning"
    )
