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
  * an ABSOLUTE path (leading "/" or POSIX's reserved leading "//"), or one escaping the pack dir
    via `..` — R9 rejects these shapes itself, and staging them would launder a path-confinement
    violation into a pass;
  * `pack.yml` or `brief.yml` — the canonical names harness-floor.yml stages the pack and brief
    under, which the journal must never be written over (see STAGED_RESERVED_NAMES);
  * a `council_run:` that does not name a REGULAR FILE (git mode 100644/100755) at HEAD — an absent
    path, but also a directory, a symlink or a gitlink. `git show` on a TREE succeeds and prints the
    child filenames, so without the mode gate a directory whose children are named like JSON records
    would stage as a valid two-seat journal that R9 refuses on a real tree;
  * a `..` that cancels something which EXISTS at HEAD and is not a directory — there the lexical
    resolution below and R9's symlink-aware `Path.resolve()` would name different files. A cancelled
    prefix that does not exist is fine: `Path.resolve()` is non-strict and normalizes it lexically
    too.

A `..` that stays INSIDE the pack dir ("a/../b") is NOT in that list: R9 resolves it and accepts
it, so this script resolves it the same way and stages it. Refusing it would fail a legitimate
pack — this defect in miniature.

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
    # Returned UNSTRIPPED (only the emptiness test strips). R9 tests `council_run.strip()` for
    # emptiness but then resolves the RAW string, so a value like " journal.jsonl" names a file
    # whose first character is a space. Stripping here would stage it under a different name than
    # the one R9 goes looking for — a divergence in the direction that fails a legitimate pack,
    # which is the whole class of defect this script exists to remove.
    return raw


#: Staged filenames the journal may never be written over: harness-floor.yml stages the pack and
#: the brief under exactly these canonical names, so a `council_run:` naming one of them would have
#: the staging clobber the very files the lint is about to judge. R9 could never find a quorum in
#: either (both are YAML documents, not JSON Lines), so refusing them costs no legitimate pack
#: anything — it only removes the clobber.
STAGED_RESERVED_NAMES = frozenset({"pack.yml", "brief.yml"})


def sanitize_relpath(council_run: str) -> str | None:
    """The pack-dir-relative form of `council_run`, or None if R9 would refuse to resolve it.

    Mirrors _read_council_journal_seats' confinement check by construction, and the mirror has to
    be exact in BOTH directions: a value this refuses but R9 accepts fails a legitimate pack, and a
    value this accepts but R9 refuses stages a file R9 will not look at. So the `..` components are
    resolved LEXICALLY here, exactly as R9's `(pack_dir / council_run).resolve()` resolves them
    (cross-family review, kimi-code/k3): "a/../b" is a perfectly good reference to "b" inside the
    pack dir, and refusing it outright — as the first version of this function did — would have
    reintroduced the defect in miniature.

    Absoluteness is asked of PurePosixPath rather than tested against a leading "/" for the same
    reason (same review): POSIX reserves a LEADING DOUBLE SLASH, so `PurePosixPath("//x").parts[0]`
    is "//" and never equals "/". `Path("//x").is_absolute()` is True, so R9 refuses it — and a
    string-compare version of this check would have accepted it and then joined it onto the staged
    pack dir, where an absolute right-hand operand discards the left and the write lands outside
    the staged tree entirely.
    """
    if PurePosixPath(council_run).is_absolute():
        return None
    resolved: list[str] = []
    for part in PurePosixPath(council_run).parts:
        if part == "..":
            if not resolved:
                return None  # escapes the pack dir, exactly as R9's confinement check refuses
            resolved.pop()
        else:
            resolved.append(part)
    if not resolved:
        return None
    relpath = PurePosixPath(*resolved).as_posix()
    if relpath in STAGED_RESERVED_NAMES:
        return None
    return relpath


def dotdot_cancelled_prefixes(council_run: str) -> list[str]:
    """The pack-dir-relative directory paths that `..` components of `council_run` cancel.

    Each one must be a REAL DIRECTORY in the tree for the lexical resolution above to agree with
    R9's `Path.resolve()` — see verify_cancelled_prefixes_are_directories, which is where that is
    enforced. Returns [] for a value with no `..`, which is every real pack.
    """
    prefixes: list[str] = []
    stack: list[str] = []
    for part in PurePosixPath(council_run).parts:
        if part == "..":
            if not stack:
                return prefixes
            prefixes.append(PurePosixPath(*stack).as_posix())
            stack.pop()
        else:
            stack.append(part)
    return prefixes


def tree_entry_mode(repo: Path, head_sha: str, path: str, git_bin: str = "git") -> str | None:
    """The git mode of `<head_sha>:<path>` ("100644", "040000", "120000", ...), or None if absent.

    `git ls-tree` is asked rather than `git cat-file -t` because TYPE IS NOT ENOUGH: a symlink is
    stored as a blob, so `cat-file -t` answers "blob" for both a real file and a symlink, and only
    the mode tells them apart (measured: `.claude/skills/bot` in this repo is type blob, mode
    120000).
    """
    proc = subprocess.run(
        [git_bin, "-C", str(repo), "ls-tree", "--full-tree", head_sha, "--", path],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.split()[0]


def journal_bytes_at_head(repo: Path, head_sha: str, path: str, git_bin: str = "git") -> bytes | None:
    """The REGULAR-FILE blob at `<head_sha>:<path>`, or None for anything else.

    The mode gate is the point, not the read (cross-family review, codex-gpt-5.6-sol, CRITICAL):
    `git show <sha>:<a-tree>` succeeds and prints a HEADER PLUS THE CHILD FILENAMES, one per line.
    Written out as the journal, a directory whose children are named like JSON records becomes a
    perfectly valid two-seat JSONL — and R9, which refuses the directory outright on a real tree
    (`journal_path.is_file()` is False), would read the staged listing and find quorum. Verified on
    this repo: `git show HEAD:evidence/2026-08/<a pack dir>` prints "tree <sha>:<path>" then
    brief.yml / council-journal.jsonl / pack.yml. Symlinks (120000) and gitlinks (160000) are
    refused by the same gate; git does not follow symlinks in a pathspec either (measured), so a
    journal can never be read from outside the pack directory.
    """
    if tree_entry_mode(repo, head_sha, path, git_bin) not in ("100644", "100755"):
        return None
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
            f"stage_council_journal: council_run: '{declared}' is absolute, escapes the pack dir, "
            f"or names one of the staged files {sorted(STAGED_RESERVED_NAMES)} — staging nothing"
        )
        return 0

    repo = Path(args.repo)
    source_dir = PurePosixPath(args.source_path).parent

    # A `..` is resolved LEXICALLY above; R9's Path.resolve() is SYMLINK-AWARE. The two agree only
    # while every directory a `..` cancels really is a directory (cross-family review,
    # codex-gpt-5.6-sol, HIGH — demonstrated with a symlink already tracked in this repo:
    # ".claude/skills/bot/../x" is ".claude/skills/x" lexically and ".agents/skills/x" resolved).
    # Where they would disagree, stage nothing and let R9 judge the pack.
    # A prefix that does not exist at all is NOT a disagreement: Path.resolve() is non-strict and
    # normalizes a missing component lexically, exactly as this script does. Only an EXISTING
    # non-directory — a symlink, or a file — makes the two name different things.
    for prefix in dotdot_cancelled_prefixes(declared):
        prefix_path = (source_dir / prefix).as_posix()
        mode = tree_entry_mode(repo, args.head_sha, prefix_path, args.git_bin)
        if mode is not None and mode != "040000":
            print(
                f"stage_council_journal: council_run: '{declared}' cancels '{prefix}', which exists "
                f"at HEAD but is not a directory (mode {mode}) — lexical and symlink-aware "
                "resolution would name different files, so staging nothing"
            )
            return 0

    journal_source = (source_dir / relpath).as_posix()
    blob = journal_bytes_at_head(repo, args.head_sha, journal_source, args.git_bin)
    if blob is None:
        print(
            f"stage_council_journal: pack declares council_run: '{declared}' but '{journal_source}' "
            "is not a regular file at HEAD — staging nothing, R9 will judge the pack on that"
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
