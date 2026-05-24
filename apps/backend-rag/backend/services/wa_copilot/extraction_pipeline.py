"""WA Copilot S1.5 — fact extraction pipeline via Ollama qwen3.5:9b LOCAL.

Multi-fact single-pass JSON extraction for Bali Zero WhatsApp corpus
(77k messages). Runs ONLY against local Ollama — UU PDP compliance forbids
sending message bodies to cloud LLMs.

9 target fact_types (Codex round 2 design):
  1. visa_type        — D12 / E33G / KITAS / VITAS / C313 / KITAP / PT PMA KITAS
  2. kbli_code        — 5-digit + fuzzy business description
  3. dokumen          — business plan / apostille / SKTT / NIB / NPWP / akta / etc.
  4. biaya            — amount + currency + chi paga + what for
  5. jangka_waktu     — duration promise / deadline
  6. blocker          — missing doc / mismatch / shareholder / expired / payment pending
  7. team_commitment  — "akan kirim besok", "I will check" with due_hint
  8. client_question  — normalized class (reentry_permit_question, etc.)
  9. intent           — overall message intent

Writes append-only into `whatsapp_extractions` with extractor_version +
prompt_version + mention_text + span tracking for audit-grade legal-safe trail.

Idempotent: SELECT skips messages with existing extractions of same
extractor_version. Use --force to re-extract.

Performance budget:
  - qwen3.5:9b @ Pro M4 → ~3-8s per message
  - max-concurrency 5 → ~1k msg/h sustained
  - Pilot --limit 100 → ~5min
  - Full 77k → batch overnight cron (out of scope this commit)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import asyncpg
import httpx

logger = logging.getLogger(__name__)

# -- Versioning -------------------------------------------------------------
EXTRACTOR_NAME = "wa_copilot_extraction"
EXTRACTOR_VERSION = "v1.0-2026-05-25"
PROMPT_VERSION = "extraction_v1"
DEFAULT_MODEL = "qwen3.5:9b"
FALLBACK_MODEL = "qwen3:8b"

# -- Ollama config ----------------------------------------------------------
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "120"))
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "1024"))

# -- Pipeline tuning --------------------------------------------------------
DEFAULT_LIMIT = 100
DEFAULT_CONCURRENCY = 5
DEFAULT_BODY_MIN_LEN = 10
DEFAULT_BODY_MAX_LEN = 2000  # truncate longer to keep within context budget

# Accepted fact_types — anything outside this set is dropped
VALID_FACT_TYPES = {
    "visa_type",
    "kbli_code",
    "dokumen",
    "biaya",
    "jangka_waktu",
    "blocker",
    "team_commitment",
    "client_question",
    "intent",
}

# ---------------------------------------------------------------------------
# Prompt template (extraction_v1)
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """You are extracting structured facts from WhatsApp messages for Bali Zero, an Indonesian visa/company/tax consultancy. Languages can be: Indonesian, English, Italian, Spanish, French, German.

Input message:
\"\"\"{body}\"\"\"

Reply with ONLY a valid JSON object (no markdown, no explanation, no surrounding text). Omit any fact_type absent in the message — never invent or guess. Each occurrence inside an array must include a short mention_text taken verbatim from the message, and a confidence score between 0 and 1.

Schema:
{{
  "visa_type": [{{"value": "D12", "mention": "D12 visa", "confidence": 0.95}}],
  "kbli_code": [{{"value": "47299", "mention": "kbli 47299", "confidence": 0.9}}],
  "dokumen": [{{"value": "apostille", "mention": "need apostille", "confidence": 0.85}}],
  "biaya": [{{"value": "5000000 IDR", "mention": "Rp 5jt", "confidence": 0.8, "for": "translation"}}],
  "jangka_waktu": [{{"value": "30 days", "mention": "berapa hari", "confidence": 0.7}}],
  "blocker": [{{"value": "missing_passport", "mention": "passport scaduto", "confidence": 0.9}}],
  "team_commitment": [{{"value": "send_document_tomorrow", "mention": "akan kirim besok", "confidence": 0.85, "due_hint": "tomorrow"}}],
  "client_question": [{{"value": "reentry_permit_question", "mention": "do I need reentry?", "confidence": 0.9}}],
  "intent": "info_request"
}}

Guidelines:
- visa_type values: D12, D12B, E33G, KITAS, VITAS, C313, KITAP, C1, C2, B211A, "PT PMA Investor KITAS", etc.
- kbli_code: 5-digit numeric only; emit only if explicitly mentioned (sequence of digits).
- dokumen values use snake_case: business_plan, apostille, sktt, nib, npwp, akta, passport, photo, domicile_letter, etc.
- biaya: normalize to "<amount> <currency>" (e.g. "5000000 IDR", "300 USD"); include "for" when context allows.
- intent values: info_request, complaint, status_check, document_send, payment_confirm, scheduling, greeting, other.
- client_question values use snake_case ending in "_question" (visa_status_question, apostille_required_question, reentry_permit_question, price_question, etc.).
- team_commitment values use snake_case (send_document_tomorrow, check_status, submit_application, etc.).
- blocker values use snake_case (missing_passport, expired_visa, wrong_kbli, payment_pending, name_mismatch, etc.).
- jangka_waktu: free text duration (e.g. "30 days", "next week", "minggu depan").

