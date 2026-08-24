"""ClientBrainProvider — the contract every brain leg (Gemini, codex broker,
a future metered leg) implements. Research capture Sol §1.5.

A provider consumes a frozen ``BrainRequest`` (``contracts.py`` — the
evidence/pricing package is built ONCE, before provider selection, so every
provider sees identical grounding) and returns only a ``BrainCandidate``. It
cannot enqueue a message, invoke a surface sender, or ship anything the
FinalPolicyGate has not yet cleared (F1.5 routing rule 3).

Failure is a typed exception, not a return-type union: a provider's
``generate()`` either returns a valid ``BrainCandidate`` or raises
``ProviderFailure`` with one of the closed ``ProviderFailureKind`` members —
this is the "closed wire error vocabulary: AUTH_DEAD | QUOTA | TIMEOUT |
HOST_OFFLINE | OUTPUT_INVALID | POLICY_BLOCKED | INTERNAL" F3 names for the
codex broker leg specifically, generalized here to every provider so
``ClientBrainProviderRouter`` has one failure shape to catch regardless of
which leg raised it. AUTH_DEAD and QUOTA are deliberately distinct members
(F3: "auth and quota MUST be distinct (today they collapse; split before
arming)") — a provider that cannot tell the two apart yet must raise
INTERNAL, never guess.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from backend.services.client_bot.contracts import BrainCandidate, BrainRequest

__all__ = [
    "ClientBrainProvider",
    "ProviderFailure",
    "ProviderFailureKind",
    "ProviderHealth",
]


class ProviderFailureKind(StrEnum):
    """Closed wire error vocabulary (F3), generalized to every provider."""

    AUTH_DEAD = "auth_dead"
    QUOTA = "quota"
    TIMEOUT = "timeout"
    HOST_OFFLINE = "host_offline"
    OUTPUT_INVALID = "output_invalid"
    POLICY_BLOCKED = "policy_blocked"
    INTERNAL = "internal"


class ProviderFailure(Exception):
    """Raised by ``ClientBrainProvider.generate()`` instead of returning a
    partial/invalid candidate. The router catches this — never a bare
    ``Exception`` — so an unclassified bug in a provider implementation
    surfaces as a real traceback rather than being silently swallowed as
    "just try the next provider" (that would turn a provider bug into a
    quiet fallback-ratio metric increment with no trace of the real cause).
    """

    def __init__(self, provider_name: str, kind: ProviderFailureKind, detail: str) -> None:
        self.provider_name = provider_name
        self.kind = kind
        self.detail = detail
        super().__init__(f"{provider_name}: {kind.value} — {detail}")


class ProviderHealth(BaseModel):
    """A provider's own self-report, used for pre-flight routing decisions
    (e.g. skip a provider whose breaker is latched without spending a full
    ``generate()`` timeout to discover it). Never authoritative on its own —
    ``ClientBrainProviderRouter`` still catches ``ProviderFailure`` from
    ``generate()`` even when ``health()`` reported healthy; health can go
    stale between the check and the call.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    healthy: bool
    detail: Annotated[str, Field(max_length=500)] | None = None
    checked_at: datetime


@runtime_checkable
class ClientBrainProvider(Protocol):
    """What ``providers/gemini.py``, ``providers/codex_broker.py``, and
    ``providers/future_metered.py`` (other lanes) each implement.
    ``runtime_checkable`` so the router's own tests can assert a fake test
    double actually satisfies the protocol shape without importing a real
    provider module.
    """

    name: str

    async def generate(self, request: BrainRequest) -> BrainCandidate:
        """Return a valid candidate, or raise ``ProviderFailure``. Never
        raises anything else for an expected failure mode — an
        unclassified exception is a bug in the implementation, not a
        signal the router should route around.
        """
        ...

    async def health(self) -> ProviderHealth: ...
