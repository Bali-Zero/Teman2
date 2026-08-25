"""Per-member memory — owner directive #1 §3 (relayed via
`/tmp/due-bot-directive-1.md`, integrated into MANDATE.md by `dd23aab94`).

Three layers (data shape: `models.py`; CAS/storage: `store.py`), a ~200
-token per-turn card (`card.py`), and a deterministic "dimentica X" parser
(`forget_input.py`). See `store.py`'s module docstring for the PII
boundary and the cross-lane note on the F6/F9 epoch gap this lane
deliberately does not resolve.
"""

from __future__ import annotations

from .card import (
    DEFAULT_MAX_CARD_TOKENS,
    MAX_CARD_EPISODIC_EVENTS,
    MAX_CARD_PATTERNS,
    estimate_tokens,
    render_member_card,
)
from .forget_input import ForgetRequest, parse_forget_text
from .models import (
    PATTERN_KEY_PATTERN,
    WORKING_HOURS_PATTERN,
    EpisodicEvent,
    IntentCategory,
    LearnedPattern,
    Locale,
    MemberProfile,
    ResponseFormat,
    StaffRole,
    TargetType,
)
from .store import (
    DEFAULT_MAX_EPISODIC_PER_PRINCIPAL,
    DEFAULT_MIN_PATTERN_OBSERVATIONS,
    ForgetResult,
    ForgetScope,
    SqliteMemberMemoryStore,
)

__all__ = [
    "DEFAULT_MAX_CARD_TOKENS",
    "DEFAULT_MAX_EPISODIC_PER_PRINCIPAL",
    "DEFAULT_MIN_PATTERN_OBSERVATIONS",
    "MAX_CARD_EPISODIC_EVENTS",
    "MAX_CARD_PATTERNS",
    "PATTERN_KEY_PATTERN",
    "WORKING_HOURS_PATTERN",
    "EpisodicEvent",
    "ForgetRequest",
    "ForgetResult",
    "ForgetScope",
    "IntentCategory",
    "LearnedPattern",
    "Locale",
    "MemberProfile",
    "ResponseFormat",
    "SqliteMemberMemoryStore",
    "StaffRole",
    "TargetType",
    "estimate_tokens",
    "parse_forget_text",
    "render_member_card",
]
