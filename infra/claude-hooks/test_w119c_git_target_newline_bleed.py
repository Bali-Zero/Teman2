r"""W119c — the git-target and read-command regexes must not pair across a newline.

Sibling of `test_w119b_write_regex_newline_bleed.py`, which pinned the WRITE-target
block. This file pins the three sites that block did NOT reach, found by a repo-wide
sweep on 2026-08-31 after W119b had already landed. That is the lesson these tests
exist to make mechanical: curing the regexes a scar NAMED leaves the regexes beside
them alive, and a comment saying "same class, already handled" is not a check.

A Bash tool call is several statements joined by BARE NEWLINES, and bash reads `\n`
as `;`. So any `\s` in a pattern applied to the whole command string can weld the
tail of one statement onto the head of the next.

The three sites, and the DIRECTION each fails in — they are not the same defect:

  GIT_C_RE           FAIL-OPEN.  A line ending in a dangling `git -C` captures the
                     next statement's first token as the git target, so a real
                     `git reset --hard` in the main checkout is judged against a
                     path that does not exist and comes back allowed.
  BLOCKED_SUBCMD_RE  FAIL-CLOSED.  Its optional `-C <path>` prefix could span the
                     newline too. The command still matched (bare `git reset` on
                     the second line matches on its own), so this one never opened
                     a hole by itself — it is cured for hygiene, and because the
                     next reader should not have to re-derive which of the two it
                     was.
  READ_CMD_RE        FAIL-OPEN, detection-only.  `_read_hits_secret` uses
                     `.search()`, so the first match wins; a phantom pairing
                     consumed that one search and a genuine secret read later in
                     the same command never produced its WARN.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wi = _load("worktree_isolation")
hb = _load("host_boundary")

REPO = "/repo/main-checkout"


# --- GIT_C_RE: the fail-open, stated as the verdict it changes -----------------


def test_w119c_a_dangling_git_dash_c_cannot_hijack_the_next_statements_target():
    """The bypass itself: an innocent line above must not move the target.

    Pre-fix this returned "something"; the identical `git reset --hard` with no
    decoy returned the main checkout. Same command, two verdicts, chosen by a
    line that does nothing.
    """
    decoy = "git -C\nsomething && git reset --hard"
    assert wi._effective_git_target(decoy, REPO) == REPO


def test_w119c_git_c_regex_does_not_span_a_newline():
    assert wi.GIT_C_RE.search("git -C") is None
    assert wi.GIT_C_RE.search("something && git reset --hard") is None
    m = wi.GIT_C_RE.search("git -C\nsomething && git reset --hard")
    assert m is None or "\n" not in m.group(0)


def test_w119c_a_real_git_dash_c_is_still_extracted():
    """Innocence: the flag must keep working, including with -c flags before it."""
    assert wi._effective_git_target("git -C /tmp/elsewhere status", REPO) == "/tmp/elsewhere"
    assert (
        wi._effective_git_target("git -c core.pager=cat -C /tmp/elsewhere log", REPO)
        == "/tmp/elsewhere"
    )
    # tabs are legitimate same-line separators
    assert wi._effective_git_target("git\t-C\t/tmp/elsewhere\tstatus", REPO) == "/tmp/elsewhere"


def test_w119c_a_real_git_dash_c_on_the_second_line_is_still_extracted():
    """The cure must not make the guard blind to a -C that really is there."""
    cmd = "echo starting\ngit -C /tmp/elsewhere reset --hard"
    assert wi._effective_git_target(cmd, REPO) == "/tmp/elsewhere"


# --- BLOCKED_SUBCMD_RE: fail-closed, cured for hygiene -------------------------


def test_w119c_blocked_subcmd_prefix_does_not_span_a_newline():
    m = wi.BLOCKED_SUBCMD_RE.search("git -C\nsomething reset --hard")
    assert m is None or "\n" not in m.group(0)


def test_w119c_blocked_subcmd_still_catches_every_verb_it_guards():
    """Innocence AND guilt: the enumeration must survive the binding untouched."""
    for verb in ("checkout main", "switch main", "reset --hard", "merge x", "rebase x", "pull"):
        assert wi.BLOCKED_SUBCMD_RE.search(f"git {verb}"), verb
    assert wi.BLOCKED_SUBCMD_RE.search("git -C /some/path reset --hard")
    assert wi.BLOCKED_SUBCMD_RE.search("git -c user.name=x -C /some/path reset --hard")
    assert wi.BLOCKED_SUBCMD_RE.search("git stash")
    assert wi.BLOCKED_SUBCMD_RE.search("git clean -fd")
    assert wi.BLOCKED_SUBCMD_RE.search("git restore .")
    # W85 / W117 read-only escapes must stay spared
    assert wi.BLOCKED_SUBCMD_RE.search("git stash list") is None
    assert wi.BLOCKED_SUBCMD_RE.search("git stash show") is None
    assert wi.BLOCKED_SUBCMD_RE.search("git clean -fdn") is None


# --- READ_CMD_RE: the suppressed warning ---------------------------------------


def test_w119c_read_cmd_regex_does_not_span_a_newline():
    assert hb.READ_CMD_RE.search("cat") is None
    m = hb.READ_CMD_RE.search("cat\n/etc/nuzantara-secrets.env")
    assert m is None or "\n" not in m.group(0)


def test_w119c_a_phantom_read_does_not_consume_the_search_and_hide_a_real_one():
    """The consequence, not the regex: `.search()` returns the first match only.

    Pre-fix the dangling `tail` paired with the next line and won that single
    search, so the genuine secret read further down was never examined.
    """
    cmd = "tail\n-n 5 /tmp/harmless.log\ncat ~/.nuzantara-secrets.env\n"
    m = hb.READ_CMD_RE.search(cmd)
    assert m is not None
    assert "\n" not in m.group(0)
    assert "secrets" in cmd  # the read the guard must still be able to reach
    hits = [x.group(3) for x in hb.READ_CMD_RE.finditer(cmd)]
    assert any("nuzantara-secrets.env" in h for h in hits), hits


def test_w119c_a_real_read_is_still_matched():
    m = hb.READ_CMD_RE.search("cat /etc/passwd")
    assert m is not None and m.group(3) == "/etc/passwd"
    m = hb.READ_CMD_RE.search("tail -f /var/log/x")
    assert m is not None and m.group(3) == "/var/log/x"


def test_w119c_a_flag_that_takes_a_value_still_shadows_the_filename():
    """Pre-existing limit, pinned so the cure is not blamed for it later.

    `group(2)` eats only flag-shaped tokens, so a flag's separate VALUE lands in
    `group(3)` where a filename is expected: `head -n 20 /etc/shadow` reports
    `20`. This is unchanged by the newline binding — it was true before and is
    true after — and it is written down here because a reader comparing the two
    behaviours would otherwise have to re-derive whether W119c caused it.
    It makes `_read_hits_secret` MISS a read, never invent one, so it is a
    detection gap in the safe direction; widening the flag grammar is a separate
    concern and not part of this fix.
    """
    m = hb.READ_CMD_RE.search("head -n 20 /etc/shadow")
    assert m is not None and m.group(3) == "20"


# --- the class, not the three instances ----------------------------------------


def test_w119c_no_newline_can_be_welded_by_these_regexes():
    """Behavioural, per-regex: assert on what the pattern MATCHES, never its text.

    A source-grep for `\\s` would go green the moment someone reintroduced the
    defect with `[^|]`, `[^;&]`, `[\\s\\S]` or `.` under DOTALL — every one of
    which also crosses a newline.
    """
    probe = "git -C\nsomething && git reset --hard\ncat\n/etc/shadow\n"
    for mod, name in ((wi, "GIT_C_RE"), (wi, "BLOCKED_SUBCMD_RE"), (hb, "READ_CMD_RE")):
        rx = getattr(mod, name)
        for m in rx.finditer(probe):
            assert "\n" not in m.group(0), f"{name} matched across a newline: {m.group(0)!r}"
