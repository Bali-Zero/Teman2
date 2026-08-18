#!/usr/bin/env python3
"""W119 regression test — cross-line argument bleed in the removal/write regexes.

THE SCAR (2026-08-18, found live during an unrelated node_modules repair session,
NOT by adversarial fuzzing). `RM_RF_RE`, `WT_REMOVE_GIT_RE`, and `CPMV_RE` each
collect their arguments with a repeated capture group of the shape
`(?:\\s+TOKEN)+`. `\\s` matches a literal newline, and a single Bash tool call is
routinely SEVERAL shell statements joined by bare newlines — which bash itself
treats as statement separators, exactly like `;` — but these regexes did not.
The capture group kept consuming tokens PAST the end of the `rm`/`cp`/`git
worktree remove` line, across every following line, until it hit the first
`|`/`;`/`&`/`)` character anywhere further down the whole command string.

Live incident: a 9-line command whose FIRST line was `rm -f "$VAR/pkg"` (a
harmless removal of a broken symlink inside gitignored `node_modules/`, itself
noise-stripped to `rm -f ""` since the quoted variable reference contributes no
literal text) and whose SIXTH line was an entirely unrelated
`cd /repo/.worktrees/<this-worktree>/apps/mouth`. That `cd` TARGET got vacuumed
up by `RM_RF_RE`'s capture group as if it were an `rm` argument, naming the
live, dirty (mid-repair), unarmed worktree as a removal victim — blocking the
whole harmless command with "WORKTREE REMOVAL BLOCKED (dirty + unarmed — scar
W80)" while the actual `rm` target was a gitignored build artifact three levels
removed from anything W80 exists to protect.

Family #3 (guard-over-match), 9th instance in this file. The axis here is
neither "form vs entity" (W105/W109) nor "substring vs word-boundary" (W85) —
it is a missing STATEMENT BOUNDARY: the regex's own token-separator character
class did not encode the same "a token never spans a bare newline" invariant
that `_strip_noise`'s quote-stripping already had to learn the hard way (W84,
"the char-class MUST exclude newline" — this is that lesson applied to a
different regex family in the SAME file).

`CPMV_RE` carries the identical defect independently (a `cp`/`mv` line can
misattribute a LATER, unrelated line's path as its own destination, risking a
false `_write_hits_main` block on an otherwise harmless multi-line script) and
is fixed the same way; `WT_REMOVE_GIT_RE` likewise.

Fix: confine the inter-token separator inside all three repeated groups to
same-line whitespace (`[ \\t]+`, no `\\n`) instead of `\\s+`.

Run:  python3 infra/claude-hooks/test_w119_multiline_token_bleed.py
      pytest infra/claude-hooks/test_w119_multiline_token_bleed.py -q
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
HOOK_SRC = HERE / "worktree_isolation.py"


def _git(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=30)


def _run_hook(hook: pathlib.Path, cmd: str, cwd: str, repo_root: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["NUZ_REPO_ROOT"] = repo_root
    env.pop("AGENT_WORKTREE_ENFORCEMENT", None)
    env.pop("HOST_BOUNDARY_OFF", None)
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd}
    proc = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=20, env=env)
    return proc.returncode, proc.stderr


def _build_repo(tmp: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    root = tmp / "main"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "agent_start.py").write_text("# signature\n")
    (root / "infra" / "claude-hooks").mkdir(parents=True)
    shutil.copy2(HOOK_SRC, root / "infra" / "claude-hooks" / "worktree_isolation.py")
    (root / ".gitignore").write_text(".worktrees/\nnode_modules/\n")
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t.t"], root)
    _git(["config", "user.name", "t"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "init"], root)
    return root, root / "infra" / "claude-hooks" / "worktree_isolation.py"


def _add_worktree(root: pathlib.Path, path: pathlib.Path, branch: str) -> pathlib.Path:
    _git(["worktree", "add", "-q", "-b", branch, str(path), "HEAD"], root)
    return path


def _rm_bleed_case() -> list[str]:
    """The exact live incident, reproduced with a real dirty+unarmed worktree:
    a harmless `rm -f` of a gitignored path on line 1, an unrelated `cd` into
    a dirty worktree on a LATER line. Pre-fix this blocks; must now ALLOW."""
    if not shutil.which("git"):
        return []
    fails: list[str] = []
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="w119_rm_"))
    try:
        root, hook = _build_repo(tmp)
        rr = str(root)
        dirty = _add_worktree(root, root / ".worktrees" / "dirty", "b/dirty")
        (dirty / "UNTRACKED.txt").write_text("uncommitted work that must not be lost\n")
        (root / "node_modules").mkdir()
        junk = root / "node_modules" / "broken-symlink"
        junk.symlink_to("/nonexistent-target")

        # Line 1: harmless rm of a gitignored dangling symlink (noise-stripped
        # quotes contribute nothing real). Line 6: unrelated `cd` into the
        # DIRTY worktree — this is the token RM_RF_RE's old capture group used
        # to bleed into.
        live_repro = (
            f'VAR="{junk}"\n'
            'OTHER="unrelated"\n'
            'test -f "$VAR" && echo yes || echo no\n'
            'rm -f "$VAR"\n'
            'ln -s /tmp/target "$VAR"\n'
            'echo "=== next ==="\n'
            f'cd {dirty}\n'
            'somebinary --flag > /tmp/out.log 2>&1\n'
            'echo done'
        )
        rc, err = _run_hook(hook, live_repro, str(dirty), rr)
        if rc == 2:
            fails.append(
                "BIT-INNOCENT (W119 rm bleed): a harmless line-1 `rm -f` on a "
                "gitignored path, followed by an UNRELATED later-line `cd` into "
                f"a dirty worktree, was blocked → expected ALLOW. stderr: {err[:300]}"
            )

        # GUILT (same repo, same worktree): a SINGLE-LINE `rm -rf` naming the
        # dirty worktree directly must still block — the fix must not have
        # gone blind on the real case.
        rc2, _ = _run_hook(hook, f"rm -rf {dirty}", rr, rr)
        if rc2 != 2:
            fails.append("WENT-BLIND (W119 rm bleed, guilt): a single-line "
                         "`rm -rf <dirty-unarmed-worktree>` must still block")

        # GUILT: same-line multi-flag rm -rf must still fully capture and block
        # (confirms the fix narrowed the SEPARATOR, not the token set).
        rc3, _ = _run_hook(hook, f"rm -rf --interactive=never {dirty}", rr, rr)
        if rc3 != 2:
            fails.append("WENT-BLIND (W119 rm bleed, same-line multi-flag): "
                         "`rm -rf --interactive=never <dirty-wt>` must still block")
    finally:
        try:
            _git(["worktree", "prune"], tmp / "main")
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


def _cpmv_bleed_case() -> list[str]:
    """Same defect, CPMV_RE / _write_hits_main channel: a harmless cp on line 1,
    an unrelated later line whose path lands inside the MAIN checkout, must not
    have that later path misattributed as the cp's own destination."""
    if not shutil.which("git"):
        return []
    fails: list[str] = []
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="w119_cpmv_"))
    try:
        root, hook = _build_repo(tmp)
        rr = str(root)
        wt = _add_worktree(root, root / ".worktrees" / "wt", "b/wt")

        # Line 1: cp entirely within /tmp (never touches main). Line 3: an
        # unrelated `cd` into the MAIN checkout — CPMV_RE's old capture group
        # would bleed into this and misreport it as the cp's own destination.
        # `_extract_write_targets` takes ONLY THE LAST swept token as the
        # destination (`toks[-1]`), so the repro must end right at the `cd`
        # target — a trailing line would just become a new (wrong) last token
        # and mask the very defect this case exists to catch.
        live_repro = (
            "cp /tmp/a /tmp/b\n"
            'echo "next"\n'
            f"cd {root}"
        )
        rc, err = _run_hook(hook, live_repro, str(wt), rr)
        if rc == 2:
            fails.append(
                "BIT-INNOCENT (W119 cpmv bleed): a harmless line-1 `cp` entirely "
                "under /tmp, followed by an UNRELATED later-line `cd` into the "
                f"main checkout, was blocked → expected ALLOW. stderr: {err[:300]}"
            )

        # GUILT: a genuine same-line write into main via cp must still block.
        rc2, _ = _run_hook(hook, f"cp /tmp/src {root}/scripts/hijack.py", str(wt), rr)
        if rc2 != 2:
            fails.append("WENT-BLIND (W119 cpmv bleed, guilt): a single-line "
                         "`cp /tmp/src <main>/scripts/hijack.py` must still block")
    finally:
        try:
            _git(["worktree", "prune"], tmp / "main")
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


