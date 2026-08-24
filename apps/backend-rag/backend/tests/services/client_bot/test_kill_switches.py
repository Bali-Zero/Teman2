"""Tests for the F11/B7 kill-switch registry (`services/client_bot/kill_switches.py`).

The team lead's framing: "A kill switch nobody can find at 3am is not a
kill switch." Two things are checked here: the registry itself is
internally consistent (no duplicate names, every plane is a real F11
plane), and the human-facing doc
(`docs/plans/2026-08-25-due-bot-live/ops/KILL-SWITCHES.md`) cannot drift
from the registry — a switch documented but not registered, or
registered but not documented, is exactly the class of defect this file
exists to catch (superscar family #2, "esiste != armato", applied to
documentation about switches rather than to the switches themselves).
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.services.client_bot.kill_switches import (
    KILL_SWITCHES,
    KillSwitchStatus,
    TripwirePlane,
    by_env_var,
    by_plane,
)

_DOC_PATH = (
    Path(__file__).resolve().parents[6]
    / "docs"
    / "plans"
    / "2026-08-25-due-bot-live"
    / "ops"
    / "KILL-SWITCHES.md"
)
# ENV_VAR-shaped tokens: uppercase, digits, underscores, at least one underscore.
_ENV_VAR_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9<>a-z]+)+\b")


def test_registry_is_non_empty() -> None:
    assert len(KILL_SWITCHES) >= 10


def test_no_duplicate_env_vars() -> None:
    names = [k.env_var for k in KILL_SWITCHES]
    assert len(names) == len(set(names)), "duplicate env_var in KILL_SWITCHES"


def test_every_switch_covers_a_real_f11_plane() -> None:
    for switch in KILL_SWITCHES:
        assert isinstance(switch.plane, TripwirePlane)


def test_all_five_f11_planes_have_at_least_one_switch() -> None:
    for plane in TripwirePlane:
        assert by_plane(plane), f"plane {plane} has no registered kill switch"


def test_by_env_var_round_trips() -> None:
    for switch in KILL_SWITCHES:
        assert by_env_var(switch.env_var) is switch
    assert by_env_var("NOT_A_REAL_SWITCH") is None


def test_default_dark_is_true_unless_runtime_latched() -> None:
    # Every operator-set flag must default OFF ("everything ships dark").
    # The one exception is a runtime-latched breaker state (not an operator
    # env var at all) — those are named `status=WIRED` with a scope that
    # says "runtime-latched", never an operator-facing on/off default.
    for switch in KILL_SWITCHES:
        if switch.default_dark:
            continue
        assert "runtime-latched" in switch.effect_when_off or "N/A" in switch.effect_when_off, (
            f"{switch.env_var} defaults to ON but is not documented as a "
            "runtime-latched exception"
        )


def test_markdown_doc_matches_registry() -> None:
    assert _DOC_PATH.exists(), f"missing {_DOC_PATH}"
    doc_text = _DOC_PATH.read_text(encoding="utf-8")

    registered = {k.env_var for k in KILL_SWITCHES}
    for env_var in registered:
        assert env_var in doc_text, (
            f"{env_var} is registered in kill_switches.py but does not appear "
            f"verbatim in {_DOC_PATH.name} — a switch nobody can find at 3am "
            "is not a kill switch."
        )

    # Reverse direction: every ENV_VAR-shaped token the doc names as a flag
    # (heuristically: appears immediately followed by `=` — the doc's own
    # convention for showing a flag's default) must be a registered switch,
    # so the doc cannot invent a flag the registry never agreed to.
    documented_flags = set(re.findall(r"(" + _ENV_VAR_TOKEN_RE.pattern + r")=", doc_text))
    unregistered = documented_flags - registered
    assert not unregistered, (
        f"KILL-SWITCHES.md documents flags never registered in "
        f"kill_switches.py: {sorted(unregistered)}"
    )


def test_wired_status_is_a_closed_vocabulary() -> None:
    for switch in KILL_SWITCHES:
        assert switch.status in (KillSwitchStatus.WIRED, KillSwitchStatus.PLANNED)
