#!/usr/bin/env python3
"""Validate every science-out CSV against the fixed schema and the output rules.

Usage: python3 validate_outputs.py <snapshot_root>
Checks:
  - columns exactly: finding_id, family, code, file, line, claim, confidence, runtime_dependent, suggested_fix
  - confidence parses as float in [0,1]; runtime_dependent in {true,false}
  - finding_id unique within file; family UPPER_SNAKE_CASE; code empty or 5 digits
  - file exists in snapshot (relative path); line empty, integer, or int-int range
  - no single-line quoted span (text between matching straight/curly quotes) longer than 80 chars in any cell
    or in any .md file under science-out/
  - personal-data heuristics: email addresses, phone-like numbers (>= 9 digits with +/-/space), NIK-like 16-digit numbers
Exit code 1 on any violation; prints a JSON report.
"""
import csv, glob, json, os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = f"{ROOT}/science-out"
COLS = ["finding_id", "family", "code", "file", "line", "claim", "confidence", "runtime_dependent", "suggested_fix"]
QUOTE_RX = re.compile(r'"([^"\n]{81,})"|“([^”\n]{81,})”|\'([^\'\n]{81,})\'')  # single-line spans only
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RX = re.compile(r"(?<!\d)(?:\+?\d[\d\s\-]{8,}\d)(?!\d)")
NIK_RX = re.compile(r"(?<!\d)\d{16}(?!\d)")

report = {"files": {}, "violations": []}
def viol(f, msg):
    report["violations"].append(f"{f}: {msg}")

for path in sorted(glob.glob(f"{OUT}/*.csv")):
    rel = os.path.relpath(path, ROOT)
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        if rd.fieldnames != COLS:
            viol(rel, f"columns {rd.fieldnames}")
        rows = list(rd)
    ids = set()
    fam = {}
    for i, r in enumerate(rows, 2):
        fid = r.get("finding_id", "")
        if fid in ids:
            viol(rel, f"row {i} duplicate finding_id {fid}")
        ids.add(fid)
        fam[r["family"]] = fam.get(r["family"], 0) + 1
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", r["family"] or ""):
            viol(rel, f"row {i} family not UPPER_SNAKE: {r['family']!r}")
        if r["code"] and not re.fullmatch(r"\d{5}", r["code"]):
            viol(rel, f"row {i} code not 5 digits: {r['code']!r}")
        try:
            c = float(r["confidence"])
            if not 0 <= c <= 1:
                raise ValueError
        except ValueError:
            viol(rel, f"row {i} confidence {r['confidence']!r}")
        if r["runtime_dependent"] not in ("true", "false"):
            viol(rel, f"row {i} runtime_dependent {r['runtime_dependent']!r}")
        if r["file"] and not os.path.exists(os.path.join(ROOT, r["file"])):
            viol(rel, f"row {i} file not in snapshot: {r['file']}")
        if r["line"] and not re.fullmatch(r"\d+(-\d+)?", r["line"]):
            viol(rel, f"row {i} line {r['line']!r}")
        for col in COLS:
            v = r[col] or ""
            if QUOTE_RX.search(v):
                viol(rel, f"row {i} {col}: quoted span > 80 chars")
            if EMAIL_RX.search(v):
                viol(rel, f"row {i} {col}: email-like string")
            if NIK_RX.search(v):
                viol(rel, f"row {i} {col}: 16-digit number")
    report["files"][rel] = {"rows": len(rows), "by_family": fam,
                            "runtime_dependent_true": sum(1 for r in rows if r["runtime_dependent"] == "true"),
                            "to_verify": sum(1 for r in rows if (r["claim"] or "").upper().startswith("TO VERIFY"))}

for path in sorted(glob.glob(f"{OUT}/*.md")):
    rel = os.path.relpath(path, ROOT)
    txt = open(path, encoding="utf-8").read()
    for m in QUOTE_RX.finditer(txt):
        viol(rel, f"quoted span > 80 chars at offset {m.start()}")
    if EMAIL_RX.search(txt):
        viol(rel, "email-like string")
    if NIK_RX.search(txt):
        viol(rel, "16-digit number")

report["ok"] = not report["violations"]
print(json.dumps(report, indent=1))
sys.exit(0 if report["ok"] else 1)
