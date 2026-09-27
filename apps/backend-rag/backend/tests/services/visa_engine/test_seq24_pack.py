"""Gates for seq-24 (``fold_pack_seq24.py``): a retiree without a confirmed
sponsor becomes an E33F candidate. Zero's ruling of 2026-09-27 — one semantic
change for one product: ``hf.e33f.sponsor-required`` (the only emitter of
``SPONSOR_REQUIRED``) is retired and ``el.e33f.retirement`` stops reading
``family.sponsor_confirmed``. No new rule, no new reason code (Option A: the
note that a sponsor may still be needed lives in the mouth). The fold itself
never signs or activates anything; ``rulepack-prod-024.signed.json`` (signed
2026-09-27T01:31:02Z, kid ``prod-2026-07-1``, NOT activated) is tied to this
source and verified against the public production key by
``TestSignedBundleTiesToSource`` at the bottom of this file, exactly as
``test_seq23_pack.py``'s own tie is.

Ground: ``fold_pack_seq24.py``'s own docstring. The anchor is the REAL,
production ``rulepack-prod-023.signed.json`` on disk, verified against the
pinned production public key — exactly as ``fold_pack_seq23.py``'s own gates
verify seq-22. If either on-disk artifact is missing these tests FAIL; they
never skip (cicatrix #2 — a green suite that ran no witness proves nothing).

Every behavioural witness is stated TWICE — guilt (the defect is present and
refused) and innocence (the legitimate shape the same guard still allows). The
engine witnesses run the retiree through the evaluator on BOTH packs: seq-24
must accept what seq-23 refused, and seq-23 must still refuse it — a witness
that both packs pass would prove nothing.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import fold_pack_seq24
from backend.scripts.visa_engine.compile_pack import wrap_as_unsigned_pack
from backend.scripts.visa_engine.fold_pack_seq24 import (
    E33F_AGE_RULE_ID,
    E33F_INCOME_RULE_ID,
    E33F_PRODUCT_VERSION_ID,
    E33F_RETIREMENT_RULE_ID,
    FOLD_CREATED_AT,
    INSERTED_RULE_IDS,
    MODIFIED_RULE_IDS,
    REMOVED_RULE_IDS,
    SEQ23_PAYLOAD_SHA256,
    SPONSOR_FACT,
    SPONSOR_READERS_AFTER_FOLD,
    SPONSOR_REQUIRED_REASON_CODE,
    SPONSOR_REQUIRED_RULE_ID,
    STUDIO_RULE_ID,
    SYNTHESISED_TWIN_BASIS_FACTS,
    _assert_candidate_review_inventory,
    _assert_no_rule_emits_sponsor_required,
    _assert_retired_rule_is_the_expected_shape,
    _assert_sponsor_readers,
    _rule_pack_id,
    _rules_by_id,
    _rules_emitting_reason_code,
    _rules_reading_fact,
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact,
    assert_only_expected_changes,
    build_modified_e33f_retirement,
    fold,
)
from backend.scripts.visa_engine.gold_replay_driver import (
    _offline_identity_provider,
    build_persona_request,
)
from backend.scripts.visa_engine.review_hold_inventory import (
    pack_review_rules,
    pack_unknown_escalations,
)
from backend.services.visa_engine import compiler, evaluate_path, evaluator
from backend.services.visa_engine.api_models import VisaOracleEvaluateRequest
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.evaluator import ProductProofStatus
from backend.services.visa_engine.models import DecisionState, FactPath, RulePackPayload
from backend.tests.services.visa_engine.gold_replay import _decision_actual
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ23_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-023.source.json"
_SEQ23_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-023.signed.json"
_SEQ24_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-024.source.json"
_SEQ24_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-024.signed.json"

#: The pinned production Ed25519 PUBLIC key — the same constant
#: `test_seq23_pack.py` verifies seq-22 with. A public key is not a secret.
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

#: Shortly after seq-23's own `signed_at` (2026-09-24T09:32:53Z) — fixed, never
#: `datetime.now()`, so this file never rots into a time-dependent red.
OBSERVED_AT = datetime(2026, 9, 24, 9, 45, 0, tzinfo=timezone.utc)
SEQ23_SIGNED_AT = datetime(2026, 9, 24, 9, 32, 53, tzinfo=timezone.utc)

#: The engine witnesses' evaluation instant — after every rule's
#: `valid_period.from` (the newest is seq-23's 2026-09-23), fixed, never
#: `datetime.now()`.
EVALUATED_AT = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)

#: seq-24's own payload digest (H24), independently recomputed off the emitted
#: source and pinned here so the candidate the owner signs is the candidate
#: this suite graded — a moved byte moves this literal in the same PR.
SEQ24_PAYLOAD_SHA256 = "5a569091f84a858f1957cdf96086ee7212f67d13a8225d64492a7212093cd272"

#: seq-24's own `signed_at` (read off the signed envelope's protected header)
#: and an observation instant shortly after it — fixed, never `datetime.now()`,
#: because `verify_rule_pack` rejects a signature dated after `observed_at`.
SEQ24_SIGNED_AT = datetime(2026, 9, 27, 1, 31, 2, 441320, tzinfo=timezone.utc)
SEQ24_OBSERVED_AT = datetime(2026, 9, 27, 1, 45, 0, tzinfo=timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk. This must FAIL, not skip: a "
            "witness that never ran proves nothing (cicatrix #2)."
        )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq23_source() -> dict[str, Any]:
    return _read_json(_SEQ23_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq23_signed() -> dict[str, Any]:
    return _read_json(_SEQ23_SIGNED_PATH)


@pytest.fixture(scope="module")
def seq24_signed() -> dict[str, Any]:
    return _read_json(_SEQ24_SIGNED_PATH)


@pytest.fixture(scope="module")
def seq24_source_on_disk() -> dict[str, Any]:
    return _read_json(_SEQ24_SOURCE_PATH)


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


@pytest.fixture
def seq24_source(
    seq23_source: dict[str, Any],
    seq23_signed: dict[str, Any],
    prod_trust_store_env: None,
) -> dict[str, Any]:
    return fold(seq23_source, seq23_signed, observed_at=OBSERVED_AT)


def _compiled(payload_dict: dict[str, Any]) -> compiler.CompiledRulePack:
    payload = RulePackPayload.model_validate(payload_dict)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture
def seq24_compiled(seq24_source: dict[str, Any]) -> compiler.CompiledRulePack:
    return _compiled(seq24_source)


@pytest.fixture
def seq23_compiled(seq23_source: dict[str, Any]) -> compiler.CompiledRulePack:
    return _compiled(seq23_source)


# ---------------------------------------------------------------------------
# Fold integrity — the anchor, the chain, the shape of the edit.
# ---------------------------------------------------------------------------


class TestFoldIntegrity:
    def test_fold_refuses_without_a_verifiable_anchor(
        self,
        seq23_source: dict[str, Any],
        seq23_signed: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", raising=False)
        with pytest.raises(SystemExit) as excinfo:
            fold(seq23_source, seq23_signed, observed_at=OBSERVED_AT)
        assert "verify" in str(excinfo.value)

    def test_fold_refuses_a_source_that_is_not_the_signed_digest(
        self,
        seq23_source: dict[str, Any],
        seq23_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        """GUILT: flip one anchor byte -> the fold aborts naming the digest."""
        tampered = {**seq23_source, "version": "9999.9.9-tampered"}
        with pytest.raises(SystemExit) as excinfo:
            fold(tampered, seq23_signed, observed_at=OBSERVED_AT)
        assert "not the activated artifact" in str(excinfo.value)

    def test_fold_refuses_a_signature_that_does_not_verify(
        self,
        seq23_source: dict[str, Any],
        seq23_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        """GUILT: the source digest is right but the envelope's signature is
        not the production key's — the anchor is never taken on the digest
        constant alone."""
        tampered = copy.deepcopy(seq23_signed)
        signature = tampered["signature"]
        tampered["signature"] = ("A" if signature[0] != "A" else "B") + signature[1:]
        with pytest.raises(SystemExit) as excinfo:
            fold(seq23_source, tampered, observed_at=OBSERVED_AT)
        assert "does not verify" in str(excinfo.value)

    def test_fold_chains_to_seq23(self, seq24_source: dict[str, Any]) -> None:
        assert seq24_source["previous_payload_sha256"] == SEQ23_PAYLOAD_SHA256
        assert (
            SEQ23_PAYLOAD_SHA256
            == "e5f791b5232fd1369ef3b94ca7bb5f349f9bb6eb4073895aa9f7deb682e72204"
        )

    def test_fold_identity_fields(self, seq24_source: dict[str, Any]) -> None:
        assert seq24_source["sequence"] == 24
        assert seq24_source["rule_pack_id"] == str(_rule_pack_id(24))
        assert seq24_source["rule_pack_id"] == "ecea2663-35ed-586d-aa52-9ed1849e0060"
        assert seq24_source["version"] == "2026.9.27"
        assert seq24_source["created_at"] == FOLD_CREATED_AT == "2026-09-26T21:00:00Z"
        assert seq24_source["rollback_of_payload_sha256"] is None

    def test_created_at_follows_the_anchors_own_signature(
        self, seq24_source: dict[str, Any]
    ) -> None:
        """The pack's own timestamp is after its anchor was signed — the
        chain never runs backwards, and it precedes any signing to come."""
        created_at = datetime.fromisoformat(seq24_source["created_at"].replace("Z", "+00:00"))
        assert created_at > SEQ23_SIGNED_AT

    def test_fold_retires_one_inserts_none_modifies_one(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        before = set(_rules_by_id(seq23_source))
        after = set(_rules_by_id(seq24_source))
        assert before - after == REMOVED_RULE_IDS == {"hf.e33f.sponsor-required"}
        assert after - before == INSERTED_RULE_IDS == set()
        assert MODIFIED_RULE_IDS == {"el.e33f.retirement"}
        assert len(seq24_source["rules"]) == len(seq23_source["rules"]) - 1 == 113

    def test_fold_edits_no_rule_outside_the_disposition_table(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        before = _rules_by_id(seq23_source)
        for rule_id, rule in _rules_by_id(seq24_source).items():
            if rule_id in MODIFIED_RULE_IDS:
                continue
            assert canonicalize_json(rule) == canonicalize_json(before[rule_id]), rule_id

    def test_fold_touches_no_other_top_level_key(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        for key in set(seq23_source) - {
            "sequence",
            "version",
            "rule_pack_id",
            "created_at",
            "created_by",
            "previous_payload_sha256",
            "rollback_of_payload_sha256",
            "rules",
        }:
            assert canonicalize_json(seq24_source[key]) == canonicalize_json(seq23_source[key]), key

    def test_surviving_rules_keep_their_order(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        expected = [
            r["rule_id"] for r in seq23_source["rules"] if r["rule_id"] != SPONSOR_REQUIRED_RULE_ID
        ]
        assert [r["rule_id"] for r in seq24_source["rules"]] == expected

    def test_fold_is_deterministic(
        self,
        seq23_source: dict[str, Any],
        seq23_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        first = fold(seq23_source, seq23_signed, observed_at=OBSERVED_AT)
        second = fold(seq23_source, seq23_signed, observed_at=OBSERVED_AT)
        assert first == second

    def test_the_emitted_source_on_disk_is_what_this_fold_produces(
        self, seq24_source: dict[str, Any]
    ) -> None:
        on_disk = _read_json(_SEQ24_SOURCE_PATH)
        assert canonicalize_json(on_disk) == canonicalize_json(seq24_source)

    def test_the_emitted_source_digest_is_pinned(self, seq24_source: dict[str, Any]) -> None:
        assert hashlib.sha256(canonicalize_json(seq24_source)).hexdigest() == SEQ24_PAYLOAD_SHA256

    def test_flipping_one_byte_of_the_canonical_source_moves_the_digest_away_from_h24(
        self, seq24_source: dict[str, Any]
    ) -> None:
        """GUILT: proves H24 actually discriminates — a scratch bytearray
        copy of the canonical bytes, ONE byte flipped, must not hash to H24.
        Never mutates the fixture or any file on disk."""
        canonical = bytearray(canonicalize_json(seq24_source))
        canonical[-1] ^= 0x01
        assert hashlib.sha256(bytes(canonical)).hexdigest() != SEQ24_PAYLOAD_SHA256

    def test_output_refuses_a_signed_path(
        self, seq23_source: dict[str, Any], seq23_signed: dict[str, Any], tmp_path: Path
    ) -> None:
        """The fold's own CLI refuses to write a `.signed.json` output —
        exercised through the module's `main`, the idiom
        `test_seq23_pack.py` uses."""
        seq23_path = tmp_path / "rulepack-prod-023.source.json"
        seq23_path.write_text(json.dumps(seq23_source), encoding="utf-8")
        signed_path = tmp_path / "rulepack-prod-023.signed.json"
        signed_path.write_text(json.dumps(seq23_signed), encoding="utf-8")
        output = tmp_path / "rulepack-prod-024.signed.json"
        with pytest.raises(SystemExit) as excinfo:
            fold_pack_seq24.main(
                ["--seq23-source", str(seq23_path), "--output", str(output)],
                observed_at=OBSERVED_AT,
            )
        assert "signed.json" in str(excinfo.value)
        assert not output.exists()

    def test_output_refuses_to_collide_with_an_input(
        self, seq23_source: dict[str, Any], seq23_signed: dict[str, Any], tmp_path: Path
    ) -> None:
        seq23_path = tmp_path / "rulepack-prod-023.source.json"
        seq23_path.write_text(json.dumps(seq23_source), encoding="utf-8")
        signed_path = tmp_path / "rulepack-prod-023.signed.json"
        signed_path.write_text(json.dumps(seq23_signed), encoding="utf-8")
        with pytest.raises(SystemExit) as excinfo:
            fold_pack_seq24.main(
                ["--seq23-source", str(seq23_path), "--output", str(seq23_path)],
                observed_at=OBSERVED_AT,
            )
        assert "same file" in str(excinfo.value)

    def test_the_cli_writes_the_same_bytes_the_fold_returns(
        self,
        seq23_source: dict[str, Any],
        seq23_signed: dict[str, Any],
        seq24_source: dict[str, Any],
        tmp_path: Path,
        prod_trust_store_env: None,
    ) -> None:
        seq23_path = tmp_path / "rulepack-prod-023.source.json"
        seq23_path.write_text(json.dumps(seq23_source), encoding="utf-8")
        (tmp_path / "rulepack-prod-023.signed.json").write_text(
            json.dumps(seq23_signed), encoding="utf-8"
        )
        output = tmp_path / "rulepack-prod-024.source.json"
        assert (
            fold_pack_seq24.main(
                ["--seq23-source", str(seq23_path), "--output", str(output)],
                observed_at=OBSERVED_AT,
            )
            == 0
        )
        assert canonicalize_json(
            json.loads(output.read_text(encoding="utf-8"))
        ) == canonicalize_json(seq24_source)


# ---------------------------------------------------------------------------
# The two edits, by id. INNOCENCE the built pack is the shape the ruling
# names; GUILT undoing (or widening) the edit in a scratch copy fails
# `assert_only_expected_changes` naming the rule id.
# ---------------------------------------------------------------------------


class TestDispositionTableRows:
    def test_the_retired_rule_was_the_e33f_sponsor_gate_and_the_only_emitter_of_its_code(
        self, seq23_source: dict[str, Any]
    ) -> None:
        rule = _rules_by_id(seq23_source)[SPONSOR_REQUIRED_RULE_ID]
        assert rule["stage"] == "HARD_FILTER"
        assert rule["effect"] == {"type": "EXCLUDE", "reason_code": SPONSOR_REQUIRED_REASON_CODE}
        assert rule["when"] == {"op": "eq", "fact": SPONSOR_FACT, "value": False}
        assert rule["product_version_ids"] == [E33F_PRODUCT_VERSION_ID]
        assert _rules_emitting_reason_code(seq23_source, SPONSOR_REQUIRED_REASON_CODE) == {
            SPONSOR_REQUIRED_RULE_ID
        }

    def test_the_retired_rule_is_absent_from_seq24(self, seq24_source: dict[str, Any]) -> None:
        assert SPONSOR_REQUIRED_RULE_ID not in _rules_by_id(seq24_source)

    def test_no_rule_emits_sponsor_required_after_the_fold(
        self, seq24_source: dict[str, Any]
    ) -> None:
        assert _rules_emitting_reason_code(seq24_source, SPONSOR_REQUIRED_REASON_CODE) == set()
        _assert_no_rule_emits_sponsor_required(seq24_source)

    def test_no_reason_code_is_minted_and_only_one_disappears(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        """Option A: no new reason code. The set of codes the pack can emit
        loses SPONSOR_REQUIRED and gains nothing."""

        def codes(payload: dict[str, Any]) -> set[str]:
            return {
                r["effect"]["reason_code"]
                for r in payload["rules"]
                if r["effect"].get("reason_code")
            }

        assert codes(seq23_source) - codes(seq24_source) == {SPONSOR_REQUIRED_REASON_CODE}
        assert codes(seq24_source) - codes(seq23_source) == set()

    def test_e33f_retirement_drops_exactly_the_sponsor_conjunct(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        before = _rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID]
        after = _rules_by_id(seq24_source)[E33F_RETIREMENT_RULE_ID]
        assert before["when"]["op"] == "all" and len(before["when"]["args"]) == 3
        assert before["when"]["args"][2] == {"op": "eq", "fact": SPONSOR_FACT, "value": True}
        assert after["when"] == {"op": "all", "args": before["when"]["args"][:2]}
        assert after["required_facts"] == [
            "intent.purposes",
            "secondhome.passive_monthly_income_usd",
        ]
        assert SPONSOR_FACT in before["required_facts"]
        assert SPONSOR_FACT not in after["required_facts"]
        for key in set(before) - {"when", "required_facts"}:
            assert canonicalize_json(after[key]) == canonicalize_json(before[key]), key
        assert set(after) == set(before)

    def test_e33f_retirement_keeps_its_validity_window(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        """`valid_period.from` is unchanged, as seq-23's own in-place edits
        left theirs — the rule was in force before this fold and stays so."""
        before = _rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID]["valid_period"]
        after = _rules_by_id(seq24_source)[E33F_RETIREMENT_RULE_ID]["valid_period"]
        assert after == before == {"to": None, "from": "2026-07-24T00:00:00Z"}

    @pytest.mark.parametrize("rule_id", [E33F_AGE_RULE_ID, E33F_INCOME_RULE_ID])
    def test_the_other_e33f_filters_are_brought_forward_byte_identical(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any], rule_id: str
    ) -> None:
        """INNOCENCE: the age and income filters that decide E33F stay."""
        before = _rules_by_id(seq23_source)[rule_id]
        after = _rules_by_id(seq24_source)[rule_id]
        assert canonicalize_json(after) == canonicalize_json(before)

    @pytest.mark.parametrize("rule_id", sorted(SPONSOR_READERS_AFTER_FOLD))
    def test_the_four_other_sponsor_readers_stay_byte_identical(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any], rule_id: str
    ) -> None:
        before = _rules_by_id(seq23_source)[rule_id]
        after = _rules_by_id(seq24_source)[rule_id]
        assert canonicalize_json(after) == canonicalize_json(before)
        assert rule_id in _rules_reading_fact(seq24_source, SPONSOR_FACT)

    def test_exactly_four_rules_read_the_sponsor_fact_after_the_fold(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        assert _rules_reading_fact(seq23_source, SPONSOR_FACT) == SPONSOR_READERS_AFTER_FOLD | {
            SPONSOR_REQUIRED_RULE_ID,
            E33F_RETIREMENT_RULE_ID,
        }
        assert _rules_reading_fact(seq24_source, SPONSOR_FACT) == SPONSOR_READERS_AFTER_FOLD
        assert len(SPONSOR_READERS_AFTER_FOLD) == 4

    def test_innocence_the_real_pack_passes_assert_only_expected_changes(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        assert_only_expected_changes(seq23_source, seq24_source)

    def test_guilt_reinstating_the_retired_rule_fails_naming_it(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq24_source)
        tampered["rules"].append(
            copy.deepcopy(_rules_by_id(seq23_source)[SPONSOR_REQUIRED_RULE_ID])
        )
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq23_source, tampered)
        assert f"not retired [{SPONSOR_REQUIRED_RULE_ID!r}]" in str(excinfo.value)

    def test_guilt_keeping_the_sponsor_conjunct_on_e33f_retirement_fails_naming_it(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq24_source)
        original = _rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID]
        for index, rule in enumerate(tampered["rules"]):
            if rule["rule_id"] == E33F_RETIREMENT_RULE_ID:
                tampered["rules"][index] = copy.deepcopy(original)
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq23_source, tampered)
        assert E33F_RETIREMENT_RULE_ID in str(excinfo.value)

    def test_guilt_dropping_the_income_conjunct_instead_fails_naming_the_rule(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        """GUILT: a fold that dropped the WRONG conjunct (income, keeping
        sponsor) is not this fold — the edit is a named conjunct, not 'one'."""
        tampered = copy.deepcopy(seq24_source)
        original = _rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID]
        for rule in tampered["rules"]:
            if rule["rule_id"] == E33F_RETIREMENT_RULE_ID:
                rule["when"]["args"] = [original["when"]["args"][0], original["when"]["args"][2]]
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq23_source, tampered)
        assert E33F_RETIREMENT_RULE_ID in str(excinfo.value)

    def test_guilt_touching_the_validity_window_fails_naming_the_rule(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq24_source)
        for rule in tampered["rules"]:
            if rule["rule_id"] == E33F_RETIREMENT_RULE_ID:
                rule["valid_period"]["from"] = "2026-09-27T00:00:00Z"
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq23_source, tampered)
        assert E33F_RETIREMENT_RULE_ID in str(excinfo.value)

    def test_guilt_touching_any_other_rule_fails_naming_it(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq24_source)
        for rule in tampered["rules"]:
            if rule["rule_id"] == E33F_AGE_RULE_ID:
                rule["on_unknown"] = "NO_EFFECT"
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq23_source, tampered)
        assert E33F_AGE_RULE_ID in str(excinfo.value)

    def test_guilt_inserting_a_rule_fails(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        """Option A: this fold inserts nothing — a new sponsor-note rule (or
        any other) is a different PR."""
        tampered = copy.deepcopy(seq24_source)
        extra = copy.deepcopy(_rules_by_id(seq23_source)[E33F_AGE_RULE_ID])
        extra["rule_id"] = "hf.e33f.a-new-rule"
        tampered["rules"].append(extra)
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq23_source, tampered)
        assert "hf.e33f.a-new-rule" in str(excinfo.value)

    def test_guilt_reordering_the_surviving_rules_fails(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq24_source)
        tampered["rules"][0], tampered["rules"][1] = tampered["rules"][1], tampered["rules"][0]
        with pytest.raises(SystemExit) as excinfo:
            assert_only_expected_changes(seq23_source, tampered)
        assert "order" in str(excinfo.value)


class TestEditPreconditions:
    """The fold reads its donors and refuses a base that has drifted from the
    shape the ruling was written against — the edit set is never applied to
    a rule that is no longer the one named."""

    def test_innocence_the_real_donor_builds_the_seq24_rule(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        built = build_modified_e33f_retirement(_rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID])
        assert canonicalize_json(built) == canonicalize_json(
            _rules_by_id(seq24_source)[E33F_RETIREMENT_RULE_ID]
        )

    def test_guilt_a_donor_whose_sponsor_conjunct_moved_is_refused(
        self, seq23_source: dict[str, Any]
    ) -> None:
        donor = copy.deepcopy(_rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID])
        donor["when"]["args"][1], donor["when"]["args"][2] = (
            donor["when"]["args"][2],
            donor["when"]["args"][1],
        )
        with pytest.raises(SystemExit) as excinfo:
            build_modified_e33f_retirement(donor)
        assert "third conjunct" in str(excinfo.value)

    def test_guilt_a_donor_with_two_conjuncts_is_refused(
        self, seq23_source: dict[str, Any]
    ) -> None:
        donor = copy.deepcopy(_rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID])
        donor["when"]["args"] = donor["when"]["args"][:2]
        with pytest.raises(SystemExit) as excinfo:
            build_modified_e33f_retirement(donor)
        assert "expected 3" in str(excinfo.value)

    def test_guilt_a_donor_scoped_to_another_product_is_refused(
        self, seq23_source: dict[str, Any]
    ) -> None:
        donor = copy.deepcopy(_rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID])
        donor["product_version_ids"] = ["00000000-0000-0000-0000-000000000000"]
        with pytest.raises(SystemExit) as excinfo:
            build_modified_e33f_retirement(donor)
        assert "E33F-only" in str(excinfo.value)

    def test_guilt_a_donor_whose_required_facts_omit_the_sponsor_fact_is_refused(
        self, seq23_source: dict[str, Any]
    ) -> None:
        donor = copy.deepcopy(_rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID])
        donor["required_facts"] = [f for f in donor["required_facts"] if f != SPONSOR_FACT]
        with pytest.raises(SystemExit) as excinfo:
            build_modified_e33f_retirement(donor)
        assert "required_facts" in str(excinfo.value)

    def test_innocence_the_real_retired_rule_passes_its_precondition(
        self, seq23_source: dict[str, Any]
    ) -> None:
        _assert_retired_rule_is_the_expected_shape(seq23_source)

    def test_guilt_a_second_emitter_of_sponsor_required_is_refused_before_the_fold(
        self, seq23_source: dict[str, Any]
    ) -> None:
        """GUILT: had another rule emitted SPONSOR_REQUIRED, retiring this
        one would leave the code reachable — the ruling did not cover that,
        so the fold names both emitters and stops."""
        tampered = copy.deepcopy(seq23_source)
        second = copy.deepcopy(_rules_by_id(seq23_source)[SPONSOR_REQUIRED_RULE_ID])
        second["rule_id"] = "hf.another.sponsor-required"
        tampered["rules"].append(second)
        with pytest.raises(SystemExit) as excinfo:
            _assert_retired_rule_is_the_expected_shape(tampered)
        message = str(excinfo.value)
        assert SPONSOR_REQUIRED_RULE_ID in message and "hf.another.sponsor-required" in message

    def test_guilt_a_retired_rule_that_emits_another_code_is_refused(
        self, seq23_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq23_source)
        for rule in tampered["rules"]:
            if rule["rule_id"] == SPONSOR_REQUIRED_RULE_ID:
                rule["effect"]["reason_code"] = "SOMETHING_ELSE"
        with pytest.raises(SystemExit) as excinfo:
            _assert_retired_rule_is_the_expected_shape(tampered)
        assert "SOMETHING_ELSE" in str(excinfo.value)

    def test_innocence_the_sponsor_readers_before_and_after(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        _assert_sponsor_readers(seq23_source, after_fold=False)
        _assert_sponsor_readers(seq24_source, after_fold=True)

    def test_guilt_seq23_is_not_a_valid_after_fold_pack(self, seq23_source: dict[str, Any]) -> None:
        with pytest.raises(SystemExit) as excinfo:
            _assert_sponsor_readers(seq23_source, after_fold=True)
        assert SPONSOR_REQUIRED_RULE_ID in str(excinfo.value)
        assert E33F_RETIREMENT_RULE_ID in str(excinfo.value)

    def test_guilt_dropping_the_sponsor_question_from_another_product_is_refused(
        self, seq24_source: dict[str, Any]
    ) -> None:
        """GUILT: the ruling drops the sponsor question from E33F and nowhere
        else — a pack that also lost `el.c6.social` is not this pack."""
        tampered = copy.deepcopy(seq24_source)
        tampered["rules"] = [r for r in tampered["rules"] if r["rule_id"] != "el.c6.social"]
        with pytest.raises(SystemExit) as excinfo:
            _assert_sponsor_readers(tampered, after_fold=True)
        assert "el.c6.social" in str(excinfo.value)

    def test_guilt_a_second_emitter_after_the_fold_is_refused(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq24_source)
        tampered["rules"].append(
            copy.deepcopy(_rules_by_id(seq23_source)[SPONSOR_REQUIRED_RULE_ID])
        )
        with pytest.raises(SystemExit) as excinfo:
            _assert_no_rule_emits_sponsor_required(tampered)
        assert SPONSOR_REQUIRED_RULE_ID in str(excinfo.value)


# ---------------------------------------------------------------------------
# ENGINE witnesses — the retiree, run through the evaluator on both packs.
# ---------------------------------------------------------------------------


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


_UNKNOWN: dict[str, Any] = {"status": "UNKNOWN", "reason": "NOT_ASKED"}

_INCOME_FACT = "secondhome.passive_monthly_income_usd"

#: A retiree who clears every E33F conjunct that is NOT the sponsor's: the
#: RETIREMENT purpose, passive income at 5000 (bound 3000) and an age of 66
#: (bound 55). The sponsor answer is what each test varies.
_RETIREE: dict[str, Any] = {
    "intent.purposes": _known(["RETIREMENT"]),
    "person.birth_date": _known("1960-01-01"),
    _INCOME_FACT: _known(5000),
}

_SPONSOR_ANSWERS: dict[str, dict[str, Any]] = {
    "TRUE": _known(True),
    "FALSE": _known(False),
    "UNKNOWN": _UNKNOWN,
}


def _retiree(sponsor: str, **overrides: Any) -> dict[str, Any]:
    return {**_RETIREE, SPONSOR_FACT: _SPONSOR_ANSWERS[sponsor], **overrides}


def _request(overrides: dict[str, Any]) -> VisaOracleEvaluateRequest:
    persona = Persona(
        id=0, label="seq24-e33f", overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    return build_persona_request(persona)


def _decide(pack: compiler.CompiledRulePack, overrides: dict[str, Any]) -> dict[str, Any]:
    """compile -> evaluate -> ``apply_public_policy_adapters``, the same
    applicant-facing path ``test_seq23_pack.py``'s own ``_decide`` walks."""
    request = _request(overrides)
    facts = request.applicant_facts()
    decision = evaluator.evaluate(
        facts,
        pack,
        effective_at=EVALUATED_AT,
        observed_at=EVALUATED_AT,
        identity_provider=_offline_identity_provider,
    )
    decision = evaluate_path.apply_public_policy_adapters(
        decision, facts, pack, disclosed_review_flags=request.effective_review_flags()
    )
    return _decision_actual(decision)


