#!/usr/bin/env python3
"""guard_fuzz_harness.py — reusable property/fuzz corpus runner for command-matching
guards (superscar #3: guard-over-match / under-match, cicatrix-superscar.md #3).

WHY THIS EXISTS: `worktree_isolation.py` produced FIVE over-matches in sequence
(W83, W84, W85, W91, W92) — each fixed by hand-adding one more guilt/innocence
pair to a hook-specific test file, after a LIVE false-block already bit someone.
A hand-written regression suite only ever covers shapes someone already got
burned by; it never proactively covers the surrounding shape-space (quotes,
comments, newlines, heredocs, pipes, ssh-wrapping, git-verbs-inside-strings)
BEFORE the sixth over-match ships. This harness generates a combinatorial
CORPUS of realistic shell command shapes and classifies every one against BOTH
decision channels of worktree_isolation.py, so a NEW blind spot shows up as an
"unexplained mismatch" during CI/dev, not as a live false-block in someone's
session weeks later.

DESIGN (deliberately guard-agnostic, so a future guard reuses this without a
rewrite): the harness does not hardcode "the git-verb regex" or "the write
regex" — it takes a GENERATOR (produces (command, expected_verdict, tag)
triples from a combinatorial grammar) and a CLASSIFIER (the guard function
under test) and reports mismatches. `worktree_isolation_corpus()` below is the
generator for THIS guard's two channels; a different guard registers its own
generator function and calls `run_corpus()` the same way.

USAGE:
    python3 infra/claude-hooks/guard_fuzz_harness.py
        # runs the worktree_isolation corpus (git-verb channel + write-target
        # channel), reports every mismatch, exit 0 iff zero mismatches.

    python3 infra/claude-hooks/guard_fuzz_harness.py --list
        # print the corpus size per channel without executing (sanity check).

Every mismatch is a FINDING (per the mandate): either a new over-match (should
allow, guard blocks) or a new under-match (should block, guard allows). The
harness does not assert VERDICT VALUES against a HAND-CURATED oracle for every
one of the hundreds of generated commands (that would just be another
hand-written regression suite in disguise) — instead each generated case
carries its expected verdict from the GRAMMAR RULE that produced it (e.g. "this
shape wraps a real local git-mutating verb with no ssh/quote/comment escape,
so it MUST block"), which is the property being fuzzed, not a memorized
example.

Reference: cicatrix-superscar.md #3 · W83/W84/W85/W91/W92 · registry.json.
"""
from __future__ import annotations

import importlib.util
import itertools
import pathlib
import sys
import tempfile
from typing import Callable, Iterable, NamedTuple

HERE = pathlib.Path(__file__).resolve().parent


