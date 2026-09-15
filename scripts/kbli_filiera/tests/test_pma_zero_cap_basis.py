"""No whole-code 0% foreign-ownership verdict may rest on a missing Usaha Besar scale.

THE CLAIM THIS GATE KILLS. PR #6488 (`cure_pma_closed_no_besar_scale.py`, spec
`pma_closed_no_besar_scale_2026_09_14.json`, never merged — see
DOSSIER-no-besar-normativo-2026-09-15.md) reasoned: OSS publishes no Usaha Besar scale row
for a KBLI 2025 code, therefore a PT PMA (Usaha Besar by Perpres 10/2021 Pasal 7(1) / BKPM
5/2025 Pasal 26(1)) cannot operate it, therefore foreign ownership is 0%. The dossier's
refuter found the opposite: BKPM 5/2025 Pasal 8(6) keeps a scale-absent activity
exercisable "sepanjang tidak dibatasi" by the Perpres bidang-usaha rules; closures/caps
live only in the Perpres 10/2021 (as amended by 49/2021) annexes (Lampiran II
`dialokasikan`, Lampiran III, the Pasal 2 closed list) or a Pasal 5(5) partial reservation
— never in the absence of a scale row. The same inference was withdrawn once already, on
2026-08-03 (PR #3551/#3579), for the l4_bali layer; this gate stops it re-entering through
the NATIONAL pma_* tuple #6488 targeted instead.

SCOPE, STATED. This gate reads a record's NATIONAL PMA-verdict fields — `pma_kondisi`,
`pma_nota`, `pma_source`, `pma_official_basis` — never `l4_bali`. Deliberate, and measured:
the four certified Lampiran II codes (95291, 96100, 96210, 96220) carry a *legacy*
`l4_bali.rule` reading literally "per-scala-Besar (OSS risk at scale Besar; PMA is Besar by
law)" — a stale internal label the client-facing `l4_bali.reason` (guarded by
`test_withdrawn_umkm_inference_absent.py`) already overrides. Reading `l4_bali` here would
convict the codes this gate exists to protect (filed as a finding in the PR-1 report; out
of lane to fix here).

ENTITY, NOT SPELLING (superscar #3). The predicate requires BOTH an annex/closed-list
locator AND the absence of scale-absence language — never either alone.
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
CANONICAL = REPO / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
CURE_SPECS_DIR = REPO / "scripts/kbli_filiera/cure_specs"

# The locator this gate accepts. Measured against the 19 TERBATAS/located records on
# origin/main: every one names Lampiran II ("... DIALOKASIKAN untuk Koperasi dan UMKM
# ...") or Lampiran III ("Lampiran III (Daftar Bidang Usaha dengan Persyaratan
# Tertentu) entry #N") in `pma_official_basis` and/or `pma_kondisi`.
ANNEX_LOCATOR = re.compile(r"lampiran\s*ii\b|lampiran\s*iii\b|dialokasikan", re.IGNORECASE)

# The argument this gate refuses, taken verbatim from the #6488 fields actually written
# to `73300`/`38110`/`43110` on branch `5535726236` (pma_kondisi/pma_nota/pma_official_basis).
# Deliberately does NOT include a bare "per_skala" trigger: measured against the 52 files
# in cure_specs/, that field name is also used to describe/discuss OSS scale rows in
# passing (`l4_withdrawn_umkm_prose.json`, `editorial_body_national_scope.json`,
# `gold_86101_government_hospital_2026_08_07.json`) with no scale-absence verdict nearby
# — a bare match there is family #3 over-match, not guilt.
SCALE_ABSENCE_BASIS = re.compile(
    r"PMA_CLOSED_NO_BESAR_SCALE"
    r"|no\s+Usaha\s+Besar\s+scale"
    r"|(?:tidak\s+ada|tanpa)\s+skala(?:\s+Usaha)?\s+Besar"
    r"|no-Besar"
    r"|PMA\s+is\s+Besar\s+by\s+law",
    re.IGNORECASE,
)


def _basis_text(rec: dict[str, Any]) -> str:
    return " || ".join(
        str(rec.get(k) or "") for k in ("pma_kondisi", "pma_nota", "pma_source", "pma_official_basis")
    )


def judge(rec: dict[str, Any]) -> tuple[bool, str]:
    """True (innocent) iff not a 0% verdict, or a 0% verdict whose basis names an annex/
    closed-list locator and does not argue from scale absence. False (guilty) otherwise."""
    if rec.get("pma_max_asing") != 0:
        return True, "not a 0% verdict"
    text = _basis_text(rec)
    if SCALE_ABSENCE_BASIS.search(text):
        return False, f"basis argues from scale absence: {text[:200]!r}"
    if ANNEX_LOCATOR.search(text):
        return True, "annex locator present"
    # Pasal 2 closed-list basis, as the corpus already expresses it: the 60 TERTUTUP
    # records on origin/main carry no per-code Lampiran citation (they are the absolute
    # closures — narcotics cultivation, gambling, government monopolies, ...) and instead
    # cite the base instrument bare. Bypass requires status TERTUTUP AND no
    # `pma_official_basis` (a populated one means a MORE specific claim is being made and
    # must clear the locator check on its own merits).
    if (
        rec.get("pma_status") == "TERTUTUP"
        and not rec.get("pma_official_basis")
        and re.search(r"perpres\s*10/2021", rec.get("pma_source") or "", re.IGNORECASE)
    ):
        return True, "TERTUTUP bare Perpres 10/2021 citation (Pasal 2 closed-list, corpus convention)"
    return False, f"no annex/closed-list locator named: {text[:200]!r}"


def _canonical_rows() -> list[dict]:
    return json.loads(CANONICAL.read_text(encoding="utf-8"))["data"]


def test_the_store_this_gate_reads_is_actually_there():
    assert CANONICAL.is_file(), f"canonical missing at {CANONICAL}"
    assert len(_canonical_rows()) == 1559


def test_every_zero_percent_verdict_on_main_passes_today():
    """MEASURED: 79 records carry `pma_max_asing == 0` on origin/main (60 TERTUTUP/
    declared_gap, 19 TERBATAS/located). Not pinned as an exact count — sibling PRs in this
    mission add Lampiran II allocations — only that the sweep actually read some."""
    zero = [r for r in _canonical_rows() if r.get("pma_max_asing") == 0]
    assert len(zero) > 0, "the sweep read no 0% records — a truncated checkout passes vacuously (W84)"
    offenders = []
    for rec in zero:
        ok, reason = judge(rec)
        if not ok:
            offenders.append((rec["kode_kbli_2025"], reason))
    assert offenders == [], f"0% verdicts with no valid basis: {offenders}"


def test_guilt_the_6488_patch_is_refused():
    """GUILT. Fields verbatim from `git show 5535726236:data/source_documents/
    KBLI_2025_FINAL_CLEAN.json` records `73300` and `38110` — the actual patch #6488
    would have shipped, not a sentence written to match this gate."""
    kondisi = (
        "No Usaha Besar scale in OSS for this code and a PT PMA must be an Usaha Besar — "
        "foreign ownership 0% / Tidak ada skala Usaha Besar di OSS untuk KBLI ini, sedangkan "
        "PMA wajib Usaha Besar — kepemilikan asing 0% (Perpres 10/2021 Pasal 7(1); "
        "Permeninves/BKPM 5/2025 Pasal 26(1))"
    )
    nota = (
        "PMA_CLOSED_NO_BESAR_SCALE: closed to PT PMA, no Usaha Besar scale / tertutup bagi "
        "PMA, tanpa skala Usaha Besar"
    )
    source = "Perpres 10/2021 Pasal 7(1); Permeninves/BKPM 5/2025 Pasal 26(1) (retrieved 2026-09-14)"
    official_basis = (
        "Perpres 10/2021 (as amended by Perpres 49/2021) Pasal 7 ayat (1) — a foreign investor "
        "may carry on business only as an Usaha Besar — and Peraturan Menteri Investasi dan "
        "Hilirisasi/Kepala BKPM No. 5 Tahun 2025 Pasal 26 ayat (1), «yang dikategorikan PMA "
        "merupakan usaha besar» (ditetapkan 2025-10-01; retrieved 2026-09-14). OSS publishes "
        "no Usaha Besar scale for this KBLI 2025 code, so a PT PMA cannot operate it; max "
        "foreign 0% [PMA_CLOSED_NO_BESAR_SCALE, owner ruling 2026-09-14]."
    )
    for code in ("73300", "38110"):
        patched = {
            "kode_kbli_2025": code,
            "pma_status": "TERBATAS",
            "pma_max_asing": 0,
            "pma_verification_status": "located",
            "pma_kondisi": kondisi,
            "pma_nota": nota,
            "pma_source": source,
            "pma_official_basis": official_basis,
        }
        ok, reason = judge(patched)
        assert not ok, f"{code}: the #6488 patch must be refused, was accepted ({reason})"


def test_innocence_the_certified_lampiran_ii_codes_pass():
    by_code = {r["kode_kbli_2025"]: r for r in _canonical_rows()}
    for code in ("95291", "96100", "96210", "96220"):
        rec = by_code[code]
        assert rec.get("pma_max_asing") == 0, f"{code}: fixture assumption drifted, re-measure"
        ok, reason = judge(rec)
        assert ok, f"{code}: certified Lampiran II allocation wrongly refused ({reason})"


def test_innocence_tertutup_bare_citation_and_lampiran_iii_pass():
    by_code = {r["kode_kbli_2025"]: r for r in _canonical_rows()}
    rec_tertutup = by_code["01287"]  # Budidaya tanaman narkoba golongan I — Pasal 2 closure
    assert rec_tertutup.get("pma_status") == "TERTUTUP"
    ok, reason = judge(rec_tertutup)
    assert ok, f"01287: TERTUTUP national closure wrongly refused ({reason})"

    rec_l3 = by_code["16221"]
    assert "Lampiran III" in (rec_l3.get("pma_official_basis") or "")
    ok, reason = judge(rec_l3)
    assert ok, f"16221: Lampiran III basis wrongly refused ({reason})"


def test_innocence_a_legitimate_usaha_besar_mention_is_not_scale_absence():
    """A Pasal 26 investment-threshold note conditions the INVESTOR, not the activity — it
    must stay sayable. Over-match here would accuse every PMA-eligibility note of guilt."""
    sentence = (
        "Perpres 10/2021 Pasal 7(1) and BKPM 5/2025 Pasal 26(1) require a foreign investor "
        "to invest as Usaha Besar, above Rp10 miliar per KBLI — a condition on the investor, "
        "not a closure of the activity."
    )
    assert SCALE_ABSENCE_BASIS.search(sentence) is None


def _live_locator_entries() -> list[tuple[str, str, str]]:
    """Every (file, code, locator) the `apply_umkm_reservations.py`-style compilers actually
    read to WRITE a fresh 0% cap — the `items[].locator` schema shared by
    `umkm_lampiran_ii_readjudicated_2026_08_06.json` and `umkm_lampiran_ii_split_heirs_
    2026_08_06.json`. Deliberately narrower than "every file mentioning pma_max_asing":
    measured, that broader set is dominated by editorial-prose specs whose `old` field
    quotes the withdrawn sentence as the thing being REMOVED (evidence of the cure, not the
    claim) and `expect` blocks that assert a precondition rather than setting anything — a
    whole-file sweep over those produces false guilt, not real coverage.
    """
    entries: list[tuple[str, str, str]] = []
    for path in sorted(glob.glob(str(CURE_SPECS_DIR / "*.json"))):
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
        items = spec.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and "code" in item and "locator" in item:
                entries.append((path, str(item["code"]), str(item["locator"])))
    return entries


def test_spec_sweep_every_live_locator_entry_passes():
    entries = _live_locator_entries()
    assert len(entries) > 0, "the sweep read no live locator entries (W84)"
    offenders = []
    for path, code, locator in entries:
        if SCALE_ABSENCE_BASIS.search(locator) or not ANNEX_LOCATOR.search(locator):
            offenders.append((Path(path).name, code, locator[:160]))
    assert offenders == [], f"cure_spec locator entries with no valid basis: {offenders}"
