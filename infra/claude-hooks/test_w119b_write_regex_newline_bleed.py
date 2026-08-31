#!/usr/bin/env python3
"""W119b — statement-boundary bleed in the regexes the 2026-08-18 pass did not
look at, plus the two cures that reached one copy of this block and not the other.

## What W119 already cured, and what it left alive

`test_w119_multiline_token_bleed.py` (2026-08-18) established the invariant: a
shell token never spans a bare newline, because bash treats a newline exactly as
it treats `;`, so a guard's inter-token separator must be `[ \\t]`, never `\\s`.
It applied that cure to `RM_RF_RE`, `WT_REMOVE_GIT_RE` and `CPMV_RE` — **in
`worktree_isolation.py` only**.

Three things survived it, and this file is about all three:

1. **`SEDI_RE` and `DDOF_RE` were never cured, in EITHER file.** They sit three
   lines from `CPMV_RE` in the same block. Their span between verb and flag is
   `[^|;&]*?`, and a negated class matches a newline, so `sed` on line 1 welds
   itself to a `-i` any number of lines later — and the `-i` need not be sed's.
2. **`host_boundary.py` never received the `CPMV_RE` half of that cure**, under a
   comment reading *"CLONED VERBATIM from worktree_isolation.py"* — an assertion
   that stopped being true the moment the original moved, and that is precisely
   what kept anyone from looking. Thirteen days.
3. **`host_boundary.py` never received the W84 `_strip_noise` cure either**, and
   that one fails **OPEN**. See below.

## Two live incidents, both measured

**Over-match (2026-08-31, a real session).** Three lines that write nothing:

    sed -n '40,75p' <repo>/scripts/fleet_mail.sh
    echo "=== ssh config for air ==="
    grep -A6 -i "^Host air" <HOME>/.ssh/config 2>/dev/null | head -20

blocked as *"HOST BOUNDARY VIOLATION (write to host-sensitive path)"*.
`WRITE_HINT_RE`'s `\\bsed\\b[^|]*-i` matched from `sed` on line 1 across two
newlines to the **`-i` of grep** on line 3; `SEDI_RE` took the next token as the
destination and handed the guard a credentials file.

**Under-match, fail-OPEN (found by a cross-family refuter reviewing the first
draft of this very fix).** `host_boundary._strip_noise` used `'[^']*'`, which
matches newlines, so:

    echo don't panic
    cp /tmp/evil <HOME>/.ssh/config
    echo it's done

collapsed to `echo don''s done` — the apostrophes in *don't* and *it's* paired
across three lines and **deleted the `cp` line from the scanned text entirely**.
The write to a protected path was ALLOWED. Same defect class, opposite and worse
direction, on the credentials guard, in the copy that never got the W84 cure.

That is why an over-matching guard is not "the safe direction": the two live in
the same char-class mistake, and only one of them announces itself.

## What this file asserts

- **Over-match** — commands that write nothing are allowed (three of the four
  cases reproduce a real pre-fix block; the `tee` case is labelled below).
- **Innocence** — every real write to a protected path is still blocked, through
  all five channels, alone and on line 2, **including the BSD `sed -i ''` form,
  which is the only form `sed -i` has on macOS — this fleet's own OS.** The first
  draft tested only the GNU form and therefore certified nothing about the form
  that actually runs here.
- **Parity** — the six shared regexes are pinned identical across both hooks,
  read with a paren-balancing extractor so a multi-line `re.compile(` cannot
  fake agreement (`data_plane_guard.py` in this directory already uses that
  style, so this is a live risk, not a hypothetical one).
- **Behavioural parity of `_strip_noise`** — a string compare cannot see a
  divergence in a function body, and that is where the fail-open lived.
- **The property, behaviourally** — for each regex, "no token pair joins across
  `\\n`", asserted by running it. The first draft grepped the source for `\\s+`,
  which would not have caught the ORIGINAL defect being reintroduced: `[^|;&]*?`
  contains no `\\s` at all. So would `re.DOTALL`, `[\\s\\S]+`, `[ \\t\\n]+`, `\\v+`.
- **Both hooks are executed**, not just host_boundary: the shared extraction
  functions are imported and driven directly, because the two files' plumbing
  around these regexes is NOT identical and string equality cannot see that.

## Known residuals, named rather than inherited silently

Verified still-allowed after this fix, and deliberately out of scope — each is a
pre-existing path-resolution gap that this diff neither introduces nor worsens,
and each is recorded in the PR so it is inherited knowingly:

- `$HOME`-expanded targets (`cp /tmp/evil $HOME/.ssh/config`) — `_resolve_target`
  expands `~` but not `$VAR`.
- multi-file `tee` (`tee /tmp/ok ~/.ssh/config`) — only the first file is read.
- `cd ~/.ssh && echo evil > config` — relative to the payload's cwd, not the `cd`.
- `cp -t ~/.ssh /tmp/evil` — GNU `--target-directory` hides the destination in a flag.
- `>|` noclobber-override redirects.
- a genuine backslash-newline continuation is no longer swept into one statement.
  That trade-off is the one the 2026-08-18 cure already chose for
  `RM_RF_RE`/`CPMV_RE`; this file matches it rather than inventing a second.

VERIFIED NOT VACUOUS: run against the pre-fix hooks restored from `origin/main`,
the over-match, parity and property tests FAIL and the innocence test passes
(it must pass on both sides — that is what makes it evidence the guard was
narrowed across statements and not within one). The `tee` over-match case passed
before the fix too: its bleed could only capture a following line's command
*name*, never a protected path, so it is a FORWARD guard against the same class,
not a reproduction. Calling it a fourth reproduction would make this docstring
the same confident-and-wrong artifact the fix exists to remove.
"""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
HOST_BOUNDARY = HERE / "host_boundary.py"
WORKTREE_ISOLATION = HERE / "worktree_isolation.py"
HOME = pathlib.Path.home()
SSH_CONFIG = HOME / ".ssh" / "config"


