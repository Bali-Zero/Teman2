"""The final gate's seat may not drift from the ruling that names it.

WHY. On 2026-08-20 Zero ruled Fable 5 out of the workflow: "no doctrine,
skill, cron, or script may auto-route to it", and the final on-disk gate
became Opus 5. Eight days later `launch_worker_plane_review_panel.py` still
opened by saying it "invokes Fable 5 as the only sequential final gate" — a
docstring describing a world the ruling had ended. Nothing was watching, so
nothing said anything.

WHAT THIS PINS, and what it deliberately does not.

The launcher's Fable machinery is DORMANT: `launch_final_gate()` raises
unconditionally and nothing calls it, and `V3_FINAL_GATE_READY` is False, so
the parity tripwire in `test_v3_final_gate_parity.py` reads
`not V3_FINAL_GATE_READY or <parity>` and passes vacuously. That is sound
engineering — but it means the dormant design would come alive routing to a
RETIRED model the moment someone flips one boolean, and the tripwire guarding
that flip currently demands parity with exactly that retired seat.

So this file asserts two different things:

  1. the docstring must not NAME a doctrine-retired model as the gate — the
     drift that actually happened, caught by reading the prose; and
  2. the arming flag must not be True while the gate seat is still the
     retired model — the drift that has not happened yet, and the one that
     would matter.

It does NOT re-point `FABLE_GATE`. Changing which model the v3 protocol would
invoke is a design decision, not a docstring correction, and folding it into
this change would be exactly the "fix of a fix" depth the lane forbids.

The retired seat is not hardcoded here: it is read from CLAUDE.md, so a future
ruling that retires a different model updates this test by updating doctrine.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "scripts" / "launch_worker_plane_review_panel.py"
VALIDATOR = REPO_ROOT / "scripts" / "check_worker_plane_review.py"
DOCTRINE = REPO_ROOT / "CLAUDE.md"

# The sentence in CLAUDE.md §5 that retires a model from every automated route.
# Anchored on the ruling's own words, not on a model name, so the name comes
# from doctrine rather than from this file.
RETIREMENT_RE = re.compile(
    r"`(?P<model>claude-[a-z0-9.-]+)`[^.\n]*?is simply not routed to by any doctrine",
)


def _doctrine_text() -> str:
    assert DOCTRINE.is_file(), f"doctrine source missing: {DOCTRINE}"
    return DOCTRINE.read_text(encoding="utf-8", errors="replace")


def retired_model() -> str:
    """The model CLAUDE.md says no automated route may reach."""
    m = RETIREMENT_RE.search(_doctrine_text())
    if not m:
        pytest.fail(
            "CLAUDE.md no longer carries the retirement sentence this test reads "
            "('… is simply not routed to by any doctrine …'). Either the ruling "
            "changed — in which case update this anchor deliberately — or the "
            "sentence was reworded and this guard has silently stopped guarding."
        )
    return m.group("model")


def _module_docstring(path: pathlib.Path) -> str:
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    assert doc, f"{path} has no module docstring to check"
    return doc


def test_doctrine_actually_names_a_retired_model() -> None:
    """Premise check: without this, both tests below pass vacuously."""
    assert retired_model() == "claude-fable-5", (
        "the retirement sentence resolved to an unexpected model — read it "
        "before trusting either assertion below"
    )


def test_launcher_docstring_does_not_name_the_retired_model_as_the_gate() -> None:
    doc = _module_docstring(LAUNCHER)
    model = retired_model()
    short = model.removeprefix("claude-").replace("-", " ")  # 'fable 5'

    # The docstring is allowed to MENTION the retired model — this file's own
    # correction explains why it used to be named, and a guard that forbids the
    # word would forbid its own explanation (W112). What it may not do is
    # assert that the model IS the gate.
    #
    # The first version of this guard matched ONE literal phrasing,
    # "invokes fable 5 as the only sequential final gate". A cross-family
    # refuter reproduced four evasions of it, each pasted into the docstring
    # and each leaving the suite green:
    #   - "invokes claude-fable-5 as the only sequential final gate"
    #     (the MODEL ID rather than the prose name — and the natural one, since
    #     FABLE_GATE_ARGV_SUFFIX in the launcher literally contains that string)
    #   - "the only sequential final gate is Fable 5."
    #   - "phase two invokes Fable 5, the only sequential final gate."
    #   - "phase two invokes Fable 5 as the sequential final gate."  (drops "only")
    # A guard that forbids one wording of a claim does not forbid the claim.
    #
    # So this is negative-gated on INTENT instead of positive-matched on a
    # phrase (the W115 shape): a sentence that mentions the retired model —
    # by prose name OR model ID — anywhere near "final gate" asserts the claim,
    # UNLESS it also carries a retirement marker, which is what every honest
    # sentence about the correction carries.
    tokens = "|".join(re.escape(x) for x in (short, model, model.removeprefix("claude-")))
    model_re = re.compile(rf"\b(?:{tokens})\b", re.IGNORECASE)
    retirement_re = re.compile(
        r"\b(?:retired|no longer|superseded|used to|taken out|was false|not the gate|"
        r"instead of|ruled out|removed)\b",
        re.IGNORECASE,
    )
    offenders = [
        s.strip()
        for s in re.split(r"(?<=[.;])\s+", doc)
        if "final gate" in s.lower() and model_re.search(s) and not retirement_re.search(s)
    ]
    assert not offenders, (
        f"{LAUNCHER.name}'s docstring asserts {short} is the sequential final "
        f"gate, but CLAUDE.md retired `{model}` from every automated route "
        f"(ruling 2026-08-20). The gate seat is Opus 5. Offending sentence(s): "
        f"{offenders}"
    )


def test_arming_flag_is_false_while_the_gate_seat_is_the_retired_model() -> None:
    """The flip that has not happened yet, and the one that would matter.

    `test_v3_final_gate_parity.py` guards the flag against a STALE validator.
    Nothing guarded it against a RETIRED seat: flipping the boolean would arm
    a protocol whose final gate routes to a model doctrine forbids.
    """
    launcher_src = LAUNCHER.read_text(encoding="utf-8")
    validator_src = VALIDATOR.read_text(encoding="utf-8")
    model = retired_model()

    gate_seat_is_retired = bool(
        re.search(
            rf'FABLE_GATE\s*=\s*Seat\((?:[^)]*?)requested_route\s*=\s*"{re.escape(model)}"',
            launcher_src,
            re.DOTALL,
        )
    )
    # The first version required a bare `= True`. A refuter reproduced two
    # evasions that are completely ordinary edits, each leaving the suite
    # green while the flag was actually on:
    #     V3_FINAL_GATE_READY: bool = True      (adding a type annotation)
    #     V3_FINAL_GATE_READY = bool(True)
    # An arming flag read by a pattern that a natural edit slips past is not a
    # guard on the flag, it is a guard on one way of writing it.
    flag_on = bool(
        re.search(
            r"^V3_FINAL_GATE_READY\s*(?::[^=\n]+)?=\s*(?:True\b|bool\(\s*True\s*\))",
            validator_src,
            re.MULTILINE,
        )
    )

    assert not (gate_seat_is_retired and flag_on), (
        f"V3_FINAL_GATE_READY is True while the sequential gate seat still "
        f"requests `{model}`, which CLAUDE.md retired from every automated "
        "route. Re-point the gate seat to the ruled model BEFORE arming the "
        "protocol — arming it as-is would auto-route to a retired seat."
    )
    # Premise check, so the assertion above cannot pass because the pattern
    # simply stopped matching anything.
    assert gate_seat_is_retired or not flag_on, "unreachable"
    assert gate_seat_is_retired, (
        "the FABLE_GATE seat no longer requests the retired model — if the "
        "seat was re-pointed, delete this test; if the pattern merely stopped "
        "matching, it has silently stopped guarding."
    )


def test_this_guard_is_actually_executed_by_its_workflow() -> None:
    """The guard that guards THIS guard's arming.

    A cross-family refuter's BLOCKER on this PR was not that the test was
    wrong — it was that `.github/workflows/worker-plane-review-tests.yml`
    named it nowhere, so it ran in no CI job at all while the launcher's
    docstring claimed it made a retired-seat flip "impossible". That workflow's
    OWN header exists because "NO CI job anywhere referenced any of these files
    by name"; this file had quietly joined that set.

    Three places must name it, and all three matter independently: `push.paths`
    (a direct push to main), the pull_request sentinel regex (whether the work
    steps run at all on a PR), and the pytest invocation (whether this file is
    collected once they do). Naming it in two of the three is a guard that runs
    on some events and not others — which is worse than not running, because
    the green looks the same.
    """
    wf = REPO_ROOT / ".github" / "workflows" / "worker-plane-review-tests.yml"
    assert wf.is_file(), f"{wf} is missing — this pin cannot verify anything"
    src = wf.read_text(encoding="utf-8")
    me = "test_gate_seat_conformance"

    # Premise check first: if the workflow stops naming the files it has always
    # named, this pin's shape has changed and its silence would mean nothing.
    assert "test_v3_final_gate_parity" in src, (
        "worker-plane-review-tests.yml no longer names test_v3_final_gate_parity — "
        "this pin's premise is gone, so it has stopped guarding rather than passed"
    )

    in_paths = f'"scripts/tests/{me}.py"' in src
    in_sentinel = f"scripts/tests/{me}\\.py" in src
    in_pytest = f"scripts/tests/{me}.py \\" in src or f"scripts/tests/{me}.py\n" in src

    missing = [
        name
        for name, present in (
            ("push.paths", in_paths),
            ("pull_request sentinel regex", in_sentinel),
            ("pytest invocation", in_pytest),
        )
        if not present
    ]
    assert not missing, (
        f"{me}.py is not named in: {missing}. A guard its workflow does not "
        "execute is decorative — it reports nothing, forbids nothing, and its "
        "green is indistinguishable from a real one (superscar #2)."
    )
