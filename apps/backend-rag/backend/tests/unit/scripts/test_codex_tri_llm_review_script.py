"""Tests for the Pro-side tri-LLM review gate (scripts/codex_tri_llm_review.py).

Focus: the pure-logic surfaces that gate auto-merge eligibility — the robust
quorum (`compute_outcome`) and the diff-truncation fail-closed — plus the
review-only `post_pr_comment` path (mocked `gh`, no network).

Each test follows the cicatrix discipline (W64): assert the guardian both
PASSES the correct case AND blocks the wrong one. The two load-bearing
properties under test:
  - an env-down reviewer is NEVER counted as a non-green vote over a fixed
    denominator (it drops to "inconclusive", not "red");
  - a unanimous green over a TRUNCATED diff is NOT eligible (Codex P0).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _load_review_module() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[6]
    script_path = repo_root / "scripts" / "codex_tri_llm_review.py"
    spec = importlib.util.spec_from_file_location("codex_tri_llm_review_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


review = _load_review_module()


def _v(reviewer: str, verdict: str, *, error: str | None = None) -> object:
    return review.ReviewVerdict(reviewer=reviewer, verdict=verdict, error=error)


# ── compute_outcome: robust quorum over LIVE reviewers ───────────────────────


def test_all_three_green_is_green_and_eligible() -> None:
    outcome, green, eligible = review.compute_outcome(
        [_v("codex", "green"), _v("claude", "green"), _v("deepseek", "green")]
    )
    assert outcome == "green"
    assert green == 3
    assert eligible is True


def test_two_live_green_one_down_is_green_and_eligible() -> None:
    # The down reviewer must NOT drag the verdict to yellow/red over a fixed
    # denominator of 3 — decide over the 2 live reviewers only.
    outcome, green, eligible = review.compute_outcome(
        [_v("codex", "green"), _v("claude", "green"), _v("deepseek", "x", error="quota")]
    )
    assert outcome == "green"
    assert green == 2
    assert eligible is True


def test_any_live_red_is_red_not_eligible() -> None:
    outcome, _green, eligible = review.compute_outcome(
        [_v("codex", "green"), _v("claude", "red"), _v("deepseek", "green")]
    )
    assert outcome == "red"
    assert eligible is False


def test_mixed_green_yellow_is_yellow_not_eligible() -> None:
    outcome, green, eligible = review.compute_outcome(
        [_v("codex", "green"), _v("claude", "yellow"), _v("deepseek", "green")]
    )
    assert outcome == "yellow"
    assert green == 2
    assert eligible is False


def test_only_one_live_reviewer_is_inconclusive() -> None:
    # <2 live reviewers → cannot bind a verdict (env-down quorum, W64).
    outcome, _green, eligible = review.compute_outcome(
        [_v("codex", "green"), _v("claude", "x", error="down"), _v("deepseek", "x", error="down")]
    )
    assert outcome == "inconclusive"
    assert eligible is False


def test_zero_live_reviewers_is_inconclusive() -> None:
    outcome, green, eligible = review.compute_outcome(
        [_v("codex", "x", error="down"), _v("claude", "x", error="down")]
    )
    assert outcome == "inconclusive"
    assert green == 0
    assert eligible is False


# ── diff_complete fail-closed (Codex P0) ─────────────────────────────────────


def _decision(*, diff_complete: bool, outcome: str, eligible: bool) -> object:
    return review.PanelDecision(
        pr_number=1,
        branch="agent/x/infra/y",
        diff_sha="deadbeef",
        diff_lines=10,
        verdicts=[_v("codex", "green"), _v("claude", "green"), _v("deepseek", "green")],
        panel_outcome=outcome,
        green_count=3,
        auto_merge_eligible=eligible,
        timestamp="2026-06-10T00:00:00+0800",
        diff_complete=diff_complete,
    )


def test_panel_decision_defaults_diff_complete_true() -> None:
    # Back-compat: existing callers that don't pass diff_complete get True.
    d = review.PanelDecision(
        pr_number=None,
        branch=None,
        diff_sha="abc",
        diff_lines=0,
        verdicts=[],
        panel_outcome="inconclusive",
        green_count=0,
        auto_merge_eligible=False,
        timestamp="t",
    )
    assert d.diff_complete is True


def test_truncated_diff_comment_marks_not_reviewed() -> None:
    # A green-but-truncated decision: the comment must say "treat as NOT
    # reviewed" and surface diff_complete=False — never read as an approval.
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="https://github.com/x/y/pull/1#c", stderr="")

    d = _decision(diff_complete=False, outcome="inconclusive", eligible=False)
    posted = _call_post_comment(d, fake_run)
    assert posted is True
    body = _body_from_cmd(captured["cmd"])
    assert "diff_complete=False" in body
    assert "truncated" in body.lower()
    assert "NOT reviewed" in body


def test_comment_footer_states_review_only_legge5() -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    d = _decision(diff_complete=True, outcome="green", eligible=True)
    assert _call_post_comment(d, fake_run) is True
    body = _body_from_cmd(captured["cmd"])
    # The bot must explicitly disclaim merge authority (Legge 5).
    assert "operator's decision" in body
    assert "never labels, approves, or merges" in body.lower()


def test_comment_no_pr_number_skips() -> None:
    d = review.PanelDecision(
        pr_number=None,
        branch="b",
        diff_sha="s",
        diff_lines=0,
        verdicts=[],
        panel_outcome="green",
        green_count=0,
        auto_merge_eligible=False,
        timestamp="t",
    )
    called = {"n": 0}

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        called["n"] += 1
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    assert _call_post_comment(d, fake_run) is False
    assert called["n"] == 0  # never shells out without a PR number


def test_comment_gh_failure_returns_false() -> None:
    def fake_run(cmd, **kwargs):  # noqa: ANN001
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    d = _decision(diff_complete=True, outcome="green", eligible=True)
    assert _call_post_comment(d, fake_run) is False


# ── helpers ──────────────────────────────────────────────────────────────────


def _call_post_comment(decision: object, fake_run) -> bool:  # noqa: ANN001
    orig = review.subprocess.run
    review.subprocess.run = fake_run
    try:
        return review.post_pr_comment(decision)
    finally:
        review.subprocess.run = orig


def _body_from_cmd(cmd: object) -> str:
    assert isinstance(cmd, list)
    # gh pr comment <n> --repo R --body <BODY>
    idx = cmd.index("--body")
    return cmd[idx + 1]
