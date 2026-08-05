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
PASS_FALSE_CONTINUITY = "false_continuity_claim"
PASS_TRUNCATED = "midword_truncation"

ALL_PASSES = (
    PASS_FALSE_CLAIM,
    PASS_CONTRADICTED_PREDECESSOR,
    PASS_FALSE_CONTINUITY,
    PASS_TRUNCATED,
)

FALSE_CLAIM = "Renumbered/adjusted from KBLI 2020."
HONEST_CLAIM = "No KBLI-2020 predecessor is recorded for this code."

TRUNCATION_LENGTH = 216

_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_NAMED_PREDECESSOR = re.compile(r"KBLI 2020:\s*(\d{5})")
_ENDS_COMPLETE = re.compile(r"[.!?]\s*$")

# Pass D fires only on wordings that assert the NUMBER carried over. "Direct
# match from KBLI 2020" is deliberately NOT here: it is ambiguous between "the
# same number" and "a clean 1:1 activity mapping", and 49213's own sentence
# resolves it the second way ("this is the same urban-transport activity carried
# forward"). Deleting on ambiguity would remove possibly-true prose.
#
# MEASURED COST OF THAT CHOICE, so it is a declared limit and not a silent one
# (2026-08-05, canonical + gold, union of all three crosswalk layers): the broad
# pattern reaches 27 (code, surface) pairs across 21 codes, this narrow one
# reaches 17 across 14. The 10 uncovered pairs are reported by `--census` under
# `ambiguous_continuity`, never cured.
#
# WIDENED 2026-08-05 AFTER A LIVE UNDER-MATCH ON THE THIRD SURFACE (superscar #3,
# the W82 twin). The census above was measured on canonical + gold ONLY. The KG
# — which feeds `inspect_kbli`, i.e. WhatsApp and webchat — phrases the same
# assertion differently, so the guard read it as innocent: 11 of the 14 codes
# cured on the website were still telling clients, on every conversational
# channel, "Direct 1:1 match from KBLI 2020 — code and scope unchanged." Eight
# nodes carried that exact sentence and one carried "keep the same code and
# scope"; `number_is_discontinuous` was True on all eleven. A pattern written
# from the instances you happened to look at catches the instances you happened
# to look at — so this alternation is now written around the ASSERTION ("the
# code did not change") rather than around a phrasing, and the census is
# measured over all THREE surfaces.
#
# Still NOT here, deliberately, and still reported by `--census`: the two
# remaining live shapes assert something narrower than the number. `68210` says
# "Direct match from KBLI 2020, BUT the PP28 source code is 68200", which names
# a different number in the same breath; `86992` says the "classification" is
# unchanged, which is a claim about the activity, not about the digits.
# A SAME-CODE PHRASE ONLY SPEAKS ABOUT 2020 WHEN A 2020 MARKER IS PRESENT.
# An independent cross-family review (Codex GPT-5.6, instructed to refute)
# produced the sentence "The NIB entry keeps the same code and scope when you
# amend the address; its KBLI 2020 predecessor is 62010." The first draft of the
# widening convicted it: true prose about an ADDRESS AMENDMENT, deleted from a
# client-facing page. So the weak phrases below are not standalone triggers —
# they resolve the ambiguity of the 2020 match marker, and only in its presence.
# That is also the honest reading of what makes them a claim: "code and scope
# unchanged" says nothing about 2020 by itself; "Direct 1:1 match from KBLI 2020
# — code and scope unchanged" does.
_CONTINUITY_STRONG = re.compile(
    r"unchanged from KBLI 2020" r"|same code, same scope" r"|the code and scope remain unchanged",
    re.IGNORECASE,
)
_CONTINUITY_WEAK = re.compile(
    r"(?:the )?code and scope (?:are )?unchanged" r"|keeps? the same code and scope",
    re.IGNORECASE,
)
_CONTINUITY_AMBIGUOUS = re.compile(r"direct (?:1:1 )?match from KBLI 2020", re.IGNORECASE)
# Kept as the removal pattern: once guilt is established, every span that carries
# either half of the claim goes, so no residue contradicts the replacement.
_CONTINUITY = re.compile(
    f"{_CONTINUITY_STRONG.pattern}|{_CONTINUITY_WEAK.pattern}", re.IGNORECASE
)