def _product_proof(
    pack: compiler.CompiledRulePack, overrides: dict[str, Any], product_code: str
) -> evaluator.ProductProof:
    """The one product's own proof — its reasons carry `rule_ids`, so the
    witness names the rule that decided, not only a code other rules share."""
    snapshot = DEFAULT_FACT_REGISTRY.derive(
        _request(overrides).applicant_facts(), effective_at=EVALUATED_AT
    )
    purposes_fact = snapshot.values.get(FactPath.INTENT_PURPOSES)
    purposes = frozenset(getattr(purposes_fact, "value", None) or ())
    product = next(p for p in pack.products if p.product_code == product_code)
    return evaluator.evaluate_product(
        product=product,
        rules=pack.rules_for(product, effective_at=EVALUATED_AT),
        facts=snapshot,
        purposes=purposes,
    )


def _reasons(proof: evaluator.ProductProof) -> list[tuple[str, tuple[str, ...]]]:
    return [(reason.code, tuple(reason.rule_ids)) for reason in proof.reasons]


def _e33f_candidate_failures(pack: compiler.CompiledRulePack, sponsor: str) -> list[str]:
    """Every way the retiree with this sponsor answer is NOT an E33F
    candidate on `pack`. Empty means the ruling is in force for that answer."""
    failures: list[str] = []
    overrides = _retiree(sponsor)
    proof = _product_proof(pack, overrides, "E33F")
    if proof.status is not ProductProofStatus.SUPPORTED:
        failures.append(
            f"sponsor {sponsor}: E33F is {proof.status.value} {_reasons(proof)} "
            f"missing {sorted(f.value for f in proof.missing_facts)}, not SUPPORTED"
        )
    decision = _decide(pack, overrides)
    if decision["state"] != "SUPPORTED_CANDIDATES" or "E33F" not in decision["candidates"]:
        failures.append(
            f"sponsor {sponsor}: decision is {decision['state']} {decision['candidates']} "
            f"missing {decision['missing_facts']} no-path {decision['no_path_reason_codes']}, "
            "not SUPPORTED_CANDIDATES naming E33F"
        )
    if SPONSOR_FACT in decision["missing_facts"]:
        failures.append(f"sponsor {sponsor}: the applicant is still asked for {SPONSOR_FACT}")
    if SPONSOR_REQUIRED_REASON_CODE in decision["no_path_reason_codes"]:
        failures.append(
            f"sponsor {sponsor}: the applicant is still told {SPONSOR_REQUIRED_REASON_CODE}"
        )
    return failures


