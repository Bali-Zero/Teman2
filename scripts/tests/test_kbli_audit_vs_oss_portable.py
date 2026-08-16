from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT = REPO_ROOT / "scripts/kbli_audit_vs_oss.py"


def test_audit_resolves_inputs_from_the_repository_not_the_caller_cwd(tmp_path: Path):
    result = subprocess.run(
        [sys.executable, str(AUDIT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "OURS: 1559 codes | OSS 5-digit: 1559" in result.stdout
