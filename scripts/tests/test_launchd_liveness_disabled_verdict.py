"""Healer tick 2026-07-18: deliberate disarm read as an alarm. `NOT-LOADED`
is in ALARM_VERDICTS, but a job the operator explicitly `launchctl disable`-d
is not a finding — it's a documented decision.

Real cases, same day: `com.balizero.agent-library-evolver.daily`/`.weekly`
were disarmed via `launchctl bootout + disable` per an operator decision
documented in `research/operations/specs/WR3-QUALITY-DECISIONS.md`
(~lines 293-304, 2026-06-12) but the detector reports NOT-LOADED (a perpetual
alarm for a job that is SUPPOSED to be off). `com.matagaruda.kg-query-api`
was also `launchctl disable`-d the same day on Pro — a phantom instance of a
service that actually lives on Mini. Verified live 2026-07-18:
`launchctl print-disabled "gui/$(id -u)"` lists
`"com.balizero.agent-library-evolver.daily" => disabled`,
`"com.balizero.agent-library-evolver.weekly" => disabled`, and
`"com.matagaruda.kg-query-api" => disabled`.

Contract under test (_disabled_labels / _disabled_verdict):
  - guilt: a NOT-LOADED verdict whose label IS in the disabled registry
    becomes DISABLED, and DISABLED does not increment alarms (it's not in
    ALARM_VERDICTS)
  - innocence: a NOT-LOADED verdict whose label is NOT in the disabled
    registry stays NOT-LOADED (still an alarm) — a bare-substring or
    wildcard-match bug here would silently swallow a REAL outage
  - innocence: any OTHER verdict (DEAD-GREEN, ARMED-TO-NOTHING,
    FAILING-HONESTLY, OK, RECOVERED) is left untouched even if the label
    happens to also be disabled — those verdicts rest on evidence a mere
    disable doesn't explain away
  - _disabled_labels() parses real `launchctl print-disabled` output shape
    (tabs, `=> disabled` / `=> enabled`) and best-effort-degrades to an
    empty set on any failure (never raises, never crashes audit())
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "launchd_liveness_detector.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("launchd_liveness_detector", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------ _disabled_verdict


def test_not_loaded_becomes_disabled_when_label_is_disabled():
    """Guilt: NOT-LOADED + label in the disabled registry -> DISABLED."""
    mod = _load_module()
    disabled = {"com.balizero.agent-library-evolver.daily"}
    verdict = mod._disabled_verdict(
        "NOT-LOADED", "com.balizero.agent-library-evolver.daily", disabled
    )
    assert verdict == "DISABLED"


def test_disabled_is_not_an_alarm_verdict():
    """Guilt (structural): DISABLED must never be added to ALARM_VERDICTS —
    that's what makes the override actually silence the noise."""
    mod = _load_module()
    assert "DISABLED" not in mod.ALARM_VERDICTS


def test_not_loaded_stays_not_loaded_when_label_not_disabled():
    """Innocence: a genuinely dead job (NOT-LOADED, not in the disabled
    registry) must keep alarming — the override must not be a blanket
    'not-loaded is fine' pass."""
    mod = _load_module()
    disabled = {"com.balizero.agent-library-evolver.daily"}
    verdict = mod._disabled_verdict(
        "NOT-LOADED", "com.nuzantara.some-other-cron.daily", disabled
    )
    assert verdict == "NOT-LOADED"
    assert verdict in mod.ALARM_VERDICTS


def test_other_verdicts_untouched_even_if_label_is_disabled():
    """Innocence: DEAD-GREEN / ARMED-TO-NOTHING / FAILING-HONESTLY / OK /
    RECOVERED are never rewritten to DISABLED, even for a label that IS in
    the disabled registry — those verdicts carry independent evidence a
    mere `launchctl disable` doesn't explain away."""
    mod = _load_module()
    disabled = {"com.matagaruda.kg-query-api"}
    for other in ("DEAD-GREEN", "DEAD-NONZERO", "ARMED-TO-NOTHING",
                  "FAILING-HONESTLY", "OK", "RECOVERED"):
        assert mod._disabled_verdict(other, "com.matagaruda.kg-query-api", disabled) == other


def test_empty_disabled_registry_never_overrides():
    """Innocence: an empty (best-effort-failed) registry means NOT-LOADED
    always stays NOT-LOADED — degrade-to-noisy, never degrade-to-blind."""
    mod = _load_module()
    assert mod._disabled_verdict("NOT-LOADED", "com.anything.here", set()) == "NOT-LOADED"


# ------------------------------------------------------------- _disabled_labels


_PRINT_DISABLED_SAMPLE = (
    '\tdisabled services = {\n'
    '\t\t"io.tailscale.ipn.macsys.login-item-helper" => enabled\n'
    '\t\t"com.balizero.warroom.morning" => disabled\n'
    '\t\t"com.matagaruda.kg-query-api" => disabled\n'
    '\t\t"com.balizero.agent-library-evolver.weekly" => disabled\n'
    '\t\t"com.balizero.agent-library-evolver.daily" => disabled\n'
    '\t\t"com.matagaruda.kita-feed.daily" => enabled\n'
    '\t\t"com.matagaruda.kita-feed" => enabled\n'
    '\t}\n'
)


