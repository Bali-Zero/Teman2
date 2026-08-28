#!/usr/bin/env python3
"""stage_council_journal.py — stage a Gear-3 pack's council journal alongside the staged pack.

WHY THIS EXISTS (measured 2026-08-29, reproduced before the fix): harness-floor.yml's pack-lint
step builds a SYNTHETIC evidence tree under /tmp/evidence-check and stages exactly two files into
it — the pack (from `git show "$HEAD_SHA:$PACK_PATH"`) and the brief — under the canonical
evidence/{pack,brief}.yml names. That is enough for every rule that resolves a path against
--repo-root (check_brief_ref_exists), and it was enough for every rule that existed when the
staging was written.

R9 (scripts/evidence_pack_lint.py::check_council_run_gear3) does NOT resolve against --repo-root.
It resolves the pack's `council_run:` against the PACK'S OWN directory, one level deeper, and the
staged pack directory contains only the two files above. So a pack whose council journal IS
committed next to it in the real tree — the shape the one existing council pack in this repo uses,
`evidence/2026-08/<slug>/council-journal.jsonl` with `council_run: council-journal.jsonl` — still
lints in CI as "gear:3 pack declares no council_run journal with >=2 distinct review seats". The
verdict is about the staging, not about the pack.

Measured on that real pack, staged exactly the way the workflow stages it:

    council_run declared by the pack: 'council-journal.jsonl'
    NOTICE — council_run: gear:3 pack declares no council_run journal with >=2 distinct
             review seats from (...) marked ok:true

R9 is phased: NOTICE before R9_R11_ENFORCEMENT_DATE (2026-09-02), hard violation on/after. So from
2026-09-02 this staging gap fails EVERY Gear-3 PR, by construction and independent of the diff —
including a PR that did convene a full council and committed the journal to prove it.

DIRECTION OF THE FIX, decided from the pack contract rather than from convenience: R9's own
docstring declares `council_run` a path "relative to the pack dir" and confines it there, and the
only real council pack in the tree commits the journal into that directory. The journal therefore
TRAVELS WITH THE PACK, and the staging is what is incomplete — not the rule. This script stages it,
at the path `council_run:` names relative to the STAGED pack dir, so the synthetic tree reproduces
the shape R9 was written against.

WHAT IS DELIBERATELY NOT STAGED (each of these leaves R9 to judge the pack on its own terms —
NOTICE today, violation on/after the flip — which is strictly stricter than staging, never a
fail-open):

  * no `council_run:` field, or a blank/non-string one — nothing is declared, nothing to stage;
  * an ABSOLUTE path, or one escaping the pack dir via `..` — R9 rejects these shapes itself, and
    staging them would launder a path-confinement violation into a pass;
  * a `council_run:` that names a file not present at HEAD — the pack declares a journal it did
    not commit, which is exactly what R9 exists to catch.

Exit codes: 0 = staged, or nothing to stage (every case above); 1 = the journal was resolved but
could not be written (a real infrastructure failure, never a verdict about the pack).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath

import yaml


def read_council_run(pack_text: str) -> str | None:
    """The pack's declared `council_run:`, or None when it declares none.

    Malformed YAML and a non-mapping document both return None rather than raising: this script
    never renders a verdict on the pack — evidence_pack_lint.py does, on the same file, moments
    later, and it reports a parse failure far better than a traceback here would.
    """
    try:
        pack = yaml.safe_load(pack_text)
    except yaml.YAMLError:
        return None
    if not isinstance(pack, dict):
        return None
    raw = pack.get("council_run")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip()


def sanitize_relpath(council_run: str) -> str | None:
    """The pack-dir-relative form of `council_run`, or None if R9 would refuse to resolve it.

    Mirrors _read_council_journal_seats' confinement check by construction: absolute paths and any
    `..` component are refused here for the same reason they are refused there. PurePosixPath is
    used (not os.path) because evidence/ paths in this repo are always POSIX-style, and it collapses
    `.` components on its own, so "./journal.jsonl" and "journal.jsonl" stage identically.
    """
    parts = PurePosixPath(council_run).parts
    if not parts or parts[0] == "/" or ".." in parts:
        return None
    return PurePosixPath(*parts).as_posix()


def journal_bytes_at_head(repo: Path, head_sha: str, path: str, git_bin: str = "git") -> bytes | None:
    """The blob at `<head_sha>:<path>`, or None when it does not exist there."""
    proc = subprocess.run(
        [git_bin, "-C", str(repo), "show", f"{head_sha}:{path}"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--staged-pack", required=True, help="the pack.yml already staged into the synthetic evidence tree")
    parser.add_argument("--source-path", required=True, help="the pack's REAL repo-relative path at HEAD")
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--git-bin", default="git")
    args = parser.parse_args(argv)

    staged_pack = Path(args.staged_pack)
    try:
        pack_text = staged_pack.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"stage_council_journal: staged pack unreadable ({exc}) — staging nothing")
        return 0

    declared = read_council_run(pack_text)
    if declared is None:
        print("stage_council_journal: pack declares no council_run — staging nothing")
        return 0

    relpath = sanitize_relpath(declared)
    if relpath is None:
        print(
            f"stage_council_journal: council_run: '{declared}' is absolute or escapes the pack dir — "
            "staging nothing, R9 refuses this shape itself"
        )
        return 0

    source_dir = PurePosixPath(args.source_path).parent
    journal_source = (source_dir / relpath).as_posix()
    blob = journal_bytes_at_head(Path(args.repo), args.head_sha, journal_source, args.git_bin)
    if blob is None:
        print(
            f"stage_council_journal: pack declares council_run: '{declared}' but '{journal_source}' "
            "does not exist at HEAD — staging nothing, R9 will judge the pack on that"
        )
        return 0

    destination = staged_pack.parent / relpath
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob)
    except OSError as exc:
        print(f"stage_council_journal: could not write '{destination}': {exc}", file=sys.stderr)
        return 1

    print(f"stage_council_journal: staged '{journal_source}' as '{relpath}' beside the staged pack")
    return 0


if __name__ == "__main__":
    sys.exit(main())
