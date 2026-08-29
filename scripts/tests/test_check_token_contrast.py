"""Guilt AND innocence for scripts/check_token_contrast.py against the real
shipped design/tokens/merah-putih.tokens.json (PR-2 of
docs/plans/2026-08-29-beyond-sota-craft-wave/L11-product-ux-visual-design.md).

Every test that needs a MUTATED token file writes its own copy under
`tmp_path` — the shipped file is only ever read, never edited by a test
(family #9: two writers on one artifact, here a test run and a human).

Two distinct failure modes are drilled separately because they are
genuinely different defects with the same symptom (a claim that no longer
matches reality):

  * Guilt A — the `$value` (hex) drifts away from a claim that was true when
    written. The color moved; the comment is now a lie about the color.
  * Guilt B — the claimed `ratio` is hand-edited while the hex stays put.
    The color is fine; the comment is now a lie about a fact that never
    changed.

Both must be caught by the SAME recomputation, because the checker cannot
know which side is "true" — only that they disagree.

Guilt C is a third, independent defect: a claim that is internally
CONSISTENT (claimed ratio == recomputed ratio) but still fails the WCAG
floor its own declared `duty` demands. Drift-checking alone would wave this
through; the checker must also gate on the floor.

Innocence B exists because a checker naive about `duty` would "fix" this
file by rejecting `hairline` (1.21:1) and the `whatsapp` white-on-icon claim
(1.98:1) — both real, both correct, both legitimately below the text floor
because neither carries a text (or non-text) duty. A checker that fails
these is worse than none: someone would "fix" the design to please it.

A cross-family adversarial review of check_token_contrast.py found five
more real holes, each drilled below in its own class:

  * REQUIRED-CLAIMS FLOOR (TestRequiredClaimsFloor) — a token can be
    silenced by emptying its claims list (or deleting it outright) while
    drifting its hex in the same edit; the drift/floor checks above have
    nothing to recompute for a claim-less token, so the run stays quiet.
    `check_required_claims()` is the independent-of-content answer.
  * FLOOR PRECISION (TestFloorComparisonHonorsPublicationPrecision) — the
    floor check used to compare a raw, un-rounded float against the floor
    with a near-zero epsilon, disagreeing with the drift check's own ±0.02
    tolerance for this file's 2-decimal publication convention. A claim
    whose true ratio is 4.4951, correctly published as 4.50, cleared drift
    and then failed the floor outright — a false red on a correct claim.
  * TAUTOLOGICAL TEST (removed) — the old
    `test_every_against_reference_resolves` asserted only
    `isinstance(violations, list)`, true on any non-raising run whether or
    not an unresolved alias was silently swallowed. Replaced below with a
    test that actually sabotages a real alias and asserts the RAISE.
  * UNBOUNDED --tolerance (TestToleranceIsBounded) — `--tolerance 99` used
    to make the gate green by construction now that this script is a CI
    gate; `main()` refuses anything outside [0, MAX_TOLERANCE].
  * BOOLEAN RATIO (TestBooleanRatioIsRejected) — `isinstance(x, (int,
    float))` admits `True`/`False` because bool subclasses int in Python;
    a JSON `"ratio": true` used to pass as the number 1.
  * ALIAS DEPTH (TestAliasChainDepthIsBounded) — a very long, non-cyclic
    alias chain (never revisiting a path, so the existing cycle guard
    cannot see it) used to raise a bare RecursionError instead of the
    documented TokenContrastError.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# Imported as `from scripts.check_token_contrast import ...` — a PACKAGE
# import, not the importlib.util.spec_from_file_location loading that
# scripts/tests/test_adversarial_review_gate.py and
# scripts/tests/test_pending_arms_report.py document and use ("because
# scripts/ is a flat bag of standalone tools, not a Python package").
# Both conventions are live in this same test directory (as of this file,
# ~60 files use this package-style import, ~150 use importlib) and BOTH
# work, for different reasons: this one resolves because `scripts/` has no
# `__init__.py` and is therefore a PEP-420 namespace package, resolvable
# from the repo root the moment the repo root is on `sys.path` — which it
# is here, because every invocation in this file's own module docstring
# and in this repo's CI runs pytest as `python -m pytest` FROM THE REPO
# ROOT, and `-m` inserts the current working directory as `sys.path[0]`.
# Change the invocation to a bare `pytest scripts/tests/...` (no `-m`, or
# run from a different cwd) and this import would break while the
# importlib-based siblings would not — that fragility, not indecision, is
# the actual argument for standardising on importlib repo-wide; it is not
# fixed in THIS PR, which only touches check_token_contrast.py's own
# defects, but this comment exists so the two conventions are never
# silently contradictory again.
from scripts.check_token_contrast import (
    DEFAULT_TOKENS_PATH,
    DUTY_FLOORS,
    MAX_ALIAS_DEPTH,
    MAX_TOLERANCE,
    REQUIRED_CLAIM_PATHS,
    TokenContrastError,
    check,
    check_required_claims,
    collect_claims,
    contrast_ratio,
    main,
)


def _load_real_tree() -> dict[str, Any]:
    return json.loads(DEFAULT_TOKENS_PATH.read_text(encoding="utf-8"))


def _write_tree(tmp_path: Path, tree: dict[str, Any]) -> Path:
    out = tmp_path / "tokens.json"
    out.write_text(json.dumps(tree, indent=2), encoding="utf-8")
    return out


# --------------------------------------------------------------- innocence


class TestInnocenceShippedFile:
    def test_shipped_file_exists_and_is_valid_json(self) -> None:
        assert DEFAULT_TOKENS_PATH.is_file(), DEFAULT_TOKENS_PATH
        _load_real_tree()  # raises if not valid JSON

    def test_every_claim_recomputes_clean(self) -> None:
        tree = _load_real_tree()
        violations, _notices = check(tree)
        assert violations == [], "\n".join(violations)

    def test_claim_count_is_pinned(self) -> None:
        """28 claims: the 26 pairs R4 §3 states exactly, plus the retired
        token's 2 self-computed pairs (R4 gives only a 3.20-3.39 RANGE
        across three papers for retired-vs-carta, not an exact per-carta
        value — this file computes and cites its own carta-specific
        number instead of copying an approximation).

        Update this pin deliberately (with a one-line reason in the PR) if
        a future PR adds or removes a measured pair — an unexplained drift
        in this count is exactly the silent-shrink class W99 was about.
        """
        assert len(collect_claims(_load_real_tree())) == 28

    def test_cli_exits_zero_on_the_shipped_file(self, capsys) -> None:
        rc = main([])
        out = capsys.readouterr().out
        assert rc == 0
        assert "OK" in out

    def test_module_selftest_passes(self) -> None:
        rc = main(["--selftest"])
        assert rc == 0


class TestInnocenceBLowRatioDutiesPass:
    """hairline (decorative, 1.21:1) and the white-on-whatsapp claim
    (icon-only, 1.98:1) are real, correct, and MUST pass — see module
    docstring above."""

    def test_hairline_is_decorative_with_no_floor_and_passes(self) -> None:
        tree = _load_real_tree()
        hairline = tree["color"]["boundary"]["hairline"]
        claims = hairline["$extensions"]["com.balizero.contrast"]
        assert len(claims) == 1
        assert claims[0]["duty"] == "decorative"
        assert claims[0]["ratio"] < 3.0  # fails even the lighter non-text floor
        assert DUTY_FLOORS["decorative"] is None
        violations, notices = check(tree)
        assert violations == []
        assert any("hairline" in n and "decorative" in n for n in notices)

    def test_whatsapp_white_on_is_icon_only_with_no_floor_and_passes(self) -> None:
        tree = _load_real_tree()
        elevated = tree["color"]["ground"]["elevated"]
        claims = elevated["$extensions"]["com.balizero.contrast"]
        whatsapp_claim = next(
            c for c in claims if c["against"] == "{color.state.whatsapp}"
        )
        assert whatsapp_claim["duty"] == "icon-only"
        assert whatsapp_claim["ratio"] < 4.5  # fails the text floor outright
        assert DUTY_FLOORS["icon-only"] is None
        violations, notices = check(tree)
        assert violations == []
        assert any("whatsapp" in n and "icon-only" in n for n in notices)

    def test_a_checker_naive_about_duty_would_wrongly_fail_these(self) -> None:
        """Mutation proof that the pass above is duty-driven, not a blanket
        exemption for low numbers: relabeling hairline's duty to "text"
        (hex and claimed ratio both UNCHANGED) must turn it red.
        """
        tree = _load_real_tree()
        tree["color"]["boundary"]["hairline"]["$extensions"][
            "com.balizero.contrast"
        ][0]["duty"] = "text"
        violations, _notices = check(tree)
        assert len(violations) == 1
        assert "color.boundary.hairline" in violations[0]
        assert "duty=text" in violations[0]


# --------------------------------------------------------------------- guilt


class TestGuiltATamperedHex:
    """The hex changes; the comment (claimed ratio) still says the old
    truth."""

    def test_check_flags_the_tampered_token_by_path(self) -> None:
        tree = _load_real_tree()
        # ink vs carta is claimed 14.79:1 — collapse ink onto carta's own
        # hex so the real pair now contrasts at ~1:1.
        tree["color"]["text"]["ink"]["$value"] = tree["color"]["ground"]["carta"][
            "$value"
        ]
        violations, _notices = check(tree)
        assert len(violations) >= 1
        assert any("color.text.ink" in v for v in violations)
        # message shows both sides of the disagreement, not just a verdict
        hit = next(v for v in violations if "color.text.ink" in v)
        assert "claimed 14.79" in hit
        assert "recomputed" in hit

    def test_cli_exits_nonzero_on_a_scratch_copy(self, tmp_path, capsys) -> None:
        tree = _load_real_tree()
        tree["color"]["text"]["ink"]["$value"] = "#ffffff"  # == elevated, ~1:1 vs itself pairs
        path = _write_tree(tmp_path, tree)
        rc = main(["--path", str(path)])
        err = capsys.readouterr().err
        assert rc == 1
        assert "color.text.ink" in err

    def test_the_shipped_file_is_unaffected(self) -> None:
        """The tests above mutate an in-memory copy / a tmp_path file only
        — re-read the real file fresh and confirm it never moved."""
        violations, _notices = check(_load_real_tree())
        assert violations == []


class TestGuiltBTamperedClaimedRatio:
    """The hex is untouched; only the CLAIMED ratio (the comment) is
    edited — the reverse direction of Guilt A, caught by the same
    recomputation."""

    def test_check_flags_a_hand_edited_ratio(self) -> None:
        tree = _load_real_tree()
        tree["color"]["text"]["ink-soft"]["$extensions"]["com.balizero.contrast"][
            0
        ]["ratio"] = 2.0  # true value is ~7.07
        violations, _notices = check(tree)
        assert len(violations) == 1
        assert "color.text.ink-soft" in violations[0]
        assert "claimed 2.00" in violations[0]

    def test_cli_exits_nonzero_naming_the_token(self, tmp_path, capsys) -> None:
        tree = _load_real_tree()
        tree["color"]["red"]["merah"]["$extensions"]["com.balizero.contrast"][0][
            "ratio"
        ] = 20.0  # true value is ~5.44
        path = _write_tree(tmp_path, tree)
        rc = main(["--path", str(path)])
        err = capsys.readouterr().err
        assert rc == 1
        assert "color.red.merah" in err
        assert "claimed 20.00" in err

    def test_the_shipped_file_is_unaffected(self) -> None:
        violations, _notices = check(_load_real_tree())
        assert violations == []


class TestGuiltCInternallyConsistentButFailsFloor:
    """A claim is not a drift defect: hex and claimed ratio AGREE with each
    other, but the color genuinely fails the WCAG floor its duty demands."""

    def test_a_standalone_failing_text_claim_is_rejected(self) -> None:
        fg, bg = "#c8c8c8", "#ffffff"
        real_ratio = round(contrast_ratio(fg, bg), 2)
        assert real_ratio < 4.5, "fixture must genuinely fail the text floor"
        tree = {
            "color": {
                "white": {"$value": bg},
                "pale": {
                    "$value": fg,
                    "$extensions": {
                        "com.balizero.contrast": [
                            {
                                "against": "{color.white}",
                                "ratio": real_ratio,
                                "duty": "text",
                            }
                        ]
                    },
                },
            }
        }
        violations, _notices = check(tree)
        assert len(violations) == 1
        assert "color.pale" in violations[0]
        assert "duty=text" in violations[0]
        assert "4.5" in violations[0]

    def test_cli_exits_nonzero_on_the_same_fixture(self, tmp_path, capsys) -> None:
        fg, bg = "#c8c8c8", "#ffffff"
        real_ratio = round(contrast_ratio(fg, bg), 2)
        tree = {
            "color": {
                "white": {"$value": bg},
                "pale": {
                    "$value": fg,
                    "$extensions": {
                        "com.balizero.contrast": [
                            {
                                "against": "{color.white}",
                                "ratio": real_ratio,
                                "duty": "text",
                            }
                        ]
                    },
                },
            }
        }
        path = _write_tree(tmp_path, tree)
        rc = main(["--path", str(path)])
        err = capsys.readouterr().err
        assert rc == 1
        assert "color.pale" in err

    def test_the_shipped_file_has_zero_floor_failures(self) -> None:
        """The real file must never contain a Guilt-C-shaped token — every
        claim with a floor-bearing duty (text/large-text/non-text) must
        actually clear it, or CI would be red from day one."""
        tree = _load_real_tree()
        for token_path, idx, claim, _token in collect_claims(tree):
            floor = DUTY_FLOORS[claim["duty"]]
            if floor is not None:
                assert claim["ratio"] >= floor, (
                    f"{token_path}[{idx}] duty={claim['duty']} claims "
                    f"{claim['ratio']} which is below its own {floor} floor"
                )


# --------------------------------------------------------------- structural


class TestStructuralDefectsAreHardErrorsNotSilentSkips:
    def test_missing_alias_raises_rather_than_silently_skipping(self) -> None:
        tree = {
            "color": {
                "ink": {
                    "$value": "#16213a",
                    "$extensions": {
                        "com.balizero.contrast": [
                            {"against": "{color.nope}", "ratio": 1.0, "duty": "text"}
                        ]
                    },
                }
            }
        }
        with pytest.raises(TokenContrastError, match="does not resolve"):
            check(tree)

    def test_circular_alias_raises(self) -> None:
        tree = {
            "color": {
                "a": {"$value": "{color.b}"},
                "b": {
                    "$value": "{color.a}",
                    "$extensions": {
                        "com.balizero.contrast": [
                            {"against": "{color.a}", "ratio": 1.0, "duty": "text"}
                        ]
                    },
                },
            }
        }
        with pytest.raises(TokenContrastError, match="circular"):
            check(tree)

    def test_unrecognised_duty_raises(self) -> None:
        tree = {
            "color": {
                "ink": {"$value": "#16213a"},
                "x": {
                    "$value": "#ffffff",
                    "$extensions": {
                        "com.balizero.contrast": [
                            {
                                "against": "{color.ink}",
                                "ratio": 1.0,
                                "duty": "not-a-real-duty",
                            }
                        ]
                    },
                },
            }
        }
        with pytest.raises(TokenContrastError, match="unrecognised duty"):
            check(tree)

    def test_missing_token_file_is_a_structural_error_not_a_crash(
        self, tmp_path, capsys
    ) -> None:
        rc = main(["--path", str(tmp_path / "does-not-exist.json")])
        err = capsys.readouterr().err
        assert rc == 2
        assert "not found" in err


class TestAliasResolutionAgainstTheRealAliasGraph:
    """Every `against` in the shipped file must resolve inside it — a
    dangling reference here would be a hard error at CI time, not
    something a human notices in review.

    The previous version of this test asserted only
    `isinstance(violations, list)` after calling `check(tree)` — true on
    ANY non-raising run, whether or not an unresolved alias inside it was
    silently swallowed instead of raising. That assertion could not fail
    (cicatrix W95/#3: "a test that cannot fail is not a test"); it has
    been replaced with one that sabotages a REAL claim in the shipped file
    and asserts the documented raise, not a tautology about the return
    type of the happy path.
    """

    def test_a_real_claims_against_reference_raises_when_it_dangles(self) -> None:
        tree = _load_real_tree()
        token = tree["color"]["text"]["ink-soft"]
        claim = token["$extensions"]["com.balizero.contrast"][0]
        assert claim["against"] == "{color.ground.carta}"
        # Sabotage exactly this one claim's `against` alias so it points
        # nowhere; every other claim, and the hex values, are untouched.
        claim["against"] = "{color.ground.does-not-exist}"
        with pytest.raises(TokenContrastError, match="does not resolve"):
            check(tree)


# --------------------------------------------------- required-claims floor


class TestRequiredClaimsFloor:
    """A token can be silenced without tripping `check()` above: delete its
    whole `$extensions."com.balizero.contrast"` block (or just empty the
    list) and drift its hex in the same edit — `check()` only ever
    recomputes claims that EXIST, so a claim-less token has nothing to
    disagree with and the run stays quiet. `check_required_claims()` is
    the independent-of-content answer: an explicit set of token paths that
    must carry >=1 contrast claim, verified regardless of what the file
    happens to contain.
    """

    def test_the_shipped_file_clears_the_required_claims_floor(self) -> None:
        assert check_required_claims(_load_real_tree()) == []

    def test_the_floor_is_a_real_non_empty_set(self) -> None:
        # A required-claims floor that is empty by accident would pass
        # everything trivially — this is the sanity check that it isn't.
        assert len(REQUIRED_CLAIM_PATHS) > 0
        for path in REQUIRED_CLAIM_PATHS:
            assert _lookup_exists(_load_real_tree(), path), (
                f"{path} is in REQUIRED_CLAIM_PATHS but does not exist in "
                "the shipped file — the constant has drifted from reality"
            )

    def test_emptying_a_required_tokens_claims_list_is_caught_by_path(self) -> None:
        assert "color.text.ink" in REQUIRED_CLAIM_PATHS
        tree = _load_real_tree()
        # Silence AND drift in the same edit — exactly the attack
        # check_token_contrast.py's own module docstring names: the
        # per-claim recompute in check() has nothing left to disagree
        # with once the claims list is gone.
        tree["color"]["text"]["ink"]["$extensions"]["com.balizero.contrast"] = []
        tree["color"]["text"]["ink"]["$value"] = "#f7f6f2"  # drift to == carta
        drift_violations, _notices = check(tree)
        assert drift_violations == [], (
            "sanity: check() alone must stay quiet on a claim-less token "
            f"(this is exactly the hole this floor exists to close): "
            f"{drift_violations!r}"
        )
        floor_violations = check_required_claims(tree)
        assert len(floor_violations) == 1
        assert "color.text.ink" in floor_violations[0]
        assert "required-claims floor" in floor_violations[0]

    def test_deleting_the_extensions_block_entirely_is_caught_the_same_way(
        self,
    ) -> None:
        tree = _load_real_tree()
        del tree["color"]["text"]["ink-soft"]["$extensions"]
        violations = check_required_claims(tree)
        assert len(violations) == 1
        assert "color.text.ink-soft" in violations[0]

    def test_deleting_a_required_token_outright_is_caught(self) -> None:
        assert "color.red.merah" in REQUIRED_CLAIM_PATHS
        tree = _load_real_tree()
        del tree["color"]["red"]["merah"]
        violations = check_required_claims(tree)
        assert len(violations) == 1
        assert "color.red.merah" in violations[0]
        assert "MISSING" in violations[0]

    def test_cli_exits_nonzero_naming_the_silenced_token(
        self, tmp_path, capsys
    ) -> None:
        tree = _load_real_tree()
        tree["color"]["red"]["merah"]["$extensions"]["com.balizero.contrast"] = []
        path = _write_tree(tmp_path, tree)
        rc = main(["--path", str(path)])
        err = capsys.readouterr().err
        assert rc == 1
        assert "color.red.merah" in err
        assert "required-claims floor" in err


def _lookup_exists(tree: dict[str, Any], dotted_path: str) -> bool:
    node: Any = tree
    for segment in dotted_path.split("."):
        if not isinstance(node, dict) or segment not in node:
            return False
        node = node[segment]
    return isinstance(node, dict) and "$value" in node


# ------------------------------------------------ floor publication precision


class TestFloorComparisonHonorsPublicationPrecision:
    """The drift check already forgives up to ±0.02 against a claim
    published at this file's own 2-decimal precision (see
    DEFAULT_TOLERANCE's comment in check_token_contrast.py). The floor
    check must forgive the SAME thing, or a claim that is transcribed
    correctly per that convention can pass drift and still fail the floor
    purely from comparing a raw, un-rounded float against the floor with a
    near-zero epsilon.

    Repro: #bb4f96 on #ffffff computes to 4.495100028222215 (verified
    below) — rounds to the published 4.50 under this file's own
    convention, and the 0.0049 drift from that published value clears the
    ±0.02 drift tolerance comfortably. duty=text demands >=4.5:1. The OLD
    floor check (`computed < floor - 1e-9`) failed this: a false red on a
    token that is not actually broken. Comparing the rounded (2dp) value —
    matching this file's own publication precision — must pass.
    """

    def test_a_correctly_transcribed_borderline_claim_clears_the_floor(self) -> None:
        fg, bg = "#bb4f96", "#ffffff"
        computed = contrast_ratio(fg, bg)
        assert abs(computed - 4.4951) < 1e-4, f"fixture drifted: {computed}"
        assert round(computed, 2) == 4.50
        tree = {
            "color": {
                "white": {"$value": bg},
                "borderline": {
                    "$value": fg,
                    "$extensions": {
                        "com.balizero.contrast": [
                            {
                                "against": "{color.white}",
                                "ratio": 4.50,
                                "duty": "text",
                            }
                        ]
                    },
                },
            }
        }
        violations, _notices = check(tree)
        assert violations == [], violations

    def test_a_genuinely_failing_borderline_ratio_still_fails(self) -> None:
        """Mutation proof for the pass above: a claim whose rounded value
        is BELOW the floor (4.49, not 4.50) must still be rejected — this
        is not a blanket widening of the floor, only a precision fix."""
        fg, bg = "#c506f2", "#ffffff"  # true ratio 4.4850..., rounds to 4.49
        computed = contrast_ratio(fg, bg)
        assert round(computed, 2) < 4.5, f"fixture no longer below the floor: {computed}"
        tree = {
            "color": {
                "white": {"$value": bg},
                "just-under": {
                    "$value": fg,
                    "$extensions": {
                        "com.balizero.contrast": [
                            {
                                "against": "{color.white}",
                                "ratio": round(computed, 2),
                                "duty": "text",
                            }
                        ]
                    },
                },
            }
        }
        violations, _notices = check(tree)
        assert len(violations) == 1
        assert "color.just-under" in violations[0]


# -------------------------------------------------------- --tolerance bound


class TestToleranceIsBounded:
    """`--tolerance` is a CI-gate parameter as of this PR; an unbounded
    value is the obvious way to neuter the gate by construction
    (`--tolerance 99` makes any drift claim recompute "clean")."""

    def test_absurd_tolerance_is_refused_not_silently_accepted(
        self, tmp_path, capsys
    ) -> None:
        path = _write_tree(tmp_path, _load_real_tree())
        rc = main(["--path", str(path), "--tolerance", "99"])
        err = capsys.readouterr().err
        assert rc == 2
        assert "REFUSED" in err

    def test_negative_tolerance_is_refused(self, tmp_path, capsys) -> None:
        path = _write_tree(tmp_path, _load_real_tree())
        rc = main(["--path", str(path), "--tolerance", "-1"])
        err = capsys.readouterr().err
        assert rc == 2
        assert "REFUSED" in err

    def test_tolerance_exactly_at_the_bound_is_accepted(self, tmp_path, capsys) -> None:
        # The bound itself must be inclusive, not an off-by-one trap.
        path = _write_tree(tmp_path, _load_real_tree())
        rc = main(["--path", str(path), "--tolerance", str(MAX_TOLERANCE)])
        assert rc == 0

    def test_default_tolerance_is_within_the_bound(self) -> None:
        from scripts.check_token_contrast import DEFAULT_TOLERANCE

        assert 0 <= DEFAULT_TOLERANCE <= MAX_TOLERANCE


# ------------------------------------------------------------ boolean ratio


class TestBooleanRatioIsRejected:
    """`isinstance(x, (int, float))` admits `True`/`False` because `bool`
    subclasses `int` in Python — a JSON `"ratio": true` would otherwise
    silently pass as the number 1."""

    def test_ratio_as_json_true_is_rejected_not_silently_treated_as_one(
        self,
    ) -> None:
        tree = {
            "color": {
                "a": {"$value": "#ffffff"},
                "b": {
                    "$value": "#fefefe",
                    "$extensions": {
                        "com.balizero.contrast": [
                            {"against": "{color.a}", "ratio": True, "duty": "text"}
                        ]
                    },
                },
            }
        }
        with pytest.raises(TokenContrastError, match="numeric"):
            check(tree)

    def test_ratio_as_json_false_is_rejected(self) -> None:
        tree = {
            "color": {
                "a": {"$value": "#ffffff"},
                "b": {
                    "$value": "#000000",
                    "$extensions": {
                        "com.balizero.contrast": [
                            {"against": "{color.a}", "ratio": False, "duty": "text"}
                        ]
                    },
                },
            }
        }
        with pytest.raises(TokenContrastError, match="numeric"):
            check(tree)


# --------------------------------------------------------- alias chain depth


class TestAliasChainDepthIsBounded:
    """A chain of all-DISTINCT alias paths never revisits anything, so the
    existing `_visiting` cycle guard cannot see it coming — without a
    depth bound it would recurse until it exhausts CPython's own
    recursion limit and raises a bare RecursionError instead of the
    documented TokenContrastError."""

    def test_a_very_long_non_cyclic_chain_raises_not_recursionerror(self) -> None:
        n = MAX_ALIAS_DEPTH + 10
        tree: dict[str, Any] = {"color": {"ground": {"$value": "#ffffff"}}}
        for i in range(n):
            tree["color"][f"step{i}"] = {"$value": f"{{color.step{i + 1}}}"}
        tree["color"][f"step{n}"] = {"$value": "{color.ground}"}
        tree["color"]["step0"]["$extensions"] = {
            "com.balizero.contrast": [
                {"against": "{color.ground}", "ratio": 1.0, "duty": "text"}
            ]
        }
        with pytest.raises(TokenContrastError, match="MAX_ALIAS_DEPTH"):
            check(tree)

    def test_a_chain_within_the_bound_still_resolves_normally(self) -> None:
        n = MAX_ALIAS_DEPTH - 5
        tree: dict[str, Any] = {"color": {"ground": {"$value": "#ffffff"}}}
        for i in range(n):
            tree["color"][f"step{i}"] = {"$value": f"{{color.step{i + 1}}}"}
        tree["color"][f"step{n}"] = {"$value": "{color.ground}"}
        # step0's chain resolves to the SAME hex as `ground` (#ffffff), so
        # the true ratio is exactly 1.0:1 — duty="decorative" (no floor)
        # is what isolates "does the long chain resolve at all" from an
        # unrelated floor failure a 1.0:1 pair would trip under duty=text.
        tree["color"]["step0"]["$extensions"] = {
            "com.balizero.contrast": [
                {"against": "{color.ground}", "ratio": 1.0, "duty": "decorative"}
            ]
        }
        violations, _notices = check(tree)
        assert violations == [], violations
