"""Tests for the async review supervisor (ship #3 V1 — LABEL+BLOCK, never revert).

These assert the STADIO-0 falsifiable acceptance criteria:
- PII per-path gate routes risky diffs away from the cloud reviewer
- outcome → action mapping is correct (red blocks, green/yellow/inconclusive don't)
- the supervisor NEVER carries destructive-gh intent (no merge/close/revert/branch -D)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_supervisor_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "async_review_supervisor.py"
    spec = importlib.util.spec_from_file_location("async_review_supervisor_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sup = _load_supervisor_module()


# --- PII per-path gate --------------------------------------------------------

def test_pii_gate_flags_kb_fixtures_crm_paths() -> None:
    files = [
        "apps/backend-rag/backend/kb/visa.json",
        "apps/backend-rag/backend/tests/fixtures/sample_ktp.json",
        "apps/mouth/src/crm/client_card.tsx",
        "research/visa/clients/marta-reyes-case.md",
        "OSINT-Nexus/target.json",
    ]
    hits = sup.pii_risk(files)
    assert set(hits) == set(files), "every PII-path file must be flagged"


def test_pii_gate_lets_plain_code_through() -> None:
    files = [
        "scripts/async_review_supervisor.py",
        "apps/backend-rag/backend/app/routers/health.py",
        "docs/runbooks/something.md",
    ]
    assert sup.pii_risk(files) == [], "plain code must NOT be flagged as PII-risk"


# --- outcome → action mapping -------------------------------------------------

def test_red_outcome_blocks_merge() -> None:
    action = sup.plan_action("red", pii_files=[])
    assert action["label"] == "review:auto-reject"
    assert action["check"] == "failure"
    assert action["blocks"] is True


@pytest.mark.parametrize("outcome", ["green", "yellow", "inconclusive"])
def test_non_red_outcomes_do_not_block(outcome: str) -> None:
    action = sup.plan_action(outcome, pii_files=[])
    assert action["blocks"] is False, f"{outcome} must never block merge"
    assert action["check"] != "failure"


def test_unknown_outcome_defaults_to_needs_human_not_block() -> None:
    action = sup.plan_action("garbage-outcome", pii_files=[])
    assert action["blocks"] is False
    assert action["label"] == "review:needs-human"


# --- PII overrides label but never escalates a green/yellow to a block --------

def test_pii_files_relabel_but_do_not_block_a_green() -> None:
    action = sup.plan_action("green", pii_files=["apps/backend-rag/backend/kb/x.json"])
    assert action["pii_local_only"] is True
    assert action["label"] == "review:pii-local-only"
    assert action["blocks"] is False


def test_pii_files_do_not_downgrade_a_red_block() -> None:
    # A real RED defect must still block even when PII files are present.
    action = sup.plan_action("red", pii_files=["apps/backend-rag/backend/kb/x.json"])
    assert action["blocks"] is True
    assert action["label"] == "review:auto-reject"  # red label wins over pii relabel
    assert action["pii_local_only"] is True


# --- LOAD-BEARING: the supervisor must never carry destructive intent ---------

@pytest.mark.parametrize(
    "outcome", ["green", "yellow", "red", "inconclusive", "garbage-outcome"]
)
def test_no_planned_action_implies_destructive_gh_op(outcome: str) -> None:
    for pii in ([], ["apps/backend-rag/backend/kb/x.json"]):
        action = sup.plan_action(outcome, pii_files=pii)
        # Must not raise — the guard proves no merge/close/revert/branch-delete intent.
        sup._assert_no_destructive_intent(action)
        # Explicit: the planned action's stringified form carries no destructive token.
        blob = repr(action).lower()
        assert not any(tok in blob for tok in sup._FORBIDDEN_GH), (
            f"planned action for {outcome} must carry zero destructive-gh intent: {action}"
        )


def test_guard_actually_rejects_a_destructive_action() -> None:
    # Negative control: the guard is real, not a no-op.
    with pytest.raises(RuntimeError, match="forbidden destructive"):
        sup._assert_no_destructive_intent({"label": "review:auto-reject", "note": "gh pr merge --auto"})


def test_source_contains_no_destructive_gh_calls() -> None:
    # The script's own source must never call merge/close/revert/branch -D.
    repo_root = Path(__file__).resolve().parents[6]
    src = (repo_root / "scripts" / "async_review_supervisor.py").read_text()
    for forbidden in ("gh pr merge", "gh pr close", "git revert", "branch -D", "branch --delete"):
        # allowed only inside the _FORBIDDEN_GH guard tuple / docstring, never as an actual call
        # heuristic: forbidden token must not appear in a subprocess/run/Popen context
        for line in src.splitlines():
            if forbidden in line and any(
                tok in line for tok in ("subprocess", "run(", "Popen", "os.system", "check_call")
            ):
                pytest.fail(f"destructive gh op '{forbidden}' used in a call site: {line!r}")


# --- comment rendering --------------------------------------------------------

def test_render_comment_states_never_reverts() -> None:
    action = sup.plan_action("red", pii_files=[])
    body = sup.render_comment("red", action, green=0, live=3)
    assert "never reverts" in body.lower()
    assert "blocks merge" in body.lower()
