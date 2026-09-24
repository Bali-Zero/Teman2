#!/usr/bin/env python3
"""lint_paid_llm_entity.py — judge the paid-endpoint ban as an ENTITY.

WHY THIS EXISTS, stated as the gap and not as a feature.

Builder Contract §3 bans reaching a Claude model through a paid per-token
Anthropic endpoint, and says in as many words that grepping is only a first pass:

    an alias, a renamed env var, a wrapper library or a Bedrock/Vertex route
    reaches the same endpoint without either literal, and is equally banned

What CI enforces today (catE-sovereignty-lint.yml) is:

    one grep for the vendor's constructor taking a per-token credential
    keyword argument, and one for a shell export that sets the vendor's
    credential environment variable to a value.

Both live in .github/workflows/catE-sovereignty-lint.yml as regex literals,
where they are safe because a pattern does not match itself. Quoting either
one here would not be safe, and finding that out cost this lane four reds.

Those catch the canonical shape. Each of the four routes §3 names walks past
them: an ALIASED import, so the constructor no longer carries the vendor's
name; a SPLATTED config dict, so the key never appears as a keyword argument;
a WRAPPER library pointed at a claude model; and a Bedrock or Vertex route,
which names the model in a string and the vendor nowhere. The grep judges
SPELLING. This lint asks a System One model to judge the ENTITY.

The four are described rather than written out — a docstring is scanned by
the same guards as code, and the literals belong in the guilt corpus, where
they are load-bearing. See scripts/tests/fixtures/paid_llm_entity/bench_cases.json
for each route as an actual line of source.

COMPOSITION — the one rule that matters (cicatrix #3, and the reason this file
is not simply "smarter matching"):

    verdict = grep_says_violation  OR  jev_says_violation

Never AND. An AND-composed guard fires LESS than the grep alone, so one model
false negative silently authorises what the repo blocks today. Under OR, every
failure mode of the model — wrong answer, hallucination, an injected diff that
steers it, the service being down — costs at most a false alarm that a human
clears in seconds. It can never open a gate.

Corollary, enforced by the code below: a missing key or an unreachable service
degrades to exactly today's behaviour. `ask()` returning None is "no opinion",
and no-opinion contributes nothing to an OR.

SCOPE: changed files only. A full-repo scan would re-surface the three
pre-existing baseline sites on every PR, which is what
catE-paid-anthropic-baseline.txt exists to prevent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from redact_for_external import redact  # noqa: E402
from typesafe_client import ask, available, noul, unavailable_reason  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
PARDON = REPO_ROOT / "infra" / "paid-llm-entity" / "pardoned.json"

# ──────────────────────────────────────────────────────────── incumbent, verbatim

# These two are the SAME predicates catE-sovereignty-lint.yml runs, transcribed
# so this lint can report what the grep alone would have said. They are not an
# improvement on it and must not drift from it: if catE changes, change these.
GREP_CONSTRUCTOR = re.compile(r"Anthropic\(\s*api_key")
GREP_ASSIGNMENT = re.compile(
    r"""export[ \t]+ANTHROPIC_API_KEY=[^"'\s]|setenv\([ \t]*["']ANTHROPIC_API_KEY"""
)


# catE applies each predicate to a specific file set:
#   constructor  →  --include='*.py'
#   assignment   →  --include='*.py' --include='*.sh'
# Transcribing the PATTERNS without their FILE SETS would not replicate the
# incumbent — it would silently widen it, and the half that widens is the
# over-matching half. A CI yaml quoting the banned constructor spelling in order
# to FAIL a build is condemned by that pattern and is not scanned by catE;
# applying the pattern to .yml here would invent a violation catE never had.
# Found by test_grep_does_not_fire_on_innocence_cases[test_asserting_the_ban].
GREP_CONSTRUCTOR_SUFFIXES = {".py"}
GREP_ASSIGNMENT_SUFFIXES = {".py", ".sh"}


def grep_verdict(text: str, path: str = "x.py") -> bool:
    """What today's CI would conclude from this file, alone.

    `path` decides which predicates apply, because catE scopes each one by
    suffix. The default keeps the common case (a .py file) terse at call sites.
    """
    suffix = Path(path).suffix
    if suffix in GREP_CONSTRUCTOR_SUFFIXES and GREP_CONSTRUCTOR.search(text):
        return True
    if suffix in GREP_ASSIGNMENT_SUFFIXES and GREP_ASSIGNMENT.search(text):
        return True
    return False


# ────────────────────────────────────────────────────────────── cheap prefilter

