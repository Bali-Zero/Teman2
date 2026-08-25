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

IDENTITY_VERDICTS = frozenset({"consistent", "mistyped", "contradictory", "lost"})
DISPOSITIONS = frozenset({
    "promote_after_repair", "discard_duplicate", "blocked_identity", "catalogue_only",
})
DECISION_CHOICES = frozenset({"retire_as_target", "promote", "point_a_reader_at_it"})

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
        if retired in lint.extract_collection_literals(
            (ROOT / rel).read_text(encoding="utf-8")
        ):
            offenders.append(rel)
    assert offenders == [], (
        f"{path.name} declares {retired!r} retired as an ingest target, but these entrypoints still "
        f"name it: {offenders}"
    )
