"""UNIT 2: Green-class safety gate for the modus autonomous loop.

PURE deterministic predicate — no LLM call, no network I/O. This is the
load-bearing safety unit: a task may only be auto-executed by the modus
autoloop if is_green() returns (True, "green").

Contract
--------
    is_green(task: dict) -> tuple[bool, str]

    task is expected to carry (at minimum):
        task["class"]      : str  — must be exactly "green" to even be
                                    considered (any other value, including
                                    "proposal", is rejected outright).
        task["perimeter"]  : list[str] | str — file/dir paths the task
                                    intends to touch.
        task["mandate"]    : str  — free-text description of the task
                                    (checked for business-decision keywords).

    Returns (allowed, reason):
        allowed is True  only if class == "green" AND no disqualifier fires.
        reason  is "green" on success, or the exact disqualifier name that
        fired on rejection (see DISQUALIFIER_PATHS / DISQUALIFIER_KEYWORDS
        below) so callers/logs can cite precisely why a task was blocked.

Matching discipline (scar family #3 — guard-over-match / substring trap)
--------------------------------------------------------------------------
Path disqualifiers match on PATH-SEGMENT intersection: a perimeter path is
split on "/" and each disqualifier is compared as a segment (or exact
tail-component) against those segments — never as a bare substring of the
raw path string. This is what stops "release/" tripping "auth" or
"docs/authoring-guide/x.md" tripping "auth": "auth" is not a path segment
of either.

Keyword disqualifiers (business-decision detection) match on WORD
boundaries via regex (`\\b...\\b`), case-insensitive — never bare
`keyword in text`. This is what stops "author" tripping "auth" and
"released" tripping "lease" (not applicable here but same principle).

HARD INVARIANT (out of scope for this predicate, documented for callers):
the final gate never cascades to a weaker model; quota-dead at the final
gate means the task is deferred, never silently downgraded and executed by
a lesser model. This gate only decides GREEN eligibility, it does not
itself run or cascade anything.
"""
from __future__ import annotations

import re
from typing import Final

# ---------------------------------------------------------------------------
# Disqualifier catalog
# ---------------------------------------------------------------------------

# Path-segment disqualifiers. Each entry is matched against the individual
# "/"-split segments (and dotted sub-tokens, see _path_segments()) of every
# perimeter path — NEVER as a substring of the raw path.
DISQUALIFIER_PATHS: Final[dict[str, tuple[str, ...]]] = {
    "migrations": ("migrations",),
    "migrations_v2": ("migrations_v2",),
    "alembic": ("alembic",),
    "auth": ("auth",),
    "billing": ("billing",),
    "pricing": ("pricing",),
    "pricing_tool": ("pricingtool",),
    "secrets_env": (".env",),
    "fly_toml": ("fly.toml",),
    "deploy": ("deploy",),
    "github_workflows": (".github",),  # combined with "workflows" segment check
    "zantara_core": ("zantara_core.py",),
    "alembic_env": ("env.py",),  # combined with "alembic" ancestor check below
}

# Business-decision keywords (word-boundary regex, case-insensitive).
DISQUALIFIER_KEYWORDS: Final[dict[str, re.Pattern[str]]] = {
    "business_decision_quote": re.compile(r"\bquote\b", re.IGNORECASE),
    "business_decision_client_price": re.compile(
        r"\bclient[\s_-]?price\b", re.IGNORECASE
    ),
    "business_decision_refund": re.compile(r"\brefund\b", re.IGNORECASE),
    "business_decision_contract": re.compile(r"\bcontract\b", re.IGNORECASE),
    "business_decision_hire": re.compile(r"\bhire\b", re.IGNORECASE),
    "business_decision_fire": re.compile(r"\bfire\b", re.IGNORECASE),
    "business_decision_email_to_client": re.compile(
        r"\bemail\s+to\s+client\b", re.IGNORECASE
    ),
}

_GREEN_CLASS: Final[str] = "green"


