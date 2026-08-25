"""`kb_inventory_probe.py` must be able to probe a `kind: topic` inventory too.

Measured 2026-08-26: `main()` unconditionally read `data["compared_with"]["collection"]`
— a key that exists ONLY on the `kind: retired_collection` schema. Four real inventories
(`kb/inventory/{company,immigration,property,tax}.yaml`) are `kind: topic` and declare
numbers "measured against production" with nothing that ever re-measures them; handing
any one of them to the unmodified probe raised `KeyError: 'compared_with'` before this
module existed. `test_kb_inventory_contract.py` proves a topic inventory is internally
sound; it has no Qdrant credentials and cannot prove the file still describes the world.

Two layers of proof, same discipline `test_probe_retrieval_refusals.py` already uses for
the sibling module:

  1. `topic_drift()` — a PURE function over already-scrolled census output
     (`points` / `by_doc` / `shapes`, exactly what `census()` returns). No Qdrant object
     is touched, so guilt and innocence are provable with zero network cost.

  2. `_run_topic()` / `_run_retired_collection()` / `main()` — run for real against a
     `FakeQdrantClient` that reproduces the REAL client's `scroll()` pagination contract
     (`(batch, next_offset)`, `next_offset is None` on the last page). `census()` never
     issues a server-side filter — it scrolls every point and classifies the payload in
     Python — so the fake needs no `400`-on-unindexed-key behaviour to be honest: that
     failure mode does not exist on this code path, and reproducing it here would be
     testing a scenario the code never triggers. What the fake DOES have to get right,
     and does, is the pagination contract and the payload shapes `payload_shape()`
     dispatches on — a fake that just returns everything shape-blind would prove nothing
     about the modern/legacy split MANDATE.md §4.1 exists to catch.
"""

from __future__ import annotations

import collections
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise AssertionError(f"repo root not found from {here}")


ROOT = _repo_root()


