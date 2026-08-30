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


def test_a_cap_too_small_for_even_the_header_still_says_so() -> None:
    """Degenerate input must not produce a silently empty map, which reads
    exactly like a clean small repo."""
    out, verdict = cap.cap_text(_map(200), 120)
    assert "TRUNCATED" in out, "an unusable cap must still be explained, not obeyed silently"
    assert verdict == "truncated 0/200"


def test_the_cap_is_measured_in_bytes_not_characters() -> None:
    """Non-ASCII symbol names are ordinary here (the scar corpus is bilingual);
    a character-counted cap would overshoot on them."""
    body = "".join(f"\n{i:04d}_fïlé.py:\n  function: {'è' * 200}\n" for i in range(200))
    out, _ = cap.cap_text(HEADER + body, 20_480)
    assert len(out.encode()) <= 20_480, "counted characters, not bytes"
