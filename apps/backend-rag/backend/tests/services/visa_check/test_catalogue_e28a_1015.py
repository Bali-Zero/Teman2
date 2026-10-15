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
STEPS = [
    "Passport valid ≥ 6 months",
    "Company established with the Kemenkumham deed, acting as your sponsor",
    "Proof of your own shareholding of at least IDR 10 billion in the sponsoring company",
    "Company current-account statement for the last 2 months",
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


def test_pre_arrival_steps_are_the_page_requirements() -> None:
    r = recommend_visa(
        nationality="USA", purpose=Purpose.INVESTOR, duration_months=24, budget_band=BudgetBand.OVER_500M
    )
    assert r.recommended_visa is VisaType.E28A
    assert r.pre_arrival_steps == STEPS
    text = " ".join(r.pre_arrival_steps)
    for dropped in ("plan ready to incorporate", "24 months", "Investment plan", "Share capital confirmation"):
        assert dropped not in text, dropped
    page = _page_text()
    assert "paling singkat 6 bulan" in page and "Rekening giro perusahaan 2 (dua) bulan" in page
    assert "pengesahan pendirian perusahaan" in page


def test_reason_text_never_presents_the_budget_gate_as_a_requirement() -> None:
    for band in (BudgetBand.MID_50_500M, BudgetBand.OVER_500M):
        r = recommend_visa(nationality="USA", purpose=Purpose.INVESTOR, duration_months=24, budget_band=band)
        for x in (x for x in r.ranking if x.visa is VisaType.E28A):
            assert "(requires" not in x.reason.lower() and "500M" not in x.reason, x.reason
            assert "IDR" not in x.reason.replace("IDR 10 billion", ""), x.reason
            assert ".." not in x.reason


def test_reason_text_carries_the_notes_innocence() -> None:
    r = recommend_visa(
        nationality="USA", purpose=Purpose.INVESTOR, duration_months=24, budget_band=BudgetBand.OVER_500M
    )
    reason = next(x.reason for x in r.ranking if x.visa is VisaType.E28A)
    assert NOTES in reason and "your own shareholding of at least IDR 10 billion" in reason
    assert reason.startswith("Investor Visa \u2014 ") and "Covers 1095 days total." in reason
