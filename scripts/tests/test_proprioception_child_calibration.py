#!/usr/bin/env python3
"""Guilt + innocence for `probe_child_calibration` (scripts/proprioception.py).

Every case builds a synthetic root carrying the REAL child_context.py (never a
copy) plus a synthetic profile — never this machine's real `~/.claude`
(superscar #1: a test on real state passes/fails for the wrong reasons).
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve()
_SPEC = importlib.util.spec_from_file_location("proprioception", _HERE.parents[1] / "proprioception.py")
assert _SPEC and _SPEC.loader
pp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pp)
_CC_SOURCE = (_HERE.parents[2] / "infra" / "claude-hooks" / "child_context.py").read_text()

def _scope(root: Path, profile: Path) -> str:
    """Ground-truth scope for fixtures — the real function, not a guess."""
    old = os.environ.get("CLAUDE_CONFIG_DIR")
    os.environ["CLAUDE_CONFIG_DIR"] = str(profile)
    try:
        s = importlib.util.spec_from_file_location("_cc_fixture", root / "infra" / "claude-hooks" / "child_context.py")
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        return m.scope(str(root))
    finally:
        (os.environ.pop("CLAUDE_CONFIG_DIR", None) if old is None
         else os.environ.__setitem__("CLAUDE_CONFIG_DIR", old))

@contextlib.contextmanager
def _case(settings: dict | None = None):
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        root = tmp / "repo"
        (root / "infra" / "claude-hooks").mkdir(parents=True)
        (root / "infra" / "claude-hooks" / "child_context.py").write_text(_CC_SOURCE)
        prof = tmp / "profile"
        prof.mkdir()
        if settings is not None:
            (prof / "settings.json").write_text(json.dumps(settings))
        yield root, prof

def _record(profile: Path, model: str, version: str, scope_val: str,
            window: int = 200000, age: float = 3600.0, raw: str | None = None) -> None:
    capdir = profile / "state" / "child-context-capacities"
    capdir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps([model, version, scope_val]).encode()).hexdigest()
    body = raw if raw is not None else json.dumps({
        "model": model, "version": version, "window": window, "scope": scope_val,
        "observed_at": time.time() - age, "source": "test", "session_id": "s"})
    (capdir / f"{key}.json").write_text(body)

def _run(root: Path, profile: Path, models: list[str], version: str | None = "9.9.9"):
    orig = pp._cc_current_version
    pp._cc_current_version = lambda bound: version
    try:
        return pp.probe_child_calibration(root, {"models": models, "profiles": [str(profile)]}, 15)
    finally:
        pp._cc_current_version = orig

def test_valid_fresh_matching_record_in_range():
    with _case() as (root, prof):
        _record(prof, "claude-sonnet-5", "9.9.9", _scope(root, prof))
        status, n, ev = _run(root, prof, ["claude-sonnet-5"])
        assert status == pp.RECONCILED and n == 0 and any(e.endswith(": VALID") for e in ev), (status, n, ev)

def test_missing_configured_model_has_no_record():
    with _case() as (root, prof):
        status, n, ev = _run(root, prof, ["claude-opus-5"])
        assert status == pp.DIVERGED and n == 1 and any(e.endswith(": MISSING") for e in ev), ev

def test_expired_older_than_ttl():
    with _case() as (root, prof):
        _record(prof, "claude-sonnet-5", "9.9.9", _scope(root, prof), age=7 * 86400 + 100)
        _, n, ev = _run(root, prof, ["claude-sonnet-5"])
        assert n == 1 and any(e.endswith(": EXPIRED") for e in ev), ev

def test_expired_negative_age_future_observed_at():
    with _case() as (root, prof):
        _record(prof, "claude-sonnet-5", "9.9.9", _scope(root, prof), age=-100)
        _, n, ev = _run(root, prof, ["claude-sonnet-5"])
        assert n == 1 and any(e.endswith(": EXPIRED") for e in ev), ev

def test_version_mismatch_same_model_and_scope_other_version():
    with _case() as (root, prof):
        _record(prof, "claude-sonnet-5", "1.0.0", _scope(root, prof))
        _, n, ev = _run(root, prof, ["claude-sonnet-5"], version="9.9.9")
        assert n == 1 and any("VERSION-MISMATCH" in e for e in ev), ev

def test_unknown_current_version_undeterminable():
    with _case() as (root, prof):
        _record(prof, "claude-sonnet-5", "9.9.9", _scope(root, prof))  # a VALID record, still UNKNOWN
        _, n, ev = _run(root, prof, ["claude-sonnet-5"], version=None)
        assert n == 1 and any(e.endswith(": UNKNOWN") for e in ev), ev

def test_unknown_malformed_record_for_configured_model():
    with _case() as (root, prof):
        _record(prof, "claude-sonnet-5", "9.9.9", _scope(root, prof), raw="{not json")
        _, n, ev = _run(root, prof, ["claude-sonnet-5"])
        assert n == 1 and any(e.endswith(": UNKNOWN") for e in ev), ev

def test_record_for_a_non_configured_model_is_ignored():
    with _case() as (root, prof):
        _record(prof, "claude-old-retired", "9.9.9", _scope(root, prof))
        status, n, ev = _run(root, prof, ["claude-sonnet-5"])  # sonnet-5 itself is MISSING
        assert status == pp.DIVERGED and n == 1 and not any("claude-old-retired" in e for e in ev), ev

def test_settings_model_value_is_reported_verbatim():
    with _case(settings={"model": "claude-fable-5-1[1m]"}) as (root, prof):
        _, n, ev = _run(root, prof, [])
        assert n == 1 and any(e.endswith("claude-fable-5-1[1m]: MISSING") for e in ev), ev

if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    print(f"\n{'FAILED' if failures else 'OK'} — {failures} failure(s)")
    raise SystemExit(1 if failures else 0)
