#!/usr/bin/env python3
"""The operative foreign-ownership cap relation, and what the catalogue says instead.

WHAT THIS IS
------------
`Perpres 10/2021` is the Daftar Positif Investasi — the instrument every
`pma_status` / `pma_max_asing` value in this catalogue ultimately claims to come
from (`pma_source` reads "Perpres 10/2021, 49/2021" on all 1,559 records). Its
Lampiran III is the list of business fields carrying a foreign-ownership
condition. This module holds that list as DATA, with a per-entry locator, so the
PMA axis stops being the one axis with no checkable source (corner §5.0).

THE INSTRUMENT IS 49/2021, NOT 10/2021 — verified, not assumed. Perpres 49/2021
articles 3, 4 and 5 read `Lampiran I diubah` / `Lampiran II diubah` /
`Lampiran III diubah`: all three annexes of 10/2021 were REPLACED. So a locator
naming "Perpres 10/2021 Lampiran III" points at superseded text. Measured
consequence, 2026-08-01: canonical's `pma_official_basis` for `47221` cites
"Lampiran III ... entry #44"; the operative Lampiran III has **37** entries and
does not contain 47221 at all — 49/2021 moved it into the body (art. 3a,
"persyaratan Penanaman Modal lainnya"), a different legal category from a
percentage cap. Following that locator today leads nowhere.
Still in force as of 2026: no presidential regulation has replaced 10/2021+49/2021.

WHY THE ROWS ARE TRANSCRIBED FROM PAGE IMAGES
---------------------------------------------
The vaulted PDFs' text layer is OCR output and it corrupts exactly the two
columns that matter. Codes: `10761`->"to76r", `26513`->"265L3", `90011`->"9001 I".
Percentages: `49%`->"497o", `100%`->"lOOo/o". A parse of that layer produced 40
code tokens for a 41-pair table and could not read a single percentage. The four
pages were therefore rendered at 200dpi and read as images; the image is the
authority here and the text layer is the suspect. (The three Lampiran of
Perpres 10/2021 in the vault are worse still: zero real words and zero 5-digit
sequences extract from them, so any `grep <code>` against those files returns 0
for EVERY code — an extraction failure that reads exactly like an absence.)

THE UNIT IS THE (bidang usaha, KBLI) PAIR — NEVER THE CODE
-----------------------------------------------------------
Entry 7 gives `30111` a 49% foreign cap as a WARSHIP yard; entry 8 gives the SAME
code a 0% cap as a builder of pinisi/cadik/traditional wooden vessels. The body
says so explicitly (art. 3(3): where one KBLI spans several bidang usaha, the
Lampiran III requirement applies only to the bidang usaha named in the column).
A code -> cap join is therefore structurally wrong for such a code, and a single
`pma_max_asing` integer cannot represent it. Same for phase-dependent caps
(`58130`: 0% at establishment, 49% via the capital market for expansion) and for
conditional ones (defence: above 49% with the Defence Minister's approval; air
transport: 49% AND the national owner must retain single majority). Codes whose
pairs disagree are reported as `ambiguous`, never as a divergence to auto-patch.

REPORTER, NOT A GATE — DELIBERATELY, FOR NOW
---------------------------------------------
`--check` exits 0 while divergences exist, because on the day this landed there
were 35 of them: arming a gate on a 35-item backlog turns every unrelated PR red
and teaches people to bypass it (W95). `--strict` is the flip, and flipping it is
the closing act of the cure lane, not a rider on this diff.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
OUT_PATH = REPO_ROOT / "data" / "kbli-filiera" / "perpres-foreign-caps.json"

INSTRUMENT = "Perpres 49/2021 Lampiran III (Daftar Bidang Usaha dengan Persyaratan Tertentu)"
VINTAGE = "2021-05-25"

# (entry, bidang_usaha, kbli_2020, foreign_cap_pct, condition)
# Transcribed from the 4 rendered pages. `foreign_cap_pct` is the FOREIGN share:
# "Modal dalam negeri 100%" (100% domestic capital) is therefore 0, not 100 —
# the column in the document names the side that is NOT the foreign investor's.
RELATION: list[tuple[int, str, str, int, str | None]] = [
    (1, "Industri pengolahan kopi yang sudah mendapatkan indikasi geografis", "10761", 0, None),
    (2, "Industri batik cap", "13134", 0, None),
    (3, "Industri barang bangunan dari kayu", "16221", 0, None),
    (4, "Industri kosmetik tradisional", "20232", 0, None),
    (5, "Industri bahan baku obat tradisional untuk manusia", "21021", 0, None),
    (6, "Industri produk obat tradisional untuk manusia", "21022", 0, None),
    (7, "Industri senjata dan amunisi", "25200", 49, "may exceed 49% with Menteri Pertahanan approval"),
    (7, "Industri kendaraan perang", "30400", 49, "may exceed 49% with Menteri Pertahanan approval"),
    (7, "Industri radar pertahanan untuk sistem persenjataan", "26513", 49, "may exceed 49% with Menteri Pertahanan approval"),
    (7, "Industri kapal perang", "30111", 49, "may exceed 49% with Menteri Pertahanan approval"),
    (7, "Industri pesawat terbang militer", "30300", 49, "may exceed 49% with Menteri Pertahanan approval"),
    (8, "Industri kapal: Pinisi, Cadik, kapal dari kayu lainnya dengan desain khas tradisional", "30111", 0, None),
    (9, "Angkutan laut dalam negeri liner dan tramper untuk penumpang", "50111", 49, None),
    (10, "Angkutan laut dalam negeri untuk wisata", "50113", 49, None),
    (11, "Angkutan laut dalam negeri perintis untuk penumpang", "50114", 49, None),
    (12, "Angkutan laut dalam negeri liner dan tramper untuk barang", "50131", 49, None),
    (13, "Angkutan laut dalam negeri untuk barang khusus", "50133", 49, None),
    (14, "Angkutan laut dalam negeri perintis untuk barang", "50134", 49, None),
    (15, "Angkutan laut dalam negeri pelayaran rakyat", "50135", 49, None),
    (16, "Angkutan laut luar negeri liner dan tramper untuk barang", "50141", 49, None),
    (17, "Angkutan laut luar negeri untuk barang khusus", "50142", 49, None),
    (18, "Angkutan penyeberangan umum antar provinsi", "50214", 49, None),
    (19, "Angkutan penyeberangan perintis antar provinsi", "50215", 49, None),
    (20, "Angkutan penyeberangan umum antar kabupaten/kota", "50216", 49, None),
    (21, "Angkutan penyeberangan perintis antar kabupaten/kota", "50217", 49, None),
    (22, "Angkutan penyeberangan umum dalam kabupaten/kota", "50218", 49, None),
    (23, "Angkutan sungai dan danau untuk penumpang dengan trayek tetap dan teratur", "50211", 49, None),
    (24, "Angkutan sungai dan danau untuk penumpang dengan trayek tidak tetap dan tidak teratur", "50212", 49, None),
    (25, "Angkutan sungai dan danau dengan trayek tidak tetap dan tidak teratur untuk wisata", "50213", 49, None),
    (26, "Angkutan sungai dan danau untuk barang umum dan/atau hewan", "50221", 49, None),
    (27, "Angkutan sungai dan danau untuk barang khusus", "50222", 49, None),
    (28, "Angkutan sungai dan danau untuk barang berbahaya", "50223", 49, None),
    (29, "Angkutan moda udara niaga berjadwal", "51101", 49, "national capital owner must retain single majority"),
    (30, "Angkutan udara niaga tidak berjadwal dalam negeri", "51102", 49, "national capital owner must retain single majority"),
    (31, "Kegiatan angkutan udara", "51109", 49, "national capital owner must retain single majority"),
    (32, "Aktivitas kurir", "53201", 49, None),
    (33, "Penerbitan surat kabar, majalah, dan buletin (pers)", "58130", 0, "0% at establishment; 49% via capital market for expansion"),
    (34, "Lembaga Penyiaran Swasta (LPS)", "60102", 0, "0% at establishment; 20% for expansion"),
    (35, "Lembaga Penyiaran Berlangganan (LPB)", "60202", 0, "0% at establishment; 20% for expansion"),
    (36, "Aktivitas biro perjalanan ibadah umroh dan haji khusus", "79122", 0, "domestic capital and Islamic faith requirement"),
    (37, "Sanggar seni", "90011", 0, None),
]


def relation_rows() -> list[dict]:
    return [
        {
            "entry": entry,
            "bidang_usaha": bidang,
            "kbli_2020": code,
            "foreign_cap_pct": cap,
            "condition": cond,
            "locator": f"{INSTRUMENT} entry #{entry}",
            "vintage": VINTAGE,
        }
        for entry, bidang, code, cap, cond in RELATION
    ]


def caps_by_code(relation: list[tuple]) -> dict[str, list[tuple]]:
    out: dict[str, list[tuple]] = defaultdict(list)
    for entry, bidang, code, cap, cond in relation:
        out[code].append((entry, bidang, cap, cond))
    return dict(out)


def ancestors_of(record: dict) -> list[str]:
    """The KBLI-2020 codes this 2025 record descends from. Reading `codes` OR
    `ancestors` because both shapes exist in the wild; a shape we do not
    recognise yields an empty list, which lands the code in `no_descendant`
    rather than inventing a lineage."""
    anc = record.get("bps_2020_ancestors")
    out: list[str] = []
    if isinstance(anc, dict):
        for c in anc.get("codes") or anc.get("ancestors") or []:
            if isinstance(c, str):
                out.append(c)
            elif isinstance(c, dict):
                v = c.get("code") or c.get("kode")
                if v:
                    out.append(str(v))
    return out


def classify_join(relation: list[tuple], records: list[dict]) -> dict:
    """Pure. Three buckets per the corner's F2 step 3, plus the one the law
    itself creates: a 2020 code whose pairs carry DIFFERENT caps is `ambiguous`
    by the instrument, not by our uncertainty, and must never be auto-patched."""
    by_code = caps_by_code(relation)
    reverse: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        for a in ancestors_of(rec):
            reverse[a].append(rec)

    agree, disagree, ambiguous, no_descendant = [], [], [], []
    for code, rows in sorted(by_code.items()):
        descendants = reverse.get(code, [])
        if not descendants:
            no_descendant.append({"kbli_2020": code, "law_caps": sorted({r[2] for r in rows})})
            continue
        caps = {r[2] for r in rows}
        for rec in descendants:
            item = {
                "kbli_2020": code,
                "kbli_2025": str(rec.get("kode_kbli_2025")),
                "judul_2025": rec.get("judul"),
                "catalogue_cap": rec.get("pma_max_asing"),
                "catalogue_status": rec.get("pma_status"),
                "law_caps": sorted(caps),
                "locator": f"{INSTRUMENT} entry #{rows[0][0]}",
            }
            if len(caps) > 1:
                ambiguous.append(item)
            elif rec.get("pma_max_asing") == next(iter(caps)):
                agree.append(item)
            else:
                disagree.append(item)
    return {
        "agree": agree,
        "disagree": disagree,
        "ambiguous": ambiguous,
        "no_descendant": no_descendant,
    }


def load_canonical(path: Path) -> list[dict]:
    return json.loads(path.read_text())["data"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report only; do not write the artifact")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when a divergence exists (arm this once the cure lane has landed)")
    ap.add_argument("--dataset", default=str(CANONICAL))
    args = ap.parse_args(argv)

    rows = relation_rows()
    codes = {r["kbli_2020"] for r in rows}
    conflicting = {c for c, v in caps_by_code(RELATION).items() if len({x[2] for x in v}) > 1}
    print(f"relation: {len(rows)} (bidang usaha, KBLI) pairs | {len(codes)} distinct KBLI-2020 codes")
    print(f"codes carrying CONFLICTING caps across bidang usaha: {sorted(conflicting) or 'none'}")
    print(f"instrument: {INSTRUMENT} (vintage {VINTAGE})")

    result = classify_join(RELATION, load_canonical(Path(args.dataset)))
    print(f"\njoin onto KBLI-2025 through the BPS crosswalk — "
          f"agree {len(result['agree'])} | DISAGREE {len(result['disagree'])} | "
          f"ambiguous-by-law {len(result['ambiguous'])} | no 2025 descendant {len(result['no_descendant'])}")
    for item in result["disagree"]:
        print(f"  {item['kbli_2020']} -> {item['kbli_2025']}: catalogue "
              f"{item['catalogue_cap']!r} ({item['catalogue_status']}) vs law {item['law_caps']}%"
              f"  «{(item['judul_2025'] or '')[:44]}»")
    for item in result["ambiguous"]:
        print(f"  AMBIGUOUS {item['kbli_2020']} -> {item['kbli_2025']}: law says {item['law_caps']} "
              f"depending on bidang usaha — a single integer cannot say this")
    for item in result["no_descendant"]:
        print(f"  NO DESCENDANT {item['kbli_2020']}: restricted at {item['law_caps']}% but no 2025 "
              f"code in our ancestry inherits from it")

    if not args.check:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(
            {"instrument": INSTRUMENT, "vintage": VINTAGE,
             "transcribed_from": "page images rendered at 200dpi; the PDF text layer corrupts codes and percentages",
             "unit": "(bidang usaha, KBLI-2020) pair — the cap does not attach to the code alone",
             "rows": rows}, indent=1, ensure_ascii=False) + "\n")
        print(f"\nwrote {OUT_PATH.relative_to(REPO_ROOT)}")

    if args.strict and result["disagree"]:
        print(f"\nSTRICT: {len(result['disagree'])} divergence(s) between the catalogue and the operative instrument")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
