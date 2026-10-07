#!/usr/bin/env python3
"""Run one required context's steps inside the candidate container and write one junit <testcase> per step, in plan order.

Runner-owned: runner.py injects this file and its steps config at /cfg (never from the candidate tree) and pins its sha256 in
the plan. Usage: python -I steps_driver.py <steps.json> <junit.xml>

Exit 0 = every executed step returned 0 · 1 = at least one step failed · 3 = a step could not start and none failed ·
2 = the driver itself broke (no verdict). Every step runs even after a failure: the junit is the per-step evidence.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

GIT_ID = {"GIT_AUTHOR_NAME": "localci", "GIT_AUTHOR_EMAIL": "localci@invalid", "GIT_COMMITTER_NAME": "localci",
          "GIT_COMMITTER_EMAIL": "localci@invalid"}


def index_tree(root: str) -> None:
    """Steps that call `git ls-files`/`git diff` see the frozen tree as one commit. The tar carries tracked blobs only, so
    `add -f` indexes exactly the candidate's tracked set (ignored-but-tracked files included)."""
    env = {**os.environ, **GIT_ID}
    for argv in (["git", "init", "-q"], ["git", "add", "-A", "-f"], ["git", "commit", "-q", "--no-verify", "-m", "localci candidate tree"]):
        subprocess.run(argv, cwd=root, env=env, check=True, stdout=subprocess.DEVNULL)


def main(cfg_path: str, junit_path: str) -> int:
    cfg = json.loads(Path(cfg_path).read_text())
    root = cfg["root"]
    if cfg.get("git_index"):
        index_tree(root)
    gh = Path("/tmp/localci-gh")
    gh.mkdir(parents=True, exist_ok=True)
    suite = ET.Element("testsuite", name=cfg["context"])
    failed = blocked = skipped = 0
    for i, st in enumerate(cfg["steps"]):
        case = ET.SubElement(suite, "testcase", classname="localci.ctx", name=st["name"])
        if "not_applicable" in st:
            skipped += 1
            ET.SubElement(case, "skipped", message=st["not_applicable"])
            continue
        env = {**os.environ, **cfg.get("env", {}), **st.get("env", {}),
               **{k: str(gh / f"{k.lower()}-{i}") for k in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")}}   # written, never read back
        Path(env.get("RUNNER_TEMP", "/tmp")).mkdir(parents=True, exist_ok=True)
        print(f"##[localci] step {i}: {st['name']}", flush=True)
        t0 = time.monotonic()
        try:
            rc = subprocess.run(st["argv"], cwd=os.path.join(root, st.get("cwd") or "."), env=env).returncode
        except OSError as e:
            rc = None
            blocked += 1
            ET.SubElement(case, "error", message=f"could not start: {type(e).__name__}: {e}")
        else:
            if rc != 0:
                failed += 1
                ET.SubElement(case, "failure", message=f"rc={rc}")
        case.set("time", f"{time.monotonic() - t0:.3f}")
        print(f"##[localci] step {i} rc={rc}", flush=True)
    suite.set("tests", str(len(cfg["steps"])))
    suite.set("failures", str(failed))
    suite.set("errors", str(blocked))
    suite.set("skipped", str(skipped))
    ET.ElementTree(suite).write(junit_path, encoding="utf-8", xml_declaration=True)
    return 1 if failed else 3 if blocked else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1], sys.argv[2]))
    except Exception as e:  # noqa: BLE001 — a broken driver is no verdict (rc 2), never a failed step
        print(f"##[localci] driver error: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        sys.exit(2)
