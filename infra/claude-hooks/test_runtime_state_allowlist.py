#!/usr/bin/env python3
"""Runtime-state allowlist for the ff-only pull exception — guilt+innocence.

PENDING-ARMS "Pro main self-align strutturalmente chiuso" (opened 2026-07-06),
iteration 5: Pro carries 3 tracked files continuously rewritten by live
runtime processes (shared/escalations_pro.jsonl, published_articles.json,
docs/AUTOMATIONS_REFERENCE.md). Under the plain tracked-clean probe that
permanent dirt shut `_only_ffonly_pull`'s exception forever on Pro. The
allowlist (infra/claude-hooks/runtime_state_allowlist.json) declares those
SPECIFIC paths, machine-scoped, as expected residue.

W91 lesson applied to the allowlist ITSELF (an exception is a guard with an
inverted sign — it wants its own guilt+innocence, not just a new "yes"):

  INNOCENCE — a tree dirty with EXACTLY the 3 declared Pro paths (and nothing
              else) still reports clean-enough → exception opens.
  GUILT     — a tree dirty with any ONE additional non-allowlisted tracked
              file (even alongside the 3 declared ones) reports dirty →
              exception stays shut. A rename touching an allowlisted name is
              ALSO guilt (fail-closed: the rename status line names two
              paths, never a clean single-path match). Machine-scoping:
              the same 3 paths on a machine NOT in ["pro"] do not match
              (a broken/missing allowlist file — or wrong machine — is
              guilt too, same as the historical all-or-nothing probe).

    python3 infra/claude-hooks/test_runtime_state_allowlist.py
Exit 0 = allowlist behaves on both polarities. Exit 1 = regression.

Reference: cicatrix-superscar.md #3 (W91 lesson) · registry.json ·
infra/claude-hooks/runtime_state_allowlist.json · scripts/lint_home_fork.py
machine_label() (mirrored convention).
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("wi_allowlist", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _git(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(_GIT_ENV)
    env["HOME"] = str(repo)
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)


def _write_allowlist(path: pathlib.Path, entries: list[dict]) -> None:
    path.write_text(json.dumps({"_doc": "test fixture", "entries": entries}))


def main() -> int:
    mod = _load_module()
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td) / "fixture"
        repo.mkdir()
        _git(repo, "init", "-q")
        (repo / "shared").mkdir()
        (repo / "docs").mkdir()
        (repo / "shared" / "escalations_pro.jsonl").write_text("{}\n")
        (repo / "published_articles.json").write_text("[]\n")
        (repo / "docs" / "AUTOMATIONS_REFERENCE.md").write_text("# ref\n")
        (repo / "apps.py").write_text("x = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "init")

        mod.REPO_ROOT = str(repo)
        allowlist_fixture = repo / "allowlist.json"
        mod.RUNTIME_STATE_ALLOWLIST_PATH = allowlist_fixture
        _write_allowlist(allowlist_fixture, [
            {"path": "shared/escalations_pro.jsonl", "machines": ["pro"]},
            {"path": "published_articles.json", "machines": ["pro"]},
            {"path": "docs/AUTOMATIONS_REFERENCE.md", "machines": ["pro"]},
        ])
        mod._machine_label = lambda hostname=None: "pro"

        # ---- baseline: truly clean tree → probe True (unchanged historical case)
        if not mod._main_tree_tracked_clean():
            failures.append("BASELINE: clean fixture tree reported dirty")

        # ---- INNOCENCE 1: exactly the 3 declared paths dirty → still "clean enough"
        (repo / "shared" / "escalations_pro.jsonl").write_text('{"new": true}\n')
        (repo / "published_articles.json").write_text('[{"id": 1}]\n')
        (repo / "docs" / "AUTOMATIONS_REFERENCE.md").write_text("# ref\nupdated\n")
        if not mod._main_tree_tracked_clean():
            failures.append("INNOCENCE: exactly-3-declared-dirty wrongly reports dirty")

        # ---- INNOCENCE 2: only ONE of the 3 dirty (subset) → still clean enough
        _git(repo, "checkout", "--", "published_articles.json", "docs/AUTOMATIONS_REFERENCE.md")
        if not mod._main_tree_tracked_clean():
            failures.append("INNOCENCE: single-declared-file-dirty wrongly reports dirty")
        _git(repo, "checkout", "--", "shared/escalations_pro.jsonl")  # reset for next cases

        # ---- GUILT 1: the 3 declared dirty PLUS one non-allowlisted tracked file
        (repo / "shared" / "escalations_pro.jsonl").write_text('{"new": true}\n')
        (repo / "apps.py").write_text("x = 2\n")
        if mod._main_tree_tracked_clean():
            failures.append("GUILT: declared-dirty + 1 extra non-allowlisted file wrongly reports clean")
        _git(repo, "checkout", "--", "apps.py", "shared/escalations_pro.jsonl")

        # ---- GUILT 2: a non-allowlisted file dirty ALONE (sanity — unchanged historical behavior)
        (repo / "apps.py").write_text("x = 3\n")
        if mod._main_tree_tracked_clean():
            failures.append("GUILT: non-allowlisted file dirty alone wrongly reports clean")
        _git(repo, "checkout", "--", "apps.py")

        # ---- GUILT 3: a RENAME touching an allowlisted name → fail-closed (never eligible)
        _git(repo, "mv", "published_articles.json", "published_articles_renamed.json")
        if mod._main_tree_tracked_clean():
            failures.append("GUILT: rename touching an allowlisted name wrongly reports clean")
        _git(repo, "mv", "published_articles_renamed.json", "published_articles.json")

        # ---- GUILT 4: machine scoping — same 3 declared-dirty files, WRONG machine label
        (repo / "shared" / "escalations_pro.jsonl").write_text('{"new": true}\n')
        mod._machine_label = lambda hostname=None: "m5"
        if mod._main_tree_tracked_clean():
            failures.append("GUILT: machine-scoped allowlist wrongly applies on a non-pro machine")
        mod._machine_label = lambda hostname=None: "pro"
        _git(repo, "checkout", "--", "shared/escalations_pro.jsonl")

        # ---- GUILT 5: allowlist file missing/unparseable → fail-closed on dirty tree
        mod.RUNTIME_STATE_ALLOWLIST_PATH = repo / "does-not-exist.json"
        (repo / "shared" / "escalations_pro.jsonl").write_text('{"new": true}\n')
        if mod._main_tree_tracked_clean():
            failures.append("GUILT: missing allowlist file wrongly opens on a dirty tree")
        _git(repo, "checkout", "--", "shared/escalations_pro.jsonl")
        mod.RUNTIME_STATE_ALLOWLIST_PATH = allowlist_fixture

        # ---- end-to-end integration: _only_ffonly_pull + allowlist-aware probe
        # together decide the SAME way the live main() does at the call site.
        (repo / "shared" / "escalations_pro.jsonl").write_text('{"new": true}\n')
        cmd_scan = mod._strip_noise("git pull --ff-only origin main")
        exception_opens = mod._only_ffonly_pull(cmd_scan) and mod._main_tree_tracked_clean()
        if not exception_opens:
            failures.append("INTEGRATION: ff-only pull exception does not open on Pro with only declared-dirty files")
        _git(repo, "checkout", "--", "shared/escalations_pro.jsonl")

    if failures:
        print("FAIL — runtime-state allowlist regressions:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK — runtime-state allowlist opens the ff-only exception ONLY for declared "
          "Pro paths (2 innocence + 5 guilt + 1 integration + 1 baseline)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
