"""codex_broker_wire.py — F3 closed wire-error vocabulary + classification.

F3 (docs/plans/2026-08-25-due-bot-live/MANDATE.md), verbatim: "Codex broker
leg reuses the existing dark implementation (queue depth 1, lease 20s,
breaker 3-fail/5-min)... Closed wire error vocabulary: AUTH_DEAD | QUOTA |
TIMEOUT | HOST_OFFLINE | OUTPUT_INVALID | POLICY_BLOCKED | INTERNAL — auth
and quota MUST be distinct (today they collapse; split before arming)."
See also research capture §2.3 (research/operations/2026-08-25-due-bot-7-lens-research.md).

This module is the PRODUCTION side of that closed vocabulary.
``backend.tests.duebot.fake_codex_broker.BrokerErrorClass`` already models
the SAME seven values on the test side, as the daemon-facing wire-protocol
fake lane B6 built ahead of this unit — that module is test-only (it lives
under ``backend/tests/``) and this one is production code, so the two
enums are two independent Python classes rather than one shared import.
They are drift-guarded instead: see
``tests/services/integrations/test_codex_broker_wire.py::test_broker_error_class_matches_fake_broker_wire_vocabulary``,
which asserts the two value-sets stay identical.

``classify_codex_exec_failure`` maps every exception type
``backend.llm.codex_exec_client.CodexExecClient.generate()`` can raise onto
this closed set. Its job is narrow and specific: give a future daemon (out
of scope for this unit — see MANDATE.md F3's daemon/promotion-ladder/
tripwire pieces) a single, exhaustive place to convert a codex_exec_client
failure into the value it POSTs as ``error_class`` to
``/api/wa-broker/complete``, instead of re-deriving that mapping ad hoc at
each call site (which is exactly how AUTH_DEAD and QUOTA collapsed into one
bucket in the first place, per F3's own framing).

Two DIFFERENT kinds of claim live in this unit — do not conflate them.
``classify_codex_exec_failure`` itself is a plain ``isinstance`` mapping
over a closed, enumerable set of Python exception types: it is PROVABLY
EXHAUSTIVE by construction (every branch is visible in the function body,
an unmatched type raises loudly rather than guessing, and a test enumerates
all nine known types against it). That certainty does NOT extend to
*which* exception a real ``codex exec`` failure produces in the first
place — the ``_QUOTA_RE`` / ``_POLICY_BLOCKED_RE`` trigger patterns that
decide whether ``CodexExecQuotaError`` or ``CodexExecPolicyBlockedError``
gets raised at all (defined in ``codex_exec_client.py``, see that module's
comments) are an UNVERIFIED HYPOTHESIS about Codex CLI stderr wording,
never observed against a real quota or policy event. This module's own
logic is sound by inspection; whether the right exception reaches it on a
real failure is a separate, unproven question that stays open until this
leg's first live quota/policy event.

ZERO WIRING: nothing in this repo imports this module today, matching
``codex_exec_client.py``'s own "OFFLINE, standalone provider adapter"
posture (see that module's docstring). This unit (B2a) is scoped to the
wire vocabulary and its classification only — the daemon, the promotion
ladder, the tripwires, and the ``ClientBrainProvider`` adapter itself
(``services/client_bot/providers/codex_broker.py``) are separate, later
units and are deliberately not created here.

Author: Claude Opus 5 (lane B2a — codex broker wire vocabulary)
"""

from __future__ import annotations

from enum import StrEnum

from backend.llm.codex_exec_client import (
    CodexExecAuthError,
    CodexExecCommunicationError,
    CodexExecModelNotAllowedError,
    CodexExecOutputShapeError,
    CodexExecPolicyBlockedError,
    CodexExecProcessError,
    CodexExecQuotaError,
    CodexExecTimeoutError,
    CodexExecUnavailableError,
)

__all__ = ["BrokerErrorClass", "classify_codex_exec_failure"]


