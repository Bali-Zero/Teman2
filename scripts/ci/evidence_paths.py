#!/usr/bin/env python3
"""Map a git branch ref to that PR's evidence directory slug.

Why this exists (S12/C6, 2026-08-23): ``evidence/pack.yml`` and
``evidence/brief.yml`` used to be FIXED paths at repo root, and every
Gear>=2 PR rewrote them entirely. Measured on origin/main: those two files
were rewritten 4 times in 8 hours (#4599, #4649, #4647, #4646). Each rewrite
dirties EVERY open Gear>=2 PR simultaneously, so two such PRs could never
coexist cleanly in the merge queue — by construction, not by bad luck. This
module is the single source of truth for turning a branch ref into a
per-PR evidence directory (``evidence/<YYYY-MM>/<slug>/``) so CI and humans
never rewrite each other's files again.

THE SLUG RULES — each one exists because a specific thing went wrong:

1. Sanitize: lowercase; every character outside ``[a-z0-9]`` becomes ``-``;
   collapse runs of ``-``; strip leading/trailing ``-``.
2. Truncate the sanitized part to at most ``_MAX_SANITIZED_LEN`` (48)
   characters — branch names here are long
   (``agent/<host>/<lane>/<task>``).
3. ALWAYS append ``-`` + the first 8 hex chars of ``sha256(ref)`` — of the
   FULL ORIGINAL REF, never the sanitized/truncated form.

Rule 3 is NON-NEGOTIABLE and is the whole point of this module. Branches
here live under ``agent/<host>/<lane>/<task>`` and are full of hyphens:
sanitizing ``/`` -> ``-`` makes ``agent/a/b-c`` and ``agent/a-b/c`` collapse
to the identical string ``agent-a-b-c``. Two different branches sharing one
evidence directory would recreate the exact collision this module removes
— but silently, with no git conflict to surface it, which is strictly
worse than the problem it replaces. (Family #3 in
``.claude/rules/cicatrix-superscar.md`` — "guard/mapping over substring" —
already has a scar about a path truncation that collapsed distinct names;
don't repeat it here.) The hash is computed over the *original* ref
precisely so that two refs which sanitize identically still diverge: the
sanitized-and-truncated prefix is for human readability only, the hash
suffix is what actually guarantees injectivity.

THE MONTH IS A GLOB, NEVER A COMPUTED VALUE. The write-time directory is
``evidence/<YYYY-MM>/<slug>/``, but CI must never compute "the current
month" to go looking for a PR's evidence. A PR opened 2026-08-31 and
landed 2026-09-01 would have its files under ``evidence/2026-08/`` while a
clock-derived validator looked under ``evidence/2026-09/`` and found
nothing — a false "no evidence" failure caused entirely by wall-clock
timing, not by the PR. So ``evidence_glob()`` returns
``evidence/*/<slug>``, and the month is only ever *read* from wherever the
directory actually landed. The CLI's "suggested write path for today" is
the ONLY place in this module a date is generated, and it is a write-time
convenience for a human invoking the CLI, never a value fed back into
validation. Resist the urge to "simplify" this into a computed month
somewhere on the read path — that is precisely the bug described above.

CI MUST NOT COMPUTE THE SLUG — IT MUST DISCOVER THE PATH INSTEAD. This is
a second, sharper instance of the same "don't derive from a clock/ref you
don't control" lesson as the month rule above, and it is why this module
also ships ``resolve_evidence_path`` / ``--resolve`` alongside
``slug_for_ref`` / ``--ref``. On a ``merge_group`` event the ref GitHub
hands CI is ``gh-readonly-queue/main/pr-NNNN-<sha>`` — NOT the PR's own
branch ref. Feeding that into ``slug_for_ref`` would compute a DIFFERENT
slug than the one the PR's author used when writing its evidence files on
``pull_request``, so a Gear-3 PR would pass its own ``pull_request`` run
and then fail in the merge queue looking for a directory that was never
going to exist under that ref. ``slug_for_ref`` stays exactly as written —
it is the correct, collision-safe tool for a HUMAN/CI-at-PR-open-time to
pick a write-time directory. It is simply the wrong tool for CI to use
later to find that directory again. For that, CI reads its own
``changed-files`` enumeration (already computed once per run, merge-base
anchored, per ``hotzone_changed_files.sh`` — never re-derived from a ref)
and asks "which ``evidence/<kind>.yml`` did THIS diff actually touch" —
see ``resolve_evidence_path`` below.

THE ``brief_ref:`` CONTRACT — READ THIS BEFORE WRITING A NEW PACK. A
per-PR pack living at e.g. ``evidence/2026-08/<slug>/pack.yml`` must
still declare ``brief_ref: evidence/brief.yml`` — NEVER
``brief_ref: evidence/2026-08/<slug>/brief.yml``, even though the latter
looks like the "obviously correct" value once the files have moved out
of the repo root. Why: ``scripts/evidence_pack_lint.py`` never validates
a pack in place. CI (``harness-floor.yml``'s Step 7b) stages both the
resolved pack and the resolved brief into a synthetic tree under
``/tmp/evidence-check/evidence/{pack,brief}.yml`` (canonical names,
always) and lints THAT tree via ``--repo-root /tmp/evidence-check`` — so
``brief_ref`` is resolved against the STAGING layout, not the real repo
layout. A pack that "correctly" points at its own real per-PR brief path
fails that resolution (``brief_ref: '...' does not resolve to a file on
disk``) with a message that says nothing about staging vs. real layout —
exactly the shape of trap this module exists to remove. Always write the
literal ``evidence/brief.yml``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from datetime import datetime, timezone

_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")
_MAX_SANITIZED_LEN = 48
_HASH_SUFFIX_LEN = 8


def _sanitize(ref: str) -> str:
    """Lowercase ``ref``, collapse every non-alphanumeric run to one ``-``.

    Leading/trailing dashes are stripped. This alone is NOT collision-safe
    (see module docstring, Rule 3) — it exists purely to keep the slug
    human-readable; ``slug_for_ref`` is what guarantees uniqueness.
    """
    lowered = ref.lower()
    collapsed = _NON_ALNUM_RUN.sub("-", lowered)
    return collapsed.strip("-")


def slug_for_ref(ref: str) -> str:
    """Return the evidence-directory slug for a git branch ref.

    Deterministic and injective: distinct ``ref`` values always produce
    distinct slugs, even when they sanitize to the same string (e.g.
    ``agent/a/b-c`` and ``agent/a-b/c`` both sanitize to ``agent-a-b-c``,
    but the sha256 suffix over the full original ref keeps their slugs
    apart). See the module docstring for why the hash is non-negotiable.

    Args:
        ref: A git branch ref, e.g. ``agent/mini-pro2/infra/task-id``.
            Any string is accepted, including one with no alphanumeric
            characters at all (e.g. ``"///"``) or an empty string — the
            hash suffix alone still makes the result unique and non-empty.

    Returns:
        A slug matching ``^[a-z0-9]+(-[a-z0-9]+)*-[0-9a-f]{8}$`` — safe to
        use as a single path segment (no ``/``, no leading/trailing ``-``).
    """
    digest = hashlib.sha256(ref.encode("utf-8")).hexdigest()[:_HASH_SUFFIX_LEN]
    sanitized = _sanitize(ref)[:_MAX_SANITIZED_LEN].strip("-")
    if not sanitized:
        # A ref with no alphanumeric content (e.g. "///", "", "---") would
        # otherwise produce a bare hash or a leading-dash string. Fall back
        # to a fixed literal so the slug shape is never dash-only/empty on
        # its non-hash side.
        return f"ref-{digest}"
    return f"{sanitized}-{digest}"


def evidence_glob(ref: str) -> str:
    """Return the glob CI uses to find ``ref``'s evidence pack anywhere
    under ``evidence/``.

    This is a glob rather than a concrete path because the month directory
    a PR's evidence lands in is a write-time fact, not something derivable
    from "now" at read time — see the module docstring's "month is a glob"
    section. The returned string always contains exactly one ``*`` and
    ends with the slug for ``ref``.
    """
    return f"evidence/*/{slug_for_ref(ref)}"


def suggested_write_path(ref: str, *, today: datetime | None = None) -> str:
    """Return the suggested write-time evidence directory for ``ref``.

    This is the ONLY place in this module a date is generated. It is a
    convenience for a human/CI job writing evidence *right now* — it must
    never be used to *look up* an existing PR's evidence (use
    ``evidence_glob`` for that). ``today`` is injectable for testability;
    defaults to the current UTC date.
    """
    stamp = today or datetime.now(timezone.utc)
    return f"evidence/{stamp:%Y-%m}/{slug_for_ref(ref)}/"


class AmbiguousEvidencePathError(ValueError):
    """Raised by ``resolve_evidence_path`` when a PR's own diff touches more
    than one ``evidence/<kind>.yml`` candidate.

    Two evidence directories in one diff is ambiguous and must fail
    closed, never silently pick one — "just take the first match" is
    precisely the guard-over-match disease (family #3 in
    ``.claude/rules/cicatrix-superscar.md``): a guard that resolves
    ambiguity by guessing is a guard that can be fooled.
    """


def _evidence_pattern(kind: str) -> re.Pattern[str]:
    if kind not in ("brief", "pack"):
        raise ValueError(f"unknown evidence kind: {kind!r} (must be 'brief' or 'pack')")
    # Anchored, full-line match against a changed-file path — never a bare
    # substring test (superscar #3: a substring guard is how W68/W72/W73
    # happened). The literal root path ("evidence/pack.yml") deliberately
    # does NOT match this pattern: after "evidence/" there is no further
    # "/" left for ".*/ " to consume before "pack.yml", so the un-migrated
    # root file can never be misread as a per-PR nested path.
    return re.compile(rf"^evidence/.*/{re.escape(kind)}\.yml$")


def resolve_evidence_path(kind: str, changed_files: Iterable[str]) -> str:
    """Discover which ``evidence/<kind>.yml`` path THIS PR's own diff touches.

    This is a DISCOVERY function operating on a changed-files list, never
    a computation from a branch ref — see the module docstring's "CI must
    not compute the slug" section for why ``slug_for_ref`` is the wrong
    tool for this job (a ``merge_group`` ref is not the PR's branch ref).

    Args:
        kind: ``"brief"`` or ``"pack"``.
        changed_files: This PR's own changed-file paths (e.g. the lines of
            ``hotzone_changed_files.sh``'s output) — POSIX-style relative
            paths, one file per element.

    Returns:
        - Exactly one path in ``changed_files`` matches
          ``^evidence/.*/<kind>\\.yml$`` -> that path.
        - Zero matches -> the ROOT path ``evidence/<kind>.yml``. This
          preserves pre-migration behavior exactly for every PR that has
          not adopted a per-PR evidence directory yet. It is also what
          keeps the "a PR that writes NEITHER path must not pass by
          inheriting root evidence/pack.yml" invariant honest: the
          returned root path is still handed to
          ``scripts/ci/tracked_file_present_in_diff.sh``, which reports it
          ``inherited`` (not ``present``) when this diff didn't actually
          touch it, and the existing hot-zone gate fails closed on that.
          This function must never special-case that away — it always
          returns a concrete path, never an empty string, never a
          "not found" sentinel that a caller could forget to check.

    Raises:
        AmbiguousEvidencePathError: two or more matches — see that
            exception's docstring.
    """
    pattern = _evidence_pattern(kind)
    matches = [path for path in changed_files if pattern.match(path)]
    if len(matches) > 1:
        raise AmbiguousEvidencePathError(
            f"{len(matches)} evidence/{kind}.yml candidates in this PR's "
            f"diff (ambiguous, refusing to guess which one is THIS PR's "
            f"evidence): {matches!r}"
        )
    if matches:
        return matches[0]
    return f"evidence/{kind}.yml"


def _build_result(ref: str) -> dict[str, str]:
    return {
        "ref": ref,
        "slug": slug_for_ref(ref),
        "glob": evidence_glob(ref),
        "suggested_write_path": suggested_write_path(ref),
    }


def _read_changed_files(path: str) -> list[str]:
    """Read a newline-delimited changed-files list (blank lines dropped).

    Same format ``hotzone_changed_files.sh`` writes to
    ``/tmp/changed-files.txt`` in the CI workflows — this module does not
    invent a second format.
    """
    with open(path, encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Map a git branch ref to its per-PR evidence directory slug/glob "
            "(--ref), or discover THIS PR's evidence/<kind>.yml path from its "
            "own changed-files list (--resolve) — see the module docstring "
            "for why these are two different operations, not one."
        )
    )
    parser.add_argument("--ref", help="Git branch ref, e.g. agent/host/lane/task")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON (--ref mode only)")
    parser.add_argument(
        "--resolve",
        choices=["brief", "pack"],
        help=(
            "Discovery mode: print THIS PR's own evidence/<kind>.yml path, "
            "found in --changed-files-file. Mutually exclusive with --ref."
        ),
    )
    parser.add_argument(
        "--changed-files-file",
        help="Path to a newline-delimited changed-files list (required with --resolve).",
    )
    args = parser.parse_args(argv)

    if args.resolve:
        if args.ref:
            parser.error("--ref and --resolve are mutually exclusive")
        if not args.changed_files_file:
            parser.error("--resolve requires --changed-files-file")
        changed_files = _read_changed_files(args.changed_files_file)
        try:
            resolved = resolve_evidence_path(args.resolve, changed_files)
        except AmbiguousEvidencePathError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(resolved)
        return 0

    if not args.ref:
        parser.error("--ref is required unless --resolve is given")

    result = _build_result(args.ref)

    if args.json:
        print(json.dumps(result))
    else:
        print(f"slug: {result['slug']}")
        print(f"glob: {result['glob']}")
        print(f"suggested_write_path: {result['suggested_write_path']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
