"""Gates for seq-15 (``rulepack-prod-015.source.json``, see
``backend.scripts.visa_engine.fold_pack_seq15``).

V1/E23UV lane (2026-08-25), owner ruling (A). seq-15 RESTORES the two
``review.e23{u,v}.requested-product`` HUMAN_REVIEW rules that seq-14
removed: 109 -> 111.

seq-14's removal was correct on its own premise — the rules were keyed on
``intent.requested_product_code``, which the interview hard-coded
NOT_ASKED, making them permanently UNKNOWN and (per the evaluator's
precedence) poisoning their product's whole proof to BLOCKED_UNKNOWN. The
premise stopped being true in the same change that produced this fold:
``employment_special_employer`` (tree.ts/flow.ts) now lets a work-branch
applicant name E23U/E23V, so the rules are reachable.

Only the two HUMAN_REVIEW rules come back. NO SUPPORT rule is authored for
E23U/E23V — seq-14's fold rejected that shape for a reason that still
stands (no predicate over the current fact vocabulary separates "a
diplomat's household" from "any individual employer"). That objection is
fatal to a rule that AUTO-APPROVES and does not bind one that raises a
HUMAN review, where over-capture costs a consultant reading an ordinary
case and under-capture leaves a client a confidently wrong answer.

Unlike ``test_seq14_pack.py``, this module does NOT skip when the pack file
is missing. The artifact is committed, so "absent" is a real failure, not a
"run the fold first" convenience — a defensive skip here would let exactly
the condition that breaks the feature silence the probe that guards it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine import fold_pack_seq15 as fold
from backend.services.visa_engine.bundle import canonicalize_json

_PACKS = (
    Path(__file__).resolve().parents[3]
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
)
_SEQ13 = _PACKS / "rulepack-prod-013.source.json"
_SEQ14 = _PACKS / "rulepack-prod-014.source.json"
_SEQ15 = _PACKS / "rulepack-prod-015.source.json"

_RESTORED = ("review.e23u.requested-product", "review.e23v.requested-product")


def _load(path: Path) -> dict[str, Any]:
    assert path.exists(), f"{path} is committed and must exist — absent is a failure, not a skip"
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@pytest.fixture(scope="module")
def seq13() -> dict[str, Any]:
    return _load(_SEQ13)


@pytest.fixture(scope="module")
def seq14() -> dict[str, Any]:
    return _load(_SEQ14)


@pytest.fixture(scope="module")
def seq15() -> dict[str, Any]:
    return _load(_SEQ15)


def test_identity_and_rule_count(seq14: dict[str, Any], seq15: dict[str, Any]) -> None:
    assert seq15["sequence"] == 15
    assert len(seq14["rules"]) == 109
    assert len(seq15["rules"]) == 111, "the fold claims 109 -> 111; count it, do not trust the docstring"


def test_chain_links_to_the_seq14_bytes_on_disk(
    seq14: dict[str, Any], seq15: dict[str, Any]
) -> None:
    """seq-14 has no ``.signed.json`` — it is an unsigned candidate — so the
    link is to its SOURCE bytes. If someone signs seq-14 with different
    bytes, this goes red, which is the point."""
    expected = hashlib.sha256(canonicalize_json(seq14)).hexdigest()
    assert seq15["previous_payload_sha256"] == expected


def test_the_two_rules_are_back_and_are_the_seq13_originals(
    seq13: dict[str, Any], seq15: dict[str, Any]
) -> None:
    """'Restored' must mean COPIED, not re-authored — otherwise the fold is
    quietly authoring new regulatory logic under the word 'restore'."""
    s13 = {r["rule_id"]: r for r in seq13["rules"]}
    s15 = {r["rule_id"]: r for r in seq15["rules"]}
    for rule_id in _RESTORED:
        assert rule_id in s15, f"{rule_id} is the whole point of seq-15"
        assert _canon(s15[rule_id]) == _canon(s13[rule_id])


def test_seq15_rules_are_byte_identical_to_seq13(
    seq13: dict[str, Any], seq15: dict[str, Any]
) -> None:
    """The load-bearing claim: seq-15 is a TRUE REVERT of seq-14's rule
    change, not a revert plus an unnoticed edit."""
    assert _canon(seq15["rules"]) == _canon(seq13["rules"])


def test_nothing_outside_rules_and_identity_moved(
    seq14: dict[str, Any], seq15: dict[str, Any]
) -> None:
    identity = {
        "sequence",
        "version",
        "rule_pack_id",
        "previous_payload_sha256",
        "created_at",
        "created_by",
    }
    for key in set(seq14) | set(seq15):
        if key in identity or key == "rules":
            continue
        assert _canon(seq15.get(key)) == _canon(seq14.get(key)), f"{key} drifted"


def test_no_support_rule_was_authored_for_e23u_or_e23v(seq15: dict[str, Any]) -> None:
    """The line seq-14's fold drew, held. Every rule naming E23U/E23V must be
    HUMAN_REVIEW — an ELIGIBILITY/SUPPORT rule here would re-introduce
    exactly the over-broad auto-approval adversarial review killed."""
    for rule in seq15["rules"]:
        blob = json.dumps(rule)
        if "E23U" in blob or "E23V" in blob:
            assert rule["stage"] == "HUMAN_REVIEW", (
                f"{rule['rule_id']} names E23U/E23V at stage {rule['stage']!r}; only "
                "HUMAN_REVIEW is licensed for these two products"
            )
            assert rule["effect"]["type"] == "REQUIRE_REVIEW"


def test_the_restored_rules_gate_on_no_sponsor_type(seq15: dict[str, Any]) -> None:
    """flow.ts deliberately does NOT sponsor-gate the interview question that
    arms these rules. That is only correct while the rules themselves carry
    no ``sponsor.type`` conjunct — pin it, so the two cannot drift apart."""
    by_id = {r["rule_id"]: r for r in seq15["rules"]}
    for rule_id in _RESTORED:
        assert "sponsor.type" not in json.dumps(by_id[rule_id]["when"])


def test_fold_is_deterministic() -> None:
    first = canonicalize_json(fold.assemble_payload())
    second = canonicalize_json(fold.assemble_payload())
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()


def test_fold_output_matches_the_artifact_on_disk(seq15: dict[str, Any]) -> None:
    """The committed file must BE what the script produces — otherwise the
    pack on disk is hand-edited and the fold is decorative."""
    assert _canon(fold.assemble_payload()) == _canon(seq15)


def test_fold_refuses_to_restore_a_rule_that_is_already_present(
    seq13: dict[str, Any]
) -> None:
    """Guilt test for the gate itself: feeding it a payload that already has
    the rules must fail loudly, not silently duplicate them."""
    with pytest.raises(fold.FoldPackError, match="already present"):
        fold._restore_rules(json.loads(json.dumps(seq13)), seq13)
