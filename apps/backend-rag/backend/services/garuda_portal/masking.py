"""Recipient-identifier masking for the GARUDA VOA magic-link preview.

`previewMagicLink` (`garuda_portal_auth.py`) answers "whose application does
this token open?" before the customer spends it -- but the whole reason it
is safe to leave that operation unauthenticated (like every other operation
on this router; see `magic_link.py`'s module docstring) is that its answer
discloses just enough for someone who ALREADY knows the address to
recognise it, and nothing a stranger holding the same link could use to
learn it. This module owns exactly that boundary, in one place, so a future
call site cannot reinvent a weaker rule.

Rule: reveal the first two characters of the local part only when the local
part is longer than two characters; otherwise reveal none of it. The
remainder is replaced by a FIXED three-asterisk mask -- never one sized to
the actual remaining length -- because a variable-width mask leaks the
local part's length, which narrows a guess. The domain is left untouched: a
common domain (gmail.com, or a corporate domain already public on a
business card) identifies a provider, not a person -- the same line every
masking convention this module is aware of already draws (GitHub, Google's
own account chooser).

The two SHORT cases are the ones a naive "reveal all but the last
character" rule gets wrong: a one-character local part would reveal it in
full (0 characters left to mask), and a two-character local part would
reveal half of it while still calling itself "masked". Both are treated as
fully opaque here -- zero characters revealed -- rather than as a smaller
version of the normal case.
"""

from __future__ import annotations

__all__ = ["mask_email"]

#: Local parts at or below this length reveal nothing -- see module
#: docstring for why the naive "keep the first char" rule is wrong here.
_LOCAL_PART_REVEAL_THRESHOLD = 2
#: Fixed width, never proportional to the actual remaining length.
_MASK = "***"


def mask_email(email: str) -> str:
    """Mask `email`'s local part for display back to its own owner.

    Never raises: a value this module cannot parse as `local@domain` masks
    to the fixed sentinel below rather than propagating an exception into a
    response path whose entire job is to be safe by default.
    """
    local, sep, domain = email.rpartition("@")
    if not sep or not domain:
        return _MASK
    visible = local[:_LOCAL_PART_REVEAL_THRESHOLD] if len(local) > _LOCAL_PART_REVEAL_THRESHOLD else ""
    return f"{visible}{_MASK}@{domain}"
