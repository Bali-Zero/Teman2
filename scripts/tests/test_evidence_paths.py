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

import pytest

from scripts.ci.evidence_paths import (
    AmbiguousEvidencePathError,
    evidence_glob,
    main,
    resolve_evidence_path,
    slug_for_ref,
)

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


# ---------------------------------------------------------------------------
# resolve_evidence_path — CI's DISCOVERY entry point (never slug_for_ref).
#
# On a merge_group event the ref GitHub hands CI is
# gh-readonly-queue/main/pr-NNNN-<sha>, not the PR's own branch — computing
# a slug from it would look for the WRONG directory. resolve_evidence_path
# instead answers "which evidence/<kind>.yml did THIS PR's own diff touch",
# from the changed-files list CI already has. Tests below are paired
# guilt+innocence per superscar #3 (guard-over-match discipline): every
# "this must match" case has a sibling "this must NOT match" case.
# ---------------------------------------------------------------------------


class TestResolveEvidencePathInnocence:
    """Cases that must resolve WITHOUT raising, including the load-bearing
    invariant: a PR that touches neither evidence path must get the ROOT
    path back (never an empty string, never a raised error) so that the
    existing tracked_file_present_in_diff.sh -> "inherited" -> hot-zone-FAIL
    chain still catches it downstream. This function must never special-
    case that chain away.
    """

    def test_no_evidence_file_at_all_returns_root_path(self) -> None:
        """THE invariant seat6/S11/H1-P04 all flagged: a diff with NO
        evidence file whatsoever must resolve to the concrete root path,
        not an empty string and not a raised error — the caller still has
        something to hand to tracked_file_present_in_diff.sh, which is
        what actually fails a hot-zone diff carrying neither path."""
        changed_files = ["apps/backend-rag/backend/app/main.py", "README.md"]

        resolved = resolve_evidence_path("pack", changed_files)

        assert resolved == "evidence/pack.yml"
        assert resolved != ""

    def test_empty_changed_files_list_returns_root_path(self) -> None:
        assert resolve_evidence_path("brief", []) == "evidence/brief.yml"

    def test_root_path_literal_in_diff_is_not_mistaken_for_a_nested_match(self) -> None:
        """Explicit check (asked for by design review): the literal root
        path itself, when it DOES appear in changed_files (an un-migrated
        PR touching evidence/pack.yml directly), must not be matched by
        the nested-path pattern — it still comes back via the zero-matches
        fallback branch, which happens to equal the same string, but the
        two code paths must not be confused. Proven here by asserting the
        pattern truly has zero matches, not just that the return value
        looks right."""
        changed_files = ["evidence/pack.yml"]

        resolved = resolve_evidence_path("pack", changed_files)

        assert resolved == "evidence/pack.yml"
        # The literal root path was not counted as a "nested" match — a
        # second, distinct nested path in the same diff must still be free
        # to raise Ambiguous (proven in test_root_path_plus_nested_is_not_two_matches).

    def test_root_path_plus_nested_is_not_two_matches(self) -> None:
        """If the pattern wrongly matched the literal root path too, this
        would raise AmbiguousEvidencePathError (2 matches). It must not —
        the root literal never counts as a "nested" candidate."""
        changed_files = ["evidence/pack.yml", "evidence/2026-08/some-slug-abcd1234/pack.yml"]

        resolved = resolve_evidence_path("pack", changed_files)

        assert resolved == "evidence/2026-08/some-slug-abcd1234/pack.yml"

    def test_single_nested_match_returns_that_path(self) -> None:
        changed_files = [
            "apps/backend-rag/backend/app/main.py",
            "evidence/2026-08/agent-mini-pro2-infra-s12-c6-35e07be7/pack.yml",
        ]

        resolved = resolve_evidence_path("pack", changed_files)

        assert resolved == "evidence/2026-08/agent-mini-pro2-infra-s12-c6-35e07be7/pack.yml"

    def test_other_kind_present_does_not_satisfy_this_kind(self) -> None:
        """A diff that writes its brief but not its pack must resolve
        "pack" to the root fallback, not to the brief's nested path —
        kinds are independent lookups."""
        changed_files = ["evidence/2026-08/some-slug-abcd1234/brief.yml"]

        resolved = resolve_evidence_path("pack", changed_files)

        assert resolved == "evidence/pack.yml"

    def test_unrelated_changed_files_are_ignored(self) -> None:
        changed_files = [
            "scripts/ci/evidence_paths.py",
            "docs/wr2/flowkit-integration.md",
            "evidence/2026-08/some-slug-abcd1234/pack.yml",
        ]

        resolved = resolve_evidence_path("pack", changed_files)

        assert resolved == "evidence/2026-08/some-slug-abcd1234/pack.yml"


