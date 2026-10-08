"""Guilt AND innocence for the fleet-target derivation in install-3mac.sh.

The defect (2026-10-08): REMOTE_TARGETS was hard-coded to `pro mini`, assuming M5 drives. Only Pro
can build; from Pro `ssh pro` is refused, so the script marked pro unreachable and never reached M5.
Targets are now derived from the driver host. To confirm these tests can fail, hard-code the
targets again: the Nuzantara innocence test must go red.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "apps" / "kbli-navigator-macos" / "deploy" / "install-3mac.sh"


def targets(host: str | None, override: str | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("KBLI_")}
    if host is not None:
        env["KBLI_DRIVER_HOST"] = host
    if override is not None:
        env["KBLI_REMOTE_TARGETS"] = override
    return subprocess.run(
        ["zsh", str(SCRIPT), "--print-targets"],
        capture_output=True, text=True, timeout=30, env=env, cwd=REPO,
    )


def test_pro_drives_m5_and_mini() -> None:
    r = targets("Nuzantara")
    assert (r.returncode, r.stdout.strip()) == (0, "m5 mini")


def test_m5_drives_pro_and_mini() -> None:
    r = targets("Air-M5")
    assert (r.returncode, r.stdout.strip()) == (0, "pro mini")


def test_mini_drives_m5_and_pro() -> None:
    r = targets("mini-pro2")
    assert (r.returncode, r.stdout.strip()) == (0, "m5 pro")


def test_override_is_honoured() -> None:
    r = targets("Nuzantara", override="m5")
    assert (r.returncode, r.stdout.strip()) == (0, "m5")


def test_override_listing_the_driver_is_refused() -> None:
    r = targets("Nuzantara", override="pro mini")
    assert r.returncode == 2
    assert "driver" in r.stderr
    assert r.stdout.strip() == ""


def test_unknown_host_without_override_is_refused() -> None:
    r = targets("some-other-box")
    assert r.returncode == 2
    assert "KBLI_REMOTE_TARGETS" in r.stderr


def test_unknown_host_with_override_is_accepted() -> None:
    r = targets("some-other-box", override="m5 mini")
    assert (r.returncode, r.stdout.strip()) == (0, "m5 mini")
