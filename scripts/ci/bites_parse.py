#!/usr/bin/env python3
"""bites_parse.py - turn the `Bites:` contract from prose into something a machine can run.

Every verification contract in this repository is prose honoured by an LLM: 110 of the
177 PRs merged since 2026-09-01 carry a `Bites:` line, and nothing reads any of them.
This module is the first half of the cure - a `bites` block a machine can PARSE, and a
runner can later EXECUTE. It executes nothing itself, so the security model can be
reviewed and tested with no runner anywhere near it.

Why the contract lives in the DIFF rather than in the PR body, and the measurement
behind that count: docs/plans/2026-09-03-relaunch-lanes/LANE-H-bites-reconciler.md
(RULED 2026-09-04, Zero, Legge 5).

    evidence/<YYYY-MM>/<slug>/pack.yml     # the dated dir from evidence_paths.py

        bites:
          consumer: <who reads or executes the changed thing>
          where: ci | fly | pro | mini
          observe: python3 scripts/ci/bites_parse.py --selftest
          expect: exit0

THREE PARSE OUTCOMES, and the difference between them is the whole migration story:

  absent     - no `bites:` key at all.                     -> {"absent": true},  exit 0
  legacy     - a `bites:` block with no `observe:` key.    -> {"legacy": true},  exit 0
  executable - an `observe:` key is present.               -> the four fields,   exit 0
               Malformed (missing key, guard violation)    -> {"malformed":...}, exit 2

`absent` and `legacy` are NEVER an error: no merged pack may turn red retroactively
because a format arrived after it.

THE SECURITY MODEL is the point rather than a footnote. `observe:` comes from a file in a
PULL REQUEST - text any account that can open a PR controls - and the executor that will
consume this parser runs on a GitHub runner holding a token. So the rules are an
ALLOW-LIST, and they run at PARSE time: a command that fails them never becomes an
executable block, so no downstream caller can forget to check. The list itself, with the
scar record for every entry, is DATA in `bites_allowlist.yaml`; each `_guard_*` function
below documents what it refuses and why.

WHAT THIS MODULE DELIBERATELY DOES NOT DO: decide whether a command may run. Trust
(author_association, fork-ness) is the EXECUTOR's question - a Dependabot pack parses
exactly like anyone else's and is simply never executed.

TWO CONSTRAINTS THE EXECUTOR INHERITS, because neither is decidable from a command
string. Neither is a note: PR-2 ships tests for both or it ships a hole.

(1) A SANITISED ENVIRONMENT. Half of git's dangerous behaviour is reached through CONFIG
rather than argv, where no allow-list over a command line can see it: `diff` runs an
external diff or textconv filter, `status` starts `core.fsmonitor`, `cat-file`
lazy-fetches in a partial clone, a `%G` format runs `gpg.program`, a pager starts on a
TTY. The executor therefore runs every observation with `GIT_CONFIG_GLOBAL=/dev/null`,
`GIT_CONFIG_SYSTEM=/dev/null`, `GIT_ATTR_NOSYSTEM=1`, `GIT_PAGER=cat`,
`GIT_TERMINAL_PROMPT=0`, `GIT_OPTIONAL_LOCKS=0`, and curl with `-q` prepended (curl reads
`~/.curlrc` on every invocation, and that file can carry `output=`). One rule against a
whole class, where argv-level rules would be a list of the config keys somebody remembered.

(2) POST-MERGE ONLY. A pull request can add a script and its `bites-observable` marker in
the same diff, so the marker is exactly as strong as the review of the diff that
introduces it - no more. Post-merge, the marked script is reviewed, merged code. Against
an unmerged PR checkout there is no boundary here at all, and the same holds for
`python3 -m pytest`, which imports whatever `conftest.py` the branch happens to carry.
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

#: The security model is DATA, in `bites_allowlist.yaml` beside this file. It was ~200
#: lines of constants and rationale inside this module until 2026-09-04, when Zero ruled
#: the module had to shrink. The rationale moved WITH the data rather than into a
#: document: a rule whose scar record lives elsewhere is a rule the next editor deletes
#: without knowing what it cost. Names below are unchanged, so every caller and every
#: test still reads the same identifiers.
SPEC_PATH = Path(__file__).with_name("bites_allowlist.yaml")


def _load_spec(path: Path) -> dict[str, Any]:
    """Read the allow-list. Unreadable or empty is fatal, never an empty allow-list.

    An allow-list that fails open admits everything; an allow-list that fails to an
    EMPTY tuple refuses everything and looks like a broken parser rather than a
    breached one. Neither is a state this file may reach silently (superscar #2).
    """
    try:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"bites_parse: allow-list unreadable at {path}: {exc}") from exc
    if not isinstance(spec, dict) or not spec.get("commands"):
        raise SystemExit(f"bites_parse: allow-list at {path} is empty or malformed")
    return spec


def _flat(rows: list[Any] | None) -> tuple[str, ...]:
    """Flatten the file's comma-joined rows. Rows exist so the data stays readable."""
    out: list[str] = []
    for row in rows or []:
        out.extend(w.strip() for w in row.split(",")) if isinstance(row, str) else out.append(row)
    return tuple(w for w in out if w)


def _pairs(rows: list[Any]) -> tuple[tuple[str, str], ...]:
    """Subcommand PAIRS, with the two sentinels resolved."""
    return tuple((a, {"NO_SUBCOMMAND": NO_SUBCOMMAND,
                      "ANY_POSITIONAL": ANY_POSITIONAL}.get(b, b)) for a, b in rows)


#: What may follow an allow-listed subcommand word. The first draft spelled both of these
#: `None`, which read as "anything may follow" and was two rules wearing one name:
#: `gh api <path>` is followed by DATA, `fly version` by nothing - and `fly version
#: upgrade` REPLACES THE BINARY. See the file for the full record.
NO_SUBCOMMAND = "\x00no-subcommand"    # nothing but flags may follow
ANY_POSITIONAL = "\x00any-positional"  # a data argument follows, never a verb

_SPEC = _load_spec(SPEC_PATH)

BITES_KEY = _SPEC["key"]
REQUIRED_KEYS = tuple(_SPEC["required_keys"])
WHERE_SCOPES = tuple(_SPEC["where_scopes"])
ALLOWED_COMMANDS = tuple(_SPEC["commands"])

FLY_READONLY_SUBCOMMANDS = _pairs(_SPEC["fly"]["subcommands"])
FLY_ALLOWED_FLAGS = _flat(_SPEC["fly"]["flags"])
CURL_ALLOWED_FLAGS = _flat(_SPEC["curl"]["flags"])
CURL_ALLOWED_SHORT_BUNDLE = _SPEC["curl"]["short_bundle"]
CURL_VALUE_TAKING_FLAGS = _flat(_SPEC["curl"]["value_taking"])
PYTEST_ALLOWED_FLAGS = _flat(_SPEC["pytest"]["flags"])
PYTEST_VALUE_TAKING_FLAGS = _flat(_SPEC["pytest"]["value_taking"])
GH_READONLY_SUBCOMMANDS = _pairs(_SPEC["gh"]["subcommands"])
GH_ALLOWED_FLAGS = _flat(_SPEC["gh"]["flags"])
GH_API_FORBIDDEN_FLAGS = _flat(_SPEC["gh"]["api_forbidden"])
GIT_READONLY_SUBCOMMANDS = _flat(_SPEC["git"]["subcommands"])
GIT_GLOBAL_ALLOWED_FLAGS = _flat(_SPEC["git"]["global_flags"])
GIT_SUB_ALLOWED_FLAGS = _flat(_SPEC["git"]["flags"])
GIT_NUMERIC_FLAG_PREFIXES = _flat(_SPEC["git"]["numeric_prefixes"])
OBSERVABLE_MARKER = _SPEC["observable_marker"]
REMOTE_SHELL_TOKENS = _flat(_SPEC["remote_shell_tokens"])
_SHELL_METACHARS = tuple(_SPEC["shell_metachars"])
_INVISIBLE_CHARS = tuple(_SPEC["invisible_chars"])


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


def _flag_violation(tokens: list[str], allowed: tuple[str, ...], *,
                    numeric: bool = False) -> str | None:
    """The first flag not on the allow-list, or None. One loop for five commands.

    It was written out five times before 2026-09-04. The copies had NOT drifted - a
    differential over 1,501 invocations across all six commands reports zero verdict
    changes from the merge - so this is a size cut, not a bug fix, and it is recorded
    as one. The only asymmetry the five copies carried is pytest's `-o<name>=<value>`
    normalisation, kept here: `-O` (git grep's pager option) is a different, uppercase
    flag and is still refused.
    """
    for token in tokens:
        if not token.startswith("-"):
            continue
        base = token.split("=", 1)[0]
        if base.startswith("-o") and base != "-o":   # pytest's `-o<name>=<value>`
            base = "-o"
        if base in allowed or (numeric and _is_count_flag(base)):
            continue
        return base
    return None


def _see(section: str) -> str:
    """Every refusal ends at the entry's own scar record instead of restating it."""
    return f"see the `{section}` section of scripts/ci/bites_allowlist.yaml"


def _check_python3(head: str, rest: list[str]) -> list[str]:
    if rest[:1] != ["-m"]:
        if not (rest and rest[0].startswith("scripts/")):
            return ["observe: `python3` must run `scripts/...` from the checkout, or "
                    "`python3 -m pytest`"]
        return []
    if rest[1:2] != ["pytest"]:
        return ["observe: `python3 -m` is permitted only for `pytest`"]
    for flag in rest[2:]:
        if flag.split("=", 1)[0] in PYTEST_VALUE_TAKING_FLAGS and "=" not in flag:
            return [f"observe: write `pytest {flag}=<value>`. With a separate value there "
                    f"is no way to tell an option's value from a test path - `pytest -k "
                    f"tests` reads as the target `tests`, which exists, and pytest then "
                    f"discovers every test from the working directory."]
    bad = _flag_violation(rest[2:], PYTEST_ALLOWED_FLAGS)
    if bad:
        return [f"observe: `pytest {bad}` is not an allow-listed option - {_see('pytest')}"]
    if not [a for a in rest[2:] if not a.startswith("-")]:
        return ["observe: `pytest` with no target discovers every test from the working "
                "directory. Name the test path the observation is about."]
    return []


def _check_fly(head: str, rest: list[str]) -> list[str]:
    words = _leading_words(rest)
    if not _subcommand_permitted(words, FLY_READONLY_SUBCOMMANDS):
        return [f"observe: `{head} {' '.join(words[:2]) or '<none>'}` is not a read-only "
                f"subcommand - permitted: " + _render_table(FLY_READONLY_SUBCOMMANDS, "")]
    bad = _flag_violation(rest, FLY_ALLOWED_FLAGS)
    if bad:
        return [f"observe: `{head} {bad}` is not an allow-listed option - `-c`/`--config` "
                f"READS the file its argument names. {_see('fly')}"]
    return []


def _check_gh(head: str, rest: list[str]) -> list[str]:
    words = _leading_words(rest)
    if not _subcommand_permitted(words, GH_READONLY_SUBCOMMANDS):
        return [f"observe: `gh {' '.join(words[:2]) or '<none>'}` is not a read-only "
                f"subcommand - permitted: " + _render_table(GH_READONLY_SUBCOMMANDS, "gh ")]
    bad = _flag_violation(rest, GH_ALLOWED_FLAGS)
    if bad:
        return [f"observe: `gh {bad}` is not an allow-listed option - `--cache` writes a "
                f"response cache and `--web` opens a browser. {_see('gh')}"]
    if words[:1] == ["api"]:
        for flag in rest:
            base = _any_flag_is(flag, GH_API_FORBIDDEN_FLAGS)
            if base:
                return [f"observe: `gh api {base}` sends a request body or a method other "
                        f"than GET - an observation reads"]
        for token in rest:
            if not token.startswith("-") and "://" in token:
                return [f"observe: `gh api {token}` names an absolute URL. gh uses an "
                        f"endpoint containing `://` VERBATIM as the request URL, so the "
                        f"host comes from the argument rather than from GitHub; and for a "
                        f"non-GitHub host gh falls through to $GH_ENTERPRISE_TOKEN / "
                        f"$GITHUB_ENTERPRISE_TOKEN unconditionally, sending it as an "
                        f"Authorization header to whatever host the argument named. "
                        f"An observation names a REST path: `repos/<owner>/<repo>`."]
    return []


def _check_git(head: str, rest: list[str]) -> list[str]:
    sub_at = next((i for i, a in enumerate(rest) if not a.startswith("-")), len(rest))
    bad = _flag_violation(rest[:sub_at], GIT_GLOBAL_ALLOWED_FLAGS)
    if bad:
        return [f"observe: `git {bad}` is a GLOBAL git option, and none are permitted - "
                f"`-c` runs a program the argument names and `--paginate` starts $PAGER. "
                f"Put the subcommand first. {_see('git')}"]
    for flag in rest[sub_at + 1:]:
        if flag.split("=", 1)[0] in ("--format", "--pretty") and "%G" in flag:
            return ["observe: a `%G` pretty-format placeholder asks git to VERIFY a "
                    "signature, which runs `gpg.program` - a program a config value names"]
    bad = _flag_violation(rest[sub_at + 1:], GIT_SUB_ALLOWED_FLAGS, numeric=True)
    if bad:
        return [f"observe: `git {bad}` is not an allow-listed option - the deny-list this "
                f"replaced lost `--output`, `-O` and `--no-index` one at a time. "
                f"{_see('git')}"]
    sub = rest[sub_at] if sub_at < len(rest) else ""
    if sub not in GIT_READONLY_SUBCOMMANDS:
        return [f"observe: `git {sub or '<none>'}` is not a local read-only subcommand - "
                f"permitted: {', '.join(GIT_READONLY_SUBCOMMANDS)}"]
    return []


def _check_curl(head: str, rest: list[str]) -> list[str]:
    for flag in rest:
        if not flag.startswith("-"):
            continue
        base, _, value = flag.partition("=")
        if value.startswith("@") or (base not in CURL_ALLOWED_FLAGS and "@" in flag):
            return ["observe: a curl option whose value begins with `@` makes curl READ A "
                    "LOCAL FILE into the request - an observation reads the network, not "
                    "the disk"]
        if base in CURL_ALLOWED_FLAGS:
            continue
        if not base.startswith("--") and len(base) > 1 and all(
                c in CURL_ALLOWED_SHORT_BUNDLE for c in base[1:]):
            continue  # a bundle of valueless short options, e.g. -sS
        return [f"observe: `curl {base}` is not an allow-listed option - the deny-list it "
                f"replaced lost `-b`, `-w@`, `--netrc-file`, `--variable`, `--json=@`, "
                f"`--libcurl` and `--etag-save` one at a time. {_see('curl')}"]
    # The first draft only checked args that LOOKED like URLs, so `curl evil.test/x` sailed
    # through and curl defaulted it to plain http. The rule is positive: exactly one
    # non-flag argument, https. Consuming a value-taking option's value by ARITY rather
    # than by "does it start with -" is what admits `curl -m 5 <url>` and
    # `-w '%{http_code}' <url>` without admitting a second URL.
    words: list[str] = []
    skip_next = False
    for token in rest:
        if skip_next:
            skip_next = False
        elif token in CURL_VALUE_TAKING_FLAGS:
            skip_next = True
        elif not token.startswith("-"):
            words.append(token)
    if len(words) != 1:
        return [f"observe: `curl` must take exactly one non-flag argument (the https URL); "
                f"found {len(words)}. Write value-taking flags as `--flag=value`."]
    if not words[0].startswith("https://"):
        return [f"observe: `curl` target `{words[0]}` is not an https:// URL"]
    return []


_COMMAND_CHECKS = {
    "python3": _check_python3, "gh": _check_gh, "git": _check_git,
    "curl": _check_curl, "fly": _check_fly, "flyctl": _check_fly,
}


def _guard_command_allowlist(command: str) -> list[str]:
    """First token must be allow-listed, and each allowed command is then narrowed."""
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return [f"observe: not parseable as a command ({exc})"]
    if not argv:
        return ["observe: empty command"]
    head, rest = argv[0], argv[1:]
    if head not in ALLOWED_COMMANDS:
        return [f"observe: `{head}` is not allow-listed - permitted first tokens are "
                f"{', '.join(ALLOWED_COMMANDS)}"]
    return _COMMAND_CHECKS[head](head, rest)


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
#: The corpus is DATA and lives in `bites_corpus.yaml` beside this file: 104 fixtures,
#: 218 lines of Python until 2026-09-04, when Zero ruled the module itself had to
#: shrink. Only the loader has to stay here. `_pack` is what makes the compact form
#: possible - most fixtures differ from each other in exactly one field, and spelling
#: the surrounding four lines 104 times would move the bulk without removing it.
#:
#: EDITING NOTE. Two guilt fixtures in that file carry the literal shape
#: "curl ... pipe ... sh". `~/.claude/hooks/guardrails-client.sh` scans every Bash
#: command for that shape and refuses it - including inside a heredoc that is merely
#: WRITING the file. Edit the corpus with a Python script or an editor tool, never by
#: piping a heredoc through Bash. Superscar #3 in miniature, on our own tooling.
CORPUS_PATH = Path(__file__).with_name("bites_corpus.yaml")


def _pack(observe: str, *, consumer: str = "CI", where: str = "ci",
          expect: str = "exit0") -> str:
    """A minimal pack carrying one `bites:` block, with the command single-quoted.

    Quoting `observe` is deliberate: the command guards, not YAML's plain-scalar
    rules, are what these fixtures are about, and a plain scalar beginning with
    `{`, `*`, `&`, `>` or `|` would be typed by YAML before any guard saw it.
    Fixtures that are ABOUT the YAML layer carry a verbatim `pack:` instead, and
    three carry an unquoted `observe:` so the corpus still proves that spelling parses.
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


def load_corpus(path: Path | None = None) -> tuple[tuple[str, str, str], ...]:
    """(label, pack text, expected class) for every fixture on disk.

    A missing or unreadable corpus is a hard error rather than an empty tuple: a
    selftest that silently runs zero fixtures reports `0/0 pass`, which is superscar
    #2 - green because nothing ran.
    """
    target = path or CORPUS_PATH
    try:
        entries = yaml.safe_load(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"bites_parse: corpus unreadable at {target}: {exc}") from exc
    if not entries:
        raise SystemExit(f"bites_parse: corpus at {target} is empty")
    return tuple(
        (
            entry["label"],
            entry["pack"] if "pack" in entry else _pack(
                entry["observe"],
                consumer=entry.get("consumer", "CI"),
                where=entry.get("where", "ci"),
                expect=entry.get("expect", "exit0"),
            ),
            entry["class"],
        )
        for entry in entries
    )


CONFORMANCE_CORPUS: tuple[tuple[str, str, str], ...] = load_corpus()


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
