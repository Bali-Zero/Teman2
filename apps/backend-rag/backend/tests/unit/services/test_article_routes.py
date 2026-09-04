"""Cross-language drift tripwire for the folder → served-category table.

`apps/mouth/src/lib/blog/categories.ts::CATEGORY_MAP` is the SSOT for which
public category (`/business/`, `/visas/`, `/taxes/`, ...) each content
folder is served at. `backend/services/article_routes.py::served_category`
is a hand-kept Python COPY of that table — the FastAPI backend and the
Next.js frontend cannot share a constant across languages. A folder present
on only one side means the backend builds an `article_url`/`published_url`
that the site does not route (measured live 2026-09-05: the folder-named
URL 404s with "Article not found" while the served-category URL renders).

This test is the mechanism, not the comment promising sync. It reads the TS
source as plain text (no bundler, no AST parser — a tripwire), extracts the
`CATEGORY_MAP` object literal, and compares it against the Python table as
dicts, not as text, so formatting/ordering/quoting style can never flip it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services.article_routes import _FOLDER_TO_SERVED_CATEGORY, served_category

# Five levels up from this file (services -> unit -> tests -> backend ->
# backend-rag) reaches apps/ itself, same convention as
# test_service_accounts_ts_sync.py's _TS_HOOK_PATH (six levels up from one
# directory deeper, also landing on apps/).
_TS_CATEGORIES_PATH = (
    Path(__file__).resolve().parents[5] / "mouth" / "src" / "lib" / "blog" / "categories.ts"
)

_CATEGORY_MAP_BLOCK_RE = re.compile(
    r"export\s+const\s+CATEGORY_MAP\s*:\s*Record<string,\s*ArticleCategory>\s*=\s*\{"
    r"(?P<body>.*?)\n\};",
    re.DOTALL,
)

_ENTRY_RE = re.compile(
    r"""^\s*(?:"(?P<qkey>[^"]+)"|(?P<bkey>[A-Za-z_][A-Za-z0-9_]*))\s*:\s*"(?P<value>[^"]+)"\s*,?\s*$"""
)


def _extract_ts_category_map(source: str) -> dict[str, str]:
    """Parse the `CATEGORY_MAP` object literal out of TS source as text.

    Raises if the declaration cannot be found at all, so a rename or a
    reformat past what this regex tolerates breaks this test LOUDLY instead
    of silently comparing against an empty extracted map and passing for the
    wrong reason.
    """
    match = _CATEGORY_MAP_BLOCK_RE.search(source)
    if match is None:
        raise AssertionError(
            "Could not find `export const CATEGORY_MAP: Record<string, "
            f"ArticleCategory> = {{...}}` in {_TS_CATEGORIES_PATH} — the "
            "declaration was renamed, reformatted past what this regex "
            "tolerates, or removed. Update this test's extraction pattern "
            "to match the new shape; do not delete this test or weaken it "
            "to skip on a miss."
        )
    entries: dict[str, str] = {}
    for line in match.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        entry_match = _ENTRY_RE.match(line)
        if entry_match is None:
            continue
        key = entry_match.group("qkey") or entry_match.group("bkey")
        entries[key] = entry_match.group("value")
    return entries


class TestServedCategoryStaysInSyncWithCategoriesTs:
    """Guilt + innocence for the cross-language sync itself."""

    def test_python_table_matches_the_ts_category_map_exactly(self) -> None:
        """Guilt: a folder present on only one side, or mapped to a
        different served category on each side, must fail this test.
        """
        assert _TS_CATEGORIES_PATH.is_file(), f"expected TS file at {_TS_CATEGORIES_PATH}"

        ts_map = _extract_ts_category_map(_TS_CATEGORIES_PATH.read_text())

        # Non-vacuity: an empty extracted map would trivially equal an
        # empty Python dict and pass for the wrong reason.
        assert ts_map, (
            "Extracted an EMPTY CATEGORY_MAP from "
            f"{_TS_CATEGORIES_PATH} — that is almost certainly a bug in "
            "this test's extraction regex, not a real empty table."
        )

        assert ts_map == _FOLDER_TO_SERVED_CATEGORY, (
            f"backend/services/article_routes.py's served-category table has "
            f"drifted from CATEGORY_MAP in {_TS_CATEGORIES_PATH}. A folder "
            "present on only one side (or mapped to a different served "
            "category on each side) means the backend hands out a public "
            "URL the site does not route the same way the frontend does."
        )

    def test_extraction_raises_when_the_declaration_is_absent(self) -> None:
        """Innocence of the tripwire itself: prove the fail-loud path fires."""
        with pytest.raises(AssertionError, match="Could not find"):
            _extract_ts_category_map("// CATEGORY_MAP was removed here\n")

    def test_extraction_ignores_an_unrelated_object_literal(self) -> None:
        """Innocence: a same-shaped object for something else must not match."""
        source = 'export const SOME_OTHER_MAP: Record<string, string> = {\n  foo: "bar",\n};\n'
        with pytest.raises(AssertionError, match="Could not find"):
            _extract_ts_category_map(source)


class TestServedCategory:
    """Direct unit coverage of `served_category` itself."""

    def test_business_regulations_folder_serves_business(self) -> None:
        assert served_category("business_regulations") == "business"

    def test_immigration_folder_serves_visas(self) -> None:
        assert served_category("immigration") == "visas"

    def test_unknown_folder_is_returned_unchanged(self) -> None:
        assert served_category("some-new-folder-nobody-mapped-yet") == (
            "some-new-folder-nobody-mapped-yet"
        )
