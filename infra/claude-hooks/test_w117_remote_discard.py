#!/usr/bin/env python3
"""W117 — ssh-dispatched DISCARD of a remote main checkout: guilt+innocence.

W117 (cicatrix-superscar #3 / #5): the git-verb channel of this hook cannot see
`ssh pro 'cd ~/nuzantara && git reset --hard origin/main'` AT ALL. Measured, not
reasoned: `_strip_noise()` empties quoted text by design (W83), so the payload is
gone before the scan and the verdict is *no_blocked_verb* — the remote-dispatch
exemption is never consulted. An earlier draft of the cure sat inside that
exemption branch and would have been DEAD CODE on the only path it exists for
(W116: a mutant that survives is sometimes a guard that could not fire).

That gap bit on 2026-08-10, when exactly that command — run to realign Pro's
main checkout — discarded 159 entries of the intel publish ledger (whose loss
re-publishes already-published articles) and 24 open escalations. Both are
runtime state no commit holds; `scripts/pro/pro-git-pull.sh` exists precisely to
realign that checkout while keeping them.

  GUILT      (refuses real danger): reset --hard / checkout -- / checkout . /
             clean -fd / restore / mutating stash, ssh-dispatched at a main
             checkout — named as `~/nuzantara`, as a deep path inside it
             (`~/nuzantara/apps`: the reset discards the WHOLE worktree, so
             basename-only judging would UNDER-match), via `git -C`, or with the
             remote cwd NOT NAMED at all (fail-closed).
  INNOCENCE  (spares adjacent-legit): `ssh pro git pull` and the ff-only pull
             stay exempt; a remote `.worktrees/` path is allowed (a worktree
             carries no runtime state); read-only `git stash list|show` is not
             caught (W85); a discarding verb quoted INSIDE the payload
             (`ssh pro 'echo "git reset --hard"'`) is not read as a command;
             a LOCAL reset after a remote probe is left to the git-verb channel,
             not misattributed here; another repo's path is not policed.

    python3 infra/claude-hooks/test_w117_remote_discard.py
Exit 0 = the channel refuses the discards and spares the legitimate neighbours.
Exit 1 = regression on either side (went blind, or started over-matching).

Reference: cicatrix-superscar.md #3 · registry: infra/guard-conformance/registry.json
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _load_hook():
    spec = importlib.util.spec_from_file_location("wi_w117", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# (command, expect_blocked, label)
CASES: list[tuple[str, bool, str]] = [
    # ---- GUILT ----
    (
        "ssh pro 'cd ~/nuzantara && git reset --hard origin/main'",
        True,
        "the 2026-08-10 command itself",
    ),
    (
        'ssh pro "cd ~/nuzantara && git reset --hard origin/main"',
        True,
        "same, double-quoted payload",
    ),
    (
        "ssh pro 'cd /Users/nuzantara/nuzantara && git reset --hard'",
        True,
        "absolute remote main checkout",
    ),
    (
        "ssh pro 'cd ~/nuzantara/apps && git reset --hard'",
        True,
        "deep path INSIDE main (reset discards the whole worktree)",
    ),
    (
        "ssh mini 'git -C ~/nuzantara reset --hard origin/main'",
        True,
        "git -C instead of cd",
    ),
    (
        "ssh pro 'git reset --hard'",
        True,
        "remote cwd NOT named — fail-closed",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git checkout -- shared/escalations_pro.jsonl'",
        True,
        "checkout -- <path> discards one file's runtime state",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git checkout .'",
        True,
        "checkout . discards everything",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git clean -fd'",
        True,
        "clean -fd removes untracked runtime output",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git restore apps/'",
        True,
        "git restore discards the worktree copy",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git stash'",
        True,
        "bare stash = stash push, hides the state from its writer",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git reset --quiet --hard origin/main'",
        True,
        "flags between reset and --hard",
    ),
    (
        "ssh pro 'cd ~/nuzantara/.worktrees/ops-x && git -C ~/nuzantara reset --hard'",
        True,
        "names a worktree AND the main checkout — every path is judged",
    ),
    # ---- INNOCENCE ----
    (
        "ssh pro 'cd ~/nuzantara && git pull --ff-only'",
        False,
        "the legitimate remote realign verb stays exempt",
    ),
    (
        "ssh pro git pull origin main",
        False,
        "unquoted remote pull stays exempt",
    ),
    (
        "ssh pro 'cd ~/nuzantara/.worktrees/ops-x && git reset --hard origin/main'",
        False,
        "a remote WORKTREE carries no runtime state",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git stash list'",
        False,
        "W85: read-only stash query is not a discard",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git stash show'",
        False,
        "W85: stash show likewise",
    ),
    (
        "ssh pro 'echo \"git reset --hard\"'",
        False,
        "the verb only appears inside a quoted literal",
    ),
    (
        "ssh pro hostname && git reset --hard origin/main",
        False,
        "a LOCAL reset belongs to the git-verb channel, not misattributed here",
    ),
    (
        "ssh pro 'cd /tmp/someone-elses-repo && git reset --hard'",
        False,
        "another repo is not ours to police",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git status --porcelain'",
        False,
        "read-only status",
    ),
    (
        "ssh pro 'cd ~/nuzantara && git log -1 --format=%H'",
        False,
        "read-only log",
    ),
    (
        "git reset --hard origin/main",
        False,
        "no ssh at all — this channel must stay silent",
    ),
    # ---- HEREDOCS: the 10th over-match and the twin it would have birthed ----
    # The channel bit its OWN commit message on 2026-08-10: prose that NAMES the
    # gesture, inside a body handed to `git commit -F -`, was read AS the gesture.
    # Whether a body is code or data is a property of its CONSUMER, so the pair of
    # cases below must disagree while sharing an identical body.
    (
        "git commit -F - <<'EOF'\n"
        "docs: ssh pro 'cd ~/nuzantara && git reset --hard origin/main' cost 159 entries\n"
        "EOF",
        False,
        "prose about the gesture in a commit-message body is prose (over-match)",
    ),
    (
        "cat <<'EOF' > /tmp/runbook.md\n"
        "Never run: ssh pro 'cd ~/nuzantara && git clean -fdx'\n"
        "EOF",
        False,
        "a runbook warning against the gesture is not the gesture",
    ),
    (
        "ssh pro <<'EOF'\ncd ~/nuzantara\ngit reset --hard origin/main\nEOF",
        True,
        "heredoc DISPATCHED to ssh is a real remote command (the under-match twin)",
    ),
    (
        "bash <<'EOF'\nssh pro 'cd ~/nuzantara && git reset --hard'\nEOF",
        True,
        "a shell executes its body, so the ssh inside it still dispatches",
    ),
    (
        "ssh pro <<'EOF'\ncd ~/nuzantara\ngit pull --ff-only\nEOF",
        False,
        "heredoc-dispatched ff-only pull stays exempt like its one-line form",
    ),
]


def main() -> int:
    hook = _load_hook()
    failures: list[str] = []
    for cmd, expect_blocked, label in CASES:
        got = hook._remote_discard_on_main(cmd)
        blocked = got is not None
        if blocked != expect_blocked:
            failures.append(
                "  %-9s %s\n      cmd: %s\n      verdict: %r"
                % (
                    "MISSED" if expect_blocked else "OVER-MATCH",
                    label,
                    cmd,
                    got,
                )
            )

    guilt = sum(1 for _, e, _ in CASES if e)
    innocence = len(CASES) - guilt
    if failures:
        print("W117 corpus FAILED (%d guilt / %d innocence):" % (guilt, innocence))
        print("\n".join(failures))
        return 1
    print("W117 corpus OK — %d guilt + %d innocence cases" % (guilt, innocence))
    return 0


if __name__ == "__main__":
    sys.exit(main())
