"""Merah Putih DAY palette — the identity law, machine-checked.

Two guards, both reading the REAL source of truth rather than a copy:

1. CONTRAST — every text/background pair the R4 law binds is recomputed from the
   hexes actually present in `merahPutihDayVars.ts`. A token edited tomorrow is
   re-measured tomorrow; nothing here is a frozen number a reader must trust.
   Spec: research/design/2026-08-27-r4-identity-merah-putih-token-spec.md §4.

2. INNOCENCE — the retired colours (navy `#1e3863`, editorial blue `#3a6dff`,
   the bright red `#ff3344` that measures 3.34 on carta) and the retired
   Montserrat face must not appear anywhere in the public second-home perimeter.

The internal kita console `(workspace)/second-home` is deliberately OUT of scope:
its operative copper is a different, still-valid system (R4 §6).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOKENS = REPO / "apps/mouth/src/lib/theme/merahPutihDayVars.ts"
PERIMETER = REPO / "apps/mouth/src/app/visa/second-home"


# ── contrast machinery ────────────────────────────────────────────────────────


def _srgb_to_linear(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return (
        0.2126 * _srgb_to_linear(r)
        + 0.7152 * _srgb_to_linear(g)
        + 0.0722 * _srgb_to_linear(b)
    )


def contrast_ratio(fg: str, bg: str) -> float:
    a, b = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def read_tokens() -> dict[str, str]:
    """Parse the `"--token": "#hex"` pairs out of the TS source."""
    src = TOKENS.read_text(encoding="utf-8")
    return {
        m.group(1): m.group(2).lower()
        for m in re.finditer(r'"(--[a-z0-9-]+)":\s*"(#[0-9a-fA-F]{6})"', src)
    }


# ── 1. contrast law ───────────────────────────────────────────────────────────

AA_TEXT = 4.5
NON_TEXT = 3.0

# (foreground token, background token, floor). Grounds are carta / elevated.
TEXT_PAIRS = [
    ("--text-primary", "--surface-base", AA_TEXT),
    ("--text-primary", "--surface-raised", AA_TEXT),
    ("--text-primary", "--surface-sunken", AA_TEXT),
    ("--text-secondary", "--surface-base", AA_TEXT),
    ("--text-secondary", "--surface-raised", AA_TEXT),
    ("--text-tertiary", "--surface-base", AA_TEXT),
    ("--accent-funnel", "--surface-base", AA_TEXT),
    ("--accent-funnel-text", "--surface-base", AA_TEXT),
    ("--accent-funnel-text", "--surface-raised", AA_TEXT),
    ("--state-success", "--surface-base", AA_TEXT),
    ("--state-likely", "--surface-base", AA_TEXT),
    ("--state-warning", "--surface-base", AA_TEXT),
    ("--state-danger", "--surface-base", AA_TEXT),
    ("--accent-whatsapp-ink", "--surface-raised", AA_TEXT),
    ("--accent-whatsapp-ink", "--surface-base", AA_TEXT),
]

# White text is legal ONLY on these fills (R4 §4.2).
WHITE_ON = [
    "--accent-funnel",
    "--accent-funnel-text",
    "--cta-bg",  # the primary CTA fill — StudioApp's primaryNavButtonStyle
    "--cta-bg-hover",
    "--state-danger",
]

# Boundaries that IDENTIFY an interactive component must clear 3:1 (SC 1.4.11).
NON_TEXT_PAIRS = [
    ("--border-strong", "--surface-base", NON_TEXT),
    ("--border-strong", "--surface-raised", NON_TEXT),
    ("--accent-funnel", "--surface-base", NON_TEXT),  # progress fill
]


@pytest.mark.parametrize("fg,bg,floor", TEXT_PAIRS)
def test_text_pairs_clear_wcag_aa(fg: str, bg: str, floor: float) -> None:
    tokens = read_tokens()
    ratio = contrast_ratio(tokens[fg], tokens[bg])
    assert ratio >= floor, (
        f"{fg} ({tokens[fg]}) on {bg} ({tokens[bg]}) = {ratio:.2f}, needs {floor}"
    )


@pytest.mark.parametrize("fill", WHITE_ON)
def test_white_text_is_legal_on_its_declared_fills(fill: str) -> None:
    tokens = read_tokens()
    ratio = contrast_ratio("#ffffff", tokens[fill])
    assert ratio >= AA_TEXT, (
        f"white on {fill} ({tokens[fill]}) = {ratio:.2f}, needs {AA_TEXT}"
    )


@pytest.mark.parametrize("fg,bg,floor", NON_TEXT_PAIRS)
def test_interactive_boundaries_clear_three_to_one(fg: str, bg: str, floor: float) -> None:
    tokens = read_tokens()
    ratio = contrast_ratio(tokens[fg], tokens[bg])
    assert ratio >= floor, (
        f"{fg} ({tokens[fg]}) on {bg} ({tokens[bg]}) = {ratio:.2f}, needs {floor}"
    )


def test_hairline_is_decorative_and_documented_as_such() -> None:
    """`--border-subtle` CANNOT carry component identity — it measures ~1.2:1.

    This is not a defect to fix by darkening it: the law wants a quiet divider.
    The test pins the DUTY, so that a future edit which raises it into
    interactive service has to change this test deliberately.
    """
    tokens = read_tokens()
    ratio = contrast_ratio(tokens["--border-subtle"], tokens["--surface-base"])
    assert ratio < NON_TEXT, (
        "border-subtle now clears 3:1 — if that is intentional, say so here and "
        "state which components may use it as their boundary"
    )
    assert "DECORATIVE" in TOKENS.read_text(encoding="utf-8")


def test_the_retired_red_would_fail_which_is_why_it_is_retired() -> None:
    """Anchors the reason. #ff3344 on carta = 3.34, below the 4.5 AA floor."""
    tokens = read_tokens()
    assert contrast_ratio("#ff3344", tokens["--surface-base"]) < AA_TEXT


