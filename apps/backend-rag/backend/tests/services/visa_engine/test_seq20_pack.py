"""Gates for seq-20 (``rulepack-prod-020.source.json``): the decisiveness fold.

Ground: ``research/visa/2026-09-06-visa-oracle-decisiveness-investigation.md``
§2.3 (the three pack-content defects), §4 "PR-1" (the five edits, by rule id)
and §5 Rulings (owner decisions 1, 2 and 5, all RULED 2026-09-06). See
``fold_pack_seq20.py``'s docstring for what each edit is and why.

seq-20 is NOT SIGNED and NOT ACTIVATED by anything in this module or in
``fold_pack_seq20.py`` — signing is the owner's offline ceremony
(``sign_pack.py``, an operator-supplied Ed25519 key). Every witness here that
needs a compiled pack therefore builds one with
``compile_pack.wrap_as_unsigned_pack`` (a placeholder envelope, never a trust
claim) instead of going through
``gold_replay_driver.select_highest_repository_pack``/``verify_rule_pack``,
which are pinned to the real production public key and would refuse an
unsigned ``environment: PRODUCTION`` payload unconditionally. That is a disk
fact, not a choice made here: ``gold_coverage_eval._evaluate`` and
``gold_replay_driver.replay_offline_decisions`` both hardcode
``PACKS_DIR``/``_repository_trust_store()`` with no override, so neither CLI
can be pointed at an unsigned candidate pack at all.

Every behavioural witness below is stated TWICE — guilt (the defect is gone)
and innocence (the legitimate outcome the same rule still produces) — because
each of these five edits either removes a gate or widens a bound, and a
one-sided witness cannot tell "the defect is fixed" from "the rule stopped
working".
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
from backend.scripts.visa_engine.fold_pack_seq20 import (
    BRIDGING_RULE_IDS,
    EDITED_RULE_IDS,
    NEW_RULE_ID,
    NEW_RULE_PRODUCT_CODES,
    REMOVED_RULE_IDS,
    RETIRED_RULE_SUPPORT_TWIN,
    SEQ19_PAYLOAD_SHA256,
    SPONSOR_STATUS_NO_EFFECT_RULE_IDS,
    STAY_DAY_CAP_EXEMPT_RULE_IDS,
    STAY_DAY_CAPS,
    _rule_pack_id,
    fold,
)
from backend.scripts.visa_engine.gold_replay_driver import (
    _offline_identity_provider,
    build_persona_request,
)
from backend.services.visa_engine import compiler, evaluate_path, evaluator
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import DecisionState, RulePackPayload
from backend.tests.services.visa_engine.gold_replay import _decision_actual
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ19_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-019.source.json"
_SEQ19_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-019.signed.json"
_SEQ20_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-020.source.json"
_GOLD_COVERAGE_CORPUS = Path(__file__).resolve().parent / "gold_coverage" / "personas"

pytestmark = pytest.mark.skipif(
    not _SEQ20_SOURCE_PATH.exists(),
    reason="rulepack-prod-020.source.json does not exist on disk — run "
    "`PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq20`",
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

#: After seq-19's ``signed_at`` (2026-09-05T20:48:52Z), before this fold's own
#: ``created_at`` — never real wall clock.
OBSERVED_AT = datetime(2026, 9, 6, 0, 30, 0, tzinfo=timezone.utc)

#: Pinned instant for every evaluator call: at/after the new rule's
#: ``valid_period.from`` (2026-09-06T00:00:00Z) and inside the pack's
#: OFFICIAL_PORTAL freshness window (boundary 2026-10-01T13:18:00Z — the
#: 32-day policy on sources verified 2026-08-30T13:18:00Z). Never
#: ``datetime.now()``: a wall-clock evaluation against a freshness-windowed
#: pack is a clock bomb (see ``test_seq18_freshness_window.py``).
AS_OF = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _nodes(node: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        out.append(node)
        for value in node.values():
            out.extend(_nodes(value))
    elif isinstance(node, list):
        for value in node:
            out.extend(_nodes(value))
    return out


@pytest.fixture(scope="module")
def seq19_source() -> dict[str, Any]:
    return _read_json(_SEQ19_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq19_signed() -> dict[str, Any]:
    return _read_json(_SEQ19_SIGNED_PATH)


@pytest.fixture(scope="module")
def seq20_source() -> dict[str, Any]:
    return _read_json(_SEQ20_SOURCE_PATH)


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


@pytest.fixture(scope="module")
def seq19_compiled() -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(_SEQ19_SOURCE_PATH)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def seq20_compiled() -> compiler.CompiledRulePack:
    """A CompiledRulePack built from 020 through a PLACEHOLDER envelope — never
    a trust claim (see ``wrap_as_unsigned_pack``'s own docstring). 020 is
    unsigned by design; this is the only way any witness here can exercise the
    real evaluator against it before the owner signs it."""
    payload = load_rule_pack_payload(_SEQ20_SOURCE_PATH)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


# ---------------------------------------------------------------------------
# Fold integrity
# ---------------------------------------------------------------------------


class TestFoldIntegrity:
    def test_fold_is_deterministic_and_matches_disk(
        self,
        seq19_source: dict[str, Any],
        seq19_signed: dict[str, Any],
        seq20_source: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        assert fold(seq19_source, seq19_signed, observed_at=OBSERVED_AT) == seq20_source

    def test_fold_is_byte_invariant_across_two_runs(
        self,
        seq19_source: dict[str, Any],
        seq19_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        first = fold(seq19_source, seq19_signed, observed_at=OBSERVED_AT)
        second = fold(seq19_source, seq19_signed, observed_at=OBSERVED_AT)
        assert canonicalize_json(first) == canonicalize_json(second)

    def test_compile_rule_pack_reports_ok(self) -> None:
        payload = load_rule_pack_payload(_SEQ20_SOURCE_PATH)
        report = compile_rule_pack(wrap_as_unsigned_pack(payload))
        assert report.ok, f"seq-20 does not compile clean: {report}"

    def test_source_validates_against_the_payload_model(self, seq20_source: dict[str, Any]) -> None:
        assert RulePackPayload.model_validate(seq20_source).sequence == 20


# ---------------------------------------------------------------------------
# Identity + chain
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_sequence_is_20(self, seq20_source: dict[str, Any]) -> None:
        assert seq20_source["sequence"] == 20

    def test_rule_pack_id_follows_the_uuid5_convention(self, seq20_source: dict[str, Any]) -> None:
        assert seq20_source["rule_pack_id"] == str(_rule_pack_id(20))

    def test_chain_anchor_is_the_measured_seq19_digest(
        self, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        """The anchor is re-derived from the seq-19 bytes on disk, never taken
        from the constant alone — the constant is what the fold pins, and this
        is the independent check that it names the real payload."""
        import hashlib

        recomputed = hashlib.sha256(canonicalize_json(seq19_source)).hexdigest()
        assert recomputed == SEQ19_PAYLOAD_SHA256
        assert seq20_source["previous_payload_sha256"] == SEQ19_PAYLOAD_SHA256

    def test_chain_anchor_is_also_the_signed_artifacts_own_digest(
        self, seq19_signed: dict[str, Any]
    ) -> None:
        assert seq19_signed["payload_sha256"] == SEQ19_PAYLOAD_SHA256

    def test_payload_digest_survives_reformatting_of_the_file(
        self, seq20_source: dict[str, Any]
    ) -> None:
        """The pack's identity is JCS over the PARSED document, never the file
        bytes, so the repo's prettier gate can reshape the file freely — this
        pins that invariant instead of leaving it to be rediscovered. The
        constant below is the digest the owner will sign and the digest
        `previous_payload_sha256` of seq-21 will have to name; it was measured
        BEFORE the prettier pass and re-measured after it, unchanged. A future
        reformat that moved it would mean the reformatter edited content."""
        import hashlib

        digest = hashlib.sha256(canonicalize_json(seq20_source)).hexdigest()
        assert digest == "df02287b7fc8f572a9e6674fdf3445a2131c428e8a1492ab8a388dee5bf01a4d"

    def test_version_is_the_fold_date(self, seq20_source: dict[str, Any]) -> None:
        assert seq20_source["version"] == "2026.9.6"

    def test_rollback_of_payload_sha256_is_null(self, seq20_source: dict[str, Any]) -> None:
        assert seq20_source["rollback_of_payload_sha256"] is None

    def test_non_identity_metadata_is_untouched(
        self, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        for key in (
            "environment",
            "jurisdiction",
            "decision_domain",
            "hit_policy",
            "valid_period",
            "engine_min_version",
            "engine_max_version",
            "engine_contract_version",
            "products",
            "source_records",
        ):
            assert _canon(seq20_source[key]) == _canon(seq19_source[key]), key


class TestSignatureAndChain:
    def test_signed_seq19_bundle_verifies_against_the_pinned_trust_store(
        self, seq19_signed: dict[str, Any], prod_trust_store_env: None
    ) -> None:
        verified = verify_rule_pack(
            seq19_signed,
            trust_store=StaticTrustStore.from_env(),
            observed_at=OBSERVED_AT,
        )
        assert verified.pack.payload.sequence == 19
        assert verified.payload_sha256.hex() == SEQ19_PAYLOAD_SHA256


# ---------------------------------------------------------------------------
# The declared rule-set delta, exactly
# ---------------------------------------------------------------------------


class TestRuleSetDelta:
    def test_rule_delta_is_exactly_the_declared_one(
        self, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        r19 = {r["rule_id"]: r for r in seq19_source["rules"]}
        r20 = {r["rule_id"]: r for r in seq20_source["rules"]}
        assert set(r19) - set(r20) == set(REMOVED_RULE_IDS)
        assert set(r20) - set(r19) == {NEW_RULE_ID}
        drifted = {rid for rid in r20 if rid in r19 and _canon(r20[rid]) != _canon(r19[rid])}
        assert drifted == set(EDITED_RULE_IDS)

    def test_rule_count_is_conserved_minus_one_plus_one(
        self, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        assert len(seq19_source["rules"]) == 109
        assert len(seq20_source["rules"]) == 109

    def test_the_edit_set_is_the_twenty_two_caps_plus_eight_sponsors_plus_four_bridging(
        self,
    ) -> None:
        assert len(STAY_DAY_CAPS) == 22
        assert len(SPONSOR_STATUS_NO_EFFECT_RULE_IDS) == 8
        assert len(BRIDGING_RULE_IDS) == 4
        assert len(set(EDITED_RULE_IDS)) == 34


# ---------------------------------------------------------------------------
# Edit 1 — stay-day caps
# ---------------------------------------------------------------------------


def _stay_days_bounds(rule: dict[str, Any]) -> list[int]:
    return [
        node["value"]
        for node in _nodes(rule["when"])
        if node.get("fact") == "intent.stay_days" and node.get("op") == "lte"
    ]


class TestStayDayCaps:
    @pytest.mark.parametrize("rule_id", sorted(STAY_DAY_CAPS))
    def test_each_cap_holds_its_declared_new_bound(
        self, rule_id: str, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        old, new = STAY_DAY_CAPS[rule_id]
        r19 = {r["rule_id"]: r for r in seq19_source["rules"]}[rule_id]
        r20 = {r["rule_id"]: r for r in seq20_source["rules"]}[rule_id]
        assert _stay_days_bounds(r19) == [old]
        assert _stay_days_bounds(r20) == [new]

    def test_a1_bvk_keeps_its_non_extendable_thirty_days(
        self, seq20_source: dict[str, Any]
    ) -> None:
        """A1 is the visa-exemption entry: its 30 days are not extendable, so
        its cap already IS the lawful total. Named exempt, not forgotten."""
        assert STAY_DAY_CAP_EXEMPT_RULE_IDS == frozenset({"el.a1.tourism"})
        r20 = {r["rule_id"]: r for r in seq20_source["rules"]}["el.a1.tourism"]
        assert _stay_days_bounds(r20) == [30]

    def test_no_rule_carries_an_unaccounted_stay_day_bound(
        self, seq20_source: dict[str, Any]
    ) -> None:
        carriers = {r["rule_id"] for r in seq20_source["rules"] if _stay_days_bounds(r)}
        assert carriers == set(STAY_DAY_CAPS) | STAY_DAY_CAP_EXEMPT_RULE_IDS

    def test_the_document_siblings_moved_with_their_covering_rule(
        self, seq20_source: dict[str, Any]
    ) -> None:
        """The trap §4 edit 1 names: leaving a ``*-passport-validity`` or
        ``*-funds-usd-*`` sibling at the old bound does not block support, it
        silently drops the document checklist for a long-stay applicant."""
        r20 = {r["rule_id"]: r for r in seq20_source["rules"]}
        for family, bound in (("d1", 180), ("d2", 180), ("d12", 360)):
            siblings = [
                rid
                for rid in r20
                if rid.startswith(f"el.{family}-") and _stay_days_bounds(r20[rid])
            ]
            assert len(siblings) == 6, (family, siblings)
            for rid in siblings:
                assert _stay_days_bounds(r20[rid]) == [bound], rid


# ---------------------------------------------------------------------------
# Edit 2 — the duplicate E33G review rule
# ---------------------------------------------------------------------------


class TestE33GReviewRetirement:
    def test_the_retired_rule_was_a_byte_copy_of_its_support_twin(
        self, seq19_source: dict[str, Any]
    ) -> None:
        """The justification, restated against the base pack: the review rule
        fired on the product's own success condition."""
        r19 = {r["rule_id"]: r for r in seq19_source["rules"]}
        for retired_id, twin_id in RETIRED_RULE_SUPPORT_TWIN.items():
            assert _canon(r19[retired_id]["when"]) == _canon(r19[twin_id]["when"])

    def test_it_is_gone_from_seq20(self, seq20_source: dict[str, Any]) -> None:
        assert REMOVED_RULE_IDS == frozenset({"review.e33g.income-evidence"})
        assert not [r for r in seq20_source["rules"] if r["rule_id"] in REMOVED_RULE_IDS]

    def test_its_support_twin_survives_untouched(
        self, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        r19 = {r["rule_id"]: r for r in seq19_source["rules"]}
        r20 = {r["rule_id"]: r for r in seq20_source["rules"]}
        assert _canon(r20["el.e33g.remote-work"]) == _canon(r19["el.e33g.remote-work"])


# ---------------------------------------------------------------------------
# Edit 3 — the ITAS-sponsor gates
# ---------------------------------------------------------------------------


class TestSponsorStatusGates:
    @pytest.mark.parametrize("rule_id", SPONSOR_STATUS_NO_EFFECT_RULE_IDS)
    def test_each_named_rule_is_now_no_effect(
        self, rule_id: str, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        r19 = {r["rule_id"]: r for r in seq19_source["rules"]}[rule_id]
        r20 = {r["rule_id"]: r for r in seq20_source["rules"]}[rule_id]
        assert r19["on_unknown"] == "NEEDS_INPUT"
        assert r20["on_unknown"] == "NO_EFFECT"
        assert r20["effect"]["type"] == "SUPPORT", "NO_EFFECT is only fail-closed on SUPPORT"
        assert _canon(r20["when"]) == _canon(r19["when"]), "only on_unknown may move"

    def test_no_reader_of_the_fact_still_blocks_on_it(self, seq20_source: dict[str, Any]) -> None:
        blocking = [
            r["rule_id"]
            for r in seq20_source["rules"]
            if "family.sponsor_status_code" in r["required_facts"]
            and r["on_unknown"] != "NO_EFFECT"
        ]
        assert blocking == []


# ---------------------------------------------------------------------------
# Edit 4 — BRIDGING's unstated request
# ---------------------------------------------------------------------------


class TestBridgingPremise:
    @pytest.mark.parametrize("rule_id", BRIDGING_RULE_IDS)
    def test_each_bridging_rule_now_states_its_premise(
        self, rule_id: str, seq20_source: dict[str, Any]
    ) -> None:
        rule = {r["rule_id"]: r for r in seq20_source["rules"]}[rule_id]
        presence = [
            n
            for n in _nodes(rule["when"])
            if n.get("fact") == "intent.requested_product_code" and n.get("op") == "known"
        ]
        neq = [
            n
            for n in _nodes(rule["when"])
            if n.get("fact") == "intent.requested_product_code" and n.get("op") == "neq"
        ]
        assert len(presence) == 1, "the premise must be stated exactly once"
        assert neq, "the original neq guard must survive"
        assert rule["effect"]["type"] == "SUPPORT"

    def test_no_other_support_rule_is_guarded_on_a_bare_neq(
        self, seq20_source: dict[str, Any]
    ) -> None:
        """A SUPPORT rule that reads ``requested_product_code`` with ``neq``
        and no presence test can manufacture support from an unstated
        request — §6 R2's measured fail-open."""
        offenders = []
        for rule in seq20_source["rules"]:
            if rule["effect"]["type"] != "SUPPORT":
                continue
            nodes = _nodes(rule["when"])
            has_neq = any(
                n.get("fact") == "intent.requested_product_code" and n.get("op") == "neq"
                for n in nodes
            )
            has_known = any(
                n.get("fact") == "intent.requested_product_code" and n.get("op") == "known"
                for n in nodes
            )
            if has_neq and not has_known:
                offenders.append(rule["rule_id"])
        assert offenders == []


# ---------------------------------------------------------------------------
# Edit 5 — CL-D2-01 compiled
# ---------------------------------------------------------------------------


class TestLocalCompensationRule:
    def test_the_new_rule_has_the_declared_shape(self, seq20_source: dict[str, Any]) -> None:
        rule = {r["rule_id"]: r for r in seq20_source["rules"]}[NEW_RULE_ID]
        assert rule["stage"] == "HARD_FILTER"
        assert rule["effect"] == {
            "type": "EXCLUDE",
            "reason_code": "BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED",
        }
        assert rule["on_unknown"] == "NEEDS_INPUT"
        assert rule["safety_critical"] is True
        assert sorted(rule["required_facts"]) == [
            "intent.purposes",
            "work.indonesia_source_compensation",
        ]

    def test_it_is_scoped_to_c2_d1_d2_only(self, seq20_source: dict[str, Any]) -> None:
        versions = {p["product_code"]: p["product_version_id"] for p in seq20_source["products"]}
        rule = {r["rule_id"]: r for r in seq20_source["rules"]}[NEW_RULE_ID]
        assert [versions[code] for code in NEW_RULE_PRODUCT_CODES] == rule["product_version_ids"]
        assert NEW_RULE_PRODUCT_CODES == ("C2", "D1", "D2")

    def test_it_cites_the_rule_the_claim_ledger_says_it_backs(
        self, seq20_source: dict[str, Any]
    ) -> None:
        """CL-D2-01's ``Backs:`` line names ``el.d2-multi-entry-support``; the
        new rule compiles the same claim, so it inherits the same citations
        rather than acquiring hand-typed ones."""
        rules = {r["rule_id"]: r for r in seq20_source["rules"]}
        assert (
            rules[NEW_RULE_ID]["source_refs"] == rules["el.d2-multi-entry-support"]["source_refs"]
        )

    def test_it_does_not_shorten_the_safety_critical_freshness_horizon(
        self, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        """``_apply_safety_critical_source_hold`` unions the ``source_refs`` of
        every ACTIVE safety-critical rule, fired or not, and abstains globally
        if any is not CURRENT. A new safety-critical rule citing a
        shorter-lived source would therefore make the WHOLE engine start
        returning HUMAN_REVIEW_REQUIRED sooner — invisible until the day it
        fires."""
        from backend.scripts.visa_engine.fold_pack_seq20 import _freshness_horizon

        sources = {s["source_record_id"]: s for s in seq20_source["source_records"]}
        before = min(
            _freshness_horizon(sources[ref])
            for rule in seq19_source["rules"]
            if rule["safety_critical"]
            for ref in rule["source_refs"]
        )
        after = min(
            _freshness_horizon(sources[ref])
            for rule in seq20_source["rules"]
            if rule["safety_critical"]
            for ref in rule["source_refs"]
        )
        assert after == before


# ---------------------------------------------------------------------------
# Fold guards: innocence (the real payload passes) then guilt (each guard
# rejects what it claims to). `pytest.raises` is visible in every test body,
# per this repo's anti-reward-hacking lint convention.
# ---------------------------------------------------------------------------


class TestFoldGuardsGuilt:
    def test_a_new_stay_day_bound_nobody_decided_about_is_refused(
        self, seq19_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import _assert_stay_day_cap_census

        _assert_stay_day_cap_census(seq19_source)  # innocence
        mutated = json.loads(json.dumps(seq19_source))
        mutated["rules"].append(
            {
                "rule_id": "el.some-future-product",
                "when": {"op": "lte", "fact": "intent.stay_days", "value": 45},
            }
        )
        with pytest.raises(SystemExit):
            _assert_stay_day_cap_census(mutated)

    def test_retiring_a_review_rule_that_grew_its_own_condition_is_refused(
        self, seq19_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import (
            _assert_retired_rule_is_a_copy_of_its_support_twin,
        )

        rules = {r["rule_id"]: r for r in json.loads(json.dumps(seq19_source))["rules"]}
        _assert_retired_rule_is_a_copy_of_its_support_twin(rules)  # innocence
        rules["review.e33g.income-evidence"]["when"]["args"].append(
            {"op": "lte", "fact": "intent.stay_days", "value": 180}
        )
        with pytest.raises(SystemExit):
            _assert_retired_rule_is_a_copy_of_its_support_twin(rules)

    def test_a_ninth_blocking_sponsor_reader_is_refused(self, seq19_source: dict[str, Any]) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import _assert_sponsor_status_census

        _assert_sponsor_status_census(seq19_source)  # innocence
        mutated = json.loads(json.dumps(seq19_source))
        for rule in mutated["rules"]:
            if rule["rule_id"] == "el.e31j-dependency-age":
                rule["on_unknown"] = "NEEDS_INPUT"
        with pytest.raises(SystemExit):
            _assert_sponsor_status_census(mutated)

    def test_a_fifth_support_rule_guarded_on_neq_is_refused(
        self, seq19_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import _assert_bridging_census

        _assert_bridging_census(seq19_source)  # innocence
        mutated = json.loads(json.dumps(seq19_source))
        mutated["rules"].append(
            {
                "rule_id": "el.some-future-support",
                "effect": {"type": "SUPPORT", "reason_code": "X"},
                "when": {
                    "op": "all",
                    "args": [
                        {
                            "op": "neq",
                            "fact": "intent.requested_product_code",
                            "value": "BRIDGING",
                        }
                    ],
                },
            }
        )
        with pytest.raises(SystemExit):
            _assert_bridging_census(mutated)

    def test_a_shorter_lived_citation_on_the_new_rule_is_refused(
        self, seq19_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import (
            _assert_new_rule_shortens_no_freshness_horizon,
            build_new_rule,
        )

        real = build_new_rule(seq19_source)
        _assert_new_rule_shortens_no_freshness_horizon(
            seq19_source, list(real["source_refs"])
        )  # innocence
        mutated = json.loads(json.dumps(seq19_source))
        stale_ref = real["source_refs"][0]
        for source in mutated["source_records"]:
            if source["source_record_id"] == stale_ref:
                source["verified_at"] = "2026-01-01T00:00:00Z"
        with pytest.raises(SystemExit):
            _assert_new_rule_shortens_no_freshness_horizon(mutated, [stale_ref])

    def test_the_fold_refuses_an_anchor_that_is_not_the_activated_payload(
        self,
        seq19_source: dict[str, Any],
        seq19_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        tampered = json.loads(json.dumps(seq19_source))
        tampered["created_by"] = "somebody else"
        with pytest.raises(SystemExit):
            fold(tampered, seq19_signed, observed_at=OBSERVED_AT)

    def test_the_fold_refuses_without_a_trust_store(
        self,
        seq19_source: dict[str, Any],
        seq19_signed: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", raising=False)
        with pytest.raises(SystemExit):
            fold(seq19_source, seq19_signed, observed_at=OBSERVED_AT)

    def test_the_output_may_not_look_signed(self, tmp_path: Path) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import (
            _assert_output_does_not_collide_with_inputs,
        )

        _assert_output_does_not_collide_with_inputs(
            tmp_path / "out.source.json", {"--seq19-source": _SEQ19_SOURCE_PATH}
        )  # innocence
        with pytest.raises(SystemExit):
            _assert_output_does_not_collide_with_inputs(
                tmp_path / "out.signed.json", {"--seq19-source": _SEQ19_SOURCE_PATH}
            )

    def test_the_output_may_not_overwrite_the_signed_anchor(self, tmp_path: Path) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import (
            _assert_output_does_not_collide_with_inputs,
        )

        with pytest.raises(SystemExit):
            _assert_output_does_not_collide_with_inputs(
                _SEQ19_SOURCE_PATH, {"--seq19-source": _SEQ19_SOURCE_PATH}
            )

    def test_value_guard_rejects_a_wrong_sequence(self, seq20_source: dict[str, Any]) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import (
            assert_changed_fields_hold_their_expected_values,
            build_new_rule,
        )

        after = json.loads(json.dumps(seq20_source))
        new_rule = {r["rule_id"]: r for r in after["rules"]}[NEW_RULE_ID]
        assert_changed_fields_hold_their_expected_values(
            after, expected_new_rule=new_rule
        )  # innocence
        after["sequence"] = 99
        with pytest.raises(SystemExit):
            assert_changed_fields_hold_their_expected_values(after, expected_new_rule=new_rule)
        assert build_new_rule(seq20_source)["rule_id"] == NEW_RULE_ID

    def test_change_guard_rejects_an_untouched_rule_that_moved(
        self, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import assert_only_expected_changes

        after = json.loads(json.dumps(seq20_source))
        assert_only_expected_changes(seq19_source, after)  # innocence
        for rule in after["rules"]:
            if rule["rule_id"] == "el.a1.tourism":
                rule["priority"] = 99
        with pytest.raises(SystemExit):
            assert_only_expected_changes(seq19_source, after)

    def test_change_guard_rejects_a_second_inserted_rule(
        self, seq19_source: dict[str, Any], seq20_source: dict[str, Any]
    ) -> None:
        from backend.scripts.visa_engine.fold_pack_seq20 import assert_only_expected_changes

        after = json.loads(json.dumps(seq20_source))
        after["rules"].append({"rule_id": "el.smuggled-in", "when": {}})
        with pytest.raises(SystemExit):
            assert_only_expected_changes(seq19_source, after)


# ---------------------------------------------------------------------------
# Behavioural witnesses (the real evaluator on a CompiledRulePack built from
# 020, with 019 as the before-picture) — guilt AND innocence for every edit.
# ---------------------------------------------------------------------------


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


#: A COMPLETE-fact baseline: every fact any rule in the pack reads is KNOWN,
#: with a neutral, definitely-non-matching value. This is the investigation's
#: own persona method (§3, ``scratchpad/inv/d4/run_personas.py``) and it exists
#: so that a ``NEEDS_INPUT`` in any witness below cannot be an artifact of a
#: gap the interview happens not to fill: with no unknowns left, the only
#: reason a product can block is the rule under test. Values are synthetic —
#: no client data, no real person.
_COMPLETE: dict[str, dict[str, Any]] = {
    "person.nationalities": _known(["DE"]),
    "person.birth_date": _known("1990-05-02"),
    "immigration.current_status_code": _known("NO_STAY_PERMIT"),
    "immigration.currently_in_indonesia": _known(False),
    "immigration.overstay_days": _known(0),
    "immigration.violation_history": _known([]),
    "family.relation_to_sponsor": _known("OTHER"),
    "family.sponsor_nationalities": _known(["FR"]),
    "family.sponsor_status_code": _known("NONE"),
    "family.sponsor_confirmed": _known(False),
    "family.marriage_registered": _known(False),
    "family.stepchild_marriage_certificate_confirmed": _known(False),
    "family.stepchild_birth_certificate_confirmed": _known(False),
    "study.level": _known("OTHER"),
    "study.admission_confirmed": _known(False),
    "study.sponsor_confirmed": _known(False),
    "sponsor.type": _known("NONE"),
    "secondhome.bank_deposit_usd": _known(0),
    "secondhome.bank_deposit_at_state_bank": _known(False),
    "secondhome.bank_deposit_in_own_name": _known(False),
    "secondhome.qualifying_property_value_usd": _known(0),
    "secondhome.passive_monthly_income_usd": _known(0),
    "investment.pt_pma_committed": _known(False),
    "investment.investment_capital_idr": _known(0),
    "investment.paid_up_capital_idr": _known(0),
    "investment.proposed_role": _known("NO_OPERATIONAL_ROLE"),
    "work.employer_is_indonesian_entity": _known(False),
    "work.serves_indonesian_clients": _known(False),
    "work.indonesia_source_compensation": _known(False),
    "work.indonesian_work_sponsor_confirmed": _known(False),
    "process.application_channel": _known("OFFSHORE"),
    "process.wants_onshore_conversion": _known(False),
    "intent.desired_entry_date": _known("2026-10-15"),
    "intent.entry_pattern": _known("SINGLE"),
}


def _complete(**overrides: dict[str, Any]) -> dict[str, dict[str, Any]]:
    facts = dict(_COMPLETE)
    facts.update(overrides)
    return facts


def _evaluate(
    compiled: compiler.CompiledRulePack, overrides: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    persona = Persona(
        id=0, label="seq20-witness", overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    request = build_persona_request(persona)
    facts = request.applicant_facts()
    decision = evaluator.evaluate(
        facts,
        compiled,
        effective_at=AS_OF,
        observed_at=AS_OF,
        identity_provider=_offline_identity_provider,
    )
    decision = evaluate_path.apply_public_policy_adapters(decision, facts, compiled)
    return _decision_actual(decision)


#: The owner's own persona shape (§3 row #14): a 121-day multi-entry business
#: trip with a confirmed local sponsor. Told "no path" by seq-19.
_BUSINESS_121D = _complete(
    **{
        "intent.purposes": _known(["BUSINESS_MEETINGS"]),
        "intent.stay_days": _known(121),
        "intent.entry_pattern": _known("MULTIPLE"),
        "family.sponsor_confirmed": _known(True),
    }
)

_REMOTE_CLEAN = _complete(
    **{
        "intent.purposes": _known(["REMOTE_WORK"]),
        "intent.stay_days": _known(180),
        "person.nationalities": _known(["AU"]),
    }
)

#: §3 row #23: the spouse of an ITAS holder, whose status code the browser can
#: never certify.
_SPOUSE_OF_ITAS = _complete(
    **{
        "intent.purposes": _known(["FAMILY"]),
        "intent.stay_days": _known(365),
        "family.relation_to_sponsor": _known("SPOUSE"),
        "family.marriage_registered": _known(True),
        "family.sponsor_confirmed": _known(True),
        "family.sponsor_status_code": {"status": "UNKNOWN", "reason": "UNVERIFIED"},
    }
)


class TestStayDayCapWitnesses:
    def test_guilt_the_121_day_business_trip_had_no_path_and_now_has_one(
        self, seq19_compiled: compiler.CompiledRulePack, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        before = _evaluate(seq19_compiled, _BUSINESS_121D)
        after = _evaluate(seq20_compiled, _BUSINESS_121D)
        assert before["state"] == "NO_SUPPORTED_PATH"
        assert after["state"] == "SUPPORTED_CANDIDATES"
        assert {"C2", "D1", "D2"} <= set(after["candidates"])

    def test_innocence_a_stay_beyond_the_lawful_total_still_has_no_path(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        """The cap moved to the lawful extendable total — it was not removed.
        A 400-day visit request must still be refused."""
        after = _evaluate(seq20_compiled, {**_BUSINESS_121D, "intent.stay_days": _known(400)})
        assert after["state"] == "NO_SUPPORTED_PATH"
        assert after["candidates"] == []

    def test_innocence_a_short_tourist_keeps_exactly_the_products_seq19_gave(
        self, seq19_compiled: compiler.CompiledRulePack, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        tourist = _complete(
            **{
                "intent.purposes": _known(["TOURISM"]),
                "intent.stay_days": _known(21),
            }
        )
        assert (
            _evaluate(seq19_compiled, tourist)["candidates"]
            == _evaluate(seq20_compiled, tourist)["candidates"]
        )


class TestE33GWitnesses:
    def test_guilt_a_clean_remote_worker_is_recommended_instead_of_reviewed(
        self, seq19_compiled: compiler.CompiledRulePack, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        before = _evaluate(seq19_compiled, _REMOTE_CLEAN)
        after = _evaluate(seq20_compiled, _REMOTE_CLEAN)
        assert before["state"] == "HUMAN_REVIEW_REQUIRED"
        assert "E33G_INCOME_EVIDENCE_REVIEW" in before["review_reason_codes"]
        assert after["state"] == "SUPPORTED_CANDIDATES"
        assert "E33G" in after["candidates"]

    def test_innocence_serving_indonesian_clients_still_goes_to_a_human(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        """``review.e33g.local-market-activity`` is the sibling with a REAL
        discriminating condition — §7.3 keeps it, and this fold must not have
        taken it down with its duplicate."""
        after = _evaluate(
            seq20_compiled,
            {**_REMOTE_CLEAN, "work.serves_indonesian_clients": _known(True)},
        )
        assert after["state"] == "HUMAN_REVIEW_REQUIRED"
        assert "E33G" not in after["candidates"]

    def test_innocence_an_indonesian_employer_is_still_barred_from_e33g(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        after = _evaluate(
            seq20_compiled,
            {**_REMOTE_CLEAN, "work.employer_is_indonesian_entity": _known(True)},
        )
        assert "E33G" not in after["candidates"]


class TestSponsorStatusWitnesses:
    def test_guilt_an_uncertifiable_sponsor_status_no_longer_takes_the_decision_down(
        self, seq19_compiled: compiler.CompiledRulePack, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        """The browser can never certify this fact (fact-mapper.ts returns
        UNVERIFIED by design), so seq-19 asked a question nothing can answer."""
        before = _evaluate(seq19_compiled, _SPOUSE_OF_ITAS)
        after = _evaluate(seq20_compiled, _SPOUSE_OF_ITAS)
        assert "family.sponsor_status_code" in before["missing_facts"]
        assert "family.sponsor_status_code" not in after["missing_facts"]

    def test_innocence_the_itas_family_products_are_still_not_recommended(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        """NO_EFFECT is fail-CLOSED: those routes stay consultation-only, they
        do not become candidates on an unknown sponsor status."""
        after = _evaluate(seq20_compiled, _SPOUSE_OF_ITAS)
        assert not ({"E31B", "E31E", "E31H", "E31J"} & set(after["candidates"]))

    def test_innocence_a_certified_itas_sponsor_still_reaches_e31b(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        after = _evaluate(
            seq20_compiled,
            {**_SPOUSE_OF_ITAS, "family.sponsor_status_code": _known("E23")},
        )
        assert after["state"] == "SUPPORTED_CANDIDATES"
        assert "E31B" in after["candidates"]

    def test_innocence_a_sponsor_status_of_none_still_does_not_reach_e31b(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        after = _evaluate(
            seq20_compiled,
            {**_SPOUSE_OF_ITAS, "family.sponsor_status_code": _known("NONE")},
        )
        assert "E31B" not in after["candidates"]


class TestBridgingWitnesses:
    #: §6 R2's own browser-reachable persona: onshore, holding an E23 stay
    #: permit, category `other`.
    _ONSHORE_OTHER = _complete(
        **{
            "intent.purposes": _known(["OTHER"]),
            "intent.stay_days": _known(60),
            "immigration.currently_in_indonesia": _known(True),
            "immigration.current_status_code": _known("E23"),
            "immigration.current_status_expiry": _known("2026-12-01"),
            "process.application_channel": _known("STATUS_BRIDGING"),
            "intent.requested_product_code": {"status": "UNKNOWN", "reason": "NOT_ASKED"},
        }
    )

    def test_guilt_an_unstated_request_no_longer_blocks_on_a_fact_nothing_supplies(
        self, seq19_compiled: compiler.CompiledRulePack, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        before = _evaluate(seq19_compiled, self._ONSHORE_OTHER)
        after = _evaluate(seq20_compiled, self._ONSHORE_OTHER)
        assert "intent.requested_product_code" in before["missing_facts"]
        assert "intent.requested_product_code" not in after["missing_facts"]

    def test_guilt_bridging_is_never_supported_on_an_unstated_request(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        after = _evaluate(seq20_compiled, self._ONSHORE_OTHER)
        assert "BRIDGING" not in after["candidates"]

    def test_innocence_a_stated_destination_still_reaches_bridging(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        """The premise was made explicit, not made impossible: with a
        destination product actually named, the route still works."""
        after = _evaluate(
            seq20_compiled,
            {**self._ONSHORE_OTHER, "intent.requested_product_code": _known("E23")},
        )
        assert "BRIDGING" in after["candidates"]


class TestLocalCompensationWitnesses:
    def test_guilt_declared_local_compensation_now_excludes_d2(
        self, seq19_compiled: compiler.CompiledRulePack, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        # Taken at 60 days, INSIDE seq-19's own cap, so the before-picture
        # cannot be confused with the stay-day defect this same fold repairs:
        # seq-19 confidently recommends D2 to an applicant who has declared
        # local compensation, with no review reason at all (§4 edit 5's
        # measurement, reproduced here).
        facts = _complete(
            **{
                "intent.purposes": _known(["BUSINESS_MEETINGS"]),
                "intent.stay_days": _known(60),
                "family.sponsor_confirmed": _known(True),
                "work.indonesia_source_compensation": _known(True),
            }
        )
        before = _evaluate(seq19_compiled, facts)
        after = _evaluate(seq20_compiled, facts)
        assert before["state"] == "SUPPORTED_CANDIDATES"
        assert "D2" in before["candidates"]
        assert before["review_reason_codes"] == []
        assert "D2" not in after["candidates"]
        assert "BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED" in after["no_path_reason_codes"]

    def test_innocence_a_business_trip_without_local_compensation_keeps_d2(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        after = _evaluate(seq20_compiled, _BUSINESS_121D)
        assert "D2" in after["candidates"]

    def test_innocence_a_tourist_is_never_asked_about_local_compensation(
        self, seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        """The purpose guard makes the rule definitely FALSE — never UNKNOWN —
        for anyone who did not declare BUSINESS_MEETINGS, so a NEEDS_INPUT
        cannot leak into a branch that has no question for the fact."""
        tourist = _complete(
            **{
                "intent.purposes": _known(["TOURISM"]),
                "intent.stay_days": _known(45),
                "work.indonesia_source_compensation": {
                    "status": "UNKNOWN",
                    "reason": "NOT_ASKED",
                },
            }
        )
        after = _evaluate(seq20_compiled, tourist)
        assert "work.indonesia_source_compensation" not in after["missing_facts"]
        assert after["state"] == "SUPPORTED_CANDIDATES"


# ---------------------------------------------------------------------------
# The floor that would catch a fail-open: every coverage persona is still
# supported for its own product. Same evaluate path as
# `gold_coverage_eval._evaluate`, minus the file-selection/signature step that
# script does not let a caller override (see the module docstring).
# ---------------------------------------------------------------------------


def _coverage_persona_specs() -> list[tuple[str, dict[str, Any]]]:
    return [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(_GOLD_COVERAGE_CORPUS.glob("*.json"))
    ]


class TestGoldCoverageReplay:
    def test_corpus_has_eighteen_personas(self) -> None:
        assert len(_coverage_persona_specs()) == 18

    @pytest.mark.parametrize(
        "name,spec", _coverage_persona_specs(), ids=[n for n, _ in _coverage_persona_specs()]
    )
    def test_persona_is_supported_against_seq20(
        self, name: str, spec: dict[str, Any], seq20_compiled: compiler.CompiledRulePack
    ) -> None:
        actual = _evaluate(seq20_compiled, spec["overrides"])
        expected_candidates = list(spec.get("expected_candidates") or [])
        missing = [c for c in expected_candidates if c not in actual["candidates"]]
        assert actual["state"] == spec["expected_state"], (name, actual)
        assert not missing, (name, missing, actual["candidates"])