class TestE33fEngineWitnesses:
    @pytest.mark.parametrize("sponsor", sorted(_SPONSOR_ANSWERS))
    def test_a_retiree_is_an_e33f_candidate_whatever_the_sponsor_answer(
        self, seq24_compiled: compiler.CompiledRulePack, sponsor: str
    ) -> None:
        """INNOCENCE: sponsor TRUE, FALSE and UNKNOWN, RETIREMENT with income
        >= 3000 and age >= 55, all yield SUPPORTED E33F on seq-24."""
        assert _e33f_candidate_failures(seq24_compiled, sponsor) == []

    def test_the_same_retiree_on_seq23_is_refused_unless_the_sponsor_is_confirmed(
        self, seq23_compiled: compiler.CompiledRulePack
    ) -> None:
        """GUILT of the witness itself: on the signed seq-23 the FALSE answer
        is EXCLUDED by the retired rule and the UNKNOWN answer is BLOCKED on
        the sponsor fact; only TRUE is a candidate. A witness both packs
        pass would not be measuring the ruling."""
        assert _e33f_candidate_failures(seq23_compiled, "TRUE") == []

        false_proof = _product_proof(seq23_compiled, _retiree("FALSE"), "E33F")
        assert false_proof.status is ProductProofStatus.EXCLUDED
        assert (SPONSOR_REQUIRED_REASON_CODE, (SPONSOR_REQUIRED_RULE_ID,)) in _reasons(false_proof)
        assert _e33f_candidate_failures(seq23_compiled, "FALSE") != []

        unknown_proof = _product_proof(seq23_compiled, _retiree("UNKNOWN"), "E33F")
        assert unknown_proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert SPONSOR_FACT in {f.value for f in unknown_proof.missing_facts}
        assert _e33f_candidate_failures(seq23_compiled, "UNKNOWN") != []

    @pytest.mark.parametrize("sponsor", sorted(_SPONSOR_ANSWERS))
    def test_income_below_the_minimum_still_excludes_e33f(
        self, seq24_compiled: compiler.CompiledRulePack, sponsor: str
    ) -> None:
        overrides = _retiree(sponsor, **{_INCOME_FACT: _known(2000)})
        proof = _product_proof(seq24_compiled, overrides, "E33F")
        assert proof.status is ProductProofStatus.EXCLUDED
        assert _reasons(proof) == [("RETIREMENT_INCOME_BELOW_THRESHOLD", (E33F_INCOME_RULE_ID,))]
        assert _decide(seq24_compiled, overrides)["candidates"] == []

    @pytest.mark.parametrize("sponsor", sorted(_SPONSOR_ANSWERS))
    def test_age_below_55_still_excludes_e33f(
        self, seq24_compiled: compiler.CompiledRulePack, sponsor: str
    ) -> None:
        overrides = _retiree(sponsor, **{"person.birth_date": _known("1990-01-01")})
        proof = _product_proof(seq24_compiled, overrides, "E33F")
        assert proof.status is ProductProofStatus.EXCLUDED
        assert _reasons(proof) == [("AGE_BELOW_55", (E33F_AGE_RULE_ID,))]
        assert _decide(seq24_compiled, overrides)["candidates"] == []

    @pytest.mark.parametrize(
        ("income", "supported"),
        [(3000, True), (2999, False)],
    )
    def test_the_income_bound_is_still_3000_for_an_unconfirmed_sponsor(
        self, seq24_compiled: compiler.CompiledRulePack, income: int, supported: bool
    ) -> None:
        proof = _product_proof(
            seq24_compiled, _retiree("FALSE", **{_INCOME_FACT: _known(income)}), "E33F"
        )
        assert (proof.status is ProductProofStatus.SUPPORTED) is supported

    @pytest.mark.parametrize(
        ("birth_date", "supported"),
        [("1971-09-26", True), ("1971-09-28", False)],
    )
    def test_the_age_bound_is_still_55_for_an_unconfirmed_sponsor(
        self, seq24_compiled: compiler.CompiledRulePack, birth_date: str, supported: bool
    ) -> None:
        proof = _product_proof(
            seq24_compiled,
            _retiree("FALSE", **{"person.birth_date": _known(birth_date)}),
            "E33F",
        )
        assert (proof.status is ProductProofStatus.SUPPORTED) is supported

    def test_an_unknown_income_is_asked_for_and_is_no_longer_masked_by_the_sponsor(
        self, seq24_compiled: compiler.CompiledRulePack
    ) -> None:
        """The applicant who declared no sponsor and has not said what the
        income is is asked for the income — not told SPONSOR_REQUIRED, as
        seq-23's excluded-first ordering did."""
        overrides = _retiree("FALSE", **{_INCOME_FACT: _UNKNOWN})
        proof = _product_proof(seq24_compiled, overrides, "E33F")
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert {f.value for f in proof.missing_facts} == {_INCOME_FACT}
        decision = _decide(seq24_compiled, overrides)
        assert decision["state"] == "NEEDS_INPUT"
        assert decision["missing_facts"] == [_INCOME_FACT]

    @pytest.mark.parametrize("sponsor", sorted(_SPONSOR_ANSWERS))
    def test_no_product_proof_emits_sponsor_required_for_a_retiree(
        self, seq24_compiled: compiler.CompiledRulePack, sponsor: str
    ) -> None:
        """The engine-level twin of "no rule emits SPONSOR_REQUIRED": every
        product's proof of the retiree, not only E33F's."""
        overrides = _retiree(sponsor)
        for product in seq24_compiled.products:
            proof = _product_proof(seq24_compiled, overrides, product.product_code)
            assert SPONSOR_REQUIRED_REASON_CODE not in {code for code, _ in _reasons(proof)}, (
                product.product_code
            )

    def test_the_minor_sponsor_gate_elsewhere_in_the_pack_still_fires(
        self, seq24_compiled: compiler.CompiledRulePack
    ) -> None:
        """INNOCENCE: the ruling touches E33F only — a minor with no
        confirmed sponsor is still excluded, and one whose sponsor is unknown
        is still asked for it (`hf.minor-without-confirmed-sponsor`)."""
        minor = {"person.birth_date": _known("2015-01-01")}
        excluded = _product_proof(seq24_compiled, {**minor, SPONSOR_FACT: _known(False)}, "C1")
        assert excluded.status is ProductProofStatus.EXCLUDED
        assert ("MINOR_SPONSOR_NOT_CONFIRMED", ("hf.minor-without-confirmed-sponsor",)) in _reasons(
            excluded
        )
        asked = _product_proof(seq24_compiled, {**minor, SPONSOR_FACT: _UNKNOWN}, "C1")
        assert asked.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert SPONSOR_FACT in {f.value for f in asked.missing_facts}

    def test_guilt_reinstating_the_retired_rule_turns_the_false_witness_red(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any]
    ) -> None:
        """GUILT: put `hf.e33f.sponsor-required` back in a scratch copy of
        seq-24 and the FALSE persona is no longer a candidate — the witness
        discriminates the retirement."""
        reverted = copy.deepcopy(seq24_source)
        reverted["rules"].append(
            copy.deepcopy(_rules_by_id(seq23_source)[SPONSOR_REQUIRED_RULE_ID])
        )
        pack = _compiled(reverted)
        assert _e33f_candidate_failures(pack, "FALSE") != []
        assert _e33f_candidate_failures(pack, "TRUE") == []

    @pytest.mark.parametrize("sponsor", ["FALSE", "UNKNOWN"])
    def test_guilt_restoring_the_sponsor_conjunct_turns_the_witness_red(
        self, seq23_source: dict[str, Any], seq24_source: dict[str, Any], sponsor: str
    ) -> None:
        """GUILT: put the third conjunct back on `el.e33f.retirement` in a
        scratch copy — without the retired rule, so the conjunct alone is the
        cause — and the unconfirmed-sponsor personas stop being candidates."""
        reverted = copy.deepcopy(seq24_source)
        original = _rules_by_id(seq23_source)[E33F_RETIREMENT_RULE_ID]
        for index, rule in enumerate(reverted["rules"]):
            if rule["rule_id"] == E33F_RETIREMENT_RULE_ID:
                reverted["rules"][index] = copy.deepcopy(original)
        pack = _compiled(reverted)
        assert _e33f_candidate_failures(pack, sponsor) != []
        assert _e33f_candidate_failures(pack, "TRUE") == []

    def test_the_compiled_e33f_rule_set_matches_the_source(
        self, seq24_compiled: compiler.CompiledRulePack
    ) -> None:
        product = next(p for p in seq24_compiled.products if p.product_code == "E33F")
        rule_ids = {r.rule_id for r in seq24_compiled.rules_for(product, effective_at=EVALUATED_AT)}
        assert SPONSOR_REQUIRED_RULE_ID not in rule_ids
        assert {E33F_RETIREMENT_RULE_ID, E33F_AGE_RULE_ID, E33F_INCOME_RULE_ID} <= rule_ids


