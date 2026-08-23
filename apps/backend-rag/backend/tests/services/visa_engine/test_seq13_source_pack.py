"""seq-13 JOIN — gates for the assembled ``rulepack-prod-013.source.json``
(see ``backend.scripts.visa_engine.fold_pack_seq13_source``).

This module SKIPS cleanly (not error, not red) unless BOTH of this fold's
inputs exist on disk: ``rulepack-prod-013.rules-only.json`` (PR #4660,
``fold_pack_seq13_rules.py``) and the s13-fresh lane's freshness restamp
JSON. Neither is guaranteed to be present in every checkout of this
branch — the rules-only half ships in a separate, independently-armed PR,
and the freshness half is a research capture from a third lane. An absent
input here is a legitimate pre-join state, not a defect (contrast
``test_seq12_pack.py``, which does NOT skip: seq-12 ships its pack in the
same PR as its single-source fold).

Checks, each verified against the real files on disk or a fresh
``assemble_payload()`` call — never eyeballed:

(a) chain gate — ``previous_payload_sha256`` equals the RECOMPUTED
    SHA256(JCS(...)) of seq-12's own SIGNED payload declaration, itself
    cross-checked against a fresh re-hash of the seq-12 SOURCE bytes.
    identity — ``sequence == 13``, ``rule_pack_id`` matches the uuid5
    convention recomputed in-test (never imported from the fold module as
    a trusted constant).
(b) complement-of-the-rules-fold — ``rules`` in the combined pack equals
    the rules-only artifact's ``rules`` byte-for-byte, and everything
    OUTSIDE ``rules`` in the rules-only artifact equals seq-12
    byte-for-byte (the rules lane kept its own promise); the freshness
    input carries no ``rules``/``products`` key at all.
(c) restamp parity — exactly 18 source_records differ from seq-12, each
    ONLY in ``verified_at``/``verified_by``; the restamped set is exactly
    the OFFICIAL_PORTAL set (entity, not a frozen id list); every restamp
    advances the clock past what the freshness input declares as the
    PRIOR value, cross-checked against seq-12's actual bytes (ledger
    drift); no restamp is timestamped after the pack's own
    ``created_at``; ``content_sha256`` is byte-identical on all 28
    records.
(d) byte-invariance — products and the 10 non-restamped source_records
    are fully identical to seq-12; every top-level key outside the
    identity set is identical.
(e) regeneration parity — the disk file is canonically identical to what
    ``fold_pack_seq13_source.assemble_payload()`` produces right now, and
    calling it twice in a row is canonically identical (idempotence).
(f) guard mutation tests — for each hard guard in the fold, a
    deliberately-broken input is shown to raise ``FoldPackError`` with
    the module's OWN (re-imported, not re-implemented) machinery, proving
    the guard is reachable and not vacuously green. Also covers the
    identical-timestamp NOTE: fires on a batch with fewer distinct stamps
    than records, does not fire once every record's stamp is distinct.
"""

from __future__ import annotations

import copy
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
_SEQ12_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-012.source.json"
_SEQ12_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-012.signed.json"
_SEQ13_RULES_ONLY_PATH = _PACKS_DIR / "rulepack-prod-013.rules-only.json"
_SEQ13_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-013.source.json"
_FRESHNESS_INPUT_PATH = (
    _REPO_ROOT / "research" / "visa" / "2026-08-23-seq13-restamp-source-records.json"
)

_EXPECTED_RESTAMP_COUNT = 18
_PORTAL_AUTHORITY_TYPE = "OFFICIAL_PORTAL"
_RESTAMP_FIELDS = frozenset({"verified_at", "verified_by"})
_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)