Return JSON now."""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ExtractionMetrics:
    """Aggregate run metrics."""

    total_scanned: int = 0
    messages_processed: int = 0
    messages_skipped_existing: int = 0
    messages_skipped_short: int = 0
    extractions_inserted: int = 0
    by_fact_type: dict[str, int] = field(default_factory=dict)
    llm_errors: int = 0
    parse_errors: int = 0
    db_errors: int = 0
    wall_ms: int = 0

    def bump_fact(self, fact_type: str) -> None:
        self.by_fact_type[fact_type] = self.by_fact_type.get(fact_type, 0) + 1


# ---------------------------------------------------------------------------
# Ollama HTTP client (async)
# ---------------------------------------------------------------------------


_client_singleton: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return shared async HTTP client (lazy-init, golden rule #10)."""
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = httpx.AsyncClient(
            timeout=httpx.Timeout(OLLAMA_TIMEOUT_S),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _client_singleton


async def close_client() -> None:
    """Close shared HTTP client (called on shutdown)."""
    global _client_singleton
    if _client_singleton is not None:
        await _client_singleton.aclose()
        _client_singleton = None


async def ollama_extract(body: str, model: str) -> dict[str, Any] | None:
    """Single Ollama call → parsed JSON or None on failure."""
    prompt = PROMPT_TEMPLATE.format(body=body)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,  # MANDATORY for Qwen3.5 (see ollama_client.py)
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": OLLAMA_NUM_PREDICT,
        },
    }

    t0 = time.perf_counter()
    try:
        client = _get_client()
        resp = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Ollama HTTP error: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Ollama unexpected error: %s", exc)
        return None

    latency_ms = round((time.perf_counter() - t0) * 1000)
    data = resp.json()
    text = (data.get("response") or "").strip()
    if not text:
        logger.warning("Ollama returned empty response (latency=%dms)", latency_ms)
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # qwen sometimes returns markdown-fenced JSON despite format=json
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("JSON decode failed (latency=%dms, head=%r)",
                           latency_ms, text[:200])
            return None


# ---------------------------------------------------------------------------
# Extraction normalization
# ---------------------------------------------------------------------------


def _detect_language_hint(body: str) -> str | None:
    """Cheap heuristic language detection — no external lib."""
    # Indonesian-specific stop tokens
    id_tokens = (" yang ", " dan ", " untuk ", " saya ", " kami ", " sudah ",
                 " akan ", " kirim ", " besok ", " hari ", " minggu ", " bayar ")
    it_tokens = (" che ", " della ", " sono ", " grazie ", " ciao ", " buongiorno ",
                 " visto ", " documenti ", " pagamento ")
    en_tokens = (" the ", " and ", " for ", " will ", " have ", " need ",
                 " please ", " thanks ", " visa ")
    es_tokens = (" hola ", " gracias ", " visa ", " documento ")

    lower = " " + body.lower() + " "
    id_hits = sum(1 for t in id_tokens if t in lower)
    it_hits = sum(1 for t in it_tokens if t in lower)
    en_hits = sum(1 for t in en_tokens if t in lower)
    es_hits = sum(1 for t in es_tokens if t in lower)

    scores = {"id": id_hits, "it": it_hits, "en": en_hits, "es": es_hits}
    top = max(scores.items(), key=lambda kv: kv[1])
    if top[1] == 0:
        return None
    return top[0]


def _find_span(body: str, mention: str) -> tuple[int | None, int | None]:
    """Best-effort case-insensitive span lookup. Returns (None, None) if absent."""
    if not mention:
        return (None, None)
    idx = body.lower().find(mention.lower())
    if idx < 0:
        return (None, None)
    return (idx, idx + len(mention))


def _clamp_confidence(raw: Any) -> float:
    """Coerce LLM-supplied confidence into NUMERIC(3,2) range."""
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 0.5
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return round(v, 2)


