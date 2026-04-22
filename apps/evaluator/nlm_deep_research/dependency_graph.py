"""NB Dependency Graph — static curated map of cross-NB claim relationships.

Sacred root (comment only): in the Buddhist principle of pratītyasamutpāda,
nothing arises alone — every phenomenon has conditions. The NB ecosystem
expresses this as "no claim is an island". BPHTB (tax) depends on HGB
(property); KITAS E23 (immigration) depends on PT PMA sponsor (company);
OSS-RBA changes (operations) ripple into licensing (company). Today the
CrossNotebookCorrelator sees these co-dependences only post-hoc per query.
This module makes them explicit: a curated JSON of ~20 well-known dependency
patterns that the claim_extractor consults at the moment a new claim is
recorded, so the ledger entry carries links to relevant claims in other NBs.

Design rules:

    1. Curation is manual. Never generate via LLM — risk of allucinated
       relations that fabricate legal dependencies.
    2. Failure is silent. If nb_dependency.json is missing, malformed, or
       patched — the extractor still works, just without related_claims.
    3. The map is sparse by design. ~20 entries is enough to cover the
       most common Bali Zero cases. Not every NB.category needs an entry.
    4. Read-only. No side effect on the file system or on claims.

Usage:

    from apps.evaluator.nlm_deep_research.dependency_graph import (
        load_dependencies,
        find_dependencies_for_claim,
    )

    deps = load_dependencies()
    matches = find_dependencies_for_claim(
        claim_text="BPHTB rate changes 2026", category="FEE_CHANGE", nb="nb4", deps=deps
    )
    # matches = [
    #   {"key": "nb4.FEE_CHANGE.BPHTB",
    #    "requires_context_from": [...],
    #    "enriches": [...],
    #    "matched_keywords": ["bphtb"]}
    # ]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

_DIR = Path(__file__).parent
DEPENDENCIES_FILE = _DIR / "nb_dependency.json"

# Cache (module-level, loaded lazily; re-loaded when file mtime changes)
_cache: dict[str, Any] = {}


# ── Load ─────────────────────────────────────────────────────────────────────


def load_dependencies(
    path: Optional[Path] = None,
    force_reload: bool = False,
) -> dict[str, Any]:
    """Load the dependency map. Returns {} on any failure (silent).

    Args:
        path: override file path (tests).
        force_reload: ignore mtime cache, re-read.
    """
    target = path or DEPENDENCIES_FILE
    if not target.exists():
        logger.debug("dependency: file missing (%s) — no dependencies returned", target)
        return {}

    try:
        mtime = target.stat().st_mtime
    except OSError:
        return {}

    cache_key = str(target)
    cached = _cache.get(cache_key)
    if (
        not force_reload
        and cached is not None
        and cached.get("mtime") == mtime
    ):
        return cached.get("deps", {})

    try:
        with open(target, encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("dependency: failed to read %s — %s", target, exc)
        return {}

    deps = raw.get("dependencies") or {}
    if not isinstance(deps, dict):
        logger.warning("dependency: malformed file (missing 'dependencies' dict)")
        return {}

    _cache[cache_key] = {"mtime": mtime, "deps": deps}
    return deps


# ── Matching ─────────────────────────────────────────────────────────────────


def _matches_key(nb: str, category: str, dep_key: str) -> bool:
    """A dep key like 'nb4.FEE_CHANGE.BPHTB' matches nb=nb4 + category=FEE_CHANGE."""
    parts = dep_key.split(".", 2)
    if len(parts) < 2:
        return False
    return parts[0] == nb and parts[1] == category


def find_dependencies_for_claim(
    claim_text: str,
    category: str,
    nb: str,
    deps: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Return list of dependency matches for the given claim.

    A match means:
      - The key prefix 'nb.CATEGORY' matches the claim's nb+category.
      - At least one keyword appears in claim_text (case-insensitive).

    Returns list sorted by number of matched keywords (best match first).
    Empty list when no match or deps missing.
    """
    if deps is None:
        deps = load_dependencies()
    if not deps:
        return []
    if not claim_text or not category or not nb:
        return []

    claim_lower = claim_text.lower()
    matches: list[dict[str, Any]] = []

    for key, entry in deps.items():
        if not _matches_key(nb, category, key):
            continue
        keywords = entry.get("keywords") or []
        matched = [kw for kw in keywords if kw.lower() in claim_lower]
        if not matched:
            continue
        matches.append(
            {
                "key": key,
                "requires_context_from": entry.get("requires_context_from", []),
                "enriches": entry.get("enriches", []),
                "matched_keywords": matched,
                "gloss": entry.get("gloss", ""),
                "match_score": len(matched),
            }
        )

    # Sort by number of matched keywords desc (best match first)
    matches.sort(key=lambda m: m["match_score"], reverse=True)
    return matches


def summarize_dependency_graph(
    deps: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Return a pure-stat summary of the map (no claim matching)."""
    if deps is None:
        deps = load_dependencies()
    if not deps:
        return {"entry_count": 0, "source_nbs": [], "target_nbs": []}

    source_nbs: set[str] = set()
    target_nbs: set[str] = set()
    total_requires = 0
    total_enriches = 0

    for key, entry in deps.items():
        parts = key.split(".")
        if parts:
            source_nbs.add(parts[0])
        for ref in entry.get("requires_context_from") or []:
            t_parts = ref.split(".")
            if t_parts:
                target_nbs.add(t_parts[0])
            total_requires += 1
        for ref in entry.get("enriches") or []:
            t_parts = ref.split(".")
            if t_parts:
                target_nbs.add(t_parts[0])
            total_enriches += 1

    return {
        "entry_count": len(deps),
        "source_nbs": sorted(source_nbs),
        "target_nbs": sorted(target_nbs),
        "total_requires_context_edges": total_requires,
        "total_enriches_edges": total_enriches,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="NB Dependency Graph reader + CLI test harness")
    parser.add_argument("--summary", action="store_true", help="print summary stats")
    parser.add_argument("--match", action="store_true", help="test match against --nb/--category/--text")
    parser.add_argument("--nb", help="NB key (for --match)")
    parser.add_argument("--category", help="category (for --match)")
    parser.add_argument("--text", help="claim text (for --match)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.summary:
        summary = summarize_dependency_graph()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    if args.match:
        if not (args.nb and args.category and args.text):
            print("--match requires --nb and --category and --text", file=sys.stderr)
            return 2
        matches = find_dependencies_for_claim(
            claim_text=args.text, category=args.category, nb=args.nb
        )
        print(json.dumps(matches, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
