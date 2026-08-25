"""team_bot.brain — the pluggable TP1 cloud brain + local read-only
fallback (directive#1§1, lane B4-tp1). See `router.py` for the top-level
`BrainRouter`, `tp1_client.py` for the TP1 HTTP adapter, `errors.py` for
the closed error taxonomy, `circuit_breaker.py` and `depletion_probe.py`
for the two degradation mechanisms, and `local_readonly.py` for the R0-only
third lane.
"""

from __future__ import annotations

from .circuit_breaker import BreakerConfig, BreakerState, CircuitBreaker
from .depletion_probe import DepletionAlarm, DepletionProbe, UsageSample
from .errors import (
    BrainErrorClass,
    BrainErrorVerdict,
    EvidenceProvenance,
    MatchConfidence,
    classify_response,
)
from .local_readonly import LocalReadOnlyClient, LocalReadOnlyResult, r0_tools_as_openai_schema
from .router import (
    BrainAttemptLog,
    BrainCompletion,
    BrainRouter,
    BrainRouterExhaustedError,
    BrainTier,
)
from .settings import TP1_BASE_URL, TP1CredentialError, load_tp1_api_key
from .tp1_client import BrainCallError, BrainCallResult, TP1Client, TP1Model

__all__ = [
    "TP1_BASE_URL",
    "BrainAttemptLog",
    "BrainCallError",
    "BrainCallResult",
    "BrainCompletion",
    "BrainErrorClass",
    "BrainErrorVerdict",
    "BrainRouter",
    "BrainRouterExhaustedError",
    "BrainTier",
    "BreakerConfig",
    "BreakerState",
    "CircuitBreaker",
    "DepletionAlarm",
    "DepletionProbe",
    "EvidenceProvenance",
    "LocalReadOnlyClient",
    "LocalReadOnlyResult",
    "MatchConfidence",
    "TP1Client",
    "TP1CredentialError",
    "TP1Model",
    "UsageSample",
    "classify_response",
    "load_tp1_api_key",
    "r0_tools_as_openai_schema",
]
