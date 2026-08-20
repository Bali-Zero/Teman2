"""seq-12 freshness re-stamp — gates for the assembled
``rulepack-prod-012.source.json`` (see
``backend.scripts.visa_engine.fold_pack_seq12``).

Unlike ``test_seq11_pack.py`` this module does NOT skip when the pack file
is missing: seq-12 ships in the same PR as its fold, so an absent
``rulepack-prod-012.source.json`` is a defect (armed-on-paper, scar family
#2), never a legitimate pre-fold state. Six checks, each verified against
the real files on disk:

(a) chain gate — seq-12's ``previous_payload_sha256`` equals the
    RECOMPUTED SHA256(JCS(...)) of seq-11's own source payload (never a
    declared-field-vs-declared-field comparison — the house pattern from
    ``test_seq10_pack.py``/``test_seq11_pack.py``, one generation later).
(b) identity — ``sequence == 12``, ``rule_pack_id`` matches the uuid5
    convention recomputed in-test (never imported from the fold module as
    a trusted constant).
(c) restamp parity — exactly 18 source_records differ from seq-11, each
    ONLY in ``verified_at``/``verified_by``; the restamped set is exactly
    the OFFICIAL_PORTAL set (entity, not a frozen id list); every restamp
    advances the clock; every restamped stamp equals the inc5 edits-file
    ledger value (pack ↔ capture-ledger parity); ``content_sha256`` is
    byte-identical on all 28 records — with a positive control proving
    the only-restamp-fields-differ checker CAN fail on a mutated record.
(d) byte-invariance — rules and products are canonically identical to
    seq-11's as WHOLE collections (this fold declares zero edits in
    either); the 10 non-restamped source_records are fully identical;
    every top-level key outside the identity set is identical.
(e) regeneration parity — the disk file is canonically identical to what
    ``fold_pack_seq12.assemble_payload()`` produces right now (the fold
    is deterministic; a hand-edited pack diverges here). This is the one
    test that imports the fold module — the property checks above stay
    independent re-derivations (W100: a test that reuses the code it is
    grading is not evidence).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from backend.services.visa_engine.bundle import canonicalize_json

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS_DIR = (
    _REPO_ROOT
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
)
_SEQ11_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-011.source.json"
_SEQ11_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-011.signed.json"
_SEQ12_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-012.source.json"

_RESTAMP_EDITS_PATH = (
    _REPO_ROOT
    / "research"
    / "visa"
    / "doctrine-factory"
    / "e5"
    / "inc5-pack-edits"
    / "source-restamp-edits.json"
)

_EXPECTED_RESTAMP_COUNT = 18
_PORTAL_AUTHORITY_TYPE = "OFFICIAL_PORTAL"
_RESTAMP_FIELDS = frozenset({"verified_at", "verified_by"})


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _differs_only_in_restamp_fields(baseline: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """True iff the two records are canonically identical once
    ``verified_at``/``verified_by`` are removed from both. Independent
    re-implementation (not imported from the fold module)."""

    b = {k: v for k, v in baseline.items() if k not in _RESTAMP_FIELDS}
    c = {k: v for k, v in candidate.items() if k not in _RESTAMP_FIELDS}
    return _canon(b) == _canon(c)


@pytest.fixture(scope="module")
def seq11_source() -> dict[str, Any]:
    return _read_json(_SEQ11_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq12_source() -> dict[str, Any]:
    return _read_json(_SEQ12_SOURCE_PATH)


@pytest.fixture(scope="module")
def restamp_edits() -> dict[str, Any]:
    return _read_json(_RESTAMP_EDITS_PATH)


# ---------------------------------------------------------------------------
# (a) chain + (b) identity
# ---------------------------------------------------------------------------


class TestChainGate:
    def test_pack_file_exists(self) -> None:
        assert _SEQ12_SOURCE_PATH.exists(), (
            "rulepack-prod-012.source.json is missing — the seq-12 fold ships "
            "in the same PR as this test; an absent pack is a defect, not a "
            "pre-fold state"
        )

    def test_previous_payload_sha256_chains_to_recomputed_seq11(
        self, seq11_source: dict[str, Any], seq12_source: dict[str, Any]
    ) -> None:
        recomputed = hashlib.sha256(canonicalize_json(seq11_source)).hexdigest()
        seq11_signed = _read_json(_SEQ11_SIGNED_PATH)
        assert recomputed == seq11_signed["payload_sha256"]
        assert seq12_source["previous_payload_sha256"] == recomputed

    def test_sequence_is_12(self, seq12_source: dict[str, Any]) -> None:
        assert seq12_source["sequence"] == 12

    def test_rule_pack_id_matches_uuid5_convention(self, seq12_source: dict[str, Any]) -> None:
        expected = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/12",
        )
        assert seq12_source["rule_pack_id"] == str(expected)
        # Formula sanity: the same convention reproduces seq-11's id.
        seq11_expected = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/11",
        )
        assert str(seq11_expected) == "5c3974ab-bb15-5a73-b74f-f9f0af88a4a7"


# ---------------------------------------------------------------------------
# (c) restamp parity — the one declared edit, held to its exact shape
# ---------------------------------------------------------------------------


class TestRestampParity:
    def test_exactly_18_records_differ_and_only_in_restamp_fields(
        self, seq11_source: dict[str, Any], seq12_source: dict[str, Any]
    ) -> None:
        seq11_by_id = {r["source_record_id"]: r for r in seq11_source["source_records"]}
        changed = []
        illegal = []
        for record in seq12_source["source_records"]:
            baseline = seq11_by_id[record["source_record_id"]]
            if _canon(record) == _canon(baseline):
                continue
            changed.append(record["source_record_id"])
            if not _differs_only_in_restamp_fields(baseline, record):
                illegal.append(record["source_record_id"])
        assert len(changed) == _EXPECTED_RESTAMP_COUNT
        assert illegal == []

    def test_restamped_set_is_exactly_the_official_portal_set(
        self, seq11_source: dict[str, Any], seq12_source: dict[str, Any]
    ) -> None:
        seq11_by_id = {r["source_record_id"]: r for r in seq11_source["source_records"]}
        changed = {
            r["source_record_id"]
            for r in seq12_source["source_records"]
            if _canon(r) != _canon(seq11_by_id[r["source_record_id"]])
        }
        portal = {
            r["source_record_id"]
            for r in seq12_source["source_records"]
            if r.get("authority_type") == _PORTAL_AUTHORITY_TYPE
        }
        assert changed == portal
        assert len(portal) == _EXPECTED_RESTAMP_COUNT

    def test_every_restamp_advances_the_clock(
        self, seq11_source: dict[str, Any], seq12_source: dict[str, Any]
    ) -> None:
        seq11_by_id = {r["source_record_id"]: r for r in seq11_source["source_records"]}
        not_advanced = []
        checked = 0
        for record in seq12_source["source_records"]:
            baseline = seq11_by_id[record["source_record_id"]]
            if record["verified_at"] == baseline["verified_at"]:
                continue
            checked += 1
            # Both stamps are "YYYY-MM-DDTHH:MM:SSZ" UTC — lexicographic
            # order is chronological for this fixed shape.
            if not record["verified_at"] > baseline["verified_at"]:
                not_advanced.append(record["source_record_id"])
        assert checked == _EXPECTED_RESTAMP_COUNT
        assert not_advanced == []

    def test_pack_stamps_equal_the_inc5_ledger(
        self, seq12_source: dict[str, Any], restamp_edits: dict[str, Any]
    ) -> None:
        seq12_by_id = {r["source_record_id"]: r for r in seq12_source["source_records"]}
        mismatches = []
        assert len(restamp_edits["restamps"]) == _EXPECTED_RESTAMP_COUNT
        for edit in restamp_edits["restamps"]:
            record = seq12_by_id[edit["source_record_id"]]
            if (
                record["verified_at"] != edit["new_verified_at"]
                or record["verified_by"] != edit["new_verified_by"]
            ):
                mismatches.append(edit["source_record_id"])
        assert mismatches == []

    def test_content_sha256_untouched_on_all_records(
        self, seq11_source: dict[str, Any], seq12_source: dict[str, Any]
    ) -> None:
        seq11_by_id = {r["source_record_id"]: r for r in seq11_source["source_records"]}
        drifted = []
        for record in seq12_source["source_records"]:
            baseline = seq11_by_id[record["source_record_id"]]
            if record.get("content_sha256") != baseline.get("content_sha256"):
                drifted.append(record["source_record_id"])
        assert len(seq12_source["source_records"]) == len(seq11_source["source_records"])
        assert drifted == []

    def test_positive_control_checker_detects_a_mutated_record(
        self, seq11_source: dict[str, Any]
    ) -> None:
        baseline = seq11_source["source_records"][0]
        mutated = dict(baseline)
        mutated["title"] = str(baseline.get("title")) + " TAMPERED"
        mutated["verified_at"] = "2099-01-01T00:00:00Z"
        assert _differs_only_in_restamp_fields(baseline, mutated) is False
        # ...while a pure re-stamp of the same record passes the checker.
        restamped = dict(baseline)
        restamped["verified_at"] = "2099-01-01T00:00:00Z"
        restamped["verified_by"] = "someone.else"
        assert _differs_only_in_restamp_fields(baseline, restamped) is True


# ---------------------------------------------------------------------------
# (d) byte-invariance — rules, products, non-restamped records, top level
# ---------------------------------------------------------------------------


class TestByteInvariance:
    def test_rules_canonically_identical_to_seq11(
        self, seq11_source: dict[str, Any], seq12_source: dict[str, Any]
    ) -> None:
        assert len(seq12_source["rules"]) == len(seq11_source["rules"])
        assert _canon(seq12_source["rules"]) == _canon(seq11_source["rules"])

    def test_products_canonically_identical_to_seq11(
        self, seq11_source: dict[str, Any], seq12_source: dict[str, Any]
    ) -> None:
        assert len(seq12_source["products"]) == len(seq11_source["products"])
        assert _canon(seq12_source["products"]) == _canon(seq11_source["products"])

    def test_source_record_set_unchanged(
        self, seq11_source: dict[str, Any], seq12_source: dict[str, Any]
    ) -> None:
        seq11_ids = {r["source_record_id"] for r in seq11_source["source_records"]}
        seq12_ids = {r["source_record_id"] for r in seq12_source["source_records"]}
        assert seq11_ids == seq12_ids
        assert len(seq12_source["source_records"]) == len(seq11_source["source_records"])

    def test_non_restamped_records_fully_identical(
        self,
        seq11_source: dict[str, Any],
        seq12_source: dict[str, Any],
        restamp_edits: dict[str, Any],
    ) -> None:
        restamped_ids = {e["source_record_id"] for e in restamp_edits["restamps"]}
        seq11_by_id = {r["source_record_id"]: r for r in seq11_source["source_records"]}
        drifted = []
        checked = 0
        for record in seq12_source["source_records"]:
            if record["source_record_id"] in restamped_ids:
                continue
            checked += 1
            if _canon(record) != _canon(seq11_by_id[record["source_record_id"]]):
                drifted.append(record["source_record_id"])
        assert checked == len(seq12_source["source_records"]) - _EXPECTED_RESTAMP_COUNT
        assert drifted == []

    def test_top_level_keys_other_than_identity_unchanged(
        self, seq11_source: dict[str, Any], seq12_source: dict[str, Any]
    ) -> None:
        identity_keys = {
            "sequence",
            "version",
            "rule_pack_id",
            "previous_payload_sha256",
            "created_at",
            "created_by",
        }
        for key in set(seq11_source) | set(seq12_source):
            if key in identity_keys or key == "source_records":
                continue
            assert _canon(seq12_source.get(key)) == _canon(seq11_source.get(key)), (
                f"top-level key {key!r} drifted from seq-11"
            )


# ---------------------------------------------------------------------------
# (e) regeneration parity — the disk file IS the fold's output
# ---------------------------------------------------------------------------


class TestRegenerationParity:
    def test_disk_pack_equals_freshly_assembled_payload(
        self, seq12_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq12

        regenerated = fold_pack_seq12.assemble_payload()
        assert (
            hashlib.sha256(canonicalize_json(regenerated)).hexdigest()
            == hashlib.sha256(canonicalize_json(seq12_source)).hexdigest()
        )
