#!/usr/bin/env python3
"""One-shot: 47222 is a UMKM/Koperasi reservation, not a closed-to-everyone code.

WHAT'S WRONG TODAY
-------------------
Canonical carries `pma_status: TERTUTUP` for 47222 (Perdagangan Eceran Minuman
Tidak Beralkohol). `TERTUTUP` in this catalogue is reserved for activities
closed to EVERYONE — narcotics cultivation, alcohol manufacture. 47222's own
`pma_official_basis` names the actual instrument: "Perpres 10/2021 Lampiran
II, line 3731 '- Minuman Tidak Beralkohol 47222 V', V in
DIALOKASIKAN-UNTUK-KOPERASI-DAN-UMKM column, KEMITRAAN column EMPTY = pure
reservation for domestic cooperatives/UMKM". A Koperasi/UMKM allocation closes
the activity to FOREIGN capital, not to domestic entities in general — anyone
who is not disqualified by being foreign (or by not being a cooperative/UMKM)
may still run it.

The precedent already in this catalogue is `47111` (TERBATAS / cap 0 /
kondisi "UMKM only") — a minimarket reservation of the identical shape,
already correctly classified. This is the twin, corrected the same way. Ruled
2026-08-01 (repo-wide, see apply_perpres_foreign_caps.py's docstring): "0%
foreign becomes TERBATAS, never TERTUTUP."

WHAT THIS WRITES, AND WHAT IT REFUSES TO TOUCH
------------------------------------------------
`pma_status`: TERTUTUP -> TERBATAS. `pma_max_asing` stays 0 (unchanged — the
lawful foreign share of a Koperasi/UMKM-reserved activity is zero either way).
`pma_cap_verified` stays True (unchanged). `pma_official_basis` stays
unchanged — it already cites the row.

`pma_kondisi` is written ONLY if the record does not already carry one. On the
live record it already reads "Kemitraan dengan UMKM/Koperasi" (non-null), so
this tool does NOT overwrite it — clobbering a human-authored condition string
is exactly the failure `apply_perpres_foreign_caps.py` and
`apply_umkm_reservations.py` both refuse to commit, and this tool inherits the
same refusal. It prints what it found and moves on.

REFUSES, LOUDLY, RATHER THAN GUESSING
---------------------------------------
Aborts before writing anything if: the code is missing from the dataset; the
observed `pma_max_asing` is not 0 (the world moved since this was drafted);
`pma_official_basis` is empty or does not name Lampiran II (the one fact this
tool's whole premise rests on); or `pma_cap_verified` is not True. Already-
applied (`pma_status` already TERBATAS with the rest matching) is treated as
success, not failure — idempotent, not a re-adjudication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_VERSION = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
SIDECAR_DATASET = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"

CODE = "47222"
KONDISI_IF_ABSENT = "Dialokasikan untuk Koperasi & UMKM (Perpres 49/2021 Lampiran II)"

EXIT_OK = 0
EXIT_REFUSED = 2


class CureError(RuntimeError):
    """A refusal. Never downgraded to a warning."""


def load(path: Path) -> tuple[dict, list[dict], str]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    records = payload["data"] if isinstance(payload, dict) else payload
    if not isinstance(records, list) or not records:
        raise CureError(f"{path}: expected a non-empty record list")
    return payload, records, text


def plan(records: list[dict]) -> dict:
    """Pure. Returns the patch plan or raises CureError on any precondition miss."""
    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    rec = by_code.get(CODE)
    if rec is None:
        raise CureError(f"{CODE}: not in the dataset")

    status = rec.get("pma_status")
    if status == "TERBATAS" and rec.get("pma_max_asing") == 0:
        return {"code": CODE, "noop": True, "reason": "already TERBATAS/0 — idempotent"}
    if status != "TERTUTUP":
        raise CureError(
            f"{CODE}: expected pma_status TERTUTUP (or already-cured TERBATAS), "
            f"found {status!r} — the world moved, re-adjudicate before writing"
        )
    if rec.get("pma_max_asing") != 0:
        raise CureError(
            f"{CODE}: expected pma_max_asing 0, found {rec.get('pma_max_asing')!r}"
        )
    if rec.get("pma_cap_verified") is not True:
        raise CureError(f"{CODE}: pma_cap_verified is not True — refusing to build on it")
    basis = rec.get("pma_official_basis") or ""
    if "Lampiran II" not in basis or "3731" not in basis:
        raise CureError(
            f"{CODE}: pma_official_basis does not cite Lampiran II line 3731 as expected "
            f"— refusing to assert the reservation on a basis that has changed: {basis[:120]!r}"
        )

    existing_kondisi = (rec.get("pma_kondisi") or "").strip()
    patch = {"pma_status": "TERBATAS"}
    kept_kondisi = None
    if existing_kondisi:
        kept_kondisi = existing_kondisi
    else:
        patch["pma_kondisi"] = KONDISI_IF_ABSENT

    return {
        "code": CODE,
        "noop": False,
        "was": {"pma_status": status, "pma_kondisi": rec.get("pma_kondisi")},
        "patch": patch,
        "kept_kondisi": kept_kondisi,
    }


def propagate(dry: bool = False) -> list[str]:
    """Push canonical to every consumer copy and re-stamp the version sidecar.
    Mirrors apply_umkm_reservations.py::propagate — proves the sync rather than
    trusting the exit code (superscar #2)."""
    problems: list[str] = []
    result = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "sync"], capture_output=True, text=True
    )
    if result.returncode != 0:
        problems.append(f"sync_kbli_dataset.sh exited {result.returncode}: {result.stderr[-400:]}")
        return problems

    check = subprocess.run(
        ["bash", str(SYNC_SCRIPT), "--check"], capture_output=True, text=True
    )
    if check.returncode != 0:
        problems.append(f"consumer copies still differ after sync: {check.stdout[-400:]}")
        return problems

    if not SIDECAR_DATASET.exists():
        problems.append(f"sidecar dataset copy missing: {SIDECAR_DATASET}")
        return problems

    digest = "sha256:" + hashlib.sha256(SIDECAR_DATASET.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_VERSION.read_text(encoding="utf-8"))
    if sidecar.get("datasetSha256") == digest:
        return problems  # content did not move; nothing to bump

    if not dry:
        sidecar["datasetSha256"] = digest
        sidecar["lastModified"] = date.today().isoformat()
        SIDECAR_VERSION.write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"  sidecar version -> {digest}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    ap.add_argument("--dataset", default=str(CANONICAL))
    args = ap.parse_args(argv)

    path = Path(args.dataset)
    try:
        payload, records, original = load(path)
        item = plan(records)
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    if item["noop"]:
        print(f"{CODE}: {item['reason']} — nothing to do")
        return EXIT_OK

    print(f"{CODE}: {item['was']} -> {item['patch']}")
    if item["kept_kondisi"] is not None:
        print(f"  keeping existing pma_kondisi on {CODE}: {item['kept_kondisi']!r} (not overwritten)")

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return EXIT_OK

    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    by_code[CODE].update(item["patch"])

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(body + ("\n" if original.endswith("\n") else ""), encoding="utf-8")

    # Read back and prove the write, rather than trusting that it happened.
    _, again, _ = load(path)
    fresh = {str(r.get("kode_kbli_2025")): r for r in again}
    rec = fresh[CODE]
    if rec.get("pma_status") != "TERBATAS" or rec.get("pma_max_asing") != 0:
        print(f"WROTE BUT READ BACK WRONG: {rec.get('pma_status')} / {rec.get('pma_max_asing')}")
        return EXIT_REFUSED
    print(f"\napplied and verified on re-read: {CODE}")

    if path.resolve() != CANONICAL.resolve():
        print(f"not canonical ({path}) — skipping consumer propagation")
        return EXIT_OK

    problems = propagate()
    for p in problems:
        print(f"  PROPAGATION FAILED: {p}")
    if problems:
        return EXIT_REFUSED
    print("consumer copies in sync with canonical")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