# A QUOTATION OF THE CLAIM IS NOT AN ASSERTION OF IT (2026-08-05).
#
# `52101` had already been corrected by hand, and its correction QUOTES what it
# corrects: "…code number reused (corrected 2026-07-19 — the previous 'Direct
# 1:1 match... code and scope unchanged' label was a false narrative)". The
# widened pattern above matched INSIDE that quotation and the wide removal cut
# the sentence in half, splicing the honest sentence into the middle of a
# dangling quote. The output was not merely a false positive, it was gibberish —
# and it would have replaced a record that documents a real, image-verified
# five-parent merge with "the mapping is unconfirmed", which for THIS record is
# false. Same shape as W113: a probe judging by FORM catches the citation living
# inside the retraction.
#
# Deliberately narrow, so that fixing this over-match does not birth the
# under-match twin (W94): only BALANCED pairs mask, an unbalanced quote masks
# NOTHING (W84 — a greedy quote scan that swallows the rest of the text is how
# this repo has been bitten before), and a straight `'` counts as a delimiter
# only when it is not an intra-word apostrophe, so "don't" and "it's" cannot
# fabricate a region that hides a real claim.
_QUOTE_PAIRS = (("‘", "’"), ("“", "”"), ('"', '"'), ("'", "'"))


def _quoted_regions(text: str) -> list[tuple[int, int]]:
    """Half-open spans covered by a BALANCED quotation. Never a bare-open run."""
    regions: list[tuple[int, int]] = []
    for opener, closer in _QUOTE_PAIRS:
        # A SYMMETRIC delimiter with an ODD count is unbalanced as a WHOLE, and
        # the rule above says an unbalanced quote masks nothing. Without this the
        # code broke its own promise on the first text the cross-family reviewer
        # tried: `"The code and scope remain unchanged. The source calls it
        # "legacy".` has three `"`, the scan paired the first two, and a real
        # assertion went unconvicted inside a region the text never balanced.
        # Asymmetric pairs (‘…’, “…”) are exempt — their counts are independent.
        if opener == closer and text.count(opener) % 2:
            continue
        idx = 0
        while True:
            start = text.find(opener, idx)
            if start < 0:
                break
            if opener == closer == "'" and not _is_quote_delimiter(text, start, opening=True):
                idx = start + 1
                continue
            search_from = start + 1
            while True:
                end = text.find(closer, search_from)
                if end < 0:
                    break
                if opener == closer == "'" and not _is_quote_delimiter(text, end, opening=False):
                    search_from = end + 1
                    continue
                break
            if end < 0:  # unbalanced: masks nothing
                break
            regions.append((start, end + 1))
            idx = end + 1
    return regions


def _is_quote_delimiter(text: str, pos: int, *, opening: bool) -> bool:
    """A straight `'` is a quote mark only when it is not inside a word."""
    before = text[pos - 1] if pos > 0 else " "
    after = text[pos + 1] if pos + 1 < len(text) else " "
    if opening:
        return not before.isalnum() and not after.isspace()
    return not before.isspace() and not after.isalnum()


def _outside_quotes(pattern: re.Pattern[str], text: str) -> bool:
    """True when `pattern` hits at least once OUTSIDE every balanced quotation."""
    regions = _quoted_regions(text)
    return any(
        not any(start <= m.start() and m.end() <= end for start, end in regions)
        for m in pattern.finditer(text)
    )


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


