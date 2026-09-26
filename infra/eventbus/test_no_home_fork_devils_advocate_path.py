"""Regression: the devils-advocate spawn in meta_dispatcher.py must resolve
against the checkout, never a HOME-fork literal path.

PENDING-ARMS L1621 (cicatrix family #1, HOME-fork drift): the handler used to
hardcode ``/Users/nuzantara/scripts/eventbus/devils_advocate_runner.py`` in a
``subprocess.Popen`` call — a callee an invoker resolves by absolute path can
always drift from the repo copy, unlike a ``python -m`` invocation resolved
against ``REPO_ROOT``, which has no second copy to diverge from.
"""

from __future__ import annotations

import re
from pathlib import Path

_SOURCE = (Path(__file__).resolve().parent / "meta_dispatcher.py").read_text(encoding="utf-8")

_HOME_FORK_LITERAL = re.compile(r"/Users/nuzantara/scripts/eventbus/devils_advocate_runner\.py")
_MODULE_INVOCATION = re.compile(r'"-m",\s*"infra\.eventbus\.devils_advocate_runner"')


def test_no_hardcoded_home_path_to_devils_advocate_runner() -> None:
    assert not _HOME_FORK_LITERAL.search(_SOURCE), (
        "meta_dispatcher.py reintroduced a HOME-fork literal path to "
        "devils_advocate_runner.py (PENDING-ARMS L1621)"
    )


def test_devils_advocate_spawn_uses_checkout_resolved_module_invocation() -> None:
    assert _MODULE_INVOCATION.search(_SOURCE), (
        "meta_dispatcher.py's devils-advocate spawn must invoke "
        "`-m infra.eventbus.devils_advocate_runner`, resolved against REPO_ROOT"
    )
