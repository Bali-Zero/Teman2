"""B42 follow-up: the flip runbook's carry-over command (scripts/localci/README.md) is run against a fake gh by a shell test no workflow runs by itself."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(shutil.which("jq") is None, reason="the fake gh applies --jq with the real jq")
def test_the_flip_carryover_selection_shell_suite_passes():
    run = subprocess.run(["bash", str(ROOT / "scripts/tests/test_localci_flip_carryover_selection.sh")], capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout[-1500:] + run.stderr[-500:]
