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
import hashlib
import json
import subprocess
import sys
from datetime import date
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
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_kbli_dataset.sh"
SIDECAR_DATASET_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json"
SIDECAR_PATH = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json"

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
    "51103": (BROADER, "transportasi antariksa (space) for passengers; entry 31 restricts "
                       "'Kegiatan angkutan udara' — air transport. Its siblings 51101/51102 are the "
                       "air entries and ARE patched at 49%; space transport is not air transport. "
                       "Same shape as 30303 (spacecraft vs military aircraft). The 51109 edge is the "
                       "2020 residual air bucket that carried space transport before KBLI 2025 gave "
                       "it its own code"),
    "90200": (BROADER, "performing arts generally; the annex restricts 'sanggar seni' (art studios)"),
    "58130": (BROADER, "journals and periodicals; the annex restricts newspapers, magazines and bulletins as PRESS, a narrower press-law category"),
    "60102": (BROADER, "digital radio broadcasting as an activity; the annex restricts 'Lembaga Penyiaran Swasta', an institutional status"),
    "60103": (BROADER, "on-demand audio distribution and streaming; entry 34 restricts 'Lembaga "
                       "Penyiaran Swasta', an institutional status under the broadcasting law — "
                       "already this table's stated basis for refusing 60102, which IS radio "
                       "broadcasting. Streaming on demand is not penyiaran. Independently: its two "
                       "candidate ancestors do NOT carry the same cap (60101 has no annex row at "
                       "all, 60102 has 0%), so a mis-assigned ancestor would change the value "
                       "written — the same test that licenses the PLAIN verdicts on 50125 and the "
                       "ferry family forbids it here"),
    "60202": (BROADER, "television programming and broadcasting; the annex restricts 'Lembaga Penyiaran Berlangganan' (subscription)"),
    "60203": (BROADER, "on-demand video distribution and streaming; entry 35 restricts 'Lembaga "
                       "Penyiaran Berlangganan' (subscription), an institutional status — already "
                       "this table's stated basis for refusing 60202. Independently: candidate "
                       "ancestors 60201 (no annex row) and 60202 (0%) disagree, so the value written "
                       "would depend on which ancestor is picked"),
    # --- RENAMED -> PLAIN, adjudicated 2026-08-07 on primary-source research
    # (four legs, cited verbatim in NOTA_OVERRIDE below): UU 17/2023 Pasal 1
    # substitutes "Obat Bahan Alam" into the exact definitional slot "obat
    # tradisional" held under UU 36/2009; Peraturan BPOM 25/2023 replaces the
    # 2005 obat-tradisional registration rule while keeping the jamu/OHT/
    # fitofarmaka substructure; SEB 4.S/2026 (BKPM+Kemenkumham+BPS) rules
    # title-only KBLI conversions carry no new legal consequence; and OSS RBA
    # still serves 21021 under the OLD title "Industri Bahan Baku Obat
    # Tradisional untuk Manusia" (the operative system never re-opened the
    # code). Perpres 49/2021 Lampiran III entries 5-6 name both codes BY
    # NUMBER AND TITLE at 100% modal dalam negeri — no longer BROADER-than or
    # a bare inference, a plain (bidang usaha, KBLI) identity match.
    "21021": (PLAIN, "UU 17/2023 Pasal 1 + Peraturan BPOM 25/2023 + SEB 4.S/2026 + "
                     "OSS RBA still serving the pre-rename title together establish "
                     "'Obat Bahan Alam' as the 2025 name for 'obat tradisional', not a "
                     "new activity — see NOTA_OVERRIDE for the presumption stated to readers"),
    "21022": (PLAIN, "same four-leg basis as 21021 — see NOTA_OVERRIDE"),
}

CONDITION_NOTE = {
    0: "Modal dalam negeri 100% — open to domestic capital only",
}

# Per-code override of the generated `pma_nota` — the free-text rationale field
# read by clients, distinct from `pma_kondisi` (which states the LEGAL EFFECT
# of the cap, e.g. "domestic capital only"). `patch_for()` writes the generic
# `pma_kondisi` from `CONDITION_NOTE`/`condition_for()` on every PLAIN code as
# usual; this dict additionally overwrites `pma_nota` on the two codes below
# with the exact rename-presumption sentence the adjudication requires — a
# reader of `/kbli/21021` needs to know WHY a 2025-titled, seemingly-new code
# inherits a 2020-titled Perpres restriction, and the generic kondisi text
# does not say that. Deliberately NOT gated behind "never overwrite existing
# human text" (unlike `pma_kondisi` in the write loop below): this dict IS the
# human adjudication, replacing 21021's pre-existing unrelated `pma_nota`
# ("Sektor prioritas: Industri produk farmasi") on purpose.
NOTA_OVERRIDE: dict[str, str] = {
    "21021": (
        "Perpres restriction presumed to continue under the 2025 title "
        "(rename, not new activity — UU 17/2023; no contrary OSS/BKPM "
        "guidance found)"
    ),
    "21022": (
        "Perpres restriction presumed to continue under the 2025 title "
        "(rename, not new activity — UU 17/2023; no contrary OSS/BKPM "
        "guidance found)"
    ),
}

