"""VisaEngineRepository — bitemporal read/write substrate for signed rule packs.

Persistence for migration 250's two tables (``backend/db/migrations_v2/
250_visa_engine_core.sql``): ``visa_rule_packs`` (the immutable, Ed25519-signed
pack envelope) and ``visa_ruleset_activations`` (the bitemporal activation
ledger — which pack is "active" is a pure range-containment join on two
independent clocks, ``legal_period`` and ``system_period``; the table's GiST
``EXCLUDE`` constraint makes overlapping activations impossible at the DB
level, so there is never more than one active pack per
``(environment, jurisdiction, decision_domain)`` at any
``(effective_at, observed_at)``).

SCOPE — this module is pure data access, nothing else (Golden Rule #7,
data/logic separation):

* :meth:`VisaEngineRepository.load_active_rule_pack` reconstructs the exact
  raw wire envelope shape :func:`backend.services.visa_engine.bundle.
  verify_rule_pack` expects — ``{"canonicalization", "protected", "payload",
  "payload_sha256", "signature"}`` — straight from the DB columns, so a
  caller can pass the return value directly to that function. **It never
  calls ``verify_rule_pack`` itself and never inspects ``payload`` for
  business meaning** — cryptographic verification and rule evaluation are
  the service layer's job, not the repository's.
* :meth:`insert_rule_pack` is a pure, single-row INSERT into the
  append-only ``visa_rule_packs`` table (the DB's
  ``visa_rule_packs_immutable`` trigger rejects any later UPDATE/DELETE —
  this repository never attempts either).

PR4 SCOPE — no activation WRITER (2026-07-19): a fourth cross-family
adversarial round found that the activation WRITER (the bitemporal
supersession — closing every still-open, legal-period-overlapping prior
activation for a triple and inserting the new one at one shared instant) is
**un-closeable** at the layer this repository lives in. The raw-SQL
``system_period``-timestamp backdating and partial-overlap bypass this
method used to guard against (a Python method's close-then-insert pair,
plus migration 250's ``BEFORE INSERT``/``BEFORE UPDATE`` triggers) cannot
give the same caller-independent atomicity guarantee a single
``SECURITY DEFINER`` DB function can: that function —
``visa_activate_rule_pack(...)`` — plus a GRANT model that ``REVOKE``s
direct ``INSERT``/``UPDATE``/``DELETE`` on ``visa_ruleset_activations``
from the runtime role and grants only ``EXECUTE`` on the function, is
**STEP 6**.
This module therefore ships **no activation writer at all** in PR4 — only
the read substrate (:meth:`load_active_rule_pack`) and the signed-pack
insert (:meth:`insert_rule_pack`) above. What it DOES ship from day 1 are
migration 250's ledger structural triggers
(``reject_visa_activation_insert`` — scope/hash-chain/sequence-monotonicity
binding — and ``reject_visa_activation_mutation`` — append-only-with-close):
these are exactly the caller-independent guards STEP-6's ``SECURITY
DEFINER`` function will itself run under, so they are correct and
load-bearing defense-in-depth from the moment this migration lands, not
something STEP-6 introduces later. Any INSERT into
``visa_ruleset_activations`` before STEP-6 ships (e.g. from a script or a
test) must go in raw, through those same triggers — this repository offers
no wrapper for it, by design.

Envelope reconstruction detail: ``visa_rule_packs.protected_header`` and
``.payload`` are stored as JSONB and come back from asyncpg either as a
``dict`` (when the pool has a jsonb type codec registered — the production
pool built by ``app/setup/service_initializer.py``) or as a raw JSON ``str``
(a pool without that codec, e.g. a plain ``asyncpg.create_pool()`` in tests).
:func:`_jsonb_to_dict` below normalises both cases — the same defensive
pattern already used by ``services/compliance/alert_repository.py``'s
``_row_to_alert`` and ``services/intel/dossier_repository.py``. For the
inverse direction (INSERT), this repository follows that same sibling
convention: it calls ``json.dumps`` itself and casts the parameter with
``::text::jsonb`` in SQL (NOT a bare ``::jsonb`` — see the "PR4 FIX-FIRST
note" below for why the extra ``::text`` hop is load-bearing against a
codec-registered pool), rather than relying on a codec being present on
whatever pool it is handed — this is what makes the repository correct
against *either* pool shape, including the codec-less throwaway pool this
package's own tests build (see ``backend/tests/services/visa_engine/
test_repository.py``).

``payload_sha256``/``signature`` are ``BYTEA`` columns (raw 32/64 bytes);
the signed-envelope wire shape (``models.RulePack.payload_sha256``: a
64-char lowercase hex string per ``$defs/Sha256Hex``; ``.signature``: an
86-char unpadded base64url string per ``$defs/Ed25519Signature``) is a wire
*encoding* of those same bytes, not a different value — reconstruction is a
pure encode, never a re-derivation.

``canonicalization`` has no DB column: ``models.RulePack.canonicalization``
is a ``Literal["RFC8785"]`` (the only value the schema ever allows), so the
repository hardcodes it when reconstructing the envelope rather than storing
a column that could only ever hold one value.

PR4 FIX-FIRST note (2026-07-19, P0-1): ``insert_rule_pack`` casts its two
JSONB parameters as ``$N::text::jsonb``, NOT ``$N::text``/``$N::jsonb``
directly. Empirically proven: under the production pool's registered jsonb
codec (``set_type_codec("jsonb", encoder=json.dumps, ...)``,
``backend/app/core/database.py``'s ``init_db_connection``), asyncpg's
codec ALSO runs on a parameter cast with ``::jsonb`` — so a Python ``str``
that is already a JSON-encoded object (``json.dumps(dict(...))``, this
module's own convention) gets encoded a SECOND time by the codec, landing
in the column as a JSONB *string* (``jsonb_typeof() = 'string'``) whose
content happens to be more JSON, not a JSONB *object*. Casting through
``::text::jsonb`` forces Postgres to parse the parameter as literal
``text`` first (bypassing the codec's jsonb encode path entirely) and only
then cast that text to ``jsonb`` — this stores a genuine object on BOTH the
codec-registered production pool and a codec-less pool (the one this
package's own tests build), which is the actual invariant this repository
needs: correct against either pool shape. Migration 250's two new
``jsonb_typeof(...) = 'object'`` CHECK constraints on ``visa_rule_packs``
are the structural backstop for this — a future regression back to bare
``::jsonb`` now fails loudly at INSERT time instead of silently degrading
every downstream ``bundle.verify_rule_pack`` call.
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID

import asyncpg

from backend.db.base_repository import BaseRepository

logger = logging.getLogger(__name__)

#: A raw, JSON-safe value. Defined locally — no importable shared home in
#: this package (see ``bundle.py``'s module docstring, PR2b adaptation note,
#: and ``fact_registry.py``'s identical local definition).
JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]

#: The two constants every row of both tables is pinned to (migration 250's
#: CHECK constraints; also ``Literal["ID"]``/``Literal["IMMIGRATION_VISA"]``
#: on ``models.RulePackPayload`` — see ``bundle.py``'s module docstring for
#: why a mismatch is schema-structurally impossible upstream of here).
#: :meth:`VisaEngineRepository.load_active_rule_pack` needs them as literal
#: SQL filter values (a WHERE clause cannot lean on a column DEFAULT the way
#: an INSERT can) — belt-and-suspenders scoping even though every row is
#: constitutionally ``ID``/``IMMIGRATION_VISA`` today (see that method's own
#: docstring, "P0-2 latent"). PR4 ships no activation WRITER (deferred to
#: STEP 6 — see the module docstring's "PR4 SCOPE" note above), so these
#: constants no longer also double as a lock-key/scope-derivation input here.
_JURISDICTION = "ID"
_DECISION_DOMAIN = "IMMIGRATION_VISA"


def _b64url_nopad_encode(raw: bytes) -> str:
    """Base64url-encode ``raw`` with NO padding.

    This is the exact wire shape ``bundle.py``'s
    ``_decode_base64url_no_padding`` requires for the envelope's
    ``signature`` field: the unpadded base64url alphabet
    ``[A-Za-z0-9_-]``, no ``=`` characters. ``base64.urlsafe_b64encode``
    always pads to a multiple of 4; ``.rstrip("=")`` removes it (safe here
    because unpadded base64url has no other legitimate use of ``=``).
    """
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _jsonb_to_dict(value: Any) -> dict[str, JsonValue]:
    """Normalise a JSONB column read-back to a plain ``dict``.

    See the module docstring's "Envelope reconstruction detail" section —
    asyncpg returns a jsonb value as ``dict`` (codec-registered pool) or
    ``str`` (no codec); this makes the repository correct against either.
    """
    if isinstance(value, str):
        return json.loads(value)
    return value


class VisaEngineRepository(BaseRepository):
    """Data access for ``visa_rule_packs`` + ``visa_ruleset_activations``.

    Pure persistence: no signature verification, no rule evaluation, no
    business-meaning inspection of ``payload``. Callers (the PR2b/PR4
    service layer) own everything downstream of what this class returns.

    PR4 ships only the two methods below (read + signed-pack insert) — no
    activation writer. See the module docstring's "PR4 SCOPE — no
    activation WRITER" note for why: the bitemporal supersession is
    deferred to STEP 6's ``SECURITY DEFINER`` DB function.
    """

    # ── Bitemporal read ──────────────────────────────────────────────────

    async def load_active_rule_pack(
        self,
        *,
        environment: str,
        effective_at: datetime,
        observed_at: datetime,
    ) -> dict[str, JsonValue] | None:
        """Return the single active pack's raw envelope, or ``None``.

        "Active" is a pure range-containment join against the activation
        ledger (migration 250's own doc comment): the activation whose
        ``legal_period`` contains ``effective_at`` (the legally-in-force
        clock) AND whose ``system_period`` contains ``observed_at`` (the
        "what did the system consider current at that instant" clock),
        scoped to ``environment`` AND (belt-and-suspenders, P0-2 latent) the
        module's own ``_JURISDICTION``/``_DECISION_DOMAIN`` constants —
        every row is ``ID``/``IMMIGRATION_VISA`` today (both tables' own
        CHECK constraints pin it), so this filter is currently a no-op in
        practice, but it makes the query total rather than relying on that
        invariant holding silently forever. ``ORDER BY ... LIMIT 1`` is
        defensive belt-and-suspenders — the GiST ``EXCLUDE`` constraint on
        ``visa_ruleset_activations`` already guarantees at most one row can
        ever match a single ``(effective_at, observed_at)`` point for a
        given ``(environment, jurisdiction, decision_domain)``: two matching
        rows would necessarily have overlapping ``legal_period`` (both
        contain ``effective_at``) AND overlapping ``system_period`` (both
        contain ``observed_at``), which the EXCLUDE constraint forbids.

        Returns the raw wire envelope dict — the EXACT shape
        ``bundle.verify_rule_pack`` expects as its ``raw_envelope``
        argument (``canonicalization``/``protected``/``payload``/
        ``payload_sha256``/``signature``) — reconstructed from
        ``protected_header``/``payload`` (JSONB), ``payload_sha256``/
        ``signature`` (BYTEA), per the module docstring. This method does
        NOT call ``verify_rule_pack`` — that is the service layer's job.
        """
        row = await self.fetchrow_safe(
            """
            SELECT
                p.protected_header,
                p.payload,
                p.payload_sha256,
                p.signature
            FROM visa_ruleset_activations a
            JOIN visa_rule_packs p ON p.id = a.rule_pack_id
            WHERE a.environment = $1
              AND a.jurisdiction = $2
              AND a.decision_domain = $3
              AND a.legal_period @> $4::timestamptz
              AND a.system_period @> $5::timestamptz
            ORDER BY a.created_at DESC
            LIMIT 1
            """,
            environment,
            _JURISDICTION,
            _DECISION_DOMAIN,
            effective_at,
            observed_at,
        )
        if row is None:
            return None

        return {
            "canonicalization": "RFC8785",
            "protected": _jsonb_to_dict(row["protected_header"]),
            "payload": _jsonb_to_dict(row["payload"]),
            "payload_sha256": row["payload_sha256"].hex(),
            "signature": _b64url_nopad_encode(row["signature"]),
        }

    # ── Signed pack insert (append-only) ────────────────────────────────

    async def insert_rule_pack(
        self,
        *,
        id: UUID,
        environment: str,
        sequence: int,
        pack_version: str,
        engine_contract_version: str,
        engine_min_version: str,
        engine_max_version: str,
        legal_period: asyncpg.Range,
        protected_header: Mapping[str, JsonValue],
        payload: Mapping[str, JsonValue],
        payload_sha256: bytes,
        previous_payload_sha256: bytes | None,
        signature: bytes,
        signing_key_id: str,
        signed_at: datetime,
    ) -> None:
        """INSERT one signed pack row. Pure insert — never UPDATE/DELETE.

        ``jurisdiction``/``decision_domain`` are omitted from the column
        list and take their table DEFAULTs (``'ID'``/``'IMMIGRATION_VISA'``
        — migration 250). ``legal_period`` must be an ``asyncpg.Range``
        with ``lower_inc=True, upper_inc=False`` (the DB CHECK constraint
        enforces exactly the ``'[)'`` shape — see migration 250's
        ``visa_rule_packs_legal_period_check``). The caller is expected to
        have already verified the pack (this class never verifies) — this
        method trusts its arguments and only persists them.

        ``protected_header``/``payload`` are cast ``$N::text::jsonb``, not
        a bare ``$N::jsonb`` — see this module's docstring "PR4 FIX-FIRST
        note" (P0-1) for the empirically-proven reason: a bare ``::jsonb``
        double-encodes under the production pool's jsonb codec, silently
        storing a JSONB *string* instead of an *object*.
        """
        await self.execute_safe(
            """
            INSERT INTO visa_rule_packs (
                id, environment, sequence, pack_version,
                engine_contract_version, engine_min_version, engine_max_version,
                legal_period, protected_header, payload, payload_sha256,
                previous_payload_sha256, signature, signing_key_id, signed_at
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7,
                $8, $9::text::jsonb, $10::text::jsonb, $11,
                $12, $13, $14, $15
            )
            """,
            id,
            environment,
            sequence,
            pack_version,
            engine_contract_version,
            engine_min_version,
            engine_max_version,
            legal_period,
            json.dumps(dict(protected_header)),
            json.dumps(dict(payload)),
            payload_sha256,
            previous_payload_sha256,
            signature,
            signing_key_id,
            signed_at,
        )
