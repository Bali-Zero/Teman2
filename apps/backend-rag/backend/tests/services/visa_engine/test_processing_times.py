"""Bali Zero's typical processing time: catalogue window, Indonesian working days, honest UNKNOWN."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from backend.scripts.visa_engine.review_hold_inventory import load_highest_signed_pack
from backend.services.visa_engine import processing_times
from backend.services.visa_engine.api_models import (
    CandidateProcessingTimelineDTO,
    VisaOracleDisplayDTO,
)
from backend.services.visa_engine.evaluate_path import _build_display, _processing_timeline
from backend.services.visa_engine.pricing_adapter import UnavailablePricingCatalog
from backend.services.visa_engine.processing_times import estimate, typical_window

_PACKS = Path(__file__).resolve().parents[3] / "services/visa_engine/contracts/packs"
_OBSERVED = datetime(2026, 10, 9, 1, 0, tzinfo=timezone.utc)


def _decision(evaluated_at: datetime) -> Any:
    return SimpleNamespace(evaluated_at=evaluated_at, observed_at=_OBSERVED)


_NO_CATALOGUE_TIME = frozenset({"BRIDGING"})


def unmapped_products(product_codes: Iterable[str]) -> set[str]:
    """Pack products that neither have a catalogue window nor are the named exclusion."""

    return {
        code
        for code in product_codes
        if code not in _NO_CATALOGUE_TIME and typical_window(code) is None
    }


def _pack_product_codes() -> dict[str, set[str]]:
    """Product codes of the highest signed pack and of every newer prod source on disk."""

    highest = load_highest_signed_pack()
    found = {f"signed seq-{highest.sequence}": {str(p.product_code) for p in highest.products}}
    for path in sorted(_PACKS.glob("rulepack-prod-*.source.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw["sequence"] > highest.sequence:
            found[path.name] = {p["product_code"] for p in raw["products"]}
    return found


class TestSnapshot:
    def test_covers_every_product_of_the_signed_pack_and_every_newer_source(self) -> None:
        for label, codes in _pack_product_codes().items():
            assert unmapped_products(codes) == set(), label
        assert typical_window("BRIDGING") is None
        assert typical_window("NOPE") is None

    def test_the_snapshot_holds_exactly_the_signed_pack_minus_the_named_exclusion(self) -> None:
        snapshot = json.loads(Path(processing_times._SNAPSHOT).read_text(encoding="utf-8"))
        signed = next(iter(_pack_product_codes().values()))
        assert set(snapshot["products"]) == signed - _NO_CATALOGUE_TIME

    def test_a_product_missing_from_the_snapshot_is_reported(self) -> None:
        assert unmapped_products({"C1", "BRIDGING", "E99Z"}) == {"E99Z"}
        assert unmapped_products({"C1", "BRIDGING"}) == set()

    @pytest.mark.parametrize(
        ("code", "window"),
        [
            ("E23", (20, 30)),
            ("B1", (0, 1)),
            ("A1", (0, 0)),
            ("C1", (3, 5)),
            ("D12", (7, 10)),
            ("E31B", (7, 10)),
        ],
    )
    def test_interpretation(self, code: str, window: tuple[int, int]) -> None:
        assert typical_window(code) == window

    def test_every_window_is_ordered(self) -> None:
        for code, (low, high) in processing_times._windows().items():
            assert 0 <= low <= high, code


class TestEstimate:
    def test_walks_across_a_weekend(self) -> None:
        # Friday 2026-10-09: +3 working days is Wednesday 10-14, +5 is Friday 10-16.
        assert estimate(date(2026, 10, 9), (3, 5)) == (date(2026, 10, 14), date(2026, 10, 16))

    def test_zero_is_the_anchor_itself(self) -> None:
        assert estimate(date(2026, 10, 10), (0, 0)) == (date(2026, 10, 10), date(2026, 10, 10))

    def test_skips_cuti_bersama_and_christmas(self) -> None:
        # 2026-12-24 (cuti bersama) and 12-25 (Natal) are closed.
        assert estimate(date(2026, 12, 23), (1, 2)) == (date(2026, 12, 28), date(2026, 12, 29))

    def test_a_walk_into_an_undecreed_year_is_unknown(self) -> None:
        assert estimate(date(2027, 12, 30), (5, 5)) is None
        assert estimate(date(2030, 1, 4), (0, 0)) is None

    def test_a_walk_inside_the_last_decreed_year_still_answers(self) -> None:
        assert estimate(date(2027, 12, 1), (3, 5)) is not None


class TestDisplayTimeline:
    def test_e31b_is_available_seven_to_ten_working_days(self) -> None:
        shown = _processing_timeline(
            "E31B", _decision(datetime(2026, 10, 9, 1, 0, tzinfo=timezone.utc))
        )
        assert shown["status"] == "AVAILABLE"
        assert shown["reason_code"] == "BALI_ZERO_TYPICAL_PROCESSING_TIME"
        assert (shown["working_days_min"], shown["working_days_max"]) == (7, 10)
        assert shown["anchor_date"] == "2026-10-09"
        assert shown["estimated_completion_from"] == "2026-10-20"
        assert shown["estimated_completion_to"] == "2026-10-23"

    def test_the_anchor_is_the_wita_calendar_day(self) -> None:
        # 17:00 UTC on the 9th is already the 10th in Bali.
        shown = _processing_timeline(
            "A1", _decision(datetime(2026, 10, 9, 17, 0, tzinfo=timezone.utc))
        )
        assert shown["anchor_date"] == "2026-10-10"

    def test_bridging_stays_the_unchanged_unknown_object(self) -> None:
        shown = _processing_timeline("BRIDGING", _decision(_OBSERVED))
        assert shown == {
            "status": "UNKNOWN",
            "reason_code": "PROCESSING_TIMELINE_NOT_VERIFIED",
            "observed_at": _OBSERVED.isoformat(),
            "anchor_date": None,
            "estimated_completion_from": None,
            "estimated_completion_to": None,
        }

    def test_an_undecreed_year_falls_back_to_unknown(self) -> None:
        shown = _processing_timeline("E31B", _decision(datetime(2028, 3, 1, tzinfo=timezone.utc)))
        assert shown["status"] == "UNKNOWN"
        assert "working_days_min" not in shown

    def test_every_walk_candidate_validates_and_prunes_absent_keys(self) -> None:
        from backend.tests.services.visa_engine import test_interview_walk_census as census

        seen = {"AVAILABLE": 0, "UNKNOWN": 0}
        for label, spec in list(census._load_walks().items())[:60]:
            decision, compiled, _ = census._decide(spec["overrides"], label)
            if not decision.candidates:
                continue
            raw = _build_display(
                decision, compiled, request_trace="t", pricing_catalog=UnavailablePricingCatalog()
            )
            dumped = VisaOracleDisplayDTO.model_validate(raw).model_dump(mode="json")
            for entry in dumped["candidates"]:
                timeline = entry["processing_timeline"]
                seen[timeline["status"]] += 1
                has_window = "working_days_min" in timeline
                assert has_window == (timeline["status"] == "AVAILABLE")
                assert has_window == ("working_days_max" in timeline)
        assert seen["AVAILABLE"] > 0


def _timeline(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "status": "AVAILABLE",
        "reason_code": "BALI_ZERO_TYPICAL_PROCESSING_TIME",
        "observed_at": _OBSERVED,
        "anchor_date": date(2026, 10, 9),
        "estimated_completion_from": date(2026, 10, 20),
        "estimated_completion_to": date(2026, 10, 23),
        "working_days_min": 7,
        "working_days_max": 10,
    }
    base.update(over)
    return base


class TestTimelineDto:
    def test_available_with_a_window_is_valid(self) -> None:
        dto = CandidateProcessingTimelineDTO.model_validate(_timeline())
        assert (dto.working_days_min, dto.working_days_max) == (7, 10)

    @pytest.mark.parametrize(
        "over",
        [
            {"working_days_min": None},
            {"working_days_max": None},
            {"working_days_min": 11},
            {"working_days_min": -1},
        ],
    )
    def test_available_rejects_a_missing_or_inverted_window(self, over: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            CandidateProcessingTimelineDTO.model_validate(_timeline(**over))

    def test_unknown_cannot_carry_a_window(self) -> None:
        unknown = _timeline(
            status="UNKNOWN",
            reason_code="PROCESSING_TIMELINE_NOT_VERIFIED",
            anchor_date=None,
            estimated_completion_from=None,
            estimated_completion_to=None,
        )
        with pytest.raises(ValidationError):
            CandidateProcessingTimelineDTO.model_validate(unknown)
        unknown["working_days_min"] = unknown["working_days_max"] = None
        dumped = CandidateProcessingTimelineDTO.model_validate(unknown).model_dump(mode="json")
        assert "working_days_min" not in dumped and "working_days_max" not in dumped

    def test_zero_zero_is_a_legitimate_instant_window(self) -> None:
        dumped = CandidateProcessingTimelineDTO.model_validate(
            _timeline(
                working_days_min=0,
                working_days_max=0,
                estimated_completion_from=date(2026, 10, 9),
                estimated_completion_to=date(2026, 10, 9),
            )
        ).model_dump(mode="json")
        assert dumped["working_days_min"] == 0
        assert dumped["working_days_max"] == 0
