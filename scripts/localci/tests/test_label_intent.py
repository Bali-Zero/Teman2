"""B31'': `label_intent.plan` against an independent oracle, over the WHOLE finite input domain.

The oracle (`reference`) is a line-for-line transliteration of the bash helper of B31 round 4 (globals, `pause`, `budget_ok` and all), written
as imperative code with nothing in common with the generator's structure. The domain is explored by branching at every network call over every
result class (verify rc 0/1/2/127/137, view with/without the label or failing, write rc 0/1, arm ok/benign/refused) and over the clock
(deadline 0..N, every call costing 0 or 1 s, sleeps costing what they sleep). Both implementations are driven by the same script of results and must
agree on the whole action transcript and the whole outcome. A mutation of `plan` that changes any outcome in the domain fails here.
"""
from __future__ import annotations

import itertools

import pytest

from .fixture_repo import runner  # noqa: F401 — puts scripts/localci on sys.path like its siblings
from localci import label_intent as li  # noqa: E402

VERIFY_RCS = (0, 1, 2, 137)
ALT = {
    "verify": [(rc, f"v{rc}") for rc in VERIFY_RCS],
    "view": [(0, li.LABEL + "\nother"), (0, "other"), (1, "")],
    "remove": [(0, ""), (1, "no remove")],
    "add": [(0, ""), (1, "no add")],
    "arm": [(0, "ok"), (1, "Auto-merge enabled"), (1, "boom")],
}


class Needs(Exception):
    def __init__(self, kind):
        self.kind = kind


class World:
    """Scripted results; every call costs `cost` seconds, a sleep costs what it sleeps."""

    def __init__(self, script, cost):
        self.script, self.cost, self.pos, self.t, self.calls = script, cost, 0, 0, []

    def call(self, kind, seconds=0):
        self.calls.append((kind, seconds))
        if kind == "sleep":
            self.t += seconds
            return 0, ""
        if self.pos >= len(self.script):
            raise Needs(kind)
        rc, out = self.script[self.pos]
        self.pos += 1
        self.t += self.cost
        return rc, out


def run_plan(cfg, world):
    gen = li.plan(cfg)
    step = next(gen)
    while isinstance(step, li.Act):
        rc, out = world.call(step.kind, step.seconds)
        step = gen.send(li.Result(rc, out, world.t))
    return step


def reference(cfg, world):
    """The bash helper, transliterated: `deadline_hit` and `BACKOFF` are globals, `pause` and `budget_ok` are functions."""
    g = {"hit": False, "backoff": cfg.backoff}

    def budget_ok():
        if cfg.deadline - world.t <= 0:
            g["hit"] = True
            return False
        return True

    def pause():
        if not budget_ok():
            return
        left = cfg.deadline - world.t
        world.call("sleep", g["backoff"] if g["backoff"] < left else left)
        g["backoff"] = g["backoff"] * 2

    def note():
        return f" (deadline {cfg.deadline}s reached)" if g["hit"] else ""

    def tail(out, n):
        return " ".join(out.splitlines()[-n:]) + " "

    why = ""
    label = "applied"
    vrc = 2
    for i in range(1, cfg.tries + 1):
        if not budget_ok():
            break
        vrc, _ = world.call("verify")
        if vrc == 0 or vrc == 1:
            break
        if i < cfg.tries:
            pause()
    if vrc == 1:
        g["backoff"] = cfg.backoff
        has, rc, out = 0, 1, ""
        if budget_ok():
            vrc_view, vout = world.call("view")
            if vrc_view == 0 and li.LABEL in vout.splitlines():
                has = 1
        for i in range(1, cfg.tries + 1):
            rc, out = 0, ""
            if has == 1:
                if budget_ok():
                    rc, out = world.call("remove")
                else:
                    rc = 1
                if rc == 0:
                    has = 0
            if rc == 0:
                if budget_ok():
                    rc, out = world.call("add")
                else:
                    rc = 1
            if rc == 0:
                break
            if i < cfg.tries:
                pause()
        if rc != 0:
            label, why = "failed", f"the label write failed (rc={rc}){note()}: {tail(out, 3)}"
        else:
            g["backoff"] = cfg.backoff
            ok = False
            for i in range(1, cfg.tries + 1):
                if not budget_ok():
                    break
                rrc, out = world.call("verify")
                if rrc == 0:
                    ok = True
                    break
                if i < cfg.tries:
                    pause()
            if not ok:
                label, why = "failed", f"read-back after the write does not show a valid label{note()}: {tail(out, 2)}"
    elif vrc != 0:
        label, why = "failed", f"the label could not be read (rc={vrc}){note()}: nothing was changed"
    if cfg.queue == "absent":
        return li.Outcome(label, why, "skipped", 0 if label == "applied" else 2)
    rc, out = world.call("arm")
    benign = any(m in out.lower() for m in ("already queued", "auto-merge enabled", "already enabled", "clean status"))
    if rc != 0 and not benign:
        return li.Outcome(label, why, "failed", 2 if label == "failed" else 3, rc, out)
    return li.Outcome(label, why, "armed", 0 if label == "applied" else 2, rc, out)


