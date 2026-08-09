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
    render_pma_block,
    rewrite_pma_prose,
    rewrite_whatchanged_prose,
)

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


def _blob_point(pid: Any, blob: str, status: str = "TERBUKA", cap: Any = 100) -> dict:
    payload: dict[str, Any] = {"pma_status": status, "pma_max_asing": cap}
    for key in PROSE_KEYS:
        payload[key] = blob
    return {"id": pid, "payload": payload}


def test_the_blob_still_saying_terbuka_100_is_repaired_not_left_behind():
    """The P0 this whole section exists for: an arms factory advertised at 100%
    foreign ownership in the text the LLM is handed, while the flat field
    already said 49."""
    rec = _rec("25200", status="TERBATAS", cap=49)
    point = _blob_point("p1", _BLOB_OPEN, status="TERBATAS", cap=49)  # flat ALREADY cured
    plan = build_plan("25200", Target("25200", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}, rec), [point])

    assert plan.stale_points() == ["p1"], "a cured flat field must not excuse an uncured blob"
    for key in PROSE_KEYS:
        new = plan.prose["p1"][key]
        assert "## Status PMA: TERBATAS" in new
        assert "- Kepemilikan asing maksimal: 49" in new
        assert "TERBUKA" not in new
        assert "maksimal: 100" not in new
        # everything outside the owned block survives untouched
        assert "Industri Senjata dan Amunisi" in new
        assert "## Perizinan per Skala Usaha (PP 28/2025)" in new
        assert "- whatItMeans: Making weapons and ammunition." in new


def test_a_zero_percent_cap_omits_the_line_because_the_generator_omits_it():
    """`build_embedding_text` writes the cap line under `if
    entry.get("pma_max_asing")`, so 0 is FALSY and the line is absent. `79122`
    (Umrah/Hajj travel) is capped at 0: a repair that wrote `maksimal: 0` would
    diverge from the next re-index and re-open this exact gap."""
    rec = _rec("79122", status="TERBATAS", cap=0)
    out = rewrite_pma_prose(rec, _BLOB_OPEN)
    assert "## Status PMA: TERBATAS" in out
    assert "Kepemilikan asing maksimal" not in out
    assert render_pma_block(rec) == ["## Status PMA: TERBATAS"]


def test_a_point_whose_blob_already_tells_the_truth_is_not_rewritten():
    """Innocence: the repair must be a no-op on a truthful blob, or every run
    would rewrite the whole collection and the diff would stop meaning anything."""
    rec = _rec("25200", status="TERBATAS", cap=49)
    cured = rewrite_pma_prose(rec, _BLOB_OPEN)
    point = _blob_point("p1", cured, status="TERBATAS", cap=49)
    plan = build_plan("25200", Target("25200", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}, rec), [point])
    assert plan.prose == {}
    assert plan.stale_points() == []


def test_a_blob_without_the_owned_block_is_REFUSED_not_guessed_at():
    """A blob we cannot locate the block in is a blob we do not understand.
    Refusing is the whole point — writing into it would be a guess about a
    client-facing store."""
    rec = _rec("25200", status="TERBATAS", cap=49)
    point = _blob_point("p1", "# KBLI 25200\n\nno pma section here at all\n", status="TERBATAS", cap=49)
    plan = build_plan("25200", Target("25200", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}, rec), [point])
    assert plan.unshaped == ["p1"]
    assert plan.prose == {}
    assert plan.stale_points() == [], "an unshaped point must not be written"


def test_the_whatchanged_layer_replaces_only_its_own_line():
    rec = {
        "kode_kbli_2025": "25200",
        "intel_2026": {"whatChanged": "Our records do not support this code number carrying over."},
    }
    out = rewrite_whatchanged_prose(rec, _BLOB_OPEN)
    assert "- whatChanged: Our records do not support this code number carrying over." in out
    assert "Direct 1:1 match" not in out
    # the neighbours in the same section are untouched
    assert "- whatItMeans: Making weapons and ammunition." in out
    assert "- baliContext: Not a Bali activity." in out
    # and it does not touch the PMA block it does not own
    assert "## Status PMA: TERBUKA" in out


def test_the_whatchanged_layer_owns_no_flat_key():
    """It has none in the live payload (29 flat keys, measured 2026-08-05), so a
    run must not invent one — writing `whatChanged` as a flat field would create
    a second representation nobody reads and nobody keeps in step."""
    targets, refusals = build_targets(
        [{"kode_kbli_2025": "25200", "intel_2026": {"whatChanged": "x"}}], ["25200"], layer="whatchanged"
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
    points = [_blob_point("p1", _BLOB_OPEN, "TERBATAS", 49), _blob_point("p2", other, "TERBATAS", 49)]
    plan = build_plan("25200", Target("25200", "pma", {"pma_status": "TERBATAS", "pma_max_asing": 49}, rec), points)
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
    output. It is what caught the falsy-zero trap: `build_embedding_text` omits
    the cap line when the cap is 0, and a repair that emitted `maksimal: 0`
    passes every hand-written test above and still diverges in production.
    """
    import pathlib
    import types

    here = pathlib.Path(__file__).resolve()
    root = next(
        (p for p in here.parents if (p / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json").is_file()),
        None,
    )
    assert root is not None, f"canonical dataset not found walking up from {here}"

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
        (root / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json").read_text(encoding="utf-8")
    )["data"]

    checked_pma = checked_wc = truncated = 0
    zero_cap_seen = False
    for rec in records:
        fresh = build_embedding_text(rec)
        if rec.get("pma_status"):
            assert rewrite_pma_prose(rec, fresh) == fresh, (
                f"{rec['kode_kbli_2025']}: the PMA repair is not a no-op on freshly generated text — "
                "it would fight the next re-index"
            )
            checked_pma += 1
            if rec.get("pma_max_asing") in (0, None):
                zero_cap_seen = True
        if (rec.get("intel_2026") or {}).get("whatChanged"):
            out = rewrite_whatchanged_prose(rec, fresh)
            if "\n- whatChanged: " not in fresh:
                # The generator CAPS the embedding text (`build_embedding_text`
                # truncates long per_skala blocks with "... dipotong untuk batas
                # panjang"), so for 101 of 1,559 records the Intelligence 2026
                # section never makes it into the blob at all. There is no line
                # to repair, and the tool must REFUSE rather than append one —
                # appending would put text past a truncation marker, where a
                # reader has been told the document stops.
                assert out is None, (
                    f"{rec['kode_kbli_2025']}: repaired a whatChanged line into a blob that has none"
                )
                truncated += 1
                continue
            assert out == fresh, (
                f"{rec['kode_kbli_2025']}: the whatChanged repair is not a no-op on freshly generated text"
            )
            checked_wc += 1

    assert checked_pma > 1400 and checked_wc > 1400, (
        f"corpus too thin to mean anything: pma={checked_pma} whatChanged={checked_wc}"
    )
    assert zero_cap_seen, "no zero/absent cap in the corpus — the falsy-zero branch went untested"
    assert truncated > 0, (
        "no truncated record in the corpus — the refusal branch went untested, and it is the "
        "branch that stops the tool inventing content past a truncation marker"
    )
