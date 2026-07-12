"""LEVA 2 — auto-attach double-concordant (FASE 5C extension).

The intake decision matrix (``routing._classify_decision``) already produces
``AUTO_ATTACH`` when a document carries ONE strong identifier (passport / NPWP /
NIB / akta number) that resolves to exactly ONE CRM client, and the route stage
already records ``commit_gate.auto_attach_eligible``. But nothing CONSUMES that
flag: every proposal — AUTO_ATTACH included — is born ``review_pending`` and
waits for a human tap. This module arms the dormant flag (superscar #2,
"esiste ≠ armato": the capability was built but never activated).

The gate is deliberately STRICTER than ``auto_attach_eligible`` alone. A strong
document identifier tells you the document's SUBJECT; it does NOT tell you the
SENDER is that subject. To bypass the human we require a SECOND, independent
signal that agrees: the sender's phone must resolve to the SAME single client.
Two concordant signals (strong-id ⟂ phone) confirm the subject and dissolve the
"sender ≠ subject" risk that keeps phone-only matches in review forever.

Double-concordance gate — ALL must hold:
  1. decision == AUTO_ATTACH                         (single strong identifier)
  2. routing.client_id resolved (not None)           (a concrete target)
  3. sender phone resolves to EXACTLY ONE client     (not 0, not shared)
  4. that phone-client == routing.client_id          (the two signals AGREE)
  5. auto_attach_enabled() killswitch is ON          (default OFF)

When the gate passes, the commit reuses the existing FASE-5 writer machinery
(``plan_commit`` → ``execute_commit``) so the document lands in the SAME precise
CRM destination a human approve would have chosen, with the SAME P0#3 in-TX
revalidation (a stale/soft-deleted client blocks the plan and nothing writes).
The proposal advances ``review_pending`` → ``auto_routed`` (distinct from the
human ``routed`` terminal) and one ``intake_commit_audit`` row records it. Undo
is the existing ``rollback_commit`` — every auto-attach is reversible.

The Pro→Fly DELIVERY leg (placing the file in the client's Drive folder so it is
visible in kita) runs only AFTER the local commit succeeds and reuses the shared
``crm_delivery`` service. Headless delivery authenticates with the scoped
``X-CRM-Write-Key`` bridge; if the key is absent or Fly rejects it, the returned
verdict says so and never claims the document is in Kita.

PII / Symbiosis Law 2: everything here runs against the LOCAL Postgres only.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import asyncpg

from backend.services.intake import crm_delivery as intake_crm_delivery
from backend.services.intake import writer as intake_writer
from backend.services.intake.routing import _match_sender_phone, normalize_sender_phone

logger = logging.getLogger("zantara.intake.auto_attach")

# System actor recorded as ``committed_by`` on auto-attached commits — never a
# human email, so the audit trail and CRM doc clearly attribute the write.
AUTO_ATTACH_ACTOR = "system:auto-attach"
DIRECT_PHONE_AUTO_ATTACH_ACTOR = "system:auto-direct-phone"
NAMEID_AUTO_ATTACH_ACTOR = "system:auto-nameid"

# Terminal status for an auto-committed proposal (migration 234). Distinct from
# the human ``routed`` so reports / undo can target machine commits.
AUTO_ROUTED_STATUS = "auto_routed"

INTERNAL_PHONE_NUMBERS_ENV = "BZ_INTERNAL_PHONE_NUMBERS"
_INTERNAL_PREFIX_SUFFIX = "*"


def _normalize_internal_phone_token(value: object, *, allow_prefix: bool = False) -> str | None:
    normalized = normalize_sender_phone(value)
    if normalized or not allow_prefix:
        return normalized
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return None
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    return digits


def _load_internal_phone_config(raw: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    numbers: list[str] = []
    prefixes: list[str] = []
    for item in (raw or "").split(","):
        token = item.strip()
        if not token:
            continue
        is_prefix = token.endswith(_INTERNAL_PREFIX_SUFFIX)
        if is_prefix:
            token = token[: -len(_INTERNAL_PREFIX_SUFFIX)]
        normalized = _normalize_internal_phone_token(token, allow_prefix=is_prefix)
        if not normalized:
            continue
        if is_prefix:
            prefixes.append(normalized)
        else:
            numbers.append(normalized)
    return (tuple(numbers), tuple(prefixes))


INTERNAL_PHONE_NUMBERS, INTERNAL_PHONE_PREFIXES = _load_internal_phone_config(
    os.environ.get(INTERNAL_PHONE_NUMBERS_ENV)
)


def _internal_phone_config() -> tuple[frozenset[str], frozenset[str]]:
    env_numbers, env_prefixes = _load_internal_phone_config(
        os.environ.get(INTERNAL_PHONE_NUMBERS_ENV)
    )
    return (
        frozenset((*INTERNAL_PHONE_NUMBERS, *env_numbers)),
        frozenset((*INTERNAL_PHONE_PREFIXES, *env_prefixes)),
    )


def _is_internal_sender_phone(sender_phone: str | None) -> bool:
    normalized = normalize_sender_phone(sender_phone)
    if not normalized:
        return False
    numbers, prefixes = _internal_phone_config()
    return normalized in numbers or any(normalized.startswith(prefix) for prefix in prefixes)


def auto_attach_enabled() -> bool:
    """True only if INTAKE_AUTO_ATTACH_ENABLED is explicitly truthy (default OFF).

    Read at call time so ops / tests can flip it per-process. This is the LEVA-2
    killswitch and is INDEPENDENT of ``INTAKE_WRITER_ENABLED``: auto-attach
    ALSO requires the writer flag (it performs a real commit), so BOTH must be
    on for any autonomous CRM write. Default OFF = no autonomous writes.
    """
    return os.environ.get("INTAKE_AUTO_ATTACH_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def direct_phone_auto_attach_enabled() -> bool:
    """True only if direct-chat phone-only auto-catalog is explicitly armed.

    This is intentionally separate from ``INTAKE_AUTO_ATTACH_ENABLED``. Strong ID
    + phone concordance and direct phone-only concordance have different risk
    profiles, so ops can roll them out independently.
    """
    return os.environ.get("INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def nameid_auto_attach_enabled() -> bool:
    """True only if LEVA-3 name-id auto-catalog is explicitly armed (default OFF).

    Third independently-armable gate (after LEVA-2 phone concordance and the
    direct-phone variant): strong document identifier + document subject name,
    for sources that carry NO sender phone at all (Drive/Dropbox bulk — 38 of
    the first 48 eligible historical proposals had no phone to concord with).
    Separate flag because it is a different risk profile: both signals come
    from the document itself, verified against two different CRM fields.
    """
    return os.environ.get("INTAKE_NAMEID_AUTO_ATTACH_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def evaluate_concordance(
    conn: asyncpg.Connection,
    *,
    decision: str | None,
    client_id: int | None,
    sender_phone: str | None,
) -> dict[str, Any]:
    """Compute the double-concordance verdict (READ-ONLY — no writes).

    Returns a dict ``{concordant: bool, reason: str, phone_client_id: int|None,
    phone_match_count: int}``. Pure resolution logic so it can be unit-tested and
    logged without committing anything.
    """
    if decision != "AUTO_ATTACH":
        return {
            "concordant": False,
            "reason": f"decision={decision} (not AUTO_ATTACH)",
            "phone_client_id": None,
            "phone_match_count": 0,
        }
    if client_id is None:
        return {
            "concordant": False,
            "reason": "AUTO_ATTACH but routing.client_id unresolved",
            "phone_client_id": None,
            "phone_match_count": 0,
        }

    phone_matches = await _match_sender_phone(conn, sender_phone)
    n = len(phone_matches)
    if n == 0:
        return {
            "concordant": False,
            "reason": "sender phone matches no CRM client (strong-id only — needs human)",
            "phone_client_id": None,
            "phone_match_count": 0,
        }
    if n > 1:
        return {
            "concordant": False,
            "reason": f"sender phone shared by {n} clients (ambiguous — needs human)",
            "phone_client_id": None,
            "phone_match_count": n,
        }

    phone_client_id = phone_matches[0]["id"]
    if phone_client_id != client_id:
        return {
            "concordant": False,
            "reason": (
                f"signals DISAGREE: strong-id→client {client_id}, "
                f"phone→client {phone_client_id} (needs human)"
            ),
            "phone_client_id": phone_client_id,
            "phone_match_count": 1,
        }

    return {
        "concordant": True,
        "reason": "strong-id and sender phone agree on the same single client",
        "phone_client_id": phone_client_id,
        "phone_match_count": 1,
    }


def _as_reason_text(reason: Any) -> str:
    if isinstance(reason, dict):
        return str(reason.get("reason") or "")
    return str(reason or "")


def _has_subject_mismatch(reason: Any) -> bool:
    return isinstance(reason, dict) and bool(reason.get("sender_subject_mismatch"))


# Volumetric anti-funnel thresholds: a single sender phone that has produced many
# documents spanning many distinct doc types is a TRANSIT/AGENCY funnel (one phone
# forwarding for many people), NOT a single client. Lived example: a phone with 51
# documents across 8 doc types resolving to one client_id. Auto-attaching those
# mis-attributes N people's PII to 1 client. Defaults overridable via env.
_FUNNEL_MIN_DOCS = int(os.getenv("INTAKE_FUNNEL_MIN_DOCS", "8") or "8")
_FUNNEL_MIN_DISTINCT_TYPES = int(os.getenv("INTAKE_FUNNEL_MIN_DISTINCT_TYPES", "5") or "5")

# Names below this token-overlap ratio are treated as NOT the same person.
_NAME_MATCH_MIN_RATIO = float(os.getenv("INTAKE_NAME_MATCH_MIN_RATIO", "0.5") or "0.5")

_NAME_NOISE = re.compile(r"[^a-z0-9\s]+")


def _name_tokens(value: object) -> frozenset[str]:
    """Lowercased word-token set of a person name (diacritics/punct stripped).

    Returns tokens of length >= 2 so single-letter initials don't create false
    overlaps. Used for order-insensitive name comparison (Indonesian names and
    passport MRZ frequently reorder given/family parts).
    """
    if not value:
        return frozenset()
    text = _NAME_NOISE.sub(" ", str(value).strip().lower())
    return frozenset(t for t in text.split() if len(t) >= 2)


def _extracted_subject_name(stage_output: Any) -> str | None:
    """Pull the OCR-extracted subject name from a queue row's ``stage_output``.

    Path: ``stage_output.extract.fields.name`` (present for passport / kitas /
    birth_certificate; absent for ktp / bank_statement / payment_receipt). Returns
    None when missing — the gate then abstains because the subject is unverifiable.
    """
    so = intake_writer._as_dict(stage_output)
    if not so:
        return None
    fields = intake_writer._as_dict((intake_writer._as_dict(so.get("extract")) or {}).get("fields"))
    name = fields.get("name") if fields else None
    return str(name).strip() if name and str(name).strip() else None


def _name_concordant(extracted_name: object, client_name: object) -> tuple[bool, float]:
    """True when the document's subject name plausibly matches the client name.

    Order-insensitive token overlap (Jaccard-ish, normalized by the SMALLER set so
    a short CRM name still matches a longer full passport name). Returns
    (is_match, ratio). Empty either side → (False, 0.0): we cannot verify the
    subject, so we must NOT auto-attach.
    """
    a = _name_tokens(extracted_name)
    b = _name_tokens(client_name)
    if not a or not b:
        return (False, 0.0)
    overlap = len(a & b)
    ratio = overlap / min(len(a), len(b))
    return (ratio >= _NAME_MATCH_MIN_RATIO, ratio)


async def evaluate_direct_phone_concordance(
    conn: asyncpg.Connection,
    *,
    decision: str | None,
    client_id: int | None,
    doc_type: str | None,
    sender_phone: str | None,
    source_context: dict[str, Any] | None,
    reason: Any,
    extracted_name: str | None = None,
) -> dict[str, Any]:
    """Gate direct-chat phone-only proposals before autonomous cataloging.

    This does NOT change FASE-4's decision matrix: sender-phone-only remains a
    ``LINK_CANDIDATE``. The extra gate is a post-routing opt-in for the WA Mirror
    direct-chat case where the transport policy says the sender phone is the
    client identity, the doc type maps to a known Kita category, and a fresh phone
    lookup still resolves to the same single client.
    """
    if decision != "LINK_CANDIDATE":
        return {
            "concordant": False,
            "reason": f"decision={decision} (not LINK_CANDIDATE)",
            "phone_client_id": None,
            "phone_match_count": 0,
        }
    if client_id is None:
        return {
            "concordant": False,
            "reason": "LINK_CANDIDATE but routing.client_id unresolved",
            "phone_client_id": None,
            "phone_match_count": 0,
        }
    if not doc_type or doc_type not in intake_writer.DOCUMENT_CATEGORY_MAP:
        return {
            "concordant": False,
            "reason": f"doc_type={doc_type or 'missing'} has no Kita category",
            "phone_client_id": None,
            "phone_match_count": 0,
        }

    source_context = source_context or {}
    if source_context.get("chat_type") != "direct":
        return {
            "concordant": False,
            "reason": "not a WA direct-chat document",
            "phone_client_id": None,
            "phone_match_count": 0,
        }
    if source_context.get("routing_identity_policy") != "sender_phone_enabled":
        return {
            "concordant": False,
            "reason": "sender phone is not enabled as the routing identity policy",
            "phone_client_id": None,
            "phone_match_count": 0,
        }

    reason_text = _as_reason_text(reason)
    if not reason_text.startswith("sender phone"):
        return {
            "concordant": False,
            "reason": f"reason={reason_text or 'missing'} is not sender-phone based",
            "phone_client_id": None,
            "phone_match_count": 0,
        }
    if _has_subject_mismatch(reason):
        return {
            "concordant": False,
            "reason": "sender phone matched a forwarder, not the document subject",
            "phone_client_id": None,
            "phone_match_count": 0,
        }
    if _is_internal_sender_phone(sender_phone):
        return {
            "concordant": False,
            "reason": "sender phone is internal-number/operator relay (never client concordance)",
            "phone_client_id": None,
            "phone_match_count": 0,
        }

    phone_matches = await _match_sender_phone(conn, sender_phone)
    n = len(phone_matches)
    if n == 0:
        return {
            "concordant": False,
            "reason": "sender phone matches no current CRM client",
            "phone_client_id": None,
            "phone_match_count": 0,
        }
    if n > 1:
        return {
            "concordant": False,
            "reason": f"sender phone shared by {n} clients",
            "phone_client_id": None,
            "phone_match_count": n,
        }

    phone_client_id = phone_matches[0]["id"]
    if phone_client_id != client_id:
        return {
            "concordant": False,
            "reason": (
                f"signals DISAGREE: routing.client_id={client_id}, "
                f"phone→client {phone_client_id}"
            ),
            "phone_client_id": phone_client_id,
            "phone_match_count": 1,
        }

    # Anti-funnel volumetric guard. A sender phone that has produced many docs of
    # many distinct types is a transit/agency funnel forwarding for many people,
    # not a single client — even though it "resolves to one client_id". Keep these
    # in human review so N people's PII is not collapsed onto 1 client.
    funnel = await conn.fetchrow(
        """
        SELECT count(*) AS docs,
               count(DISTINCT p.routing->>'doc_type') AS distinct_types
        FROM document_routing_proposal p
        JOIN intake_queue q ON q.id = p.queue_id
        WHERE q.sender_phone IS NOT NULL
          AND regexp_replace(q.sender_phone, '[^0-9]', '', 'g')
              = regexp_replace($1, '[^0-9]', '', 'g')
          AND p.entity_resolution->>'decision' = 'LINK_CANDIDATE'
        """,
        sender_phone or "",
    )
    if funnel is not None and (
        funnel["docs"] >= _FUNNEL_MIN_DOCS
        and funnel["distinct_types"] >= _FUNNEL_MIN_DISTINCT_TYPES
    ):
        return {
            "concordant": False,
            "reason": (
                f"sender phone is a funnel/transit: {funnel['docs']} docs across "
                f"{funnel['distinct_types']} doc types (not a single client)"
            ),
            "phone_client_id": phone_client_id,
            "phone_match_count": 1,
        }

    # Name-concordance — "the phone proposes, the document content disposes".
    # The phone tells you the LATTER; the name extracted from the document tells
    # you the SUBJECT. Auto-attach only when both agree. If the document carries
    # no extractable name (ktp/bank_statement/payment_receipt) we cannot verify
    # the subject → abstain to review. This is the structural cure for the
    # operator-/funnel-forwarding mis-attribution class.
    client_name = await conn.fetchval(
        "SELECT full_name FROM clients WHERE id = $1 AND deleted_at IS NULL",
        phone_client_id,
    )
    name_ok, ratio = _name_concordant(extracted_name, client_name)
    if not name_ok:
        if not _name_tokens(extracted_name):
            why = "document carries no extractable subject name"
        elif not _name_tokens(client_name):
            why = "resolved client has no name to verify against"
        else:
            why = f"document subject name does not match client (overlap {ratio:.2f})"
        return {
            "concordant": False,
            "reason": f"name not concordant: {why}",
            "phone_client_id": phone_client_id,
            "phone_match_count": 1,
        }

    return {
        "concordant": True,
        "reason": (
            "direct WA sender phone resolves to the same single routed client "
            f"and document subject name matches (overlap {ratio:.2f})"
        ),
        "phone_client_id": phone_client_id,
        "phone_match_count": 1,
    }


async def evaluate_nameid_concordance(
    conn: asyncpg.Connection,
    *,
    decision: str | None,
    client_id: int | None,
    sender_phone: str | None,
    extracted_name: str | None,
) -> dict[str, Any]:
    """LEVA-3 gate: strong-id + document-subject-name concordance, no-phone sources only.

    Built for sources where the phone leg of LEVA 2 is structurally absent
    (Drive/Dropbox bulk, scans with no transport sender). Two independent
    signals are still required: the document's strong identifier resolves to
    exactly ONE client (decision==AUTO_ATTACH) AND the OCR-extracted subject
    name matches that client's CRM name (order-insensitive token overlap,
    same ``_name_concordant`` the direct-phone gate uses).

    A sender phone that resolves to ANY client makes this gate abstain:
    every present-phone verdict (agree / disagree / shared) belongs to LEVA 2,
    and name evidence must never overrule a phone signal. READ-ONLY.
    """
    if decision != "AUTO_ATTACH":
        return {"concordant": False, "reason": f"decision={decision} (not AUTO_ATTACH)"}
    if client_id is None:
        return {"concordant": False, "reason": "AUTO_ATTACH but routing.client_id unresolved"}

    phone_matches = await _match_sender_phone(conn, sender_phone)
    if phone_matches:
        return {
            "concordant": False,
            "reason": (
                f"sender phone resolves to {len(phone_matches)} CRM client(s) — "
                "phone concordance (LEVA 2) owns this case; name evidence never overrules it"
            ),
        }

    client_name = await conn.fetchval(
        "SELECT full_name FROM clients WHERE id = $1 AND deleted_at IS NULL",
        client_id,
    )
    name_ok, ratio = _name_concordant(extracted_name, client_name)
    if not name_ok:
        if not _name_tokens(extracted_name):
            why = "document carries no extractable subject name"
        elif not _name_tokens(client_name):
            why = "resolved client has no name to verify against"
        else:
            why = f"document subject name does not match client (overlap {ratio:.2f})"
        return {"concordant": False, "reason": f"name not concordant: {why}"}

    return {
        "concordant": True,
        "reason": (
            "no phone signal exists for this source; strong-id resolves to a single "
            f"client and document subject name matches (overlap {ratio:.2f})"
        ),
    }


async def try_auto_attach(
    proposal: dict[str, Any] | asyncpg.Record,
    pool: asyncpg.Pool,
    *,
    sender_phone: str | None,
) -> dict[str, Any]:
    """Attempt a double-concordant auto-attach for one review_pending proposal.

    Idempotent + safe-by-default. Returns a verdict dict; ``committed`` is True
    ONLY when a real CRM write happened. No-ops (returning committed=False with a
    reason) when: the killswitch is off, the writer flag is off, the gate fails,
    the proposal is no longer review_pending, or the plan is blocked by P0#3
    revalidation. NEVER raises on a benign skip — only a genuine DB/commit fault
    propagates (so the worker's retry/DLQ machinery sees it).
    """
    p = dict(proposal)
    proposal_id = p["id"]
    routing = intake_writer._as_dict(p.get("routing"))
    entity_resolution = intake_writer._as_dict(p.get("entity_resolution"))
    decision = entity_resolution.get("decision") or routing.get("decision")
    client_id = routing.get("client_id")

    if not auto_attach_enabled():
        return {"committed": False, "skipped": "killswitch_off", "proposal_id": proposal_id}
    if not intake_writer.writer_enabled():
        # Auto-attach performs a REAL commit; without the writer flag it would be
        # a dry-run that never advances — pointless and confusing. Treat as off.
        return {"committed": False, "skipped": "writer_off", "proposal_id": proposal_id}

    async with pool.acquire() as conn:
        verdict = await evaluate_concordance(
            conn, decision=decision, client_id=client_id, sender_phone=sender_phone
        )
        if not verdict["concordant"]:
            logger.info(
                "auto_attach.skip proposal=%s reason=%s", proposal_id, verdict["reason"]
            )
            return {
                "committed": False,
                "skipped": "not_concordant",
                "reason": verdict["reason"],
                "proposal_id": proposal_id,
            }

        # Gate passed — commit atomically, advancing review_pending → auto_routed.
        async with conn.transaction():
            # Re-read FOR UPDATE so a human who claimed/approved it meanwhile wins
            # the race (we must NOT auto-commit a proposal already being handled).
            locked = await conn.fetchrow(
                """
                SELECT id, queue_id, doc_index, pipeline_version, status,
                       entity_resolution, routing, commit_gate
                FROM document_routing_proposal
                WHERE id = $1
                FOR UPDATE
                """,
                proposal_id,
            )
            if locked is None:
                return {"committed": False, "skipped": "not_found", "proposal_id": proposal_id}
            if locked["status"] != "review_pending":
                return {
                    "committed": False,
                    "skipped": "not_review_pending",
                    "status": locked["status"],
                    "proposal_id": proposal_id,
                }

            plan = await intake_writer.plan_commit(
                locked, conn, committed_by=AUTO_ATTACH_ACTOR
            )
            if plan.blocked:
                # P0#3 revalidation failed (e.g. client soft-deleted since routing).
                # Leave the proposal review_pending for a human; nothing written.
                logger.warning(
                    "auto_attach.blocked proposal=%s reasons=%s",
                    proposal_id, plan.block_reasons,
                )
                # execute_commit on a blocked plan writes only the forensic audit row.
                result = await intake_writer.execute_commit(plan, conn, dry_run=False)
                return {
                    "committed": False,
                    "skipped": "plan_blocked",
                    "block_reasons": plan.block_reasons,
                    "proposal_id": proposal_id,
                    "result": result.to_dict(),
                }

            result = await intake_writer.execute_commit(
                plan,
                conn,
                dry_run=False,
                advance_from="review_pending",
                advance_to=AUTO_ROUTED_STATUS,
            )

    committed = result.outcome == "committed"
    delivery = None
    if committed:
        delivery = await intake_crm_delivery.deliver_committed_to_crm(
            pool=pool,
            queue_id=plan.queue_id,
            plan=plan,
            result=result,
        )
    logger.info(
        "auto_attach.%s proposal=%s client=%s doc=%s phone_client=%s",
        "COMMITTED" if committed else result.outcome,
        proposal_id, client_id, result.doc_id, verdict["phone_client_id"],
    )
    return {
        "committed": committed,
        "outcome": result.outcome,
        "proposal_id": proposal_id,
        "client_id": client_id,
        "doc_id": result.doc_id,
        "status": AUTO_ROUTED_STATUS if committed else None,
        "delivery": delivery or {"status": "not_committed"},
        "result": result.to_dict(),
    }


async def try_direct_phone_auto_attach(
    proposal: dict[str, Any] | asyncpg.Record,
    pool: asyncpg.Pool,
    *,
    sender_phone: str | None,
    source_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attempt opt-in auto-catalog for a direct WA phone-only LINK_CANDIDATE."""
    p = dict(proposal)
    proposal_id = p["id"]

    if not direct_phone_auto_attach_enabled():
        return {
            "committed": False,
            "skipped": "direct_phone_killswitch_off",
            "proposal_id": proposal_id,
        }
    if not intake_writer.writer_enabled():
        return {"committed": False, "skipped": "writer_off", "proposal_id": proposal_id}

    async with pool.acquire() as conn:
        async with conn.transaction():
            locked = await conn.fetchrow(
                """
                SELECT p.id, p.queue_id, p.doc_index, p.pipeline_version, p.status,
                       p.entity_resolution, p.routing, p.commit_gate,
                       q.sender_phone, q.source_context, q.stage_output
                FROM document_routing_proposal p
                JOIN intake_queue q ON q.id = p.queue_id
                WHERE p.id = $1
                FOR UPDATE
                """,
                proposal_id,
            )
            if locked is None:
                return {"committed": False, "skipped": "not_found", "proposal_id": proposal_id}
            if locked["status"] != "review_pending":
                return {
                    "committed": False,
                    "skipped": "not_review_pending",
                    "status": locked["status"],
                    "proposal_id": proposal_id,
                }

            routing = intake_writer._as_dict(locked["routing"])
            entity_resolution = intake_writer._as_dict(locked["entity_resolution"])
            locked_context = intake_writer._as_dict(
                locked["source_context"] if source_context is None else source_context
            )
            verdict = await evaluate_direct_phone_concordance(
                conn,
                decision=entity_resolution.get("decision") or routing.get("decision"),
                client_id=routing.get("client_id"),
                doc_type=routing.get("doc_type"),
                sender_phone=sender_phone or locked["sender_phone"],
                source_context=locked_context,
                reason=entity_resolution.get("reason"),
                extracted_name=_extracted_subject_name(locked["stage_output"]),
            )
            if not verdict["concordant"]:
                logger.info(
                    "direct_phone_auto_attach.skip proposal=%s reason=%s",
                    proposal_id,
                    verdict["reason"],
                )
                return {
                    "committed": False,
                    "skipped": "not_concordant",
                    "reason": verdict["reason"],
                    "proposal_id": proposal_id,
                }

            plan = await intake_writer.plan_commit(
                locked, conn, committed_by=DIRECT_PHONE_AUTO_ATTACH_ACTOR
            )
            if plan.blocked:
                logger.warning(
                    "direct_phone_auto_attach.blocked proposal=%s reasons=%s",
                    proposal_id,
                    plan.block_reasons,
                )
                result = await intake_writer.execute_commit(plan, conn, dry_run=False)
                return {
                    "committed": False,
                    "skipped": "plan_blocked",
                    "block_reasons": plan.block_reasons,
                    "proposal_id": proposal_id,
                    "result": result.to_dict(),
                }

            result = await intake_writer.execute_commit(
                plan,
                conn,
                dry_run=False,
                advance_from="review_pending",
                advance_to=AUTO_ROUTED_STATUS,
            )

    committed = result.outcome == "committed"
    delivery = None
    if committed:
        delivery = await intake_crm_delivery.deliver_committed_to_crm(
            pool=pool,
            queue_id=plan.queue_id,
            plan=plan,
            result=result,
        )
    logger.info(
        "direct_phone_auto_attach.%s proposal=%s client=%s doc=%s phone_client=%s",
        "COMMITTED" if committed else result.outcome,
        proposal_id,
        routing.get("client_id"),
        result.doc_id,
        verdict["phone_client_id"],
    )
    return {
        "committed": committed,
        "outcome": result.outcome,
        "proposal_id": proposal_id,
        "client_id": routing.get("client_id"),
        "doc_id": result.doc_id,
        "status": AUTO_ROUTED_STATUS if committed else None,
        "delivery": delivery or {"status": "not_committed"},
        "result": result.to_dict(),
    }


async def try_nameid_auto_attach(
    proposal: dict[str, Any] | asyncpg.Record,
    pool: asyncpg.Pool,
) -> dict[str, Any]:
    """Attempt opt-in LEVA-3 auto-catalog for a no-phone AUTO_ATTACH proposal.

    Same idempotent, safe-by-default contract as :func:`try_auto_attach`:
    ``committed`` is True ONLY when a real CRM write happened; every benign
    skip returns a reason instead of raising; the FOR UPDATE re-read means a
    human (or LEVA 2) that handled the proposal meanwhile wins the race; a
    blocked plan writes only the forensic audit row and leaves the proposal
    in review. Commits are attributed to ``system:auto-nameid`` and remain
    reversible via the existing ``rollback_commit``.
    """
    p = dict(proposal)
    proposal_id = p["id"]

    if not nameid_auto_attach_enabled():
        return {
            "committed": False,
            "skipped": "nameid_killswitch_off",
            "proposal_id": proposal_id,
        }
    if not intake_writer.writer_enabled():
        return {"committed": False, "skipped": "writer_off", "proposal_id": proposal_id}

    async with pool.acquire() as conn:
        async with conn.transaction():
            locked = await conn.fetchrow(
                """
                SELECT p.id, p.queue_id, p.doc_index, p.pipeline_version, p.status,
                       p.entity_resolution, p.routing, p.commit_gate,
                       q.sender_phone, q.stage_output
                FROM document_routing_proposal p
                JOIN intake_queue q ON q.id = p.queue_id
                WHERE p.id = $1
                FOR UPDATE
                """,
                proposal_id,
            )
            if locked is None:
                return {"committed": False, "skipped": "not_found", "proposal_id": proposal_id}
            if locked["status"] != "review_pending":
                return {
                    "committed": False,
                    "skipped": "not_review_pending",
                    "status": locked["status"],
                    "proposal_id": proposal_id,
                }

            routing = intake_writer._as_dict(locked["routing"])
            entity_resolution = intake_writer._as_dict(locked["entity_resolution"])
            verdict = await evaluate_nameid_concordance(
                conn,
                decision=entity_resolution.get("decision") or routing.get("decision"),
                client_id=routing.get("client_id"),
                sender_phone=locked["sender_phone"],
                extracted_name=_extracted_subject_name(locked["stage_output"]),
            )
            if not verdict["concordant"]:
                logger.info(
                    "nameid_auto_attach.skip proposal=%s reason=%s",
                    proposal_id,
                    verdict["reason"],
                )
                return {
                    "committed": False,
                    "skipped": "not_concordant",
                    "reason": verdict["reason"],
                    "proposal_id": proposal_id,
                }

            plan = await intake_writer.plan_commit(
                locked, conn, committed_by=NAMEID_AUTO_ATTACH_ACTOR
            )
            if plan.blocked:
                logger.warning(
                    "nameid_auto_attach.blocked proposal=%s reasons=%s",
                    proposal_id,
                    plan.block_reasons,
                )
                result = await intake_writer.execute_commit(plan, conn, dry_run=False)
                return {
                    "committed": False,
                    "skipped": "plan_blocked",
                    "block_reasons": plan.block_reasons,
                    "proposal_id": proposal_id,
                    "result": result.to_dict(),
                }

            result = await intake_writer.execute_commit(
                plan,
                conn,
                dry_run=False,
                advance_from="review_pending",
                advance_to=AUTO_ROUTED_STATUS,
            )

    committed = result.outcome == "committed"
    delivery = None
    if committed:
        delivery = await intake_crm_delivery.deliver_committed_to_crm(
            pool=pool,
            queue_id=plan.queue_id,
            plan=plan,
            result=result,
        )
    logger.info(
        "nameid_auto_attach.%s proposal=%s client=%s doc=%s",
        "COMMITTED" if committed else result.outcome,
        proposal_id,
        routing.get("client_id"),
        result.doc_id,
    )
    return {
        "committed": committed,
        "outcome": result.outcome,
        "proposal_id": proposal_id,
        "client_id": routing.get("client_id"),
        "doc_id": result.doc_id,
        "status": AUTO_ROUTED_STATUS if committed else None,
        "delivery": delivery or {"status": "not_committed"},
        "result": result.to_dict(),
    }
