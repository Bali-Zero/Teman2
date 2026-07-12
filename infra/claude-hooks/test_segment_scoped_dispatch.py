#!/usr/bin/env python3
"""Segment-scoped remote-dispatch exemption — guilt+innocence (6th over-match).

Superscar #3, found at the PR-2266 gate 2026-07-11 (the SAME session that
shipped W92): the git-verb channel (W83, live on `main` since 2026-06-16) and
the write-target channel (W92, this same PR) both used `_is_remote_dispatch`
as a WHOLE-COMMAND exemption — it returns True the instant ANY segment of the
command starts with ssh/scp/rsync, even when a LATER segment is a genuine
LOCAL mutation.

  `ssh mini hostname && cp /tmp/x scripts/f.py`   — write channel: the `cp`
  `ssh pro hostname; tee scripts/g.py < /tmp/y`   — write channel: the `tee`
  `ssh pro hostname && git pull origin main`      — git channel: the `pull`

all got wrongly exempted (the FIRST segment is remote, but the mutating verb
lives in a LATER, LOCAL segment). The corpus in guard_fuzz_harness.py never
encoded this shape — its only "compound" cases had ssh INSIDE quotes (a
different, already-correctly-handled class), so 382/382 passed while the
disease was still live.

Fix: `_segments()` splits the noise-stripped command on `&& || ; |`;
`_is_position_remote_dispatched(cmd_scan, pos)` answers "is the segment
CONTAINING this character offset itself remote-dispatched" rather than "is
ANY segment of the whole command remote-dispatched". Both call sites
(`main()`'s git-verb loop and `_write_hits_main`'s per-target loop) now check
EVERY match/target against its OWN segment.

  GUILT     — a mutating verb/write-target in a LOCAL segment must still
              block even when an EARLIER segment in the same compound
              command is remote-dispatched (the 3 counter-examples above +
              their `;`/`&&` siblings + a 3-segment chain).
  INNOCENCE — the pre-existing legitimate compound shapes must still be
              exempt: `foo | ssh mini git pull` (the mutating segment IS the
              ssh one), `scp -q file pro:/tmp/x && ssh pro git pull` (both
              segments remote), and every single-segment case from
              test_w83_remote_dispatch.py / test_w92_remote_write_dispatch.py
              (this fix must not regress either predecessor suite — both are
              re-run independently in CI as their own pins).

    python3 infra/claude-hooks/test_segment_scoped_dispatch.py
Exit 0 = segment-scoping holds on both channels. Exit 1 = regression.

Reference: cicatrix-superscar.md #3 (W83, W92, this) · PR #2266 gate finding
2026-07-11 · registry: infra/guard-conformance/registry.json. Scar filing for
this instance deferred to orchestrator serial reconciliation (W-number
collision live the night this was found) — see
research/operations/2026-07-11-guard-fuzz-immune.md for the full trauma text.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def _load_module():
    spec = importlib.util.spec_from_file_location("wi_segscope", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _fixture(mod):
    """Same throwaway-tempdir + monkeypatched-worktree-resolver pattern as
    every other suite in this dir — required so a relative token (e.g.
    `scripts/f.py`) resolves against the FIXTURE, not wherever this script
    happens to be invoked from (which would make _is_path_in_allowed_worktree
    pass for the wrong reason if run from inside a real .worktrees/<lane>)."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="segscope_"))
    main_checkout = str(tmp / "nuzantara")
    pathlib.Path(main_checkout, "scripts").mkdir(parents=True)
    mod.REPO_ROOT = main_checkout

    wt_root = pathlib.Path(main_checkout, ".worktrees").resolve()

    def _fake_allowed(path_str: str) -> bool:
        if not path_str:
            return False
        try:
            p = pathlib.Path(mod.os.path.expanduser(path_str))
            if not p.is_absolute():
                return False
            p = p.resolve()
        except Exception:
            return False
        try:
            return p.is_relative_to(wt_root)
        except Exception:
            return False

    mod._is_path_in_allowed_worktree = _fake_allowed
    return main_checkout


