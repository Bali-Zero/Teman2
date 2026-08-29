#!/usr/bin/env python3
"""check_token_contrast.py — WCAG contrast MEASUREMENT check for the Merah
Putih DTCG token file (PR-2 of
docs/plans/2026-08-29-beyond-sota-craft-wave/L11-product-ux-visual-design.md).

This is deliberately NOT a schema validator. A schema check would confirm the
JSON has the right shape and stop there — it would never notice that a hex
value has drifted, or that the prose claiming a ratio was never updated to
match a hex that WAS changed. A token file can go stale in exactly two
directions, and a schema check catches neither:

  1. The `$value` (hex) changes and the `$extensions."com.balizero.contrast"`
     claim next to it is never updated — the comment now LIES about the color.
  2. The claimed ratio is hand-edited (typo, optimistic rounding, a copy-paste
     from a different pair) while the hex stays untouched — the color is fine
     but the DOCUMENTED FACT about it is now false.

This script recomputes every claimed ratio from the raw hex values with the
WCAG 2.x relative-luminance formula and compares the result to what the
token claims, in both directions at once: if the numbers disagree beyond a
small tolerance, the FILE is wrong regardless of which side moved. It also
enforces the WCAG floor each claim's declared `duty` demands — a token whose
`$value` was edited to something legible-looking but failing 4.5:1 while
still declaring `duty: "text"` is caught the same way a stale ratio is.

Two classes of defect, two exit codes:
  - STRUCTURAL problems (a claim's `against` alias does not resolve, resolves
    in a cycle, or names a `duty` this script does not recognise) are a
    defect in the FILE'S CONTRACT with this checker, not a content drift —
    exit 2, same bucket as a usage error. A hard error here, not a skip:
    silently ignoring an unresolvable claim would let exactly the kind of
    drift this script exists to catch sail through unnoticed.
  - CONTENT problems (a claimed ratio does not match the recomputed one, or a
    claim fails the WCAG floor its own declared duty demands) are exit 1.

Exit codes:
    0 — every claim recomputes within tolerance and clears its duty's floor
    1 — one or more content violations (drift or floor failure); printed to
        stderr, each line naming the offending token path
    2 — structural/usage error (bad JSON, unresolvable/circular alias,
        unrecognised duty, missing --path file)

Standard library only. No network, no PII, no repo mutation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TOKENS_PATH = REPO_ROOT / "design" / "tokens" / "merah-putih.tokens.json"

# The doc this checker's numbers are transcribed from rounds every ratio to
# 2 decimal places before publishing it; recomputing at full float precision
# can therefore differ from the published claim by up to half a rounding
# unit (0.005) purely from that rounding, with zero actual drift. 0.02 gives
# a 4x margin over that worst case while still catching a materially wrong
# hex — an actually-wrong color typically moves a contrast ratio by well
# over 0.1, not by a couple of thousandths. Measured against the 26 pairs in
# research/design/2026-08-27-r4-identity-merah-putih-token-spec.md §3, the
# largest observed rounding gap is 0.005 (merah-action vs carta).
DEFAULT_TOLERANCE = 0.02

# WCAG floor each recognised `duty` demands. `None` means this script
# deliberately enforces NO floor for that duty — printed explicitly at
# runtime so a reader never has to wonder whether the absence of a floor
# check is an oversight.
#   text        -> WCAG 2.x SC 1.4.3, normal text, AA:            4.5:1
#   large-text  -> WCAG 2.x SC 1.4.3, large text (>=18.66px/14pt-bold), AA: 3:1
#   non-text    -> WCAG 2.2 SC 1.4.11, UI component boundaries, AA: 3:1
#   decorative  -> no SC applies; the token is explicitly not an identifier
#                  of anything interactive (WCAG 2.2 SC 1.4.11's own carve-out)
#   icon-only   -> no text SC applies; an icon fill is not a text run
DUTY_FLOORS: dict[str, float | None] = {
    "text": 4.5,
    "large-text": 3.0,
    "non-text": 3.0,
    "decorative": None,
    "icon-only": None,
}

_ALIAS_RE = re.compile(r"^\{([^{}]+)\}$")
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{6})$")


class TokenContrastError(Exception):
    """Structural defect: malformed file, unresolved/circular alias,
    unrecognised duty. Always maps to exit code 2, never exit 1."""


# --------------------------------------------------------------------- WCAG


def _srgb_channel_to_linear(c: float) -> float:
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def hex_to_rgb(hexcolor: str) -> tuple[int, int, int]:
    m = _HEX_RE.match(hexcolor)
    if not m:
        raise TokenContrastError(
            f"unsupported color literal {hexcolor!r} — only 6-digit "
            "#RRGGBB hex is supported (no 3/4/8-digit shorthand, no "
            "rgb()/hsl() functional forms)"
        )
    h = m.group(1)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def relative_luminance(hexcolor: str) -> float:
    r, g, b = hex_to_rgb(hexcolor)
    rl = _srgb_channel_to_linear(r / 255.0)
    gl = _srgb_channel_to_linear(g / 255.0)
    bl = _srgb_channel_to_linear(b / 255.0)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def contrast_ratio(hex1: str, hex2: str) -> float:
    l1, l2 = relative_luminance(hex1), relative_luminance(hex2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# --------------------------------------------------------------- DTCG tree


def _get_by_path(tree: dict[str, Any], dotted_path: str) -> dict[str, Any]:
    node: Any = tree
    walked: list[str] = []
    for segment in dotted_path.split("."):
        if not isinstance(node, dict) or segment not in node:
            raise TokenContrastError(
                f"alias {{{dotted_path}}} does not resolve — no key "
                f"{segment!r} under {'.'.join(walked) or '<root>'}"
            )
        node = node[segment]
        walked.append(segment)
    if not isinstance(node, dict) or "$value" not in node:
        raise TokenContrastError(
            f"alias {{{dotted_path}}} points at {node!r}, which is not a "
            "token (no $value)"
        )
    return node


def resolve_value(
    tree: dict[str, Any], value: Any, _visiting: frozenset[str] = frozenset()
) -> str:
    """Resolve a `$value` that may be a literal hex string or a
    `{dotted.alias.path}` reference, following chains. Raises
    TokenContrastError (never returns a placeholder) on a missing or
    circular alias — a silently-skipped unresolvable claim is exactly the
    kind of drift this script exists to catch.
    """
    if not isinstance(value, str):
        raise TokenContrastError(
            f"expected a color literal or alias string, got {value!r}"
        )
    m = _ALIAS_RE.match(value)
    if not m:
        return value  # literal hex (or something hex_to_rgb will reject)
    dotted_path = m.group(1)
    if dotted_path in _visiting:
        chain = " -> ".join(sorted(_visiting)) + f" -> {dotted_path}"
        raise TokenContrastError(f"circular alias: {chain}")
    target = _get_by_path(tree, dotted_path)
    return resolve_value(tree, target["$value"], _visiting | {dotted_path})


def iter_tokens(
    node: Any, prefix: tuple[str, ...] = ()
) -> list[tuple[str, dict[str, Any]]]:
    """Every leaf token (a dict carrying `$value`) in the tree, as
    (dotted.path, token_dict). Never descends into a token's own `$value`
    even when it is itself a dict (a composite type like `border`) — that
    inner dict is a value shape, not more token-tree structure.
    """
    out: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(node, dict):
        return out
    if "$value" in node:
        out.append((".".join(prefix), node))
        return out
    for key, child in node.items():
        if key.startswith("$"):
            continue
        out.extend(iter_tokens(child, prefix + (key,)))
    return out


def collect_claims(
    tree: dict[str, Any],
) -> list[tuple[str, int, dict[str, Any], dict[str, Any]]]:
    """Every (token_path, claim_index, claim, token) for tokens that carry
    `$extensions."com.balizero.contrast"`. A token with no such extension is
    not required to have one — only tokens claiming a WCAG duty are checked.
    """
    claims: list[tuple[str, int, dict[str, Any], dict[str, Any]]] = []
    for token_path, token in iter_tokens(tree):
        ext = token.get("$extensions")
        if not isinstance(ext, dict):
            continue
        contrast_list = ext.get("com.balizero.contrast")
        if not contrast_list:
            continue
        if not isinstance(contrast_list, list):
            raise TokenContrastError(
                f"{token_path}: com.balizero.contrast must be a list, got "
                f"{type(contrast_list).__name__}"
            )
        for idx, claim in enumerate(contrast_list):
            claims.append((token_path, idx, claim, token))
    return claims


# ------------------------------------------------------------------- check


def check(
    tree: dict[str, Any], tolerance: float = DEFAULT_TOLERANCE
) -> tuple[list[str], list[str]]:
    """Recompute every claim in `tree`.

    Returns (violations, notices). `violations` is content-defect messages
    (exit-1 material: drift beyond tolerance, or a floor failure) —
    non-empty means FAIL. `notices` is informational lines, including the
    explicit "no floor enforced here by design" line for every
    decorative/icon-only claim, printed on every run so that absence never
    reads as an oversight.

    Raises TokenContrastError (never returns) on any structural problem:
    unresolved/circular alias, unrecognised duty, malformed claim shape.
    That is exit-2 territory in `main`, never folded into `violations`.
    """
    violations: list[str] = []
    notices: list[str] = []

    for token_path, idx, claim, token in collect_claims(tree):
        for required in ("against", "ratio", "duty"):
            if required not in claim:
                raise TokenContrastError(
                    f"{token_path}[{idx}]: claim missing required key "
                    f"{required!r}: {claim!r}"
                )
        against_ref = claim["against"]
        claimed_ratio = claim["ratio"]
        duty = claim["duty"]

        if duty not in DUTY_FLOORS:
            raise TokenContrastError(
                f"{token_path}[{idx}]: unrecognised duty {duty!r} — must be "
                f"one of {sorted(DUTY_FLOORS)}"
            )
        if not isinstance(claimed_ratio, (int, float)):
            raise TokenContrastError(
                f"{token_path}[{idx}]: ratio must be numeric, got "
                f"{claimed_ratio!r}"
            )

        fg_hex = resolve_value(tree, token["$value"])
        bg_hex = resolve_value(tree, against_ref)
        computed = contrast_ratio(fg_hex, bg_hex)

        drift = abs(computed - claimed_ratio)
        if drift > tolerance:
            violations.append(
                f"{token_path}[{idx}]: claimed {claimed_ratio:.2f}:1 against "
                f"{against_ref} ({bg_hex}) but recomputed {computed:.4f}:1 "
                f"from the raw hex values — drift {drift:.4f} exceeds "
                f"tolerance ±{tolerance}"
            )
            continue  # a claim that has drifted has nothing further to say

        floor = DUTY_FLOORS[duty]
        if floor is None:
            notices.append(
                f"{token_path}[{idx}]: duty={duty} against {against_ref} — "
                f"measured {computed:.2f}:1, no WCAG floor enforced here BY "
                "DESIGN (decorative/icon-only carry no text or "
                "non-text contrast obligation)"
            )
            continue

        if computed < floor - 1e-9:
            violations.append(
                f"{token_path}[{idx}]: duty={duty} demands >= {floor}:1 "
                f"against {against_ref} ({bg_hex}), but the claimed AND "
                f"recomputed ratio is {computed:.4f}:1"
            )

    return violations, notices


# --------------------------------------------------------------------- CLI


def _load_tree(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise TokenContrastError(f"token file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TokenContrastError(f"{path}: invalid JSON — {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Recompute every WCAG contrast claim in a DTCG token file and "
            "fail if a value has drifted or a floor is not cleared."
        )
    )
    ap.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_TOKENS_PATH,
        help=f"token file to check (default: {DEFAULT_TOKENS_PATH})",
    )
    ap.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help=f"allowed drift before a claim is flagged (default: {DEFAULT_TOLERANCE})",
    )
    ap.add_argument(
        "--selftest",
        action="store_true",
        help="run in-process guilt+innocence fixtures and exit (no file I/O)",
    )
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    try:
        tree = _load_tree(args.path)
        violations, notices = check(tree, tolerance=args.tolerance)
    except TokenContrastError as exc:
        print(f"check_token_contrast: STRUCTURAL ERROR — {exc}", file=sys.stderr)
        return 2

    for line in notices:
        print(f"check_token_contrast: NOTICE — {line}")

    claim_count = len(collect_claims(tree))
    if violations:
        print(
            f"check_token_contrast: FAIL — {len(violations)}/{claim_count} "
            f"claim(s) in {args.path} failed (drift or WCAG floor):",
            file=sys.stderr,
        )
        for line in violations:
            print(f"  {line}", file=sys.stderr)
        return 1

    print(
        f"check_token_contrast: OK — {claim_count} claim(s) in {args.path} "
        f"recompute within ±{args.tolerance} and clear their duty's floor"
    )
    return 0


# ----------------------------------------------------------------- selftest


def _selftest() -> int:
    """Guilt + innocence, entirely in-process — no file on disk is read or
    written. Mirrors (but does not replace) the pytest suite in
    scripts/tests/test_check_token_contrast.py; this is the fast path a
    human or a pre-commit hook can run with zero dependencies.
    """
    ok = True

    def report(label: str, condition: bool, detail: str = "") -> None:
        nonlocal ok
        status = "PASS" if condition else "FAIL"
        if not condition:
            ok = False
        print(f"check_token_contrast --selftest: {status} — {label}{detail}")

    carta = "#f7f6f2"
    ink = "#16213a"
    computed_ink_on_carta = contrast_ratio(ink, carta)

    # --- innocence: a correct claim recomputes clean and has zero floor
    # violations.
    good_tree = {
        "color": {
            "carta": {"$value": carta},
            "ink": {
                "$value": ink,
                "$extensions": {
                    "com.balizero.contrast": [
                        {
                            "against": "{color.carta}",
                            "ratio": round(computed_ink_on_carta, 2),
                            "duty": "text",
                        }
                    ]
                },
            },
        }
    }
    violations, notices = check(good_tree)
    report(
        "innocence: correct claim recomputes clean",
        violations == [],
        f" (violations={violations!r})",
    )

    # --- innocence B: decorative/icon-only claims with LOW ratios must NOT
    # fail — a checker that fails these is worse than none, because someone
    # will "fix" the design to satisfy it.
    hairline = "#e3e1da"
    hairline_ratio = round(contrast_ratio(hairline, carta), 2)
    whatsapp = "#25d366"
    white = "#ffffff"
    whatsapp_ratio = round(contrast_ratio(white, whatsapp), 2)
    low_ratio_tree = {
        "color": {
            "carta": {"$value": carta},
            "hairline": {
                "$value": hairline,
                "$extensions": {
                    "com.balizero.contrast": [
                        {
                            "against": "{color.carta}",
                            "ratio": hairline_ratio,
                            "duty": "decorative",
                        }
                    ]
                },
            },
            "whatsapp": {"$value": whatsapp},
            "white": {
                "$value": white,
                "$extensions": {
                    "com.balizero.contrast": [
                        {
                            "against": "{color.whatsapp}",
                            "ratio": whatsapp_ratio,
                            "duty": "icon-only",
                        }
                    ]
                },
            },
        }
    }
    assert hairline_ratio < 3.0 and whatsapp_ratio < 4.5, "fixture no longer low-ratio"
    violations2, notices2 = check(low_ratio_tree)
    report(
        "innocence B: hairline (decorative) and whatsapp (icon-only) pass "
        "despite low ratios",
        violations2 == [] and len(notices2) == 2,
        f" (violations={violations2!r}, notices={len(notices2)})",
    )

    # --- guilt A: hex edited to a value that fails its declared ratio.
    bad_hex_tree = json.loads(json.dumps(good_tree))
    bad_hex_tree["color"]["ink"]["$value"] = "#f7f6f2"  # == carta -> ratio ~1.0
    violations3, _ = check(bad_hex_tree)
    report(
        "guilt A: edited hex fails its declared ratio",
        len(violations3) == 1 and "color.ink" in violations3[0],
        f" (violations={violations3!r})",
    )

    # --- guilt B: hex untouched, only the CLAIMED ratio is edited (the
    # comment lying about the hex, not the reverse).
    bad_ratio_tree = json.loads(json.dumps(good_tree))
    bad_ratio_tree["color"]["ink"]["$extensions"]["com.balizero.contrast"][0][
        "ratio"
    ] = 99.0
    violations4, _ = check(bad_ratio_tree)
    report(
        "guilt B: claimed ratio edited away from the true hex-derived value",
        len(violations4) == 1 and "color.ink" in violations4[0],
        f" (violations={violations4!r})",
    )

    # --- guilt C: duty=text, ratio is internally consistent (claim ==
    # recomputed) but fails the 4.5 floor outright.
    low_text_fg = "#c8c8c8"
    low_text_bg = "#ffffff"
    low_text_ratio = round(contrast_ratio(low_text_fg, low_text_bg), 2)
    assert low_text_ratio < 4.5, "fixture no longer below the text floor"
    floor_fail_tree = {
        "color": {
            "white": {"$value": low_text_bg},
            "pale": {
                "$value": low_text_fg,
                "$extensions": {
                    "com.balizero.contrast": [
                        {
                            "against": "{color.white}",
                            "ratio": low_text_ratio,
                            "duty": "text",
                        }
                    ]
                },
            },
        }
    }
    violations5, _ = check(floor_fail_tree)
    report(
        "guilt C: duty=text with a genuinely-failing (internally consistent) "
        "ratio",
        len(violations5) == 1 and "color.pale" in violations5[0],
        f" (violations={violations5!r})",
    )

    # --- structural: missing alias is a hard error, not a silent skip.
    missing_alias_tree = {
        "color": {
            "ink": {
                "$value": ink,
                "$extensions": {
                    "com.balizero.contrast": [
                        {"against": "{color.nope}", "ratio": 1.0, "duty": "text"}
                    ]
                },
            }
        }
    }
    try:
        check(missing_alias_tree)
        report("structural: missing alias raises TokenContrastError", False)
    except TokenContrastError:
        report("structural: missing alias raises TokenContrastError", True)

    # --- structural: circular alias is a hard error.
    circular_tree = {
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
    try:
        check(circular_tree)
        report("structural: circular alias raises TokenContrastError", False)
    except TokenContrastError:
        report("structural: circular alias raises TokenContrastError", True)

    if ok:
        print("check_token_contrast --selftest: ALL PASS")
        return 0
    print("check_token_contrast --selftest: FAILURES ABOVE", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