# ── 2. innocence: no retired colour or face in the public perimeter ──────────

RETIRED = {
    "#ff3344": "the bright red retired by R4 (3.34 on carta)",
    "#1e3863": "the navy retired from the whole public perimeter",
    "#3a6dff": "the editorial McKinsey blue that the navy carried",
}


def _perimeter_sources() -> list[Path]:
    return sorted(
        p
        for p in PERIMETER.rglob("*.tsx")
        if not p.name.endswith(".test.tsx")
    )


_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"//[^\n]*")


def strip_comments(src: str) -> str:
    """Remove JS/TS comments so the guard judges PAINTED VALUES, not prose.

    A retired hex NAMED in a comment ("we replaced the retired #ff3344") paints
    nothing — flagging it would push authors to stop explaining themselves, which
    is how a codebase loses the reason behind its own rules (scar family #3,
    over-match). `test_the_stripper_cannot_hide_a_real_use` is the guilt half
    that keeps this leniency honest.
    """
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", src))


@pytest.mark.parametrize("colour,why", sorted(RETIRED.items()))
def test_no_retired_colour_in_public_perimeter(colour: str, why: str) -> None:
    offenders = [
        f"{p.relative_to(REPO)}:{i}"
        for p in _perimeter_sources()
        for i, line in enumerate(
            strip_comments(p.read_text(encoding="utf-8")).splitlines(), 1
        )
        if colour in line.lower()
    ]
    assert not offenders, f"{colour} ({why}) still present as a VALUE at: {offenders}"


def test_the_stripper_cannot_hide_a_real_use() -> None:
    """Guilt half of the guard: a real declaration must survive stripping.

    Without this, `strip_comments` could be widened until the innocence test
    passes on a perimeter that is actually painting the retired red.
    """
    painted = 'const s = { color: "#ff3344" }; // the retired #ff3344, explained'
    stripped = strip_comments(painted)
    assert "#ff3344" in stripped, "the stripper swallowed a real declaration"
    assert stripped.count("#ff3344") == 1, "the comment mention was not stripped"

    prose_only = "// we migrated away from #ff3344 and #1e3863\n/* #3a6dff too */"
    assert "#ff3344" not in strip_comments(prose_only)
    assert "#1e3863" not in strip_comments(prose_only)
    assert "#3a6dff" not in strip_comments(prose_only)


def test_montserrat_does_not_reach_the_second_home_perimeter() -> None:
    """R4 §9.3 retires Montserrat from the web funnels (it stays on IG covers).

    `/visa/layout.tsx` still imports it for the rest of the funnel — that is a
    different lane's perimeter. What this test pins is that second-home neither
    imports it nor names it, and that our own wrapper re-declares fontFamily so
    the inherited face stops at our boundary.
    """
    offenders = [
        str(p.relative_to(REPO))
        for p in _perimeter_sources()
        if "montserrat" in strip_comments(p.read_text(encoding="utf-8")).lower()
    ]
    assert not offenders, f"Montserrat reached the perimeter at: {offenders}"
    assert "fontFamily" in TOKENS.read_text(encoding="utf-8"), (
        "the day set must re-declare fontFamily, or the visa layout's forced "
        "Montserrat inherits straight through the wrapper"
    )


