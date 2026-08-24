"""PendingAction — the frozen shape (MANDATE.md F6) of one confirmation-gated
mutation, and the closed state set it moves through.

F6 verbatim: "PendingAction (short_code, canonical args encrypted,
args_sha256, 5-min expiry, one pending mutation per actor, leader_epoch):
PROPOSED -> CONFIRMED -> EXECUTED with idempotency keys; the executor calls
the CRM with the STORED payload — post-confirmation text never touches the
arguments. ... Replay returns the existing receipt. Steal the shape from
review_handler.py and the wa_broker CAS — both already in the repo."

This module carries only the DATA shape. State-machine BEHAVIOR (the CAS
transitions, idempotency, expiry sweep) lives in ``store.py``; encryption in
``crypto.py``; the composite idempotency key in ``idempotency.py``; the
confirm-code parsers in ``confirmation_input.py``.

Two things F6's frozen text names but does not fully specify, resolved here
(not escalated — see ../../README.md's confirmation-state-machine note for
the full reasoning, mirroring how the F5 naming call was resolved and
reported rather than silently assumed):

1. **"idempotency keys" (plural) vs. the single named field
   ``args_sha256``.** ``args_sha256`` alone hashes only the mutation's
   arguments — two DIFFERENT actors proposing the identical mutation on the
   identical target would collide under an args-only key, which is wrong
   (see Kimi's own worked design, research capture LENS 6 §2:
   ``idempotency_key = hash(wa_number, action_type, canonical_payload,
   date_trunc('hour', now))``). ``idempotency.py`` builds the REAL
   dedup key as that composite (principal + tool + args_sha256 +
   hour-bucket); ``args_sha256`` stays a separate stored field whose job is
   POST-DECRYPT INTEGRITY VERIFICATION (``crypto.py``'s ``decrypt_args``
   raises on mismatch), not primary dedup.
2. **The "numbered/code fallback (`CONFERMA 7F3K`)" MANDATE requires,
   vs. Kimi's looser bare-word matcher** (``sì|si|ok|confermo|yes``, no
   code — sufficient under Kimi's own design ONLY because "one pending
   mutation per actor" already disambiguates). F6's frozen prose is
   stricter than that: it explicitly names a per-proposal CODE, even in the
   text-fallback path. This is a deliberate hardening — a bare "sì" is much
   likelier to fire by accident in an async WhatsApp thread than a random
   4-character code is — and this codebase implements the STRICTER, frozen
   requirement (``confirmation_input.py`` never accepts a bare
   confirmation word), not Kimi's looser proposal.

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from team_bot.registry import TOOL_NAMES

__all__ = [
    "PRINCIPAL_ID_PATTERN",
    "SHORT_CODE_PATTERN",
    "PendingAction",
    "PendingActionStatus",
    "is_valid_short_code",
]

# F6's own worked example is "CONFERMA 7F3K" — four uppercase-alnum
# characters. Bounded 4-12 to leave room without inventing a longer default.
#
# This is the SHAPE only (pydantic-core's regex engine — the Rust `regex`
# crate, not Python's `re` — does not support lookaround at all: a
# `(?=.*[A-Z])` lookahead here fails at model-class-build time with
# "look-around ... is not supported", not merely at validation time; found
# empirically while wiring this up, not assumed). The companion, non-regex
# requirement that the code contain AT LEAST ONE LETTER lives in
# ``is_valid_short_code`` below and is enforced by ``PendingAction``'s
# model_validator. A pure-digit code would be indistinguishable, in
# free-text confirmation replies, from a fragment of a practice/client ID
# (e.g. the "3090" tail of "PR-3090") — see confirmation_input.py's module
# docstring. Every generated short_code (store.py) is mixed alnum by
# construction, so this is a real, always-true invariant, not just a
# parser-side filter.
SHORT_CODE_PATTERN = r"^[A-Z0-9]{4,12}$"


_SHORT_CODE_SHAPE = re.compile(SHORT_CODE_PATTERN)


def is_valid_short_code(code: str) -> bool:
    """Full check: shape (``SHORT_CODE_PATTERN``) AND at least one letter.
    The single source of truth both ``PendingAction`` and
    ``confirmation_input.py``'s parsers use — never two independently
    maintained copies of the same rule."""
    return bool(_SHORT_CODE_SHAPE.match(code)) and any(c.isalpha() for c in code)

# F7 (identity -> principal, not built in this unit) is what PRODUCES this
# value — see F7: "wa_id -> HMAC -> enrolled team mapping -> 60s principal
# ticket". This module only consumes its shape as an opaque, bounded,
# non-PII token (F7's own text: "Raw phone never in logs" — so whatever F7
# hands this module is never the raw phone number itself).
PRINCIPAL_ID_PATTERN = r"^[A-Za-z0-9_-]{1,128}$"

_SHA256_HEX = r"^[0-9a-f]{64}$"


class PendingActionStatus(StrEnum):
    """PROPOSED -> CONFIRMED -> EXECUTED is F6's frozen happy path.
    EXPIRED/CANCELLED are the terminal off-ramps Kimi's elaboration
    (LENS 6 §2) names explicitly ("Expiry 5 min -> ... flips to EXPIRED",
    "Anything else while a proposal is open -> cancel proposal") and F6's
    "Replay returns the existing receipt" presupposes SOME terminal state
    a replay can be judged against."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


