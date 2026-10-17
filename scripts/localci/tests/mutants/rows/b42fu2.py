"""B42 follow-up round 2: the flip carry-over reads role_name, not the legacy permission (which folds maintain into write)."""
CO = ("scripts/localci/tests/test_flip_carryover_selection.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b42fu2-carryover-role-from-permission": ("scripts/localci/README.md", "--jq .role_name", "--jq .permission", CO),
}
