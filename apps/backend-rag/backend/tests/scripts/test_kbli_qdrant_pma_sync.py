"""Tests for kbli_qdrant_pma_sync.

The dangerous failure here is not a missed update: it is writing a PMA figure
that the canonical does not carry, onto the store `inspect_kbli` prefers over
the KG. So most of this file is refusal and innocence.

Qdrant is mocked entirely via a fake httpx transport — no live Qdrant needed.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from backend.scripts.kbli_qdrant_pma_sync import (
    CODE_KEY,
    Target,
    apply_plan,
    build_plan,
    build_targets,
    find_points_for_code,
)

_COLLECTION = "kbli_2025_final_hybrid"
_BASE = "http://qdrant.test"
_HEADERS = {"Content-Type": "application/json"}


def _rec(code: str, status: str = "TERBUKA", cap: Any = 100) -> dict:
    return {"kode_kbli_2025": code, "pma_status": status, "pma_max_asing": cap}


def _point(pid: Any, status: str = "TERBUKA", cap: Any = 100) -> dict:
    return {"id": pid, "payload": {"pma_status": status, "pma_max_asing": cap, "judul": "x"}}


class FakeQdrant:
    """Serves /points/scroll from a code->pages map and records payload writes."""

    def __init__(self, pages_by_code: dict[str, list[list[dict]]]) -> None:
        self._pages = pages_by_code
        self.payload_writes: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path.endswith("/points/scroll"):
            code = body["filter"]["must"][0]["match"]["value"]
            assert body["filter"]["must"][0]["key"] == CODE_KEY
            pages = self._pages.get(code, [[]])
            idx = body.get("offset") or 0
            page = pages[idx] if idx < len(pages) else []
            nxt = idx + 1 if idx + 1 < len(pages) else None
            return httpx.Response(200, json={"result": {"points": page, "next_page_offset": nxt}})
        if request.url.path.endswith("/points/payload"):
            self.payload_writes.append(body)
            return httpx.Response(200, json={"result": {}, "status": "ok"})
        raise AssertionError(f"unexpected path {request.url.path}")

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


# --- refusal: the whole point ------------------------------------------------


def test_a_code_absent_from_the_canonical_is_refused_not_skipped():
    targets, refusals = build_targets([_rec("25200")], ["25200", "99999"])
    assert "25200" in targets
    assert any("99999" in r and "absent from the canonical" in r for r in refusals)


def test_a_canonical_record_without_a_status_is_refused():
    targets, refusals = build_targets([{"kode_kbli_2025": "25200"}], ["25200"])
    assert targets == {}
    assert any("no pma_status" in r for r in refusals)


# --- guilt -------------------------------------------------------------------


def test_a_stale_point_is_rewritten_to_the_canonical_verdict():
    fake = FakeQdrant({"25200": [[_point(7)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "TERBATAS", 49), points)
        n = apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert n == 1
    assert fake.payload_writes == [
        {"payload": {"pma_status": "TERBATAS", "pma_max_asing": 49}, "points": [7]}
    ]


def test_every_point_of_a_code_is_rewritten_across_scroll_pages():
    """Pagination is not decoration — a code with points on page 2 must not be
    half-cured, which would leave the same code answering two ways."""
    fake = FakeQdrant({"51102": [[_point(1)], [_point(2)], []]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "51102")
        assert [p["id"] for p in points] == [1, 2]
        plan = build_plan("51102", Target("51102", "TERBATAS", 49), points)
        apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert fake.payload_writes[0]["points"] == [1, 2]


# --- innocence ---------------------------------------------------------------


def test_dry_run_writes_nothing():
    fake = FakeQdrant({"25200": [[_point(7)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "TERBATAS", 49), points)
        n = apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=False)
    assert n == 0 and fake.payload_writes == []


def test_a_point_already_agreeing_is_left_alone():
    """Idempotence with teeth: a second run must not re-write, so a diff of
    'points written' stays a real signal rather than a constant."""
    fake = FakeQdrant({"25200": [[_point(7, "TERBATAS", 49)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "TERBATAS", 49), points)
        assert plan.stale_points() == []
        assert apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True) == 0
    assert fake.payload_writes == []


def test_a_code_with_no_points_never_writes_and_never_crashes():
    fake = FakeQdrant({})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "62010")
        plan = build_plan("62010", Target("62010", "TERBUKA", 100), points)
        assert not plan.found
        assert apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True) == 0
    assert fake.payload_writes == []


def test_only_the_two_pma_keys_are_ever_sent():
    """`set_payload` is a MERGE; the request must carry nothing but the two
    fields this tool owns, or it silently becomes an editor of the rest of the
    flat payload."""
    fake = FakeQdrant({"25200": [[_point(7)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "TERBATAS", 49), points)
        apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert set(fake.payload_writes[0]["payload"]) == {"pma_status", "pma_max_asing"}


@pytest.mark.parametrize("cap", [0, 49, 100, "special", None])
def test_the_canonical_cap_is_written_verbatim_never_coerced(cap):
    """0 must stay 0 (`|| 100`-style coercion is how a closed code became
    "100% open" elsewhere in this codebase), and "special" must stay a string
    rather than becoming an invented number."""
    fake = FakeQdrant({"47221": [[_point(3, "TERBUKA", 100)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "47221")
        plan = build_plan("47221", Target("47221", "TERBATAS", cap), points)
        apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert fake.payload_writes[0]["payload"]["pma_max_asing"] == cap


def test_stale_is_judged_on_both_fields_not_just_the_status():
    """A point whose status already reads TERBATAS but whose cap is still 100
    is stale. Judging on the status alone would leave the number — the thing a
    client actually acts on — uncured."""
    fake = FakeQdrant({"25200": [[_point(7, "TERBATAS", 100)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "TERBATAS", 49), points)
    assert plan.stale_points() == [7]
