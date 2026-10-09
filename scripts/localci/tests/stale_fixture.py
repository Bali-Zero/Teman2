"""A mirror whose main moved at known dates, with the BASE change_map and a two-flag matrix in it (B10 fixtures; no network)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REAL_MAP = Path(__file__).resolve().parents[2] / "ci" / "change_map.py"
MATRIX = "scripts/localci/contexts_matrix.yaml"
CTX_BACKEND, CTX_FRONTEND, CTX_ALWAYS, CTX_MCP = "Backend Tests (Python)", "Frontend Tests", "Always Runs", "MCP Tests"
LOCK, DOC, TSX = "apps/backend-rag/requirements.lock.txt", "docs/x.md", "apps/mouth/src/a.tsx"
MCP = "apps/nuzantara-mcp/nuzantara_mcp/x.py"   # selects mcp-tests and nothing else
MATRIX_YAML = f"""contexts:
  - name: "{CTX_BACKEND}"
    local: {{check: ctx.backend, runs_when: backend-tests}}
  - name: "{CTX_FRONTEND}"
    local: {{check: ctx.frontend, runs_when: frontend-tests}}
  - name: "{CTX_ALWAYS}"
    local: {{check: ctx.always}}
  - name: "{CTX_MCP}"
    local: {{check: ctx.mcp, runs_when: mcp-tests}}
"""
T0, T1, T2, T3 = "2026-10-05T00:00:00Z", "2026-10-06T04:36:00Z", "2026-10-07T10:00:00Z", "2026-10-08T12:00:00Z"
T_SIDE, T_MERGE = "2026-10-07T13:00:00Z", "2026-10-08T06:00:00Z"


def git(repo: Path, *args: str, when: str | None = None) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


def _commit(path: Path, files: dict, msg: str, when: str) -> str:
    for rel, body in files.items():
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text(body)
    git(path, "add", "-A")
    git(path, "commit", "-qm", msg, when=when)
    return git(path, "rev-parse", "HEAD")


def make_main(path: Path) -> dict:
    """c0 (T0: the classifier and the matrix) -> c1 (T1: a lock file) -> c2 (T2: a doc) -> m (T_MERGE: merges `side`, whose one commit
    s, dated T_SIDE, is an mcp-only source) -> c3 (T3: a mouth source); base = c3. The first-parent line is c0 c1 c2 m c3: s is on it
    only through m, and s is dated BEFORE m, so a history walk that is not first-parent finds s where main had not yet taken it."""
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    shas = {"c0": _commit(path, {"scripts/ci/change_map.py": REAL_MAP.read_text(), MATRIX: MATRIX_YAML, "README.md": "r\n"}, "c0", T0),
            "c1": _commit(path, {LOCK: "pin==2\n"}, "c1", T1), "c2": _commit(path, {DOC: "d\n"}, "c2", T2)}
    git(path, "checkout", "-q", "-b", "side")
    shas["s"] = _commit(path, {MCP: "x\n"}, "s", T_SIDE)
    git(path, "checkout", "-q", "main")
    git(path, "merge", "--no-ff", "-q", "-m", "m", "side", when=T_MERGE)
    shas["m"] = git(path, "rev-parse", "HEAD")
    shas["c3"] = _commit(path, {TSX: "x\n"}, "c3", T3)
    return {**shas, "base": shas["c3"]}