def _path_segments(path: str) -> list[str]:
    """Split a path into lowercase segments, splitting on '/' AND '\\'.

    Backslash-separated paths (e.g. "migrations_v2\\v99.sql") are normalized
    to forward slashes first, so a Windows-style or backslash-escaped path
    cannot smuggle a disqualified segment past the "/"-only splitter
    (scar family #3 — the splitter itself must not under-match).

    Filenames (e.g. "fly.toml", ".env", "env.py") are kept as whole
    segments — disqualifier matching for those compares full segment
    equality, not substring, so "myenv.py" does not falsely match "env.py".
    """
    normalized = path.strip().lower().replace("\\", "/")
    return [seg for seg in normalized.split("/") if seg]


def _perimeter_list(task: dict) -> list[str]:
    """Return every perimeter path as its own list entry.

    A single string containing whitespace-separated globs
    (e.g. "research/x.md migrations/evil.sql") is split so EACH glob is
    checked independently — otherwise the disqualifier check would run the
    whole string through _path_segments() as one opaque path and never see
    the second, dangerous glob (scar family #3 — composition under-match).
    """
    perimeter = task.get("perimeter", [])
    if isinstance(perimeter, str):
        return [tok for tok in perimeter.split() if tok] or [perimeter]
    if isinstance(perimeter, (list, tuple)):
        out: list[str] = []
        for p in perimeter:
            out.extend(tok for tok in str(p).split() if tok)
        return out
    return []


def _segment_hits(segments: list[str], needles: tuple[str, ...]) -> bool:
    """True if any needle exactly matches a path segment or a segment's
    filename stem (text before the last '.'), never a bare substring.

    The stem comparison lets a filename-style needle like "pricingtool"
    match a segment such as "pricingtool.py" (stem == needle) without
    resorting to substring matching — "mypricingtoolhelper.py" still does
    NOT match, because its stem is "mypricingtoolhelper", not "pricingtool".
    """
    for needle in needles:
        for segment in segments:
            if segment == needle:
                return True
            stem = segment.rsplit(".", 1)[0]
            if stem == needle:
                return True
    return False


def _check_path_disqualifiers(path: str) -> str | None:
    """Return the disqualifier name that fired for this path, or None."""
    segments = _path_segments(path)

    for name, needles in DISQUALIFIER_PATHS.items():
        if name == "github_workflows":
            # Require BOTH ".github" and "workflows" as segments — avoids a
            # false hit on a bare ".github" dir that isn't the workflows
            # subtree (e.g. ".github/ISSUE_TEMPLATE/...").
            if _segment_hits(segments, (".github",)) and "workflows" in segments:
                return name
            continue
        if name == "alembic_env":
            # Require BOTH "alembic" ancestor and "env.py" leaf — avoids a
            # false hit on an unrelated "env.py" outside the alembic tree.
            if "alembic" in segments and _segment_hits(segments, needles):
                return name
            continue
        if _segment_hits(segments, needles):
            return name

    return None


def _check_keyword_disqualifiers(mandate: str) -> str | None:
    for name, pattern in DISQUALIFIER_KEYWORDS.items():
        if pattern.search(mandate):
            return name
    return None


def is_green(task: dict) -> tuple[bool, str]:
    """Decide whether `task` is GREEN-class auto-executable.

    Pure, deterministic, no I/O. See module docstring for the full contract.
    """
    task_class = task.get("class")

    # class == "proposal" is ALWAYS not-green, regardless of perimeter.
    if task_class == "proposal":
        return False, "class_proposal_never_green"

    if task_class != _GREEN_CLASS:
        return False, "class_not_green"

    for path in _perimeter_list(task):
        hit = _check_path_disqualifiers(path)
        if hit is not None:
            return False, f"perimeter_disqualifier:{hit}"

    mandate = str(task.get("mandate", ""))
    hit = _check_keyword_disqualifiers(mandate)
    if hit is not None:
        return False, f"mandate_disqualifier:{hit}"

    return True, "green"
