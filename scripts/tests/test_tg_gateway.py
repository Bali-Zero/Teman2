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


# --- the FAIL message must be actionable for a PROSE offender ---------------
# Added 2026-08-31. The lint's advice ("use tg_notify.py instead") is right for a
# code offender and useless for a file that only WRITES ABOUT the endpoint: an
# evidence pack has no sender to migrate. Measured that day: nothing anywhere
# else in this repo warns a pack author the literal is forbidden — not
# evidence_paths.py's docstring, not the modus skill, not docs/, not the
# gateway's own runbook — so this message is the only place the remedy reaches
# them, and PR #5422 spent a round of CI discovering that by hand.


def _run_lint_against(root: Path, rel: str) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ, TG_LINT_ROOT=str(root), TG_LINT_FILES=rel)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "lint_tg_direct_senders.py")],
        capture_output=True, text=True, timeout=120, env=env,
    )


def test_fail_message_tells_a_prose_author_what_to_do(tmp_path: Path):
    """GUILT: the hint appears, and names BOTH remedies in preference order."""
    # Built at runtime, never spelled as a literal — this test file is itself
    # scanned by the lint it is testing.
    pattern = "https://api." + "telegram" + ".org/bot<TOKEN>/sendMessage"
    guilty = tmp_path / "evidence" / "2026-08" / "some-task" / "brief.yml"
    guilty.parent.mkdir(parents=True)
    guilty.write_text(f"note: the alert step posts to {pattern} directly\n", encoding="utf-8")

    proc = _run_lint_against(tmp_path, "evidence/2026-08/some-task/brief.yml")

    assert proc.returncode == 1, proc.stdout + proc.stderr
    err = proc.stderr
    assert "evidence/2026-08/some-task/brief.yml" in err, "the offender must still be named"
    assert "only DESCRIBES the endpoint" in err, "the prose case must be addressed"
    assert "rephrase" in err, "remedy 1 (preferred) must be offered"
    assert "GATEWAY_ALLOWLIST" in err, "remedy 2 must be named"
    assert err.index("rephrase") < err.index("GATEWAY_ALLOWLIST"), (
        "the cheap remedy must come first — the allowlist does not scale"
    )
    assert "deliberate" in err, "the author must learn the over-match is intended, not a bug"


def test_no_hint_when_the_tree_is_clean(tmp_path: Path):
    """INNOCENCE: a passing run must not print the hint at all."""
    clean = tmp_path / "scripts" / "harmless.py"
    clean.parent.mkdir(parents=True)
    clean.write_text("print('no endpoint here')\n", encoding="utf-8")

    proc = _run_lint_against(tmp_path, "scripts/harmless.py")

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "only DESCRIBES the endpoint" not in (proc.stdout + proc.stderr)
