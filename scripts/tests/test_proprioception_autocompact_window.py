"""proprioception.py's `autocompact_window` receptor (2026-09-18).

THE M5 INCIDENT this receptor exists to catch: ~/.claude/settings.json carried
`autoCompactWindow` BELOW the context guard's trip point (window × 0.40 = 400K
on the 1M seat). The CLI compacted every long session in place before the guard
could write the handoff and jump, and what looked like a Claude Code regression
was this one key. Decided the same day: jump first at 400K, auto-compact as the
backstop at 500K — the registry's `expected` pins it.

Each test names the mutation it would survive: a probe that hard-codes the 1M
window, ignores the env override, reads only settings.json, or never compares
the value to the trip is caught by one case below.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)  # type: ignore[union-attr]

REPO_ROOT = Path(__file__).resolve().parents[2]


def _root(tmp_path: Path, *, guard: bool = True, threshold: str = "0.40") -> Path:
    root = tmp_path / "root"
    hooks = root / "infra" / "claude-hooks"
    hooks.mkdir(parents=True, exist_ok=True)   # a test may _run twice in one tmp_path
    if guard:
        (hooks / "context_window_guard.py").write_text(
            f"GRACE_TURNS = 30\nDEFAULT_WINDOW = 200_000\nLARGE_WINDOW = 1_000_000\n"
            f"DEFAULT_THRESHOLD = {threshold}\n")
    return root


def _profile(tmp_path: Path, settings: dict | None, local: dict | None = None, raw: str | None = None) -> Path:
    pdir = tmp_path / "prof"
    pdir.mkdir(exist_ok=True)
    if raw is not None:
        (pdir / "settings.json").write_text(raw)
    elif settings is not None:
        (pdir / "settings.json").write_text(json.dumps(settings))
    if local is not None:
        (pdir / "settings.local.json").write_text(json.dumps(local))
    return pdir


def _run(tmp_path: Path, settings, *, local=None, raw=None, expected=500000, guard=True, threshold="0.40"):
    root = _root(tmp_path, guard=guard, threshold=threshold)
    pdir = _profile(tmp_path, settings, local, raw)
    args = {"profiles": [str(pdir)]}
    if expected is not None:
        args["expected"] = expected
    return prop.probe_autocompact_window(root, args, 5)


ONE_M = {"model": "opus[1m]", "autoCompactWindow": 500000, "env": {"CONTEXT_WINDOW_TOKENS": "1000000"}}


# ------------------------------------------------------------------ guilt

def test_the_fleet_value_above_the_trip_is_reconciled(tmp_path):
    status, n, ev = _run(tmp_path, ONE_M)
    assert (status, n) == (prop.RECONCILED, 0), ev
    assert "500000 > guard trip 400000" in ev[0]


def test_the_m5_incident_value_below_the_trip_is_p1_evidence(tmp_path):
    # mutation survived: a probe that never compares value to trip
    status, n, ev = _run(tmp_path, {**ONE_M, "autoCompactWindow": 300000})
    assert (status, n) == (prop.DIVERGED, 1)
    assert "300000 <= guard trip 400000" in ev[0] and "PRE-EMPTS" in ev[0]


def test_equal_to_the_trip_is_still_below_it(tmp_path):
    status, n, ev = _run(tmp_path, {**ONE_M, "autoCompactWindow": 400000})
    assert (status, n) == (prop.DIVERGED, 1) and "<= guard trip 400000" in ev[0]


def test_absent_key_is_a_finding_only_when_the_fleet_pinned_a_value(tmp_path):
    no_key = {k: v for k, v in ONE_M.items() if k != "autoCompactWindow"}
    status, n, ev = _run(tmp_path, no_key)
    assert (status, n) == (prop.DIVERGED, 1) and "ABSENT" in ev[0] and "500000" in ev[0]
    status, n, ev = _run(tmp_path, no_key, expected=None)
    assert (status, n) == (prop.RECONCILED, 0) and "absent" in ev[0]


def test_above_the_trip_but_off_the_fleet_value_is_a_finding_that_says_the_jump_still_wins(tmp_path):
    status, n, ev = _run(tmp_path, {**ONE_M, "autoCompactWindow": 600000})
    assert (status, n) == (prop.DIVERGED, 1)
    assert "600000 != fleet value 500000" in ev[0] and "jump still comes first" in ev[0]


def test_a_small_window_seat_has_a_small_trip(tmp_path):
    # mutation survived: a probe that hard-codes the 1M window (100000 <= 400000)
    status, n, ev = _run(tmp_path, {"model": "claude-sonnet-5", "autoCompactWindow": 100000}, expected=None)
    assert (status, n) == (prop.RECONCILED, 0), ev
    assert "guard trip 80000 (200000 × 0.40)" in ev[0]


def test_the_env_override_beats_the_model_spelling_as_in_the_guard(tmp_path):
    # mutation survived: a probe that reads the model and ignores CONTEXT_WINDOW_TOKENS
    status, n, ev = _run(tmp_path, {"model": "claude-sonnet-5", "autoCompactWindow": 300000,
                                    "env": {"CONTEXT_WINDOW_TOKENS": "1000000"}}, expected=None)
    assert (status, n) == (prop.DIVERGED, 1) and "1000000 × 0.40" in ev[0]


def test_a_1m_model_without_the_env_is_the_large_window(tmp_path):
    status, n, ev = _run(tmp_path, {"model": "opus[1m]", "autoCompactWindow": 300000}, expected=None)
    assert (status, n) == (prop.DIVERGED, 1) and "guard trip 400000" in ev[0]


def test_settings_local_overlays_settings_key_by_key(tmp_path):
    # mutation survived: a probe that reads only settings.json
    status, n, _ = _run(tmp_path, {**ONE_M, "autoCompactWindow": 300000}, local={"autoCompactWindow": 500000})
    assert (status, n) == (prop.RECONCILED, 0)
    status, n, _ = _run(tmp_path, ONE_M, local={"autoCompactWindow": 300000})
    assert (status, n) == (prop.DIVERGED, 1)


def test_the_threshold_is_read_from_the_guard_source_not_hard_coded(tmp_path):
    # the guard at 0.60 puts the trip at 600K: 500K is now BELOW it
    status, n, ev = _run(tmp_path, ONE_M, threshold="0.60")
    assert (status, n) == (prop.DIVERGED, 1) and "guard trip 600000" in ev[0]


def test_the_real_guard_source_is_readable_by_the_regex():
    thr, small, large = prop._guard_constants(REPO_ROOT)
    assert (thr, small, large) == (0.40, 200_000, 1_000_000)


# ------------------------------------------------------------------ innocence / tri-state

def test_no_guard_source_falls_back_to_the_shipped_constants_never_to_silence(tmp_path):
    status, n, ev = _run(tmp_path, {**ONE_M, "autoCompactWindow": 300000}, guard=False)
    assert (status, n) == (prop.DIVERGED, 1) and "guard trip 400000" in ev[0]


def test_missing_profile_or_settings_file_is_unprobeable_not_reconciled(tmp_path):
    root = _root(tmp_path)
    assert prop.probe_autocompact_window(root, {"profiles": [str(tmp_path / "nope")], "expected": 500000}, 5)[0] == prop.UNPROBEABLE
    (tmp_path / "empty").mkdir()
    assert prop.probe_autocompact_window(root, {"profiles": [str(tmp_path / "empty")], "expected": 500000}, 5)[0] == prop.UNPROBEABLE


def test_unreadable_settings_is_a_finding_not_a_crash(tmp_path):
    status, n, ev = _run(tmp_path, None, raw="{not json")
    assert (status, n) == (prop.DIVERGED, 1) and "unreadable JSON" in ev[0]


def test_a_non_integer_value_is_a_finding(tmp_path):
    status, n, ev = _run(tmp_path, {**ONE_M, "autoCompactWindow": "five hundred k"})
    assert (status, n) == (prop.DIVERGED, 1) and "not an integer" in ev[0]


def test_evidence_never_carries_other_settings_content(tmp_path):
    status, _, ev = _run(tmp_path, {**ONE_M, "hooks": {"PreToolUse": "SECRET-SHAPE"}, "env": {"CONTEXT_WINDOW_TOKENS": "1000000", "TOKEN_X": "hunter2"}})
    assert status == prop.RECONCILED and not any("SECRET-SHAPE" in line or "hunter2" in line for line in ev)


# ------------------------------------------------------------------ registry wiring

def test_registry_entry_is_wired_to_the_builtin_and_pins_the_fleet_value():
    entry = next(e for e in prop.DEFAULT_REGISTRY if e["id"] == "autocompact_window")
    assert entry["type"] == "builtin" and prop.BUILTINS[entry["target"]] is prop.probe_autocompact_window
    assert entry["severity"] == "P1" and entry["args"]["expected"] == 500000
    assert entry["args"]["profiles"] == ["~/.claude"]
    assert "/autocompact 500k" in entry["fix_hint"]
    assert prop.validate_registry(prop.DEFAULT_REGISTRY) == []
