#!/usr/bin/env python3
"""Measure the SUPERSEDED Second Home threshold, and the claims that replace it.

The E33 eligibility threshold is USD 130,000 held in the applicant's own name at a
state-owned (BUMN) Indonesian bank, or USD 1,000,000 of qualifying completed
strata-title property (`e33_base_deposit_amount` / `e33_base_property_alternative`,
both `confirmed` in research/secondhome/e33-fact-registry.json).

"IDR 2 billion" is the SUPERSEDED figure. This probe rewrites nothing. It reports
the CO-OCCURRENCE set — a line naming the product AND the superseded amount —
because an IDR 2 billion figure belonging to another product is not a defect and
must never be swept.

A zero here is NOT a correctness proof, and the W3 PRE-review said so in writing: a
line reading "E33 requires IDR 2B", or a product name and its amount split across two
lines, once escaped this check. `--claims` exists for that reason — it asserts what
each locale must SAY, not only what it must not say, and it fails on the contradictions
the amount check cannot see (a named qualifying title, a decomposed fee table, a
province-varying property threshold).

Usage:
  probe-superseded-threshold.py <file> [<file> ...]  # co-occurrence, e.g. a built llms-full.txt
  probe-superseded-threshold.py --sources            # every amount hit in the 5 canonical sources
  probe-superseded-threshold.py --claims             # positive + contradiction checks per locale
  probe-superseded-threshold.py --attribute <file>   # each hit + the nearest product mention above it
  probe-superseded-threshold.py --selftest           # the probe's own guilt/innocence cases
"""
import re
import sys

# `2(?![\d.,]*\d)` keeps IDR 20B, IDR 2.5B and IDR 2,000,000 (not billions) OUT: the
# amount has to be TWO billion, not merely start with a 2.
_TWO = r"2(?![\d.,]*\d)"
_UNIT = r"B\b|Miliar|miliar|milyar|billion|milliards?|miliardi|млрд|миллиард\w*"
THRESHOLD = re.compile(
    # IDR 2B · Rp 2 miliar · IDR 2 milliards
    rf"(?:IDR|Rp)\s*{_TWO}\s*(?:{_UNIT})"
    # 2 miliardi di IDR · 2 milliards de roupies · 2 млрд IDR · 2 billion rupiah
    rf"|\b{_TWO}\s*(?:{_UNIT})\s*(?:(?:di|de|of|d'|в)\s+)?(?:rupiah|roupies|IDR|Rp|рупий)?"
    # grouped digits, with dots, commas OR the spaces French uses: IDR 2 000 000 000
    r"|(?:IDR|Rp)\s*2[.,\s]0{3}[.,\s]0{3}[.,\s]0{3}"
    # ranges that present 2 billion as the floor: IDR 2B-5B · 2 à 5 milliards IDR
    rf"|\b{_TWO}\s*(?:{_UNIT})?\s*(?:[-–—]|à|to|sampai|a|до)\s*\d+\s*(?:{_UNIT})"
    # spelled out
    r"|\b(?:two|due|deux|два|dua)\s+(?:billion|miliardi|milliards?|миллиарда|miliar)"
    # the Rp2M shorthand — flagged for classification, never auto-converted
    rf"|\bRp\s*{_TWO}\s*M\b",
    re.IGNORECASE,
)
# E33E/E33F/E33G are DIFFERENT products with different thresholds: `\bE33\b` matches
# the base code only, never the senior or remote-worker routes.
PRODUCT = re.compile(r"second\s*home|rumah\s*kedua|\bSHV\b|\bE33\b", re.IGNORECASE)

LOCALES = ("", ".it", ".id", ".ru", ".fr")
FAMILY = [
    f"apps/mouth/src/content/articles/immigration/second-home-visa-indonesia{s}.mdx"
    for s in LOCALES
]

# What each locale must SAY (the cure), and must NOT say (the contradiction).
# Deliberately short: each entry is a claim the fact registry settles.
REQUIRED = {
    "": ["USD 130,000", "own name", "state-owned (BUMN)", "USD 1,000,000", "completed apartment or strata unit", "Pasal 113"],
    ".it": ["USD 130.000", "a nome del richiedente", "banca statale (BUMN)", "USD 1.000.000", "unità strata già ultimata", "Pasal 113"],
    ".id": ["USD 130.000", "atas nama pemohon sendiri", "bank milik negara (BUMN)", "USD 1.000.000", "unit strata yang sudah selesai dibangun", "Pasal 113"],
    ".ru": ["USD 130 000", "на собственное имя", "(BUMN)", "USD 1 000 000", "strata-юнита", "Pasal 113"],
    ".fr": ["130 000 USD", "au nom propre du demandeur", "banque publique (BUMN)", "1 000 000 USD", "lot en copropriété (rumah susun) déjà achevé", "Pasal 113"],
}
# Contradictions the amount check is blind to. `Hak Pakai` and `PT PMA` are barred as
# ELIGIBLE-TITLE claims: `e33_base_property_title_type` is an `unknown` fact, so naming
# any qualifying title resolves it by assertion. The fee patterns catch the decomposed
# cost table the 2026-07-23 owner ruling forbids.
FORBIDDEN = [
    (r"Hak Pakai", "names a qualifying property title; e33_base_property_title_type is `unknown`"),
    (r"Sertifikat Hak Milik Satuan Rumah Susun", "same — names a certificate as the qualifying title"),
    (r"PT PMA .{0,40}(shareholder|azionista|pemegang saham|actionnaire|акционер)", "PT PMA majority holding as an E33 property route: no registry fact"),
    (r"(3[.,]000[.,]000|3 000 000)\s*-\s*(5[.,]000[.,]000|5 000 000)", "an invented government/renewal fee range"),
    (r"(varies by province|varia da provincia|berbeda-beda per provinsi|varie selon la province|различаются по провинциям)", "a province-varying property threshold; the requirement is USD 1,000,000"),
    (r"(Costs Breakdown|Dettaglio dei Costi|Rincian Biaya|Распределение затрат|Répartition des coûts)", "the decomposed cost table"),
]


