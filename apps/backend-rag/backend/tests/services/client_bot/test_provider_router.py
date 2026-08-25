"""ClientBrainProviderRouter — routing rules 1-6 (research capture Sol §1.5).

Uses fake providers (never Gemini/Codex) so this suite has zero network
dependency and zero coupling to other lanes' concrete provider modules.
"""

from __future__ import annotations

import pytest

from backend.channels.profiles import CLIENT_WA_V1
from backend.services.client_bot.contracts import BrainCandidate
from backend.services.client_bot.provider_router import (
    AllProvidersExhaustedError,
    ClientBrainProviderRouter,
)
from backend.services.client_bot.providers.base import (
    ClientBrainProvider,
    ProviderFailure,
    ProviderFailureKind,
    ProviderHealth,
)
from backend.tests.duebot.goldens.builders import (
    FIXED_NOW,
    make_answer_candidate,
    make_brain_request,
    make_canonical_message,
    make_grounding_bundle,
)


class _FakeProvider:
    """A minimal ``ClientBrainProvider`` test double. Records every call it
    receives so a test can assert exactly which providers were tried and
    in what order, without any real generation.
    """

    def __init__(
        self, name: str, *, candidate: BrainCandidate | None = None, failure: ProviderFailure | None = None
    ) -> None:
        self.name = name
        self._candidate = candidate
        self._failure = failure
        self.calls: list[object] = []

    async def generate(self, request):  # noqa: ANN001 - protocol shape, not this file's contract to name
        self.calls.append(request)
        if self._failure is not None:
            raise self._failure
        assert self._candidate is not None
        return self._candidate

    async def health(self) -> ProviderHealth:
        return ProviderHealth(healthy=self._failure is None, detail=None, checked_at=FIXED_NOW)


def _request(case_id: str = "router-case"):
    message = make_canonical_message(case_id)
    grounding = make_grounding_bundle(case_id)
    return make_brain_request(case_id, message=message, profile=CLIENT_WA_V1, grounding=grounding)


def test_protocol_shape_is_satisfied_by_the_fake() -> None:
    """Guards against the fake test double silently drifting from the real
    Protocol shape (isinstance() works because ClientBrainProvider is
    ``@runtime_checkable``).
    """
    fake = _FakeProvider("gemini", candidate=make_answer_candidate("x"))
    assert isinstance(fake, ClientBrainProvider)


@pytest.mark.asyncio
async def test_primary_success_never_touches_fallback() -> None:
    candidate = make_answer_candidate("primary-ok")
    primary = _FakeProvider("gemini", candidate=candidate)
    fallback = _FakeProvider("codex_broker")
    router = ClientBrainProviderRouter(
        {"gemini": primary, "codex_broker": fallback},
        primary_provider="gemini",
        fallback_provider="codex_broker",
        shadow_provider=None,
        codex_broker_enabled=True,
        future_metered_enabled=False,
    )
    result = await router.route(_request())
    assert result is candidate
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 0


@pytest.mark.asyncio
async def test_primary_failure_falls_back() -> None:
    fallback_candidate = make_answer_candidate("fallback-ok")
    primary = _FakeProvider(
        "codex_broker",
        failure=ProviderFailure("codex_broker", ProviderFailureKind.TIMEOUT, "deadline exceeded"),
    )
    fallback = _FakeProvider("gemini", candidate=fallback_candidate)
    router = ClientBrainProviderRouter(
        {"codex_broker": primary, "gemini": fallback},
        primary_provider="codex_broker",
        fallback_provider="gemini",
        shadow_provider=None,
        codex_broker_enabled=True,
        future_metered_enabled=False,
    )
    result = await router.route(_request())
    assert result is fallback_candidate
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 1


@pytest.mark.asyncio
async def test_both_fail_raises_all_providers_exhausted_with_both_attempts() -> None:
    primary = _FakeProvider(
        "gemini", failure=ProviderFailure("gemini", ProviderFailureKind.HOST_OFFLINE, "connect refused")
    )
    fallback = _FakeProvider(
        "codex_broker", failure=ProviderFailure("codex_broker", ProviderFailureKind.QUOTA, "seat exhausted")
    )
    router = ClientBrainProviderRouter(
        {"gemini": primary, "codex_broker": fallback},
        primary_provider="gemini",
        fallback_provider="codex_broker",
        shadow_provider=None,
        codex_broker_enabled=True,
        future_metered_enabled=False,
    )
    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        await router.route(_request())
    attempts = exc_info.value.attempts
    assert [a.provider_name for a in attempts] == ["gemini", "codex_broker"]
    assert attempts[0].kind == ProviderFailureKind.HOST_OFFLINE
    assert attempts[1].kind == ProviderFailureKind.QUOTA