# Sending every changed file to the model would be wasteful, not unsafe. A file
# that mentions no model vendor and no HTTP client cannot be reaching one. This
# is deliberately GENEROUS — it over-includes, because a missed file is a missed
# violation while an extra file costs a fraction of a cent.
_INTEREST = re.compile(
    r"""(?ix)
    anthropic | claude | bedrock | vertex | litellm | openrouter
    | langchain | llamaindex | portkey | helicone | openai
    | \bllm\b | completion | chat\.completions
    | api_key | auth_token | _TOKEN | _KEY | x-api-key
    | requests | httpx | aiohttp | urllib\.request | http\.client | axios
    | \.post\( | \.request\( | fetch\(
    """
)
# The HTTP clauses above were once `requests\.post` alone, which missed
# `requests.Session().post(...)`, `requests.request("POST", ...)`, `aiohttp` and
# `http.client`. A file pulling URL, model and credential from config produced
# zero prefilter hits and was judged by nobody — neither the grep nor the model.
# Widened by the kimi-code/k3 council seat's finding, 2026-09-20. Over-inclusion
# here costs a fraction of a cent; under-inclusion costs the whole lane.

SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".sh", ".yml", ".yaml", ".toml"}

# catE does NOT use one exclusion list — it uses a DIFFERENT one per predicate:
#   constructor grep:  .venv/ node_modules/ .git/ tests/ test_
#   assignment  grep:  the same PLUS examples/ vendor/
# Collapsing them into one list excluded vendor/ and examples/ from the
# constructor predicate, which catE scans — so `vendor/runtime.py` carrying the
# banned constructor failed catE and was dropped here before composition. Third
# instance in this file of the same mistake: an exclusion wider than the
# incumbent's makes the composed verdict WEAKER than the regex alone, which is
# precisely what Rule 3 forbids. Found by the codex-gpt-5.6-sol council seat.
EXCLUDE_PARTS_CONSTRUCTOR = (".venv", "node_modules", ".git")
# The driver keeps the NARROWER set: a file only the constructor predicate
# scans must still reach the composition.
EXCLUDE_PARTS = EXCLUDE_PARTS_CONSTRUCTOR
# catE excludes `tests/` and a `test_` PREFIX — and nothing else. An earlier
# version here also excluded a `_test.` SUFFIX, which hid real repo files
# (admission_test.py, smoke_test.py) that catE does scan. Excluding more than
# the incumbent while claiming to mirror it is drift in the UNDER-matching
# direction. Found by an adversarial reviewer, 2026-09-20.
# `tests?/` also matched a SINGULAR `test/` directory, which catE does not
# exclude — so `test/smoke.py` carrying the banned constructor failed catE and
# was never even grep-checked here. That made the composed verdict WEAKER than
# the regex alone on that path, which Rule 3 exists to make impossible. Second
# instance of the same mistake in one file. Found by the kimi-code/k3 council
# seat, 2026-09-20.
EXCLUDE_TEST = re.compile(r"(^|/)tests/|(^|/)test_")

# The fixture corpus for this lint is, by construction, full of banned shapes.
# Judging it would fire on every run. It is excluded here and exercised by
# scripts/test_lint_paid_llm_entity.py instead.
FIXTURE_DIR = "scripts/tests/fixtures/paid_llm_entity"


def in_scope(path: str) -> bool:
    if FIXTURE_DIR in path:
        return False
    if any(f"/{part}/" in f"/{path}" for part in EXCLUDE_PARTS):
        return False
    if EXCLUDE_TEST.search(path):
        return False
    return Path(path).suffix in SOURCE_SUFFIXES


def worth_asking(text: str) -> bool:
    return bool(_INTEREST.search(text))


# ────────────────────────────────────────────────────────────────── the questions

