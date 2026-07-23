"""Tests for scripts/token_lint.py (WS1 token-SSOT gate: no NEW hardcoded
brand hex colors in the redesigned route groups).

Doctrine (cicatrix-superscar.md #3, same as scripts/prepush_classify.py):
"nessuna guardia mergiata senza un test di innocenza E di colpevolezza" —
no guard merges without BOTH an innocence test and a guilt test. Every
exemption in the module (comment lines, token-source paths, the
`token-lint-ok: <reason>` marker, out-of-scope paths) has a dedicated
INNOCENCE test; every flagged shape (workspace hex, portal hex, bare
marker without reason) has a dedicated GUILT test; the error paths
(malformed diff input) prove the fail-closed exit-2 contract.

The module under test is imported directly (no subprocess) for the pure
`scan()`/`parse_unified_diff()` logic — fast and exhaustive. A handful of
CLI-level tests drive the real `python3 scripts/token_lint.py` entrypoint
via subprocess to prove the --stdin/--files/exit-code/stdout contract
itself actually holds (and never needs git).

Run:  python3 -m pytest scripts/tests/test_token_lint.py -q
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "token_lint.py"
_spec = importlib.util.spec_from_file_location("token_lint", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
tl = importlib.util.module_from_spec(_spec)
# Register in sys.modules BEFORE exec_module: @dataclass resolution under
# `from __future__ import annotations` looks up the module there (3.11).
sys.modules["token_lint"] = tl
_spec.loader.exec_module(tl)  # type: ignore[union-attr]

WORKSPACE_PAGE = "apps/mouth/src/app/(workspace)/accounting/page.tsx"
PORTAL_PAGE = "apps/mouth/src/app/portal/dashboard/page.tsx"
MARKETING_PAGE = "apps/mouth/src/app/(marketing)/page.tsx"
TOKEN_FILE = "packages/core/tokens/semantic.css"


def make_diff(path: str, added: list[str], *, start: int = 1, new_file: bool = True) -> str:
    """Build a minimal, well-formed unified diff adding `added` to `path`.

    `start` is the new-file line number of the first added line, so tests
    can assert exact `path:line:` reporting (e.g. start=71 -> line 71).
    """
    header = [f"diff --git a/{path} b/{path}"]
    if new_file:
        header += ["new file mode 100644", "--- /dev/null"]
    else:
        header += ["index 1111111..2222222 100644", f"--- a/{path}"]
    header.append(f"+++ b/{path}")
    old_start = 0 if new_file else start
    header.append(f"@@ -{old_start},0 +{start},{len(added)} @@")
    return "\n".join(header + [f"+{line}" for line in added]) + "\n"


def make_rename_diff(old: str, new: str, *, similarity: int = 100) -> str:
    """Build a minimal pure-rename diff (no content hunks — the round-5
    invisibility shape: the parser sees zero additions for this file)."""
    return (
        f"diff --git a/{old} b/{new}\n"
        f"similarity index {similarity}%\n"
        f"rename from {old}\n"
        f"rename to {new}\n"
    )


# ---------------------------------------------------------------------------
# Sanity on the SSOT constants themselves.
# ---------------------------------------------------------------------------


def test_scoped_prefixes_exist_on_disk() -> None:
    """The scope is verified, never presumed (golden rule #9): every encoded
    prefix MUST be a real directory in this tree. `(authenticated)` was
    verified ABSENT on 2026-07-19 and is deliberately not encoded — if it
    appears later, add it to SCOPED_PREFIXES and this test keeps passing."""
    assert tl.SCOPED_PREFIXES, "SCOPED_PREFIXES must not be empty"
    for prefix in tl.SCOPED_PREFIXES:
        assert (REPO_ROOT / prefix).is_dir(), (
            f"scoped prefix {prefix!r} is encoded in token_lint.py but does "
            "not exist on disk — the scope is stale"
        )
    assert "apps/mouth/src/app/(workspace)/" in tl.SCOPED_PREFIXES
    assert "apps/mouth/src/app/portal/" in tl.SCOPED_PREFIXES


def test_scoped_prefixes_have_trailing_slash() -> None:
    """Every prefix ends in '/' so `portal` can never prefix-match a
    lookalike sibling like `portal-old/` (the same word-boundary disease
    cicatrix-superscar.md #3 keeps finding in bare prefix checks)."""
    for prefix in tl.SCOPED_PREFIXES:
        assert prefix.endswith("/"), f"prefix {prefix!r} must end with '/'"


# ---------------------------------------------------------------------------
# GUILT — new hardcoded hexes in scoped surfaces MUST be flagged.
# ---------------------------------------------------------------------------


def test_guilt_workspace_page_hex() -> None:
    """The canonical guilt case from the mandate: `#d4845a` added in a
    (workspace) page -> exactly one violation, with file:line reporting."""
    diff = make_diff(WORKSPACE_PAGE, ['const BRAND = "#d4845a";'], start=71)
    result = tl.scan(diff, [WORKSPACE_PAGE])
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.path == WORKSPACE_PAGE
    assert violation.line == 71
    assert violation.hex == "#d4845a"
    assert result.scanned_file_count == 1


def test_guilt_portal_hex() -> None:
    """The second scoped route group is guarded too."""
    diff = make_diff(PORTAL_PAGE, ["color: #fff;"], start=3)
    result = tl.scan(diff, [PORTAL_PAGE])
    assert [v.hex for v in result.violations] == ["#fff"]


def test_guilt_bare_marker_without_reason_still_flagged() -> None:
    """`token-lint-ok` WITHOUT `: <reason>` does NOT exempt — the reason is
    the audit trail; a bare marker is exactly the lazy escape hatch the
    required-reason rule exists to close."""
    line = 'fill: #d4845a; // token-lint-ok'
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#d4845a"]


def test_guilt_marker_with_empty_reason_still_flagged() -> None:
    """`token-lint-ok:` with nothing after the colon is still not a reason."""
    line = "fill: #d4845a; // token-lint-ok: "
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#d4845a"]


def test_guilt_multiple_hexes_one_line() -> None:
    """Two DISTINCT hexes on one added line -> two violations on the same
    line number (each unique hex is reported once)."""
    line = 'background: linear-gradient(#d4845a, #1a2b3c);'
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line], start=9), [WORKSPACE_PAGE])
    assert [(v.hex, v.line) for v in result.violations] == [
        ("#d4845a", 9),
        ("#1a2b3c", 9),
    ]