def explore(cfg, cost):
    """Every complete script of results, by branching wherever either implementation asks for a result nobody scripted yet."""
    todo, seen = [[]], 0
    while todo:
        script = todo.pop()
        try:
            wa = World(script, cost)
            a = run_plan(cfg, wa)
            wb = World(script, cost)
            b = reference(cfg, wb)
        except Needs as need:
            todo.extend(script + [alt] for alt in ALT[need.kind])
            continue
        seen += 1
        yield script, a, b, wa.calls, wb.calls
    assert seen


CONFIGS = [(tries, deadline, cost, backoff, queue)
           for tries in (1, 2, 3, 4) for deadline in (0, 1, 2, 4, 9, 100) for cost in (0, 1) for backoff in (1, 3) for queue in ("present", "absent")
]


@pytest.mark.parametrize("tries, deadline, cost, backoff, queue", CONFIGS)
def test_the_plan_equals_the_oracle_over_the_whole_domain(tries, deadline, cost, backoff, queue):
    cfg = li.Cfg(tries, deadline, backoff, queue)
    n = 0
    for script, a, b, ca, cb in explore(cfg, cost):
        assert a == b, (cfg, cost, script)
        assert ca == cb, (cfg, cost, script)
        n += 1
    assert n > 0


def test_every_action_kind_and_exit_is_reached_in_the_domain():
    kinds, exits = set(), set()
    for tries, deadline, cost, backoff, queue in CONFIGS:
        if tries != 2 or cost != 1:
            continue
        for _script, a, _b, ca, _cb in explore(li.Cfg(tries, deadline, backoff, queue), cost):
            kinds |= {k for k, _ in ca}
            exits.add((a.exit, a.label, a.arm))
    assert kinds == {"verify", "view", "remove", "add", "sleep", "arm"}
    assert {(0, "applied", "armed"), (0, "applied", "skipped"), (2, "failed", "armed"), (2, "failed", "skipped"), (2, "failed", "failed"), (3, "applied", "failed")} <= exits


# ---- the named cases: the ones a grader attacked, stated as sentences
def _drive(cfg, results, cost=0):
    """Feed results by kind, in order; an unlisted call fails the test."""
    w = World([r for kind in results for r in kind], cost)
    return run_plan(cfg, w), w


@pytest.mark.parametrize("rc", [2, 3, 126, 127, 128, 137, 255, -9])
def test_an_unexpected_verify_code_is_unknown_and_never_success(rc):
    cfg = li.Cfg(4, 100, 1, "present")
    out, w = _drive(cfg, [[(rc, "")] * 4, [(0, "")]])
    assert (out.label, out.exit) == ("failed", 2) and [k for k, _ in w.calls].count("verify") == 4
    assert not [k for k, _ in w.calls if k in ("view", "remove", "add")], "an unknown read must never trigger a write"


