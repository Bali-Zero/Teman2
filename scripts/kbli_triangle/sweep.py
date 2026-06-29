"""KBLI Triangle — Phase A runner: deterministic sweep over all 1559 codes.

Produces:
  - FINDINGS.jsonl       : every Layer-0 finding (all severities)
  - auto-patch-LOW.json  : the forced, reversible fixes (NEVER pma_*), as a list
                           of {code, path, old, new, rule_id} — applied by a
                           SEPARATE patcher step, not here.
  - pilot-codes.json     : ~50 codes covering all 9 l4 statuses + trap classes,
                           for the LLM Layer-2 pilot.
  - SUMMARY.md           : human-readable rollup.

Hard gate: sha256 of the concatenated PMA-fingerprint fields across ALL codes is
computed BEFORE and asserted UNCHANGED — this sweep is read-only on pma_*.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kbli_triangle.invariants import Finding, run_all, PMA_FROZEN  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DATASET = REPO / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
OUT = Path(__file__).resolve().parent / "_out"
OUT.mkdir(exist_ok=True)


def load() -> list[dict]:
    raw = json.loads(DATASET.read_text())
    return raw["data"] if isinstance(raw, dict) and "data" in raw else raw


def pma_fingerprint(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for r in rows:
        code = str(r.get("kode_kbli_2025") or "")
        for f in PMA_FROZEN:
            h.update(f"{code}|{f}|{r.get(f)!r}\n".encode())
    return h.hexdigest()


def pick_pilot(rows: list[dict], findings_by_code: dict[str, list[Finding]]) -> list[str]:
    """~50 codes that maximize coverage: every l4 status, every rule that fired,
    plus the known trap classes (national-closed, no-Besar, special-cap)."""
    chosen: list[str] = []
    seen_status: set[str] = set()
    seen_rule: set[str] = set()

    def take(code: str) -> None:
        if code and code not in chosen:
            chosen.append(code)

    # one exemplar per distinct l4 status
    for r in rows:
        st = (r.get("l4_bali") or {}).get("status")
        if st and st not in seen_status:
            seen_status.add(st)
            take(str(r.get("kode_kbli_2025")))
    # one exemplar per distinct rule that fired
    for code, fs in findings_by_code.items():
        for f in fs:
            if f.rule_id not in seen_rule:
                seen_rule.add(f.rule_id)
                take(code)
    # trap classes
    for r in rows:
        c = str(r.get("kode_kbli_2025"))
        if r.get("pma_cap_special") is True:
            take(c)
        if r.get("pma_status") == "TERTUTUP":
            take(c)
        if len(chosen) >= 50:
            break
    return chosen[:50]


def main() -> None:
    rows = load()
    fp_before = pma_fingerprint(rows)

    all_findings: list[Finding] = []
    by_code: dict[str, list[Finding]] = defaultdict(list)
    for r in rows:
        fs = run_all(r)
        for f in fs:
            all_findings.append(f)
            by_code[f.code].append(f)

    # hard gate: nothing in the sweep mutated pma_*
    fp_after = pma_fingerprint(rows)
    assert fp_before == fp_after, "PMA FINGERPRINT MUTATED DURING SWEEP — abort"

    # write ledger
    (OUT / "FINDINGS.jsonl").write_text(
        "\n".join(json.dumps(f.to_dict(), ensure_ascii=False) for f in all_findings)
    )

    # auto-patch LOW: only forced fixes, none touching pma_*
    patch = []
    rows_by_code = {str(r.get("kode_kbli_2025")): r for r in rows}
    for f in all_findings:
        if f.auto_fix is None:
            continue
        path, val = f.auto_fix
        top = path.split(".")[0]
        assert top not in PMA_FROZEN, f"auto_fix targets frozen pma field: {path}"
        # resolve current value for the reversible diff
        rec = rows_by_code.get(f.code, {})
        cur: object = rec
        for seg in path.split("."):
            cur = (cur or {}).get(seg) if isinstance(cur, dict) else None
        patch.append({
            "code": f.code, "path": path, "old": cur, "new": val,
            "rule_id": f.rule_id, "severity": f.severity,
        })
    (OUT / "auto-patch-LOW.json").write_text(json.dumps(patch, ensure_ascii=False, indent=1))

    pilot = pick_pilot(rows, by_code)
    (OUT / "pilot-codes.json").write_text(json.dumps(pilot, ensure_ascii=False, indent=1))

    # summary
    by_rule = Counter(f.rule_id for f in all_findings)
    by_sev = Counter(f.severity for f in all_findings)
    auto = sum(1 for f in all_findings if f.auto_fix is not None)
    edit_cand = sum(1 for f in all_findings if f.rule_id == "R-EDIT-CAND")
    lines = [
        "# KBLI Triangle — Phase A (deterministic) summary",
        "",
        f"- codes scanned: **{len(rows)}**",
        f"- PMA fingerprint sha256: `{fp_before[:16]}…` (unchanged before==after ✓)",
        f"- total findings: **{len(all_findings)}**  (codes with ≥1: {len(by_code)})",
        f"- auto-fixable (forced, non-pma): **{auto}** → auto-patch-LOW.json",
        f"- editorial candidates routed to LLM Layer 2: **{edit_cand}**",
        f"- pilot codes selected: **{len(pilot)}**",
        "",
        "## by severity",
        *[f"- {k}: {v}" for k, v in by_sev.most_common()],
        "",
        "## by rule",
        *[f"- {k}: {v}" for k, v in by_rule.most_common()],
    ]
    (OUT / "SUMMARY.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
