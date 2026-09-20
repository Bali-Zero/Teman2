#!/usr/bin/env python3
"""redact_for_external.py — strip values before any text leaves this machine.

Builder Contract §4 is an OUTPUT boundary: it does not care that the output is a
code review rather than a client report. Anything sent to a third-party endpoint
passes through here first.

The design rule that makes this safe for a *semantic* lint: redact VALUES, keep
STRUCTURE. A judge deciding whether a vendor client is being built with a paid
credential needs the call, the keyword argument and the fact that a literal is
there — it does not need the literal. So a constructor written with a live key
comes out as:

    VendorClient(api_key="<REDACTED:secret>")

which carries every bit of the signal and none of the credential. Over-redaction
is the failure mode to avoid here; a lint that redacts the function name cannot
judge anything.

NB: the examples above deliberately do NOT spell the banned Anthropic
constructor. catE-sovereignty-lint counts that spelling repo-wide against a
budget of three, and it cannot tell prose about the pattern from a use of it —
which is the very over-match this module's caller exists to adjudicate. Writing
the literal here would have spent a third of that budget on a docstring.

The name prefix is OPTIONAL in every rule: the first version required at
least one character before the sensitive word, so a variable literally
called TOKEN or SECRET was not redacted at all. Found by the
codex-gpt-5.6-sol council seat, 2026-09-20.

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
    # AWS access key id. Its absence was noted as ironic by a council seat,
    # since the unquoted-assignment scar that preceded it used an AWS key.
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]

# `TOKEN = "...."` / `"password": "...."` — the name says it is a credential, so
# the value goes regardless of its shape.
_NAMED_ASSIGNMENT = re.compile(
    r"""(?ix)
    (?P<name>\b[A-Za-z_]?[A-Za-z0-9_]*
        (?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|DSN)\b)
    (?P<sep>\s*[:=]\s*)
    (?P<quote>['"])
    (?P<value>[^'"\n]{4,})
    (?P=quote)
    """
)

# The unquoted form — `AWS_SECRET_ACCESS_KEY: wJalr...` in YAML, `TOKEN=abc` in
# a shell line. The quoted rule above silently did not cover it, so a live
# credential went to a third-party endpoint byte-for-byte. Found by an
# adversarial reviewer on 2026-09-20 with a real AWS key shape; it is the worst
# class of bug this module can have, because the module IS the §4 boundary.
_NAMED_ASSIGNMENT_BARE = re.compile(
    r"""(?ix)
    (?P<name>\b[A-Za-z_]?[A-Za-z0-9_]*
        (?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|DSN)\b)
    (?P<sep>\s*[:=]\s*)
    (?P<value>[^\s'"#][^\s#]{3,})
    """
)

# A JSON or dict key puts a quote between the name and the colon, so the two
# assignment rules above — which need the name adjacent to `[:=]` — both miss
# `{"api_key": "opaque-value"}`. An opaque value matches no literal shape
# either, so it left verbatim. Third redaction hole found by review rather than
# by the author. Found by the kimi-code/k3 council seat, 2026-09-20.
_QUOTED_KEY_ASSIGNMENT = re.compile(
    r"""(?ix)
    (?P<open>['"])
    (?P<name>[A-Za-z_]?[A-Za-z0-9_]*
        (?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|DSN))
    (?P=open)
    (?P<sep>\s*:\s*)
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
    out = _QUOTED_KEY_ASSIGNMENT.sub(
        lambda m: (
            f"{m['open']}{m['name']}{m['open']}{m['sep']}"
            f"{m['quote']}<REDACTED:secret>{m['quote']}"
        ),
        out,
    )
    out = _NAMED_ASSIGNMENT_BARE.sub(
        lambda m: f"{m['name']}{m['sep']}<REDACTED:secret>", out
    )
    out = _EMAIL.sub("<REDACTED:email>", out)
    return out


def redact_lines(lines: list[str]) -> list[str]:
    return [redact(line) for line in lines]
