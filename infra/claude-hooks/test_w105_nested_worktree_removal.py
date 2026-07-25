#!/usr/bin/env python3
"""W105 nested-worktree removal — guilt+innocence with REAL git worktrees.

THE SCAR (2026-07-26). `_resolve_under_worktrees` truncated its verdict to the
FIRST segment under `.worktrees/`:

    return pathlib.Path(wt_root, rel.parts[0])

so removing `.worktrees/<outer>/.worktrees/<inner>` resolved to `<outer>`, and the
hook refused with `<outer>`'s name and `<outer>`'s dirtiness — for a nested worktree
that was brand-new and empty. `.worktrees/A/.worktrees/B` *has* `.worktrees/A` as a
path prefix but **is not** `.worktrees/A`: family #3, deciding on path SHAPE instead
of on the ENTITY the path names. It matters past the annoyance because the escape
the block message implies is `AGENT_WORKTREE_ENFORCEMENT=false`, which disarms the
guard wholesale — an over-match loud enough teaches people to turn the guard off.

THE TWIN (why this suite has more than the obvious two cases). Resolving to the
INNERMOST worktree, on its own, would open the under-match gemello W94 warns about:
`.worktrees/` is gitignored, so `git status` inside an OUTER worktree is blind to a
worktree nested in it — remove the outer and the nested one's uncommitted work dies
while the outer reads CLEAN. So `_unarmed_dirty_removal_target` now judges every
VICTIM of the removal — the named target plus everything `_worktrees_strictly_inside`
reports — and the composition case below pins exactly that.

Run:  python3 infra/claude-hooks/test_w105_nested_worktree_removal.py
      pytest infra/claude-hooks/test_w105_nested_worktree_removal.py -q
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT_SRC = HERE.parent.parent
HOOK_SRC = HERE / "worktree_isolation.py"


def _git(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=30)


def _run_hook(hook: pathlib.Path, cmd: str, cwd: str, repo_root: str) -> int:
    env = dict(os.environ)
    env["NUZ_REPO_ROOT"] = repo_root
    env.pop("AGENT_WORKTREE_ENFORCEMENT", None)
    env.pop("HOST_BOUNDARY_OFF", None)
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd}
    proc = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=20, env=env)
    return proc.returncode


def _build_repo(tmp: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    root = tmp / "main"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "agent_start.py").write_text("# signature\n")
    (root / "infra" / "claude-hooks").mkdir(parents=True)
    shutil.copy2(HOOK_SRC, root / "infra" / "claude-hooks" / "worktree_isolation.py")
    # `.worktrees/` gitignored exactly as in the real repo — that is WHY an outer
    # worktree's `git status` cannot see a nested one (the twin above).
    (root / ".gitignore").write_text(".worktrees/\n")
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t.t"], root)
    _git(["config", "user.name", "t"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "init"], root)
    return root, root / "infra" / "claude-hooks" / "worktree_isolation.py"


def _add_worktree(root: pathlib.Path, path: pathlib.Path, branch: str) -> pathlib.Path:
    _git(["worktree", "add", "-q", "-b", branch, str(path), "HEAD"], root)
    return path


def evaluate() -> list[str]:
    if not shutil.which("git"):
        return []  # no git → skip (treated as pass)
    fails: list[str] = []
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="w105_nested_"))
    try:
        root, hook = _build_repo(tmp)
        rr = str(root)

        # ---- INNOCENCE (the scar itself) ---------------------------------------
        # outer is DIRTY; the nested worktree inside it is CLEAN and brand-new.
        # Removing the nested one cannot touch outer's work → must be ALLOWED.
        outer = _add_worktree(root, root / ".worktrees" / "outer", "b/outer")
        (outer / "UNTRACKED.txt").write_text("outer's uncommitted work\n")
        nested = _add_worktree(root, outer / ".worktrees" / "nested", "b/nested")
        for cmd, desc in [
            (f"git worktree remove --force {nested}", "git worktree remove CLEAN nested"),
            (f"rm -rf {nested}", "rm -rf CLEAN nested"),
        ]:
            if _run_hook(hook, cmd, rr, rr) == 2:
                fails.append(f"BIT-INNOCENT (W105 over-match): {desc} inside a DIRTY outer "
                             "→ expected ALLOW")

        # ---- GUILT (the protection the truncation was paying for) --------------
        # 1. The dirty outer, named by its OWN exact path, is still BLOCKED.
        if _run_hook(hook, f"git worktree remove --force {outer}", rr, rr) != 2:
            fails.append("WENT-BLIND: remove DIRTY+unarmed outer by its own path "
                         "→ expected BLOCK")
        # 2. A subdirectory of a dirty worktree still resolves TO that worktree —
        #    `rm -rf <dirty-wt>/sub` is a removal of its content (the W80 reason the
        #    truncation existed). Innermost-resolution must not lose this.
        (outer / "sub").mkdir()
        if _run_hook(hook, f"rm -rf {outer / 'sub'}", rr, rr) != 2:
            fails.append("WENT-BLIND: rm -rf <DIRTY-worktree>/sub → expected BLOCK")

        # ---- GUILT, COMPOSITION (the under-match twin, W94's lesson) -----------
        # A CLEAN outer whose NESTED worktree is dirty. `.worktrees/` is gitignored,
        # so the outer's own `git status` is empty — the pre-fix code would have
        # allowed the removal and destroyed the nested worktree's work silently.
        clean_outer = _add_worktree(root, root / ".worktrees" / "clean_outer", "b/co")
        dirty_nested = _add_worktree(root, clean_outer / ".worktrees" / "dn", "b/dn")
        (dirty_nested / "UNTRACKED.txt").write_text("nested work that would die\n")
        # premise check: the outer really does read clean (else the case proves nothing)
        st = _git(["status", "--porcelain"], clean_outer)
        if any(ln.strip() for ln in st.stdout.splitlines()):
            fails.append("PREMISE BROKEN: outer worktree is not clean — the composition "
                         "case cannot prove what it claims")
        if _run_hook(hook, f"rm -rf {clean_outer}", rr, rr) != 2:
            fails.append("WENT-BLIND (composition): rm -rf a CLEAN outer holding a DIRTY "
                         "nested worktree → expected BLOCK (the nested work dies with it)")

        # ---- INNOCENCE, the other direction ------------------------------------
        # An entirely clean worktree with a clean nested one: nothing to lose.
        ok_outer = _add_worktree(root, root / ".worktrees" / "ok_outer", "b/ok")
        _add_worktree(root, ok_outer / ".worktrees" / "ok_nested", "b/okn")
        if _run_hook(hook, f"rm -rf {ok_outer}", rr, rr) == 2:
            fails.append("BIT-INNOCENT: rm -rf a CLEAN outer holding a CLEAN nested "
                         "worktree → expected ALLOW")
    finally:
        try:
            _git(["worktree", "prune"], tmp / "main")
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


def test_w105_nested_worktree_removal():
    fails = evaluate()
    assert not fails, "W105 nested-worktree removal regressions:\n" + "\n".join(fails)


if __name__ == "__main__":
    f = evaluate()
    if f:
        print(f"=== {len(f)} FAIL ===")
        for x in f:
            print("  [FAIL] " + x)
        sys.exit(1)
    print("=== W105 OK (nested removal allowed; outer, subdir and dirty-nested still blocked) ===")
    sys.exit(0)
