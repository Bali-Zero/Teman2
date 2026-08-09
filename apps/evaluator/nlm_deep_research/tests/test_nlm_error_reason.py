"""An `nlm` failure must arrive with its reason attached (2026-08-09).

TRAUMA, measured on Pro: `nlm notebook list` on an expired session exits 1,
writes **0 bytes to stderr**, and prints to STDOUT

    ✗ Authentication Error
      Authentication expired. Run 'nlm login' in your terminal to re-authenticate.

Fourteen call sites in this package logged `result.stderr.strip()` as the
reason, so for three months the logs read "nlm source add failed: " with
nothing after the colon. `~/logs/cron-tmp/nlm-nb3-pipeline.log` holds 68 such
lines going back to 2026-05-04.

That empty sentence is what let a real regression hide: NB-3 is **7-for-7
failed in August** against 22-of-23 succeeded in July, but the August total
outage and the old ~40% intermittency print the identical line, so no reader
could tell them apart. Same family as W104 (`redis-cli` exits 0 and puts NOAUTH
on stdout): judge the REPLY, and read the stream the tool actually writes to.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.nlm_bridge import nlm_error_reason

PKG = Path(__file__).resolve().parent.parent


def _proc(returncode=1, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["nlm"], returncode=returncode,
                                       stdout=stdout, stderr=stderr)


# ── guilt ────────────────────────────────────────────────────────────────────

def test_the_measured_reply_is_surfaced_not_swallowed():
    """The exact bytes Pro produced on 2026-08-09, stderr empty."""
    reason = nlm_error_reason(_proc(
        stdout="\n✗ Authentication Error\n  Authentication expired. Run 'nlm login' "
               "in your terminal to re-authenticate.\n",
        stderr="",
    ))
    assert "Authentication expired" in reason
    assert reason != ""


def test_an_expired_session_names_its_own_cure():
    reason = nlm_error_reason(_proc(stdout="✗ Authentication Error\n  Authentication expired."))
    assert reason.startswith("AUTH_EXPIRED")
    assert "nlm login" in reason


def test_a_silent_failure_still_says_something():
    """Both streams empty must not produce a log line ending in a colon."""
    reason = nlm_error_reason(_proc(returncode=7))
    assert reason.strip()
    assert "7" in reason


def test_the_reason_is_one_line_and_bounded():
    reason = nlm_error_reason(_proc(stdout="a\n\n   b\tc" + "x" * 500), limit=40)
    assert "\n" not in reason and "\t" not in reason
    assert reason.startswith("a b c")
    assert len(reason) == 40


# ── innocence ────────────────────────────────────────────────────────────────

def test_stderr_still_wins_when_the_tool_does_use_it():
    reason = nlm_error_reason(_proc(stdout="progress noise", stderr="connection refused"))
    assert reason == "connection refused"


def test_an_ordinary_failure_gets_no_auth_prefix():
    reason = nlm_error_reason(_proc(stderr="notebook 933509f9 not found"))
    assert not reason.startswith("AUTH_EXPIRED")
    assert reason == "notebook 933509f9 not found"


def test_a_success_shaped_result_is_not_special_cased():
    """The helper only ever runs on a failure — it must not invent one."""
    reason = nlm_error_reason(_proc(returncode=0, stdout="ok"))
    assert reason == "ok"


# ── the class, not just the instance (W107) ──────────────────────────────────

def test_no_nlm_failure_in_this_package_reports_from_stderr_alone():
    """Every logger call that NAMES nlm must not take its reason from stderr only.

    Anchored on the message text naming the tool, so the Gemini-CLI call sites
    in freshness_monitor/gap_scanner — which legitimately do use stderr — are
    out of scope. DECLARED LIMIT: this sees logger calls whose format string is
    a literal; a message built elsewhere is invisible to it.
    """
    offenders = []
    for path in sorted(PKG.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"error", "warning", "info", "critical"}:
                continue
            if not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            msg = str(node.args[0].value)
            if "nlm " not in msg.lower():
                continue
            for arg in node.args[1:]:
                src = ast.unparse(arg)
                if "stderr" in src and "nlm_error_reason" not in src:
                    offenders.append(f"{path.name}:{node.lineno}: {msg[:48]!r} <- {src}")
    assert not offenders, "nlm failures reporting from stderr alone:\n  " + "\n  ".join(offenders)


@pytest.mark.parametrize("module", [
    "cross_notebook_correlator", "db_to_nlm_sync", "freshness_monitor", "gap_scanner",
    "nlm_bridge", "ops_intelligence", "persona_engine", "source_snapshot",
    "synthesis_roller", "yt_monitor",
])
def test_every_rewired_module_can_reach_the_shared_reader(module):
    """The import must not break its host AND must actually bind the name.

    The first attempt at this rewiring inserted the import INSIDE a
    parenthesised multi-line import block in db_to_nlm_sync.py — a SyntaxError.
    A second failure mode is subtler and silent: the module imports fine while
    the name never binds, so every rewired call site would raise NameError only
    on the failure path, i.e. exactly when it is needed.
    """
    import importlib

    mod = importlib.import_module(f"apps.evaluator.nlm_deep_research.{module}")
    assert getattr(mod, "nlm_error_reason", None) is nlm_error_reason
