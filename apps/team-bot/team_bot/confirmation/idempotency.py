"""The composite idempotency key F6's frozen field list under-specifies.

F6 names ``args_sha256`` as a field but says "PROPOSED -> CONFIRMED ->
EXECUTED with idempotency keys" (plural, unqualified) — ``args_sha256``
alone would collide two DIFFERENT actors proposing the identical mutation
on the identical target, which is wrong. Kimi's worked design (research
capture LENS 6 §2) is explicit about the real key:

    idempotency_key = hash(wa_number, action_type, canonical_payload,
                            date_trunc('hour', now))

— principal + tool + args + an HOUR bucket, so a retry or a model
double-invocation within the same hour dedupes to the SAME proposal, while
an identical request the NEXT day is treated as a legitimately new one
rather than silently merged into a year-old row.

Author: Claude Sonnet 5 (lane B3 — team-bot confirmation state machine)
"""

from __future__ import annotations

import hashlib
from datetime import datetime

__all__ = ["compute_idempotency_key"]


def compute_idempotency_key(
    *,
    principal_id: str,
    tool_name: str,
    args_sha256: str,
    now: datetime,
) -> str:
    """Hour-bucketed composite key. ``now`` must be a timezone-aware UTC
    datetime — callers own picking a consistent clock (F6's ``PendingAction``
    is a sqlite row, not a distributed system with clock-skew concerns
    across nodes, since Mini/Pro failover per F9 is a single-writer
    leader-epoch handoff, not concurrent writers)."""
    hour_bucket = now.strftime("%Y-%m-%dT%H")
    raw = f"{principal_id}|{tool_name}|{args_sha256}|{hour_bucket}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
