"""Content-folder → served-category mapping for public article URLs.

Bali Zero's site collapses 13 content folders (where MDX files live, and
where the CMS/Article Composer writes them) onto 7 categories the Next.js
frontend actually routes (`apps/mouth/src/lib/blog/categories.ts::CATEGORY_MAP`,
consumed there by `normalizeCategory`/`articleUrl`). Any backend code that
hands out a public `article_url`/`published_url` MUST run the folder through
this table first, or the link 404s with "Article not found" — measured live
2026-09-05: `https://balizero.com/business_regulations/<slug>` (folder name)
404s while `https://balizero.com/business/<slug>` (served category) renders.

This table is a hand-kept COPY of `CATEGORY_MAP` in `categories.ts` — there is
no cross-language import path between the FastAPI backend and the Next.js
frontend. `tests/unit/services/test_article_routes.py` parses the TypeScript
source and asserts every key here maps identically, so a drift in either file
fails CI instead of shipping another dead link.
"""

from __future__ import annotations

# Keep this literally in sync with `CATEGORY_MAP` in
# apps/mouth/src/lib/blog/categories.ts. See test_article_routes.py.
_FOLDER_TO_SERVED_CATEGORY: dict[str, str] = {
    # Canonical categories
    "visas": "visas",
    "business": "business",
    "taxes": "taxes",
    "property": "property",
    "living": "living",
    "trends": "trends",
    # Backward compat (old category names)
    "immigration": "visas",
    "lifestyle": "living",
    "tech": "trends",
    "bali_news": "living",
    # Folder mappings (14 folders → 7 categories)
    "tax": "taxes",
    "tax-legal": "taxes",
    "digital-nomad": "living",
    "bali-news": "living",
    "business_regulations": "business",
    "emerging_trends": "trends",
    "social_media": "trends",
    "news": "business",
    # Backend compatibility
    "general": "business",
    "legal": "taxes",
}


def served_category(folder: str) -> str:
    """Map a content-folder name to the category the site actually serves.

    An unknown folder is returned unchanged (never raises, never silently
    defaults to some other category) so a new content folder cannot break
    the publish flow — it will just 404 as itself until someone extends this
    table and its TypeScript twin.
    """
    return _FOLDER_TO_SERVED_CATEGORY.get(folder, folder)
