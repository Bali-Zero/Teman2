#!/usr/bin/env python3
"""Read ONE key out of a 0600 credential file. Print its value, or fail loudly.

Why this is Python and not a line of shell. Two review rounds on the bash
version of this read found four distinct defects, all of them properties of
the instrument rather than of the intent: `head -n 1` closing a pipe so `sed`
took SIGPIPE and `set -euo pipefail` aborted the launcher (measured, exit
141); any stage's nonzero status propagating the same way; first-assignment
instead of last where `source` takes the last; and CRLF, trailing blanks,
escapes and mixed quotes silently producing a WRONG password — which lands
straight back in the fail-open this whole change exists to end. A credential
file must never be able to stop CELL from starting, and it must never be able
to hand it a value that is quietly not the password.

So the parse happens here, where each rule is one explicit line:

  * mode must be exactly 0600, or refuse (the posture scripts/pg.sh documents)
  * the LAST assignment wins, because `set -a; source` takes the last and two
    readers of one file must not disagree about what it says
  * `\r`, trailing blanks and a wrapping pair of quotes come off; blanks
    INSIDE quotes stay, because there they are deliberate
  * anything this parser cannot read UNAMBIGUOUSLY is refused, never guessed:
    backslash escapes, unbalanced or mid-value quotes, control bytes. Shell
    would resolve some of those with `eval`, and `eval` on a credential file
    is not a trade worth making.

Exit 0 and the value on stdout, or exit nonzero with a reason on stderr. The
value is NEVER written to stderr, and never appears in argv.

Usage:  read_secret_key.py <file> <KEY>
"""

from __future__ import annotations

import os
import re
import stat
import sys

# Deliberately conservative: printable ASCII except backslash and the quote
# characters, which are the forms this parser refuses to disambiguate. A
# password outside this set is not corrupted silently — it is reported.
_SAFE = re.compile(r"^[\x20-\x21\x23-\x26\x28-\x5b\x5d-\x7e]+$")


def _fail(msg: str) -> int:
    print(f"read_secret_key: {msg}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        return _fail("usage: read_secret_key.py <file> <KEY>")
    path, key = argv[1], argv[2]

    try:
        st = os.stat(path)
    except OSError as exc:
        return _fail(f"cannot stat {path}: {exc.strerror}")

    mode = stat.S_IMODE(st.st_mode)
    if mode != 0o600:
        return _fail(f"{path} mode {mode:04o} != 0600 — refusing to read {key} from it")

    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return _fail(f"cannot read {path}: {exc.strerror}")

    if b"\x00" in raw:
        return _fail(f"{path} contains NUL bytes — refusing to parse it")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _fail(f"{path} is not valid UTF-8 — refusing to parse it")

    prefix = key + "="
    value: str | None = None
    for line in text.splitlines():  # splitlines handles CRLF and lone CR
        if line.startswith(prefix):
            value = line[len(prefix) :]  # LAST assignment wins, like `source`
    if value is None:
        return _fail(f"{path} carries no {key} assignment")

    # Quotes come off only as a WRAPPING pair; blanks inside them are the
    # value. Unquoted trailing blanks are separators, which is what `source`
    # would have done with them too.
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    else:
        value = value.rstrip()

    if not value:
        return _fail(f"{path} carries an empty {key}")
    if not _SAFE.match(value):
        return _fail(
            f"{key} in {path} contains characters this reader refuses to "
            "disambiguate (backslash, quote or control byte) — fix the file "
            "rather than have a wrong value exported"
        )

    sys.stdout.write(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
