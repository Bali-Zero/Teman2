"""The contract every `kb/inventory/*.yaml` obeys.

This is the gate that makes an inventory an ARTIFACT rather than a document: if it
does not satisfy these rules, CI is red and the campaign does not advance on it.

Two of the rules deliberately compare the inventory against a DIFFERENT source —
`collection_registry.py` and the declared ingest entrypoints — rather than against
itself. A tripwire that only checks a file for internal consistency is comparing
two outputs of one generator, and this repo has already paid for that.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# A hard import, NOT importorskip: pyyaml==6.0.3 is pinned in
# requirements.lock.txt and another CI-collected test already imports it plainly.
# `importorskip` here would turn a missing dependency into a silent green gate —
# the exact shape of an empty proof.
import yaml


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise AssertionError(f"repo root not found from {here}")


ROOT = _repo_root()
INVENTORY_DIR = ROOT / "kb" / "inventory"


def _probe():
    """Load kb_inventory_probe.py as a module (it lives outside any package)."""
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


IDENTITY_VERDICTS = frozenset({"consistent", "mistyped", "contradictory", "lost"})
DISPOSITIONS = frozenset({
    "promote_after_repair", "discard_duplicate", "blocked_identity", "catalogue_only",
})
DECISION_CHOICES = frozenset({"retire_as_target", "promote", "point_a_reader_at_it"})

# The closed payload-shape vocabulary. Imported from the probe rather than
# restated, so the gate and the probe can never disagree about what a shape is
# named — a tripwire that compares two restatements of one idea is blind, but
# these two read the SAME tuple, and the probe's version is the one production
# is measured with.
PAYLOAD_SHAPES = frozenset(_probe().PAYLOAD_SHAPES)

# MANDATE.md §2 gives topic inventories a different shape (instruments in scope,
# in-force/superseded/revoked, official URL). They are validated by their own gate
# when lane A opens; this module owns `retired_collection` and must not judge a
# topic inventory by a schema that was never meant for it.
KINDS = frozenset({"retired_collection", "topic"})
# MANDATE.md §5 — the seven lanes. Every document must be owned by one of them,
# so a finding cannot be recorded with nobody on the hook for it.
LANES = frozenset("ABCDEFP")
OWNED_KIND = "retired_collection"


def _inventories() -> list[Path]:
    return sorted(INVENTORY_DIR.glob("*.yaml"))


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_the_inventory_directory_is_not_empty():
    """Anti-vacuity. Every parametrized test below is over this glob; an empty
    glob would make the whole module green while checking nothing."""
    found = _inventories()
    assert found, (
        "kb/inventory/ holds no *.yaml — either the campaign has produced no "
        "inventory yet, or this gate has been pointed at the wrong directory. "
        "Both are red, neither is silence."
    )


@pytest.fixture(params=_inventories(), ids=lambda p: p.stem)
def any_inventory(request):
    return request.param, _load(request.param)


@pytest.fixture
def inventory(any_inventory):
    path, data = any_inventory
    if data.get("kind") != OWNED_KIND:
        pytest.skip("kind={!r} is owned by another gate (MANDATE §2)".format(data.get("kind")))
    return path, data


def test_every_inventory_declares_a_known_kind(any_inventory):
    """Applies to EVERY inventory, so a typo in `kind` cannot make a file invisible
    to both this gate and the topic gate."""
    path, data = any_inventory
    assert data.get("kind") in KINDS, (
        "{}: kind={!r} is not one of {} — an inventory with an unknown kind is "
        "validated by nobody".format(path.name, data.get("kind"), sorted(KINDS))
    )


def test_at_least_one_inventory_is_owned_by_this_gate():
    """Anti-vacuity for the skip above: if every file were skipped, this module
    would report all-green while validating nothing."""
    owned = [p.name for p in _inventories() if _load(p).get("kind") == OWNED_KIND]
    assert owned, (
        f"no kb/inventory/*.yaml has kind={OWNED_KIND!r} — every test in this module would "
        "skip, and a fully-skipped gate reads as a passing one"
    )


def test_schema_version_is_known(inventory):
    path, data = inventory
    assert data.get("schema_version") == 1, path


def test_document_points_sum_to_the_measured_total(inventory):
    """Arithmetic, so it cannot be argued with.

    A per-document triage that does not add up to the collection's measured point
    count is a triage of some other collection.
    """
    path, data = inventory
    docs = data.get("documents") or []
    total = sum(d["points"] for d in docs)
    declared = data["measured_against"]["points"]
    assert total == declared, (
        f"{path.name}: documents sum to {total} points but measured_against.points "
        f"is {declared} — the triage does not cover the collection it claims to"
    )
    distinct = data["measured_against"]["distinct_documents"]
    assert len(docs) == distinct, (
        f"{path.name}: {len(docs)} document entries vs distinct_documents={distinct}"
    )


def test_every_document_carries_a_closed_vocabulary_verdict(inventory):
    path, data = inventory
    for doc in data["documents"]:
        did = doc["document_id"]
        assert doc["identity"]["verdict"] in IDENTITY_VERDICTS, (path.name, did)
        assert doc["disposition"] in DISPOSITIONS, (path.name, did, doc["disposition"])
        assert doc.get("lane") in LANES, (
            "{}: {} is owned by lane {!r}, which is not one of MANDATE §5's {}".format(path.name, did, doc.get("lane"), sorted(LANES))
        )
        assert (doc.get("reason") or "").strip(), f"{path.name}: {did} has no reason"


def test_identity_before_content(inventory):
    """Mandate §3.4, mechanized.

    Nothing may be queued for promotion under an identity its own text
    contradicts. This is the rule that stops a Klaten price schedule from being
    promoted because it is labelled as the visa regulation.
    """
    path, data = inventory
    offenders = [
        doc["document_id"]
        for doc in data["documents"]
        if doc["disposition"] == "promote_after_repair"
        and doc["identity"]["verdict"] != "consistent"
    ]
    assert offenders == [], (
        f"{path.name}: queued for promotion with a non-consistent identity: {offenders}"
    )


def test_nothing_is_discarded_without_a_containment_proof(inventory):
    """Mandate §3.6, mechanized — including the ratio, printed."""
    path, data = inventory
    for doc in data["documents"]:
        if doc["disposition"] != "discard_duplicate":
            continue
        did = doc["document_id"]
        proof = doc.get("containment_proof")
        assert proof, f"{path.name}: {did} marked discard_duplicate with no containment_proof"
        covered = proof["distinct_fragments_covered"]
        total = proof["distinct_fragments_total"]
        assert covered == total, (
            f"{path.name}: {did} containment proof is incomplete: {covered}/{total}"
        )
        assert proof["ratio"] == 1.0, (path.name, did, proof["ratio"])
        assert doc["presence_in_legal_unified"]["fragments_absent_there"] == 0, (
            f"{path.name}: {did} is marked duplicate but has unshared fragments"
        )


def test_a_proven_duplicate_is_not_left_untriaged(inventory):
    """The inverse of the rule above.

    A document whose identity is sound and whose every fragment is already in the
    read collection, yet is marked for promotion, would re-ingest what is there.
    """
    path, data = inventory
    for doc in data["documents"]:
        if (
            doc["identity"]["verdict"] == "consistent"
            and doc["presence_in_legal_unified"]["fragments_absent_there"] == 0
            and doc["presence_in_legal_unified"]["by_document_id"] > 0
        ):
            assert doc["disposition"] == "discard_duplicate", (
                "{}: {} adds no fragment the read collection lacks — promoting it "
                "re-ingests what is already there".format(path.name, doc["document_id"])
            )


def test_deletion_is_interlocked_on_a_complete_proof(inventory):
    """No deletion may be authorized while any containment proof declares a gap."""
    path, data = inventory
    incomplete = [
        doc["document_id"]
        for doc in data["documents"]
        if (doc.get("containment_proof") or {}).get("complete") is False
    ]
    if incomplete:
        assert data["decision"]["deletions_authorized"] is False, (
            f"{path.name}: deletions are authorized while these containment proofs declare a "
            f"gap: {incomplete}. §4.6 — one uncovered fragment means do not delete."
        )
        assert (data["decision"].get("deletions_blocked_because") or "").strip(), path.name


def test_a_leak_claim_is_backed_by_the_measurement(inventory):
    path, data = inventory
    for doc in data["documents"]:
        if doc.get("leaked_to_production"):
            assert doc["presence_in_legal_unified"]["by_document_id"] > 0, (
                "{}: {} claims a production leak but measured 0 points there".format(path.name, doc["document_id"])
            )


def test_decision_choice_is_from_the_mandates_three(inventory):
    path, data = inventory
    assert data["decision"]["choice"] in DECISION_CHOICES, path.name
    assert (data["decision"].get("rationale") or "").strip(), path.name


# ── The two cross-source rules ───────────────────────────────────────────────

def test_registry_mapped_claims_match_the_real_registry(inventory):
    """Cross-source: check the claim against collection_registry.py itself."""
    sys.path.insert(0, str(ROOT / "apps" / "backend-rag"))
    from backend.core.collection_registry import is_known_collection

    path, data = inventory
    for block in ("measured_against", "compared_with"):
        section = data.get(block)
        if not section:
            continue
        claimed = section["registry_mapped"]
        actual = is_known_collection(section["collection"])
        assert claimed == actual, (
            "{}: {}.registry_mapped says {!r} but collection_registry.py says {!r} for {!r}".format(path.name, block, claimed, actual, section["collection"])
        )


def test_a_retired_collection_is_named_by_no_ingest_entrypoint(inventory):
    """Cross-source: the decision to retire must be enforced by the lint, not
    merely declared here. This is what stops the inventory from being prose."""
    path, data = inventory
    if data.get("kind") != "retired_collection":
        pytest.skip("not a retired-collection inventory")
    if data["decision"]["choice"] != "retire_as_target":
        pytest.skip("not retired as a target")

    spec = importlib.util.spec_from_file_location(
        "ingest_target_lint", ROOT / "scripts" / "ci" / "ingest_target_lint.py"
    )
    lint = importlib.util.module_from_spec(spec)
    sys.modules["ingest_target_lint"] = lint
    spec.loader.exec_module(lint)

    retired = data["measured_against"]["collection"]
    offenders = []
    for rel in lint.DECLARED_ENTRYPOINTS:
        targets = lint.collection_targets((ROOT / rel).read_text(encoding="utf-8"))
        if any(value == retired for value, _, _ in targets):
            offenders.append(rel)
    assert offenders == [], (
        f"{path.name} declares {retired!r} retired as an ingest target, but these entrypoints still "
        f"name it: {offenders}"
    )


def test_payload_shapes_use_the_closed_vocabulary(inventory):
    """§4.1 is only enforceable if every inventory names shapes the probe measures.

    A shape spelled some other way is not a stricter record — it is a row the
    probe silently scores as 0 and the drift check can never reach.
    """
    path, data = inventory
    for section in ("measured_against", "compared_with"):
        block = data.get(section)
        if block is None:
            continue
        shapes = block.get("payload_shapes")
        assert isinstance(shapes, dict) and shapes, (
            f"{path.name}: {section} has no payload_shapes — §4.1 requires the shape "
            f"mix to be recorded, and the probe compares it against production"
        )
        unknown = set(shapes) - PAYLOAD_SHAPES
        assert not unknown, (
            f"{path.name}: {section}.payload_shapes names {sorted(unknown)}, which "
            f"kb_inventory_probe.py cannot measure — known shapes are "
            f"{sorted(PAYLOAD_SHAPES)}"
        )
        missing = PAYLOAD_SHAPES - set(shapes)
        assert not missing, (
            f"{path.name}: {section}.payload_shapes omits {sorted(missing)}. Omission "
            f"reads as 'absent' and 'absent' is indistinguishable from 'never looked' — "
            f"record a 0 when a shape is genuinely absent"
        )


def test_payload_shapes_sum_to_the_measured_points(inventory):
    """Arithmetic, so no wording can soften it.

    Every point in a collection has exactly one shape. If the shape counts do
    not add up to the point count, the census read a different collection, or a
    shape went uncounted — and in either case §4.1's guarantee is void.
    """
    path, data = inventory
    for section in ("measured_against", "compared_with"):
        block = data.get(section)
        if block is None:
            continue
        shapes = block.get("payload_shapes") or {}
        total = sum(shapes.values())
        declared = block["points"]
        assert total == declared, (
            f"{path.name}: {section}.payload_shapes sums to {total} but points is "
            f"{declared} — every point has exactly one shape, so these must be equal"
        )


def test_the_probe_actually_compares_the_recorded_shapes(inventory):
    """The measurement existed for a day and was only printed, never compared.

    census() computed the shape mix and main() formatted it into a log line;
    nothing ever went red on it. This asserts the drift comparison is wired to
    BOTH collections, because a probe that checks one of the two still passes
    green over a re-ingest of the other.
    """
    del inventory  # gate on the probe source, once per parametrisation
    source = (ROOT / "scripts" / "kb" / "kb_inventory_probe.py").read_text(encoding="utf-8")
    assert source.count("shape_drift(") >= 3, (
        "kb_inventory_probe.py must DEFINE shape_drift and CALL it for the topic "
        "collection and the read collection — found fewer than 3 occurrences"
    )
    probe = _probe()
    findings = probe.shape_drift("c", {"modern_full": 5}, {"modern_full": 4})
    assert findings, "shape_drift returned nothing for a count that differs"
    assert not probe.shape_drift("c", {"modern_full": 4}, {"modern_full": 4}), (
        "shape_drift reported drift for two identical censuses"
    )
    vanished = probe.shape_drift("c", {}, {"modern_full": 7})
    assert vanished, (
        "shape_drift stayed silent about a shape that disappeared from production — "
        "iterating the LIVE keys instead of the vocabulary is exactly this bug"
    )
