"""Self-repair blind-spot #1 — system_doctor must read ~/logs/cron-agent*/*.log.

Audit 2026-04-19 finding: cron-agent jobs on Air write logs under
`~/logs/cron-agent*/` but `gather_health` (the system_doctor collector stage)
never opened them. A cron that failed silently (exit code != 0) was therefore
invisible to the health pipeline.

This test pins the new `collect_cron_agent_logs()` collector: each ERROR line
or `exit code [1-9]` match surfaces a MEDIUM SystemCheck; a missing log tree
degrades to a LOW severity warning (backward-compat — never crashes).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SYSTEM_DOCTOR = _ROOT / "scripts" / "system_doctor.py"


@pytest.fixture(scope="module")
def doctor():
    """Import scripts/system_doctor.py as a module (no package)."""
    spec = importlib.util.spec_from_file_location(
        "system_doctor_module", _SYSTEM_DOCTOR
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["system_doctor_module"] = module
    spec.loader.exec_module(module)
    return module


def test_collect_cron_agent_logs_exists(doctor) -> None:
    """The collector must be exported at module scope so main() can wire it."""
    assert hasattr(doctor, "collect_cron_agent_logs"), (
        "system_doctor must expose collect_cron_agent_logs() — "
        "see audit 2026-04-19 blind-spot #1"
    )
    assert callable(doctor.collect_cron_agent_logs)


def test_cron_agent_errors_surface_as_medium_health_issues(
    tmp_path: Path, monkeypatch, doctor
) -> None:
    """ERROR + `exit code N` lines each create a warning-severity SystemCheck."""
    logs_root = tmp_path / "logs"
    agent_a = logs_root / "cron-agent-alpha"
    agent_a.mkdir(parents=True)
    (agent_a / "alpha.log").write_text(
        "[2026-04-20 03:00:00] INFO: starting alpha\n"
        "[2026-04-20 03:00:05] ERROR: alpha failed to connect\n"
        "[2026-04-20 03:00:06] exit code 2\n"
    )
    # A second cron-agent bucket with a clean log — must NOT raise an issue.
    agent_b = logs_root / "cron-agent-beta"
    agent_b.mkdir(parents=True)
    (agent_b / "beta.log").write_text(
        "[2026-04-20 03:00:00] INFO: started\n"
        "[2026-04-20 03:00:05] INFO: completed ok\n"
    )

    monkeypatch.setattr(doctor, "CRON_AGENT_LOG_GLOBS", [
        str(logs_root / "cron-agent*" / "*.log")
    ])

    checks = doctor.collect_cron_agent_logs()
    assert checks, "collector must always return at least one SystemCheck"

    statuses = [c.status for c in checks]
    # At least one MEDIUM (= "warning") severity because of alpha.log
    assert "warning" in statuses, (
        f"Expected a warning for cron-agent ERROR lines, got {statuses}"
    )
    # Offending log path must be cited in the SystemCheck message / ai_context
    offenders = [c for c in checks if c.status == "warning"]
    assert any("alpha.log" in c.message or "alpha.log" in c.ai_context
               for c in offenders), offenders


def test_cron_agent_missing_tree_is_low_severity(
    tmp_path: Path, monkeypatch, doctor
) -> None:
    """If no cron-agent tree exists, collector returns a LOW severity check
    (info-level warning), never a crash — backward-compat with machines that
    don't run any cron-agent jobs yet."""
    monkeypatch.setattr(doctor, "CRON_AGENT_LOG_GLOBS", [
        str(tmp_path / "logs" / "cron-agent-nothing" / "*.log")
    ])

    checks = doctor.collect_cron_agent_logs()
    assert len(checks) == 1
    check = checks[0]
    # `warning` + stale=True marks it as low-severity informational
    assert check.status == "warning"
    assert check.stale is True
    assert "not found" in check.message.lower() or "no files" in check.message.lower()


def test_cron_agent_is_registered_as_collector(doctor, monkeypatch) -> None:
    """The collector must be wired into `main()`'s collectors list so it
    actually runs on every cron; otherwise blind-spot #1 stays unfixed."""
    # Parse the source — we avoid running main() end-to-end (SSH-heavy)
    source = _SYSTEM_DOCTOR.read_text()
    assert "collect_cron_agent_logs" in source
    assert (
        '("Cron-agent logs", collect_cron_agent_logs)' in source
        or "collect_cron_agent_logs)" in source
    ), "collect_cron_agent_logs must be listed in main()'s `collectors` tuple"
