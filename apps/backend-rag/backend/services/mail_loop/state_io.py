"""Atomic, owner-only writes for the loop's on-disk state.

Both files this package persists carry material that is nobody else's business:

  * `pending-drafts.json` holds the reply text we generated for a client, kept
    until the next run can compare it with what the human actually sent. A
    reply opens with a salutation, so it carries a name.
  * `reply-style.md` holds distilled habits. `style.py` redacts and drops a
    lesson that still trips its PII tripwire, so it is the safer of the two —
    but "safer" is not "public".

Left to the default umask these land 0644 inside a 0755 directory. That is
superscar #4 (secret/personal data in the clear) waiting for the first person
who shares the machine, restores a backup, or points a sync client at $HOME —
and #4's own antidote is to enforce the mode at the moment of writing rather
than to remember a `chmod` later.

The write is atomic for a duller reason: a run interrupted mid-write must not
leave a half-written buffer that `_load` then reports as corrupt, silently
costing a cycle of learning. Temp file, fsync-free rename, done.

The temp name APPENDS `.tmp` instead of replacing the extension. `Path(
"pending-drafts.json").with_suffix(".tmp")` yields `pending-drafts.tmp`, which
is a different file from `reply-style.md.tmp` produced by the append form — two
call sites that looked alike were doing different things. One definition, one
shape.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["DIR_MODE", "FILE_MODE", "write_private"]

DIR_MODE = 0o700
FILE_MODE = 0o600


def write_private(path: Path, body: str, *, suffix: str = ".tmp") -> None:
    """Write `body` to `path` atomically, owner-only, creating the dir 0700.

    The mode is applied to the TEMP file before the rename, so the destination
    is never observable at a wider mode — not even for the microsecond between
    creating it and tightening it.

    `mkdir(mode=...)` only applies to directories this call actually creates,
    and umask still masks it, so an existing loose directory is tightened
    explicitly. A `chmod` that fails (an odd filesystem, a foreign owner) is
    left to raise: this is state we promised to keep private, and a silent
    fallback to 0644 would be the promise breaking quietly.
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    os.chmod(parent, DIR_MODE)

    tmp = path.with_name(path.name + suffix)
    tmp.write_text(body, encoding="utf-8")
    os.chmod(tmp, FILE_MODE)
    tmp.replace(path)
