"""Atomic, owner-only writes for the loop's on-disk state.

Both files this package persists carry material that is nobody else's business:

  * `pending-drafts.json` holds the reply text we generated for a client, kept
    until the next run can compare it with what the human actually sent. A
    reply opens with a salutation, so it carries a name.
  * `reply-style.md` holds distilled habits. `style.py` redacts and drops a
    lesson that still trips its PII tripwire, so it is the safer of the two —
    but "safer" is not "public".

Left to the default umask these land 0644 inside a 0755 directory. That is
superscar #4 (personal data in the clear) waiting for the first person who
shares the machine, restores a backup, or points a sync client at $HOME — and
#4's own antidote is to enforce the mode at the moment of writing rather than
to remember a `chmod` later.

The temp file is created 0600 by `tempfile.mkstemp`, which opens with
`O_CREAT|O_EXCL` at that mode — so the private bytes are never on disk at a
wider one, and two processes cannot collide on the name.

The first version chmod'd AFTER writing, and its docstring claimed the content
was "never observable at a wider mode — not even for the microsecond between
creating it and tightening it". Adversarial review measured that claim and it
was false: the temp file held the bytes at 0644 for the whole window between
`write_text` and `chmod`, and what actually protected them was the 0700 parent,
which the comment did not credit. The claim is true now because the code
changed, not because the wording softened.

Atomicity claim, stated narrowly: the RENAME is atomic, so a reader never sees
a half-written file and an interrupted run leaves the previous contents intact.
It is NOT a concurrency protocol — two writers still race, and the last rename
wins. `ReplyStyleStore` holds a `threading.Lock` around its read-modify-write,
which covers threads in one process and nothing more; `PendingDrafts` has no
lock at all. That is adequate for a once-a-day cron and would not be for
anything else.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

__all__ = ["DIR_MODE", "FILE_MODE", "write_private"]

DIR_MODE = 0o700
FILE_MODE = 0o600


def write_private(path: Path, body: str) -> None:
    """Write `body` to `path` atomically and owner-only, dir included.

    `mkdir(mode=...)` applies only to directories this call actually creates,
    and umask still masks it, so every level is tightened explicitly — the
    intermediate levels too, since a 0700 leaf inside a 0755 parent still
    announces the leaf's name to everyone.

    A `chmod` that fails (an odd filesystem, a foreign owner) is left to raise:
    this is state we promised to keep private, and degrading quietly to 0644
    would be the promise breaking in silence.
    """
    parent = path.parent
    if parent == Path.home():
        # Tightening $HOME to 0700 would be a surprising, machine-wide side
        # effect of writing one state file. Reachable only by pointing
        # --state-dir or MAIL_LOOP_STATE_DIR at the home directory itself;
        # nothing in this repo does, and refusing costs one line.
        raise ValueError(
            f"refusing to write state directly into {parent} — it would chmod "
            "your home directory. Use a subdirectory."
        )

    created: list[Path] = []
    for ancestor in reversed(parent.parents):
        if not ancestor.exists():
            created.append(ancestor)
    if not parent.exists():
        created.append(parent)
    parent.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    for directory in created:
        os.chmod(directory, DIR_MODE)
    os.chmod(parent, DIR_MODE)

    fd, name = tempfile.mkstemp(dir=parent, prefix=f"{path.name}.", suffix=".tmp")
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        # mkstemp already creates at 0600. This makes FILE_MODE the single
        # source of truth, so changing the constant changes the file rather
        # than silently disagreeing with it.
        os.chmod(tmp, FILE_MODE)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(path)