def _load(path: pathlib.Path, name: str):
    """Import a hook module so its real functions can be driven directly."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_hook(hook: pathlib.Path, cmd: str, cwd: str) -> tuple[int, str]:
    """Drive a hook end-to-end the way the harness does: JSON payload on stdin."""
    env = dict(os.environ)
    env.pop("HOST_BOUNDARY_OFF", None)
    env.pop("AGENT_WORKTREE_ENFORCEMENT", None)
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd}
    proc = subprocess.run(
        [sys.executable, str(hook)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=20, env=env,
    )
    return proc.returncode, proc.stderr


# The shared W79 extraction regexes. REDIR_RE is here deliberately: leaving it
# out of the first draft let a real, security-relevant divergence stand one line
# below the block the parity test was written to protect.
_SHARED_REGEX_NAMES = (
    "WRITE_HINT_RE", "REDIR_RE", "TEE_RE", "SEDI_RE", "DDOF_RE", "CPMV_RE",
)


def _regex_source(path: pathlib.Path, name: str) -> str | None:
    """The full `<name> = re.compile(...)` expression, however many lines it spans.

    Balances parens rather than taking the first line: two files can carry the
    same first line and different patterns underneath, and `data_plane_guard.py`
    in this same directory already declares a multi-line `re.compile(`, so the
    first refactor to that style would silently disarm a first-line comparison.
    Comments are stripped so a divergence in prose is not reported as a
    divergence in behaviour.
    """
    text = path.read_text()
    marker = f"{name} = re.compile("
    idx = text.find(marker)
    if idx == -1:
        return None
    depth = 0
    out: list[str] = []
    for ch in text[idx:]:
        out.append(ch)
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
    else:
        return None  # unbalanced — report as unreadable, never as parity
    expr = "".join(out)
    return " ".join(expr.split())


# ---------------------------------------------------------------- over-match --

def _overmatch_cases() -> list[str]:
    """Commands that write NOTHING. Three of these were false BLOCKs pre-fix."""
    fails: list[str] = []
    cwd = str(HERE)

    cases = {
        "SEDI_RE bleed (the live 2026-08-31 incident)": (
            f"sed -n '40,75p' {HERE / 'host_boundary.py'}\n"
            'echo "=== ssh config ==="\n'
            f'grep -A6 -i "^Host air" {SSH_CONFIG} 2>/dev/null | head -20\n'
        ),
        "DDOF_RE bleed (an `of=` two lines below a flagless dd)": (
            "dd if=/dev/zero bs=1 count=1 2>/dev/null\n"
            'echo "next"\n'
            f"echo of={SSH_CONFIG}\n"
        ),
        "CPMV_RE bleed (the half of the 2026-08-18 cure the clone never got)": (
            f"cp a.txt b.txt\ncat {SSH_CONFIG}\n"
        ),
        "TEE_RE bleed (forward guard — was already green pre-fix)": (
            f"echo hi | tee\ncat {SSH_CONFIG}\n"
        ),
        "_strip_noise quote bleed, read direction": (
            f"echo don't panic\ncat {SSH_CONFIG}\necho it's done\n"
        ),
    }
    for label, cmd in cases.items():
        rc, err = _run_hook(HOST_BOUNDARY, cmd, cwd)
        if rc != 0:
            fails.append(f"{label}: a command that writes nothing was blocked "
                         f"rc={rc}: {err.strip()[:170]}")
    return fails


# ----------------------------------------------------------------- innocence --

_REAL_WRITES = {
    # BSD form FIRST: on macOS — this fleet's OS — `sed -i` REQUIRES the
    # backup-suffix argument, so this is the only spelling that actually runs
    # here. Testing solely the GNU form certifies the wrong thing.
    "sed -i '' (BSD/macOS)": f"sed -i '' 's/x/y/' {SSH_CONFIG}",
    "sed -i (GNU)": f"sed -i 's/x/y/' {SSH_CONFIG}",
    "sed -i.bak (suffix attached)": f"sed -i.bak 's/x/y/' {SSH_CONFIG}",
    "sed -e ... -i (flags reordered)": f"sed -e 's/x/y/' -i {SSH_CONFIG}",
    "dd of=": f"dd if=/dev/zero of={SSH_CONFIG} bs=1 count=1",
    "cp": f"cp /tmp/evil.txt {SSH_CONFIG}",
    "mv": f"mv /tmp/evil.txt {SSH_CONFIG}",
    "redirect >": f"echo 'Host evil' > {SSH_CONFIG}",
    "redirect >>": f"echo 'Host evil' >> {SSH_CONFIG}",
    "redirect 2> (fd-qualified)": f"echo 'Host evil' 2> {SSH_CONFIG}",
    "redirect &> (combined)": f"echo 'Host evil' &> {SSH_CONFIG}",
    "tee": f"echo 'Host evil' | tee {SSH_CONFIG}",
    "tee -a": f"echo 'Host evil' | tee -a {SSH_CONFIG}",
}


def _innocence_cases() -> list[str]:
    """Real writes to a protected path. Every one MUST still be blocked."""
    fails: list[str] = []
    cwd = str(HERE)
    for label, cmd in _REAL_WRITES.items():
        rc, _ = _run_hook(HOST_BOUNDARY, cmd, cwd)
        if rc == 0:
            fails.append(
                f"DISARMED: a real write to a protected path via {label} was "
                f"ALLOWED — `{cmd}` returned rc=0. This fix narrows the guard's "
                "reach ACROSS statements; it must never narrow it WITHIN one."
            )
    # Same battery, each preceded by an unrelated line: confining the separator
    # must not blind the guard to a write that simply is not the first statement.
    for label, cmd in _REAL_WRITES.items():
        rc, _ = _run_hook(HOST_BOUNDARY, f'echo "preamble"\n{cmd}\n', cwd)
        if rc == 0:
            fails.append(f"DISARMED (multi-line): a real {label} write to a "
                         "protected path on line 2 was ALLOWED.")
    # And the fail-open that a cross-family refuter found in the first draft:
    # apostrophes on lines 1 and 3 must not delete the write on line 2.
    quote_bleed = (
        f"echo don't panic\ncp /tmp/evil {SSH_CONFIG}\necho it's done\n"
    )
    rc, _ = _run_hook(HOST_BOUNDARY, quote_bleed, cwd)
    if rc == 0:
        fails.append(
            "FAIL-OPEN: `_strip_noise` paired the apostrophes in \"don't\" and "
            "\"it's\" across three lines, deleting the `cp` to a protected path "
            "from the scanned text. This is the W84 cure host_boundary never "
            "received; the write was ALLOWED."
        )
    return fails


# ------------------------------------------------------- both hooks, for real --

def _both_hooks_behavioural_cases() -> list[str]:
    """Drive the shared extraction in BOTH files, not just host_boundary.

    String equality of six regex lines cannot see a divergence in the plumbing
    around them — which is exactly where the `_strip_noise` fail-open lived. So
    the real functions are imported and called. This covers the shared
    extraction path; it does not claim to cover worktree_isolation's own
    repo-relative decision logic, which `test_w119_multiline_token_bleed.py`
    exercises end-to-end.
    """
    fails: list[str] = []
    hb = _load(HOST_BOUNDARY, "hb_w119b")
    wi = _load(WORKTREE_ISOLATION, "wi_w119b")

    def _paths(mod, cmd: str) -> list[str]:
        """Normalize the two hooks' differently-shaped returns.

        `_extract_write_targets` is one NAME with two RETURN TYPES:
        host_boundary yields `list[str]`, worktree_isolation yields
        `list[tuple[str, int]]` (it needs each target's offset to judge
        repo-relativeness). The divergence is legitimate — but it is exactly the
        shape that makes a naive `"path" in targets` membership test silently
        False against the tuple form, which is how the first draft of this test
        reported a phantom fail-open in worktree_isolation that did not exist.
        Normalize explicitly rather than assume a shape.
        """
        out: list[str] = []
        for t in mod._extract_write_targets(cmd):
            out.append(t[0] if isinstance(t, tuple) else t)
        return out

    bleeders = {
        "sed/grep -i across lines": "sed -n '1,5p' a.txt\ngrep -i host /etc/ssh/x\n",
        "dd then a later of=": "dd if=/dev/zero bs=1\necho of=/etc/ssh/x\n",
        "cp then a later cat": "cp a.txt b.txt\ncat /etc/ssh/x\n",
        "quote pairing across lines": "echo don't\ncp /tmp/e /etc/ssh/x\necho it's\n",
    }
    for label, cmd in bleeders.items():
        if label == "quote pairing across lines":
            continue  # inverse expectation — handled below
        for mod, name in ((hb, "host_boundary"), (wi, "worktree_isolation")):
            targets = _paths(mod, cmd)
            if "/etc/ssh/x" in targets:
                fails.append(
                    f"{name}: `{label}` still extracts /etc/ssh/x as a write "
                    f"target from a command that writes nothing. Got {targets!r}"
                )
    # The quote case is the inverse: the `cp` line MUST survive _strip_noise in
    # both files, so the destination IS expected among the targets. Its absence
    # is the fail-OPEN, not a pass.
    quote_cmd = bleeders["quote pairing across lines"]
    for mod, name in ((hb, "host_boundary"), (wi, "worktree_isolation")):
        if "/etc/ssh/x" not in _paths(mod, quote_cmd):
            fails.append(
                f"{name}: `_strip_noise` deleted the `cp` line — apostrophes on "
                "lines 1 and 3 paired across the newline and the real write "
                "vanished from the scanned text (W84, fail-OPEN)."
            )
    return fails


# -------------------------------------------------------------------- parity --

def _parity_cases() -> list[str]:
    """The shared W79 extraction regexes must be identical in both copies."""
    fails: list[str] = []
    for name in _SHARED_REGEX_NAMES:
        a = _regex_source(HOST_BOUNDARY, name)
        b = _regex_source(WORKTREE_ISOLATION, name)
        if a is None or b is None:
            missing = "host_boundary.py" if a is None else "worktree_isolation.py"
            fails.append(
                f"{name}: not found (or unbalanced parens) in {missing} — if it "
                "was deliberately removed, remove it from _SHARED_REGEX_NAMES in "
                "the SAME commit, so absence is never reported as parity."
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


def _strip_noise_parity_cases() -> list[str]:
    """`_strip_noise` must behave identically in both copies.

    A string compare of regex assignments cannot see into a function body, and
    that blind spot is where a fail-open lived for 13 days.
    """
    fails: list[str] = []
    hb = _load(HOST_BOUNDARY, "hb_sn")
    wi = _load(WORKTREE_ISOLATION, "wi_sn")
    probes = [
        "echo don't panic\ncp /tmp/evil /etc/ssh/x\necho it's done\n",
        'echo "open\ncp /tmp/evil /etc/ssh/x\necho close"\n',
        "echo 'single line' && cp a b\n",
        "cat <<'EOF'\nnot a command\nEOF\ncp a b\n",
    ]
    for probe in probes:
        got_hb, got_wi = hb._strip_noise(probe), wi._strip_noise(probe)
        if got_hb != got_wi:
            fails.append(
                "_strip_noise DIVERGED between the two hooks on:\n"
                f"  input : {probe!r}\n  host_boundary     : {got_hb!r}\n"
                f"  worktree_isolation: {got_wi!r}"
            )
    return fails


# ------------------------------------------------------------------ property --

def _property_cases() -> list[str]:
    """No token pair may join across a newline — asserted BEHAVIOURALLY.

    The first draft grepped the source for `\\s+`. That would not have caught
    the ORIGINAL defect being reintroduced: `[^|;&]*?` contains no `\\s` at all.
    Nor would `re.DOTALL`, `[\\s\\S]+`, `[ \\t\\n]+`, or `\\v+`. Pin the property
    by running the regex, and every spelling of the defect goes red.
    """
    fails: list[str] = []
    for path, modname in ((HOST_BOUNDARY, "hb_prop"), (WORKTREE_ISOLATION, "wi_prop")):
        mod = _load(path, modname)
        probes = [
            ("SEDI_RE", mod.SEDI_RE, "sed -n '1p' a.txt\ngrep -i x b.txt c.txt"),
            ("DDOF_RE", mod.DDOF_RE, "dd if=x bs=1\nof=/tmp/victim"),
            ("CPMV_RE", mod.CPMV_RE, "cp a.txt b.txt\ncat /tmp/victim"),
            ("TEE_RE", mod.TEE_RE, "echo x | tee\n/tmp/victim"),
            ("REDIR_RE", mod.REDIR_RE, "echo x >\n/tmp/victim"),
            ("WRITE_HINT_RE", mod.WRITE_HINT_RE, "sed -n '1p' a\ngrep -i b c"),
        ]
        for name, rx, probe in probes:
            m = rx.search(probe)
            if m and "\n" in m.group(0):
                fails.append(
                    f"{path.name}:{name} matched ACROSS a newline — a bash "
                    "newline is a statement boundary, so no token pair may join "
                    f"over one. Match spanned: {m.group(0)!r}"
                )
    return fails


def test_w119b_overmatch_allows_commands_that_write_nothing():
    assert not (f := _overmatch_cases()), "\n".join(f)


def test_w119b_innocence_real_writes_are_still_blocked():
    assert not (f := _innocence_cases()), "\n".join(f)


def test_w119b_both_hooks_extract_the_same_way():
    assert not (f := _both_hooks_behavioural_cases()), "\n".join(f)


def test_w119b_shared_regexes_are_identical_in_both_hooks():
    assert not (f := _parity_cases()), "\n".join(f)


def test_w119b_strip_noise_behaves_identically_in_both_hooks():
    assert not (f := _strip_noise_parity_cases()), "\n".join(f)


def test_w119b_no_regex_joins_tokens_across_a_newline():
    assert not (f := _property_cases()), "\n".join(f)


if __name__ == "__main__":
    problems = 0
    for fn in (
        test_w119b_overmatch_allows_commands_that_write_nothing,
        test_w119b_innocence_real_writes_are_still_blocked,
        test_w119b_both_hooks_extract_the_same_way,
        test_w119b_shared_regexes_are_identical_in_both_hooks,
        test_w119b_strip_noise_behaves_identically_in_both_hooks,
        test_w119b_no_regex_joins_tokens_across_a_newline,
    ):
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            problems += 1
            print(f"FAIL {fn.__name__}\n{exc}")
    sys.exit(1 if problems else 0)