# ---------------------------------------------------------------------------
# Antibodies carried forward — copied, not weakened.
# ---------------------------------------------------------------------------


class TestAntibodies:
    def test_innocence_the_real_pack_passes_the_twin_basis_guard(
        self, seq24_source: dict[str, Any]
    ) -> None:
        assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(seq24_source)

    @pytest.mark.parametrize("fact", SYNTHESISED_TWIN_BASIS_FACTS)
    def test_guilt_adding_a_twin_basis_fact_to_an_e33f_filter_aborts(
        self, seq24_source: dict[str, Any], fact: str
    ) -> None:
        """GUILT: add a twin-basis fact to the E33F income HARD_FILTER and the
        fold-time antibody refuses, naming the rule."""
        tampered = copy.deepcopy(seq24_source)
        target = _rules_by_id(tampered)[E33F_INCOME_RULE_ID]
        target["when"]["args"].append({"op": "eq", "fact": fact, "value": False})
        with pytest.raises(SystemExit) as excinfo:
            assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(tampered)
        assert E33F_INCOME_RULE_ID in str(excinfo.value)

    def test_the_guard_still_measures_something(self) -> None:
        """A pack with no reader of any twin-basis fact aborts: the traversal
        that found nothing is not measuring what it claims to measure."""
        with pytest.raises(SystemExit) as excinfo:
            assert_no_hard_filter_reads_a_synthesised_twin_basis_fact({"rules": []})
        assert "not measuring" in str(excinfo.value)


