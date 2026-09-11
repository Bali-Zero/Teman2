#!/usr/bin/env python3
"""vault_to_risk_jsonl.py — pure adapter: vault ruang-lingkup evidence -> the
flat jsonl shape scripts/build_kbli_l2_oss_risk.py expects
(RAW=/tmp/oss_risk_raw.jsonl by default): one line per code,
{"kode","uuid","status","data"}.

WHY: the L2 OSS-risk transform (v10.0-L2-oss-risk, PR #1592/#1598) was fed by
a single-endpoint fetcher (scripts/fetch_oss_risk.py) writing that jsonl
directly and leaving nothing reproducible on disk. The GARUDA-FILIERA vault
(scripts/kbli_filiera/vault_fetch_oss.py) stores the SAME raw
ruang-lingkup/{uuid} response per code at
<vault-root>/oss/<code>/ruang_lingkup.json, plus a 404 record in
<vault-root>/oss/absences.jsonl (endpoint "ruang_lingkup") when OSS has no
scope for that code. This adapter is the missing link: it lets the transform
re-run against a frozen vault snapshot (July or September) instead of a
temp file that no longer exists, so a launch is reproducible from L0
evidence (docs/specs/2026-09-11-kbli-l2-oss-resnapshot-reingest-spec.md §2).

Pure and deterministic: no network, no timestamps, no filesystem-iteration
order — every 5-digit code in the ground truth, in ascending `kode` order
(spec rule 2). A code with neither a data file nor an absence record is
evidence gone missing, not a legitimate 404 — the adapter refuses to invent
it and exits 2 naming the code (Builder Contract, anti-hallucination).

Usage:
    python3 scripts/kbli_filiera/vault_to_risk_jsonl.py \\
        --vault-root ~/nuzantara-vault-20260911 \\
        --out /tmp/l2/sept.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from kbli_filiera import vault_common as common
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from kbli_filiera import vault_common as common

DEFAULT_GROUND_TRUTH = Path("data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json")
ENDPOINT = "ruang_lingkup"


def load_five_digit_codes(ground_truth_path: Path) -> list[tuple[str, str]]:
    """Returns (kode, uuid) pairs for every 5-digit code, sorted ascending by
    `kode` — the ground truth's own array order is not sorted, and
    determinism requires a fixed order (spec rule 2: "ascending kode
    order")."""
    data = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    pairs = [(str(x["kode"]), x["uuid"]) for x in data["data"] if x.get("digits") == 5]
    pairs.sort(key=lambda p: p[0])
    return pairs


def has_absence(vault_root: Path, code: str) -> bool:
    """True if absences.jsonl records at least one ruang_lingkup 404 for this
    code. A snapshot reader only cares whether the absence was recorded, not
    P3's corroboration-over-time policy (that governs the FETCHER, not this
    adapter)."""
    for rec in common.read_jsonl(vault_root / "oss" / "absences.jsonl"):
        if rec.get("code") == code and rec.get("endpoint") == ENDPOINT:
            return True
    return False


def build_record(vault_root: Path, code: str, uuid: str) -> dict:
    """One {"kode","uuid","status","data"} line for `code`. Raises
    LookupError(code) when the vault has neither a data file nor an absence
    record — the caller turns that into exit 2, never a silent skip."""
    data_path = vault_root / "oss" / code / f"{ENDPOINT}.json"
    if data_path.exists():
        raw = json.loads(data_path.read_text(encoding="utf-8"))
        return {"kode": code, "uuid": uuid, "status": 200, "data": raw}
    if has_absence(vault_root, code):
        return {"kode": code, "uuid": uuid, "status": 404, "data": {"success": False, "code": 404}}
    raise LookupError(code)


def build_records(vault_root: Path, ground_truth_path: Path) -> list[dict]:
    return [build_record(vault_root, kode, uuid) for kode, uuid in load_five_digit_codes(ground_truth_path)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault-root", required=True, type=Path, help="e.g. ~/nuzantara-vault-20260911")
    ap.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    vault_root = args.vault_root.expanduser()
    try:
        records = build_records(vault_root, args.ground_truth)
    except LookupError as exc:
        print(
            f"vault_to_risk_jsonl: code {exc} has neither a data file nor an "
            f"absence record under {vault_root} — refusing to invent evidence",
            file=sys.stderr,
        )
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"vault_to_risk_jsonl: wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
