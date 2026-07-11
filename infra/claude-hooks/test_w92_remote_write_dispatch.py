#!/usr/bin/env python3
"""W92 regression test — remote-dispatched shell WRITE over-match fix.

Superscar #3 (guard-over-match), 5th consecutive instance on worktree_isolation.py
after W83/W84/W85/W91. Unlike its predecessors (all in the git-verb dispatcher
channel), W92 lives in the FILE-WRITE channel (`_write_hits_main`): an
ssh/scp/rsync-dispatched command carries its write to ANOTHER host, but a
RELATIVE destination inside that payload used to be resolved against the LOCAL
session cwd — producing a phantom write-target into the main checkout for a
write that never touches this machine.

  GUILT     (the guard still bites): a LOCAL write with the same relative
            destination, with or without an "ssh" WORD mentioned elsewhere
            in the command (echo/text), must still block. scp/rsync with an
            ABSOLUTE local destination must still block.
  INNOCENCE (the over-match is gone): ssh/scp/rsync-dispatched writes with
            relative OR colon-form remote destinations must be allowed,
            across every write-verb the channel recognizes (redirect,
            append, tee, sed -i, cp, mv, dd) and every quoting shape
            (unquoted, single-quoted, double-quoted whole payload).

    python3 infra/claude-hooks/test_w92_remote_write_dispatch.py
Exit 0 = the over-match stays fixed. Exit 1 = regression.

Reference: cicatrix-scars.md / cicatrix-superscar.md #3 (W92) · PR #2260
(documentation-only) · this file is the CODE fix's guilt+innocence proof ·
registry: infra/guard-conformance/registry.json.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def _load_module():
    spec = importlib.util.spec_from_file_location("wi_w92", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = _load_module()

    # Fixture layout — same pattern as test_w79/w83/w84: a throwaway tempdir
    # stands in for REPO_ROOT so a RELATIVE token (e.g. `apps/f.py`) cannot
    # accidentally resolve against wherever this script happens to be
    # INVOKED from (e.g. inside a real .worktrees/<lane> dir, which would
    # make `_is_path_in_allowed_worktree` pass for the wrong reason — a test
    # artifact, not the guard's real behavior when the hook runs live from
    # the actual main checkout).
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="w92_"))
    main_checkout = str(tmp / "nuzantara")
    pathlib.Path(main_checkout, "apps").mkdir(parents=True)
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

    failures: list[str] = []

    # ---- INNOCENCE: remote-dispatched writes must NOT be classified as a
    # main-checkout write, across every recognized write verb + quoting shape.
    innocent = [
        "ssh mini echo x > apps/f.py",
        "ssh mini echo x >> apps/f.py",
        "ssh mini echo x | tee apps/f.py",
        "ssh mini sed -i 's/a/b/' apps/f.py",
        "ssh mini cp /tmp/src apps/f.py",
        "ssh mini mv /tmp/src apps/f.py",
        "ssh mini dd if=/tmp/x of=apps/f.py",
        "ssh mini 'cp /tmp/src apps/f.py'",
        'ssh mini "cp /tmp/src apps/f.py"',
        "ssh pro-lan cp /tmp/src apps/f.py",
        "scp /tmp/src mini:apps/f.py",
        "rsync -av /tmp/dir/ mini:apps/backend-rag/",
        "echo prelude && ssh mini cp /tmp/src apps/f.py",   # ssh starts post-&& segment
        "foo | ssh mini cp /tmp/src apps/f.py",             # ssh starts post-pipe segment
    ]
    for cmd in innocent:
        offending = mod._write_hits_main(cmd, main_checkout)
        if offending is not None:
            failures.append(f"INNOCENCE: wrongly blocked remote write: {cmd!r} -> {offending}")

    # ---- GUILT: local writes with the SAME relative destination — including
    # when "ssh" is mentioned as a mere WORD, not a dispatcher — must still block.
    guilty = [
        "cp /tmp/src apps/f.py",                       # bare local, no ssh at all
        "echo x > apps/f.py",
        "echo ssh && cp /tmp/src apps/f.py",            # 'ssh' just a word, git runs locally
        "echo 'copy via ssh' ; cp /tmp/src apps/f.py",  # ssh mentioned, write is LOCAL after ;
        "mysshscript && cp /tmp/src apps/f.py",         # 'ssh' substring inside a longer token
    ]
    # NOTE: `scp mini:/remote/src <local-abs-dest>` (remote SOURCE, local
    # DEST — direction-reversed scp) is NOT a guilt case here. The existing
    # W83 REMOTE_DISPATCH_RE is direction-agnostic by design (it matches the
    # ssh/scp/rsync VERB prefix, never which argument is local vs. remote —
    # confirmed against the git-verb channel's own test_w83_remote_dispatch.py,
    # whose only scp case is local->remote and is treated identically). This
    # write-channel fix reuses that SAME function, so it inherits the SAME
    # accepted trade-off, not a new blind spot: the file's own stated
    # philosophy is "defense conservative... must NOT false-positive"
    # (docstring line 39) — an occasional missed direction-reversed scp is
    # the deliberate cost of that conservatism, already paid before W92.
    for cmd in guilty:
        offending = mod._write_hits_main(cmd, main_checkout)
        if offending is None:
            failures.append(f"GUILT: exception wrongly opens for local write: {cmd!r}")

    if failures:
        print("FAIL — W92 remote-write-dispatch regressions:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"OK (W92) — remote-dispatched writes allowed "
          f"({len(innocent)} innocence), local writes still blocked ({len(guilty)} guilt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
