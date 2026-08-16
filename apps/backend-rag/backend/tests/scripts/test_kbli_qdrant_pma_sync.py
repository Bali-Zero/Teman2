"""Tests for kbli_qdrant_pma_sync.

The dangerous failure here is not a missed update: it is writing a PMA figure
that the canonical does not carry, onto the store `inspect_kbli` prefers over
the KG. So most of this file is refusal and innocence.

Qdrant is mocked entirely via a fake httpx transport — no live Qdrant needed.
"""

from __future__ import annotations

import json
from pathlib import Path
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
    load_dataset,
)

_COLLECTION = "kbli_2025_final_hybrid"
_BASE = "http://qdrant.test"
_HEADERS = {"Content-Type": "application/json"}
_BASIS = "Perpres 49/2021 Lampiran III entry 3"
_VINTAGE = "2021-05-25"


def _pma_fields(status: str = "TERBUKA", cap: Any = 100) -> dict:
    return {
        "pma_status": status,
        "pma_max_asing": cap,
        "pma_verification_status": "located",
        "pma_official_basis": _BASIS,
        "pma_source_vintage": _VINTAGE,
        "pma_cap_special": cap == "special",
        "pma_cap_verified": True,
    }


def _rec(code: str, status: str = "TERBUKA", cap: Any = 100) -> dict:
    return {"kode_kbli_2025": code, **_pma_fields(status, cap)}


def _point(pid: Any, status: str = "TERBUKA", cap: Any = 100) -> dict:
    return {"id": pid, "payload": {**_pma_fields(status, cap), "judul": "x"}}


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


def test_a_canonical_record_without_a_status_clears_stale_pma_claims():
    targets, refusals = build_targets([{"kode_kbli_2025": "25200"}], ["25200"])
    assert refusals == []
    assert targets["25200"].fields == {
        "pma_status": "NOT_VERIFIED",
        "pma_max_asing": None,
        "pma_verification_status": "declared_gap",
        "pma_official_basis": None,
        "pma_source_vintage": None,
        "pma_cap_special": False,
        "pma_cap_verified": False,
    }


def test_a_declared_gap_never_copies_raw_pma_status_or_cap() -> None:
    rec = _rec("01111")
    rec.update(
        {
            "pma_verification_status": "declared_gap",
            "pma_official_basis": None,
            "pma_source_vintage": None,
        }
    )

    targets, refusals = build_targets([rec], ["01111"])

    assert refusals == []
    assert targets["01111"].fields["pma_status"] == "NOT_VERIFIED"
    assert targets["01111"].fields["pma_max_asing"] is None


# --- guilt -------------------------------------------------------------------


