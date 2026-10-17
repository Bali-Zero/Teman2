"""Fold seq-31: the E28A own-shareholding re-key, chained on verified signed seq-30.

Chained on the signed seq-30 anchor (payload
``972f339283e6a66962f3dd8f4dbb1c4a5014c5b16352234e425abfed988df413``).  Like seq-26 and
seq-30 this is a mid-week content fold: all 28 ``source_records`` (and every
``OFFICIAL_PORTAL`` stamp, so the freshness boundary) stay byte-identical to signed seq-30.
Products, prices and duration options do not move.

One content item (owner ruling 1 of 2026-10-15; handoff SEQ29-A1, never folded into seq-30).
The saved official Imigrasi E28A page (``df3ba889-e28a.txt``) says "Bukti kepemilikan saham
paling sedikit Rp10.000.000.000,00 (sepuluh miliar rupiah) atau setara pada perusahaan
penjamin yang terdaftar di Kementerian Investasi/Badan Koordinasi Penanaman Modal."  That is
the APPLICANT'S OWN shareholding value in the sponsoring company; the page states no company
total-investment figure.  So the IDR 10,000,000,000 test is re-keyed from the company-level
``investment.investment_capital_idr`` to the new fact ``investment.own_shareholding_idr``
(engine step A, interview step B):

* ``el.e28a.investment`` -- ``investment.own_shareholding_idr gte 10_000_000_000`` replaces
  ``investment.investment_capital_idr gte 10_000_000_000``; ``required_facts`` follows.  The
  INVESTMENT purpose, the PT PMA commitment and the IDR 2.5bn paid-up bound stay.
* ``hf.e28a.total-investment-below-min`` (``E28A_TOTAL_INVESTMENT_BELOW_MIN``) is RETIRED and
  ``hf.e28a.own-shareholding-below-min`` (``E28A_OWN_SHAREHOLDING_BELOW_MIN``) is inserted
  at the end of the rule list, exactly as seq-29 retired and inserted E31J rules.  The
  semantics changed, so the reason code is renamed rather than repurposed: a replayed
  ``E28A_TOTAL_INVESTMENT_BELOW_MIN`` from an older pack keeps its old meaning.
* ``hf.e28a.paid-capital-below-min`` stays untouched: the IDR 2.5bn paid-up bound is a
  PT PMA company prerequisite (company law, not the visa).  The pack carries no explanation
  prose, only ``explanation_key``; the user-facing copy lives in the mouth adapter.

No regulation number is written anywhere: the pinpoint ``Permenkumham 22/2023 jo 11/2024
Pasal 38(2)(a)`` is UNVERIFIED in this repository (TO VERIFY against source).  The rules cite
the E28A ``source_record`` the pack already carries (the official Indeks Visa catalogue,
locator ``/wna/daftar-visa-indonesia/E28A``).

This module never signs or activates anything.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

from backend.scripts.visa_engine import fold_pack_seq28 as seq28
from backend.scripts.visa_engine import fold_pack_seq30 as seq30
from backend.scripts.visa_engine.compile_pack import compile_pack_source
from backend.scripts.visa_engine.fold_pack_seq24 import (
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact,
)
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload

SEQ30_SEQUENCE = 30
SEQ30_PAYLOAD_SHA256 = (
    "972f339283e6a66962f3dd8f4dbb1c4a5014c5b16352234e425abfed988df413"  # pragma: allowlist secret
)
SEQ31_SEQUENCE = 31
FOLD_VERSION = "2026.10.17"
FOLD_CREATED_AT = "2026-10-17T12:00:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.vo-seq31-e28a-own-share-1017"
NEW_RULE_VALID_FROM = "2026-10-17T00:00:00Z"

E28A_PRODUCT_VERSION_ID = seq30.E28A_PRODUCT_VERSION_ID
# The Indeks Visa catalogue record that already backs every E28A rule (locator
# /wna/daftar-visa-indonesia/E28A); reused, never re-stamped.
SRC_E28A_CATALOGUE = "6f5135f2-1f77-571f-88ed-26d1d2b9efba"

OWN_SHAREHOLDING_FACT = "investment.own_shareholding_idr"
INVESTMENT_CAPITAL_FACT = "investment.investment_capital_idr"
OWN_SHAREHOLDING_THRESHOLD_IDR = 10_000_000_000
PAID_UP_THRESHOLD_IDR = 2_500_000_000

E28A_RULE_ID = seq30.E28A_RULE_ID
OLD_TOTAL_INVESTMENT_RULE_ID = "hf.e28a.total-investment-below-min"
OLD_TOTAL_INVESTMENT_REASON_CODE = "E28A_TOTAL_INVESTMENT_BELOW_MIN"
OWN_SHAREHOLDING_RULE_ID = "hf.e28a.own-shareholding-below-min"
OWN_SHAREHOLDING_REASON_CODE = "E28A_OWN_SHAREHOLDING_BELOW_MIN"
PAID_CAPITAL_RULE_ID = "hf.e28a.paid-capital-below-min"

MODIFIED_RULE_IDS = frozenset({E28A_RULE_ID})
INSERTED_RULE_IDS_IN_ORDER = (OWN_SHAREHOLDING_RULE_ID,)
INSERTED_RULE_IDS = frozenset(INSERTED_RULE_IDS_IN_ORDER)
RETIRED_RULE_IDS = frozenset({OLD_TOTAL_INVESTMENT_RULE_ID})

_IDENTITY_KEYS = seq28._IDENTITY_KEYS
_PACKS = seq28._PACKS
_CATALOGUE = seq28._CATALOGUE
_canon = seq28._canon
_rules_by_id = seq28._rules_by_id
_fact_paths = seq28._fact_paths


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"fold_pack_seq31: {message}")


def _e28a_when(fact: str) -> dict[str, Any]:
    return {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["INVESTMENT"]},
            {"op": "eq", "fact": "investment.pt_pma_committed", "value": True},
            {"op": "gte", "fact": "investment.paid_up_capital_idr", "value": PAID_UP_THRESHOLD_IDR},
            {"op": "gte", "fact": fact, "value": OWN_SHAREHOLDING_THRESHOLD_IDR},
        ],
    }


def build_e28a_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Re-key the IDR 10bn test of ``el.e28a.investment`` to the applicant's own shareholding."""

    if rule.get("rule_id") != E28A_RULE_ID:
        _fail(f"expected {E28A_RULE_ID!r}, got {rule.get('rule_id')!r}")
    if rule.get("when") != _e28a_when(INVESTMENT_CAPITAL_FACT):
        _fail(f"{E28A_RULE_ID!r} no longer has the seq-30 investment_capital_idr shape")
    if rule.get("on_unknown") != "NEEDS_INPUT":
        _fail(f"{E28A_RULE_ID!r} on_unknown is not NEEDS_INPUT")

    out = copy.deepcopy(rule)
    out["when"] = _e28a_when(OWN_SHAREHOLDING_FACT)
    out["required_facts"] = _fact_paths(out["when"])
    return out


