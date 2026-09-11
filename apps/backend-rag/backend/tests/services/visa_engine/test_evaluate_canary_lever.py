"""Tests for the per-request CANARY mode override on the evaluate read-path.

The lever under test lets ONE authenticated request run under a different
``EngineMode`` than the deployment env, so ENFORCE can be tried without
taking every live visitor from 0% to 100% in a single gesture (the
ASSEMBLY-LINE dark -> 5% -> 100% ruling). Three properties are
load-bearing, and each is covered here by a GUILT test (it really does the
thing) and an INNOCENCE test (it does nothing to anyone else):

1. Absent by default => behaviour identical to before the lever existed.
   Guilt: ``TestCanaryEngages``. Innocence: ``TestCanaryAbsentChangesNothing``
   — including the case where the secret IS provisioned but no header is
   sent, which is the shape the allowlist scar taught us to test.
2. Not reachable from a guessable public parameter. Guilt: every rejection
   case in ``TestCanaryCredential``/``TestCanaryRejections``. Innocence:
   ``test_driver_token_is_not_a_canary_token`` — the two credentials are
   separate, so holding one does not confer the other's authority.
3. The row says it was a canary. Guilt:
   ``test_canary_forces_synthetic_driver_label``. Innocence:
   ``test_non_canary_request_keeps_its_declared_traffic_source``.

No DB is touched: ``run_public_evaluation`` is replaced by a recorder that
captures what the router actually handed it AND what
``resolve_evaluate_mode()`` answered at that moment — which is the only
honest way to assert that the override reached the evaluator rather than
merely being stored somewhere.

No test asserts against raw applicant-fact values (SYMBIOSIS Law 2).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from backend.app.routers import visa_oracle_evaluate
from backend.services.visa_check.match_tree import Purpose
from backend.services.visa_engine import evaluate_path, shadow
from backend.services.visa_engine.api_models import VisaOracleEvaluateResponse
from backend.services.visa_engine.enums import EngineMode
from backend.services.visa_engine.models import ApplicantFacts

CANARY_MODE_HEADER = "x-visa-canary-mode"
CANARY_TOKEN_HEADER = "x-visa-canary-token"
CANARY_SECRET = "canary-secret-value"
DRIVER_SECRET = "w4-driver-secret"

EVALUATE_URL = "/api/visa-oracle/evaluate"


def _facts() -> ApplicantFacts:
    """A valid ApplicantFacts with a KNOWN single purpose."""
    facts = shadow.build_shadow_facts(
        nationality="US", purpose=Purpose.OTHER, duration_months=1, match_hash="canary-hash"
    )
    assert facts is not None
    wire = facts.model_dump(mode="json", by_alias=True)
    wire["facts"]["intent.purposes"] = {"status": "KNOWN", "value": ["TOURISM"]}
    return ApplicantFacts.model_validate(wire)


def _payload() -> dict:
    return _facts().model_dump(mode="json", by_alias=True)


class _UntouchedPool:
    """Pool stand-in that fails the test if a connection is ever acquired."""

    def acquire(self) -> None:  # pragma: no cover - failure path only
        raise AssertionError("db_pool must not be touched on this path")


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(visa_oracle_evaluate.router)
    app.state.db_pool = _UntouchedPool()
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


class _Recorder:
    """Stands in for ``run_public_evaluation``.

    Records the ``traffic_source`` the router chose AND the mode
    ``resolve_evaluate_mode()`` returns *inside* the call — the latter is
    the actual claim under test, because the override has to be visible to
    the evaluator, not merely set somewhere the router can see.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, _db_pool: Any, **kwargs: Any) -> Any:
        self.calls.append(
            {
                "traffic_source": kwargs["traffic_source"],
                "mode_seen_by_evaluator": evaluate_path.resolve_evaluate_mode(),
                "canonical_request": kwargs["canonical_request"],
            }
        )
        return VisaOracleEvaluateResponse.model_validate(
            evaluate_path.build_temp_unavailable_body(
                now=datetime.now(timezone.utc),
                code="EVALUATE_SURFACE_DISABLED",
            )
        )

    @property
    def only(self) -> dict[str, Any]:
        assert len(self.calls) == 1, f"expected exactly one evaluation, got {len(self.calls)}"
        return self.calls[0]


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()
    monkeypatch.setattr(evaluate_path, "run_public_evaluation", rec)
    return rec


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test states its own arming; nothing inherits a live deployment."""
    monkeypatch.delenv(evaluate_path.CANARY_TOKEN_ENV, raising=False)
    monkeypatch.delenv(evaluate_path.DRIVER_TOKEN_ENV, raising=False)
    monkeypatch.delenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, raising=False)
    monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")


# ---------------------------------------------------------------------------
# §1 — parse_canary_mode: the closed vocabulary (unit)
# ---------------------------------------------------------------------------


class TestParseCanaryMode:
    @pytest.mark.parametrize("raw", ["ENFORCE", "enforce", "  Enforce  "])
    def test_enforce_is_accepted_case_insensitively(self, raw: str) -> None:
        assert evaluate_path.parse_canary_mode(raw) is EngineMode.ENFORCE

    def test_shadow_is_accepted(self) -> None:
        assert evaluate_path.parse_canary_mode("SHADOW") is EngineMode.SHADOW

    @pytest.mark.parametrize("raw", [None, "", "   ", "OFF", "BOGUS", "ENGINE", "CURATED", "1"])
    def test_everything_else_is_none(self, raw: str | None) -> None:
        """``OFF`` is refused on purpose: the canary exists to try an
        authority the deployment has NOT armed, and a request that disables
        its own surface is indistinguishable from not sending one."""
        assert evaluate_path.parse_canary_mode(raw) is None


# ---------------------------------------------------------------------------
# §2 — verify_canary_token: fail-closed credential (unit)
# ---------------------------------------------------------------------------


class TestCanaryCredential:
    def test_unset_env_rejects_everything(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(evaluate_path.CANARY_TOKEN_ENV, raising=False)
        assert evaluate_path.verify_canary_token("anything") is False
        assert evaluate_path.verify_canary_token("") is False
        assert evaluate_path.verify_canary_token(None) is False

    def test_whitespace_only_env_is_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, "   ")
        assert evaluate_path.verify_canary_token("   ") is False

    def test_matching_token_verifies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        assert evaluate_path.verify_canary_token(CANARY_SECRET) is True

    def test_mismatched_or_missing_token_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        assert evaluate_path.verify_canary_token("canary-secret-valuE") is False
        assert evaluate_path.verify_canary_token(None) is False
        assert evaluate_path.verify_canary_token("") is False

    def test_non_ascii_header_value_is_rejected_not_raised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``compare_digest`` raises TypeError on non-ASCII str; the guard
        must answer False rather than turn a header into a 500."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        assert evaluate_path.verify_canary_token("canarì-secret") is False

    def test_driver_token_is_not_a_canary_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """INNOCENCE for property 2: the two credentials are separate
        secrets, so holding the W4 replay-driver token does not confer the
        authority to change the engine's mode."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, DRIVER_SECRET)
        assert evaluate_path.verify_canary_token(DRIVER_SECRET) is False
        assert evaluate_path.verify_driver_token(CANARY_SECRET) is False