class TestResolveEvidencePathGuilt:
    """Cases that must be rejected: ambiguous diffs (fail closed, never
    guess) and substring-trap near-misses (guard-over-match, superscar
    #3) that must NOT be mistaken for a real evidence path.
    """

    def test_two_nested_candidates_raises_ambiguous(self) -> None:
        changed_files = [
            "evidence/2026-08/slug-one-aaaaaaaa/pack.yml",
            "evidence/2026-08/slug-two-bbbbbbbb/pack.yml",
        ]

        with pytest.raises(AmbiguousEvidencePathError):
            resolve_evidence_path("pack", changed_files)

    def test_three_nested_candidates_raises_and_names_all_of_them(self) -> None:
        changed_files = [
            "evidence/2026-08/a/pack.yml",
            "evidence/2026-08/b/pack.yml",
            "evidence/2026-09/c/pack.yml",
        ]

        with pytest.raises(AmbiguousEvidencePathError) as excinfo:
            resolve_evidence_path("pack", changed_files)

        message = str(excinfo.value)
        for path in changed_files:
            assert path in message

    def test_substring_trap_extra_suffix_not_matched(self) -> None:
        """"pack.yml.bak" contains "pack.yml" as a substring but must not
        match the anchored, full-line pattern."""
        changed_files = ["evidence/2026-08/some-slug/pack.yml.bak"]

        assert resolve_evidence_path("pack", changed_files) == "evidence/pack.yml"

    def test_substring_trap_wrong_filename_not_matched(self) -> None:
        """"not-pack.yml" ends with "pack.yml" but is a different file —
        a non-anchored ".*pack\\.yml$" pattern would wrongly match this."""
        changed_files = ["evidence/2026-08/some-slug/not-pack.yml"]

        assert resolve_evidence_path("pack", changed_files) == "evidence/pack.yml"

    def test_missing_leading_evidence_segment_not_matched(self) -> None:
        changed_files = ["notevidence/2026-08/some-slug/pack.yml"]

        assert resolve_evidence_path("pack", changed_files) == "evidence/pack.yml"

    def test_cross_kind_confusion_not_matched(self) -> None:
        """A "brief.yml" nested path must never satisfy a "pack" lookup —
        proven separately from test_other_kind_present_does_not_satisfy_this_kind
        by also asserting the reverse direction here."""
        changed_files = ["evidence/2026-08/some-slug/brief.yml"]

        assert resolve_evidence_path("pack", changed_files) == "evidence/pack.yml"
        assert (
            resolve_evidence_path("brief", changed_files)
            == "evidence/2026-08/some-slug/brief.yml"
        )

    def test_unknown_kind_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            resolve_evidence_path("brief_and_pack", ["evidence/pack.yml"])


class TestResolveEvidencePathCLI:
    """--resolve wired through main(): the discovery mode CI actually
    invokes as a subprocess."""

    def test_single_match_prints_path_and_exits_zero(self, tmp_path, capsys) -> None:
        changed_files_path = tmp_path / "changed-files.txt"
        changed_files_path.write_text(
            "apps/backend-rag/backend/app/main.py\n"
            "evidence/2026-08/some-slug/pack.yml\n"
        )

        exit_code = main(["--resolve", "pack", "--changed-files-file", str(changed_files_path)])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert out.strip() == "evidence/2026-08/some-slug/pack.yml"

    def test_zero_matches_prints_root_path_and_exits_zero(self, tmp_path, capsys) -> None:
        changed_files_path = tmp_path / "changed-files.txt"
        changed_files_path.write_text("README.md\n")

        exit_code = main(["--resolve", "brief", "--changed-files-file", str(changed_files_path)])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert out.strip() == "evidence/brief.yml"

    def test_ambiguous_prints_nothing_to_stdout_error_to_stderr_exit_one(
        self, tmp_path, capsys
    ) -> None:
        changed_files_path = tmp_path / "changed-files.txt"
        changed_files_path.write_text(
            "evidence/2026-08/a/pack.yml\nevidence/2026-08/b/pack.yml\n"
        )

        exit_code = main(["--resolve", "pack", "--changed-files-file", str(changed_files_path)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "ambiguous" in captured.err.lower()

    def test_ref_and_resolve_are_mutually_exclusive(self, tmp_path) -> None:
        changed_files_path = tmp_path / "changed-files.txt"
        changed_files_path.write_text("README.md\n")

        with pytest.raises(SystemExit) as excinfo:
            main(
                [
                    "--ref",
                    "agent/pro/lane/task",
                    "--resolve",
                    "pack",
                    "--changed-files-file",
                    str(changed_files_path),
                ]
            )
        assert excinfo.value.code == 2

    def test_resolve_without_changed_files_file_errors(self) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--resolve", "pack"])
        assert excinfo.value.code == 2
