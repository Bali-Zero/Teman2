#!/usr/bin/env python3
"""parse_perpres_lampiran2.py — compile the Koperasi/UMKM reservation table.

WHAT IT READS
-------------
`Perpres 49/2021 Lampiran II` — "Bidang Usaha yang Dialokasikan atau Kemitraan
dengan Koperasi dan Usaha Mikro, Kecil, dan Menengah", 22 pages, vaulted by
`vault_fetch_perpres.py` as BPK download id 161564. This is the OPERATIVE
annex: 49/2021 art. 4 replaced 10/2021's Lampiran II wholesale.

WHY IT IS A COMPILER AND NOT A TRANSCRIPTION
---------------------------------------------
Its sibling `perpres_foreign_cap_relation.py` holds 41 hand-transcribed rows
because Lampiran III's text layer is unusable. Lampiran II's is not: it is
CORRUPTED but DETERMINISTICALLY so, which is a different thing, and a parse
beats a transcription whenever the corruption can be inverted with evidence.
Both halves of that inversion are derived here, never assumed:

* **The substitution table.** The text layer renders digits as letters —
  `01122`->`oLt22`, `10392`->`to392`, `16293`->`r6293`. The table was not
  guessed: for every corrupt token, the candidate 2020 codes were filtered by
  (a) the digits that DID survive, in position, and (b) whether the row's own
  bidang usaha shares a content word with that code's official title. Only
  tokens with exactly ONE surviving candidate contributed, and the resulting
  map is internally consistent across 33 independent observations — `t`->`1`
  twenty times and never anything else, `o`->`0` eleven times. A character that
  had mapped two ways would have invalidated the method; none does.

* **The column boundary.** DIALOKASIKAN (reserved — blocks a PMA) and KEMITRAAN
  (a partnership duty — does NOT block a PMA) are adjacent tick columns, and
  confusing them is the exact over-match the corner warns about. The `V` marks
  fall in two clusters, x in 90..100 and x in 108..109, with **no mark anywhere
  between 101 and 107**; the split at 105 sits inside a real gap, not on a
  guessed threshold. `--json` re-emits the histogram so a future reader can see
  the gap is still there rather than trust this sentence.

THE UNIT IS THE (bidang usaha, KBLI) PAIR — NEVER THE CODE
-----------------------------------------------------------
`71204` (Jasa Pengujian Teknis) appears in this annex TWICE under different
bidang usaha. And many reservations are qualified by CONSTRUCTION GRADE in the
bidang usaha text — "sederhana dan madya" — so the row reserves a segment of
the activity, not the whole code. A code -> reserved boolean join is therefore
structurally wrong, and this module refuses to emit one: it emits ROWS, each
carrying its own bidang usaha and page.

COUNTS: 181 ROWS FROM 180 TICKS, AND THE DIFFERENCE IS NOT AN ERROR
--------------------------------------------------------------------
Annex row 13 (page 4) carries TWO codes under a single tick, so `ticks` and
`rows_emitted` are separate fields rather than one number: reading "181 of 180"
as a tick count that grew would be a defect, and a single `tick_rows` field
invited exactly that. `unresolved` is 0 — but the field stays, and an
`unresolved` list is never omitted from the output, because the honest report
of a gap is a gap that is printed and not a gap that leaves no trace.

Five rows do not come from the text layer at all; they are in `IMAGE_READ`,
carry `read_from: "page-image"`, and a stale override is a hard failure rather
than four silently dropped rows.

Usage:
    python scripts/kbli_filiera/parse_perpres_lampiran2.py [--vault-root PATH] [--write] [--json]

Exit: 0 ok · 1 output differs from the committed file (with --write absent)
      4 CANNOT-VERIFY (vault artifact or pdftotext missing) — never confused
        with "parsed and found nothing", superscar #2.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "data" / "kbli-filiera" / "perpres-umkm-reservation.json"
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
CROSSWALK = REPO_ROOT / "data" / "kbli-filiera" / "bps-crosswalk" / "edges-lampiran5.json"

VAULT_ID = 161564
VAULT_REL = "perpres/161564__Perpres Nomor 49 Tahun 2021 - Lampiran II.pdf"
INSTRUMENT = "Perpres 49/2021 Lampiran II"

EXIT_OK, EXIT_DIFF, EXIT_CANNOT_VERIFY = 0, 1, 4

# Derived (see docstring), not assumed. Every entry is a digit the text layer
# renders as a letter; each was confirmed by >=1 unambiguous row and no entry
# was ever observed mapping two ways.
SUBSTITUTIONS = {"o": "0", "O": "0", "t": "1", "l": "1", "L": "1", "i": "1",
                 "I": "1", "r": "1", "S": "5", "s": "5", "B": "8", "Z": "2"}
COLUMN_SPLIT_X = 105  # inside the empty 101..107 band between the two tick clusters
CODE_WINDOW = 45      # chars left of the tick that can hold the KBLI cell

_WORD_RE = re.compile(r"[a-z]{4,}")
# A numbered activity heading — "26", "27." — at the left margin of the bidang
# usaha column. It is where one row ends and the next begins, and it is the only
# structural marker the text layer preserves; continuation lines are indented far
# past it. The bound is 12 chars so a deeply indented "5." INSIDE a cell (several
# rows carry one) can never be read as the start of a new row.
_ROW_START_RE = re.compile(r"^\s{0,12}\d{1,3}\.?\s+\S")
# NOT a row boundary — this is written down because it looks like one.
# A dash bullet can be a sibling ROW ("- mekanikal", "- pemasangan kaca") or a
# sub-item INSIDE a single row: annex row 13 on page 4 lists four dashed
# products (peci/kopiah, ikat kepala, ikat pinggang, mukena) under ONE tick.
# Treating dashes as boundaries was tried and measured: it tidied one row's text
# and cost `47971` its code, because the line carrying it was cut out of the
# span. The layer cannot tell the two dashes apart, so the row span does not
# try — a slightly over-long activity string is harmless, a lost code is not.

# The four rows the text layer cannot yield, read from 150dpi renders of the
# vaulted PDF (id 161564) and keyed by the exact junk the layer DID produce, so
# a stale override cannot silently attach to a different row.
#
# Three are digit-to-digit corruption — a printed `1` coming through as `7` —
# which the substitution table cannot invert BY CONSTRUCTION: it maps letters to
# digits and never a digit to another digit, because a digit-to-digit rule would
# make every surviving digit in every code a guess. The fourth is a shape the
# one-tick-one-code model does not have: annex row 13 carries TWO codes under a
# single tick, so it expands to two rows here.
IMAGE_READ: dict[tuple[int, str], tuple[str, ...]] = {
    # (page, the junk the layer produced) -> what the page image shows
    (3, "70794"): ("10794",),     # p3 row 8 — Industri kerupuk, keripik, peyek
    (9, "42973"): ("42913",),     # p9 row 35 — pelabuhan perikanan
    (11, "43297"): ("43291",),    # p11 — mekanikal
    (14, "47971"): ("47911",),    # p14 row 47 — komoditi makanan/minuman/farmasi (retired in 2025)
    (4, ""): ("14111", "14131"),  # p4 row 13 — two codes under one tick, empty KBLI cell
}
# The row's own leading number is structure, not activity ("26  Konstruksi …").
_LEADING_NUMBER_RE = re.compile(r"^\d{1,3}\.?\s+")
# Page furniture below the table. Without this stop the downward walk swallows
# the printing-office mark into the last row's activity — measured on `42201`,
# whose text gained "SK No 054252C".
_PAGE_FURNITURE_RE = re.compile(r"^\s*(SK\s*No|PRES\s*IDEN|REPUBLIK\s+INDONESIA)", re.IGNORECASE)
# Words too generic to corroborate a code (they head hundreds of KBLI titles).
_GENERIC = frozenset({
    "industri", "usaha", "aktivitas", "pertanian", "budidaya", "pengolahan",
    "jasa", "perdagangan", "lainnya", "konstruksi", "bangunan", "pemasangan",
})


def decode(token: str) -> str:
    return "".join(SUBSTITUTIONS.get(ch, ch) for ch in token)


def content_words(text: str) -> set[str]:
    return set(_WORD_RE.findall(unicodedata.normalize("NFKD", text.lower()))) - _GENERIC


def pdf_text(pdf: Path) -> str:
    """Layout-preserving text. Column positions are the whole method here, so
    `-layout` is not a nicety — without it every x coordinate is gone."""
    if shutil.which("pdftotext") is None:
        raise FileNotFoundError("pdftotext not on PATH (poppler); cannot verify")
    proc = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext exited {proc.returncode}: {proc.stderr.strip()[:200]}")
    return proc.stdout


def code_at(line: str, tick_x: int) -> str:
    """The KBLI cell immediately left of a tick, decoded. '' when unreadable."""
    window = re.sub(r"\s+", "", decode(line[max(0, tick_x - CODE_WINDOW):tick_x]))
    return window[-5:] if len(window) >= 5 and window[-5:].isdigit() else ""


def cell_at(line: str, tick_x: int) -> str:
    """The bidang usaha column of one line, cut where the KBLI cell begins.

    Cutting at a fixed `tick_x - CODE_WINDOW` instead would slice mid-word:
    the code column floats (a code can sit 10 or 40 chars left of its tick), so
    a fixed margin is either too narrow to catch the code or wide enough to eat
    the end of the activity — and the words it eats are the ones that decide the
    bucket, e.g. "…teknologi sederhana | dan madya".
    """
    left = line[:tick_x]
    # Walk back over the KBLI cell: whitespace, then its (possibly corrupted,
    # possibly space-split) glyphs. Nothing else lives between the two columns.
    cut = len(left.rstrip())
    token = 0
    while cut > 0 and token < 8 and (left[cut - 1].isalnum() or (token and left[cut - 1] == " ")):
        cut -= 1
        token += 1
    if not re.fullmatch(r"\d{5}", decode(re.sub(r"\s", "", left[cut:]))):
        cut = len(left)  # no KBLI cell on this line — the whole width is activity
    return _LEADING_NUMBER_RE.sub("", left[:cut].strip(" -\t")).strip(" -\t")


def row_line_span(lines: list[str], i: int, ticks: list[int], tick_x: int) -> list[int]:
    """Which lines belong to the table row whose tick is on line `i`.

    A row wraps over several lines and the tick sits on only one of them, so
    reading the tick's own line alone truncates the activity — measured: the
    grade qualifier "sederhana dan madya" wraps off the tick line on `42101`
    and `42201`, which is exactly the text that decides whether a reservation
    covers a whole code or one construction grade. Truncating it does not
    produce a missing bucket, it produces a WRONG one, and in the dangerous
    direction: a row wrongly called whole-code would be handed to the owner as
    a question about an activity the annex never reserved.

    Bounds, all three derived from the layout rather than guessed:
    * never past an adjacent tick — measured, no line in this annex carries two
      ticks, so one tick is exactly one row;
    * never past a numbered row start (`26`, `27.`), which is where the next
      activity begins;
    * **never past a SECOND KBLI cell.** A row has exactly one, so a second code
      line means the next row has begun. This is the bound that matters, because
      the neighbouring row's code is close enough to be picked up as this row's:
      on page 14 the `47911` row ran on and took `47912` from the row below it,
      which is a silently WRONG code rather than a declared gap.
      Dash bullets are NOT usable for this — see the note at `_ROW_START_RE`.
    Upward is walked only when the tick line has no text of its own, since a
    tick vertically centred in a tall cell can land below its first line; it
    stops INCLUSIVE at the row's own code line, which is that row's top edge.
    """
    previous = max([t for t in ticks if t < i], default=-1)
    following = min([t for t in ticks if t > i], default=len(lines))
    has_code = lambda j: bool(code_at(lines[j], tick_x))

    span = [i]
    seen_code = has_code(i)
    for j in range(i + 1, following):
        if _ROW_START_RE.match(lines[j]) or _PAGE_FURNITURE_RE.match(lines[j]):
            break
        if has_code(j):
            if seen_code:
                break
            seen_code = True
        span.append(j)
    if not cell_at(lines[i], tick_x):
        for j in range(i - 1, previous, -1):
            if _PAGE_FURNITURE_RE.match(lines[j]):
                break
            span.insert(0, j)
            if _ROW_START_RE.match(lines[j]) or has_code(j):
                break  # inclusive: that line IS the row's first
    return span


def parse(text: str, titles: dict[str, str], known: frozenset[str]) -> dict:
    rows: list[dict] = []
    unresolved: list[dict] = []
    tick_histogram: dict[int, int] = {}
    consumed: set[tuple[int, str]] = set()

    for page_no, page in enumerate(text.split("\f"), start=1):
        lines = page.splitlines()
        ticks = [n for n, line in enumerate(lines) if re.search(r"\bV\b", line)]
        for i in ticks:
            x = min(m.start() for m in re.finditer(r"\bV\b", lines[i]))
            tick_histogram[x] = tick_histogram.get(x, 0) + 1
            span = row_line_span(lines, i, ticks, x)
            column = "dialokasikan" if x < COLUMN_SPLIT_X else "kemitraan"

            code = next((c for c in (code_at(lines[j], x) for j in span) if c in known), "")
            activity = " ".join(filter(None, (cell_at(lines[j], x) for j in span))).strip() or None

            if code:
                found, read_from = (code,), "text-layer"
            else:
                key = (page_no, code_at(lines[i], x))
                found, read_from = IMAGE_READ.get(key, ()), "page-image"
                if found:
                    consumed.add(key)
                else:
                    unresolved.append({"page": page_no, "column": column,
                                       "window": key[1] or None, "text": activity})
                    continue

            for one in found:
                official = titles.get(one, "")
                rows.append({
                    "code": one,
                    "column": column,
                    "page": page_no,
                    "text": activity,
                    "read_from": read_from,
                    # True only when the row's own words independently corroborate the
                    # decoded digits. A row without it is not wrong — it is single-witness.
                    "title_corroborated": bool(activity and content_words(activity) & content_words(official)),
                })

    rows.sort(key=lambda r: (r["page"], r["code"], r["column"]))
    unresolved.sort(key=lambda r: (r["page"], r["window"] or ""))
    return {"rows": rows, "unresolved": unresolved, "ticks": sum(tick_histogram.values()),
            # Overrides that matched nothing. On a full-document parse that means
            # the layer's output moved under them, so the hand-read code is now
            # attached to a row that no longer exists — the caller must fail
            # rather than publish 176 rows and quietly drop 4.
            "image_read_unused": sorted(set(IMAGE_READ) - consumed),
            "tick_x_histogram": {str(k): v for k, v in sorted(tick_histogram.items())}}


def load_reference() -> tuple[dict[str, str], frozenset[str]]:
    """2020 titles (the annex speaks KBLI 2020) plus every code either catalogue
    knows, which is the membership test a decoded token must pass."""
    titles: dict[str, str] = {}
    for edge in json.loads(CROSSWALK.read_text()):
        code = str(edge.get("kbli_2020") or "")
        if code and code not in titles and edge.get("uraian_2020"):
            titles[code] = edge["uraian_2020"]
    canonical = json.loads(CANONICAL.read_text())["data"]
    live = {str(rec["kode_kbli_2025"]): rec["judul"] for rec in canonical}
    for code, judul in live.items():
        titles.setdefault(code, judul)
    return titles, frozenset(titles)


def build(vault_root: Path) -> dict:
    pdf = vault_root / VAULT_REL
    if not pdf.is_file():
        raise FileNotFoundError(
            f"vault artifact missing: {pdf}\n"
            "run: python scripts/kbli_filiera/vault_fetch_perpres.py"
        )
    titles, known = load_reference()
    parsed = parse(pdf_text(pdf), titles, known)
    if parsed["image_read_unused"]:
        raise RuntimeError(
            "image-read overrides matched nothing on a full parse: "
            f"{parsed['image_read_unused']} — the text layer moved under them; "
            "re-read those pages before trusting this table"
        )
    return {
        "instrument": INSTRUMENT,
        "vintage": "2021 (Perpres 49/2021, arts. 3-5 replaced all three annexes of 10/2021)",
        "unit": "(bidang usaha, KBLI) pair — a code may appear in both columns and under several bidang usaha",
        "columns": {
            "dialokasikan": "reserved for Koperasi/UMKM — a PT PMA cannot take the named bidang usaha",
            "kemitraan": "partnership duty with Koperasi/UMKM — does NOT bar foreign ownership",
        },
        "source": {"vault_id": VAULT_ID, "vault_rel_path": VAULT_REL,
                   "fetcher": "scripts/kbli_filiera/vault_fetch_perpres.py"},
        "method": {
            "text_layer": "pdftotext -layout; column x-positions are load-bearing",
            "substitutions": SUBSTITUTIONS,
            "substitutions_derived_by": "unique-candidate resolution (surviving digits in position + bidang usaha word shared with the official 2020 title); internally consistent over 33 observations",
            "column_split_x": COLUMN_SPLIT_X,
            "code_window_chars": CODE_WINDOW,
        },
        "counts": {
            # `ticks` is the population; `resolved` can EXCEED a per-tick count
            # because one tick may carry two codes (annex row 13). Keeping them
            # as separate fields is why "180 of 181" cannot be read as a tick
            # count that grew.
            "ticks": parsed["ticks"],
            "rows_emitted": len(parsed["rows"]),
            "unresolved": len(parsed["unresolved"]),
            "dialokasikan": sum(1 for r in parsed["rows"] if r["column"] == "dialokasikan"),
            "kemitraan": sum(1 for r in parsed["rows"] if r["column"] == "kemitraan"),
            "title_corroborated": sum(1 for r in parsed["rows"] if r["title_corroborated"]),
            "text_cell_missing": sum(1 for r in parsed["rows"] if r["text"] is None),
        },
        "tick_x_histogram": parsed["tick_x_histogram"],
        "rows": parsed["rows"],
        "unresolved": parsed["unresolved"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault-root", type=Path, default=Path.home() / "nuzantara-vault")
    ap.add_argument("--write", action="store_true", help="write the compiled table to data/kbli-filiera/")
    ap.add_argument("--json", action="store_true", help="print the compiled table to stdout")
    args = ap.parse_args(argv)

    try:
        table = build(args.vault_root.expanduser())
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"CANNOT-VERIFY: {exc}", file=sys.stderr)
        return EXIT_CANNOT_VERIFY

    body = json.dumps(table, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    if args.json:
        print(body, end="")
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(body)
        print(f"wrote {OUTPUT.relative_to(REPO_ROOT)}: "
              f"{table['counts']['rows_emitted']} rows from {table['counts']['ticks']} ticks, "
              f"{table['counts']['unresolved']} unresolved", file=sys.stderr)
        return EXIT_OK

    if OUTPUT.is_file() and OUTPUT.read_text() != body:
        print(f"DIFFERS from {OUTPUT.relative_to(REPO_ROOT)} — re-run with --write", file=sys.stderr)
        return EXIT_DIFF
    if not args.json:
        print(f"{table['counts']['rows_emitted']} rows from {table['counts']['ticks']} ticks, "
              f"{table['counts']['unresolved']} unresolved "
              f"({table['counts']['dialokasikan']} dialokasikan / {table['counts']['kemitraan']} kemitraan)",
              file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
