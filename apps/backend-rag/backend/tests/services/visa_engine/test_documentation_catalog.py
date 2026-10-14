"""The source-stamped document catalogue: AVAILABLE only where an official page was read."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.portal_read_receipt import fingerprint, visible_text
from backend.services.visa_engine.api_models import CandidateDocumentationDTO
from backend.services.visa_engine.documentation_catalog import (
    UNKNOWN_REASON_CODE,
    catalogue_codes,
    documentation_for,
)

# Reused as module fixtures: the signed seq-29 pack and the census walks' displays.
from backend.tests.services.visa_engine.test_evaluate_path_display import (  # noqa: F401
    candidate_displays,
    signed_seq29_pack,
)

_REPO_ROOT = Path(__file__).resolve().parents[6]
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_documentation_catalog_2026.json"
# The pack freshness max age (one year): a page read older than this must be read again.
_MAX_AGE_SECONDS = 31536000
_EXPECTED_CODES = {"E33", "E33A", "E33B", "E33C", "E33E", "E33F", "E33G"}
_OBSERVED = "2026-10-14T01:00:00+00:00"


def _raw() -> dict[str, Any]:
    return json.loads(_CATALOGUE.read_text(encoding="utf-8"))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def test_catalogue_covers_exactly_the_verified_second_home_products() -> None:
    assert catalogue_codes() == _EXPECTED_CODES
    assert set(_raw()["products"]) == _EXPECTED_CODES


def test_every_item_has_both_languages_and_every_product_lists_a_document() -> None:
    for code, row in _raw()["products"].items():
        assert row["requirements"] or row["checklist"], code
        for item in [*row["requirements"], *row["checklist"]]:
            assert set(item) == {"en", "id", "page_quote"}, (code, item)
            assert item["en"].strip() and item["id"].strip() and item["page_quote"].strip()
            assert item["en"] != item["id"], (code, item)


def test_every_product_is_stamped_with_an_official_page_a_time_and_a_fingerprint() -> None:
    for code, row in _raw()["products"].items():
        assert (
            row["canonical_url"] == f"https://www.imigrasi.go.id/wna/daftar-visa-indonesia/{code}"
        )
        assert datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00")).tzinfo is not None
        assert re.fullmatch(r"[0-9a-f]{64}", row["content_sha256"]), code


def test_stamps_agree_with_the_saved_pages_and_the_read_receipts() -> None:
    receipts = {
        json.loads(line)["canonical_url"]: json.loads(line)
        for line in (
            _REPO_ROOT / "research/visa/2026-10-14-e33-documents/e33-documents.receipts.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
    }
    for code, row in _raw()["products"].items():
        receipt = receipts[row["canonical_url"]]
        assert receipt["http_status"] == 200 and receipt["key_phrase_found"] is True
        assert receipt["fetched_at"] == row["fetched_at"], code
        assert receipt["visible_text_sha256"] == row["content_sha256"], code
        page = (_REPO_ROOT / row["text_file"]).read_text(encoding="utf-8")
        # The saved text re-derives the fingerprint: the stamp is not a free-floating string.
        assert fingerprint(page.rstrip("\n")) == row["content_sha256"], code
        assert visible_text(page) == page.rstrip("\n")


def test_every_item_quotes_the_saved_official_page_verbatim() -> None:
    for code, row in _raw()["products"].items():
        page = _norm((_REPO_ROOT / row["text_file"]).read_text(encoding="utf-8"))
        for item in [*row["requirements"], *row["checklist"]]:
            assert _norm(item["page_quote"]) in page, (code, item["page_quote"])


def test_no_vendor_only_item_is_listed() -> None:
    blob = json.dumps(_raw()["products"], ensure_ascii=False).lower()
    for banned in ("health insurance", "asuransi", "helper", "pembantu", "domestic"):
        assert banned not in blob, banned


def test_stale_guard_fails_when_a_page_was_read_more_than_one_year_ago() -> None:
    now = datetime.now(timezone.utc)
    for code, row in _raw()["products"].items():
        fetched = datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
        age = (now - fetched).total_seconds()
        assert 0 <= age <= _MAX_AGE_SECONDS, (
            f"{code} page read {age:.0f}s ago is in the future or exceeds the "
            f"{_MAX_AGE_SECONDS}s freshness max age: re-read the official page and re-stamp "
            "the catalogue"
        )


@pytest.mark.parametrize("code", ["E31B", "E31A", "C1", "D12", "E28A", "E30", "BRIDGING", "XX9"])
def test_codes_outside_the_catalogue_stay_unknown(code: str) -> None:
    block = documentation_for(code, _OBSERVED)
    assert block == {
        "status": "UNKNOWN",
        "reason_code": UNKNOWN_REASON_CODE,
        "observed_at": _OBSERVED,
        "requirements": [],
        "checklist": [],
    }
    CandidateDocumentationDTO.model_validate(block)


@pytest.mark.parametrize("code", sorted(_EXPECTED_CODES))
def test_catalogue_codes_are_available_and_dto_valid(code: str) -> None:
    block = documentation_for(code, _OBSERVED)
    assert block["status"] == "AVAILABLE"
    dto = CandidateDocumentationDTO.model_validate(block)
    assert all(item.en and item.id for item in [*dto.requirements, *dto.checklist])


def test_the_catalogue_returns_copies_not_the_shared_snapshot() -> None:
    first = documentation_for("E33F", _OBSERVED)
    first["requirements"].append({"en": "x", "id": "y"})  # type: ignore[union-attr]
    assert {"en": "x", "id": "y"} not in documentation_for("E33F", _OBSERVED)["requirements"]  # type: ignore[operator]


def test_e33_family_figures_are_the_pages_own() -> None:
    flat = {
        code: json.dumps(documentation_for(code, _OBSERVED), ensure_ascii=False)
        for code in _EXPECTED_CODES
    }
    assert "USD 2,000" in flat["E33"] and "USD 130,000" in flat["E33"]
    assert "USD 1,000,000" in flat["E33"]
    assert "USD 50,000" in flat["E33E"] and "USD 3,000 per month" in flat["E33E"]
    assert "USD 3,000 per month" in flat["E33F"] and "surat penjaminan" in flat["E33F"].lower()
    assert "GPA of at least 3.5" in flat["E33B"] and "top 100" in flat["E33B"]
    assert "central government" in flat["E33C"]
    assert "USD 60,000 per year" in flat["E33G"] and "company established outside" in flat["E33G"]


def test_an_e33f_persona_carries_available_with_the_penjamin_letter(
    candidate_displays: list[tuple[Any, Any, dict[str, Any]]],  # noqa: F811
) -> None:
    e33f = [
        shown
        for _d, _c, display in candidate_displays
        for shown in display["candidates"]
        if shown["product_code"] == "E33F"
    ]
    assert e33f
    for shown in e33f:
        documentation = shown["documentation"]
        assert documentation["status"] == "AVAILABLE"
        assert documentation["reason_code"] == "OFFICIAL_IMIGRASI_DOCUMENT_CHECKLIST"
        assert any(
            "sponsorship letter" in item["en"].lower() and "surat penjaminan" in item["id"].lower()
            for item in documentation["requirements"]
        )


def test_available_exactly_where_the_catalogue_verifies_and_unknown_everywhere_else(
    candidate_displays: list[tuple[Any, Any, dict[str, Any]]],  # noqa: F811
) -> None:
    seen: set[str] = set()
    for _d, _c, display in candidate_displays:
        for shown in display["candidates"]:
            code = shown["product_code"]
            seen.add(code)
            documentation = shown["documentation"]
            if code in _EXPECTED_CODES:
                assert documentation["status"] == "AVAILABLE", code
            else:
                assert documentation["status"] == "UNKNOWN", code
                assert documentation["reason_code"] == UNKNOWN_REASON_CODE
                assert documentation["requirements"] == [] and documentation["checklist"] == []
    # The census reaches both sides: an E31B persona shows none, every E33-family code shows its list.
    assert "E31B" in seen and _EXPECTED_CODES <= seen


# The approved EN/ID pairs for the items whose two languages must say the same thing.
_TRAVEL_PAIRS = {
    "Riwayat perjalanan dan rencana perjalanan (itinerary)": "Travel history and travel plan (itinerary)",
    "Riwayat perjalanan (itinerary)": "Travel history (itinerary)",
}


def test_the_travel_items_pin_the_approved_english_for_each_indonesian_text() -> None:
    seen: set[str] = set()
    for code, row in _raw()["products"].items():
        for item in [*row["requirements"], *row["checklist"]]:
            if item["id"] in _TRAVEL_PAIRS:
                seen.add(item["id"])
                assert item["en"] == _TRAVEL_PAIRS[item["id"]], (code, item)
            else:
                assert "itinerary" not in item["id"].lower(), (code, item["id"])
    assert seen == set(_TRAVEL_PAIRS)


def test_no_post_entry_obligation_is_listed_as_a_document() -> None:
    blob = json.dumps(_raw()["products"], ensure_ascii=False)
    assert "must be kept" not in blob and "dipertahankan" not in blob


def test_the_two_numeric_thresholds_are_anchored_on_the_page() -> None:
    products = _raw()["products"]
    e33_quotes = [_norm(i["page_quote"]) for i in products["E33"]["requirements"]]
    assert any("us$130.000" in q and "pernyataan komitmen" in q for q in e33_quotes)
    e33b_quotes = [_norm(i["page_quote"]) for i in products["E33B"]["requirements"]]
    assert any("paling sedikit 3,5" in q for q in e33b_quotes)
