"""seq-25 — the 18 OFFICIAL_PORTAL sources re-stamped from a read ledger.

What this file proves, each with a guilt twin where one exists:

* the fold is anchored on the SIGNED seq-24 (digest + signature), chains to it,
  and mints seq-25's identity by the uuid5 convention;
* the stamp is DERIVED from the ledger on disk — the earliest successful read —
  and the fold refuses every way the ledger can be short (a page not read, a
  non-200, an unsure reader, an unaccepted "changed", a quote that is not in
  the saved text);
* nothing but stamps and identity moves (inverted-polarity guard);
* the committed source is what the fold produces, and the committed signed
  bundle is that source under the PUBLIC production key.

A missing artifact FAILS (``_read_json``), it never skips (cicatrix #2).
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import fold_pack_seq25
from backend.scripts.visa_engine.fold_pack_seq25 import (
    EXPECTED_PORTAL_COUNT,
    EXPECTED_SEQ24_STAMP,
    FOLD_CREATED_AT,
    FOLD_VERSION,
    RESTAMP_VERIFIED_BY,
    SEQ24_PAYLOAD_SHA256,
    Ledger,
    assert_only_expected_changes,
    attestation_instant,
    fold,
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
_PACKS_DIR = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_SEQ24_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-024.source.json"
_SEQ24_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-024.signed.json"
_SEQ25_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-025.source.json"
_SEQ25_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-025.signed.json"
_LEDGER_DIR = _REPO_ROOT / "research/visa/2026-10-07-freshness-restamp-seq25"

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
#: After the fold's declared created_at (13:38Z) and the signing (13:39Z).
OBSERVED_AT = datetime(2026, 10, 7, 13, 45, 0, tzinfo=timezone.utc)
SEQ25_PAYLOAD_SHA256 = "603f777e5fdd8ffbd5824282593b6584893f39b0b6b192f59c4563ae6d9c9d11"
EXPECTED_STAMP = "2026-10-07T13:32:18Z"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(f"{path.name} does not exist on disk — a witness that never ran proves nothing")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq24_source() -> dict[str, Any]:
    return _read_json(_SEQ24_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq24_signed() -> dict[str, Any]:
    return _read_json(_SEQ24_SIGNED_PATH)


@pytest.fixture(scope="module")
def seq25_source_on_disk() -> dict[str, Any]:
    return _read_json(_SEQ25_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq25_signed() -> dict[str, Any]:
    return _read_json(_SEQ25_SIGNED_PATH)


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


@pytest.fixture(scope="module")
def ledger() -> Ledger:
    return load_ledger(_LEDGER_DIR)


@pytest.fixture
def seq25_source(
    seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger: Ledger, prod_trust_store_env: None
) -> dict[str, Any]:
    return fold(seq24_source, seq24_signed, ledger, observed_at=OBSERVED_AT)


@pytest.fixture
def ledger_copy(tmp_path: Path) -> Path:
    """A private, mutable copy of the real ledger for guilt tests."""
    target = tmp_path / "ledger"
    shutil.copytree(_LEDGER_DIR, target)
    return target


def _portals(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in payload["source_records"] if r["authority_type"] == "OFFICIAL_PORTAL"]


def _rewrite_jsonl(path: Path, mutate) -> None:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [mutate(row) for row in rows]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows if r is not None), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fold integrity — the anchor, the chain, the identity.
# ---------------------------------------------------------------------------


class TestFoldIntegrity:
    def test_fold_refuses_without_a_verifiable_anchor(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger: Ledger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", raising=False)
        with pytest.raises(SystemExit, match="cannot verify the seq-24 anchor"):
            fold(seq24_source, seq24_signed, ledger, observed_at=OBSERVED_AT)

    def test_fold_refuses_a_source_that_is_not_the_signed_digest(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger: Ledger, prod_trust_store_env: None
    ) -> None:
        tampered = copy.deepcopy(seq24_source)
        tampered["version"] = "2026.9.28"
        with pytest.raises(SystemExit, match="not the signed artifact"):
            fold(tampered, seq24_signed, ledger, observed_at=OBSERVED_AT)

    def test_fold_refuses_a_signature_that_does_not_verify(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger: Ledger, prod_trust_store_env: None
    ) -> None:
        broken = copy.deepcopy(seq24_signed)
        broken["signature"] = "A" + broken["signature"][1:] if not broken["signature"].startswith("A") else "B" + broken["signature"][1:]
        with pytest.raises(SystemExit, match="does not verify"):
            fold(seq24_source, broken, ledger, observed_at=OBSERVED_AT)

    def test_fold_chains_to_seq24_and_is_not_a_rollback(self, seq25_source: dict[str, Any]) -> None:
        assert seq25_source["previous_payload_sha256"] == SEQ24_PAYLOAD_SHA256
        assert seq25_source["rollback_of_payload_sha256"] is None

    def test_fold_identity_fields(self, seq25_source: dict[str, Any]) -> None:
        assert seq25_source["sequence"] == 25
        assert seq25_source["rule_pack_id"] == str(fold_pack_seq25._rule_pack_id(25))
        assert seq25_source["version"] == FOLD_VERSION == "2026.10.7"
        assert seq25_source["created_at"] == FOLD_CREATED_AT
        assert seq25_source["created_by"].endswith("fold-2026-10-07")

    def test_rules_and_products_are_byte_identical_to_seq24(
        self, seq25_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        assert canonicalize_json({"r": seq25_source["rules"]}) == canonicalize_json({"r": seq24_source["rules"]})
        assert canonicalize_json({"p": seq25_source["products"]}) == canonicalize_json({"p": seq24_source["products"]})

    def test_fold_is_deterministic(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger: Ledger, prod_trust_store_env: None
    ) -> None:
        a = fold(seq24_source, seq24_signed, ledger, observed_at=OBSERVED_AT)
        b = fold(seq24_source, seq24_signed, ledger, observed_at=OBSERVED_AT)
        assert canonicalize_json(a) == canonicalize_json(b)

    def test_the_emitted_source_on_disk_is_what_this_fold_produces(
        self, seq25_source: dict[str, Any], seq25_source_on_disk: dict[str, Any]
    ) -> None:
        assert canonicalize_json(seq25_source) == canonicalize_json(seq25_source_on_disk)

    def test_the_emitted_source_digest_is_pinned(self, seq25_source_on_disk: dict[str, Any]) -> None:
        assert hashlib.sha256(canonicalize_json(seq25_source_on_disk)).hexdigest() == SEQ25_PAYLOAD_SHA256

    def test_the_payload_validates_against_the_model(self, seq25_source: dict[str, Any]) -> None:
        assert RulePackPayload.model_validate(seq25_source).sequence == 25


# ---------------------------------------------------------------------------
# The stamp comes from the ledger, and only from a ledger that is whole.
# ---------------------------------------------------------------------------


class TestLedgerGate:
    def test_innocence_the_real_ledger_stamps_every_portal_record_at_the_earliest_read(
        self, seq25_source: dict[str, Any]
    ) -> None:
        portals = _portals(seq25_source)
        assert len(portals) == EXPECTED_PORTAL_COUNT
        assert {r["verified_at"] for r in portals} == {EXPECTED_STAMP}
        assert {r["verified_by"] for r in portals} == {RESTAMP_VERIFIED_BY}

    def test_the_stamp_is_the_earliest_successful_fetched_at_in_the_ledger(self, ledger: Ledger) -> None:
        successes = [r["fetched_at"] for r in ledger.receipts if r.get("http_status") == 200 and r.get("key_phrase_found")]
        assert min(successes) == EXPECTED_STAMP
        assert EXPECTED_STAMP > EXPECTED_SEQ24_STAMP

    def test_the_real_ledger_reads_every_portal_record_with_a_quote_from_the_saved_text(
        self, ledger: Ledger, seq24_source: dict[str, Any]
    ) -> None:
        portal_ids = {r["source_record_id"] for r in _portals(seq24_source)}
        judged = {j["source_record_id"] for j in ledger.judgements}
        assert judged == portal_ids
        for judgement in ledger.judgements:
            assert fold_pack_seq25._quote_is_in_saved_text(ledger, judgement), judgement["source_record_id"]

    def test_every_accepted_changed_is_a_judged_changed_and_vice_versa(self, ledger: Ledger) -> None:
        changed = {j["source_record_id"] for j in ledger.judgements if j["semantic_change"] == "changed"}
        assert set(ledger.accepted_changed) == changed
        assert all(reason.strip() for reason in ledger.accepted_changed.values())

    def test_guilt_a_page_never_fetched_is_refused_by_name(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        victim = _portals(seq24_source)[0]["source_record_id"]
        for path in ledger_copy.glob("*-receipts.jsonl"):
            _rewrite_jsonl(path, lambda row: None if row["source_record_id"] == victim else row)
        with pytest.raises(SystemExit, match=f"{victim[:8]}.*no receipt with HTTP 200"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_a_non_200_is_not_a_read(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        victim = _portals(seq24_source)[3]["source_record_id"]

        def degrade(row: dict[str, Any]) -> dict[str, Any]:
            if row["source_record_id"] == victim:
                row["http_status"] = 503
            return row

        for path in ledger_copy.glob("*-receipts.jsonl"):
            _rewrite_jsonl(path, degrade)
        with pytest.raises(SystemExit, match="no receipt with HTTP 200"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_a_page_whose_key_phrase_was_not_found_is_not_a_read(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        victim = _portals(seq24_source)[5]["source_record_id"]

        def lose_phrase(row: dict[str, Any]) -> dict[str, Any]:
            if row["source_record_id"] == victim:
                row["key_phrase_found"] = False
            return row

        for path in ledger_copy.glob("*-receipts.jsonl"):
            _rewrite_jsonl(path, lose_phrase)
        with pytest.raises(SystemExit, match="no receipt with HTTP 200 and the key phrase found"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_an_unsure_reader_blocks_the_stamp(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        victim = _portals(seq24_source)[7]["source_record_id"]

        def doubt(row: dict[str, Any]) -> dict[str, Any]:
            if row["source_record_id"] == victim:
                row["semantic_change"] = "unsure"
            return row

        for path in ledger_copy.glob("*-judgements.jsonl"):
            _rewrite_jsonl(path, doubt)
        with pytest.raises(SystemExit, match="a reader is unsure"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_a_changed_verdict_without_a_disposition_blocks_the_stamp(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        (ledger_copy / "disposition.json").unlink()
        with pytest.raises(SystemExit, match="disposition.json does not accept it"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_a_disposition_without_a_reason_is_refused(self, ledger_copy: Path) -> None:
        disposition = json.loads((ledger_copy / "disposition.json").read_text(encoding="utf-8"))
        first = next(iter(disposition["accepted_changed"]))
        disposition["accepted_changed"][first] = "  "
        (ledger_copy / "disposition.json").write_text(json.dumps(disposition), encoding="utf-8")
        with pytest.raises(SystemExit, match="non-empty reason"):
            load_ledger(ledger_copy)

    def test_guilt_a_quote_that_is_not_in_the_saved_text_is_refused(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        victim = _portals(seq24_source)[9]["source_record_id"]

        def invent(row: dict[str, Any]) -> dict[str, Any]:
            if row["source_record_id"] == victim:
                row["checked_sentence"] = "Anda dapat tinggal selamanya tanpa visa."
            return row

        for path in ledger_copy.glob("*-judgements.jsonl"):
            _rewrite_jsonl(path, invent)
        with pytest.raises(SystemExit, match="not a substring of the saved visible text"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_a_read_older_than_the_seq24_stamp_cannot_restamp(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        def backdate(row: dict[str, Any]) -> dict[str, Any]:
            row["fetched_at"] = "2026-08-01T00:00:00Z"
            return row

        for path in ledger_copy.glob("*-receipts.jsonl"):
            _rewrite_jsonl(path, backdate)
        with pytest.raises(SystemExit, match="is not after the seq-24 stamp"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_a_read_in_the_future_cannot_be_attested(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        def postdate(row: dict[str, Any]) -> dict[str, Any]:
            row["fetched_at"] = "2026-10-07T14:30:00Z"
            return row

        for path in ledger_copy.glob("*-receipts.jsonl"):
            _rewrite_jsonl(path, postdate)
        with pytest.raises(SystemExit, match="is in the future"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_a_future_receipt_that_is_not_the_minimum_is_still_refused(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        """Codex finding 1 (2026-10-07): only the minimum used to be checked, so one
        page's receipts moved to 2099 rode through while the others set the stamp."""
        victim = _portals(seq24_source)[17]["source_record_id"]

        def postdate_one(row: dict[str, Any]) -> dict[str, Any]:
            if row["source_record_id"] == victim:
                row["fetched_at"] = "2099-01-01T00:00:00Z"
            return row

        for path in ledger_copy.glob("*-receipts.jsonl"):
            _rewrite_jsonl(path, postdate_one)
        with pytest.raises(SystemExit, match=f"{victim[:8]}.*is in the future"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_a_receipt_for_another_url_is_not_a_read_of_this_page(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        victim = _portals(seq24_source)[2]["source_record_id"]

        def swap_url(row: dict[str, Any]) -> dict[str, Any]:
            if row["source_record_id"] == victim:
                row["canonical_url"] = "https://www.imigrasi.go.id/wna/daftar-visa-indonesia/C1"
            return row

        for path in ledger_copy.glob("*-receipts.jsonl"):
            _rewrite_jsonl(path, swap_url)
        with pytest.raises(SystemExit, match="not the record's canonical_url"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_a_judgement_written_before_the_read_is_refused(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        victim = _portals(seq24_source)[4]["source_record_id"]

        def predate(row: dict[str, Any]) -> dict[str, Any]:
            if row["source_record_id"] == victim:
                row["judged_at"] = "2026-10-07T13:00:00Z"
            return row

        for path in ledger_copy.glob("*-judgements.jsonl"):
            _rewrite_jsonl(path, predate)
        with pytest.raises(SystemExit, match="a judgement must follow the read it judges"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_innocence_every_saved_text_carries_a_receipts_fingerprint(
        self, ledger: Ledger, seq24_source: dict[str, Any]
    ) -> None:
        for record in _portals(seq24_source):
            record_id = record["source_record_id"]
            assert fold_pack_seq25._saved_text_matches_a_receipt(
                ledger, record_id, fold_pack_seq25._successful_receipts(ledger, record_id)
            ), record_id

    def test_guilt_a_saved_text_edited_after_the_fetch_is_refused(
        self, seq24_source: dict[str, Any], seq24_signed: dict[str, Any], ledger_copy: Path, prod_trust_store_env: None
    ) -> None:
        """A quote can be planted in the text file; the receipt's fingerprint, written
        at request time, is what ties the file to a real fetch."""
        victim = _portals(seq24_source)[11]["source_record_id"]
        text_path = ledger_copy / "text" / f"{victim[:8]}.txt"
        text_path.write_text(text_path.read_text(encoding="utf-8") + "Anda dapat tinggal selamanya.\n", encoding="utf-8")
        with pytest.raises(SystemExit, match="does not carry the fingerprint of any successful receipt"):
            fold(seq24_source, seq24_signed, load_ledger(ledger_copy), observed_at=OBSERVED_AT)

    def test_guilt_an_empty_ledger_dir_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="nothing was fetched"):
            load_ledger(tmp_path)

    def test_attestation_instant_takes_the_earliest_over_all_readers(self, ledger: Ledger, seq24_source: dict[str, Any]) -> None:
        assert attestation_instant(ledger, _portals(seq24_source)) == EXPECTED_STAMP


# ---------------------------------------------------------------------------
# Nothing else moves.
# ---------------------------------------------------------------------------


class TestGuard:
    def test_innocence_the_real_pair_passes(self, seq24_source: dict[str, Any], seq25_source: dict[str, Any]) -> None:
        assert_only_expected_changes(seq24_source, seq25_source)

    def test_guilt_content_sha256_change_on_a_portal_record_is_rejected(
        self, seq24_source: dict[str, Any], seq25_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq25_source)
        _portals(tampered)[0]["content_sha256"] = "0" * 64
        with pytest.raises(SystemExit, match="content_sha256"):
            assert_only_expected_changes(seq24_source, tampered)

    def test_guilt_verified_at_change_on_a_non_portal_record_is_rejected(
        self, seq24_source: dict[str, Any], seq25_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq25_source)
        other = next(r for r in tampered["source_records"] if r["authority_type"] != "OFFICIAL_PORTAL")
        other["verified_at"] = EXPECTED_STAMP
        with pytest.raises(SystemExit, match="only on portal records"):
            assert_only_expected_changes(seq24_source, tampered)

    def test_guilt_a_rule_edit_is_rejected(self, seq24_source: dict[str, Any], seq25_source: dict[str, Any]) -> None:
        tampered = copy.deepcopy(seq25_source)
        tampered["rules"] = tampered["rules"][1:]
        with pytest.raises(SystemExit, match="rules changed"):
            assert_only_expected_changes(seq24_source, tampered)

    def test_guilt_a_new_top_level_key_is_rejected(self, seq24_source: dict[str, Any], seq25_source: dict[str, Any]) -> None:
        tampered = copy.deepcopy(seq25_source)
        tampered["notes"] = "x"
        with pytest.raises(SystemExit, match="top-level key set changed"):
            assert_only_expected_changes(seq24_source, tampered)

    def test_guilt_a_dropped_source_record_is_rejected(self, seq24_source: dict[str, Any], seq25_source: dict[str, Any]) -> None:
        tampered = copy.deepcopy(seq25_source)
        tampered["source_records"] = tampered["source_records"][:-1]
        with pytest.raises(SystemExit, match="changed length"):
            assert_only_expected_changes(seq24_source, tampered)


# ---------------------------------------------------------------------------
# The signed artifact IS the tracked source.
# ---------------------------------------------------------------------------


class TestSignedBundleTiesToSource:
    def test_signed_payload_is_byte_identical_to_source_under_jcs(
        self, seq25_signed: dict[str, Any], seq25_source_on_disk: dict[str, Any]
    ) -> None:
        assert canonicalize_json(seq25_signed["payload"]) == canonicalize_json(seq25_source_on_disk)
        assert seq25_signed["payload_sha256"] == SEQ25_PAYLOAD_SHA256

    def test_the_committed_bundle_verifies_against_the_pinned_production_key(
        self, seq25_signed: dict[str, Any], prod_trust_store_env: None
    ) -> None:
        verified = verify_rule_pack(seq25_signed, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT)
        assert verified.unsigned_dev is False
        assert verified.pack.protected.kid == "prod-2026-07-1"
        assert verified.pack.protected.environment == "PRODUCTION"
        assert verified.pack.payload.sequence == 25
        assert verified.payload_sha256.hex() == SEQ25_PAYLOAD_SHA256
        assert len(verified.pack.payload.rules) == 113

    def test_the_chain_anchor_is_the_signed_seq24_payload_digest(
        self, seq25_signed: dict[str, Any], seq24_signed: dict[str, Any]
    ) -> None:
        assert seq25_signed["payload"]["previous_payload_sha256"] == seq24_signed["payload_sha256"] == SEQ24_PAYLOAD_SHA256

    def test_the_signed_stamps_are_inside_the_window_at_signing_and_until_november(
        self, seq25_signed: dict[str, Any]
    ) -> None:
        portals = _portals(seq25_signed["payload"])
        assert {r["verified_at"] for r in portals} == {EXPECTED_STAMP}
        assert {r["freshness_policy"]["max_age_seconds"] for r in portals} == {2764800}

    def test_guilt_one_flipped_byte_breaks_the_signature(
        self, seq25_signed: dict[str, Any], prod_trust_store_env: None
    ) -> None:
        tampered = copy.deepcopy(seq25_signed)
        _portals(tampered["payload"])[0]["verified_at"] = "2026-10-07T13:32:19Z"
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(tampered, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT)