def claims_number_unchanged(text: str) -> bool:
    """The prose ASSERTS THIS code's NUMBER is what it was in KBLI 2020.

    Asserts, not merely contains: a match that lives entirely inside a balanced
    quotation is a REPRODUCTION of the claim — typically by prose that exists to
    correct it — and convicting on it re-corrects a correction (see the note on
    `_QUOTE_PAIRS`).
    """
    if _outside_quotes(_CONTINUITY_STRONG, text):
        return True
    return _outside_quotes(_CONTINUITY_WEAK, text) and _outside_quotes(_CONTINUITY_AMBIGUOUS, text)


def claims_ambiguous_continuity(text: str) -> bool:
    """Census-only. "Direct match from KBLI 2020" can mean the same NUMBER or a
    clean 1:1 ACTIVITY mapping onto a different one, and nothing in the sentence
    settles it. Reported, never cured — see the note on `_CONTINUITY`."""
    return bool(_CONTINUITY_AMBIGUOUS.search(text))


def number_is_discontinuous(record: dict[str, Any]) -> bool:
    """The record's OWN code is in none of the crosswalk layers that name a 2020 origin.

    Two refusals, each one a case where "the number changed" is not something we
    know: NOTHING readable on file (which covers both "no rows at all" — pass A
    owns that sentence — and "rows on file that no layer could parse", the
    UNDECIDABLE case pass C also refuses; `recorded_predecessors` is by
    construction a subset of the readable rows, so one test answers both); and a
    record with no code of its own to compare against.

    An explicit `has_unreadable_layer_rows` branch stood here first and no
    mutation could kill it — it is wholly contained in the emptiness test below.
    A guard that cannot fire is an antibody in name only, so it is gone; the test
    that pins the UNDECIDABLE behaviour stays, because it asserts the outcome and
    does not care which line delivers it.

    ONE decision function, shared by the cure and by the census that reports what
    the cure deliberately leaves alone — so the two can never disagree about the
    same fact (W105).
    """
    recorded = recorded_predecessors(record)
    if not recorded:
        return False
    code = str(record.get("kode_kbli_2025") or "")
    if not code:
        return False
    return code not in recorded


def contradicted_continuity(text: str, record: dict[str, Any]) -> bool:
    """The prose claims the number carried over; the crosswalk names other codes."""
    return claims_number_unchanged(text) and number_is_discontinuous(record)


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
    return _replace_spans(text, spans, replacement)


def _replace_spans(text: str, spans: list[tuple[int, int]], replacement: str) -> str:
    """Write ONE honest sentence where the first offending span was; delete the rest.

    Shared by passes C and D so the two cures cannot drift apart in how they
    edit — the only thing that differs between them is WHICH spans are guilty
    and WHAT the honest sentence says.
    """
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


def unconfirmed_continuity_sentence(code: str) -> str:
    """The replacement for a false continuity claim. It NAMES NO 2020 CODE, on purpose.

    A first draft enumerated the record's recorded predecessors ("the crosswalk
    sources on file record 91012 as the 2020 origin of 91212"). Checked against
    the BPS edge files — an independent source, not the record's own field — that
    enumeration was WRONG on 4 of the 14 codes this pass cures: BPS puts 91212's
    origin at 91022, 91222's at 91024/91029, 91424's at 91034, 91425's at 91033,
    while the records' `pp28_sources` say 91012 / 91022 / 91024 / 91025. Those
    four records carry no `bps_2020_ancestors` at all, so the weaker layer was
    the only one this function could see — and it would have published that
    layer's answer AS the answer on four client-facing pages.

    What survives independent checking is the NEGATIVE: none of the 14 exists on
    the 2020 side of the crosswalk at all. So that is all this sentence asserts.
    Replacing a false claim with a shakier one is how a correction becomes the
    next defect; when the support is not verifiable, drop it rather than soften
    it. (The 4 layer disagreements are a finding of their own, ledgered — this
    cure neither hides nor adjudicates them.)
    """
    # NOTE the wording "carrying over FROM KBLI 2020", not "…unchanged from KBLI
    # 2020": the first draft said "unchanged" and thereby contained `_CONTINUITY`
    # verbatim, so the cure re-convicted its own output and the live organs stayed
    # red after a successful apply. A guard whose replacement text matches its own
    # trigger is the over-match family biting the remedy (superscar #3).
    return (
        f"Our records do not support this code number carrying over from "
        f"KBLI 2020: no crosswalk source we hold records {code} as its own KBLI-2020 "
        f"predecessor, so a 2020 registration under this number should not be assumed "
        f"to carry over. The 2020-to-2025 mapping for this code is unconfirmed pending "
        f"re-verification (GARUDA-FILIERA)."
    )


