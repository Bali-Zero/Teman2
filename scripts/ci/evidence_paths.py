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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
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


def _build_result(ref: str) -> dict[str, str]:
    return {
        "ref": ref,
        "slug": slug_for_ref(ref),
        "glob": evidence_glob(ref),
        "suggested_write_path": suggested_write_path(ref),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Map a git branch ref to its per-PR evidence directory slug/glob."
        )
    )
    parser.add_argument("--ref", required=True, help="Git branch ref, e.g. agent/host/lane/task")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

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
