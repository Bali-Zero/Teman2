"""B37: a would_enqueue row GitHub overtook counts toward liveness — one row per term of the rule."""
from merger_mutants import PY

MF = ("scripts/localci/tests/test_liveness_merged_first.py",)

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "b37-merged-not-required": (PY, 'isinstance(pull, dict) and pull.get("merged") is True', 'isinstance(pull, dict) and pull.get("merged") is not None', MF),
    "b37-merged-truthy": (PY, 'isinstance(pull, dict) and pull.get("merged") is True', 'isinstance(pull, dict) and bool(pull.get("merged"))', MF),
    "b37-head-not-compared": (PY, 'and head_of(pull) == r.get("head_sha"))', "and True)", MF),
    "b37-row-head-not-a-sha": (PY, 'and is_sha(r.get("head_sha")) and head_of(pull)', "and head_of(pull)", MF),
    "b37-pull-not-a-dict": (PY, "return (open_only_false(r) and isinstance(pull, dict) and", "return (open_only_false(r) and pull is not None and", MF),
    "b37-second-term-ignored": (PY, 'if k not in LIVENESS_EXCLUDED and k != "open"))', 'if k not in LIVENESS_EXCLUDED and k not in ("open", "review_not_blocking")))', MF),
    "b37-excluded-terms-required": (PY, 'if k not in LIVENESS_EXCLUDED and k != "open"))', 'if k != "open"))', MF),
    "b37-absent-open-counts": (PY, 'isinstance(c, dict) and c.get("open") is False', 'isinstance(c, dict) and c.get("open") is not True', MF),
    "b37-kind-ignored": (PY, 'return (r.get("kind") == "would_enqueue" and isinstance(c, dict) and c.get("open") is False', 'return (isinstance(c, dict) and c.get("open") is False', MF),
    "b37-strict-row-dropped": (PY, "return strict or merged_first_row(r, pull)", "return merged_first_row(r, pull)", MF),
    "b37-pull-never-passed": (PY, "mergeable_row(r, pull_of(r))", "mergeable_row(r)", MF),
    "b37-pr-number-unguarded": (PY, 'if type(r.get("pr")) is int else None', "if True else None", MF),
    "b37-merged-first-uncounted": (PY, "merged_first = sum(1 for r in mergeable if open_only_false(r))", "merged_first = 0", MF),
    "b37-unread-uncounted": (PY, "unread = sum(1 for r in in_window if open_only_false(r) and not isinstance(pull_of(r), dict))", "unread = 0", MF),
    "b37-line-split-dropped": (PY, "(merged_first={lv['merged_first']}\"", "(\"", MF),
    "b37-line-unread-silent": (PY, 'if lv["merged_first_unread"] else ""', 'if False else ""', MF),
}
