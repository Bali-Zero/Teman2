"""Fold seq-28: the organ re-stamp plus the ruled E33 content corrections.

The production path is deliberately two-stage and fail-closed:

1. ``fold_pack_generic.fold`` re-stamps the signed seq-27 anchor from the
   selected organ ledger;
2. that restamp, apart from identity fields, must equal the organ candidate;
3. four content paths are changed: E33E pricing, the E33E/E33F retirement-age
   scope, E33G annual-income eligibility, and one appended below-minimum rule.

This module never signs or activates anything.  Until a post-seq-27 organ
ledger exists, ``--dry-run-reuse-anchor-ledger`` may be used only with the
ledger that produced seq-27.  It re-proves that provenance from signed seq-26
before applying the content changes to the already-restamped seq-27 anchor.
The dry-run path never pretends that the old receipts are a new re-attestation.

Normal usage after the organ run::

    PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.fold_pack_seq28 \
      --ledger-dir ../../research/visa/<new-organ-ledger> \
      --organ-candidate /path/to/organ/rulepack-prod-028.source.json \
      --output backend/services/visa_engine/contracts/packs/rulepack-prod-028.source.json

Scratch rehearsal before that run::

    PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.fold_pack_seq28 \
      --ledger-dir ../../research/visa/2026-10-08-organ-reattest-seq27 \
      --dry-run-reuse-anchor-ledger --output /tmp/rulepack-prod-028.source.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from backend.scripts.visa_engine.compile_pack import compile_pack_source
from backend.scripts.visa_engine.fold_pack_generic import fold as generic_fold
from backend.scripts.visa_engine.fold_pack_seq24 import (
    _assert_candidate_review_inventory,
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact,
)
from backend.scripts.visa_engine.fold_pack_seq25 import PORTAL_AUTHORITY, load_ledger
from backend.services.visa_engine.bundle import StaticTrustStore, canonicalize_json
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload

SEQ27_PAYLOAD_SHA256 = (
    "a9098744e0cd8369fb4fe9ca5bef851705cf43dabb1c69398b63b36985cb42d0"  # pragma: allowlist secret
)
FOLD_VERSION = "2026.10.11"
# The 2026-10-11 organ run read at 18:00Z (latest evidence 18:00:29Z).  This fixed instant is
# after its expected short read window and before the later signing ceremony.
FOLD_CREATED_AT = "2026-10-11T18:05:00Z"
FOLD_CREATED_BY = "agent.mini-pro2.backend-rag.vo-seq28c-fold-1011"
NEW_RULE_VALID_FROM = "2026-10-11T00:00:00Z"

E33E_PRODUCT_VERSION_ID = "796d09bd-3220-5c91-a6ce-e3a99a9b0ddb"
E33G_PRODUCT_VERSION_ID = "51e023ea-3229-5233-b88f-cb204b5df713"
E33E_PRICE_ITEM_KEY = "E33E Second Home Senior (5 Years)"
OLD_E33E_PRICE_ITEM_KEY = "Retirement (Offshore)"
E33G_ANNUAL_INCOME_FACT = "work.annual_foreign_income_usd"
E33G_ANNUAL_INCOME_THRESHOLD_USD = 60_000

E33E_AGE_RULE_ID = "hf.e33e.age-below-55"
E33F_AGE_RULE_ID = "hf.e33f.age-below-55"
E33G_ELIGIBILITY_RULE_ID = "el.e33g.remote-work"
E33G_INCOME_FILTER_RULE_ID = "hf.e33g.annual-income-below-minimum"
MODIFIED_RULE_IDS = frozenset({E33E_AGE_RULE_ID, E33F_AGE_RULE_ID, E33G_ELIGIBILITY_RULE_ID})
INSERTED_RULE_IDS = frozenset({E33G_INCOME_FILTER_RULE_ID})

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)
_IDENTITY_KEYS = frozenset(
    {
        "sequence",
        "version",
        "rule_pack_id",
        "created_at",
        "created_by",
        "previous_payload_sha256",
        "rollback_of_payload_sha256",
    }
)
_PORTAL_STAMP_FIELDS = frozenset({"verified_at", "verified_by"})
_REPO_ROOT = Path(__file__).resolve().parents[5]
_PACKS = _REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
_RESEARCH = _REPO_ROOT / "research/visa"
_CATALOGUE = _REPO_ROOT / "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json"


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"fold_pack_seq28: {message}")


def _canon(value: Any) -> bytes:
    return canonicalize_json(value)


def _rule_pack_id(sequence: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_RULE_PACK_ID_URL_PREFIX}{sequence}")


def _rules_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rule["rule_id"]: rule for rule in payload["rules"]}


def _products_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {product["product_version_id"]: product for product in payload["products"]}


def _fact_paths(node: Any) -> list[str]:
    facts: set[str] = set()
    if isinstance(node, dict):
        if isinstance(node.get("fact"), str):
            facts.add(node["fact"])
        for value in node.values():
            facts.update(_fact_paths(value))
    elif isinstance(node, list):
        for value in node:
            facts.update(_fact_paths(value))
    return sorted(facts)


def _without_identity(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in _IDENTITY_KEYS}


def _catalogue_rows(catalogue: dict[str, Any]) -> dict[str, Any]:
    try:
        rows = catalogue["services"]["kitas_permits"]
    except (KeyError, TypeError):
        _fail("pricing catalogue has no services.kitas_permits object")
    if not isinstance(rows, dict):
        _fail("pricing catalogue services.kitas_permits is not an object")
    return rows


def assert_catalogue_preconditions(catalogue: dict[str, Any]) -> None:
    rows = _catalogue_rows(catalogue)
    senior = rows.get(E33E_PRICE_ITEM_KEY)
    if not isinstance(senior, dict):
        _fail(f"pricing row {E33E_PRICE_ITEM_KEY!r} does not exist")
    if senior.get("price") != "18.000.000 IDR" or senior.get("validity") != "5 years":
        _fail(
            f"pricing row {E33E_PRICE_ITEM_KEY!r} is not 18.000.000 IDR / 5 years: "
            f"{senior.get('price')!r} / {senior.get('validity')!r}"
        )
    if OLD_E33E_PRICE_ITEM_KEY not in rows:
        _fail(f"pricing row {OLD_E33E_PRICE_ITEM_KEY!r} disappeared")


def build_scoped_age_rule(rule: dict[str, Any]) -> dict[str, Any]:
    rule_id = str(rule.get("rule_id"))
    if rule_id not in {E33E_AGE_RULE_ID, E33F_AGE_RULE_ID}:
        _fail(f"{rule_id!r} is not one of the two age rules")
    if rule.get("when") != {"op": "lt", "fact": "derived.age_years", "value": 55}:
        _fail(f"{rule_id!r} no longer has the seq-27 age-only predicate")
    if rule.get("required_facts") != ["derived.age_years"]:
        _fail(f"{rule_id!r} no longer has the seq-27 required_facts")
    if rule.get("on_unknown") != "NEEDS_INPUT":
        _fail(f"{rule_id!r} on_unknown is not NEEDS_INPUT")

    out = copy.deepcopy(rule)
    out["when"] = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["RETIREMENT"]},
            {"op": "lt", "fact": "derived.age_years", "value": 55},
        ],
    }
    out["required_facts"] = ["derived.age_years", "intent.purposes"]
    return out


def build_e33g_eligibility_rule(rule: dict[str, Any]) -> dict[str, Any]:
    if rule.get("rule_id") != E33G_ELIGIBILITY_RULE_ID:
        _fail(f"expected {E33G_ELIGIBILITY_RULE_ID!r}, got {rule.get('rule_id')!r}")
    when = rule.get("when")
    if (
        not isinstance(when, dict)
        or when.get("op") != "all"
        or not isinstance(when.get("args"), list)
    ):
        _fail(f"{E33G_ELIGIBILITY_RULE_ID!r} is not a top-level all")
    if any(
        node.get("fact") == E33G_ANNUAL_INCOME_FACT
        for node in when["args"]
        if isinstance(node, dict)
    ):
        _fail(f"{E33G_ELIGIBILITY_RULE_ID!r} already reads annual foreign income")
    if rule.get("on_unknown") != "NEEDS_INPUT":
        _fail(f"{E33G_ELIGIBILITY_RULE_ID!r} on_unknown is not NEEDS_INPUT")

    out = copy.deepcopy(rule)
    out["when"]["args"].append(
        {
            "op": "gte",
            "fact": E33G_ANNUAL_INCOME_FACT,
            "value": E33G_ANNUAL_INCOME_THRESHOLD_USD,
        }
    )
    out["required_facts"] = _fact_paths(out["when"])
    return out


def build_e33g_income_filter() -> dict[str, Any]:
    return {
        "rule_id": E33G_INCOME_FILTER_RULE_ID,
        "stage": "HARD_FILTER",
        "scope": "PRODUCTS",
        "product_version_ids": [E33G_PRODUCT_VERSION_ID],
        "when": {
            "op": "all",
            "args": [
                {
                    "op": "intersects",
                    "fact": "intent.purposes",
                    "values": ["REMOTE_WORK"],
                },
                {
                    "op": "lt",
                    "fact": E33G_ANNUAL_INCOME_FACT,
                    "value": E33G_ANNUAL_INCOME_THRESHOLD_USD,
                },
            ],
        },
        "effect": {"type": "EXCLUDE", "reason_code": "E33G_INCOME_BELOW_THRESHOLD"},
        "on_unknown": "NO_EFFECT",
        "priority": 100,
        "required_facts": ["intent.purposes", E33G_ANNUAL_INCOME_FACT],
        "source_refs": [
            "6f5135f2-1f77-571f-88ed-26d1d2b9efba",
            "9248b1d7-9172-54d9-ad61-251e83a2285b",
        ],
        "valid_period": {"from": NEW_RULE_VALID_FROM, "to": None},
        "explanation_key": "explain.hf.e33g.annual-income-below-minimum",
        "safety_critical": False,
    }


def _assert_required_facts(rule: dict[str, Any]) -> None:
    expected = _fact_paths(rule["when"])
    if rule.get("required_facts") != expected:
        _fail(
            f"{rule['rule_id']}: required_facts {rule.get('required_facts')!r} "
            f"!= condition facts {expected!r}"
        )


def _assert_retirement_support_witnesses(payload: dict[str, Any]) -> None:
    def requires_retirement(node: Any) -> bool:
        if not isinstance(node, dict):
            return False
        if node == {
            "op": "intersects",
            "fact": "intent.purposes",
            "values": ["RETIREMENT"],
        }:
            return True
        args = node.get("args")
        if not isinstance(args, list) or not args:
            return False
        if node.get("op") == "all":
            return any(requires_retirement(arg) for arg in args)
        if node.get("op") == "any":
            return all(requires_retirement(arg) for arg in args)
        return False

    products = {E33E_PRODUCT_VERSION_ID, "7c1da88f-f7cd-571a-95c2-7da32463d3e6"}
    witnesses = 0
    for rule in payload["rules"]:
        if rule.get("stage") != "ELIGIBILITY" or rule.get("effect", {}).get("type") != "SUPPORT":
            continue
        if not products.intersection(rule.get("product_version_ids") or []):
            continue
        witnesses += 1
        when = rule.get("when")
        if not isinstance(when, dict) or when.get("op") != "all" or not requires_retirement(when):
            _fail(f"{rule['rule_id']}: E33E/E33F SUPPORT no longer requires RETIREMENT")
    if witnesses == 0:
        _fail("no E33E/E33F SUPPORT rule was inspected")


def assert_only_expected_changes(restamped: dict[str, Any], out: dict[str, Any]) -> None:
    if set(restamped) != set(out):
        _fail("top-level key set changed")
    for key in set(restamped) - _IDENTITY_KEYS - {"products", "rules"}:
        if _canon(restamped[key]) != _canon(out[key]):
            _fail(f"{key} changed; source_records and all other content must be byte-identical")

    before_products = _products_by_id(restamped)
    after_products = _products_by_id(out)
    if set(before_products) != set(after_products):
        _fail("product set changed")
    for product_id, before in before_products.items():
        after = after_products[product_id]
        if product_id == E33E_PRODUCT_VERSION_ID:
            expected = copy.deepcopy(before)
            if expected.get("pricing_key") != {
                "category": "kitas_permits",
                "item_key": OLD_E33E_PRICE_ITEM_KEY,
            }:
                _fail("E33E's donor pricing_key is not the seq-27 Retirement (Offshore) row")
            if "duration_options" in expected:
                _fail("E33E unexpectedly has duration_options; do not wire the Extend row")
            expected["pricing_key"]["item_key"] = E33E_PRICE_ITEM_KEY
            if _canon(after) != _canon(expected):
                _fail("E33E changed outside pricing_key.item_key")
        elif _canon(before) != _canon(after):
            _fail(f"product {before.get('product_code')} changed unexpectedly")

    before_rules = _rules_by_id(restamped)
    after_rules = _rules_by_id(out)
    if set(before_rules) - set(after_rules):
        _fail(f"rules were removed: {sorted(set(before_rules) - set(after_rules))}")
    if set(after_rules) - set(before_rules) != INSERTED_RULE_IDS:
        _fail(f"inserted rules are {sorted(set(after_rules) - set(before_rules))}")
    expected_builders = {
        E33E_AGE_RULE_ID: build_scoped_age_rule,
        E33F_AGE_RULE_ID: build_scoped_age_rule,
        E33G_ELIGIBILITY_RULE_ID: build_e33g_eligibility_rule,
    }
    for rule_id, before in before_rules.items():
        after = after_rules[rule_id]
        if rule_id in expected_builders:
            if _canon(after) != _canon(expected_builders[rule_id](before)):
                _fail(f"{rule_id} differs from its builder output")
        elif _canon(before) != _canon(after):
            _fail(f"rule {rule_id} changed unexpectedly")
    if _canon(after_rules[E33G_INCOME_FILTER_RULE_ID]) != _canon(build_e33g_income_filter()):
        _fail(f"{E33G_INCOME_FILTER_RULE_ID} differs from its builder output")
    before_order = [rule["rule_id"] for rule in restamped["rules"]]
    after_order = [rule["rule_id"] for rule in out["rules"]]
    if after_order[:-1] != before_order or after_order[-1] != E33G_INCOME_FILTER_RULE_ID:
        _fail("surviving rule order changed or the new rule is not last")


def assert_anchor_relative_changes(anchor: dict[str, Any], out: dict[str, Any]) -> None:
    if set(anchor) != set(out):
        _fail("anchor-relative top-level key set changed")
    for key in set(anchor) - _IDENTITY_KEYS - {"source_records", "products", "rules"}:
        if _canon(anchor[key]) != _canon(out[key]):
            _fail(f"anchor-relative unexpected top-level change in {key}")

    before_sources = {r["source_record_id"]: r for r in anchor["source_records"]}
    after_sources = {r["source_record_id"]: r for r in out["source_records"]}
    if set(before_sources) != set(after_sources):
        _fail("anchor-relative source-record set changed")
    moved_portals = 0
    for record_id, before in before_sources.items():
        after = after_sources[record_id]
        changed = {key for key in before if before[key] != after[key]}
        if before.get("authority_type") == PORTAL_AUTHORITY:
            if changed:
                moved_portals += 1
            if not changed.issubset(_PORTAL_STAMP_FIELDS):
                _fail(f"portal record {record_id[:8]} changed outside its stamp: {sorted(changed)}")
        elif changed:
            _fail(f"non-portal record {record_id[:8]} changed")
    if moved_portals not in {0, 18}:
        _fail(f"anchor-relative portal movement is partial ({moved_portals}/18)")

    # Content-specific guards prove the remaining two surfaces.
    restamped_shape = copy.deepcopy(anchor)
    restamped_shape["source_records"] = copy.deepcopy(out["source_records"])
    for key in _IDENTITY_KEYS:
        restamped_shape[key] = out[key]
    assert_only_expected_changes(restamped_shape, out)


def _assert_compile_gate(out: dict[str, Any]) -> None:
    with tempfile.TemporaryDirectory(prefix="seq28-compile-") as temp_dir:
        path = Path(temp_dir) / "rulepack-prod-028.source.json"
        path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        _, report = compile_pack_source(
            path,
            observed_at=datetime.fromisoformat(FOLD_CREATED_AT.replace("Z", "+00:00")),
        )
    if not report.ok:
        detail = "; ".join(f"{error.code}:{error.message}" for error in report.errors)
        _fail(f"compile_pack gate failed: {detail}")


def apply_content_edits(restamped: dict[str, Any], catalogue: dict[str, Any]) -> dict[str, Any]:
    if restamped.get("sequence") != 28:
        _fail(f"restamped base carries sequence {restamped.get('sequence')!r}, expected 28")
    assert_catalogue_preconditions(catalogue)
    out = copy.deepcopy(restamped)

    product = _products_by_id(out).get(E33E_PRODUCT_VERSION_ID)
    if product is None:
        _fail("E33E product is absent")
    product["pricing_key"]["item_key"] = E33E_PRICE_ITEM_KEY

    rules = _rules_by_id(out)
    for rule_id in MODIFIED_RULE_IDS:
        if rule_id not in rules:
            _fail(f"rule {rule_id!r} is absent")
    replacements = {
        E33E_AGE_RULE_ID: build_scoped_age_rule(rules[E33E_AGE_RULE_ID]),
        E33F_AGE_RULE_ID: build_scoped_age_rule(rules[E33F_AGE_RULE_ID]),
        E33G_ELIGIBILITY_RULE_ID: build_e33g_eligibility_rule(rules[E33G_ELIGIBILITY_RULE_ID]),
    }
    out["rules"] = [replacements.get(rule["rule_id"], rule) for rule in out["rules"]]
    out["rules"].append(build_e33g_income_filter())

    out["sequence"] = 28
    out["rule_pack_id"] = str(_rule_pack_id(28))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ27_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(restamped, out)
    for rule_id in (*sorted(MODIFIED_RULE_IDS), E33G_INCOME_FILTER_RULE_ID):
        _assert_required_facts(_rules_by_id(out)[rule_id])
    _assert_candidate_review_inventory(out)
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(out)
    _assert_retirement_support_witnesses(out)
    RulePackPayload.model_validate(out)
    _assert_compile_gate(out)
    return out


def _portal_verified_by(candidate: dict[str, Any]) -> str:
    readers = {
        str(record.get("verified_by"))
        for record in candidate["source_records"]
        if record.get("authority_type") == PORTAL_AUTHORITY
    }
    if len(readers) != 1 or None in readers:
        _fail(f"organ candidate portal verified_by values disagree: {sorted(readers)}")
    return next(iter(readers))


def fold(
    anchor: dict[str, Any],
    anchor_signed: dict[str, Any],
    ledger_dir: Path,
    organ_candidate: dict[str, Any],
    catalogue: dict[str, Any],
    *,
    trust_store: StaticTrustStore,
    baseline_root: Path,
    observed_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if anchor.get("sequence") != 27:
        _fail(f"anchor carries sequence {anchor.get('sequence')!r}, expected 27")
    if hashlib.sha256(_canon(anchor)).hexdigest() != SEQ27_PAYLOAD_SHA256:
        _fail("anchor source is not the pinned signed seq-27 payload")
    if organ_candidate.get("sequence") != 28:
        _fail("organ candidate is not sequence 28")

    restamped = generic_fold(
        anchor,
        anchor_signed,
        load_ledger(ledger_dir),
        trust_store=trust_store,
        version=FOLD_VERSION,
        created_at=FOLD_CREATED_AT,
        created_by=FOLD_CREATED_BY,
        verified_by=_portal_verified_by(organ_candidate),
        observed_at=observed_at,
        baseline_root=baseline_root,
        ledger_dir=ledger_dir,
    )
    if _canon(_without_identity(restamped)) != _canon(_without_identity(organ_candidate)):
        _fail(
            "generic restamp does not equal the organ candidate after identity fields are removed"
        )
    out = apply_content_edits(restamped, catalogue)
    assert_anchor_relative_changes(anchor, out)
    return restamped, out


def dry_run_from_anchor_ledger(
    anchor: dict[str, Any],
    anchor_signed: dict[str, Any],
    ledger_dir: Path,
    catalogue: dict[str, Any],
    *,
    trust_store: StaticTrustStore,
    baseline_root: Path,
    previous_source: dict[str, Any],
    previous_signed: dict[str, Any],
    observed_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rehearsal only: prove ``ledger -> seq27`` from seq26, then edit seq27.

    The returned restamped base has seq-28 identity solely so the content
    builder can exercise the real seq-28 guards.  Its source records are the
    already-attested seq-27 records; no receipt is presented as newer.
    """

    reproduced = generic_fold(
        previous_source,
        previous_signed,
        load_ledger(ledger_dir),
        trust_store=trust_store,
        version=str(anchor["version"]),
        created_at=str(anchor["created_at"]),
        created_by=str(anchor["created_by"]),
        verified_by=_portal_verified_by(anchor),
        observed_at=observed_at,
        baseline_root=baseline_root,
        ledger_dir=ledger_dir,
    )
    if _canon(reproduced) != _canon(anchor):
        _fail("dry-run ledger does not reproduce the signed seq-27 anchor from seq-26")

    restamped = copy.deepcopy(anchor)
    restamped.update(
        {
            "sequence": 28,
            "rule_pack_id": str(_rule_pack_id(28)),
            "version": FOLD_VERSION,
            "created_at": FOLD_CREATED_AT,
            "created_by": FOLD_CREATED_BY,
            "previous_payload_sha256": SEQ27_PAYLOAD_SHA256,
            "rollback_of_payload_sha256": None,
        }
    )
    out = apply_content_edits(restamped, catalogue)
    assert_anchor_relative_changes(anchor, out)
    return restamped, out


