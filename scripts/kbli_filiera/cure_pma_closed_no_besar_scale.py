#!/usr/bin/env python3
"""PMA_CLOSED_NO_BESAR_SCALE — no Usaha Besar scale in OSS means no PT PMA.

THE RULING
----------
Owner ruling, 2026-09-14, verbatim: «100% non PMA i codici che non hanno skala
besar». A KBLI 2025 code whose OSS scale matrix (`per_skala`) is NON-EMPTY and
names no Usaha Besar scale cannot be operated by a PT PMA: foreign ownership 0%.

Legal basis, both read at source:
* Perpres 10/2021 (as amended by 49/2021) Pasal 7 ayat (1): a foreign investor
  may carry on business only as an Usaha Besar.
* Peraturan Menteri Investasi dan Hilirisasi/Kepala BKPM No. 5 Tahun 2025
  Pasal 26 ayat (1): «... yang dikategorikan PMA merupakan usaha besar ...»
  (ditetapkan 2025-10-01; PDF retrieved 2026-09-14, sha256 pinned in the spec).

This REVERSES a reading the filiera took on 2026-08-02/03, when a cross-family
legal review held that Pasal 7(1) conditions the investor and not the activity
(`perpres_body_default_relation.pasal7_review_flags`). That module said which
way those codes move "is the owner's reading (Legge 5)"; this is that reading.

THE SELECTOR — three states, and the rule fires on exactly one
---------------------------------------------------------------
`perpres_body_default_relation.besar_state()`:
* `observed`   — some `per_skala` entry names Besar       -> rule silent
* `unobserved` — `per_skala` is EMPTY (217 records)       -> rule silent: an
                 empty scale matrix is a gap in OUR snapshot, not a fact
* `absent`     — non-empty, and no entry names Besar       -> rule fires

WHAT IT WRITES
--------------
On every `absent` record not already closed: the PMA tuple (TERBATAS / 0 /
located, the two citations as `pma_official_basis`, a bilingual condition), and
on `l4_bali` ONLY the sentences that the ruling makes false — "so this is NOT
closed to foreign ownership", "the answer depends on the scope actually
declared", "nationally TERBUKA 100%", and 93114's provisional "Registrable by a
PT PMA in Bali" verdict. Every other Bali status and reason is left as it was.

Records already TERBATAS/0/located (the four Lampiran II split heirs) are only
ASSERTED, never rewritten: their tuple is fingerprinted by a human editorial
certification, and a rewrite would silently withdraw certified content.

REFUSES RATHER THAN GUESSES
---------------------------
The derived scope must equal the spec's; each record must still hold the tuple
the spec snapshotted (`to_patch`) unless it already holds the cured tuple; every
l4_bali sentence must be found exactly once; nothing outside the declared field
paths may move (`_hardened_cure_io.verify_untouched`).

Usage:
  python scripts/kbli_filiera/cure_pma_closed_no_besar_scale.py           # dry-run
  python scripts/kbli_filiera/cure_pma_closed_no_besar_scale.py --apply
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

FILIERA_DIR = Path(__file__).resolve().parent
if str(FILIERA_DIR) not in sys.path:
    sys.path.insert(0, str(FILIERA_DIR))

import _hardened_cure_io as H  # noqa: E402
from perpres_body_default_relation import besar_state  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL = REPO_ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
SPEC = FILIERA_DIR / "cure_specs/pma_closed_no_besar_scale_2026_09_14.json"
SYNC_SCRIPT = REPO_ROOT / "scripts/sync_kbli_dataset.sh"
SIDECAR_PATH = REPO_ROOT / "apps/mouth/data/kbli-dataset-version.json"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"

RULE = "PMA_CLOSED_NO_BESAR_SCALE"
CODE = "kode_kbli_2025"
METADATA_KEY = "pma_closed_no_besar_scale_2026_09_14"
EXIT_OK, EXIT_REFUSED = 0, 2

CITE_SHORT = "Perpres 10/2021 Pasal 7(1); Permeninves/BKPM 5/2025 Pasal 26(1)"
VINTAGE = "2025-10-01"
BASIS = (
    "Perpres 10/2021 (as amended by Perpres 49/2021) Pasal 7 ayat (1) — a foreign "
    "investor may carry on business only as an Usaha Besar — and Peraturan Menteri "
    "Investasi dan Hilirisasi/Kepala BKPM No. 5 Tahun 2025 Pasal 26 ayat (1), "
    "«yang dikategorikan PMA merupakan usaha besar» (ditetapkan 2025-10-01; "
    "https://www.peraturan.go.id/files/peraturan-bkpm-no-5-tahun-2025.pdf, retrieved "
    "2026-09-14). OSS publishes no Usaha Besar scale for this KBLI 2025 code, so a "
    f"PT PMA cannot operate it; max foreign 0% [{RULE}, owner ruling 2026-09-14]."
)
SOURCE = f"{CITE_SHORT} (retrieved 2026-09-14)"
KONDISI = (
    "No Usaha Besar scale in OSS for this code and a PT PMA must be an Usaha Besar — "
    "foreign ownership 0% / Tidak ada skala Usaha Besar di OSS untuk KBLI ini, "
    f"sedangkan PMA wajib Usaha Besar — kepemilikan asing 0% ({CITE_SHORT})"
)
NOTA = (
    f"{RULE}: closed to PT PMA, no Usaha Besar scale / tertutup bagi PMA, "
    "tanpa skala Usaha Besar"
)
CAP_NOTE = f"owner ruling 2026-09-14 ({RULE}): 0% supersedes the earlier curated cap"

NATIONAL = (
    "OSS publishes no Usaha Besar scale for this code and a PT PMA must be an "
    f"Usaha Besar, so it is closed to foreign ownership nationally ({CITE_SHORT})"
)
# (old sentence, new sentence) — each must occur exactly once where it occurs.
L4_REWRITES: tuple[tuple[str, str, str], ...] = (
    (
        "reason",
        "so this is NOT closed to foreign ownership. It is blocked in Bali",
        f"but {NATIONAL}. It is also blocked in Bali",
    ),
    (
        "reason",
        "The rest of the code is not reserved; the answer depends on the scope actually declared.",
        "The rest of the code is not reserved by the annex — but " + NATIONAL
        + ", at any declared scope.",
    ),
    (
        "bali_closure_note",
        "nationally TERBUKA 100% but",
        f"closed to a PT PMA nationally (no Usaha Besar scale; {CITE_SHORT}), and",
    ),
)
# 93114 carried a provisional, LOW-confidence "registrable by a PT PMA" verdict
# that the ruling contradicts outright; it is the one status this cure moves.
PROVISIONAL_OPEN = "APERTO_BALI_RISCHIO_ALTO"
CLOSED_L4 = {
    "status": "CHIUSO_PMA_NO_BESAR",
    "blocked": True,
    "confidence": "HIGH",
    "needs_review": False,
    "verdict_state": "blocked",
    "review_basis": "owner_ruling_2026_09_14_no_besar_scale",
}
CLOSED_L4_REASON = (
    f"{NATIONAL}. OSS names only Mikro/Kecil/Menengah scales here. Supersedes the "
    "provisional 2026-06-28 APERTO_BALI_RISCHIO_ALTO derivation, which read the "
    "code as registrable by a PT PMA [owner ruling 2026-09-14]."
)


def fires(record: dict[str, Any]) -> bool:
    """The rule, pure. True only on an OBSERVED absence of a Besar scale."""
    return besar_state(record) == "absent"


def is_closed(record: dict[str, Any]) -> bool:
    return (
        record.get("pma_max_asing") == 0
        and record.get("pma_status") in {"TERBATAS", "TERTUTUP"}
        and record.get("pma_verification_status") == "located"
    )


def pma_patch(record: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "pma_status": "TERBATAS",
        "pma_max_asing": 0,
        "pma_verification_status": "located",
        "pma_cap_verified": True,
        "pma_source_vintage": VINTAGE,
        "pma_official_basis": BASIS,
        "pma_source": SOURCE,
        "pma_kondisi": KONDISI,
        "pma_nota": NOTA,
    }
    if record.get("pma_cap_note") is not None:
        patch["pma_cap_note"] = CAP_NOTE
    return patch


def l4_patch(l4: dict[str, Any]) -> dict[str, Any]:
    """Field -> new value on `l4_bali`; raises CureError on an ambiguous match."""
    out: dict[str, Any] = {}
    if l4.get("status") == PROVISIONAL_OPEN:
        out.update(CLOSED_L4)
        out["reason"] = CLOSED_L4_REASON
        return out
    for field, old, new in L4_REWRITES:
        text = l4.get(field)
        if not isinstance(text, str) or new in text:
            continue
        n = text.count(old)
        if n > 1:
            raise H.CureError(f"l4_bali.{field}: {old[:40]!r} occurs {n} times")
        if n == 1:
            out[field] = text.replace(old, new)
    return out


def plan(records: list[dict[str, Any]], spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """code -> {field_path: new_value}. Refuses on any drift from the spec."""
    if spec.get("rule") != RULE:
        raise H.CureError(f"spec rule {spec.get('rule')!r} != {RULE}")
    snap: dict[str, dict[str, Any]] = spec["to_patch"]
    untouched = set(spec["already_closed_untouched"]["codes"])
    derived = {str(r[CODE]) for r in records if fires(r)}
    if derived != set(snap) | untouched:
        raise H.CureError(
            f"derived scope moved: +{sorted(derived - set(snap) - untouched)} "
            f"-{sorted(set(snap) | untouched - derived)}"
        )
    unobserved = sum(besar_state(r) == "unobserved" for r in records)
    if unobserved != spec["out_of_scope"]["unobserved_empty_per_skala"]:
        raise H.CureError(f"empty per_skala count moved: {unobserved}")

    out: dict[str, dict[str, Any]] = {}
    for record in records:
        code = str(record[CODE])
        if code in untouched:
            if not is_closed(record):
                raise H.CureError(f"{code}: expected already closed, is not")
            continue
        if code not in snap:
            continue
        target = pma_patch(record)
        cured = all(record.get(k) == v for k, v in target.items())
        if not cured:
            now = {k: record.get(k) for k in snap[code]}
            if now != snap[code]:
                raise H.CureError(f"{code}: moved since the spec snapshot")
        changes = {k: v for k, v in target.items() if record.get(k) != v}
        l4 = record.get("l4_bali") or {}
        changes.update({f"l4_bali.{k}": v for k, v in l4_patch(l4).items() if l4.get(k) != v})
        if changes:
            out[code] = changes
    return out


def apply_plan(records: list[dict[str, Any]], todo: dict[str, dict[str, Any]]) -> None:
    by_code = {str(r[CODE]): r for r in records}
    for code, changes in todo.items():
        for path, value in changes.items():
            H.write_field(by_code[code], path, value)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    ap.add_argument("--spec", type=Path, default=SPEC)
    args = ap.parse_args(argv)
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        payload, records, original = H.load_dataset(args.canonical)
        todo = plan(records, spec)
    except (OSError, json.JSONDecodeError, KeyError, H.CureError) as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    print(f"{RULE} — mode={'APPLY' if args.apply else 'DRY-RUN'} — {len(todo)} record(s) to patch")
    for code, changes in sorted(todo.items()):
        print(f"  {code}: {sorted(changes)}")
    if not args.apply or not todo:
        print("nothing written")
        return EXIT_OK

    before = copy.deepcopy(records)
    apply_plan(records, todo)
    try:
        H.verify_untouched(before, records, CODE, touched_codes=set(todo),
                           touched_field_paths={c: set(ch) for c, ch in todo.items()})
    except H.CureError as exc:
        print(f"REFUSED (untouched fields): {exc}")
        return EXIT_REFUSED
    if isinstance(payload, dict):
        payload.setdefault("metadata", {})[METADATA_KEY] = {
            "rule": RULE, "ruled": spec["ruled"], "citations": spec["citations"],
            "codes": sorted(set(spec["to_patch"]) | set(spec["already_closed_untouched"]["codes"])),
            "count": len(spec["to_patch"]) + len(spec["already_closed_untouched"]["codes"]),
            "unobserved_out_of_scope": spec["out_of_scope"]["unobserved_empty_per_skala"],
        }
    H.atomic_write_text(args.canonical, json.dumps(payload, ensure_ascii=False, indent=2)
                        + ("\n" if original.endswith("\n") else ""))
    _, reread, _ = H.load_dataset(args.canonical)
    if plan(reread, spec):
        print("REFUSED: read-back still has work to do")
        return EXIT_REFUSED
    print(f"applied and verified on re-read: {len(todo)} record(s)")
    if args.canonical.resolve() != DEFAULT_CANONICAL.resolve():
        print("custom canonical — consumer sync and sidecar skipped")
        return EXIT_OK
    sync = subprocess.run(["bash", str(SYNC_SCRIPT), "sync"], cwd=REPO_ROOT, check=False)
    check = subprocess.run(["bash", str(SYNC_SCRIPT), "--check"], cwd=REPO_ROOT, check=False)
    if sync.returncode or check.returncode:
        print("REFUSED: consumer copies not in sync after the write")
        return EXIT_REFUSED
    digest = "sha256:" + hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    sidecar["datasetSha256"] = digest
    sidecar["lastModified"] = date.today().isoformat()
    H.atomic_write_text(SIDECAR_PATH, json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n")
    print(f"consumers synced; sidecar -> {digest}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
