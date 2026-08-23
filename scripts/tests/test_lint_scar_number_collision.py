"""
Guilt AND innocence for scripts/lint_scar_number_collision.py — the executable
antidote for W128 (scar-number collision: a `W<n>` is only CLAIMED when a PR
opens and only RESOLVED when it merges; `origin/main` alone undercounts the
live claim set by every number sitting in an open, unmerged PR).

These run the real CLI as a subprocess against a `--fixture` JSON file (no
git/gh network calls, no live repo state) and read `result.returncode`
directly off the command — never through a pipe, per the mandate's own
warning that a piped rc measures the wrong process.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "lint_scar_number_collision.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import lint_scar_number_collision as lint  # noqa: E402


def _run_fixture(
    tmp_path: Path,
    main_md: str,
    prs: dict[str, str],
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"main": main_md, "prs": prs}))
    cmd = [sys.executable, str(SCRIPT), "--fixture", str(fixture), *(extra_args or [])]
    # rc captured ON this command, never after a pipe — a piped rc would
    # measure the pipe's last stage, not this process (the same trap the
    # mandate names for manual dogfooding, pinned here as an automated test).
    return subprocess.run(cmd, capture_output=True, text=True)


def _added_heading_patch(number: int) -> str:
    """A minimal unified-diff `.patch` fragment adding one scar heading —
    the shape `gh api repos/{repo}/pulls/{n}/files` really returns."""
    return (
        "@@ -1325,3 +1325,8 @@ some context line\n"
        " unchanged context\n"
        "+\n"
        f"+### 🐛 W{number} (2026-08-23): a new scar\n"
        "+\n"
        "+body text\n"
    )


MAIN_MD = "### 🐛 W125 (2026-08-23): risolvere i marker A MANO non è `--ours`\n"


class TestGuiltTwoOpenPRsClaimTheSameNumber:
    """The 2026-08-23 incident, reproduced verbatim: main tops out at W125,
    two open PRs each independently add a bare W126 heading three minutes
    apart — a naive `sort -n | tail -1` against main alone would have called
    W126 free for both of them."""

    def test_the_w126_w126_incident_is_caught(self, tmp_path: Path) -> None:
        result = _run_fixture(
            tmp_path,
            MAIN_MD,
            {"PR #4713": _added_heading_patch(126), "PR #4714": _added_heading_patch(126)},
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "COLLISION" in result.stdout
        assert "W126" in result.stdout
        assert "PR #4713" in result.stdout
        assert "PR #4714" in result.stdout

    def test_a_pr_claiming_a_number_already_on_main_is_also_a_collision(self, tmp_path: Path) -> None:
        result = _run_fixture(tmp_path, MAIN_MD, {"PR #9999": _added_heading_patch(125)})
        assert result.returncode == 1, result.stdout + result.stderr
        assert "W125" in result.stdout


class TestInnocenceDistinctNumbersPass:
    def test_two_open_prs_with_distinct_numbers_exit_zero(self, tmp_path: Path) -> None:
        result = _run_fixture(
            tmp_path,
            MAIN_MD,
            {"PR #4713": _added_heading_patch(126), "PR #4714": _added_heading_patch(127)},
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "COLLISION" not in result.stdout
        assert "Next free scar number: W128" in result.stdout

    def test_next_only_mode_prints_the_bare_number(self, tmp_path: Path) -> None:
        result = _run_fixture(
            tmp_path,
            MAIN_MD,
            {"PR #4713": _added_heading_patch(126)},
            extra_args=["--next-only"],
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == "W127"

    def test_suffix_disambiguated_history_on_main_alone_is_not_a_collision(self, tmp_path: Path) -> None:
        """W81 / W81-armamento-sospeso / W81b-dlq-blind-heal-loop coexist on
        origin/main by design (cicatrix-superscar.md #1, already-resolved
        disambiguation) — same base number, ONE source (origin/main itself),
        never flagged."""
        main_md = (
            "### ✅ W81 (FIXED): i 3 loop di apprendimento WR3 erano verdi ma vuoti\n"
            "### \U0001F41B W81-armamento-sospeso (2026-06-15): ~20 cron armati a vuoto\n"
            "### \U0001F41B W81b-dlq-blind-heal-loop (2026-06-15): 14 DLQ corpses mai puliti\n"
        )
        result = _run_fixture(tmp_path, main_md, {})
        assert result.returncode == 0, result.stdout + result.stderr
        assert "COLLISION" not in result.stdout


class TestHeadingRegexSurvivesTheEmojiGap:
    """The mandate's own first grep (`^#+ W[0-9]+`) matched nothing because an
    emoji sits between the `#`s and the `W`. Pin that this parser does not
    repeat the mistake, on lines lifted verbatim from the real scar file."""

    def test_bare_emoji_heading(self) -> None:
        assert lint.parse_heading_numbers("### \U0001F41B W77\n") == [77]

    def test_dated_emoji_heading(self) -> None:
        text = "### \U0001F41B W127 (2026-08-23): un `Formatter` mutava `record.levelname`\n"
        assert lint.parse_heading_numbers(text) == [127]

    def test_hash4_twin_scar_subheading(self) -> None:
        assert lint.parse_heading_numbers("#### W67b — the follow-up\n") == [67]

    def test_hash2_heading(self) -> None:
        text = "## W94 — worktree-isolation remote-dispatch exemption is WHOLE-COMMAND\n"
        assert lint.parse_heading_numbers(text) == [94]

    def test_non_heading_prose_mentioning_a_w_number_is_ignored(self) -> None:
        text = "Citato nella famiglia #3 come W68 — nessun dettaglio ulteriore.\n"
        assert lint.parse_heading_numbers(text) == []


class TestFindCollisionsUnit:
    """Direct unit coverage of the pure function the CLI's exit code hangs on."""

    def test_no_sources_no_collisions(self) -> None:
        assert lint.find_collisions({}) == {}

    def test_single_non_main_source_is_never_a_collision(self) -> None:
        claim_map = lint.compute_claim_map([], {"PR #1": [126]})
        assert lint.find_collisions(claim_map) == {}

    def test_next_free_number_is_max_plus_one(self) -> None:
        claim_map = lint.compute_claim_map([125], {"PR #4713": [126]})
        assert lint.next_free_number(claim_map) == 127

    def test_next_free_number_on_empty_claim_map_is_one(self) -> None:
        assert lint.next_free_number({}) == 1
