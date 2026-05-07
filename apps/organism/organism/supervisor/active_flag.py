"""W2 active-mode kill switch — file-based flag.

Why a file (not env var, Redis key, etc.):
- Reachable in <1s without restarting the daemon (`echo 0 > flag` flips it).
- Survives reboot (boot-time launchd reads it on first run_once cycle).
- mtime gives audit trail when an operator paged a flip.
- No external dependency: works even if Redis is down.

Semantics:
- File missing → inactive (shadow).
- File contents `"1"` (after strip) → active (W2 dispatch).
- Anything else (`"0"`, `""`, garbage) → inactive.

The flag is re-read on every `is_active()` call. Do NOT cache: the operator
flips it without restarting the daemon, and the daemon must observe the
change on the very next supervise cycle.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path


log = logging.getLogger(__name__)


@dataclass
class ActiveFlag:
    path: Path

    def is_active(self) -> bool:
        try:
            return self.path.read_text().strip() == "1"
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            return False
        except OSError:
            log.exception("active_flag: unexpected read error at %s", self.path)
            return False