def discover_newest_ledger(baseline_root: Path) -> Path:
    candidates: list[tuple[str, Path]] = []
    for path in baseline_root.iterdir():
        if not path.is_dir() or not list(path.glob("*-receipts.jsonl")):
            continue
        ledger = load_ledger(path)
        fetched = [str(row.get("fetched_at")) for row in ledger.receipts if row.get("fetched_at")]
        if fetched:
            candidates.append((max(fetched), path))
    if not candidates:
        _fail(f"no organ ledger with receipts under {baseline_root}")
    return max(candidates, key=lambda item: item[0])[1]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"cannot read {path}: {exc}")
    if not isinstance(value, dict):
        _fail(f"{path} is not a JSON object")
    return value


def _assert_output_path(output: Path, inputs: list[Path]) -> None:
    if output.name.endswith(".signed.json"):
        _fail("refusing to write unsigned bytes to a .signed.json path")
    if output.resolve() in {path.resolve() for path in inputs}:
        _fail("--output resolves to an input path")


def main(argv: list[str] | None = None, *, observed_at: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--anchor-source", type=Path, default=_PACKS / "rulepack-prod-027.source.json"
    )
    parser.add_argument(
        "--anchor-signed", type=Path, default=_PACKS / "rulepack-prod-027.signed.json"
    )
    parser.add_argument("--ledger-dir", type=Path, default=None)
    parser.add_argument("--organ-candidate", type=Path, default=None)
    parser.add_argument("--baseline-root", type=Path, default=_RESEARCH)
    parser.add_argument("--catalogue", type=Path, default=_CATALOGUE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--dry-run-reuse-anchor-ledger",
        action="store_true",
        help="rehearsal only: prove the selected ledger produced seq-27, then apply content edits",
    )
    args = parser.parse_args(argv)

    ledger_dir = args.ledger_dir or discover_newest_ledger(args.baseline_root)
    candidate_path = args.organ_candidate or ledger_dir / "rulepack-prod-028.source.json"
    inputs = [args.anchor_source, args.anchor_signed, ledger_dir, args.catalogue]
    if candidate_path.exists():
        inputs.append(candidate_path)
    _assert_output_path(args.output, inputs)

    try:
        trust_store = StaticTrustStore.from_env()
    except RulePackVerificationError as exc:
        _fail(f"cannot load production trust store: {exc}")
    anchor = _read_json(args.anchor_source)
    anchor_signed = _read_json(args.anchor_signed)
    catalogue = _read_json(args.catalogue)

    if args.dry_run_reuse_anchor_ledger:
        if candidate_path.exists():
            _fail("dry-run replay is forbidden when a real organ seq-28 candidate exists")
        now = observed_at or datetime.now(timezone.utc)
        previous_source_path = _PACKS / "rulepack-prod-026.source.json"
        previous_signed_path = _PACKS / "rulepack-prod-026.signed.json"
        _, out = dry_run_from_anchor_ledger(
            anchor,
            anchor_signed,
            ledger_dir,
            catalogue,
            trust_store=trust_store,
            baseline_root=args.baseline_root,
            previous_source=_read_json(previous_source_path),
            previous_signed=_read_json(previous_signed_path),
            observed_at=now,
        )
        mode = "DRY RUN: reused only the ledger proven to have produced seq-27"
    else:
        if not candidate_path.exists():
            _fail(
                f"no organ candidate at {candidate_path}; wait for the new organ run or use "
                "--dry-run-reuse-anchor-ledger with a scratch output"
            )
        _, out = fold(
            anchor,
            anchor_signed,
            ledger_dir,
            _read_json(candidate_path),
            catalogue,
            trust_store=trust_store,
            baseline_root=args.baseline_root,
            observed_at=observed_at,
        )
        mode = "REAL ORGAN RESTAMP"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(_canon(out)).hexdigest()
    print(f"fold_pack_seq28: mode = {mode}")
    print(f"fold_pack_seq28: ledger = {ledger_dir}")
    print(f"fold_pack_seq28: wrote {args.output}")
    print(f"fold_pack_seq28: seq-28 payload_sha256 = {digest}")
    print(f"fold_pack_seq28: modified rules = {sorted(MODIFIED_RULE_IDS)}")
    print(f"fold_pack_seq28: inserted rules = {sorted(INSERTED_RULE_IDS)}")
    print("fold_pack_seq28: NOT SIGNED, NOT ACTIVATED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
