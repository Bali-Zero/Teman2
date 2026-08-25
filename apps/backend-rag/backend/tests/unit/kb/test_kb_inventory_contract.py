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


def _proof_is_incomplete(proof: dict | None) -> bool:
    """True when a `containment_proof` fails to affirmatively declare `complete: true`.

    Replaces `.get("complete") is False` — an identity comparison against a literal
    — which reads a MISSING `complete` key as complete: `None is False` is `False`,
    so `{"distinct_fragments_covered": 40, "distinct_fragments_total": 65}` (no
    `complete` key at all) was never flagged. §4.6's interlock is written for the
    case where a gap is DECLARED; a proof that is merely silent about completeness
    is not evidence of completeness, and this campaign's own rule (§4.6, "one
    uncovered fragment means do not delete") means unknown must fail closed, not
    open. `None` — no containment_proof at all — is deliberately NOT incomplete
    by this predicate: a document that never claimed containment in the first
    place (e.g. disposition=promote_after_repair) is a different question, owned
    by test_nothing_is_discarded_without_a_containment_proof for
    disposition == discard_duplicate.
    """
    if proof is None:
        return False
    return proof.get("complete") is not True


def test_guilt_a_containment_proof_missing_complete_is_treated_as_a_gap():
    """The exact shape measured live: `complete` is a MISSING key, not a declared
    `false`, sitting next to `decision.deletions_authorized: true`. The old
    `is False` predicate called this complete; §4.6 says an unproven fragment
    blocks deletion, so this must be a gap."""
    assert _proof_is_incomplete(
        {"distinct_fragments_covered": 40, "distinct_fragments_total": 65}
    )


def test_guilt_a_containment_proof_declaring_false_is_still_a_gap():
    """The case the old predicate already caught — must not regress."""
    assert _proof_is_incomplete({"complete": False})


def test_innocence_no_containment_proof_at_all_is_not_this_rules_business():
    """A document that never claimed containment (promote_after_repair,
    catalogue_only, blocked_identity) is not a gap by THIS predicate — it is the
    ordinary shape of most rows in a retired_collection inventory, and flagging
    it would make deletions_authorized:true fail on files with zero discard
    candidates."""
    assert _proof_is_incomplete(None) is False


def test_innocence_a_containment_proof_declaring_complete_true_is_not_a_gap():
    assert (
        _proof_is_incomplete(
            {"distinct_fragments_covered": 65, "distinct_fragments_total": 65, "complete": True}
        )
        is False
    )


