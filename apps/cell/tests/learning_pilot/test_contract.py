import pytest

from .contract import validate_splits


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
