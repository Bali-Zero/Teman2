#!/usr/bin/env python3
"""_whatchanged_basis.py — one decision function for the `whatChanged` field.

WHY THIS MODULE EXISTS
----------------------
`whatChanged` answers "what changed for this code between KBLI 2020 and 2025?"
on every `/kbli/<code>` page. It lives on **three live surfaces that hold three
different vintages of the same sentence**:

  1. canonical `intel_2026.whatChanged` — the dataset (+ its synced copies)
  2. `apps/mouth/data/kbli-gold-all.json` — the editorial layer, 428 codes,
     which **WINS over canonical on the rendered page** (`kbli-data.server.ts`
     `transformCode`: `whatChanged: goldEntry.whatChanged`, and `page.tsx:428`
     renders `gold.whatChanged` directly). Curing canonical alone changes
     nothing a client sees for those 428.
  3. `kg_nodes.properties.whatChanged` — 1,554 nodes, read by `inspect_kbli`,
     i.e. WhatsApp / webchat / kbli-explorer. Its texts are their own vintage
     (measured 2026-07-25: same defect counts as canonical, different lengths).

Three surfaces × three defects is nine chances for a selector to drift apart.
So every surface calls exactly ONE function here — `plan_text` — and no surface
is allowed its own copy of a predicate. Same lesson as `_l4bali_basis.py`.

THE THREE DEFECTS
-----------------
**A · false renumbering claim.** The text opens with the template sentence
"Renumbered/adjusted from KBLI 2020." while the record carries **no predecessor
at all** — `pp28_sources` empty, `kbli_2020_source` null, `bps_2020_ancestors`
null. `64995` contradicts itself inside one paragraph: the template says
renumbered, the body says _"Codice completamente nuovo in KBLI 2025 … Nessuna
migrazione da KBLI 2020 necessaria"_.

**B · mid-word truncation.** Exactly 216 characters, no terminal punctuation,
cut mid-word — "…the modern evolution of a press th". A client reads that.

**C · contradicted predecessor.** The text names an explicit "KBLI 2020: <code>"
that appears in **none** of the record's three crosswalk layers. Four cases, and
two of them invert the advice a client would act on: `46415` and `46496` say
"→ KBLI 2025: 46415 (confermato)" — *your code is unchanged, just refresh the
NIB* — while `status_mapping` is `CODICE_RINUMERATO` and the layers record a
DIFFERENT 2020 origin. A business operating under the 2020 code would be told
nothing changed.

WHY C IS CURED BY DELETION, NEVER BY CORRECTION
-----------------------------------------------
We cannot substitute "the right number", because on `46415` the layers do not
agree with each other either (PP28/`kbli_2020_source` say 46694, BPS says
46419) — any substitution would be us picking a winner and publishing it as
fact, which is the disease, not the cure. So the unsupported sentence is
replaced by a statement of what our records actually hold, all of it, with the
mapping declared unconfirmed. Honesty over completeness (corner §0): a declared
gap is acceptable, a plausible-but-wrong assertion is not. Which layer is true
is a source adjudication, tracked separately — not something a compiler decides.

ORDER
-----
Detection runs on the ORIGINAL text for all three passes, because B's evidence
IS the original length; rewriting first would erase the signature. Application
is A → C → B, so the trim always runs last and cannot leave a fragment behind.
"""

from __future__ import annotations

import re
from typing import Any

PASS_FALSE_CLAIM = "false_renumbering_claim"
PASS_CONTRADICTED_PREDECESSOR = "contradicted_predecessor"
PASS_TRUNCATED = "midword_truncation"

ALL_PASSES = (PASS_FALSE_CLAIM, PASS_CONTRADICTED_PREDECESSOR, PASS_TRUNCATED)

FALSE_CLAIM = "Renumbered/adjusted from KBLI 2020."
HONEST_CLAIM = "No KBLI-2020 predecessor is recorded for this code."

TRUNCATION_LENGTH = 216

_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_NAMED_PREDECESSOR = re.compile(r"KBLI 2020:\s*(\d{5})")
_ENDS_COMPLETE = re.compile(r"[.!?]\s*$")


