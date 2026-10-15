#!/usr/bin/env python3
"""B31'': every decision of `scripts/signal_merge_intent.sh` lives here, as ONE pure plan.

`plan(cfg)` is a generator: it yields the next network action (an `Act`), is sent the result of the previous one (a `Result`), and ends by
yielding an `Outcome`. It performs no I/O and reads no clock, so every branch of it can be driven by a scripted environment: the oracle test
(`tests/test_label_intent.py`) drives it over the whole finite input domain. `drive` is the only place that touches the world, and
`scripts/signal_merge_intent.sh` is `exec python3 label_intent.py`, a line with no conditional.

Rules the plan carries (B31, B31-prime):
  - the label is read back first with `label_census.py verify` (rc 0 valid, 1 not valid; ANYTHING else is unknown and is retried, never read as valid);
  - valid: nothing is written; not valid: remove (when present) then add, retried; then read back again; only a read-back rc 0 is success;
  - the wall-clock deadline is asked before every network call and every sleep; a sleep never runs past it;
  - a label not shown valid at the end is FATAL: exit 2; an arm failure is exit 3; usage is exit 1.
"""
from __future__ import annotations

import functools
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

LABEL = "localci:merge-shadow-ok"
DEFAULT_TRIES, DEFAULT_DEADLINE, DEFAULT_BACKOFF = 4, 45, 2
BENIGN_ARM = ("already queued", "auto-merge enabled", "already enabled", "clean")


@dataclass(frozen=True)
class Cfg:
    tries: int
    deadline: int
    backoff: int
    queue: str


@dataclass(frozen=True)
class Act:
    kind: str          # verify | view | remove | add | sleep | arm
    seconds: int = 0


@dataclass(frozen=True)
class Result:
    rc: int
    out: str
    elapsed: int       # whole seconds since the plan started


@dataclass(frozen=True)
class Outcome:
    label: str         # applied | failed
    why: str           # "" when applied
    arm: str           # armed | skipped | failed
    exit: int
    arm_rc: int = 0
    arm_out: str = ""


def _number(raw: str, default: int) -> int:
    return int(raw) if raw.isascii() and raw.isdigit() else default


def parse_config(env: dict, queue: str) -> Cfg:
    tries = _number(env.get("SIGNAL_INTENT_TRIES", ""), 0)
    return Cfg(tries if tries >= 1 else DEFAULT_TRIES, _number(env.get("SIGNAL_INTENT_DEADLINE_S", ""), DEFAULT_DEADLINE),
               _number(env.get("SIGNAL_INTENT_BACKOFF_S", ""), DEFAULT_BACKOFF), queue)


def has_label(out: str) -> bool:
    return LABEL in out.splitlines()


def arm_is_benign(out: str) -> bool:
    return any(m in out.lower() for m in BENIGN_ARM)


def _tail(out: str, n: int) -> str:
    return " ".join(out.splitlines()[-n:]) + " "


def _note(cfg: Cfg, hit: bool) -> str:
    return f" (deadline {cfg.deadline}s reached)" if hit else ""


def _pause(cfg: Cfg, backoff: int, elapsed: int):
    """-> (backoff, elapsed, hit): no sleep once the deadline is spent, and none past it."""
    left = cfg.deadline - elapsed
    if left <= 0:
        return backoff, elapsed, True
    r = yield Act("sleep", min(backoff, left))
    return backoff * 2, r.elapsed, False


def _first_read(cfg: Cfg):
    """-> (vrc, elapsed, hit): rc 0 or 1 end it; anything else is unknown and is read again, bounded."""
    vrc, elapsed, hit, backoff = 2, 0, False, cfg.backoff
    for i in range(1, cfg.tries + 1):
        if cfg.deadline - elapsed <= 0:
            return vrc, elapsed, True
        r = yield Act("verify")
        vrc, elapsed = r.rc, r.elapsed
        if vrc in (0, 1):
            return vrc, elapsed, hit
        if i < cfg.tries:
            backoff, elapsed, hit = yield from _pause(cfg, backoff, elapsed)
    return vrc, elapsed, hit


def _write(cfg: Cfg, elapsed: int):
    """-> (rc, out, elapsed, hit): remove a stale label, add, retried with backoff, every call asked of the deadline."""
    backoff, has, rc, out, hit = cfg.backoff, False, 1, "", False
    if cfg.deadline - elapsed > 0:
        r = yield Act("view")
        has, elapsed = r.rc == 0 and has_label(r.out), r.elapsed
    else:
        hit = True
    for i in range(1, cfg.tries + 1):
        rc, out = 0, ""
        if has:
            rc = 1
            if cfg.deadline - elapsed > 0:
                r = yield Act("remove")
                rc, out, elapsed = r.rc, r.out, r.elapsed
            else:
                hit = True
            has = has and rc != 0
        if rc == 0:
            rc = 1
            if cfg.deadline - elapsed > 0:
                r = yield Act("add")
                rc, out, elapsed = r.rc, r.out, r.elapsed
            else:
                hit = True
        if rc == 0:
            return rc, out, elapsed, hit
        if i < cfg.tries:
            backoff, elapsed, pause_hit = yield from _pause(cfg, backoff, elapsed)
            hit = hit or pause_hit
    return rc, out, elapsed, hit


