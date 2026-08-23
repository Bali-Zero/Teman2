"""Offline unit coverage for the Visa Oracle G-b gold replay driver."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from backend.scripts.visa_engine import gold_replay_driver as driver
from backend.services.visa_engine import evaluator
from backend.services.visa_engine.api_models import (
    DisclosedReviewFlag,
    VisaOracleEvaluateRequest,
)
from backend.services.visa_engine.models import ApplicantFactsData, Decision
from backend.tests.services.visa_engine import _gold_fixtures as gf
from backend.tests.services.visa_engine.test_evaluator_gold import PERSONAS

_GOLD_AT = gf.GOLD_EFFECTIVE_AT

# The offline clock must sit AFTER every repository pack's signed_at: the
# driver verifies the selected bundle with observed_at=generated_at, and the
# verifier rejects a signed_at in the future beyond its 5-minute tolerance.
# A frozen wall date here is a frozen measurement that silently expires the
# day a newer pack is signed — the seq-11 bundle broke the previous pin
# (2026-08-19T12:00Z) within hours of signing. Deriving the clock from the
# packs themselves keeps the test deterministic per checkout and immune to
# every future pack landing.
_OFFLINE_AT = max(
    datetime.fromisoformat(
        json.loads(path.read_text(encoding="utf-8"))["protected"]["signed_at"].replace(
            "Z", "+00:00"
        )
    )
    for path in driver.PACKS_DIR.glob("*.signed.json")
) + timedelta(hours=1)


def _fixture_decisions() -> tuple[Decision, ...]:
    compiled = gf.build_gold_compiled_pack()
    return tuple(
        evaluator.evaluate(
            driver.build_persona_request(persona).applicant_facts(),
            compiled,
            effective_at=_GOLD_AT,
            observed_at=_GOLD_AT,
        )
        for persona in PERSONAS
    )


def _fixture_report(
    decisions: tuple[Decision, ...],
    *,
    explanations: dict[int, driver.AcceptedExplanation] | None = None,
) -> dict:
    return driver.build_report(
        mode="offline",
        generated_at=_GOLD_AT,
        decisions=decisions,
        pack_source={"kind": "test"},
        explanations=explanations,
    )


def test_all_canonical_personas_map_to_the_real_wire_model() -> None:
    expected_fact_aliases = {
        field.alias for field in ApplicantFactsData.model_fields.values() if field.alias
    }

    for persona in PERSONAS:
        payload = driver.build_persona_payload(persona)
        validated = VisaOracleEvaluateRequest.model_validate(payload)

        assert validated.assessment_id == driver._persona_assessment_id(persona.id)
        assert set(payload["facts"]) == expected_fact_aliases
        # 44, not 41 (2026-08-23 vocabulary extension, PR #4650): the count
        # is derived structurally above from `ApplicantFactsData.model_fields`
        # aliases, so this literal is a redundant pin, not the source of
        # truth — bump it in lockstep whenever that model gains a field.
        assert len(payload["facts"]) == 44
        assert payload["disclosed_review_flags"] == []


def test_report_structure_preserves_expected_actual_and_null_explanation() -> None:
    report = _fixture_report(_fixture_decisions())

    assert report["gate"] == "G-b"
    assert report["mode"] == "offline"
    assert report["persona_count"] == 20
    assert report["pack"] == {
        "rule_pack_id": str(gf.build_gold_compiled_pack().rule_pack_id),
        "sequence": 1,
        "version": "1.0.0",
        "payload_sha256": "b" * 64,
        "consistent_across_personas": True,
    }
    assert report["summary"] == {
        "personas_total": 20,
        "personas_match": 20,
        "personas_with_divergence": 0,
        "explained_divergences": 0,
        "unexplained_divergences": 0,
    }
    assert report["overall_pass"] is True
    for row in report["personas"]:
        assert row["expected"]["state"] == row["actual"]["state"]
        assert row["expected"]["candidate_products"] == row["actual"]["candidate_products"]
        assert row["divergence"] is False
        assert row["differences"] == []
        assert row["explanation"] is None


def test_exit_code_counts_only_unexplained_divergences() -> None:
    decisions = list(_fixture_decisions())
    decisions[0] = decisions[1]

    unexplained = _fixture_report(tuple(decisions))
    assert unexplained["personas"][0]["divergence"] is True
    assert unexplained["personas"][0]["explanation"] is None
    assert unexplained["summary"]["unexplained_divergences"] == 1
    assert driver.exit_code_for_report(unexplained) == 1

    row = unexplained["personas"][0]
    accepted = driver.AcceptedExplanation(
        explanation="Accepted after independent review: policy intentionally changed.",
        expected=row["expected"],
        actual=row["actual"],
        pack=row["pack"],
        differences=row["differences"],
    )
    explained = _fixture_report(
        tuple(decisions),
        explanations={1: accepted},
    )
    assert explained["personas"][0]["divergence"] is True
    assert explained["personas"][0]["explanation"]
    assert explained["summary"]["explained_divergences"] == 1
    assert explained["summary"]["unexplained_divergences"] == 0
    assert explained["overall_pass"] is True
    assert driver.exit_code_for_report(explained) == 0

    stale = driver.AcceptedExplanation(
        explanation=accepted.explanation,
        expected=accepted.expected,
        actual={**accepted.actual, "state": "STALE_DIFFERENT_RESULT"},
        pack=accepted.pack,
        differences=accepted.differences,
    )
    stale_report = _fixture_report(tuple(decisions), explanations={1: stale})
    assert stale_report["personas"][0]["explanation"] is None
    assert driver.exit_code_for_report(stale_report) == 1


def test_accepted_explanations_are_loaded_only_from_persona_rows(tmp_path: Path) -> None:
    decisions = list(_fixture_decisions())
    decisions[2] = decisions[0]
    report = _fixture_report(tuple(decisions))
    report["personas"][2]["explanation"] = "Accepted regulation change."
    report_path = tmp_path / "reviewed.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    loaded = driver._load_accepted_explanations(report_path)
    assert set(loaded) == {3}
    assert loaded[3].explanation == "Accepted regulation change."


@pytest.mark.asyncio
async def test_live_replay_uses_mocked_http_and_never_logs_token(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "driver-token-that-must-never-appear"
    token_path = tmp_path / "driver-token"
    token_path.write_text(secret + "\n", encoding="utf-8")
    endpoint_decision = _fixture_decisions()[0]
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        assert str(request.url).startswith(driver.LIVE_ENDPOINT)
        assert request.url.params["traffic_source"] == "synthetic_gold"
        assert request.headers["X-Visa-Driver-Token"] == secret
        VisaOracleEvaluateRequest.model_validate(json.loads(request.content))
        return httpx.Response(
            200,
            json={"decision": endpoint_decision.model_dump(mode="json")},
        )

    caplog.set_level(logging.DEBUG)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        report = await driver.build_live_report(
            client,
            generated_at=_OFFLINE_AT,
            token_path=token_path,
        )

    assert len(requests_seen) == 20
    assert report["mode"] == "live"
    assert report["pack"]["sequence"] == endpoint_decision.rule_pack.sequence
    assert report["pack"]["version"] == endpoint_decision.rule_pack.version
    assert report["pack_source"]["pack_metadata_source"].startswith("each endpoint response")
    assert secret not in caplog.text


def test_driver_token_has_no_argv_surface() -> None:
    parser = driver._parser()
    option_strings = {option for action in parser._actions for option in action.option_strings}
    args = parser.parse_args(["--live"])

    assert not any("token" in option for option in option_strings)
    assert not any("token" in key for key in vars(args))


def test_offline_replay_uses_highest_signed_pack_without_claiming_it_is_active() -> None:
    selected_path, selected_raw = driver.select_highest_repository_pack()
    selected_sequence = selected_raw["payload"]["sequence"]
    report = driver.build_offline_report(generated_at=_OFFLINE_AT)

    assert report["mode"] == "offline"
    assert report["persona_count"] == 20
    assert report["pack"]["sequence"] == selected_sequence
    assert report["pack"]["version"] == selected_raw["payload"]["version"]
    assert report["pack_source"]["file"].endswith(selected_path.name)
    assert report["pack_source"]["selection"].startswith("highest signed PRODUCTION")
    assert report["pack_source"]["production_activation_status"].startswith("not checked")
    assert report["pack_source"]["policy_adapters"] == list(
        driver.evaluate_path.PUBLIC_POLICY_ADAPTER_NAMES
    )
    assert "active_database_binding" in report["pack_source"]["runtime_operations_excluded"]


def test_offline_replay_match_count_does_not_regress_below_measured_floor() -> None:
    """G-b regression floor for the offline gold-persona replay.

    Measured 2026-08-23 (independently reproduced while wiring this gate):
    ``python -m backend.scripts.visa_engine.gold_replay_driver --offline``
    against the highest-sequence signed PRODUCTION pack then in the
    repository (``rulepack-prod-012.signed.json``, sequence=12) replayed
    the 20 canonical gold personas and matched exactly 4/20, with 16
    unexplained divergences. That count was NOT previously asserted by any
    test — the driver's other offline-mode test above checks the report's
    *structure* (mode, persona_count, pack identity) but never its *content*,
    so a regression in the match count could land on main with every check
    green.

    4 is a FLOOR to raise as divergences get cured, never a target to hold
    steady at and never something to lower back down to make this test pass
    again. This test exists to catch the count going DOWN (a real engine or
    pack regression), not to celebrate it staying flat — if a fix legitimately
    raises the match count, bump the floor below (and the mirrored
    ``unexplained_divergences`` ceiling) up to the newly measured value in the
    same PR as the fix, with a fresh timestamp/measurement in this docstring.
    A future signed PRODUCTION pack landing (sequence > 12) will also replay
    here, since ``build_offline_report`` always selects the highest sequence
    present on disk — if that changes the count, re-measure and move the
    floor, do not just widen the assertion.
    """

    report = driver.build_offline_report(generated_at=_OFFLINE_AT)

    summary = report["summary"]
    assert summary["personas_total"] == 20
    assert summary["personas_match"] >= 4, (
        f"gold-persona offline replay regressed below the measured floor: "
        f"{summary['personas_match']}/20 matched (floor=4), "
        f"{summary['unexplained_divergences']} unexplained divergences "
        f"(ceiling=16) against pack sequence={report['pack']['sequence']}"
    )
    assert summary["unexplained_divergences"] <= 16


@pytest.mark.parametrize(
    ("overstay_days", "expected_flags"),
    [
        (0, ()),
        (2, (DisclosedReviewFlag.CONFLICTING_IMMIGRATION_STATUS,)),
    ],
)
def test_offline_replay_passes_effective_review_flags_to_public_adapters(
    monkeypatch: pytest.MonkeyPatch,
    overstay_days: int,
    expected_flags: tuple[DisclosedReviewFlag, ...],
) -> None:
    persona = PERSONAS[0]
    wire = driver.build_persona_payload(persona)
    wire["facts"]["immigration.currently_in_indonesia"] = {
        "status": "KNOWN",
        "value": False,
    }
    wire["facts"]["immigration.overstay_days"] = {
        "status": "KNOWN",
        "value": overstay_days,
    }
    request = VisaOracleEvaluateRequest.model_validate(wire)
    flags_seen: list[tuple[DisclosedReviewFlag, ...]] = []

    def recording_adapter(
        decision,
        facts,
        compiled,
        *,
        disclosed_review_flags=(),
    ):
        flags_seen.append(disclosed_review_flags)
        return decision

    monkeypatch.setattr(driver, "PERSONAS", (persona,))
    monkeypatch.setattr(driver, "build_persona_request", lambda _: request)
    monkeypatch.setattr(
        driver.evaluate_path,
        "apply_public_policy_adapters",
        recording_adapter,
    )

    driver.replay_offline_decisions(evaluated_at=_OFFLINE_AT)

    assert flags_seen == [expected_flags]


def test_public_policy_helper_and_manifest_are_explicit_exports() -> None:
    assert {
        "PUBLIC_POLICY_ADAPTER_NAMES",
        "apply_public_policy_adapters",
    } <= set(driver.evaluate_path.__all__)


def test_public_policy_helper_preserves_endpoint_adapter_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = _fixture_decisions()[0]
    facts = driver.build_persona_request(PERSONAS[0]).applicant_facts()
    compiled = gf.build_gold_compiled_pack()
    calls: list[str] = []

    def minor(current, current_facts):
        assert current_facts is facts
        calls.append("_apply_minor_privacy_hold")
        return current

    def decisive(current, current_compiled):
        assert current_compiled is compiled
        calls.append("_apply_decisive_source_authority_hold")
        return current

    def safety(current, current_compiled):
        assert current_compiled is compiled
        calls.append("_apply_safety_critical_source_hold")
        return current

    def disclosed(current, flags):
        assert flags == ()
        calls.append("_apply_disclosed_review_flags")
        return current

    monkeypatch.setattr(driver.evaluate_path, "_apply_minor_privacy_hold", minor)
    monkeypatch.setattr(driver.evaluate_path, "_apply_decisive_source_authority_hold", decisive)
    monkeypatch.setattr(driver.evaluate_path, "_apply_safety_critical_source_hold", safety)
    monkeypatch.setattr(driver.evaluate_path, "_apply_disclosed_review_flags", disclosed)

    assert driver.evaluate_path.apply_public_policy_adapters(decision, facts, compiled) is decision
    assert calls == list(driver.evaluate_path.PUBLIC_POLICY_ADAPTER_NAMES)


def test_offline_replay_applies_public_policy_adapter_to_every_persona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = driver.evaluate_path.apply_public_policy_adapters
    persona_calls: list[str] = []

    def recording_adapter(decision, facts, compiled, *, disclosed_review_flags=()):
        persona_calls.append(facts.assessment_id)
        return original(
            decision,
            facts,
            compiled,
            disclosed_review_flags=disclosed_review_flags,
        )

    monkeypatch.setattr(driver.evaluate_path, "apply_public_policy_adapters", recording_adapter)
    decisions, _ = driver.replay_offline_decisions(evaluated_at=_OFFLINE_AT)

    assert len(decisions) == len(PERSONAS)
    assert persona_calls == [driver._persona_assessment_id(persona.id) for persona in PERSONAS]
