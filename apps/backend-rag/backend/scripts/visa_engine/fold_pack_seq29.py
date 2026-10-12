"""Fold seq-29: the organ re-stamp of signed seq-28 plus four decision-free corrections.

Chained on the signed seq-28 anchor (payload ``a23a5bf5...``).  The content, in order of
client impact: three wrong admissions (E31J adults and married applicants, E31D under a
non-Indonesian step-parent, E28F without a foreign parent company) and one wrong reason (the
E31E age and marital exclusions fired on every family relation).  The A1 conversion gate and
the E30A/E30B multi-year options moved to seq-30 when the slice outgrew ~400 net lines.
No product moves.  No E33 rule, no E33 copy and no non-portal source record moves.

The production path is fail-closed and two-stage, as in seq-28:

1. ``fold_pack_generic.fold`` re-stamps signed seq-28 from the newest organ ledger;
2. that restamp, apart from identity fields, must equal the organ candidate;
3. the content edits are applied by one builder per item, each refusing unless it finds the
   seq-28 shape, and the result is compared against the builders again.

The organ run that follows seq-28 has not happened when this module is written, so the
committed source is the ``--dry-run-reuse-anchor-ledger`` output: it re-proves that the
2026-10-11 ledger produced signed seq-28 from signed seq-27, keeps the seq-28 portal stamps
unchanged and applies the content edits.  The dry-run never presents old receipts as a new
re-attestation.  At hand-off the same module runs in REAL mode on the newest organ ledger.
This module never signs or activates anything.

REAL, after the organ run::

    PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.fold_pack_seq29 \
      --ledger-dir ../../research/visa/<new-organ-ledger> \
      --organ-candidate <organ>/rulepack-prod-029.source.json --created-at <after last read> \
      --output backend/services/visa_engine/contracts/packs/rulepack-prod-029.source.json

Rehearsal::

    PYTHONPATH=. .venv/bin/python -m backend.scripts.visa_engine.fold_pack_seq29 \
      --ledger-dir ../../research/visa/2026-10-11-organ-reattest-seq28 \
      --dry-run-reuse-anchor-ledger \
      --output backend/services/visa_engine/contracts/packs/rulepack-prod-029.source.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from backend.scripts.visa_engine import fold_pack_seq28 as seq28
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

SEQ28_PAYLOAD_SHA256 = (
    "a23a5bf55a77a658aef4ff06637cdb6fea476c5569d3d47a56896af2b8557046"  # pragma: allowlist secret
)
FOLD_VERSION = "2026.10.12"
# Rehearsal identity: after the 2026-10-11 ledger's last read (18:00:29Z) and before the
# build.  REAL mode passes ``--created-at`` after the new ledger's last read instead.
FOLD_CREATED_AT = "2026-10-12T07:30:00Z"
FOLD_CREATED_BY = "agent.nuzantara.backend-rag.vo-seq29-fold-1012"
NEW_RULE_VALID_FROM = "2026-10-12T00:00:00Z"

E28F_PRODUCT_VERSION_ID = "2df6f723-7fc3-585a-b26f-0e8c060a2d8d"
E31D_PRODUCT_VERSION_ID = "3204e973-59da-5da1-bad0-06a7172e5b2c"
E31E_PRODUCT_VERSION_ID = "1266d5cb-84a3-51f7-b82d-c6b756254074"
E31J_PRODUCT_VERSION_ID = "4a4a0f7c-a6a0-5835-acd6-8a096342ef68"

SRC_E31D_PORTAL = "50457cd0-b67f-5b88-bf66-33bcf62f3d9b"
SRC_E31J_PORTAL = "2d090f3a-5a93-5181-b3d1-253d87a1a17c"
SRC_KEPMEN_LAMPIRAN = "e3572ad2-08a9-55bd-b818-353b3e9db715"

E31D_RULE_ID = "hf.e31d-sponsor-not-indonesian"
E31J_ADULT_RULE_ID = "hf.e31j-adult-excluded"
E31J_MARRIED_RULE_ID = "hf.e31j-married-excluded"
E31J_RETIRED_RULE_ID = "el.e31j-dependency-age"
E28F_RULE_ID = "el.e28f.ikn-subsidiary"
E31E_ADULT_RULE_ID = "hf.e31e-adult-excluded"
E31E_MARRIED_RULE_ID = "hf.e31e-married-excluded"
MODIFIED_RULE_IDS = frozenset({E28F_RULE_ID, E31E_ADULT_RULE_ID, E31E_MARRIED_RULE_ID})
INSERTED_RULE_IDS_IN_ORDER = (E31D_RULE_ID, E31J_ADULT_RULE_ID, E31J_MARRIED_RULE_ID)
INSERTED_RULE_IDS = frozenset(INSERTED_RULE_IDS_IN_ORDER)
RETIRED_RULE_IDS = frozenset({E31J_RETIRED_RULE_ID})

_FAMILY = {"op": "intersects", "fact": "intent.purposes", "values": ["FAMILY"]}
_IDENTITY_KEYS = seq28._IDENTITY_KEYS
_PORTAL_STAMP_FIELDS = seq28._PORTAL_STAMP_FIELDS
_PACKS = seq28._PACKS
_RESEARCH = seq28._RESEARCH
_CATALOGUE = seq28._CATALOGUE
_canon = seq28._canon
_rules_by_id = seq28._rules_by_id
_products_by_id = seq28._products_by_id
_fact_paths = seq28._fact_paths
_without_identity = seq28._without_identity


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"fold_pack_seq29: {message}")


def _relation(value: str) -> dict[str, Any]:
    return {"op": "eq", "fact": "family.relation_to_sponsor", "value": value}


# --- item builders -----------------------------------------------------------------------


def build_e28f_rule(rule: dict[str, Any]) -> dict[str, Any]:
    if rule.get("rule_id") != E28F_RULE_ID:
        _fail(f"expected {E28F_RULE_ID!r}, got {rule.get('rule_id')!r}")
    if rule.get("when") != {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["INVESTMENT"]},
            {"op": "eq", "fact": "investment.ikn_subsidiary", "value": True},
            {"op": "eq", "fact": "investment.meets_published_threshold", "value": True},
        ],
    }:
        _fail(f"{E28F_RULE_ID!r} no longer has the seq-28 three-argument shape")
    out = copy.deepcopy(rule)
    out["when"]["args"].append(
        {"op": "eq", "fact": "investment.foreign_branch_or_subsidiary", "value": True}
    )
    out["required_facts"] = _fact_paths(out["when"])
    return out


def build_scoped_e31e_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Scope an E31E hard filter to the PARENT relation, as the E31C filters already are."""

    rule_id = str(rule.get("rule_id"))
    seq28_when = {
        E31E_ADULT_RULE_ID: {"op": "gte", "fact": "derived.age_years", "value": 18},
        E31E_MARRIED_RULE_ID: {"op": "neq", "fact": "person.marital_status", "value": "SINGLE"},
    }.get(rule_id)
    if seq28_when is None:
        _fail(f"{rule_id!r} is not one of the two E31E filters")
    if rule.get("when") != seq28_when:
        _fail(f"{rule_id!r} no longer has the seq-28 single-predicate shape")
    if rule.get("on_unknown") != "NEEDS_INPUT":
        _fail(f"{rule_id!r} on_unknown is not NEEDS_INPUT")
    out = copy.deepcopy(rule)
    out["when"] = {"op": "all", "args": [dict(_FAMILY), _relation("PARENT"), seq28_when]}
    out["required_facts"] = _fact_paths(out["when"])
    return out


