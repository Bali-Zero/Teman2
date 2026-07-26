"""_prose_disclosure.py — the ONE rule for the risk-tier disclosure paragraph.

`intel_2026.whatYouNeed` now has two writers, and they had different ideas about
what the field is:

  - `cure_canonical_collisions.py` (lot cures) owns the BODY. Its contract is that
    the body equals its spec's honest-gap text VERBATIM — "never paraphrase or
    invent it" — and its idempotency check is that same equality.
  - `cure_l3_prose_gap_disclosure.py` APPENDS a recorded risk-tier disclosure
    paragraph to 152 records, 5 of which a lot cure also owns.

Measured before this module existed: after the append, the lot-2 compiler reported
`42999: intel_2026.whatYouNeed -> honest-gap` — i.e. its next run would have
rewritten the body back to the spec text and DESTROYED the disclosure, silently, on
a page that needs it. Not a failing test: a cure reverting a cure.

So the rule lives in one place and both writers read it here (the same reason
`_l4bali_basis` is shared between the l4_bali census and its writer — two modules
that must never disagree about a predicate should not each own a copy of it):

    body = <base, owned by whoever owns the body> + <at most one disclosure appendix>

`split_disclosure` separates the two; `reattach` puts an appendix back after the
body owner rewrites its half. A lot cure therefore compares and writes only the
BASE, and carries the appendix across untouched.

The pattern is anchored at END-OF-STRING on purpose (same discipline as
`cure_l4bali_disclosure.LEGACY_SUFFIX_RE`): a body that a human edited after the
append no longer matches, and is left alone and reported rather than re-shaped on a
guess about where the paragraph ended.
"""

from __future__ import annotations

import re

DISCLOSURE_HEADING = "**Risk tier under review.**"

# `\n\n**Risk tier under review.** <one line>` at the very end of the body.
DISCLOSURE_RE = re.compile(r"\n\n\*\*Risk tier under review\.\*\* [^\n]+$")


def split_disclosure(body: str) -> tuple[str, str]:
    """(base, appendix). `appendix` is "" when there is no anchored disclosure."""
    if not isinstance(body, str):
        return body, ""
    stripped = body.rstrip()
    match = DISCLOSURE_RE.search(stripped)
    if not match:
        return body, ""
    return stripped[: match.start()].rstrip(), stripped[match.start():]


def reattach(base: str, appendix: str) -> str:
    """Put an appendix back after a body rewrite. No appendix → base unchanged."""
    if not appendix:
        return base
    return base.rstrip() + appendix