# One question per route §3 names. They are separate Nouls rather than one
# "does this violate the ban?" because the jaggedness notes are explicit that a
# broad question hides several judgments — and because a per-route answer tells
# the human WHICH route fired, which is the difference between a useful CI error
# and "the model said no".
ROUTE_QUESTIONS: dict[str, dict] = {
    "direct_paid_sdk": {
        "type": "noul",
        "instructions": (
            "Does `file.content` construct an Anthropic SDK client with a per-token API "
            "key — that is, a paid pay-as-you-go credential — regardless of how the class "
            "or the key variable is named or imported?"
        ),
        "criteria": {
            "true": (
                "An Anthropic client is built with an API-key credential. This includes an "
                "aliased import (`from anthropic import Anthropic as X` then `X(api_key=...)`), "
                "a key read from a variable with any name, and a key passed through a dict or "
                "kwargs expansion."
            ),
            "false": (
                "No Anthropic client is constructed, OR it is constructed with auth_token= / "
                "an OAuth bearer token / CLAUDE_CODE_OAUTH_TOKEN, which is the sanctioned path. "
                "Code that UNSETS, deletes or blanks an API key is also false — stripping a "
                "credential is a defence, not a use."
            ),
        },
    },
    "wrapper_library": {
        "type": "noul",
        "instructions": (
            "Does `file.content` reach a Claude model through a third-party wrapper or "
            "gateway library rather than the Anthropic SDK directly?"
        ),
        "criteria": {
            "true": (
                "A library such as litellm, langchain, llamaindex, openrouter, portkey or a "
                "local wrapper module is called with a Claude/Anthropic model identifier and a "
                "per-token credential."
            ),
            "false": (
                "No such library is used, or it is used with a non-Anthropic model, or it is "
                "pointed at a local/self-hosted endpoint such as Ollama."
            ),
        },
    },
    "cloud_reseller_route": {
        "type": "noul",
        "instructions": (
            "Does `file.content` reach a Claude model through a cloud reseller — AWS Bedrock "
            "or Google Vertex AI?"
        ),
        "criteria": {
            "true": (
                "AnthropicBedrock / AnthropicVertex is constructed, or a bedrock/vertex client "
                "is invoked with a model identifier naming Claude (for example one beginning "
                "`anthropic.claude`)."
            ),
            "false": "No Bedrock or Vertex path to a Claude model is present.",
        },
    },
    "renamed_credential": {
        "type": "noul",
        "instructions": (
            "Does `file.content` supply an Anthropic per-token credential that is read from an "
            "environment variable or setting whose name is NOT `ANTHROPIC_API_KEY`?"
        ),
        "criteria": {
            "true": (
                "A credential reaching an Anthropic endpoint comes from a differently-named "
                "variable or config field — for example UPSTREAM_TOKEN, LLM_KEY, or a settings "
                "attribute."
            ),
            "false": (
                "No Anthropic credential is supplied, or it comes from ANTHROPIC_API_KEY itself "
                "(which the existing grep already covers), or the credential is an OAuth token."
            ),
        },
    },
}

# Above this, the route counts as fired. Deliberately high: under OR-composition
# a false alarm costs a human ten seconds, but this lint runs on every PR and a
# noisy gate gets disabled, which would cost everything. Calibrate on the bench
# (scripts/test_lint_paid_llm_entity.py --bench), not by intuition.
FIRE_THRESHOLD = 0.80


def jev_verdict(path: str, text: str) -> tuple[dict[str, float], list[str]]:
    """Ask the four route questions about one file.

    Returns (probabilities, fired_routes). An unavailable service yields ({}, [])
    — no opinion, which contributes nothing to the OR.
    """
    state = {
        "file": {"path": path, "content": redact(text)},
        "policy": (
            "This repository forbids reaching a Claude model through any paid per-token "
            "Anthropic endpoint, because a subscription already covers it. The sanctioned "
            "path is the `claude` CLI with CLAUDE_CODE_OAUTH_TOKEN, or the SDK with "
            "auth_token=. Local models and non-Anthropic providers are not covered by this ban."
        ),
    }
    answers = ask(state, ROUTE_QUESTIONS)
    if answers is None:
        return {}, []
    probs: dict[str, float] = {}
    fired: list[str] = []
    for route in ROUTE_QUESTIONS:
        value = noul(answers, route)
        if value is None:
            continue
        probs[route] = value
        if value >= FIRE_THRESHOLD:
            fired.append(route)
    return probs, fired


# ─────────────────────────────────────────────────────────────────────── pardon

# A pardon narrows ONLY the model's contribution to the composed verdict
# (see the module docstring's COMPOSITION section). It can never touch
# `by_grep` — the incumbent predicate is not in question here, and a pardon
# that reached it would be able to clear a file today's grep alone condemns.

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _normalize_path(p: str) -> str:
    """Exact-match key: posix separators, no leading `./`. No globs, no
    substring, no suffix — this is the only normalisation a pardon gets."""
    return Path(p).as_posix().removeprefix("./")


