#!/usr/bin/env python3
"""observe_visa_fold_generic.py — bites: observation for the generic ledger fold.

# bites-observable — this script takes NO arguments: every path and command
# below is a literal in this file, so nothing an invoker types can name a
# program to run, a file to write, or a database to reach.

Runs ``fold_pack_generic`` on the committed seq-24 signed pair and the 2026-10-07
read ledger with the seq-25 metadata, writes into a private tempdir, and exits 0
only if the printed payload digest is the committed seq-25 one.
"""

# bites-observable — no arguments; every path and command is a literal below and the
# only file written lives in a tempdir this script creates, so an invoker cannot name a
# program to run, a file to write or a database to reach.

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
PACKS = BACKEND_RAG_DIR / "backend" / "services" / "visa_engine" / "contracts" / "packs"
LEDGER_DIR = REPO_ROOT / "research" / "visa" / "2026-10-07-freshness-restamp-seq25"
EXPECTED_DIGEST = "603f777e5fdd8ffbd5824282593b6584893f39b0b6b192f59c4563ae6d9c9d11"  # pragma: allowlist secret
TRUST_STORE_JSON = json.dumps(
    [
        {
            "kid": "prod-2026-07-1",
            "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",  # pragma: allowlist secret
            "environment": "PRODUCTION",
            "valid_from": "2026-07-19T00:00:00Z",
            "valid_to": None,
            "revoked_at": None,
        }
    ]
)
DIGEST_PREFIX = "fold_pack_generic: seq-25 payload_sha256 = "


def _python() -> str:
    venv_python = BACKEND_RAG_DIR / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.is_file() else sys.executable


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND_RAG_DIR)
    env["VISA_ENGINE_TRUST_STORE_KEYS_JSON"] = TRUST_STORE_JSON
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            _python(),
            "-m",
            "backend.scripts.visa_engine.fold_pack_generic",
            "--anchor-source", str(PACKS / "rulepack-prod-024.source.json"),
            "--anchor-signed", str(PACKS / "rulepack-prod-024.signed.json"),
            "--ledger-dir", str(LEDGER_DIR),
            "--output", str(Path(tmp) / "out.json"),
            "--version", "2026.10.7",
            "--created-at", "2026-10-07T13:38:00Z",
            "--created-by", "agent.air-m5.backend-rag.visa-freshness-restamp.fold-2026-10-07",
            "--verified-by", "agent.air-m5.backend-rag.visa-freshness-restamp.live-recheck-2026-10-07",
        ]  # fmt: skip
        result = subprocess.run(
            cmd,
            cwd=BACKEND_RAG_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        print(result.stdout + result.stderr, file=sys.stderr)
        print(
            f"observe_visa_fold_generic: FAIL — fold exited {result.returncode}",
            file=sys.stderr,
        )
        return 1
    printed = [
        line[len(DIGEST_PREFIX) :]
        for line in result.stdout.splitlines()
        if line.startswith(DIGEST_PREFIX)
    ]
    if printed != [EXPECTED_DIGEST]:
        print(
            f"observe_visa_fold_generic: FAIL — printed digest {printed!r}, expected {EXPECTED_DIGEST}",
            file=sys.stderr,
        )
        return 1
    print(
        f"observe_visa_fold_generic: generic fold reproduces seq-25 {EXPECTED_DIGEST[:8]}…{EXPECTED_DIGEST[-4:]}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