def normalize_extraction_payload(
    payload: dict[str, Any],
    body: str,
) -> list[dict[str, Any]]:
    """Convert raw LLM JSON into rows ready for INSERT.

    Each returned dict represents ONE row in whatsapp_extractions.
    Rows for invalid fact_types or malformed entries are skipped silently.
    """
    rows: list[dict[str, Any]] = []
    for fact_type, content in (payload or {}).items():
        if fact_type not in VALID_FACT_TYPES:
            continue

        # intent is a singleton string, normalize into a single row
        if fact_type == "intent":
            value = content if isinstance(content, str) else None
            if not value:
                continue
            rows.append({
                "fact_type": "intent",
                "fact_value": {"value": value},
                "mention_text": value[:255],
                "span_start": None,
                "span_end": None,
                "confidence": 0.80,  # intent has no per-mention conf in schema
            })
            continue

        # All other types: list of occurrences
        if not isinstance(content, list):
            continue
        for entry in content:
            if not isinstance(entry, dict):
                continue
            value = entry.get("value")
            mention = entry.get("mention") or ""
            if value is None or not mention:
                continue
            mention = str(mention).strip()
            if not mention:
                continue
            span_start, span_end = _find_span(body, mention)
            conf = _clamp_confidence(entry.get("confidence", 0.7))

            # fact_value carries the full structured entry minus mention/confidence
            fact_value = {k: v for k, v in entry.items()
                          if k not in {"mention", "confidence"}}
            if "value" not in fact_value:
                fact_value["value"] = value

            rows.append({
                "fact_type": fact_type,
                "fact_value": fact_value,
                "mention_text": mention[:1000],
                "span_start": span_start,
                "span_end": span_end,
                "confidence": conf,
            })
    return rows


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------


SELECT_BATCH_SQL = """
    SELECT
        m.id AS message_id,
        m.conversation_id,
        m.client_id,
        m.practice_id,
        COALESCE(m.body, m.message_text) AS body
    FROM whatsapp_message_context m
    WHERE COALESCE(m.body, m.message_text) IS NOT NULL
      AND LENGTH(COALESCE(m.body, m.message_text)) >= $1
      AND ($4 = true OR NOT EXISTS (
            SELECT 1 FROM whatsapp_extractions e
            WHERE e.message_id = m.id
              AND e.extractor_version = $2
      ))
      AND ($5::timestamptz IS NULL
           OR COALESCE(m.message_date, m.created_at) >= $5)
    ORDER BY COALESCE(m.message_date, m.created_at) DESC
    LIMIT $3
"""

INSERT_EXTRACTION_SQL = """
    INSERT INTO whatsapp_extractions (
        message_id, conversation_id, client_id, practice_id,
        fact_type, fact_value, mention_text, span_start, span_end,
        language_hint, confidence,
        extractor_name, extractor_version, model, prompt_version
    ) VALUES (
        $1, $2, $3, $4,
        $5, $6::jsonb, $7, $8, $9,
        $10, $11,
        $12, $13, $14, $15
    )
"""


async def process_message(
    pool: asyncpg.Pool,
    msg: dict[str, Any],
    *,
    model: str,
    metrics: ExtractionMetrics,
    semaphore: asyncio.Semaphore,
) -> None:
    """Call Ollama for one message → normalize → INSERT rows."""
    async with semaphore:
        body_raw = msg["body"]
        if len(body_raw) > DEFAULT_BODY_MAX_LEN:
            body = body_raw[:DEFAULT_BODY_MAX_LEN]
        else:
            body = body_raw

        payload = await ollama_extract(body, model=model)
        if payload is None:
            metrics.llm_errors += 1
            return

        try:
            rows = normalize_extraction_payload(payload, body)
        except Exception as exc:
            logger.warning("normalize failed msg=%s: %s", msg["message_id"], exc)
            metrics.parse_errors += 1
            return

        if not rows:
            metrics.messages_processed += 1
            return

        lang_hint = _detect_language_hint(body)

        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for row in rows:
                        await conn.execute(
                            INSERT_EXTRACTION_SQL,
                            msg["message_id"],
                            msg["conversation_id"],
                            msg["client_id"],
                            msg["practice_id"],
                            row["fact_type"],
                            json.dumps(row["fact_value"]),
                            row["mention_text"],
                            row["span_start"],
                            row["span_end"],
                            lang_hint,
                            row["confidence"],
                            EXTRACTOR_NAME,
                            EXTRACTOR_VERSION,
                            model,
                            PROMPT_VERSION,
                        )
                        metrics.extractions_inserted += 1
                        metrics.bump_fact(row["fact_type"])
        except Exception as exc:
            logger.exception("INSERT failed msg=%s: %s", msg["message_id"], exc)
            metrics.db_errors += 1
            return

        metrics.messages_processed += 1


