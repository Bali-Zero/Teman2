#!/usr/bin/env python3
"""Apply the 2026-09-22 OSS refresh loop proposal (#7136), ADOPT for all 10.

Spec: cure_specs/oss_refresh_2026_09_22.json — the loop's own PROPOSAL, not an
adjudication (regenerated on M5 2026-09-22 from origin/main 5a4fa3c2fe; its
`canonical_sha256` pins the exact pre-cure canonical). Adjudication: cure_specs/
oss_refresh_adjudication_2026_09_22.json — the signed session decision that
turns the 9 `quarantine_owner` proposals into an applyable ADOPT, one entry
per code (`decision`, `record_sha256`, `oss_rows_sha256`, `disputed_key`,
`reason`, `data_note_append`). The spec's own `l2_transform` entry (93114)
already carries applyable `premises`/`per_skala`/`set`/`drop_keys` and needs
no adjudication file at all — the loop's own docstring says why: its per_skala
is not cure-owned.

Two routes, two different gates (`classify_l2_transform` / `classify_quarantine_owner`
below), both feeding the same `_hardened_cure_io.judge_patch`-style "patch" /
"noop" / refuse vocabulary as `cure_pr2b_source_rows_93114_43110.py`:

  l2_transform (93114 only) — judge each of the spec's `premises`
    (per_skala / _l2_source / _l2_status / absent_probes) against the live
    record; all four must agree on the same state (drift on any one, or
    disagreement between them, refuses).

  quarantine_owner (the other 9) — REFUSED unless the adjudication names the
    code with `decision == "adopt_oss_2025"`, its `record_sha256` pin matches
    the spec's own pin, and its `oss_rows_sha256` pin matches
    `sha256_of(spec's oss_rows)` (a tampered or stale adjudication refuses).
    Only then is the LIVE record read: hashing to the pinned `record_sha256`
    is "patch" (pre-cure); `per_skala == oss_rows` AND `_l2_source ==
    OSS_RBA_resiko_2025` AND neither `_l2_status` nor `absent_probes` present
    is "noop" (post-cure); anything else — including a partial application —
    is a refusal, named, never guessed at. The code's own
    `per_skala_disputed_*` block (`disputed_key`) is NEVER read for its
    content and NEVER written: it stays on the record, byte-identical, as
    the audit trail (the 49213 precedent, `cure_restore_per_ancestor.py`).

The run is all-or-nothing: the first code that refuses aborts before any
write, for every code in the spec. On patch, `l4_bali.verdict_state` is
recomputed via `_l4bali_basis.derive_verdict_state` and only listed as a
touched path if it actually changed (pr2b's own rule) — `l4_bali.status` and
every other `l4_bali` field are left untouched by this compiler.

Dry-run is the default; `--apply` writes, propagates to the canonical's
4 consumer copies via `sync_kbli_dataset.sh sync`, and restamps the
`apps/mouth/data/kbli-dataset-version.json` sidecar. `--spec`, `--adjudication`
and `--canonical` are overridable paths (tests point them at fixtures/tmp
copies and must monkeypatch `propagate` to a no-op — it always targets the
REAL canonical's consumers, matching `cure_pr2b_source_rows_93114_43110.py`).

Exit codes: 0 applied or already cured, 2 refused, 64 usage.
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

_FILIERA_DIR = str(Path(__file__).resolve().parent)
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

import _coverage_basis as coverage  # noqa: E402
import _hardened_cure_io as H  # noqa: E402
import _l4bali_basis as basis  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC_PATH = Path(__file__).resolve().parent / "cure_specs" / "oss_refresh_2026_09_22.json"
ADJUDICATION_PATH = Path(__file__).resolve().parent / "cure_specs" / "oss_refresh_adjudication_2026_09_22.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"
CODE_FIELD = "kode_kbli_2025"
CureError = H.CureError

L2_TRANSFORM = "l2_transform"
QUARANTINE_OWNER = "quarantine_owner"
QUARANTINE_DROP_KEYS = ["_l2_status", "absent_probes"]


class _ArgParser(argparse.ArgumentParser):
    """argparse's default usage-error exit is 2, which this compiler already
    uses for a REFUSAL — a usage typo must never read as a refused cure."""

    def error(self, message: str) -> None:  # noqa: D401
        self.print_usage(sys.stderr)
        self.exit(64, f"{self.prog}: error: {message}\n")


def classify_l2_transform(record: dict, code: str, premises: dict[str, dict]) -> str:
    """Verdict against pinned premises: "patch", "noop", or raise on drift/disagreement.

    Byte-for-byte the same rule as cure_pr2b_source_rows_93114_43110.classify."""
    judged = {f: H.judge_patch(record.get(f), p["old_sha256"], p["new_sha256"], f"{code}.{f}") for f, p in premises.items()}
    distinct = {v for f, v in judged.items() if premises[f]["old_sha256"] != premises[f]["new_sha256"]}
    if len(distinct) != 1:
        raise CureError(f"{code}: premises disagree on state {judged} — partial application, refusing")
    return distinct.pop()


def classify_quarantine_owner(record: dict, code: str, spec_entry: dict, adjudication_codes: dict[str, dict]) -> str:
    """Verdict for a quarantine_owner code: refuse unless the adjudication
    names this code as adopted AND its pins hold, then read the LIVE record's
    own state — pre-cure ("patch"), post-cure ("noop"), or neither (refuse).
    Never touches or type-checks the disputed key's VALUE (list or dict —
    e.g. 20111's `{per_skala, per_skala_legacy}` — this function never reads
    its shape, only its presence)."""
    quarantined_by = spec_entry.get("quarantined_by") or []
    if len(quarantined_by) != 1:
        raise CureError(f"{code}: spec's quarantined_by is not exactly one key: {quarantined_by!r} — refusing an ambiguous owner")
    disputed_key = quarantined_by[0]

    adj = adjudication_codes.get(code)
    if adj is None:
        raise CureError(f"{code}: quarantine_owner with no adjudication entry — refusing an unadjudicated adoption")
    if adj.get("decision") != "adopt_oss_2025":
        raise CureError(f"{code}: adjudication decision {adj.get('decision')!r} is not 'adopt_oss_2025' — refusing")
    if adj.get("disputed_key") != disputed_key:
        raise CureError(f"{code}: adjudication disputed_key {adj.get('disputed_key')!r} != spec's quarantined_by {disputed_key!r} — refusing")

    spec_record_sha256 = spec_entry.get("record_sha256")
    if not spec_record_sha256 or adj.get("record_sha256") != spec_record_sha256:
        raise CureError(f"{code}: adjudication record_sha256 does not match the spec's pin — refusing")

    oss_rows = spec_entry.get("oss_rows")
    if oss_rows is None:
        raise CureError(f"{code}: spec carries no oss_rows to adopt — refusing")
    live_oss_rows_sha256 = H.sha256_of(oss_rows)
    if adj.get("oss_rows_sha256") != live_oss_rows_sha256:
        raise CureError(f"{code}: adjudication oss_rows_sha256 does not match sha256_of(spec oss_rows) — refusing (tampered or stale oss_rows)")

    if disputed_key not in record:
        raise CureError(f"{code}: disputed key {disputed_key!r} missing from the live record — refusing an ungated adoption")

    live_record_sha256 = H.sha256_of(record)
    if live_record_sha256 == spec_record_sha256:
        return "patch"

    per_skala_ok = record.get("per_skala") == oss_rows
    l2_source_ok = record.get("_l2_source") == coverage.OSS_2025_SOURCE
    status_absent = "_l2_status" not in record
    probes_absent = "absent_probes" not in record
    if per_skala_ok and l2_source_ok and status_absent and probes_absent:
        return "noop"

    raise CureError(
        f"{code}: live record hashes to {live_record_sha256!r}, matching neither the pinned "
        f"pre-cure record_sha256 {spec_record_sha256!r} nor the structural post-cure state "
        f"(per_skala==oss_rows:{per_skala_ok} _l2_source_ok:{l2_source_ok} "
        f"_l2_status_absent:{status_absent} absent_probes_absent:{probes_absent}) — the record "
        "drifted or was partially cured under this adjudication; re-derive before writing, "
        "do not overwrite blind"
    )


def plan(records: list[dict], spec: dict, adjudication_codes: dict[str, dict], verdicts: dict[str, str]) -> dict[str, Any]:
    by_code = {str(r.get(CODE_FIELD)): r for r in records}
    items: dict[str, Any] = {}
    for code, verdict in verdicts.items():
        if verdict != "patch":
            continue
        if by_code.get(code) is None:
            raise CureError(f"{code}: not in canonical")
        entry = spec["codes"][code]
        route = entry.get("route")
        if route == L2_TRANSFORM:
            per_skala = entry.get("per_skala")
            if not isinstance(per_skala, list) or not per_skala:
                raise CureError(f"{code}: spec's per_skala must be a non-empty list")
            items[code] = {
                "per_skala": copy.deepcopy(per_skala),
                "set": dict(entry.get("set") or {}),
                "drop_keys": list(entry.get("drop_keys") or []),
            }
        elif route == QUARANTINE_OWNER:
            adj = adjudication_codes[code]
            items[code] = {
                "per_skala": copy.deepcopy(entry["oss_rows"]),
                "set": {"_l2_source": coverage.OSS_2025_SOURCE},
                "drop_keys": list(QUARANTINE_DROP_KEYS),
                "data_note_append": adj["data_note_append"],
            }
        else:
            raise CureError(f"{code}: unknown route {route!r}")
    return items


def apply_item(record: dict, item: dict) -> None:
    record["per_skala"] = item["per_skala"]
    for key, value in item["set"].items():
        record[key] = value
    for key in item["drop_keys"]:
        record.pop(key, None)
    if "data_note_append" in item:
        addition = item["data_note_append"]
        existing = record.get("_data_note")
        record["_data_note"] = f"{existing.rstrip()} {addition}" if isinstance(existing, str) and existing.strip() else addition
    l4 = record.get("l4_bali")
    new_state = basis.derive_verdict_state(record)
    item["_verdict_changed"] = bool(isinstance(l4, dict) and l4.get("verdict_state") != new_state)
    if item["_verdict_changed"]:
        l4["verdict_state"] = new_state


def touched_paths(item: dict) -> set[str]:
    paths = {"per_skala"}
    paths.update(item["set"].keys())
    paths.update(item["drop_keys"])
    if "data_note_append" in item:
        paths.add("_data_note")
    if item.get("_verdict_changed"):
        paths.add("l4_bali.verdict_state")
    return paths


def propagate() -> None:
    check = subprocess.run(["bash", str(SYNC_SCRIPT), "sync"], capture_output=True, text=True)
    if check.returncode != 0:
        raise CureError(f"sync_kbli_dataset.sh failed: {check.stderr[-800:]}")
    sidecar = json.loads(SIDECAR.read_text(encoding="utf-8"))
    sidecar["datasetSha256"] = "sha256:" + hashlib.sha256(CANONICAL.read_bytes()).hexdigest()
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("synced + sidecar updated")


def main(argv: list[str] | None = None) -> int:
    ap = _ArgParser(description=__doc__)
    ap.add_argument("--spec", type=Path, default=SPEC_PATH)
    ap.add_argument("--adjudication", type=Path, default=ADJUDICATION_PATH)
    ap.add_argument("--canonical", type=Path, default=CANONICAL)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    adjudication_doc = json.loads(args.adjudication.read_text(encoding="utf-8"))
    adjudication_codes = adjudication_doc.get("codes") or {}

    payload, records, original = H.load_dataset(args.canonical)
    by_code = {str(r.get(CODE_FIELD)): r for r in records}

    try:
        verdicts: dict[str, str] = {}
        for code, entry in spec["codes"].items():
            record = by_code.get(code)
            if record is None:
                raise CureError(f"{code}: not in canonical")
            route = entry.get("route")
            if route == L2_TRANSFORM:
                verdicts[code] = classify_l2_transform(record, code, entry["premises"])
            elif route == QUARANTINE_OWNER:
                verdicts[code] = classify_quarantine_owner(record, code, entry, adjudication_codes)
            else:
                raise CureError(f"{code}: unknown route {route!r}")
        items = plan(records, spec, adjudication_codes, verdicts)
    except CureError as exc:
        print(f"REFUSED: {exc}")
        return 2

    if not items:
        print(f"already cured ({verdicts}) — no-op")
        return 0

    if not args.apply:
        for code, item in items.items():
            print(f"{code}: per_skala -> {len(item['per_skala'])} row(s); set {item['set']}; drop {item['drop_keys']}")
        print("\ndry-run — rerun with --apply to write")
        return 0

    before = copy.deepcopy(records)
    for code, item in items.items():
        apply_item(by_code[code], item)

    try:
        paths = {code: touched_paths(item) for code, item in items.items()}
        H.verify_untouched(before, records, CODE_FIELD, touched_codes=set(items), touched_field_paths=paths)
    except CureError as exc:
        print(f"REFUSED (untouched_fields): {exc}")
        return 2

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    H.atomic_write_text(args.canonical, body + ("\n" if original.endswith("\n") else ""))

    _, fresh_records, _ = H.load_dataset(args.canonical)
    fresh = {str(r.get(CODE_FIELD)): r for r in fresh_records}
    for code, item in items.items():
        if fresh[code]["per_skala"] != item["per_skala"]:
            print(f"WROTE BUT READ BACK WRONG on {code}")
            return 2

    print(f"applied and verified on re-read: {sorted(items)}")
    propagate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
