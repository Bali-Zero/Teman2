#!/usr/bin/env python3
"""observe_visa_gold_replay.py — bites: observation for the gold-corpus drift lane.

# bites-observable — this script takes NO arguments: the one command it runs is a
# literal below (the in-tree gold replay driver, offline mode), and its output goes
# to a fresh temporary directory, so nothing an invoker types can name a program to
# run, a file to write or a database to reach.

Runs the Visa Oracle gold replay driver ``--offline`` against the highest signed
production pack on disk and exits 0 only if at least 18 of the 20 personas match and
the unexplained divergences are exactly personas 9 and 10 (the ledgered engine gap:
no production rule reads ``process.application_channel``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
MIN_MATCHES = 18
EXPECTED_UNEXPLAINED = {9, 10}


def _backend_rag_python() -> str:
    venv_python = BACKEND_RAG_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND_RAG_DIR)
    with tempfile.TemporaryDirectory(prefix="gold-replay-") as tmp:
        out = Path(tmp) / "report.json"
        cmd = [
            _backend_rag_python(),
            "-m",
            "backend.scripts.visa_engine.gold_replay_driver",
            "--offline",
            "--out",
            str(out),
        ]
        print(
            "observe_visa_gold_replay: running gold_replay_driver --offline (cwd=apps/backend-rag)"
        )
        subprocess.run(
            cmd,
            cwd=BACKEND_RAG_DIR,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if not out.is_file():
            print("observe_visa_gold_replay: the driver wrote no report")
            return 1
        report = json.loads(out.read_text(encoding="utf-8"))

    summary = report["summary"]
    unexplained = {
        row["persona_id"]
        for row in report["personas"]
        if row["divergence"]
        and (not isinstance(row["explanation"], str) or not row["explanation"].strip())
    }
    print(
        f"observe_visa_gold_replay: pack sequence={report['pack']['sequence']} "
        f"matches={summary['personas_match']}/{summary['personas_total']} "
        f"unexplained={sorted(unexplained)}"
    )
    if summary["personas_match"] < MIN_MATCHES or unexplained != EXPECTED_UNEXPLAINED:
        print("observe_visa_gold_replay: gold replay drifted from the ledgered state")
        return 1
    print(
        "observe_visa_gold_replay: offline gold replay 18/20, "
        "unexplained = personas 9 and 10 (engine gap, ledgered)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
