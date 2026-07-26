"""Tests for kbli_qdrant_risk_clear.

Mocks the Qdrant client entirely — no live Qdrant needed. Verifies the
core --apply gate (dry-run writes nothing, --apply writes exactly once per
matched point with the cleared value) and the not-found path never
crashes (honest-gap cure pattern, PR #2597 / kg_kbli_license_fix.py sibling).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from backend.scripts.kbli_qdrant_risk_clear import (
    CLEARED_RISK_VALUE,
    build_plan,
    clear_risk_for_code,
    find_points_for_code,
)

_COLLECTION = "kbli_2025_final_hybrid"


class FakeQdrantClient:
    """Minimal stand-in for qdrant_client.QdrantClient.

    `pages_by_code` maps a KBLI code to a list of scroll "pages" (each page
    a list of SimpleNamespace(id=..., payload={...}) records) so pagination
    can be exercised deterministically without a real Qdrant offset type.
    """

    def __init__(self, pages_by_code: dict[str, list[list[SimpleNamespace]]]) -> None:
        self._pages_by_code = pages_by_code
        self.set_payload_calls: list[dict[str, Any]] = []

    def scroll(
        self,
        collection_name: str,
        scroll_filter: Any,
        limit: int,
        with_payload: bool,
        with_vectors: bool,
        offset: int | None,
    ) -> tuple[list[SimpleNamespace], int | None]:
        code = scroll_filter.must[0].match.value
        pages = self._pages_by_code.get(code, [])
        page_index = offset or 0
        if page_index >= len(pages):
            return [], None
        page = pages[page_index]
        next_offset = page_index + 1 if page_index + 1 < len(pages) else None
        return page, next_offset

    def set_payload(self, collection_name: str, payload: dict[str, Any], points: list[Any]) -> None:
        self.set_payload_calls.append(
            {"collection_name": collection_name, "payload": payload, "points": points},
        )


def _record(point_id: Any, kategori_risiko: Any = "MT") -> SimpleNamespace:
    return SimpleNamespace(
        id=point_id,
        payload={
            "kode_kbli": "68112",
            "kategori_risiko": kategori_risiko,
        },
    )


# ---------------------------------------------------------------------------
# find_points_for_code — pagination
# ---------------------------------------------------------------------------


def test_find_points_for_code_paginates_across_multiple_pages() -> None:
    client = FakeQdrantClient(
        {
            "68112": [[_record(1)], [_record(2)]],
        },
    )
    records = find_points_for_code(client, _COLLECTION, "68112")
    assert [r.id for r in records] == [1, 2]


# ---------------------------------------------------------------------------
# (a) dry-run performs zero writes
# ---------------------------------------------------------------------------


def test_dry_run_performs_zero_writes() -> None:
    client = FakeQdrantClient({"68112": [[_record(1), _record(2)]]})
    records = find_points_for_code(client, _COLLECTION, "68112")
    plan = build_plan("68112", records)

    clear_risk_for_code(client, _COLLECTION, plan, apply=False)

    assert client.set_payload_calls == []


# ---------------------------------------------------------------------------
# (b) --apply calls set_payload exactly once per matched point with the
#     cleared value
# ---------------------------------------------------------------------------


def test_apply_calls_set_payload_once_per_matched_point() -> None:
    client = FakeQdrantClient({"68112": [[_record(1, "MT"), _record(2, "T")]]})
    records = find_points_for_code(client, _COLLECTION, "68112")
    plan = build_plan("68112", records)

    clear_risk_for_code(client, _COLLECTION, plan, apply=True)

    assert len(client.set_payload_calls) == 2
    for call, expected_point in zip(client.set_payload_calls, [1, 2], strict=True):
        assert call["collection_name"] == _COLLECTION
        assert call["payload"] == {"kategori_risiko": CLEARED_RISK_VALUE}
        assert call["points"] == [expected_point]


def test_apply_writes_empty_string_not_none() -> None:
    """The resolver (_resolve_risk_profile, kbli_notebook.py:292) and the flat-payload
    reader (_payload_value, kbli_notebook.py:119-125) both treat "" as absent —
    the cleared value must be the empty string, not a None/null payload value."""
    assert CLEARED_RISK_VALUE == ""

    client = FakeQdrantClient({"68112": [[_record(1, "MT")]]})
    records = find_points_for_code(client, _COLLECTION, "68112")
    plan = build_plan("68112", records)

    clear_risk_for_code(client, _COLLECTION, plan, apply=True)

    assert client.set_payload_calls[0]["payload"]["kategori_risiko"] == ""


# ---------------------------------------------------------------------------
# (c) a code with no matching points is reported and does not crash
# ---------------------------------------------------------------------------


def test_code_with_no_matching_points_does_not_crash_and_reports_not_found() -> None:
    client = FakeQdrantClient({})  # no pages registered for any code
    records = find_points_for_code(client, _COLLECTION, "99999")
    plan = build_plan("99999", records)

    assert plan.found is False
    assert plan.point_ids == []

    # Must not raise, and must not attempt any write, even with --apply.
    clear_risk_for_code(client, _COLLECTION, plan, apply=True)

    assert client.set_payload_calls == []


def test_build_plan_captures_current_values_per_point() -> None:
    records = [_record(1, "MT"), _record(2, None)]
    plan = build_plan("68112", records)

    assert plan.current_values == {1: "MT", 2: None}
    assert plan.point_ids == [1, 2]
    assert plan.found is True