def _hard_filter(
    rule_id: str,
    product_version_id: str,
    when: dict[str, Any],
    reason_code: str,
    *,
    on_unknown: str,
    source_refs: list[str],
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "stage": "HARD_FILTER",
        "scope": "PRODUCTS",
        "product_version_ids": [product_version_id],
        "when": when,
        "effect": {"type": "EXCLUDE", "reason_code": reason_code},
        "on_unknown": on_unknown,
        "priority": 100,
        "required_facts": _fact_paths(when),
        "source_refs": source_refs,
        "valid_period": {"from": NEW_RULE_VALID_FROM, "to": None},
        "explanation_key": f"explain.{rule_id}",
        "safety_critical": True,
    }


def build_e31d_rule() -> dict[str, Any]:
    return _hard_filter(
        E31D_RULE_ID,
        E31D_PRODUCT_VERSION_ID,
        {
            "op": "all",
            "args": [
                dict(_FAMILY),
                _relation("STEPCHILD"),
                {
                    "op": "not",
                    "arg": {
                        "op": "intersects",
                        "fact": "family.sponsor_nationalities",
                        "values": ["ID"],
                    },
                },
            ],
        },
        "E31D_REQ_SPONSOR_INDONESIAN",
        on_unknown="NEEDS_INPUT",
        source_refs=[SRC_E31D_PORTAL, SRC_KEPMEN_LAMPIRAN],
    )


