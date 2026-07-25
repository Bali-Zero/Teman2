"""Guilt+innocence tests for scripts/detect_secrets_auto_triage.py's
CONTENT_KEYED_RULES (cicatrix-superscar.md #3 — guard over/under-match).

Registered in infra/guard-conformance/registry.json under the
`detect_secrets_content_keyed_rules` surface; executed by
.github/workflows/worker-plane-review-tests.yml — the workflow that already
owns scripts/check_worker_plane_review.py and
scripts/launch_worker_plane_review_panel.py, the two files this rule scopes
to.

Context (PR #3127): a fresh `detect-secrets scan` surfaced 18 unaudited
"Hex High Entropy String" findings in these two files — all executable
code-signing identity pins (sha256/cdhash of production CLI binaries used
to verify supply-chain integrity before spawning a reviewer process, plus a
PRODUCTION_ARTIFACT_SHA256 dict of the same class of content hash). These
are public integrity anchors, never credentials — removing them would
weaken the check they implement.

A plain PATH-based auto-triage rule (the shape most of this file's existing
AUTO_APPROVE_RULES use) would have blanket-approved ANY future finding
anywhere in these two files, including a real secret added later on an
unrelated line — exactly the #3 guard-over-match failure mode this repo's
cicatrix catalog warns about. CONTENT_KEYED_RULES instead requires the
actual source line at the finding's line_number to ALSO match a narrow
assignment-target pattern (`sha256|cdhash|codex_wrapper|codex_package`), so
the corpus below proves both halves: the 18 real findings get approved
(guilt) AND an unrelated secret on some other line in the SAME files does
not (innocence).
"""

from __future__ import annotations

from scripts.detect_secrets_auto_triage import CONTENT_KEYED_RULES, classify

CHECK_WORKER_PLANE_REVIEW = "scripts/check_worker_plane_review.py"
LAUNCH_WORKER_PLANE_REVIEW_PANEL = "scripts/launch_worker_plane_review_panel.py"

# Line numbers verified against the actual files on disk 2026-07-26 (the
# exact 18 findings `Detect Secrets` flagged on PR #3127).
CHECK_WORKER_PLANE_REVIEW_PIN_LINES = [142, 143, 153, 154]
LAUNCH_WORKER_PLANE_REVIEW_PANEL_PIN_LINES = [
    210,
    211,
    222,
    223,
    238,
    239,
    248,
    249,
    260,
    261,
    273,
    274,
    284,
    285,
]


def test_rule_registered_and_scoped_to_exactly_two_files() -> None:
    """Sanity: exactly one content-keyed rule, path-scoped to the two
    worker-plane review files — not a blanket match on scripts/*.py."""
    assert len(CONTENT_KEYED_RULES) == 1
    path_pat, _content_pat, reason = CONTENT_KEYED_RULES[0]
    assert path_pat.search(CHECK_WORKER_PLANE_REVIEW)
    assert path_pat.search(LAUNCH_WORKER_PLANE_REVIEW_PANEL)
    assert not path_pat.search("scripts/some_other_review_script.py")
    assert "credentials" in reason


# --- GUILT: the 18 real PR #3127 findings must be auto-approved -----------


def test_guilt_check_worker_plane_review_identity_pins_approved() -> None:
    for line in CHECK_WORKER_PLANE_REVIEW_PIN_LINES:
        auto, _reason = classify(CHECK_WORKER_PLANE_REVIEW, line)
        assert auto, f"{CHECK_WORKER_PLANE_REVIEW}:{line} should be auto-approved"


def test_guilt_launch_worker_plane_review_panel_identity_pins_approved() -> None:
    for line in LAUNCH_WORKER_PLANE_REVIEW_PANEL_PIN_LINES:
        auto, _reason = classify(LAUNCH_WORKER_PLANE_REVIEW_PANEL, line)
        assert auto, f"{LAUNCH_WORKER_PLANE_REVIEW_PANEL}:{line} should be auto-approved"


def test_guilt_production_artifact_sha256_dict_members_approved() -> None:
    """PRODUCTION_ARTIFACT_SHA256's members (codex_wrapper, codex_package)
    don't say sha256=/cdhash= on their own line — they are the two findings
    a rule keyed ONLY on the literal names `sha256`/`cdhash` would have
    missed, which is why those two names are also in the content pattern."""
    for line in (284, 285):
        auto, _reason = classify(LAUNCH_WORKER_PLANE_REVIEW_PANEL, line)
        assert auto, f"{LAUNCH_WORKER_PLANE_REVIEW_PANEL}:{line} should be auto-approved"


# --- INNOCENCE: unrelated lines/files must stay flagged --------------------


def test_innocence_unrelated_lines_in_same_files_not_approved() -> None:
    """Lines that are NOT sha256/cdhash/codex_wrapper/codex_package
    assignments must remain unaudited even inside the two approved files —
    this is what distinguishes a content-keyed rule from a blanket
    whole-file path rule (the over-match this rule exists to avoid)."""
    # kimi=Path(...) — unrelated identifier.
    auto, reason = classify(LAUNCH_WORKER_PLANE_REVIEW_PANEL, 190)
    assert not auto
    assert reason == "no rule matched"
    # team_identifier="..." — also unrelated.
    auto, reason = classify(LAUNCH_WORKER_PLANE_REVIEW_PANEL, 212)
    assert not auto
    assert reason == "no rule matched"


def test_innocence_synthetic_secret_on_unrelated_key_in_same_file() -> None:
    """A real secret assigned to a DIFFERENT identifier in one of these two
    files (e.g. a leaked API key added on a future PR) must still be
    caught — proves the rule is keyed on the assignment target, never on
    hex/secret shape alone."""
    _path_pat, content_pat, _reason = CONTENT_KEYED_RULES[0]
    fake_secret_line = '        api_key="sk-FAKESECRETVALUE1234567890ABCDEF",\n'
    assert content_pat.search(fake_secret_line) is None


def test_innocence_other_file_with_sha256_assignment_not_approved() -> None:
    """The identical sha256= assignment shape in a file OUTSIDE the two
    scoped paths must not be auto-approved by this rule — proves the path
    scope, not just the content pattern, is load-bearing."""
    auto, reason = classify("scripts/some_other_script.py", 210)
    assert not auto
    assert reason == "no rule matched"
