#!/usr/bin/env python3
"""observe_visa_portal_judge.py — bites: observation for the portal_judge lane.

# bites-observable — this script takes NO arguments: every path and command is a
# literal in this file, and all writing happens in a private temp directory, so
# nothing an invoker types can name a program to run, a file to write, or a
# database to reach (the bar `scripts/ci/bites_parse.py::_guard_observable_script`
# sets). No network, no Claude call: the judge is the deterministic `--judge fake`.

It copies the 2026-10-07 read ledger to a temp dir, rewrites it the way
``portal_read_receipt.py`` now writes it (one ``text/<8id>-<stamp>.txt`` per fetch),
drops its judgements, lets ``portal_judge.py --judge fake`` regenerate them from the
seq-24 source pack, then folds with ``fold_pack_generic`` against the signed seq-24
anchor and checks the stamp. Exit 0 and the final line prove the consumer (the fold)
accepts what the two tools write.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_RAG_DIR = REPO_ROOT / "apps" / "backend-rag"
LEDGER = REPO_ROOT / "research" / "visa" / "2026-10-07-freshness-restamp-seq25"
PACKS = "backend/services/visa_engine/contracts/packs/rulepack-prod-024"
EXPECTED_STAMP = "2026-10-07T13:32:18Z"
# The production PUBLIC key (the same literal the fold's tests pin); no secret.
TRUST_JSON = json.dumps(
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


def _python() -> str:
    venv = BACKEND_RAG_DIR / ".venv" / "bin" / "python3"
    return str(venv) if venv.is_file() else sys.executable


def _make_per_fetch(ledger: Path) -> None:
    for old in sorted((ledger / "text").glob("????????.txt")):
        old.rename(old.with_name(f"{old.stem}-20261007T133000Z.txt"))
    for path in ledger.glob("*-receipts.jsonl"):
        rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for row in rows:
            row["text_file"] = f"/dead/text/{row['source_record_id'][:8]}-20261007T133000Z.txt"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    for old in ledger.glob("*-judgements.jsonl"):
        old.unlink()


def _step(cmd: list[str], env: dict[str, str]) -> bool:
    done = subprocess.run(cmd, cwd=BACKEND_RAG_DIR, env=env, capture_output=True, text=True)
    print(done.stdout.strip().splitlines()[-1] if done.stdout.strip() else "(no output)")
    if done.returncode != 0:
        print((done.stderr or done.stdout).strip()[-600:], file=sys.stderr)
        print("observe_visa_portal_judge: FAILED", file=sys.stderr)
    return done.returncode == 0


def main() -> int:
    env = {**os.environ, "PYTHONPATH": ".", "VISA_ENGINE_TRUST_STORE_KEYS_JSON": TRUST_JSON}
    py = _python()
    with tempfile.TemporaryDirectory(prefix="observe-portal-judge-") as tmp:
        ledger = Path(tmp) / "ledger"
        output = Path(tmp) / "next.source.json"
        shutil.copytree(LEDGER, ledger)
        _make_per_fetch(ledger)
        judge = [py, "-m", "backend.scripts.visa_engine.portal_judge", "--pack", f"{PACKS}.source.json",
                 "--ledger-dir", str(ledger), "--reader", "observer", "--all", "--judge", "fake"]  # fmt: skip
        if not _step(judge, env):
            return 1
        # created_at is read AFTER the judge ran: the pack may not be dated before its evidence.
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fold = [py, "-m", "backend.scripts.visa_engine.fold_pack_generic", "--anchor-source", f"{PACKS}.source.json",
                "--anchor-signed", f"{PACKS}.signed.json", "--ledger-dir", str(ledger), "--output", str(output),
                "--created-at", created_at]  # fmt: skip
        if not _step(fold, env):
            return 1
        packed = json.loads(output.read_text(encoding="utf-8"))
        stamps = {r["verified_at"] for r in packed["source_records"] if r["authority_type"] == "OFFICIAL_PORTAL"}
        if stamps != {EXPECTED_STAMP}:
            print(f"observe_visa_portal_judge: FAILED stamps={sorted(stamps)}", file=sys.stderr)
            return 1
    print("observe_visa_portal_judge: fake judge regenerates an accepted ledger")
    return 0


if __name__ == "__main__":
    sys.exit(main())