def _load_wi_module(repo_root: str | None = None):
    """Load worktree_isolation.py as an isolated module instance so REPO_ROOT
    and the worktree resolver can be monkeypatched without touching the real
    hook (mirrors the pattern already used by test_w79/w83/w84/ffonly)."""
    spec = importlib.util.spec_from_file_location(
        "wi_fuzz", str(HERE / "worktree_isolation.py")
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    if repo_root is not None:
        mod.REPO_ROOT = repo_root
    return mod


class Case(NamedTuple):
    tag: str            # short id for the failure report, e.g. "gitverb/ssh-wrap/quoted"
    command: str
    cwd: str
    channel: str         # "git_verb" | "write_target"
    expect_block: bool   # the PROPERTY: what a correct guard must decide


# --------------------------------------------------------------------------
# Corpus generator for worktree_isolation.py — TWO decision channels.
# --------------------------------------------------------------------------

# A representative MUTATING git verb per historical scar family (checkout,
# stash-push i.e. bare stash, reset, merge, rebase, pull, commit -a, add -A).
_GIT_MUTATING_VERBS = [
    "checkout main",
    "stash",              # bare stash == stash push, must still block (W85 guilt)
    "reset --hard",
    "merge origin/main",
    "rebase origin/main",
    "pull",                # WITHOUT --ff-only — must still block (W91/2022 guilt)
    "commit -am wip",
    "add -A",
]
# Read-only git ops that must NEVER block regardless of wrapper (innocence floor).
_GIT_READONLY_VERBS = [
    "status",
    "log --oneline -5",
    "diff",
    "stash list",          # W85 innocence
    "stash show",          # W85 innocence
    "branch -a",
]

# Wrapper shapes that carry a command WITHOUT changing where it executes
# (must NOT flip the verdict — a mutating verb inside them still blocks,
# a read-only verb inside them still allows).
def _make_noop_wrappers(main_checkout: str) -> list[Callable[[str], str]]:
    """Wrappers built PER-fixture (need the concrete absolute main-checkout
    path baked in for the `cd <path> && git` shape).

    NOTE: `$(pwd)` and `$HOME`/tilde cd-targets are DELIBERATELY excluded.
    `$(pwd)` is a fuzzer artifact no real transcript produces (nobody types
    `cd $(pwd)`) and is already the documented conservative-allow case ("ANY
    write whose target is... unclassifiable" — file docstring). `$HOME`/tilde
    expansion resolves against the REAL machine's env, which this fixture-based
    corpus (a throwaway tempdir standing in for REPO_ROOT) structurally cannot
    validate without the fixture ITSELF living at a real $HOME-relative path —
    that property is already correctly owned by the dedicated
    test_tilde_target_resolver.py (which tests _effective_git_target directly,
    not through this fixture). Forcing it into this harness produces false
    noise (fixture-path != real-$HOME-path), not real coverage — reusing an
    existing tool wrong is itself a #3-family risk (testing the harness, not
    the guard).
    """
    return [
        lambda g: f"git {g}",
        lambda g: f"git {g}  # trailing comment mentioning --ff-only and 429 and stash",
        lambda g: f"# leading comment\ngit {g}",
        lambda g: f"cd {main_checkout} && git {g}",   # absolute literal — resolves in THIS fixture
        lambda g: f"echo about to run && git {g}",
        lambda g: f"git {g} && echo done",
        lambda g: f"git {g}; echo done",
        lambda g: f"git {g} | cat",
    ]

# Wrapper shapes that DO carry the op OFF-BOX (remote dispatch) — a mutating
# verb inside these must be ALLOWED (this checkout is never touched), and a
# read-only verb obviously still allowed.
_REMOTE_WRAPPERS: list[Callable[[str], str]] = [
    lambda g: f"ssh mini git {g}",
    lambda g: f"ssh mini 'git {g}'",
    lambda g: f'ssh mini "git {g}"',
    lambda g: f"ssh pro-lan git {g}",
    lambda g: f"scp -q file pro:/tmp/x && ssh pro git {g}",
    lambda g: f"echo prelude && ssh mini git {g}",   # ssh must start the SEGMENT
    lambda g: f"foo | ssh mini git {g}",              # ssh starts post-pipe segment
]

# Wrapper shapes where the git verb appears ONLY inside text — never a real
# command — must be ALLOWED even though it names a mutating verb literally.
_TEXT_ONLY_WRAPPERS: list[Callable[[str], str]] = [
    lambda g: f'echo "git {g} is dangerous"',
    lambda g: f"grep 'git {g}' docs/runbook.md",
    lambda g: f"printf 'reminder: git {g}\\n'",
    lambda g: f"cat <<'EOF'\nnote: run git {g} later\nEOF",
    lambda g: f"git commit -m \"mentions git {g} in the message\"",
]

# Malicious-adjacent shapes: a mutating verb WRAPPED so it LOOKS like one of
# the exempt patterns above but is actually still local + real — the guard
# must NOT be fooled (these are the "under-match" fuzz cases, the twin risk
# alongside over-match).
_DECEPTIVE_LOCAL_WRAPPERS: list[Callable[[str], str]] = [
    lambda g: f"echo ssh && git {g}",                       # 'ssh' just a word, not a dispatcher
    lambda g: f"echo 'run via ssh' ; git {g}",               # ssh mentioned, git runs LOCALLY after ;
    lambda g: f"mysshscript && git {g}",                     # 'ssh' substring inside a longer token
    lambda g: f'echo "# --ff-only later" && git {g}',        # W91-shape: flag-looking comment text
]

# TRUE-COMPOUND under-match (6th over-match, found at PR-2266 gate 2026-07-11,
# AFTER this corpus's first version shipped 382/382 green): a REAL
# ssh/scp/rsync dispatch runs in one segment, but the mutating verb lives in
# a DIFFERENT, LOCAL segment of the SAME compound command. This is distinct
# from _DECEPTIVE_LOCAL_WRAPPERS above (where "ssh" is merely a WORD, never a
# real dispatcher at all) — here ssh genuinely dispatches something off-box,
# just not the mutating verb. The whole-command `_is_remote_dispatch` check
# (pre-fix) was fooled by this shape because it only asked "does ANY segment
# start with ssh/scp/rsync", never "does THIS verb's OWN segment". Corpus gap
# that let W92's twin ship silently: the only "compound" cases the original
# corpus had were single-segment (ssh IS the first real token, carrying the
# WHOLE trailing command remotely) — this class needs TWO+ segments where
# the FIRST is remote and a LATER one is a real local mutation.
_TRUE_COMPOUND_REMOTE_PRELUDE_WRAPPERS: list[Callable[[str], str]] = [
    lambda g: f"ssh mini hostname && git {g}",         # && sibling of the gate's own counter-example
    lambda g: f"ssh pro hostname; git {g}",             # ; sibling
    lambda g: f"ssh pro hostname || git {g}",           # || sibling
]


def _git_verb_corpus(main_checkout: str) -> list[Case]:
    cases: list[Case] = []
    noop_wrappers = _make_noop_wrappers(main_checkout)
    for verb in _GIT_MUTATING_VERBS:
        for wrap in noop_wrappers:
            cmd = wrap(verb)
            cases.append(Case(f"gitverb/mutating/noop-wrap/{verb.split()[0]}", cmd, "MAIN", "git_verb", True))
        for wrap in _REMOTE_WRAPPERS:
            cmd = wrap(verb)
            cases.append(Case(f"gitverb/mutating/remote-wrap/{verb.split()[0]}", cmd, "MAIN", "git_verb", False))
        for wrap in _TEXT_ONLY_WRAPPERS:
            cmd = wrap(verb)
            cases.append(Case(f"gitverb/mutating/text-only-wrap/{verb.split()[0]}", cmd, "MAIN", "git_verb", False))
        for wrap in _DECEPTIVE_LOCAL_WRAPPERS:
            cmd = wrap(verb)
            cases.append(Case(f"gitverb/mutating/deceptive-local/{verb.split()[0]}", cmd, "MAIN", "git_verb", True))
        for wrap in _TRUE_COMPOUND_REMOTE_PRELUDE_WRAPPERS:
            cmd = wrap(verb)
            # the mutating verb's OWN segment is LOCAL (only the PRELUDE
            # segment is remote-dispatched) — must still block. This is the
            # exact shape the 6th over-match let through before segment-scoping.
            cases.append(Case(f"gitverb/mutating/true-compound-remote-prelude/{verb.split()[0]}", cmd, "MAIN", "git_verb", True))
    for verb in _GIT_READONLY_VERBS:
        for wrap in noop_wrappers + _REMOTE_WRAPPERS + _TEXT_ONLY_WRAPPERS + _TRUE_COMPOUND_REMOTE_PRELUDE_WRAPPERS:
            cmd = wrap(verb)
            cases.append(Case(f"gitverb/readonly/{verb.split()[0]}", cmd, "MAIN", "git_verb", False))
    # pull with --ff-only on the pull segment: allowed ONLY when the
    # tree-clean probe passes — the harness runs this against a FIXTURE where
    # the probe is forced clean, so the property under test is purely the
    # regex/segment logic, not the git-status side effect (that is covered by
    # test_ffonly_pull_exception.py's dedicated probe cases).
    ffonly_variants = [
        "git pull --ff-only",
        "git pull --ff-only origin main",
        "git pull origin main --ff-only",
        "git pull --ff-only  # fleet self-align",
        "git pull origin main  # use --ff-only next time",   # W91 guilt: comment must NOT open it
        "git pull; echo --ff-only",                           # flag in later segment
        "git pull --ff-only && git checkout main",            # compound still blocks (checkout)
    ]
    ffonly_expect = [False, False, False, False, True, True, True]
    for cmd, expect in zip(ffonly_variants, ffonly_expect):
        cases.append(Case(f"gitverb/ffonly/{cmd[:24]}", cmd, "MAIN", "git_verb", expect))
    return cases


# --- write-target channel ---------------------------------------------------

_WRITE_VERBS = [
    ("echo x > {t}", "redirect"),
    ("echo x >> {t}", "append-redirect"),
    ("echo x | tee {t}", "tee"),
    ("sed -i 's/a/b/' {t}", "sed-i"),
    ("cp /tmp/src {t}", "cp"),
    ("mv /tmp/src {t}", "mv"),
    ("dd if=/tmp/x of={t}", "dd"),
]

# Relative destinations — the W92 shape: no leading slash, resolved against
# SESSION cwd. `apps/f.py` legitimately lands in main when run bare-local;
# the SAME relative token inside a remote wrapper must NOT be classified as
# a main-checkout write (the actual write happens on the OTHER host).
_REL_DEST = "apps/f.py"
_ABS_MAIN_DEST = "{MAIN}/apps/f.py"
_ABS_WT_DEST = "{MAIN}/.worktrees/lane-x/apps/f.py"


def _write_target_corpus(main_checkout: str, worktree: str) -> list[Case]:
    cases: list[Case] = []
    for tmpl, tag in _WRITE_VERBS:
        # LOCAL bare command, relative dest, cwd=main → true positive (must block)
        local_cmd = tmpl.format(t=_REL_DEST)
        cases.append(Case(f"write/local-relative/{tag}", local_cmd, main_checkout, "write_target", True))

        # LOCAL bare command, absolute main dest → true positive
        abs_main_cmd = tmpl.format(t=_ABS_MAIN_DEST.format(MAIN=main_checkout))
        cases.append(Case(f"write/local-absolute-main/{tag}", abs_main_cmd, main_checkout, "write_target", True))

        # LOCAL bare command, absolute WORKTREE dest → true negative (allowed)
        abs_wt_cmd = tmpl.format(t=_ABS_WT_DEST.format(MAIN=main_checkout))
        cases.append(Case(f"write/local-absolute-worktree/{tag}", abs_wt_cmd, main_checkout, "write_target", False))

        # THE W92 SHAPE: ssh-wrapped, UNQUOTED, relative dest → the actual
        # write happens on the REMOTE host; this checkout is never touched.
        # This is the property W92 violates: guard must ALLOW.
        #
        # EXCEPTION (6th over-match correction, 2026-07-11 PR-gate finding):
        # if the write-verb TEMPLATE itself contains an unquoted `|` (only
        # `tee` does: "echo x | tee {t}"), wrapping it in `ssh mini <tmpl>`
        # unquoted does NOT keep the whole thing remote — the pipe SPLITS
        # into a remote segment (`ssh mini echo x`) and a SEPARATE local
        # segment (`tee {t}`), because ssh's stdout crosses back to the
        # local shell before `tee` runs. Empirically verified (piped ssh
        # output created a local file even when ssh auth itself failed).
        # This is genuinely different from the OTHER templates (redirect,
        # sed -i, cp, mv, dd), none of which contain a bare `|` — for those,
        # `ssh mini <tmpl>` really is ssh's own single implicit remote
        # command (trailing unquoted args all become the remote command
        # line), so the write stays off-box. Must block ONLY the tee case.
        remote_unquoted = f"ssh mini {tmpl.format(t=_REL_DEST)}"
        expect_block_unquoted = "|" in tmpl
        cases.append(Case(f"write/remote-unquoted-relative/{tag}", remote_unquoted, main_checkout, "write_target", expect_block_unquoted))

        # ssh-wrapped, SINGLE-quoted whole remote payload → same property
        remote_squoted = f"ssh mini '{tmpl.format(t=_REL_DEST)}'"
        cases.append(Case(f"write/remote-squoted-relative/{tag}", remote_squoted, main_checkout, "write_target", False))

        # ssh-wrapped, DOUBLE-quoted whole remote payload
        remote_dquoted = f'ssh mini "{tmpl.format(t=_REL_DEST)}"'
        cases.append(Case(f"write/remote-dquoted-relative/{tag}", remote_dquoted, main_checkout, "write_target", False))

        # scp / rsync dispatch to a remote-relative dest (colon-form) — must
        # never be misread as a LOCAL write into main.
        if tag in ("cp", "mv"):
            scp_cmd = f"scp /tmp/src mini:{_REL_DEST}"
            cases.append(Case(f"write/scp-colon-dest/{tag}", scp_cmd, main_checkout, "write_target", False))
            rsync_cmd = f"rsync -av /tmp/dir/ mini:{_REL_DEST}"
            cases.append(Case(f"write/rsync-colon-dest/{tag}", rsync_cmd, main_checkout, "write_target", False))

        # heredoc BODY mentioning a redirect-looking line — must never be a target
        heredoc_cmd = f"cat > /tmp/scratch.md <<'EOF'\n{tmpl.format(t=_REL_DEST)}\nEOF"
        cases.append(Case(f"write/heredoc-body-noise/{tag}", heredoc_cmd, main_checkout, "write_target", False))

        # quoted commit-message noise — must never be a target
        commit_cmd = f'git commit -m "note: {tmpl.format(t=_REL_DEST)}"'
        cases.append(Case(f"write/commit-message-noise/{tag}", commit_cmd, main_checkout, "write_target", False))

        # TRUE-COMPOUND under-match (6th over-match, PR-2266 gate finding
        # 2026-07-11): a remote ssh PRELUDE segment, then a LOCAL write in a
        # LATER segment — the exact shape that fooled the whole-command
        # exemption. The write's OWN segment has no ssh/scp/rsync token, so
        # it must still block regardless of the earlier remote segment.
        for sep in ("&&", ";", "||"):
            compound_cmd = f"ssh mini hostname {sep} {tmpl.format(t=_REL_DEST)}"
            cases.append(Case(
                f"write/true-compound-remote-prelude-{sep}/{tag}",
                compound_cmd, main_checkout, "write_target", True,
            ))

    # sinks / fd-dup / process-substitution — never a real write target
    for cmd in ["python x.py 2>&1 | tail", "echo ok > /dev/null", "diff <(cat a) <(cat b)"]:
        cases.append(Case("write/sink-or-nonwrite", cmd, main_checkout, "write_target", False))

    return cases


def worktree_isolation_corpus() -> tuple[list[Case], str, str, str]:
    """Build the full corpus against a throwaway fixture layout (machine-
    independent, same pattern as test_w79/w83/w84). Returns
    (cases, main_checkout_path, worktree_path, tmp_root) — caller owns cleanup."""
    tmp = tempfile.mkdtemp(prefix="wi_fuzz_")
    main_checkout = str(pathlib.Path(tmp) / "nuzantara")
    worktree = str(pathlib.Path(main_checkout) / ".worktrees" / "lane-x")
    pathlib.Path(main_checkout, "apps").mkdir(parents=True)
    pathlib.Path(worktree).mkdir(parents=True)

    cases = _git_verb_corpus(main_checkout) + _write_target_corpus(main_checkout, worktree)
    # substitute the MAIN placeholder cwd token used by _git_verb_corpus
    cases = [c._replace(cwd=main_checkout) if c.cwd == "MAIN" else c for c in cases]
    return cases, main_checkout, worktree, tmp


# --------------------------------------------------------------------------
# Runner — guard-agnostic given a corpus + a classify() callable per channel.
# --------------------------------------------------------------------------

def run_corpus(cases: Iterable[Case], mod) -> tuple[int, list[str]]:
    """Classify every case against the loaded module `mod`. Returns
    (n_mismatches, [failure lines]).

    STRUCTURAL FIX (6th over-match, 2026-07-11 PR-gate finding): this used to
    RE-IMPLEMENT the git-verb decision inline (a stale hand-copy that used the
    pre-segment-scoping whole-command `_is_remote_dispatch` check). That copy
    drifted from the real fix in `main()` the same day it was written,
    producing 24 false "mismatches" against cases the ACTUAL guard already
    handled correctly — a fuzz harness testing its own stale reimplementation
    instead of the guard is the exact failure mode this tool exists to
    prevent. Now calls `mod._git_verb_verdict()` directly — the SAME pure
    function `main()` calls — so the two can never diverge again."""
    fails: list[str] = []
    n = 0
    for c in cases:
        n += 1
        if c.channel == "git_verb":
            verdict = mod._git_verb_verdict(c.command, c.cwd)
            got_block = verdict.decision == "block"
        elif c.channel == "write_target":
            got_block = mod._write_hits_main(c.command, c.cwd) is not None
        else:
            raise ValueError(f"unknown channel: {c.channel}")

        if got_block != c.expect_block:
            fails.append(
                f"  [MISMATCH] tag={c.tag:42s} expect_block={c.expect_block!s:5} "
                f"got_block={got_block!s:5}  cmd={c.command!r}"
            )
    return len(fails), fails


def main() -> int:
    list_only = "--list" in sys.argv
    cases, main_checkout, worktree, tmp = worktree_isolation_corpus()

    if list_only:
        by_channel: dict[str, int] = {}
        for c in cases:
            by_channel[c.channel] = by_channel.get(c.channel, 0) + 1
        print(f"Corpus size: {len(cases)} total")
        for ch, n in sorted(by_channel.items()):
            print(f"  {ch}: {n}")
        return 0

    mod = _load_wi_module(repo_root=main_checkout)

    # worktree resolver monkeypatch — same fixture pattern as existing suites,
    # so the git-verb channel's `_is_path_in_allowed_worktree` reflects the
    # FIXTURE layout, not whatever real worktrees exist on the runner box.
    wt_root = pathlib.Path(main_checkout, ".worktrees").resolve()

    def _fake_allowed(path_str: str) -> bool:
        if not path_str:
            return False
        try:
            p = pathlib.Path(mod.os.path.expanduser(path_str))
            if not p.is_absolute():
                return False
            p = p.resolve()
        except Exception:
            return False
        try:
            return p.is_relative_to(wt_root)
        except Exception:
            return False

    mod._is_path_in_allowed_worktree = _fake_allowed

    # The fixture's main_checkout is a plain directory tree, not a real git
    # repo with committed history — `_main_tree_tracked_clean()`'s live
    # `git status` subprocess would error or behave unpredictably there.
    # Force it True so the ff-only PROPERTY (segment/regex logic in
    # `_only_ffonly_pull` — the thing THIS harness's git_verb corpus is
    # fuzzing) is exercised independent of the git-status side effect; the
    # side effect itself has its own dedicated probe-fixture coverage in
    # test_ffonly_pull_exception.py.
    mod._main_tree_tracked_clean = lambda: True

    n_fail, fail_lines = run_corpus(cases, mod)
    print(f"Ran {len(cases)} generated cases across 2 channels (git_verb + write_target).")
    if n_fail:
        print(f"\n=== {n_fail}/{len(cases)} UNEXPLAINED MISMATCHES ===")
        for line in fail_lines:
            print(line)
        return 1
    print(f"=== ALL {len(cases)} PASS — 0 unexplained mismatches ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
