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
    limit = max_kb * 1024

    def _encoded_len() -> int:
        return len(json.dumps(sanitized, default=str))

    if _encoded_len() > limit:
        # Collect all (parent, key, value) triples where value is a long string
        # Sorted by string length descending so we trim worst offenders first.
        def _walk_strings(obj, path=()):
            results = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    results.extend(_walk_strings(v, path + (k,)))
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    results.extend(_walk_strings(v, path + (i,)))
            elif isinstance(obj, str) and len(obj) > 20:
                results.append((path, obj))
            return results

        def _set_at(path, value):
            cursor = sanitized
            for step in path[:-1]:
                cursor = cursor[step]
            cursor[path[-1]] = value

        string_entries = sorted(_walk_strings(sanitized), key=lambda t: -len(t[1]))
        for path, value in string_entries:
            if _encoded_len() <= limit:
                break
            overflow = _encoded_len() - limit
            cut = min(len(value) - 1, overflow + 20)
            if cut <= 0:
                continue
            _set_at(path, value[: len(value) - cut] + "…")

    return sanitized