def test_guilt_eight_digit_hex_matches_once() -> None:
    """Longest-first: `#d4845a00` (RGBA 8-digit) is ONE violation, not a
    6-digit match plus noise."""
    result = tl.scan(make_diff(WORKSPACE_PAGE, ["color: #d4845a00;"]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#d4845a00"]


# ---------------------------------------------------------------------------
# INNOCENCE — every exemption has its own proof.
# ---------------------------------------------------------------------------


def test_innocence_1_token_source_file() -> None:
    """Innocence-1 (mandate): the same hex in `packages/core/tokens/x.css`
    passes — that file IS the SSOT the gate protects. Round-3 (codex RED):
    ONLY the two declared SSOT roots exempt (packages/core/tokens/ and
    apps/mouth/src/styles/) — the generic `tokens/` segment rule is gone."""
    result = tl.scan(make_diff(TOKEN_FILE, ["--accent-funnel: #d4845a;"]), [TOKEN_FILE])
    assert result.violations == []
    assert tl.is_token_source(TOKEN_FILE)


def test_guilt_tokens_segment_not_exempt() -> None:
    """GUILT (PR #2987 round-3, codex RED finding 1): the round-2 generic
    `tokens/` path-SEGMENT rule still let route-local files bypass. A hex
    in `portal/tokens/theme.css` AND in `portal/tokens/component.tsx` MUST
    both be flagged — exemption is by SSOT LOCATION, never by name-shape."""
    for trap in (
        "apps/mouth/src/app/portal/tokens/theme.css",
        "apps/mouth/src/app/portal/tokens/component.tsx",
    ):
        assert not tl.is_token_source(trap), f"still exempt: {trap}"
        result = tl.scan(make_diff(trap, ["--x: #d4845a;"]), [trap])
        assert [v.hex for v in result.violations] == ["#d4845a"], trap


def test_guilt_basename_trap_tokens_files() -> None:
    """GUILT (PR #2987 round-2, Tri-LLM finding 1): the v1 basename globs
    (`tokens*.css`, `*.tokens.*`) gave a free SSOT pass to files that merely
    LOOK token-ish by name. A route-local `portal/tokens.css` or a
    `brand.tokens.tsx` inside a scoped route MUST be flagged — only real
    token-source LOCATIONS (prefix or `tokens/` segment) exempt."""
    basename_trap = "apps/mouth/src/app/portal/tokens.css"
    assert not tl.is_token_source(basename_trap)
    result = tl.scan(make_diff(basename_trap, ["--x: #d4845a;"]), [basename_trap])
    assert [v.hex for v in result.violations] == ["#d4845a"]
    glob_trap = "apps/mouth/src/app/(workspace)/brand.tokens.tsx"
    assert not tl.is_token_source(glob_trap)
    result = tl.scan(make_diff(glob_trap, ['const C = "#d4845a";']), [glob_trap])
    assert [v.hex for v in result.violations] == ["#d4845a"]


def test_innocence_1b_styles_directory() -> None:
    """`apps/mouth/src/styles/` is a token-source prefix too."""
    path = "apps/mouth/src/styles/kbli-theme.css"
    assert tl.is_token_source(path)
    result = tl.scan(make_diff(path, [":root { --c: #d4845a; }"]), [path])
    assert result.violations == []


def test_innocence_2_full_line_comment() -> None:
    """Innocence-2 (mandate): a hex in a full-line comment passes — every
    comment shape the module recognizes, including the hardened `^\\*\\s`
    (star + whitespace, no CSS-rule chars) block-continuation shape."""
    comment_lines = [
        "// brand orange: #d4845a",
        "/* legacy: #d4845a */",
        "* #d4845a (inside a block comment)",
        "   * indented block-comment interior #d4845a",
        "<!-- #d4845a -->",
        " * see tokens.css for values",
    ]
    for line in comment_lines:
        assert tl.is_comment_line(line), f"not recognized as comment: {line!r}"
        result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
        assert result.violations == [], f"comment line was flagged: {line!r}"


def test_guilt_universal_selector_not_a_comment() -> None:
    """GUILT (PR #2987 round-2, Tri-LLM finding 2): `* { color: #d4845a; }`
    is the CSS universal selector, NOT a block-comment continuation — the
    v1 bare-`*` prefix test waved it through the comment exemption."""
    line = "* { color: #d4845a; }"
    assert not tl.is_comment_line(line)
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#d4845a"]
    # `*/` is a block-comment ENDER, not a continuation — it no longer
    # matches the predicate at all (it never carries a hex, but lock the
    # predicate shape honestly).
    assert not tl.is_comment_line("*/")


def test_guilt_commented_out_css_rule_judged_as_code() -> None:
    """Documented honest cost of the finding-2 fix (module docstring,
    exemption 1): `* color: #d4845a;` inside a real comment block carries
    CSS-rule characters, so it is judged as code, not as a comment.
    Legitimate doc lines carrying a hex use exemption 3
    (`token-lint-ok: <reason>`)."""
    line = "* color: #d4845a;"
    assert not tl.is_comment_line(line)
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#d4845a"]


def test_guilt_inline_closed_comment_then_code() -> None:
    """GUILT (PR #2987 round-3, codex RED finding 2): an opener CLOSED on
    the same line exempts only the comment part — the code AFTER the closer
    is judged, at the line's real number."""
    line = "/* legacy */ color: #d4845a;"
    assert tl.effective_code(line) == "color: #d4845a;"  # remainder is lstripped
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line], start=42), [WORKSPACE_PAGE])
    assert [(v.line, v.hex) for v in result.violations] == [(42, "#d4845a")]
    html_line = "<!-- x --> background: #c9a96e;"
    result = tl.scan(make_diff(WORKSPACE_PAGE, [html_line]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#c9a96e"]


def test_guilt_chained_leading_comments_then_code() -> None:
    """GUILT (PR #2987 round-4, codex RED P0): the round-3 strip removed
    only the FIRST leading closed comment — `/* first */ /* second */
    color: #d4845a;` left a remainder starting with `/*` again, which the
    comment exemption then exempted wholesale. The strip now LOOPS."""
    line = "/* first */ /* second */ color: #d4845a;"
    assert tl.effective_code(line) == "color: #d4845a;"
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#d4845a"]


def test_innocence_chained_comments_pure_comment() -> None:
    """INNOCENCE (round-4 P0 counterpart): after stripping chained leading
    comments, plain comment text with no hex still passes — the loop
    changes WHAT is judged, not whether plain prose is a violation."""
    line = "/* a */ /* b */ pure comment"
    assert tl.effective_code(line) == "pure comment"
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
    assert result.violations == []


def test_guilt_jsx_comment_then_code() -> None:
    """GUILT (PR #2987 round-6, k3): the JSX block-comment shape gets the
    same closed-on-same-line semantics as `/* */` — `{/* legacy */}` closed
    on the same line exempts only the comment part, never the whole line."""
    line = "{/* legacy */} color: #d4845a;"
    assert tl.effective_code(line) == "color: #d4845a;"
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#d4845a"]
    chained = "{/* a */} {/* b */} color: #c9a96e;"
    assert tl.effective_code(chained) == "color: #c9a96e;"
    result = tl.scan(make_diff(WORKSPACE_PAGE, [chained]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#c9a96e"]


def test_innocence_jsx_full_line_comment() -> None:
    """INNOCENCE (round-6, k3): a full-line JSX block comment IS a comment —
    no false positive in .tsx, the gate's main target."""
    for line in (
        "{/* palette: #d4845a */}",
        "{/* unclosed JSX comment swallows the line: #c9a96e",
    ):
        result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
        assert result.violations == [], f"flagged: {line!r}"


def test_guilt_jsx_closer_with_space_before_brace() -> None:
    """GUILT (PR #2987 round-8, codex P0): `{/* comment */ }` (whitespace
    before the brace) is valid JSX — treating it as unclosed would exempt
    the whole line and smuggle the hex."""
    line = "{/* comment */ } color: #d4845a;"
    assert tl.effective_code(line) == "color: #d4845a;"
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#d4845a"]


def test_innocence_jsx_full_line_comment_spaced_brace() -> None:
    """INNOCENCE (round-8): a full-line JSX comment with a spaced brace is
    still a comment."""
    result = tl.scan(
        make_diff(WORKSPACE_PAGE, ["{/* palette: #d4845a */ }"]),
        [WORKSPACE_PAGE],
    )
    assert result.violations == []


def test_workflow_scan_step_runs_before_proof_suite() -> None:
    """ORDERING LOCK (PR #2987 round-6, codex RED P0): the scan step MUST
    run before the pytest proof suite in the gate workflow. pytest
    auto-loads conftest.py from the PR head, so proof-first would let a
    hostile conftest (pytest hooks) rewrite the scanner after the proofs
    but before the scan executes it. String-index check on the raw file —
    deliberately no yaml dependency (the CI proof step installs pytest
    only; PyYAML is not guaranteed)."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "token-lint.yml").read_text(
        encoding="utf-8"
    )
    fetch_idx = workflow.index("- name: Fetch base ref")
    scan_idx = workflow.index("- name: token-lint — scan added lines")
    proof_idx = workflow.index("- name: token-lint proof suite")
    assert fetch_idx < scan_idx, "scan needs origin/<base> fetched first"
    assert scan_idx < proof_idx, (
        "scan must run before the proof suite (recursive-disarm guard) — "
        "see the ORDERING IS LOAD-BEARING note in the workflow"
    )


def test_meta_verifier_push_trigger_covers_conftest_sentinel() -> None:
    """A main-only conftest change must wake the same meta-verifier whose
    PR relevance regex already treats conftest as load-bearing."""
    workflow = (
        REPO_ROOT / ".github" / "workflows" / "verify-the-verifiers.yml"
    ).read_text(encoding="utf-8")
    push_block = workflow.split("  push:", 1)[1].split("\nconcurrency:", 1)[0]
    relevant_step = workflow.split("- name: Did relevant paths change?", 1)[1].split(
        "- uses: actions/setup-python", 1
    )[0]
    assert '- "scripts/tests/conftest.py"' in push_block
    assert r"scripts/tests/conftest\.py" in relevant_step


def test_innocence_inline_comment_fully_closed() -> None:
    """INNOCENCE (finding 2 counterpart): when the closer ends the line (or
    never comes), nothing judgeable remains."""
    for line in (
        "/* palette: #d4845a #c9a96e */",
        "<!-- brand #ff2d4c -->",
        "/* unclosed opener swallows the rest of the line: #d4845a",
    ):
        result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
        assert result.violations == [], f"flagged: {line!r}"


def test_innocence_3_ok_marker_with_reason() -> None:
    """Innocence-3 (mandate): `token-lint-ok: <reason>` exempts the line."""
    line = "background: #d4845a; // token-lint-ok: brand logo asset"
    result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
    assert result.violations == []


def test_innocence_4_out_of_scope_marketing_page() -> None:
    """Innocence-4 (mandate): a hex added in a marketing page OUTSIDE the
    scoped route groups passes — the gate guards the redesigned surfaces,
    not the whole repo."""
    result = tl.scan(make_diff(MARKETING_PAGE, ['const C = "#d4845a";']), [MARKETING_PAGE])
    assert result.violations == []
    assert result.scanned_file_count == 0


def test_innocence_non_color_shapes_not_flagged() -> None:
    """Word-boundary discipline: markdown headings, HTML entities, and
    5-digit non-colors are not hex colors."""
    lines = [
        "## Section d4845a heading",  # ## is not a color
        "&#039; is an HTML entity",  # entity, not a color
        "id: #fffff",  # 5 digits — not a valid CSS hex
        "anchor: #go",  # not hex digits
    ]
    result = tl.scan(make_diff(WORKSPACE_PAGE, lines), [WORKSPACE_PAGE])
    assert result.violations == []


def test_innocence_files_list_filters_diff() -> None:
    """The --files contract: added lines attributed by the diff to a path
    NOT in the changed-file list are ignored (mirrors the
    `git diff --name-only` union in the real flow)."""
    diff = make_diff(PORTAL_PAGE, ["color: #d4845a;"])
    result = tl.scan(diff, [MARKETING_PAGE])  # portal page not in the list
    assert result.violations == []


# ---------------------------------------------------------------------------
# ERROR PATHS — malformed input fails CLOSED (exit 2), never waves through.
# ---------------------------------------------------------------------------


def test_error_malformed_hunk_header() -> None:
    bad = f"diff --git a/x b/x\n+++ b/x\n@@ not-a-hunk @@\n+color: #d4845a;\n"
    with pytest.raises(tl.DiffParseError):
        tl.parse_unified_diff(bad)


def test_error_hunk_before_file_header() -> None:
    with pytest.raises(tl.DiffParseError):
        tl.parse_unified_diff("@@ -0,0 +1 @@\n+x\n")


def test_error_hunk_body_overrun() -> None:
    """A body longer than the declared counts means the diff cannot be
    trusted (line numbers would silently drift — and silently IGNORING the
    extra `+` line would be fail-open, so the parser raises instead)."""
    # Shape 1: extra added line AFTER the hunk closed (outside any hunk).
    with pytest.raises(tl.DiffParseError):
        tl.parse_unified_diff("+++ b/x\n@@ -0,0 +1,1 @@\n+a\n+b\n")
    # Shape 2: removed line inside an addition-only hunk (count goes negative).
    with pytest.raises(tl.DiffParseError):
        tl.parse_unified_diff("+++ b/x\n@@ -0,0 +1,1 @@\n-removed\n")


def test_error_hunk_body_bad_sigil() -> None:
    bad = "+++ b/x\n@@ -0,0 +1,1 @@\n?a\n"
    with pytest.raises(tl.DiffParseError):
        tl.parse_unified_diff(bad)


def test_error_truncated_hunk_at_eof() -> None:
    """GUILT (PR #2987 round-2, Tri-LLM finding 3): EOF arriving BEFORE a
    hunk consumes its declared counts is a truncated diff — the parser must
    raise (fail-closed), not return a partial, trustworthy-looking result
    that could silently under-report violations."""
    truncated = "+++ b/x\n@@ -0,0 +1,5 @@\n+a\n+b\n"  # declares 5, delivers 2
    with pytest.raises(tl.DiffParseError):
        tl.parse_unified_diff(truncated)


def test_innocence_exact_count_hunk_then_eof() -> None:
    """INNOCENCE (finding 3 counterpart): a hunk that consumes EXACTLY its
    declared counts and then hits EOF is a complete, well-formed diff —
    normal parse, normal scan, no error."""
    exact = "+++ b/x\n@@ -0,0 +1,2 @@\n+a\n+b\n"
    added = tl.parse_unified_diff(exact)
    assert [(a.line, a.content) for a in added] == [(1, "a"), (2, "b")]
    result = tl.scan(exact, ["x"])
    assert result.violations == []  # out of scope, but parses clean


def test_error_state_leak_second_file_without_header() -> None:
    """GUILT (PR #2987 round-3, codex RED finding 3): per-file state must
    reset at every `diff --git` boundary — a malformed second file with
    hunks but no `+++` header used to INHERIT the first file's path, so its
    added lines were attributed to the wrong (possibly out-of-scope) file
    and the gate could exit clean. Now: fail-closed."""
    leaked = (
        f"diff --git a/{WORKSPACE_PAGE} b/{WORKSPACE_PAGE}\n"
        f"--- a/{WORKSPACE_PAGE}\n"
        f"+++ b/{WORKSPACE_PAGE}\n"
        "@@ -0,0 +1,1 @@\n"
        "+ok\n"
        "diff --git a/apps/mouth/src/app/(marketing)/m.tsx b/apps/mouth/src/app/(marketing)/m.tsx\n"
        "index 1111111..2222222 100644\n"
        "@@ -0,0 +1,1 @@\n"
        "+color: #d4845a;\n"
    )
    with pytest.raises(tl.DiffParseError):
        tl.parse_unified_diff(leaked)


def test_error_added_line_for_dev_null_file() -> None:
    """GUILT (finding 3, sibling guard): `+++ /dev/null` (deleted file)
    never carries additions — a `+` line in its hunk means the input is
    garbled -> fail-closed, never silently drop the line."""
    bad = "+++ /dev/null\n@@ -0,0 +1,1 @@\n+x\n"
    with pytest.raises(tl.DiffParseError):
        tl.parse_unified_diff(bad)


def test_innocence_two_file_diff_attributes_per_file() -> None:
    """INNOCENCE (finding 3 counterpart): a well-formed two-file diff keeps
    correct per-file attribution — the boundary reset changes nothing for
    honest input."""
    two = (
        f"diff --git a/{PORTAL_PAGE} b/{PORTAL_PAGE}\n"
        f"--- a/{PORTAL_PAGE}\n"
        f"+++ b/{PORTAL_PAGE}\n"
        "@@ -0,0 +1,1 @@\n"
        "+color: #d4845a;\n"
        f"diff --git a/{WORKSPACE_PAGE} b/{WORKSPACE_PAGE}\n"
        f"--- a/{WORKSPACE_PAGE}\n"
        f"+++ b/{WORKSPACE_PAGE}\n"
        "@@ -0,0 +5,1 @@\n"
        "+// comment: #c9a96e\n"
    )
    result = tl.scan(two, [PORTAL_PAGE, WORKSPACE_PAGE])
    assert [(v.path, v.line, v.hex) for v in result.violations] == [
        (PORTAL_PAGE, 1, "#d4845a")
    ]


def test_error_binary_marker_scoped_file() -> None:
    """GUILT (PR #2987 round-4, codex RED P0): a binary marker for a SCOPED
    file means the diff carries no readable content for a surface the gate
    must see (e.g. a `.gitattributes -diff` smuggle) — fail-closed, never
    a silent clean."""
    diff = (
        f"diff --git a/{WORKSPACE_PAGE} b/{WORKSPACE_PAGE}\n"
        "index 1111111..2222222 100644\n"
        f"Binary files a/{WORKSPACE_PAGE} and b/{WORKSPACE_PAGE} differ\n"
    )
    with pytest.raises(tl.DiffParseError):
        tl.scan(diff, [WORKSPACE_PAGE])


def test_innocence_binary_marker_out_of_scope() -> None:
    """INNOCENCE (round-4 P0 counterpart): a legitimately binary change
    OUTSIDE the scoped route groups (an image asset) must not block the
    gate — only scoped blind spots fail closed."""
    asset = "apps/mouth/public/logo.png"
    diff = (
        f"diff --git a/{asset} b/{asset}\n"
        "index 1111111..2222222 100644\n"
        f"Binary files a/{asset} and b/{asset} differ\n"
    )
    result = tl.scan(diff, [asset])
    assert result.violations == []


def test_error_binary_marker_unparseable() -> None:
    """A `Binary files` line that cannot be attributed to any path MIGHT be
    scoped -> fail-closed rather than guess."""
    with pytest.raises(tl.DiffParseError):
        tl.binary_marked_paths("Binary files <garbled>\n")


def test_git_diff_invocation_uses_text_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """GUILT guard (PR #2987 round-4, codex RED P0): --base mode MUST pass
    `--text` to git diff, so a `.gitattributes -diff` rule on scoped files
    cannot reduce the patch to `Binary files ... differ`. Asserted on the
    actual argv the module builds (subprocess fully mocked — no git needed)."""
    calls: list[list[str]] = []

    class _Proc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args: list[str], **kwargs: object) -> _Proc:
        calls.append(list(args))
        return _Proc()

    monkeypatch.setattr(tl.subprocess, "run", fake_run)
    names, text = tl._git_diff("origin/main")
    assert names == [] and text == ""
    assert calls[0][:3] == ["git", "diff", "--name-only"]
    unified_call = calls[1]
    assert "--unified=0" in unified_call
    assert "--text" in unified_call, "git diff lost --text — binary-mark bypass is back"


def test_cli_binary_marker_scoped_exit_2() -> None:
    """End-to-end (round-4 P0): a binary-marker diff for a scoped file via
    stdin exits 2 fail-closed — never a silent clean."""
    diff = (
        f"diff --git a/{WORKSPACE_PAGE} b/{WORKSPACE_PAGE}\n"
        f"Binary files a/{WORKSPACE_PAGE} and b/{WORKSPACE_PAGE} differ\n"
    )
    proc = _run_cli(["--stdin", "--files", WORKSPACE_PAGE], diff)
    assert proc.returncode == 2
    assert "fail-closed" in proc.stderr


# ---------------------------------------------------------------------------
# ROUND-5 — cross-scope rename ingress (codex RED P0).
# ---------------------------------------------------------------------------

RENAME_OLD = "apps/mouth/src/app/(marketing)/old.tsx"
RENAME_NEW = "apps/mouth/src/app/portal/new.tsx"


def test_parse_renames_pairs() -> None:
    renames = tl.parse_renames(make_rename_diff(RENAME_OLD, RENAME_NEW))
    assert renames == [tl.Rename(RENAME_OLD, RENAME_NEW)]


def test_guilt_cross_scope_rename_content_scanned_base_mode() -> None:
    """GUILT (PR #2987 round-5, codex RED P0): a 100% rename INTO a scoped
    prefix produces no added-line hunks, but the destination content is new
    to the gate's regime — in --base mode (reader wired to git show) its
    full content is judged."""
    diff = make_rename_diff(RENAME_OLD, RENAME_NEW)
    reads: list[str] = []

    def reader(path: str) -> str:
        reads.append(path)
        return 'const BRAND = "#d4845a";\nexport const ok = 1;\n'

    result = tl.scan(diff, [RENAME_NEW], read_head_file=reader)
    assert reads == [RENAME_NEW]
    assert [(v.path, v.line, v.hex) for v in result.violations] == [
        (RENAME_NEW, 1, "#d4845a")
    ]
    assert result.violations[0].note is not None
    assert "rename into scope" in result.violations[0].note


def test_guilt_cross_scope_rename_unverified_stdin_mode() -> None:
    """GUILT (round-5, stdin path): no filesystem in --stdin mode -> the
    rename into scope is reported as an unverified violation (fail-hostile,
    exit 1 at the CLI)."""
    result = tl.scan(make_rename_diff(RENAME_OLD, RENAME_NEW), [RENAME_NEW])
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.path == RENAME_NEW
    assert violation.line == 0
    assert violation.hex == tl.UNVERIFIED_RENAME_HEX
    assert violation.note is not None and "not verifiable" in violation.note


def test_cli_cross_scope_rename_stdin_exit_1() -> None:
    proc = _run_cli(["--stdin", "--files", RENAME_NEW], make_rename_diff(RENAME_OLD, RENAME_NEW))
    assert proc.returncode == 1
    assert "(rename-unverified)" in proc.stdout
    assert RENAME_NEW in proc.stdout


def test_innocence_cross_scope_rename_no_hex() -> None:
    """INNOCENCE (round-5): same cross-scope rename, but the destination
    content carries zero hexes -> clean."""
    result = tl.scan(
        make_rename_diff(RENAME_OLD, RENAME_NEW),
        [RENAME_NEW],
        read_head_file=lambda path: "const ok = 1;\n// no colors here\n",
    )
    assert result.violations == []


def test_innocence_out_of_scope_rename_with_hex() -> None:
    """INNOCENCE (round-5): a rename between two OUT-OF-SCOPE paths keeps
    the gate out of it entirely — the content reader must not even be
    called (unchanged behavior)."""

    def reader(path: str) -> str:
        raise AssertionError(f"reader called for out-of-scope rename: {path}")

    old = "apps/mouth/src/app/(marketing)/a.tsx"
    new = "apps/mouth/src/app/(marketing)/b.tsx"
    result = tl.scan(make_rename_diff(old, new), [new], read_head_file=reader)
    assert result.violations == []


def test_innocence_in_scope_pure_rename_keeps_legacy() -> None:
    """INNOCENCE (round-5, documented design): an IN-SCOPE -> IN-SCOPE pure
    rename stays invisible — its content was already inside the gate's
    regime (legacy stays legacy, the ~600-hex cleanup is not this gate's
    job). Round-5 judges only CROSS-SCOPE ingress, so the reader is never
    consulted here either."""
    old = "apps/mouth/src/app/portal/old.tsx"
    new = "apps/mouth/src/app/portal/new.tsx"

    def reader(path: str) -> str:
        raise AssertionError(f"reader called for in-scope rename: {path}")

    result = tl.scan(make_rename_diff(old, new), [new], read_head_file=reader)
    assert result.violations == []


# ---------------------------------------------------------------------------
# PARSER UNIT CHECKS — line numbers and tricky shapes.
# ---------------------------------------------------------------------------


def test_parser_tracks_line_numbers_across_hunks() -> None:
    path = WORKSPACE_PAGE
    diff = (
        f"diff --git a/{path} b/{path}\n"
        f"index 1111111..2222222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -10,0 +11,1 @@\n"
        "+first\n"
        "@@ -40,0 +42,1 @@\n"
        "+second\n"
    )
    added = tl.parse_unified_diff(diff)
    assert [(a.line, a.content) for a in added] == [(11, "first"), (42, "second")]


def test_parser_added_line_starting_with_plus_plus_is_content() -> None:
    """Hunk-count tracking (not naive startswith) is what keeps an added
    line that literally begins with `++` from being read as a `+++` file
    header."""
    path = WORKSPACE_PAGE
    diff = make_diff(path, ["++combined = '#d4845a';"])
    added = tl.parse_unified_diff(diff)
    assert [(a.line, a.content) for a in added] == [(1, "++combined = '#d4845a';")]


def test_parser_empty_diff_is_clean() -> None:
    assert tl.parse_unified_diff("") == []
    result = tl.scan("", [WORKSPACE_PAGE])
    assert result.violations == []
    assert result.scanned_file_count == 0


def test_guilt_unicode_line_separator_not_a_line_break() -> None:
    """GUILT (PR #2987 round-7, codex RED P0): U+2028/U+2029 are NOT line
    breaks to git — a single git record carrying U+2028 before a hex must
    be judged as ONE added line. With str.splitlines() the record split in
    two: the hunk consumed the safe prefix and the hex suffix landed
    OUTSIDE the hunk -> false clean. _git_lines splits on "\\n" only.
    INNOCENCE counterpart: the entire rest of this suite — every make_diff
    fixture is a normal multi-line diff and behaves exactly as before."""
    payload = 'const safe = 1;\u2028const C = "#d4845a";'
    diff = make_diff(WORKSPACE_PAGE, [payload], start=7)
    added = tl.parse_unified_diff(diff)
    assert len(added) == 1, "U+2028 must not split one git record into two"
    result = tl.scan(diff, [WORKSPACE_PAGE])
    assert [(v.line, v.hex) for v in result.violations] == [(7, "#d4845a")]
    # And U+2029 gets the same treatment.
    payload_29 = 'const safe = 1;\u2029const C = "#c9a96e";'
    result = tl.scan(make_diff(WORKSPACE_PAGE, [payload_29]), [WORKSPACE_PAGE])
    assert [v.hex for v in result.violations] == ["#c9a96e"]


# ---------------------------------------------------------------------------
# CLI CONTRACT — drive the real entrypoint via subprocess (never needs git).
# ---------------------------------------------------------------------------


def _run_cli(args: list[str], stdin_text: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_stdin_guilt_exit_1_with_file_line() -> None:
    diff = make_diff(WORKSPACE_PAGE, ['const BRAND = "#d4845a";'], start=71)
    proc = _run_cli(["--stdin", "--files", WORKSPACE_PAGE], diff)
    assert proc.returncode == 1
    expected = (
        f"{WORKSPACE_PAGE}:71: #d4845a — hardcoded color in redesigned "
        "surface; use a semantic token from packages/core (see PLAN §WS1)"
    )
    assert expected in proc.stdout
    assert "1 violation(s)" in proc.stdout


def test_cli_stdin_clean_exit_0() -> None:
    diff = make_diff(MARKETING_PAGE, ['const C = "#d4845a";'])
    proc = _run_cli(["--stdin", "--files", MARKETING_PAGE], diff)
    assert proc.returncode == 0
    assert "clean" in proc.stdout


def test_cli_stdin_malformed_exit_2() -> None:
    bad = "+++ b/x\n@@ not-a-hunk @@\n+color: #d4845a;\n"
    proc = _run_cli(["--stdin", "--files", "x"], bad)
    assert proc.returncode == 2
    assert "fail-closed" in proc.stderr


def test_cli_stdin_truncated_hunk_exit_2() -> None:
    """CLI contract for finding 3: a truncated diff (declared 5, got 2)
    exits 2 with the fail-closed message, never a clean/partial result."""
    truncated = "+++ b/x\n@@ -0,0 +1,5 @@\n+a\n+b\n"
    proc = _run_cli(["--stdin", "--files", "x"], truncated)
    assert proc.returncode == 2
    assert "fail-closed" in proc.stderr


def test_cli_state_leak_second_file_exit_2() -> None:
    """CLI contract for round-3 finding 3: crafted two-file stdin where the
    second file has hunks but no `+++` header exits 2 (fail-closed) — it
    must never inherit the first file's path and exit clean."""
    leaked = (
        f"diff --git a/{WORKSPACE_PAGE} b/{WORKSPACE_PAGE}\n"
        f"--- a/{WORKSPACE_PAGE}\n"
        f"+++ b/{WORKSPACE_PAGE}\n"
        "@@ -0,0 +1,1 @@\n"
        "+ok\n"
        "diff --git a/apps/mouth/src/app/(marketing)/m.tsx b/apps/mouth/src/app/(marketing)/m.tsx\n"
        "@@ -0,0 +1,1 @@\n"
        "+color: #d4845a;\n"
    )
    proc = _run_cli(
        ["--stdin", "--files", f"{WORKSPACE_PAGE},apps/mouth/src/app/(marketing)/m.tsx"],
        leaked,
    )
    assert proc.returncode == 2
    assert "fail-closed" in proc.stderr


def test_cli_stdin_requires_files_exit_2() -> None:
    proc = _run_cli(["--stdin"], "anything\n")
    assert proc.returncode == 2  # argparse usage error — fail-closed by construction


def test_cli_json_mode_is_machine_readable() -> None:
    diff = make_diff(WORKSPACE_PAGE, ["color: #d4845a;"], start=5)
    proc = _run_cli(["--stdin", "--files", WORKSPACE_PAGE, "--json"], diff)
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["violationCount"] == 1
    assert payload["violations"][0]["path"] == WORKSPACE_PAGE
    assert payload["violations"][0]["line"] == 5
    assert payload["violations"][0]["hex"] == "#d4845a"
    assert payload["scopedPrefixes"] == list(tl.SCOPED_PREFIXES)


def test_cli_json_clean_mode() -> None:
    proc = _run_cli(["--stdin", "--files", MARKETING_PAGE, "--json"], "")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["violationCount"] == 0


# ---------------------------------------------------------------------------
# ROUND-7 — end-to-end --base mode against a REAL git repo (codex RED P1).
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_e2e_base_mode_real_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole --base path with zero mocks: real `git init`, real commits,
    real `git diff` output parsed by the real scanner. The module's only
    location seam is `_repo_root()` (by design the scanner is immune to the
    caller's cwd), so the test points that seam at the tmp repo — the exact
    isolation the mandate's "cwd=tmp repo" asks for.

    GUILT: a commit adding `#d4845a` to a scoped file -> exit 1, and the
    violation line names the file at the right line number.
    INNOCENCE: a follow-up hex-free commit over the same base -> exit 0.
    """

    def git(*args: str) -> None:
        proc = subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=False
        )
        assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"

    git("init", "-b", "master")
    git("config", "user.email", "token-lint-e2e@test.invalid")
    git("config", "user.name", "token-lint e2e")
    page = tmp_path / "apps" / "mouth" / "src" / "app" / "(workspace)" / "x" / "page.tsx"
    page.parent.mkdir(parents=True)
    page.write_text("export const ok = 1;\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "clean scoped file")
    monkeypatch.setattr(tl, "_repo_root", lambda: tmp_path)

    # GUILT — second commit adds the hex line (line 2 of the file).
    page.write_text(
        'export const ok = 1;\nconst BRAND = "#d4845a";\n', encoding="utf-8"
    )
    git("commit", "-am", "add hardcoded brand hex")
    assert tl.main(["--base", "master~1"]) == 1
    out = capsys.readouterr().out
    assert "apps/mouth/src/app/(workspace)/x/page.tsx:2: #d4845a" in out

    # INNOCENCE — third commit adds only a hex-free line; diff vs its parent
    # carries no violation.
    page.write_text(
        'export const ok = 1;\nconst BRAND = "#d4845a";\nexport const ok2 = 2;\n',
        encoding="utf-8",
    )
    git("commit", "-am", "benign follow-up")
    assert tl.main(["--base", "master~1"]) == 0
    assert "clean" in capsys.readouterr().out