def _valid_entry(entry: object) -> bool:
    """One entry, all fields required. Any defect pardons nothing — the same
    fail-closed shape as `typesafe_client.authorized()`'s entry check: an
    entry that cannot prove its own shape authorizes/pardons exactly as much
    as no entry at all."""
    if not isinstance(entry, dict):
        return False
    path = entry.get("path")
    routes = entry.get("routes")
    reason = entry.get("reason")
    pr = entry.get("pr")
    date = entry.get("date")
    if not isinstance(path, str) or not path:
        return False
    if not isinstance(routes, list) or not routes:
        return False
    if not all(isinstance(r, str) and r in ROUTE_QUESTIONS for r in routes):
        return False
    if not isinstance(reason, str) or not reason:
        return False
    # bool is an int subclass in Python — excluded explicitly, same reason
    # `noul()` excludes it from a probability.
    if isinstance(pr, bool) or not isinstance(pr, int) or pr <= 0:
        return False
    if not isinstance(date, str) or not _DATE_RE.match(date):
        return False
    return True


def _parse_pardons(raw: str) -> dict[str, list[dict]]:
    """path -> [valid entry, ...]. Malformed JSON, a non-dict top level, or a
    non-list `entries` pardons NOTHING — same choice `load_grandfathered()`
    makes for the same reason: failing open would make corrupting one file
    the way to silence every violation it names. An individual entry that
    fails `_valid_entry` is dropped and the rest of the file still applies —
    one bad entry cannot take a whole registry down."""
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        return {}
    if not isinstance(data, dict):
        return {}
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}
    by_path: dict[str, list[dict]] = {}
    for entry in entries:
        if not _valid_entry(entry):
            continue
        by_path.setdefault(_normalize_path(entry["path"]), []).append(entry)
    return by_path


def load_pardons() -> dict[str, list[dict]]:
    """The registry on disk, path -> [valid entry, ...]. Absent, unreadable
    or malformed pardons NOTHING — deleting this file must not be the way to
    clear a violation it never actually pardoned."""
    try:
        raw = PARDON.read_text(encoding="utf-8")
    except (OSError, ValueError, RecursionError):
        return {}
    return _parse_pardons(raw)


def _pardons_for_path(path: str, pardons: dict[str, list[dict]]) -> dict[str, dict]:
    """route -> the entry that pardons it, for this one path."""
    result: dict[str, dict] = {}
    for entry in pardons.get(_normalize_path(path), []):
        for route in entry["routes"]:
            result[route] = entry
    return result