@pytest.mark.asyncio
async def test_no_registered_providers_raises_all_providers_exhausted() -> None:
    """Nothing registered at all — not even the primary — must still raise
    the terminal error, never return None or hang.
    """
    router = ClientBrainProviderRouter(
        {},
        primary_provider="gemini",
        fallback_provider="codex_broker",
        shadow_provider=None,
        codex_broker_enabled=True,
        future_metered_enabled=False,
    )
    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        await router.route(_request())
    assert exc_info.value.attempts == ()


@pytest.mark.asyncio
async def test_codex_broker_kill_switch_off_skips_it_even_as_primary() -> None:
    """F3: 'Ships dark behind CLIENT_BOT_CODEX_BROKER_ENABLED=false' — even
    an operator who mis-set CLIENT_BOT_PRIMARY_PROVIDER=codex_broker while
    the kill switch is off must not route there.
    """
    codex = _FakeProvider("codex_broker", candidate=make_answer_candidate("should-never-fire"))
    router = ClientBrainProviderRouter(
        {"codex_broker": codex},
        primary_provider="codex_broker",
        fallback_provider=None,
        shadow_provider=None,
        codex_broker_enabled=False,  # the kill switch
        future_metered_enabled=False,
    )
    with pytest.raises(AllProvidersExhaustedError):
        await router.route(_request())
    assert len(codex.calls) == 0


@pytest.mark.asyncio
async def test_future_metered_fail_closed_with_flag_on_but_no_approval_id() -> None:
    """Routing rule 4: the flag alone is not evidence of authorization."""
    metered = _FakeProvider("future_metered", candidate=make_answer_candidate("should-never-fire"))
    router = ClientBrainProviderRouter(
        {"future_metered": metered},
        primary_provider="future_metered",
        fallback_provider=None,
        shadow_provider=None,
        codex_broker_enabled=False,
        future_metered_enabled=True,
        future_metered_approval_id=None,
    )
    with pytest.raises(AllProvidersExhaustedError):
        await router.route(_request())
    assert len(metered.calls) == 0


@pytest.mark.asyncio
async def test_future_metered_fail_closed_with_default_verifier_even_with_approval_id() -> None:
    """No verifier registered == always False — an approval_id string alone
    (still just an env-var-shaped value here) cannot authorize it either.
    """
    metered = _FakeProvider("future_metered", candidate=make_answer_candidate("should-never-fire"))
    router = ClientBrainProviderRouter(
        {"future_metered": metered},
        primary_provider="future_metered",
        fallback_provider=None,
        shadow_provider=None,
        codex_broker_enabled=False,
        future_metered_enabled=True,
        future_metered_approval_id="OWNER-APPROVED-001",
        future_metered_approval_verifier=None,
    )
    with pytest.raises(AllProvidersExhaustedError):
        await router.route(_request())
    assert len(metered.calls) == 0


@pytest.mark.asyncio
async def test_future_metered_routes_only_when_flag_id_and_verifier_all_agree() -> None:
    candidate = make_answer_candidate("metered-ok")
    metered = _FakeProvider("future_metered", candidate=candidate)
    router = ClientBrainProviderRouter(
        {"future_metered": metered},
        primary_provider="future_metered",
        fallback_provider=None,
        shadow_provider=None,
        codex_broker_enabled=False,
        future_metered_enabled=True,
        future_metered_approval_id="OWNER-APPROVED-001",
        future_metered_approval_verifier=lambda approval_id: approval_id == "OWNER-APPROVED-001",
    )
    result = await router.route(_request())
    assert result is candidate


@pytest.mark.asyncio
async def test_fallback_none_or_same_as_primary_means_no_second_attempt() -> None:
    primary = _FakeProvider(
        "gemini", failure=ProviderFailure("gemini", ProviderFailureKind.INTERNAL, "boom")
    )
    router = ClientBrainProviderRouter(
        {"gemini": primary},
        primary_provider="gemini",
        fallback_provider="gemini",  # same as primary — must not double-attempt it
        shadow_provider=None,
        codex_broker_enabled=False,
        future_metered_enabled=False,
    )
    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        await router.route(_request())
    assert len(primary.calls) == 1
    assert [a.provider_name for a in exc_info.value.attempts] == ["gemini"]