def drop_false_continuity(text: str, record: dict[str, Any]) -> str:
    """Replace the sentence claiming the number is unchanged. Never renumber it."""
    if not contradicted_continuity(text, record):
        raise WhatChangedError("no contradicted continuity claim in this text — nothing to drop")

    # Guilt is decided by the NARROW pattern; once decided, the removal takes the
    # ambiguous wording in the same text too. "Direct match from KBLI 2020" is
    # ambiguous only in isolation — in a passage that also says "same code, same
    # scope" the whole passage is asserting number continuity. Leaving it behind
    # would publish "Direct match from KBLI 2020. Our records do not support this
    # code number carrying over…" in one breath (measured on 96210), and a verdict
    # that keeps the rationale it just overturned invites its own reversal.
    # …and the removal honours the same quotation rule as the conviction, on
    # ABSOLUTE offsets: a quotation may straddle a sentence boundary, so the
    # regions are computed once over the whole text rather than per slice.
    _quoted = _quoted_regions(text)

    def _asserts_here(start: int, end: int) -> bool:
        # `finditer(text, start, end)` is NOT slice-equivalent in general: `^`
        # still means the start of the whole string, and a lookbehind can read
        # text before `start`. It is used here because both patterns are plain
        # alternations with no anchors and no lookarounds, where the two agree —
        # and because it keeps absolute offsets for the quotation test. Add an
        # anchor or a lookbehind to either pattern and this line changes meaning
        # silently. (Raised by the cross-family review; safe today, pinned so it
        # stays that way.)
        for pattern in (_CONTINUITY, _CONTINUITY_AMBIGUOUS):
            assert "^" not in pattern.pattern and "(?<" not in pattern.pattern, (
                "an anchor or lookbehind reached a pattern scanned with pos/endpos — "
                "this is no longer equivalent to searching the sentence slice"
            )
            for m in pattern.finditer(text, start, end):
                if not any(qs <= m.start() and m.end() <= qe for qs, qe in _quoted):
                    return True
        return False

    spans = [
        (start, end)
        for start, end in _sentence_spans(text)
        if _asserts_here(start, end)
    ]
    if not spans:  # pragma: no cover - a match outside every span is structurally impossible
        raise WhatChangedError("continuity claim matched no sentence span")

    replacement = unconfirmed_continuity_sentence(str(record.get("kode_kbli_2025")))
    return _replace_spans(text, spans, replacement)


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
    # Pass D is the ONE pass re-detected on the partly-cured text, on purpose: a
    # single sentence can carry both an unsupported predecessor number and the
    # continuity phrase, and pass C will already have taken it. Detecting on the
    # original and applying here would raise on a text that is now correct.
    if contradicted_continuity(cured, record):
        cured = drop_false_continuity(cured, record)
        applied.append(PASS_FALSE_CONTINUITY)
    if do_trim:
        trimmed = trim_to_last_complete_sentence(cured)
        if trimmed is None:  # pragma: no cover - guarded by do_trim
            raise WhatChangedError("no complete sentence survived the earlier passes")
        cured = trimmed
        applied.append(PASS_TRUNCATED)

    if applied and cured == text:  # pragma: no cover - a pass that changes nothing is a bug
        raise WhatChangedError(f"passes {applied} claimed to fire but produced identical text")
    return cured, applied