# ── 3. typography floors (R4 §3) ─────────────────────────────────────────────

CORMORANT_FLOOR_REM = 1.5  # 24px — below it, low-DPI Android antialiasing shreds the serif
_CLAMP_MIN = re.compile(r'fontSize: *"clamp\(([\d.]+)rem')
_WEIGHT = re.compile(r"fontWeight: *(\d+)")


def _serif_context(lines: list[str], idx: int) -> bool:
    """A serif face declared within a few lines of this declaration."""
    window = "\n".join(lines[max(0, idx - 6) : idx + 5])
    return "fontSerif" in window or "--font-serif" in window


def test_no_serif_heading_below_the_24px_floor() -> None:
    offenders = []
    for p in _perimeter_sources():
        lines = strip_comments(p.read_text(encoding="utf-8")).splitlines()
        for i, line in enumerate(lines):
            m = _CLAMP_MIN.search(line)
            if m and _serif_context(lines, i) and float(m.group(1)) < CORMORANT_FLOOR_REM:
                offenders.append(
                    f"{p.relative_to(REPO)}:{i + 1} min={m.group(1)}rem "
                    f"({float(m.group(1)) * 16:.1f}px)"
                )
    assert not offenders, (
        "Cormorant below the 24px floor (R4 §3) — raise the clamp minimum to "
        f"1.5rem or switch the heading to Inter 600: {offenders}"
    )


def test_no_cormorant_weight_below_500() -> None:
    offenders = []
    for p in _perimeter_sources():
        lines = strip_comments(p.read_text(encoding="utf-8")).splitlines()
        for i, line in enumerate(lines):
            m = _WEIGHT.search(line)
            if m and _serif_context(lines, i) and int(m.group(1)) < 500:
                offenders.append(f"{p.relative_to(REPO)}:{i + 1} weight={m.group(1)}")
    assert not offenders, (
        f"R4 §3 allows Cormorant at 500/600 only: {offenders}"
    )


# ── 4. the alias trap ────────────────────────────────────────────────────────

SEMANTIC_CSS = REPO / "packages/core/tokens/semantic.css"
_ALIAS = re.compile(r"^\s*(--[a-z0-9-]+):\s*var\((--[a-z0-9-]+)")


def test_every_consumed_root_alias_is_restated_in_the_day_set() -> None:
    """Aliases declared at :root do NOT follow a wrapper-scoped override.

    `semantic.css` declares e.g. `--color-text-muted: var(--text-secondary)` at
    :root. A var() inside a custom-property declaration is substituted using the
    cascade AT THE DECLARING ELEMENT, so that alias resolves against :root's
    value and hands the already-computed result down by inheritance. Overriding
    `--text-secondary` on a wrapper deep in the tree does not move it.

    MEASURED 2026-08-31 on the running app, which is why this test exists: at
    :root the day pages resolved `--color-text-muted` to `rgba(255,255,255,0.68)`
    and `--color-border-subtle` to `rgba(255,255,255,0.06)` — white, from the
    dark theme. Consumed 42 and 36 times in this perimeter, that is white text
    on warm paper and invisible borders. The cure is to restate the alias itself
    in the day set; this test fails if a NEW alias is consumed without doing so.
    """
    if not SEMANTIC_CSS.exists():  # pragma: no cover - layout guard
        pytest.skip("semantic.css not found")

    aliases = {}
    for line in SEMANTIC_CSS.read_text(encoding="utf-8").splitlines():
        m = _ALIAS.match(line)
        if m:
            aliases.setdefault(m.group(1), m.group(2))

    perimeter_text = "\n".join(
        strip_comments(p.read_text(encoding="utf-8")) for p in _perimeter_sources()
    )
    day_set = read_tokens()

    missing = [
        f"{alias} (alias of {src})"
        for alias, src in aliases.items()
        if alias in perimeter_text and alias not in day_set
    ]
    assert not missing, (
        "these :root aliases are consumed in the second-home perimeter but are "
        "NOT restated in MERAH_PUTIH_DAY_VARS, so they keep the shared theme's "
        f"(dark) value on a paper page: {missing}"
    )


