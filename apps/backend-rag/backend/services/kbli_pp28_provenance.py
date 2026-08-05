"""Whose PP 28/2025 licensing rows is this KBLI code actually serving?

A KBLI-2025 code that is NEW in the 2025 numbering has no PP 28/2025 licensing
row of its own — PP 28 was written against the 2020 numbering. The canonical
dataset fills those codes from their KBLI-2020 ancestors and records where it
took the rows from, in `pp28_sources`. Measured on the 1,559-code canonical:
**390** codes serve licensing content sourced ONLY from other codes, and
**217** of those inherit a `pb_umku` permit that way.

The visible harm this closes: `inspect_kbli 62110` (video game development,
sourced from five 62xxx computer-programming codes) returns three
defence-industry permits — "Industri Kelaikan Produksi Alat Peralatan
Pertahanan" and friends. They are really in the canonical record, so this is
not a data bug to delete; they belong to the ANCESTOR activity, and a client
told to obtain them would be sent somewhere no video-game studio needs to go.

WHY A SEPARATE SIGNAL FROM `_l2_source`. `_l2_source` names the OSS-RBA **risk**
source, and the two disagree: a code can be genuinely 2025-native on risk while
its licensing content is carried. Reading one for the other is what let this
survive.

WHY THIS SURFACE DISCLOSES INSTEAD OF GOING SILENT. The indexed `<meta>` on the
web page suppresses the licence type entirely, because a `<title>` has no room
for a qualifier (`apps/mouth/src/lib/kbli-meta.ts`). `inspect_kbli` returns
structured JSON to a model that CAN carry a qualifier, so here the rows stay
and name their source — same fact, opposite correct answer, which is why the
two surfaces get two helpers rather than one shared flag.

The rule below is the Python counterpart of `pp28ContentInheritedFrom` in
`apps/mouth/src/lib/kbli-provenance.ts`. Two languages cannot share a function,
so they share a PINNED MEMBERSHIP instead: the test hashes the sorted list of
inherited codes, not just its length — two divergent implementations can both
answer 390 while disagreeing about WHICH 390.

THEY ARE NOT BYTE-FOR-BYTE IDENTICAL, and the difference is stated rather than
papered over (an adversarial review caught the earlier "exact twin" claim). On
inputs the canonical does not contain, they diverge two ways:

  - whitespace: `[" 62110 "]` on own code `62110` — Python strips and reads
    self-sourced (silent); TypeScript does not strip and reads inherited.
  - `null` entries: TypeScript's `String(null)` yields the client-visible
    source code `"null"`; Python drops it.

Measured on the canonical: **0** padded entries and **0** non-string entries out
of 1,735. So both divergences are latent, and the Python side takes the
fail-safe reading of each. The TypeScript fix is a follow-up (its file is under
an open PR); until it lands, the hash pin is what would catch a real drift.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def content_inherited_from(pp28_sources: Any, own_code: Any) -> list[str] | None:
    """The OTHER codes this record's PP 28 licensing rows came from, or None.

    None means "nothing to disclose", and it covers two different worlds on
    purpose:

    - **self-sourced** — the record's own code appears in `pp28_sources`, so it
      HAS a row of its own; any extra entries are supplements, not a
      substitution.
    - **nothing recorded** — `pp28_sources` absent or empty (175 codes). Absence
      is not evidence. This signal exists to qualify a claim, and qualifying one
      on missing data would be asserting an inheritance we cannot show.

    Both return the permissive answer. The failure mode is a missing note, never
    an invented provenance.
    """
    if isinstance(pp28_sources, (str, bytes)) or not isinstance(pp28_sources, Iterable):
        # A scalar where a list belongs is malformed input, not an inheritance
        # claim — and iterating a str would yield characters, which is how a
        # code like "62011" becomes five phantom sources.
        return None

    # `str(None)` is "None", which is truthy and would be printed to a client as
    # a source KBLI code that does not exist. Drop non-strings BEFORE stringify
    # rather than after — found by the fail-safe test, not by a live record:
    # the canonical carries 1,735 entries and all 1,735 are strings today.
    sources: list[str] = []
    for entry in pp28_sources:
        # `bool` is a subclass of `int`, and "True" is not a KBLI code either.
        if not isinstance(entry, (str, int)) or isinstance(entry, bool):
            continue
        text = str(entry).strip()
        if text:
            sources.append(text)
    if not sources:
        return None

    own = str(own_code or "").strip()
    if own and own in sources:
        return None

    return sources


def inherited_licensing_note(sources: list[str] | None) -> str | None:
    """The sentence a model can pass through to a client, or None.

    Built FROM the list rather than beside it, so the note and the codes cannot
    drift apart: there is one derivation, and the note is a rendering of it.
    """
    if not sources:
        return None
    plural = "s" if len(sources) > 1 else ""
    return (
        f"This code has no PP 28/2025 licensing row of its own — the licences "
        f"listed were carried over from KBLI code{plural} {', '.join(sources)}. "
        f"They may belong to the source activity rather than this one; confirm "
        f"the licence type with the Bali Zero team before acting on it."
    )


def licensing_disclosure(
    pp28_sources: Any, own_code: Any, has_licenses: bool
) -> tuple[list[str] | None, str | None]:
    """The full decision for one `inspect_kbli` response: (codes, note).

    `has_licenses` is the second half of the rule and it lives HERE rather than
    inline at the call site, because a rule written where nothing can exercise
    it is a rule that is not enforced. A response listing no licences must not
    carry a sentence about "the licences listed" — that would be an assertion
    about nothing, which is the same class of harm as an unqualified one.

    Returned together so the two response fields have a single derivation and
    cannot be updated one without the other.
    """
    if not has_licenses:
        return None, None
    sources = content_inherited_from(pp28_sources, own_code)
    return sources, inherited_licensing_note(sources)