# ---------------------------------------------------------------------------
# §3 — resolve_evaluate_mode + canary_mode_override (unit)
# ---------------------------------------------------------------------------


class TestModeOverrideMechanics:
    def test_without_override_the_env_still_decides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW

    def test_override_wins_over_env_and_is_restored_on_exit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
        with evaluate_path.canary_mode_override(EngineMode.ENFORCE):
            assert evaluate_path.resolve_evaluate_mode() is EngineMode.ENFORCE
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW

    def test_override_is_restored_even_when_the_body_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
        with pytest.raises(RuntimeError):
            with evaluate_path.canary_mode_override(EngineMode.ENFORCE):
                raise RuntimeError("boom")
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW

    def test_override_reaches_the_derived_resolvers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A lever that reached ``resolve_evaluate_mode`` but not the
        resolvers built on top of it would produce a response envelope that
        disagreed with the persisted row about who decided."""
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
        assert evaluate_path.resolve_response_mode() == "CURATED"
        with evaluate_path.canary_mode_override(EngineMode.ENFORCE):
            assert evaluate_path.resolve_response_mode() == "ENGINE"
            assert evaluate_path.resolve_evaluate_shadow_enabled() is True
        assert evaluate_path.resolve_response_mode() == "CURATED"

    def test_nested_override_restores_the_outer_binding(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "OFF")
        with evaluate_path.canary_mode_override(EngineMode.SHADOW):
            with evaluate_path.canary_mode_override(EngineMode.ENFORCE):
                assert evaluate_path.resolve_evaluate_mode() is EngineMode.ENFORCE
            assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.OFF

    async def test_canary_override_does_not_leak_to_a_concurrent_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The isolation claim, exercised rather than asserted from theory:
        two tasks run concurrently, one under the override, and the other
        must never observe ENFORCE."""
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
        started = asyncio.Event()

        async def with_canary() -> EngineMode:
            with evaluate_path.canary_mode_override(EngineMode.ENFORCE):
                started.set()
                await asyncio.sleep(0)
                return evaluate_path.resolve_evaluate_mode()

        async def without_canary() -> EngineMode:
            await started.wait()
            await asyncio.sleep(0)
            return evaluate_path.resolve_evaluate_mode()

        canary_seen, bystander_seen = await asyncio.gather(with_canary(), without_canary())
        assert canary_seen is EngineMode.ENFORCE
        assert bystander_seen is EngineMode.SHADOW


