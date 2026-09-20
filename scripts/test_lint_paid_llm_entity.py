#!/usr/bin/env python3
"""Tests for lint_paid_llm_entity.py.

Two halves, deliberately separated because they cost different things:

  pytest scripts/test_lint_paid_llm_entity.py
      Offline. No network, no key. Covers redaction, scope, the transcribed
      grep predicate, and the OR-composition — including the case that matters
      most: a service returning nothing must not turn into a pass or a crash.

  python3 scripts/test_lint_paid_llm_entity.py --bench
      Online. Runs the 39-case corpus against the live model and prints recall
      on the guilt half, false-alarm rate on the innocence half, and — the
      number the lane exists for — recall on the guilt cases today's grep
      misses. Not a pytest test: it costs money and needs a key, so CI never
      runs it and a human reads its output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lint_paid_llm_entity as lint  # noqa: E402
from redact_for_external import redact  # noqa: E402

CASES = json.loads(
    (
        Path(__file__).parent / "tests/fixtures/paid_llm_entity/bench_cases.json"
    ).read_text()
)


# ─────────────────────────────────────────────────────────────────── redaction


# These two need a credential-SHAPED string, because that is the thing being
# redacted. They build it at runtime rather than committing the literal: a
# key-shaped token in git trips the repo's hardcoded-secret guard, and rightly
# so — the guard cannot tell a fixture from the real thing, and neither can a
# scraper. Assembling it here keeps the test honest and the repo clean.
FAKE_KEY = "sk-" + "ant-" + "abcdefghijklmnop0123"


def test_redaction_keeps_structure_drops_value():
    out = redact(f'client = Anthropic(api_key="{FAKE_KEY}")')
    assert "Anthropic(api_key=" in out, "structure must survive or the judge is blind"
    assert "abcdefghijklmnop0123" not in out


def test_redaction_handles_named_assignment():
    out = redact('UPSTREAM_TOKEN = "hunter2hunter2hunter2"')
    assert "hunter2hunter2hunter2" not in out
    assert "UPSTREAM_TOKEN" in out


def test_redaction_strips_dsn_credentials_keeps_scheme():
    out = redact("postgres://admin:s3cr3tpw@db.internal:5432/nuzantara")
    assert "s3cr3tpw" not in out
    assert out.startswith("postgres://")


def test_redaction_strips_email():
    assert "@" not in redact("contact zero@balizero.com").split("REDACTED")[-1]


# ───────────────────────────────────────────────────────────────────── scoping


@pytest.mark.parametrize(
    "path,expected",
    [
        ("scripts/foo.py", True),
        ("apps/mouth/src/x.ts", True),
        ("docs/readme.md", False),
        ("scripts/tests/fixtures/paid_llm_entity/bench_cases.json", False),
        ("apps/x/.venv/lib/thing.py", False),
        ("apps/x/tests/test_thing.py", False),
        ("scripts/test_lint_paid_llm_entity.py", False),
    ],
)
def test_in_scope(path, expected):
    assert lint.in_scope(path) is expected


def test_prefilter_lets_plain_code_through_unasked():
    assert lint.worth_asking("def add(a, b):\n    return a + b\n") is False


def test_prefilter_is_generous_about_anything_llm_shaped():
    assert lint.worth_asking("resp = requests.post(url, json=payload)") is True


# ──────────────────────────────────────────── the transcribed grep predicate


def test_grep_matches_the_canonical_constructor():
    case = next(
        c for c in CASES["guilt"] if c["name"].startswith("canonical_constructor")
    )
    assert lint.grep_verdict(case["content"]) is True


def test_grep_matches_the_canonical_export():
    case = next(c for c in CASES["guilt"] if c["name"].startswith("canonical_export"))
    assert lint.grep_verdict(case["content"]) is True


@pytest.mark.parametrize(
    "case", [c for c in CASES["guilt"] if c["missed_by_grep"]], ids=lambda c: c["name"]
)
def test_grep_misses_every_case_marked_missed(case):
    """The corpus must not lie about what the incumbent catches.

    If this fails, a case labelled `missed_by_grep` is in fact caught, and the
    lane's headline number would be inflated by it.
    """
    assert lint.grep_verdict(case["content"], f"case{case['suffix']}") is False


@pytest.mark.parametrize("case", CASES["innocence"], ids=lambda c: c["name"])
def test_grep_does_not_fire_on_innocence_cases(case):
    assert lint.grep_verdict(case["content"], f"case{case['suffix']}") is False


def test_grep_is_suffix_scoped_exactly_like_cate():
    """A yaml quoting the banned constructor is NOT what catE scans.

    This is the regression for a real bug this corpus found: the first version
    transcribed catE's PATTERNS without its --include file sets, so a CI yaml
    written to FAIL a build on the pattern was itself condemned by it. Widening
    a guard's file set while calling it a transcription widens the OVER-matching
    half — cicatrix #3, committed by the lint written to cure cicatrix #3.
    """
    yaml_case = next(
        c for c in CASES["innocence"] if c["name"] == "test_asserting_the_ban"
    )
    assert lint.grep_verdict(yaml_case["content"], "check.yml") is False
    assert lint.grep_verdict(yaml_case["content"], "check.py") is True, (
        "in a .py file the same text IS what catE condemns — the scoping is the "
        "whole difference, so this half must keep failing"
    )


# ─────────────────────────────────────────────────────── OR-composition, offline


def test_no_key_means_grep_verdict_stands(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    case = next(
        c for c in CASES["guilt"] if c["name"].startswith("canonical_constructor")
    )
    result = lint.judge_file("x.py", case["content"])
    assert result["asked"] is False
    assert result["violation"] is True, "the grep half must keep working without a key"


def test_no_key_does_not_invent_violations(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    case = next(c for c in CASES["guilt"] if c["name"] == "aliased_import")
    result = lint.judge_file("x.py", case["content"])
    assert result["violation"] is False, (
        "degrades to today's behaviour, no more no less"
    )


def test_service_silence_is_not_a_pass(monkeypatch):
    """An unreachable service must not clear a file the grep condemns.

    This is the OR rule under its worst condition and the reason `ask()` returns
    None rather than a falsy verdict.
    """
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(lint, "ask", lambda *a, **k: None)
    case = next(
        c for c in CASES["guilt"] if c["name"].startswith("canonical_constructor")
    )
    assert lint.judge_file("x.py", case["content"])["violation"] is True


def test_model_saying_no_cannot_clear_the_grep(monkeypatch):
    """The core anti-AND test.

    Even with every route answered 0.0, a file the grep condemns stays
    condemned. If this test ever fails, the composition has been inverted and a
    model false negative can open the gate.
    """
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(
        lint,
        "ask",
        lambda *a, **k: {
            r: {"type": "noul", "noul": 0.0} for r in lint.ROUTE_QUESTIONS
        },
    )
    case = next(
        c for c in CASES["guilt"] if c["name"].startswith("canonical_constructor")
    )
    assert lint.judge_file("x.py", case["content"])["violation"] is True


def test_model_alone_can_add_a_violation(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(
        lint,
        "ask",
        lambda *a, **k: {"wrapper_library": {"type": "noul", "noul": 0.95}},
    )
    case = next(c for c in CASES["guilt"] if c["name"] == "litellm_wrapper")
    result = lint.judge_file("x.py", case["content"])
    assert result["violation"] is True
    assert result["fired_routes"] == ["wrapper_library"]


def test_probability_below_threshold_does_not_fire(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(
        lint,
        "ask",
        lambda *a, **k: {"wrapper_library": {"type": "noul", "noul": 0.5}},
    )
    case = next(c for c in CASES["guilt"] if c["name"] == "litellm_wrapper")
    assert lint.judge_file("x.py", case["content"])["violation"] is False


def test_redaction_runs_before_the_payload_leaves(monkeypatch):
    """A credential in the source must not be in what we send."""
    seen: dict = {}
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(lint, "ask", lambda state, q: seen.update(state) or None)
    lint.judge_file("x.py", f'k = "{FAKE_KEY}"\nimport anthropic\n')
    assert "abcdefghijklmnop0123" not in json.dumps(seen)


# ─────────────────────────────────────────────────────────────────────── bench


def _run_bench() -> int:
    from typesafe_client import available

    if not available():
        print("TYPESAFE_API_KEY absent — the bench needs it. Nothing run.")
        return 2

    guilt_hit = missed_hit = missed_total = 0
    false_alarm = 0
    rows: list[str] = []
    missed_max: list[float] = []
    innocent_max: list[float] = []

    for case in CASES["guilt"]:
        probs, fired = lint.jev_verdict(f"case{case['suffix']}", case["content"])
        ok = bool(fired)
        guilt_hit += ok
        if case["missed_by_grep"]:
            missed_total += 1
            missed_hit += ok
            missed_max.append(max(probs.values()) if probs else 0.0)
        top = max(probs.values()) if probs else 0.0
        rows.append(
            f"  {'HIT ' if ok else 'MISS'} {case['name']:<38} max={top:.2f} {fired}"
        )

    rows.append("")
    for case in CASES["innocence"]:
        probs, fired = lint.jev_verdict(f"case{case['suffix']}", case["content"])
        bad = bool(fired)
        false_alarm += bad
        innocent_max.append(max(probs.values()) if probs else 0.0)
        top = max(probs.values()) if probs else 0.0
        rows.append(
            f"  {'FALSE-ALARM' if bad else 'clear      '} {case['name']:<34} max={top:.2f}"
        )

    print("\n".join(rows))
    n_guilt, n_innocent = len(CASES["guilt"]), len(CASES["innocence"])
    print(f"\nguilt recall          {guilt_hit}/{n_guilt}")
    print(
        f"recall on grep-misses {missed_hit}/{missed_total}   <- the lane's reason to exist"
    )
    print(f"false alarms          {false_alarm}/{n_innocent}")
    print(f"threshold             {lint.FIRE_THRESHOLD}")

    # Threshold sensitivity. Printed rather than acted on: picking the threshold
    # that maximises this table IS tuning on the test set, and the corpus is
    # self-authored. It exists so a later decision has numbers under it.
    print("\nsensitivity (recall on grep-misses / false alarms):")
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        mh = sum(1 for m in missed_max if m >= t)
        fa = sum(1 for m in innocent_max if m >= t)
        print(f"  t={t:.1f}  {mh}/{missed_total}   {fa}/{n_innocent}")
    return 0


if __name__ == "__main__":
    if "--bench" in sys.argv:
        raise SystemExit(_run_bench())
    raise SystemExit(pytest.main([__file__, "-q"]))
