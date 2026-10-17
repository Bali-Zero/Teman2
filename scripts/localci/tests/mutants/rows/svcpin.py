"""A bump carries its own matrix pin: the candidate-vs-candidate comparison of candidate_pin_follow (runner.py)."""
from merger_mutants import CQ_T, RUNNER as PY

SVC = tuple(f"{CQ_T}::{n}" for n in (
    "test_a_dependabot_bump_that_carries_its_matrix_pin_is_planned", "test_a_bump_without_its_matrix_pin_is_refused_so_main_never_diverges_from_the_matrix",
    "test_a_matrix_pin_without_the_workflow_following_is_refused", "test_a_new_pin_that_is_a_movable_tag_is_refused_even_when_both_files_agree",
    "test_a_changed_action_input_without_the_matrix_with_pin_is_refused", "test_an_unreadable_candidate_matrix_cannot_have_its_pins_compared",
    "test_a_candidate_that_touches_neither_file_is_not_compared", "test_a_candidate_matrix_that_drops_a_pin_is_refused",
    "test_a_pin_the_candidate_adds_must_agree_with_the_candidate_workflow", "test_a_non_string_uses_is_described_by_type_never_echoed",
    "test_a_pin_with_a_trailing_newline_is_not_an_immutable_ref"))
USES = 'if ws.get("uses") != ms["uses_pin"]:\n                    seen ='

ROWS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "svcpin-uses-follow-ignored": (PY, USES, 'if False:\n                    seen =', SVC),
    "svcpin-with-follow-ignored": (PY, 'if isinstance(ms.get("with_pin"), dict) and _squashed(ws.get("with")) != _squashed(ms["with_pin"]):', "if False:", SVC),
    "svcpin-mutable-ref-accepted": (PY, 'and not PIN_REF.fullmatch(ms["uses_pin"]):', "and False:", SVC),
    "svcpin-ref-prefix-only": (PY, r'PIN_REF = re.compile(r"[^@\s]+@[0-9a-f]{40}")', r'PIN_REF = re.compile(r"[^@\s]+@[0-9a-f]{4}")', SVC),
    "svcpin-unreadable-is-agreement": (PY, 'return f"candidate workflow/matrix unreadable as data ({type(e).__name__}): its pins cannot be compared"', "return None", SVC),
    "svcpin-changed-files-skipped": (PY, "    if all(a == b for a, b in blobs.values()) or (not base_pins and blobs[mrel][0] == blobs[mrel][1]):\n        return None\n", "    return None\n", SVC),
    "svcpin-dropped-pin-accepted": (PY, 'if isinstance(bms.get("uses_pin"), str) and not isinstance(ms.get("uses_pin"), str):', "if False:", SVC),
    "svcpin-added-pin-unchecked": (PY, "for jid, step in [*base_pins, *(k for k in cand_pins if k not in base_pins)]:", "for jid, step in [*base_pins]:", SVC),
    "svcpin-newline-ref-accepted": (PY, 'not PIN_REF.fullmatch(ms["uses_pin"])', 'not PIN_REF.match(ms["uses_pin"])', SVC),
    "svcpin-uses-value-echoed": (PY, 'seen = ws["uses"][:120] if isinstance(ws.get("uses"), str) else f"a {type(ws.get(\'uses\')).__name__}"', "seen = ws.get('uses')", SVC),
    "svcpin-second-loader": (PY, "parity_yaml(blobs[r][1] or b\"\", r) for r in (wf, mrel)", "__import__('yaml').safe_load(blobs[r][1] or b\"\") for r in (wf, mrel)", SVC),
}
