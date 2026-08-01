#!/usr/bin/env python3
"""Patch the canonical dataset where the catalogue contradicts the operative Perpres.

Reads the relation and the join from `perpres_foreign_cap_relation.py` (the
evidence layer) and writes ONLY the codes whose activity identity is plain. Every
other divergent code is named below with the reason it is NOT being patched —
the list of what we refused to touch is as much the deliverable as the patch.

WHY AN EXPLICIT TABLE AND NOT A SIMILARITY SCORE
------------------------------------------------
The join is by KBLI-2020 ancestry; the RESTRICTION is by bidang usaha. The two
coincide only when the 2025 code covers the same activity the annex names. Where
it covers MORE, patching would assert a cap over activities the instrument never
restricted: `10761` is "Pengolahan Kopi" while the annex restricts only coffee
WITH a geographical indication; `26513` is "Alat Ukur dan Alat Uji Elektronik"
while the annex restricts defence radar. A string-similarity gate would have
scored both as near-matches — the failure mode is silent and in the direction
that harms a client, so the judgement is written down per code instead.

WHY 0% FOREIGN BECOMES `TERBATAS`, NOT `TERTUTUP`
--------------------------------------------------
"Modal dalam negeri 100%" does not close the activity — it closes it to FOREIGN
capital. `TERTUTUP` in this catalogue holds narcotics cultivation and alcohol
manufacture, i.e. activities closed to everyone; filing an umrah travel agency
there would be a different false statement. The precedent for "anyone may run
it, a foreigner may not own it" already exists and is `47111`
(TERBATAS / cap 0 / kondisi "UMKM only"). These follow it.

NEVER SILENTLY: `--apply` refuses if any divergent code is unadjudicated, if the
table names a code that is not divergent, or if a code the instrument itself
gives two caps is marked plain.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_FILIERA_DIR = str(Path(__file__).resolve().parent)
if _FILIERA_DIR not in sys.path:
    sys.path.insert(0, _FILIERA_DIR)

from perpres_foreign_cap_relation import (  # noqa: E402
    INSTRUMENT,
    RELATION,
    VINTAGE,
    caps_by_code,
    classify_join,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

PLAIN = "plain"          # 2025 code names the same activity the annex restricts
BROADER = "broader"      # 2025 code covers more than the restricted activity
RENAMED = "renamed"      # plausibly the same activity under a new name — unproven

# kbli_2025 -> (verdict, reason). Every divergent code appears exactly once.
ADJUDICATION: dict[str, tuple[str, str]] = {
    # --- identical or unambiguous synonym --------------------------------
    "16221": (PLAIN, "title identical to the annex entry"),
    "25200": (PLAIN, "title identical to the annex entry"),
    "30400": (PLAIN, "'Kendaraan Tempur Militer' is the 2025 name for 'kendaraan perang'"),
    "53200": (PLAIN, "title identical to the annex entry"),
    "79122": (PLAIN, "title identical to the annex entry"),
    "50124": (PLAIN, "title identical: Angkutan Laut Dalam Negeri Pelayaran Rakyat"),
    # Ferry and river/lake transport: the 2025 renumbering shuffled the digits, but
    # EVERY candidate ancestor in this family carries the same 49% cap, so a
    # mis-assigned ancestor cannot change the value written.
    "50131": (PLAIN, "penyeberangan umum antarprovinsi; whole family capped at 49%"),
    "50132": (PLAIN, "penyeberangan umum antarkabupaten/kota; whole family capped at 49%"),
    "50133": (PLAIN, "penyeberangan umum dalam kabupaten/kota; whole family capped at 49%"),
    "50134": (PLAIN, "penyeberangan perintis antarprovinsi; whole family capped at 49%"),
    "50135": (PLAIN, "penyeberangan perintis antarkabupaten/kota; whole family capped at 49%"),
    "50211": (PLAIN, "sungai/danau liner (trayek tetap); goods carried by 5022x, so this is the passenger entry"),
    "50212": (PLAIN, "sungai/danau tramper (trayek tidak tetap); passenger entry"),
    "50213": (PLAIN, "sungai/danau untuk wisata, named verbatim in the annex"),
    "50221": (PLAIN, "sungai/danau barang umum, named verbatim"),
    "50222": (PLAIN, "sungai/danau barang khusus, named verbatim"),
    "50223": (PLAIN, "sungai/danau barang berbahaya, named verbatim"),
    "50125": (PLAIN, "angkutan laut luar negeri barang; both candidate ancestors (50141 liner/tramper, 50142 barang khusus) carry 49%"),
    "51101": (PLAIN, "angkutan udara niaga berjadwal, named verbatim"),
    "51102": (PLAIN, "angkutan udara niaga tidak berjadwal, named verbatim"),
    # --- 2025 code is BROADER than the restricted activity — NOT patched ---
    "10761": (BROADER, "'Pengolahan Kopi' as a whole; the annex restricts only coffee WITH a geographical indication"),
    "13133": (BROADER, "'Industri Kain Batik' as a whole; the annex restricts only 'batik cap' (stamped batik)"),
    "20232": (BROADER, "cosmetics generally; the annex restricts only 'kosmetik tradisional'"),
    "20235": (BROADER, "bespoke perfume is not traditional cosmetics; likely not restricted at all"),
    "26513": (BROADER, "electronic measuring and testing instruments; the annex restricts defence radar for weapons systems"),
    "30301": (BROADER, "manned aircraft generally; the annex restricts military aircraft"),
    "30302": (BROADER, "unmanned aircraft generally; the annex restricts military aircraft"),
    "30303": (BROADER, "spacecraft; the annex restricts military aircraft"),
    "90200": (BROADER, "performing arts generally; the annex restricts 'sanggar seni' (art studios)"),
    "58130": (BROADER, "journals and periodicals; the annex restricts newspapers, magazines and bulletins as PRESS, a narrower press-law category"),
    "60102": (BROADER, "digital radio broadcasting as an activity; the annex restricts 'Lembaga Penyiaran Swasta', an institutional status"),
    "60202": (BROADER, "television programming and broadcasting; the annex restricts 'Lembaga Penyiaran Berlangganan' (subscription)"),
    # --- plausibly a rename, but unproven — NOT patched -------------------
    "21021": (RENAMED, "'Obat Bahan Alam' is plausibly the current name for 'obat tradisional', but that equivalence needs a BPOM source, not an inference"),
    "21022": (RENAMED, "same as 21021 — needs the naming instrument before a client-facing flip"),
}

CONDITION_NOTE = {
    0: "Modal dalam negeri 100% — open to domestic capital only",
}


def patch_for(item: dict, cap: int, condition: str | None) -> dict:
    """Pure — the field-level patch for one record, given the lawful cap."""
    patch = {
        "pma_max_asing": cap,
        "pma_status": "TERBATAS",
        "pma_official_basis": item["locator"],
        "pma_cap_verified": True,
        "pma_source_vintage": VINTAGE,
    }
    note = condition or CONDITION_NOTE.get(cap)
    if note:
        patch["pma_kondisi"] = note
    return patch


def condition_for(code_2020: str) -> str | None:
    conds = {c for _, _, cap, c in caps_by_code(RELATION)[code_2020] if c}
    return sorted(conds)[0] if conds else None


def plan(records: list[dict]) -> tuple[list[dict], list[str]]:
    """Pure. Returns (planned patches, refusals). A refusal is a hard stop, not
    a warning: every one of them means the table and the evidence disagree."""
    result = classify_join(RELATION, records)
    divergent = {i["kbli_2025"]: i for i in result["disagree"]}
    ambiguous = {i["kbli_2025"] for i in result["ambiguous"]}
    # Every 2025 code the instrument reaches at all lands in exactly one bucket.
    judged = divergent.keys() | ambiguous | {i["kbli_2025"] for i in result["agree"]}
    present = {str(r.get("kode_kbli_2025")) for r in records}

    refusals = []
    for code in sorted(set(divergent) - set(ADJUDICATION)):
        refusals.append(f"{code}: divergent but never adjudicated — refusing to leave it undecided")
    # Scoped to codes actually IN this dataset: on a subset (a test fixture, a
    # single-code run) an absent code is unseen, not phantom — and a code that
    # already carries the lawful value is cured, not phantom either. Only a code
    # the instrument does not reach at all accuses the table.
    for code in sorted((set(ADJUDICATION) & present) - judged):
        refusals.append(f"{code}: adjudicated but the instrument does not restrict it — the table names a code the evidence does not")
    for code in sorted(ambiguous & {c for c, (v, _) in ADJUDICATION.items() if v == PLAIN}):
        refusals.append(f"{code}: the instrument gives it two caps; it can never be plain")

    planned = []
    for code, item in sorted(divergent.items()):
        verdict, reason = ADJUDICATION.get(code, (None, ""))
        if verdict != PLAIN:
            continue
        cap = item["law_caps"][0]
        planned.append({
            "kbli_2025": code,
            "was": {"pma_max_asing": item["catalogue_cap"], "pma_status": item["catalogue_status"]},
            "patch": patch_for(item, cap, condition_for(item["kbli_2020"])),
            "reason": reason,
        })
    return planned, refusals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the dataset (default: dry-run)")
    ap.add_argument("--dataset", default=str(CANONICAL))
    args = ap.parse_args(argv)

    path = Path(args.dataset)
    original_text = path.read_text(encoding="utf-8")
    payload = json.loads(original_text)
    records = payload["data"]

    planned, refusals = plan(records)
    counts = {v: sum(1 for x, _ in ADJUDICATION.values() if x == v) for v in (PLAIN, BROADER, RENAMED)}
    print(f"adjudicated: plain {counts[PLAIN]} | broader {counts[BROADER]} | renamed-unproven {counts[RENAMED]}")
    print(f"planned patches: {len(planned)}")
    for p in planned:
        print(f"  {p['kbli_2025']}: {p['was']['pma_max_asing']}% {p['was']['pma_status']}"
              f" -> {p['patch']['pma_max_asing']}% {p['patch']['pma_status']}   ({p['reason'][:58]})")
    for code, (verdict, reason) in sorted(ADJUDICATION.items()):
        if verdict != PLAIN:
            print(f"  NOT PATCHED {code} [{verdict}]: {reason[:88]}")

    if refusals:
        print("\nREFUSING TO APPLY:")
        for r in refusals:
            print(f"  {r}")
        return 2

    if not args.apply:
        print("\ndry-run — rerun with --apply to write")
        return 0

    by_code = {str(r.get("kode_kbli_2025")): r for r in records}
    touched = 0
    for p in planned:
        rec = by_code[p["kbli_2025"]]
        for key, value in p["patch"].items():
            # never silently overwrite an existing human-authored condition
            if key == "pma_kondisi" and (rec.get("pma_kondisi") or "").strip():
                print(f"  keeping existing pma_kondisi on {p['kbli_2025']}: {rec['pma_kondisi']!r}")
                continue
            rec[key] = value
        touched += 1
    # Match the file's OWN serialisation (indent=2, ensure_ascii=False, the
    # convention every existing canonical patcher uses) and preserve whether it
    # ended with a newline. Getting this wrong reformats all 540,083 lines, and
    # a 20-record change would arrive as an unreviewable whole-file diff.
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    path.write_text(body + ("\n" if original_text.endswith("\n") else ""), encoding="utf-8")
    print(f"\nAPPLIED: {touched} record(s) patched in {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
