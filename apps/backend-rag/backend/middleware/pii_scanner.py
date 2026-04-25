"""
PII Scanner Middleware for UU PDP Compliance

Scans all LLM/RAG output for Indonesian PII before returning to users.
Custom recognizers for: KTP (16 digits), NPWP (15+16 digit formats),
Indonesian passport, phone (+62), email.

Compliance: UU PDP No. 27/2022 Art. 35, 36, 38
"""

import json
import logging
from typing import Any

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

from backend.middleware.correlation import get_correlation_id
from backend.services.pii.violation_store import (
    aggregate,
    hash_subject,
    record_violations,
    set_app,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Custom Indonesian PII Recognizers
# ============================================================================

# KTP / NIK — 16 digits (Indonesian national ID)
_ktp_recognizer = PatternRecognizer(
    supported_entity="ID_KTP",
    name="Indonesian KTP Recognizer",
    patterns=[
        Pattern("KTP_16", r"\b\d{16}\b", 0.7),
    ],
    supported_language="en",
)

# NPWP — Old format (15 digits with dots/dashes: XX.XXX.XXX.X-XXX.XXX)
_npwp_old_recognizer = PatternRecognizer(
    supported_entity="ID_NPWP",
    name="Indonesian NPWP Old Format",
    patterns=[
        Pattern("NPWP_OLD", r"\b\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b", 0.9),
    ],
    supported_language="en",
)

# NPWP — New 16-digit format for foreigners (leading zero + old 15 digits)
_npwp_new_recognizer = PatternRecognizer(
    supported_entity="ID_NPWP",
    name="Indonesian NPWP New Format (16 digits)",
    patterns=[
        Pattern("NPWP_NEW_16", r"\b0\d{15}\b", 0.85),
        Pattern("NPWP_NEW_DOTS", r"\b0\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b", 0.9),
    ],
    supported_language="en",
)

# Indonesian Passport — 1-2 letters + 6-7 digits
_passport_id_recognizer = PatternRecognizer(
    supported_entity="ID_PASSPORT",
    name="Indonesian Passport Recognizer",
    patterns=[
        Pattern("PASSPORT_ID", r"\b[A-Z]{1,2}\d{6,7}\b", 0.6),
    ],
    supported_language="en",
)

# Indonesian Phone — +62 prefix
_phone_id_recognizer = PatternRecognizer(
    supported_entity="PHONE_ID",
    name="Indonesian Phone Recognizer",
    patterns=[
        Pattern("PHONE_62", r"\+62\d{8,12}", 0.8),
        Pattern("PHONE_08", r"\b08\d{8,11}\b", 0.6),
    ],
    supported_language="en",
)


# ============================================================================
# Scanner Engine (singleton)
# ============================================================================

_analyzer: AnalyzerEngine | None = None
_anonymizer: AnonymizerEngine | None = None


def _get_analyzer() -> AnalyzerEngine:
    """Lazy-init analyzer with Indonesian recognizers."""
    global _analyzer
    if _analyzer is None:
        _analyzer = AnalyzerEngine()
        _analyzer.registry.add_recognizer(_ktp_recognizer)
        _analyzer.registry.add_recognizer(_npwp_old_recognizer)
        _analyzer.registry.add_recognizer(_npwp_new_recognizer)
        _analyzer.registry.add_recognizer(_passport_id_recognizer)
        _analyzer.registry.add_recognizer(_phone_id_recognizer)
        logger.info("PII Scanner initialized with Indonesian recognizers (KTP, NPWP, Passport, Phone)")
    return _analyzer


def _get_anonymizer() -> AnonymizerEngine:
    """Lazy-init anonymizer."""
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()
    return _anonymizer


def scan_text(text: str, language: str = "en") -> list[dict[str, Any]]:
    """
    Scan text for PII entities.

    Returns list of detected entities with type, start, end, score.
    """
    analyzer = _get_analyzer()
    results = analyzer.analyze(
        text=text,
        language=language,
        entities=[
            "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
            "ID_KTP", "ID_NPWP", "ID_PASSPORT", "PHONE_ID",
        ],
    )
    return [
        {
            "entity_type": r.entity_type,
            "start": r.start,
            "end": r.end,
            "score": r.score,
            "text": text[r.start:r.end],
        }
        for r in results
    ]


def redact_text(text: str, language: str = "en") -> tuple[str, int]:
    """
    Scan and redact PII from text.

    Returns (redacted_text, count_of_entities_redacted). Backward-compatible
    2-tuple — callers that also need the per-pattern breakdown should use
    `redact_text_detailed()`.
    """
    redacted, count, _ = redact_text_detailed(text, language)
    return redacted, count


def redact_text_detailed(
    text: str, language: str = "en",
) -> tuple[str, int, list[str]]:
    """
    Scan and redact PII from text, also returning the flat list of detected
    entity types (one per match, duplicates preserved) — for the violation
    store's per-pattern aggregation.
    """
    analyzer = _get_analyzer()
    anonymizer = _get_anonymizer()

    results = analyzer.analyze(
        text=text,
        language=language,
        entities=[
            "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
            "ID_KTP", "ID_NPWP", "ID_PASSPORT", "PHONE_ID",
        ],
    )

    if not results:
        return text, 0, []

    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
    patterns = [r.entity_type for r in results]

    if patterns:
        logger.warning(
            f"PII redacted: {len(patterns)} entities found "
            f"({', '.join(set(patterns))})"
        )

    return anonymized.text, len(patterns), patterns


# ============================================================================
# FastAPI Middleware (scoped to /api/agentic/* responses)
# ============================================================================


class PIIScannerMiddleware:
    """
    ASGI middleware that redacts PII from JSON responses on /api/agentic/* paths.

    Intercepts the response body, deserializes JSON, redacts PII fields
    ('answer', 'generation', 'response', 'text', 'message'), then re-serializes.
    Non-JSON or non-agentic responses pass through untouched.

    Compliance: UU PDP No. 27/2022 Art. 35, 36, 38
    """

    _SCOPED_PREFIX = "/api/agentic/"
    _REDACT_FIELDS = {"answer", "generation", "response", "text", "message", "content"}

    def __init__(self, app: Any) -> None:
        self.app = app
        # Register the app so the violation store can reach app.state.db_pool
        # from an ASGI-level middleware that does not own a Request.
        try:
            set_app(app)
        except Exception:  # noqa: BLE001 — never fail construction
            logger.debug("pii_scanner.set_app_failed", exc_info=True)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if not path.startswith(self._SCOPED_PREFIX):
            await self.app(scope, receive, send)
            return

        # Capture the response body
        response_started = False
        response_headers: list = []
        response_status: int = 200
        body_chunks: list[bytes] = []

        async def capture_send(message: dict) -> None:
            nonlocal response_started, response_headers, response_status
            if message["type"] == "http.response.start":
                response_started = True
                response_status = message["status"]
                response_headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))

        await self.app(scope, receive, capture_send)

        raw_body = b"".join(body_chunks)

        # Only attempt PII redaction on JSON responses
        content_type = ""
        for name, value in response_headers:
            if name.lower() == b"content-type":
                content_type = value.decode("utf-8", errors="ignore").lower()
                break

        redacted_body = raw_body
        if "application/json" in content_type and raw_body:
            try:
                payload = json.loads(raw_body)
                total_redacted = 0
                all_patterns: list[str] = []
                for field in self._REDACT_FIELDS:
                    if field in payload and isinstance(payload[field], str):
                        cleaned, count, patterns = redact_text_detailed(payload[field])
                        payload[field] = cleaned
                        total_redacted += count
                        all_patterns.extend(patterns)
                if total_redacted > 0:
                    logger.info(
                        f"[PIIScanner] Redacted {total_redacted} PII entities from agentic response on {path}"
                    )
                    # Persist a durable audit row per distinct pattern.
                    subject = None
                    for name, value in response_headers:
                        if name.lower() == b"x-user-email":
                            subject = value.decode("utf-8", errors="ignore")
                            break
                    if subject is None:
                        # Fall back to client IP from scope (no hashing yet)
                        client = scope.get("client")
                        if isinstance(client, (list, tuple)) and client:
                            subject = str(client[0])
                    cid = get_correlation_id()
                    record_violations(
                        aggregate(
                            all_patterns,
                            request_id=None if cid in (None, "-", "") else cid,
                            route=path,
                            user_hash=hash_subject(subject),
                        ),
                    )
                redacted_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                # UU PDP audit: an agentic endpoint declared JSON but returned
                # an unparsable body. Pass-through is safe (no redaction can
                # happen on bytes we can't decode) — but we MUST record it so
                # the PII-redaction coverage gap is traceable.
                logger.warning(
                    "pii_scanner.unparsable_response_body",
                    extra={
                        "path": path,
                        "error_type": type(exc).__name__,
                        "content_type": content_type,
                        "body_len": len(raw_body),
                    },
                )

        # Update Content-Length if body changed
        updated_headers = []
        for name, value in response_headers:
            if name.lower() == b"content-length":
                updated_headers.append((b"content-length", str(len(redacted_body)).encode()))
            else:
                updated_headers.append((name, value))

        await send({"type": "http.response.start", "status": response_status, "headers": updated_headers})
        await send({"type": "http.response.body", "body": redacted_body})
