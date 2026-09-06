"""Pure measurement primitives for the bounded Cell learning pilot."""


def validate_splits(rows: list[dict[str, str]]) -> None:
    """Reject invalid split identities and causal groups spanning splits."""
    seen: dict[str, str] = {}
    for row in rows:
        group = row.get("group_id", "")
        split = row.get("split", "")
        if not group or split not in {"development", "validation", "test"}:
            raise ValueError("invalid split identity")
        if group in seen and seen[group] != split:
            raise ValueError("cross-split incident group")
        seen[group] = split