class BrokerErrorClass(StrEnum):
    """F3's closed wire-error vocabulary, verbatim (MANDATE.md F3 / research
    capture §2.3). Mirrors
    ``backend.tests.duebot.fake_codex_broker.BrokerErrorClass``
    value-for-value — a dedicated test guards against the two ever
    silently drifting apart (see module docstring).
    """

    AUTH_DEAD = "AUTH_DEAD"
    QUOTA = "QUOTA"
    TIMEOUT = "TIMEOUT"
    HOST_OFFLINE = "HOST_OFFLINE"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    INTERNAL = "INTERNAL"


def classify_codex_exec_failure(exc: Exception) -> BrokerErrorClass:
    """Map a raised ``codex_exec_client`` exception onto F3's closed
    wire-error vocabulary.

    Exhaustive over every exception type that module's ``generate()`` can
    raise. An unrecognized exception type raises ``TypeError`` rather than
    silently defaulting to ``INTERNAL`` — deliberately: F3 exists because
    today's collapse hides a real failure class inside a neighbouring
    bucket (auth swallowing quota), and a classifier with a silent
    catch-all fallback would just relocate that same defect one layer up
    instead of closing it. A future new exception type added to
    ``codex_exec_client.py`` must extend this function explicitly — it is
    never allowed to fall through unnoticed.

    The mapping, and the one-line rationale for each entry that is not
    self-evident from its F3 name:

    - ``CodexExecAuthError``            -> ``AUTH_DEAD``
    - ``CodexExecQuotaError``           -> ``QUOTA``
    - ``CodexExecPolicyBlockedError``   -> ``POLICY_BLOCKED``
    - ``CodexExecTimeoutError``         -> ``TIMEOUT``
    - ``CodexExecUnavailableError``     -> ``HOST_OFFLINE`` (binary/auth-material
      missing, or the binary could not be launched at all — the seat/host
      cannot run codex right now, which is exactly what F3's HOST_OFFLINE
      denotes)
    - ``CodexExecOutputShapeError``     -> ``OUTPUT_INVALID`` (exit 0 but the
      output contract was violated — a shape problem, not an execution
      failure)
    - ``CodexExecCommunicationError``,
      ``CodexExecProcessError``,
      ``CodexExecModelNotAllowedError`` -> ``INTERNAL`` (an unexpected
      subprocess I/O fault, a generic non-zero exit that matched none of
      the three named word classes, and a caller-side model-allowlist
      configuration error, respectively — none of these three is a more
      specific F3 member; grouping them under INTERNAL is a judgment call
      made explicit here rather than left implicit)

    Args:
        exc: an exception instance raised by
            ``backend.llm.codex_exec_client.CodexExecClient.generate()``.

    Returns:
        The ``BrokerErrorClass`` member this failure maps to.

    Raises:
        TypeError: ``exc`` is not one of the nine known
            ``codex_exec_client`` exception types.
    """
    if isinstance(exc, CodexExecAuthError):
        return BrokerErrorClass.AUTH_DEAD
    if isinstance(exc, CodexExecQuotaError):
        return BrokerErrorClass.QUOTA
    if isinstance(exc, CodexExecPolicyBlockedError):
        return BrokerErrorClass.POLICY_BLOCKED
    if isinstance(exc, CodexExecTimeoutError):
        return BrokerErrorClass.TIMEOUT
    if isinstance(exc, CodexExecUnavailableError):
        return BrokerErrorClass.HOST_OFFLINE
    if isinstance(exc, CodexExecOutputShapeError):
        return BrokerErrorClass.OUTPUT_INVALID
    if isinstance(
        exc,
        (CodexExecCommunicationError, CodexExecProcessError, CodexExecModelNotAllowedError),
    ):
        return BrokerErrorClass.INTERNAL
    raise TypeError(
        f"classify_codex_exec_failure: unrecognized codex_exec_client exception "
        f"type {type(exc).__name__} — F3's closed vocabulary requires an "
        f"exhaustive mapping; extend this function, do not let it fall through"
    )
