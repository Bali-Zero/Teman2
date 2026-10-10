"""seq-27 — the 18 OFFICIAL_PORTAL sources re-stamped by the weekly re-attestation organ.

Candidate: organ PR #8105 (``research/visa/2026-10-08-organ-reattest-seq27/``). Proves, each with a
guilt twin where one exists:

* seq-27 chains to the SIGNED seq-26 and mints its identity by the uuid5 convention;
* nothing but identity and the 18 portal stamps moves: rules, products (so every E31A-J
  ``duration_options``) and the 10 non-portal source records are untouched;
* the stamp is the earliest successful read of the ledger, and every receipt is a 200 with the key
  phrase, the record's own canonical URL, judged after the read, with a saved text that carries the
  receipt's fingerprint;
* every judgement is ``judge: fingerprint`` (the visible-text fingerprint equals the attested read
  of 2026-10-07) -- NO model read the pages; that is stated here so no reader assumes otherwise;
* the committed source is what ``fold_pack_generic`` produces from the ledger;
* the committed signed bundle is that source under the PUBLIC production key.

A missing artifact FAILS (``_read_json``), it never skips (cicatrix #2).
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.fold_pack_generic import fold
from backend.scripts.visa_engine.fold_pack_seq25 import (
    PORTAL_AUTHORITY,
    assert_only_expected_changes,
    load_ledger,
)
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_SEQ26_SOURCE = _PACKS / "rulepack-prod-026.source.json"
_SEQ26_SIGNED = _PACKS / "rulepack-prod-026.signed.json"
_SEQ27_SOURCE = _PACKS / "rulepack-prod-027.source.json"
_SEQ27_SIGNED = _PACKS / "rulepack-prod-027.signed.json"
_RESEARCH = _REPO_ROOT / "research/visa"
_LEDGER = _RESEARCH / "2026-10-08-organ-reattest-seq27"

PROD_TRUST_STORE_JSON = json.dumps(
    [
        {
            "kid": "prod-2026-07-1",
            "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",
            "environment": "PRODUCTION",
            "valid_from": "2026-07-19T00:00:00Z",
            "valid_to": None,
            "revoked_at": None,
        }
    ]
)
SEQ26_PAYLOAD_SHA256 = "05511184caf05119ac0adf644601e322d845c276faad3146ea243c507cf23b7f"
#: Digest of the committed source (what the organ's fold printed, re-derived by this lane).
SEQ27_PAYLOAD_SHA256 = "a9098744e0cd8369fb4fe9ca5bef851705cf43dabb1c69398b63b36985cb42d0"
EXPECTED_STAMP = "2026-10-08T13:21:22Z"
FOLD_VERSION = "2026.10.8"
FOLD_CREATED_AT = "2026-10-08T13:21:34Z"
FOLD_CREATED_BY = "organ.pro.visa-reattestation"
FOLD_VERIFIED_BY = "organ-sonnet-20261008"
#: After the fold's created_at; the signing falls after it too.
OBSERVED_AT = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
_PORTAL_MAX_AGE = timedelta(seconds=2764800)
_E31 = ["E31A", "E31B", "E31C", "E31D", "E31E", "E31F", "E31G", "E31H", "E31J"]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk — a witness that never ran proves nothing"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _portals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in payload["source_records"] if r["authority_type"] == PORTAL_AUTHORITY]


@pytest.fixture(scope="module")
def seq26_source() -> dict[str, Any]:
    return _read_json(_SEQ26_SOURCE)


@pytest.fixture(scope="module")
def seq26_signed() -> dict[str, Any]:
    return _read_json(_SEQ26_SIGNED)


@pytest.fixture(scope="module")
def seq27() -> dict[str, Any]:
    return _read_json(_SEQ27_SOURCE)


@pytest.fixture(scope="module")
def seq27_signed() -> dict[str, Any]:
    return _read_json(_SEQ27_SIGNED)


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


def _receipts_and_judgements() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipts = _read_jsonl(next(_LEDGER.glob("*-receipts.jsonl")))
    judgements = _read_jsonl(next(_LEDGER.glob("*-judgements.jsonl")))
    return receipts, judgements


class TestIntegrity:
    def test_chain_and_identity(self, seq26_signed: dict[str, Any], seq27: dict[str, Any]) -> None:
        assert seq26_signed["payload_sha256"] == SEQ26_PAYLOAD_SHA256
        assert seq27["sequence"] == 27
        assert seq27["previous_payload_sha256"] == SEQ26_PAYLOAD_SHA256
        assert seq27["rollback_of_payload_sha256"] is None
        assert seq27["rule_pack_id"] == str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/27",
            )
        )
        assert (seq27["version"], seq27["created_by"], seq27["created_at"]) == (
            FOLD_VERSION,
            FOLD_CREATED_BY,
            FOLD_CREATED_AT,
        )
        assert hashlib.sha256(canonicalize_json(seq27)).hexdigest() == SEQ27_PAYLOAD_SHA256

    def test_the_anchor_source_is_the_signed_seq26_payload(
        self, seq26_source: dict[str, Any], seq26_signed: dict[str, Any]
    ) -> None:
        assert canonicalize_json(seq26_source) == canonicalize_json(seq26_signed["payload"])

    def test_only_identity_and_portal_stamps_move(
        self, seq26_source: dict[str, Any], seq27: dict[str, Any]
    ) -> None:
        assert_only_expected_changes(seq26_source, seq27)
        moved = {
            k
            for k in seq27
            if json.dumps(seq27[k], sort_keys=True) != json.dumps(seq26_source[k], sort_keys=True)
        }
        assert moved == {
            "sequence",
            "previous_payload_sha256",
            "rule_pack_id",
            "created_at",
            "created_by",
            "source_records",
        }
        for key in ("rules", "products", "valid_period", "version"):
            assert seq27[key] == seq26_source[key]

    def test_non_portal_records_are_byte_identical(
        self, seq26_source: dict[str, Any], seq27: dict[str, Any]
    ) -> None:
        before = [
            r for r in seq26_source["source_records"] if r["authority_type"] != PORTAL_AUTHORITY
        ]
        after = [r for r in seq27["source_records"] if r["authority_type"] != PORTAL_AUTHORITY]
        assert len(after) == 10
        assert after == before

    def test_portal_records_move_only_in_their_stamp(
        self, seq26_source: dict[str, Any], seq27: dict[str, Any]
    ) -> None:
        before = {r["source_record_id"]: r for r in _portals(seq26_source)}
        after = {r["source_record_id"]: r for r in _portals(seq27)}
        assert set(before) == set(after) and len(after) == 18
        for rid, record in after.items():
            moved = {k for k in record if record[k] != before[rid][k]}
            assert moved == {"verified_at", "verified_by"}, rid
            assert record["verified_at"] == EXPECTED_STAMP
            assert record["verified_by"] == FOLD_VERIFIED_BY
            assert record["freshness_policy"]["max_age_seconds"] == 2764800

    def test_every_e31_product_keeps_its_duration_options(
        self, seq26_source: dict[str, Any], seq27: dict[str, Any]
    ) -> None:
        old = {p["product_code"]: p for p in seq26_source["products"]}
        new = {p["product_code"]: p for p in seq27["products"]}
        for code in _E31:
            assert new[code]["duration_options"], code
            assert new[code] == old[code], code

    def test_the_freshness_boundary_is_stamp_plus_32_days(self, seq27: dict[str, Any]) -> None:
        stamp = datetime.strptime(EXPECTED_STAMP, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        assert min(r["verified_at"] for r in _portals(seq27)) == EXPECTED_STAMP
        assert stamp + _PORTAL_MAX_AGE == datetime(2026, 11, 9, 13, 21, 22, tzinfo=timezone.utc)

    def test_the_payload_validates_against_the_model(self, seq27: dict[str, Any]) -> None:
        payload = RulePackPayload.model_validate(seq27)
        assert payload.sequence == 27
        assert len(payload.rules) == 113


class TestLedger:
    def test_every_portal_record_has_one_clean_receipt_and_one_fingerprint_judgement(
        self, seq27: dict[str, Any]
    ) -> None:
        receipts, judgements = _receipts_and_judgements()
        portals = {r["source_record_id"]: r for r in _portals(seq27)}
        assert {r["source_record_id"] for r in receipts} == set(portals)
        assert {j["source_record_id"] for j in judgements} == set(portals)
        assert len(receipts) == len(judgements) == 18
        by_id = {r["source_record_id"]: r for r in receipts}
        for j in judgements:
            receipt = by_id[j["source_record_id"]]
            assert receipt["http_status"] == 200 and receipt["key_phrase_found"] is True
            assert receipt["canonical_url"] == receipt["final_url"]
            assert receipt["canonical_url"] == portals[j["source_record_id"]]["canonical_url"]
            assert j["judged_at"] >= receipt["fetched_at"]

    def test_the_judge_is_the_fingerprint_not_a_model(self) -> None:
        """STATED PLAINLY: no model read these pages. Each judgement is 'none' because the
        visible-text fingerprint equals the attested read of 2026-10-07."""
        _, judgements = _receipts_and_judgements()
        assert {j["judge"] for j in judgements} == {"fingerprint"}
        assert {j["semantic_change"] for j in judgements} == {"none"}
        assert all("no model consulted" in j["notes"] for j in judgements)

    def test_the_stamp_is_the_earliest_successful_read(self, seq27: dict[str, Any]) -> None:
        receipts, _ = _receipts_and_judgements()
        assert min(r["fetched_at"] for r in receipts) == EXPECTED_STAMP
        assert {r["verified_at"] for r in _portals(seq27)} == {EXPECTED_STAMP}

    def test_every_saved_text_carries_its_receipts_fingerprint(self) -> None:
        receipts, _ = _receipts_and_judgements()
        assert len(list((_LEDGER / "text").glob("*.txt"))) == 18
        for receipt in receipts:
            text = (_LEDGER / "text" / Path(receipt["text_file"]).name).read_text(encoding="utf-8")
            body = text[:-1] if text.endswith("\n") else text
            assert (
                hashlib.sha256(body.encode("utf-8")).hexdigest() == receipt["visible_text_sha256"]
            )

    def test_the_committed_source_is_what_the_generic_fold_produces(
        self,
        seq26_source: dict[str, Any],
        seq26_signed: dict[str, Any],
        seq27: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        refolded = fold(
            seq26_source,
            seq26_signed,
            load_ledger(_LEDGER),
            trust_store=StaticTrustStore.from_env(),
            version=FOLD_VERSION,
            created_at=FOLD_CREATED_AT,
            created_by=FOLD_CREATED_BY,
            verified_by=FOLD_VERIFIED_BY,
            observed_at=OBSERVED_AT,
            baseline_root=_RESEARCH,
            ledger_dir=_LEDGER,
        )
        assert canonicalize_json(refolded) == canonicalize_json(seq27)

    def test_guilt_a_ledger_missing_a_receipt_is_refused(
        self,
        seq26_source: dict[str, Any],
        seq26_signed: dict[str, Any],
        tmp_path: Path,
        prod_trust_store_env: None,
    ) -> None:
        copy_dir = tmp_path / "ledger"
        shutil.copytree(_LEDGER, copy_dir)
        receipts_path = next(copy_dir.glob("*-receipts.jsonl"))
        lines = receipts_path.read_text(encoding="utf-8").splitlines()
        receipts_path.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
        with pytest.raises(SystemExit):
            fold(
                seq26_source,
                seq26_signed,
                load_ledger(copy_dir),
                trust_store=StaticTrustStore.from_env(),
                version=FOLD_VERSION,
                created_at=FOLD_CREATED_AT,
                created_by=FOLD_CREATED_BY,
                verified_by=FOLD_VERIFIED_BY,
                observed_at=OBSERVED_AT,
                baseline_root=_RESEARCH,
                ledger_dir=copy_dir,
            )


class TestSignedBundleTiesToSource:
    """Wait for ``rulepack-prod-027.signed.json`` (added by the signing commit); fail, never skip, without it."""

    def test_signed_payload_is_byte_identical_to_source_under_jcs(
        self, seq27_signed: dict[str, Any], seq27: dict[str, Any]
    ) -> None:
        assert canonicalize_json(seq27_signed["payload"]) == canonicalize_json(seq27)
        assert seq27_signed["payload_sha256"] == SEQ27_PAYLOAD_SHA256

    def test_the_committed_bundle_verifies_against_the_pinned_production_key(
        self, seq27_signed: dict[str, Any], prod_trust_store_env: None
    ) -> None:
        verified = verify_rule_pack(
            seq27_signed, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT
        )
        assert verified.unsigned_dev is False
        assert verified.pack.protected.kid == "prod-2026-07-1"
        assert verified.pack.protected.environment == "PRODUCTION"
        assert verified.pack.payload.sequence == 27
        assert verified.payload_sha256.hex() == SEQ27_PAYLOAD_SHA256
        assert len(verified.pack.payload.rules) == 113

    def test_the_chain_anchor_is_the_signed_seq26_payload_digest(
        self, seq27_signed: dict[str, Any], seq26_signed: dict[str, Any]
    ) -> None:
        assert (
            seq27_signed["payload"]["previous_payload_sha256"]
            == seq26_signed["payload_sha256"]
            == SEQ26_PAYLOAD_SHA256
        )

    def test_guilt_one_flipped_byte_breaks_the_signature(
        self, seq27_signed: dict[str, Any], prod_trust_store_env: None
    ) -> None:
        tampered = copy.deepcopy(seq27_signed)
        _portals(tampered["payload"])[0]["verified_at"] = "2026-10-08T13:21:23Z"
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                tampered, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT
            )