# The 2 AMBIGUOUS-by-law codes (perpres_foreign_cap_relation.py's own bucket —
# never `disagree`, so `plan()` below never plans a patch for them; canonical
# stays TERBUKA/100 for both, correctly, because neither restriction covers
# the WHOLE code). Merged into ADJUDICATION (not a separate dict) so
# `--strict` on the sibling module — which checks membership in THIS dict for
# every DISAGREE **and AMBIGUOUS** row — recognises them as adjudicated rather
# than silently waived: 30111 covers both a warship slice (Lampiran III entry
# 7, 49%, Menteri Pertahanan condition) and a traditional-wooden-vessel slice
# (entry 8, Pinisi/Cadik, 0%); 30113 (unmanned vessels) reaches only the
# defence slice (entry 7's "operasi militer" reading) — a traditional wooden
# Pinisi is not an unmanned vehicle, so it does NOT inherit entry 8. Both
# slices are disclosed per-row by `perpres_slice_disclosure_relation.py`,
# which hand-authors its own rows for these two codes (see MANUAL_SLICE_ROWS
# there) — never derived from this dict, because the general one-ancestor ->
# one-annex-row derivation runs only on the other 10 BROADER codes
# (17 total minus the 2 MANUAL_SLICE_ROWS codes minus the 5 ADJACENT_NOT_CONTAINED
# exclusions) and therefore does not
# distinguish 30111's two rows from 30113's one. `plan()` below is unaffected:
# its `divergent` set comes only from `result["disagree"]`, and 30111/30113
# live in `result["ambiguous"]`, so adding them here plans no patch — verified
# by `test_perpres_foreign_cap_relation.py`'s
# `test_innocence_ambiguous_codes_in_adjudication_plan_no_patch`.
ADJUDICATION["30111"] = (
    BROADER,
    "covers BOTH a warship slice (Lampiran III entry 7, 49%, Menteri "
    "Pertahanan condition) and a traditional wooden-vessel slice (entry 8, "
    "Pinisi/Cadik, 0%) — neither restriction covers manned-vessel "
    "manufacturing as a whole, so the code stays TERBUKA/100; both slices "
    "are disclosed per-row in kbli-perpres-slice-disclosures.json",
)
ADJUDICATION["30113"] = (
    BROADER,
    "reaches only the defence slice (entry 7, 49%, Menteri Pertahanan "
    "condition, read as 'operasi militer') — no Pinisi/Cadik row: a "
    "traditional wooden vessel is not an unmanned vehicle, so entry 8 does "
    "not apply; the code stays TERBUKA/100, one slice disclosed",
)


def patch_for(item: dict, cap: int, condition: str | None, code_2025: str | None = None) -> dict:
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
    nota = NOTA_OVERRIDE.get(code_2025 or "")
    if nota:
        patch["pma_nota"] = nota
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
            "patch": patch_for(item, cap, condition_for(item["kbli_2020"]), code_2025=code),
            "reason": reason,
        })
    return planned, refusals


def run_sync() -> None:
    """Fan the canonical out to its four published copies.

    Skipping this is not cosmetic: `check-kbli-dataset-sync` fails the PR, and
    `apps/mouth` serves its OWN physical copy, so an un-synced cure changes
    nothing on the pages it was written for.
    """
    result = subprocess.run(["bash", str(SYNC_SCRIPT), "sync"], cwd=REPO_ROOT,
                            capture_output=True, text=True, check=False)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"sync_kbli_dataset.sh failed with exit {result.returncode}")


def update_sidecar() -> None:
    """Bump the SEO/derived-pin sidecar the required frontend suite guards.

    Every filiera compiler carries this; this one did not, and all three
    dataset-derived gates went red on its first PR — the sidecar hash, the copy
    sync, and the batch membership pin. A compiler that writes the canonical and
    leaves its derivatives stale is a half-cure that fails somebody else's check.
    """
    if not SIDECAR_DATASET_PATH.exists():
        raise SystemExit(f"sidecar dataset copy missing: {SIDECAR_DATASET_PATH} (sync must run first)")
    digest = hashlib.sha256(SIDECAR_DATASET_PATH.read_bytes()).hexdigest()
    sidecar = json.loads(SIDECAR_PATH.read_text(encoding="utf-8"))
    before = sidecar.get("datasetSha256")
    sidecar["datasetSha256"] = f"sha256:{digest}"
    sidecar["lastModified"] = date.today().isoformat()
    SIDECAR_PATH.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"sidecar: {before} -> {sidecar['datasetSha256']}")


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

    # Only for the real canonical. A test fixture in tmp_path must never reach
    # out and rewrite the repo's copies or the sidecar (W96: tests that write
    # production state), so the derivatives are keyed on identity, not on the
    # fact that --apply was passed.
    if path.resolve() == CANONICAL.resolve():
        run_sync()
        update_sidecar()
    else:
        print(f"(not the canonical: skipping copy sync + sidecar for {path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
