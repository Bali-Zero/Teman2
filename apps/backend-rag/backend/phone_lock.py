"""Cooperative advisory-lock protocol for client phone identity keys.

A client's phone is an IDENTITY-RESOLUTION key: intake delivery resolves the
Fly identity by it while holding ``phonecore:`` advisory locks (Codex
2026-07-19 rounds 8-10, F12). EVERY writer that inserts or updates
``clients.phone`` / ``clients.phone_normalized`` must take the canonical core
lock(s) inside its transaction BEFORE writing, so a phone mutation cannot race
the cross-DB resolution window. Lock keys are acquired in lexicographic order —
one total order shared by every participant (deadlock-safe against the other
lock-respecting writers; concurrent additive acquisition in the PATCH
convergence loop can still deadlock in pathological races, resolved by
Postgres' detector aborting one side).

``phone_core`` is the SINGLE canonical projection (digits, one leading ``62``
or ``0`` prefix stripped, ≥6 digits) — the CRM dedup helper and the delivery
gate both delegate here, so drift between "the same phone" definitions is
structurally impossible.
"""

from __future__ import annotations

import re

import asyncpg


def phone_core(raw: object) -> str | None:
    """Canonical dedup core of a phone number.

    ASCII digits with ONE leading Indonesian country/trunk prefix (``62`` or
    ``0``) removed; None when fewer than 6 digits remain (a short fragment is
    never a usable identity key). ``0812…``, ``62812…`` and ``+62 812…`` all
    collapse to the same core.
    """
    if raw is None:
        return None
    digits = re.sub(r"[^0-9]", "", str(raw))
    if digits.startswith("62"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) >= 6 else None


def phone_value_state(raw: object) -> tuple[str, str | None]:
    """Classify ONE stored phone-ish value for consistency gates.

    THE shared absent/unusable/usable primitive (Codex round 15, F23 — the
    delivery gate and the upload ownership gate each carried their own copy
    and the 'absent' semantics drifted):

    - ``('absent', None)`` — empty, or contains NO digit at all: free-text
      garbage like ``"n/a"`` is not a phone CLAIM.
    - ``('unusable', None)`` — has a digit SIGNAL but ``phone_core`` yields
      no core (short fragment, non-ASCII digits): a present-but-garbage claim
      that cannot cross-check anything → callers fail closed.
    - ``('usable', core)`` — yields a canonical core.

    Digit-SIGNAL detection is Unicode-aware on purpose (round 12, F11
    Unicode variant): Arabic-Indic/full-width digits are a phone CLAIM even
    though ``phone_core`` (deliberately ASCII-only, mirroring the SQL
    ``[^0-9]`` projections) extracts no core — that combination is
    ``unusable``, never ``absent``.
    """
    s = ("" if raw is None else str(raw)).strip()
    if not s or not re.search(r"\d", s):
        return ("absent", None)
    core = phone_core(s)
    if core is None:
        return ("unusable", None)
    return ("usable", core)


async def lock_cores(conn: asyncpg.Connection, *cores: str | None) -> set[str]:
    """Take transaction-scoped advisory locks on ALREADY-canonical cores.

    For callers that hold a core (not a raw phone) — e.g. an ownership token
    carried across an HTTP boundary. ``phone_core`` is NOT idempotent (a core
    that itself starts with ``62``/``0`` would be re-stripped), so re-deriving
    from a core would lock the WRONG key; this primitive locks the given cores
    verbatim. None/empty entries are skipped. Same keyspace, same sorted-order
    acquisition, same in-transaction requirement as :func:`lock_phone_cores`.
    """
    wanted = {c for c in cores if c}
    for key in sorted(f"phonecore:{c}" for c in wanted):
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", key)
    return wanted


async def lock_phone_cores(conn: asyncpg.Connection, *values: object) -> set[str]:
    """Take transaction-scoped advisory locks on the cores of ``values``.

    Values that yield no core (None/empty/short) are skipped. Keys are
    ``phonecore:<core>`` hashed via 1-arg ``hashtext`` (the same keyspace the
    upsert-by-phone endpoint and intake delivery use), acquired in sorted
    order. Returns the set of cores locked. MUST be called inside an open
    transaction — ``pg_advisory_xact_lock`` outside one releases at statement
    end, silently disarming the protocol.
    """
    return await lock_cores(conn, *(phone_core(v) for v in values))
