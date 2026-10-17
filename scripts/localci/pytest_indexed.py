"""Runs inside a candidate container (kind "pytest"): indexes the frozen tree as a commit, as hosted's checkout is one, then runs pytest as a
CHILD. Tests that ask git for the tree (`git rev-parse --show-toplevel`, `git ls-files`) see a repository, and a test that reads its
parent process sees this wrapper, not the container's init (a parent of pid 1 reads as launchd to scripts/secrets_permissions_audit.py).

    python -I pytest_indexed.py <cfg.json>     cfg: {"root", "history", "tree_pack", "argv", "path_prefix", "install", "home_dirs"}; the siblings steps_driver.py and base/ sit beside it.
    `install` = [[cwd under root, argv], ...] run before pytest (hosted's sweep installs its dependencies first); one that fails ends the run with INSTALL_RC, no verdict.
    `home_dirs` = directories created under $HOME first: hosted's whole-directory collection imports test_profile_monitor_wrapper_bind.py, which makes ~/logs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

INSTALL_RC = 97   # runner.INSTALL_RC (this file ships alone into the sandbox and cannot import it; a test pins the two together)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import steps_driver  # noqa: E402 — the BASE-built driver shipped beside this file


def main(cfg_path: str) -> int:
    cfg = json.loads(Path(cfg_path).read_text())
    steps_driver.index_tree(cfg["root"], cfg.get("history"), HERE / "base", cfg.get("tree_pack"))
    env = dict(os.environ)
    if cfg.get("path_prefix"):   # a bare `python3` inside the tests is hosted's interpreter too
        env["PATH"] = cfg["path_prefix"] + os.pathsep + env.get("PATH", "")
    for rel in cfg.get("home_dirs") or []:
        (Path(os.path.expanduser("~")) / rel).mkdir(parents=True, exist_ok=True)
    for cwd, argv in cfg.get("install") or []:
        if (rc := subprocess.run(argv, cwd=os.path.join(cfg["root"], cwd), env=env).returncode):
            print(f"# env install failed rc={rc}: {' '.join(argv)} — no verdict on the candidate", flush=True)
            return INSTALL_RC
    return subprocess.run(cfg["argv"], cwd=cfg["root"], env=env).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
