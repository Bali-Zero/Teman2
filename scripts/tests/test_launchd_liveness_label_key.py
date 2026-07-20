"""Healer tick 2026-07-18: filename-stem-as-label bug. The detector keyed
`launchctl list`/findings on `plist.stem`, but launchctl keys on the plist's
DECLARED `:Label`, and some of our own plists disagree with their filename.

Real finding (live, verified same day): `com.matagaruda.kita-feed.daily.plist`
and `com.matagaruda.wr2-bridge.hourly.plist` both declare a Label WITHOUT the
trailing `.daily`/`.hourly` suffix (`com.matagaruda.kita-feed` /
`com.matagaruda.wr2-bridge`) — confirmed via
`plutil -extract Label raw -o - <plist>`. The jobs are alive and running
(success logs 05:00 and 14:22 the same day) but the OLD stem-keyed detector
reported both NOT-LOADED, because `launchctl list com.matagaruda.kita-
feed.daily` asks about a label launchctl has never heard of.

Fix reuses the pattern already proven in
apps/mata-garuda/mata_garuda/workers/plist_watchdog.py::_label_of
(~lines 77-93): `plutil -extract Label raw -o -` with a fallback to the
filename stem when plutil fails.

Contract under test (_label_of / audit()):
  - guilt: stem != declared Label -> _label_of returns the declared Label
  - guilt (end-to-end): audit() queries launchctl by the REAL label, not the
    stem — a mock that only answers the real label proves the job's live
    verdict (not NOT-LOADED) reaches the finding
  - innocence: stem == declared Label -> _label_of returns that label
    (identical to pre-fix behavior)
  - innocence: plutil fails (non-zero rc / missing binary) -> falls back to
    the filename stem, exactly the old behavior
"""
from __future__ import annotations

import importlib.util
import plistlib
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "launchd_liveness_detector.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("launchd_liveness_detector", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write_plist(path: Path, label: str, program: str) -> None:
    path.write_bytes(plistlib.dumps({
        "Label": label,
        "ProgramArguments": [program],
        "RunAtLoad": True,
    }))


# --------------------------------------------------------------- _label_of


def test_label_of_returns_declared_label_when_it_diverges_from_stem(tmp_path, monkeypatch):
    """Guilt: real shape — plist filename stem is
    'com.matagaruda.kita-feed.daily' but the declared Label is
    'com.matagaruda.kita-feed'."""
    mod = _load_module()
    plist = tmp_path / "com.matagaruda.kita-feed.daily.plist"
    _write_plist(plist, "com.matagaruda.kita-feed", "/bin/echo")
    assert plist.stem == "com.matagaruda.kita-feed.daily"
    assert mod._label_of(plist) == "com.matagaruda.kita-feed"


def test_label_of_returns_stem_when_label_matches(tmp_path):
    """Innocence: stem == declared Label -> unchanged from pre-fix stem
    behavior."""
    mod = _load_module()
    plist = tmp_path / "com.nuzantara.overlap-detector.daily.plist"
    _write_plist(plist, "com.nuzantara.overlap-detector.daily", "/bin/echo")
    assert mod._label_of(plist) == "com.nuzantara.overlap-detector.daily"


def test_label_of_falls_back_to_stem_when_plutil_fails(tmp_path, monkeypatch):
    """Innocence: plutil erroring out (malformed plist, missing binary, ...)
    degrades to the OLD stem-based behavior — never raises, never returns
    an empty/garbage label."""
    mod = _load_module()
    plist = tmp_path / "com.matagaruda.kita-feed.daily.plist"
    _write_plist(plist, "com.matagaruda.kita-feed", "/bin/echo")

    class _FailedRun:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _FailedRun())
    assert mod._label_of(plist) == "com.matagaruda.kita-feed.daily"


def test_label_of_falls_back_to_stem_on_subprocess_error(tmp_path, monkeypatch):
    """Innocence (2nd shape): plutil literally missing/erroring (OSError) is
    handled the same as a non-zero return code."""
    mod = _load_module()
    plist = tmp_path / "com.matagaruda.kita-feed.daily.plist"
    _write_plist(plist, "com.matagaruda.kita-feed", "/bin/echo")

    def _raise(*a, **k):
        raise OSError("plutil not found")

    monkeypatch.setattr(mod.subprocess, "run", _raise)
    assert mod._label_of(plist) == "com.matagaruda.kita-feed.daily"


# ------------------------------------------------------------ audit() end-to-end


def test_audit_queries_the_real_label_not_the_stem(tmp_path, monkeypatch):
    """Guilt, end-to-end: a mock `launchctl list` that ONLY answers the
    real (declared) label — and returns 'not found' for the stem — must
    still produce a live verdict (not NOT-LOADED) in audit()'s findings.
    This is the exact shape that was silently misreporting kita-feed/
    wr2-bridge as dead."""
    mod = _load_module()
    monkeypatch.setattr(mod, "LAUNCHAGENTS", tmp_path)

    real_label = "com.matagaruda.kita-feed"
    stem_label = "com.matagaruda.kita-feed.daily"
    plist = tmp_path / f"{stem_label}.plist"
    program = str(tmp_path / "wrapper.sh")
    Path(program).write_text("#!/bin/sh\n", encoding="utf-8")
    _write_plist(plist, real_label, program)

    def _fake_run(cmd, **kwargs):
        class _R:
            returncode = 0
            stdout = ""

        if cmd[0] == "plutil":
            r = _R()
            r.stdout = real_label
            return r
        if cmd[0] == "launchctl" and cmd[1] == "list":
            queried = cmd[2]
            r = _R()
            if queried == real_label:
                r.returncode = 0
                r.stdout = '{\n\t"LastExitStatus" = 0;\n\t"PID" = 111;\n};\n'
            else:
                r.returncode = 113
                r.stdout = ""
            return r
        if cmd[0] == "ps":
            r = _R()
            r.stdout = "00:05:00"
            return r
        r = _R()
        r.returncode = 1
        r.stdout = ""
        return r

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    findings = mod.audit()
    assert len(findings) == 1
    finding = findings[0]
    # Strong assertion, not just "!= NOT-LOADED": the mock ONLY answers the
    # REAL label with a live 0-exit/PID status and returns "not found" (113)
    # for the stem — so landing on OK (not NOT-LOADED) is only possible if
    # audit() queried launchctl by the resolved Label, exactly as _label_of
    # returns it, not by plist.stem.
    assert finding["label"] == real_label
    assert finding["verdict"] == "OK"
    assert finding["last_exit"] == 0