def _probe():
    cached = sys.modules.get("kb_inventory_probe")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(
        "kb_inventory_probe", ROOT / "scripts" / "kb" / "kb_inventory_probe.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["kb_inventory_probe"] = module
    spec.loader.exec_module(module)
    return module


PROBE = _probe()


# ── a fake Qdrant client that honours the real scroll() pagination contract ────


class _FakePoint:
    def __init__(self, payload: dict):
        self.payload = payload


class FakeQdrantClient:
    """Reproduces `QdrantClient.scroll`'s `(batch, next_offset)` contract.

    `census()` never filters server-side — it scrolls everything and classifies in
    Python — so this fake carries no filter/index behaviour at all. That is not a
    shortcut: it is the same code path production takes, because `census()` genuinely
    never issues a filtered query (MANDATE §4.1's 400-on-unindexed-key trap applies to
    a DIFFERENT code shape than this one).
    """

    def __init__(self, collections_: dict[str, list[dict]]):
        self._collections = collections_

    def get_collections(self):
        return SimpleNamespace(
            collections=[SimpleNamespace(name=n) for n in self._collections]
        )

    def scroll(self, collection, limit=2000, offset=None, with_payload=True, with_vectors=False):
        points = self._collections.get(collection, [])
        start = offset or 0
        chunk = points[start : start + limit]
        batch = [_FakePoint(p) for p in chunk]
        next_offset = start + limit if start + limit < len(points) else None
        return batch, next_offset


def _modern_id_only(doc_id: str) -> dict:
    """A payload shaped `modern_id_only` — top-level document_id, no chunk_key."""
    return {"document_id": doc_id, "text": "x" * 50}


def _legacy(doc_id: str) -> dict:
    """A payload shaped `legacy_metadata_text` — identity only under metadata."""
    return {"metadata": {"document_id": doc_id}, "text": "y" * 50}


def _modern_full(doc_id: str) -> dict:
    return {"document_id": doc_id, "chunk_key": "k1", "section": "pasal_1", "text": "z" * 50}


# ── resolve_physical(): the OTHER real bug this run found ──────────────────────
# MEASURED against real production 2026-08-26: no literal Qdrant collection is
# named `legal_unified` — the four names below prove both directions this
# function must get right, imported straight from the real registry so a change
# to that table cannot silently desync from what this test expects.


def test_resolve_physical_maps_the_logical_alias_to_the_live_collection(monkeypatch):
    # monkeypatch.syspath_prepend, not a bare sys.path.insert with no matching
    # .remove/.pop: pytest restores sys.path at teardown, so this cannot leak a
    # path entry into every test collected after this one for the rest of the
    # process (the defect this same cure closes in test_kb_inventory_contract.py).
    monkeypatch.syspath_prepend(str(ROOT / "apps" / "backend-rag"))
    from backend.core.collection_registry import LOGICAL_TO_PHYSICAL_COLLECTIONS

    assert PROBE.resolve_physical("legal_unified") == LOGICAL_TO_PHYSICAL_COLLECTIONS["legal_unified"]
    assert PROBE.resolve_physical("legal_unified") != "legal_unified", (
        "if this ever becomes true, 'legal_unified' has become a literal "
        "collection and every guilt case in this section is now vacuous"
    )


def test_resolve_physical_passes_through_a_name_outside_the_registry_unchanged():
    """`legal_unified_2026` is a literal collection, not a logical alias — the
    retired-collection inventory's `measured_against.collection`. Resolution
    must be a no-op here, or that inventory's probe would query the wrong name."""
    assert PROBE.resolve_physical("legal_unified_2026") == "legal_unified_2026"
    assert PROBE.resolve_physical("acme_never_registered_anywhere") == "acme_never_registered_anywhere"


def test_resolve_physical_is_actually_called_before_membership_and_census(capsys):
    """Wired, not decoration: run `_run_topic` with `legal_unified` as the
    declared collection and a fake client that only knows the PHYSICAL name —
    if resolution were skipped, this would print ABSENT even though the fake
    client explicitly serves the collection under its real live name."""
    data = _good_topic_inventory()
    data["measured_against"]["collection"] = "legal_unified"
    data["measured_against"]["points"] = 7
    data["measured_against"]["payload_shapes"] = {
        "legacy_metadata_text": 0, "orphan_no_identity": 0,
        "modern_id_only": 7, "modern_id_chunk": 0, "modern_full": 0,
    }
    data["instruments"] = [{"id": "UU_6_2011", "points": 7, "present": True, "complete": True}]
    client = FakeQdrantClient({"legal_unified_hybrid_hybrid": [_modern_id_only("UU_6_2011")] * 7})
    rc = PROBE._run_topic(client, data)
    out = capsys.readouterr().out
    assert "ABSENT" not in out, out
    assert rc == 0, out


# ── layer 1: topic_drift(), pure, no Qdrant object anywhere ────────────────────


def _good_topic_inventory() -> dict:
    return {
        "schema_version": 1,
        "kind": "topic",
        "lane": "A",
        "topic": "immigration",
        "measured_at": "2026-08-25",
        "measured_against": {
            # Deliberately NOT a name in collection_registry.py's logical map —
            # these tests exercise topic_drift()/_run_topic() in isolation, and
            # must not be coupled to (or accidentally validated by) the real
            # registry's exact mapping table. `resolve_physical()` itself is
            # exercised separately, against the real file on disk, below.
            "collection": "acme_legal_topic",
            "points": 10,
            "payload_shapes": {
                "legacy_metadata_text": 3,
                "orphan_no_identity": 0,
                "modern_id_only": 7,
                "modern_id_chunk": 0,
                "modern_full": 0,
            },
        },
        "instruments": [
            {"id": "UU_6_2011", "points": 7, "present": True, "complete": True},
            {"id": "Permen_22_2023", "points": 3, "present": True, "complete": True},
        ],
    }


def _matching_by_doc_and_shapes():
    """`(by_doc, shapes_by_doc)` that agree exactly with `_good_topic_inventory()`.

    `shapes_by_doc` mirrors `census()`'s real return shape: a dict keyed by
    document id, each value a `Counter` of shape name -> count for THAT
    document only.
    """
    by_doc = collections.Counter({"UU_6_2011": 7, "Permen_22_2023": 3})
    shapes_by_doc = {
        "UU_6_2011": collections.Counter({"modern_id_only": 7}),
        "Permen_22_2023": collections.Counter({"legacy_metadata_text": 3}),
    }
    return by_doc, shapes_by_doc


def test_innocence_topic_drift_reports_nothing_when_everything_matches():
    """If this failed, every guilt case below would be vacuous."""
    by_doc, shapes_by_doc = _matching_by_doc_and_shapes()
    assert PROBE.topic_drift(_good_topic_inventory(), by_doc, shapes_by_doc) == []


def test_guilt_topic_drift_catches_a_moved_aggregate_point_count():
    """The SUM over THIS topic's own instruments no longer matches
    `measured_against.points`.

    Scoped to the topic, never to the whole shared collection — that is the
    exact defect measured 2026-08-25/26: a first version of this function
    compared the topic-scoped `measured_against.points` against the WHOLE
    `legal_unified` collection's live total (84,283, shared across every
    lane) and reported all four real topic inventories at 100% DRIFT, on
    every run, regardless of whether a single document had moved.
    """
    by_doc, shapes_by_doc = _matching_by_doc_and_shapes()
    by_doc["UU_6_2011"] = 9  # +2 -> topic-scoped sum becomes 12, was 10
    findings = PROBE.topic_drift(_good_topic_inventory(), by_doc, shapes_by_doc)
    assert any("point count is 12, inventory recorded 10" in f for f in findings), findings


def test_innocence_the_aggregate_check_ignores_other_lanes_sharing_the_collection():
    """The regression this redesign exists to close, proven directly: a
    document belonging to some OTHER topic's instrument, inside the SAME
    shared `legal_unified` collection, must not move this topic's aggregate
    point count or shape mix at all — `by_doc`/`shapes_by_doc` for the whole
    collection legitimately carry hundreds of ids this topic never scoped."""
    by_doc, shapes_by_doc = _matching_by_doc_and_shapes()
    by_doc["UU_40_2007"] = 50_000  # a different lane's instrument, same collection
    shapes_by_doc["UU_40_2007"] = collections.Counter({"modern_full": 50_000})
    findings = PROBE.topic_drift(_good_topic_inventory(), by_doc, shapes_by_doc)
    assert findings == [], findings


def test_guilt_topic_drift_catches_a_payload_shape_that_moved():
    """Delegated to `shape_drift` — this proves the delegation is actually wired,
    not merely present as an unreachable call. Summed ONLY over this topic's
    own instruments (shape_drift itself is tested for the pure aggregation
    logic elsewhere; this proves topic_drift feeds it the right numbers)."""
    by_doc, shapes_by_doc = _matching_by_doc_and_shapes()
    # UU_6_2011's 7 points re-ingested under a different shape.
    shapes_by_doc["UU_6_2011"] = collections.Counter({"modern_full": 7})
    findings = PROBE.topic_drift(_good_topic_inventory(), by_doc, shapes_by_doc)
    assert any("modern_full is 7, inventory recorded 0" in f for f in findings), findings
    assert any("modern_id_only is 0, inventory recorded 7" in f for f in findings), findings


def test_guilt_topic_drift_catches_an_instrument_that_grew():
    """The shape of a promotion nobody recorded: production has MORE of an
    instrument than the inventory claims."""
    by_doc, shapes_by_doc = _matching_by_doc_and_shapes()
    by_doc["UU_6_2011"] = 9
    findings = PROBE.topic_drift(_good_topic_inventory(), by_doc, shapes_by_doc)
    assert any("UU_6_2011: 9 points in acme_legal_topic, inventory recorded 7" in f
               for f in findings), findings


def test_guilt_topic_drift_catches_an_instrument_that_vanished():
    """The shape that matters most for this campaign: content the inventory
    swears is there is gone from production — a bad delete, a re-ingest that
    dropped it, a collection that moved underneath the file."""
    by_doc, shapes_by_doc = _matching_by_doc_and_shapes()
    del by_doc["Permen_22_2023"]
    findings = PROBE.topic_drift(_good_topic_inventory(), by_doc, shapes_by_doc)
    assert any("Permen_22_2023: 0 points in acme_legal_topic, inventory recorded 3" in f
               for f in findings), findings


def test_guilt_topic_drift_catches_an_instrument_present_in_the_file_but_absent_from_by_doc():
    """`by_doc` simply never mentions the id — the shape the whole-collection-gone
    case produces, and a dict.get default must not swallow it."""
    _, shapes_by_doc = _matching_by_doc_and_shapes()
    findings = PROBE.topic_drift(
        _good_topic_inventory(), collections.Counter(), shapes_by_doc
    )
    assert any("UU_6_2011: 0 points" in f for f in findings), findings
    assert any("Permen_22_2023: 0 points" in f for f in findings), findings


def test_innocence_an_instrument_declared_zero_and_absent_live_is_not_drift():
    """`present: false, points: 0` is a legitimate, already-honest state — the
    probe must not invent drift where the file already told the truth."""
    data = _good_topic_inventory()
    data["instruments"].append({"id": "Permen_35_2012", "points": 0, "present": False,
                                 "lookup_attempts": ["a", "b", "c"]})
    by_doc, shapes_by_doc = _matching_by_doc_and_shapes()
    findings = PROBE.topic_drift(data, by_doc, shapes_by_doc)
    assert findings == [], findings


TOPIC_DRIFT_GUILT_COUNT = 5  # the five test_guilt_topic_drift_* cases above


def test_the_guilt_matrix_is_not_empty():
    """Anti-vacuity: this file's guilt cases are plain functions, not a
    `pytest.mark.parametrize` table, so nothing collects them automatically —
    assert the count by hand so deleting a case is loud.

    Scoped to `test_guilt_topic_drift_*` specifically (not the bare
    `test_guilt_` prefix) because the --json section below adds its own,
    separately-counted guilt case (`test_guilt_json_*`,
    `test_the_json_guilt_matrix_is_not_empty`) — a shared bare prefix would
    make this count silently absorb that unrelated section's cases (or vice
    versa) the next time either grows."""
    import inspect

    guilt_fns = [
        name for name, obj in inspect.getmembers(sys.modules[__name__])
        if name.startswith("test_guilt_topic_drift_") and inspect.isfunction(obj)
    ]
    assert len(guilt_fns) == TOPIC_DRIFT_GUILT_COUNT, guilt_fns


# ── layer 2: _run_topic / _run_retired_collection / main(), against a fake client ──


def test_run_topic_returns_0_and_prints_at_target_when_everything_matches(capsys):
    client = FakeQdrantClient({
        "acme_legal_topic": [
            _modern_id_only("UU_6_2011"), *([_modern_id_only("UU_6_2011")] * 6),
            _legacy("Permen_22_2023"), *([_legacy("Permen_22_2023")] * 2),
        ]
    })
    rc = PROBE._run_topic(client, _good_topic_inventory())
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "AT TARGET" in out


def test_run_topic_returns_1_and_prints_drift_when_production_moved(capsys):
    client = FakeQdrantClient({
        "acme_legal_topic": [_modern_id_only("UU_6_2011")] * 7,  # Permen_22_2023 is GONE
    })
    rc = PROBE._run_topic(client, _good_topic_inventory())
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "DRIFT" in out
    assert "Permen_22_2023" in out


def test_run_topic_treats_an_absent_collection_as_total_drift(capsys):
    """The collection this topic reads has vanished from Qdrant entirely — every
    declared number is now wrong, and the probe must say so rather than crash on
    a missing key or silently report zero findings."""
    client = FakeQdrantClient({"some_other_collection": []})
    rc = PROBE._run_topic(client, _good_topic_inventory())
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "ABSENT from Qdrant" in out


def test_run_topic_at_target_with_a_shared_collection_holding_other_lanes_data(capsys):
    """End-to-end proof of the real regression MEASURED against production
    2026-08-25/26: `_run_topic` MUST return AT TARGET for a topic whose own
    instruments match, even when the collection it reads also holds tens of
    thousands of points belonging to OTHER lanes' instruments — which is the
    literal shape of `legal_unified` in production (84,283 points / 388
    documents, of which immigration's own instruments are 1,868 / 10). A
    version of this function that compared against the whole scroll's totals
    fails this test by construction; this is the test that would have caught
    it before it ran against real production instead of after."""
    payloads = (
        [_modern_id_only("UU_6_2011")] * 7
        + [_legacy("Permen_22_2023")] * 3
        + [_modern_full("UU_40_2007")] * 50_000  # another lane's instrument
    )
    client = FakeQdrantClient({"acme_legal_topic": payloads})
    rc = PROBE._run_topic(client, _good_topic_inventory())
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "AT TARGET" in out


def test_run_topic_does_not_raise_keyerror_on_the_schema_that_broke_it():
    """The exact regression this module exists to close: a `kind: topic`
    inventory has no `compared_with` key, and the pre-dispatch `main()` body
    read `data["compared_with"]["collection"]` unconditionally."""
    data = _good_topic_inventory()
    assert "compared_with" not in data
    client = FakeQdrantClient({"acme_legal_topic": []})
    PROBE._run_topic(client, data)  # must not raise


def test_run_topic_against_a_real_inventory_file_on_disk():
    """Load an actual `kb/inventory/*.yaml` (`kind: topic`) and run it through
    the real function with a fake client shaped to match exactly — proves the
    code handles the real schema, not just this test file's synthetic shrink."""
    import yaml

    path = ROOT / "kb" / "inventory" / "immigration.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["kind"] == "topic"

    payloads = []
    for inst in data["instruments"]:
        n = inst["points"]
        if n == 0:
            continue
        payloads.extend(_modern_full(inst["id"]) for _ in range(n))
    # Keyed by the RESOLVED physical name — `immigration.yaml` declares the
    # LOGICAL `legal_unified`, and `resolve_physical()` is what turns that into
    # the name a real Qdrant `get_collections()` would actually list.
    physical = PROBE.resolve_physical(data["measured_against"]["collection"])
    assert physical != data["measured_against"]["collection"], (
        "this fixture is meant to prove resolution happens — if 'legal_unified' "
        "ever stops being a logical alias, this test stops proving anything"
    )
    client = FakeQdrantClient({physical: payloads})
    rc = PROBE._run_topic(client, data)
    # A shape mismatch is expected (this fixture is all modern_full, the file
    # records a mix) — the point here is only that it runs to completion and
    # returns the documented vocabulary, never an exception.
    assert rc in (0, 1)


# ── retired_collection stays behaviourally identical after the extraction ──────


def _good_retired_inventory() -> dict:
    return {
        "schema_version": 1,
        "kind": "retired_collection",
        "measured_at": "2026-08-25",
        "decision": {"choice": "retire_as_target", "deletions_authorized": False,
                     "deletions_blocked_because": "x"},
        "measured_against": {
            "collection": "legal_unified_2026",
            "points": 5,
            "payload_shapes": {
                "legacy_metadata_text": 5, "orphan_no_identity": 0,
                "modern_id_only": 0, "modern_id_chunk": 0, "modern_full": 0,
            },
        },
        "compared_with": {
            # Same reasoning as `_good_topic_inventory()`: kept OUT of
            # collection_registry.py's logical map on purpose, so these tests
            # never depend on that table's exact contents.
            "collection": "acme_read_collection",
            "points": 3,
            "payload_shapes": {
                "legacy_metadata_text": 3, "orphan_no_identity": 0,
                "modern_id_only": 0, "modern_id_chunk": 0, "modern_full": 0,
            },
        },
        "documents": [
            {
                "document_id": "X_1_2026",
                "points": 5,
                "disposition": "discard_duplicate",
                "presence_in_legal_unified": {"by_document_id": 3},
                "identity": {"verdict": "consistent"},
            },
        ],
    }


def test_run_retired_collection_at_target_when_disposition_is_reached(capsys):
    client = FakeQdrantClient({
        # discard_duplicate reaches target when in_topic == 0 (already removed)
        "acme_read_collection": [_legacy("X_1_2026")] * 3,
    })
    rc = PROBE._run_retired_collection(client, _good_retired_inventory())
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "AT TARGET" in out


def test_run_retired_collection_outstanding_when_disposition_is_not_reached(capsys):
    client = FakeQdrantClient({
        "legal_unified_2026": [_legacy("X_1_2026")] * 5,  # still there — not discarded
        "acme_read_collection": [_legacy("X_1_2026")] * 3,
    })
    rc = PROBE._run_retired_collection(client, _good_retired_inventory())
    out = capsys.readouterr().out
    assert rc == 2, out
    assert "OUTSTANDING" in out


def test_run_retired_collection_drift_when_production_moved(capsys):
    client = FakeQdrantClient({
        "acme_read_collection": [_legacy("X_1_2026")] * 3,
        # measured_against declared 5 points; production now has 6.
        "legal_unified_2026": [_legacy("X_1_2026")] * 6,
    })
    rc = PROBE._run_retired_collection(client, _good_retired_inventory())
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "DRIFT" in out


# ── main() dispatch, wired not merely defined ───────────────────────────────


def test_main_dispatches_topic_and_retired_collection_and_refuses_the_rest():
    import inspect

    src = inspect.getsource(PROBE.main)
    assert '_run_topic(' in src
    assert '_run_retired_collection(' in src
    assert 'kind == "topic"' in src
    assert 'kind == "retired_collection"' in src


def test_main_returns_3_and_says_broken_for_an_unrecognised_kind(monkeypatch, tmp_path, capsys):
    """The dispatch itself, exercised end-to-end through `main()` — argv, yaml
    load, env, and the fake client — for the one branch that needs no Qdrant
    schema at all: an inventory whose `kind` this probe has never heard of."""
    import qdrant_client
    import yaml

    monkeypatch.setattr(PROBE, "load_env", lambda root: None)
    monkeypatch.setenv("QDRANT_URL", "http://fake")
    monkeypatch.setenv("QDRANT_API_KEY", "fake")
    monkeypatch.setattr(
        qdrant_client, "QdrantClient",
        lambda *a, **k: FakeQdrantClient({}),
    )

    path = tmp_path / "mystery.yaml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "kind": "nonsense"}), encoding="utf-8")

    rc = PROBE.main([str(path)])
    err = capsys.readouterr().err
    assert rc == 3
    assert "BROKEN" in err
    assert "nonsense" in err


def test_main_runs_a_real_topic_yaml_end_to_end(monkeypatch, tmp_path, capsys):
    import qdrant_client
    import yaml

    monkeypatch.setattr(PROBE, "load_env", lambda root: None)
    monkeypatch.setenv("QDRANT_URL", "http://fake")
    monkeypatch.setenv("QDRANT_API_KEY", "fake")

    data = _good_topic_inventory()
    client = FakeQdrantClient({
        "acme_legal_topic": [_modern_id_only("UU_6_2011")] * 7 + [_legacy("Permen_22_2023")] * 3,
    })
    monkeypatch.setattr(qdrant_client, "QdrantClient", lambda *a, **k: client)

    path = tmp_path / "topic.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    rc = PROBE.main([str(path)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "AT TARGET" in out


# ── --json (2026-08-26): one JSON object, same verdict, nothing else on stdout ──
#
# Team lead's ask, verbatim reasoning: without --json nothing can make
# kb/ops/probe_history.py (out of THIS PR's scope — a different lane owns it
# right now) record a topic inventory's drift rather than just its file's
# sha256. "Same structure as kb/ops/probe_retrieval.py --json" — proven below
# by cross-checking the actual VERDICT_BY_EXIT vocabulary in that file, not by
# import (this module does not depend on probe_retrieval.py at runtime; the
# two dicts are kept string-identical by convention, and this test is what
# would catch them drifting apart).


def _load_probe_retrieval_for_vocabulary_check():
    """Test-only import of kb/ops/probe_retrieval.py, same out-of-package
    pattern kb/ops/probe_history.py itself uses at runtime (`_probe_retrieval_module`)
    and `test_probe_retrieval_collection_override.py` uses in this same test suite.
    This is a TEST dependency only — kb_inventory_probe.py itself never imports
    this file; see the module docstring's --json paragraph for why."""
    cached = sys.modules.get("kb_probe_retrieval_for_vocab_check")
    if cached is not None:
        return cached
    path = ROOT / "kb" / "ops" / "probe_retrieval.py"
    assert path.is_file(), f"{path} is missing"
    spec = importlib.util.spec_from_file_location("kb_probe_retrieval_for_vocab_check", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["kb_probe_retrieval_for_vocab_check"] = module
    spec.loader.exec_module(module)
    return module


def test_verdict_by_exit_matches_probe_retrieval_pys_vocabulary_string_for_string():
    """"Coherent with kb/ops/probe_retrieval.py" (team lead's requirement) means
    the same four strings, not just a superficially similar shape. If this ever
    fails because probe_retrieval.py's dict changed, kb_inventory_probe.py's
    copy needs a matching edit — that is the point of keeping this asserted
    rather than only documented in a comment."""
    probe_retrieval = _load_probe_retrieval_for_vocabulary_check()
    for exit_code, word in probe_retrieval.VERDICT_BY_EXIT.items():
        assert PROBE.VERDICT_BY_EXIT[exit_code] == word, (
            exit_code, PROBE.VERDICT_BY_EXIT[exit_code], word,
        )


def test_run_topic_json_at_target_emits_exactly_one_json_object_and_nothing_else(capsys):
    client = FakeQdrantClient({
        "acme_legal_topic": [_modern_id_only("UU_6_2011")] * 7 + [_legacy("Permen_22_2023")] * 3,
    })
    rc = PROBE._run_topic(client, _good_topic_inventory(), as_json=True)
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)  # raises if anything besides the JSON object was printed
    assert payload["verdict"] == "at_target"
    assert payload["exit_code"] == 0
    assert payload["collection"] == "acme_legal_topic"
    assert payload["collection_live"] is True
    assert payload["findings"] == []
    assert {i["id"] for i in payload["instruments"]} == {"UU_6_2011", "Permen_22_2023"}
    assert all(i["at_target"] for i in payload["instruments"])


def test_run_topic_json_drift_case_reports_findings_and_per_instrument_detail(capsys):
    client = FakeQdrantClient({
        "acme_legal_topic": [_modern_id_only("UU_6_2011")] * 7,  # Permen_22_2023 is GONE
    })
    rc = PROBE._run_topic(client, _good_topic_inventory(), as_json=True)
    out = capsys.readouterr().out
    assert rc == 1
    payload = json.loads(out)
    assert payload["verdict"] == "drift"
    assert payload["exit_code"] == 1
    assert len(payload["findings"]) >= 1
    assert any("Permen_22_2023" in f for f in payload["findings"])
    by_id = {i["id"]: i for i in payload["instruments"]}
    assert by_id["Permen_22_2023"]["live"] == 0
    assert by_id["Permen_22_2023"]["at_target"] is False
    assert by_id["UU_6_2011"]["at_target"] is True


def test_run_topic_json_absent_collection_reports_collection_live_false(capsys):
    client = FakeQdrantClient({"some_other_collection": []})
    rc = PROBE._run_topic(client, _good_topic_inventory(), as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["collection_live"] is False
    assert payload["verdict"] == "drift"


def test_run_topic_json_inventory_file_is_present_when_given_and_null_when_omitted(capsys):
    client = FakeQdrantClient({
        "acme_legal_topic": [_modern_id_only("UU_6_2011")] * 7 + [_legacy("Permen_22_2023")] * 3,
    })
    PROBE._run_topic(client, _good_topic_inventory(), Path("kb/inventory/immigration.yaml"), as_json=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload["inventory_file"] == "kb/inventory/immigration.yaml"

    PROBE._run_topic(client, _good_topic_inventory(), as_json=True)  # inventory_path omitted
    payload = json.loads(capsys.readouterr().out)
    assert payload["inventory_file"] is None


def test_guilt_json_mode_actually_suppresses_the_human_report(capsys):
    """Mutation-tested: comment out any `if not as_json:` guard around a human
    `print()` in `_run_topic` and this goes red — `json.loads` raises on the
    extra text sharing stdout with the JSON object. Proves as_json is WIRED,
    not merely accepted and ignored."""
    client = FakeQdrantClient({
        "acme_legal_topic": [_modern_id_only("UU_6_2011")] * 7 + [_legacy("Permen_22_2023")] * 3,
    })
    PROBE._run_topic(client, _good_topic_inventory(), as_json=True)
    out = capsys.readouterr().out
    json.loads(out)  # must not raise
    assert "[live]" not in out
    assert "INSTRUMENT" not in out
    assert "AT TARGET" not in out  # the human closing line — JSON says "at_target"


JSON_GUILT_COUNT = 1  # test_guilt_json_mode_actually_suppresses_the_human_report


def test_the_json_guilt_matrix_is_not_empty():
    import inspect

    guilt_fns = [
        name for name, obj in inspect.getmembers(sys.modules[__name__])
        if name.startswith("test_guilt_json") and inspect.isfunction(obj)
    ]
    assert len(guilt_fns) == JSON_GUILT_COUNT, guilt_fns


def test_main_json_flag_is_wired_into_the_run_topic_call():
    import inspect

    src = inspect.getsource(PROBE.main)
    assert "as_json=args.json" in src


def test_main_json_end_to_end_at_target(monkeypatch, tmp_path, capsys):
    import qdrant_client
    import yaml

    monkeypatch.setattr(PROBE, "load_env", lambda root: None)
    monkeypatch.setenv("QDRANT_URL", "http://fake")
    monkeypatch.setenv("QDRANT_API_KEY", "fake")

    data = _good_topic_inventory()
    client = FakeQdrantClient({
        "acme_legal_topic": [_modern_id_only("UU_6_2011")] * 7 + [_legacy("Permen_22_2023")] * 3,
    })
    monkeypatch.setattr(qdrant_client, "QdrantClient", lambda *a, **k: client)

    path = tmp_path / "topic.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    rc = PROBE.main([str(path), "--json"])
    out = capsys.readouterr().out
    assert rc == 0, out
    payload = json.loads(out)
    assert payload["verdict"] == "at_target"
    assert payload["inventory_file"] == str(path)


def test_main_json_refuses_retired_collection_kind_with_a_broken_json_object(
    monkeypatch, tmp_path, capsys
):
    """`--json` combined with `kind: retired_collection` must still print ONE
    valid JSON object (verdict=broken) — never the human report this flag was
    explicitly asked NOT to produce, and never a crash."""
    import qdrant_client
    import yaml

    monkeypatch.setattr(PROBE, "load_env", lambda root: None)
    monkeypatch.setenv("QDRANT_URL", "http://fake")
    monkeypatch.setenv("QDRANT_API_KEY", "fake")
    monkeypatch.setattr(qdrant_client, "QdrantClient", lambda *a, **k: FakeQdrantClient({}))

    path = tmp_path / "retired.yaml"
    path.write_text(yaml.safe_dump(_good_retired_inventory()), encoding="utf-8")

    rc = PROBE.main([str(path), "--json"])
    out = capsys.readouterr().out
    assert rc == 3, out
    payload = json.loads(out)
    assert payload["verdict"] == "broken"
    assert payload["exit_code"] == 3
    assert payload["kind"] == "retired_collection"
    assert payload["reason"] == "json_only_implemented_for_topic"


def test_main_json_refuses_unrecognised_kind_with_a_broken_json_object(
    monkeypatch, tmp_path, capsys
):
    import qdrant_client
    import yaml

    monkeypatch.setattr(PROBE, "load_env", lambda root: None)
    monkeypatch.setenv("QDRANT_URL", "http://fake")
    monkeypatch.setenv("QDRANT_API_KEY", "fake")
    monkeypatch.setattr(qdrant_client, "QdrantClient", lambda *a, **k: FakeQdrantClient({}))

    path = tmp_path / "mystery.yaml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "kind": "nonsense"}), encoding="utf-8")

    rc = PROBE.main([str(path), "--json"])
    captured = capsys.readouterr()  # ONE snapshot — a second call would always read "" for both
    assert rc == 3, captured.out
    assert captured.err == ""  # the human BROKEN message must NOT also print alongside JSON
    payload = json.loads(captured.out)
    assert payload["verdict"] == "broken"
    assert payload["kind"] == "nonsense"