def test_a_stale_point_is_rewritten_to_the_canonical_verdict():
    fake = FakeQdrant({"25200": [[_point(7)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "pma", _pma_fields("TERBATAS", 49)), points)
        n = apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert n == 1
    assert fake.payload_writes == [{"payload": _pma_fields("TERBATAS", 49), "points": [7]}]


def test_every_point_of_a_code_is_rewritten_across_scroll_pages():
    """Pagination is not decoration — a code with points on page 2 must not be
    half-cured, which would leave the same code answering two ways."""
    fake = FakeQdrant({"51102": [[_point(1)], [_point(2)], []]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "51102")
        assert [p["id"] for p in points] == [1, 2]
        plan = build_plan("51102", Target("51102", "pma", _pma_fields("TERBATAS", 49)), points)
        apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert fake.payload_writes[0]["points"] == [1, 2]


# --- innocence ---------------------------------------------------------------


def test_dry_run_writes_nothing():
    fake = FakeQdrant({"25200": [[_point(7)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "pma", _pma_fields("TERBATAS", 49)), points)
        n = apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=False)
    assert n == 0 and fake.payload_writes == []


def test_a_point_already_agreeing_is_left_alone():
    """Idempotence with teeth: a second run must not re-write, so a diff of
    'points written' stays a real signal rather than a constant."""
    fake = FakeQdrant({"25200": [[_point(7, "TERBATAS", 49)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "pma", _pma_fields("TERBATAS", 49)), points)
        assert plan.stale_points() == []
        assert apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True) == 0
    assert fake.payload_writes == []


def test_a_code_with_no_points_never_writes_and_never_crashes():
    fake = FakeQdrant({})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "62010")
        plan = build_plan("62010", Target("62010", "pma", _pma_fields()), points)
        assert not plan.found
        assert apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True) == 0
    assert fake.payload_writes == []


def test_only_the_five_pma_evidence_keys_are_ever_sent():
    """The PMA layer owns one five-field evidence tuple and nothing else."""
    fake = FakeQdrant({"25200": [[_point(7)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "pma", _pma_fields("TERBATAS", 49)), points)
        apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert set(fake.payload_writes[0]["payload"]) == set(_pma_fields())


@pytest.mark.parametrize("cap", [0, 49, 100, "special", None])
def test_the_canonical_cap_is_written_verbatim_never_coerced(cap):
    """0 must stay 0 (`|| 100`-style coercion is how a closed code became
    "100% open" elsewhere in this codebase), and "special" must stay a string
    rather than becoming an invented number."""
    fake = FakeQdrant({"47221": [[_point(3, "TERBUKA", 100)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "47221")
        plan = build_plan("47221", Target("47221", "pma", _pma_fields("TERBATAS", cap)), points)
        apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert fake.payload_writes[0]["payload"]["pma_max_asing"] == cap


def test_stale_is_judged_on_both_fields_not_just_the_status():
    """A point whose status already reads TERBATAS but whose cap is still 100
    is stale. Judging on the status alone would leave the number — the thing a
    client actually acts on — uncured."""
    fake = FakeQdrant({"25200": [[_point(7, "TERBATAS", 100)]]})
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "25200")
        plan = build_plan("25200", Target("25200", "pma", _pma_fields("TERBATAS", 49)), points)
    assert plan.stale_points() == [7]


# --- the bali layer ----------------------------------------------------------
#
# Added 2026-08-03 with the layer itself, and with the tool it replaced:
# `apps/backend-rag/scripts/patch_qdrant_bali_l4.py` re-derived the verdict from
# `l4_bali.verdict` instead of copying `l4_bali.status`. The first test below is
# that defect, frozen: it is the shape that would have published 118 blocked
# codes as registrable.


def _bali_rec(
    code: str,
    status: object,
    blocked: object,
    reason: object = "r",
    verdict: str | None = None,
    needs_review: object = False,
) -> dict:
    rec: dict = {
        "kode_kbli_2025": code,
        **_pma_fields(),
        "l4_bali": {
            "status": status,
            "blocked": blocked,
            "needs_review": needs_review,
            "reason": reason,
        },
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


def test_a_verified_record_without_a_bali_status_clears_stale_bali_claims():
    """Absence is an authoritative neutral value, never an inferred open verdict."""
    targets, refusals = build_targets([_rec("93122")], ["93122"], "bali")
    assert refusals == []
    assert targets["93122"].fields == {
        "bali_status": None,
        "bali_blocked": None,
        "bali_needs_review": None,
        "bali_reason": "",
        "has_bali_l4": False,
    }


def test_a_declared_gap_clears_all_flat_bali_claims():
    rec = _bali_rec("01111", "OK_or_HIGHER_RISK", False)
    rec.update(
        {
            "pma_verification_status": "declared_gap",
            "pma_official_basis": None,
            "pma_source_vintage": None,
        }
    )

    targets, refusals = build_targets([rec], ["01111"], "bali")

    assert refusals == []
    assert targets["01111"].fields == {
        "bali_status": None,
        "bali_blocked": None,
        "bali_needs_review": None,
        "bali_reason": "",
        "has_bali_l4": False,
    }


@pytest.mark.parametrize("blocked", ["false", "true", 0, 1, None])
def test_the_bali_layer_never_truthiness_coerces_blocked(blocked: object) -> None:
    targets, refusals = build_targets(
        [_bali_rec("86995", "CHIUSO_MORATORIA_BALI", blocked)],
        ["86995"],
        "bali",
    )

    assert refusals == []
    assert targets["86995"].fields["bali_status"] is None
    assert targets["86995"].fields["bali_blocked"] is None
    assert targets["86995"].fields["has_bali_l4"] is False


@pytest.mark.parametrize("needs_review", ["false", "true", 0, 1, None])
def test_the_bali_layer_never_truthiness_coerces_needs_review(
    needs_review: object,
) -> None:
    targets, refusals = build_targets(
        [
            _bali_rec(
                "86995",
                "CHIUSO_MORATORIA_BALI",
                True,
                needs_review=needs_review,
            )
        ],
        ["86995"],
        "bali",
    )

    assert refusals == []
    assert targets["86995"].fields["bali_status"] is None
    assert targets["86995"].fields["bali_needs_review"] is None
    assert targets["86995"].fields["has_bali_l4"] is False


def test_sync_disclosures_match_the_shared_runtime_contract() -> None:
    from backend.services.kbli_pma_disclosure import disclose_bali, disclose_pma

    located = _bali_rec("86995", "CHIUSO_MORATORIA_BALI", True, "moratorium")
    pma_target, _ = build_targets([located], ["86995"], "pma")
    bali_target, _ = build_targets([located], ["86995"], "bali")
    shared_pma = disclose_pma(located)

    assert pma_target["86995"].fields == {
        key: shared_pma[key]
        for key in (
            "pma_status",
            "pma_max_asing",
            "pma_verification_status",
            "pma_official_basis",
            "pma_source_vintage",
            "pma_cap_special",
            "pma_cap_verified",
        )
    }
    assert bali_target["86995"].fields == disclose_bali(located)

    unverified = located | {"pma_cap_verified": False}
    unverified_target, _ = build_targets([unverified], ["86995"], "pma")
    shared_unverified = disclose_pma(unverified)
    assert unverified_target["86995"].fields == {
        key: shared_unverified[key]
        for key in (
            "pma_status",
            "pma_max_asing",
            "pma_verification_status",
            "pma_official_basis",
            "pma_source_vintage",
            "pma_cap_special",
            "pma_cap_verified",
        )
    }


def test_the_bali_layer_writes_its_five_keys_and_no_pma_key():
    """Layer isolation, asserted on the wire. A Bali cure that also carried a
    `pma_status` would silently make the national answer this tool's business."""
    fake = FakeQdrant({"86995": [[{"id": 5, "payload": {"bali_status": "CHIUSO_PMA_NO_BESAR"}}]]})
    targets, _ = build_targets(
        [_bali_rec("86995", "CHIUSO_MORATORIA_BALI", True)], ["86995"], "bali"
    )
    with fake.client() as http:
        points = find_points_for_code(http, _BASE, _HEADERS, _COLLECTION, "86995")
        plan = build_plan("86995", targets["86995"], points)
        assert apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True) == 1
    written = fake.payload_writes[0]["payload"]
    assert set(written) == {
        "bali_status",
        "bali_blocked",
        "bali_needs_review",
        "bali_reason",
        "has_bali_l4",
    }
    assert not any(k.startswith("pma_") for k in written)


def test_a_bali_point_already_agreeing_is_left_alone():
    """Innocence: idempotence on the new layer too, so 'points written' stays a
    signal rather than a constant."""
    payload = {
        "bali_status": "CHIUSO_MORATORIA_BALI",
        "bali_blocked": True,
        "bali_needs_review": False,
        "bali_reason": "r",
        "has_bali_l4": True,
    }
    fake = FakeQdrant({"86995": [[{"id": 5, "payload": payload}]]})
    targets, _ = build_targets(
        [_bali_rec("86995", "CHIUSO_MORATORIA_BALI", True)], ["86995"], "bali"
    )
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
        "bali_needs_review": False,
        "bali_reason": "OSS has no Usaha Besar scale row",
        "has_bali_l4": True,
    }
    fake = FakeQdrant({"86995": [[{"id": 5, "payload": payload}]]})
    targets, _ = build_targets(
        [
            _bali_rec(
                "86995", "CHIUSO_MORATORIA_BALI", True, reason="blocked by the Bali moratorium"
            )
        ],
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
    """Regression pin: the default layer owns one complete evidence tuple."""
    targets, _ = build_targets([_rec("25200", "TERBATAS", 49)], ["25200"])
    assert targets["25200"].layer == "pma"
    assert targets["25200"].fields == _pma_fields("TERBATAS", 49)


# ---------------------------------------------------------------------------
# PROSE REPAIR — the same fact in the blob the retriever hands to the LLM.
#
# Measured on prod 2026-08-05: 20 codes had the flat keys cured by `--layer pma`
# and their `content`/`text` blob still opened `## Status PMA: TERBUKA` /
# `- Kepemilikan asing maksimal: 100` — including `25200` (arms, real cap 49)
# and `79122` (Umrah travel, real cap 0). One fact, two representations, one
# cured. These tests exist so that cannot recur silently.
# ---------------------------------------------------------------------------

from backend.scripts.kbli_qdrant_pma_sync import (  # noqa: E402
    PROSE_KEYS,
    certified_intelligence_block,
    render_pma_block,
    rewrite_pma_prose,
    rewrite_whatchanged_prose,
)
from backend.services.kbli_editorial_certification import load_editorial_registry  # noqa: E402

_BLOB_OPEN = """[CONTEXT: KBLI 2025 - Kode 25200 - Industri Senjata dan Amunisi]

# KBLI 25200: Industri Senjata dan Amunisi

## Deskripsi (BPS)
Kelompok ini mencakup pembuatan senjata dan amunisi.

**Sektor:** I.C

## Status PMA: TERBUKA
- Kepemilikan asing maksimal: 100

## Perizinan per Skala Usaha (PP 28/2025)
### Skala: Besar
- Kategori risiko: Tinggi

## Intelligence 2026
- whatItMeans: Making weapons and ammunition.
- whatChanged: Direct 1:1 match from KBLI 2020 - code and scope unchanged.
- baliContext: Not a Bali activity.
"""


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    root = next(
        (
            parent
            for parent in here.parents
            if (parent / "data/source_documents/KBLI_2025_FINAL_CLEAN.json").is_file()
        ),
        None,
    )
    assert root is not None
    return root


def _real_record(code: str) -> dict:
    payload = json.loads(
        (_repo_root() / "data/source_documents/KBLI_2025_FINAL_CLEAN.json").read_text(
            encoding="utf-8"
        )
    )
    return next(record for record in payload["data"] if record["kode_kbli_2025"] == code)


def _blob_point(pid: Any, blob: str, status: str = "TERBUKA", cap: Any = 100) -> dict:
    payload: dict[str, Any] = _pma_fields(status, cap)
    for key in PROSE_KEYS:
        payload[key] = blob
    return {"id": pid, "payload": payload}


def test_the_blob_still_saying_terbuka_100_is_repaired_not_left_behind():
    """The P0 this whole section exists for: an arms factory advertised at 100%
    foreign ownership in the text the LLM is handed, while the flat field
    already said 49."""
    rec = _rec("25200", status="TERBATAS", cap=49)
    point = _blob_point("p1", _BLOB_OPEN, status="TERBATAS", cap=49)  # flat ALREADY cured
    plan = build_plan("25200", Target("25200", "pma", _pma_fields("TERBATAS", 49), rec), [point])

    assert plan.stale_points() == ["p1"], "a cured flat field must not excuse an uncured blob"
    for key in PROSE_KEYS:
        new = plan.prose["p1"][key]
        assert "## Status PMA: TERBATAS" in new
        assert "- Kepemilikan asing maksimal: 49" in new
        assert "TERBUKA" not in new
        assert "maksimal: 100" not in new
        # Non-editorial sections survive, but a synthetic/raw Intelligence
        # section has no matching content certificate and is retracted atomically.
        assert "Industri Senjata dan Amunisi" in new
        assert "## Perizinan per Skala Usaha (PP 28/2025)" in new
        assert "## Intelligence 2026" not in new
        assert "- whatItMeans: Making weapons and ammunition." not in new


def test_a_zero_percent_cap_is_rendered_without_falsy_coercion():
    """`79122` (Umrah/Hajj travel) is capped at 0; zero is a real cap."""
    rec = _rec("79122", status="TERBATAS", cap=0)
    out = rewrite_pma_prose(rec, _BLOB_OPEN)
    assert "## Status PMA: TERBATAS" in out
    assert "Kepemilikan asing maksimal: 0%" in out
    assert render_pma_block(rec) == [
        "## Status PMA: TERBATAS",
        "- Kepemilikan asing maksimal: 0%",
    ]


def test_a_special_cap_is_rendered_as_a_non_percentage_condition():
    rec = _rec("47221", status="TERBATAS", cap="special")

    out = rewrite_pma_prose(rec, _BLOB_OPEN)

    assert "Kepemilikan asing: kondisi khusus non-persentase" in out
    assert "special%" not in out


def test_a_declared_gap_withholds_raw_status_and_cap_from_the_blob():
    """A canonical raw value is not a publishable verdict without its located
    basis and vintage. The repair must remove both values from retriever prose."""
    rec = {
        "kode_kbli_2025": "01111",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "declared_gap",
        "pma_official_basis": None,
        "pma_source_vintage": None,
    }
    out = rewrite_pma_prose(rec, _BLOB_OPEN)
    assert out is not None
    assert "## Status PMA: NOT_VERIFIED" in out
    assert "Whole-code foreign ownership is withheld" in out
    assert "## Status PMA: TERBUKA" not in out
    assert "Kepemilikan asing maksimal: 100" not in out


def test_an_unknown_located_status_is_withheld_from_the_blob():
    rec = {
        "kode_kbli_2025": "01111",
        "pma_status": "FUTURE_STATUS",
        "pma_max_asing": 100,
        "pma_verification_status": "located",
        "pma_official_basis": _BASIS,
        "pma_source_vintage": _VINTAGE,
    }

    out = rewrite_pma_prose(rec, _BLOB_OPEN)

    assert out is not None
    assert "## Status PMA: NOT_VERIFIED" in out
    assert "FUTURE_STATUS" not in out
    assert "Kepemilikan asing maksimal: 100" not in out


@pytest.mark.parametrize(
    ("basis", "vintage"),
    [({"locator": "not text"}, _VINTAGE), (_BASIS, ["2021-05-25"])],
)
def test_non_text_provenance_never_verifies_retriever_prose(basis, vintage):
    rec = {
        "kode_kbli_2025": "01111",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "located",
        "pma_official_basis": basis,
        "pma_source_vintage": vintage,
    }

    assert render_pma_block(rec) == [
        "## Status PMA: NOT_VERIFIED",
        "- Whole-code foreign ownership is withheld: no located official basis and source vintage are recorded.",
    ]


def test_a_declared_gap_removes_editorial_and_the_whole_bali_verdict():
    rec = {
        "kode_kbli_2025": "01111",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "declared_gap",
        "pma_official_basis": None,
        "pma_source_vintage": None,
        "l4_bali": {
            "status": "OK_or_HIGHER_RISK",
            "blocked": False,
            "reason": "UNSAFE_BALI_REASON asserting national openness",
        },
    }
    legacy = (
        _BLOB_OPEN.replace(
            "Direct 1:1 match from KBLI 2020 - code and scope unchanged.",
            "UNSAFE_EDITORIAL_ASSERTION",
        )
        + """
## Status PMA di Bali (L4 — moratorium provinsi)
- Status Bali: OK_or_HIGHER_RISK
- Alasan: UNSAFE_BALI_REASON asserting national openness
- Catatan: legacy prose.
"""
    )

    out = rewrite_pma_prose(rec, legacy)

    assert out is not None
    assert "## Status PMA: NOT_VERIFIED" in out
    assert "## Intelligence 2026" not in out
    assert "UNSAFE_EDITORIAL_ASSERTION" not in out
    assert "UNSAFE_BALI_REASON" not in out
    assert "- Alasan:" not in out
    assert "Status Bali: OK_or_HIGHER_RISK" not in out
    assert "## Status PMA di Bali" not in out


def test_a_truncated_legacy_gap_with_unsafe_editorial_is_refused():
    rec = {
        "kode_kbli_2025": "01111",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "declared_gap",
        "l4_bali": {
            "status": "OK_or_HIGHER_RISK",
            "blocked": False,
            "reason": "UNSAFE_BALI_REASON",
        },
    }
    truncated = (
        _BLOB_OPEN
        + "\n## Status PMA di Bali (L4 — moratorium provinsi)\n"
        + "- Status Bali: OK_or_HIGHER_RISK\n"
        + "- Alasan: UNSAFE_BALI_REASON\n"
        + "(... dipotong untuk batas panjang.)"
    )

    assert rewrite_pma_prose(rec, truncated) is None


def test_a_point_whose_blob_already_tells_the_truth_is_not_rewritten():
    """Innocence: the repair must be a no-op on a truthful blob, or every run
    would rewrite the whole collection and the diff would stop meaning anything."""
    rec = _rec("25200", status="TERBATAS", cap=49)
    cured = rewrite_pma_prose(rec, _BLOB_OPEN)
    point = _blob_point("p1", cured, status="TERBATAS", cap=49)
    plan = build_plan("25200", Target("25200", "pma", _pma_fields("TERBATAS", 49), rec), [point])
    assert plan.prose == {}
    assert plan.stale_points() == []


def test_a_blob_without_the_owned_block_is_REFUSED_not_guessed_at():
    """A blob we cannot locate the block in is a blob we do not understand.
    Refusing is the whole point — writing into it would be a guess about a
    client-facing store."""
    rec = _rec("25200", status="TERBATAS", cap=49)
    point = _blob_point(
        "p1", "# KBLI 25200\n\nno pma section here at all\n", status="TERBATAS", cap=49
    )
    plan = build_plan("25200", Target("25200", "pma", _pma_fields("TERBATAS", 49), rec), [point])
    assert plan.unshaped == ["p1"]
    assert plan.prose == {}
    assert plan.stale_points() == [], "an unshaped point must not be written"


def test_the_whatchanged_layer_retracts_an_uncertified_editorial_section():
    rec = {
        "kode_kbli_2025": "25200",
        "intel_2026": {"whatChanged": "Our records do not support this code number carrying over."},
    }
    out = rewrite_whatchanged_prose(rec, _BLOB_OPEN)
    assert out is not None
    assert "## Intelligence 2026" not in out
    assert "Direct 1:1 match" not in out
    assert "Making weapons and ammunition" not in out
    # The historical layer name does not make it own the PMA block.
    assert "## Status PMA: TERBUKA" in out


def test_the_whatchanged_layer_replaces_the_complete_certified_editorial_block():
    registry = load_editorial_registry()
    rec = _real_record("25200")

    out = rewrite_whatchanged_prose(rec, _BLOB_OPEN, registry)

    assert out is not None
    assert "- whatChanged: Direct 1:1 match from KBLI 2020 — code and scope unchanged." in out
    assert "Ask me about KBLI 25200: its official scope" in out
    assert "Making weapons and ammunition." not in out
    assert "Looking into Industri Senjata" not in out
    assert certified_intelligence_block(rec, registry)[0] == "## Intelligence 2026"


def test_frozen_47222_cannot_publish_raw_zero_percent_prose_without_a_certificate():
    """Regression for the final OpenAI P1 on frozen HEAD 3d5b8fb9."""
    registry = load_editorial_registry()
    rec = _real_record("47222")
    unsafe = _BLOB_OPEN.replace(
        "- whatChanged: Direct 1:1 match from KBLI 2020 - code and scope unchanged.",
        f"- whatChanged: {rec['intel_2026']['whatChanged']}",
    )

    targets, refusals = build_targets(
        [rec],
        ["47222"],
        "whatchanged",
        registry,
    )
    plan = build_plan("47222", targets["47222"], [_blob_point("p1", unsafe)])
    out = plan.prose["p1"]["content"]

    assert refusals == []
    assert out is not None
    assert "## Intelligence 2026" not in out
    assert "foreign investment is 0%" not in out
    assert certified_intelligence_block(rec, registry) == []
    assert plan.prose["p1"]["text"] == out


def test_dataset_bytes_are_bound_to_the_registry_before_any_target_is_built(tmp_path: Path):
    registry = load_editorial_registry()
    canonical = _repo_root() / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"

    assert len(load_dataset(str(canonical), registry)) == 1559

    tampered = tmp_path / "tampered.json"
    tampered.write_bytes(canonical.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="do not match the editorial review registry"):
        load_dataset(str(tampered), registry)


def test_the_whatchanged_layer_owns_no_flat_key():
    """It has none in the live payload (29 flat keys, measured 2026-08-05), so a
    run must not invent one — writing `whatChanged` as a flat field would create
    a second representation nobody reads and nobody keeps in step."""
    targets, refusals = build_targets(
        [{"kode_kbli_2025": "25200", "intel_2026": {"whatChanged": "x"}}],
        ["25200"],
        layer="whatchanged",
    )
    assert refusals == []
    assert targets["25200"].fields == {}


def test_a_record_without_whatchanged_is_refused_not_blanked():
    _, refusals = build_targets(
        [{"kode_kbli_2025": "25200", "intel_2026": {}}], ["25200"], layer="whatchanged"
    )
    assert len(refusals) == 1 and "whatChanged" in refusals[0]


def test_each_point_gets_its_OWN_repaired_blob_never_a_shared_body():
    """The blob is per-point. A single shared `set_payload` body would stamp one
    point's text onto its siblings — silently replacing another point's content
    with a near-copy."""
    rec = _rec("25200", status="TERBATAS", cap=49)
    other = _BLOB_OPEN.replace("Industri Senjata dan Amunisi", "SIBLING CHUNK")
    points = [
        _blob_point("p1", _BLOB_OPEN, "TERBATAS", 49),
        _blob_point("p2", other, "TERBATAS", 49),
    ]
    plan = build_plan("25200", Target("25200", "pma", _pma_fields("TERBATAS", 49), rec), points)
    fake = FakeQdrant({})
    with fake.client() as http:
        written = apply_plan(http, _BASE, _HEADERS, _COLLECTION, plan, apply=True)
    assert written == 2
    bodies = fake.payload_writes
    assert [b["points"] for b in bodies] == [["p1"], ["p2"]]
    assert "SIBLING CHUNK" in bodies[1]["payload"]["content"]
    assert "SIBLING CHUNK" not in bodies[0]["payload"]["content"]


def test_the_prose_repair_matches_the_real_generator_on_real_canonical_records():
    """THE ORGAN. These renderers must emit exactly what a full re-index emits,
    or the next re-index reverts the cure and the two disagree again.

    So this loads the REAL canonical dataset, runs the REAL
    `build_embedding_text`, and requires both repairs to be no-ops on its fresh
    output. This includes the exact zero-cap and special non-percentage shapes;
    a hand-written repair that formats either differently would still diverge
    in production.
    """
    import types

    root = _repo_root()

    gen_path = root / "apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py"
    mod = types.ModuleType("rix_for_test")
    # The script resolves the repo root via resolve_repo_root(), which honours
    # KBLI_REPO_ROOT and otherwise walks up from __file__ looking for a marker
    # file.  Set the env override to the real root and a fake __file__ to avoid
    # importing the module for real (it would also try to load .env at import
    # time from the resolved backend-rag dir).
    mod.__dict__["__file__"] = "/fake/reindex.py"
    import os

    old_env = os.environ.get("KBLI_REPO_ROOT")
    os.environ["KBLI_REPO_ROOT"] = str(root)
    try:
        exec(compile(gen_path.read_text(encoding="utf-8"), str(gen_path), "exec"), mod.__dict__)
    finally:
        if old_env is None:
            os.environ.pop("KBLI_REPO_ROOT", None)
        else:
            os.environ["KBLI_REPO_ROOT"] = old_env
    build_embedding_text = mod.build_embedding_text

    records = json.loads(
        (root / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json").read_text(
            encoding="utf-8"
        )
    )["data"]
    registry = load_editorial_registry()

    checked_pma = checked_wc = truncated = eligible_wc = 0
    zero_cap_seen = False
    for rec in records:
        fresh = build_embedding_text(rec, registry)
        if rec.get("pma_status"):
            assert rewrite_pma_prose(rec, fresh, registry) == fresh, (
                f"{rec['kode_kbli_2025']}: the PMA repair is not a no-op on freshly generated text — "
                "it would fight the next re-index"
            )
            checked_pma += 1
            if rec.get("pma_max_asing") in (0, None):
                zero_cap_seen = True
        if rec.get("kode_kbli_2025") in registry["canonicalIntel"] and (
            rec.get("intel_2026") or {}
        ).get("whatChanged"):
            eligible_wc += 1
            out = rewrite_whatchanged_prose(rec, fresh, registry)
            if "\n- whatChanged: " not in fresh:
                # The generator CAPS the embedding text (`build_embedding_text`
                # truncates long per_skala blocks with "... dipotong untuk batas
                # panjang"). If no Intelligence section exists, there is
                # nothing safe to address and the writer refuses. If the cap
                # falls inside an exact certified prefix before whatChanged,
                # the only valid operation is an unchanged no-op.
                if "\n## Intelligence 2026\n" in fresh:
                    assert out == fresh, (
                        f"{rec['kode_kbli_2025']}: changed an exact certified truncated prefix"
                    )
                else:
                    assert out is None, (
                        f"{rec['kode_kbli_2025']}: repaired editorial prose into a blob that has none"
                    )
                truncated += 1
                continue
            assert out == fresh, (
                f"{rec['kode_kbli_2025']}: the whatChanged repair is not a no-op on freshly generated text"
            )
            checked_wc += 1

    assert checked_pma > 1400
    assert eligible_wc > 0 and checked_wc + truncated == eligible_wc, (
        f"eligible editorial coverage drifted: eligible={eligible_wc} "
        f"checked={checked_wc} truncated={truncated}"
    )
    assert zero_cap_seen, "no zero/absent cap in the corpus — the edge-cap branch went untested"
    assert truncated > 0, (
        "no truncated record in the corpus — the refusal branch went untested, and it is the "
        "branch that stops the tool inventing content past a truncation marker"
    )
