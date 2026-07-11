#!/usr/bin/env python3
"""Tilde/env blind-spot in `_effective_git_target` — guilt+innocence suite.

Found 2026-07-06 by the W85 live guilt-probe: `git -C ~/Desktop/nuzantara
stash push` PASSED the live hook while the absolute-path form was correctly
BLOCKED. Root cause: `_effective_git_target` returned the raw extracted token,
and downstream `pathlib.Path('~/x').resolve()` is CWD-RELATIVE — the target
never compared equal to REPO_ROOT, so the op fell into the conservative
"allow_external" branch. Same class for `$HOME/...` / `${HOME}/...` forms.

Fix under test: the extracted `-C` / `cd` token is passed through
`os.path.expandvars(os.path.expanduser(...))` at the single choke point, so
both consumers (allowed-worktree check and repo-root comparison) see what the
shell will actually touch.

  GUILT     — tilde/env forms of a main-checkout target must resolve to the
              same absolute path the shell would use (the downstream block
              then fires exactly like the absolute form).
  INNOCENCE — absolute and relative externals are untouched; unknown `$VARS`
              stay literal (expandvars semantics); no `-C`/`cd` → default cwd.

    python3 infra/claude-hooks/test_tilde_target_resolver.py
Exit 0 = resolver mirrors shell expansion. Exit 1 = regression.

Reference: PENDING-ARMS tilde blind-spot line · superscar #3 (the resolver
sits UPSTREAM of BLOCKED_SUBCMD_RE: a target the resolver cannot see makes
the best regex irrelevant).
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _load_module():
    spec = importlib.util.spec_from_file_location("wi_tilde", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = _load_module()
    fx = mod._effective_git_target
    home = os.path.expanduser("~")
    failures: list[str] = []

    def check(label: str, cmd: str, cwd: str, expected: str) -> None:
        got = fx(cmd, cwd)
        if got != expected:
            failures.append(f"{label}: {cmd!r} → {got!r}, expected {expected!r}")

    # GUILT — shell-expandable forms of a main-checkout target must expand.
    check("guilt tilde -C", "git -C ~/Desktop/nuzantara stash push -m x", "/tmp",
          f"{home}/Desktop/nuzantara")
    check("guilt $HOME -C", "git -C $HOME/Desktop/nuzantara stash pop", "/tmp",
          f"{home}/Desktop/nuzantara")
    check("guilt ${HOME} -C", "git -C ${HOME}/Desktop/nuzantara reset --hard", "/tmp",
          f"{home}/Desktop/nuzantara")
    check("guilt tilde cd", "cd ~/Desktop/nuzantara && git pull", "/tmp",
          f"{home}/Desktop/nuzantara")
    check("guilt $HOME cd", "cd $HOME/Desktop/nuzantara ; git merge x", "/tmp",
          f"{home}/Desktop/nuzantara")

    # GUILT end-to-end shape: expanded tilde target now resolves EQUAL to the
    # absolute form — the exact comparison the block decision uses.
    tilde_resolved = pathlib.Path(fx("git -C ~/Desktop/nuzantara stash push", "/tmp")).resolve()
    abs_resolved = pathlib.Path(f"{home}/Desktop/nuzantara").resolve()
    if tilde_resolved != abs_resolved:
        failures.append(
            f"guilt e2e: tilde target resolves to {tilde_resolved}, absolute form to "
            f"{abs_resolved} — the downstream repo-root comparison would still diverge"
        )

    # INNOCENCE — untouched cases.
    check("innocence absolute", "git -C /tmp/elsewhere pull", "/x", "/tmp/elsewhere")
    check("innocence relative", "git -C sub/dir pull", "/x", "sub/dir")
    check("innocence no -C/cd", "git pull", "/some/cwd", "/some/cwd")
    unknown = fx("git -C $__NUZ_NO_SUCH_VAR__/repo pull", "/x")
    if unknown != "$__NUZ_NO_SUCH_VAR__/repo":
        failures.append(
            f"innocence unknown-var: expected literal passthrough, got {unknown!r}"
        )
    # mid-token tilde is NOT a home reference in shell — expanduser leaves it.
    check("innocence mid-token tilde", "git -C /data/ver~2/repo pull", "/x", "/data/ver~2/repo")

    if failures:
        print("TILDE RESOLVER FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"=== ALL {5 + 1 + 5} OK — resolver mirrors shell expansion; externals untouched ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
