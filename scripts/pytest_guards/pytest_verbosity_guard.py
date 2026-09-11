"""Fail a pytest run whose effective verbosity hides the pass/fail tally.

`-q` inside a config's ``addopts`` already puts that root at verbosity ``-1``.
One more ``-q`` on the command line reaches ``-2``, and at ``-2`` pytest prints
no tally at all.

Measured 2026-08-29 in ``apps/backend-rag`` (whose ``pytest.ini`` addopts
carries ``-q``), same test file both times::

    $ python -m pytest backend/tests/unit/test_business_rules_i18n.py
    ...
    16 passed in 0.03s

    $ python -m pytest backend/tests/unit/test_business_rules_i18n.py -q
    ...
    (10 durations < 0.005s hidden.  Use -vv to show these durations.)

The second run's last line is the durations block. The count is simply gone,
and the exit code is ``0`` either way.

WHAT THIS PROTECTS, AND WHAT IT DOES NOT
----------------------------------------
A consumer that judges a run by its EXIT CODE is unaffected by verbosity, and
does not need this guard: pytest still exits ``5`` on "no tests collected" and
``2`` on a collection error — both measured 2026-08-29, at effective verbosity
``-2``, with ``--collect-only -q --noconftest``. Every committed invocation in
this repo is of that kind, so none of them was ever blind.

The consumer this protects is the one that reads the printed OUTPUT: a human,
or an agent that greps the tally to decide whether a change is verified. That
reader gets nothing to read at ``-2``, and a green exit with no number is not
evidence that anything ran. This exact instrument told this exact lie twice in
the night of 2026-08-28/29, ten hours apart, to a session that knew the rule
the second time — which is the argument for a guard rather than a convention.

Raising verbosity back works (measured: ``-q -v`` lands at ``-1`` and the tally
returns), so this is not a claim that quiet output is unreachable. It is a
claim that the last readable evidence a run produces must not vanish silently.
"""

from __future__ import annotations

import pytest

#: Effective verbosity at or below which pytest emits no pass/fail tally.
#: Measured, not read from documentation: at ``-1`` the tally is present, at
#: ``-2`` and ``-3`` it is absent.
SUMMARY_SUPPRESSED_AT = -2


def summary_is_suppressed(verbosity: int) -> bool:
    """Whether pytest prints no pass/fail tally at this effective verbosity."""
    return verbosity <= SUMMARY_SUPPRESSED_AT


def pytest_configure(config: pytest.Config) -> None:
    """Refuse to run when the tally would be suppressed.

    Raised as a ``UsageError`` so the run dies before collection with a
    readable message, rather than producing the unreadable green this guard
    exists to prevent.
    """
    verbosity = config.option.verbose
    if not summary_is_suppressed(verbosity):
        return

    configfile = getattr(config, "inipath", None)
    raise pytest.UsageError(
        f"effective verbosity is {verbosity}: pytest would print no pass/fail "
        "tally, so this run cannot be read as evidence that anything ran.\n"
        f"  config in force: {configfile if configfile else '<none>'}\n"
        "  cause          : this root's addopts already lower verbosity, and "
        "the command line lowered it again.\n"
        "  fix            : drop the extra -q from the command line — the "
        "config already sets it.\n"
        "  guard          : scripts/pytest_guards/pytest_verbosity_guard.py"
    )