pytestmark = pytest.mark.skipif(
    not (_SEQ13_RULES_ONLY_PATH.exists() and _FRESHNESS_INPUT_PATH.exists()),
    reason=(
        "seq-13 join needs BOTH rulepack-prod-013.rules-only.json (PR #4660) and "
        "the s13-fresh freshness restamp JSON on disk — at least one is missing. "
        "This module SKIPS, not reds, until both land."
    ),
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _differs_only_in_restamp_fields(baseline: dict[str, Any], candidate: dict[str, Any]) -> bool:
    b = {k: v for k, v in baseline.items() if k not in _RESTAMP_FIELDS}
    c = {k: v for k, v in candidate.items() if k not in _RESTAMP_FIELDS}
    return _canon(b) == _canon(c)


@pytest.fixture(scope="module")
def seq12_source() -> dict[str, Any]:
    return _read_json(_SEQ12_SOURCE_PATH)


@pytest.fixture(scope="module")
def rules_only() -> dict[str, Any]:
    return _read_json(_SEQ13_RULES_ONLY_PATH)


@pytest.fixture(scope="module")
def freshness_input() -> dict[str, Any]:
    return _read_json(_FRESHNESS_INPUT_PATH)


@pytest.fixture(scope="module")
def seq13_source() -> dict[str, Any]:
    return _read_json(_SEQ13_SOURCE_PATH)


# ---------------------------------------------------------------------------
# (a) chain + identity
# ---------------------------------------------------------------------------


class TestChainGate:
    def test_pack_file_exists(self) -> None:
        assert _SEQ13_SOURCE_PATH.exists(), (
            "rulepack-prod-013.source.json is missing — run "
            "`PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq13_source` "
            "once both inputs are present"
        )

    def test_previous_payload_sha256_chains_to_recomputed_seq12(
        self, seq12_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        recomputed = hashlib.sha256(canonicalize_json(seq12_source)).hexdigest()
        seq12_signed = _read_json(_SEQ12_SIGNED_PATH)
        assert recomputed == seq12_signed["payload_sha256"]
        assert seq13_source["previous_payload_sha256"] == recomputed

    def test_sequence_is_13(self, seq13_source: dict[str, Any]) -> None:
        assert seq13_source["sequence"] == 13

    def test_rule_pack_id_matches_uuid5_convention(self, seq13_source: dict[str, Any]) -> None:
        expected = uuid.uuid5(
            uuid.NAMESPACE_URL,
            "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/13",
        )
        assert seq13_source["rule_pack_id"] == str(expected)


# ---------------------------------------------------------------------------
# (b) complement-of-the-rules-fold
# ---------------------------------------------------------------------------


class TestComplementOfRulesFold:
    def test_rules_taken_wholesale_from_rules_only(
        self, rules_only: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        assert _canon(seq13_source["rules"]) == _canon(rules_only["rules"])

    def test_rules_only_non_rules_content_matches_seq12(
        self, seq12_source: dict[str, Any], rules_only: dict[str, Any]
    ) -> None:
        for key in set(seq12_source) | set(rules_only):
            if key in _IDENTITY_KEYS or key == "rules":
                continue
            assert _canon(rules_only.get(key)) == _canon(seq12_source.get(key)), (
                f"rules-only artifact's {key!r} drifted from seq-12 — the rules lane "
                "broke its own contract"
            )
        for key in _IDENTITY_KEYS:
            assert rules_only[key] == seq12_source[key], (
                f"rules-only artifact's {key!r} differs from seq-12's own value — "
                "identity is not the rules lane's to change"
            )

    def test_freshness_input_carries_no_rule_or_product_key(
        self, freshness_input: dict[str, Any]
    ) -> None:
        assert "rules" not in freshness_input
        assert "products" not in freshness_input


# ---------------------------------------------------------------------------
# (c) restamp parity
# ---------------------------------------------------------------------------


class TestRestampParity:
    def test_exactly_18_records_differ_and_only_in_restamp_fields(
        self, seq12_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        seq12_by_id = {r["source_record_id"]: r for r in seq12_source["source_records"]}
        changed = []
        illegal = []
        for record in seq13_source["source_records"]:
            baseline = seq12_by_id[record["source_record_id"]]
            if _canon(record) == _canon(baseline):
                continue
            changed.append(record["source_record_id"])
            if not _differs_only_in_restamp_fields(baseline, record):
                illegal.append(record["source_record_id"])
        assert len(changed) == _EXPECTED_RESTAMP_COUNT
        assert illegal == []

    def test_restamped_set_is_exactly_the_official_portal_set(
        self, seq12_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        seq12_by_id = {r["source_record_id"]: r for r in seq12_source["source_records"]}
        changed = {
            r["source_record_id"]
            for r in seq13_source["source_records"]
            if _canon(r) != _canon(seq12_by_id[r["source_record_id"]])
        }
        portal = {
            r["source_record_id"]
            for r in seq13_source["source_records"]
            if r.get("authority_type") == _PORTAL_AUTHORITY_TYPE
        }
        assert changed == portal
        assert len(portal) == _EXPECTED_RESTAMP_COUNT

    def test_every_restamp_advances_past_freshness_declared_prior(
        self, seq13_source: dict[str, Any], freshness_input: dict[str, Any]
    ) -> None:
        seq13_by_id = {r["source_record_id"]: r for r in seq13_source["source_records"]}
        for fr in freshness_input["restamped_source_records"]:
            sid = fr["source_record_id"]
            pack_record = seq13_by_id[sid]
            assert pack_record["verified_at"] == fr["verified_at"]
            assert pack_record["verified_by"] == fr["verified_by"]
            assert fr["verified_at"] > fr["_prior_verified_at"], (
                f"{sid!r}: freshness input's own declared new/prior stamps do not advance"
            )

    def test_no_restamp_is_after_pack_created_at(self, seq13_source: dict[str, Any]) -> None:
        created_at = seq13_source["created_at"]
        for record in seq13_source["source_records"]:
            if record.get("authority_type") != _PORTAL_AUTHORITY_TYPE:
                continue
            assert record["verified_at"] <= created_at, (
                f"{record['source_record_id']!r}: verified_at {record['verified_at']!r} "
                f"is after the pack's own created_at {created_at!r}"
            )

    def test_content_sha256_untouched_on_all_records(
        self, seq12_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        seq12_by_id = {r["source_record_id"]: r for r in seq12_source["source_records"]}
        drifted = []
        for record in seq13_source["source_records"]:
            baseline = seq12_by_id[record["source_record_id"]]
            if record.get("content_sha256") != baseline.get("content_sha256"):
                drifted.append(record["source_record_id"])
        assert len(seq13_source["source_records"]) == len(seq12_source["source_records"])
        assert drifted == []


# ---------------------------------------------------------------------------
# (d) byte-invariance — products, non-restamped records, top-level keys
# ---------------------------------------------------------------------------


class TestByteInvariance:
    def test_products_canonically_identical_to_seq12(
        self, seq12_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        assert len(seq13_source["products"]) == len(seq12_source["products"])
        assert _canon(seq13_source["products"]) == _canon(seq12_source["products"])

    def test_source_record_set_unchanged(
        self, seq12_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        seq12_ids = {r["source_record_id"] for r in seq12_source["source_records"]}
        seq13_ids = {r["source_record_id"] for r in seq13_source["source_records"]}
        assert seq12_ids == seq13_ids
        assert len(seq13_source["source_records"]) == len(seq12_source["source_records"])

    def test_non_restamped_records_fully_identical(
        self, seq12_source: dict[str, Any], seq13_source: dict[str, Any], freshness_input: dict[str, Any]
    ) -> None:
        restamped_ids = {r["source_record_id"] for r in freshness_input["restamped_source_records"]}
        seq12_by_id = {r["source_record_id"]: r for r in seq12_source["source_records"]}
        drifted = []
        checked = 0
        for record in seq13_source["source_records"]:
            if record["source_record_id"] in restamped_ids:
                continue
            checked += 1
            if _canon(record) != _canon(seq12_by_id[record["source_record_id"]]):
                drifted.append(record["source_record_id"])
        assert checked == len(seq13_source["source_records"]) - _EXPECTED_RESTAMP_COUNT
        assert drifted == []

    def test_top_level_keys_other_than_identity_unchanged(
        self, seq12_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        for key in set(seq12_source) | set(seq13_source):
            if key in _IDENTITY_KEYS or key in ("rules", "source_records"):
                continue
            assert _canon(seq13_source.get(key)) == _canon(seq12_source.get(key)), (
                f"top-level key {key!r} drifted from seq-12"
            )


# ---------------------------------------------------------------------------
# (e) regeneration parity + idempotence
# ---------------------------------------------------------------------------


class TestRegenerationParity:
    def test_disk_pack_equals_freshly_assembled_payload(self, seq13_source: dict[str, Any]) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source

        regenerated = fold_pack_seq13_source.assemble_payload()
        assert (
            hashlib.sha256(canonicalize_json(regenerated)).hexdigest()
            == hashlib.sha256(canonicalize_json(seq13_source)).hexdigest()
        )

    def test_two_consecutive_runs_are_byte_identical(self) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source

        first = fold_pack_seq13_source.assemble_payload()
        second = fold_pack_seq13_source.assemble_payload()
        assert canonicalize_json(first) == canonicalize_json(second)


# ---------------------------------------------------------------------------
# (f) guard mutation tests — red-then-green on each hard guard, using the
# module's OWN functions (never a reimplementation) against deliberately
# broken in-memory copies of the real inputs.
# ---------------------------------------------------------------------------


class TestGuardsFireOnMutation:
    def test_chain_hash_guard_fires_on_wrong_expected_anchor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        monkeypatch.setattr(m, "_EXPECTED_SEQ12_PAYLOAD_SHA256", "0" * 64)
        with pytest.raises(m.FoldPackError, match="the signed seq-12 on disk is not"):
            m.assemble_payload()

    def test_rule_pack_id_guard_fires_on_wrong_expected_uuid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        monkeypatch.setattr(m, "_EXPECTED_SEQ13_RULE_PACK_ID", uuid.uuid4())
        with pytest.raises(m.FoldPackError, match="rule_pack_id convention drifted"):
            m.assemble_payload()

    def test_rules_only_identity_drift_guard_fires(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rules_only: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(rules_only)
        mutated["created_by"] = "someone.who.should.not.touch.identity"
        bad_path = tmp_path / "rulepack-prod-013.rules-only.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_SEQ13_RULES_ONLY", bad_path)
        with pytest.raises(m.FoldPackError, match="declares no identity change"):
            m.assemble_payload()

    def test_rules_only_products_drift_guard_fires(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rules_only: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(rules_only)
        mutated["products"] = list(mutated["products"])[:-1]  # drop one product
        bad_path = tmp_path / "rulepack-prod-013.rules-only.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_SEQ13_RULES_ONLY", bad_path)
        with pytest.raises(m.FoldPackError, match="owns neither products nor source_records"):
            m.assemble_payload()

    def test_freshness_forbidden_key_guard_fires(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, freshness_input: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(freshness_input)
        mutated["products"] = []
        bad_path = tmp_path / "freshness.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_FRESHNESS_INPUT", bad_path)
        with pytest.raises(m.FoldPackError, match="owns only source_records"):
            m.assemble_payload()

    def test_freshness_wrong_record_count_guard_fires(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, freshness_input: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(freshness_input)
        mutated["restamped_source_records"] = mutated["restamped_source_records"][:-1]
        bad_path = tmp_path / "freshness.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_FRESHNESS_INPUT", bad_path)
        with pytest.raises(m.FoldPackError, match=f"expected exactly {_EXPECTED_RESTAMP_COUNT} restamps"):
            m.assemble_payload()

    def test_freshness_ledger_drift_guard_fires(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, freshness_input: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(freshness_input)
        mutated["restamped_source_records"][0]["_prior_verified_at"] = "2099-01-01T00:00:00Z"
        bad_path = tmp_path / "freshness.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_FRESHNESS_INPUT", bad_path)
        with pytest.raises(m.FoldPackError, match="ledger drift"):
            m.assemble_payload()

    def test_freshness_content_drift_guard_fires_on_content_sha256_change(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, freshness_input: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(freshness_input)
        mutated["restamped_source_records"][0]["content_sha256"] = "f" * 64
        bad_path = tmp_path / "freshness.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_FRESHNESS_INPUT", bad_path)
        with pytest.raises(m.FoldPackError, match="changed beyond verified_at/verified_by"):
            m.assemble_payload()

    def test_freshness_backward_stamp_guard_fires(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, freshness_input: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(freshness_input)
        rec = mutated["restamped_source_records"][0]
        rec["verified_at"] = rec["_prior_verified_at"]  # holds time still
        bad_path = tmp_path / "freshness.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_FRESHNESS_INPUT", bad_path)
        with pytest.raises(m.FoldPackError, match="does not advance past the prior"):
            m.assemble_payload()

    def test_freshness_future_stamp_guard_fires(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, freshness_input: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(freshness_input)
        mutated["restamped_source_records"][0]["verified_at"] = "2099-01-01T00:00:00Z"
        bad_path = tmp_path / "freshness.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_FRESHNESS_INPUT", bad_path)
        with pytest.raises(m.FoldPackError, match="is after this pack's own created_at"):
            m.assemble_payload()

    def test_freshness_entity_mismatch_guard_fires(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, freshness_input: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(freshness_input)
        mutated["restamped_source_records"] = mutated["restamped_source_records"][1:]
        extra = copy.deepcopy(freshness_input["restamped_source_records"][0])
        extra["source_record_id"] = str(uuid.uuid4())
        extra["_prior_verified_at"] = "2020-01-01T00:00:00Z"
        extra["_prior_verified_by"] = "nobody"
        mutated["restamped_source_records"].append(extra)
        bad_path = tmp_path / "freshness.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_FRESHNESS_INPUT", bad_path)
        with pytest.raises(m.FoldPackError, match="not exactly the OFFICIAL_PORTAL set"):
            m.assemble_payload()

    def test_missing_rules_only_input_raises_clear_error_not_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        monkeypatch.setattr(m, "_SEQ13_RULES_ONLY", tmp_path / "does-not-exist.json")
        with pytest.raises(m.FoldPackError, match="not found at"):
            m.assemble_payload()

    def test_missing_freshness_input_raises_clear_error_not_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        monkeypatch.setattr(m, "_FRESHNESS_INPUT", tmp_path / "does-not-exist.json")
        with pytest.raises(m.FoldPackError, match="not found at"):
            m.assemble_payload()


class TestIdenticalTimestampNote:
    """The identical-timestamp shape is FLAGGED, not rejected (see the
    fold module's docstring for the reasoning). These prove the flag is
    reachable (fires on the real, current batch of 18 identical stamps)
    and precise (does NOT fire once every stamp in the batch is made
    distinct) — a guard never exercised in both directions is not
    verified."""

    def test_note_fires_on_the_real_identical_batch(self, capsys: pytest.CaptureFixture[str]) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        m.assemble_payload()
        captured = capsys.readouterr()
        assert "distinct verified_at value(s)" in captured.err

    def test_note_does_not_fire_once_every_stamp_is_distinct(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        freshness_input: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from backend.scripts.visa_engine import fold_pack_seq13_source as m

        mutated = copy.deepcopy(freshness_input)
        assert len(mutated["restamped_source_records"]) <= 60, "helper below assumes < 60 records"
        for i, rec in enumerate(mutated["restamped_source_records"]):
            # Still a legal UTC-Z shape, still after _prior_verified_at,
            # still not after created_at — only made pairwise distinct via
            # the seconds field.
            rec["verified_at"] = f"2026-08-23T06:14:{i:02d}Z"
        bad_path = tmp_path / "freshness.json"
        bad_path.write_text(json.dumps(mutated), encoding="utf-8")
        monkeypatch.setattr(m, "_FRESHNESS_INPUT", bad_path)

        m.assemble_payload()
        captured = capsys.readouterr()
        assert "distinct verified_at value(s)" not in captured.err
