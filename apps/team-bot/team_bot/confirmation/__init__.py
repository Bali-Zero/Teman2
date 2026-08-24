"""F6's confirmation-gated mutation state machine (server-side, never a
prompt convention) — data shape (``models.py``), CAS behavior (``store.py``),
encryption (``crypto.py``), composite idempotency key (``idempotency.py``),
confirm-code extraction (``confirmation_input.py``), server-authored outcome
text (``outcomes.py``), and the reply-composition structural fix
(``reply_composer.py``)."""

from __future__ import annotations

from .confirmation_input import parse_confirmation_button_payload, parse_confirmation_text
from .crypto import ArgsCipher, ArgsIntegrityError, canonicalize_args, load_cipher_from_env, sha256_hex
from .idempotency import compute_idempotency_key
from .models import PRINCIPAL_ID_PATTERN, SHORT_CODE_PATTERN, PendingAction, PendingActionStatus, is_valid_short_code
from .outcomes import DEFAULT_LOCALE, ConfirmationOutcome, ConfirmationStage, Locale, render_outcome
from .reply_composer import ComposedReply, TurnIntent, compose_reply
from .store import (
    DEFAULT_TTL_SECONDS,
    CancelOutcome,
    CancelResult,
    ConfirmOutcome,
    ConfirmResult,
    ExecuteOutcome,
    ExecuteResult,
    ProposeOutcome,
    ProposeResult,
    SqlitePendingActionStore,
)

__all__ = [
    "DEFAULT_LOCALE",
    "DEFAULT_TTL_SECONDS",
    "PRINCIPAL_ID_PATTERN",
    "SHORT_CODE_PATTERN",
    "ArgsCipher",
    "ArgsIntegrityError",
    "CancelOutcome",
    "CancelResult",
    "ComposedReply",
    "ConfirmOutcome",
    "ConfirmResult",
    "ConfirmationOutcome",
    "ConfirmationStage",
    "ExecuteOutcome",
    "ExecuteResult",
    "Locale",
    "PendingAction",
    "PendingActionStatus",
    "ProposeOutcome",
    "ProposeResult",
    "SqlitePendingActionStore",
    "TurnIntent",
    "canonicalize_args",
    "compose_reply",
    "compute_idempotency_key",
    "is_valid_short_code",
    "load_cipher_from_env",
    "parse_confirmation_button_payload",
    "parse_confirmation_text",
    "render_outcome",
    "sha256_hex",
]
