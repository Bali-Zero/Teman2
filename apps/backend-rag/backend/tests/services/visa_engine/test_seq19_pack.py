"""Gates for seq-19 (``rulepack-prod-019.source.json``): re-landing seq-15's
E31 fail-open repair onto the currently-active seq-18 chain.

Ground: ``research/operations/2026-09-05-consuls-ground-visaoracle-engine.md``
(Q3) and its independently re-run refutation
(``...-visaoracle-refutation.md``) establish that seq-15's repair never
reached production — seq-16 re-parented onto seq-13, bypassing 14/15, and
seq-17/seq-18 chain from seq-16. See ``fold_pack_seq19.py``'s docstring for
the full chain diagnosis and what this fold transplants.

seq-19 is NOT SIGNED and NOT ACTIVATED by anything in this module or in
``fold_pack_seq19.py`` — signing is the consul's ceremony
(``sign_pack.py``, an operator-supplied Ed25519 key), so every witness here
that needs a compiled pack builds one with ``compile_pack.wrap_as_unsigned_
pack`` (a placeholder envelope, never a trust claim — see that helper's own
docstring) instead of going through ``gold_replay_driver.select_highest_
repository_pack``/``verify_rule_pack``, both of which are pinned to the real
hardcoded production Ed25519 public key and would refuse an unsigned
``environment: PRODUCTION`` payload unconditionally. This is a disk fact,
not a design choice made here: ``gold_coverage_eval._evaluate`` and
``gold_replay_driver.replay_offline_decisions`` both hardcode
``PACKS_DIR``/``_repository_trust_store()`` internally with no override, so
neither CLI can be pointed at an unsigned candidate pack at all. The gold
coverage and gold-replay witnesses below reproduce those two scripts' own
evaluate path (``evaluator.evaluate`` -> ``apply_public_policy_adapters``,
imported, never reimplemented) directly against a 019 ``CompiledRulePack``
instead of going through the file-selection/signature layer neither script
lets a caller bypass.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_pack import (
    compile_rule_pack,
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.scripts.visa_engine.fold_pack_seq19 import (
    EDITED_RULE_IDS,
    REMOVED_RULE_IDS,
    SEQ18_PAYLOAD_SHA256,
    SPONSOR_TERMINAL_RULE_IDS,
    STEPCHILD_RULE_ID,
    _rule_pack_id,
    fold,
)
from backend.scripts.visa_engine.gold_replay_driver import (
    PERSONAS,
    _offline_identity_provider,
    build_persona_request,
    build_report,
)
from backend.services.visa_engine import compiler, evaluate_path, evaluator
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import DecisionState, RulePackPayload
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ13_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-013.source.json"
_SEQ15_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-015.source.json"
_SEQ18_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-018.source.json"
_SEQ18_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-018.signed.json"
_SEQ19_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-019.source.json"
_GOLD_COVERAGE_CORPUS = Path(__file__).resolve().parent / "gold_coverage" / "personas"

pytestmark = pytest.mark.skipif(
    not _SEQ19_SOURCE_PATH.exists(),
    reason="rulepack-prod-019.source.json does not exist on disk — run "
    "`PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq19`",
)

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

#: After the seq-18 signed_at (2026-08-30T17:18:16Z), before the seq-19 fold
#: date's own claimed created_at — never real wall clock.
OBSERVED_AT = datetime(2026, 9, 5, 0, 30, 0, tzinfo=timezone.utc)

#: Pinned instant for every evaluator call below: inside the seq-18/seq-19
#: OFFICIAL_PORTAL freshness window (boundary 2026-10-01T13:18:00Z, see
#: ``fold_pack_seq18.py``), never ``datetime.now()`` — see the module
#: docstrings of ``test_seq15_e31_failopen_repair.py`` / ``test_seq18_
#: freshness_window.py`` for why a wall-clock evaluation against a
#: freshness-windowed pack is a clock bomb.
AS_OF = datetime(2026, 9, 5, 0, 30, 0, tzinfo=timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq13_source() -> dict[str, Any]:
    return _read_json(_SEQ13_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq15_source() -> dict[str, Any]:
    return _read_json(_SEQ15_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq18_source() -> dict[str, Any]:
    return _read_json(_SEQ18_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq18_signed() -> dict[str, Any]:
    return _read_json(_SEQ18_SIGNED_PATH)


@pytest.fixture(scope="module")
def seq19_source() -> dict[str, Any]:
    return _read_json(_SEQ19_SOURCE_PATH)


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


@pytest.fixture(scope="module")
def prod_trust_store_env_module(monkeypatch_module: pytest.MonkeyPatch) -> None:
    monkeypatch_module.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def seq19_compiled() -> compiler.CompiledRulePack:
    """A CompiledRulePack built from 019 through a PLACEHOLDER envelope —
    never a trust claim (see ``wrap_as_unsigned_pack``'s own docstring).
    019 is unsigned by design; this is the only way any witness here can
    exercise the real evaluator against it before the consul signs it."""
    payload = load_rule_pack_payload(_SEQ19_SOURCE_PATH)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


# ---------------------------------------------------------------------------
# Fold integrity
# ---------------------------------------------------------------------------


class TestFoldIntegrity:
    def test_fold_is_deterministic_and_matches_disk(
        self,
        seq18_source: dict[str, Any],
        seq18_signed: dict[str, Any],
        seq15_source: dict[str, Any],
        seq13_source: dict[str, Any],
        seq19_source: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        assert fold(seq18_source, seq18_signed, seq15_source, seq13_source) == seq19_source

    def test_fold_is_byte_invariant_across_two_runs(
        self,
        seq18_source: dict[str, Any],
        seq18_signed: dict[str, Any],
        seq15_source: dict[str, Any],
        seq13_source: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        first = fold(seq18_source, seq18_signed, seq15_source, seq13_source)
        second = fold(seq18_source, seq18_signed, seq15_source, seq13_source)
        assert canonicalize_json(first) == canonicalize_json(second)

    def test_compile_rule_pack_reports_ok(self) -> None:
        payload = load_rule_pack_payload(_SEQ19_SOURCE_PATH)
        report = compile_rule_pack(wrap_as_unsigned_pack(payload))
        assert report.ok, f"seq-19 does not compile clean: {report}"

    def test_source_validates_against_the_payload_model(
        self, seq19_source: dict[str, Any]
    ) -> None:
        payload = RulePackPayload.model_validate(seq19_source)
        assert payload.sequence == 19

    def test_rule_delta_is_exactly_the_declared_one(
        self, seq18_source: dict[str, Any], seq19_source: dict[str, Any]
    ) -> None:
        def canon(rule: dict[str, Any]) -> str:
            return json.dumps(rule, sort_keys=True, separators=(",", ":"))

        r18 = {r["rule_id"]: r for r in seq18_source["rules"]}
        r19 = {r["rule_id"]: r for r in seq19_source["rules"]}
        assert set(r18) - set(r19) == set(REMOVED_RULE_IDS)
        assert set(r19) - set(r18) == set()
        drifted = {rid for rid in r19 if canon(r19[rid]) != canon(r18[rid])}
        assert drifted == set(EDITED_RULE_IDS)
        assert len(seq18_source["rules"]) - len(REMOVED_RULE_IDS) == len(seq19_source["rules"])

    def test_transplant_matches_seq15_bytes_exactly(
        self, seq15_source: dict[str, Any], seq19_source: dict[str, Any]
    ) -> None:
        """The whole point of a transplant: not "close to seq-15's shape",
        the EXACT bytes."""
        r15 = {r["rule_id"]: r for r in seq15_source["rules"]}
        r19 = {r["rule_id"]: r for r in seq19_source["rules"]}
        for rule_id in EDITED_RULE_IDS:
            assert r19[rule_id]["when"] == r15[rule_id]["when"], rule_id
        stepchild19, stepchild15 = r19[STEPCHILD_RULE_ID], r15[STEPCHILD_RULE_ID]
        assert stepchild19["required_facts"] == stepchild15["required_facts"]

    def test_no_sponsor_status_known_terminal_survives(
        self, seq19_source: dict[str, Any]
    ) -> None:
        def has_known_on_sponsor_status(node: Any) -> bool:
            if isinstance(node, dict):
                if node.get("op") == "known" and node.get("fact") == "family.sponsor_status_code":
                    return True
                return any(has_known_on_sponsor_status(v) for v in node.values())
            if isinstance(node, list):
                return any(has_known_on_sponsor_status(item) for item in node)
            return False

        for rule in seq19_source["rules"]:
            assert not has_known_on_sponsor_status(rule["when"]), rule["rule_id"]


# ---------------------------------------------------------------------------
# Identity + chain
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_sequence_is_19(self, seq19_source: dict[str, Any]) -> None:
        assert seq19_source["sequence"] == 19

    def test_rule_pack_id_follows_the_uuid5_convention(
        self, seq18_source: dict[str, Any], seq19_source: dict[str, Any]
    ) -> None:
        assert seq18_source["rule_pack_id"] == str(_rule_pack_id(18))
        assert seq19_source["rule_pack_id"] == str(_rule_pack_id(19))
        assert seq19_source["rule_pack_id"] != seq18_source["rule_pack_id"]

    def test_chain_anchor_is_the_real_seq18_digest(
        self, seq18_source: dict[str, Any], seq19_source: dict[str, Any]
    ) -> None:
        import hashlib

        recomputed = hashlib.sha256(canonicalize_json(seq18_source)).hexdigest()
        assert recomputed == SEQ18_PAYLOAD_SHA256
        assert seq19_source["previous_payload_sha256"] == SEQ18_PAYLOAD_SHA256

    def test_version_is_the_fold_date(
        self, seq18_source: dict[str, Any], seq19_source: dict[str, Any]
    ) -> None:
        assert seq18_source["version"] == "2026.8.31"
        assert seq19_source["version"] == "2026.9.5"

    def test_rollback_of_payload_sha256_is_null(self, seq19_source: dict[str, Any]) -> None:
        assert seq19_source["rollback_of_payload_sha256"] is None

    def test_non_identity_metadata_is_untouched(
        self, seq18_source: dict[str, Any], seq19_source: dict[str, Any]
    ) -> None:
        for key in (
            "environment",
            "decision_domain",
            "hit_policy",
            "jurisdiction",
            "engine_contract_version",
            "engine_min_version",
            "engine_max_version",
            "valid_period",
            "products",
            "source_records",
        ):
            assert seq19_source[key] == seq18_source[key], key


class TestSignatureAndChain:
    def test_signed_seq18_bundle_verifies_against_pinned_production_trust_store(
        self, seq18_signed: dict[str, Any], prod_trust_store_env: None
    ) -> None:
        verified = verify_rule_pack(
            seq18_signed,
            trust_store=StaticTrustStore.from_env(),
            observed_at=OBSERVED_AT,
        )
        assert verified.pack.protected.kid == "prod-2026-07-1"
        assert verified.pack.payload.sequence == 18

    def test_seq18_signed_digest_matches_the_source_on_disk(
        self, seq18_source: dict[str, Any], seq18_signed: dict[str, Any], prod_trust_store_env: None
    ) -> None:
        verified = verify_rule_pack(
            seq18_signed,
            trust_store=StaticTrustStore.from_env(),
            observed_at=OBSERVED_AT,
        )
        import hashlib

        assert (
            hashlib.sha256(canonicalize_json(seq18_source)).hexdigest()
            == verified.payload_sha256.hex()
        )


# ---------------------------------------------------------------------------
# The guard — exercised directly on hand-built minimal pairs (superscar #3:
# never a guard without guilt AND innocence). `fold()`'s own success path
# above proves the guards accept the REAL payload; this proves they reject
# what they claim to.
# ---------------------------------------------------------------------------


def _minimal_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """A minimal before/after ``assert_only_expected_changes`` must accept:
    one edited rule, all four retired rules, one untouched rule."""
    before: dict[str, Any] = {
        "sequence": 18,
        "rule_pack_id": "aaaaaaaa-0000-0000-0000-000000000000",
        "version": "2026.8.31",
        "created_at": "2026-08-31T00:00:00Z",
        "created_by": "someone",
        "previous_payload_sha256": "0" * 64,
        "rollback_of_payload_sha256": None,
        "environment": "PRODUCTION",
        "rules": [
            {
                "rule_id": SPONSOR_TERMINAL_RULE_IDS[0],
                "when": {"op": "known", "fact": "family.sponsor_status_code"},
                "priority": 100,
            },
            {"rule_id": "el.e31d-step-parent-relation", "when": {"op": "all", "args": []}},
            {"rule_id": "el.e31d-sponsor-mixed-marriage", "when": {"op": "all", "args": []}},
            {"rule_id": "review.e23u.requested-product", "when": {"op": "all", "args": []}},
            {"rule_id": "review.e23v.requested-product", "when": {"op": "all", "args": []}},
            {"rule_id": "el.untouched-rule", "when": {"op": "all", "args": []}, "priority": 50},
        ],
    }
    after = json.loads(json.dumps(before))
    after["sequence"] = 19
    after["rule_pack_id"] = "bbbbbbbb-0000-0000-0000-000000000000"
    after["version"] = "2026.9.5"
    after["created_at"] = "2026-09-05T00:00:00Z"
    after["created_by"] = "the fold"
    after["previous_payload_sha256"] = "1" * 64
    after["rules"] = [
        r for r in after["rules"] if r["rule_id"] not in REMOVED_RULE_IDS
    ]
    for rule in after["rules"]:
        if rule["rule_id"] == SPONSOR_TERMINAL_RULE_IDS[0]:
            rule["when"] = {"op": "in", "fact": "family.sponsor_status_code", "values": ["E23"]}
    return before, after


class TestGuardInnocence:
    def test_the_real_shape_of_this_fold_passes(self) -> None:
        before, after = _minimal_pair()
        from backend.scripts.visa_engine.fold_pack_seq19 import assert_only_expected_changes

        assert_only_expected_changes(before, after)  # must not raise


class TestGuardGuilt:
    """One parametrized case per mutation — `pytest.raises` visible in the
    test body, per this repo's anti-reward-hacking lint convention (a helper
    that swallows the assertion is exactly where a silently-weakened check
    would hide)."""

    @pytest.mark.parametrize(
        "mutate",
        [
            pytest.param(
                lambda a: a["rules"][-1].__setitem__("priority", 999),
                id="an-untouched-rule-changes",
            ),
            pytest.param(lambda a: a.__setitem__("surprise", 1), id="top-level-key-added"),
            pytest.param(
                lambda a: a["rules"].append({"rule_id": "el.new-rule", "when": {}}),
                id="a-rule-is-added",
            ),
            pytest.param(
                lambda a: a["rules"][0].__setitem__("priority", 200),
                id="an-edited-rule-changes-a-field-other-than-when",
            ),
            pytest.param(lambda a: a.__setitem__("environment", "STAGING"), id="a-non-identity-key-changes"),
        ],
    )
    def test_assert_only_expected_changes_rejects(self, mutate) -> None:
        from backend.scripts.visa_engine.fold_pack_seq19 import assert_only_expected_changes

        before, after = _minimal_pair()
        mutate(after)
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)

    def test_assert_only_expected_changes_rejects_a_retirement_that_did_not_land(self) -> None:
        from backend.scripts.visa_engine.fold_pack_seq19 import assert_only_expected_changes

        before, after = _minimal_pair()
        after["rules"].append(
            {"rule_id": "el.e31d-step-parent-relation", "when": {"op": "all", "args": []}}
        )
        with pytest.raises(SystemExit):
            assert_only_expected_changes(before, after)

    def test_value_guard_rejects_wrong_sequence(self, seq15_source: dict[str, Any]) -> None:
        from backend.scripts.visa_engine.fold_pack_seq19 import (
            assert_changed_fields_hold_their_expected_values,
        )

        _, after = _minimal_pair()
        after["sequence"] = 99
        seq15_rules_by_id = {r["rule_id"]: r for r in seq15_source["rules"]}
        with pytest.raises(SystemExit):
            assert_changed_fields_hold_their_expected_values(
                after, seq15_rules_by_id=seq15_rules_by_id
            )

    def test_value_guard_rejects_a_transplant_that_does_not_match_seq15_bytes(
        self, seq15_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq19 import (
            assert_changed_fields_hold_their_expected_values,
        )

        _, after = _minimal_pair()
        after["sequence"] = 19
        after["rule_pack_id"] = str(_rule_pack_id(19))
        after["created_at"] = "2026-09-05T00:00:00Z"
        after["created_by"] = "agent.air-m5.backend-rag.e31-failopen-repair-seq19.fold-2026-09-05"
        after["previous_payload_sha256"] = SEQ18_PAYLOAD_SHA256
        # Hand-authored instead of transplanted — exactly what this guard exists to catch.
        for rule in after["rules"]:
            if rule["rule_id"] == SPONSOR_TERMINAL_RULE_IDS[0]:
                rule["when"] = {"op": "neq", "fact": "family.sponsor_status_code", "value": "NONE"}
        seq15_rules_by_id = {r["rule_id"]: r for r in seq15_source["rules"]}
        with pytest.raises(SystemExit):
            assert_changed_fields_hold_their_expected_values(
                after, seq15_rules_by_id=seq15_rules_by_id
            )


class TestDriftGuard:
    """`_assert_edited_rules_unchanged_since_seq13` — added after adversarial
    review (kimi-code/k3) found the fold transplanted seq-15's delta onto
    seq-18 without ever verifying its own precondition (that none of the ten
    edited rule ids had drifted from seq-13 in seq-18). The real payloads'
    innocence is already proven by `TestFoldIntegrity`'s successful `fold()`
    call; this exercises guilt directly."""

    def test_innocence_the_real_payloads_pass(
        self, seq18_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq19 import (
            _assert_edited_rules_unchanged_since_seq13,
        )

        seq18_by_id = {r["rule_id"]: r for r in seq18_source["rules"]}
        seq13_by_id = {r["rule_id"]: r for r in seq13_source["rules"]}
        _assert_edited_rules_unchanged_since_seq13(seq18_by_id, seq13_by_id)  # must not raise

    def test_guilt_a_drifted_edited_rule_is_rejected(
        self, seq18_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq19 import (
            _assert_edited_rules_unchanged_since_seq13,
        )

        seq18_by_id = {r["rule_id"]: json.loads(json.dumps(r)) for r in seq18_source["rules"]}
        seq13_by_id = {r["rule_id"]: r for r in seq13_source["rules"]}
        seq18_by_id[SPONSOR_TERMINAL_RULE_IDS[0]]["priority"] = 999999
        with pytest.raises(SystemExit):
            _assert_edited_rules_unchanged_since_seq13(seq18_by_id, seq13_by_id)

    def test_guilt_a_missing_edited_rule_is_rejected(
        self, seq18_source: dict[str, Any], seq13_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq19 import (
            _assert_edited_rules_unchanged_since_seq13,
        )

        seq18_by_id = {
            r["rule_id"]: r
            for r in seq18_source["rules"]
            if r["rule_id"] != SPONSOR_TERMINAL_RULE_IDS[0]
        }
        seq13_by_id = {r["rule_id"]: r for r in seq13_source["rules"]}
        with pytest.raises(SystemExit):
            _assert_edited_rules_unchanged_since_seq13(seq18_by_id, seq13_by_id)

    def test_fold_rejects_a_tampered_seq13_drift_check_input(
        self,
        seq18_source: dict[str, Any],
        seq18_signed: dict[str, Any],
        seq15_source: dict[str, Any],
        seq13_source: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        """`fold()` itself refuses a `--seq13-source` that does not re-hash to
        the real signed seq-13 digest — never trusts the caller's file."""
        tampered_seq13 = json.loads(json.dumps(seq13_source))
        tampered_seq13["rules"][0]["priority"] = 999999
        with pytest.raises(SystemExit):
            fold(seq18_source, seq18_signed, seq15_source, tampered_seq13)