# ---------------------------------------------------------------------------
# The inventory target, derived: exactly one HUMAN_REVIEW rule, no escalation.
# ---------------------------------------------------------------------------


class TestDerivedInventory:
    def test_innocence_the_candidate_carries_exactly_one_review_rule_and_no_escalation(
        self, seq24_source: dict[str, Any]
    ) -> None:
        _assert_candidate_review_inventory(seq24_source)
        validated = RulePackPayload.model_validate(seq24_source)
        assert [r.rule_id for r in pack_review_rules(validated)] == [STUDIO_RULE_ID]
        assert tuple(pack_unknown_escalations(validated)) == ()

    def test_guilt_keeping_human_review_on_a_bridging_filter_fails_naming_it(
        self, seq24_source: dict[str, Any]
    ) -> None:
        tampered = copy.deepcopy(seq24_source)
        for rule in tampered["rules"]:
            if rule["rule_id"] == "hf.bridging.offshore":
                rule["on_unknown"] = "HUMAN_REVIEW"
        with pytest.raises(SystemExit) as excinfo:
            _assert_candidate_review_inventory(tampered)
        assert "hf.bridging.offshore" in str(excinfo.value)

    def test_guilt_a_second_human_review_rule_fails(self, seq24_source: dict[str, Any]) -> None:
        """GUILT: a second HUMAN_REVIEW-stage rule (a copy of the Studio rule
        under another id) and the derived inventory refuses — one is the
        target, not 'at least one'."""
        tampered = copy.deepcopy(seq24_source)
        second = copy.deepcopy(_rules_by_id(seq24_source)[STUDIO_RULE_ID])
        second["rule_id"] = "review.a-second-hold"
        tampered["rules"].append(second)
        with pytest.raises(SystemExit) as excinfo:
            _assert_candidate_review_inventory(tampered)
        assert "expected exactly" in str(excinfo.value)
        assert "review.a-second-hold" in str(excinfo.value)

    def test_guilt_losing_the_studio_rule_is_refused_by_the_inventory_itself(
        self, seq24_source: dict[str, Any]
    ) -> None:
        """GUILT: with no HUMAN_REVIEW rule left the inventory raises rather
        than return a silent empty result (its own guard-under-match antidote,
        cicatrix family #3)."""
        tampered = copy.deepcopy(seq24_source)
        tampered["rules"] = [r for r in tampered["rules"] if r["rule_id"] != STUDIO_RULE_ID]
        with pytest.raises(RuntimeError, match="zero HUMAN_REVIEW-stage rules"):
            _assert_candidate_review_inventory(tampered)


