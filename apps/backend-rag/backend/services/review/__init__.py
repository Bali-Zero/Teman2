"""Review Gate — Telegram approve/edit/reject workflow for War Room 2.0.

Reference: docs/war-room-2.0-design.md §8 (Review Gate M11).

Legge 5: Zero ultima istanza. Nothing auto-publishes.

Modules:
- models: data contracts (ReviewAction, ReviewCallback, callback encode/decode)
- telegram_adapter: small wrapper over TelegramBotService for photo-URL workflow
- review_handler: orchestrates send_review_request + process_callback + DB updates
- sla_worker: periodic job — soft alerts at 4h/12h, auto-expire at 48h
"""

from backend.services.review.models import (
    ReviewAction,
    ReviewCallback,
    ReviewCallbackError,
    ReviewRequest,
    decode_callback,
    encode_callback,
)
from backend.services.review.review_handler import (
    CallbackProcessingResult,
    ReviewHandler,
    ReviewSendResult,
)
from backend.services.review.sla_worker import (
    SLAWorker,
    SLAWorkerResult,
)
from backend.services.review.telegram_adapter import TelegramReviewAdapter

__all__ = [
    "CallbackProcessingResult",
    "ReviewAction",
    "ReviewCallback",
    "ReviewCallbackError",
    "ReviewHandler",
    "ReviewRequest",
    "ReviewSendResult",
    "SLAWorker",
    "SLAWorkerResult",
    "TelegramReviewAdapter",
    "decode_callback",
    "encode_callback",
]