def scan(path, require_product=True):
    """Offending (line_number, text) pairs in `path`."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    return [
        (n, line)
        for n, line in enumerate(lines, 1)
        if THRESHOLD.search(line) and (PRODUCT.search(line) or not require_product)
    ]


def run_cooccurrence(paths, require_product):
    total = 0
    for path in paths:
        hits = scan(path, require_product)
        total += len(hits)
        print(f"{len(hits):4d}  {path}")
        for n, line in hits:
            print(f"        {n}: {line.strip()[:140]}")
    kind = "second-home lines" if require_product else "amount occurrences"
    print(f"TOTAL {kind} carrying the superseded threshold: {total}")
    return 1 if total else 0


def run_attribution(paths, window=40):
    """Attribute every amount hit to the nearest product mention ABOVE it.

    The line-scoped co-occurrence check has a measured blind spot: in a comparison
    table the product is the COLUMN HEADER and the amount is a body row, and in a
    document checklist the product is a section heading. Three families were
    classified "not an E33 claim" by the line check and turned out to be E33 claims
    exactly that way (e311a-retirement-visa-kitas-guide, indonesia-visa-timeline-comparison,
    kitas-for-digital-nomads-reality, measured 2026-09-12). This mode prints the
    evidence a human classifies from; it never classifies by itself.
    """
    for path in paths:
        lines = open(path, encoding="utf-8").read().split("\n")
        hits = [(n, l) for n, l in enumerate(lines, 1) if THRESHOLD.search(l)]
        if not hits:
            continue
        print(f"=== {path}")
        for n, line in hits:
            context = None
            for back in range(n - 1, max(0, n - 1 - window), -1):
                if PRODUCT.search(lines[back - 1]):
                    context = (back, lines[back - 1].strip()[:110])
                    break
            print(f"  {n}: {line.strip()[:120]}")
            print(f"      nearest product mention: {context if context else 'NONE within %d lines' % window}")
    return 0


def run_claims():
    """Every locale must carry the cure and none of the contradictions."""
    failures = 0
    for suffix, path in zip(LOCALES, FAMILY):
        text = open(path, encoding="utf-8").read()
        for needle in REQUIRED[suffix]:
            if needle not in text:
                print(f"MISSING  {path}: {needle!r}")
                failures += 1
        for pattern, why in FORBIDDEN:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                print(f"PRESENT  {path}: {match.group(0)!r} — {why}")
                failures += 1
        print(f"{'ok  ' if not failures else '    '}  {path}")
    print(f"TOTAL claim failures: {failures}")
    return 1 if failures else 0


def run_selftest():
    """The probe's own guilt and innocence cases. Innocence matters as much here:
    a probe that flags another product's figure is what produces a blind sweep."""
    guilt = [
        "IDR 2B", "IDR 2 billion", "Rp 2 miliar", "IDR 2Miliar", "2 млрд IDR",
        "2 milliards IDR", "2 miliardi di IDR", "IDR 2.000.000.000",
        "IDR 2 000 000 000", "2 à 5 milliards IDR", "IDR 2B-5B", "two billion rupiah",
        "due miliardi", "deux milliards", "два миллиарда", "Rp2M",
    ]
    innocence = [
        "IDR 20B", "IDR 2.5 billion", "USD 350K+ investment", "Above IDR 5B",
        "IDR 500M - IDR 5B", "IDR 2,000,000 fine",
    ]
    product_yes = ["Second Home Visa", "Visa Rumah Kedua", "the SHV", "E33 requires it"]
    product_no = ["E33E senior route", "E33G remote worker", "KITAP holders"]
    bad = 0
    for s in guilt:
        if not THRESHOLD.search(s):
            print(f"GUILT MISSED: {s!r}"); bad += 1
    for s in innocence:
        if THRESHOLD.search(s):
            print(f"INNOCENCE FLAGGED: {s!r}"); bad += 1
    for s in product_yes:
        if not PRODUCT.search(s):
            print(f"PRODUCT MISSED: {s!r}"); bad += 1
    for s in product_no:
        if PRODUCT.search(s):
            print(f"PRODUCT OVER-MATCHED: {s!r}"); bad += 1
    print(f"selftest failures: {bad}")
    return 1 if bad else 0


def main(argv):
    if argv == ["--selftest"]:
        return run_selftest()
    if argv[:1] == ["--attribute"]:
        return run_attribution(argv[1:] or FAMILY)
    if argv == ["--claims"]:
        return run_claims()
    if argv == ["--sources"]:
        # Inside this family every amount is about this product, and the listing below
        # is printed so that premise is auditable rather than assumed.
        return run_cooccurrence(FAMILY, require_product=False)
    if not argv:
        print(__doc__)
        return 2
    return run_cooccurrence(argv, require_product=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
