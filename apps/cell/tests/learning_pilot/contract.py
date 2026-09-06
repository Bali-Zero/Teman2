"""Pure measurement primitives for the bounded Cell learning pilot."""

import hashlib


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


def bind_trial(
    trial_id: str,
    skill_texts: tuple[str, ...],
    proposed_action: str,
) -> dict[str, object]:
    """Bind supplied skill content to a non-execution proposal receipt."""
    return {
        "trial_id": trial_id,
        "supplied_skill_hashes": [
            hashlib.sha256(text.encode("utf-8")).hexdigest() for text in skill_texts
        ],
        "proposed_action": proposed_action,
        "executed": False,
        "verified_success": None,
    }
