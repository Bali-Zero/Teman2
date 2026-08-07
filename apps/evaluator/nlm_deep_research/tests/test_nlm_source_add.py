"""Guilt + innocence for `nlm_source_add`: the diagnosis, and the sentinel.

The CLI output below is not invented. It is what `nlm source add … --wait`
printed on Pro on 2026-08-07 when probed directly (a throwaway source, added
and then deleted, residue verified at zero):

    Adding text and waiting for processing...
    ✓ Added source: ZZ-PROBE-2026-08-07-delete-me (ready)
    Source ID: ae22e663-2199-41ca-9abd-29fc1c8f7552

Prose, not JSON — `nlm source add` has no `--json` flag. That is why the JSON
branch had never once matched, and why all 279 recorded source_ids across the
eight synthesis state files were the literal string "ok".
"""

from __future__ import annotations

import logging
import subprocess
from types import SimpleNamespace

import pytest

from apps.evaluator.nlm_deep_research import synthesis_roller as sr

REAL_OUTPUT = (
    "Adding text and waiting for processing...\n"
    "✓ Added source: ZZ-PROBE-2026-08-07-delete-me (ready)\n"
    "Source ID: ae22e663-2199-41ca-9abd-29fc1c8f7552\n"
)


def _run(monkeypatch, *, rc: int, stdout: str = "", stderr: str = ""):
    monkeypatch.setattr(
        sr.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=rc, stdout=stdout, stderr=stderr),
    )
    return sr.nlm_source_add("nb-id", title="t", text="body")


# --- the diagnosis: a failure must never log a blank reason ----------------


def test_a_failure_with_output_only_on_stdout_is_still_diagnosed(monkeypatch, caplog):
    """The exact shape that produced six blank nights: rc!=0, stderr empty."""
    caplog.set_level(logging.ERROR)
    assert _run(monkeypatch, rc=1, stdout="Error: notebook not found", stderr="") is None
    logged = caplog.text
    assert "notebook not found" in logged, "the only diagnosis available was dropped"
    assert "rc=1" in logged


def test_a_failure_with_nothing_anywhere_SAYS_it_has_nothing(monkeypatch, caplog):
    """Silence must be stated, not rendered as an empty string after a colon."""
    caplog.set_level(logging.ERROR)
    assert _run(monkeypatch, rc=2, stdout="", stderr="") is None
    assert "both streams empty" in caplog.text
    assert not caplog.text.rstrip().endswith(":"), "blank reason is the defect"


def test_stderr_is_still_reported_when_it_does_carry_the_error(monkeypatch, caplog):
    """Innocence for the original behaviour: stderr must not be lost."""
    caplog.set_level(logging.ERROR)
    assert _run(monkeypatch, rc=1, stderr="Authentication expired") is None
    assert "Authentication expired" in caplog.text


# --- the sentinel: widen the parse, never tighten the branch ---------------


def test_the_real_cli_output_yields_the_real_source_id(monkeypatch):
    """279/279 stored ids were "ok" because the id is printed as prose."""
    assert _run(monkeypatch, rc=0, stdout=REAL_OUTPUT) == "ae22e663-2199-41ca-9abd-29fc1c8f7552"


def test_json_output_still_wins_if_the_cli_ever_grows_json(monkeypatch):
    assert _run(monkeypatch, rc=0, stdout='{"value": {"source_id": "abc-123"}}') == "abc-123"


def test_unparseable_success_still_returns_the_TRUTHY_sentinel(monkeypatch):
    """DECLARED, not an oversight. Callers gate the weekly/monthly roll-up on
    `if sid:` and consume the stored TEXT, never the id — so returning None on
    an output we cannot parse would trade a mislabelled map for a DEAD roll-up.
    Widening the parse is safe; tightening this branch is a regression."""
    out = _run(monkeypatch, rc=0, stdout="✓ Added source: something (ready)")
    assert out == "ok"
    assert bool(out) is True


def test_an_empty_stdout_on_success_is_also_the_sentinel(monkeypatch):
    assert _run(monkeypatch, rc=0, stdout="") == "ok"


# --- the failure paths that bypass returncode entirely ---------------------


@pytest.mark.parametrize(
    "exc", [subprocess.TimeoutExpired(cmd="nlm", timeout=1), FileNotFoundError(), RuntimeError("boom")]
)
def test_every_exception_path_returns_None_and_names_itself(monkeypatch, caplog, exc):
    caplog.set_level(logging.ERROR)

    def _raise(*a, **k):
        raise exc

    monkeypatch.setattr(sr.subprocess, "run", _raise)
    assert sr.nlm_source_add("nb", title="t", text="b") is None
    assert caplog.text.strip(), "a swallowed exception is a blank night"