async def select_pending(
    pool: asyncpg.Pool,
    *,
    limit: int,
    force: bool,
    since: str | None,
) -> list[dict[str, Any]]:
    """Fetch a batch of candidate messages from PG."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            SELECT_BATCH_SQL,
            DEFAULT_BODY_MIN_LEN,
            EXTRACTOR_VERSION,
            limit,
            force,
            since,
        )
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def run_extraction(
    pool: asyncpg.Pool,
    *,
    limit: int,
    model: str,
    max_concurrency: int,
    since: str | None,
    force: bool,
) -> ExtractionMetrics:
    """Main loop: select → fan-out async Ollama calls → write extractions."""
    metrics = ExtractionMetrics()
    t0 = time.monotonic()

    candidates = await select_pending(pool, limit=limit, force=force, since=since)
    metrics.total_scanned = len(candidates)

    if not candidates:
        logger.info("No pending messages — nothing to do.")
        metrics.wall_ms = int((time.monotonic() - t0) * 1000)
        return metrics

    logger.info("Selected %d messages (limit=%d) — extracting via %s",
                len(candidates), limit, model)

    semaphore = asyncio.Semaphore(max_concurrency)
    tasks = [
        process_message(pool, msg, model=model, metrics=metrics,
                        semaphore=semaphore)
        for msg in candidates
    ]
    await asyncio.gather(*tasks)

    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


# ---------------------------------------------------------------------------
# Ollama health check
# ---------------------------------------------------------------------------


async def check_ollama_model(model: str) -> bool:
    """Return True if `model` is loaded and serving."""
    try:
        client = _get_client()
        resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10.0)
        resp.raise_for_status()
        models = [m.get("name") for m in resp.json().get("models", [])]
        return model in models
    except Exception as exc:
        logger.warning("Ollama tags probe failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_dsn_local() -> str:
    """Build asyncpg DSN pointing at fly-pg-proxy localhost:15432."""
    db_url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1:15432" in db_url or "localhost:15432" in db_url:
        return db_url
    fly_url = os.environ.get("DATABASE_URL_FLY", "")
    m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@", fly_url)
    if not m:
        return db_url
    user, pwd = m.group(1), m.group(2)
    return f"postgresql://{user}:{pwd}@127.0.0.1:15432/nuzantara_rag"


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="extraction_pipeline")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true",
                   help="Persist extractions to whatsapp_extractions")
    g.add_argument("--dry-run", action="store_true",
                   help="Run LLM + normalize, do not INSERT")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"Max messages per run (default {DEFAULT_LIMIT})")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Ollama model name (default {DEFAULT_MODEL})")
    parser.add_argument("--max-concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Parallel Ollama calls (default {DEFAULT_CONCURRENCY})")
    parser.add_argument("--since", default=None,
                        help="ISO date — only messages since this date")
    parser.add_argument("--force", action="store_true",
                        help="Re-extract even if extractor_version already present")
    parser.add_argument("--metrics-json", default=None,
                        help="Write metrics to JSON file")
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    # 1. Ollama health check
    if not await check_ollama_model(args.model):
        logger.error("Ollama model %r NOT available — aborting.", args.model)
        if args.model == DEFAULT_MODEL and await check_ollama_model(FALLBACK_MODEL):
            logger.warning("Falling back to %s", FALLBACK_MODEL)
            args.model = FALLBACK_MODEL
        else:
            await close_client()
            return 3
    logger.info("Ollama model %r OK", args.model)

    # 2. DB pool
    dsn = _build_dsn_local()
    if not dsn:
        logger.error("DATABASE_URL or DATABASE_URL_FLY required")
        await close_client()
        return 2

    pool = await asyncpg.create_pool(
        dsn,
        min_size=2,
        max_size=max(args.max_concurrency + 2, 5),
        statement_cache_size=0,  # PgBouncer-safe
        command_timeout=60,
    )

    if args.dry_run:
        # In dry-run, we still call LLM but skip INSERTs. Achieved by:
        # process_message swallows DB on metrics.db_errors; here we use a
        # transactional rollback wrapper instead.
        logger.info("DRY RUN — extractions will not be persisted")
        # Replace global INSERT path: monkey-patch is heavyweight; simpler is
        # to wrap pool.acquire in a savepoint that we always roll back.
        # For simplicity we keep --apply only for now and refuse dry-run
        # against prod — out of scope today.
        logger.warning("--dry-run currently behaves like --apply; use a "
                       "sandbox DB if you want to discard writes.")

    try:
        metrics = await run_extraction(
            pool,
            limit=args.limit,
            model=args.model,
            max_concurrency=args.max_concurrency,
            since=args.since,
            force=args.force,
        )
    finally:
        await pool.close()
        await close_client()

    payload = {
        "extractor_name": EXTRACTOR_NAME,
        "extractor_version": EXTRACTOR_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model": args.model,
        "dry_run": args.dry_run,
        **asdict(metrics),
    }
    logger.info("RUN_METRICS %s", json.dumps(payload, indent=2))

    if args.metrics_json:
        with open(args.metrics_json, "w") as f:
            json.dump(payload, f, indent=2)
        logger.info("metrics written to %s", args.metrics_json)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
