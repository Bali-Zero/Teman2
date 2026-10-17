"""A bump carries its own matrix pin: the candidate-vs-candidate comparison of candidate_pin_follow (runner.py)."""
from merger_mutants import CQ_T, RUNNER as PY

SVC = tuple(f"{CQ_T}::{n}" for n in (
    "test_a_dependabot_bump_that_carries_its_matrix_pin_is_planned", "test_a_bump_without_its_matrix_pin_is_refused_so_main_never_diverges_from_the_matrix",
    "test_a_matrix_pin_without_the_workflow_following_is_refused", "test_a_new_pin_that_is_a_movable_tag_is_refused_even_when_both_files_agree",
    "test_a_changed_action_input_without_the_matrix_with_pin_is_refused", "test_an_unreadable_candidate_matrix_cannot_have_its_pins_compared",
    "test_a_candidate_that_touches_neither_file_is_not_compared", "test_a_candidate_matrix_that_drops_a_pin_is_refused"))
USES = 'if ws.get("uses") != ms["uses_pin"]:\n                    return f"{lab}: the candidate workflow uses'

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "svcpin-uses-follow-ignored": (PY, USES, 'if False:\n                    return f"{lab}: the candidate workflow uses', SVC),
    "svcpin-with-follow-ignored": (PY, "                if _squashed(ws.get(\"with\")) != _squashed(ms[\"with_pin\"]):\n                    return f\"{lab}: the candidate workflow's",
                                   "                if False:\n                    return f\"{lab}: the candidate workflow's", SVC),
    "svcpin-mutable-ref-accepted": (PY, 'and not PIN_REF.match(ms["uses_pin"]):', "and False:", SVC),
    "svcpin-ref-prefix-only": (PY, r'PIN_REF = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")', r'PIN_REF = re.compile(r"^[^@\s]+@[0-9a-f]{4}")', SVC),
    "svcpin-unreadable-is-agreement": (PY, 'return f"candidate workflow/matrix unreadable as data ({type(e).__name__}): its pins cannot be compared"', "return None", SVC),
    "svcpin-changed-files-skipped": (PY, "    if not base_pins or all(a == b for a, b in blobs.values()):\n        return None\n", "    return None\n", SVC),
    "svcpin-dropped-pin-accepted": (PY, 'if not isinstance(ms.get("uses_pin"), str):\n                    return f"{lab}: the candidate matrix no longer pins the action"', "if False:\n                    return None", SVC),
}