def build_e31j_adult_rule() -> dict[str, Any]:
    return _hard_filter(
        E31J_ADULT_RULE_ID,
        E31J_PRODUCT_VERSION_ID,
        {
            "op": "all",
            "args": [
                dict(_FAMILY),
                _relation("SIBLING"),
                {"op": "gte", "fact": "derived.age_years", "value": 18},
            ],
        },
        "E31J_REQ_UNDER_18",
        on_unknown="NEEDS_INPUT",
        source_refs=[SRC_E31J_PORTAL, SRC_KEPMEN_LAMPIRAN],
    )


def build_e31j_married_rule() -> dict[str, Any]:
    return _hard_filter(
        E31J_MARRIED_RULE_ID,
        E31J_PRODUCT_VERSION_ID,
        {
            "op": "all",
            "args": [
                dict(_FAMILY),
                _relation("SIBLING"),
                {"op": "neq", "fact": "person.marital_status", "value": "SINGLE"},
            ],
        },
        "E31J_REQ_UNMARRIED",
        on_unknown="NEEDS_INPUT",
        source_refs=[SRC_E31J_PORTAL, SRC_KEPMEN_LAMPIRAN],
    )


_INSERTED_BUILDERS = {
    E31D_RULE_ID: build_e31d_rule,
    E31J_ADULT_RULE_ID: build_e31j_adult_rule,
    E31J_MARRIED_RULE_ID: build_e31j_married_rule,
}
_MODIFIED_BUILDERS = {
    E28F_RULE_ID: build_e28f_rule,
    E31E_ADULT_RULE_ID: build_scoped_e31e_rule,
    E31E_MARRIED_RULE_ID: build_scoped_e31e_rule,
}


def _assert_required_facts(rule: dict[str, Any]) -> None:
    expected = _fact_paths(rule["when"])
    if rule.get("required_facts") != expected:
        _fail(
            f"{rule['rule_id']}: required_facts {rule.get('required_facts')!r} "
            f"!= condition facts {expected!r}"
        )


# --- guards ------------------------------------------------------------------------------


def assert_only_expected_changes(restamped: dict[str, Any], out: dict[str, Any]) -> None:
    """The seq-28 restamp may differ from the candidate in exactly the seven content paths."""

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
        if _canon(before) != _canon(after_products[product_id]):
            _fail(f"product {before.get('product_code')} changed unexpectedly")

    before_rules = _rules_by_id(restamped)
    after_rules = _rules_by_id(out)
    if set(before_rules) - set(after_rules) != RETIRED_RULE_IDS:
        _fail(f"retired rules are {sorted(set(before_rules) - set(after_rules))}")
    if set(after_rules) - set(before_rules) != INSERTED_RULE_IDS:
        _fail(f"inserted rules are {sorted(set(after_rules) - set(before_rules))}")
    for rule_id, after in after_rules.items():
        if rule_id in INSERTED_RULE_IDS:
            if _canon(after) != _canon(_INSERTED_BUILDERS[rule_id]()):
                _fail(f"{rule_id} differs from its builder output")
        elif rule_id in MODIFIED_RULE_IDS:
            if _canon(after) != _canon(_MODIFIED_BUILDERS[rule_id](before_rules[rule_id])):
                _fail(f"{rule_id} differs from its builder output")
        elif _canon(before_rules[rule_id]) != _canon(after):
            _fail(f"rule {rule_id} changed unexpectedly")
    surviving = [r["rule_id"] for r in restamped["rules"] if r["rule_id"] not in RETIRED_RULE_IDS]
    after_order = [r["rule_id"] for r in out["rules"]]
    if after_order != [*surviving, *INSERTED_RULE_IDS_IN_ORDER]:
        _fail("surviving rule order changed or the new rules are not last, in the fixed order")


def assert_anchor_relative_changes(anchor: dict[str, Any], out: dict[str, Any]) -> None:
    """Against signed seq-28: portals move their stamp (all 18) or not at all; the rest is exact."""

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
    restamped_shape = copy.deepcopy(anchor)
    restamped_shape["source_records"] = copy.deepcopy(out["source_records"])
    for key in _IDENTITY_KEYS:
        restamped_shape[key] = out[key]
    assert_only_expected_changes(restamped_shape, out)


def _assert_compile_gate(out: dict[str, Any], created_at: str) -> None:
    with tempfile.TemporaryDirectory(prefix="seq29-compile-") as temp_dir:
        path = Path(temp_dir) / "rulepack-prod-029.source.json"
        path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        _, report = compile_pack_source(
            path, observed_at=datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        )
    if not report.ok:
        detail = "; ".join(f"{error.code}:{error.message}" for error in report.errors)
        _fail(f"compile_pack gate failed: {detail}")


