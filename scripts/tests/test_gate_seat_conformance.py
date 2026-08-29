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
    claim = re.compile(
        rf"invokes\s+{re.escape(short)}\s+as\s+the\s+only\s+sequential\s+final\s+gate",
        re.IGNORECASE,
    )
    assert not claim.search(doc), (
        f"{LAUNCHER.name}'s docstring claims {short} is the sequential final "
        f"gate, but CLAUDE.md retired `{model}` from every automated route "
        "(ruling 2026-08-20). The gate seat is Opus 5."
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
    flag_on = bool(re.search(r"^V3_FINAL_GATE_READY\s*=\s*True\b", validator_src, re.MULTILINE))

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
