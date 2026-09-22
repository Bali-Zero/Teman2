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
import subprocess
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


@pytest.fixture(autouse=True)
def _no_ambient_base_ref(monkeypatch):
    """Every test controls its own view of the pardon growth check
    explicitly. Without this, a stray BASE_SHA in the calling shell — the
    exact shape the CI step sets in the real workflow — would make every
    unrelated test in this file exercise the anti-bypass path by accident."""
    monkeypatch.delenv("BASE_SHA", raising=False)


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


def test_a_violation_exits_one_unless_advisory(monkeypatch, tmp_path, capsys):
    """The arming line. RULED 2026-09-21-ter dropped --advisory from catE step
    #40c, and until this test nothing in the suite reached main()'s exit path
    with a violation present — the flag's effect was proven only by hand.
    GUILT and INNOCENCE on the same stubbed verdict: exit 1 armed, exit 0
    advisory. `in_scope` is stubbed because pytest's tmp_path carries the
    test's own name, which the `test_` exclusion would otherwise filter out
    before main() ever judged the file."""
    target = tmp_path / "changed.py"
    target.write_text("x = 1\n")
    verdict = {
        "violation": True,
        "grep": True,
        "fired_routes": [],
        "pardoned_routes": [],
        "probabilities": {},
        "asked": False,
    }
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    monkeypatch.setattr(
        lint, "judge_file", lambda path, text, pardons=None: {"path": path, **verdict}
    )

    assert lint.main([str(target)]) == 1
    assert lint.main(["--advisory", str(target)]) == 0
    assert "1 violation(s)" in capsys.readouterr().out


@pytest.mark.parametrize(
    "bad",
    [True, False, 1.5, -0.1, float("inf"), float("nan"), "0.9", None, [0.9], {"p": 0.9}],
    ids=["true", "false", "above-one", "below-zero", "inf", "nan", "string", "none", "list", "dict"],
)
def test_a_malformed_noul_value_is_no_opinion(bad):
    """GUILT for 'malformed = no opinion' (codex council finding on the arming
    PR): `noul()` returned float(value) for any int or float, and bool is an
    int — a vendor answer of `{"noul": true}` became probability 1.0 and, once
    the step was armed, a red build. A bool, a number outside [0, 1], inf,
    nan or a non-number must never become a probability."""
    assert lint.noul({"route": {"noul": bad}}, "route") is None


@pytest.mark.parametrize("good", [0, 1, 0.83], ids=["zero", "one", "fraction"])
def test_a_well_formed_noul_value_is_its_probability(good):
    """INNOCENCE. Without this the guard above could be `return None`."""
    assert lint.noul({"route": {"noul": good}}, "route") == float(good)


# ───────────────────────────────────────────────────────────────── pardon
#
# The pardon narrows ONLY the model's contribution: violation = by_grep or
# bool(live), where live = fired - pardoned. A grep hit is never pardoned.


def _write_pardons(tmp_path, entries):
    p = tmp_path / "pardoned.json"
    p.write_text(json.dumps({"_doc": "test fixture", "entries": entries}))
    return p


def test_pardon_clears_a_fired_listed_route(monkeypatch, tmp_path, authorized_vendor):
    """INNOCENCE. A pardoned path with a pardoned, fired route is no longer a
    violation — but the model's opinion is still reported in fired_routes."""
    monkeypatch.setattr(
        lint,
        "PARDON",
        _write_pardons(
            tmp_path,
            [
                {
                    "path": "x.py",
                    "routes": ["wrapper_library"],
                    "reason": "a doc comment describing the ban, not using it",
                    "pr": 7200,
                    "date": "2026-09-21",
                }
            ],
        ),
    )
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(
        lint,
        "ask",
        lambda *a, **k: {"wrapper_library": {"type": "noul", "noul": 0.95}},
    )
    case = next(c for c in CASES["guilt"] if c["name"] == "litellm_wrapper")
    result = lint.judge_file("x.py", case["content"])
    assert result["violation"] is False
    assert result["pardoned_routes"] == ["wrapper_library"]
    assert "wrapper_library" in result["fired_routes"], (
        "the model's opinion is reported unchanged, pardoned or not"
    )