# --- the fold ----------------------------------------------------------------------------


def apply_content_edits(
    restamped: dict[str, Any], *, created_at: str = FOLD_CREATED_AT
) -> dict[str, Any]:
    if restamped.get("sequence") != 29:
        _fail(f"restamped base carries sequence {restamped.get('sequence')!r}, expected 29")
    out = copy.deepcopy(restamped)

    rules = _rules_by_id(out)
    for rule_id in MODIFIED_RULE_IDS | RETIRED_RULE_IDS:
        if rule_id not in rules:
            _fail(f"rule {rule_id!r} is absent")
    for rule_id in INSERTED_RULE_IDS:
        if rule_id in rules:
            _fail(f"rule {rule_id!r} already exists")
    out["rules"] = [
        _MODIFIED_BUILDERS[rule["rule_id"]](rule) if rule["rule_id"] in MODIFIED_RULE_IDS else rule
        for rule in out["rules"]
        if rule["rule_id"] not in RETIRED_RULE_IDS
    ]
    out["rules"].extend(_INSERTED_BUILDERS[rule_id]() for rule_id in INSERTED_RULE_IDS_IN_ORDER)

    assert_only_expected_changes(restamped, out)
    for rule_id in (*sorted(MODIFIED_RULE_IDS), *INSERTED_RULE_IDS_IN_ORDER):
        _assert_required_facts(_rules_by_id(out)[rule_id])
    _assert_candidate_review_inventory(out)
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(out)
    RulePackPayload.model_validate(out)
    _assert_compile_gate(out, created_at)
    return out


def _with_identity(payload: dict[str, Any], created_at: str, created_by: str) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    out.update(
        {
            "sequence": 29,
            "rule_pack_id": str(seq28._rule_pack_id(29)),
            "version": FOLD_VERSION,
            "created_at": created_at,
            "created_by": created_by,
            "previous_payload_sha256": SEQ28_PAYLOAD_SHA256,
            "rollback_of_payload_sha256": None,
        }
    )
    return out


