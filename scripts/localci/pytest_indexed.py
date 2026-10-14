"""Runs inside a candidate container (kind "pytest"): indexes the frozen tree as a commit, as hosted's checkout is one, then runs pytest as a
CHILD. Tests that ask git for the tree (`git rev-parse --show-toplevel`, `git ls-files`) see a repository, and a test that reads its
parent process sees this wrapper, not the container's init (a parent of pid 1 reads as launchd to scripts/secrets_permissions_audit.py).

    python -I pytest_indexed.py <cfg.json>     cfg: {"root", "history", "tree_pack", "argv", "path_prefix"}; the siblings steps_driver.py and base/ sit beside it."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import steps_driver  # noqa: E402 — the BASE-built driver shipped beside this file


def main(cfg_path: str) -> int:
    cfg = json.loads(Path(cfg_path).read_text())
    steps_driver.index_tree(cfg["root"], cfg.get("history"), HERE / "base", cfg.get("tree_pack"))
    env = dict(os.environ)
    if cfg.get("path_prefix"):   # a bare `python3` inside the tests is hosted's interpreter too
        env["PATH"] = cfg["path_prefix"] + os.pathsep + env.get("PATH", "")
    return subprocess.run(cfg["argv"], cwd=cfg["root"], env=env).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
