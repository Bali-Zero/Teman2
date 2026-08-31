#!/usr/bin/env python3
"""W119b — the same statement-boundary defect, in the regexes the 2026-08-18 pass
did not look at, and in the copy that never received the half it did fix.

## What W119 already cured, and what it left alive

`test_w119_multiline_token_bleed.py` (2026-08-18) established the invariant: a
shell token never spans a bare newline, because bash treats a newline exactly as
it treats `;`, so a guard's inter-token separator must be `[ \\t]`, never `\\s`.
It applied that cure to three regexes — `RM_RF_RE`, `WT_REMOVE_GIT_RE`,
`CPMV_RE` — **in `worktree_isolation.py`**.

Two things survived it, and this file is about both:

1. **`SEDI_RE` and `DDOF_RE` were never cured, in EITHER file.** They sit three
   lines away from `CPMV_RE` in the same block and carry the identical defect,
   in a worse spot: their span between the verb and its flag is `[^|;&]*?`, and
   a negated character class matches a newline, so `sed` on line 1 welds itself
   to a `-i` appearing ANY number of lines later. The `-i` does not even have to
   belong to sed.
2. **`host_boundary.py` never received the `CPMV_RE` half of the 2026-08-18
   cure.** Its block is introduced by the comment *"CLONED VERBATIM from
   worktree_isolation.py"* — an assertion that stopped being true the moment the
   original was fixed and the clone was not. That comment is precisely what made
   the divergence invisible: a reader who trusts it has no reason to look.

## The live incident (2026-08-31, this repo, a real session)

A single Bash call of three lines:

    sed -n '40,75p' /Users/nuzantara/nuzantara/scripts/fleet_mail.sh
    echo "=== ssh config for air ==="
    grep -A6 -i "^Host air" <HOME>/.ssh/config 2>/dev/null | head -20

Nothing in it writes anything. `host_boundary.py` blocked it with **"HOST
BOUNDARY VIOLATION (write to host-sensitive path) — target: <HOME>/.ssh/config"**.

The mechanism, measured: `WRITE_HINT_RE`'s `\\bsed\\b[^|]*-i` matched from `sed`
on line 1 across two newlines to the `-i` of **grep** on line 3; `SEDI_RE` then
took the next token as the write destination and handed the guard a credentials
file. A pure read was convicted as a mutating write.

## Why an over-matching guard is not "the safe direction"

It fails closed, so nothing was damaged. The damage is downstream and slower: a
guard that blocks correct work teaches the next session to reach for
`HOST_BOUNDARY_OFF=1`, and a disarmed guard blocks nothing at all. The escape
hatch is legitimate (W33); training people to use it routinely is not.

## Known residual, stated rather than inherited silently

Confining the separator to `[ \\t]` means a genuine backslash-newline line
continuation (`cp foo \\` / newline / `<HOME>/.ssh/config`) is no longer swept
into one statement, so its destination is not seen — an UNDER-match. That
trade-off is not introduced here: it is the one the 2026-08-18 cure already
chose for `RM_RF_RE`/`CPMV_RE`, and this file deliberately matches the
established cure rather than inventing a second, divergent one — divergence
between these two copies is the very disease being treated. It is named here so
the next reader inherits a known limit instead of an unexamined one.

## Guilt and innocence, both required (superscar family #3)

Over-match cases below assert the hook now ALLOWS commands that write nothing.
Innocence cases assert it still BLOCKS every real write to a protected path
through each of the five channels. A fix that only satisfied the first half
would be a disarmed guard wearing a green tick.

VERIFIED NOT VACUOUS, and stated exactly. Re-running this file against the
pre-fix hooks (restored from `origin/main`) produced:

  FAIL over-match     — SEDI_RE, DDOF_RE and CPMV_RE cases each blocked rc=2
                        with "HOST BOUNDARY VIOLATION (write to host-sensitive
                        path)" on commands that write nothing
  PASS innocence      — the pre-fix guard blocked real writes too, as it must;
                        this half exists to prove the fix did not disarm it,
                        so it is expected green on both sides
  FAIL parity         — CPMV_RE diverged between the two copies
  FAIL no-backslash-s — the separators were still `\\s`

The `tee` case is the one exception and is labelled honestly: it passed BEFORE
the fix as well. `TEE_RE`'s bleed could only capture a following line's first
token, which is a command name rather than a path, so it never reached a
protected target. It is a FORWARD guard against the same class in a regex that
happened not to have a live victim — not a reproduction of an observed defect.
Three of the four over-match cases are real reproductions; this one is not, and
saying otherwise would make this docstring the same kind of confident-and-wrong
artifact the fix is about.
"""
import json
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
HOST_BOUNDARY = HERE / "host_boundary.py"
WORKTREE_ISOLATION = HERE / "worktree_isolation.py"
HOME = pathlib.Path.home()
SSH_CONFIG = HOME / ".ssh" / "config"


