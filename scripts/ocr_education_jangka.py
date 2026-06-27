#!/usr/bin/env python3
"""ocr_education_jangka.py — locate the education (85xxx) rows in the PP28 Lampiran scans and
OCR their jangka_waktu column.

The Lampiran sub-files for Pariwisata-Kesehatan (2.10) and Keuangan-Ketenagakerjaan (2.11) are
image-only scans (no text layer — pdftotext returns nothing), so we rasterise each page with
pdftoppm and OCR with tesseract (ind+eng). The table column order is:
  KBLI | Lingkup/Ruang Lingkup | Tingkat Risiko | Perizinan Berusaha | Jangka Waktu | Kewajiban ...

This script runs in two phases driven by argv:
  --locate <pdf>       : OCR every Nth page (stride) at low DPI, print pages whose text contains
                         an 85xxx code, so we learn the page range cheaply.
  --extract <pdf> <p0> <p1> : OCR pages p0..p1 at high DPI, scan each line for a leading 85xxx
                         code and the first "N Hari"/"Otomatis" token on or near that line, and
                         write a {code: jangka} JSON to OUT.

Output JSON: scratch/education_jangka_ocr.json  (then a SEPARATE apply step folds CLEAN values
into the canonical — this script never mutates the dataset).
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

LAMP = Path("/Users/balizero/Desktop/nuzantara/data/kb_sources/lampiran_pp28")
OUT = Path(__file__).resolve().parents[1] / "scratch" / "education_jangka_ocr.json"

CODE_RE = re.compile(r"\b(85\d{3})\b")           # education KBLI
JANGKA_RE = re.compile(r"(\d{1,3})\s*[Hh]ari(?:\s*[Kk]erja)?|Otomatis")


def ppm_text(pdf: Path, page: int, dpi: int) -> str:
    """Rasterise one page and OCR it, returning the text."""
    with tempfile.TemporaryDirectory() as td:
        stem = Path(td) / "pg"
        subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi), "-png",
             str(pdf), str(stem)],
            check=True, capture_output=True,
        )
        pngs = list(Path(td).glob("pg*.png"))
        if not pngs:
            return ""
        res = subprocess.run(
            ["tesseract", str(pngs[0]), "stdout", "-l", "ind+eng", "--psm", "6"],
            capture_output=True, text=True,
        )
        return res.stdout or ""


def locate(pdf: Path, stride: int = 5, dpi: int = 150):
    import pdfplumber
    with pdfplumber.open(pdf) as p:
        n = len(p.pages)
    hits = []
    for pg in range(1, n + 1, stride):
        txt = ppm_text(pdf, pg, dpi)
        codes = sorted(set(CODE_RE.findall(txt)))
        if codes:
            hits.append((pg, codes))
            print(f"  page {pg}: {codes}", flush=True)
    print(f"LOCATE done: {len(hits)} sample-pages with 85xxx in {pdf.name}", flush=True)
    return hits


def extract(pdf: Path, p0: int, p1: int, dpi: int = 300):
    found = {}
    for pg in range(p0, p1 + 1):
        txt = ppm_text(pdf, pg, dpi)
        lines = txt.splitlines()
        for i, line in enumerate(lines):
            m = CODE_RE.search(line)
            if not m:
                continue
            code = m.group(1)
            # look for a jangka token on this line or the next 2 (tables wrap)
            window = " ".join(lines[i:i + 3])
            jm = JANGKA_RE.search(window)
            if jm:
                val = jm.group(0)
                val = "Otomatis" if val.strip().lower() == "otomatis" else re.sub(
                    r"\s+", " ", val).strip()
                # normalise "5Hari" → "5 Hari"
                nm = re.match(r"(\d{1,3})\s*[Hh]ari", val)
                if nm:
                    val = f"{nm.group(1)} Hari"
                found.setdefault(code, val)
                print(f"  p{pg} {code} → {val}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prev = json.loads(OUT.read_text()) if OUT.exists() else {}
    prev.update(found)
    OUT.write_text(json.dumps(prev, ensure_ascii=False, indent=2))
    print(f"EXTRACT done: {len(found)} codes this run, {len(prev)} total → {OUT}", flush=True)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    mode = sys.argv[1]
    pdf = LAMP / sys.argv[2]
    if not pdf.exists():
        print(f"::error:: {pdf} not found")
        return 2
    if mode == "--locate":
        stride = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        locate(pdf, stride=stride)
    elif mode == "--extract":
        extract(pdf, int(sys.argv[3]), int(sys.argv[4]))
    else:
        print(f"unknown mode {mode}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
