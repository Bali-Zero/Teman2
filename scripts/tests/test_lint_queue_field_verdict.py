"""Tests for scripts/ci/lint_queue_field_verdict.py.

Guilt+innocence per cicatrix-superscar.md #3 ("nessuna guardia mergiata
senza un test di innocenza E di colpevolezza"): every shape this lint
matches gets a guilt fixture (unaware -> violation) and an innocence
fixture (same shape, but aware -> clean), PLUS a guilt+innocence pair on
the allowlist tripwire itself, PLUS a guilt+innocence pair on the real
repo tree -- this is the guard's own proof, the same discipline
`test_check_required_workflow_conformance.py` applies to its sibling
guard.

MEASURED (2026-08-29): 22 tracked files in this repo mention
`autoMergeRequest`/`isInMergeQueue`/`mergeQueueEntry`; exactly 2 match this
lint's null-comparison shape (`scripts/queue_unstick.py`, aware, and
`scripts/ci/queue_rearm_population.sh`, which carried the sole live
allowlist entry until 2026-08-31 -- that file grew its own `mergeQueueEntry`
co-occurrence that day (the positive-probe fix for the live #5422 defect
scripts/lint_arm_probe.py documents), clears via awareness now, and the
entry was removed per this lint's own SHRINK-ONLY policy. ALLOWLIST is
empty as of that date; the allowlist-tripwire tests below inject and remove
a synthetic entry via `monkeypatch` so the MECHANISM stays tested without
depending on whichever real file happens to need a waiver today. Two of
those 22 files were near-miss false positives
during authoring -- `scripts/lane_ship.sh`'s prose ("...not armed after gh
pr merge --auto (autoMergeRequest...") and a test fixture's
`! grep -qi "autoMergeRequest"` -- both matched an early, looser
negated-truthy pattern that allowed ANY character as filler between the
negation and the field. The module's NEGATED_TRUTHY_RE filler is a
no-bare-space character class specifically because of this: superscar #3
(guard over-match) is this repo's single most common bug class (nine
prior instances before this lint was even written), and a filler that
lets prose masquerade as a code idiom would have been its tenth.

Run:  python3 -m pytest scripts/tests/test_lint_queue_field_verdict.py -q
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "ci" / "lint_queue_field_verdict.py"
_spec = importlib.util.spec_from_file_location("lint_queue_field_verdict", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _write(tmp_path: Path, name: str, content: str) -> Path:
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# --------------------------------------------------------------------- guilt


def test_guilt_jq_null_comparison_unaware_is_violation(tmp_path):
    """Shape A, the real `scripts/ci/queue_rearm_population.sh` idiom in
    miniature -- a bare jq filter with no queue-awareness marker anywhere
    in the file."""
    f = _write(
        tmp_path,
        "guilt_jq.sh",
        'jq -r \'select(.mergeable=="MERGEABLE" and .autoMergeRequest==null)\'\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1
    assert report["violations"][0]["path"] == "guilt_jq.sh"


def test_guilt_negated_get_unaware_is_violation(tmp_path):
    """Shape B -- `not pr.get("autoMergeRequest")` -- the exact idiom the
    brief names as the one `.get(...)` style that must be caught."""
    f = _write(
        tmp_path,
        "guilt_negated.py",
        'if not pr.get("autoMergeRequest"):\n    alarm("disarmed")\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1
    assert report["violations"][0]["path"] == "guilt_negated.py"


def test_guilt_bang_prefixed_attribute_unaware_is_violation(tmp_path):
    """Shape B's other named example -- `!node.autoMergeRequest` -- no
    `.get(...)` call, bare attribute access."""
    f = _write(tmp_path, "guilt_bang.js", 'if (!node.autoMergeRequest) alarm("disarmed");\n')
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1


def test_guilt_trap10_shape_direct_null_compare_unaware_is_violation(tmp_path):
    """The 'trap-#10' shape from the brief -- `if auto == None:
    print("ARM CONSUMED, re-arm needed")` -- reproduces the historical
    false alarm this lint exists to catch: a null-comparison on the field
    that concludes "re-arm needed" from that alone. Reproduced here
    comparing the field EXPRESSION directly
    (`pr.get("autoMergeRequest") == None`) rather than through an
    intermediate variable named `auto`: a regex-based scanner that traced
    aliasing through an arbitrary variable name would need real dataflow
    analysis, which this lint deliberately is not (see module docstring's
    "WHAT IT CHECKS" -- both shapes require the literal token
    `autoMergeRequest` itself). The disease and the alarmed message are
    reproduced faithfully; only the aliasing is collapsed to keep the
    fixture inside what a textual scanner can actually see."""
    f = _write(
        tmp_path,
        "guilt_trap10.py",
        'if pr.get("autoMergeRequest") == None:\n    print("ARM CONSUMED, re-arm needed")\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1
    assert report["violations"][0]["path"] == "guilt_trap10.py"


def test_guilt_aliased_trap10_intermediate_variable_is_violation(tmp_path):
    """The REAL historical incident shape (PR #5218 review finding): the
    trap-#10 verdict derived through an intermediate variable named `auto`
    rather than comparing the field expression directly. Shapes A/B, which
    require the literal `autoMergeRequest` token at the comparison site,
    do not see this -- this is what Shape C (single-hop alias tracking)
    exists to catch."""
    f = _write(
        tmp_path,
        "guilt_aliased_trap10.py",
        'auto = pr.get("autoMergeRequest")\n'
        'if auto is None:\n    print("ARM CONSUMED, re-arm needed")\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1
    assert report["violations"][0]["path"] == "guilt_aliased_trap10.py"
    assert "auto" in report["violations"][0]["reason"]


def test_guilt_aliased_negated_truthy_via_variable_is_violation(tmp_path):
    """Shape C's negated-truthy sibling: `state = pr.get("autoMergeRequest")`
    then `if not state:` two lines later, same function body."""
    f = _write(
        tmp_path,
        "guilt_aliased_negated.py",
        'state = pr.get("autoMergeRequest")\n'
        'log.debug("checking")\n'
        'if not state:\n    alarm("disarmed")\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1
    assert report["violations"][0]["path"] == "guilt_aliased_negated.py"


# ----------------------------------------------------------------- innocence


def test_innocence_null_comparison_plus_merge_queue_entry_is_clean(tmp_path):
    f = _write(
        tmp_path,
        "innocent_aware.py",
        'if pr.get("autoMergeRequest") is None:\n'
        '    if pr.get("mergeQueueEntry") is None:\n'
        '        alarm("truly disarmed")\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_innocence_null_comparison_plus_waiver_marker_is_clean(tmp_path):
    f = _write(
        tmp_path,
        "innocent_waiver.py",
        "# queue-field-verdict-lint: aware -- awareness documented elsewhere, see runbook\n"
        'if pr.get("autoMergeRequest") is None:\n    alarm("disarmed")\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_innocence_docstring_mention_only_never_matched(tmp_path):
    """A file that merely MENTIONS the field in prose, never compares it,
    must not even register as matched -- not "matched but aware", simply
    out of scope. This is the over-match guard shape the brief names after
    real code: see test_innocence_real_queue_doctor_truthy_check_is_not_flagged
    below for the live-code version of the same guard."""
    f = _write(
        tmp_path,
        "innocent_docstring.py",
        '"""This module discusses autoMergeRequest at length but never\n'
        'compares it to null or None anywhere in code."""\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []
    assert mod.is_matched(f.read_text(encoding="utf-8")) is None


def test_innocence_real_queue_doctor_truthy_check_is_not_flagged():
    """scripts/queue_doctor.py's real code does `if pr.get("autoMergeRequest")`
    -- a plain truthy check, not negated and not a null-comparison -- right
    beside its own `mergeQueue(` GraphQL selection and an explicit comment
    that neither field alone is the state. A bare truthy check on the
    field must never be confused with the negated/null-comparison shapes
    this lint exists to catch; this is the real file the brief names this
    over-match guard after."""
    doctor = REPO_ROOT / "scripts" / "queue_doctor.py"
    assert doctor.exists()
    report = mod.evaluate([str(doctor)], REPO_ROOT)
    assert report["violations"] == []


def test_innocence_no_mention_at_all_is_clean(tmp_path):
    f = _write(tmp_path, "unrelated.py", "def add(a, b):\n    return a + b\n")
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []
    assert report["scanned"] == 1


def test_innocence_prose_near_negation_is_not_matched_as_negated_truthy(tmp_path):
    """Anti-regression for the near-miss found during authoring: prose
    that happens to contain the word "not" within reach of the field name
    must not be read as a negated truthiness test on the field's own
    value. Reproduces `scripts/lane_ship.sh`'s real line verbatim."""
    f = _write(
        tmp_path,
        "prose_not.sh",
        '_die "PR #$PR_NUMBER not armed after gh pr merge --auto '
        '(autoMergeRequest.enabledAt unset AND isInMergeQueue false)" 3\n',
    )
    text = f.read_text(encoding="utf-8")
    assert mod.NEGATED_TRUTHY_RE.search(text) is None


def test_innocence_shell_absence_check_is_not_matched_as_negated_truthy(tmp_path):
    """Reproduces a real test-fixture line verbatim:
    `! grep -qi "autoMergeRequest"` checks a LOG for the string, it is not
    a truthiness test on the field's own GraphQL value."""
    f = _write(tmp_path, "absence_check.sh", '! grep -qi "autoMergeRequest" "$out"\n')
    text = f.read_text(encoding="utf-8")
    assert mod.NEGATED_TRUTHY_RE.search(text) is None


def test_innocence_aliased_usage_after_dedent_is_not_matched(tmp_path):
    """Bounding proof #1: the alias tracker must NOT bleed across a dedent.
    `f()`'s `auto` is the real incident shape; `g()`'s `auto` is an
    unrelated later reuse of the same bare name in a SIBLING function. If
    Shape C tracked the whole file instead of stopping at the dedent, this
    would false-positive on `g()`."""
    f = _write(
        tmp_path,
        "innocent_aliased_dedent.py",
        "def f():\n"
        '    auto = pr.get("autoMergeRequest")\n'
        "    do_a()\n"
        "def g():\n"
        '    auto = "unrelated"\n'
        "    if not auto:\n        handle()\n",
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_innocence_aliased_usage_after_reassignment_is_not_matched(tmp_path):
    """Bounding proof #2: a later reassignment of the SAME name to
    something that no longer mentions the field ends the alias's blame --
    single-hop only, no re-derivation tracking (`x = x or {}` etc.)."""
    f = _write(
        tmp_path,
        "innocent_aliased_reassign.py",
        'auto = pr.get("autoMergeRequest")\n'
        "do_a()\n"
        "auto = compute_something_else()\n"
        "if not auto:\n    handle_something_else()\n",
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_innocence_aliased_usage_beyond_window_is_not_matched(tmp_path):
    """Bounding proof #3: the hard `_ALIAS_WINDOW` cap is real, not
    decorative -- a usage far enough past the assignment (no dedent, no
    reassignment, just distance) at module level must not be attributed to
    the field either. Keeps the tracker from becoming unbounded whole-file
    aliasing by accident."""
    filler = "\n".join(f"noop_{i}()" for i in range(mod._ALIAS_WINDOW + 5))
    f = _write(
        tmp_path,
        "innocent_aliased_far.py",
        f'auto = pr.get("autoMergeRequest")\n{filler}\nif auto is None:\n    alarm("disarmed")\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_innocence_aliased_with_awareness_marker_is_clean(tmp_path):
    """The Shape C hit still routes through the SAME file-wide awareness
    check as Shapes A/B -- an aliased verdict is clean if the file shows
    queue-awareness anywhere, exactly like the direct shapes."""
    f = _write(
        tmp_path,
        "innocent_aliased_aware.py",
        'auto = pr.get("autoMergeRequest")\n'
        'if auto is None:\n'
        '    if pr.get("mergeQueueEntry") is None:\n'
        '        alarm("truly disarmed")\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_innocence_real_merge_queue_watch_alias_idiom_is_not_flagged():
    """The real live-code version of the Shape C idiom:
    `.github/workflows/merge-queue-watch.yml` does `amr =
    pr.get('autoMergeRequest')` then `if amr and amr.get('enabledAt'):` --
    a plain truthy check, never a null-comparison or negated-truthy test on
    `amr`. Asserts BOTH the outcome (clean under `evaluate`) AND the
    mechanism (`find_aliased_hit` finds no hit at all) -- an earlier
    revision of this module's docstring claimed the file "matches but
    clears via awareness", which a cross-family review measured false;
    the file carries `mergeQueueEntry`/`isInMergeQueue` awareness for an
    unrelated reason, but Shape C never matches it in the first place."""
    workflow = REPO_ROOT / ".github" / "workflows" / "merge-queue-watch.yml"
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8")
    assert mod.find_aliased_hit(text) is None
    report = mod.evaluate([str(workflow)], REPO_ROOT)
    assert report["violations"] == []


# ------------------------- Shape C hardening (2026-08-31 cross-family review)


def test_guilt_aliased_type_annotated_assignment_is_violation(tmp_path):
    """Golden rule #5 mandates type hints in this repo -- the incident
    shape written idiomatically for this codebase (`auto: dict | None =
    pr.get("autoMergeRequest")`) must not be invisible just because it
    carries an annotation. Cross-family review finding, reproduced."""
    f = _write(
        tmp_path,
        "guilt_annotated.py",
        'auto: dict | None = pr.get("autoMergeRequest")\n'
        'if auto is None:\n    print("ARM CONSUMED, re-arm needed")\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1


def test_innocence_aliased_annotated_reassignment_is_not_matched(tmp_path):
    """The mirror of the annotated-assignment fix: an ANNOTATED
    reassignment (`auto: str = "unrelated"`) must also count as staling the
    alias, or the alias gets blamed past its own rebinding."""
    f = _write(
        tmp_path,
        "innocent_annotated_reassign.py",
        'auto = pr.get("autoMergeRequest")\n'
        'auto: str = "unrelated"\n'
        'if not auto:\n    handle()\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_innocence_aliased_for_loop_target_shadow_is_not_matched(tmp_path):
    """A `for <alias> in ...` loop rebinds the name just as much as an `=`
    -- a common short alias (`state`) reused as a loop variable a few lines
    later must not be blamed on the field. Cross-family review finding,
    reproduced (`(3, 'if not state:', 'state')` before the fix)."""
    f = _write(
        tmp_path,
        "innocent_for_shadow.py",
        'state = pr.get("autoMergeRequest")\n'
        'for state in other_states:\n'
        '    if not state:\n        continue\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_innocence_for_loop_reading_alias_as_iterable_still_tracks(tmp_path):
    """The mirror-innocence for the for-loop fix: `for x in auto:` READS
    the alias as the iterable -- it must NOT be treated as a rebinding, or
    a genuine later violation on `auto` itself would be wrongly hidden."""
    f = _write(
        tmp_path,
        "guilt_for_reads_alias.py",
        'auto = pr.get("autoMergeRequest")\n'
        'for x in auto:\n'
        '    pass\n'
        'if not auto:\n    handle()\n',
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1


def test_innocence_aliased_def_param_shadow_is_not_matched(tmp_path):
    """A nested function's OWN parameter of the same name is unrelated to
    the outer alias. Cross-family review finding, reproduced
    (`(4, 'if not auto:', 'auto')` before the fix)."""
    f = _write(
        tmp_path,
        "innocent_def_param_shadow.py",
        "def f(pr):\n"
        '    auto = pr.get("autoMergeRequest")\n'
        "    def helper(auto):\n"
        "        if not auto:\n            return\n",
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_guilt_aliased_usage_past_dedented_comment_is_violation(tmp_path):
    """A column-0 comment between the assignment and its usage carries no
    scope semantics and must not abort the scan. Cross-family review
    finding: `find_aliased_hit` returned None here before the fix (the
    dedent check fired on the comment line itself)."""
    f = _write(
        tmp_path,
        "guilt_comment_gap.py",
        "def f(pr):\n"
        '    auto = pr.get("autoMergeRequest")\n'
        "# TODO: rearm check happens below\n"
        "    if auto is None:\n        print(\"ARM CONSUMED, re-arm needed\")\n",
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1


def test_innocence_comment_mentioning_null_check_is_not_a_usage(tmp_path):
    """The over-match mirror of the previous test: a comment that merely
    DISCUSSES the null-check idiom near the alias is prose, not a verdict,
    and must not itself be read as a usage."""
    f = _write(
        tmp_path,
        "innocent_comment_prose.py",
        'auto = pr.get("autoMergeRequest")\n'
        "# note: upstream already handles the auto is None case in mq state\n",
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert report["violations"] == []


def test_guilt_aliased_js_strict_equality_is_violation(tmp_path):
    """Shape C explicitly supports `const|let|var`, which invites JS/TS --
    where `=== null` / `!== null` is the canonical idiom, not `==`/`!=`.
    The alias null-check must accept strict equality too."""
    f = _write(
        tmp_path,
        "guilt_strict_eq.js",
        'const auto = pr.autoMergeRequest;\n'
        "if (auto === null) { alarm('disarmed'); }\n",
    )
    report = mod.evaluate([str(f)], tmp_path)
    assert len(report["violations"]) == 1


def test_innocence_real_lane_ship_alias_idiom_is_not_flagged():
    """Same real-code proof for `scripts/lane_ship.sh`'s `amr = pr.get(
    "autoMergeRequest") or {}` -- `amr` is only ever `.get()`-ed
    afterwards, never null-compared or negated, so (same as the
    merge-queue-watch.yml sibling test above) `find_aliased_hit` finds no
    hit at all; the file's `isInMergeQueue` awareness is real but not why
    this one stays clean."""
    lane_ship = REPO_ROOT / "scripts" / "lane_ship.sh"
    assert lane_ship.exists()
    text = lane_ship.read_text(encoding="utf-8")
    assert mod.find_aliased_hit(text) is None
    report = mod.evaluate([str(lane_ship)], REPO_ROOT)
    assert report["violations"] == []


# ------------------------------------------------------------- allowlist tripwire


# ALLOWLIST is empty on disk (2026-08-31 SHRINK-ONLY removal -- see module
# docstring). These three tests inject a SYNTHETIC entry via `monkeypatch`
# so the tripwire mechanism itself stays covered, independent of whichever
# real file (if any) needs a waiver on a given day. `monkeypatch.setitem`
# restores `mod.ALLOWLIST` to its real (currently empty) state on teardown.
_SUBJECT = "scripts/ci/_test_allowlist_subject.sh"
_ORCHESTRATOR = "scripts/ci/_test_allowlist_orchestrator.sh"


def test_allowlist_tripwire_holds_when_orchestrator_carries_both_substrings(tmp_path, monkeypatch):
    monkeypatch.setitem(
        mod.ALLOWLIST, _SUBJECT,
        {
            "reason": "synthetic subject for this test only",
            "orchestrator": _ORCHESTRATOR,
            "orchestrator_requires": ("mergeQueue(", "already in the queue"),
        },
    )
    _write(tmp_path, _SUBJECT, 'jq -r "select(.autoMergeRequest==null)"\n')
    _write(
        tmp_path,
        _ORCHESTRATOR,
        'inq=$(gh api graphql -f query="{mergeQueue(branch:\\"main\\"){entries}}")\n'
        'case " $inq " in *" $n "*) echo "already in the queue" ;; esac\n',
    )
    report = mod.evaluate([_SUBJECT], tmp_path)
    assert report["violations"] == []
    assert len(report["allowlisted"]) == 1
    assert report["allowlisted"][0]["path"] == _SUBJECT


def test_allowlist_tripwire_breaks_when_subtraction_line_removed(tmp_path, monkeypatch):
    """The orchestrator still fetches the queue snapshot (`mergeQueue(`)
    but the line that subtracts it before acting is gone -- the waiver's
    stated justification no longer holds, so the allowlist entry stops
    silencing the violation instead of silently continuing to."""
    monkeypatch.setitem(
        mod.ALLOWLIST, _SUBJECT,
        {
            "reason": "synthetic subject for this test only",
            "orchestrator": _ORCHESTRATOR,
            "orchestrator_requires": ("mergeQueue(", "already in the queue"),
        },
    )
    _write(tmp_path, _SUBJECT, 'jq -r "select(.autoMergeRequest==null)"\n')
    _write(
        tmp_path,
        _ORCHESTRATOR,
        'inq=$(gh api graphql -f query="{mergeQueue(branch:\\"main\\"){entries}}")\n'
        "# the subtraction line was removed\n",
    )
    report = mod.evaluate([_SUBJECT], tmp_path)
    assert report["allowlisted"] == []
    assert len(report["violations"]) == 1
    assert "no longer hold" in report["violations"][0]["reason"]


def test_allowlist_tripwire_breaks_when_orchestrator_missing_entirely(tmp_path, monkeypatch):
    monkeypatch.setitem(
        mod.ALLOWLIST, _SUBJECT,
        {
            "reason": "synthetic subject for this test only",
            "orchestrator": _ORCHESTRATOR,
            "orchestrator_requires": ("mergeQueue(", "already in the queue"),
        },
    )
    _write(tmp_path, _SUBJECT, 'jq -r "select(.autoMergeRequest==null)"\n')
    # the orchestrator file is deliberately not written.
    report = mod.evaluate([_SUBJECT], tmp_path)
    assert report["allowlisted"] == []
    assert len(report["violations"]) == 1
    assert "no longer hold" in report["violations"][0]["reason"]


def test_allowlist_is_empty_on_disk():
    """SHRINK-ONLY, verified rather than assumed: as of 2026-08-31 nothing
    needs a waiver -- if this ever fails because a new entry was ADDED to
    silence a violation instead of curing it, that is exactly the drift
    the module docstring's ALLOWLIST policy forbids."""
    assert mod.ALLOWLIST == {}


# ------------------------------------------------------------------ empty-set guard


def test_scanning_zero_paths_exits_3_never_0(capsys):
    rc = mod.main(["--paths"])
    captured = capsys.readouterr()
    assert rc == 3, captured.err
    assert "CANNOT VERIFY" in captured.err


def test_missing_git_repo_root_exits_3(tmp_path, capsys):
    """No `.git` at all under repo_root -> `git ls-files` fails -> CANNOT
    VERIFY, never a silent 0-file scan read as clean."""
    rc = mod.main(["--repo-root", str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 3, captured.err
    assert "CANNOT VERIFY" in captured.err


# ------------------------------------------------------------------ live tree


def test_the_real_repo_tree_is_clean_today():
    """The proof this lint ships: run it against the REAL git-tracked
    tree. Fails loudly -- not softened -- if a future file re-derives an
    armed/disarmed verdict from a bare null-comparison on
    `autoMergeRequest` without awareness. This test is what makes the lint
    armed, not just present (cicatrix-superscar.md #2, "esiste != armato")."""
    tracked = mod.git_tracked_files(REPO_ROOT)
    assert tracked is not None, "git ls-files must succeed against the real repo"
    report = mod.evaluate(tracked, REPO_ROOT)
    assert report["scanned"] > 0
    assert report["violations"] == [], f"live repo tree has violations: {report['violations']}"


def test_main_cli_exits_zero_on_the_real_repo_tree(capsys):
    rc = mod.main(["--repo-root", str(REPO_ROOT)])
    captured = capsys.readouterr()
    assert rc == 0, captured.out


def test_selftest_cli_flag_passes(capsys):
    rc = mod.main(["--selftest"])
    captured = capsys.readouterr()
    assert rc == 0, captured.out
    assert "[FAIL]" not in captured.out