def _simulate_git_channel(mod, cmd: str, cwd: str) -> bool:
    """Calls the REAL decision function (`_git_verb_verdict`, extracted from
    main() during this same fix specifically so no caller ever needs its own
    copy — a hand-reimplementation here would repeat the exact drift risk
    guard_fuzz_harness.py's original run_corpus() just demonstrated: a
    second stale copy of this logic, written the same day, would already be
    wrong the moment either one changes). Returns True = BLOCK, False =
    ALLOW — thin wrapper kept only so call sites below read the same as
    before this refactor."""
    return mod._git_verb_verdict(cmd, cwd).decision == "block"


def main() -> int:
    mod = _load_module()
    main_checkout = _fixture(mod)
    failures: list[str] = []

    # ---- WRITE CHANNEL (W92's own channel) --------------------------------
    write_guilty = [
        "ssh mini hostname && cp /tmp/x scripts/f.py",   # gate counter-example #1
        "ssh pro hostname; tee scripts/g.py < /tmp/y",    # gate counter-example #2
        "ssh mini hostname || cp /tmp/x scripts/f.py",    # || sibling
        "echo prelude && ssh mini hostname && cp /tmp/x scripts/f.py",  # 3-segment chain, write is 3rd
    ]
    for cmd in write_guilty:
        offending = mod._write_hits_main(cmd, main_checkout)
        if offending is None:
            failures.append(f"WRITE-GUILT: wrongly ALLOWED (should block): {cmd!r}")

    write_innocent = [
        "ssh mini cp /tmp/x scripts/f.py",                       # single segment — W92 baseline
        "echo prelude && ssh mini cp /tmp/x scripts/f.py",       # write segment IS the ssh one
        "foo | ssh mini cp /tmp/x scripts/f.py",                 # write segment IS the ssh one
        "scp -q file pro:/tmp/x && ssh pro cp /tmp/y scripts/f.py",  # both segments remote
    ]
    for cmd in write_innocent:
        offending = mod._write_hits_main(cmd, main_checkout)
        if offending is not None:
            failures.append(f"WRITE-INNOCENCE: wrongly BLOCKED (should allow): {cmd!r} -> {offending}")

    # ---- GIT-VERB CHANNEL (W83's channel, latent hole pre-dating this PR) -
    git_guilty = [
        "ssh pro hostname && git pull origin main",       # gate counter-example #3
        "ssh pro hostname; git reset --hard",              # ; sibling
        "ssh pro hostname || git checkout main",           # || sibling
        "ssh pro git pull && git checkout main",           # compound: 2nd segment local mutation
        "echo hi && ssh pro hostname && git pull origin main",  # 3-segment chain
    ]
    for cmd in git_guilty:
        if not _simulate_git_channel(mod, cmd, main_checkout):
            failures.append(f"GIT-GUILT: wrongly ALLOWED (should block): {cmd!r}")

    git_innocent = [
        "ssh pro git pull",                                 # single segment — W83 baseline
        "foo | ssh mini git pull",                          # mutating segment IS the ssh one
        "scp -q file pro:/tmp/x && ssh pro git pull",        # both segments remote
        "echo pull-note && ssh pro git pull",               # prelude segment innocuous, git segment IS remote
    ]
    for cmd in git_innocent:
        if _simulate_git_channel(mod, cmd, main_checkout):
            failures.append(f"GIT-INNOCENCE: wrongly BLOCKED (should allow): {cmd!r}")

    if failures:
        print("FAIL — segment-scoped dispatch regressions:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        f"OK — segment-scoped remote-dispatch holds on both channels "
        f"({len(write_guilty)}+{len(git_guilty)} guilt, "
        f"{len(write_innocent)}+{len(git_innocent)} innocence)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
