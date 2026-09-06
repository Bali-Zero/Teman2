import pytest

from .contract import bind_trial, validate_splits


def test_related_variants_cannot_cross_splits() -> None:
    with pytest.raises(ValueError, match="cross-split"):
        validate_splits(
            [
                {"group_id": "incident-1", "split": "development"},
                {"group_id": "incident-1", "split": "test"},
            ]
        )
    validate_splits(
        [
            {"group_id": "incident-1", "split": "development"},
            {"group_id": "incident-1", "split": "development"},
        ]
    )


def test_receipt_does_not_turn_prompt_inclusion_into_execution() -> None:
    first = bind_trial("trial-1", ("inspect dependency",), "inspect")
    revised = bind_trial("trial-2", ("escalate uncertainty",), "escalate")
    assert first["supplied_skill_hashes"] != revised["supplied_skill_hashes"]
    assert first["proposed_action"] == "inspect"
    assert first["executed"] is False
    assert first["verified_success"] is None
