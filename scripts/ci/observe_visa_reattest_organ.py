#!/usr/bin/env python3
"""observe_visa_reattest_organ.py — bites: observation for the weekly re-attestation organ.

# bites-observable — this script takes NO arguments: every path and command below is a
# literal in this file; all git work happens in two tempdirs this script creates, with the
# user's git config and hooks switched off. No network, no gh, no Telegram.

Builds a temp "origin" holding only the committed seq-24 signed pair, then runs the organ
in --offline --skip-judge mode on a COPY of the 2026-10-07 read ledger. The organ must
create its own worktree and branch, fold the candidate, commit and push it to the temp
origin and print the PR title and body. Exits 0 only if the candidate on that branch
carries the committed seq-25 payload digest and the PR text names it, with a Bites: line.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKS_REL = "apps/backend-rag/backend/services/visa_engine/contracts/packs"
LEDGER = REPO_ROOT / "research" / "visa" / "2026-10-07-freshness-restamp-seq25"
EXPECTED_DIGEST = "603f777e5fdd8ffbd5824282593b6584893f39b0b6b192f59c4563ae6d9c9d11"  # pragma: allowlist secret
BRANCH = "organ/visa-reattest/24-2026-10-07"
CANDIDATE = f"{PACKS_REL}/rulepack-prod-025.source.json"
NOTE = "research/visa/2026-10-07-organ-reattest-seq25-attestation.md"


def _fail(msg: str) -> int:
    print(f"observe_visa_reattest_organ: FAIL — {msg}", file=sys.stderr)
    return 1


def _git(env: dict[str, str], cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(cwd), "-c", "user.name=observer", "-c", "user.email=o@o", "-c", "gc.auto=0", "-c", "maintenance.auto=false", *args],
                          env=env, capture_output=True, text=True, check=True)
    return done.stdout


def main() -> int:
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_name:
        tmp = Path(tmp_name)
        origin, shared = tmp / "origin.git", tmp / "shared"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], env=env, check=True, capture_output=True)
        _git(env, origin, "config", "receive.autogc", "false")
        subprocess.run(["git", "clone", str(origin), str(shared)], env=env, check=True, capture_output=True)
        (shared / PACKS_REL).mkdir(parents=True)
        for name in ("rulepack-prod-024.signed.json", "rulepack-prod-024.source.json"):
            shutil.copy(REPO_ROOT / PACKS_REL / name, shared / PACKS_REL / name)
        _git(env, shared, "add", "-A")
        _git(env, shared, "commit", "-m", "seed seq-24")
        _git(env, shared, "push", "origin", "HEAD:refs/heads/main")
        ledger = tmp / "ledger-copy"
        shutil.copytree(LEDGER, ledger)
        cmd = [
            sys.executable, str(REPO_ROOT / "scripts" / "visa_reattestation_organ.py"),
            "--offline", "--skip-judge", "--ledger-dir", str(ledger),
            "--repo", str(shared), "--code-root", str(REPO_ROOT),
            "--state-dir", str(tmp / "state"), "--board", str(tmp / "board.jsonl"),
            "--now", "2026-10-07T13:38:00Z", "--fold-created-at", "2026-10-07T13:38:00Z",
            "--fold-created-by", "agent.air-m5.backend-rag.visa-freshness-restamp.fold-2026-10-07",
            "--fold-verified-by", "agent.air-m5.backend-rag.visa-freshness-restamp.live-recheck-2026-10-07",
        ]  # fmt: skip
        done = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        if done.returncode != 0:
            print(done.stdout + done.stderr, file=sys.stderr)
            return _fail(f"organ exited {done.returncode}")
        plan, _ = json.JSONDecoder().raw_decode(done.stdout)
        body, title = plan.get("pr_body", ""), plan.get("pr_title", "")
        if "candidate seq-25 (unsigned)" not in title or "Bites:" not in body or EXPECTED_DIGEST not in body:
            return _fail(f"PR text lacks title/Bites/digest: {title!r}")
        candidate = json.loads(_git(env, origin, "show", f"{BRANCH}:{CANDIDATE}"))
        if candidate.get("sequence") != 25 or "signature" in candidate:
            return _fail("candidate on the organ branch is not an unsigned seq-25 source")
        note = _git(env, origin, "show", f"{BRANCH}:{NOTE}")
        if "adversarial_review: pending-session" not in note:
            return _fail("attestation note lacks the pending-session review field")
        if _git(env, shared, "status", "--porcelain").strip():
            return _fail("the shared checkout was written to")
    print(f"observe_visa_reattest_organ: offline run produced unsigned seq-25 candidate on {BRANCH}, "
          f"digest {EXPECTED_DIGEST[:8]}…{EXPECTED_DIGEST[-4:]}, PR text carries Bites:")
    return 0


if __name__ == "__main__":
    sys.exit(main())
