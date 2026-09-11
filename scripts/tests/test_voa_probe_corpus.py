"""pytest shim for scripts/tests/test_voa_probe_wrapper.sh.

That shell corpus (guilt/innocence for the VOA journey probe's pure
classifiers, F11's runJourney fake-fetchImpl scenarios (a)-(g), F1's
--dry-run heartbeat gating, and the wrapper's missing-probe/probe-fails/
happy-path behavior) is bash, not python — pytest cannot collect it
directly. This file exists purely so the existing pytest sweep (local and
CI) picks it up automatically, per the L07-PR2 mandate item F13, rather than
requiring anyone to remember a separate `bash scripts/tests/...sh` step.

The shell script itself is the source of truth for the assertions; this
shim's only job is to run it and surface its FULL output (stdout AND
stderr) on failure, since that output names exactly which PASS/FAIL line(s)
broke.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHELL_CORPUS = _REPO_ROOT / "scripts" / "tests" / "test_voa_probe_wrapper.sh"


def test_voa_probe_shell_corpus_passes() -> None:
    assert _SHELL_CORPUS.is_file(), f"shell corpus missing at {_SHELL_CORPUS}"

    result = subprocess.run(
        ["bash", str(_SHELL_CORPUS)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"voa journey probe shell corpus failed (rc={result.returncode})\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