def test_both_public_wrappers_actually_apply_the_day_set() -> None:
    """The set is inert unless it is spread on the two route wrappers."""
    for rel in (
        "apps/mouth/src/app/visa/second-home/SecondHomeLanding.tsx",
        "apps/mouth/src/app/visa/second-home/studio/StudioApp.tsx",
    ):
        src = (REPO / rel).read_text(encoding="utf-8")
        assert "MERAH_PUTIH_DAY_VARS" in src, f"{rel} does not apply the day set"
        assert "...MERAH_PUTIH_DAY_VARS" in src, (
            f"{rel} imports the day set but never spreads it into a style"
        )


# ── The derived-colour class ────────────────────────────────────────────────
# Found twice during the day migration, in two different components, with two
# different justifications — which is what makes it a class and not a bug:
#   SavePlanBar   armed fill  color-mix(--accent-funnel 85%, black) -> ~#aa0e27
#   ScenarioToggle hover label color-mix(--accent-funnel 70%, white) -> ~#D8586D
# Both were CORRECT when written. On the retired navy ground, mixing a token
# toward white moves it AWAY from the backdrop and raises contrast. On carta the
# identical gesture runs backwards: the ScenarioToggle label measured 3.07:1
# against its own hover tint, a fail, while the flat token measures 4.77:1.
#
# The second harm is permanent regardless of ground: a mix toward white or black
# MINTS A COLOUR THAT BELONGS TO NO TOKEN. #aa0e27 is a fourth red in a palette
# that declares exactly three, and nothing in R4 can ever be checked against it.
#
# A mix toward `transparent` is a different thing and stays allowed: it is an
# opacity tint that composites the token over whatever is behind it, so the hue
# remains the token's own.
# Two things defeat a naive regex here, and the guilt test below caught both:
#   - `color-mix(in srgb, var(--accent-funnel) 85%, black)` contains a NESTED
#     `)`, so any `[^)]*` pattern stops inside `var(...)` and never sees `black`;
#   - the real declarations are pretty-printed across FOUR lines, so a
#     line-by-line scan never has `color-mix(` and `black` in the same string.
# Hence a balanced-paren scan over the whole source. `var(...)` contents are
# dropped before looking, so a token whose NAME contains "white" is not an
# offender — only a literal white/black ARGUMENT is.
def _deriving_mixes(src: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for match in re.finditer(r"color-mix\(", src):
        depth, idx = 0, match.end() - 1
        while idx < len(src):
            if src[idx] == "(":
                depth += 1
            elif src[idx] == ")":
                depth -= 1
                if depth == 0:
                    break
            idx += 1
        body = src[match.end() : idx]
        if re.search(r"\b(?:white|black)\b", re.sub(r"var\([^)]*\)", "", body), re.I):
            line = src.count("\n", 0, match.start()) + 1
            found.append((line, " ".join(body.split())))
    return found


def test_no_colour_is_derived_by_mixing_a_token_toward_white_or_black() -> None:
    offenders = [
        f"{path.name}:{line}: color-mix({body})"
        for path in _perimeter_sources()
        for line, body in _deriving_mixes(
            strip_comments(path.read_text(encoding="utf-8"))
        )
    ]
    assert not offenders, (
        "a colour is being derived by mixing a token toward white/black. That "
        "mints a hue no token declares, and any contrast measured for it was "
        "taken on the retired dark ground — on carta, lightening is the "
        "direction of FAILURE. Use a declared token: " + "; ".join(offenders)
    )


def test_the_derived_mix_guard_catches_the_historical_offenders() -> None:
    """Guilt: the exact declarations this class was found in must trip it."""
    for guilty in (
        "--fill: color-mix(in srgb, var(--accent-funnel) 85%, black);",
        "color: color-mix(in srgb, var(--accent-funnel) 70%, white);",
        "color-mix(\n  in srgb,\n  var(--accent-funnel) 85%,\n  black\n)",
    ):
        assert _deriving_mixes(guilty), f"guard blind to: {guilty}"


def test_the_derived_mix_guard_leaves_opacity_tints_alone() -> None:
    """Innocence: mixing toward `transparent` keeps the token's own hue."""
    for innocent in (
        "background: color-mix(in srgb, var(--state-success) 6%, transparent);",
        "border: 1px solid color-mix(in srgb, var(--text-primary) 45%, transparent);",
        "background: color-mix(in srgb, currentColor 10%, transparent);",
        # A token whose NAME contains the word is not a literal argument.
        "background: color-mix(in srgb, var(--surface-white) 8%, transparent);",
    ):
        assert not _deriving_mixes(innocent), (
            f"guard over-matches an opacity tint: {innocent}"
        )
