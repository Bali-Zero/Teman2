"""
Mata Garuda — Legacy gap entry adapter (Anti-Corruption Layer).

The `nexus:gaps` Redis stream contains entries produced by the OSINT-Nexus
gap-detector (~/Desktop/OSINT-Nexus/), a SEPARATE repo whose schema evolves
independently from this consumer. This module is the Anti-Corruption Layer
between the two schemas — see SYMBIOSIS.md Pilastro 3 Condivisione.

It bridges the two by:
  - `coerce_to_canonical()` accepts ANY entry data dict from the stream
  - returns (canonical_gap_type, payload) when the entry can be routed to an
    agent currently in `gap_consumer.GAP_DISPATCH`
  - returns None for shapes we choose to drain (skip+ack with a forensic log
    line)

Translation matrix (live histogram 4059 entries on 2026-05-16, from
research/symbiosis/2026-05-16-dispatch-alias-brainstorm.md):

    OSINT (gap_type, attribute)              CANONICAL gap_type        COUNT
    ----------------------------------       --------------------      -----
    missing_attribute / nip                  gap.missing_nip            1180
    missing_attribute / lhkpn                gap.missing_lhkpn           177
    missing_attribute / angkatan             gap.missing_angkatan         58
    missing_attribute / officials_struktur   gap.kanim_struktur            0  ★
    missing_attribute / procurement_link     gap.missing_procurement       0  ★
    stale_attribute   / *                    gap.stale_official          885
    missing_relation  / officials_struktur   gap.kanim_struktur          116  ✚ 2026-05-16
    missing_relation  / officials_or_documents  gap.orphan_org           886  ✚ 2026-05-16
    missing_relation  / procurement_link     gap.missing_procurement     580  ✚ 2026-05-16
    missing_relation  / WORKS_AT:<kanim>     gap.kanim_struktur          177  ✚ 2026-05-16 (prefix)
    ----------------------------------       --------------------      -----
                                                       subtotal MAPPED 4059  (100%)

    ★ The two zero-count rows are kept for forward-compat with older
      OSINT-Nexus schema versions that emitted them on `missing_attribute`
      instead of `missing_relation`. Removing them would silently regress
      if OSINT ever rolls back.

Schema drift history:
  - 2026-04-13: pre-envelope legacy era (828 entries with mixed shapes).
  - 2026-04-14: canonical 8-type taxonomy declared in
    `docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §5`.
  - 2026-05-08: OSINT-Nexus refactored to emit (gap_type, attribute) tuples
    drawn from {missing_attribute, missing_relation, stale_attribute} × full
    attribute namespace. This broke ~43% of routing (1759 unmapped entries)
    until 2026-05-16 extension. Reference incident: Pilastro 1 Riflessione
    regression doc.

Entries that already use the new envelope shape (have `id`+`type`+`source`)
pass through unchanged.

Reference: `docs/PHASE1_SINAPSI_STATUS_2026-04-16.md` open item #2 +
`research/symbiosis/2026-05-16-reflection-regression-2026-05-08.md`.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("mata_garuda.workers.gap_legacy")


# (legacy gap_type, legacy attribute) → canonical gap_type
# Wildcard attribute uses None as the second key.
# Prefix attributes use a separate _PREFIX_TRANSLATION table.
_TRANSLATION: dict[tuple[str, Optional[str]], str] = {
    # Pre-2026-05-08 OSINT schema (still emitted by older deployments)
    ("missing_attribute", "nip"):                "gap.missing_nip",
    ("missing_attribute", "lhkpn"):              "gap.missing_lhkpn",
    ("missing_attribute", "angkatan"):           "gap.missing_angkatan",
    ("missing_attribute", "officials_struktur"): "gap.kanim_struktur",
    ("missing_attribute", "procurement_link"):   "gap.missing_procurement",
    ("stale_attribute",   None):                 "gap.stale_official",
    # Post-2026-05-08 OSINT schema (current production emitters)
    ("missing_relation",  "officials_struktur"): "gap.kanim_struktur",
    ("missing_relation",  "officials_or_documents"): "gap.orphan_org",
    ("missing_relation",  "procurement_link"):   "gap.missing_procurement",
    # C.4 — explicit DLQ for orphan attributes (no agent target by design).
    # Mapped instead of drained so they appear in dispatch counters and can
    # be distinguished from genuinely-unknown gap shapes in the audit.
    ("missing_attribute", "phone"):              "gap.dlq:phone",
    ("missing_attribute", "profile"):            "gap.dlq:profile",
}

# (legacy gap_type, attribute prefix) → canonical gap_type
# Used when OSINT emits structured attribute names like "WORKS_AT:<kanim_name>"
# where the prefix encodes the relation type but the suffix is data.
_PREFIX_TRANSLATION: dict[tuple[str, str], str] = {
    ("missing_relation", "WORKS_AT:"): "gap.kanim_struktur",
}


def is_legacy_shape(data: dict[str, Any]) -> bool:
    """True if `data` lacks the canonical envelope marker fields.

    Canonical envelope entries always carry `id`, `type`, `source`. Legacy
    entries have `gap_type` instead of `type` and lack `id`/`source`.
    """
    return "type" not in data or "source" not in data


def _lookup_prefix(legacy_type: str, legacy_attr: Optional[str]) -> Optional[str]:
    """Match legacy_attr against _PREFIX_TRANSLATION prefixes.

    Returns canonical gap_type if any (legacy_type, prefix) where
    legacy_attr.startswith(prefix) is registered, else None.
    """
    if legacy_attr is None:
        return None
    for (lt, prefix), canonical in _PREFIX_TRANSLATION.items():
        if lt == legacy_type and legacy_attr.startswith(prefix):
            return canonical
    return None


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
        - Legacy entries are mapped via `_TRANSLATION` (exact match) or
          `_PREFIX_TRANSLATION` (prefix match for structured attributes
          like ``WORKS_AT:<kanim_name>``). The full original dict becomes
          the payload, so the agent retains every field.
        - Unmapped legacy entries log a structured warning, record via
          `_record_unmapped` for daily audit, and return None.
    """
    if not is_legacy_shape(data):
        # Already canonical — caller continues with its existing parsing.
        return data.get("type", ""), data

    legacy_type = data.get("gap_type", "") or ""
    legacy_attr = data.get("attribute") or None

    # Resolution order:
    # 1. exact (type, attr)
    # 2. exact (type, None) — wildcard attr
    # 3. prefix (type, "PREFIX:") for structured attribute names
    canonical = (
        _TRANSLATION.get((legacy_type, legacy_attr))
        or _TRANSLATION.get((legacy_type, None))
        or _lookup_prefix(legacy_type, legacy_attr)
    )

    if canonical is None:
        logger.warning(
            "Legacy gap drained: msg_id=%s gap_type=%r attribute=%r entity=%r — no canonical mapping",
            msg_id,
            legacy_type,
            legacy_attr,
            data.get("entity_name") or data.get("entity_type") or "?",
        )
        _record_unmapped(legacy_type, legacy_attr)
        return None

    # Whole legacy dict becomes payload, plus an explicit marker for
    # downstream auditability.
    payload: dict[str, Any] = dict(data)
    payload["_legacy_source"] = "nexus:gaps:pre-2026-04-14"
    return canonical, payload


# ── Unmapped audit counter (C.2 — loud failure signature) ─────────────────
# In-process counter; persisted snapshot via record_unmapped_snapshot() called
# by the gap_consumer at the end of each tick. SQLite (knowledge.db) is the
# authoritative store — see mata_garuda.runtime.knowledge.

_UNMAPPED_COUNTER: dict[tuple[str, Optional[str]], int] = {}


def _record_unmapped(legacy_type: str, legacy_attr: Optional[str]) -> None:
    """In-process counter increment. Persistence happens in snapshot fn."""
    key = (legacy_type, legacy_attr)
    _UNMAPPED_COUNTER[key] = _UNMAPPED_COUNTER.get(key, 0) + 1


def consume_unmapped_counter() -> dict[tuple[str, Optional[str]], int]:
    """Atomic snapshot+reset of the in-process counter. Caller persists."""
    snapshot = dict(_UNMAPPED_COUNTER)
    _UNMAPPED_COUNTER.clear()
    return snapshot
