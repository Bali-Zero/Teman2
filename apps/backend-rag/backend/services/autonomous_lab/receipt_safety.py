"""Shared receipt-safety helpers for autonomous lab payloads."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlsplit

RAW_MARKER_PATTERN = re.compile(
    r"\b(?:RAW(?:_[A-Z0-9]+){1,}|[A-Z0-9]+_(?:MUST_NOT_LEAK|SHOULD_NOT_APPEAR))\b"
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"<>,;]{12,}"
)
SECRET_QUERY_KEY_PATTERN = re.compile(
    r"(?i)(?:^|[?&])(?:access[_-]?token|api[_-]?key|key|password|secret|signature|sig|token)="
)
EMAIL_PATTERN = re.compile(
    r"(?i)(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![A-Z0-9._%+-])"
)
PHONE_PATTERN = re.compile(r"(?<![A-Za-z0-9])\+?\d[\d .()/-]{7,}\d(?![A-Za-z0-9])")
WHATSAPP_HANDLE_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:\+?\d[\d .()/-]{7,}\d|[a-z0-9._-]{3,})@(?:c|g|s)\.us"
    r"|(?<![A-Za-z0-9])(?:\+?\d[\d .()/-]{7,}\d)@s\.whatsapp\.net"
)
URL_WITH_QUERY_PATTERN = re.compile(r"https?://[^\s\"'<>]+")


def safe_sha256_fingerprint(value: str, hex_chars: int = 16) -> str:
    """Return a grouped SHA-256 prefix that is useful but not secret-like."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:hex_chars]
    grouped = "-".join(digest[index : index + 4] for index in range(0, len(digest), 4))
    return f"sha256:{grouped}"


def contains_receipt_sensitive_value(value: str) -> bool:
    """Return True when a string should not be persisted verbatim in a receipt."""
    return bool(
        RAW_MARKER_PATTERN.search(value)
        or SECRET_ASSIGNMENT_PATTERN.search(value)
        or SECRET_QUERY_KEY_PATTERN.search(value)
        or EMAIL_PATTERN.search(value)
        or _contains_phone_like_value(value)
        or WHATSAPP_HANDLE_PATTERN.search(value)
    )


def receipt_safe_evidence(value: str, *, force_fingerprint: bool = False) -> str:
    """Return short evidence or a fingerprint when evidence may contain sensitive data."""
    if force_fingerprint or contains_receipt_sensitive_value(value):
        return f"evidence_fingerprint:{safe_sha256_fingerprint(value)}; chars:{len(value)}"
    return shorten_receipt_value(value)


def redacted_receipt_value(value: str) -> str:
    """Return a deterministic redaction token for unsafe receipt values."""
    return f"redacted_receipt_value:{safe_sha256_fingerprint(value)}"


def receipt_safe_source_uri(
    source_uri: str,
    source_type: str,
    *,
    preserve_public_host: bool = True,
) -> str:
    """Return a provenance pointer without path, query, fragment, or identifiers."""
    candidate = source_uri.strip()
    parsed = urlsplit(candidate)
    fingerprint = safe_sha256_fingerprint(candidate)
    if preserve_public_host and parsed.netloc and not contains_receipt_sensitive_value(parsed.netloc):
        scheme = parsed.scheme or source_type
        return f"{scheme}://{parsed.netloc}/source_fingerprint:{fingerprint}"
    return f"{source_type}:source_fingerprint:{fingerprint}"


def shorten_receipt_value(value: str, limit: int = 180) -> str:
    """Collapse whitespace and bound a string for receipt evidence."""
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def receipt_safe_command_output(
    value: str,
    *,
    source: str,
    limit: int = 12_000,
    hash_only: bool = True,
) -> str:
    """Return a redacted command-output reference safe for receipts."""
    if source not in {"stdout", "stderr"}:
        raise ValueError("command output source must be stdout or stderr")
    redacted = _redact_command_output(value)
    bounded = redacted[:limit]
    if hash_only:
        return (
            f"{source}_fingerprint:{safe_sha256_fingerprint(bounded, hex_chars=24)}; "
            f"chars:{len(value)}; redacted_chars:{len(bounded)}"
        )
    return shorten_receipt_value(bounded, limit=limit)


def _contains_phone_like_value(value: str) -> bool:
    """Detect likely phone numbers without flagging dates or receipt fingerprints."""
    for match in PHONE_PATTERN.finditer(value):
        prefix = value[max(0, match.start() - 24) : match.start()].lower()
        if "sha256:" in prefix or "fingerprint:" in prefix:
            continue
        token = match.group(0).strip()
        digits = re.sub(r"\D", "", token)
        if not 10 <= len(digits) <= 15:
            continue
        if token.startswith("+"):
            return True
        if digits.startswith(
            (
                "0",
                "1",
                "33",
                "39",
                "44",
                "49",
                "60",
                "61",
                "62",
                "65",
                "66",
                "81",
                "82",
                "84",
                "86",
                "91",
            )
        ):
            return True
    return False


def _redact_command_output(value: str) -> str:
    redacted = SECRET_ASSIGNMENT_PATTERN.sub("[REDACTED_SECRET_ASSIGNMENT]", value)
    redacted = _redact_url_queries(redacted)
    redacted = WHATSAPP_HANDLE_PATTERN.sub("[REDACTED_WHATSAPP_HANDLE]", redacted)
    redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", redacted)
    redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
    redacted = RAW_MARKER_PATTERN.sub("[REDACTED_RAW_MARKER]", redacted)
    return redacted


def _redact_url_queries(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        parsed = urlsplit(raw_url)
        if not parsed.query:
            return raw_url
        base = raw_url.split("?", 1)[0]
        return f"{base}?REDACTED_QUERY"

    return URL_WITH_QUERY_PATTERN.sub(replace, value)


__all__ = [
    "EMAIL_PATTERN",
    "PHONE_PATTERN",
    "RAW_MARKER_PATTERN",
    "SECRET_ASSIGNMENT_PATTERN",
    "SECRET_QUERY_KEY_PATTERN",
    "WHATSAPP_HANDLE_PATTERN",
    "contains_receipt_sensitive_value",
    "receipt_safe_command_output",
    "receipt_safe_evidence",
    "receipt_safe_source_uri",
    "redacted_receipt_value",
    "safe_sha256_fingerprint",
    "shorten_receipt_value",
]
