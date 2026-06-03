"""Real stage-handler dispatcher for the document-intake worker (FASE 3 integration).

Wires the FASE-2 worker (``services/intake/worker.py``) to the FASE-3 real stage
implementations:

  * ``classify`` / ``ocr`` -> :mod:`backend.services.intake.classify`
    (preprocess + local OCR via qwen3-vl, then keyword classification).
  * ``extract``            -> :func:`backend.services.intake.extract.extract_stage`
    (local SEA-LION field extraction, Maybe pattern).
  * ``validate``           -> :func:`backend.services.intake.validate_rules.validate_stage`
    (deterministic, no LLM).
  * ``route``              -> :func:`_route_stage_stub` (FASE-4 placeholder: writes
    ONE ``document_routing_proposal`` row, ZERO CRM writes).

Contract (FASE-2 worker, ``worker.py``):
    The worker calls ``stage_handler(job, stage)`` async, and merges the returned
    dict into ``intake_queue.stage_output[stage]``. The claimed ``job`` dict only
    carries ``id / attempts / max_attempts / source / source_ref / _inbound_status``
    -- it does NOT include the accumulated ``stage_output``. The classify handler
    (``build_stage_handler``) already works around this by fetching the blob by
    ``job['id']``; the ``extract`` and ``validate`` handlers, however, read prior
    stages out of ``job['stage_output']``. So this dispatcher FETCHES the live
    ``stage_output`` from ``intake_queue`` by ``job['id']`` and injects it into the
    job before delegating, and adapts the classify-stage OCR shape
    (``ocr_text_per_page`` = list of per-page dicts) into the list[str] that
    :func:`extract_stage` expects.

Stage-machine order note (no worker change required)
----------------------------------------------------
The FASE-2 stage machine maps statuses ``pending -> classify``, ``processing ->
ocr``, ``ocr -> extract`` ... so the stage NAMED ``classify`` runs FIRST and the
stage NAMED ``ocr`` runs second. That ordering is *semantically fine* because the
real ``classify`` stage performs the heavy OCR + classification in a single pass
(re-OCR at the ``ocr`` stage would double the local-VLM cost), and the ``ocr``
stage is a cheap idempotent passthrough that surfaces the already-computed OCR
payload. The logical pipeline is therefore OCR(+classify) -> extract -> validate
-> route, achieved WITHOUT renaming any status (the ``chk_iq_status`` CHECK
constraint stays untouched, no migration needed).

Metrics
-------
The worker already inserts exactly one ``intake_stage_metrics`` row per stage
(``model='stub-passthrough'``, generic ok/latency). To avoid DUPLICATE latency
rows we do NOT write a second metrics row here; instead each handler embeds the
REAL ``model`` + ``confidence`` into its returned payload (persisted verbatim in
``stage_output``), so the true model/confidence are auditable per stage. (A future
worker tweak can lift ``payload['_metric']`` into the metrics row; the convention
is provided below but the worker is not modified in this FASE.)

PII / Symbiosis Law 2: every model call is to localhost Ollama. ZERO cloud, ZERO
CRM writes. The only structured side effect is one ``document_routing_proposal``
row (read-only proposal; FASE-5 HITL decides actual routing).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

import asyncpg

from backend.services.intake import classify as _classify
from backend.services.intake.extract import (
    EXTRACTION_MODEL_LABEL,
    canonical_doc_type,
    extract_stage,
)
from backend.services.intake.validate_rules import validate_stage

logger = logging.getLogger("zantara.intake.stages")

StageHandler = Callable[[dict, str], Awaitable[dict]]

# Stages whose real handler reads the accumulated stage_output (which the worker
# does NOT include in the claimed job dict) -> we hydrate it from the DB first.
_NEEDS_STAGE_OUTPUT: frozenset[str] = frozenset({"extract", "validate"})


async def _fetch_stage_output(pool: asyncpg.Pool, queue_id: int) -> dict[str, Any]:
    """Load the live ``stage_output`` JSONB for a queue row (prior stages' output)."""
    row = await pool.fetchrow(
        "SELECT stage_output FROM intake_queue WHERE id = $1", queue_id
    )
    if row is None or row["stage_output"] is None:
        return {}
    so = row["stage_output"]
    # asyncpg returns jsonb as str unless a codec is registered on the pool.
    if isinstance(so, str):
        try:
            return json.loads(so)
        except json.JSONDecodeError:
            return {}
    return dict(so)


def _ocr_text_per_page_as_strings(stage_output: dict[str, Any]) -> list[str]:
    """Flatten classify's ``ocr_text_per_page`` (list of dicts) into list[str].

    classify writes ``ocr_text_per_page`` as ``[{"page", "text", "confidence",
    ...}]``; :func:`extract_stage` expects per-page plain strings. We project the
    ``text`` field, preserving page order.
    """
    classify_out = stage_output.get("classify") or {}
    pages = classify_out.get("ocr_text_per_page") or []
    out: list[str] = []
    for p in pages:
        if isinstance(p, dict):
            out.append(str(p.get("text") or ""))
        else:
            out.append(str(p or ""))
    return out


async def _route_stage_stub(pool: asyncpg.Pool, job: dict) -> dict:
    """FASE-4 placeholder: write ONE ``document_routing_proposal`` row.

    This is the ONLY structured output of the whole pipeline at this FASE. It is a
    read-only *proposal* (status ``review_pending``): FASE-5 HITL / FASE-4 routing
    will decide whether to act on it. ZERO CRM writes — we never touch clients /
    practices / documents here.

    The proposal carries the resolved doc_type + extracted fields + the validate
    verdict as evidence, but takes NO routing decision (entity_resolution / routing
    are empty placeholders; commit_gate records that this is a FASE-3 stub).
    """
    queue_id = job["id"]
    so = await _fetch_stage_output(pool, queue_id)
    classify_out = so.get("classify") or {}
    extract_out = so.get("extract") or {}
    validate_out = so.get("validate") or {}

    doc_type = classify_out.get("doc_type") or extract_out.get("doc_type") or "unknown"
    # routing_key is UNIQUE; make it idempotent per (queue_id, doc_index).
    routing_key = f"intake:{queue_id}:0:{job.get('pipeline_version', 'v1')}"

    proposal = {
        "doc_type": doc_type,
        "type_confidence": classify_out.get("type_confidence"),
        "fields": extract_out.get("fields") or {},
        "validate": {
            "valid": validate_out.get("valid"),
            "rule_failures": validate_out.get("rule_failures") or [],
        },
    }
    commit_gate = {
        "fase": "3-stub",
        "decision": "proposal_only",
        "note": "FASE-4 will do real routing/entity-resolution. No CRM write.",
    }

    proposal_id = await pool.fetchval(
        """
        INSERT INTO document_routing_proposal
            (queue_id, doc_index, pipeline_version, routing_key,
             entity_resolution, routing, commit_gate, status)
        VALUES ($1, 0, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, 'review_pending')
        ON CONFLICT (routing_key) DO UPDATE
            SET routing      = EXCLUDED.routing,
                commit_gate  = EXCLUDED.commit_gate
        RETURNING id
        """,
        queue_id,
        job.get("pipeline_version", "v1"),
        routing_key,
        json.dumps({}),          # entity_resolution: FASE-4 fills this.
        json.dumps(proposal),    # routing: the proposal evidence payload.
        json.dumps(commit_gate),
    )
    logger.info(
        "route(stub): job=%s proposal_id=%s doc_type=%s (0 CRM writes)",
        queue_id, proposal_id, doc_type,
    )
    return {
        "routed": False,
        "proposal_id": proposal_id,
        "routing_key": routing_key,
        "doc_type": doc_type,
        "stub": True,
        "_metric": {"model": "route-proposal-stub", "confidence": 1.0},
    }


def build_real_stage_handler(pool: asyncpg.Pool) -> StageHandler:
    """Return a single ``stage_handler(job, stage)`` wired to all real FASE-3 stages.

    Wire into the worker as::

        worker = IntakeWorker(pool, stage_handler=build_real_stage_handler(pool))

    Error policy: handlers PROPAGATE exceptions — the FASE-2 worker owns
    retry/backoff/DLQ. We never swallow a failure into a fake success (that would
    advance the stage machine on a lie).
    """
    classify_handler = _classify.build_stage_handler(pool)

    async def real_stage_handler(job: dict, stage: str) -> dict:
        if stage in ("classify", "ocr"):
            # classify.build_stage_handler owns both: 'classify' does the heavy
            # preprocess+OCR+classify pass; 'ocr' is its idempotent passthrough.
            payload = await classify_handler(job, stage)
            if stage == "classify":
                payload.setdefault(
                    "_metric",
                    {
                        "model": payload.get("model", _classify._resolve_ocr_model()),
                        "confidence": payload.get("type_confidence", 0.0),
                    },
                )
            return payload

        if stage in _NEEDS_STAGE_OUTPUT:
            # Hydrate the accumulated stage_output (worker omits it from the job).
            so = await _fetch_stage_output(pool, job["id"])
            enriched = dict(job)
            enriched["stage_output"] = so
            if stage == "extract":
                # Adapt classify's per-page OCR dicts -> list[str] for extract.
                enriched["ocr_text_per_page"] = _ocr_text_per_page_as_strings(so)
                doc_type = (so.get("classify") or {}).get("doc_type")
                enriched["doc_type"] = doc_type
                # Anti-poison-pill: an 'unknown'/unschematised doc_type is a
                # legitimate "route to human review" outcome of the golden-rule
                # classifier, NOT a stage failure. extract_stage() raises
                # ValueError for it; if we let that propagate the worker would
                # burn 5 retries to DLQ a doc that is simply not auto-extractable.
                # So we short-circuit to an empty-extraction result and let the
                # doc flow on to validate -> route-proposal for human triage.
                if canonical_doc_type(doc_type) is None:
                    logger.info(
                        "extract: doc_type=%r not auto-extractable (job=%s) -> "
                        "empty fields, route to review (no DLQ)",
                        doc_type, job.get("id"),
                    )
                    return {
                        "doc_type": doc_type or "unknown",
                        "fields": {},
                        "extraction_model": EXTRACTION_MODEL_LABEL,
                        "any_low_confidence": True,
                        "skipped": "unschematised_doc_type",
                        "_metric": {"model": EXTRACTION_MODEL_LABEL, "confidence": 0.0},
                    }
                payload = await extract_stage(enriched, stage)
                payload.setdefault(
                    "_metric",
                    {
                        "model": payload.get("extraction_model", EXTRACTION_MODEL_LABEL),
                        "confidence": 0.0 if payload.get("any_low_confidence") else 0.85,
                    },
                )
                return payload
            # validate
            payload = await validate_stage(enriched, stage)
            payload.setdefault(
                "_metric",
                {"model": "deterministic-rules", "confidence": 1.0 if payload.get("valid") else 0.0},
            )
            return payload

        if stage == "route":
            return await _route_stage_stub(pool, job)

        # Unknown stage: do not fabricate. Surface a no-op marker so the worker can
        # advance only if it chooses; an unexpected stage is a wiring bug.
        logger.warning("real_stage_handler: unhandled stage=%s (job=%s)", stage, job.get("id"))
        return {"handled_by": "fase3-dispatcher", "unhandled_stage": stage}

    return real_stage_handler
