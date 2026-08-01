"""Tests for the state-based `kbli_documents` conformance detector.

Guilt + innocence per scar #3, on synthetic two-store fixtures. No DB.

The point of this detector is that it selects on a STATE, never on a list of
codes — so the guilt cases below deliberately use codes that appear in no cure
spec anywhere. If a future edit reintroduces a list, these tests keep passing
while the tool goes blind, so the FIRST test asserts the tool's own scope: every
row of the table is judged and every canonical code is asked for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import _coverage_basis as B  # noqa: E402
import kbli_surface_conformance as C  # noqa: E402


def canon(code: str, **kwargs) -> dict:
    base = {B.CODE_FIELD: code, "pma_status": "TERBUKA", "per_skala": [], "judul": "Judul Kanonico"}
    base.update(kwargs)
    return base


def row(code: str, **kwargs) -> dict:
    base = {
        "code": code,
        "pma_status": "TERBUKA",
        "judul": "Judul Kanonico",
        "licensing_status": "N/A",
        "rows": 0,
    }
    base.update(kwargs)
    return base


def store(*records) -> dict:
    return {r[B.CODE_FIELD]: r for r in records}


# --------------------------------------------------------------------------
# scope — the property that makes this tool different from every cure before it
# --------------------------------------------------------------------------


def test_it_judges_codes_no_cure_spec_has_ever_named():
    """A code invented for this test, in neither store's cure history, still
    gets caught. This is the whole thesis: state, not list."""
    report = C.plan_conformance(store(canon("77777")), [row("77777", pma_status="TERTUTUP")])
    assert [d["code"] for d in report["pma_divergent"]] == ["77777"]


def test_it_asks_for_every_canonical_code():
    report = C.plan_conformance(store(canon("11111"), canon("22222")), [row("11111")])
    assert report["missing_from_table"] == ["22222"]
    assert report["enforced_divergences"] == 1


# --------------------------------------------------------------------------
# guilt
# --------------------------------------------------------------------------


def test_guilt_pma_status_disagreement():
    report = C.plan_conformance(
        store(canon("50122", pma_status="TERBATAS")), [row("50122", pma_status="TERBUKA")]
    )
    assert report["pma_divergent"][0]["canonical"] == "TERBATAS"
    assert report["pma_divergent"][0]["table"] == "TERBUKA"


def test_guilt_table_serves_licensing_for_a_code_canonical_detached():
    """The 50113 disease: canonical declared the gap, the channel kept serving
    the vintage-2020 rows into the LLM context."""
    report = C.plan_conformance(store(canon("50113", per_skala=[])), [row("50113", rows=4)])
    assert report["licensing_divergent"] == [
        {"code": "50113", "canonical_rows": 0, "table_rows": 4}
    ]


def test_guilt_table_serves_nothing_where_canonical_has_verified_rows():
    """The opposite direction, found on 80 codes at first run: the channel
    answers "N/A" while the website publishes the verified permit table."""
    report = C.plan_conformance(store(canon("82400", per_skala=[{"x": 1}] * 8)), [row("82400", rows=0)])
    assert report["licensing_divergent"][0]["canonical_rows"] == 8


def test_guilt_row_absent_from_canonical_and_not_neutralised():
    report = C.plan_conformance(store(), [row("47911")])
    assert report["unneutralised_phantoms"] == ["47911"]


def test_guilt_live_code_advertised_as_retired():
    """The inverse phantom error: a code the catalogue still carries, marked as
    deleted-by-KBLI-2025 in the store clients talk to."""
    report = C.plan_conformance(store(canon("56101")), [row("56101", licensing_status=C.PHANTOM_MARKER)])
    assert report["live_marked_retired"] == ["56101"]


# --------------------------------------------------------------------------
# innocence
# --------------------------------------------------------------------------


def test_innocence_identical_stores_are_clean():
    report = C.plan_conformance(store(canon("01111")), [row("01111")])
    assert report["enforced_divergences"] == 0


def test_innocence_a_properly_neutralised_phantom_is_not_a_divergence():
    """`26120`/`60111`/`82920`/`85598` are KBLI-2020 codes 2025 retired. They
    are SUPPOSED to sit in the table with no canonical record — flagging them
    would make the gate red forever and get it muted."""
    report = C.plan_conformance(store(), [row("82920", licensing_status=C.PHANTOM_MARKER)])
    assert report["unneutralised_phantoms"] == []
    assert report["enforced_divergences"] == 0


def test_innocence_title_difference_alone_never_fails_the_gate():
    """1,423 rows still carry the original UPPERCASE seed titles. Enforcing on
    them would drown the ownership and licensing signals in cosmetic noise."""
    report = C.plan_conformance(
        store(canon("01111", judul="Pertanian Padi Inbrida")), [row("01111", judul="RICE FARMING (PERTANIAN PADI)")]
    )
    assert report["enforced_divergences"] == 0
    assert report["declared_only"]["judul_differs"] == 1


def test_case_only_title_difference_is_not_even_counted():
    report = C.plan_conformance(store(canon("01111", judul="Pertanian Padi")), [row("01111", judul="PERTANIAN PADI")])
    assert report["declared_only"]["judul_differs"] == 0


def test_truncated_titles_are_counted_separately_because_truncation_changes_meaning():
    """On 5 government codes the cut lands past the word `Pemerintah` — the one
    word that says the activity is governmental."""
    report = C.plan_conformance(
        store(canon("91221", judul="Situs Bersejarah dan Monumen yang Dikelola Pemerintah")),
        [row("91221", judul="Situs Bersejarah dan Monumen yang")],
    )
    assert report["declared_only"]["judul_truncated"] == 1
    assert report["enforced_divergences"] == 0


def test_innocence_matching_licensing_presence_is_clean_at_both_ends():
    both_full = C.plan_conformance(store(canon("01111", per_skala=[{"x": 1}])), [row("01111", rows=3)])
    both_empty = C.plan_conformance(store(canon("68112", per_skala=[])), [row("68112", rows=0)])
    assert both_full["licensing_divergent"] == []
    assert both_empty["licensing_divergent"] == []


# --------------------------------------------------------------------------
# the report must distinguish "syncs to evidence" from "syncs to the SSOT"
# --------------------------------------------------------------------------


def test_divergence_records_whether_canonical_has_an_adjudicated_basis():
    """Six of the eight live divergences sync the table to an adjudicated
    Perpres basis; two only sync it to canonical's own unverified value. A cure
    that blurs the two would claim a truth fix it did not make."""
    report = C.plan_conformance(
        store(
            canon("50122", pma_status="TERBATAS", pma_official_basis="Perpres 10/2021 Lampiran III"),
            canon("02101", pma_status="TERBUKA", pma_cap_verified=False),
        ),
        [row("50122", pma_status="TERBUKA"), row("02101", pma_status="TERBATAS")],
    )
    by_code = {d["code"]: d for d in report["pma_divergent"]}
    assert by_code["50122"]["canonical_basis"] is True
    assert by_code["02101"]["canonical_basis"] is False
    assert by_code["02101"]["canonical_cap_verified"] is False


# --------------------------------------------------------------------------
# CLI contract
# --------------------------------------------------------------------------


def test_empty_snapshot_is_cannot_verify_never_clean(tmp_path, capsys):
    """Zero rows traversed is not a clean bill of health (W84)."""
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text("[]", encoding="utf-8")
    rc = C.main(["--canonical", str(canonical), "--table-json", str(snap)])
    assert rc == C.EXIT_CANNOT_VERIFY
    assert "not a clean bill" in capsys.readouterr().out


def test_unreachable_database_is_cannot_verify_not_divergence(tmp_path, capsys):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    rc = C.main(["--canonical", str(canonical), "--psql-wrapper", str(tmp_path / "no-such-pg.sh")])
    assert rc == C.EXIT_CANNOT_VERIFY
    assert "CANNOT VERIFY" in capsys.readouterr().out


def test_conformant_stores_exit_zero(tmp_path):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111")]), encoding="utf-8")
    assert C.main(["--canonical", str(canonical), "--table-json", str(snap)]) == C.EXIT_OK


def test_divergent_stores_exit_one(tmp_path):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [canon("01111", pma_status="TERTUTUP")]}), encoding="utf-8")
    snap = tmp_path / "s.json"
    snap.write_text(json.dumps([row("01111", pma_status="TERBUKA")]), encoding="utf-8")
    assert C.main(["--canonical", str(canonical), "--table-json", str(snap)]) == C.EXIT_DIVERGENCE
