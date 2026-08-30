"""The legacy probe command must remain a zero-network fail-closed shim."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "wr3_probe_single_clip.py"


def test_legacy_probe_command_cannot_generate_or_recover() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "/path/that/does/not/exist"],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert result.returncode == 64
    payload = json.loads(result.stdout)
    assert payload == {
        "status": "HALT",
        "reason": "legacy_paid_probe_entrypoint_retired",
        "automatic_generation_forbidden": True,
        "generate_with": "scripts/wr3_camera_probe_run.py",
        "recover_with": "scripts/wr3_camera_probe_recover.py",
    }
    assert result.stderr == ""