def test_pardon_never_clears_a_grep_hit(monkeypatch, tmp_path):
    """GUILT. Mutant: let a pardon entry for the path also clear `by_grep` →
    this must go RED. A grep hit is never pardoned, by any entry, for any
    reason."""
    monkeypatch.setattr(
        lint,
        "PARDON",
        _write_pardons(
            tmp_path,
            [
                {
                    "path": "x.py",
                    "routes": ["wrapper_library"],
                    "reason": "unrelated pardon on the same file",
                    "pr": 1,
                    "date": "2026-09-21",
                }
            ],
        ),
    )
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    case = next(
        c for c in CASES["guilt"] if c["name"].startswith("canonical_constructor")
    )
    result = lint.judge_file("x.py", case["content"])
    assert result["violation"] is True, "a grep hit is never pardoned"


def test_pardon_never_clears_a_grep_hit_even_when_its_own_route_fired(
    monkeypatch, tmp_path
):
    """GUILT, the half the test above cannot see. There the service is silent,
    so `pardoned_routes` is empty and a mutant that clears `by_grep` ONLY when a
    pardoned route also fired — `(by_grep and not pardoned_routes) or live` —
    stays green. Here the pardoned route DOES fire on a grep-guilty file: the
    route is pardoned, the grep hit is not, and the verdict stays a violation.
    Caught by the grader's own mutant on 2026-09-22, not by the builder's."""
    monkeypatch.setattr(
        lint,
        "PARDON",
        _write_pardons(
            tmp_path,
            [
                {
                    "path": "x.py",
                    "routes": ["wrapper_library"],
                    "reason": "the model misreads this file's wrapper",
                    "pr": 1,
                    "date": "2026-09-21",
                }
            ],
        ),
    )
    monkeypatch.setattr(lint, "available", lambda: True)
    monkeypatch.setattr(
        lint,
        "jev_verdict",
        lambda path, text: ({"wrapper_library": 0.97}, ["wrapper_library"]),
    )
    case = next(
        c for c in CASES["guilt"] if c["name"].startswith("canonical_constructor")
    )
    result = lint.judge_file("x.py", case["content"])
    assert result["pardoned_routes"] == ["wrapper_library"]
    assert result["grep"] is True
    assert result["violation"] is True, "the pardon narrowed the model, never the grep"


def test_pardon_does_not_cover_an_unlisted_route(
    monkeypatch, tmp_path, authorized_vendor
):
    """GUILT. The entry pardons a different route than the one that fired."""
    monkeypatch.setattr(
        lint,
        "PARDON",
        _write_pardons(
            tmp_path,
            [
                {
                    "path": "x.py",
                    "routes": ["cloud_reseller_route"],
                    "reason": "wrong route pardoned on purpose for this test",
                    "pr": 1,
                    "date": "2026-09-21",
                }
            ],
        ),
    )
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(
        lint,
        "ask",
        lambda *a, **k: {"wrapper_library": {"type": "noul", "noul": 0.95}},
    )
    case = next(c for c in CASES["guilt"] if c["name"] == "litellm_wrapper")
    result = lint.judge_file("x.py", case["content"])
    assert result["violation"] is True
    assert result["pardoned_routes"] == []
    assert result["fired_routes"] == ["wrapper_library"]


def test_pardons_absent_file_pardons_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(lint, "PARDON", tmp_path / "does-not-exist.json")
    assert lint.load_pardons() == {}


def test_pardons_malformed_json_pardons_nothing(monkeypatch, tmp_path):
    p = tmp_path / "pardoned.json"
    p.write_text("{this is not json")
    monkeypatch.setattr(lint, "PARDON", p)
    assert lint.load_pardons() == {}


def test_pardons_deeply_nested_json_pardons_nothing_no_exception():
    raw = "[" * 60000 + "]" * 60000
    assert lint._parse_pardons(raw) == {}


