"""ClientBrainProviderRouter — the ONLY component that reads provider-
selection configuration (research capture Sol §1.5 routing rule 1).

Adapters and ``ClientBotEngine`` call the router; neither imports Gemini,
Codex, or any provider environment variable directly. The router itself
does not import a concrete provider module either — it is constructed with
an injected ``providers: Mapping[str, ClientBrainProvider]`` so this module
has zero import-time coupling to ``providers/gemini.py`` or
``providers/codex_broker.py`` (other lanes' modules, which may not exist
yet on every branch this module is tested from).

Routing rules implemented here (Sol §1.5, verbatim numbering):

1. This is the only config-reading component.
2. (GroundingBundleBuilder's job, not this module's — the router receives
   an already-built ``BrainRequest``.)
3. A provider returns only ``BrainCandidate``; this router never lets a
   provider's return value skip ``FinalPolicyGate`` — it hands the
   candidate back to its caller (``ClientBotEngine``), never sends
   anything itself.
4. ``future_metered`` stays fail-closed unless BOTH
   ``CLIENT_BOT_FUTURE_METERED_ENABLED=true`` AND a persisted,
   owner-approved ``approval_id`` are present. No persisted-approval store
   exists yet, so the default ``approval_verifier`` always returns
   ``False`` — an environment variable alone can never authorize this leg,
   by construction, until a real lane wires a verifier that actually reads
   a persisted decision.
5. Anthropic pay-as-you-go must never be a provider here — this router
   has no branch that could route to one; adding one would require
   importing ``anthropic`` directly, which CLAUDE.md §5 bans outright.
6. Shadow output is evaluated and recorded, but never delivered —
   ``run_shadow()`` is a separate, explicit, non-blocking method
   ``ClientBotEngine`` may call after ``route()`` returns; it is never
   invoked from inside ``route()`` itself, so a shadow-provider failure
   can never affect what gets delivered.

When every eligible provider fails, ``route()`` raises
``AllProvidersExhaustedError`` — the engine catches this and builds the
terminal ``FinalDecision`` (verdict=HANDOFF, reason=PROVIDERS_EXHAUSTED)
directly; ``FinalPolicyGate.evaluate()`` is never called in that path
because there is no candidate to evaluate (see
``policy/types.py``'s ``GateReason.PROVIDERS_EXHAUSTED`` docstring).

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from backend.services.client_bot.contracts import BrainCandidate, BrainRequest
from backend.services.client_bot.providers.base import (
    ClientBrainProvider,
    ProviderFailure,
    ProviderFailureKind,
)

logger = logging.getLogger("zantara.backend")

__all__ = [
    "AllProvidersExhaustedError",
    "ClientBrainProviderRouter",
    "ProviderAttempt",
]

# Reserved provider names this router understands structurally (routing
# rule 4's fail-closed gate is keyed on this literal, not a free string —
# a typo in CLIENT_BOT_PRIMARY_PROVIDER cannot accidentally satisfy it).
_FUTURE_METERED_NAME = "future_metered"
_CODEX_BROKER_NAME = "codex_broker"
_NONE_SENTINEL = "none"


@dataclass(frozen=True)
class ProviderAttempt:
    """One failed attempt, carried into ``AllProvidersExhaustedError`` for
    logging/tripwires — never logs candidate content, only the closed
    failure vocabulary (CLAUDE.md §14: log identifiers/hashes, not content).
    """

    provider_name: str
    kind: ProviderFailureKind
    detail: str


class AllProvidersExhaustedError(Exception):
    """Every eligible provider failed (or none were eligible) before a
    candidate was produced. Distinct from any ``ProviderFailure`` — this is
    the router's OWN terminal state, not a re-raise of the last provider's
    exception, so a caller catching this always knows generation is
    globally exhausted rather than that one specific leg failed.
    """

    def __init__(self, attempts: tuple[ProviderAttempt, ...]) -> None:
        self.attempts = attempts
        summary = ", ".join(f"{a.provider_name}:{a.kind.value}" for a in attempts) or "no eligible provider"
        super().__init__(f"all providers exhausted before generation ({summary})")


class ClientBrainProviderRouter:
    """Selects and calls one ``ClientBrainProvider`` per request, with one
    fallback attempt, then raises ``AllProvidersExhaustedError``.

    Constructed with already-resolved config values (not a live ``Settings``
    object) so unit tests never need to monkeypatch global settings — see
    ``from_settings()`` for the app-wiring path that reads env-backed
    config once at startup.
    """

    def __init__(
        self,
        providers: Mapping[str, ClientBrainProvider],
        *,
        primary_provider: str,
        fallback_provider: str | None,
        shadow_provider: str | None,
        codex_broker_enabled: bool,
        future_metered_enabled: bool,
        future_metered_approval_id: str | None = None,
        future_metered_approval_verifier: Callable[[str], bool] | None = None,
    ) -> None:
        self._providers = dict(providers)
        self._primary = primary_provider
        self._fallback = fallback_provider if fallback_provider not in (None, _NONE_SENTINEL) else None
        self._shadow = shadow_provider if shadow_provider not in (None, _NONE_SENTINEL) else None
        self._codex_broker_enabled = codex_broker_enabled
        self._future_metered_enabled = future_metered_enabled
        self._future_metered_approval_id = future_metered_approval_id
        # Routing rule 4: no verifier registered == always fail closed. A
        # real verifier is a future lane's job (it must check a PERSISTED
        # decision, not re-read the same env var this constructor already
        # read) — see module docstring.
        self._future_metered_approval_verifier = future_metered_approval_verifier or (lambda _approval_id: False)

    def _is_eligible(self, name: str) -> bool:
        """Whether ``name`` may be attempted right now — structural gates
        that apply regardless of provider registration.
        """
        if name == _CODEX_BROKER_NAME and not self._codex_broker_enabled:
            return False
        if name == _FUTURE_METERED_NAME:
            if not self._future_metered_enabled:
                return False
            if self._future_metered_approval_id is None:
                return False
            if not self._future_metered_approval_verifier(self._future_metered_approval_id):
                return False
        return True

    def _resolution_order(self) -> tuple[str, ...]:
        order = [self._primary]
        if self._fallback is not None and self._fallback != self._primary:
            order.append(self._fallback)
        return tuple(order)

    async def route(self, request: BrainRequest) -> BrainCandidate:
        """Try the primary provider, then the fallback, in that order.
        Raises ``AllProvidersExhaustedError`` if neither produces a
        candidate — never returns ``None`` and never silently drops the
        request.
        """
        attempts: list[ProviderAttempt] = []
        for name in self._resolution_order():
            if not self._is_eligible(name):
                logger.info("client-bot provider-router: %s ineligible, skipping", name)
                continue
            provider = self._providers.get(name)
            if provider is None:
                logger.warning(
                    "client-bot provider-router: %s eligible but not registered, skipping", name
                )
                continue
            try:
                return await provider.generate(request)
            except ProviderFailure as exc:
                logger.warning(
                    "client-bot provider-router: %s failed (%s), trying next",
                    name,
                    exc.kind.value,
                )
                attempts.append(ProviderAttempt(provider_name=name, kind=exc.kind, detail=exc.detail))
                continue
        raise AllProvidersExhaustedError(tuple(attempts))

    async def run_shadow(self, request: BrainRequest) -> BrainCandidate | None:
        """Best-effort shadow evaluation — routing rule 6: "evaluated and
        recorded, but never delivered". Never raises: a shadow-leg failure
        must never surface anywhere the primary answer path can see it.
        Returns ``None`` when no shadow provider is configured/eligible/
        registered, or when it failed — the caller decides what "recorded"
        means (a metric increment, a log line); this method's job ends at
        "safely produced a candidate or didn't".
        """
        if self._shadow is None or not self._is_eligible(self._shadow):
            return None
        provider = self._providers.get(self._shadow)
        if provider is None:
            return None
        try:
            return await provider.generate(request)
        except ProviderFailure as exc:
            logger.info("client-bot provider-router: shadow %s failed (%s)", self._shadow, exc.kind.value)
            return None

    @classmethod
    def from_settings(
        cls,
        providers: Mapping[str, ClientBrainProvider],
        settings: object,
        *,
        future_metered_approval_verifier: Callable[[str], bool] | None = None,
    ) -> ClientBrainProviderRouter:
        """App-wiring convenience: read the env-backed config once. ``settings``
        is typed ``object`` (not ``backend.app.core.config.Settings``) so this
        module has no import-time dependency on the app-wide config module —
        callers pass the real settings singleton; tests pass a tiny stand-in
        with the same attribute names.
        """
        return cls(
            providers,
            primary_provider=getattr(settings, "client_bot_primary_provider", "gemini"),
            fallback_provider=getattr(settings, "client_bot_fallback_provider", "gemini"),
            shadow_provider=getattr(settings, "client_bot_shadow_provider", None),
            codex_broker_enabled=getattr(settings, "client_bot_codex_broker_enabled", False),
            future_metered_enabled=getattr(settings, "client_bot_future_metered_enabled", False),
            future_metered_approval_id=getattr(settings, "client_bot_future_metered_approval_id", None),
            future_metered_approval_verifier=future_metered_approval_verifier,
        )
