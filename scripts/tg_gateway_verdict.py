"""Pure parser for the machine-readable verdict emitted by ``tg_notify.py``."""
from __future__ import annotations

from typing import Final

CANONICAL_GATEWAY_VERDICTS: Final[frozenset[str]] = frozenset(
    {
        "sent",
        "logged",
        "spooled",
        "deduped",
        "p0_overflow_spooled",
        "p0_unsent_spooled",
        "acted",
    }
)


def extract_gateway_verdict(stderr: str | None) -> str | None:
    """Return the last exact canonical ``tg_notify: <verdict>`` stderr line.

    The gateway may log a human diagnostic containing the same prefix before
    its final machine-readable line.  Only a complete canonical line counts;
    malformed or missing output is deliberately unknown (``None``).
    """
    verdict: str | None = None
    for line in (stderr or "").splitlines():
        prefix = "tg_notify: "
        if not line.startswith(prefix):
            continue
        candidate = line[len(prefix) :]
        if candidate in CANONICAL_GATEWAY_VERDICTS:
            verdict = candidate
    return verdict


def gateway_delivered(verdict: str | None) -> bool:
    """Whether the gateway reports a real-time Telegram delivery.

    ``acted`` is deliberately NOT a delivery: the gateway routed the condition
    to the escalation board for a seat to cure, and no human was reached. A
    caller that records ``alerted=<this>`` keeps telling the truth — it did not
    page anyone — while the condition is still being worked. Do not widen this
    to "the gateway accepted it", or a routed p0 becomes indistinguishable from
    one that woke the owner.
    """
    return verdict == "sent"
