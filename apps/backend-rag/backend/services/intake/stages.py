"""Real stage-handler dispatcher for the document-intake worker (FASE 3, v2 machine).

Wires the FASE-2 worker (``services/intake/worker.py``) to the real stage
implementations:

  * ``classify`` -> :mod:`backend.services.intake.classify`
    (preprocess + local OCR via qwen-vl, then keyword classification — OCR and
    classification happen in this ONE stage; the v1 passthrough ``ocr`` stage
    was dropped by the v2 machine, migration 224).
  * ``extract``  -> :func:`backend.services.intake.extract.extract_stage`
    (configured local field extraction, Maybe pattern).
  * ``validate`` -> :func:`backend.services.intake.validate_rules.validate_stage`
    (deterministic, no LLM).
  * ``route``    -> :func:`backend.services.intake.routing.route_stage`
    (FASE-4: entity-resolution + ONE ``document_routing_proposal`` row +
    received_by backfill from the matched client, ZERO CRM writes).

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

Transient-infra contract (v2)
-----------------------------
A handler failure caused by INFRA being down (local Ollama unreachable, connect
timeout) is re-raised as :class:`worker.TransientStageError` at this single
chokepoint, so the worker retries with a fixed backoff WITHOUT burning an
attempt — a rebooting Ollama must never DLQ good documents. Real stage errors
(poison-pill) propagate unchanged and burn attempts as before.

Metrics
-------
Each handler embeds the REAL ``model`` + ``confidence`` into its returned
payload under ``_metric``; the v2 worker lifts it into the
``intake_stage_metrics`` row (no more 'stub-passthrough' placeholder).

PII / Symbiosis Law 2: every model call is to localhost Ollama. ZERO cloud, ZERO
CRM writes. The only structured side effect is one ``document_routing_proposal``
row (read-only proposal; FASE-5 HITL decides actual routing).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
import httpx

from backend.services.intake import classify as _classify
from backend.services.intake.extract import (
    canonical_doc_type,
    extract_stage,
    resolved_extraction_model_label,
)
from backend.services.intake.routing import route_stage as _route_stage_fase4
from backend.services.intake.validate_rules import validate_stage
from backend.services.intake.worker import TransientStageError

logger = logging.getLogger("zantara.intake.stages")

_PROPOSAL_ONLY_SKIP_EXTRACT_ENV = "INTAKE_PROPOSAL_ONLY_SKIP_EXTRACT"

StageHandler = Callable[[dict, str], Awaitable[dict]]

# Stages whose real handler reads the accumulated stage_output (which the worker
# does NOT include in the claimed job dict) -> we hydrate it from the DB first.
_NEEDS_STAGE_OUTPUT: frozenset[str] = frozenset({"extract", "validate"})

# httpx exception classes that mean "the local model endpoint is down", not
# "this document is poison" — surfaced as TransientStageError (no attempt burn).
_TRANSIENT_HTTPX_ERRORS: tuple[type[Exception], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


async def _fetch_stage_output(pool: asyncpg.Pool, queue_id: int) -> dict[str, Any]:
    """Load the live ``stage_output`` JSONB for a queue row (prior stages' output)."""
    row = await pool.fetchrow("SELECT stage_output FROM intake_queue WHERE id = $1", queue_id)
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


def build_real_stage_handler(pool: asyncpg.Pool) -> StageHandler:
    """Return a single ``stage_handler(job, stage)`` wired to all real stages.

    Wire into the worker as::

        worker = IntakeWorker(pool, stage_handler=build_real_stage_handler(pool))

    Error policy: handlers PROPAGATE exceptions — the FASE-2 worker owns
    retry/backoff/DLQ. We never swallow a failure into a fake success (that would
    advance the stage machine on a lie). Infra-down httpx failures are translated
    to TransientStageError (fixed backoff, no attempt burn) at this chokepoint.
    """
    classify_handler = _classify.build_stage_handler(pool)

    async def _dispatch(job: dict, stage: str) -> dict:
        if stage == "classify":
            # classify performs the heavy preprocess+OCR+classify pass in one go
            # (the v2 machine has no separate ocr stage).
            payload = await classify_handler(job, stage)
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
                    extraction_model = resolved_extraction_model_label()
                    logger.info(
                        "extract: doc_type=%r not auto-extractable (job=%s) -> "
                        "empty fields, route to review (no DLQ)",
                        doc_type,
                        job.get("id"),
                    )
                    return {
                        "doc_type": doc_type or "unknown",
                        "fields": {},
                        "extraction_model": extraction_model,
                        "any_low_confidence": True,
                        "skipped": "unschematised_doc_type",
                        "_metric": {"model": extraction_model, "confidence": 0.0},
                    }
                if _env_truthy(_PROPOSAL_ONLY_SKIP_EXTRACT_ENV):
                    logger.info(
                        "extract: %s set; skip field extraction for doc_type=%r "
                        "(job=%s) and continue to proposal routing",
                        _PROPOSAL_ONLY_SKIP_EXTRACT_ENV,
                        doc_type,
                        job.get("id"),
                    )
                    return {
                        "doc_type": doc_type or "unknown",
                        "fields": {},
                        "extraction_model": "proposal-only-skip",
                        "any_low_confidence": True,
                        "skipped": "proposal_only_skip_extract",
                        "_metric": {"model": "proposal-only-skip-extract", "confidence": 0.0},
                    }
                payload = await extract_stage(enriched, stage)
                payload.setdefault(
                    "_metric",
                    {
                        "model": payload.get("extraction_model", resolved_extraction_model_label()),
                        "confidence": 0.0 if payload.get("any_low_confidence") else 0.85,
                    },
                )
                return payload
            # validate
            payload = await validate_stage(enriched, stage)
            payload.setdefault(
                "_metric",
                {
                    "model": "deterministic-rules",
                    "confidence": 1.0 if payload.get("valid") else 0.0,
                },
            )
            return payload

        if stage == "route":
            # FASE-4: real entity-resolution + routing proposal + received_by backfill.
            return await _route_stage_fase4(job, stage, pool)

        # Unknown stage: do not fabricate. Surface a no-op marker so the worker can
        # advance only if it chooses; an unexpected stage is a wiring bug.
        logger.warning("real_stage_handler: unhandled stage=%s (job=%s)", stage, job.get("id"))
        return {"handled_by": "fase3-dispatcher", "unhandled_stage": stage}

    async def real_stage_handler(job: dict, stage: str) -> dict:
        try:
            return await _dispatch(job, stage)
        except _TRANSIENT_HTTPX_ERRORS as exc:
            # Local model endpoint down/unreachable: retry later, no attempt burn.
            raise TransientStageError(
                f"stage={stage} infra unreachable: {type(exc).__name__}: {exc}"
            ) from exc

    return real_stage_handler
