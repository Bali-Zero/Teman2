#!/usr/bin/env python3
"""The lane check is HONOURED by a termination surface, not merely imported.

`test_lane_check.py` proves the library decides correctly. This file proves the
decision reaches a real stop boundary: it drives `subagent_stop_verify.py` as a
subprocess with a real SubagentStop payload on stdin and reads the exit code the
harness would read (2 = block and show stderr, 0 = allow).

WHY A SECOND FILE. "Armed" for this PR means all four termination surfaces
import AND honour `lane_check`. Import is trivially assertable and proves
nothing — superscar #2 is exactly the gap between a thing existing and a thing
being in force. Two defects in this PR were found only by running the hook and
would have survived any test of the library alone:

  1. The first wiring called `evaluate(cwd)` with no change set, so
     `scope_globs` narrowed nothing at the only wired surface — a declared,
     tested, documented feature that did nothing wherever it was used.
  2. The first version of this probe wrote its transcript and its contract file
     INSIDE the worktree, which made the tree dirty, so the pre-existing dirty
     guard fired and every "innocence" case read as a block. The probe was
     measuring its own contamination (W108: a fake world too poor to reach the
     thing under test measures itself). The transcript now lives outside the
     worktree and the contract is excluded via `.git/info/exclude`, and the
     premise — that the tree really is clean — is asserted rather than assumed.

The out-of-scope case is the sharpest of the two lessons. It necessarily
creates a changed file for scope to have anything to judge, and an untracked
file makes the tree dirty, so the run exits 2 whatever the lane check decides.
Asserting `rc == 0` there would be the probe conflating two guards; the
discriminating assertion is WHICH guard spoke.

Runs as `python3 infra/claude-hooks/test_lane_check_wiring.py -v` (the CI
executor) and under pytest.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

_HOOK = pathlib.Path(__file__).resolve().parent / "subagent_stop_verify.py"
_CLEAN_ENV = {k: v for k, v in os.environ.items()
              if k not in ("SUBAGENT_STOP_VERIFY_OFF", "STOP_VERIFY_ALLOW_DIRTY", "LANE_CHECK_OFF")}


class _World:
    """A throwaway git worktree whose cleanliness is asserted, not assumed."""

    def __init__(self, td: str) -> None:
        self.root = pathlib.Path(td)
        self.wt = self.root / "wt"
        self.wt.mkdir()
        # OUTSIDE the worktree on purpose — a transcript written inside it would
        # make the tree dirty and every innocence case would read as a block.
        self.transcript = self.root / "transcript.jsonl"
        self.transcript.write_text("{}\n", encoding="utf-8")
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "lane-check@test.invalid")
        self._git("config", "user.name", "lane check")
        (self.wt / "a.txt").write_text("a\n", encoding="utf-8")
        (self.wt / "scripts").mkdir()
        (self.wt / "scripts" / "s.py").write_text("x\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "seed")
        # The contract is runtime state, not source; excluding it keeps the
        # tree clean so the two guards stay distinguishable.
        (self.wt / ".git" / "info" / "exclude").write_text(".lane-check.json\n", encoding="utf-8")

    def _git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.wt), *args], check=True, capture_output=True)

    def assert_clean(self) -> None:
        out = subprocess.run(["git", "-C", str(self.wt), "status", "--porcelain"],
                             capture_output=True, text=True).stdout
        assert out.strip() == "", f"PREMISE BROKEN — the probe dirtied its own world: {out!r}"

    def run(self, contract: dict | None, *, env_extra: dict | None = None,
            touch: list[str] | None = None) -> tuple[int, str]:
        env = dict(_CLEAN_ENV)
        env["TMPDIR"] = tempfile.mkdtemp()  # fresh once-only marker namespace per case
        if env_extra:
            env.update(env_extra)
        contract_file = self.wt / ".lane-check.json"
        contract_file.unlink(missing_ok=True)
        if contract is not None:
            contract_file.write_text(json.dumps(contract), encoding="utf-8")
        for rel in touch or []:
            p = self.wt / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("dirty\n", encoding="utf-8")
        payload = json.dumps({
            "cwd": str(self.wt),
            "transcript_path": str(self.transcript),
            "stop_hook_active": False,
        })
        proc = subprocess.run([sys.executable, str(_HOOK)], input=payload,
                              capture_output=True, text=True, env=env)
        for rel in touch or []:
            (self.wt / rel).unlink(missing_ok=True)
        return proc.returncode, proc.stderr


def _cases() -> list[str]:
    fails: list[str] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{' :: ' + detail.strip()[:160] if detail else ''}")

    with tempfile.TemporaryDirectory() as td:
        w = _World(td)
        w.assert_clean()

        rc, err = w.run(None)
        check("INNOCENCE: no .lane-check.json is a pre-PR no-op", rc == 0, err)

        rc, err = w.run({"command": "test -f a.txt"})
        check("INNOCENCE: a passing lane check allows the stop", rc == 0, err)

        rc, err = w.run({"command": "exit 1"}, env_extra={"LANE_CHECK_OFF": "1"})
        check("INNOCENCE: LANE_CHECK_OFF=1 escapes a failing check", rc == 0, err)

        # See the module docstring: this case cannot be rc==0, and asserting so
        # would conflate the two guards. What it proves is that the LANE check
        # stayed silent while the pre-existing dirty guard did its own job.
        rc, err = w.run({"command": "exit 5", "scope_globs": ["nothing/*"]}, touch=["docs/x.md"])
        check("INNOCENCE: an out-of-scope change leaves the lane check silent",
              rc == 2 and "lane's own declared check" not in err and "dirty worktree" in err, err)

        # The complement, and the case that caught the missing change set: an
        # IN-scope change must actually reach the command.
        rc, err = w.run({"command": "echo BROKE-XYZZY >&2; exit 1", "scope_globs": ["scripts/*"]},
                        touch=["scripts/s2.py"])
        check("GUILT: an in-scope change runs the check and blocks",
              rc == 2 and "BROKE-XYZZY" in err and "lane's own declared check" in err, err)

        rc, err = w.run({"command": "echo BROKE-XYZZY >&2; exit 1"})
        check("GUILT: a failing check blocks and quotes its stderr",
              rc == 2 and "BROKE-XYZZY" in err, err)

        rc, err = w.run({"command": "true"})
        check("GUILT: a tautological command is refused, not passed",
              rc == 2 and "tautology" in err, err)

        rc, err = w.run({"command": "sleep 5", "timeout": 1})
        check("GUILT: a timeout blocks rather than reading as a pass", rc == 2, err)

        rc, err = w.run(None, touch=["b.txt"])
        check("REGRESSION: the pre-existing dirty-worktree block is intact",
              rc == 2 and "dirty worktree" in err, err)

    # ---- the two wiring-side cures, each with a world of its own so the
    # ---- once-only markers from the cases above cannot mask the result.

    with tempfile.TemporaryDirectory() as td:
        w = _World(td)
        # An untracked DIRECTORY. `git status --porcelain` collapses it to
        # 'newdir/' (measured), which matches no file glob — so a scoped check
        # would have silently skipped on exactly the change it was written for.
        # `-uall` lists the file instead. Named by a blind refuter as a way for
        # a lane to skip its own check without anyone noticing.
        rc, err = w.run({"command": "echo IN-SCOPE-XYZZY >&2; exit 1", "scope_globs": ["newdir/*.py"]},
                        touch=["newdir/x.py"])
        check("GUILT: an untracked DIRECTORY's file is still in scope (-uall)",
              rc == 2 and "IN-SCOPE-XYZZY" in err, err)

    with tempfile.TemporaryDirectory() as td:
        w = _World(td)
        # A lane-check block must not consume the dirty guard's one shot. Both
        # run in the SAME TMPDIR here on purpose: with a single shared marker
        # the second call short-circuits and the dirty tree ships unnoticed —
        # adding a feature would have silently un-armed a protection that was
        # already in force.
        shared_tmp = tempfile.mkdtemp()
        env = dict(_CLEAN_ENV); env["TMPDIR"] = shared_tmp
        (w.wt / ".lane-check.json").write_text(json.dumps({"command": "exit 1"}), encoding="utf-8")
        payload = json.dumps({"cwd": str(w.wt), "transcript_path": str(w.transcript),
                              "stop_hook_active": False})
        first = subprocess.run([sys.executable, str(_HOOK)], input=payload,
                               capture_output=True, text=True, env=env)
        check("marker: the lane check blocks the first time", first.returncode == 2, first.stderr)
        # now fix the check, dirty the tree, and stop again in the SAME namespace
        (w.wt / ".lane-check.json").write_text(json.dumps({"command": "test -f a.txt"}), encoding="utf-8")
        (w.wt / "b.txt").write_text("dirty\n", encoding="utf-8")
        second = subprocess.run([sys.executable, str(_HOOK)], input=payload,
                                capture_output=True, text=True, env=env)
        check("marker: a lane block does NOT consume the dirty guard's shot",
              second.returncode == 2 and "dirty worktree" in second.stderr, second.stderr)

    return fails


def test_lane_check_is_honoured_by_the_subagent_stop_surface() -> None:
    fails = _cases()
    assert not fails, "lane-check wiring regressions:\n" + "\n".join(fails)


if __name__ == "__main__":
    fails = _cases()
    if fails:
        print(f"=== {len(fails)} FAIL ===")
        for f in fails:
            print("  [FAIL] " + f)
        sys.exit(1)
    print("=== lane_check wiring OK (11 cases through the real SubagentStop hook: "
          "absent/passing/escape/out-of-scope stay silent, in-scope + failing + tautology + "
          "timeout block, and the pre-existing dirty guard is unchanged) ===")
    sys.exit(0)