def test_deletion_is_interlocked_on_a_complete_proof(inventory):
    """No deletion may be authorized while any containment proof declares a gap."""
    path, data = inventory
    incomplete = [
        doc["document_id"]
        for doc in data["documents"]
        if _proof_is_incomplete(doc.get("containment_proof"))
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


# ── A shared identifier is not evidence of a leak, and a losing source is not an
#    identity (measured 2026-08-25 against two false claims that landed in this
#    file: UU_13_2016 and Permen_32_2022). Both predicates are pure so they can be
#    exercised twice — once against the real inventory, once against synthetic
#    guilt/innocence cases that do not depend on what the file currently contains
#    (the anti-vacuity discipline `test_kb_topic_contract.py` documents at its top).

def _leak_claim_is_evidenced(doc: dict) -> bool:
    """True unless `leaked_to_production` is asserted on zero fragment-level support.

    §4.2 says a presence/absence judgment takes more than one method; a leak claim
    IS a presence judgment. `presence_in_legal_unified.by_document_id > 0` only
    proves the id STRING exists in production — it says nothing about whether
    THIS row's own content is there, and a retired collection can hold a document
    whose id merely collides with an unrelated production document (UU_13_2016:
    118 production points, all of them a correctly-identified Patent Law that
    shares nothing but the string "UU_13_2016" with this row).

    `fragments_absent_there` is measured per-document against the same
    normalized-fragment hashes the containment proofs use elsewhere in this file.
    If it equals `distinct_fragments`, NONE of this row's own fragments were found
    in production — there is no content-level evidence at all, only the id
    collision. A real leak leaves at least one of the row's own fragments present.
    """
    if not doc.get("leaked_to_production"):
        return True
    presence = doc["presence_in_legal_unified"]
    return presence["fragments_absent_there"] < presence["distinct_fragments"]


def _identity_not_named_from_losing_source(doc: dict) -> bool:
    """True unless a `contradictory` row names `real_identity` from the side its
    own verdict already says the text contradicts.

    identity.verdict == "contradictory" means, by this file's own vocabulary,
    "metadata and text name DIFFERENT instruments" — so within a contradictory
    row, text and metadata already disagree by definition; the interesting
    question is only which side `real_identity` was drawn from. §4.3 makes the
    instrument's OWN TEXT authoritative over metadata and filename. A row that
    sets `real_identity` to a value copied verbatim from `stated_in_metadata` (or
    `stated_in_filename`) is naming the identity from the losing side while its
    own `stated_in_text` field, recorded right beside it, disagrees.

    Deliberately scoped to verdict == "contradictory" only:
      - `mistyped` rows have text and metadata AGREEING on the instrument (only
        the id's TYPE is wrong, e.g. a Pergub filed as a UU) — real_identity
        legitimately restates metadata there, and that is not this bug.
      - `lost` rows have no identity in the text at all (UNKNOWN placeholders) —
        metadata is the only source there IS, so there is no losing side to have
        preferred over it.
    A verbatim-equality check (not a substring/contains check) is deliberate: this
    repo's most-repeated defect class is guard-over-match, and a row where
    `real_identity` legitimately restates the SAME instrument metadata names, in
    different words, must not be flagged (the PP_6646_2021 shape: real_identity is
    grounded in the filename's subject with a corrected number, not copied from
    either losing field, even though the row is contradictory for other reasons).
    """
    identity = doc["identity"]
    if identity["verdict"] != "contradictory":
        return True
    real = identity.get("real_identity")
    if not real:
        return True
    return real != identity.get("stated_in_metadata") and real != identity.get("stated_in_filename")


def test_a_leak_claim_has_fragment_level_evidence(inventory):
    path, data = inventory
    for doc in data["documents"]:
        assert _leak_claim_is_evidenced(doc), (
            "{}: {} claims leaked_to_production=true but fragments_absent_there "
            "equals distinct_fragments — none of this document's own fragments "
            "were found in production, only the id string collided. A shared "
            "document_id is not evidence of a leak.".format(path.name, doc["document_id"])
        )


def test_identity_is_not_named_from_the_losing_source(inventory):
    path, data = inventory
    for doc in data["documents"]:
        assert _identity_not_named_from_losing_source(doc), (
            "{}: {} is contradictory yet real_identity is copied verbatim from "
            "stated_in_metadata or stated_in_filename — naming the identity from "
            "the side its own verdict says the text contradicts (§4.3: text "
            "outranks metadata and filename).".format(path.name, doc["document_id"])
        )


def test_leak_and_identity_rules_have_guilt_and_innocence_cases():
    """Synthetic proof, independent of what the real inventory currently contains.

    MANDATE §4.9's anti-vacuity concern applies here too: the real file could be
    repaired to zero violating rows (it now is) and the two rules above would
    still report green whether or not they are actually wired correctly. These
    cases exercise both predicates directly against the exact shapes measured
    2026-08-25, so a regression in the predicate itself — not just an absence of
    bad data — is what keeps this test honest.
    """

    def leak_doc(fragments_absent, distinct_fragments, claim=True):
        return {
            "leaked_to_production": claim,
            "presence_in_legal_unified": {
                "fragments_absent_there": fragments_absent,
                "distinct_fragments": distinct_fragments,
            },
        }

    # guilt: the exact shape of the false UU_13_2016 claim — all 7 of this row's
    # own 7 fragments are absent from production, yet a leak is asserted anyway.
    assert not _leak_claim_is_evidenced(leak_doc(7, 7))
    # innocence: partial overlap IS real fragment-level evidence — the shape of
    # the three genuine leaks still standing in this file (UU_14_2023 4/804,
    # PP_18_2025 1/99, UU_17_2026 13/49 absent).
    assert _leak_claim_is_evidenced(leak_doc(4, 804))
    assert _leak_claim_is_evidenced(leak_doc(1, 99))
    # innocence: no leak claimed at all, regardless of fragment counts — the
    # ordinary shape of most rows in this file.
    assert _leak_claim_is_evidenced(leak_doc(48, 48, claim=False))

    def identity_doc(verdict, real, metadata, filename="whatever.pdf"):
        return {
            "identity": {
                "verdict": verdict,
                "real_identity": real,
                "stated_in_metadata": metadata,
                "stated_in_filename": filename,
            }
        }

    # guilt: the exact shape of the false Permen_32_2022 claim — real_identity is
    # a verbatim copy of stated_in_metadata on a contradictory row.
    assert not _identity_not_named_from_losing_source(
        identity_doc(
            "contradictory",
            "PER-7/PJ/2025 — NIK-NPWP Coretax",
            "PER-7/PJ/2025 — NIK-NPWP Coretax",
            "PER-7-PJ-2025.pdf",
        )
    )
    # guilt, filename side: same inversion, sourced from the filename instead of
    # the metadata field.
    assert not _identity_not_named_from_losing_source(
        identity_doc("contradictory", "legal_number=6646", "something_else", "legal_number=6646")
    )
    # innocence: the shape of the genuine PP_6646_2021 row — real_identity is
    # drawn from NEITHER losing field verbatim (synthesized from the filename's
    # subject plus a corrected number), even though the row is contradictory.
    assert _identity_not_named_from_losing_source(
        identity_doc(
            "contradictory",
            "PP 34/2021 — Penggunaan Tenaga Kerja Asing",
            "legal_number=6646",
            "pp_34_2021_penggunaan_tka.pdf",
        )
    )
    # innocence: real_identity is null — nothing was named, so there is no source
    # to have inverted (the UU_13_2016 / UU_31_2010 / Perda_15_2019 shape).
    assert _identity_not_named_from_losing_source(identity_doc("contradictory", None, "x", "y"))
    # innocence: verdict is "lost", not "contradictory" — metadata IS legitimately
    # the identity source when text carries no identity at all (the
    # TAX_UNKNOWN_UNKNOWN shape). Verbatim equality on purpose, to prove the
    # verdict gate — not the string comparison — is what lets this through.
    assert _identity_not_named_from_losing_source(
        identity_doc("lost", "KEP-55/PJ/2026 — X", "KEP-55/PJ/2026 — X", "n/a")
    )
    # innocence: verdict "mistyped" — text and metadata already agree, only the
    # id's TYPE is wrong; real_identity legitimately restates metadata (the
    # UU_14_2023 shape). Verbatim equality again on purpose, same reason.
    assert _identity_not_named_from_losing_source(
        identity_doc("mistyped", "Pergub Bali 14/2023 - X", "Pergub Bali 14/2023 - X", "n/a")
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


def test_the_retirement_lint_check_is_not_examining_zero_inventories():
    """Anti-vacuity for the test above, same pattern as
    test_the_ledger_mirror_check_is_not_examining_zero_findings below.

    The cross-source check above SKIPS twice — once for `kind != retired_collection`
    (defence in depth; the `inventory` fixture already filters this), once for
    `decision.choice != retire_as_target`. Nothing forces at least one real file to
    take the second branch. If none ever did, the lint would never run against a
    real ingest entrypoint list and every parametrisation would read green while
    checking nothing — exactly the shape MANDATE.md §4.9 warns against, and the
    same failure class `test_the_ledger_mirror_check_is_not_examining_zero_findings`
    already guards for `open_findings`.
    """
    retired_as_target = []
    for path in _inventories():
        data = _load(path)
        if data.get("kind") != OWNED_KIND:
            continue
        if (data.get("decision") or {}).get("choice") == "retire_as_target":
            retired_as_target.append(path.name)
    assert retired_as_target, (
        "no kb/inventory/*.yaml with kind=retired_collection declares "
        "decision.choice=retire_as_target, so "
        "test_a_retired_collection_is_named_by_no_ingest_entrypoint skips on every "
        "parametrisation and is passing over an empty set. Either no collection is "
        "currently queued for retirement — delete this pair of tests and say so — "
        "or the field has been renamed and the gate now points at nothing"
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


def test_the_gate_this_module_defers_topic_inventories_to_actually_exists():
    """This module SKIPS every kind='topic' file saying it is "owned by another gate".

    Measured 2026-08-25, before `test_kb_topic_contract.py` was written: that
    sentence was false. A three-line topic inventory whose only content was the
    word `nonsense` passed this entire suite with rc=0 — one test looked at it,
    skipped, and named an owner that did not exist. A defensive skip pointing at
    a missing owner is worse than no skip, because it reads as coverage to
    everyone downstream, including whoever adds the next `kind`.

    So the deferral is now interlocked: delete or rename the topic gate and this
    goes red, instead of quietly reopening the hole. The same interlock runs in
    the other direction in that file.
    """
    owner = Path(__file__).with_name("test_kb_topic_contract.py")
    assert owner.is_file(), (
        f"{owner.name} is missing, but this module still skips kind='topic' files as "
        f"'owned by another gate' — that owner is gone and topic inventories are now "
        f"judged by nobody"
    )
    source = owner.read_text(encoding="utf-8")
    assert 'OWNED_KIND = "topic"' in source, (
        f"{owner.name} exists but no longer claims kind='topic' — the deferral in this "
        f"module now points at a gate that has stopped owning what it defers"
    )
    for rule in ("def check_topic(", "def check_journey(", "def check_topic_inventory("):
        assert rule in source, f"{owner.name} no longer defines {rule!r}"


GATED_DIRS = ("topics", "journeys", "inventory")


def unreadable_artifacts(relative_paths) -> list[str]:
    """Of these kb/-relative yaml paths, the ones no gate will ever parse.

    Every gate in this campaign globs `kb/<named-dir>/*.yaml` — one level deep,
    that extension, those three directories. Three shapes therefore fall outside
    all of them, and a completeness review on 2026-08-26 produced a concrete
    artifact for each:

      kb/tax.yaml            top level, read by nobody (this happened, 2026-08-25)
      kb/inventory/tax.yml   right folder, wrong extension: glob("*.yaml") misses it
      kb/inventory/archive/tax.yaml   one level too deep, the globs are not recursive

    The first version of this gate checked only the top level with two literal
    globs, so the second and third were invisible to the guard written to catch
    exactly this class.
    """
    strays = []
    for relative in relative_paths:
        parts = Path(relative).parts
        if len(parts) == 2 and parts[0] in GATED_DIRS and parts[1].endswith(".yaml"):
            continue
        strays.append(relative)
    return sorted(strays)


def test_innocence_a_yaml_in_a_gated_directory_is_read():
    assert unreadable_artifacts(["inventory/tax.yaml", "topics/company.yaml"]) == []


def test_guilt_a_yaml_at_the_top_level_is_read_by_nobody():
    assert unreadable_artifacts(["tax.yaml"]) == ["tax.yaml"]


def test_guilt_a_yml_extension_in_a_gated_directory_is_read_by_nobody():
    """The globs say `*.yaml`. A `.yml` sits in the right folder and is parsed
    by no gate — the shape the depth-1 version of this guard could not see."""
    assert unreadable_artifacts(["inventory/tax.yml"]) == ["inventory/tax.yml"]


def test_guilt_a_nested_folder_hides_a_yaml_from_every_glob():
    assert unreadable_artifacts(["inventory/archive/tax.yaml"]) == ["inventory/archive/tax.yaml"]


def test_guilt_an_ungated_top_level_directory_is_not_a_hiding_place():
    assert unreadable_artifacts(["ops/config.yaml"]) == ["ops/config.yaml"]


def test_no_artifact_sits_where_no_gate_looks(capsys):
    """A yaml directly under kb/ is read by nothing, and nothing would say so.

    Every gate in this campaign scans a NAMED subdirectory — kb/topics, kb/journeys,
    kb/inventory. A file at kb/<topic>.yaml is therefore parsed by no test, counted
    in no census and refuted by no contract: it can be wrong forever in silence.

    This is not hypothetical. On 2026-08-25 a malformed `cp` left kb/tax.yaml — a
    stray duplicate of the tax INVENTORY — and a `git add -A` committed it. Nothing
    failed, because nothing was looking. It is the campaign's own thesis turned on
    its own working directory: an artifact that no gate reads is not an artifact.
    """
    kb = _repo_root() / "kb"
    found = sorted(
        str(path.relative_to(kb)) for ext in ("*.yaml", "*.yml") for path in kb.rglob(ext)
    )
    strays = unreadable_artifacts(found)
    print(f"kb/: {len(found)} yaml file(s), {len(strays)} that no gate reads")
    assert strays == [], (
        f"these live under kb/ where no gate reads them: {strays}. Every gate globs "
        f"kb/<named-dir>/*.yaml exactly one level deep, so anything else — the top "
        f"level, a nested folder, or a .yml extension — is parsed by nobody. Move each "
        f"to kb/topics, kb/journeys or kb/inventory as a .yaml, or delete it."
    )


# ── open_findings: a finding recorded where no alarm reads it is not a finding ──
#
# Measured 2026-08-26: `open_findings` appeared NOWHERE outside the yaml that
# declares it — not in this contract, not in kb_inventory_probe.py, not in
# scripts/pending_arms_report.py. Eight findings, three of them severity `high`,
# sat in a field that nothing validates and nothing ages. PENDING-ARMS.md is the
# repo's one nagging surface (pending_arms_report.py alarms on rows open >48h and
# CI enforces its owner vocabulary), so a high-severity finding must appear there
# too. Medium and low deliberately do NOT have to: forcing every finding into the
# ledger would drown the surface that makes it useful, which is the over-match
# edge of cicatrix-superscar #3.

SEVERITIES = frozenset({"high", "medium", "low"})
LEDGER = ROOT / ".claude" / "skills" / "modus" / "PENDING-ARMS.md"


def ledger_declares(finding_id: str, ledger_text: str) -> bool:
    """True when the ledger holds a row whose SUBJECT is this finding.

    Not a substring test, and the difference is not academic. The first version
    of this helper asked `finding_id in ledger_text`, and a mutation run against
    the real ledger could not make it fail: the WIZ-2 and WIZ-3 rows each say
    "for the reason in the WIZ-1 row", so deleting the WIZ-1 row entirely left
    the string "WIZ-1" in the file and the guard stayed green. A cross-reference
    was satisfying a rule about existence — cicatrix-superscar #3 in the guard
    written to enforce this campaign's own discipline, caught by its own mutation.

    A bare substring also cannot tell WIZ-1 from WIZ-10. Ledger rows write their
    subject as `**WIZ-1 — title**`; prose referring to another row does not.
    """
    marker = f"**{finding_id} \u2014"  # bold id followed by an em dash
    # `marker in line` alone was still not enough. A completeness review on
    # 2026-08-26 passed all three of these with no row present at all:
    #     <!-- **WIZ-99 - fake** -->
    #     ```md\n**WIZ-99 - fake**\n```
    #     > **WIZ-99 - quoted from a row that was deleted**
    # A comment, a fenced block and a blockquote are not rows. Every real row in
    # PENDING-ARMS.md begins `- opened `, so the line must BE a row, not merely
    # contain the marker somewhere. (Lookalike dashes were checked and correctly
    # rejected already: U+2013 and U+2015 do not match the em dash U+2014.)
    return any(
        line.lstrip().startswith("- opened ") and marker in line
        for line in ledger_text.splitlines()
    )


def unmirrored_high_findings(findings, ledger_text: str) -> list[str]:
    """Ids of severity=high findings the ledger does not declare a row for.

    Pure, so both guilt and innocence are testable without touching a real file.
    """
    missing = []
    for finding in findings or []:
        if finding.get("severity") != "high":
            continue
        finding_id = finding.get("id") or ""
        # A missing id would make any containment test true, so a nameless high
        # finding would satisfy the rule by having no name at all. Caught by this
        # module's own guilt case before it ever shipped.
        if not finding_id or not ledger_declares(finding_id, ledger_text):
            missing.append(finding_id)
    return missing


def test_guilt_a_high_finding_absent_from_the_ledger_is_reported():
    assert unmirrored_high_findings(
        [{"id": "WIZ-99", "severity": "high"}], "an unrelated ledger"
    ) == ["WIZ-99"]


def test_innocence_a_high_finding_present_in_the_ledger_is_not_reported():
    assert unmirrored_high_findings(
        [{"id": "WIZ-99", "severity": "high"}],
        "- opened 2026-01-01 (x) | **WIZ-99 \u2014 the thing** | detail | owner: session",
    ) == []


def test_guilt_a_cross_reference_from_another_row_does_not_count_as_a_row():
    """The evasion that defeated the first version of this guard, on real data.

    Deleting the WIZ-1 row from the real ledger left the string "WIZ-1" behind in
    two sibling rows that mention it in prose, and the substring check stayed
    green. Mentioning a finding is not owning it.
    """
    ledger = (
        "- opened 2026-01-01 (x) | **WIZ-2 \u2014 other thing** | promoted for the "
        "reason in the WIZ-1 row | owner: session"
    )
    assert unmirrored_high_findings([{"id": "WIZ-1", "severity": "high"}], ledger) == ["WIZ-1"]


def test_guilt_a_longer_id_does_not_satisfy_a_shorter_one():
    """WIZ-1 is a prefix of WIZ-10. A containment test cannot tell them apart,
    and the day a tenth finding is opened the first one silently stops being
    checked."""
    ledger = "- opened 2026-01-01 (x) | **WIZ-10 \u2014 the tenth** | d | owner: session"
    assert unmirrored_high_findings([{"id": "WIZ-1", "severity": "high"}], ledger) == ["WIZ-1"]


def test_innocence_a_medium_finding_is_never_required_to_be_in_the_ledger():
    """The ledger is a nagging surface; filling it with low-severity rows is how
    it stops being read. Only `high` is mirrored."""
    assert unmirrored_high_findings(
        [{"id": "WIZ-4", "severity": "medium"}, {"id": "WIZ-8", "severity": "low"}], ""
    ) == []


def test_guilt_a_high_finding_with_no_id_cannot_pass_by_being_nameless():
    """An empty id would be `"" in ledger_text` -> True for any text, so a
    nameless finding would silently satisfy the rule. It must be reported."""
    assert unmirrored_high_findings([{"severity": "high"}], "any ledger text") == [""]


def test_every_finding_declares_a_known_severity(inventory):
    path, data = inventory
    for finding in data.get("open_findings") or []:
        severity = finding.get("severity")
        assert severity in SEVERITIES, (
            f"{path.name}: finding {finding.get('id')!r} declares severity "
            f"{severity!r}, which is outside {sorted(SEVERITIES)}. A severity this "
            f"gate does not recognise is a finding it cannot route"
        )


def test_every_high_severity_finding_is_mirrored_in_the_pending_arms_ledger(inventory, capsys):
    path, data = inventory
    findings = data.get("open_findings") or []
    ledger_text = LEDGER.read_text(encoding="utf-8")
    missing = unmirrored_high_findings(findings, ledger_text)
    high = [f for f in findings if f.get("severity") == "high"]
    print(f"{path.name}: {len(high)} high finding(s) checked against the ledger")
    assert not missing, (
        f"{path.name} records {missing} at severity=high, but {LEDGER.name} does not "
        f"mention them. open_findings is read by no alarm — it is not validated by "
        f"the probe and not aged by pending_arms_report.py — so a high finding that "
        f"lives only there will never nag anyone. Add a ledger row per id"
    )


def test_the_ledger_mirror_check_is_not_examining_zero_findings():
    """Anti-vacuity for the test above.

    Every assertion there is over `open_findings`; if no inventory declared any
    high finding, the check would be green while examining nothing — and would
    stay green through the day someone adds one. This asserts the corpus it
    guards is non-empty, so the guard's own silence is never mistaken for proof.
    """
    high_total = 0
    for path in _inventories():
        data = _load(path)
        if data.get("kind") != OWNED_KIND:
            continue
        high_total += sum(
            1 for f in (data.get("open_findings") or []) if f.get("severity") == "high"
        )
    assert high_total > 0, (
        "no inventory declares a single severity=high finding, so the mirror check "
        "above is passing over an empty set. Either the campaign genuinely has none "
        "left — delete this pair of tests and say so — or the field has been renamed "
        "and the gate is now pointed at nothing"
    )
