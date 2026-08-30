#!/usr/bin/env python3
"""repomap_cap.py — truncate a generated repo map to a hard byte cap, by rank.

WHY A HARD CAP AND NOT A WARNING
--------------------------------
`scripts/build_repomap.sh` used to emit a stderr WARN above 30 KB and let the
file through. It fired, and nobody read it: measured on Pro on 2026-08-31 the
live `~/.nuzantara-repomap.txt` was 42,779 bytes — past its own warn band, and
injected into every session on that machine. A warning nobody reads is not a
control (superscar #2; W55 — a signal emitted is not a signal seen). W76 is this
same file's earlier relapse, where a silent strategy fallback filled the map with
minified webpack chunks. So the generator truncates now, and says that it did.

TRUNCATION KEEPS A PREFIX OF THE STRATEGY'S OWN ORDER
-----------------------------------------------------
The ctags path sorts its files by symbol count, so its prefix genuinely is the
densest part. Aider does NOT: it selects tags by PageRank and then renders them
sorted BY FILENAME, so its prefix is alphabetical, not best-first. An earlier
draft of this docstring claimed both were best-first (Codex sol, 2026-08-31); a
false claim about ranking is worse than no claim, because the next reader budgets
trust on it.

Keeping a prefix is still the right cut: it preserves whatever order the strategy
chose rather than substituting one this script invented, it is stable between
runs (so a diff of two maps is readable), and a block is never cut in half — a
half-written symbol list is worse than an absent one, because a reader cannot
tell it from a genuinely short one. What it is NOT is a guarantee that the most
important files survive under aider; the note says how many blocks were dropped,
so a reader can see when that matters.

The truncation always announces itself in the output. A map that quietly stops
early is indistinguishable from a small repository — which is the confusion this
whole lane exists to remove.
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_CAP_BYTES = 20_480


# A block header is a file path followed by a colon, at column 0. The two
# strategies write their CONTINUATION lines differently and the difference is
# load-bearing: ctags indents them, but aider draws a gutter — `⋮...` for elided
# regions and `│def foo():` for kept ones — at column 0 too. Detecting a header
# as "not indented" therefore split real aider output into ten blocks where it
# had two (measured), which would cut a file's summary in half: the exact thing
# this module promises never to do. So a header is recognised by SHAPE — no
# gutter glyph, ends in a colon — not by the absence of leading whitespace.
_GUTTER_CHARS = "│⋮|"


def _is_block_header(line: str) -> bool:
    if not line.strip() or line[0].isspace() or line[0] in _GUTTER_CHARS:
        return False
    return line.rstrip().endswith(":")


def _split(text: str) -> tuple[list[str], list[list[str]]]:
    """(preamble, blocks). A block runs from one file header to the next."""
    lines = text.splitlines(keepends=True)

    # The generator's `#` header and any strategy preamble ride along
    # unconditionally: they carry the provenance a reader needs to judge
    # everything below, and dropping them to save bytes trades the label for
    # the contents.
    head: list[str] = []
    i = 0
    while i < len(lines) and (lines[i].startswith("#") or not lines[i].strip()):
        head.append(lines[i])
        i += 1
    while i < len(lines) and lines[i].startswith("Here are summaries"):
        head.append(lines[i])
        i += 1
    # ...and the blank line aider leaves after its preamble. Without this the
    # blank became a block of its own, ahead of the first real file — harmless
    # to the byte count, but it made the "kept N of M blocks" note off by one,
    # and a note that miscounts is a note a reader stops trusting.
    while i < len(lines) and not lines[i].strip():
        head.append(lines[i])
        i += 1

    blocks: list[list[str]] = []
    cur: list[str] = []
    for line in lines[i:]:
        if _is_block_header(line):
            if cur:
                blocks.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        blocks.append(cur)
    return head, blocks


def _note(kept: int, total: int, cap: int, why: str) -> str:
    return (
        f"#\n# TRUNCATED: kept {kept} of {total} file blocks to stay inside the "
        f"{cap}-byte hard cap ({why}).\n"
        "# What is kept is a PREFIX of the order the generating strategy emitted —\n"
        "# which is by symbol count under ctags, but alphabetical under aider, so do\n"
        "# not read the surviving files as the most important ones. This is a map,\n"
        "# not the territory: grep the repo for what is not here.\n"
    )


def cap_text(text: str, cap: int = DEFAULT_CAP_BYTES) -> tuple[str, str]:
    """Return (capped_text, verdict). Verdict is one word, for the caller's log."""
    if len(text.encode()) <= cap:
        return text, "within-cap"

    head, blocks = _split(text)
    head_str = "".join(head)
    # Reserve the LONGEST note we could emit, not the shortest. The reservation
    # used `kept=0` while the output carries the real count, so a run keeping 288
    # of 400 blocks writes two digits more than it budgeted — an overflow of the
    # very cap this module exists to hold, invisible except at the boundary
    # (Codex sol, 2026-08-31). `len(blocks)` is the widest `kept` can ever be.
    worst_note = len(_note(len(blocks), len(blocks), cap, "by rank").encode())
    budget = cap - len(head_str.encode()) - worst_note

    if budget <= 0:
        # A FLOOR, and it is deliberately above the cap. Below "provenance header
        # plus an explanation" there is nothing worth writing: an empty file reads
        # exactly like a clean small repo, and a byte-sliced note is unreadable.
        # So a cap this small is refused rather than obeyed, and the verdict says
        # so — the caller's own over-cap WARN then fires, which is correct: a cap
        # that cannot hold its own floor is a misconfiguration, not a map problem.
        # Named here because the module calls itself a HARD cap everywhere else,
        # and a promise with a silent exception is the defect this lane is about.
        return (
            head_str + _note(0, len(blocks), cap, "cap is below the header+note floor"),
            f"floor-exceeds-cap 0/{len(blocks)}",
        )

    # `continue`, not `break`. One pathological block — a generated file with
    # thousands of symbols — used to end the walk, so a map whose FIRST block was
    # oversized came back with nothing but a note while every later block would
    # have fitted (measured: `truncated 0/2`, both files gone). Skipping it keeps
    # the rest of the order, which is strictly more of what the strategy chose
    # than zero of it.
    kept: list[list[str]] = []
    used = 0
    for b in blocks:
        n = len("".join(b).encode())
        if used + n > budget:
            continue
        kept.append(b)
        used += n

    out = head_str + "".join("".join(b) for b in kept) + _note(len(kept), len(blocks), cap, "by rank")
    return out, f"truncated {len(kept)}/{len(blocks)}"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: repomap_cap.py <src> <dst> <cap-bytes>", file=sys.stderr)
        return 2
    src, dst, cap = Path(argv[0]), Path(argv[1]), int(argv[2])
    out, verdict = cap_text(src.read_text(encoding="utf-8", errors="replace"), cap)
    dst.write_text(out, encoding="utf-8")
    print(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
