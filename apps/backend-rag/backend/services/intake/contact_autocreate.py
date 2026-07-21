"""intake-v2 PR-1 — identity capture at the entry door.

WhatsApp always carries a sender phone. This module resolves that phone at
ENQUEUE time to a client_id_hint, so a document never lands 0-candidate for
the trivial reason that "nobody ever created a contact for this number":

  a. **team roster / internal number** -> the doc is a FORWARD, never a new
     contact (reuses ``auto_attach._is_internal_sender_phone`` — the same
     roster/env-configured internal-number gate LEVA-2's direct-phone path
     already relies on, so there is exactly ONE roster definition in the
     codebase, not two that can drift).
  b. **existing client** (``clients.phone_normalized`` match) -> return its id.
     Read-only, always attempted regardless of the create killswitch (there is
     no PII-creation risk in *finding* an existing row).
  c. **unknown phone** -> auto-create a MINIMAL contact
     (``status='unlabeled'``, ``origin='wa-intake'``) and return its id. Gated
     behind ``INTAKE_AUTOCREATE_CONTACT_ENABLED`` (default OFF, read at call
     time — same pattern as the other intake flags in ``auto_attach.py``).

Idempotent under concurrency: the INSERT targets the partial UNIQUE index
``ux_clients_phone_normalized_wa_intake`` (migration 246, scoped to
``origin='wa-intake' AND deleted_at IS NULL`` — NOT a full-column unique
index, because live legacy data has 622 duplicate ``phone_normalized`` groups
outside this origin). Two concurrent callers racing to auto-create the same
unknown phone: exactly one INSERT wins, the loser's ``ON CONFLICT DO NOTHING``
returns no row and this module re-selects the winner's id — nobody ever
observes a phantom conflict, nobody double-creates.

PII / Symbiosis Law 2: this module only ever writes ``phone_normalized`` (a
number, not a name) and an optional caller-supplied display name onto a new
row; it never fabricates identity data. Everything runs against whatever
Postgres the caller's ``conn`` is connected to (local dev for backlog tooling,
Fly prod for the live app process) — same contract as the rest of the intake
writer stack (``client_enricher.py``, ``auto_attach.py``).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import asyncpg

from backend.phone_lock import lock_phone_cores
from backend.services.intake.auto_attach import _is_internal_sender_phone
from backend.services.intake.routing import normalize_sender_phone

logger = logging.getLogger("zantara.intake.contact_autocreate")

AUTOCREATE_ENABLED_ENV = "INTAKE_AUTOCREATE_CONTACT_ENABLED"

# Values written onto an auto-created contact (migration 246 / this module).
WA_INTAKE_ORIGIN = "wa-intake"
UNLABELED_STATUS = "unlabeled"
AUTOCREATE_CREATED_BY = "system:wa-intake-autocreate"

# Resolution kinds — every branch of the entry-door decision, so callers can
# log/route without re-deriving the reason from a free-text string.
KIND_INTERNAL_FORWARD = "internal_forward"
KIND_EXISTING = "existing"
KIND_CREATED = "created"
KIND_AMBIGUOUS = "ambiguous"
KIND_NO_PHONE = "no_phone"
KIND_DISABLED = "disabled"


def autocreate_contact_enabled() -> bool:
    """True only if INTAKE_AUTOCREATE_CONTACT_ENABLED is explicitly truthy (default OFF).

    Read at call time (ops/tests can flip it per-process). Gates ONLY the
    CREATE branch — resolving an EXISTING client by phone is always attempted,
    flag or no flag, because it performs no write and carries no mis-creation
    risk.
    """
    return os.environ.get(AUTOCREATE_ENABLED_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass(frozen=True)
class ContactResolution:
    """Outcome of :func:`resolve_or_create_contact` — one call, one verdict.

    ``client_id`` is set for ``existing`` and ``created`` only; every other
    kind means "do not stamp client_id_hint from this signal".
    """

    kind: str
    client_id: int | None
    phone_normalized: str | None
    reason: str


async def _match_existing_by_phone(
    conn: asyncpg.Connection, normalized: str
) -> list[int]:
    """Exact match against ``clients.phone_normalized``, both storage variants.

    Mirrors ``routing._match_sender_phone`` (dual ``+``/bare lookup) but returns
    bare ids — this module never needs the full_name payload.
    """
    rows = await conn.fetch(
        """
        SELECT id
        FROM clients
        WHERE deleted_at IS NULL
          AND phone_normalized IN ($1, $2)
        ORDER BY id
        LIMIT 3
        """,
        normalized,
        "+" + normalized,
    )
    return [r["id"] for r in rows]


async def resolve_or_create_contact(
    conn: asyncpg.Connection,
    *,
    sender_phone: str | None,
    full_name_hint: str | None = None,
) -> ContactResolution:
    """Resolve a WA sender phone to a client_id at intake-entry time.

    Call inside the caller's own transaction (or a fresh one) — the CREATE
    branch performs a real INSERT. Never raises on a benign no-op; only a
    genuine DB fault propagates.
    """
    normalized = normalize_sender_phone(sender_phone)
    if not normalized:
        return ContactResolution(
            kind=KIND_NO_PHONE,
            client_id=None,
            phone_normalized=None,
            reason="sender phone missing or unnormalizable",
        )

    if _is_internal_sender_phone(sender_phone):
        return ContactResolution(
            kind=KIND_INTERNAL_FORWARD,
            client_id=None,
            phone_normalized=normalized,
            reason=(
                "sender phone is team roster / internal number — never "
                "auto-create a contact for a forwarder"
            ),
        )

    matches = await _match_existing_by_phone(conn, normalized)
    if len(matches) == 1:
        return ContactResolution(
            kind=KIND_EXISTING,
            client_id=matches[0],
            phone_normalized=normalized,
            reason="single existing client matches sender phone",
        )
    if len(matches) > 1:
        return ContactResolution(
            kind=KIND_AMBIGUOUS,
            client_id=None,
            phone_normalized=normalized,
            reason=f"sender phone shared by {len(matches)} clients — needs human",
        )

    if not autocreate_contact_enabled():
        return ContactResolution(
            kind=KIND_DISABLED,
            client_id=None,
            phone_normalized=normalized,
            reason="autocreate killswitch off — no existing match either",
        )

    # clients.full_name is NOT NULL. Reuse the codebase's existing placeholder
    # convention for phone-keyed leads with no known name (`Lead +<digits>` —
    # see crm_clients.py's `unnamed` filter / client_enricher._name_is_junk),
    # so this auto-created row is picked up by the SAME "still needs a name"
    # tooling that already exists for WA-mirror leads, rather than inventing a
    # second placeholder convention.
    full_name = (full_name_hint or "").strip() or f"Lead +{normalized}"
    # `phone` is set to the SAME normalized digits as `phone_normalized`, not
    # left NULL. `clients` carries a live trigger
    # (trg_normalize_phone -> update_phone_normalized()) that unconditionally
    # recomputes `NEW.phone_normalized := normalize_phone_number(NEW.phone)` on
    # every INSERT — verified empirically against nuzantara_dev 2026-07-18. If
    # `phone` were left NULL, the trigger would silently overwrite our
    # `phone_normalized` value back to NULL, and the partial unique index
    # (scoped to `phone_normalized IS NOT NULL`) would never apply — the
    # idempotency this whole module depends on would silently vanish.
    # `normalize_phone_number` only strips non-digits (no 0/8->62 rewriting),
    # so feeding it the ALREADY-normalized digits is a safe no-op.
    # Phone is an identity-resolution key (Codex 2026-07-19 round 10, F12):
    # cooperative core lock before minting a new owner, held for the INSERT in
    # the SAME transaction (an xact advisory lock outside one releases at
    # statement end, silently disarming the protocol).
    async with conn.transaction():
        await lock_phone_cores(conn, normalized)
        row = await conn.fetchrow(
            """
            INSERT INTO clients
                (full_name, phone, phone_normalized, status, origin, created_by,
                 created_at, updated_at)
            VALUES ($1, $2, $2, $3, $4, $5, NOW(), NOW())
            ON CONFLICT (phone_normalized)
            WHERE (phone_normalized IS NOT NULL
                   AND deleted_at IS NULL
                   AND origin = 'wa-intake')
            DO NOTHING
            RETURNING id
            """,
            full_name,
            normalized,
            UNLABELED_STATUS,
            WA_INTAKE_ORIGIN,
            AUTOCREATE_CREATED_BY,
        )
    if row is not None:
        logger.info(
            "contact_autocreate: created client=%s from unknown WA sender phone",
            row["id"],
        )
        return ContactResolution(
            kind=KIND_CREATED,
            client_id=row["id"],
            phone_normalized=normalized,
            reason="auto-created minimal contact for unknown WA sender phone",
        )

    # Lost the race to a concurrent caller creating the SAME phone — the
    # partial unique index is the arbiter; re-select the winner.
    winner = await conn.fetchrow(
        """
        SELECT id FROM clients
        WHERE deleted_at IS NULL AND origin = $1 AND phone_normalized = $2
        """,
        WA_INTAKE_ORIGIN,
        normalized,
    )
    if winner is not None:
        return ContactResolution(
            kind=KIND_EXISTING,
            client_id=winner["id"],
            phone_normalized=normalized,
            reason="concurrent auto-create race — reused winning row",
        )

    logger.warning(
        "contact_autocreate: INSERT conflict but re-select found no row "
        "(unexpected race outcome) — abstaining"
    )
    return ContactResolution(
        kind=KIND_AMBIGUOUS,
        client_id=None,
        phone_normalized=normalized,
        reason="insert conflict but re-select found nothing — abstain, never guess",
    )