def test_disabled_labels_parses_real_shape(monkeypatch):
    """Guilt: parses the real `launchctl print-disabled` output shape
    (verified live 2026-07-18) and returns ONLY the disabled labels."""
    mod = _load_module()

    class _FakeCompleted:
        returncode = 0
        stdout = _PRINT_DISABLED_SAMPLE

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _FakeCompleted())
    labels = mod._disabled_labels()
    assert labels == {
        "com.balizero.warroom.morning",
        "com.matagaruda.kg-query-api",
        "com.balizero.agent-library-evolver.weekly",
        "com.balizero.agent-library-evolver.daily",
    }


def test_disabled_labels_excludes_enabled_entries():
    """Innocence: entries explicitly marked `=> enabled` must never leak
    into the disabled set (word-boundary on the RHS, not a bare 'disabled'
    substring scan that would also match inside 'com.foo.disabled-thing')."""
    mod = _load_module()
    # exercised implicitly by the assertion above (kita-feed variants are
    # 'enabled' and absent from the returned set) — restated explicitly here
    # for guard-conformance (cicatrix #3 wants an EXPLICIT innocence case,
    # not just an absence inferred from a different test's equality check).
    import re
    for line in _PRINT_DISABLED_SAMPLE.splitlines():
        m = re.search(r'"([^"]+)"\s*=>\s*enabled\b', line)
        if m:
            assert m.group(1) not in {
                "com.balizero.warroom.morning",
                "com.matagaruda.kg-query-api",
                "com.balizero.agent-library-evolver.weekly",
                "com.balizero.agent-library-evolver.daily",
            }


def test_disabled_labels_best_effort_empty_on_nonzero_returncode(monkeypatch):
    """Innocence: launchctl erroring out (e.g. no GUI session) degrades to
    an empty set, never raises."""
    mod = _load_module()

    class _FakeCompleted:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: _FakeCompleted())
    assert mod._disabled_labels() == set()


def test_disabled_labels_best_effort_empty_on_subprocess_error(monkeypatch):
    """Innocence (2nd shape): launchctl missing/erroring (OSError/timeout)
    also degrades to an empty set."""
    mod = _load_module()

    def _raise(*a, **k):
        raise OSError("launchctl not found")

    monkeypatch.setattr(mod.subprocess, "run", _raise)
    assert mod._disabled_labels() == set()


# --------------------------------------------------------------- audit() wiring


def _write_minimal_plist(path: Path, label: str) -> None:
    import plistlib
    path.write_bytes(plistlib.dumps({
        "Label": label,
        "ProgramArguments": ["/bin/echo"],
        "RunAtLoad": True,
    }))


def test_audit_reports_disabled_and_does_not_alarm(tmp_path, monkeypatch):
    """Guilt, end-to-end: a plist for a disabled, not-loaded label produces
    a DISABLED finding in audit(), and that finding does not count toward
    alarms."""
    mod = _load_module()
    monkeypatch.setattr(mod, "LAUNCHAGENTS", tmp_path)
    label = "com.balizero.agent-library-evolver.daily"
    _write_minimal_plist(tmp_path / f"{label}.plist", label)

    def _fake_run(cmd, **kwargs):
        class _R:
            returncode = 0
            stdout = ""

        if cmd[0] == "plutil":
            r = _R()
            r.stdout = label
            return r
        if cmd[0] == "launchctl" and cmd[1] == "print-disabled":
            r = _R()
            r.stdout = f'\t\t"{label}" => disabled\n'
            return r
        if cmd[0] == "launchctl" and cmd[1] == "list":
            r = _R()
            r.returncode = 113  # not loaded
            return r
        r = _R()
        r.returncode = 1
        r.stdout = ""
        return r

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    findings = mod.audit()
    assert len(findings) == 1
    assert findings[0]["verdict"] == "DISABLED"
    alarms = [f for f in findings if f["verdict"] in mod.ALARM_VERDICTS]
    assert alarms == []


def test_audit_reports_not_loaded_when_label_is_not_in_disabled_registry(tmp_path, monkeypatch):
    """Innocence, end-to-end: a genuinely dead (not-loaded, not-disabled)
    job still shows NOT-LOADED and counts as an alarm."""
    mod = _load_module()
    monkeypatch.setattr(mod, "LAUNCHAGENTS", tmp_path)
    label = "com.nuzantara.some-other-cron.daily"
    _write_minimal_plist(tmp_path / f"{label}.plist", label)

    def _fake_run(cmd, **kwargs):
        class _R:
            returncode = 0
            stdout = ""

        if cmd[0] == "plutil":
            r = _R()
            r.stdout = label
            return r
        if cmd[0] == "launchctl" and cmd[1] == "print-disabled":
            r = _R()
            r.stdout = '\t\t"com.something-else.unrelated" => disabled\n'
            return r
        if cmd[0] == "launchctl" and cmd[1] == "list":
            r = _R()
            r.returncode = 113  # not loaded
            return r
        r = _R()
        r.returncode = 1
        r.stdout = ""
        return r

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    findings = mod.audit()
    assert len(findings) == 1
    assert findings[0]["verdict"] == "NOT-LOADED"
    alarms = [f for f in findings if f["verdict"] in mod.ALARM_VERDICTS]
    assert len(alarms) == 1
