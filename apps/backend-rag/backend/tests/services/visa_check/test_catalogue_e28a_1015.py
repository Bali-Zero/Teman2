"""Legacy /api/visa/match: the E28A row and its pre-arrival steps say what the pack and the page say.

Audit findings F50-F53. Sources: signed pack seq-29 (E28A product) and the saved official page
research/visa/2026-10-15-e28-pages/ (E28A).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from backend.services.visa_check.catalogue import VISA_META, VisaType
from backend.services.visa_check.clock import clock_timeline
from backend.services.visa_check.match_tree import BudgetBand, Purpose, recommend_visa

REPO_ROOT = Path(__file__).resolve().parents[6]
PACK = (
    REPO_ROOT
    / "apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-029.signed.json"
)
PAGES = REPO_ROOT / "research/visa/2026-10-15-e28-pages"

NOTES = (
    "Requires a PT PMA sponsor and your own shareholding of at least IDR 10 billion in it "
    "(official E28A page)."
)
# (step fragment, fragment of the saved page that states it)
STEP_FRAGMENTS = [
    ("Application letter", "surat permohonan"),
    ("Passport valid \u2265 6 months", "paling singkat 6 bulan"),
    ("last 3 months, in your name or your sponsor's, of at least USD 2,000", "rekening koran 3 bulan"),
    ("Recent colour photo", "pasfoto berwarna"),
    ("Curriculum vitae", "daftar riwayat hidup"),
    ("Travel itinerary", "rincian perjalanan"),
    ("own shareholding of at least IDR 10 billion in the sponsoring company", "Rp10.000.000.000"),
    ("Kemenkumham decision approving", "pengesahan pendirian perusahaan"),
    ("current-account statement for the last 2 months", "Rekening giro perusahaan 2 (dua) bulan"),
    ("within 90 days after the ITAS is issued", "90 hari setelah ITAS terbit"),
]


def _pack_e28a() -> dict:
    payload = json.loads(PACK.read_text())["payload"]
    return next(p for p in payload["products"] if p["product_code"] == "E28A")


def _page_text() -> str:
    for line in (PAGES / "e28-pages.receipts.jsonl").read_text().splitlines():
        rec = json.loads(line)
        if rec["key_phrase"] == "E28A":
            return (PAGES / "text" / Path(rec["text_file"]).name).read_text()
    raise AssertionError("no saved E28A page")


def test_stay_and_extension_follow_the_pack() -> None:
    meta, pack = VISA_META[VisaType.E28A], _pack_e28a()
    assert meta.duration_days == pack["stay_policy"]["maximum_days"] == 730
    assert pack["extension_policy"]["allowed"] is True
    count, days_each = meta.extensions
    assert days_each == pack["extension_policy"]["days_per_extension"] == 365
    assert count >= 1
    assert meta.duration_days + count * days_each == 730 + 365 * count != 1460
    tl = clock_timeline(visa_type=VisaType.E28A, entry_date=date(2026, 1, 1))
    assert tl.extension_days == 365


def test_budget_gate_is_ranking_only_and_notes_cite_the_page() -> None:
    meta = VISA_META[VisaType.E28A]
    # ranking-only band boundary (orchestrator decision 2026-10-15), never shown as a requirement
    assert meta.min_budget_idr == 500_000_000 and meta.budget_gate_is_ranking_only is True
    assert meta.notes == NOTES
    assert "Rp10.000.000.000" in _page_text()
    assert "~IDR 10bn capital" not in meta.notes and "investment plan" not in meta.notes


def _investor(band: BudgetBand):
    return recommend_visa(nationality="USA", purpose=Purpose.INVESTOR, duration_months=24, budget_band=band)


def test_pre_arrival_steps_are_the_page_list() -> None:
    r = _investor(BudgetBand.OVER_500M)
    assert r.recommended_visa is VisaType.E28A
    text = " | ".join(r.pre_arrival_steps)
    page = _page_text()
    for fragment, page_fragment in STEP_FRAGMENTS:
        assert fragment in text, fragment
        assert page_fragment in page, page_fragment
    assert len(r.pre_arrival_steps) == len(STEP_FRAGMENTS) - 1  # the 90-day rule rides on the last step
    for dropped in ("plan ready to incorporate", "24 months", "Investment plan", "Share capital confirmation"):
        assert dropped not in text, dropped


def test_d12_keeps_its_own_list_without_the_e28a_post_incorporation_documents() -> None:
    r = _investor(BudgetBand.MID_50_500M)
    assert r.recommended_visa is VisaType.D12
    text = " | ".join(r.pre_arrival_steps)
    for forbidden in ("Company established", "Kemenkumham", "own shareholding", "current-account", "24 months"):
        assert forbidden not in text, forbidden
    assert "Investment plan document" in text and len(r.pre_arrival_steps) >= 3
    # and E28A, when it is the recommendation, does show them
    assert "Kemenkumham" in " | ".join(_investor(BudgetBand.OVER_500M).pre_arrival_steps)


def test_reason_text_never_presents_the_budget_gate_as_a_requirement() -> None:
    for band in (BudgetBand.MID_50_500M, BudgetBand.OVER_500M):
        for x in (x for x in _investor(band).ranking if x.visa is VisaType.E28A):
            assert "(requires" not in x.reason.lower() and "500M" not in x.reason, x.reason
            assert ".." not in x.reason


def test_e28a_reason_states_the_stay_and_no_invented_total() -> None:
    reason = next(x.reason for x in _investor(BudgetBand.OVER_500M).ranking if x.visa is VisaType.E28A)
    import re

    assert not re.search(r"Covers \d+ days total|Max stay \d+ days", reason), reason
    assert "1095" not in reason and "1460" not in reason
    assert "730 days" in reason and "extendable online by the sponsor" in reason
    pack = _pack_e28a()
    assert pack["stay_policy"]["maximum_days"] == 730
    assert "diajukan secara online oleh sponsor" in _page_text() or "online oleh sponsor" in _page_text()


def test_reason_text_carries_the_notes_innocence() -> None:
    reason = next(x.reason for x in _investor(BudgetBand.OVER_500M).ranking if x.visa is VisaType.E28A)
    assert NOTES in reason and reason.startswith("Investor Visa \u2014 ")
    d12 = next(x.reason for x in _investor(BudgetBand.OVER_500M).ranking if x.visa is VisaType.D12)
    assert "Covers" in d12  # other visas keep the computed coverage
