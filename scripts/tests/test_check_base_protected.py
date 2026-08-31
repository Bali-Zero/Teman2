"""Tests for scripts/ci/check_base_protected.py (S5 check-half).

Guilt+innocence per cicatrix-superscar.md #3 ("nessuna guardia senza test di
innocenza E colpevolezza, su entità/intento mai bare-substring") for every
function this module exports, plus the four fixtures the mandate itself
specifies: base main covered -> 0; base feature/x with no ruleset -> 1
(guilt); base feature/x with a covering ruleset -> 0 (innocence); API error
-> 1 with a distinct (BLIND) message.

Run:  python3 -m pytest scripts/tests/test_check_base_protected.py -q
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "ci" / "check_base_protected.py"
_spec = importlib.util.spec_from_file_location("check_base_protected", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)  # type: ignore[union-attr]

MERGE_QUEUE_MAIN = {
    "id": 19779175,
    "name": "merge-queue-main",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
    "rules": [{"type": "merge_queue", "parameters": {}}],
}
COPILOT_REVIEW = {
    "id": 20608865,
    "name": "Copilot review for default branch",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "copilot_code_review", "parameters": {}},
    ],
}
# The two rulesets actually live in Bali-Zero/Teman2 as of 2026-08-27 — neither
# covers refs/heads/feature/*, which is precisely the gap this check exists
# to close. Used verbatim as the "real world, uncured" fixture below.
REAL_RULESETS_TODAY = [MERGE_QUEUE_MAIN, COPILOT_REVIEW]

MIN_CONTEXTS = {
    "Backend Tests (Python)",
    "Harness floor recompute",
    "R1 gate — adversarial review present",
    "Detect Secrets",
    "actionlint — workflow schema + expression gate",
}


def _covering_ruleset(contexts: set[str] | None, pattern: str = "refs/heads/feature/*") -> dict:
    rules: list[dict] = []
    if contexts is not None:
        rules.append(
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [{"context": c} for c in contexts]
                },
            }
        )
    return {
        "id": 1,
        "name": "integration-branch-protection",
        "target": "branch",
        "enforcement": "active",
        "conditions": {"ref_name": {"include": [pattern], "exclude": []}},
        "rules": rules,
    }


# ------------------------------------------------------------- _pattern_matches


def test_innocence_all_token_matches_anything():
    assert mod._pattern_matches("~ALL", "anything-at-all", "main") is True


def test_innocence_default_branch_token_matches_default_only():
    assert mod._pattern_matches("~DEFAULT_BRANCH", "main", "main") is True


def test_guilt_default_branch_token_does_not_match_non_default():
    assert mod._pattern_matches("~DEFAULT_BRANCH", "feature/x", "main") is False


def test_innocence_glob_matches_full_ref():
    assert mod._pattern_matches("refs/heads/feature/*", "feature/kb-current", "main") is True


def test_guilt_glob_does_not_match_unrelated_ref():
    assert mod._pattern_matches("refs/heads/feature/*", "ops/seat6", "main") is False


def test_guilt_single_star_does_not_cross_a_slash():
    # The real bug a cross-family refuter found (2026-08-27), verified
    # against GitHub's own docs: a single `*` does NOT cross `/` (Ruby
    # File.fnmatch with FNM_PATHNAME). Python's stdlib `fnmatch` module has no
    # such mode — its `*` crosses `/` freely — so using it directly made a
    # ruleset scoped to `refs/heads/feature/*` falsely appear to cover a
    # NESTED branch `feature/a/b`, which GitHub itself would NOT apply that
    # ruleset to. This must be False, not True.
    assert mod._pattern_matches("refs/heads/feature/*", "feature/a/b", "main") is False


def test_innocence_github_docs_own_example_single_star():
    # GitHub's own documented example, verbatim: "qa/* will match all
    # branches beginning with qa/ and containing a single slash, but will
    # not match qa/foo/bar."
    assert mod._pattern_matches("refs/heads/qa/*", "qa/foo", "main") is True
    assert mod._pattern_matches("refs/heads/qa/*", "qa/foo/bar", "main") is False


def test_innocence_github_docs_own_example_double_star():
    # GitHub's own documented example, verbatim: "qa/**/* ... would match,
    # for example, qa/foo/bar/foobar/hello-world."
    assert (
        mod._pattern_matches("refs/heads/qa/**/*", "qa/foo/bar/foobar/hello-world", "main")
        is True
    )


# ------------------------------------------------------------- ruleset_covers_ref


def test_guilt_wrong_target_never_covers():
    rs = _covering_ruleset(MIN_CONTEXTS)
    rs["target"] = "tag"
    assert mod.ruleset_covers_ref(rs, "feature/kb-current", "main") is False


def test_guilt_disabled_enforcement_never_covers():
    rs = _covering_ruleset(MIN_CONTEXTS)
    rs["enforcement"] = "disabled"
    assert mod.ruleset_covers_ref(rs, "feature/kb-current", "main") is False


def test_guilt_evaluate_mode_never_counts_as_covering():
    # GitHub's dry-run/monitor posture — real, but must not certify a base.
    rs = _covering_ruleset(MIN_CONTEXTS)
    rs["enforcement"] = "evaluate"
    assert mod.ruleset_covers_ref(rs, "feature/kb-current", "main") is False


def test_guilt_excluded_ref_never_covers():
    rs = _covering_ruleset(MIN_CONTEXTS)
    rs["conditions"]["ref_name"]["exclude"] = ["refs/heads/feature/kb-current"]
    assert mod.ruleset_covers_ref(rs, "feature/kb-current", "main") is False


def test_innocence_matching_active_branch_ruleset_covers():
    rs = _covering_ruleset(MIN_CONTEXTS)
    assert mod.ruleset_covers_ref(rs, "feature/kb-current", "main") is True


def test_innocence_real_rulesets_cover_main_via_default_branch_token():
    assert mod.ruleset_covers_ref(COPILOT_REVIEW, "main", "main") is True


def test_guilt_real_rulesets_today_cover_nothing_under_feature():
    # This IS the live gap the mandate measured: 0 of the 2 real rulesets
    # cover refs/heads/feature/*.
    assert not any(
        mod.ruleset_covers_ref(rs, "feature/kb-current", "main") for rs in REAL_RULESETS_TODAY
    )


# ------------------------------------------------------ required_status_check_contexts


def test_guilt_ruleset_with_no_such_rule_returns_none():
    # merge-queue-main's real, live shape: one rule, type merge_queue, no
    # required_status_checks rule at all.
    assert mod.required_status_check_contexts(MERGE_QUEUE_MAIN) is None


def test_innocence_ruleset_with_the_rule_returns_its_contexts():
    rs = _covering_ruleset({"A", "B"})
    assert mod.required_status_check_contexts(rs) == {"A", "B"}


# --------------------------------------------------------- normalize_ref / suggest_pattern


def test_innocence_normalize_ref_strips_full_ref_prefix_when_asserted_full():
    assert mod.normalize_ref("refs/heads/main", is_full_ref=True) == "main"


def test_innocence_normalize_ref_passes_through_short_name():
    assert mod.normalize_ref("feature/kb-current", is_full_ref=False) == "feature/kb-current"


def test_guilt_normalize_ref_never_strips_a_short_name_that_looks_like_a_full_ref():
    # The real bypass a cross-family refuter found (2026-08-27): a branch can
    # legitimately be NAMED 'refs/heads/main' (git allows slashes in branch
    # names). When the caller correctly asserts this is a SHORT name
    # (is_full_ref=False, e.g. it came from pull_request's base.ref, which
    # GitHub always populates as a short name), it must be used verbatim —
    # never silently collapsed into 'main' just because it starts with that
    # literal text.
    assert (
        mod.normalize_ref("refs/heads/main", is_full_ref=False) == "refs/heads/main"
    )


def test_innocence_suggest_pattern_widens_to_the_branch_family():
    assert mod.suggest_pattern("feature/kb-current") == "feature/*"
    assert mod.suggest_pattern("ops/seat6-consumers") == "ops/*"


def test_innocence_suggest_pattern_passes_through_single_segment():
    assert mod.suggest_pattern("develop") == "develop"


# --------------------------------------------------------------------------- evaluate()
#
# The four fixtures the mandate itself specifies, verbatim.


def test_innocence_base_main_covered():
    code, message = mod.evaluate("main", "main", REAL_RULESETS_TODAY, MIN_CONTEXTS)
    assert code == 0
    assert "OK" in message


def test_guilt_base_feature_x_with_no_ruleset():
    code, message = mod.evaluate(
        "feature/kb-current", "main", REAL_RULESETS_TODAY, MIN_CONTEXTS
    )
    assert code == 1
    assert message.startswith("UNPROTECTED:")
    assert "feature/kb-current" in message
    # Names the exact operator command, print-only by default.
    assert "setup_merge_queue_ruleset.sh --branch-pattern 'feature/*' --apply" in message


def test_innocence_base_feature_x_with_a_covering_ruleset():
    rulesets = REAL_RULESETS_TODAY + [_covering_ruleset(MIN_CONTEXTS)]
    code, message = mod.evaluate("feature/kb-current", "main", rulesets, MIN_CONTEXTS)
    assert code == 0
    assert "OK" in message


def test_guilt_evaluate_via_merge_group_full_ref_form():
    # merge_group's base_ref is a FULL ref, not a short name — asserted via
    # is_full_ref=True, never guessed from the string.
    code, _ = mod.evaluate(
        "refs/heads/feature/kb-current",
        "main",
        REAL_RULESETS_TODAY,
        MIN_CONTEXTS,
        is_full_ref=True,
    )
    assert code == 1


def test_innocence_evaluate_merge_group_full_ref_main_short_circuits():
    code, message = mod.evaluate(
        "refs/heads/main", "main", REAL_RULESETS_TODAY, MIN_CONTEXTS, is_full_ref=True
    )
    assert code == 0
    assert "OK" in message


def test_guilt_evaluate_a_branch_literally_named_refs_heads_main_is_not_exempted():
    # The real bypass, at the evaluate() level: a PULL_REQUEST base (always a
    # SHORT name per GitHub's contract, is_full_ref=False) whose short name
    # happens to literally BE the text 'refs/heads/main' must still be
    # treated as a non-default base needing real coverage — not silently
    # exempted as if it were main itself.
    code, message = mod.evaluate(
        "refs/heads/main",
        "main",
        REAL_RULESETS_TODAY,
        MIN_CONTEXTS,
        is_full_ref=False,
    )
    assert code == 1
    assert message.startswith("UNPROTECTED:")


# ---------------------------------------------------- partial coverage (declared, not obvious)


def test_guilt_covering_ruleset_missing_some_pinned_contexts():
    partial = MIN_CONTEXTS - {"Detect Secrets"}
    rulesets = REAL_RULESETS_TODAY + [_covering_ruleset(partial)]
    code, message = mod.evaluate("feature/kb-current", "main", rulesets, MIN_CONTEXTS)
    assert code == 1
    assert "Detect Secrets" in message


def test_guilt_covering_ruleset_with_no_required_status_checks_rule_at_all():
    # Ref-matches, but carries e.g. only `deletion` — same shape as the real
    # Copilot-review ruleset, just scoped to feature/* instead of main.
    rs = _covering_ruleset(contexts=None)
    rulesets = REAL_RULESETS_TODAY + [rs]
    code, message = mod.evaluate("feature/kb-current", "main", rulesets, MIN_CONTEXTS)
    assert code == 1
    assert "carry no required_status_checks" in message


def test_innocence_union_across_two_rulesets_satisfies_the_minimum():
    # Real GitHub semantics: rulesets are cumulative. Split the 5 pinned
    # contexts across two separate covering rulesets — union must still pass.
    half_a = _covering_ruleset({"Backend Tests (Python)", "Harness floor recompute"})
    half_a["id"] = 2
    half_b = _covering_ruleset(MIN_CONTEXTS - {"Backend Tests (Python)", "Harness floor recompute"})
    half_b["id"] = 3
    rulesets = REAL_RULESETS_TODAY + [half_a, half_b]
    code, _ = mod.evaluate("feature/kb-current", "main", rulesets, MIN_CONTEXTS)
    assert code == 0


# ------------------------------------------------------- load_minimum_contexts (BLIND path)


def test_guilt_blind_on_missing_min_contexts_file(tmp_path):
    assert mod.load_minimum_contexts(tmp_path / "does-not-exist.json") is None


def test_guilt_blind_on_empty_min_contexts_list(tmp_path):
    path = tmp_path / "contexts.json"
    path.write_text(json.dumps({"minimum_contexts": []}), encoding="utf-8")
    assert mod.load_minimum_contexts(path) is None


def test_innocence_the_real_shipped_min_contexts_file_loads():
    loaded = mod.load_minimum_contexts(mod.DEFAULT_MIN_CONTEXTS_JSON)
    assert loaded == MIN_CONTEXTS


# --------------------------------------------------------------------------- CLI main()


def _write_rulesets(tmp_path: Path, rulesets: list[dict]) -> Path:
    path = tmp_path / "rulesets.json"
    path.write_text(json.dumps(rulesets), encoding="utf-8")
    return path


def test_main_cli_exits_zero_for_the_default_branch_with_no_network_call(monkeypatch, capsys):
    # base == default branch short-circuits BEFORE ever calling `gh` — this
    # is real end-to-end CLI + the REAL shipped minimum-contexts file, and it
    # must stay deterministic in CI with zero network access. Proven, not
    # just claimed: `_gh` is monkeypatched to explode if it's ever invoked.
    def _gh_must_not_be_called(args):
        raise AssertionError(f"_gh() was called for the default-branch base: {args}")

    monkeypatch.setattr(mod, "_gh", _gh_must_not_be_called)
    rc = mod.main(["--base-ref", "main", "--repo", "Bali-Zero/Teman2", "--default-branch", "main"])
    captured = capsys.readouterr()
    assert rc == 0, captured.out


def test_guilt_fetch_live_rulesets_returns_none_on_a_partial_list_detail_failure(monkeypatch):
    # list succeeds (2 summaries), but the SECOND detail GET fails — must
    # return None (BLIND), never a partial 1-item list that could silently
    # drop a real covering ruleset from consideration.
    calls = {"n": 0}

    def _gh_partial_failure(args):
        if args == ["api", "repos/Bali-Zero/Teman2/rulesets"]:
            return True, json.dumps([{"id": 1}, {"id": 2}])
        calls["n"] += 1
        if calls["n"] == 1:
            return True, json.dumps({"id": 1, "name": "a"})
        return False, ""  # second detail GET fails

    monkeypatch.setattr(mod, "_gh", _gh_partial_failure)
    assert mod.fetch_live_rulesets("Bali-Zero/Teman2") is None


def test_main_cli_guilt_feature_base_with_no_covering_ruleset(tmp_path, capsys):
    rulesets_path = _write_rulesets(tmp_path, REAL_RULESETS_TODAY)
    rc = mod.main(
        [
            "--base-ref", "feature/kb-current",
            "--repo", "Bali-Zero/Teman2",
            "--default-branch", "main",
            "--rulesets-json", str(rulesets_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "UNPROTECTED" in captured.out


def test_main_cli_innocence_feature_base_with_a_covering_ruleset(tmp_path, capsys):
    rulesets_path = _write_rulesets(
        tmp_path, REAL_RULESETS_TODAY + [_covering_ruleset(MIN_CONTEXTS)]
    )
    rc = mod.main(
        [
            "--base-ref", "feature/kb-current",
            "--repo", "Bali-Zero/Teman2",
            "--default-branch", "main",
            "--rulesets-json", str(rulesets_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0, captured.out
    assert "OK" in captured.out


def test_main_cli_api_error_is_blind_with_a_distinct_message(monkeypatch, capsys):
    # Hermetic: force every `gh` invocation to fail rather than depending on
    # a real network 404 — deterministic, no live-network dependency in CI.
    monkeypatch.setattr(mod, "_gh", lambda args: (False, ""))
    rc = mod.main(
        [
            "--base-ref", "feature/x",
            "--repo", "Bali-Zero/Teman2",
            "--default-branch", "main",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    # Distinct from the UNPROTECTED guilt message — same exit code, per the
    # mandate's own spec ("both are fail-closed"), distinguished by prefix.
    assert "BLIND" in captured.out
    assert "UNPROTECTED" not in captured.out


def test_main_cli_blind_on_unreadable_min_contexts_json(tmp_path, capsys):
    rc = mod.main(
        [
            "--base-ref", "main",
            "--repo", "Bali-Zero/Teman2",
            "--default-branch", "main",
            "--min-contexts-json", str(tmp_path / "nope.json"),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "BLIND" in captured.out


def test_main_cli_base_ref_full_strips_the_merge_group_style_ref(capsys):
    rc = mod.main(
        [
            "--base-ref", "refs/heads/main",
            "--base-ref-full",
            "--repo", "Bali-Zero/Teman2",
            "--default-branch", "main",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0, captured.out


def test_main_cli_without_base_ref_full_a_branch_named_refs_heads_main_is_not_exempted(
    tmp_path, capsys
):
    # End-to-end CLI proof of the fixed bypass: omitting --base-ref-full (the
    # pull_request/default shape) means 'refs/heads/main' is a literal SHORT
    # branch name, not main itself, and must require real coverage.
    rulesets_path = _write_rulesets(tmp_path, REAL_RULESETS_TODAY)
    rc = mod.main(
        [
            "--base-ref", "refs/heads/main",
            "--repo", "Bali-Zero/Teman2",
            "--default-branch", "main",
            "--rulesets-json", str(rulesets_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "UNPROTECTED" in captured.out


def test_main_cli_blind_on_rulesets_json_not_an_array(tmp_path, capsys):
    bad = tmp_path / "rulesets.json"
    bad.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    rc = mod.main(
        [
            "--base-ref", "feature/x",
            "--repo", "Bali-Zero/Teman2",
            "--default-branch", "main",
            "--rulesets-json", str(bad),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "BLIND" in captured.out