# ---------------------------------------------------------------------------
# The pack still validates and compiles.
# ---------------------------------------------------------------------------


def test_the_candidate_payload_validates_against_the_model(seq24_source: dict[str, Any]) -> None:
    validated = RulePackPayload.model_validate(seq24_source)
    assert validated.sequence == 24


def test_the_candidate_pack_compiles(seq24_compiled: compiler.CompiledRulePack) -> None:
    assert seq24_compiled.sequence == 24


# ---------------------------------------------------------------------------
# The signed artifact IS the tracked source. The signing PR (2026-09-27) lands
# rulepack-prod-024.signed.json; this class ties its payload to
# rulepack-prod-024.source.json and to seq-24's own pinned digest, and verifies
# the Ed25519 signature with the repo's own code against the PUBLIC production
# key — never the signer's self-report. Same shape as test_seq23_pack.py's
# TestSignedBundleTiesToSource. A missing bundle FAILS (via `_read_json`), it
# never skips (cicatrix #2).
# ---------------------------------------------------------------------------


class TestSignedBundleTiesToSource:
    def test_sha256_of_canonicalized_source_matches_h24(
        self, seq24_source_on_disk: dict[str, Any]
    ) -> None:
        assert (
            hashlib.sha256(canonicalize_json(seq24_source_on_disk)).hexdigest()
            == SEQ24_PAYLOAD_SHA256
        )

    def test_sha256_of_canonicalized_signed_payload_matches_its_declared_field(
        self, seq24_signed: dict[str, Any]
    ) -> None:
        recomputed = hashlib.sha256(canonicalize_json(seq24_signed["payload"])).hexdigest()
        assert recomputed == seq24_signed["payload_sha256"]
        assert recomputed == SEQ24_PAYLOAD_SHA256

    def test_signed_payload_is_byte_identical_to_source_under_jcs(
        self, seq24_signed: dict[str, Any], seq24_source_on_disk: dict[str, Any]
    ) -> None:
        """The artifact that was signed is the artifact in version control — a
        divergence would mean the tracked source.json is not what the operator
        actually signed."""
        assert canonicalize_json(seq24_signed["payload"]) == canonicalize_json(seq24_source_on_disk)

    def test_the_committed_bundle_verifies_against_the_pinned_production_key(
        self, seq24_signed: dict[str, Any], prod_trust_store_env: None
    ) -> None:
        verified = verify_rule_pack(
            seq24_signed,
            trust_store=StaticTrustStore.from_env(),
            observed_at=SEQ24_OBSERVED_AT,
        )
        assert verified.unsigned_dev is False
        assert verified.pack.protected.kid == "prod-2026-07-1"
        assert verified.pack.protected.environment == "PRODUCTION"
        assert verified.pack.payload.environment == "PRODUCTION"
        assert verified.pack.payload.sequence == 24
        assert verified.payload_sha256.hex() == SEQ24_PAYLOAD_SHA256
        assert len(verified.pack.payload.rules) == 113

    def test_the_chain_anchor_is_the_signed_seq23_payload_digest(
        self, seq24_signed: dict[str, Any], seq23_signed: dict[str, Any]
    ) -> None:
        assert seq24_signed["payload"]["previous_payload_sha256"] == SEQ23_PAYLOAD_SHA256
        assert seq24_signed["payload"]["previous_payload_sha256"] == seq23_signed["payload_sha256"]
        assert seq24_signed["payload"]["rollback_of_payload_sha256"] is None

    def test_the_signature_postdates_the_payload_it_seals(
        self, seq24_signed: dict[str, Any]
    ) -> None:
        signed_at = datetime.fromisoformat(
            seq24_signed["protected"]["signed_at"].replace("Z", "+00:00")
        )
        created_at = datetime.fromisoformat(
            seq24_signed["payload"]["created_at"].replace("Z", "+00:00")
        )
        assert signed_at == SEQ24_SIGNED_AT
        assert signed_at > created_at

    def test_guilt_flipping_one_byte_of_the_signed_payload_moves_the_digest_away_from_h24(
        self, seq24_signed: dict[str, Any]
    ) -> None:
        """GUILT: H24 discriminates — a scratch copy of the signed payload's
        canonical bytes with ONE byte flipped no longer hashes to H24. Never
        mutates the fixture or any file on disk."""
        canonical = bytearray(canonicalize_json(seq24_signed["payload"]))
        canonical[-1] ^= 0x01
        assert hashlib.sha256(bytes(canonical)).hexdigest() != SEQ24_PAYLOAD_SHA256

    def test_guilt_a_tampered_payload_is_refused_by_the_verifier(
        self, seq24_signed: dict[str, Any], prod_trust_store_env: None
    ) -> None:
        """GUILT: the innocence test above proves nothing if the verifier accepts
        anything — retire-then-restore one rule id in a scratch copy and the
        signature no longer verifies."""
        tampered = copy.deepcopy(seq24_signed)
        tampered["payload"]["rules"] = [
            r for r in tampered["payload"]["rules"] if r["rule_id"] != E33F_AGE_RULE_ID
        ]
        with pytest.raises(RulePackVerificationError):
            verify_rule_pack(
                tampered,
                trust_store=StaticTrustStore.from_env(),
                observed_at=SEQ24_OBSERVED_AT,
            )
