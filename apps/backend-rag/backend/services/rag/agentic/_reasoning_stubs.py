"""Backward-compatible re-export of the neutral localized-stub SSOT.

New API-light consumers must import ``backend.services.common.localized_stubs``
directly so importing them never executes ``backend.services.rag.agentic``.
"""

from backend.services.common.localized_stubs import (
    _FALLBACK_MESSAGE,
    PROTOCOL_LANGUAGES,
    STUB_MESSAGES,
    get_localized_stub,
)

__all__ = [
    "PROTOCOL_LANGUAGES",
    "STUB_MESSAGES",
    "_FALLBACK_MESSAGE",
    "get_localized_stub",
]