def _wt_remove_bleed_case() -> list[str]:
    """Same defect, WT_REMOVE_GIT_RE channel: `git worktree remove <clean>` on
    line 1, an unrelated later line naming a DIRTY worktree, must not have that
    later path misattributed as an additional removal target."""
    if not shutil.which("git"):
        return []
    fails: list[str] = []
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="w119_wtrm_"))
    try:
        root, hook = _build_repo(tmp)
        rr = str(root)
        clean = _add_worktree(root, root / ".worktrees" / "clean", "b/clean")
        dirty = _add_worktree(root, root / ".worktrees" / "dirty", "b/dirty")
        (dirty / "UNTRACKED.txt").write_text("uncommitted\n")

        live_repro = (
            f"git worktree remove --force {clean}\n"
            'echo "next"\n'
            f"cd {dirty}\n"
            "somebinary --flag"
        )
        rc, err = _run_hook(hook, live_repro, str(root), rr)
        if rc == 2:
            fails.append(
                "BIT-INNOCENT (W119 wt-remove bleed): removing a CLEAN worktree "
                "on line 1, followed by an UNRELATED later-line `cd` into a "
                "DIFFERENT dirty worktree, was blocked → expected ALLOW "
                f"(the dirty one was never named for removal). stderr: {err[:300]}"
            )

        # GUILT: naming the dirty worktree directly for removal must still block.
        rc2, _ = _run_hook(hook, f"git worktree remove --force {dirty}", rr, rr)
        if rc2 != 2:
            fails.append("WENT-BLIND (W119 wt-remove bleed, guilt): "
                         "`git worktree remove --force <dirty-unarmed-wt>` "
                         "must still block")
    finally:
        try:
            _git(["worktree", "prune"], tmp / "main")
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


def test_w119_rm_bleed():
    fails = _rm_bleed_case()
    assert not fails, "W119 rm cross-line bleed regressions:\n" + "\n".join(fails)


def test_w119_cpmv_bleed():
    fails = _cpmv_bleed_case()
    assert not fails, "W119 cp/mv cross-line bleed regressions:\n" + "\n".join(fails)


def test_w119_wt_remove_bleed():
    fails = _wt_remove_bleed_case()
    assert not fails, "W119 worktree-remove cross-line bleed regressions:\n" + "\n".join(fails)


if __name__ == "__main__":
    f = _rm_bleed_case() + _cpmv_bleed_case() + _wt_remove_bleed_case()
    if f:
        print(f"=== {len(f)} FAIL ===")
        for x in f:
            print("  [FAIL] " + x)
        sys.exit(1)
    print("=== W119 OK (cross-line token bleed fixed on rm/cp-mv/worktree-remove; "
          "same-line multi-token capture and single-line guilt cases unaffected) ===")
    sys.exit(0)
