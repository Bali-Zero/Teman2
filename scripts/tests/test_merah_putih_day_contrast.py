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
    # The portal vocabulary ConsentBanner brings into this wrapper. Measured at
    # 2.56 and 2.90 before the day set answered for them.
    ("--tx-secondary", "--surface-raised", AA_TEXT),
    ("--bz-accent", "--surface-raised", AA_TEXT),
]

# White text is legal ONLY on these fills (R4 §4.2).
WHITE_ON = [
    "--accent-funnel",
    "--accent-funnel-text",
    "--cta-bg",  # the primary CTA fill — StudioApp's primaryNavButtonStyle
    "--cta-bg-hover",
    "--state-danger",
    "--bz-accent",  # ConsentBanner's dismiss button paints white on it
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


_SHARED_IMPORT = re.compile(r"""^import\s[^;]*?from\s+["'](@/components/[^"']+)["']""", re.M)


def _perimeter_sources() -> list[Path]:
    """Every .tsx that PAINTS inside the two converted wrappers.

    The route tree alone is NOT that set, and believing it was is what let the
    worst defect of this migration ship green. `ConsentBanner` lives at
    apps/mouth/src/components/visa/ — outside PERIMETER — yet renders as a
    descendant of both wrappers, and it speaks a token vocabulary the day set
    did not answer for: measured 2.56:1 body text and 2.90:1 links on the new
    ground. Every guard here reported clean while that was true, because none
    of them could see the file.

    So the set is the route tree PLUS whatever `@/components/...` the two
    wrappers actually import — resolved from the import statements, so a
    component added tomorrow is covered without anyone remembering to add it
    here. A hand-kept list would rot on its first commit.
    """
    files = {p for p in PERIMETER.rglob("*.tsx") if not p.name.endswith(".test.tsx")}
    src_root = REPO / "apps/mouth/src"
    for wrapper in (
        PERIMETER / "SecondHomeLanding.tsx",
        PERIMETER / "studio/StudioApp.tsx",
    ):
        for spec in _SHARED_IMPORT.findall(wrapper.read_text(encoding="utf-8")):
            candidate = src_root / (spec.removeprefix("@/") + ".tsx")
            if candidate.exists():
                files.add(candidate)
    return sorted(files)


_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_comments(src: str) -> str:
    """Remove JS/TS comments so the guard judges PAINTED VALUES, not prose.

    A retired hex NAMED in a comment ("we replaced the retired #ff3344") paints
    nothing — flagging it would push authors to stop explaining themselves, which
    is how a codebase loses the reason behind its own rules (scar family #3,
    over-match). `test_the_stripper_cannot_hide_a_real_use` is the guilt half
    that keeps this leniency honest.

    Line comments are NOT stripped with `//[^\\n]*`. That regex has no idea what
    a string literal is, so a URL inside one decapitates the rest of the line:
    `const a = "https://x"; const s = { color: "#ff3344" }` was truncated at
    `"https:` and the retired colour after it became invisible to every guard
    here. Demonstrated in `test_the_stripper_survives_a_url_in_a_string`. Hence
    the small scanner below: it tracks quote state, so `//` only starts a
    comment when it is not inside a string.
    """
    src = _BLOCK_COMMENT.sub("", src)
    out: list[str] = []
    quote: str | None = None
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:  # an escaped char cannot close the string
                out.append(src[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "\"'`":
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


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


def test_the_stripper_survives_a_url_in_a_string() -> None:
    """Guilt: `//` inside a string literal must NOT start a comment.

    The naive `//[^\n]*` truncated at the URL's slashes and silently deleted a
    real declaration later on the same line — so a retired colour could sit in
    painted code and every guard here would report clean.
    """
    line = 'const img = "https://cdn.example/hero.png"; const s = { color: "#ff3344" };'
    assert "#ff3344" in strip_comments(line), (
        "a URL inside a string ate the rest of the line — the stripper is "
        "hiding painted colours from every guard in this file"
    )
    # And the leniency it exists for still works.
    assert "#ff3344" not in strip_comments("// we retired #ff3344 here")
    assert "#ff3344" not in strip_comments("/* retired: #ff3344 */")


def test_the_perimeter_sees_shared_components_rendered_inside_the_wrappers() -> None:
    """The route tree is not the painted set.

    ConsentBanner lives outside PERIMETER but renders inside both wrappers. A
    guard that cannot see it reported clean while it measured 2.56:1.
    """
    names = {p.name for p in _perimeter_sources()}
    assert "ConsentBanner.tsx" in names, (
        "shared components imported by the wrappers are not being scanned — "
        f"saw only: {sorted(names)}"
    )
    assert "SecondHomeLanding.tsx" in names and "StudioApp.tsx" in names


WORKFLOW = REPO / ".github/workflows/merah-putih-day-contrast.yml"


def _paths_glob_to_regex(pattern: str) -> re.Pattern[str]:
    """GitHub's `paths:` glob, narrowed to the two wildcards this filter uses.

    `**` crosses directory separators, a single `*` does not. Order matters:
    `re.escape` turns `**` into `\\*\\*`, so that must be substituted BEFORE the
    single-star rule, or the first star eats the second.
    """
    rx = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.compile(rx + r"\Z")


def _workflow_trigger_paths() -> list[str]:
    import yaml  # deliberately function-local: a missing pyyaml must break THIS
    # test, not error out the other 42 — and it must FAIL, never skip. A guard
    # that skips itself when its parser is absent is the disarmament this whole
    # file exists to prevent.

    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML implements YAML 1.1, where a bare `on:` key parses as the BOOLEAN
    # True, not the string "on". Reading doc["on"] here returns None on a
    # perfectly valid workflow and the assertion below would pass on an empty
    # list — vacuously green, which is worse than red.
    trigger = doc.get("on", doc.get(True))
    assert trigger, f"{WORKFLOW.name}: no trigger block parsed — check the YAML 1.1 `on:` key trap"
    # The list moved from `pull_request.paths` to `push.paths` on 2026-09-03,
    # when this workflow took the shape a REQUIRED context must have. The
    # trigger no longer filters PRs at all — the in-job sentinel reads THIS
    # list and decides — so `push.paths` is now the single copy, and both the
    # sentinel and this test read it from here.
    paths = trigger["push"]["paths"]
    assert paths, f"{WORKFLOW.name}: `push.paths` is empty — the guarded set cannot be nothing"
    return list(paths)


def test_the_workflow_trigger_covers_every_file_this_guard_reads() -> None:
    """Arming a guard behind a filter that misses the files it protects is the
    same defect one level up — and it is invisible, because the job simply never
    starts and the PR is green with nothing having run.

    This is why the coverage is COMPUTED from the guard's own read set rather
    than eyeballed against the workflow: the perimeter resolves shared
    `@/components/...` imports out of the two wrappers, so the painted set grows
    whenever a wrapper adds an import — and the first version of that filter
    named only the route tree and missed ConsentBanner and WhatsAppLeadButton
    entirely.
    """
    patterns = [_paths_glob_to_regex(p) for p in _workflow_trigger_paths()]

    # The instrument must be able to say NO, or every assertion below is
    # vacuous. A probe that cannot return a negative cannot return a positive.
    assert not any(
        rx.match("packages/core/tokens/themes/editorial.css") for rx in patterns
    ), "the glob matcher matches everything — it is not measuring the filter"

    read_set = {TOKENS, SEMANTIC_CSS, Path(__file__).resolve(), WORKFLOW}
    read_set.update(_perimeter_sources())

    uncovered = sorted(
        str(p.relative_to(REPO))
        for p in read_set
        if not any(rx.match(str(p.relative_to(REPO))) for rx in patterns)
    )
    assert not uncovered, (
        "these files are READ by this guard but match no `paths:` pattern in "
        f"{WORKFLOW.name}, so changing one starts no check run:\n  "
        + "\n  ".join(uncovered)
    )


def test_the_workflow_has_the_shape_a_required_context_must_have() -> None:
    """A path-filtered check cannot be REQUIRED, and finding that out from a
    jammed merge queue is the expensive way.

    GitHub does not synthesise a passing report for a workflow that did not
    start: a required context whose `pull_request` trigger filters by path
    simply never reports on the PRs it does not match, and both the PR and the
    merge-queue entry wait for it forever. This repo has already paid that once
    (2026-08-30). The two properties below are what the required workflows here
    (`guard-conformance.yml`, `organ-conformance.yml`) have in common, and they
    are asserted rather than described so that a later edit re-adding a
    `paths:` filter to `pull_request` fails here instead of in the queue.

    Both halves matter independently: without `merge_group` the context never
    reports on the queue's own ref; with `pull_request.paths` it never reports
    on two thirds of the PRs.
    """
    import yaml

    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    trigger = doc.get("on", doc.get(True))
    assert trigger, f"{WORKFLOW.name}: no trigger block parsed"

    assert "pull_request" in trigger, f"{WORKFLOW.name}: no pull_request trigger"
    pr = trigger["pull_request"]
    # A bare `pull_request:` parses as None — that is the shape we want.
    assert pr is None or "paths" not in pr, (
        f"{WORKFLOW.name}: `pull_request` carries a `paths:` filter again. A "
        "required context must report on EVERY pull request; filter inside the "
        "job with the sentinel, never at the trigger."
    )
    assert "merge_group" in trigger, (
        f"{WORKFLOW.name}: no `merge_group:` trigger. A required context that "
        "never runs on the merge queue's ref leaves every entry waiting."
    )


def test_the_sentinel_reads_the_trigger_list_instead_of_restating_it() -> None:
    """The sentinel decides whether the guard runs. If it carried its own copy
    of the guarded paths, the copy would rot exactly like the hand-kept list
    this guard's docstring already warns about — and the failure is silent: the
    sentinel reports "nothing changed" for a file that did, and the job is green
    over a real regression.

    So the sentinel must READ `push.paths` out of the workflow at run time.
    This asserts the mechanism, not the wording: the sentinel step must parse
    this workflow file and index `push`/`paths`.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    sentinel = text.split("Did a guarded surface change?", 1)
    assert len(sentinel) == 2, f"{WORKFLOW.name}: the sentinel step is gone"
    body = sentinel[1].split("- name:", 1)[0]
    assert "merah-putih-day-contrast.yml" in body, (
        "the sentinel does not read this workflow file — it is deciding from "
        "something other than the trigger's own list"
    )
    assert '["push"]["paths"]' in body, (
        "the sentinel does not index `push.paths` — if it now keeps its own "
        "pattern list, the trigger and the gate can disagree silently"
    )


# ---------------------------------------------------------------------------
# The sentinel is executed here, not just grepped. Two defects found by the
# Gear-3 council on 2026-09-04 were both invisible to the static assertions
# above: (1) the whole heredoc was piped into $GITHUB_OUTPUT, notice line
# included, so the "nothing guarded changed" path — the one this promotion
# exists to make green — went red on an invalid env-file line; (2) the pattern
# list was read from the PR's OWN copy of this file, so a PR that narrowed
# `push.paths` judged itself by its own shortened list.
# ---------------------------------------------------------------------------


def _sentinel_snippet() -> str:
    """The python between `<<'PY'` and `PY` inside the sentinel step, dedented."""
    import textwrap

    text = WORKFLOW.read_text(encoding="utf-8")
    body = text.split("Did a guarded surface change?", 1)[1].split("- name:", 1)[0]
    start = body.index("<<'PY'\n") + len("<<'PY'\n")
    end = body.index("\n          PY\n", start)
    return textwrap.dedent(body[start:end])


def _run_sentinel(tmp_path, changed: list[str], **env_extra: str) -> "subprocess.CompletedProcess[str]":
    import os
    import subprocess
    import sys

    changed_file = tmp_path / "changed.txt"
    changed_file.write_text("\n".join(changed) + "\n", encoding="utf-8")
    env = {**os.environ, "BASE_SHA": "HEAD", "CHANGED_FILE": str(changed_file), **env_extra}
    return subprocess.run(
        [sys.executable, "-"],
        input=_sentinel_snippet(),
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
        check=False,
    )


def test_the_sentinel_prints_exactly_one_word_for_github_output(tmp_path) -> None:
    """Innocence for defect (1): on an unguarded change the snippet's stdout is
    the single word `false` — nothing else may reach `$GITHUB_OUTPUT`."""
    res = _run_sentinel(tmp_path, ["README.md"])
    assert res.returncode == 0, res.stderr
    assert res.stdout == "false\n", (
        "the sentinel wrote more than `false` to stdout — anything but the "
        f"verdict word becomes an invalid $GITHUB_OUTPUT line: {res.stdout!r}"
    )
    res = _run_sentinel(tmp_path, ["apps/mouth/src/lib/theme/merahPutihDayVars.ts"])
    assert res.returncode == 0, res.stderr
    assert res.stdout == "true\n"


def test_only_the_verdict_line_is_appended_to_github_output() -> None:
    """Guilt for defect (1), at the shell layer: the heredoc must not be
    redirected into `$GITHUB_OUTPUT`; only an `echo "run=…"` may write there."""
    text = WORKFLOW.read_text(encoding="utf-8")
    body = text.split("Did a guarded surface change?", 1)[1].split("- name:", 1)[0]
    assert '<<\'PY\' >> "$GITHUB_OUTPUT"' not in body, (
        "the sentinel pipes its whole heredoc into $GITHUB_OUTPUT again — the "
        "::notice:: line is not NAME=VALUE and the runner fails the step"
    )
    writers = [
        l.strip()
        for l in body.splitlines()
        if "$GITHUB_OUTPUT" in l and not l.strip().startswith("#")
    ]
    assert writers and all(l.startswith('echo "run=') for l in writers), writers


def test_a_pr_that_narrows_its_own_list_cannot_disarm_the_sentinel(tmp_path) -> None:
    """Guilt for defect (2): the PR's copy of this workflow drops every guarded
    path but one unrelated file. The sentinel must still say `true` for a
    token-file change, because it also reads the BASE copy the PR cannot edit."""
    narrowed = tmp_path / "narrowed.yml"
    narrowed.write_text(
        "on:\n  push:\n    paths:\n      - \"docs/never-touched.md\"\n", encoding="utf-8"
    )
    res = _run_sentinel(
        tmp_path,
        ["apps/mouth/src/lib/theme/merahPutihDayVars.ts"],
        HEAD_WORKFLOW=str(narrowed),
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout == "true\n", (
        "the sentinel judged itself by the PR's own narrowed list — a PR can "
        "shrink `push.paths` and skip the corpus that would catch it"
    )


def test_the_sentinel_reads_the_base_copy_via_git_show() -> None:
    """The static half of the base-copy guarantee; the executable half is
    `test_a_pr_that_narrows_its_own_list_cannot_disarm_the_sentinel`.

    This used to assert the literal `"git", "show"`, which pinned the SPELLING
    rather than the mechanism: wrapping the same call in a `_git(*args)` helper
    — as the fail-closed cure did — broke it while the sentinel still read the
    base copy exactly as before. Rewritten to name the two things that actually
    have to be true (a `show` of the base ref's own copy of this workflow, at
    `BASE_SHA`), so a helper rename passes and REMOVING the base read fails.
    """
    body = (
        WORKFLOW.read_text(encoding="utf-8")
        .split("Did a guarded surface change?", 1)[1]
        .split("- name:", 1)[0]
    )
    assert '"show"' in body and "BASE_SHA" in body, (
        "the sentinel no longer reads the base ref's copy of its pattern list"
    )
    assert "base_sha}:{WORKFLOW}" in body, (
        "the sentinel no longer addresses the BASE ref's copy of THIS workflow — "
        "if it now shows some other path or ref, the PR-controlled head copy is "
        "the only list in play"
    )


# ---------------------------------------------------------------------------
# The two conditions the Gear-3 gate attached to #5614's PASS-WITH-CONDITIONS.
# Both were prose in that PR's body and prose is not in force, so each is
# asserted here — and the sentinel one is EXECUTED rather than grepped, because
# a fail-closed path that is only described is exactly the shape that fails open
# the first time anyone reads it.
# ---------------------------------------------------------------------------


def test_the_concurrency_group_never_cancels_a_merge_group_run() -> None:
    """Condition 1. `github.ref` on a merge_group event is the QUEUE's ref, not
    this PR's — so a bare `cancel-in-progress: true` lets the queue's next entry
    cancel the entry ahead of it. A cancelled required context does not report a
    failure, it reports nothing, and the entry is torn out of the queue rather
    than merely delayed. Cancelling is right on `pull_request`, where the ref is
    the PR's own and the superseded run is genuinely dead work.
    """
    import yaml

    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    concurrency = doc.get("concurrency")
    assert concurrency, f"{WORKFLOW.name}: the concurrency block is gone"

    cancel = str(concurrency.get("cancel-in-progress", "")).strip()
    assert cancel not in {"True", "true"}, (
        f"{WORKFLOW.name}: `cancel-in-progress` is unconditionally true again. On "
        "a merge_group event the group key is the queue's own ref, so this "
        "cancels the entry ahead of this one and a cancelled required context "
        "never reports."
    )
    assert "github.event_name" in cancel and "merge_group" in cancel, (
        f"{WORKFLOW.name}: `cancel-in-progress` is {cancel!r} — it must be an "
        "expression that turns cancelling OFF for merge_group specifically, not "
        "a blanket value."
    )


def test_the_sentinel_runs_the_guard_when_the_base_ref_cannot_be_read(tmp_path) -> None:
    """Condition 2, guilt. An unreachable base sha (shallow checkout, unfetched
    ref) means the trust boundary — reading the pattern list from the copy the PR
    cannot edit — could not be applied. The sentinel must then run the WHOLE
    guard, not fall back to the head-only list it just declined to trust.

    Guilt, not innocence: the change below touches nothing guarded, so the
    head-only reading would print `false` and skip the corpus. Fail-closed is
    the only way `true` comes out of this.
    """
    res = _run_sentinel(
        tmp_path,
        ["README.md"],
        BASE_SHA="0000000000000000000000000000000000000000",
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout == "true\n", (
        "the sentinel could not read the base ref and still declared a no-op — "
        "it failed OPEN. An unreadable base means the PR-controlled head copy is "
        f"the only list available, which is precisely what must not be trusted. "
        f"stdout={res.stdout!r} stderr={res.stderr!r}"
    )


def test_a_pr_that_introduces_this_workflow_is_not_forced_through_the_guard(tmp_path) -> None:
    """Condition 2, innocence. "The base has no copy of this file" is NOT the
    same event as "the base cannot be read", and conflating them would make the
    fail-closed path fire on every PR that adds a workflow — the guard would run
    its full corpus on unrelated changes forever.

    Here the base ref IS reachable (HEAD) but the workflow is read from a path
    that does not exist in it, so only the head list applies and an unguarded
    change must still come back `false`.
    """
    import subprocess

    empty_base = subprocess.run(
        ["git", "commit-tree", "-m", "empty", subprocess.run(
            ["git", "hash-object", "-t", "tree", "/dev/null"],
            capture_output=True, text=True, cwd=REPO, check=True,
        ).stdout.strip()],
        capture_output=True, text=True, cwd=REPO, check=True,
    ).stdout.strip()

    res = _run_sentinel(tmp_path, ["README.md"], BASE_SHA=empty_base)
    assert res.returncode == 0, res.stderr
    assert res.stdout == "false\n", (
        "a reachable base that simply does not contain this workflow was treated "
        "as an unreadable base — the fail-closed path is over-matching, and every "
        "PR introducing a workflow now runs the full corpus. "
        f"stdout={res.stdout!r} stderr={res.stderr!r}"
    )
