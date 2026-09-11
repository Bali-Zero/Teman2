"""The imigrasi mirror's URL catalog must cover what the signed RulePack cites,
and must not let two pages share a snapshot filename.

Why this file exists at all: until 2026-08-31 the mirror had NO test surface.
Its only guards were two import-time asserts inside `urls.py` — one on `CODES`,
one on page `id` — and an assert that nothing exercises deliberately is a guard
whose innocence half was never checked. Both properties below are load-bearing
and both were, until this file, unwatched:

  * COVERAGE. The RulePack carries a freshness policy per OFFICIAL_PORTAL
    source. A policy on a page the mirror never fetches is a promise nobody
    can keep: the clock expires, the engine abstains, and no snapshot exists
    to say whether anything actually changed. Two of the pack's 18 portal urls
    were in exactly that state.
  * SLUG UNIQUENESS. The slug is the snapshot filename stem. `id` and `slug`
    are allowed to differ, so a hand-authored daily page can silently reuse
    another page's slug — after which the two overwrite each other every run,
    with no error, no missing file, and a permanent "no diffs" for whichever
    one lost.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from imigrasi_mirror import urls as catalog  # noqa: E402

_PACKS = (
    _REPO
    / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
)


def _latest_pack_source() -> dict:
    """The highest-numbered `rulepack-prod-NNN.source.json` on disk.

    Read by number rather than pinned to one sequence: pinning would make this
    test go quietly irrelevant the moment a forward pack ships, which is the
    same "watching the wrong thing" failure it exists to prevent.
    """
    candidates = sorted(
        _PACKS.glob("rulepack-prod-*.source.json"),
        key=lambda q: int(q.name.split("-")[2].split(".")[0]),
    )
    if not candidates:
        pytest.skip(f"no rulepack source files on disk under {_PACKS}")
    return json.loads(candidates[-1].read_text())


#: The field is `authority_type`, NOT `source_class`. Written down because the
#: first draft of this file guessed `source_class`, which matches nothing in a
#: real pack — so `_portal_urls` returned the empty set, the coverage test
#: compared nothing against everything, and it passed. A green that means "I
#: found no records to check" is indistinguishable from "every record is
#: covered" unless something asserts the set is non-empty, which
#: `test_the_pack_actually_has_portal_records_to_check` now does.
_PORTAL = "OFFICIAL_PORTAL"


def _portal_urls(pack: dict) -> set[str]:
    return {
        record["canonical_url"]
        for record in pack.get("source_records", [])
        if record.get("authority_type") == _PORTAL
    }


def _normalise(url: str) -> str:
    """Compare on scheme-less host+path, no trailing slash.

    The catalog and the pack are hand-maintained separately, so a mismatch on
    `http` vs `https` or a trailing slash would read as "not covered" and send
    someone chasing a gap that is not there.
    """
    parts = urlsplit(url)
    return f"{parts.netloc}{parts.path}".rstrip("/").lower()


def test_the_pack_actually_has_portal_records_to_check():
    """NON-VACUITY, and it is not ceremony: without it, renaming the field or
    the value in a future pack would silently turn every coverage assertion in
    this file into a comparison of two empty sets, reported as a pass."""
    portal = _portal_urls(_latest_pack_source())
    assert portal, (
        "no OFFICIAL_PORTAL records found — either the pack changed shape or "
        f"the {_PORTAL!r} value moved off `authority_type`. Every coverage "
        "check below is vacuous until this is fixed."
    )
    assert len(portal) >= 18, f"portal record count dropped to {len(portal)}"


def test_every_official_portal_url_in_the_pack_is_mirrored():
    """COVERAGE, the real thing — not a fixture."""
    pack = _latest_pack_source()
    mirrored = {_normalise(p.url) for p in catalog.ALL_PAGES}
    missing = sorted(u for u in _portal_urls(pack) if _normalise(u) not in mirrored)
    assert not missing, (
        "the signed RulePack carries a freshness policy for these OFFICIAL_PORTAL "
        "urls, but the mirror never fetches them, so nothing can tell a real "
        "'unchanged' from 'never looked': " + repr(missing)
    )


def test_the_two_urls_this_file_was_written_for_are_daily_not_weekly():
    """A page mirrored on the weekly tier is invisible for up to six days.
    For a bridging-visa announcement and a status-conversion page that is not
    coverage, it is a delay dressed as coverage."""
    by_id = {p.id: p for p in catalog.ALL_PAGES}
    for page_id in ("bridging-visa-press-2024", "itk-to-itas"):
        assert page_id in by_id, f"{page_id} vanished from the catalog"
        assert by_id[page_id].tier == "daily", (
            f"{page_id} is on the {by_id[page_id].tier} tier"
        )


def test_the_coverage_check_can_actually_fail():
    """GUILT. A coverage test that cannot go red proves nothing — and this one
    reads real files, so its silence would be indistinguishable from success if
    the normalisation or the source_class filter were wrong."""
    pack = {
        "source_records": [
            {
                "authority_type": "OFFICIAL_PORTAL",
                "canonical_url": "https://www.imigrasi.go.id/wna/a-page-nobody-mirrors",
            }
        ]
    }
    mirrored = {_normalise(p.url) for p in catalog.ALL_PAGES}
    assert [u for u in _portal_urls(pack) if _normalise(u) not in mirrored]


def test_a_non_portal_source_is_not_demanded_of_the_mirror():
    """INNOCENCE. Only OFFICIAL_PORTAL records are the mirror's business. A
    pack's IMPLEMENTING_REGULATION and PRIMARY_LAW records (7 and 3 of them in
    seq-18) cite gazettes and statutes, not crawlable portal pages, and must
    not make this test demand the crawler fetch them."""
    pack = {
        "source_records": [
            {
                "authority_type": "IMPLEMENTING_REGULATION",
                "canonical_url": "https://example.invalid/not-a-portal",
            }
        ]
    }
    assert _portal_urls(pack) == set()


def test_no_two_pages_share_a_snapshot_filename():
    """The property the catalog's own asserts did not cover."""
    slugs = [p.slug for p in catalog.ALL_PAGES]
    duplicates = sorted({s for s in slugs if slugs.count(s) > 1})
    assert not duplicates, (
        "these slugs are used by more than one page and would overwrite each "
        "other's snapshot on every run: " + repr(duplicates)
    )


def test_the_slug_guard_catches_a_collision():
    """GUILT for the slug guard. Builds the collision the guard exists to stop
    and asserts the detection logic sees it — the import-time assert in
    urls.py cannot be exercised from here without reimporting the module, so
    the property is checked directly on a constructed catalog."""
    victim = catalog.DAILY_PAGES[0]
    clash = replace(catalog.DAILY_PAGES[1], slug=victim.slug)
    slugs = [p.slug for p in (victim, clash)]
    assert sorted({s for s in slugs if slugs.count(s) > 1}) == [victim.slug]


def test_ids_and_slugs_are_allowed_to_differ():
    """INNOCENCE. Tightening the slug guard must not accidentally impose
    slug == id: the catalog deliberately ships pages where they differ, and
    an over-strict guard here would be a false alarm on shipped, correct rows."""
    assert any(p.id != p.slug for p in catalog.ALL_PAGES)
