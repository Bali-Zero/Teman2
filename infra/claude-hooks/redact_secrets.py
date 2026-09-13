#!/usr/bin/env python3
"""redact_secrets.py — shared secret redaction for Claude Code hook loggers.

Ports the earliest-anchor-cut design from `.claude/hooks/codex-spalla-trigger.sh`
(added there 2026-08-21 after a live leak — cicatrix superscar #4: an
unredacted per-call Bash logger printed real tokens to disk) into an
importable/CLI-usable function, so a new per-call logger does not have to
re-derive the same regex from a blank page. See that file's header for the
full derivation history (five leak-and-cure rounds); this module carries
only the shipped, functional shape.

Design: given a string, find the EARLIEST position matched by any
credential-shaped anchor (known token prefixes, a PEM private-key header,
URL userinfo, `Authorization: Basic <b64>`, bare `Bearer <token>`, or a
`NAME=value` / `NAME: value` assignment where NAME looks like a credential)
and replace everything from that position to the end of the string with
`<REDACTED>`. Nothing is rewritten in place and nothing is consumed twice —
each anchor is searched independently against the ORIGINAL string, so nothing
after the earliest anchor ever reaches disk. Accepted cost: a command whose
credential sits early loses the diagnostic tail that follows it. This is a
telemetry log, not a replayable transcript.

Declared residuals (inherited from the ported pattern, not re-litigated
here): a handful of narrow shapes still leak — see codex-spalla-trigger.sh's
own comment block for the exhaustive, measured list (KEY names outside a
bounded prefix vocabulary, single-segment attribute assignment, positional
secrets with no name, etc.). This module accepts the same trade the ported
pattern already made: over-redact a non-secret before under-redacting a
real one.
"""
from __future__ import annotations

import re

WIDE = r"(?:TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)"
PRE = (
    r"(?:API|AUTH|ACCESS|APP|CLIENT|PRIVATE|MASTER|ROOT|ADMIN|USER|SESSION"
    r"|REFRESH|OAUTH|BEARER|MY|ID|TOKEN|SECRET|PASSWORD|PASSWD"
    r"|CREDENTIAL)"
)
TAIL = r"S?[0-9]{0,8}(?:[_-][A-Za-z0-9]{1,64}){0,16}"
TAIL_ND = r"S?(?:[_-][A-Za-z0-9]{1,64}){0,16}"
NAME = (
    r"(?<![A-Za-z0-9.])(?:"
    + r"[A-Za-z0-9]*" + WIDE + TAIL  # a. any prefix + a wide credential word
    + r"|" + PRE + r"KEY" + TAIL  # b. vocabulary-prefixed KEY
    + r"|KEY" + TAIL_ND  # b. bare KEY, no digit-only suffix
    + r"|(?:PASS|PWD|AUTH)"  # c. bare generic name
    + r")"
)
VALUE = r"(?:\"[^\"]*\"|'[^']*'|[^\s\"']+)"

ANCHORS = (
    # Known credential shapes, by their own prefixes.
    r"sk-ant-[A-Za-z0-9_-]{8,}",
    r"gh[pousr]_[A-Za-z0-9]{8,}",
    r"github_pat_[A-Za-z0-9_]{8,}",
    r"xox[baprs]-[A-Za-z0-9-]{10,}",
    # A PEM private-key block.
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY[A-Z ]*-----",
    # URL userinfo: scheme://user:<secret>@host (including empty user, the
    # Redis form). Bounded runs keep this linear on long credential-free
    # input; the port-vs-password discriminator keeps a genuine host:port
    # followed later by an unrelated @ from anchoring.
    r"://[^\s:/@]{0,2048}:(?!\d+(?:/@|[/?#][^\s@]{0,2048}/))[^\s@]{1,2048}@",
    # Authorization: Basic <base64>, requiring a digit or +/= so ordinary
    # prose ("Basic auth support") stays innocent.
    r"(?i)Authorization:\s*Basic\s+(?=[A-Za-z0-9+/=]{16,})[A-Za-z0-9+/=]*[0-9+/=][A-Za-z0-9+/=]*",
    # Bearer <token>, which carries no keyword in a NAME at all.
    r"(?i)\b(?:Bearer)\s+[A-Za-z0-9._~+/=-]{8,}",
    # Anything ASSIGNED to a credential-ish NAME (env-style, JSON body, or
    # `NAME: value`). The \* before the optional quote covers a JSON body
    # reaching this hook through nested shell quoting (`\"api_key\": <v>`).
    r"(?i)" + NAME + r"\\*[\"']?\s*[=:]\s*" + VALUE,
)
_COMPILED = tuple(re.compile(p) for p in ANCHORS)


def redact(text: str) -> str:
    """Return `text` with everything from the earliest credential anchor cut.

    Never raises — a regex engine error (should not happen with these fixed
    patterns) falls back to returning the input unchanged rather than
    crashing a fail-open logging hook.
    """
    if not text:
        return text
    try:
        starts = [m.start() for m in (p.search(text) for p in _COMPILED) if m]
    except Exception:
        return text
    if starts:
        return text[: min(starts)] + "<REDACTED>"
    return text


def main() -> None:
    import sys

    data = sys.stdin.read()
    sys.stdout.write(redact(data))


if __name__ == "__main__":
    main()