def pardon_grew(base_ref: str) -> list[str] | None:
    """`path:route` pairs pardoned in HEAD but not at `base_ref`, or `None` when the
    check could not run at all — the caller must then fail closed (return 3)
    rather than silently skip.

    Mirrors `lint_ban_prose.grandfather_grew`, with one deliberate
    difference: here the pardon file being ABSENT at a base ref that DOES
    resolve is not "unmeasurable" (skip) but "the base line was empty" —
    every path pardoned in HEAD counts as growth, the same as a renamed or
    added entry would. A first `pardoned.json` is judged against nothing,
    not exempted from the check that exists to stop it landing in the same
    diff as the violation it pardons.
    """
    ref_ok = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if ref_ok.returncode != 0:
        return None
    rel = PARDON.relative_to(REPO_ROOT).as_posix()
    out = subprocess.run(
        ["git", "show", f"{base_ref}:{rel}"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    before = _pairs(_parse_pardons(out.stdout)) if out.returncode == 0 else set()
    after = _pairs(load_pardons())
    return sorted(f"{path}:{route}" for path, route in after - before)


def _pairs(by_path: dict[str, list[dict]]) -> set[tuple[str, str]]:
    """The unit of growth is (path, route), never the path alone: a route
    added to an entry that already existed at the base is exactly as new as
    a fresh entry, and a path-only comparison would let it land in the same
    diff as the violation it pardons."""
    return {
        (path, route)
        for path, entries in by_path.items()
        for entry in entries
        for route in entry["routes"]
    }


# ─────────────────────────────────────────────────────────────────────── driver


def judge_file(
    path: str, text: str, pardons: dict[str, list[dict]] | None = None
) -> dict:
    """The composed verdict for one file. OR, never AND — a pardon can only
    remove entries from `fired_routes` before they reach the OR, it cannot
    touch `by_grep`."""
    if pardons is None:
        pardons = load_pardons()
    by_grep = grep_verdict(text, path)
    probs: dict[str, float] = {}
    fired: list[str] = []
    asked = False
    if worth_asking(text) and available():
        asked = True
        probs, fired = jev_verdict(path, text)
    entry_by_route = _pardons_for_path(path, pardons)
    pardoned_routes = [r for r in fired if r in entry_by_route]
    live = [r for r in fired if r not in entry_by_route]
    return {
        "path": path,
        "grep": by_grep,
        "asked": asked,
        "probabilities": probs,
        # `fired_routes` keeps EVERY route the model fired, pardoned or not
        # — the model's opinion is reported unchanged.
        "fired_routes": fired,
        "pardoned_routes": pardoned_routes,
        # OR. `live` is `fired` minus what a pardon narrowed away; `by_grep`
        # is never in that narrowing. `fired` empty (service silent) still
        # makes `live` empty, so no-opinion is not a vote either way.
        "violation": by_grep or bool(live),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", help="changed files to judge")
    parser.add_argument(
        "--advisory",
        action="store_true",
        help="report findings but always exit 0 (the observation period)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--base-ref",
        default=os.environ.get("BASE_SHA", ""),
        help=(
            "ref to compare the pardon list against (anti-bypass). The CI step "
            "already exports BASE_SHA; this flag exists for a local/manual run."
        ),
    )
    args = parser.parse_args(argv)

    targets = [p for p in args.files if in_scope(p) and Path(p).is_file()]
    if not targets:
        # NO in-scope files returns 0 before the growth check runs at all —
        # that is how a pardon lands: in its own PR, touching only the
        # registry, which is not itself in SOURCE_SUFFIXES.
        if args.json:
            print(json.dumps({"results": []}))
        else:
            print("lint_paid_llm_entity: no in-scope files in this diff.")
        return 0

    if args.base_ref:
        grew = pardon_grew(args.base_ref)
        if grew is None:
            print(
                f"::error::lint_paid_llm_entity: base ref {args.base_ref} does not "
                "resolve here — the pardon list cannot be verified, refusing to "
                "proceed."
            )
            return 3
        if grew:
            print(
                "::error::lint_paid_llm_entity: the pardon list GREW by "
                f"{len(grew)} path:route pair(s) — a new pardon cannot land in the "
                f"same diff as the violation it pardons: {', '.join(grew)}"
            )
            return 3
    elif not args.json:
        # Same reason the `reason` diagnostic below is guarded: a line on
        # stdout ahead of the JSON object makes json.loads() raise instead
        # of parse.
        print("lint_paid_llm_entity: pardon growth check skipped (no base ref).")

    pardons = load_pardons()

    reason = unavailable_reason()
    if reason is not None and not args.json:
        # Never on stdout in --json mode: a diagnostic line before the object
        # makes the output unparseable, and a caller doing json.loads() on it
        # gets an exception instead of a verdict. Found by codex-gpt-5.6-sol.
        #
        # The reason is printed rather than assumed: this used to say the key
        # was absent, which became false the day a second silence existed. A
        # key present and an endpoint unauthorized is the shape someone WILL
        # hit — it is what configuring the secret without a ruling now looks
        # like — and reading "key absent" there would send them to the wrong
        # settings page.
        print(
            f"lint_paid_llm_entity: entity judgment skipped ({reason}) — "
            "grep predicate still applied (this is the documented degrade path)."
        )

    results = []
    for path in targets:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"::warning::could not read {path}: {exc}")
            continue
        results.append(judge_file(path, text, pardons))

    violations = [r for r in results if r["violation"]]

    if args.json:
        print(json.dumps({"results": results}, indent=2))
    else:
        for r in violations:
            how = []
            if r["grep"]:
                how.append("grep")
            for route in r["fired_routes"]:
                if route in r["pardoned_routes"]:
                    continue
                how.append(f"{route}={r['probabilities'][route]:.2f}")
            print(f"::error file={r['path']}::paid-endpoint route ({', '.join(how)})")
        pardoned_count = 0
        for r in results:
            if not r["pardoned_routes"]:
                continue
            entry_by_route = _pardons_for_path(r["path"], pardons)
            for route in r["pardoned_routes"]:
                pardoned_count += 1
                entry = entry_by_route[route]
                p = r["probabilities"].get(route, 0.0)
                print(
                    f"::notice file={r['path']}::paid-endpoint route pardoned "
                    f"({route}={p:.2f}) — {entry['reason']} "
                    f"(PR #{entry['pr']}, {entry['date']})"
                )
        judged = sum(1 for r in results if r["asked"])
        print(
            f"lint_paid_llm_entity: {len(results)} file(s) in scope, "
            f"{judged} judged, {len(violations)} violation(s), "
            f"{pardoned_count} pardoned."
        )

    if violations and not args.advisory:
        return 1
    if violations:
        print("::warning::advisory mode — findings above did NOT fail this build.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
