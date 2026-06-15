#!/usr/bin/env python3
"""Validate the Zantara golden corpus (schema + freshness).

Schema errors always exit 1. Expired ``valid_until`` facts print a freshness
report; they exit 1 only with ``--strict-freshness`` (meant for the weekly
cron + Telegram alert, NOT for PR-blocking CI — a date rolling over must not
block unrelated merges, cf. the clock-race flaky-test scar).

Usage:
    python apps/evaluator/zantara_persona_eval/validate_corpus.py
    python apps/evaluator/zantara_persona_eval/validate_corpus.py --strict-freshness
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

CORPUS_PATH = Path(__file__).resolve().parent / "golden_corpus.json"

EXPECTED_BEHAVIORS = frozenset(
    {"state_directly", "state_then_team", "defer", "guarded_canonical"}
)
REQUIRED_LANGS = ("en", "id", "it")
KNOWN_DOMAINS = frozenset({"visa", "tax", "company", "property", "persona"})


def validate(corpus: dict) -> tuple[list[str], list[str]]:
    """Return (schema_errors, freshness_warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    today = dt.date.today()

    scenarios = corpus.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        return (["corpus has no scenarios"], [])

    seen_ids: set[str] = set()
    for s in scenarios:
        sid = s.get("id", "<missing-id>")
        if sid in seen_ids:
            errors.append(f"{sid}: duplicate scenario id")
        seen_ids.add(sid)

        if s.get("domain") not in KNOWN_DOMAINS:
            errors.append(f"{sid}: unknown domain {s.get('domain')!r}")
        if s.get("expected_behavior") not in EXPECTED_BEHAVIORS:
            errors.append(f"{sid}: unknown expected_behavior {s.get('expected_behavior')!r}")

        questions = s.get("questions") or {}
        for lang in REQUIRED_LANGS:
            q = questions.get(lang)
            if not isinstance(q, str) or len(q.strip()) < 8:
                errors.append(f"{sid}: missing/short question for lang={lang}")

        facts = s.get("key_facts") or []
        if not facts:
            errors.append(f"{sid}: no key_facts — an unanchored scenario is not golden")
        for i, fact in enumerate(facts):
            if not (fact.get("fact") or "").strip():
                errors.append(f"{sid}: key_facts[{i}] missing fact text")
            if not (fact.get("source") or "").strip():
                errors.append(f"{sid}: key_facts[{i}] missing source — every fact must be traceable")
            valid_until = fact.get("valid_until")
            if valid_until:
                try:
                    expiry = dt.date.fromisoformat(valid_until)
                except ValueError:
                    errors.append(f"{sid}: key_facts[{i}] bad valid_until {valid_until!r}")
                    continue
                if expiry < today:
                    warnings.append(
                        f"{sid}: fact EXPIRED {valid_until} — re-verify against the live "
                        f"source and update: {fact['fact'][:80]}..."
                    )
                elif (expiry - today).days <= 7:
                    warnings.append(
                        f"{sid}: fact expires in {(expiry - today).days}d ({valid_until}): "
                        f"{fact['fact'][:80]}..."
                    )

        if s.get("expected_behavior") == "guarded_canonical" and not s.get("guard"):
            errors.append(f"{sid}: guarded_canonical scenario must name its guard")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-freshness", action="store_true")
    args = parser.parse_args()

    corpus = json.loads(CORPUS_PATH.read_text())
    errors, warnings = validate(corpus)

    for w in warnings:
        print(f"[FRESHNESS] {w}")
    for e in errors:
        print(f"[SCHEMA] {e}")

    n_scenarios = len(corpus["scenarios"])
    n_entries = sum(len(s.get("questions") or {}) for s in corpus["scenarios"])
    print(f"\ncorpus: {n_scenarios} scenarios, {n_entries} question entries, "
          f"{len(errors)} schema errors, {len(warnings)} freshness warnings")

    if errors:
        return 1
    if args.strict_freshness and warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