_TERMINAL = frozenset(
    {PendingActionStatus.EXECUTED, PendingActionStatus.EXPIRED, PendingActionStatus.CANCELLED}
)


class PendingAction(BaseModel):
    """A read-only SNAPSHOT of one confirmation-gated mutation.

    Never mutated in place — ``store.py``'s CAS operations return a FRESH
    snapshot after every transition, matching the "always re-read after a
    CAS, never assume a stale copy is current" discipline the wa_broker CAS
    module (this unit's stolen shape) itself lives by.

    ``encrypted_args`` is the ciphertext ONLY — this type never carries the
    plaintext args. Decrypting is ``crypto.py.ArgsCipher.decrypt_args``'s
    job, done just-in-time at EXECUTE, never stored back.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    short_code: Annotated[str, Field(pattern=SHORT_CODE_PATTERN)]
    principal_id: Annotated[str, Field(pattern=PRINCIPAL_ID_PATTERN)]
    tool_name: Annotated[str, Field(min_length=1, max_length=128)]
    encrypted_args: bytes
    args_sha256: Annotated[str, Field(pattern=_SHA256_HEX)]
    idempotency_key: Annotated[str, Field(pattern=_SHA256_HEX)]
    status: PendingActionStatus
    leader_epoch: Annotated[int, Field(ge=0)]
    proposed_at: datetime
    expires_at: datetime
    confirmed_at: datetime | None = None
    executed_at: datetime | None = None
    execution_result_ref: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    cancelled_reason: Annotated[str, Field(min_length=1, max_length=200)] | None = None

    @model_validator(mode="after")
    def _tool_name_is_registered(self) -> PendingAction:
        # F6 pairs directly with F5: a PendingAction for a tool the registry
        # does not know about is a contract break, not a business state.
        if self.tool_name not in TOOL_NAMES:
            raise ValueError(f"tool_name {self.tool_name!r} is not in the F5 registry")
        return self

    @model_validator(mode="after")
    def _short_code_has_a_letter(self) -> PendingAction:
        # SHORT_CODE_PATTERN's Field() enforces the SHAPE only —
        # pydantic-core's regex engine has no lookaround, so the
        # at-least-one-letter requirement lives here (see the module-level
        # comment above SHORT_CODE_PATTERN for why the requirement exists
        # at all: distinguishing a real code from an ID fragment).
        if not is_valid_short_code(self.short_code):
            raise ValueError(f"short_code {self.short_code!r} must contain at least one letter")
        return self

    @model_validator(mode="after")
    def _status_constrains_timestamps_and_refs(self) -> PendingAction:
        is_confirmed_or_later = self.status in (
            PendingActionStatus.CONFIRMED,
            PendingActionStatus.EXECUTED,
        )
        if is_confirmed_or_later and self.confirmed_at is None:
            raise ValueError("confirmed_at is required once status reaches confirmed/executed")
        if not is_confirmed_or_later and self.confirmed_at is not None:
            raise ValueError("confirmed_at must be unset before confirmation")

        is_executed = self.status == PendingActionStatus.EXECUTED
        if is_executed and (self.executed_at is None or self.execution_result_ref is None):
            raise ValueError("executed_at and execution_result_ref are required once executed")
        if not is_executed and (self.executed_at is not None or self.execution_result_ref is not None):
            raise ValueError("executed_at/execution_result_ref must be unset unless executed")

        is_cancelled = self.status == PendingActionStatus.CANCELLED
        if is_cancelled and self.cancelled_reason is None:
            raise ValueError("cancelled_reason is required when status is cancelled")
        if not is_cancelled and self.cancelled_reason is not None:
            raise ValueError("cancelled_reason must be unset unless status is cancelled")

        if self.expires_at <= self.proposed_at:
            raise ValueError("expires_at must be after proposed_at")
        return self

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL
