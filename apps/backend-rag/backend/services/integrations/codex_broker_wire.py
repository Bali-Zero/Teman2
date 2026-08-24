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
which asserts the two value-sets stay identical. **F3's 7-member vocabulary
is FROZEN** (MANDATE.md) — this module never adds an eighth member, even
for a genuinely ambiguous classification (see ``ClassifiedFailure`` below).

``classify_codex_exec_failure`` maps every exception type
``backend.llm.codex_exec_client.CodexExecClient.generate()`` can raise onto
this closed set. Its job is narrow and specific: give a future daemon (out
of scope for this unit — see MANDATE.md F3's daemon/promotion-ladder/
tripwire pieces) a single, exhaustive place to convert a codex_exec_client
failure into the value it POSTs as ``error_class`` to
``/api/wa-broker/complete``, instead of re-deriving that mapping ad hoc at
each call site (which is exactly how AUTH_DEAD and QUOTA collapsed into one
bucket in the first place, per F3's own framing). Its signature and return
type (bare ``BrokerErrorClass``) are UNCHANGED by the B2b round below —
this is the wire-protocol contract B6's ``FakeCodexBroker.complete()``
already consumes, and nothing may widen it silently.

Two DIFFERENT kinds of claim live in this unit — do not conflate them.
``classify_codex_exec_failure`` itself is a plain ``isinstance`` mapping
over a closed, enumerable set of Python exception types: it is PROVABLY
EXHAUSTIVE by construction (every branch is visible in the function body,
an unmatched type raises loudly rather than guessing, and a test enumerates
all ten known types against it — nine as of B2a, plus
``CodexExecAmbiguousError`` added in B2b, see below). That certainty does
NOT extend to *which* exception a real ``codex exec`` failure produces in
the first place — the stderr trigger patterns that decide whether
``CodexExecQuotaError``/``CodexExecPolicyBlockedError``/etc. gets raised at
all (defined in ``codex_exec_client.py``, see that module's comments) are
an UNVERIFIED HYPOTHESIS about Codex CLI stderr wording for quota/policy,
never observed against a real quota or policy event (auth-death has one
measured anchor). This module's own logic is sound by inspection; whether
the right exception reaches it on a real failure is a separate, unproven
question that stays open until this leg's first live quota/policy event.

B2b addition (2026-08-25,
docs/plans/2026-08-25-due-bot-live/SPEC-codex-error-classification.md):
``describe_codex_exec_failure`` is a NEW, ADDITIVE function returning
``ClassifiedFailure`` — ``{error_class, detail}`` — alongside the unchanged
``classify_codex_exec_failure``. It exists for two orchestrator rulings
that both require a sub-cause the bare 7-member enum cannot carry:

  Ruling A — ``OUTPUT_INVALID`` gets a REQUIRED, non-``None`` ``detail``
  distinguishing ``"empty"`` (transient, exit 0, retry is likely to help)
  from ``"oversized"`` (the same prompt reproduces it; retrying wastes a
  call — truncate or reprompt instead). See
  ``codex_exec_client.py::OutputShapeReason``.

  Ruling B — ``INTERNAL`` gets a REQUIRED, non-``None`` ``detail`` naming
  WHICH internal fault this is (``"communication_failure"``,
  ``f"unclassified_exit:{exit_code}"``, ``"model_not_allowed"``, or
  ``f"ambiguous:{candidates}"``) rather than one flat opaque bucket — an
  undistinguished ``INTERNAL`` either pages on something no code change can
  fix, or gets tuned down until it misses a real internal fault. This
  module does NOT yet detect a `codex` CLI/model VERSION-MISMATCH condition
  (the live `wa_broker.py`'s distinct ``cli_version_mismatch`` class) — no
  such signal has ever been observed against `codex exec`'s stderr, and
  this module does not invent one. The detail-carrying PATTERN this ruling
  establishes (every ``INTERNAL`` names its specific sub-cause) is what a
  future lane (B7) extends when that detection is built; flagged, not
  implemented, here.

Ruling A/B's rationale in full is B2b's landing report to the ops
orchestrator, not restated here beyond the summary above.

ZERO WIRING: nothing in this repo imports this module today, matching
``codex_exec_client.py``'s own "OFFLINE, standalone provider adapter"
posture (see that module's docstring). This unit is scoped to the wire
vocabulary and its classification only — the daemon, the promotion ladder,
the tripwires, and the ``ClientBrainProvider`` adapter itself
(``services/client_bot/providers/codex_broker.py``) are separate, later
units and are deliberately not created here.

Author: Claude Opus 5 (lane B2a — codex broker wire vocabulary; lane B2b —
error-classification rebuild to spec)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.llm.codex_exec_client import (
    CodexExecAmbiguousError,
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

__all__ = [
    "BrokerErrorClass",
    "ClassifiedFailure",
    "classify_codex_exec_failure",
    "describe_codex_exec_failure",
]


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


@dataclass(frozen=True)
class ClassifiedFailure:
    """B2b addition — the richer sibling of a bare ``BrokerErrorClass``.

    ``error_class`` is always one of F3's frozen 7 members (never an 8th —
    see module docstring). ``detail`` is a short, SAFE literal (a fixed
    canonical tag or a caller-input value already known to be safe to
    surface, e.g. an exit code or a `_WireWordClass` name — NEVER raw
    stdout/stderr content, matching `codex_exec_client.py` point 6's "no
    raw content crosses the provider boundary" discipline throughout this
    module too). REQUIRED (never ``None``) when ``error_class`` is
    ``OUTPUT_INVALID`` (Ruling A) or ``INTERNAL`` (Ruling B) — optional
    elsewhere, where the wire class alone is already unambiguous
    (``TIMEOUT``, ``HOST_OFFLINE``) or a confidence note is merely
    informative (``AUTH_DEAD``/``QUOTA``/``POLICY_BLOCKED``).
    """

    error_class: BrokerErrorClass
    detail: str | None = None


def describe_codex_exec_failure(exc: Exception) -> ClassifiedFailure:
    """Map a raised ``codex_exec_client`` exception onto F3's closed
    wire-error vocabulary PLUS a sub-cause detail (Rulings A/B, B2b) —
    ``classify_codex_exec_failure`` below is a thin wrapper over this
    function's ``error_class``, so the two can never silently drift.

    Exhaustive over every exception type
    ``CodexExecClient.generate()`` can raise. An unrecognized exception
    type raises ``TypeError`` rather than silently defaulting to
    ``INTERNAL`` — deliberately: F3 exists because today's collapse hides
    a real failure class inside a neighbouring bucket (auth swallowing
    quota), and a classifier with a silent catch-all fallback would just
    relocate that same defect one layer up instead of closing it. A future
    new exception type added to ``codex_exec_client.py`` must extend this
    function explicitly — it is never allowed to fall through unnoticed.

    The mapping, and the one-line rationale for each entry that is not
    self-evident from its F3 name:

    - ``CodexExecAuthError``          -> ``AUTH_DEAD``, detail=confidence
    - ``CodexExecQuotaError``         -> ``QUOTA``, detail=confidence
    - ``CodexExecPolicyBlockedError`` -> ``POLICY_BLOCKED``, detail=confidence
      (always ``"confidence=LOW"`` — this class has no structured tier,
      see `codex_exec_client.py`'s `_POLICY_PROSE_RE` comment)
    - ``CodexExecTimeoutError``       -> ``TIMEOUT``, detail=None
      (deterministic — a wall-clock deadline, not a pattern match)
    - ``CodexExecUnavailableError``   -> ``HOST_OFFLINE``, detail=None
      (binary/auth-material missing, or the binary could not be launched
      at all — the seat/host cannot run codex right now, which is exactly
      what F3's HOST_OFFLINE denotes; deterministic, not a pattern match)
    - ``CodexExecOutputShapeError``   -> ``OUTPUT_INVALID``,
      detail=``exc.reason.value`` (Ruling A — REQUIRED, always
      ``"empty"`` or ``"oversized"``, never ``None``: the exception's own
      constructor requires ``reason``, so this can never be unset)
    - ``CodexExecAmbiguousError``     -> ``INTERNAL``,
      detail=``f"ambiguous:{sorted candidates joined by '+'}"`` (Ruling B
      — F3 has no AMBIGUOUS slot; the candidates are preserved in the
      detail rather than one being silently guessed, per SPEC P1)
    - ``CodexExecCommunicationError`` -> ``INTERNAL``,
      detail=``"communication_failure"`` (Ruling B — an unexpected
      subprocess I/O fault)
    - ``CodexExecProcessError``       -> ``INTERNAL``,
      detail=``f"unclassified_exit:{exc.exit_code}"`` (Ruling B — a
      generic non-zero exit that matched no known word class; the exit
      code is caller-visible already via ``CodexExecProcessError`` itself,
      not new exposure)
    - ``CodexExecModelNotAllowedError`` -> ``INTERNAL``,
      detail=``"model_not_allowed"`` (Ruling B — a caller-side
      model-allowlist configuration error, not a `codex exec` failure at
      all)

    Args:
        exc: an exception instance raised by
            ``backend.llm.codex_exec_client.CodexExecClient.generate()``.

    Returns:
        A ``ClassifiedFailure``.

    Raises:
        TypeError: ``exc`` is not one of the ten known
            ``codex_exec_client`` exception types.
    """
    if isinstance(exc, CodexExecAuthError):
        return ClassifiedFailure(BrokerErrorClass.AUTH_DEAD, f"confidence={exc.confidence.value}")
    if isinstance(exc, CodexExecQuotaError):
        return ClassifiedFailure(BrokerErrorClass.QUOTA, f"confidence={exc.confidence.value}")
    if isinstance(exc, CodexExecPolicyBlockedError):
        return ClassifiedFailure(
            BrokerErrorClass.POLICY_BLOCKED, f"confidence={exc.confidence.value}"
        )
    if isinstance(exc, CodexExecTimeoutError):
        return ClassifiedFailure(BrokerErrorClass.TIMEOUT)
    if isinstance(exc, CodexExecUnavailableError):
        return ClassifiedFailure(BrokerErrorClass.HOST_OFFLINE)
    if isinstance(exc, CodexExecOutputShapeError):
        return ClassifiedFailure(BrokerErrorClass.OUTPUT_INVALID, exc.reason.value)
    if isinstance(exc, CodexExecAmbiguousError):
        return ClassifiedFailure(
            BrokerErrorClass.INTERNAL, f"ambiguous:{'+'.join(sorted(exc.candidates))}"
        )
    if isinstance(exc, CodexExecCommunicationError):
        return ClassifiedFailure(BrokerErrorClass.INTERNAL, "communication_failure")
    if isinstance(exc, CodexExecProcessError):
        return ClassifiedFailure(BrokerErrorClass.INTERNAL, f"unclassified_exit:{exc.exit_code}")
    if isinstance(exc, CodexExecModelNotAllowedError):
        return ClassifiedFailure(BrokerErrorClass.INTERNAL, "model_not_allowed")
    raise TypeError(
        f"describe_codex_exec_failure: unrecognized codex_exec_client exception "
        f"type {type(exc).__name__} — F3's closed vocabulary requires an "
        f"exhaustive mapping; extend this function, do not let it fall through"
    )


def classify_codex_exec_failure(exc: Exception) -> BrokerErrorClass:
    """Map a raised ``codex_exec_client`` exception onto F3's closed
    wire-error vocabulary — the bare ``BrokerErrorClass`` this module has
    returned since B2a. UNCHANGED signature/behavior/return type: this is
    the value B6's ``FakeCodexBroker.complete(error_class=...)`` (and any
    future real daemon POSTing to ``/api/wa-broker/complete``) consumes
    directly, so it stays a thin wrapper over ``describe_codex_exec_failure``
    rather than being redesigned — the two can never silently drift apart
    because one is defined in terms of the other.

    See ``describe_codex_exec_failure`` for the full mapping table,
    rationale, and ``Raises`` contract (identical here).
    """
    return describe_codex_exec_failure(exc).error_class
