#!/usr/bin/env python3
"""lint_paid_llm_entity.py — judge the paid-endpoint ban as an ENTITY.

WHY THIS EXISTS, stated as the gap and not as a feature.

Builder Contract §3 bans reaching a Claude model through a paid per-token
Anthropic endpoint, and says in as many words that grepping is only a first pass:

    an alias, a renamed env var, a wrapper library or a Bedrock/Vertex route
    reaches the same endpoint without either literal, and is equally banned

What CI enforces today (catE-sovereignty-lint.yml) is:

    grep -rnE 'Anthropic\\(\\s*api_key'            # the constructor, spelled out
    grep -rnE 'export\\s+ANTHROPIC_API_KEY=<value>' # the assignment, spelled out

Those catch the canonical shape. Each of the four routes §3 names walks past
them: `Anthropic as LLM` then `LLM(api_key=...)`; `Anthropic(**cfg)`; a wrapper
such as litellm routed at a claude model; `AnthropicBedrock()` or a bedrock
`invoke_model(modelId="anthropic.claude-…")`. The grep judges SPELLING. This
lint asks a System One model to judge the ENTITY.

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
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from redact_for_external import redact  # noqa: E402
from typesafe_client import ask, available, noul  # noqa: E402

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
# over-matching half. A CI yaml quoting `Anthropic(api_key` in order to FAIL a
# build is condemned by the pattern and is not scanned by catE; applying the
# pattern to .yml here would invent a violation catE never had.
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
    | api_key | auth_token | _TOKEN | _KEY
    | requests\.post | httpx | urllib\.request | fetch\(
    """
)

SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".sh", ".yml", ".yaml", ".toml"}

# Mirrors catE's exclusions so the two lints agree on what is in scope.
EXCLUDE_PARTS = (".venv", "node_modules", ".git", "vendor", "examples")
EXCLUDE_TEST = re.compile(r"(^|/)tests?/|(^|/)test_|_test\.")

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


# ─────────────────────────────────────────────────────────────────────── driver


def judge_file(path: str, text: str) -> dict:
    """The composed verdict for one file. OR, never AND."""
    by_grep = grep_verdict(text, path)
    probs: dict[str, float] = {}
    fired: list[str] = []
    asked = False
    if worth_asking(text) and available():
        asked = True
        probs, fired = jev_verdict(path, text)
    return {
        "path": path,
        "grep": by_grep,
        "asked": asked,
        "probabilities": probs,
        "fired_routes": fired,
        # OR. `fired` is empty when the service said nothing, so no-opinion is
        # not a vote either way.
        "violation": by_grep or bool(fired),
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
    args = parser.parse_args(argv)

    targets = [p for p in args.files if in_scope(p) and Path(p).is_file()]
    if not targets:
        print("lint_paid_llm_entity: no in-scope files in this diff.")
        return 0

    if not available():
        print(
            "lint_paid_llm_entity: TYPESAFE_API_KEY absent — entity judgment skipped, "
            "grep predicate still applied (this is the documented degrade path)."
        )

    results = []
    for path in targets:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"::warning::could not read {path}: {exc}")
            continue
        results.append(judge_file(path, text))

    violations = [r for r in results if r["violation"]]

    if args.json:
        print(json.dumps({"results": results}, indent=2))
    else:
        for r in violations:
            how = []
            if r["grep"]:
                how.append("grep")
            for route in r["fired_routes"]:
                how.append(f"{route}={r['probabilities'][route]:.2f}")
            print(f"::error file={r['path']}::paid-endpoint route ({', '.join(how)})")
        judged = sum(1 for r in results if r["asked"])
        print(
            f"lint_paid_llm_entity: {len(results)} file(s) in scope, "
            f"{judged} judged, {len(violations)} violation(s)."
        )

    if violations and not args.advisory:
        return 1
    if violations:
        print("::warning::advisory mode — findings above did NOT fail this build.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
