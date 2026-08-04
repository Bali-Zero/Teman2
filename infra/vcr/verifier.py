"""infra/vcr/verifier.py — is the prober itself trustworthy? (R5 / VCR spec §5.3).

Verifier auditability: hash the running scripts/arsenal_probe.py against a
certified hash declared in the registry (catches HOME-fork drift and
unreviewed hand-edits, scar #1), and run its own --selftest (guilt+innocence
corpus already embedded there, arsenal_probe.py:_SELFTEST_CANNED) as the live
canary. A drifted or failing verifier means NO observation from this run can
be trusted, regardless of what the raw probe returned — the materializer must
never report TRUE while verifier_state is anything but HEALTHY.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from infra.vcr.records import DRIFTED, FAILED, HEALTHY


def compute_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _default_run_selftest(prober_path: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            [sys.executable, str(prober_path), "--selftest"],
            capture_output=True, text=True, timeout=30,
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()[-300:]
    except subprocess.TimeoutExpired:
        return -1, "selftest timed out"
    except Exception as e:  # a verifier check must never crash the caller
        return -1, f"{type(e).__name__}: {e}"


def check_verifier(
    prober_path: Path,
    certified_hash: Optional[str],
    run_selftest_fn: Callable[[Path], tuple[int, str]] = _default_run_selftest,
) -> tuple[str, str]:
    """Returns (verifier_state, detail). Order: existence -> hash -> selftest —
    each earlier check that fails short-circuits the later ones (no point
    running a 30s selftest against a prober known to be the wrong bytes)."""
    if not prober_path.is_file():
        return FAILED, f"prober not found: {prober_path}"
    actual_hash = compute_hash(prober_path)
    if certified_hash and actual_hash != certified_hash:
        return DRIFTED, f"hash mismatch: certified={certified_hash[:12]}… actual={actual_hash[:12]}…"
    rc, detail = run_selftest_fn(prober_path)
    if rc != 0:
        return FAILED, f"selftest exit {rc}: {detail}"
    if not certified_hash:
        # GLM red-team, 2026-08-03: claiming "hash certified" here when no
        # certified_hash was registered is a literal lie — the comparison
        # above was skipped entirely, not passed. Every registry entry this
        # pilot ships DOES carry a real certified_hash (expected_claims.yaml)
        # so this branch is not live today, but a future entry registered
        # without one must not silently read as HEALTHY-with-hash-proof.
        return HEALTHY, f"hash check SKIPPED (no certified_hash registered), selftest passed ({detail})"
    return HEALTHY, f"hash certified, selftest passed ({detail})"