def _run_hook(hook: pathlib.Path, cmd: str, cwd: str) -> tuple[int, str]:
    """Drive a hook the way the harness does: JSON payload on stdin."""
    env = dict(os.environ)
    env.pop("HOST_BOUNDARY_OFF", None)
    env.pop("AGENT_WORKTREE_ENFORCEMENT", None)
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd}
    proc = subprocess.run(
        [sys.executable, str(hook)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=20, env=env,
    )
    return proc.returncode, proc.stderr


# --- the five regex source lines that MUST stay identical across both copies ---
# Named individually rather than diffed as a block: a block diff would go red on
# an unrelated comment edit and get "fixed" by loosening it.
_SHARED_REGEX_NAMES = ("WRITE_HINT_RE", "TEE_RE", "SEDI_RE", "DDOF_RE", "CPMV_RE")


def _regex_source(path: pathlib.Path, name: str) -> str | None:
    """The literal right-hand side of `<name> = re.compile(...)`, or None."""
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{name} = re.compile("):
            return stripped
    return None


# ---------------------------------------------------------------- over-match --

def _overmatch_cases() -> list[str]:
    """Commands that write NOTHING. Each was a false BLOCK before the fix."""
    fails: list[str] = []
    cwd = str(HERE)

    # 1. The live incident: `sed -n` on line 1, grep's `-i` on line 3.
    live = (
        f"sed -n '40,75p' {HERE / 'host_boundary.py'}\n"
        'echo "=== ssh config ==="\n'
        f'grep -A6 -i "^Host air" {SSH_CONFIG} 2>/dev/null | head -20\n'
    )
    rc, err = _run_hook(HOST_BOUNDARY, live, cwd)
    if rc != 0:
        fails.append(
            "SEDI_RE bleed (the live 2026-08-31 incident): a three-line command "
            f"that only reads was blocked rc={rc}: {err.strip()[:160]}"
        )

    # 2. `dd` with no `of=` on its own line; an unrelated `of=` two lines later.
    dd_bleed = (
        "dd if=/dev/zero bs=1 count=1 2>/dev/null\n"
        'echo "next"\n'
        f"echo of={SSH_CONFIG}\n"
    )
    rc, err = _run_hook(HOST_BOUNDARY, dd_bleed, cwd)
    if rc != 0:
        fails.append(
            f"DDOF_RE bleed: an `echo of=` on a later line was read as dd's "
            f"destination, rc={rc}: {err.strip()[:160]}"
        )

    # 3. CPMV_RE — the half of the 2026-08-18 cure the clone never received.
    #    Cured in worktree_isolation.py since 2026-08-18; still bleeding in
    #    host_boundary.py until this PR.
    cp_bleed = f"cp a.txt b.txt\ncat {SSH_CONFIG}\n"
    rc, err = _run_hook(HOST_BOUNDARY, cp_bleed, cwd)
    if rc != 0:
        fails.append(
            "CPMV_RE bleed in host_boundary.py (the un-synced clone): a later "
            f"`cat` target was swept in as cp's destination, rc={rc}: "
            f"{err.strip()[:160]}"
        )

    # 4. `tee` ending a pipeline, with an unrelated path on the next line.
    tee_bleed = f"echo hi | tee\ncat {SSH_CONFIG}\n"
    rc, err = _run_hook(HOST_BOUNDARY, tee_bleed, cwd)
    if rc != 0:
        fails.append(
            f"TEE_RE bleed: a bare `tee` took the next line's first token as its "
            f"file, rc={rc}: {err.strip()[:160]}"
        )

    return fails


# ----------------------------------------------------------------- innocence --

def _innocence_cases() -> list[str]:
    """Real writes to a protected path. Every one MUST still be blocked."""
    fails: list[str] = []
    cwd = str(HERE)
    real_writes = {
        "sed -i": f"sed -i 's/x/y/' {SSH_CONFIG}",
        "dd of=": f"dd if=/dev/zero of={SSH_CONFIG} bs=1 count=1",
        "cp": f"cp /tmp/evil.txt {SSH_CONFIG}",
        "redirect": f"echo 'Host evil' > {SSH_CONFIG}",
        "tee": f"echo 'Host evil' | tee {SSH_CONFIG}",
    }
    for label, cmd in real_writes.items():
        rc, _ = _run_hook(HOST_BOUNDARY, cmd, cwd)
        if rc == 0:
            fails.append(
                f"DISARMED: a real write to a protected path via {label} was "
                f"ALLOWED — `{cmd}` returned rc=0. The fix must narrow the "
                "guard's reach across statements, never its reach within one."
            )

    # The same five, each still preceded by an unrelated line: narrowing the
    # separator must not make a guard blind to a write that is simply not first.
    for label, cmd in real_writes.items():
        multi = f'echo "preamble"\n{cmd}\n'
        rc, _ = _run_hook(HOST_BOUNDARY, multi, cwd)
        if rc == 0:
            fails.append(
                f"DISARMED (multi-line): a real {label} write to a protected "
                "path on line 2 of a two-line command was ALLOWED."
            )
    return fails


# -------------------------------------------------------------------- parity --

def _parity_cases() -> list[str]:
    """The shared W79 extraction regexes must be byte-identical in both copies.

    This is the machine half of the finding: the clone's comment asserted
    verbatim-ness in prose, and prose does not go red when it stops being true.
    """
    fails: list[str] = []
    for name in _SHARED_REGEX_NAMES:
        a = _regex_source(HOST_BOUNDARY, name)
        b = _regex_source(WORKTREE_ISOLATION, name)
        if a is None or b is None:
            fails.append(
                f"{name}: not found in "
                f"{'host_boundary.py' if a is None else 'worktree_isolation.py'} — "
                "if it was deliberately removed, remove it from _SHARED_REGEX_NAMES "
                "in the same commit, so this test never reports absence as parity."
            )
            continue
        if a != b:
            fails.append(
                f"{name} DIVERGED between the two hooks — this is exactly how the "
                "2026-08-18 CPMV_RE cure reached one file and not the other, for "
                "13 days, under a comment saying they were identical.\n"
                f"  host_boundary.py     : {a}\n"
                f"  worktree_isolation.py: {b}"
            )
    return fails


def _no_bare_backslash_s_cases() -> list[str]:
    """No separator inside the shared block may be `\\s` again.

    Pins the PROPERTY, not the current strings: a future edit that reintroduces
    `\\s+` between tokens goes red here even if it spells the rest differently.
    """
    fails: list[str] = []
    for path in (HOST_BOUNDARY, WORKTREE_ISOLATION):
        for name in _SHARED_REGEX_NAMES:
            src = _regex_source(path, name)
            if src is None:
                continue
            if re.search(r"\\s[+*]", src):
                fails.append(
                    f"{path.name}:{name} uses `\\s` as a separator again — `\\s` "
                    "matches a newline, and a bash newline is a statement "
                    "boundary. Use `[ \\t]`. (W119 / W119b)"
                )
    return fails


def test_w119b_overmatch_allows_commands_that_write_nothing():
    fails = _overmatch_cases()
    assert not fails, "\n".join(fails)


def test_w119b_innocence_real_writes_are_still_blocked():
    fails = _innocence_cases()
    assert not fails, "\n".join(fails)


def test_w119b_shared_regexes_are_identical_in_both_hooks():
    fails = _parity_cases()
    assert not fails, "\n".join(fails)


def test_w119b_no_separator_reintroduces_backslash_s():
    fails = _no_bare_backslash_s_cases()
    assert not fails, "\n".join(fails)


if __name__ == "__main__":
    problems: list[str] = []
    for fn in (
        test_w119b_overmatch_allows_commands_that_write_nothing,
        test_w119b_innocence_real_writes_are_still_blocked,
        test_w119b_shared_regexes_are_identical_in_both_hooks,
        test_w119b_no_separator_reintroduces_backslash_s,
    ):
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            problems.append(f"FAIL {fn.__name__}\n{exc}")
            print(f"FAIL {fn.__name__}\n{exc}")
    sys.exit(1 if problems else 0)