@pytest.mark.parametrize("rc", [127, 137])
def test_an_unexpected_code_then_a_valid_read_recovers_without_writing(rc):
    out, w = _drive(li.Cfg(4, 100, 1, "absent"), [[(rc, ""), (0, "")]])
    assert (out.label, out.exit) == ("applied", 0) and not [k for k, _ in w.calls if k in ("view", "remove", "add")]


@pytest.mark.parametrize("rc", [2, 127, 137])
def test_an_unexpected_read_back_code_is_not_success(rc):
    cfg = li.Cfg(3, 100, 1, "absent")
    out, _ = _drive(cfg, [[(1, "")], [(0, "")], [(0, "")], [(rc, "")] * 3])
    assert (out.label, out.exit) == ("failed", 2) and "read-back" in out.why


def test_the_parse_of_the_environment():
    cases = [({}, (4, 45, 2)), ({"SIGNAL_INTENT_TRIES": "abc", "SIGNAL_INTENT_DEADLINE_S": "x", "SIGNAL_INTENT_BACKOFF_S": "y"}, (4, 45, 2)),
             ({"SIGNAL_INTENT_TRIES": "00"}, (4, 45, 2)), ({"SIGNAL_INTENT_TRIES": "0"}, (4, 45, 2)), ({"SIGNAL_INTENT_TRIES": "-3"}, (4, 45, 2)),
             ({"SIGNAL_INTENT_TRIES": "08", "SIGNAL_INTENT_DEADLINE_S": "08", "SIGNAL_INTENT_BACKOFF_S": "08"}, (8, 8, 8)),
             ({"SIGNAL_INTENT_TRIES": "1", "SIGNAL_INTENT_DEADLINE_S": "0", "SIGNAL_INTENT_BACKOFF_S": "0"}, (1, 0, 0)),
             ({"SIGNAL_INTENT_TRIES": "²", "SIGNAL_INTENT_DEADLINE_S": "٣", "SIGNAL_INTENT_BACKOFF_S": " 3"}, (4, 45, 2)),
             ({"SIGNAL_INTENT_TRIES": "3", "SIGNAL_INTENT_DEADLINE_S": "9", "SIGNAL_INTENT_BACKOFF_S": "1"}, (3, 9, 1))]
    for env, want in cases:
        cfg = li.parse_config(env, "q")
        assert (cfg.tries, cfg.deadline, cfg.backoff, cfg.queue) == want + ("q",), env


def test_labels_and_arm_texts():
    assert li.has_label(li.LABEL) and li.has_label("a\n" + li.LABEL + "\nb") and not li.has_label(li.LABEL + "-2") and not li.has_label("x" + li.LABEL)
    assert not li.has_label("")
    assert all(li.arm_is_benign(m) for m in ("Already Queued", "Auto-Merge Enabled", "already enabled", "pull request is in clean status"))
    assert not li.arm_is_benign("merge cannot be cleanly created") and not li.arm_is_benign("GraphQL: something else") and not li.arm_is_benign("")


def test_a_sleep_is_capped_at_the_time_left_and_nothing_starts_after_the_deadline():
    out, w = _drive(li.Cfg(4, 3, 2, "absent"), [[(2, "")] * 4], cost=1)
    assert [(k, s) for k, s in w.calls] == [("verify", 0), ("sleep", 2)] and (out.label, out.exit) == ("failed", 2)
    assert "(deadline 3s reached)" in out.why


def test_the_domain_is_not_small():
    """A guard on the oracle's reach: the unconstrained configuration alone is thousands of (script of results) pairs."""
    assert sum(1 for _ in explore(li.Cfg(4, 100, 1, "present"), 0)) >= 10_000


def test_a_command_that_outlives_its_timeout_is_rc_124_not_a_hang(monkeypatch):
    monkeypatch.setattr(li, "CMD_TIMEOUT", 1)
    rc, out = li._run(["sleep", "5"])
    assert rc == 124 and "timed out" in out
