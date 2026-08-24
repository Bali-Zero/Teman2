"""The no-network guard's implementation, split out of ``conftest.py``.

Why a separate module: pytest auto-imports ``conftest.py`` under its own
internal module name (derived from directory discovery), which is NOT
guaranteed to be the same ``sys.modules`` entry as an explicit
``from backend.tests.duebot.conftest import ...`` elsewhere — even with
``--import-mode=importlib`` and ``pythonpath=.`` set. Two different module
objects for the "same" file means two different class objects for
``NetworkAccessBlockedError``, so a test file's
``pytest.raises(NetworkAccessBlockedError)`` silently fails to match the
instance the autouse fixture actually raises (measured directly while
building this harness — see the B6a report). Importing this exception and
the patch functions from a plain, non-conftest module — always addressed
by the SAME dotted path on both sides — sidesteps the ambiguity entirely.
"""

from __future__ import annotations

import socket
from typing import Any


class NetworkAccessBlockedError(RuntimeError):
    """Raised when code under test attempts a real network connection
    while running under ``backend/tests/duebot/``.
    """


def blocked_connect(self: socket.socket, address: Any, *a: Any, **kw: Any) -> None:
    raise NetworkAccessBlockedError(
        f"backend/tests/duebot forbids real network access — blocked "
        f"socket.connect() to {address!r}"
    )


def blocked_connect_ex(self: socket.socket, address: Any, *a: Any, **kw: Any) -> int:
    raise NetworkAccessBlockedError(
        f"backend/tests/duebot forbids real network access — blocked "
        f"socket.connect_ex() to {address!r}"
    )


def blocked_create_connection(address: Any, *a: Any, **kw: Any) -> socket.socket:
    raise NetworkAccessBlockedError(
        f"backend/tests/duebot forbids real network access — blocked "
        f"socket.create_connection() to {address!r}"
    )
