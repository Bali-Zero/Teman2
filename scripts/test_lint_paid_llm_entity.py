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


def test_service_silence_is_not_a_pass(monkeypatch, authorized_vendor):
    """An unreachable service must not clear a file the grep condemns.

    This is the OR rule under its worst condition and the reason `ask()` returns
    None rather than a falsy verdict.

    `authorized_vendor` is load-bearing, and its absence made this the SIXTH
    vacuous test in this lane: without it `available()` is False, `judge_file`
    never calls `ask` at all, and this test passed on the grep alone — proving
    nothing about the None-handling it claims to protect. `asked is True`
    below is what makes that failure mode visible again if the fixture is
    ever dropped.
    """
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(lint, "ask", lambda *a, **k: None)
    case = next(
        c for c in CASES["guilt"] if c["name"].startswith("canonical_constructor")
    )
    result = lint.judge_file("x.py", case["content"])
    assert result["asked"] is True, "the service must actually be reached, not skipped"
    assert result["violation"] is True


def test_model_saying_no_cannot_clear_the_grep(monkeypatch, authorized_vendor):
    """The core anti-AND test.

    Even with every route answered 0.0, a file the grep condemns stays
    condemned. If this test ever fails, the composition has been inverted and a
    model false negative can open the gate.

    `authorized_vendor` is not decoration. Without it the on-disk fence makes
    the client unavailable, the model is never asked, and this test passes on
    the grep alone — proving nothing about the composition it exists to protect.
    The most important test in this file was the fifth vacuous one, and it was
    an external review seat that noticed, after four had already been found.
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


@pytest.fixture
def authorized_vendor(tmp_path, monkeypatch):
    """Authorize the endpoint ON DISK for tests that exercise the model path.

    Added with the #6968 gate's condition-3 fence. Before it, setting the key
    was enough to reach `ask`; now a key is not permission. The tests below
    monkeypatch `ask` to assert what the MODEL contributes, so they have to
    clear the fence honestly rather than route around it — without this
    fixture they would still pass, because a client that never speaks fires no
    route and asserts nothing.

    The entry carries a `paths` list because the successor to PR #6989's
    Gear-3 gate made a bare string entry authorize nothing: `paths` absent is
    the same fail-open the file itself refuses, one level down.
    """
    import typesafe_client

    listing = tmp_path / "authorized_endpoints.json"
    listing.write_text(
        json.dumps(
            {
                "endpoints": [
                    {
                        "endpoint": typesafe_client.ENDPOINT,
                        "ruling": "test fixture",
                        "use": "test",
                        "paths": ["**"],
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(typesafe_client, "AUTHORIZATION", listing)
    return listing


def test_model_alone_can_add_a_violation(monkeypatch, authorized_vendor):
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


def test_probability_below_threshold_does_not_fire(monkeypatch, authorized_vendor):
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(
        lint,
        "ask",
        lambda *a, **k: {"wrapper_library": {"type": "noul", "noul": 0.5}},
    )
    case = next(c for c in CASES["guilt"] if c["name"] == "litellm_wrapper")
    assert lint.judge_file("x.py", case["content"])["violation"] is False


def test_redaction_runs_before_the_payload_leaves(monkeypatch, authorized_vendor):
    """A credential in the source must not be in what we send."""
    seen: dict = {}
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(lint, "ask", lambda state, q: seen.update(state) or None)
    lint.judge_file("x.py", f'k = "{FAKE_KEY}"\nimport anthropic\n')
    assert "abcdefghijklmnop0123" not in json.dumps(seen)


# ─────────────────────────────────────────────────────────────────────── bench


def _run_bench() -> int:
    from typesafe_client import unavailable_reason

    reason = unavailable_reason()
    if reason is not None:
        print(f"the bench needs a live client, and it is silent ({reason}). Nothing run.")
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


# ──────────────────────────────────── regressions from the gear-3 council
# Each of these is a refuter finding that was real. They are appended rather
# than folded into the sections above so the provenance stays legible.


def test_redaction_catches_unquoted_assignment():
    """An unquoted YAML/shell value used to ship verbatim to the endpoint.

    The quoted rule required a closing quote, so `KEY: value` — the ordinary
    YAML and `export` form — matched nothing. A real AWS secret shape was sent
    byte-for-byte in the reviewer's reproduction. This module IS the §4
    boundary, which makes this the worst class of bug it can carry.
    """
    out = redact(
        "env:\n  AWS_SECRET_ACCESS_KEY: wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY"
    )
    assert "wJalrXUtnFEMIK7MDENGbPxRfiCY" not in out
    assert "AWS_SECRET_ACCESS_KEY" in out, "the name is signal and must survive"


def test_redaction_catches_unquoted_shell_export():
    out = redact("export UPSTREAM_TOKEN=abc123def456ghi789")
    assert "abc123def456ghi789" not in out


def test_ask_returns_none_on_a_non_utf8_body(monkeypatch, authorized_vendor):
    """ask() promises it never raises. A narrow except tuple could not keep it.

    UnicodeDecodeError is a ValueError, so it matched none of the original
    clauses and would have escaped into a CI step whose entire contract is that
    it always exits 0.

    The `authorized_vendor` fixture is load-bearing and was added late: once the
    on-disk fence existed, this test passed because `ask` returned None at the
    fence and never reached the body it claims to be about. It asserted nothing
    for exactly as long as nobody checked. Found by a refuting seat.
    """
    import typesafe_client

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"\xff\xfe not utf-8"

    class _Opener:
        def open(self, *a, **k):
            return _Resp()

    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    # `ask()` no longer opens the request through `urllib.request.urlopen`
    # directly — the successor to PR #6989's Gear-3 gate replaced it with a
    # module-local opener that refuses redirects, so the seam to patch moved
    # with it.
    monkeypatch.setattr(typesafe_client, "_OPENER", _Opener())
    assert typesafe_client.ask({"x": 1}, {}, timeout=1) is None


def test_in_scope_does_not_exclude_more_than_the_incumbent():
    """catE scans `*_test.py`; excluding it here was under-match drift."""
    assert lint.in_scope("packages/cell-core/cell_core/admission_test.py") is True
    assert lint.in_scope("apps/backend-rag/scripts/smoke_test.py") is True
    assert lint.in_scope("apps/x/tests/test_thing.py") is False


def test_redaction_catches_a_bare_sensitive_name():
    """`TOKEN = "..."` — the name IS the sensitive word, with no prefix.

    Every rule required at least one character before KEY/TOKEN/SECRET, so a
    variable called exactly TOKEN was not redacted at all.
    """
    assert "opaque-secret-val" not in redact('TOKEN = "opaque-secret-val"')
    assert "abc12345xyz" not in redact("SECRET: abc12345xyz")


def test_redaction_catches_a_quoted_json_key():
    """A quote sits between the name and the colon, so both rules missed it."""
    assert "opaque-value-123" not in redact('{"api_key": "opaque-value-123"}')


def test_redaction_catches_an_aws_access_key_id():
    assert "AKIAIOSFODNN7EXAMPLE" not in redact("id = AKIAIOSFODNN7EXAMPLE")


def test_scope_matches_cate_per_predicate_not_in_aggregate():
    """catE excludes vendor/ and examples/ from ONE of its two predicates.

    Collapsing both exclusion lists into one dropped files the constructor grep
    does scan — making the composed verdict weaker than the regex alone, the
    one outcome Rule 3 forbids.
    """
    assert lint.in_scope("vendor/runtime.py") is True
    assert lint.in_scope("examples/demo.py") is True
    assert lint.in_scope("apps/x/.venv/lib/thing.py") is False


def test_singular_test_dir_is_not_excluded():
    assert lint.in_scope("test/smoke.py") is True
    assert lint.in_scope("apps/x/tests/t.py") is False


def test_prefilter_sees_indirect_http_clients():
    for snippet in (
        "s = requests.Session()\ns.post(URL, headers=H)",
        'requests.request("POST", url, headers=h)',
        'import axios from "axios"',
        "import aiohttp",
        "import http.client",
    ):
        assert lint.worth_asking(snippet) is True, snippet


def test_json_mode_emits_only_json(monkeypatch, capsys):
    """A diagnostic line before the object makes json.loads() raise."""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    rc = lint.main(["--json"])
    parsed = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert parsed == {"results": []}
