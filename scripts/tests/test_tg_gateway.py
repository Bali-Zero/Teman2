"""Tests for the Telegram notification gateway (tg_notify / tg_digest_flush / lint).

The three scripts carry their own hermetic --selftest fixtures (guilt+innocence);
this file makes pytest/CI run them, and pins the lint guard's verdict function
directly for the guard-conformance registry (superscar #3).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

sys.path.insert(0, str(SCRIPTS))
from lint_tg_direct_senders import GATEWAY_ALLOWLIST, _guard_new_direct_sender  # noqa: E402


def _run_selftest(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--selftest"],
        capture_output=True, text=True, timeout=120,
    )


def test_tg_notify_selftest_passes():
    proc = _run_selftest("tg_notify.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_tg_digest_flush_selftest_passes():
    proc = _run_selftest("tg_digest_flush.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_lint_tg_selftest_passes():
    proc = _run_selftest("lint_tg_direct_senders.py")
    assert proc.returncode == 0, proc.stdout + proc.stderr


# --- guard-conformance pins (registry: tg-gateway-lint) ---------------------


def test_tg_lint_guilt_new_direct_sender_flagged():
    """GUILT: a brand-new file hitting api.telegram.org is flagged."""
    senders = {"scripts/new_rogue_alerter.py", "scripts/legacy_ok.sh"}
    grandfathered = {"scripts/legacy_ok.sh"}
    assert _guard_new_direct_sender(senders, grandfathered) == {"scripts/new_rogue_alerter.py"}


def test_tg_lint_innocence_grandfathered_and_gateway_pass():
    """INNOCENCE: legacy grandfathered senders and the gateway itself never fire."""
    senders = {"scripts/legacy_ok.sh"} | set(GATEWAY_ALLOWLIST)
    grandfathered = {"scripts/legacy_ok.sh"}
    assert _guard_new_direct_sender(senders, grandfathered) == set()


def test_lint_clean_on_real_tree():
    """The shipped tree must be lint-clean (freeze happened at gateway birth)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "lint_tg_direct_senders.py")],
        capture_output=True, text=True, timeout=180, cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