def build_own_shareholding_filter() -> dict[str, Any]:
    """The renamed IDR 10bn exclusion: the applicant's own shareholding is below the floor."""

    when = {"op": "lt", "fact": OWN_SHAREHOLDING_FACT, "value": OWN_SHAREHOLDING_THRESHOLD_IDR}
    return {
        "rule_id": OWN_SHAREHOLDING_RULE_ID,
        "stage": "HARD_FILTER",
        "scope": "PRODUCTS",
        "product_version_ids": [E28A_PRODUCT_VERSION_ID],
        "when": when,
        "effect": {"type": "EXCLUDE", "reason_code": OWN_SHAREHOLDING_REASON_CODE},
        "on_unknown": "NEEDS_INPUT",
        "priority": 100,
        "required_facts": _fact_paths(when),
        "source_refs": [SRC_E28A_CATALOGUE],
        "valid_period": {"from": NEW_RULE_VALID_FROM, "to": None},
        "explanation_key": f"explain.{OWN_SHAREHOLDING_RULE_ID}",
        "safety_critical": False,
    }


_MODIFIED_RULE_BUILDERS = {E28A_RULE_ID: build_e28a_rule}


def assert_retired_rule_shape(rule: dict[str, Any]) -> None:
    """The retired rule must be the seq-30 company-total-investment exclusion, nothing else."""

    if rule.get("effect") != {
        "type": "EXCLUDE",
        "reason_code": OLD_TOTAL_INVESTMENT_REASON_CODE,
    } or rule.get("when") != {"op": "lt", "fact": INVESTMENT_CAPITAL_FACT, "value": 10_000_000_000}:
        _fail(f"{OLD_TOTAL_INVESTMENT_RULE_ID!r} is not the seq-30 exclusion shape")


