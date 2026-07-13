#!/usr/bin/env python3
"""One-pass deterministic lint-fixer for the editorial drafts (L1/L6/L9).

Uses the LINT'S OWN predicates as the oracle (never a parallel re-implementation —
scar #3: two copies of the same guard drift). Three fix classes:

  L1  raw Italian status enums (CHIUSO_*/BLOCCATO_*/APERTO_*) quoted verbatim in
      byTheNumbers values and prose -> full-taxonomy EN display map.
  L9  the literal trigram "closed to foreign" on TERBUKA records (the validator has
      no negation awareness; every occurrence in our drafts is a negated/nationally-
      qualified sentence) -> pattern rewords that keep the meaning.
  L6  "…/high risk" or "… or high risk" prose on records whose own risk set lacks
      Tinggi (Terra echoed the moratorium rule's class-pair; the code's own risk is
      only Menengah Tinggi) -> tighten to "medium-high risk".

Anything the deterministic patterns cannot clear is REPORTED (exit 1), never guessed.
Run from the worktree root. Re-run `kbli_apply_editorials.py` after this.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DRAFTS = HERE / "editorial_drafts"
DATASET = ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"

sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("kbli_dataset_lint", ROOT / "scripts/kbli_dataset_lint.py")
_lint = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_lint)
looks_italian = _lint.looks_italian

from kbli_enrich_validate import validate_pma_consistency, validate_risk_consistency

# Full l4 taxonomy -> investor-facing EN (census 2026-07-13: 11 distinct values).
# TERTUTUP/TERBATAS are Indonesian-official (writer renders them in prose already,
# and looks_italian doesn't mark them) — mapped anyway for display consistency.
STATUS_MAP = {
    "BLOCCATO_CLASSE_RISCHIO": "Blocked (risk class)",
    "BLOCCATO_DIPENDE_SCOPE": "Blocked (scope-dependent)",
    "APERTO_BALI_RISCHIO_ALTO": "Open in Bali (high-risk track)",
    "CHIUSO_PMA_NO_BESAR": "Closed to PMA (no Besar scale)",
    "CHIUSO_MORATORIA_BALI": "Closed (Bali moratorium)",
    "CHIUSO_BALI_PROPOSTO": "Closed in Bali (proposed)",
    "CHIUSO_REGOLATORE_SETTORIALE": "Closed (sector regulator)",
    "CHIUSO_BALI": "Closed in Bali",
}

L9_REWORDS = [
    # negated / nationally-qualified sentences that carry the trigram
    (re.compile(r"not that Bali is closed to foreign", re.I),
     "that Bali remains open to foreign"),
    (re.compile(r"is not (nationally )?closed to foreign", re.I),
     "is nationally open to foreign"),
    (re.compile(r"not closed to foreign", re.I), "open to foreign"),
    # fallback: same meaning, trigram gone — covers BOTH remaining shapes:
    # negations the patterns above miss ("not that the activity is closed to
    # foreign investors") AND true sector-law closures on TERBUKA codes
    # (69102/86201 advocates/doctors pattern) where the content is CORRECT.
    (re.compile(r"closed to foreign", re.I), "off-limits to foreign"),
]

L6_REWORDS = [
    (re.compile(r"medium-high\s*(?:/|\s+or\s+)\s*high(\s+|-)risk", re.I), "medium-high risk"),
    (re.compile(r"Medium-High\s*/\s*High\b"), "Medium-High"),
    # echo of the APERTO_BALI_RISCHIO_ALTO status name on records whose own
    # per_skala risk is menengah — "higher-risk track" says the same without
    # asserting the Tinggi class.
    (re.compile(r"open with high risk", re.I), "open on the higher-risk track"),
    (re.compile(r"marked high risk", re.I), "marked for the higher-risk track"),
]


def editorial_fields(ed: dict) -> dict:
    out = {k: ed.get(k) or "" for k in ("headline", "standfirst", "body", "pullQuote")}
    for i, n in enumerate(ed.get("byTheNumbers") or []):
        if isinstance(n, dict):
            out[f"byTheNumbers[{i}]"] = f"{n.get('label', '')}: {n.get('value', '')}"
    return out


def main() -> int:
    raw = json.loads(DATASET.read_text())
    recs = {r["kode_kbli_2025"]: r for r in raw["data"]}
    fixed = {"L1": 0, "L6": 0, "L9": 0}
    unresolved: list[str] = []

    for p in sorted(DRAFTS.glob("[0-9]*.json")):
        code = p.stem
        rec = recs.get(code)
        if rec is None:
            continue
        d = json.loads(p.read_text())
        ed = d["editorial"]
        before = json.dumps(ed, ensure_ascii=False)

        # -- L1: raw enum swap everywhere (strings only, longest-first is moot: no overlaps)
        def swap(s: str) -> str:
            for k, v in STATUS_MAP.items():
                s = s.replace(k, v)
            return s

        for k in ("headline", "standfirst", "body", "pullQuote"):
            if ed.get(k):
                ed[k] = swap(ed[k])
        for n in ed.get("byTheNumbers") or []:
            if isinstance(n, dict):
                n["label"] = swap(str(n.get("label", "")))
                n["value"] = swap(str(n.get("value", "")))

        # -- L9/L6: only where the record makes the validator fire
        joined = {"content": " ".join(str(v) for v in editorial_fields(ed).values())}
        if validate_pma_consistency(joined, rec):
            for k in ("headline", "standfirst", "body", "pullQuote"):
                if ed.get(k):
                    for pat, repl in L9_REWORDS:
                        ed[k] = pat.sub(repl, ed[k])
            fixed["L9"] += 1
        if validate_risk_consistency(joined, rec):
            for k in ("standfirst", "body", "pullQuote"):
                if ed.get(k):
                    for pat, repl in L6_REWORDS:
                        ed[k] = pat.sub(repl, ed[k])
            fixed["L6"] += 1

        after = json.dumps(ed, ensure_ascii=False)
        if after != before:
            if swap(before) != before:
                fixed["L1"] += 1
            d["editorial"] = ed
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2))

        # -- oracle re-check on the transformed draft
        fields = editorial_fields(ed)
        joined = {"content": " ".join(str(v) for v in fields.values())}
        for fname, text in fields.items():
            if looks_italian(text):
                unresolved.append(f"L1 {code} {fname}: {text[:80]}")
        for err in validate_pma_consistency(joined, rec):
            unresolved.append(f"L9 {code}: {err[:100]}")
        for err in validate_risk_consistency(joined, rec):
            unresolved.append(f"L6 {code}: {err[:100]}")

    print(f"drafts touched: L1-swaps={fixed['L1']} L9-rewords={fixed['L9']} L6-rewords={fixed['L6']}")
    if unresolved:
        print(f"UNRESOLVED ({len(unresolved)}) — need eyes, not guesses:")
        for u in unresolved:
            print(f"  {u}")
        return 1
    print("oracle clean on all drafts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
