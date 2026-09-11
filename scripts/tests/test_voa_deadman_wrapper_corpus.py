"""pytest shim for scripts/tests/test_voa_deadman_wrapper.sh.

That shell corpus (guilt/innocence for infra/launchagents/wrappers/
voa-deadman-wrapper.sh -- G5 kill switch, missing-payload FATAL, the four/
five-state organism status mapping, and the deliberate absence of a G10
lock) is bash, not python -- pytest cannot collect it directly. This file
exists purely so the existing pytest sweep (local and CI) picks it up
automatically, mirroring scripts/tests/test_voa_probe_corpus.py's own
shim for its sibling organ's wrapper corpus (L07-PR2/PR3 share the pattern
on purpose).

The shell script itself is the source of truth for the assertions; this
shim's only job is to run it and surface its FULL output (stdout AND
stderr) on failure, since that output names exactly which PASS/FAIL line(s)
broke.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHELL_CORPUS = _REPO_ROOT / "scripts" / "tests" / "test_voa_deadman_wrapper.sh"


def test_voa_deadman_wrapper_shell_corpus_passes() -> None:
    assert _SHELL_CORPUS.is_file(), f"shell corpus missing at {_SHELL_CORPUS}"

    result = subprocess.run(
        ["bash", str(_SHELL_CORPUS)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"voa deadman wrapper shell corpus failed (rc={result.returncode})\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