class WhatChangedError(RuntimeError):
    """A record or text drifted from the state these rewrites were written for."""


# ---------------------------------------------------------------------------
# Record predicates — the FACTS. Never read from prose.
# ---------------------------------------------------------------------------


def recorded_predecessors(record: dict[str, Any]) -> set[str]:
    """Every KBLI-2020 code our three crosswalk layers record for this record.

    Union, deliberately: a claim is contradicted only when NO layer backs it,
    so a disagreement between layers can never manufacture a false positive.
    """
    found: set[str] = set()

    direct = record.get("kbli_2020_source")
    if direct:
        found.add(str(direct))

    for entry in record.get("pp28_sources") or []:
        if isinstance(entry, dict):
            code = entry.get("kode") or entry.get("code") or entry.get("kode_kbli_2020")
        else:
            code = entry
        if code:
            found.add(str(code))

    ancestors = record.get("bps_2020_ancestors") or {}
    for code in ancestors.get("codes") or []:
        if code:
            found.add(str(code))

    return found


def _layer_rows(record: dict[str, Any]) -> list[Any]:
    """Every crosswalk ROW on the record, parseable or not."""
    rows: list[Any] = []
    if record.get("kbli_2020_source"):
        rows.append(record["kbli_2020_source"])
    rows.extend(record.get("pp28_sources") or [])
    rows.extend((record.get("bps_2020_ancestors") or {}).get("codes") or [])
    if record.get("bps_2020_ancestors") and not (record["bps_2020_ancestors"].get("codes") or []):
        rows.append(record["bps_2020_ancestors"])
    return rows


def has_no_recorded_predecessor(record: dict[str, Any]) -> bool:
    """True when all THREE crosswalk layers hold NO ROW AT ALL.

    Deliberately presence-based, not code-extraction-based. A layer row whose
    code this parser cannot read still means a source is on file, so the
    "renumbered" sentence is defensible and pass A must keep its hands off it.
    Reading "I could not extract a code" as "there is no predecessor" is how a
    schema change would silently turn a true sentence into a deletion.
    (Measured 2026-07-25: all 1,735 pp28 rows are plain code strings and every
    `bps_2020_ancestors` carries a `codes` list, so the two readings agree on
    today's data — the divergence is a future-proofing, not a live difference.)
    """
    return not _layer_rows(record)


def has_unreadable_layer_rows(record: dict[str, Any]) -> bool:
    """Rows are on file but none yielded a code — the record is UNDECIDABLE."""
    return bool(_layer_rows(record)) and not recorded_predecessors(record)


def named_predecessors(text: str) -> set[str]:
    """The 2020 codes the PROSE names explicitly ("KBLI 2020: 46415")."""
    return set(_NAMED_PREDECESSOR.findall(text))


def contradicted_predecessors(text: str, record: dict[str, Any]) -> set[str]:
    """Named in the prose, recorded by no layer. Empty set = nothing to answer for.

    A record whose rows exist but cannot be read yields the empty set: we cannot
    tell whether the prose is contradicted, and UNDECIDABLE is not the same as
    CLEAN — it just means this pass has no standing to delete anything.
    """
    if has_unreadable_layer_rows(record):
        return set()
    return named_predecessors(text) - recorded_predecessors(record)


def claims_a_renumbering(text: str) -> bool:
    return text.startswith(FALSE_CLAIM)


def is_truncated_midword(text: str) -> bool:
    """The signature: exactly 216 chars AND no terminal punctuation.

    Length alone is not evidence — a text that happens to be 216 characters and
    ends in a period is simply a text. Both halves are required.
    """
    return len(text) == TRUNCATION_LENGTH and not _ENDS_COMPLETE.search(text)


# ---------------------------------------------------------------------------
# Rewrites — each one PURE, each one refusing to fire on a text it doesn't own
# ---------------------------------------------------------------------------