def test_pardons_top_level_list_pardons_nothing():
    raw = json.dumps(
        [{"path": "x.py", "routes": ["wrapper_library"], "reason": "t", "pr": 1, "date": "2026-09-21"}]
    )
    assert lint._parse_pardons(raw) == {}


def test_pardons_entries_non_list_pardons_nothing():
    assert lint._parse_pardons(json.dumps({"entries": "nope"})) == {}


@pytest.mark.parametrize(
    "entry",
    [
        {"routes": ["wrapper_library"], "reason": "t", "pr": 1, "date": "2026-09-21"},
        {"path": "x.py", "reason": "t", "pr": 1, "date": "2026-09-21"},
        {"path": "x.py", "routes": [], "reason": "t", "pr": 1, "date": "2026-09-21"},
        {"path": "x.py", "routes": ["not_a_real_route"], "reason": "t", "pr": 1, "date": "2026-09-21"},
        {"path": "x.py", "routes": [1], "reason": "t", "pr": 1, "date": "2026-09-21"},
        {"path": "x.py", "routes": ["wrapper_library"], "pr": 1, "date": "2026-09-21"},
        {"path": "x.py", "routes": ["wrapper_library"], "reason": "", "pr": 1, "date": "2026-09-21"},
        {"path": "x.py", "routes": ["wrapper_library"], "reason": "t", "date": "2026-09-21"},
        {"path": "x.py", "routes": ["wrapper_library"], "reason": "t", "pr": True, "date": "2026-09-21"},
        {"path": "x.py", "routes": ["wrapper_library"], "reason": "t", "pr": "12", "date": "2026-09-21"},
        {"path": "x.py", "routes": ["wrapper_library"], "reason": "t", "pr": 0, "date": "2026-09-21"},
        {"path": "x.py", "routes": ["wrapper_library"], "reason": "t", "pr": 1},
        {"path": "x.py", "routes": ["wrapper_library"], "reason": "t", "pr": 1, "date": "2026/09/21"},
        {"path": "x.py", "routes": ["wrapper_library"], "reason": "t", "pr": 1, "date": "21-09-2026"},
        "not-a-dict",
    ],
    ids=[
        "missing-path",
        "missing-routes",
        "empty-routes",
        "unknown-route",
        "route-not-string",
        "missing-reason",
        "empty-reason",
        "missing-pr",
        "pr-is-bool",
        "pr-is-string",
        "pr-not-positive",
        "missing-date",
        "bad-date-slashes",
        "bad-date-order",
        "entry-not-a-dict",
    ],
)
def test_a_malformed_entry_pardons_nothing(entry):
    assert lint._parse_pardons(json.dumps({"entries": [entry]})) == {}
    assert lint._valid_entry(entry) is False


@pytest.mark.parametrize("field", ["path", "routes", "reason", "pr", "date"])
def test_the_validator_refuses_an_entry_missing_each_field(field):
    """Not an empty-list tripwire (spent) — proof the check bites, one field
    at a time."""
    entry = {
        "path": "x.py",
        "routes": ["wrapper_library"],
        "reason": "t",
        "pr": 1,
        "date": "2026-09-21",
    }
    del entry[field]
    assert lint._valid_entry(entry) is False


def test_pardon_is_exact_path_not_prefix_suffix_or_superstring(
    monkeypatch, tmp_path, authorized_vendor
):
    """GUILT. Mutant: `==` becomes `in`/`endswith`/`startswith` → RED."""
    monkeypatch.setattr(
        lint,
        "PARDON",
        _write_pardons(
            tmp_path,
            [
                {
                    "path": "x.py",
                    "routes": ["wrapper_library"],
                    "reason": "t",
                    "pr": 1,
                    "date": "2026-09-21",
                }
            ],
        ),
    )
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(
        lint,
        "ask",
        lambda *a, **k: {"wrapper_library": {"type": "noul", "noul": 0.95}},
    )
    case = next(c for c in CASES["guilt"] if c["name"] == "litellm_wrapper")
    for other_path in ("dir/x.py", "x.py.bak", "xx.py", "x.pyc", "a/x.py"):
        result = lint.judge_file(other_path, case["content"])
        assert result["violation"] is True, other_path
        assert result["pardoned_routes"] == [], other_path


