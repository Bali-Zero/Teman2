"""Tripwire: a branded cover card must never name a different article's product.

THE DEFECT THIS PINS
--------------------
Thirteen published immigration articles shared one byte-identical cover image.
That image was not a stock photo — it was a Bali Zero card with a title printed
on it reading "Investor KITAS (E28A)". The retirement-visa article, the
student-visa article and eleven others each opened with a card announcing a
product they do not describe. (The E28A article did not even use it.)

The distinction that matters, and the one these tests encode: a generic photo
shared across articles is weak but honest; a TITLED card shared across articles
is a false claim in the most prominent position on the page. So the rule is not
"covers must be unique" — several stock photos are still legitimately shared
elsewhere in this tree — it is "the generated cards must be one-per-article".
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GENERATOR = REPO / "scripts" / "generate_insight_cover_cards.py"
COVERS = REPO / "apps/mouth/public/static/insights/immigration"

sys.path.insert(0, str(REPO / "scripts"))
from generate_insight_cover_cards import (  # noqa: E402
    CARDS,
    GENERATION_FONT,
    resolved_font_path,
)

# Re-rendering only reproduces the committed bytes under the font they were made
# with (measured: Helvetica 087a2b8c…, Arial b01a857c… for the same card). A
# Linux CI runner has neither, so the two tests that re-render skip THERE and
# say so, while the three that pin the actual defect — distinctness, the E28A
# card being gone, no article claiming a sibling's card — are pure file reads
# and run everywhere. Skipping the platform-bound pair is what lets this file
# be a CI gate at all instead of a local-only script.
needs_generation_font = pytest.mark.skipif(
    resolved_font_path() != GENERATION_FONT,
    reason=(
        f"cards were rendered with {GENERATION_FONT}; this machine resolves "
        f"{resolved_font_path()}, which renders different bytes by design"
    ),
)

# The wrong card, by content. Recorded so the exact bytes can never come back,
# no matter what filename they arrive under.
E28A_CARD_MD5 = "f6879f0dbe9c91059ffa6bd8bad5a0f6"


def _slugs() -> list[str]:
    """Slugs the generator owns, read from the generator itself.

    Deliberately not a second hand-maintained list: a copy here would drift
    from CARDS and the tests would then guard a set nobody ships.
    """
    return [c.slug for c in CARDS]


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()  # noqa: S324 — identity, not security


@pytest.fixture(scope="module")
def slugs() -> list[str]:
    return _slugs()


def test_every_generated_cover_exists(slugs: list[str]) -> None:
    missing = [s for s in slugs if not (COVERS / f"{s}.jpg").is_file()]
    assert not missing, f"generated covers missing from disk: {missing}"


def test_generated_covers_are_all_distinct(slugs: list[str]) -> None:
    """The actual defect: N articles, 1 card."""
    by_hash: dict[str, list[str]] = {}
    for s in slugs:
        by_hash.setdefault(_md5(COVERS / f"{s}.jpg"), []).append(s)
    shared = {h: v for h, v in by_hash.items() if len(v) > 1}
    assert not shared, f"articles sharing one titled card: {list(shared.values())}"


def test_sharing_a_generic_photo_is_still_allowed(slugs: list[str]) -> None:
    """INNOCENCE. The rule must not become "every cover is unique".

    Measured on this tree: 408 images, 243 distinct, 19 groups shared between
    articles — one generic photo serves 47 of them. That is editorially thin,
    and it is not what this suite polices: a photo that names nothing cannot
    name the wrong thing. Only a TITLED card can, which is why the distinctness
    rule above is scoped to the generated set.

    So this asserts the scope is deliberate: sharing outside the generated set
    still exists and is still green. If someone later widens the rule to the
    whole folder, this test fails and says why — before it starts failing every
    unrelated content PR.
    """
    tree = REPO / "apps/mouth/public/static/insights"
    own = {f"{s}.jpg" for s in slugs}
    by_hash: dict[str, list[str]] = {}
    for p in tree.rglob("*.jpg"):
        if p.name not in own:
            by_hash.setdefault(_md5(p), []).append(p.name)
    shared = [v for v in by_hash.values() if len(v) > 1]
    assert shared, (
        "expected legitimately-shared generic photos outside the generated set; "
        "found none — the premise of this test has changed, re-read the scope"
    )


def test_the_wrong_e28a_card_is_gone_from_the_whole_tree() -> None:
    """Content-addressed, so renaming the file does not evade this."""
    offenders = [
        p.relative_to(REPO).as_posix()
        for p in (REPO / "apps/mouth/public/static/insights").rglob("*.jpg")
        if _md5(p) == E28A_CARD_MD5
    ]
    assert not offenders, (
        "the 'Investor KITAS (E28A)' card is back on: " + ", ".join(offenders)
    )


def test_no_article_declares_another_articles_cover(slugs: list[str]) -> None:
    """A titled card is only correct relative to the article that loads it.

    Not every article declares `coverImage` — several resolve their cover
    elsewhere (three of these thirteen are served an on-topic photo under a
    different filename, two serve no insights cover at all). So this asserts
    the invariant that is actually checkable offline and actually load-bearing:
    when an article DOES name a cover under the immigration folder, it must be
    its own. Pointing at a sibling's card is how a titled card ends up
    announcing the wrong product in the first place.
    """
    articles = REPO / "apps/mouth/src/content/articles/immigration"
    own = set(slugs)
    wrong: list[str] = []
    for s in slugs:
        mdx = articles / f"{s}.mdx"
        assert mdx.is_file(), f"{s}: article missing"
        for line in mdx.read_text().splitlines():
            if not line.startswith("coverImage:"):
                continue
            ref = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
            stem = Path(ref).stem
            if stem in own and stem != s:
                wrong.append(f"{s} declares {ref} — that is {stem}'s card")
    assert not wrong, wrong


@needs_generation_font
def test_generator_is_deterministic(slugs: list[str]) -> None:
    """Re-running must be a git no-op, otherwise every run produces 13 spurious
    diffs and the real ones get lost in them."""
    before = {s: _md5(COVERS / f"{s}.jpg") for s in slugs}
    subprocess.run(  # noqa: S603
        [sys.executable, str(GENERATOR)], cwd=REPO, check=True, capture_output=True
    )
    after = {s: _md5(COVERS / f"{s}.jpg") for s in slugs}
    changed = [s for s in slugs if before[s] != after[s]]
    assert not changed, f"non-deterministic render for: {changed}"


def test_check_mode_writes_nothing(slugs: list[str]) -> None:
    before = {s: _md5(COVERS / f"{s}.jpg") for s in slugs}
    subprocess.run(  # noqa: S603
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    after = {s: _md5(COVERS / f"{s}.jpg") for s in slugs}
    assert before == after, "--check mutated files"
