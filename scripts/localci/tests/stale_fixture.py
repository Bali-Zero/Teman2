"""A mirror whose main moved at known dates, with the BASE change_map and a two-flag matrix in it (B10 fixtures; no network)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REAL_MAP = Path(__file__).resolve().parents[2] / "ci" / "change_map.py"
MATRIX = "scripts/localci/contexts_matrix.yaml"
CTX_BACKEND, CTX_FRONTEND, CTX_ALWAYS = "Backend Tests (Python)", "Frontend Tests", "Always Runs"
LOCK, DOC, TSX = "apps/backend-rag/requirements.lock.txt", "docs/x.md", "apps/mouth/src/a.tsx"
MATRIX_YAML = f"""contexts:
  - name: "{CTX_BACKEND}"
    local: {{check: ctx.backend, runs_when: backend-tests}}
  - name: "{CTX_FRONTEND}"
    local: {{check: ctx.frontend, runs_when: frontend-tests}}
  - name: "{CTX_ALWAYS}"
    local: {{check: ctx.always}}
"""
T0, T1, T2, T3 = "2026-10-05T00:00:00Z", "2026-10-06T04:36:00Z", "2026-10-07T10:00:00Z", "2026-10-08T12:00:00Z"


def git(repo: Path, *args: str, when: str | None = None) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout.strip()


def make_main(path: Path) -> dict:
    """c0 (T0: the classifier and the matrix) -> c1 (T1: a lock file) -> c2 (T2: a doc) -> c3 (T3: a mouth source); base = c3."""
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    shas = {}
    for key, when, files in (("c0", T0, {"scripts/ci/change_map.py": REAL_MAP.read_text(), MATRIX: MATRIX_YAML, "README.md": "r\n"}),
                             ("c1", T1, {LOCK: "pin==2\n"}), ("c2", T2, {DOC: "d\n"}), ("c3", T3, {TSX: "x\n"})):
        for rel, body in files.items():
            (path / rel).parent.mkdir(parents=True, exist_ok=True)
            (path / rel).write_text(body)
        git(path, "add", "-A")
        git(path, "commit", "-qm", key, when=when)
        shas[key] = git(path, "rev-parse", "HEAD")
    return {**shas, "base": shas["c3"]}