def fold(
    anchor: dict[str, Any],
    anchor_signed: dict[str, Any],
    ledger_dir: Path,
    organ_candidate: dict[str, Any],
    *,
    trust_store: StaticTrustStore,
    baseline_root: Path,
    created_at: str = FOLD_CREATED_AT,
    created_by: str = FOLD_CREATED_BY,
    observed_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """REAL mode: restamp signed seq-28 from a NEW organ ledger, then apply the content."""

    if anchor.get("sequence") != 28:
        _fail(f"anchor carries sequence {anchor.get('sequence')!r}, expected 28")
    if hashlib.sha256(_canon(anchor)).hexdigest() != SEQ28_PAYLOAD_SHA256:
        _fail("anchor source is not the pinned signed seq-28 payload")
    if organ_candidate.get("sequence") != 29:
        _fail("organ candidate is not sequence 29")

    restamped = generic_fold(
        anchor,
        anchor_signed,
        load_ledger(ledger_dir),
        trust_store=trust_store,
        version=FOLD_VERSION,
        created_at=created_at,
        created_by=created_by,
        verified_by=seq28._portal_verified_by(organ_candidate),
        observed_at=observed_at,
        baseline_root=baseline_root,
        ledger_dir=ledger_dir,
    )
    if _canon(_without_identity(restamped)) != _canon(_without_identity(organ_candidate)):
        _fail(
            "generic restamp does not equal the organ candidate after identity fields are removed"
        )
    out = apply_content_edits(restamped, created_at=created_at)
    assert_anchor_relative_changes(anchor, out)
    return restamped, out


def dry_run_from_anchor_ledger(
    anchor: dict[str, Any],
    ledger_dir: Path,
    catalogue: dict[str, Any],
    *,
    trust_store: StaticTrustStore,
    baseline_root: Path,
    previous_source: dict[str, Any],
    previous_signed: dict[str, Any],
    observed_at: datetime,
    created_at: str = FOLD_CREATED_AT,
    created_by: str = FOLD_CREATED_BY,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rehearsal only: prove ``ledger -> seq-28`` from seq-27, then edit seq-28.

    The ledger must be the one that produced signed seq-28: the generic restamp of signed
    seq-27 followed by the seq-28 content edits must reproduce the seq-28 anchor byte for
    byte.  The returned base keeps the seq-28 portal stamps (nothing is presented as newer)
    under seq-29 identity.
    """

    reproduced = generic_fold(
        previous_source,
        previous_signed,
        load_ledger(ledger_dir),
        trust_store=trust_store,
        version=str(anchor["version"]),
        created_at=str(anchor["created_at"]),
        created_by=str(anchor["created_by"]),
        verified_by=seq28._portal_verified_by(anchor),
        observed_at=observed_at,
        baseline_root=baseline_root,
        ledger_dir=ledger_dir,
    )
    if _canon(seq28.apply_content_edits(reproduced, catalogue)) != _canon(anchor):
        _fail("dry-run ledger does not reproduce the signed seq-28 anchor from seq-27")
    if hashlib.sha256(_canon(anchor)).hexdigest() != SEQ28_PAYLOAD_SHA256:
        _fail("anchor source is not the pinned signed seq-28 payload")

    restamped = _with_identity(anchor, created_at, created_by)
    out = apply_content_edits(restamped, created_at=created_at)
    assert_anchor_relative_changes(anchor, out)
    return restamped, out


def main(argv: list[str] | None = None, *, observed_at: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--anchor-source", type=Path, default=_PACKS / "rulepack-prod-028.source.json"
    )
    parser.add_argument(
        "--anchor-signed", type=Path, default=_PACKS / "rulepack-prod-028.signed.json"
    )
    parser.add_argument("--ledger-dir", type=Path, default=None)
    parser.add_argument("--organ-candidate", type=Path, default=None)
    parser.add_argument("--baseline-root", type=Path, default=_RESEARCH)
    parser.add_argument("--catalogue", type=Path, default=_CATALOGUE)
    parser.add_argument("--created-at", default=FOLD_CREATED_AT)
    parser.add_argument("--created-by", default=FOLD_CREATED_BY)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--dry-run-reuse-anchor-ledger",
        action="store_true",
        help="rehearsal only: prove the selected ledger produced seq-28, then apply content edits",
    )
    args = parser.parse_args(argv)

    ledger_dir = args.ledger_dir or seq28.discover_newest_ledger(args.baseline_root)
    candidate_path = args.organ_candidate or ledger_dir / "rulepack-prod-029.source.json"
    inputs = [args.anchor_source, args.anchor_signed, ledger_dir, args.catalogue]
    if candidate_path.exists():
        inputs.append(candidate_path)
    seq28._assert_output_path(args.output, inputs)

    try:
        trust_store = StaticTrustStore.from_env()
    except RulePackVerificationError as exc:
        _fail(f"cannot load production trust store: {exc}")
    anchor = seq28._read_json(args.anchor_source)
    catalogue = seq28._read_json(args.catalogue)

    if args.dry_run_reuse_anchor_ledger:
        if candidate_path.exists():
            _fail("dry-run replay is forbidden when a real organ seq-29 candidate exists")
        _, out = dry_run_from_anchor_ledger(
            anchor,
            ledger_dir,
            catalogue,
            trust_store=trust_store,
            baseline_root=args.baseline_root,
            previous_source=seq28._read_json(_PACKS / "rulepack-prod-027.source.json"),
            previous_signed=seq28._read_json(_PACKS / "rulepack-prod-027.signed.json"),
            observed_at=observed_at or datetime.now(timezone.utc),
            created_at=args.created_at,
            created_by=args.created_by,
        )
        mode = "DRY RUN: reused only the ledger proven to have produced seq-28"
    else:
        if not candidate_path.exists():
            _fail(
                f"no organ candidate at {candidate_path}; wait for the new organ run or use "
                "--dry-run-reuse-anchor-ledger"
            )
        _, out = fold(
            anchor,
            seq28._read_json(args.anchor_signed),
            ledger_dir,
            seq28._read_json(candidate_path),
            trust_store=trust_store,
            baseline_root=args.baseline_root,
            created_at=args.created_at,
            created_by=args.created_by,
            observed_at=observed_at,
        )
        mode = "REAL ORGAN RESTAMP"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(canonicalize_json(out)).hexdigest()
    print(f"fold_pack_seq29: mode = {mode}")
    print(f"fold_pack_seq29: ledger = {ledger_dir}")
    print(f"fold_pack_seq29: wrote {args.output}")
    print(f"fold_pack_seq29: seq-29 payload_sha256 = {digest}")
    print(f"fold_pack_seq29: modified rules = {sorted(MODIFIED_RULE_IDS)}")
    print(f"fold_pack_seq29: inserted rules = {list(INSERTED_RULE_IDS_IN_ORDER)}")
    print(f"fold_pack_seq29: retired rules = {sorted(RETIRED_RULE_IDS)}")
    print("fold_pack_seq29: NOT SIGNED, NOT ACTIVATED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
