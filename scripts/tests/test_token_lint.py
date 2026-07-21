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
    passes — that file IS the SSOT the gate protects. Also proves the
    basename glob for a `tokens*.css` file sitting INSIDE a scoped route."""
    result = tl.scan(make_diff(TOKEN_FILE, ["--accent-funnel: #d4845a;"]), [TOKEN_FILE])
    assert result.violations == []
    assert tl.is_token_source(TOKEN_FILE)
    scoped_tokens = "apps/mouth/src/app/portal/tokens.css"
    result = tl.scan(make_diff(scoped_tokens, ["--x: #d4845a;"]), [scoped_tokens])
    assert result.violations == []
    scoped_glob = "apps/mouth/src/app/(workspace)/brand.tokens.css"
    result = tl.scan(make_diff(scoped_glob, ["--x: #d4845a;"]), [scoped_glob])
    assert result.violations == []


def test_innocence_1b_styles_directory() -> None:
    """`apps/mouth/src/styles/` is a token-source prefix too."""
    path = "apps/mouth/src/styles/kbli-theme.css"
    assert tl.is_token_source(path)
    result = tl.scan(make_diff(path, [":root { --c: #d4845a; }"]), [path])
    assert result.violations == []


def test_innocence_2_full_line_comment() -> None:
    """Innocence-2 (mandate): a hex in a full-line comment passes — every
    comment shape the module recognizes."""
    comment_lines = [
        "// brand orange: #d4845a",
        "/* legacy: #d4845a */",
        "* #d4845a (inside a block comment)",
        "   * indented block-comment interior #d4845a",
        "<!-- #d4845a -->",
    ]
    for line in comment_lines:
        result = tl.scan(make_diff(WORKSPACE_PAGE, [line]), [WORKSPACE_PAGE])
        assert result.violations == [], f"comment line was flagged: {line!r}"


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
    bad = f"+++ b/x\n@@ -0,0 +1,1 @@\n?a\n"
    with pytest.raises(tl.DiffParseError):
        tl.parse_unified_diff(bad)


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