class TestFoldObservedAtThreading:
    """`fold()` threads `observed_at` into the anchor's signature-verification
    clock check instead of always reading `datetime.now()` — pinned here so
    the witness is not itself real-clock-dependent (found by adversarial
    review of this diff, codex terra)."""

    def test_fold_succeeds_with_a_pinned_observed_at(
        self,
        seq18_source: dict[str, Any],
        seq18_signed: dict[str, Any],
        seq15_source: dict[str, Any],
        seq13_source: dict[str, Any],
        seq19_source: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        result = fold(
            seq18_source,
            seq18_signed,
            seq15_source,
            seq13_source,
            observed_at=OBSERVED_AT,
        )
        assert result == seq19_source


class TestOutputCollisionGuard:
    """`main()`'s fail-closed guard against `--output` equalling one of its
    own inputs (or a signed-looking path) — added after adversarial review
    (codex terra) found no such guard, so a careless invocation could
    overwrite an input, or the SIGNED production anchor, with unsigned fold
    bytes. Guilt and innocence in one witness (superscar #3: never a guard
    without both): the guilty invocation must be refused without mutating
    the signed file it targeted, and a normal invocation to a fresh path
    must still go through end to end."""

    def test_output_equal_to_seq18_signed_is_refused_but_a_normal_invocation_still_works(
        self, tmp_path: Path, prod_trust_store_env: None
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq19 import main

        before_bytes = _SEQ18_SIGNED_PATH.read_bytes()
        guilty_argv = [
            "--seq18-source",
            str(_SEQ18_SOURCE_PATH),
            "--seq15-source",
            str(_SEQ15_SOURCE_PATH),
            "--seq13-source",
            str(_SEQ13_SOURCE_PATH),
            "--output",
            str(_SEQ18_SIGNED_PATH),
        ]
        with pytest.raises(SystemExit):
            main(guilty_argv, observed_at=OBSERVED_AT)
        assert _SEQ18_SIGNED_PATH.read_bytes() == before_bytes

        output_path = tmp_path / "rulepack-prod-019.source.json"
        innocent_argv = [
            "--seq18-source",
            str(_SEQ18_SOURCE_PATH),
            "--seq15-source",
            str(_SEQ15_SOURCE_PATH),
            "--seq13-source",
            str(_SEQ13_SOURCE_PATH),
            "--output",
            str(output_path),
        ]
        rc = main(innocent_argv, observed_at=OBSERVED_AT)
        assert rc == 0
        assert output_path.exists()


# ---------------------------------------------------------------------------
# Behavioral witnesses (real evaluator on a CompiledRulePack built from 019)
# ---------------------------------------------------------------------------


def _evaluate(
    seq19: compiler.CompiledRulePack, overrides: dict[str, dict[str, Any]]
) -> tuple[str, list[str]]:
    persona = Persona(
        id=0, label="seq19-witness", overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    request = build_persona_request(persona)
    facts = request.applicant_facts()
    decision = evaluator.evaluate(
        facts,
        seq19,
        effective_at=AS_OF,
        observed_at=AS_OF,
        identity_provider=_offline_identity_provider,
    )
    decision = evaluate_path.apply_public_policy_adapters(decision, facts, seq19)
    return decision.state.name, [c.product_code for c in decision.candidates]


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


_SPOUSE_BASE = {
    "intent.purposes": _known(["FAMILY"]),
    "family.relation_to_sponsor": _known("SPOUSE"),
    "family.marriage_registered": _known(True),
}


class TestGuilt:
    def test_sponsor_status_none_no_longer_supports_e31b(
        self, seq19_compiled: compiler.CompiledRulePack
    ) -> None:
        state, candidates = _evaluate(
            seq19_compiled, {**_SPOUSE_BASE, "family.sponsor_status_code": _known("NONE")}
        )
        assert "E31B" not in candidates
        assert "E31D" not in candidates

    def test_family_intent_alone_no_longer_supports_e31d(
        self, seq19_compiled: compiler.CompiledRulePack
    ) -> None:
        state, candidates = _evaluate(seq19_compiled, {"intent.purposes": _known(["FAMILY"])})
        assert "E31D" not in candidates

    def test_unknown_stepchild_evidence_never_supports_e31d(
        self, seq19_compiled: compiler.CompiledRulePack
    ) -> None:
        state, candidates = _evaluate(
            seq19_compiled,
            {
                "intent.purposes": _known(["FAMILY"]),
                "family.relation_to_sponsor": _known("STEPCHILD"),
            },
        )
        assert "E31D" not in candidates


class TestInnocence:
    def test_spouse_of_a_real_itas_holder_keeps_e31b(
        self, seq19_compiled: compiler.CompiledRulePack
    ) -> None:
        state, candidates = _evaluate(
            seq19_compiled, {**_SPOUSE_BASE, "family.sponsor_status_code": _known("E23")}
        )
        assert state == "SUPPORTED_CANDIDATES"
        assert "E31B" in candidates

    def test_stepchild_with_both_certificates_keeps_e31d(
        self, seq19_compiled: compiler.CompiledRulePack
    ) -> None:
        state, candidates = _evaluate(
            seq19_compiled,
            {
                "intent.purposes": _known(["FAMILY"]),
                "family.relation_to_sponsor": _known("STEPCHILD"),
                "family.sponsor_confirmed": _known(True),
                "family.stepchild_birth_certificate_confirmed": _known(True),
                "family.stepchild_marriage_certificate_confirmed": _known(True),
            },
        )
        assert state == "SUPPORTED_CANDIDATES"
        assert "E31D" in candidates

    def test_gold_persona_7_keeps_the_genuine_spouse_of_wni_path(
        self, seq19_compiled: compiler.CompiledRulePack
    ) -> None:
        persona_7 = PERSONAS[6]
        assert persona_7.id == 7
        state, candidates = _evaluate(seq19_compiled, dict(persona_7.overrides))
        assert state == "SUPPORTED_CANDIDATES"
        assert "E31A" in candidates
        assert "E31B" not in candidates
        assert "E31D" not in candidates


# ---------------------------------------------------------------------------
# Gold-coverage replay (all 18 personas), against the 019 CompiledRulePack —
# same evaluate path as gold_coverage_eval._evaluate, minus the repository
# file-selection/signature step neither script lets a caller override (see
# module docstring).
# ---------------------------------------------------------------------------


def _coverage_persona_specs() -> list[tuple[str, dict[str, Any]]]:
    specs = []
    for path in sorted(_GOLD_COVERAGE_CORPUS.glob("*.json")):
        specs.append((path.name, json.loads(path.read_text(encoding="utf-8"))))
    return specs


class TestGoldCoverageReplay:
    def test_corpus_has_eighteen_personas(self) -> None:
        assert len(_coverage_persona_specs()) == 18

    @pytest.mark.parametrize(
        "name,spec", _coverage_persona_specs(), ids=[n for n, _ in _coverage_persona_specs()]
    )
    def test_persona_is_supported_against_seq19(
        self, name: str, spec: dict[str, Any], seq19_compiled: compiler.CompiledRulePack
    ) -> None:
        state, candidates = _evaluate(seq19_compiled, spec["overrides"])
        expected_candidates = list(spec.get("expected_candidates") or [])
        missing = [c for c in expected_candidates if c not in candidates]
        assert state == spec["expected_state"], (name, state, candidates)
        assert not missing, (name, missing, candidates)


# ---------------------------------------------------------------------------
# gold_replay_driver's 20-persona report, built via the driver's own
# `build_report` (never reimplemented) fed decisions computed against the
# 019 CompiledRulePack — see module docstring for why this cannot go through
# `replay_offline_decisions` unmodified.
# ---------------------------------------------------------------------------


def _offline_decisions_against(
    compiled: compiler.CompiledRulePack, *, evaluated_at: datetime
) -> tuple[Any, ...]:
    decisions = []
    for persona in PERSONAS:
        request = build_persona_request(persona)
        facts = request.applicant_facts()
        decision = evaluator.evaluate(
            facts,
            compiled,
            effective_at=evaluated_at,
            observed_at=evaluated_at,
            identity_provider=_offline_identity_provider,
        )
        decisions.append(
            evaluate_path.apply_public_policy_adapters(
                decision, facts, compiled, disclosed_review_flags=request.effective_review_flags()
            )
        )
    return tuple(decisions)


def _offline_report_for(
    compiled: compiler.CompiledRulePack, *, label: str
) -> dict[str, Any]:
    decisions = _offline_decisions_against(compiled, evaluated_at=AS_OF)
    return build_report(
        mode="offline",
        generated_at=AS_OF,
        decisions=decisions,
        pack_source={"kind": "test-derived", "selection": label, "file": label},
    )


@pytest.fixture(scope="module")
def seq18_verified_compiled(
    seq18_signed: dict[str, Any], prod_trust_store_env_module: None
) -> compiler.CompiledRulePack:
    """The REAL production-signature-verified seq-18 pack — the currently
    active baseline this fold's transplant is measured against."""
    verified = verify_rule_pack(
        seq18_signed, trust_store=StaticTrustStore.from_env(), observed_at=OBSERVED_AT
    )
    return compiler.build_compiled_pack(verified.pack)


@pytest.fixture(scope="module")
def report_18(seq18_verified_compiled: compiler.CompiledRulePack) -> dict[str, Any]:
    return _offline_report_for(seq18_verified_compiled, label="rulepack-prod-018.signed.json")


@pytest.fixture(scope="module")
def report_19(seq19_compiled: compiler.CompiledRulePack) -> dict[str, Any]:
    return _offline_report_for(seq19_compiled, label="rulepack-prod-019.source.json (unsigned)")


class TestGoldReplayDriverOffline:
    """Both sides re-derived live, at test time, against the REAL evaluator
    — never a hardcoded baseline number — so a drift in either pack shows up
    here rather than in a stale magic constant. seq-18's side is verified
    through its real production signature; seq-19's cannot be (see the
    module docstring), so it goes through the placeholder-envelope path.

    Ground truth (``2026-09-05-consuls-ground-visaoracle-engine.md`` Q4,
    independently re-run by the refuter) measured seq-18 at ``matches=5/20``
    with personas #3/#4/#12/#15/#18 matching and #6/#7 divergent among the
    other 15. Re-running that measurement here (``report_18``) is this
    test's own sanity check on its re-derivation, not an assumed constant.

    What this fold actually changes, verified: persona #7's manufactured
    ``E31B``/``E31D`` candidates (the fail-open consequence Q3's diff
    explains) are GONE on seq-19 — but persona #7 still shows as
    "divergent" in the strict field-comparison sense, because its OWN
    ``expected_candidates=("E31",)`` fixture value is a generic label that
    was never going to match any real product code, on ANY pack, repaired
    or not; that is a pre-existing gold-fixture staleness this fold does not
    touch. Persona #6's divergence is unrelated to E31 entirely — its own
    reason is ``MINOR_GUARDIAN_PRIVACY_REVIEW``, a minor-guardian privacy
    gate — and is BYTE-IDENTICAL before and after this fold, proving the
    transplant did not touch it. The ground-truth report's framing of #6/#7
    as "the E31 fail-open personas" is directionally right about #7's root
    cause but imprecise about #6's; this refinement is this fold's own
    finding, carried into the PR body.
    """

    def test_seq18_baseline_reproduces_the_ground_truth_measurement(
        self, report_18: dict[str, Any]
    ) -> None:
        summary = report_18["summary"]
        assert (summary["personas_match"], summary["personas_total"]) == (5, 20)
        matching = {row["persona_id"] for row in report_18["personas"] if not row["divergence"]}
        assert matching == {3, 4, 12, 15, 18}

    def test_persona_7_manufactured_e31_candidates_are_gone_on_seq19(
        self, report_18: dict[str, Any], report_19: dict[str, Any]
    ) -> None:
        assert PERSONAS[6].id == 7
        by_id_18 = {row["persona_id"]: row for row in report_18["personas"]}
        by_id_19 = {row["persona_id"]: row for row in report_19["personas"]}
        actual_18 = by_id_18[7]["actual"]["candidate_products"]
        actual_19 = by_id_19[7]["actual"]["candidate_products"]
        assert {"E31B", "E31D"} <= set(actual_18), "seq-18 must still show the manufactured offers"
        assert not {"E31B", "E31D"} & set(actual_19), actual_19
        # The persona still "diverges" in the strict sense — its own
        # `expected_candidates=("E31",)` never matches a real product code,
        # on either pack — but that residual mismatch is the SAME shape on
        # both sides, not a new one this fold introduced.
        assert by_id_18[7]["divergence"] and by_id_19[7]["divergence"]
        fields_18 = {d["field"] for d in by_id_18[7]["differences"]}
        fields_19 = {d["field"] for d in by_id_19[7]["differences"]}
        assert fields_18 == fields_19 == {"candidate_products"}

    def test_persona_6_divergence_is_unrelated_and_untouched_by_this_fold(
        self, report_18: dict[str, Any], report_19: dict[str, Any]
    ) -> None:
        assert PERSONAS[5].id == 6
        by_id_18 = {row["persona_id"]: row for row in report_18["personas"]}
        by_id_19 = {row["persona_id"]: row for row in report_19["personas"]}

        def canon(differences: list[dict[str, Any]]) -> str:
            return json.dumps(differences, sort_keys=True)

        assert canon(by_id_18[6]["differences"]) == canon(by_id_19[6]["differences"])
        codes = {d["field"] for d in by_id_18[6]["differences"]}
        assert codes == {"candidate_products", "review_reason_codes", "state"}
        review_codes = next(
            d for d in by_id_18[6]["differences"] if d["field"] == "review_reason_codes"
        )
        assert review_codes["actual"] == ["MINOR_GUARDIAN_PRIVACY_REVIEW"]

    def test_match_set_and_count_are_unchanged_end_to_end(
        self, report_18: dict[str, Any], report_19: dict[str, Any]
    ) -> None:
        """The FLOOR: this fold's own field-comparison match count neither
        regresses nor improves (both sides' remaining 15 divergences are
        driven by facts this fold does not touch — missing evidence facts
        the legacy 20-persona corpus never supplies, per Q4). The real
        behavioral improvement (persona #7's manufactured offers) is
        asserted above at the field level, which is the falsifiable claim;
        this test pins that nothing ELSE moved as a side effect."""
        matching_18 = {row["persona_id"] for row in report_18["personas"] if not row["divergence"]}
        matching_19 = {row["persona_id"] for row in report_19["personas"] if not row["divergence"]}
        assert matching_19 == matching_18
        assert report_19["summary"]["personas_match"] == report_18["summary"]["personas_match"]
