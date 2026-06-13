"""CI binding for the Zantara golden corpus.

Validates the corpus schema (blocking) and cross-references it against the
live bridge module: every guard a scenario names must exist, and every guard
the corpus relies on must be covered by the GUARD_MATRIX polarity tests.
Freshness (valid_until) is NOT blocking here — a date rolling over must not
block unrelated PRs (clock-race flaky-test scar); the validator CLI with
--strict-freshness covers that on the cron path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[6]
CORPUS_PATH = REPO_ROOT / "apps" / "evaluator" / "zantara_persona_eval" / "golden_corpus.json"
VALIDATOR_PATH = REPO_ROOT / "apps" / "evaluator" / "zantara_persona_eval" / "validate_corpus.py"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bridge = _load_module(
    "openclaw_whatsapp_bridge_for_corpus", REPO_ROOT / "scripts" / "openclaw_whatsapp_bridge.py"
)
validator = _load_module("zantara_corpus_validator", VALIDATOR_PATH)
CORPUS = json.loads(CORPUS_PATH.read_text())


def test_corpus_schema_is_valid() -> None:
    errors, _warnings = validator.validate(CORPUS)
    assert not errors, "golden corpus schema errors:\n" + "\n".join(errors)


def test_corpus_has_minimum_coverage() -> None:
    scenarios = CORPUS["scenarios"]
    n_entries = sum(len(s["questions"]) for s in scenarios)
    assert len(scenarios) >= 50, f"corpus shrank below 50 scenarios: {len(scenarios)}"
    assert n_entries >= 150, f"corpus shrank below 150 question entries: {n_entries}"
    domains = {s["domain"] for s in scenarios}
    assert domains == {"visa", "tax", "company", "property", "persona"}, (
        f"corpus must keep covering all five domains, got {sorted(domains)}"
    )


def test_every_named_guard_exists_in_bridge() -> None:
    named = {s["guard"] for s in CORPUS["scenarios"] if s.get("guard")}
    missing = sorted(g for g in named if not callable(getattr(bridge, g, None)))
    assert not missing, f"corpus names guards that do not exist in the bridge: {missing}"


def test_every_named_guard_is_in_production_chain() -> None:
    chain = {fn.__name__ for fn in bridge._REPLY_GUARD_CHAIN}
    named = {s["guard"] for s in CORPUS["scenarios"] if s.get("guard")}
    out_of_chain = sorted(named - chain)
    assert not out_of_chain, (
        f"corpus relies on guards not wired into _REPLY_GUARD_CHAIN: {out_of_chain}"
    )


def test_perishable_facts_carry_parseable_dates() -> None:
    import datetime as dt

    parsed = 0
    for s in CORPUS["scenarios"]:
        for fact in s["key_facts"]:
            if fact.get("valid_until"):
                expiry = dt.date.fromisoformat(fact["valid_until"])  # raises on garbage
                assert expiry.year >= 2026, (
                    f"{s['id']}: valid_until {fact['valid_until']} predates the corpus"
                )
                parsed += 1
    assert parsed >= 3, (
        f"expected at least the 3 known perishable facts (KBLI switch, RUPS, "
        f"LKPM Q2) to carry valid_until, found {parsed}"
    )
