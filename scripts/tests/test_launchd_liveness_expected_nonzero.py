"""Ward-round 2026-08-07: `audit-launchd-daily-exit-by-design` +
`launchd-liveness-detector-self-flag`, both upheld sensor_stale.

`_classify()` correctly distinguishes DEAD-GREEN/DEAD-NONZERO (a launch
failure marker in the log) from FAILING-HONESTLY (a non-zero exit with no
such marker — "the job ran, and is telling the truth about failing"). But
four labels have a non-zero exit that is not a failure at all: it is the
job's own reporting convention.

  - com.balizero.audit-launchd.daily: exit = the COUNT of unhealthy jobs it
    found that run (organism_stale_detector.py's KNOWN_BENIGN_FAILED already
    documents the identical convention for pro.audit_launchd_daily's sidecar).
  - com.nuzantara.mcp-integrity: exit encodes RED/YELLOW/GREEN drift against
    a moving connectivity baseline.
  - com.nuzantara.launchd-liveness-detector.daily: THIS detector's own cron —
    `main()` returns 1 whenever audit() finds an alarm-worthy job ELSEWHERE,
    so a day with one real finding self-flags the detector's own entry too.
  - com.balizero.zoho-mail-loop.daily: exit encodes a DEGRADED draft-failure
    count for the day (W114/W115/W116 convention).

Contract under test (EXPECTED_NONZERO_LABELS / _expected_nonzero_verdict):
  - guilt: a FAILING-HONESTLY verdict for a listed label becomes
    EXPECTED-NONZERO, and EXPECTED-NONZERO does not increment alarms
  - innocence: a FAILING-HONESTLY verdict for an UNLISTED label stays
    FAILING-HONESTLY — a bare-substring or wildcard match here would
    silently swallow a real chronic failure
  - innocence: any OTHER verdict (DEAD-GREEN, DEAD-NONZERO,
    ARMED-TO-NOTHING, OK, RECOVERED, DISABLED) is left untouched even for a
    listed label — those verdicts rest on independent evidence a reporting
    convention does not explain away
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


# ------------------------------------------------------- _expected_nonzero_verdict


def test_failing_honestly_becomes_expected_nonzero_for_listed_label():
    """Guilt: FAILING-HONESTLY + label in EXPECTED_NONZERO_LABELS -> EXPECTED-NONZERO."""
    mod = _load_module()
    for label in mod.EXPECTED_NONZERO_LABELS:
        assert mod._expected_nonzero_verdict("FAILING-HONESTLY", label) == "EXPECTED-NONZERO"


def test_expected_nonzero_is_not_an_alarm_verdict():
    """Guilt (structural): EXPECTED-NONZERO must never be added to
    ALARM_VERDICTS — that's what makes the override actually silence the
    noise instead of just relabeling it."""
    mod = _load_module()
    assert "EXPECTED-NONZERO" not in mod.ALARM_VERDICTS


def test_all_four_ward_round_labels_are_covered():
    """Guilt (regression pin): the exact 4 labels the 2026-08-07 ward-round
    named must be on the allowlist — a future edit that drops one silently
    reopens that finding."""
    mod = _load_module()
    assert mod.EXPECTED_NONZERO_LABELS == {
        "com.balizero.audit-launchd.daily",
        "com.nuzantara.mcp-integrity",
        "com.nuzantara.launchd-liveness-detector.daily",
        "com.balizero.zoho-mail-loop.daily",
    }


def test_failing_honestly_stays_failing_honestly_for_unlisted_label():
    """Innocence: a genuinely chronic non-zero-exit job (not on the
    allowlist) must keep reading FAILING-HONESTLY — the override must not
    be a blanket 'any non-zero exit is fine' pass."""
    mod = _load_module()
    verdict = mod._expected_nonzero_verdict(
        "FAILING-HONESTLY", "com.nuzantara.some-other-cron.daily"
    )
    assert verdict == "FAILING-HONESTLY"


def test_other_verdicts_untouched_even_for_a_listed_label():
    """Innocence: DEAD-GREEN / DEAD-NONZERO / ARMED-TO-NOTHING / OK /
    RECOVERED / DISABLED are never rewritten to EXPECTED-NONZERO, even for a
    label that IS on the allowlist — those verdicts carry independent
    evidence a reporting convention doesn't explain away. A label re-armed
    for a different, genuinely broken purpose must still alarm."""
    mod = _load_module()
    label = "com.balizero.audit-launchd.daily"
    for other in ("DEAD-GREEN", "DEAD-NONZERO", "ARMED-TO-NOTHING",
                  "OK", "RECOVERED", "DISABLED"):
        assert mod._expected_nonzero_verdict(other, label) == other


def test_empty_allowlist_membership_never_overrides():
    """Innocence (2nd shape): an arbitrary label not on the allowlist at all
    stays untouched regardless of verdict."""
    mod = _load_module()
    assert mod._expected_nonzero_verdict("FAILING-HONESTLY", "com.anything.here") == "FAILING-HONESTLY"


# --------------------------------------------------------------- audit() wiring


def _write_minimal_plist(path: Path, label: str) -> None:
    import plistlib
    path.write_bytes(plistlib.dumps({
        "Label": label,
        "ProgramArguments": ["/bin/echo"],
        "RunAtLoad": True,
    }))


def test_audit_reports_expected_nonzero_and_does_not_alarm(tmp_path, monkeypatch):
    """Guilt, end-to-end: a plist for a listed label, loaded, non-zero exit,
    no log-failure marker, no missing program -> EXPECTED-NONZERO in
    audit(), and that finding does not count toward alarms."""
    mod = _load_module()
    monkeypatch.setattr(mod, "LAUNCHAGENTS", tmp_path)
    label = "com.nuzantara.mcp-integrity"
    plist_path = tmp_path / f"{label}.plist"
    _write_minimal_plist(plist_path, label)
    # ProgramArguments[0] must resolve so `prog_exists` is True (otherwise
    # _classify short-circuits to ARMED-TO-NOTHING before ever reaching the
    # FAILING-HONESTLY branch this test targets).
    monkeypatch.setattr(mod, "_program_path", lambda plist: "/bin/echo")

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
            r.stdout = ""
            return r
        if cmd[0] == "launchctl" and cmd[1] == "list":
            # `launchctl list <label>` — loaded, non-zero LastExitStatus, no PID.
            r = _R()
            r.stdout = (
                '{\n\t"LastExitStatus" = 256;\n\t"Label" = "%s";\n}\n' % label
            )
            return r
        r = _R()
        r.returncode = 1
        r.stdout = ""
        return r

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    monkeypatch.setattr(mod, "_log_has_failure_marker", lambda logs: None)
    monkeypatch.setattr(mod, "_log_paths", lambda plist: [])
    findings = mod.audit()
    assert len(findings) == 1
    assert findings[0]["verdict"] == "EXPECTED-NONZERO"
    alarms = [f for f in findings if f["verdict"] in mod.ALARM_VERDICTS]
    assert alarms == []


def test_audit_reports_failing_honestly_for_unlisted_label_with_same_shape(tmp_path, monkeypatch):
    """Innocence, end-to-end: the EXACT same loaded/non-zero/no-marker shape
    for a label NOT on the allowlist still shows FAILING-HONESTLY, and does
    not alarm (matching the pre-existing behavior this fix must not change
    for anyone else) — proves the override is label-scoped, not shape-scoped."""
    mod = _load_module()
    monkeypatch.setattr(mod, "LAUNCHAGENTS", tmp_path)
    label = "com.nuzantara.some-other-cron.daily"
    plist_path = tmp_path / f"{label}.plist"
    _write_minimal_plist(plist_path, label)
    monkeypatch.setattr(mod, "_program_path", lambda plist: "/bin/echo")

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
            r.stdout = ""
            return r
        if cmd[0] == "launchctl" and cmd[1] == "list":
            r = _R()
            r.stdout = (
                '{\n\t"LastExitStatus" = 256;\n\t"Label" = "%s";\n}\n' % label
            )
            return r
        r = _R()
        r.returncode = 1
        r.stdout = ""
        return r

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    monkeypatch.setattr(mod, "_log_has_failure_marker", lambda logs: None)
    monkeypatch.setattr(mod, "_log_paths", lambda plist: [])
    findings = mod.audit()
    assert len(findings) == 1
    assert findings[0]["verdict"] == "FAILING-HONESTLY"
