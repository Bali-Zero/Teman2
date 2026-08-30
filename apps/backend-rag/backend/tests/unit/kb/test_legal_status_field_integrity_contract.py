"""The contract `kb/inventory/legal_status.yaml` (kind: field_integrity) obeys.

This is the dedicated gate for `kind: field_integrity`, the same relationship
test_kb_topic_contract.py has to `kind: topic` — test_kb_inventory_contract.py's
generic `inventory` fixture already skips this file (kind != OWNED_KIND="retired_
collection"), so nothing there validates its numbers. This module is what does.

Two kinds of proof live here, deliberately kept apart:
  * static — this artifact's OWN recorded numbers are internally consistent
    (arithmetic, no live Qdrant needed);
  * behavioral — the PURE functions kb/ops/probe_amendment_invariant.py and
    scripts/kb/legal_status_drift_gate.py build their live measurements on are
    correct against synthetic guilt/innocence fixtures, independent of whatever
    the real corpus currently contains (the anti-vacuity discipline this
    campaign's other contract tests already apply: a real file repaired to zero
    violations would leave a purely-static test green whether or not the
    predicate itself still works).

The status_vigensi "must stay green" exception gets its own guilt-AND-innocence
proof against a fully isolated in-memory Qdrant instance (never `legal_unified`,
never any production collection) — a green check that has never been shown
capable of going red is indistinguishable from one nobody wired up.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Hard import, not importorskip: pyyaml is pinned in requirements.lock.txt and
# already imported plainly by test_kb_inventory_contract.py in this same package.
import yaml


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / ".git").exists() and (candidate / "apps").is_dir():
            return candidate
    raise AssertionError(f"repo root not found from {here}")


ROOT = _repo_root()
INVENTORY_PATH = ROOT / "kb" / "inventory" / "legal_status.yaml"


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def probe():
    return _load_module("probe_amendment_invariant", "kb/ops/probe_amendment_invariant.py")


@pytest.fixture(scope="module")
def gate():
    return _load_module("legal_status_drift_gate", "scripts/kb/legal_status_drift_gate.py")


@pytest.fixture(scope="module")
def data():
    assert INVENTORY_PATH.is_file(), f"{INVENTORY_PATH} does not exist"
    return yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))


# ── static: this artifact's own numbers add up ─────────────────────────────────

def test_kind_is_field_integrity(data):
    assert data.get("kind") == "field_integrity"


def test_per_point_distribution_sums_to_measured_points(data):
    ma = data["measured_against"]
    total = sum(ma["per_point"].values())
    assert total == ma["points"], (
        f"per_point sums to {total} but points is {ma['points']} — every point has "
        f"exactly one of dicabut/berlaku/none/absent, so these must be equal"
    )


def test_per_document_distribution_sums_to_distinct_documents(data):
    ma = data["measured_against"]
    total = sum(ma["per_document"].values())
    assert total == ma["distinct_documents"], (
        f"per_document sums to {total} but distinct_documents is "
        f"{ma['distinct_documents']}"
    )


def test_legal_status_key_location_sums_to_measured_points(data):
    ma = data["measured_against"]
    loc = ma["legal_status_key_location"]
    total = loc["flat_top_level_only"] + loc["nested_metadata_only"] + loc["both_locations"] + loc["neither_present"]
    assert total == ma["points"], (
        f"legal_status_key_location sums to {total} but points is {ma['points']}"
    )
    # Cross-checks the field-presence bucket against the value bucket: every point
    # where the key is present (flat, nested, or both) must equal dicabut+berlaku+none.
    present = loc["flat_top_level_only"] + loc["nested_metadata_only"] + loc["both_locations"]
    value_buckets = ma["per_point"]["dicabut"] + ma["per_point"]["berlaku"] + ma["per_point"]["none"]
    assert present == value_buckets, (
        f"{present} points have the legal_status key present, but "
        f"dicabut+berlaku+none sums to {value_buckets} — these describe the same "
        f"set of points two different ways and must agree"
    )
    assert loc["neither_present"] == ma["per_point"]["absent"]


def test_domain_knowledge_summary_matches_its_own_document_list(data):
    dkv = data["domain_knowledge_verification"]
    docs = dkv["documents"]
    assert len(docs) == dkv["summary"]["checked"]
    contradicted = sum(1 for d in docs if d["match"] is False)
    confirmed = sum(1 for d in docs if d["match"] is True)
    assert contradicted == dkv["summary"]["contradicted"]
    assert confirmed == dkv["summary"]["confirmed_correct"]
    assert contradicted + confirmed == len(docs)


def test_every_strict_violation_also_appears_as_a_weak_violation(data):
    """§3's own claim: strict is a STRENGTHENING of weak (amender=berlaku is a
    special case of "any amender status"), so every strict pair must be a subset
    of the weak list — never a disjoint, contradicting pair of tables."""
    ai = data["amendment_invariant"]
    weak_pairs = {(v["amending"], v["amended"]) for v in ai["weak_violations"]}
    for v in ai["strict_violations"]:
        pair = (v["amending"], v["amended"])
        assert pair in weak_pairs, (
            f"{pair} is recorded as a STRICT violation but does not appear in "
            f"weak_violations — strict must always be a subset of weak"
        )


def test_status_vigensi_recorded_as_zero_everywhere(data):
    """This artifact's own recorded claim. The LIVE re-check that this claim still
    holds against production today is scripts/kb/legal_status_drift_gate.py's job,
    not this static test's — this only proves the artifact is internally honest
    about what it claims."""
    sv = data["status_vigensi"]
    assert sv["measured_on_legal_unified"]["hits_flat_or_nested"] == 0
    assert sv["measured_instance_wide"]["hits"] == 0


def test_retrieval_scope_distribution_sums_to_scanned_points(data):
    rs = data["status_vigensi"]["retrieval_scope"]["measured_on_legal_unified"]
    total = rs["absent"] + rs["current"] + rs["historical_only"]
    assert total == rs["points_scanned"]
    # historical_only is a POINT count; historical_only_documents is the distinct
    # set of documents those points belong to -- one document can carry more than
    # one historical_only point, so the document list may legitimately be shorter
    # than the point count, never longer.
    assert 0 < len(rs["historical_only_documents"]) <= rs["historical_only"]


# ── behavioral: resolve_amendment_target guilt/innocence ───────────────────────

def test_guilt_ordinal_amendment_resolves_to_the_amended_instrument(probe):
    """The exact shape of the UU_63_2024 -> UU_6_2011 strict violation."""
    title = ("UU - NO 63 - TAHUN 2024 - TENTANG PERUBAHAN KETIGA ATAS "
             "UNDANG-UNDANG NOMOR 6 TAHUN 2011 TENTANG KEIMIGRASIAN")
    from backend.core.legal.constants import LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV
    from backend.core.legal.metadata_extractor import normalize_document_number
    target = probe.resolve_amendment_target(
        title, LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV, normalize_document_number
    )
    assert target == "UU_6_2011"


def test_guilt_hyphen_ocr_noise_still_resolves(probe):
    """The exact shape of the PP_1_2014 -> UU_27_2007 strict violation: 'UNDANG
    -UNDANG' (a stray space before the hyphen, real OCR line-wrap noise measured
    in this corpus) must still resolve, via the disclosed, scoped hyphen-collapse
    normalization."""
    title = ("PP - NO 1 - TAHUN 2014 - TENTANG PERUBAHAN ATAS UNDANG -UNDANG "
             "NOMOR 27 TAHUN 2007 TENTANG PENGELOLAAN WILAYAH PESISIR")
    from backend.core.legal.constants import LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV
    from backend.core.legal.metadata_extractor import normalize_document_number
    target = probe.resolve_amendment_target(
        title, LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV, normalize_document_number
    )
    assert target == "UU_27_2007"


def test_innocence_a_citation_history_sentence_is_not_the_documents_own_amendment(probe):
    """The exact shape of the UU_23_2002 false-positive this probe's first version
    produced: the document's OWN topic is "Perlindungan Anak", and a LATER clause
    in the same chunk's text quotes a completely different law's amendment
    ("Undang-Undang Nomor 35 tahun 2014 tentang Perubahan atas Undang-Undang Nomor
    23 Tahun 2002") -- resolving THAT would make the document appear to amend
    itself. Anchoring the match to the FIRST word after TENTANG is what prevents
    this; without the anchor this text resolves to UU_23_2002 (itself)."""
    title = ("UU - NO 23 - TAHUN 2002 - TENTANG Perlindungan Anak sebagaimana "
              "telah diubah dengan Undang-Undang Nomor 35 Tahun 2014 tentang "
              "Perubahan atas Undang-Undang Nomor 23 Tahun 2002 tentang "
              "Perlindungan Anak")
    from backend.core.legal.constants import LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV
    from backend.core.legal.metadata_extractor import normalize_document_number
    target = probe.resolve_amendment_target(
        title, LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV, normalize_document_number
    )
    assert target is None, (
        "resolved a target from a citation-history sentence, not the document's "
        "own amendment nature — this is the exact bug this test guards against"
    )


def test_innocence_a_non_amending_title_resolves_to_nothing(probe):
    title = "UU - NO 6 - TAHUN 2011 - TENTANG KEIMIGRASIAN"
    from backend.core.legal.constants import LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV
    from backend.core.legal.metadata_extractor import normalize_document_number
    target = probe.resolve_amendment_target(
        title, LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV, normalize_document_number
    )
    assert target is None


def test_innocence_no_tentang_at_all_resolves_to_nothing(probe):
    from backend.core.legal.constants import LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV
    from backend.core.legal.metadata_extractor import normalize_document_number
    target = probe.resolve_amendment_target(
        "just some fragment with no title structure at all",
        LEGAL_TITLE_PATTERN, LEGAL_TYPE_ABBREV, normalize_document_number,
    )
    assert target is None


# ── behavioral: classify_violations guilt/innocence ─────────────────────────────

def test_guilt_strict_and_weak_both_fire_on_a_true_violation(probe):
    by_status = {"A": "berlaku", "B": "dicabut"}
    result = probe.classify_violations([("A", "B")], by_status)
    assert len(result["strict"]) == 1
    assert len(result["weak"]) == 1


def test_innocence_both_in_force_is_no_violation(probe):
    by_status = {"A": "berlaku", "B": "berlaku"}
    result = probe.classify_violations([("A", "B")], by_status)
    assert result["strict"] == []
    assert result["weak"] == []


def test_guilt_weak_only_when_amender_is_not_berlaku(probe):
    """The Permen_11_2024(dicabut) -> Permen_22_2023(dicabut) shape: weaker
    evidence (the amender is not confidently in force either), so it must appear
    in weak but NOT strict."""
    by_status = {"A": "dicabut", "B": "dicabut"}
    result = probe.classify_violations([("A", "B")], by_status)
    assert result["strict"] == []
    assert len(result["weak"]) == 1


def test_innocence_a_pair_missing_from_by_doc_status_is_skipped(probe):
    """An id resolved outside this corpus (§3's 14 outside-corpus targets) must
    never be silently treated as if it were 'dicabut' or any other status."""
    result = probe.classify_violations([("A", "NOT_IN_CORPUS")], {"A": "berlaku"})
    assert result["strict"] == []
    assert result["weak"] == []


# ── behavioral: drift gate's diff_against_recorded and status_vigensi_regression ─

def _live_stub(**overrides):
    base = {
        "collection": "legal_unified_hybrid_hybrid",
        "points": 84283,
        "distinct_documents": 388,
        "per_point": {"dicabut": 42420, "berlaku": 26107, "none": 9012, "absent": 6744},
        "per_document": {"dicabut": 190, "berlaku": 157, "none": 19, "absent": 8, "mixed": 14},
        "no_context_points": 25832,
        "zero_header_documents": 185,
        "status_vigensi_hits": 0,
    }
    base.update(overrides)
    return base


def test_innocence_identical_recorded_and_live_is_no_drift(gate):
    live = _live_stub()
    recorded_block = {
        "points": live["points"], "distinct_documents": live["distinct_documents"],
        "per_point": live["per_point"], "per_document": live["per_document"],
        "no_context_points": live["no_context_points"],
        "zero_header_documents": live["zero_header_documents"],
    }
    assert gate.diff_against_recorded(recorded_block, live) == []


def test_guilt_a_moved_point_count_is_reported_as_drift(gate):
    live = _live_stub(points=84300)
    recorded_block = {
        "points": 84283, "distinct_documents": live["distinct_documents"],
        "per_point": live["per_point"], "per_document": live["per_document"],
        "no_context_points": live["no_context_points"],
        "zero_header_documents": live["zero_header_documents"],
    }
    findings = gate.diff_against_recorded(recorded_block, live)
    assert findings, "a moved total point count must be reported as drift"


def test_guilt_a_moved_per_point_bucket_is_reported_as_drift(gate):
    live = _live_stub()
    recorded_block = {
        "points": live["points"], "distinct_documents": live["distinct_documents"],
        "per_point": {**live["per_point"], "dicabut": live["per_point"]["dicabut"] + 1},
        "per_document": live["per_document"],
        "no_context_points": live["no_context_points"],
        "zero_header_documents": live["zero_header_documents"],
    }
    findings = gate.diff_against_recorded(recorded_block, live)
    assert any("dicabut" in f for f in findings)


def test_innocence_status_vigensi_absent_is_not_a_regression(gate):
    assert gate.status_vigensi_regression(_live_stub(status_vigensi_hits=0)) is None


def test_guilt_status_vigensi_present_is_a_regression(gate):
    finding = gate.status_vigensi_regression(_live_stub(status_vigensi_hits=3))
    assert finding is not None
    assert "3" in finding


# ── status_vigensi "must stay green" — live guilt-AND-innocence, in-memory Qdrant ─

def test_status_vigensi_regression_guilt_and_innocence(gate):
    """The must_stay_green_exception's own required proof (kb/inventory/
    legal_status.yaml §4): a check that has never been shown capable of going red
    is indistinguishable from one nobody wired up. Runs against a FULLY ISOLATED
    in-memory Qdrant instance -- never legal_unified, never any collection on the
    real server -- created and torn down entirely inside this test."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    client = QdrantClient(location=":memory:")
    client.create_collection(
        "scratch", vectors_config=VectorParams(size=4, distance=Distance.COSINE)
    )

    # Innocence, before any scratch write: status_vigensi absent -> clean.
    client.upsert("scratch", points=[
        PointStruct(id=1, vector=[0.1, 0.2, 0.3, 0.4],
                    payload={"legal_status": "dicabut", "document_id": "SCRATCH_1"}),
    ])
    live_clean = gate.scan_field_integrity(client, "scratch")
    assert live_clean["status_vigensi_hits"] == 0
    assert gate.status_vigensi_regression(live_clean) is None

    # Guilt: populate status_vigensi on a scratch point (never legal_unified, never
    # a real collection) -- the check must go RED.
    client.upsert("scratch", points=[
        PointStruct(id=2, vector=[0.5, 0.6, 0.7, 0.8],
                    payload={"status_vigensi": "dicabut", "document_id": "SCRATCH_2"}),
    ])
    live_dirty = gate.scan_field_integrity(client, "scratch")
    assert live_dirty["status_vigensi_hits"] == 1
    finding = gate.status_vigensi_regression(live_dirty)
    assert finding is not None

    # Innocence again: remove the offending point, confirm it clears.
    client.delete("scratch", points_selector=[2])
    live_clean_again = gate.scan_field_integrity(client, "scratch")
    assert live_clean_again["status_vigensi_hits"] == 0
    assert gate.status_vigensi_regression(live_clean_again) is None
