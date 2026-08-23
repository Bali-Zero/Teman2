"""Tests for scripts/ci/evidence_paths.py — per-PR evidence directory slugs.

The load-bearing property is INJECTIVITY: two distinct branch refs must
never map to the same evidence-directory slug, even when a naive
sanitize-only scheme (strip everything but [a-z0-9], collapse separators)
would collapse them. This repo's branches live under
``agent/<host>/<lane>/<task>`` and are full of hyphens, so that collision
is not a corner case — see the module docstring for the concrete example
(``agent/mini-pro2/infra/foo-bar`` vs ``agent/mini-pro2/infra-foo/bar``).
Family #3 in ``.claude/rules/cicatrix-superscar.md`` already carries a scar
about a path truncation collapsing distinct names; these tests exist to
make sure this module doesn't join that list.
"""

from __future__ import annotations

import re

from scripts.ci.evidence_paths import evidence_glob, slug_for_ref

# Shape every slug must satisfy: one or more lowercase alnum "words"
# joined by single dashes, ending in the mandatory 8-hex-char digest
# suffix. No slashes, no leading/trailing dash, no double dash.
_SLUG_SHAPE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*-[0-9a-f]{8}$")

# Total length is bounded by construction: at most 48 sanitized chars,
# one separator dash, and an 8-char hex digest.
_MAX_SLUG_LEN = 48 + 1 + 8


def _assert_valid_shape(slug: str) -> None:
    """Assert ``slug`` is a safe, well-formed single path segment.

    Centralized so every test below gets the same shape check for free
    instead of re-deriving it — this is the invariant every caller of
    ``slug_for_ref`` actually depends on (a value it can drop straight
    into a path with no further escaping).
    """
    assert "/" not in slug, f"slug must not contain a path separator: {slug!r}"
    assert not slug.startswith("-") and not slug.endswith("-"), (
        f"slug must not have leading/trailing dash: {slug!r}"
    )
    assert "--" not in slug, f"slug must not contain a collapsed-empty segment: {slug!r}"
    assert len(slug) <= _MAX_SLUG_LEN, f"slug exceeds bound {_MAX_SLUG_LEN}: {slug!r}"
    assert _SLUG_SHAPE.match(slug), f"slug does not match expected shape: {slug!r}"


class TestInjectivity:
    """The property this module exists for: distinct refs -> distinct slugs.

    Sanitizing alone (lowercase + collapse non-alnum runs to '-') is NOT
    injective, because '/' and '-' both collapse to the same separator.
    Rule 3 of the module docstring — hash the FULL ORIGINAL ref, never the
    sanitized/truncated form — is what restores injectivity, and that is
    exactly what these tests pin down.
    """

    def test_slash_vs_hyphen_collision_from_the_spec(self) -> None:
        """The exact motivating example: agent/.../infra/foo-bar vs
        agent/.../infra-foo/bar both sanitize to the identical string
        "agent-mini-pro2-infra-foo-bar", so only the hash suffix can
        keep them apart."""
        ref_a = "agent/mini-pro2/infra/foo-bar"
        ref_b = "agent/mini-pro2/infra-foo/bar"

        slug_a = slug_for_ref(ref_a)
        slug_b = slug_for_ref(ref_b)

        # Confirm the premise: naive sanitize really would collide here.
        naive_sanitize = lambda r: re.sub(r"[^a-z0-9]+", "-", r.lower()).strip("-")
        assert naive_sanitize(ref_a) == naive_sanitize(ref_b) == "agent-mini-pro2-infra-foo-bar"

        assert slug_a != slug_b
        _assert_valid_shape(slug_a)
        _assert_valid_shape(slug_b)

    def test_second_devised_collision_dot_and_slash_delimiters(self) -> None:
        """A second, independently constructed colliding pair: '.' and '/'
        are both single non-alnum characters, so "release/v1.2.3" and
        "release-v1/2.3" also sanitize to the same string
        ("release-v1-2-3") under naive sanitize, yet must still diverge."""
        ref_a = "release/v1.2.3"
        ref_b = "release-v1/2.3"

        naive_sanitize = lambda r: re.sub(r"[^a-z0-9]+", "-", r.lower()).strip("-")
        assert naive_sanitize(ref_a) == naive_sanitize(ref_b) == "release-v1-2-3"

        slug_a = slug_for_ref(ref_a)
        slug_b = slug_for_ref(ref_b)

        assert slug_a != slug_b
        _assert_valid_shape(slug_a)
        _assert_valid_shape(slug_b)

    def test_truncation_does_not_defeat_injectivity(self) -> None:
        """Two refs sharing a 60-char alnum prefix (well past the 48-char
        sanitize truncation limit) and differing only near the end must
        still produce different slugs. If the hash were computed over the
        truncated/sanitized string instead of the full original ref, this
        pair would collide because the visible/truncated prefix is
        byte-identical between them."""
        shared_prefix = "a" * 60
        assert len(shared_prefix) >= 60

        ref_a = shared_prefix + "-branch-one"
        ref_b = shared_prefix + "-branch-two"
        assert ref_a[:60] == ref_b[:60]

        slug_a = slug_for_ref(ref_a)
        slug_b = slug_for_ref(ref_b)

        assert slug_a != slug_b
        _assert_valid_shape(slug_a)
        _assert_valid_shape(slug_b)


