"""Self-test for the suite-wide OSINT-Nexus launch guard in conftest.py."""
from __future__ import annotations

import subprocess

from mata_garuda.tools import lhkpn_tools


def test_launcher_is_blocked_by_default(monkeypatch):
    calls = []

    def _recording_run(*args, **kwargs):
        calls.append(args)
        raise AssertionError("subprocess.run must not be reached")

    monkeypatch.setattr(subprocess, "run", _recording_run)

    assert lhkpn_tools._invoke_osint_nexus.__name__ == "_blocked"
    result = lhkpn_tools._invoke_osint_nexus(mode="search", query="placeholder")
    assert result["ok"] is False
    assert result["error"] == "osint_nexus_launch_blocked_in_tests"
    assert calls == []


def test_opt_in_reaches_the_real_launcher(allow_osint_launch):
    assert lhkpn_tools._invoke_osint_nexus.__name__ == "_invoke_osint_nexus"
