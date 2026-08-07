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
says so explicitly — **Pasal 6 ayat (3)**, the article that governs Lampiran III:
where one KBLI covers more than one bidang usaha, the Lampiran III requirement
applies only to the bidang usaha named in that column. (Read at the source
2026-08-06. This cited `art. 3(3)` until then, which does not exist: Pasal 3 has
two ayat. The granularity rule is written once PER ANNEX — 5(5) for Lampiran II,
6(3) for Lampiran III — so one remembered number cannot serve both, which is how
the phantom propagated to five places.)
A code -> cap join is therefore structurally wrong for such a code, and a single
`pma_max_asing` integer cannot represent it. Same for phase-dependent caps
(`58130`: 0% at establishment, 49% via the capital market for expansion) and for
conditional ones (defence: above 49% with the Defence Minister's approval; air
transport: 49% AND the national owner must retain single majority). Codes whose
pairs disagree are reported as `ambiguous`, never as a divergence to auto-patch.

REPORTER, NOT A GATE — UNTIL NOW
----------------------------------
`--check` exits 0 while divergences exist, because on the day this landed there
were 35 of them: arming a gate on a 35-item backlog turns every unrelated PR red
and teaches people to bypass it (W95). `--strict` is the flip, armed 2026-08-07
once the backlog closed: every DISAGREE row is BROADER-or-PLAIN-adjudicated (see
`apply_perpres_foreign_caps.ADJUDICATION`, imported at call time — a local
import, not a module-level one, because that module imports THIS one; see
`_adjudication()`), every AMBIGUOUS row (30111, 30113) is adjudicated too, and
NO_DESCENDANT is empty (50113's own case — see the crosswalk fallback below).
`--strict` checks every bucket the join produces, not just DISAGREE, because a
code the instrument restricts and we simply never located is as unadjudicated
as one we found and shrugged at.

THE 50113 FIX — A JOIN THAT COULD NOT SEE ITS OWN ANSWER
-----------------------------------------------------------
`50113` (Angkutan Laut Dalam Negeri untuk Wisata) used to report NO_DESCENDANT:
canonical's OWN `50113` record carries `bps_2020_ancestors: None`, because it is
a Batch-A code — its ancestry is DELIBERATELY excluded from canonical (the
Batch-A exclusion is a design choice recorded in the corner, not a gap to fill
by writing into canonical). `ancestors_of()` returned `[]` for it, so
`reverse['50113']` never got populated and the join reported "no 2025 code in
our ancestry inherits from it" — even though canonical's 50113 record ALREADY
carries the lawful value (`pma_status=TERBATAS`, `pma_max_asing=49`, with a
verified official basis, cured in an earlier lot). The join was blind to its own
agreement, not disagreeing with it.

The fix is an in-memory-only fallback, never a canonical write: when a record's
own `bps_2020_ancestors` is `None`, `ancestors_of()` falls back to
`data/kbli-filiera/phase0/bps_crosswalk.json`'s `relation[code]` — the SAME
Phase-0 gate-verified crosswalk Batch B already trusts for ancestry, just not
yet copied into canonical for Batch-A codes. With the fallback, 50113 resolves
via its own self-mapped entry (`relation['50113']['codes'] == ['50113']`) and
the join reports it correctly as `agree` (49 == 49) — the row was never a slice
case, it just could not see far enough to say so.

GATED to `pma_cap_verified is True` — trust the fallback to CONFIRM, not to
CREATE. Ungated, the identical mechanism also resolves ancestors for `51103`,
`60103` and `60203` — all three quarantined (`per_skala_disputed_pp28_collision`)
with an UNVERIFIED PMA layer, and `51103` is one of the corner's own documented
false-friends. Manufacturing three new unadjudicated restriction claims as a
side effect of un-hiding one already-settled agreement is exactly the harm this
module exists to prevent — see `ancestors_of()`'s docstring for the measurement.
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
PHASE0_CROSSWALK = REPO_ROOT / "data" / "kbli-filiera" / "phase0" / "bps_crosswalk.json"

INSTRUMENT = "Perpres 49/2021 Lampiran III (Daftar Bidang Usaha dengan Persyaratan Tertentu)"
VINTAGE = "2021-05-25"

# The artifact these 41 rows were read from. Until 2026-08-02 it was in NO vault
# — 22 PDFs held, none naming either Perpres — so `transcribed_from` below named
# a rendering of a file nobody could reach, and the docstring's promise that this
# module gives the PMA axis "a checkable source" could not be honoured by anyone
# who tried. `vault_fetch_perpres.py` pins it; naming the id here is what turns
# the promise into something a reader can act on.
VAULT_ID = 161565
VAULT_REL = "perpres/161565__Perpres Nomor 49 Tahun 2021 - Lampiran III.pdf"

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


def load_phase0_crosswalk(path: Path = PHASE0_CROSSWALK) -> dict[str, list[str]]:
    """2025 code -> KBLI-2020 ancestor codes, from the Phase-0 gate-verified
    crosswalk. Batch-A codes carry NO `bps_2020_ancestors` in canonical (the
    exclusion is deliberate — see corner §LIVE STATE), but their mechanical
    ancestry is already recorded here. Used ONLY as an in-memory fallback in
    `ancestors_of()`; never written back to canonical. A missing/unreadable
    file degrades to an empty fallback (the caller still returns `[]` for a
    Batch-A code, same as before this fix existed) rather than raising —
    this module's own `no_descendant` bucket already reports that outcome
    loudly, so a silent empty dict does not manufacture a false agreement."""
    if not path.is_file():
        return {}
    try:
        relation = json.loads(path.read_text()).get("relation") or {}
    except (json.JSONDecodeError, OSError):
        return {}
    out: dict[str, list[str]] = {}
    for code, entry in relation.items():
        if not isinstance(entry, dict):
            continue
        codes = entry.get("codes") or []
        if codes:
            out[str(code)] = [str(c) for c in codes]
    return out


def ancestors_of(record: dict, phase0_fallback: dict[str, list[str]] | None = None) -> list[str]:
    """The KBLI-2020 codes this 2025 record descends from. Reading `codes` OR
    `ancestors` because both shapes exist in the wild; a shape we do not
    recognise yields an empty list, which lands the code in `no_descendant`
    rather than inventing a lineage.

    `phase0_fallback` is consulted ONLY when canonical's own
    `bps_2020_ancestors` is absent (`None`/missing) — a Batch-A code, by
    design (see `load_phase0_crosswalk`). A record that DOES carry
    `bps_2020_ancestors` (even an empty dict) never reaches the fallback:
    canonical's own field is authoritative whenever it exists at all.

    SECOND GATE, measured before it was written: the fallback is trusted only
    to CONFIRM a fact this record's OWN `pma_status`/`pma_max_asing` has
    already been independently adjudicated to hold (`pma_cap_verified is
    True`) — never to manufacture a brand-new restriction claim on a record
    whose PMA layer is still the generic blanket default. Measured across the
    whole 1,559-record catalogue: exactly ONE Batch-A-no-ancestor record
    carries `pma_cap_verified is True` — `50113`, this fix's own motivating
    case. Without the gate, the SAME fallback also resolves ancestors for
    `51103`, `60103` and `60203` — all three already carry a
    `per_skala_disputed_pp28_collision` marker (quarantined, licensing
    disputed) with `pma_cap_verified` still unset, and `51103` is one of the
    corner's own documented false-friends (`pp28_sources` cites a wrong
    neighbour code's data). Trusting an unverified Phase-0 mechanical match on
    an already-quarantined code would manufacture three new, unadjudicated
    PMA-restriction claims as a side effect of a fix meant to un-hide one
    already-settled agreement — exactly the class of harm this module exists
    to prevent. Those three stay `no_descendant`-shaped (absent from the
    reverse map) until someone adjudicates them on their own evidence."""
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
    if phase0_fallback and record.get("pma_cap_verified") is True:
        code = str(record.get("kode_kbli_2025") or "")
        out.extend(phase0_fallback.get(code, []))
    return out


def classify_join(
    relation: list[tuple],
    records: list[dict],
    phase0_fallback: dict[str, list[str]] | None = None,
) -> dict:
    """Pure. Three buckets per the corner's F2 step 3, plus the one the law
    itself creates: a 2020 code whose pairs carry DIFFERENT caps is `ambiguous`
    by the instrument, not by our uncertainty, and must never be auto-patched."""
    by_code = caps_by_code(relation)
    reverse: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        for a in ancestors_of(rec, phase0_fallback):
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


def _adjudication() -> dict[str, tuple[str, str]]:
    """`apply_perpres_foreign_caps.ADJUDICATION`, loaded lazily.

    A LOCAL (function-scope) import, not a module-level one: that sibling
    module already does `from perpres_foreign_cap_relation import (...)` at
    ITS top level, so a module-level import here would be circular. Deferring
    to call time means this module's own top-level definitions (RELATION,
    classify_join, ...) are already fully built by the time
    `apply_perpres_foreign_caps` re-imports them — the same sys.path-sibling
    pattern every compiler in this directory already uses."""
    _dir = str(Path(__file__).resolve().parent)
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    from apply_perpres_foreign_caps import ADJUDICATION

    return ADJUDICATION


def strict_violations(result: dict) -> list[str]:
    """Every row `--strict` refuses to pass in silence, named.

    A DISAGREE or AMBIGUOUS row is tolerated only if its 2025 code is present
    in `apply_perpres_foreign_caps.ADJUDICATION` — ANY verdict (PLAIN/BROADER/
    RENAMED) counts, because presence in that dict IS the adjudication record;
    a blanket "trust every ambiguous row" waiver would defeat the point (no
    silent tolerance — every exception is a named, git-blamable line in that
    dict). NO_DESCENDANT rows have no 2025 code to look up at all — the
    instrument restricts a KBLI-2020 activity and we found no home for it in
    2025, which is unadjudicated by definition, not tolerable by any waiver.
    """
    adjudication = _adjudication()
    violations: list[str] = []
    for item in result["disagree"]:
        code = item["kbli_2025"]
        if code not in adjudication:
            violations.append(f"{code}: DISAGREE, never adjudicated")
    for item in result["ambiguous"]:
        code = item["kbli_2025"]
        if code not in adjudication:
            violations.append(f"{code}: AMBIGUOUS, never adjudicated")
    for item in result["no_descendant"]:
        violations.append(f"{item['kbli_2020']}: NO DESCENDANT — restricted by the "
                           "instrument, no 2025 code inherits from it")
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report only; do not write the artifact")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 unless every DISAGREE/AMBIGUOUS row is adjudicated "
                         "(apply_perpres_foreign_caps.ADJUDICATION) and NO_DESCENDANT is empty")
    ap.add_argument("--dataset", default=str(CANONICAL))
    args = ap.parse_args(argv)

    rows = relation_rows()
    codes = {r["kbli_2020"] for r in rows}
    conflicting = {c for c, v in caps_by_code(RELATION).items() if len({x[2] for x in v}) > 1}
    print(f"relation: {len(rows)} (bidang usaha, KBLI) pairs | {len(codes)} distinct KBLI-2020 codes")
    print(f"codes carrying CONFLICTING caps across bidang usaha: {sorted(conflicting) or 'none'}")
    print(f"instrument: {INSTRUMENT} (vintage {VINTAGE})")

    phase0_fallback = load_phase0_crosswalk()
    result = classify_join(RELATION, load_canonical(Path(args.dataset)), phase0_fallback)
    print(f"\njoin onto KBLI-2025 through the BPS crosswalk (+ Phase-0 fallback for "
          f"Batch-A codes: {len(phase0_fallback)} codes available) — "
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
             "source": {"vault_id": VAULT_ID, "vault_rel_path": VAULT_REL,
                        "fetcher": "scripts/kbli_filiera/vault_fetch_perpres.py"},
             "unit": "(bidang usaha, KBLI-2020) pair — the cap does not attach to the code alone",
             "rows": rows}, indent=1, ensure_ascii=False) + "\n")
        print(f"\nwrote {OUT_PATH.relative_to(REPO_ROOT)}")

    if args.strict:
        violations = strict_violations(result)
        if violations:
            print(f"\nSTRICT: {len(violations)} unadjudicated row(s):")
            for v in violations:
                print(f"  {v}")
            return 1
        print("\nSTRICT: every DISAGREE/AMBIGUOUS row is adjudicated, NO_DESCENDANT is empty — PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
