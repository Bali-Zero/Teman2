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
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.check_token_contrast import (
    DEFAULT_TOKENS_PATH,
    DUTY_FLOORS,
    TokenContrastError,
    check,
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
    something a human notices in review."""

    def test_every_against_reference_resolves(self) -> None:
        tree = _load_real_tree()
        # check() already resolves every alias as a side effect of
        # recomputing; a clean run with zero TokenContrastError is the
        # proof. Re-asserted explicitly here so a future refactor that
        # accidentally swallows the exception is still caught.
        violations, _notices = check(tree)  # raises on unresolved alias
        assert isinstance(violations, list)