def assert_only_expected_changes(restamped: dict[str, Any], out: dict[str, Any]) -> None:
    """Seq-30 may differ from seq-31 in exactly one modified, one retired, one inserted rule."""

    if set(restamped) != set(out):
        _fail("top-level key set changed")
    for key in set(restamped) - _IDENTITY_KEYS - {"rules"}:
        if _canon(restamped[key]) != _canon(out[key]):
            _fail(f"{key} changed; products, source_records and all other content must be identical")

    before_rules = _rules_by_id(restamped)
    after_rules = _rules_by_id(out)
    expected_order = [
        *(r["rule_id"] for r in restamped["rules"] if r["rule_id"] not in RETIRED_RULE_IDS),
        *INSERTED_RULE_IDS_IN_ORDER,
    ]
    if [r["rule_id"] for r in out["rules"]] != expected_order:
        _fail("rule order or membership changed outside the scheduled retire/insert")
    if set(before_rules) - set(after_rules) != RETIRED_RULE_IDS:
        _fail("retired rule set differs from the schedule")
    if set(after_rules) - set(before_rules) != INSERTED_RULE_IDS:
        _fail("inserted rule set differs from the schedule")

    for rule_id, before in before_rules.items():
        if rule_id in RETIRED_RULE_IDS:
            assert_retired_rule_shape(before)
            continue
        after = after_rules[rule_id]
        if rule_id in MODIFIED_RULE_IDS:
            if _canon(after) != _canon(_MODIFIED_RULE_BUILDERS[rule_id](before)):
                _fail(f"modified rule {rule_id!r} does not equal its builder output")
        elif _canon(before) != _canon(after):
            _fail(f"unscheduled rule {rule_id!r} changed")
    if _canon(after_rules[OWN_SHAREHOLDING_RULE_ID]) != _canon(build_own_shareholding_filter()):
        _fail(f"inserted rule {OWN_SHAREHOLDING_RULE_ID!r} does not equal its builder output")


def assert_anchor_relative_changes(anchor: dict[str, Any], out: dict[str, Any]) -> None:
    """Compare the seq-31 output directly with the seq-30 anchor."""

    assert_only_expected_changes(
        _with_identity(anchor, str(out["created_at"]), str(out["created_by"])), out
    )


def _with_identity(payload: dict[str, Any], created_at: str, created_by: str) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    out.update(
        {
            "sequence": SEQ31_SEQUENCE,
            "rule_pack_id": str(seq28._rule_pack_id(SEQ31_SEQUENCE)),
            "version": FOLD_VERSION,
            "created_at": created_at,
            "created_by": created_by,
            "previous_payload_sha256": SEQ30_PAYLOAD_SHA256,
            "rollback_of_payload_sha256": None,
        }
    )
    return out


def _assert_compile_gate(out: dict[str, Any], created_at: str) -> None:
    with tempfile.TemporaryDirectory(prefix="seq31-compile-") as temp_dir:
        path = Path(temp_dir) / "rulepack-prod-031.source.json"
        path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        _, report = compile_pack_source(
            path, observed_at=datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        )
    if not report.ok:
        detail = "; ".join(f"{error.code}:{error.message}" for error in report.errors)
        _fail(f"compile_pack gate failed: {detail}")


def apply_content_edits(
    restamped: dict[str, Any], *, created_at: str = FOLD_CREATED_AT
) -> dict[str, Any]:
    if restamped.get("sequence") != SEQ31_SEQUENCE:
        _fail(f"restamped base carries sequence {restamped.get('sequence')!r}, expected 31")
    rules = _rules_by_id(restamped)
    for rule_id in MODIFIED_RULE_IDS | RETIRED_RULE_IDS:
        if rule_id not in rules:
            _fail(f"rule {rule_id!r} is absent")
    for rule_id in INSERTED_RULE_IDS:
        if rule_id in rules:
            _fail(f"rule {rule_id!r} already exists")

    out = copy.deepcopy(restamped)
    out["rules"] = [
        _MODIFIED_RULE_BUILDERS[rule["rule_id"]](rule)
        if rule["rule_id"] in MODIFIED_RULE_IDS
        else rule
        for rule in out["rules"]
        if rule["rule_id"] not in RETIRED_RULE_IDS
    ]
    out["rules"].append(build_own_shareholding_filter())

    assert_only_expected_changes(restamped, out)
    for rule_id in (*sorted(MODIFIED_RULE_IDS), *INSERTED_RULE_IDS_IN_ORDER):
        seq30._assert_required_facts(_rules_by_id(out)[rule_id])
    seq30._assert_candidate_review_inventory(out)
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(out)
    RulePackPayload.model_validate(out)
    _assert_compile_gate(out, created_at)
    return out


