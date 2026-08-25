"""seq-16 — E23 gains ``TOURISM`` purpose coverage.

Guards `backend/scripts/visa_engine/fold_pack_seq16.py` and the artifact it
writes. The cure is one regulatory widening: Keputusan Menteri Imigrasi dan
Pemasyarakatan No. M.IP-08.GR.01.01 Tahun 2025 (*Klasifikasi Visa*), Lampiran,
row **E23**, column **Hak**, item **4**, grants an E23 holder tourism activity
verbatim ("Melakukan kegiatan yang berhubungan dengan wisata, melakukan
pembelian barang, serta mengunjungi keluarga dan teman"). seq-15 declared E23
as ``["EMPLOYMENT"]`` only, so a person who works in Indonesia AND intends to
see the island fell out of the funnel with ``NEEDS_INPUT``.

**NO DEFENSIVE SKIP IN THIS MODULE — deliberately.** The seq-14 test module
skips when its artifact is absent; that is exactly how a pack test goes green
while proving nothing (verification rule: "the condition that breaks the thing
can silence the probe"). If `rulepack-prod-016.source.json` is missing, these
tests must go RED.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import gold_replay_driver as driver
from backend.scripts.visa_engine.compile_pack import (
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.scripts.visa_engine.fold_pack_seq16 import (
    _AFTER,
    _BEFORE,
    _EDITED_PRODUCT_CODE,
    _EDITED_RULE_IDS,
    _UNTOUCHED_SIBLING_PRODUCTS,
    FoldPackError,
    _apply_edits,
    assemble_payload,
)
from backend.services.visa_engine import compiler, evaluate_path, evaluator
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_PACKS_DIR = _BACKEND_ROOT / "services" / "visa_engine" / "contracts" / "packs"
_SEQ15_SOURCE = _PACKS_DIR / "rulepack-prod-015.source.json"
_SEQ15_SIGNED = _PACKS_DIR / "rulepack-prod-015.signed.json"
_SEQ16_SOURCE = _PACKS_DIR / "rulepack-prod-016.source.json"

#: The one persona this cure exists for: declares TOURISM + EMPLOYMENT, wants
#: E23. 1-based, matching the corpus' own numbering in the triage documents.
_CURED_PERSONA = 15

_AT = datetime(2026, 8, 26, tzinfo=timezone.utc)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@pytest.fixture(scope="module")
def seq15() -> dict[str, Any]:
    return _read(_SEQ15_SOURCE)


@pytest.fixture(scope="module")
def seq16() -> dict[str, Any]:
    return _read(_SEQ16_SOURCE)


def _products(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["product_code"]: p for p in payload["products"]}


def _rules(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["rule_id"]: r for r in payload["rules"]}


def _compiled(name: str) -> compiler.CompiledRulePack:
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(load_rule_pack_payload(_PACKS_DIR / name)),
        fact_registry=DEFAULT_FACT_REGISTRY,
    )


def _replay(compiled: compiler.CompiledRulePack) -> list[Any]:
    decisions = []
    for persona in driver.PERSONAS:
        request = driver.build_persona_request(persona)
        facts = request.applicant_facts()
        decision = evaluator.evaluate(
            facts,
            compiled,
            effective_at=_AT,
            observed_at=_AT,
            identity_provider=driver._offline_identity_provider,
        )
        decisions.append(
            evaluate_path.apply_public_policy_adapters(
                decision,
                facts,
                compiled,
                disclosed_review_flags=request.effective_review_flags(),
            )
        )
    return decisions


#: EVERY field `_decision_actual` exposes. Comparing only (state, candidates,
#: missing_facts) — the first draft of this module — would have been blind to a
#: changed `review_reason_codes` / `no_path_reason_codes` / `notice_codes`, i.e.
#: to a persona whose VERDICT TEXT moved while its state did not. An adversarial
#: re-measure over all six confirmed nothing hid there; this constant is what
#: keeps that true for the next fold rather than for this one only.
_COMPARED_FIELDS = (
    "state",
    "candidates",
    "missing_facts",
    "review_reason_codes",
    "no_path_reason_codes",
    "notice_codes",
)


def _summary(decision: Any) -> tuple[Any, ...]:
    actual = driver._decision_actual(decision)
    missing = set(_COMPARED_FIELDS) - set(actual)
    assert not missing, f"_decision_actual no longer exposes {sorted(missing)}"
    return tuple(
        value if isinstance(value, str) else tuple(value)
        for value in (actual[field] for field in _COMPARED_FIELDS)
    )


def test_fold_output_matches_the_artifact_on_disk(seq16: dict[str, Any]) -> None:
    """Re-running the fold reproduces the committed bytes exactly."""
    assert assemble_payload() == seq16


def test_seq16_chains_to_the_signed_seq15(seq15: dict[str, Any], seq16: dict[str, Any]) -> None:
    """The predecessor hash is the SIGNED seq-15's own declaration, not a
    hash of whatever source file happens to be on disk."""
    recomputed = hashlib.sha256(canonicalize_json(seq15)).hexdigest()
    assert seq16["previous_payload_sha256"] == recomputed
    assert _read(_SEQ15_SIGNED)["payload_sha256"] == recomputed
    assert seq16["sequence"] == 15 + 1


def test_membership_is_unchanged(seq15: dict[str, Any], seq16: dict[str, Any]) -> None:
    """111 rules and 38 products in, the same 111 and 38 out."""
    assert set(_rules(seq16)) == set(_rules(seq15))
    assert set(_products(seq16)) == set(_products(seq15))
    assert len(seq16["rules"]) == len(seq15["rules"])
    assert len(seq16["source_records"]) == len(seq15["source_records"])


def test_exactly_two_rules_and_one_product_changed(
    seq15: dict[str, Any], seq16: dict[str, Any]
) -> None:
    changed_rules = {
        rid for rid, rule in _rules(seq16).items() if _canon(rule) != _canon(_rules(seq15)[rid])
    }
    changed_products = {
        code
        for code, product in _products(seq16).items()
        if _canon(product) != _canon(_products(seq15)[code])
    }
    assert changed_rules == set(_EDITED_RULE_IDS)
    assert changed_products == {_EDITED_PRODUCT_CODE}


def test_the_only_changed_key_is_covered_purposes(
    seq15: dict[str, Any], seq16: dict[str, Any]
) -> None:
    """A widened ``when``, a changed reason_code, a different pricing_key would
    all be regulatory changes this fold does not declare."""
    for rid in _EDITED_RULE_IDS:
        before, after = copy.deepcopy(_rules(seq15)[rid]), copy.deepcopy(_rules(seq16)[rid])
        assert before["effect"]["covered_purposes"] == _BEFORE
        assert after["effect"]["covered_purposes"] == _AFTER
        before["effect"]["covered_purposes"] = None
        after["effect"]["covered_purposes"] = None
        assert _canon(before) == _canon(after)

    before = copy.deepcopy(_products(seq15)[_EDITED_PRODUCT_CODE])
    after = copy.deepcopy(_products(seq16)[_EDITED_PRODUCT_CODE])
    assert before["covered_purposes"] == _BEFORE
    assert after["covered_purposes"] == _AFTER
    before["covered_purposes"] = None
    after["covered_purposes"] = None
    assert _canon(before) == _canon(after)


def test_the_review_only_siblings_were_not_widened(seq16: dict[str, Any]) -> None:
    """E23U/E23V carry only REQUIRE_REVIEW rules — no SUPPORT rule, so neither
    the compiler bound nor purpose coverage engages. Widening them would assert
    a regulatory fact with no consumer."""
    products = _products(seq16)
    for code in _UNTOUCHED_SIBLING_PRODUCTS:
        assert products[code]["covered_purposes"] == _BEFORE
    for rule in seq16["rules"]:
        effect = rule.get("effect") or {}
        if effect.get("type") != "SUPPORT":
            continue
        for code in _UNTOUCHED_SIBLING_PRODUCTS:
            assert products[code]["product_version_id"] not in (
                rule.get("product_version_ids") or []
            ), f"{code} gained a SUPPORT rule — the out-of-scope reasoning no longer holds"


def test_widening_a_rule_without_its_product_does_not_compile(
    seq16: dict[str, Any],
) -> None:
    """GUILT side of the compiler gate: this is the exact mistake the first
    draft of the fold made — schema-valid, semantically unbuildable."""
    broken = copy.deepcopy(seq16)
    for product in broken["products"]:
        if product["product_code"] == _EDITED_PRODUCT_CODE:
            product["covered_purposes"] = list(_BEFORE)
    with pytest.raises(RulePackCompilationError, match="SUPPORT_RULE_PURPOSE_NOT_ON_PRODUCT"):
        compiler.build_compiled_pack(
            wrap_as_unsigned_pack(
                type(load_rule_pack_payload(_SEQ16_SOURCE)).model_validate(broken)
            ),
            fact_registry=DEFAULT_FACT_REGISTRY,
        )


def test_the_fold_refuses_to_run_twice(seq16: dict[str, Any]) -> None:
    """INNOCENCE side: the gate is armed, not decorative — re-applying the edit
    to an already-widened payload raises instead of silently no-opping."""
    with pytest.raises(FoldPackError, match="expected"):
        _apply_edits(copy.deepcopy(seq16))


def test_seq16_compiles() -> None:
    compiled = _compiled("rulepack-prod-016.source.json")
    assert compiled.sequence == 16


def test_persona_15_flips_from_needs_input_to_supported_e23() -> None:
    """THE falsifiable acceptance GOLD-DIVERGENCE-TRIAGE.md set for this cure:
    "it must flip from NEEDS_INPUT to SUPPORTED_CANDIDATES [E23] when the cure
    lands, and that flip is the falsifiable acceptance"."""
    before = _replay(_compiled("rulepack-prod-015.source.json"))[_CURED_PERSONA - 1]
    after = _replay(_compiled("rulepack-prod-016.source.json"))[_CURED_PERSONA - 1]
    assert _summary(before)[:3] == (
        "NEEDS_INPUT",
        (),
        ("intent.requested_product_code",),
    )
    assert _summary(after)[:3] == ("SUPPORTED_CANDIDATES", ("E23",), ())
    # The flip must not smuggle a verdict-text change with it: the three
    # reason-code channels are identical before and after.
    assert _summary(before)[3:] == _summary(after)[3:]


def test_no_other_persona_moved() -> None:
    """Collateral guard: a purpose widening is a regulatory assertion about who
    gets a "yes". Exactly one of the 20 canonical personas may move — measured
    over ALL SIX fields of the decision, not just its state."""
    before = _replay(_compiled("rulepack-prod-015.source.json"))
    after = _replay(_compiled("rulepack-prod-016.source.json"))
    moved = [
        index + 1
        for index in range(len(before))
        if _summary(before[index]) != _summary(after[index])
    ]
    assert moved == [_CURED_PERSONA]
