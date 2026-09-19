"""review_hold_inventory.py — the PR-O1 keystone: every ``HUMAN_REVIEW`` producer,
derived from the pack AST and the backend adapters, never hand-listed.

# bites-observable — NO argument names a program, a file to write, or a
# database: only ``--json``, which changes stdout's format and nothing else
# (same bar `scripts/ci/observe_visa_seq22_signed.py` sets).

Plan `VISA-ORACLE-DW-20260919/PLAN.md` §1.3 counted every source of
``HUMAN_REVIEW_REQUIRED`` by hand, from four different files, and warned its
own count would go stale the moment any of the four moved independently.
This script is the derivation that count should have been: it reads the
highest SIGNED production pack on disk (never a hand glob — it reuses the
same resolver the interview-walk census pins against,
``gold_replay_driver.select_highest_repository_pack``) plus the two backend
adapter constants that raise the rest, and reports the union. Four producer
kinds, one function each below: ``pack_review_rules`` (PLAN §1.3a),
``minor_privacy_review_code`` (§1.3b), ``adapter_review_codes`` (§1.3c),
``pack_unknown_escalations`` (§1.3d, deliberately overlapping §1.3a — see its
own docstring). Also reports the orphan ``REVIEW_GATE_ITEMS`` — disclosures
`tree.ts` offers a visitor that `fact-mapper.ts`'s `REVIEW_FLAG_MAP` silently
drops (PLAN §1.3, closing paragraph): a visitor who discloses one of these
today is never heard by the engine at all.

Usage (from ``apps/backend-rag``)::

    PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.review_hold_inventory
    PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.review_hold_inventory --json

Exit 0 always — a read-only reporter, not a gate; a table full of producers
is data, not a failure. Exit non-zero only on an internal inconsistency: a
literal this script depends on (``REVIEW_GATE_ITEMS``, ``REVIEW_FLAG_MAP``,
or a non-empty HUMAN_REVIEW-stage rule set) that cannot be found is a
parser-drift bug in THIS script, not a silent empty report (cicatrix family
#3 — guard-under-match).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR,
    select_highest_repository_pack,
)
from backend.services.visa_engine.api_models import DisclosedReviewFlag
from backend.services.visa_engine.enums import OnUnknownAction, RuleStage
from backend.services.visa_engine.evaluate_path import (
    _DISCLOSED_REVIEW_REASON_CODES,
    MINOR_GUARDIAN_PRIVACY_REVIEW_CODE,
)
from backend.services.visa_engine.models import RulePackPayload

#: Monorepo root, derived from this file's own location (five parents up
#: from `apps/backend-rag/backend/scripts/visa_engine/`) — same convention
#: `reachability_report.py` uses, so this is correct regardless of the
#: caller's cwd, matching this module's own `PYTHONPATH=.` usage example.
_REPO_ROOT = Path(__file__).resolve().parents[5]

#: The live production interview's two TypeScript literals this script
#: cross-references. Neither has a Python-importable form (TypeScript), so
#: this script reads and regexes the source text — see `orphan_review_gate_items`.
DEFAULT_TREE_TS_PATH = _REPO_ROOT / "apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/tree.ts"
DEFAULT_FACT_MAPPER_PATH = (
    _REPO_ROOT / "apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts"
)

_REVIEW_GATE_ITEMS_RE = re.compile(r"export const REVIEW_GATE_ITEMS = \[(.*?)\] as const;", re.S)
_REVIEW_FLAG_MAP_RE = re.compile(r"const REVIEW_FLAG_MAP:.*?=\s*\{(.*?)\};", re.S)
_QUOTED_ITEM_RE = re.compile(r'"([a-z_]+)"')
_MAP_KEY_RE = re.compile(r"^\s*([a-z_]+):", re.M)


@dataclass(frozen=True)
class RuleReviewEntry:
    """One pack rule that either IS a review producer or can escalate to one."""

    rule_id: str
    stage: str
    scope: str
    code: str
    on_unknown: str


def load_highest_signed_pack(packs_dir: Path = PACKS_DIR) -> RulePackPayload:
    """The census's own resolver, never a hand glob of the packs directory —
    that is exactly how the census and this inventory would drift apart.

    `select_highest_repository_pack` returns the SIGNED envelope's raw dict
    (`protected`/`payload`/`signature`), not a bare payload — unlike
    `compile_pack.load_rule_pack_payload`, which parses an unsigned SOURCE
    file. This validates the envelope's own `payload` object directly.
    """

    _path, raw = select_highest_repository_pack(packs_dir)
    return RulePackPayload.model_validate(raw["payload"])


def pack_review_rules(pack: RulePackPayload) -> tuple[RuleReviewEntry, ...]:
    """Every rule with ``stage == HUMAN_REVIEW`` — PLAN §1.3(c)."""

    entries = tuple(
        RuleReviewEntry(
            rule_id=rule.rule_id,
            stage=rule.stage.value,
            scope=rule.scope.value,
            code=rule.effect.reason_code,
            on_unknown=rule.on_unknown.value,
        )
        for rule in pack.rules
        if rule.stage is RuleStage.HUMAN_REVIEW
    )
    if not entries:
        raise RuntimeError(
            f"sequence {pack.sequence}: zero HUMAN_REVIEW-stage rules found in the "
            "signed pack — either the pack changed shape or this script's stage "
            "filter drifted; a silent empty result would be the guard-under-match "
            "shape (cicatrix family #3)"
        )
    return entries


def pack_unknown_escalations(pack: RulePackPayload) -> tuple[RuleReviewEntry, ...]:
    """Every rule, of any stage, whose ``on_unknown`` is ``HUMAN_REVIEW`` —
    PLAN §1.3(d). Overlaps `pack_review_rules` on purpose: this is "which
    rules can turn UNKNOWN into a hold", a different question from that
    function's "which rules ARE a hold effect" — a rule can answer both."""

    return tuple(
        RuleReviewEntry(
            rule_id=rule.rule_id,
            stage=rule.stage.value,
            scope=rule.scope.value,
            code=rule.effect.reason_code,
            on_unknown=rule.on_unknown.value,
        )
        for rule in pack.rules
        if rule.on_unknown is OnUnknownAction.HUMAN_REVIEW
    )


