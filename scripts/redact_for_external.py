#!/usr/bin/env python3
"""redact_for_external.py — strip values before any text leaves this machine.

Builder Contract §4 is an OUTPUT boundary: it does not care that the output is a
code review rather than a client report. Anything sent to a third-party endpoint
passes through here first.

The design rule that makes this safe for a *semantic* lint: redact VALUES, keep
STRUCTURE. A judge deciding whether `Anthropic(api_key="sk-live-abc123")` reaches
a paid endpoint needs the call, the keyword and the fact that a literal is there
— it does not need the literal. So the output is:

    Anthropic(api_key="<REDACTED:secret>")

which carries every bit of the signal and none of the credential. Over-redaction
is the failure mode to avoid here; a lint that redacts the function name cannot
judge anything.

Stdlib only — this runs in CI.
"""

from __future__ import annotations

import re

# Value shapes that are credentials wherever they appear. Ordered longest-first
# so a specific prefix wins over the generic long-token rule.
_SECRET_LITERALS: list[re.Pattern[str]] = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bant-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bapikey_[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAIza[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+"),
    re.compile(r"\bfm2_[A-Za-z0-9_\-]{20,}"),
]

# `TOKEN = "...."` / `"password": "...."` — the name says it is a credential, so
# the value goes regardless of its shape.
_NAMED_ASSIGNMENT = re.compile(
    r"""(?ix)
    (?P<name>\b[A-Za-z_][A-Za-z0-9_]*
        (?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|DSN)\b)
    (?P<sep>\s*[:=]\s*)
    (?P<quote>['"])
    (?P<value>[^'"\n]{4,})
    (?P=quote)
    """
)

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# A DSN carries user:password@host. Keep the scheme and the host; drop the middle.
_DSN_CREDENTIALS = re.compile(r"\b(?P<scheme>[a-z][a-z0-9+.\-]*://)[^\s/@:]+:[^\s/@]+@")


def redact(text: str) -> str:
    """Return `text` with credential VALUES replaced and structure intact."""
    out = text
    for pattern in _SECRET_LITERALS:
        out = pattern.sub("<REDACTED:secret>", out)
    out = _DSN_CREDENTIALS.sub(r"\g<scheme><REDACTED:dsn-credentials>@", out)
    out = _NAMED_ASSIGNMENT.sub(
        lambda m: f"{m['name']}{m['sep']}{m['quote']}<REDACTED:secret>{m['quote']}", out
    )
    out = _EMAIL.sub("<REDACTED:email>", out)
    return out


def redact_lines(lines: list[str]) -> list[str]:
    return [redact(line) for line in lines]
