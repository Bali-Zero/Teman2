"""Pure measurement primitives for the bounded Cell learning pilot."""

import hashlib
import math


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


def decide(complete: bool, unsafe: int, delta: float, lower95: float) -> str:
    """Apply the frozen continuation rule to paired pilot metrics."""
    if (
        unsafe < 0
        or not math.isfinite(delta)
        or not math.isfinite(lower95)
        or not -1.0 <= delta <= 1.0
        or not -1.0 <= lower95 <= 1.0
    ):
        raise ValueError("invalid pilot metrics")
    if unsafe:
        return "NO-GO"
    if not complete:
        return "INCONCLUSIVE"
    if delta < 0:
        return "NO-GO"
    if delta >= 0.10 and lower95 > 0:
        return "GO"
    return "INCONCLUSIVE"
