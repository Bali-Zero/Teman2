"""Event payload sanitization.

Layer 1 of safety rail: prevents prompt injection + oversized payloads
from reaching the Supervisor or Claude CLI.
"""
import json
import re


DENY_PATTERNS = [
    re.compile(r"IGNORE\s+PREVIOUS", re.IGNORECASE),
    re.compile(r"</system>", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"rm\s+-rf\s*/", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"curl\s+.*\|\s*(sh|bash)", re.IGNORECASE),
]

SHELL_METACHARS = ";|`$(){}[]<>&"


class DenyListHit(Exception):
    """Raised when payload contains a hardcoded deny-list pattern."""


def _strip_shell(value: str) -> str:
    return "".join(c for c in value if c not in SHELL_METACHARS)


def sanitize_payload(payload: dict, *, max_kb: int = 2) -> dict:
    """Sanitize event payload before storage/LLM.

    - Strips shell metacharacters from string values.
    - Raises DenyListHit on prompt-injection patterns.
    - Truncates to max_kb JSON bytes (default 2KB).
    """
    def _walk(obj):
        if isinstance(obj, str):
            for pat in DENY_PATTERNS:
                m = pat.search(obj)
                if m:
                    raise DenyListHit(
                        f"deny-list pattern matched: {pat.pattern!r} — hit: {m.group(0)!r}"
                    )
            return _strip_shell(obj)
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(v) for v in obj]
        return obj

    sanitized = _walk(payload)
    encoded = json.dumps(sanitized)
    limit = max_kb * 1024
    if len(encoded) > limit:
        # Preserve structure, truncate string fields proportionally
        for key in sanitized:
            if isinstance(sanitized[key], str) and len(sanitized[key]) > 100:
                overflow = len(encoded) - limit
                cut = min(len(sanitized[key]), overflow + 20)
                sanitized[key] = sanitized[key][: len(sanitized[key]) - cut] + "…"
                encoded = json.dumps(sanitized)
                if len(encoded) <= limit:
                    break
    return sanitized
