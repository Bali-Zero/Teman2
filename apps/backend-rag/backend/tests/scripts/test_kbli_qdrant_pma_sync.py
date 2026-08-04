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
        plan = build_plan("25200", Target("25200", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}), points)
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
        plan = build_plan("51102", Target("51102", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}), points)
        apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert fake.payload_writes[0]["points"] == [1, 2]


# --- innocence ---------------------------------------------------------------


def test_dry_run_writes_nothing():
    fake = FakeQdrant({"25200": [[_point(7)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}), points)
        n = apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=False)
    assert n == 0 and fake.payload_writes == []


def test_a_point_already_agreeing_is_left_alone():
    """Idempotence with teeth: a second run must not re-write, so a diff of
    'points written' stays a real signal rather than a constant."""
    fake = FakeQdrant({"25200": [[_point(7, "TERBATAS", 49)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}), points)
        assert plan.stale_points() == []
        assert apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True) == 0
    assert fake.payload_writes == []


def test_a_code_with_no_points_never_writes_and_never_crashes():
    fake = FakeQdrant({})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "62010")
        plan = build_plan("62010", Target("62010", "pma", {"pma_status": "TERBUKA", "pma_max_asing": 100}), points)
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
        plan = build_plan("25200", Target("25200", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}), points)
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
        plan = build_plan("47221", Target("47221", "pma", {"pma_status": "TERBATAS", "pma_max_asing": cap}), points)
        apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert fake.payload_writes[0]["payload"]["pma_max_asing"] == cap


def test_stale_is_judged_on_both_fields_not_just_the_status():
    """A point whose status already reads TERBATAS but whose cap is still 100
    is stale. Judging on the status alone would leave the number — the thing a
    client actually acts on — uncured."""
    fake = FakeQdrant({"25200": [[_point(7, "TERBATAS", 100)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}), points)
    assert plan.stale_points() == [7]


# --- the bali layer ----------------------------------------------------------
#
# Added 2026-08-03 with the layer itself, and with the tool it replaced:
# `apps/backend-rag/scripts/patch_qdrant_bali_l4.py` re-derived the verdict from
# `l4_bali.verdict` instead of copying `l4_bali.status`. The first test below is
# that defect, frozen: it is the shape that would have published 118 blocked
# codes as registrable.


def _bali_rec(code: str, status: str, blocked: bool, reason: str = "r", verdict: str | None = None) -> dict:
    rec: dict = {
        "kode_kbli_2025": code,
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "l4_bali": {"status": status, "blocked": blocked, "reason": reason},
    }
    if verdict is not None:
        rec["l4_bali"]["verdict"] = verdict
    return rec


def test_the_bali_layer_copies_status_and_ignores_the_stale_verdict_field():
    """THE test this layer exists for. `86995` was re-decided to
    CHIUSO_MORATORIA_BALI while its `l4_bali.verdict` still reads NO_BESAR; a
    record with NO verdict at all (237 of them on the canonical, 118 blocked)
    must still publish its status rather than falling through to a default."""
    rec_stale = _bali_rec("86995", "CHIUSO_MORATORIA_BALI", True, verdict="NO_BESAR")
    rec_none = _bali_rec("93122", "NON_CLASSIFICABILE", True)
    targets, refusals = build_targets([rec_stale, rec_none], ["86995", "93122"], "bali")
    assert refusals == []
    assert targets["86995"].fields["bali_status"] == "CHIUSO_MORATORIA_BALI"
    assert targets["93122"].fields["bali_status"] == "NON_CLASSIFICABILE"
    for t in targets.values():
        assert t.fields["bali_blocked"] is True
        assert "verdict" not in str(t.fields)


def test_a_record_without_a_bali_status_is_refused_not_defaulted():
    """The 118-code failure mode as a refusal: absent verdict must stop the run,
    never resolve to 'open'."""
    targets, refusals = build_targets([{"kode_kbli_2025": "93122"}], ["93122"], "bali")
    assert targets == {}
    assert any("no l4_bali.status" in r for r in refusals)


def test_the_bali_layer_writes_its_four_keys_and_no_pma_key():
    """Layer isolation, asserted on the wire. A Bali cure that also carried a
    `pma_status` would silently make the national answer this tool's business."""
    fake = FakeQdrant({"86995": [[{"id": 5, "payload": {"bali_status": "CHIUSO_PMA_NO_BESAR"}}]]})
    targets, _ = build_targets([_bali_rec("86995", "CHIUSO_MORATORIA_BALI", True)], ["86995"], "bali")
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "86995")
        plan = build_plan("86995", targets["86995"], points)
        assert apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True) == 1
    written = fake.payload_writes[0]["payload"]
    assert set(written) == {"bali_status", "bali_blocked", "bali_reason", "has_bali_l4"}
    assert not any(k.startswith("pma_") for k in written)


def test_a_bali_point_already_agreeing_is_left_alone():
    """Innocence: idempotence on the new layer too, so 'points written' stays a
    signal rather than a constant."""
    payload = {
        "bali_status": "CHIUSO_MORATORIA_BALI",
        "bali_blocked": True,
        "bali_reason": "r",
        "has_bali_l4": True,
    }
    fake = FakeQdrant({"86995": [[{"id": 5, "payload": payload}]]})
    targets, _ = build_targets([_bali_rec("86995", "CHIUSO_MORATORIA_BALI", True)], ["86995"], "bali")
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "86995")
        plan = build_plan("86995", targets["86995"], points)
        assert plan.stale_points() == []
        assert apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True) == 0
    assert fake.payload_writes == []


def test_a_reason_only_change_is_still_stale():
    """The status can be right while the sentence under it still names the
    withdrawn cause — which is the half of the cure a client actually reads."""
    payload = {
        "bali_status": "CHIUSO_MORATORIA_BALI",
        "bali_blocked": True,
        "bali_reason": "OSS has no Usaha Besar scale row",
        "has_bali_l4": True,
    }
    fake = FakeQdrant({"86995": [[{"id": 5, "payload": payload}]]})
    targets, _ = build_targets(
        [_bali_rec("86995", "CHIUSO_MORATORIA_BALI", True, reason="blocked by the Bali moratorium")],
        ["86995"],
        "bali",
    )
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "86995")
        plan = build_plan("86995", targets["86995"], points)
    assert plan.stale_points() == [5]


def test_an_unknown_layer_raises_instead_of_silently_syncing_pma():
    """A typo'd --layer must not quietly write the default layer's fields."""
    with pytest.raises(ValueError, match="unknown layer"):
        build_targets([_rec("25200")], ["25200"], "balii")


def test_the_pma_layer_is_unchanged_by_the_generalisation():
    """Regression pin for the refactor: the default layer still reads exactly
    the two fields it always did, from the same canonical keys."""
    targets, _ = build_targets([_rec("25200", "TERBATAS", 49)], ["25200"])
    assert targets["25200"].layer == "pma"
    assert targets["25200"].fields == {"pma_status": "TERBATAS", "pma_max_asing": 49}