def adapter_review_codes() -> dict[DisclosedReviewFlag, str]:
    """The 11 UI-disclosed flags' review codes, read from the production
    module itself — PLAN §1.3(a). Never a copy: importing the module's own
    mapping means a twelfth flag added there is visible here without this
    script being touched."""

    return dict(_DISCLOSED_REVIEW_REASON_CODES)


def minor_privacy_review_code() -> str:
    """The one engine-level hold with no pack rule at all — PLAN §1.3(b).
    Reads the module constant `_apply_minor_privacy_hold` emits (lifted out
    of that function's hard-coded string literal by this same PR) so this
    inventory cannot drift from the emitter."""

    return MINOR_GUARDIAN_PRIVACY_REVIEW_CODE


def orphan_review_gate_items(
    tree_ts_path: Path = DEFAULT_TREE_TS_PATH,
    fact_mapper_ts_path: Path = DEFAULT_FACT_MAPPER_PATH,
) -> frozenset[str]:
    """Items `tree.ts`'s `REVIEW_GATE_ITEMS` offers a visitor (minus "none")
    that `fact-mapper.ts`'s `REVIEW_FLAG_MAP` maps to no flag at all — a
    visitor who discloses one of these is never heard by the engine.

    `REVIEW_GATE_ITEMS`/`REVIEW_FLAG_MAP` are TypeScript, not importable
    from Python, so this reads the source text directly and regexes the two
    literal blocks. Fails loud if either cannot be found — a silent empty
    orphan set here would be indistinguishable from "no orphans exist" and
    is exactly the guard-under-match shape cicatrix family #3 names.
    """

    tree_text = tree_ts_path.read_text(encoding="utf-8")
    gate_match = _REVIEW_GATE_ITEMS_RE.search(tree_text)
    if gate_match is None:
        raise RuntimeError(
            f"REVIEW_GATE_ITEMS literal not found in {tree_ts_path} — the regex "
            "drifted from the source, not proof that the list is empty"
        )
    offered = {item for item in _QUOTED_ITEM_RE.findall(gate_match.group(1)) if item != "none"}

    mapper_text = fact_mapper_ts_path.read_text(encoding="utf-8")
    map_match = _REVIEW_FLAG_MAP_RE.search(mapper_text)
    if map_match is None:
        raise RuntimeError(
            f"REVIEW_FLAG_MAP literal not found in {fact_mapper_ts_path} — the "
            "regex drifted from the source, not proof that the map is empty"
        )
    mapped = set(_MAP_KEY_RE.findall(map_match.group(1)))

    return frozenset(offered - mapped)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Derive every HUMAN_REVIEW hold producer from the signed pack "
        "AST and the backend adapters (read-only; PR-O1 keystone)."
    )
    parser.add_argument("--json", action="store_true", help="emit JSON to stdout only")
    args = parser.parse_args(argv)

    pack = load_highest_signed_pack()
    review_rules = pack_review_rules(pack)
    escalations = pack_unknown_escalations(pack)
    disclosed_codes = adapter_review_codes()
    privacy_code = minor_privacy_review_code()
    orphans = orphan_review_gate_items()

    review_rule_ids = {entry.rule_id for entry in review_rules}
    extra_escalations = tuple(
        entry for entry in escalations if entry.rule_id not in review_rule_ids
    )
    total_distinct_hold_producers = (
        len(disclosed_codes) + 1 + len(review_rules) + len(extra_escalations)
    )

    rows: list[tuple[str, str, str, str, str]] = []
    for entry in review_rules:
        rows.append(("pack_review_rule", entry.rule_id, entry.code, entry.scope, entry.on_unknown))
    for entry in escalations:
        rows.append(
            ("pack_unknown_escalation", entry.rule_id, entry.code, entry.scope, entry.stage)
        )
    for flag, code in disclosed_codes.items():
        rows.append(("disclosed_review_flag", flag.value, code, "-", "-"))
    rows.append(
        ("engine_privacy_hold", "system.privacy.minor-guardian-review", privacy_code, "-", "-")
    )

    totals = {
        "pack_review_rules": len(review_rules),
        "pack_unknown_escalations": len(escalations),
        "disclosed_review_flags": len(disclosed_codes),
        "engine_privacy_holds": 1,
        "total_distinct_hold_producers": total_distinct_hold_producers,
    }

    if args.json:
        payload = {
            "sequence": pack.sequence,
            "producers": [
                {
                    "producer_kind": row[0],
                    "id": row[1],
                    "code": row[2],
                    "scope": row[3],
                    "on_unknown_or_stage": row[4],
                }
                for row in rows
            ],
            "totals": totals,
            "orphan_review_gate_items": sorted(orphans),
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"review_hold_inventory: highest signed pack sequence {pack.sequence}")
    print(f"{'producer_kind':<26}{'id':<44}{'code':<42}{'scope':<10}{'on_unknown/stage':<18}")
    for row in rows:
        print(f"{row[0]:<26}{row[1]:<44}{row[2]:<42}{row[3]:<10}{row[4]:<18}")
    print()
    for key, value in totals.items():
        print(f"{key}: {value}")
    print(f"orphan_review_gate_items: {sorted(orphans)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
