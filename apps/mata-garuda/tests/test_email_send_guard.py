"""Self-test for the suite-wide email guard in conftest.py."""
from __future__ import annotations

import subprocess

from mata_garuda.tools import brevo_tools


def test_sender_sees_no_key_by_default(monkeypatch):
    calls = []

    def _recording_run(*args, **kwargs):
        calls.append(args)
        raise AssertionError("subprocess.run must not be reached")

    monkeypatch.setenv("BREVO_API_KEY", "xkeysib-" + "placeholder")
    monkeypatch.setattr(subprocess, "run", _recording_run)
    result = brevo_tools.send_html("placeholder@example.invalid", "subject", "<p>body</p>")
    assert result == {"ok": False, "status": 0, "reason": "no BREVO_API_KEY"}
    assert calls == []


def test_opt_in_restores_the_real_key_resolution(allow_real_email):
    assert brevo_tools._resolve_key.__name__ == "_resolve_key"
