"""
Mata Garuda — Legacy gap entry adapter.

The `nexus:gaps` Redis stream contains 828 entries from the pre-envelope era
(2026-04-10 → 2026-04-13) that use a different shape and `gap_type` taxonomy
than the canonical envelope used by gap_consumer.

This module bridges the two:
  - `coerce_to_canonical()` accepts ANY entry data dict from the stream
  - returns (canonical_gap_type, payload) when the legacy entry maps to a
    type currently in `gap_consumer.GAP_DISPATCH`
  - returns None for legacy shapes we choose to drain (skip+ack with a
    forensic log line)

Translation matrix (from a histogram of the live 828 legacy entries on
2026-04-16, see docs/PHASE1_METRICS_2026-04-16.md):

    LEGACY (gap_type, attribute)        CANONICAL gap_type           COUNT
    ----------------------------------  ---------------------------  -----
    missing_attribute / nip             gap.missing_nip                260
    missing_attribute / lhkpn           gap.missing_lhkpn               39
    missing_attribute / angkatan        gap.missing_angkatan            13
    missing_attribute / officials_struktur  gap.kanim_struktur          26
    missing_attribute / procurement_link  gap.missing_procurement      130
    stale_attribute  / *                gap.stale_official             195
    ------------------------------------ subtotal MAPPED                663

    missing_attribute / profile         <drain — no canonical mapping> 195
    missing_attribute / officials_or_documents  <drain>                195
    missing_attribute / WORKS_AT:*      <drain — relation, not attr>    39
    missing_relation / *                <drain — no canonical mapping> 390 (some overlap above)
    ------------------------------------ subtotal DRAINED              ~360

The 4 DRAINED legacy types correspond to gap detector probes that were
designed before the canonical 8-type taxonomy in
`docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §5`
was finalized. They have no agent able to act on them today; draining them
with a forensic log entry is the pragmatic choice. If a legacy type later
acquires an agent, add the mapping here — no schema migration needed.

Entries that already use the new envelope shape (have `id`+`type`+`source`)
pass through unchanged.

Reference: `docs/PHASE1_SINAPSI_STATUS_2026-04-16.md` open item #2.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("mata_garuda.workers.gap_legacy")


# (legacy gap_type, legacy attribute) → canonical gap_type
# Wildcard attribute uses None as the second key.
_TRANSLATION: dict[tuple[str, Optional[str]], str] = {
    ("missing_attribute", "nip"):                "gap.missing_nip",
    ("missing_attribute", "lhkpn"):              "gap.missing_lhkpn",
    ("missing_attribute", "angkatan"):           "gap.missing_angkatan",
    ("missing_attribute", "officials_struktur"): "gap.kanim_struktur",
    ("missing_attribute", "procurement_link"):   "gap.missing_procurement",
    ("stale_attribute",   None):                 "gap.stale_official",
}


def is_legacy_shape(data: dict[str, Any]) -> bool:
    """True if `data` lacks the canonical envelope marker fields.

    Canonical envelope entries always carry `id`, `type`, `source`. Legacy
    entries have `gap_type` instead of `type` and lack `id`/`source`.
    """
    return "type" not in data or "source" not in data


def coerce_to_canonical(
    msg_id: str,
    data: dict[str, Any],
) -> Optional[tuple[str, dict[str, Any]]]:
    """Coerce a stream entry to (canonical_gap_type, payload).

    Returns:
        (gap_type, payload)  if the entry can be routed to an agent.
        None                 if the entry should be skipped+acked (drained).

    Behavior:
        - Canonical envelope entries are returned unchanged (caller still
          parses payload from JSON string itself; we just re-expose the
          fields here for a uniform interface).
        - Legacy entries are mapped via `_TRANSLATION`. The full original
          dict becomes the payload, so the agent retains every field.
        - Unmapped legacy entries log a structured warning and return None.
    """
    if not is_legacy_shape(data):
        # Already canonical — caller continues with its existing parsing.
        return data.get("type", ""), data

    legacy_type = data.get("gap_type", "") or ""
    legacy_attr = data.get("attribute") or None

    # Try (type, attr) then (type, None) as a fallback.
    canonical = (
        _TRANSLATION.get((legacy_type, legacy_attr))
        or _TRANSLATION.get((legacy_type, None))
    )

    if canonical is None:
        logger.warning(
            "Legacy gap drained: msg_id=%s gap_type=%r attribute=%r entity=%r — no canonical mapping",
            msg_id,
            legacy_type,
            legacy_attr,
            data.get("entity_name") or data.get("entity_type") or "?",
        )
        return None

    # Whole legacy dict becomes payload, plus an explicit marker for
    # downstream auditability.
    payload: dict[str, Any] = dict(data)
    payload["_legacy_source"] = "nexus:gaps:pre-2026-04-14"
    return canonical, payload
