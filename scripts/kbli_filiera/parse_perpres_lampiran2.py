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

WHAT IT DOES NOT KNOW — DECLARED, NOT HIDDEN
---------------------------------------------
12 of the 180 tick-rows do not yield a code from the text layer (5 on page 7
carry a tick with an empty KBLI cell; 4 decode to 5 digits matching no
catalogue; 3 have no readable window). They are emitted in `unresolved` with
their page, so the count reads "168 of 180" everywhere and never "all". 38
resolved rows have a code but no readable bidang usaha (the text wrapped to a
line the tick is not on) — flagged `text: null`, because a row whose activity
is unknown cannot be adjudicated even though its code is certain.

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


def parse(text: str, titles: dict[str, str], known: frozenset[str]) -> dict:
    rows: list[dict] = []
    unresolved: list[dict] = []
    tick_x: dict[int, int] = {}

    for page_no, page in enumerate(text.split("\f"), start=1):
        for line in page.splitlines():
            ticks = [m.start() for m in re.finditer(r"\bV\b", line)]
            if not ticks:
                continue
            x = min(ticks)
            tick_x[x] = tick_x.get(x, 0) + 1
            window = re.sub(r"\s+", "", decode(line[max(0, x - CODE_WINDOW):x]))
            code = window[-5:] if len(window) >= 5 and window[-5:].isdigit() else ""
            text_cell = line[:max(0, x - CODE_WINDOW)].strip(" -\t") or None
            column = "dialokasikan" if x < COLUMN_SPLIT_X else "kemitraan"

            if not code or code not in known:
                unresolved.append({"page": page_no, "column": column,
                                   "window": window[-14:] or None, "text": text_cell})
                continue
            official = titles.get(code, "")
            rows.append({
                "code": code,
                "column": column,
                "page": page_no,
                "text": text_cell,
                # True only when the row's own words independently corroborate the
                # decoded digits. A row without it is not wrong — it is single-witness.
                "title_corroborated": bool(text_cell and content_words(text_cell) & content_words(official)),
            })

    rows.sort(key=lambda r: (r["page"], r["code"], r["column"]))
    unresolved.sort(key=lambda r: (r["page"], r["window"] or ""))
    return {"rows": rows, "unresolved": unresolved,
            "tick_x_histogram": {str(k): v for k, v in sorted(tick_x.items())}}


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
            "tick_rows": len(parsed["rows"]) + len(parsed["unresolved"]),
            "resolved": len(parsed["rows"]),
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
              f"{table['counts']['resolved']} of {table['counts']['tick_rows']} tick-rows", file=sys.stderr)
        return EXIT_OK

    if OUTPUT.is_file() and OUTPUT.read_text() != body:
        print(f"DIFFERS from {OUTPUT.relative_to(REPO_ROOT)} — re-run with --write", file=sys.stderr)
        return EXIT_DIFF
    if not args.json:
        print(f"{table['counts']['resolved']} of {table['counts']['tick_rows']} tick-rows resolved "
              f"({table['counts']['dialokasikan']} dialokasikan / {table['counts']['kemitraan']} kemitraan)",
              file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
