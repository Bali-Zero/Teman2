#!/usr/bin/env python3
"""Apply LOOP-2 editorial drafts to the canonical KBLI dataset — deterministic gates only.

Draft files (written by the editorial wave writers, adversarially verified upstream):
  <drafts-dir>/<code>.json = {"code", "editorial": {headline, standfirst, body,
  pullQuote?, byTheNumbers?}, "backfill"?: {baliContext?, youllAlsoNeed?}}

Gates (refuse the single draft, never abort the run — a refused code is listed):
  G1 code exists in the dataset
  G2 required keys non-empty; headline ≤90 chars; standfirst ≤220; body 300-700 words
  G3 no unlabeled dead 5-digit refs (KBLI-2020 label window, money/standards innocence —
     same contract as kbli_apply_wave_patches / lint L3)
  G4 L10 inline: ownership-% vs the record's pma_max_asing (imports the lint's guards —
     one SSOT, no drift)
  G5 banned stock sentences (boilerplate census head, 2026-07-08)
  G6 date canon: no dd/mm/yyyy or ISO dates in prose
  G7 backfill applied ONLY where the record field is empty/missing

Writes the canonical data/source_documents/KBLI_2025_FINAL_CLEAN.json (editorial under
intel_2026.editorial), bumps apps/mouth/data/kbli-dataset-version.json, runs the sync
script. Usage:
  python3 scripts/kbli_apply_editorials.py --drafts-dir DIR [--dry-run] [--only 56101,...]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
VERSION = ROOT / "apps/mouth/data/kbli-dataset-version.json"
SYNC = ROOT / "scripts/sync_kbli_dataset.sh"

sys.path.insert(0, str(ROOT / "scripts"))
from kbli_dataset_lint import (  # noqa: E402 — one SSOT for the guards
    L10_CLOSED_IDIOM,
    L10_FOREIGN_CTX,
    L10_HISTORICAL,
    L10_NEG,
    L10_PCT,
    L10_SECTOR_LAW_OVERRIDE,
    L10_WORK_SHARE,
)

BANNED_SENTENCES = (
    "Let me walk you through what it means for a foreign-owned setup.",
    "Here is the honest national-vs-Bali picture before you plan a foreign-owned setup.",
    "the island-wide moratorium (in force since 13 May 2026) only halts",
)
BAD_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")
CODE_REF = re.compile(r"\b(\d{5})\b")
NON_CODE_5DIGIT = {"10000", "50000", "20000", "25000", "30000", "40000", "60000"}
LABELED_2020 = (
    "kbli 2020", "2020 code", "kbli2020", "formerly",
    "previous code", "from kbli 2020", "under kbli 2020",
)


def editorial_prose(ed: dict):
    for f in ("headline", "standfirst", "body", "pullQuote"):
        v = ed.get(f)
        if isinstance(v, str) and v.strip():
            yield f, v
    for i, n in enumerate(ed.get("byTheNumbers") or []):
        if isinstance(n, dict):
            yield f"byTheNumbers[{i}]", f"{n.get('label', '')}: {n.get('value', '')}"


def gate_g2(ed: dict) -> str | None:
    for k in ("headline", "standfirst", "body"):
        if not str(ed.get(k) or "").strip():
            return f"G2 empty {k}"
    if len(ed["headline"]) > 90:
        return f"G2 headline {len(ed['headline'])} chars > 90"
    if len(ed["standfirst"]) > 220:
        return f"G2 standfirst {len(ed['standfirst'])} chars > 220"
    words = len(ed["body"].split())
    if not 300 <= words <= 700:
        return f"G2 body {words} words outside 300-700"
    return None


def gate_g3(ed: dict, codes: set[str], own: str) -> str | None:
    for field, text in editorial_prose(ed):
        for m in CODE_REF.finditer(text):
            ref = m.group(1)
            if ref == own or ref in codes or ref in NON_CODE_5DIGIT:
                continue
            idx = m.start()
            ctx = text[max(0, idx - 24) : idx + 36].lower()
            if any(w in ctx for w in ("rp", "idr", "usd", "$", "m2", "sqm", "meter")):
                continue
            std_ctx = text[max(0, idx - 70) : idx].lower()
            if re.search(r"\b(iso(/iec)?|iec|sni|din|en)\b[^.]{0,60}$", std_ctx):
                continue
            before = text[max(0, idx - 60) : idx].lower()
            if any(w in before for w in LABELED_2020):
                continue
            return f"G3 unlabeled dead ref {ref} in {field}"
    return None


def gate_g4(ed: dict, rec: dict, maxa_by_code: dict[str, int]) -> str | None:
    code = rec["kode_kbli_2025"]
    if code in L10_SECTOR_LAW_OVERRIDE:
        return None
    maxa = rec.get("pma_max_asing")
    if not isinstance(maxa, int):
        return None
    for field, text in editorial_prose(ed):
        for m in L10_PCT.finditer(text):
            val = int(m.group(1))
            if val == maxa:
                continue
            if L10_CLOSED_IDIOM.match(text[m.end() : m.end() + 12]):
                continue
            if L10_NEG.search(text[max(0, m.start() - 6) : m.start()]):
                continue
            if L10_HISTORICAL.search(text[max(0, m.start() - 40) : m.start()]):
                continue
            win = text[max(0, m.start() - 80) : m.end() + 80]
            if L10_WORK_SHARE.search(win):
                continue
            before_clause = text[max(0, m.start() - 50) : m.start()]
            refs = re.findall(r"\b(\d{5})\b", before_clause)
            if any(rc != code and maxa_by_code.get(rc) == val for rc in refs):
                continue
            if L10_FOREIGN_CTX.search(win):
                return f"G4 ownership {val}% vs pma_max_asing={maxa} in {field}"
    return None


def gate_g5(ed: dict) -> str | None:
    for field, text in editorial_prose(ed):
        for s in BANNED_SENTENCES:
            if s.lower() in text.lower():
                return f"G5 banned sentence in {field}: {s[:50]}…"
    return None


def gate_g6(ed: dict) -> str | None:
    for field, text in editorial_prose(ed):
        m = BAD_DATE.search(text)
        if m:
            return f"G6 non-canon date '{m.group(0)}' in {field}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts-dir", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    only = {c.strip() for c in args.only.split(",") if c.strip()}

    raw = json.loads(DATASET.read_text(encoding="utf-8"))
    recs = {r["kode_kbli_2025"]: r for r in raw["data"]}
    codes = set(recs)
    maxa_by_code = {
        c: r.get("pma_max_asing") for c, r in recs.items() if isinstance(r.get("pma_max_asing"), int)
    }

    applied, backfilled, refused = 0, 0, []
    for pf in sorted(Path(args.drafts_dir).glob("[0-9]*.json")):
        try:
            draft = json.loads(pf.read_text(encoding="utf-8"))
        except Exception as e:  # malformed file = refusal, not crash
            refused.append((pf.name, f"G0 unparseable: {e}"))
            continue
        code = str(draft.get("code", ""))
        if only and code not in only:
            continue
        if code not in recs:
            refused.append((code or pf.name, "G1 unknown code"))
            continue
        ed = draft.get("editorial")
        if not isinstance(ed, dict):
            refused.append((code, "G2 missing editorial object"))
            continue
        rec = recs[code]
        err = (
            gate_g2(ed)
            or gate_g3(ed, codes, code)
            or gate_g4(ed, rec, maxa_by_code)
            or gate_g5(ed)
            or gate_g6(ed)
        )
        if err:
            refused.append((code, err))
            continue

        clean = {
            "headline": ed["headline"].strip(),
            "standfirst": ed["standfirst"].strip(),
            "body": ed["body"].strip(),
        }
        if str(ed.get("pullQuote") or "").strip():
            clean["pullQuote"] = ed["pullQuote"].strip()
        btn = [
            {"label": str(n.get("label", "")).strip(), "value": str(n.get("value", "")).strip()}
            for n in (ed.get("byTheNumbers") or [])
            if isinstance(n, dict) and str(n.get("label", "")).strip() and str(n.get("value", "")).strip()
        ]
        if btn:
            clean["byTheNumbers"] = btn

        intel = rec.setdefault("intel_2026", {})
        if not args.dry_run:
            intel["editorial"] = clean
        applied += 1

        # G7 — backfill only into EMPTY record fields, same G3/G4 gates apply
        bf = draft.get("backfill") or {}
        for f in ("baliContext", "youllAlsoNeed"):
            v = str(bf.get(f) or "").strip()
            if not v or str(intel.get(f) or "").strip():
                continue
            probe = {"headline": "x", "standfirst": "x", "body": v}
            if gate_g3(probe, codes, code) or gate_g4(probe, rec, maxa_by_code):
                refused.append((code, f"G7 backfill.{f} failed content gates (kept empty)"))
                continue
            if not args.dry_run:
                intel[f] = v
            backfilled += 1

    if not args.dry_run and applied:
        # same byte-format + bump convention as kbli_apply_wave_patches.py
        body = json.dumps(raw, ensure_ascii=False, indent=2)
        DATASET.write_text(body, encoding="utf-8")
        sha = hashlib.sha256(DATASET.read_bytes()).hexdigest()
        ver = json.loads(VERSION.read_text(encoding="utf-8"))
        ver["lastModified"] = dt.date.today().isoformat()
        ver["datasetSha256"] = f"sha256:{sha}"
        VERSION.write_text(json.dumps(ver, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        subprocess.run(["bash", str(SYNC)], check=True, cwd=ROOT)
        print(f"written + synced; sha {sha[:16]}…")

    print(f"applied: {applied} | backfilled fields: {backfilled} | refused: {len(refused)}")
    for c, why in refused[:40]:
        print(f"  REFUSED {c}: {why}")
    return 0 if applied and not args.dry_run or args.dry_run else 1


if __name__ == "__main__":
    sys.exit(main())