def swap_false_claim(text: str) -> str:
    """Swap the leading sentence, preserve every following byte."""
    if not claims_a_renumbering(text):
        raise WhatChangedError(f"text does not open with the template sentence: {text[:60]!r}")
    return HONEST_CLAIM + text[len(FALSE_CLAIM) :]


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for match in _SENTENCE_END.finditer(text):
        spans.append((start, match.end()))
        start = match.end() + 1 if match.end() < len(text) else match.end()
        while start < len(text) and text[start] == " ":
            start += 1
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def unconfirmed_crosswalk_sentence(named: set[str], recorded: set[str]) -> str:
    """The replacement text. Every value in it comes from the record — nothing invented."""
    named_str = ", ".join(sorted(named))
    if recorded:
        holds = ", ".join(sorted(recorded))
        tail = f"our crosswalk sources on file record {holds} instead"
    else:
        tail = "no crosswalk source on file records any predecessor"
    return (
        f"The KBLI-2020 origin published here ({named_str}) is not supported by our "
        f"records — {tail}, so the 2020-to-2025 mapping for this code is unconfirmed "
        f"pending re-verification (GARUDA-FILIERA)."
    )


def drop_contradicted_predecessor(text: str, record: dict[str, Any]) -> str:
    """Replace the sentence that names an unsupported predecessor. Never renumber it."""
    contradicted = contradicted_predecessors(text, record)
    if not contradicted:
        raise WhatChangedError("no contradicted predecessor in this text — nothing to drop")

    spans = [
        (start, end)
        for start, end in _sentence_spans(text)
        if named_predecessors(text[start:end]) & contradicted
    ]
    if not spans:  # pragma: no cover - a match outside every span is structurally impossible
        raise WhatChangedError("contradicted predecessor matched no sentence span")

    replacement = unconfirmed_crosswalk_sentence(contradicted, recorded_predecessors(record))
    out, cursor, written = [], 0, False
    for start, end in spans:
        out.append(text[cursor:start])
        if not written:  # one honest sentence, however many spans carried the claim
            out.append(replacement)
            written = True
        else:
            out.append("")
        cursor = end
    out.append(text[cursor:])
    return re.sub(r"  +", " ", "".join(out)).strip()


def trim_to_last_complete_sentence(text: str) -> str | None:
    """Drop the trailing fragment. None when there is no complete sentence to keep."""
    ends = [m.end() for m in _SENTENCE_END.finditer(text)]
    if not ends:
        return None
    return text[: ends[-1]].rstrip()


# ---------------------------------------------------------------------------
# THE one decision function — every surface calls this and nothing else
# ---------------------------------------------------------------------------


def plan_text(text: str, record: dict[str, Any]) -> tuple[str, list[str]]:
    """Return (cured_text, passes_applied) for one text on any surface.

    `text` is whatever THIS surface holds (surfaces carry different vintages);
    `record` is always the CANONICAL record, because the crosswalk facts live
    there and nowhere else. Returns the text unchanged with an empty pass list
    when nothing is wrong — callers select on a non-empty list, never on a
    marker of their own.
    """
    if not text:
        return text, []

    applied: list[str] = []
    # Detect everything on the ORIGINAL: pass B's evidence is the original length.
    do_false_claim = claims_a_renumbering(text) and has_no_recorded_predecessor(record)
    do_contradicted = bool(contradicted_predecessors(text, record))
    do_trim = is_truncated_midword(text) and trim_to_last_complete_sentence(text) is not None

    cured = text
    if do_false_claim:
        cured = swap_false_claim(cured)
        applied.append(PASS_FALSE_CLAIM)
    if do_contradicted:
        cured = drop_contradicted_predecessor(cured, record)
        applied.append(PASS_CONTRADICTED_PREDECESSOR)
    if do_trim:
        trimmed = trim_to_last_complete_sentence(cured)
        if trimmed is None:  # pragma: no cover - guarded by do_trim
            raise WhatChangedError("no complete sentence survived the earlier passes")
        cured = trimmed
        applied.append(PASS_TRUNCATED)

    if applied and cured == text:  # pragma: no cover - a pass that changes nothing is a bug
        raise WhatChangedError(f"passes {applied} claimed to fire but produced identical text")
    return cured, applied