def test_pardon_normalizes_a_leading_dot_slash(monkeypatch, tmp_path, authorized_vendor):
    """The entry's path and the judged path can each carry a leading `./`
    and still match — normalisation, not laxer matching."""
    monkeypatch.setattr(
        lint,
        "PARDON",
        _write_pardons(
            tmp_path,
            [
                {
                    "path": "./x.py",
                    "routes": ["wrapper_library"],
                    "reason": "t",
                    "pr": 1,
                    "date": "2026-09-21",
                }
            ],
        ),
    )
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(
        lint,
        "ask",
        lambda *a, **k: {"wrapper_library": {"type": "noul", "noul": 0.95}},
    )
    case = next(c for c in CASES["guilt"] if c["name"] == "litellm_wrapper")
    result = lint.judge_file("./x.py", case["content"])
    assert result["violation"] is False
    assert result["pardoned_routes"] == ["wrapper_library"]


def test_shipped_pardon_registry_validates():
    """The registry actually on disk: parses, every entry has the full
    shape, every path it names still exists (a stale pardon must be
    deleted), and every route is one this lint actually asks about. Not an
    empty-list assertion — see test_the_validator_refuses_an_entry_missing_
    each_field above for the tripwire that proves the check bites."""
    data = json.loads(lint.PARDON.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    entries = data["entries"]
    assert isinstance(entries, list)
    for entry in entries:
        assert lint._valid_entry(entry), entry
        assert set(entry["routes"]) <= set(lint.ROUTE_QUESTIONS), entry
        target = lint.REPO_ROOT / entry["path"]
        assert target.is_file(), f"stale pardon: {entry['path']} does not exist on disk"


# ─────────────────────────────────────────────────────────────── pardon growth


def test_growth_blocks_before_any_model_call(monkeypatch, tmp_path, authorized_vendor):
    """The gate-7143 notice: the old corpus (`"x = 1\\n"`) made this assertion
    vacuous. `worth_asking` was False for that text, so `ask` was already
    unreachable regardless of where the growth block sits in `main` — moving
    it AFTER the model call, a real regression of the safety ordering, still
    left this test green. The corpus here is a `missed_by_grep` guilt case, so
    `worth_asking` is True and the model path is genuinely reachable (the key
    is set and the endpoint is authorized via `authorized_vendor`); only the
    growth block standing above the call keeps `ask` unfired."""
    case = next(c for c in CASES["guilt"] if c["name"] == "raw_http_post")
    text = case["content"]
    assert lint.worth_asking(text), "the probe must be able to reach ask()"
    target = tmp_path / "changed.py"
    target.write_text(text)
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    monkeypatch.setattr(lint, "pardon_grew", lambda ref: ["new/path.py"])
    called: list[int] = []
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(lint, "ask", lambda *a, **k: called.append(1) or None)
    rc = lint.main(["--base-ref", "deadbeef", str(target)])
    assert rc == 3
    assert called == [], "the stubbed ask must never be reached once growth trips"


def test_no_growth_continues_to_judge(monkeypatch, tmp_path):
    target = tmp_path / "changed.py"
    target.write_text("x = 1\n")
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    monkeypatch.setattr(lint, "pardon_grew", lambda ref: [])
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    rc = lint.main(["--base-ref", "deadbeef", str(target)])
    assert rc == 0


def test_no_in_scope_target_skips_growth_entirely(monkeypatch, tmp_path):
    """A diff with NO in-scope files returns 0 BEFORE the growth check —
    that is how a pardon lands: in its own PR, touching only the registry,
    which is not itself a SOURCE_SUFFIXES member."""
    target = tmp_path / "notes.md"
    target.write_text("hello\n")
    calls: list[str] = []
    monkeypatch.setattr(lint, "pardon_grew", lambda ref: calls.append(ref) or [])
    rc = lint.main(["--base-ref", "deadbeef", str(target)])
    assert rc == 0
    assert calls == []


def test_unreadable_base_ref_fails_closed(monkeypatch, tmp_path):
    target = tmp_path / "changed.py"
    target.write_text("x = 1\n")
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    monkeypatch.setattr(lint, "pardon_grew", lambda ref: None)
    called: list[int] = []
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    monkeypatch.setattr(lint, "ask", lambda *a, **k: called.append(1) or None)
    rc = lint.main(["--base-ref", "not-a-real-ref", str(target)])
    assert rc == 3
    assert called == []


def test_no_base_ref_skips_the_check(monkeypatch, tmp_path):
    target = tmp_path / "changed.py"
    target.write_text("x = 1\n")
    monkeypatch.setattr(lint, "in_scope", lambda path: True)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    called: list[str] = []
    monkeypatch.setattr(lint, "pardon_grew", lambda ref: called.append(ref) or [])
    rc = lint.main([str(target)])
    assert rc == 0
    assert called == []


def test_pardon_growth_is_exercised_for_real(tmp_path, monkeypatch):
    """Every other growth test stubs `pardon_grew` out. This one builds real
    git commits so a length-preserving path swap and a genuine shrink are
    asserted on real diffing, not on a length comparison — mirrors
    lint_ban_prose's `test_round2_7_the_growth_check_is_exercised_for_REAL`."""
    repo = tmp_path / "repo"
    (repo / "infra" / "paid-llm-entity").mkdir(parents=True)
    registry = repo / "infra" / "paid-llm-entity" / "pardoned.json"

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")

    def entry(path):
        return {
            "path": path,
            "routes": ["wrapper_library"],
            "reason": "t",
            "pr": 1,
            "date": "2026-09-21",
        }

    registry.write_text(json.dumps({"entries": [entry("a.py"), entry("b.py")]}))
    git("add", "-A")
    git("commit", "-qm", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    monkeypatch.setattr(lint, "REPO_ROOT", repo)
    monkeypatch.setattr(lint, "PARDON", registry)

    # Same count, one path swapped — a length comparison would call this clean.
    registry.write_text(json.dumps({"entries": [entry("a.py"), entry("c.py")]}))
    assert lint.pardon_grew(base) == ["c.py:wrapper_library"], "a swapped path must read as growth"

    # Shrinking is always allowed: remediation must never be punished.
    registry.write_text(json.dumps({"entries": [entry("a.py")]}))
    assert lint.pardon_grew(base) == []
    # The unit is (path, route): a route ADDED to an entry the base already
    # carried is growth, even though the set of pardoned paths is unchanged.
    widened = entry("a.py")
    widened["routes"] = ["wrapper_library", "direct_paid_sdk"]
    registry.write_text(json.dumps({"entries": [widened, entry("b.py")]}))
    assert lint.pardon_grew(base) == ["a.py:direct_paid_sdk"], (
        "a new route on an existing path must read as growth"
    )

    # Base ref that does not resolve here at all: fail-closed sentinel.
    assert lint.pardon_grew("not-a-real-ref-anywhere") is None


def test_pardon_growth_file_absent_at_base_means_everything_is_growth(tmp_path, monkeypatch):
    repo = tmp_path / "repo2"
    (repo / "infra" / "paid-llm-entity").mkdir(parents=True)
    registry = repo / "infra" / "paid-llm-entity" / "pardoned.json"

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "t")
    (repo / "README.md").write_text("x\n")
    git("add", "-A")
    git("commit", "-qm", "base without a pardon file")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()

    monkeypatch.setattr(lint, "REPO_ROOT", repo)
    monkeypatch.setattr(lint, "PARDON", registry)
    registry.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "path": "a.py",
                        "routes": ["wrapper_library"],
                        "reason": "t",
                        "pr": 1,
                        "date": "2026-09-21",
                    }
                ]
            }
        )
    )
    assert lint.pardon_grew(base) == ["a.py:wrapper_library"], (
        "the registry absent at a resolvable base ref means the base line was "
        "empty, so every currently-pardoned path is growth"
    )
