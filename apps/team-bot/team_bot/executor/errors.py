"""ExecutorErrorCode — the closed error vocabulary every tool executor uses
to populate ``team_bot.registry.envelope.ToolError.code``.

The brief this package answers to (lane B9, "the executor seam") names a
floor: "a closed vocabulary, not free strings ... distinguish at minimum:
not-authorized · not-found · upstream-unavailable · upstream-timeout ·
invalid-response · internal." This module carries exactly those six, plus
three more this lane needed once it actually had to build the mapping:

- ``INVALID_ARGUMENTS`` — the model's own ``raw_arguments`` failed to parse
  as JSON or failed the tool's own ``parameters_schema`` re-validation
  (F4: "structured output validated server-side ... grammar constraints
  only enforce a SUBSET of JSON Schema" — pattern/minLength/enum-adjacent
  cases a serving-layer grammar does not catch). This is a DIFFERENT
  failure than ``INVALID_RESPONSE`` (the BACKEND's reply is untrustworthy)
  and a different one than ``INTERNAL`` (an unexpected bug in this
  package) — collapsing it into either would make MANDATE.md F11's own
  named tripwire ("schema fail rate") unobservable as a distinct signal.
- ``FEATURE_DISABLED`` — the dark flag gating this tool is off
  (``team_bot.flags``). Deliberately NOT the same code as
  ``NOT_AUTHORIZED``: a flag being off blocks EVERY principal uniformly: a
  future on-call reading a burst of ``not_authorized`` would reasonably
  suspect one broken principal's scope; a burst of ``feature_disabled``
  correctly points at the switch instead.
- ``NOT_IMPLEMENTED`` — the F5 registry knows this tool name, but no
  executor module exists for it yet in ``team_bot.executor.tools`` (true,
  by design, for 9 of the 10 tools until their domain lanes land one each
  — see this package's own README section). Distinct from an
  unregistered/hallucinated tool name entirely (mapped to ``INTERNAL``,
  since ``classify_step``/``UnknownToolError`` upstream in
  ``team_bot.loop`` is supposed to have already caught that case before
  the executor is ever asked to run it).

pydantic v2 house style, matching ``team_bot.registry.envelope``: this is a
frozen, closed vocabulary, not a free string a caller could smuggle
anything through.

Author: Claude Sonnet 5 (lane B9 — team-bot executor seam)
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ExecutorErrorCode"]


class ExecutorErrorCode(StrEnum):
    """Every value here matches ``ToolError.code``'s own field pattern
    (``^[a-z][a-z0-9_]{1,63}$``) — verified at runtime in
    ``tests/executor/test_errors.py`` by actually constructing a
    ``ToolError`` with each value, not by re-deriving a second copy of the
    regex that could drift from the one ``envelope.py`` owns."""

    NOT_AUTHORIZED = "not_authorized"
    NOT_FOUND = "not_found"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    INVALID_RESPONSE = "invalid_response"
    INTERNAL = "internal"
    INVALID_ARGUMENTS = "invalid_arguments"
    FEATURE_DISABLED = "feature_disabled"
    NOT_IMPLEMENTED = "not_implemented"
