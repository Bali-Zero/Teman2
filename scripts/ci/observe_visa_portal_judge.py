#!/usr/bin/env python3
"""observe_visa_portal_judge.py — bites: observation for the portal_judge lane.

# bites-observable — this script takes NO arguments: every path and command is a
# literal in this file, and all writing happens in a private temp directory, so
# nothing an invoker types can name a program to run, a file to write, or a
# database to reach (the bar `scripts/ci/bites_parse.py::_guard_observable_script`
# sets). No network, no Claude call: the judge is the deterministic `--judge fake`.

It copies the 2026-10-07 read ledger to a temp dir, drops its judgements, lets
``portal_judge.py --judge fake`` regenerate them from the seq-24 source pack, then
asks ``fold_pack_seq25.attestation_instant`` to accept the regenerated ledger.
Exit 0 and the final line prove the consumer (the fold) accepts what the tool writes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
LEDGER = REPO_ROOT / "research" / "visa" / "2026-10-07-freshness-restamp-seq25"
PACK = "backend/services/visa_engine/contracts/packs/rulepack-prod-024.source.json"
FOLD_CHECK = (
    "import json,sys\n"
    "from datetime import datetime, timezone\n"
    "from pathlib import Path\n"
    "from backend.scripts.visa_engine import fold_pack_seq25 as f, portal_read_receipt as r\n"
    "pack = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))\n"
    "stamp = f.attestation_instant(f.load_ledger(Path(sys.argv[2])), r.portal_records(pack),"
    " now=datetime.now(timezone.utc))\n"
    "print('attestation_instant', stamp)\n"
)


def _python() -> str:
    venv = BACKEND_RAG_DIR / ".venv" / "bin" / "python3"
    return str(venv) if venv.is_file() else sys.executable


def main() -> int:
    env = {**os.environ, "PYTHONPATH": "."}
    py = _python()
    with tempfile.TemporaryDirectory(prefix="observe-portal-judge-") as tmp:
        ledger = Path(tmp) / "ledger"
        shutil.copytree(LEDGER, ledger)
        for old in ledger.glob("*-judgements.jsonl"):
            old.unlink()
        steps = (
            [py, "-m", "backend.scripts.visa_engine.portal_judge", "--pack", PACK, "--ledger-dir", str(ledger),
             "--reader", "observer", "--all", "--judge", "fake"],
            [py, "-c", FOLD_CHECK, PACK, str(ledger)],
        )  # fmt: skip
        for cmd in steps:
            done = subprocess.run(cmd, cwd=BACKEND_RAG_DIR, env=env, capture_output=True, text=True)
            print(done.stdout.strip().splitlines()[-1] if done.stdout.strip() else "(no output)")
            if done.returncode != 0:
                print(done.stderr.strip()[-600:], file=sys.stderr)
                print("observe_visa_portal_judge: FAILED", file=sys.stderr)
                return 1
    print("observe_visa_portal_judge: fake judge regenerates an accepted ledger")
    return 0


if __name__ == "__main__":
    sys.exit(main())