class TestDeterminism:
    def test_same_ref_same_slug_across_calls(self) -> None:
        ref = "agent/mini-pro2/infra/s12-c6-evidence-per-pr"
        first = slug_for_ref(ref)
        for _ in range(5):
            assert slug_for_ref(ref) == first

    def test_interleaved_calls_do_not_leak_state_between_refs(self) -> None:
        """Determinism must hold even when calls for different refs are
        interleaved — pins against any accidental dependence on call order
        or shared mutable state (there is none today; this is what would
        catch it if one were introduced)."""
        ref_a = "release/v1.2.3"
        ref_b = "agent/pro/wr2/carousel-task-42"
        expected_a = slug_for_ref(ref_a)
        expected_b = slug_for_ref(ref_b)

        for _ in range(3):
            assert slug_for_ref(ref_a) == expected_a
            assert slug_for_ref(ref_b) == expected_b


class TestSlugShape:
    def test_shape_on_a_representative_sample(self) -> None:
        sample_refs = [
            "agent/mini-pro2/infra/s12-c6-evidence-per-pr",
            "agent/pro/wr2/carousel-task-42",
            "main",
            "feature/x",
            "a" * 200,  # pathological length input
        ]
        for ref in sample_refs:
            _assert_valid_shape(slug_for_ref(ref))


class TestEdgeInputs:
    """None of these may crash, and none may produce an empty or
    dash-only directory-name-shaped slug — an evidence directory named
    "" or "-" is worse than the collision this module fixes."""

    def test_entirely_non_alphanumeric_ref(self) -> None:
        slug = slug_for_ref("///")
        _assert_valid_shape(slug)
        assert slug.strip("-") != ""

    def test_empty_string_ref(self) -> None:
        slug = slug_for_ref("")
        _assert_valid_shape(slug)
        assert slug.strip("-") != ""

    def test_only_dashes_ref(self) -> None:
        slug = slug_for_ref("---")
        _assert_valid_shape(slug)
        assert slug.strip("-") != ""

    def test_ref_that_is_already_only_hex(self) -> None:
        # A ref that looks exactly like a sha suffix should still get its
        # own real hash appended, not be mistaken for one.
        slug = slug_for_ref("deadbeef")
        _assert_valid_shape(slug)
        assert slug.startswith("deadbeef-")

    def test_empty_and_dash_only_and_slash_only_are_mutually_distinct(self) -> None:
        # These three degenerate inputs must not accidentally collide with
        # each other either (they'd all fall back to the same "no
        # alphanumeric content" branch if the hash weren't keyed on the
        # original ref).
        slugs = {slug_for_ref(""), slug_for_ref("---"), slug_for_ref("///")}
        assert len(slugs) == 3


class TestEvidenceGlob:
    def test_glob_has_exactly_one_star_and_ends_with_slug(self) -> None:
        ref = "agent/mini-pro2/infra/s12-c6-evidence-per-pr"
        glob = evidence_glob(ref)

        assert glob.count("*") == 1
        assert glob.endswith(slug_for_ref(ref))
        assert glob == f"evidence/*/{slug_for_ref(ref)}"

    def test_glob_for_edge_input_still_well_formed(self) -> None:
        glob = evidence_glob("///")
        assert glob.count("*") == 1
        assert glob.startswith("evidence/*/")