def fold_from_signed_seq30(
    anchor_source: dict[str, Any],
    anchor_signed: dict[str, Any],
    *,
    trust_store: StaticTrustStore,
    observed_at: datetime | None = None,
    created_at: str = FOLD_CREATED_AT,
    created_by: str = FOLD_CREATED_BY,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify signed seq-30, check its payload equals rulepack-prod-030.source.json, and fold."""

    if anchor_source.get("sequence") != SEQ30_SEQUENCE:
        _fail(f"anchor carries sequence {anchor_source.get('sequence')!r}, expected 30")
    if hashlib.sha256(_canon(anchor_source)).hexdigest() != SEQ30_PAYLOAD_SHA256:
        _fail("anchor source is not the pinned signed seq-30 payload")

    signed_at_raw = anchor_signed.get("protected", {}).get("signed_at")
    if not isinstance(signed_at_raw, str):
        _fail("anchor signed bundle is missing protected.signed_at")
    verify_at = observed_at or datetime.fromisoformat(signed_at_raw.replace("Z", "+00:00"))
    try:
        verified = verify_rule_pack(anchor_signed, trust_store=trust_store, observed_at=verify_at)
    except RulePackVerificationError as exc:
        _fail(f"signed seq-30 anchor failed verification: {exc}")
    if verified.unsigned_dev is not False or verified.pack.payload.sequence != SEQ30_SEQUENCE:
        _fail("signed seq-30 anchor did not verify as production sequence 30")
    if verified.payload_sha256.hex() != SEQ30_PAYLOAD_SHA256:
        _fail(
            f"signed seq-30 payload_sha256 {verified.payload_sha256.hex()} != {SEQ30_PAYLOAD_SHA256}"
        )
    if _canon(anchor_signed.get("payload")) != _canon(anchor_source):
        _fail("signed seq-30 payload does not equal rulepack-prod-030.source.json")

    restamped = _with_identity(anchor_source, created_at, created_by)
    out = apply_content_edits(restamped, created_at=created_at)
    assert_anchor_relative_changes(anchor_source, out)
    return restamped, out


def main(argv: list[str] | None = None, *, observed_at: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--anchor-source", type=Path, default=_PACKS / "rulepack-prod-030.source.json"
    )
    parser.add_argument(
        "--anchor-signed", type=Path, default=_PACKS / "rulepack-prod-030.signed.json"
    )
    parser.add_argument("--created-at", default=FOLD_CREATED_AT)
    parser.add_argument("--created-by", default=FOLD_CREATED_BY)
    parser.add_argument("--output", type=Path, default=_PACKS / "rulepack-prod-031.source.json")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that the existing --output file matches the fold output.",
    )
    args = parser.parse_args(argv)

    try:
        trust_store = StaticTrustStore.from_env()
    except RulePackVerificationError as exc:
        _fail(f"cannot load production trust store: {exc}")

    anchor_source = seq28._read_json(args.anchor_source)
    anchor_signed = seq28._read_json(args.anchor_signed)
    _, out = fold_from_signed_seq30(
        anchor_source,
        anchor_signed,
        trust_store=trust_store,
        observed_at=observed_at,
        created_at=args.created_at,
        created_by=args.created_by,
    )
    digest = hashlib.sha256(canonicalize_json(out)).hexdigest()

    if args.check:
        if not args.output.exists():
            _fail(f"{args.output} does not exist")
        if _canon(seq28._read_json(args.output)) != _canon(out):
            _fail(f"{args.output} differs from fold_pack_seq31 output")
        print(f"fold_pack_seq31: OK ({args.output.name}, payload_sha256={digest})")
        return 0

    seq28._assert_output_path(args.output, [args.anchor_source, args.anchor_signed])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"fold_pack_seq31: wrote {args.output}")
    print(f"fold_pack_seq31: seq-31 payload_sha256 = {digest}")
    print(f"fold_pack_seq31: modified rules = {sorted(MODIFIED_RULE_IDS)}")
    print(f"fold_pack_seq31: retired rules = {sorted(RETIRED_RULE_IDS)}")
    print(f"fold_pack_seq31: inserted rules = {list(INSERTED_RULE_IDS_IN_ORDER)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