# ---------------------------------------------------------------------------
# §4 — HTTP: the canary engages (GUILT)
# ---------------------------------------------------------------------------


class TestCanaryEngages:
    async def test_valid_canary_makes_the_evaluator_see_enforce(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        async with _client(_build_app()) as client:
            response = await client.post(
                f"{EVALUATE_URL}?traffic_source=real",
                json=_payload(),
                headers={
                    CANARY_MODE_HEADER: "ENFORCE",
                    CANARY_TOKEN_HEADER: CANARY_SECRET,
                },
            )
        assert response.status_code == 200
        assert recorder.only["mode_seen_by_evaluator"] is EngineMode.ENFORCE

    async def test_canary_forces_synthetic_driver_label(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """GUILT for property 3: the caller asked for ``real`` and the row
        is labelled ``synthetic_driver`` anyway, so a canary decision can
        never be counted as production demand."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        async with _client(_build_app()) as client:
            response = await client.post(
                f"{EVALUATE_URL}?traffic_source=real",
                json=_payload(),
                headers={
                    CANARY_MODE_HEADER: "ENFORCE",
                    CANARY_TOKEN_HEADER: CANARY_SECRET,
                },
            )
        assert response.status_code == 200
        assert recorder.only["traffic_source"] == "synthetic_driver"

    async def test_canary_cannot_self_label_synthetic_gold(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """The forced label is unconditional: a canary caller cannot use
        the lever to relabel its rows into the gold-corpus class."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "synthetic_gold")
        monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, DRIVER_SECRET)
        async with _client(_build_app()) as client:
            response = await client.post(
                f"{EVALUATE_URL}?traffic_source=synthetic_gold",
                json=_payload(),
                headers={
                    CANARY_MODE_HEADER: "ENFORCE",
                    CANARY_TOKEN_HEADER: CANARY_SECRET,
                    "x-visa-driver-token": DRIVER_SECRET,
                },
            )
        assert response.status_code == 200
        assert recorder.only["traffic_source"] == "synthetic_driver"

    async def test_forced_label_is_in_the_canonical_request(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """The overwrite happens BEFORE the canonical request is built, so
        the idempotency binding records the label the row will carry — not
        the one the caller asked for."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        async with _client(_build_app()) as client:
            await client.post(
                f"{EVALUATE_URL}?traffic_source=real",
                json=_payload(),
                headers={
                    CANARY_MODE_HEADER: "ENFORCE",
                    CANARY_TOKEN_HEADER: CANARY_SECRET,
                },
            )
        canonical = recorder.only["canonical_request"]
        assert b"synthetic_driver" in canonical
        assert b'"traffic_source":"real"' not in canonical

    async def test_canary_can_also_select_shadow(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "OFF")
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        async with _client(_build_app()) as client:
            response = await client.post(
                f"{EVALUATE_URL}?traffic_source=real",
                json=_payload(),
                headers={
                    CANARY_MODE_HEADER: "SHADOW",
                    CANARY_TOKEN_HEADER: CANARY_SECRET,
                },
            )
        assert response.status_code == 200
        assert recorder.only["mode_seen_by_evaluator"] is EngineMode.SHADOW

    async def test_override_is_released_after_the_response(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        async with _client(_build_app()) as client:
            await client.post(
                f"{EVALUATE_URL}?traffic_source=real",
                json=_payload(),
                headers={
                    CANARY_MODE_HEADER: "ENFORCE",
                    CANARY_TOKEN_HEADER: CANARY_SECRET,
                },
            )
        assert evaluate_path.resolve_evaluate_mode() is EngineMode.SHADOW


# ---------------------------------------------------------------------------
# §5 — HTTP: every way the canary is refused (GUILT for property 2)
# ---------------------------------------------------------------------------


class TestCanaryRejections:
    async def _post(self, headers: dict[str, str]) -> httpx.Response:
        async with _client(_build_app()) as client:
            return await client.post(
                f"{EVALUATE_URL}?traffic_source=real",
                json=_payload(),
                headers=headers,
            )

    async def test_mode_header_without_token_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        response = await self._post({CANARY_MODE_HEADER: "ENFORCE"})
        assert response.status_code == 400
        assert recorder.calls == []

    async def test_mode_header_with_wrong_token_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        response = await self._post(
            {CANARY_MODE_HEADER: "ENFORCE", CANARY_TOKEN_HEADER: "not-the-secret"}
        )
        assert response.status_code == 400
        assert recorder.calls == []

    async def test_unprovisioned_secret_rejects_even_a_correct_looking_token(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """Fail-closed: with the env unset there is no value a caller can
        present that engages the canary."""
        monkeypatch.delenv(evaluate_path.CANARY_TOKEN_ENV, raising=False)
        response = await self._post(
            {CANARY_MODE_HEADER: "ENFORCE", CANARY_TOKEN_HEADER: CANARY_SECRET}
        )
        assert response.status_code == 400
        assert recorder.calls == []

    @pytest.mark.parametrize("bad_mode", ["OFF", "ENGINE", "bogus", "", "   "])
    async def test_unknown_mode_with_a_valid_token_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder, bad_mode: str
    ) -> None:
        """A valid credential never widens the vocabulary — the mirror of
        the allowlist rule that a valid driver token never arms a class."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        response = await self._post(
            {CANARY_MODE_HEADER: bad_mode, CANARY_TOKEN_HEADER: CANARY_SECRET}
        )
        assert response.status_code == 400
        assert recorder.calls == []

    async def test_rejection_message_does_not_reveal_the_failing_layer(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """All three failure shapes answer with the same body, so a prober
        cannot learn whether the secret is provisioned."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        armed_no_token = await self._post({CANARY_MODE_HEADER: "ENFORCE"})
        armed_bad_token = await self._post(
            {CANARY_MODE_HEADER: "ENFORCE", CANARY_TOKEN_HEADER: "wrong"}
        )
        monkeypatch.delenv(evaluate_path.CANARY_TOKEN_ENV, raising=False)
        unarmed = await self._post(
            {CANARY_MODE_HEADER: "ENFORCE", CANARY_TOKEN_HEADER: CANARY_SECRET}
        )
        bodies = {armed_no_token.text, armed_bad_token.text, unarmed.text}
        assert len(bodies) == 1
        assert recorder.calls == []

    async def test_canary_is_not_reachable_from_a_query_parameter(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """Property 2, stated as a probe: the lever has no public
        query-parameter surface, so guessing its name changes nothing."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        async with _client(_build_app()) as client:
            response = await client.post(
                f"{EVALUATE_URL}?traffic_source=real"
                f"&canary=ENFORCE&mode=ENFORCE&engine_mode=ENFORCE"
                f"&canary_token={CANARY_SECRET}",
                json=_payload(),
            )
        assert response.status_code == 200
        assert recorder.only["mode_seen_by_evaluator"] is EngineMode.SHADOW
        assert recorder.only["traffic_source"] == "real"


# ---------------------------------------------------------------------------
# §6 — INNOCENCE: absent canary changes nothing
# ---------------------------------------------------------------------------


class TestCanaryAbsentChangesNothing:
    async def test_no_headers_keeps_the_deployment_mode(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
        async with _client(_build_app()) as client:
            response = await client.post(f"{EVALUATE_URL}?traffic_source=real", json=_payload())
        assert response.status_code == 200
        assert recorder.only["mode_seen_by_evaluator"] is EngineMode.SHADOW

    async def test_provisioned_secret_alone_changes_nothing(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """The scar this repeats: arming the allowlist alone once would have
        let any caller self-label. Arming a LEVER and arming a REQUEST are
        different acts — with the secret set but no header sent, the
        request must behave exactly as if the lever did not exist."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        monkeypatch.setenv(evaluate_path.EVALUATE_MODE_ENV, "SHADOW")
        async with _client(_build_app()) as client:
            response = await client.post(f"{EVALUATE_URL}?traffic_source=real", json=_payload())
        assert response.status_code == 200
        assert recorder.only["mode_seen_by_evaluator"] is EngineMode.SHADOW
        assert recorder.only["traffic_source"] == "real"

    async def test_token_header_without_mode_header_changes_nothing(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """Presence of the MODE header is the only thing that opens the
        branch; a stray token header is inert."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        async with _client(_build_app()) as client:
            response = await client.post(
                f"{EVALUATE_URL}?traffic_source=real",
                json=_payload(),
                headers={CANARY_TOKEN_HEADER: CANARY_SECRET},
            )
        assert response.status_code == 200
        assert recorder.only["mode_seen_by_evaluator"] is EngineMode.SHADOW
        assert recorder.only["traffic_source"] == "real"

    async def test_non_canary_request_keeps_its_declared_traffic_source(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """INNOCENCE for property 3: the forced label is confined to canary
        requests; an ordinary armed driver request keeps its own class."""
        monkeypatch.setenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, "synthetic_gold")
        monkeypatch.setenv(evaluate_path.DRIVER_TOKEN_ENV, DRIVER_SECRET)
        async with _client(_build_app()) as client:
            response = await client.post(
                f"{EVALUATE_URL}?traffic_source=synthetic_gold",
                json=_payload(),
                headers={"x-visa-driver-token": DRIVER_SECRET},
            )
        assert response.status_code == 200
        assert recorder.only["traffic_source"] == "synthetic_gold"

    async def test_synthetic_gate_still_rejects_an_unarmed_caller(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """The pre-existing trust gate is untouched by the new branch: a
        caller with no credentials still cannot self-label synthetic."""
        monkeypatch.delenv(evaluate_path.ALLOW_SYNTHETIC_SOURCES_ENV, raising=False)
        async with _client(_build_app()) as client:
            response = await client.post(
                f"{EVALUATE_URL}?traffic_source=synthetic_driver", json=_payload()
            )
        assert response.status_code == 400
        assert recorder.calls == []

    async def test_invalid_traffic_source_is_still_rejected_before_the_canary(
        self, monkeypatch: pytest.MonkeyPatch, recorder: _Recorder
    ) -> None:
        """Query-param validation keeps precedence: a canary credential
        does not buy a way past the closed vocabulary."""
        monkeypatch.setenv(evaluate_path.CANARY_TOKEN_ENV, CANARY_SECRET)
        async with _client(_build_app()) as client:
            response = await client.post(
                f"{EVALUATE_URL}?traffic_source=whatever",
                json=_payload(),
                headers={
                    CANARY_MODE_HEADER: "ENFORCE",
                    CANARY_TOKEN_HEADER: CANARY_SECRET,
                },
            )
        assert response.status_code == 400
        assert recorder.calls == []
