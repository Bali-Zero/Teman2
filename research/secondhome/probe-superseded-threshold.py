#!/usr/bin/env python3
"""Count claims that still present the SUPERSEDED Second Home threshold.

The E33 eligibility threshold is USD 130,000 held in the applicant's own name at a
state-owned (BUMN) Indonesian bank, or USD 1,000,000 of qualifying completed
strata-title property (research/secondhome/e33-fact-registry.json,
`e33_base_deposit_amount` / `e33_base_property_alternative`, both `confirmed`).

"IDR 2 billion" is the SUPERSEDED figure. This probe never rewrites anything: it
reports the CO-OCCURRENCE set — a line that names Second Home AND the superseded
threshold — because an IDR 2 billion figure that belongs to another product
(paid-up capital, a property price) is not a defect and must not be swept.

Usage:
  probe-superseded-threshold.py <file> [<file> ...]   # e.g. a generated llms-full.txt
  probe-superseded-threshold.py --sources            # the 5 canonical family MDX sources
"""
import re
import sys

THRESHOLD = re.compile(
    r"(IDR|Rp)\s*2[.,]?0*\s*(B\b|Miliar|miliar|milyar|billion|milliards?|miliardi|млрд|миллиард\w*)"
    r"|IDR\s*2[.,]000[.,]000[.,]000"
    r"|Rp\s*2[.,]000[.,]000[.,]000"
    r"|2\s*(miliar|milyar|milliards?|miliardi|млрд|миллиард\w*|billion)\s*(rupiah|IDR|Rp|di IDR)?",
    re.IGNORECASE,
)
SECOND_HOME = re.compile(r"second\s*home|rumah\s*kedua|\bSHV\b", re.IGNORECASE)

FAMILY = [
    f"apps/mouth/src/content/articles/immigration/second-home-visa-indonesia{s}.mdx"
    for s in ("", ".it", ".id", ".ru", ".fr")
]


def scan(path, require_second_home):
    """Return (line_number, text) for every offending line in `path`."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    return [
        (n, line)
        for n, line in enumerate(lines, 1)
        if THRESHOLD.search(line) and (SECOND_HOME.search(line) or not require_second_home)
    ]


def main(argv):
    sources = argv == ["--sources"]
    paths = FAMILY if sources else argv
    if not paths:
        print(__doc__)
        return 2
    total = 0
    for path in paths:
        # Inside the canonical family EVERY threshold mention is about Second Home,
        # so the co-occurrence requirement is dropped there and the file is judged whole.
        hits = scan(path, require_second_home=not sources)
        total += len(hits)
        print(f"{len(hits):4d}  {path}")
        for n, line in hits:
            print(f"        {n}: {line.strip()[:140]}")
    label = "occurrences" if sources else "second-home lines"
    print(f"TOTAL {label} carrying the superseded threshold: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
