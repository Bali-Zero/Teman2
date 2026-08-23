"""Real, cryptographically-verified, evaluator-driven proof that the Visa
Oracle emergency PACK rollback ceremony reproduces actual DECISIONS, not
merely a ledger row.

research/visa/2026-08-23-killswitch-rollback-proof.md 2.2 SUPERSEDES this
file's first version after a real cross-family adversarial refutation
(Codex gpt-5.6-sol xhigh) found the original proof used a
documented-non-real placeholder hash (test_repository.py's `_pack_hash`)
and a fabricated random-UUID signature, and never drove
`verify_rule_pack`, `build_compiled_pack`, or `run_evaluation` at all --
it proved DB bookkeeping, not that a "restored" pack is verifiable,
compilable, or produces the same decisions as the original.

This version signs three REAL Ed25519-signed, JCS-hashed envelopes over
the actual checked-in evaluatable TEST pack
(`rulepack-test-c1-tourism.source.json`: one product C1/Tourist Visit
Visa, a HARD_FILTER excluding overstay>60 days, an ELIGIBILITY rule
supporting TOURISM stays <=30 days) -- using this exact test suite's own
established real-signing idiom (`_builders.ephemeral_ed25519_keypair` +
`_builders.sign_rule_pack_envelope`, already exercised end-to-end by
`test_repository.py::_insert_activate_load_verify`, P0-1/P1-8) -- and
drives the FULL production evaluate path (`evaluate_path.run_evaluation`)
against fixed facts, unmocked from `_resolve_active_pack_binding` through
`verify_rule_pack` / `build_compiled_pack` / `evaluate_with_trace`,
asserting the restored pack (C) reproduces pack A's DECISION on the exact
same facts where the intervening "bad deploy" (B) genuinely produced a
DIFFERENT decision.

Two things are deliberately mocked, both orthogonal to pack correctness
and disclosed here rather than silently patched:

  - `evaluate_path.active_retention_policy_available` -> stubbed True.
    The real gate lives behind a Zero retention-policy record this
    proof's migration set does not provision. Corrected characterization
    (2026-08-23, gate-review follow-up): this is not a downstream
    persistence toggle -- `_retention_gate_allows_persistence`
    (evaluate_path.py:270-296) is checked at evaluate_path.py:1466,
    *before* `_resolve_active_pack_binding`, so a False short-circuits
    the whole call to `RETENTION_POLICY_UNAVAILABLE` before any pack is
    even looked up. It gates entry to the entire evaluate path, not
    merely whether the resulting decision gets written down. Stubbing it
    True remains legitimate and non-hollowing for this proof's purpose:
    it does not influence WHAT the decision is once the real evaluator
    runs, only WHETHER the real evaluator runs at all -- which this
    proof needs, since its migration set provisions no retention record.
  - `evaluate_path._save_evaluate_decision` -> stubbed no-op. Its target
    table (`visa_decisions`) is created by a migration outside this
    proof's applied set (250/251/253/254/267); the function only writes
    an audit row of an ALREADY-COMPUTED decision -- it never reads or
    influences one.

Everything else in the call chain -- `_resolve_active_pack_binding` (real
DB query), `verify_rule_pack` (real Ed25519 verification against a
`StaticTrustStore` built from `VISA_ENGINE_TRUST_STORE_KEYS_JSON`, exactly
as production resolves it inside `run_evaluation`), `build_compiled_pack`,
`evaluate_with_trace`, `apply_public_policy_adapters`,
`resolve_identity_provider` (TEST's documented no-setup placeholder
fallback, `crypto.py:390-404`), `resolve_engine_hmac_keyring` (same,
`crypto.py:299-355`) -- runs for real, unmocked. Pricing catalog
acquisition is untouched too: `run_evaluation` already catches ANY
exception from `get_pricing_service()` and degrades to
`UnavailablePricingCatalog()` (evaluate_path.py's own documented
behavior) -- that degrade path, not a test double, is what runs here.

Temporary pytest test: written into
`apps/backend-rag/backend/tests/services/visa_engine/`, run, then removed
from the tests directory; the copy in `research/visa/` is the permanent
record.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest

from backend.scripts.visa_engine.activate_pack import _build_insert_kwargs
from backend.services.visa_check.match_tree import Purpose
from backend.services.visa_engine import evaluate_path, shadow
from backend.services.visa_engine.bundle import StaticTrustStore, verify_rule_pack
from backend.services.visa_engine.enums import DecisionState
from backend.services.visa_engine.models import ApplicantFacts
from backend.services.visa_engine.repository import VisaEngineRepository
from backend.tests.services.visa_engine._builders import (
    ed25519_public_key_b64url,
    ephemeral_ed25519_keypair,
    sign_rule_pack_envelope,
)

from .test_repository import _ENV, _trust_store_for

_SOURCE_PACK_PATH = (
    Path(__file__).resolve().parents[3]
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
    / "rulepack-test-c1-tourism.source.json"
)


def _c1_source_payload() -> dict:
    """The real checked-in TEST source payload, with one addition: a
    generous ``freshness_policy`` on its source record. The checked-in
    fixture ships WITHOUT one (`SourceRecord.freshness_policy` defaults to
    ``None``), which is a legitimate real-world state
    (`FRESHNESS_POLICY_NOT_DEFINED` -> freshness status UNKNOWN, not
    STALE) but still trips `_source_is_authoritative_and_applicable`'s
    review-reason gate in `run_evaluation`'s post-evaluation decisive-
    source check (evaluate_path.py:1016-1025) -- a REAL, already-known
    production behavior (the same gate is why prod SHADOW has been
    stale-abstaining on portal-decisive paths, per this skill's own LIVE
    STATE history), not a defect in this proof. A 1-year window here is a
    deliberate simplification so THIS proof isolates the pack-rollback
    mechanism from the unrelated source re-attestation cadence.
    """
    payload = json.loads(_SOURCE_PACK_PATH.read_text())
    payload["source_records"][0]["freshness_policy"] = {
        "kind": "MAX_AGE_SINCE_VERIFIED_AT",
        "max_age_seconds": 31_536_000,
    }
    # compile_pack's EXTENSION_POLICY_STATUS_REQUIRED gate only fires for
    # sequence>=2 (the checked-in fixture is sequence=1 and omits this
    # field) -- set on every pack (A included) so A/B/C stay otherwise
    # byte-identical in this field, isolating the ONE deliberate content
    # change (pack B's HARD_FILTER threshold) as the only cross-pack diff.
    payload["products"][0]["extension_policy"]["status"] = "VERIFIED"
    return payload


def _fixed_facts(*, overstay_days: int, stay_days: int = 20) -> ApplicantFacts:
    """Fixed applicant facts for the A/B/C decision-reproduction
    comparison -- reuses `test_evaluate_endpoint.py`'s
    `_facts_with_purposes` wire pattern, additionally pinning the two
    facts the toy C1-tourism pack's HARD_FILTER
    (`immigration.overstay_days`) and ELIGIBILITY (`intent.stay_days`)
    rules actually read (models.py:961-968 wire aliases)."""
    facts = shadow.build_shadow_facts(
        nationality="US", purpose=Purpose.OTHER, duration_months=1, match_hash="category-hash"
    )
    assert facts is not None
    wire = facts.model_dump(mode="json", by_alias=True)
    wire["facts"]["intent.purposes"] = {"status": "KNOWN", "value": ["TOURISM"]}
    wire["facts"]["intent.stay_days"] = {"status": "KNOWN", "value": stay_days}
    wire["facts"]["immigration.overstay_days"] = {"status": "KNOWN", "value": overstay_days}
    wire["facts"]["person.birth_date"] = {"status": "KNOWN", "value": "1990-06-15"}
    return ApplicantFacts.model_validate(wire)


async def _insert_and_activate(
    repo: VisaEngineRepository,
    *,
    payload: dict,
    private_key,
    kid: str,
    signed_at: str,
    trust_store: StaticTrustStore,
    observed_at: datetime,
    activation_reason: str,
) -> tuple[uuid.UUID, uuid.UUID, dict]:
    """Real sign -> real verify -> real insert -> real activate.

    Returns ``(rule_pack_db_id, activation_id, signed_envelope)``.
    """
    envelope = sign_rule_pack_envelope(payload, private_key=private_key, kid=kid, signed_at=signed_at)
    verified = verify_rule_pack(envelope, trust_store=trust_store, observed_at=observed_at)
    kwargs = _build_insert_kwargs(envelope, verified)
    await repo.insert_rule_pack(**kwargs)
    activation_id = await repo.activate_rule_pack(
        rule_pack_id=kwargs["id"], activated_by="ops.ceremony", activation_reason=activation_reason
    )
    return kwargs["id"], activation_id, envelope


@pytest.mark.asyncio
async def test_emergency_rollback_ceremony_reproduces_real_decisions(
    repo: VisaEngineRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, public_key = ephemeral_ed25519_keypair()
    kid = "killswitch-proof-key"
    public_key_b64url = ed25519_public_key_b64url(public_key)
    now = datetime.now(timezone.utc)

    db_trust_store = _trust_store_for(kid=kid, public_key=public_key, environment=_ENV)

    # env-sourced trust store -- exactly how `run_evaluation` resolves one
    # in production (`StaticTrustStore.from_env()`, bundle.py:245-296).
    monkeypatch.setenv(
        "VISA_ENGINE_TRUST_STORE_KEYS_JSON",
        json.dumps(
            [
                {
                    "kid": kid,
                    "public_key": public_key_b64url,
                    "environment": _ENV,
                    "valid_from": "2020-01-01T00:00:00Z",
                    "valid_to": None,
                    "revoked_at": None,
                }
            ]
        ),
    )
    monkeypatch.setenv("VISA_ENGINE_EVALUATE_MODE", "SHADOW")
    # _resolve_evaluate_environment defaults to PRODUCTION
    # (evaluate_path.py:172) -- must be pinned to TEST or the real
    # binding query finds nothing and every call degrades to
    # RULE_PACK_UNAVAILABLE regardless of what is activated below.
    monkeypatch.setenv("VISA_ENGINE_EVALUATE_ENVIRONMENT", _ENV)

    # Orthogonal-to-pack-correctness stubs -- see module docstring.
    async def _retention_ok(*args, **kwargs) -> bool:
        return True

    async def _save_noop(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(evaluate_path, "active_retention_policy_available", _retention_ok)
    monkeypatch.setattr(evaluate_path, "_save_evaluate_decision", _save_noop)

    # --- pack A: bootstrap, the checked-in real evaluatable TEST pack. ------
    payload_a = _c1_source_payload()
    payload_a["rule_pack_id"] = str(uuid.uuid4())
    payload_a["sequence"] = 1
    payload_a["previous_payload_sha256"] = None

    pack_a_id, activation_a, envelope_a = await _insert_and_activate(
        repo,
        payload=payload_a,
        private_key=private_key,
        kid=kid,
        signed_at="2026-07-20T00:00:00Z",
        trust_store=db_trust_store,
        observed_at=now,
        activation_reason="bootstrap",
    )

    facts = _fixed_facts(overstay_days=10)  # under A/C's 60-day threshold, over B's 5-day one

    decision_a_body = await evaluate_path.run_evaluation(
        repo.db_pool,
        facts=facts,
        traffic_source="synthetic_driver",
        request_category_hint=None,
        request_trace="killswitch-proof-A",
    )
    assert decision_a_body["mode"] == "CURATED", decision_a_body  # SHADOW: public surface stays CURATED
    decision_a = decision_a_body["decision"]
    Path("/tmp/killswitch_debug_decision_a.json").write_text(json.dumps(decision_a, indent=2, default=str))
    assert decision_a["state"] == DecisionState.SUPPORTED_CANDIDATES.value, decision_a
    assert [c["product_code"] for c in decision_a["candidates"]] == ["C1"]

    # --- pack B: the "bad deploy" -- tightens the overstay HARD_FILTER
    # from 60 to 5 days, chained from A's REAL hash. -------------------------
    payload_b = _c1_source_payload()
    payload_b["rule_pack_id"] = str(uuid.uuid4())
    payload_b["sequence"] = 2
    payload_b["previous_payload_sha256"] = envelope_a["payload_sha256"]
    payload_b["rules"][0]["when"]["value"] = 5  # was 60

    pack_b_id, activation_b, envelope_b = await _insert_and_activate(
        repo,
        payload=payload_b,
        private_key=private_key,
        kid=kid,
        signed_at="2026-07-21T00:00:00Z",
        trust_store=db_trust_store,
        observed_at=now,
        activation_reason="deploy-v2-bad",
    )

    async with repo.db_pool.acquire() as conn:
        row_a = await conn.fetchrow(
            "SELECT upper(system_period) AS hi FROM visa_ruleset_activations WHERE id = $1",
            activation_a,
        )
        row_b = await conn.fetchrow(
            "SELECT lower(system_period) AS lo, upper(system_period) AS hi "
            "FROM visa_ruleset_activations WHERE id = $1",
            activation_b,
        )
    assert row_a["hi"] is not None  # A closed
    assert row_b["hi"] is None  # B open
    assert row_a["hi"] == row_b["lo"]  # adjacent, no gap

    decision_b_body = await evaluate_path.run_evaluation(
        repo.db_pool,
        facts=facts,
        traffic_source="synthetic_driver",
        request_category_hint=None,
        request_trace="killswitch-proof-B",
    )
    decision_b = decision_b_body["decision"]
    # The bad deploy genuinely changes the decision: overstay_days=10 now
    # exceeds B's 5-day threshold -- C1 is excluded, not supported.
    assert "C1" not in [c["product_code"] for c in decision_b["candidates"]], decision_b
    assert decision_b["state"] != DecisionState.SUPPORTED_CANDIDATES.value

    # --- GUILT: naive reactivation of pack A verbatim (sequence 1 <= head
    # sequence 2) must be rejected. ------------------------------------------
    with pytest.raises(asyncpg.exceptions.RaiseError, match="rollback rejected"):
        await repo.activate_rule_pack(
            rule_pack_id=pack_a_id,
            activated_by="ops.ceremony",
            activation_reason="naive-rollback-attempt",
        )

    async with repo.db_pool.acquire() as conn:
        row_b_after = await conn.fetchrow(
            "SELECT upper(system_period) AS hi FROM visa_ruleset_activations WHERE id = $1",
            activation_b,
        )
        open_count_after_guilt = await conn.fetchval(
            "SELECT count(*) FROM visa_ruleset_activations WHERE upper(system_period) IS NULL"
        )
    assert row_b_after["hi"] is None  # still open, untouched by the rejected attempt
    assert open_count_after_guilt == 1

    # --- INNOCENCE: the legitimate rollback -- re-sign A's CONTENT
    # (byte-identical products/rules/hit_policy) as a NEW pack C, sequence
    # 3, chained from B's REAL hash (the true current head). ----------------
    payload_c = _c1_source_payload()
    payload_c["rule_pack_id"] = str(uuid.uuid4())
    payload_c["sequence"] = 3
    payload_c["previous_payload_sha256"] = envelope_b["payload_sha256"]
    assert payload_c["rules"] == payload_a["rules"]  # content-identical to A
    assert payload_c["products"] == payload_a["products"]

    pack_c_id, activation_c, envelope_c = await _insert_and_activate(
        repo,
        payload=payload_c,
        private_key=private_key,
        kid=kid,
        signed_at="2026-07-22T00:00:00Z",
        trust_store=db_trust_store,
        observed_at=now,
        activation_reason="emergency-rollback-to-v1-content",
    )

    async with repo.db_pool.acquire() as conn:
        row_b_final = await conn.fetchrow(
            "SELECT upper(system_period) AS hi FROM visa_ruleset_activations WHERE id = $1",
            activation_b,
        )
        row_c = await conn.fetchrow(
            "SELECT lower(system_period) AS lo, upper(system_period) AS hi "
            "FROM visa_ruleset_activations WHERE id = $1",
            activation_c,
        )
        open_count_final = await conn.fetchval(
            "SELECT count(*) FROM visa_ruleset_activations WHERE upper(system_period) IS NULL"
        )
        all_open_rows = await conn.fetch(
            "SELECT rule_pack_id FROM visa_ruleset_activations WHERE upper(system_period) IS NULL"
        )
    assert row_b_final["hi"] is not None  # B closed
    assert row_c["hi"] is None  # C open
    assert row_b_final["hi"] == row_c["lo"]  # adjacent, no gap
    assert open_count_final == 1
    assert [r["rule_pack_id"] for r in all_open_rows] == [pack_c_id]

    # --- THE PROOF THIS FILE EXISTS FOR: pack C, driven through the REAL
    # production evaluate path (verify_rule_pack + build_compiled_pack +
    # evaluate_with_trace, all unmocked), reproduces pack A's DECISION on
    # the exact same facts -- not merely matching ledger metadata. ----------
    decision_c_body = await evaluate_path.run_evaluation(
        repo.db_pool,
        facts=facts,
        traffic_source="synthetic_driver",
        request_category_hint=None,
        request_trace="killswitch-proof-C",
    )
    decision_c = decision_c_body["decision"]
    assert decision_c["state"] == decision_a["state"] == DecisionState.SUPPORTED_CANDIDATES.value
    assert (
        [c["product_code"] for c in decision_c["candidates"]]
        == [c["product_code"] for c in decision_a["candidates"]]
        == ["C1"]
    )
    assert (
        decision_c["candidates"][0]["reason_codes"] == decision_a["candidates"][0]["reason_codes"]
    )
    assert (
        decision_c["candidates"][0]["product_version_id"]
        == decision_a["candidates"][0]["product_version_id"]
    )

    summary = (
        "\nDECISION-REPRODUCTION PROOF HOLDS: "
        f"pack_a={pack_a_id} pack_b={pack_b_id} pack_c={pack_c_id} "
        f"activation_a={activation_a} activation_b={activation_b} activation_c={activation_c} "
        f"payload_sha256(A)={envelope_a['payload_sha256']} "
        f"payload_sha256(B)={envelope_b['payload_sha256']} "
        f"payload_sha256(C)={envelope_c['payload_sha256']} -- "
        "real Ed25519-signed pack A, driven through the real unmocked evaluate path, "
        "produced state=SUPPORTED_CANDIDATES candidates=[C1]; "
        "real bad-deploy pack B (HARD_FILTER 60d->5d, same facts) genuinely EXCLUDED C1; "
        "naive reactivation of A was rejected while B was head; "
        "re-signed content-identical pack C (chained from B's real hash) was accepted and, "
        "driven through the same real evaluate path, reproduced A's exact decision: "
        "SUPPORTED_CANDIDATES=[C1] with identical reason_codes and product_version_id."
    )
    print(summary)
    Path("/tmp/killswitch_proof_summary.txt").write_text(summary)
