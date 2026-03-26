"""Mutation Filter reflex — 20ms latency budget.
Regex-based safety check on proposed actions."""
import re
from enum import Enum

HARD_BLOCK_PATTERNS = [
    re.compile(r"rm\s+-rf", re.IGNORECASE),
    re.compile(r"chmod\s+777", re.IGNORECASE),
    re.compile(r"wget.*\|\s*(sh|bash)", re.IGNORECASE),
    re.compile(r"curl.*\|\s*(sh|bash|python)", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"DROP\s+DATABASE", re.IGNORECASE),
    re.compile(r"\bsudo\b", re.IGNORECASE),
    re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    re.compile(r"mkfs\.", re.IGNORECASE),
]

SOFT_WARN_PATTERNS = [
    re.compile(r"\bdelete\b", re.IGNORECASE),
    re.compile(r"\btruncate\b", re.IGNORECASE),
    re.compile(r"\brestart\b", re.IGNORECASE),
    re.compile(r"force[=: ]+true", re.IGNORECASE),
    re.compile(r"--force\b", re.IGNORECASE),
    re.compile(r"\bkill\b", re.IGNORECASE),
]

class MutationSafety(Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    REQUIRES_REVIEW = "requires_review"

def filter_mutation(action: str) -> MutationSafety:
    """Check if a proposed action is safe to execute."""
    for pattern in HARD_BLOCK_PATTERNS:
        if pattern.search(action):
            return MutationSafety.UNSAFE
    for pattern in SOFT_WARN_PATTERNS:
        if pattern.search(action):
            return MutationSafety.REQUIRES_REVIEW
    return MutationSafety.SAFE
