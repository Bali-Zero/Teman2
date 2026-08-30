"""Guilt + innocence for the repo map's hard byte cap.

The behaviour this replaces was a stderr WARN above 30 KB that let the file
through — and the file went through: 42,779 bytes live on Pro, injected into
every session there. So the assertions below care about two things a warning
never gave: that an over-cap map is actually SHORTENED, and that it SAYS it was.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "repomap_cap", Path(__file__).resolve().parents[1] / "repomap_cap.py"
)
assert _SPEC and _SPEC.loader
cap = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cap)

HEADER = "# Nuzantara repo map (auto-generated)\n# Generated: 2026-08-31\n# Strategy: ctags\n#\n"


def _map(n_blocks: int, syms_per_block: int = 40) -> str:
    """A map shaped like the real generators': `path:` headers, indented bodies,
    emitted best-first. Block index doubles as its rank."""
    body = "".join(
        f"\n{i:04d}_file.py:\n  function: {', '.join('sym%03d' % j for j in range(syms_per_block))}\n"
        for i in range(n_blocks)
    )
    return HEADER + body


def _kept_ranks(text: str) -> list[int]:
    return [int(m) for m in re.findall(r"^(\d{4})_file\.py:", text, re.M)]


def test_innocence_a_map_already_under_the_cap_is_returned_byte_identical() -> None:
    small = _map(3)
    assert len(small.encode()) < 20_480
    out, verdict = cap.cap_text(small, 20_480)
    assert out == small, "an under-cap map must not be rewritten at all"
    assert verdict == "within-cap"
    assert "TRUNCATED" not in out


def test_guilt_an_over_cap_map_is_truncated_not_warned_about() -> None:
    big = _map(200)
    assert len(big.encode()) > 20_480, "premise: the input must actually exceed the cap"
    out, verdict = cap.cap_text(big, 20_480)
    assert len(out.encode()) <= 20_480, f"still {len(out.encode())} B — the cap did not hold"
    assert verdict.startswith("truncated")


def test_what_survives_is_the_rank_prefix_never_an_arbitrary_subset() -> None:
    """The strategies emit best-first; keeping a prefix keeps THEIR ranking.
    A subset that skipped around would be this script inventing a ranking."""
    out, _ = cap.cap_text(_map(200), 20_480)
    kept = _kept_ranks(out)
    assert kept, "something must survive"
    assert kept == list(range(len(kept))), f"not a prefix: {kept[:5]}...{kept[-3:]}"


def test_no_block_is_cut_in_half() -> None:
    """A half-written symbol list is worse than an absent one — a reader cannot
    tell it from a genuinely short one."""
    out, _ = cap.cap_text(_map(200), 20_480)
    intact = _map(200)
    for rank in _kept_ranks(out):
        block = f"\n{rank:04d}_file.py:\n  function: {', '.join('sym%03d' % j for j in range(40))}\n"
        assert block in intact and block in out, f"block {rank} was cut"


def test_the_truncation_announces_itself() -> None:
    """The load-bearing one. A map that quietly stops early is indistinguishable
    from a small repository, and that confusion is the whole disease here."""
    out, _ = cap.cap_text(_map(200), 20_480)
    assert "TRUNCATED" in out
    assert re.search(r"kept \d+ of 200 file blocks", out), "the note must give both counts"
    assert "grep the repo" in out, "the note must tell the reader where the rest is"


def test_the_provenance_header_always_survives() -> None:
    """Dropping the header to save bytes would trade the label for the contents."""
    out, _ = cap.cap_text(_map(200), 20_480)
    assert out.startswith(HEADER)


def test_a_cap_below_the_header_floor_is_refused_and_named_as_such() -> None:
    """The one place the output is deliberately LARGER than the cap.

    Below "provenance header plus an explanation" there is nothing worth
    writing: an empty file reads exactly like a clean small repo, and a
    byte-sliced note is unreadable. So such a cap is refused rather than obeyed,
    and the verdict SAYS which of the two happened — a module that calls itself a
    hard cap everywhere else must not carry a silent exception (Kimi K3, 2026-08-31:
    the earlier version returned the same `truncated` verdict here, so a caller
    could not tell an honoured cap from an impossible one)."""
    out, verdict = cap.cap_text(_map(200), 120)
    assert "TRUNCATED" in out, "an unusable cap must still be explained, not obeyed silently"
    assert verdict == "floor-exceeds-cap 0/200", (
        "the verdict must distinguish 'I truncated to fit' from 'this cap cannot fit "
        "its own explanation' — the caller's over-cap WARN depends on the difference"
    )
    assert len(out.encode()) > 120, "premise: this is the case where the floor wins"


def test_the_aider_gutter_is_not_mistaken_for_block_headers() -> None:
    """Aider draws `⋮...` and `│def foo():` at column 0, so "not indented" is not
    a block header. Measured 2026-08-31: the first version split a two-file aider
    map into TEN blocks, which would cut a file's summary in half — the one thing
    this module promises never to do."""
    aider = (
        "# Nuzantara repo map (auto-generated)\n#\n"
        "Here are summaries of some files present in my git repository.\n\n"
        "a.py:\n⋮...\n│def a():\n│    pass\n⋮...\n"
        "b.py:\n⋮...\n│def b():\n│    pass\n"
    )
    _head, blocks = cap._split(aider)
    assert len(blocks) == 2, f"expected the two files, got {len(blocks)} blocks"
    assert [b[0].strip() for b in blocks] == ["a.py:", "b.py:"]


def test_a_stray_prose_line_at_column_zero_does_not_start_a_block() -> None:
    """The other half of the header shape, and it needed its own case.

    A mutation replacing `endswith(":")` with `True` survived every other test
    here, because in all of them every non-gutter column-0 line happened to end
    in a colon — the predicate read as protection while nothing could tell it
    from a constant. Aider's preamble stripper keeps from "Here are summaries",
    so any prose after that point rides along at column 0; treated as a header it
    would invent a block and make the "kept N of M" note wrong."""
    text = (
        "# h\n#\n\n"
        "a.py:\n  function: x\n"
        "Repo-map can't include /some/path, it is not in the repo.\n"
        "b.py:\n  function: y\n"
    )
    _head, blocks = cap._split(text)
    assert [b[0].strip() for b in blocks] == ["a.py:", "b.py:"], (
        f"prose was treated as a file header: {[b[0].strip() for b in blocks]}"
    )


def test_both_strategy_formats_split_the_same_way() -> None:
    """ctags indents its continuations, aider gutters them. One detector, two
    formats — if a future strategy breaks this, the cap starts cutting blocks."""
    ctags = "# h\n#\n\nx.py:\n  function: a, b\n\ny.py:\n  class: C\n"
    _h, blocks = cap._split(ctags)
    assert [b[0].strip() for b in blocks] == ["x.py:", "y.py:"]


def test_the_cap_is_measured_in_bytes_not_characters() -> None:
    """Non-ASCII symbol names are ordinary here (the scar corpus is bilingual);
    a character-counted cap would overshoot on them."""
    body = "".join(f"\n{i:04d}_fïlé.py:\n  function: {'è' * 200}\n" for i in range(200))
    out, _ = cap.cap_text(HEADER + body, 20_480)
    assert len(out.encode()) <= 20_480, "counted characters, not bytes"