def _readback(cfg: Cfg, elapsed: int, out: str):
    """-> (valid, out, hit): only a read-back rc 0 is success."""
    backoff, hit = cfg.backoff, False
    for i in range(1, cfg.tries + 1):
        if cfg.deadline - elapsed <= 0:
            return False, out, True
        r = yield Act("verify")
        out, elapsed = r.out, r.elapsed
        if r.rc == 0:
            return True, out, hit
        if i < cfg.tries:
            backoff, elapsed, hit = yield from _pause(cfg, backoff, elapsed)
    return False, out, hit


def plan(cfg: Cfg):
    vrc, elapsed, hit = yield from _first_read(cfg)
    label, why = "applied", ""
    if vrc == 1:
        rc, out, elapsed, hit = yield from _write(cfg, elapsed)
        written = rc == 0
        valid, rout, rhit = (yield from _readback(cfg, elapsed, out)) if written else (False, "", False)
        label = "applied" if written and valid else "failed"
        why = (f"the label write failed (rc={rc}){_note(cfg, hit)}: {_tail(out, 3)}" if not written else
               "" if valid else f"read-back after the write does not show a valid label{_note(cfg, rhit)}: {_tail(rout, 2)}")
    elif vrc != 0:
        label, why = "failed", f"the label could not be read (rc={vrc}){_note(cfg, hit)}: nothing was changed"
    if cfg.queue == "absent":
        yield Outcome(label, why, "skipped", 0 if label == "applied" else 2)
        return
    r = yield Act("arm")
    failed = r.rc != 0 and not arm_is_benign(r.out)
    yield Outcome(label, why, "failed" if failed else "armed", 3 if failed else (0 if label == "applied" else 2), r.rc, r.out)


# --------------------------------------------------------------------------------------------------- the world (I/O only)
def _run(cmd: list[str], stdout_only: bool = False, env: dict | None = None) -> tuple[int, str]:
    """A command that cannot start is rc 127 (what the shell said), never a traceback."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    except OSError as exc:
        return 127, f"{cmd[0]}: {exc}"
    return res.returncode, res.stdout if stdout_only else res.stdout + res.stderr


def run_act(act: Act, env: dict, repo: str, pr: str) -> tuple[int, str]:
    here = Path(__file__).resolve().parent
    verify = env.get("SIGNAL_INTENT_VERIFY") or ""
    census = ["python3", str(here / "label_census.py"), "verify", "--repo", repo, "--pr", pr]
    gh_edit = ["gh", "pr", "edit", pr, "--repo", repo]
    cmds = {
        "verify": [verify, repo, pr] if verify else census,
        "sleep": ["sleep", str(act.seconds)],
        "view": ["gh", "pr", "view", pr, "--repo", repo, "--json", "labels", "--jq", ".labels[].name"],
        "remove": [*gh_edit, "--remove-label", LABEL],
        "add": [*gh_edit, "--add-label", LABEL],
        "arm": ["gh", "pr", "merge", pr, "--repo", repo, "--auto"],
    }
    return _run(cmds[act.kind], stdout_only=act.kind == "view")


def drive(cfg: Cfg, run) -> Outcome:
    started = time.monotonic()
    gen = plan(cfg)
    step = next(gen)
    while isinstance(step, Act):
        rc, out = run(step)
        step = gen.send(Result(rc, out, int(time.monotonic() - started)))
    return step


def main(argv: list[str], env: dict | None = None) -> int:
    env = os.environ if env is None else env
    pr = argv[0] if argv else ""
    if not (pr.isascii() and pr.isdigit()):
        print("usage: signal_merge_intent.sh <PR-number>", file=sys.stderr)
        return 1
    repo = env.get("SIGNAL_INTENT_REPO") or "Bali-Zero/Teman2"
    base = env.get("SIGNAL_INTENT_BASE") or "main"
    cfg = parse_config(env, "unknown")
    if env.get("SIGNAL_INTENT_SHOW_CONFIG") == "1":
        print(f"tries={cfg.tries} deadline={cfg.deadline} backoff={cfg.backoff}")
        return 0
    env = {**env, "SIGNAL_INTENT_REPO": repo, "SIGNAL_INTENT_BASE": base}
    _, probe = _run([str(Path(__file__).resolve().parents[1] / "merge_queue_rule.sh")], stdout_only=True, env=dict(env))
    queue = probe.strip()
    cfg = parse_config(env, queue)
    out = drive(cfg, functools.partial(run_act, env=env, repo=repo, pr=pr))
    if out.label == "failed":
        print(f"SIGNAL_INTENT_FAIL pr={pr} label=failed queue={queue}: {out.why}", file=sys.stderr)
    if out.arm == "failed":
        print(f"SIGNAL_INTENT_FAIL pr={pr} label={out.label} queue={queue} arm=failed (rc={out.arm_rc}): {_tail(out.arm_out, 3)}", file=sys.stderr)
        return out.exit
    print(f"SIGNAL_INTENT pr={pr} label={out.label} queue={queue} arm={out.arm}")
    return out.exit


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