@pytest.mark.asyncio
async def test_shadow_output_never_returned_by_route() -> None:
    """Routing rule 6: shadow is a SEPARATE method, never mixed into
    route()'s return value — route() must not even know a shadow provider
    is configured.
    """
    primary_candidate = make_answer_candidate("primary")
    primary = _FakeProvider("gemini", candidate=primary_candidate)
    shadow = _FakeProvider("codex_broker", candidate=make_answer_candidate("shadow"))
    router = ClientBrainProviderRouter(
        {"gemini": primary, "codex_broker": shadow},
        primary_provider="gemini",
        fallback_provider=None,
        shadow_provider="codex_broker",
        codex_broker_enabled=True,
        future_metered_enabled=False,
    )
    result = await router.route(_request())
    assert result is primary_candidate
    assert len(shadow.calls) == 0  # route() alone never touches shadow


@pytest.mark.asyncio
async def test_run_shadow_returns_candidate_when_eligible() -> None:
    shadow_candidate = make_answer_candidate("shadow-ok")
    shadow = _FakeProvider("codex_broker", candidate=shadow_candidate)
    router = ClientBrainProviderRouter(
        {"codex_broker": shadow},
        primary_provider="gemini",
        fallback_provider=None,
        shadow_provider="codex_broker",
        codex_broker_enabled=True,
        future_metered_enabled=False,
    )
    result = await router.run_shadow(_request())
    assert result is shadow_candidate


@pytest.mark.asyncio
async def test_run_shadow_swallows_failure_and_returns_none() -> None:
    shadow = _FakeProvider(
        "codex_broker",
        failure=ProviderFailure("codex_broker", ProviderFailureKind.OUTPUT_INVALID, "bad json"),
    )
    router = ClientBrainProviderRouter(
        {"codex_broker": shadow},
        primary_provider="gemini",
        fallback_provider=None,
        shadow_provider="codex_broker",
        codex_broker_enabled=True,
        future_metered_enabled=False,
    )
    result = await router.run_shadow(_request())
    assert result is None


@pytest.mark.asyncio
async def test_run_shadow_none_when_no_shadow_configured() -> None:
    router = ClientBrainProviderRouter(
        {},
        primary_provider="gemini",
        fallback_provider=None,
        shadow_provider=None,
        codex_broker_enabled=False,
        future_metered_enabled=False,
    )
    assert await router.run_shadow(_request()) is None


@pytest.mark.asyncio
async def test_run_shadow_none_when_codex_broker_kill_switch_off() -> None:
    shadow = _FakeProvider("codex_broker", candidate=make_answer_candidate("should-never-fire"))
    router = ClientBrainProviderRouter(
        {"codex_broker": shadow},
        primary_provider="gemini",
        fallback_provider=None,
        shadow_provider="codex_broker",
        codex_broker_enabled=False,
        future_metered_enabled=False,
    )
    assert await router.run_shadow(_request()) is None
    assert len(shadow.calls) == 0


def test_from_settings_reads_the_expected_attribute_names() -> None:
    class _FakeSettings:
        client_bot_primary_provider = "codex_broker"
        client_bot_fallback_provider = "gemini"
        client_bot_shadow_provider = "none"
        client_bot_codex_broker_enabled = True
        client_bot_future_metered_enabled = False
        client_bot_future_metered_approval_id = None

    router = ClientBrainProviderRouter.from_settings({}, _FakeSettings())
    assert router._primary == "codex_broker"  # noqa: SLF001 - white-box wiring assertion
    assert router._fallback == "gemini"  # noqa: SLF001
    assert router._codex_broker_enabled is True  # noqa: SLF001


def test_from_settings_defaults_when_settings_lacks_attributes() -> None:
    """A settings object built before these fields existed must not crash
    the router — safe defaults, not an AttributeError.
    """
    router = ClientBrainProviderRouter.from_settings({}, object())
    assert router._primary == "gemini"  # noqa: SLF001
    assert router._codex_broker_enabled is False  # noqa: SLF001
