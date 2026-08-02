#!/usr/bin/env python3
"""Compile the KBLI code set of `Perpres 49/2021 Lampiran I` (Bidang Usaha Prioritas).

WHY ONLY THE CODE SET
---------------------
Its sibling `parse_perpres_lampiran2.py` compiles ROWS, because Lampiran II is a
restriction: which column a tick sits in decides whether a PMA is barred, so the
(bidang usaha, KBLI) pair and its text are load-bearing. Lampiran I is the
opposite kind of list — `Daftar Bidang Usaha Prioritas`, activities the state
INCENTIVISES (tax holiday, allowance, facilities). Membership restricts nobody.

It is compiled anyway for one narrow but load-bearing reason: **Pasal 3 ayat (1)
huruf a**. A code in this annex is a priority field, so it is NOT in the residual
category `huruf d`, and `perpres_body_default_relation.py` would otherwise cite
Pasal 3(1)(d) — the wrong article — for every one of them. Attributing a code to
an article it does not fall under is exactly the blanket-attribution defect that
module exists to close; it may not reproduce it one annex to the left.

Caught by an independent legal-reading review (Codex, cross-family) which
observed the omission before any of this shipped: the negative locator checked
the body's lists, Lampiran II and Lampiran III, and read everything else as
residual — but "everything else" silently included category (a).

THE READ IS TOLERANT, THEN GUARDED
-----------------------------------
Same deterministic text-layer corruption as Lampiran II and III (`ott2t` for
`01121`, `ott22` for `01122` on page 1 alone), so the substitution table derived
there is reused rather than re-derived. A tolerant scan over a 22-page annex will
happily match things that are not codes, so every candidate must survive an
intersection with a KNOWN code universe (the 2025 catalogue plus the BPS
crosswalk's 2020 side) before it is emitted. Loose match, strict admission.

Bounded on the other side too: the sweep must find codes on a majority of pages
and must recover a hand-checked sample read off page 1, so a decode regression
cannot quietly emit a small set and read as a short annex.

Usage:
    python scripts/kbli_filiera/parse_perpres_lampiran1.py [--write]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    from parse_perpres_lampiran2 import SUBSTITUTIONS, decode
except ImportError:  # pragma: no cover — allow invocation from the repo root
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from parse_perpres_lampiran2 import SUBSTITUTIONS, decode

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
CROSSWALK = REPO_ROOT / "data" / "kbli-filiera" / "bps-crosswalk" / "edges-lampiran5.json"
OUT = REPO_ROOT / "data" / "kbli-filiera" / "perpres-priority-codes.json"

VAULT_ID = 161563
VAULT_REL = "perpres/161563__Perpres Nomor 49 Tahun 2021 - Lampiran I.pdf"
VAULT_PDF = Path.home() / "nuzantara-vault" / VAULT_REL

INSTRUMENT = "Perpres 49/2021 Lampiran I (Daftar Bidang Usaha Prioritas)"
VINTAGE = "2021-05-25"
BASIS = "Pasal 3 ayat (1) huruf a"

EXIT_OK, EXIT_DIFFERS, EXIT_CANNOT_VERIFY = 0, 1, 4

# Hand-read off page 1 of the vaulted PDF. The sweep must recover all of them, so
# a decoder regression fails loudly instead of emitting a plausible short list.
PAGE_ONE_SAMPLE = frozenset({"01111", "01113", "01121", "01122", "01135", "01140", "01160"})


class CannotVerify(Exception):
    """The instrument or the code universe is unreadable. Never emit a short set."""


def token_re() -> re.Pattern[str]:
    """Derived from the substitution table, never hand-copied.

    Writing the class out by hand omitted `r` once already and the run reported
    "the layer is missing a code" — a defect in the probe read as a defect in the
    source. The class has one definition, and it is the table.
    """
    alphabet = "0-9" + "".join(sorted(SUBSTITUTIONS))
    return re.compile(rf"(?<![0-9A-Za-z])([{alphabet}](?:\s?[{alphabet}]){{4}})(?![0-9A-Za-z])")


def known_codes() -> frozenset[str]:
    """Every KBLI code that exists in either vintage — the admission gate."""
    for path in (CANONICAL, CROSSWALK):
        if not path.is_file():
            raise CannotVerify(f"{path} missing; cannot admit candidates against a known universe")
    codes = {str(rec["kode_kbli_2025"]) for rec in json.loads(CANONICAL.read_text())["data"]}
    codes |= {str(e["kbli_2020"]) for e in json.loads(CROSSWALK.read_text()) if e.get("kbli_2020")}
    if not codes:
        raise CannotVerify("the known-code universe is empty")
    return frozenset(codes)


def pages(pdf: Path = VAULT_PDF) -> list[str]:
    if not pdf.is_file():
        raise CannotVerify(
            f"{pdf} absent — run: python scripts/kbli_filiera/vault_fetch_perpres.py"
        )
    proc = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise CannotVerify(f"pdftotext failed ({proc.returncode}) on {pdf}")
    return proc.stdout.split("\f")


def codes_on(page: str, known: frozenset[str]) -> set[str]:
    out = set()
    for match in token_re().finditer(page):
        code = decode(re.sub(r"\s", "", match.group(1)))
        if code.isdigit() and code in known:
            out.add(code)
    return out


def build() -> dict:
    known = known_codes()
    text_pages = pages()
    per_page = [codes_on(page, known) for page in text_pages]
    found: set[str] = set().union(*per_page) if per_page else set()

    # Bounded so a decode regression cannot pass as a short annex.
    missing_sample = PAGE_ONE_SAMPLE - found
    if missing_sample:
        raise CannotVerify(f"page-1 sample not recovered: {sorted(missing_sample)}")
    pages_with_codes = sum(1 for codes in per_page if codes)
    if pages_with_codes < len(per_page) / 2:
        raise CannotVerify(
            f"codes found on only {pages_with_codes} of {len(per_page)} pages — decode regression?"
        )

    return {
        "instrument": INSTRUMENT,
        "vintage": VINTAGE,
        "basis": BASIS,
        "unit": "KBLI 2020 code (the vintage the annex speaks)",
        "note": "Priority = INCENTIVISED, never restricted. Compiled only so the negative "
                "locator does not cite Pasal 3(1)(d) for a code that is Pasal 3(1)(a).",
        "source": {"vault_id": VAULT_ID, "vault_rel_path": VAULT_REL,
                   "fetcher": "scripts/kbli_filiera/vault_fetch_perpres.py"},
        "counts": {"codes": len(found), "pages": len(per_page), "pages_with_codes": pages_with_codes},
        "codes": sorted(found),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write the artifact (default: compare only)")
    args = ap.parse_args(argv)

    try:
        built = build()
    except CannotVerify as exc:
        print(f"CANNOT-VERIFY: {exc}", file=sys.stderr)
        return EXIT_CANNOT_VERIFY

    print(f"{built['instrument']} — {built['counts']['codes']} codes over "
          f"{built['counts']['pages_with_codes']}/{built['counts']['pages']} pages")

    if args.write:
        OUT.write_text(json.dumps(built, ensure_ascii=False, indent=1) + "\n")
        print(f"wrote {OUT.relative_to(REPO_ROOT)}")
        return EXIT_OK

    if not OUT.is_file():
        print(f"{OUT.relative_to(REPO_ROOT)} does not exist yet — run with --write", file=sys.stderr)
        return EXIT_DIFFERS
    on_disk = json.loads(OUT.read_text())
    if on_disk.get("codes") != built["codes"]:
        only_disk = sorted(set(on_disk.get("codes") or []) - set(built["codes"]))
        only_built = sorted(set(built["codes"]) - set(on_disk.get("codes") or []))
        print(f"DIFFERS — on disk only: {only_disk}; rebuilt only: {only_built}", file=sys.stderr)
        return EXIT_DIFFERS
    print("artifact matches the instrument")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
