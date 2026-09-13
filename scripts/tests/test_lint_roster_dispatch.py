"""test_lint_roster_dispatch.py — guilt + innocence fixtures for lint_roster_dispatch.py.

Runs the script as a real subprocess against `--fixture` JSON files (never calls
private functions directly) — same pattern as test_lint_scar_number_collision.py
and test_lint_home_fork.py: the CLI/argparse boundary is part of what's under
test, not just the internal logic.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "lint_roster_dispatch.py"


def run_lint(fixture: dict, tmp_path: Path) -> subprocess.CompletedProcess:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--fixture", str(fixture_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def roster_row(model_id: str, note: str = "role text") -> str:
    return f"| `{model_id}` | {note} | effort |"


# ---------------------------------------------------------------- innocence

def test_claude_alias_has_a_door(tmp_path):
    result = run_lint({"roster": roster_row("claude-opus-5")}, tmp_path)
    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout


def test_tp1_slug_with_route_file_has_a_door(tmp_path):
    fixture = {
        "roster": roster_row("deepseek-v4-flash-0731"),
        "route_files": ["deepseek-v4-flash-0731"],
    }
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


def test_gemini_and_kimi_and_imagegen_have_doors(tmp_path):
    fixture = {
        "roster": "\n".join(
            [
                roster_row("gemini-3.1-pro"),
                roster_row("k3"),
                roster_row("kimi-for-coding"),
                roster_row("$imagegen"),
            ]
        ),
    }
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


def test_ollama_role_value_has_a_door(tmp_path):
    fixture = {"roster": roster_row("qwen3.5:9b"), "ollama_roles": ["qwen3.5:9b"]}
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


def test_codex_tier_slugs_resolve_without_marker(tmp_path):
    """sol/terra/luna resolve via the codex door (PR #5044's `--seat codex
    --tier <id>`) and need no UNREACHABLE marker — corrected 2026-08-27: an
    earlier version of this lint (and of MODEL_ROSTER.md) treated the BARE
    `-m sol` slug's 2026-07-21 death as proof the versioned `-m gpt-5.6-sol`
    door was dead too. It was live all along; live 1-token probes of all
    three tiers in this PR (plus PR #5044's own refuter run for sol) proved
    it, so this test replaces the old dead-slug fixture rather than keep
    asserting a defect that no longer exists."""
    fixture = {"roster": "\n".join([roster_row("sol"), roster_row("terra"), roster_row("luna")])}
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


def test_any_doorless_row_marked_unreachable_is_clean(tmp_path):
    fixture = {"roster": roster_row("some-gui-only-tool", "GUI only. UNREACHABLE (no CLI).")}
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------- guilt


def test_tp1_slug_without_route_file_is_an_offender(tmp_path):
    fixture = {"roster": roster_row("qwen3.8-max"), "route_files": []}
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 1
    assert "`qwen3.8-max`" in result.stderr


def test_unknown_id_without_marker_is_an_offender(tmp_path):
    result = run_lint({"roster": roster_row("mystery-model-9000")}, tmp_path)
    assert result.returncode == 1
    assert "`mystery-model-9000`" in result.stderr


def test_offender_and_clean_row_together_reports_only_the_offender(tmp_path):
    fixture = {
        "roster": "\n".join([roster_row("claude-sonnet-5"), roster_row("unmapped-model-zzz")]),
    }
    result = run_lint(fixture, tmp_path)
    assert result.returncode == 1
    assert "`unmapped-model-zzz`" in result.stderr
    assert "`claude-sonnet-5`" not in result.stderr


# ---------------------------------------------------------------- blind-scan guard (W84)

def test_zero_rows_parsed_is_an_operational_error_not_a_clean_pass(tmp_path):
    """A doc with no `| \\`id\\`` rows at all must never read as 'nothing wrong'
    — that is the blind-scan disease this whole family of lints exists to
    avoid (scar W84: a run that checked 0 things is not the same as clean)."""
    result = run_lint({"roster": "# Just prose, no table rows here.\n"}, tmp_path)
    assert result.returncode == 2


def test_unreadable_fixture_is_an_operational_error(tmp_path):
    bad_path = tmp_path / "does-not-exist.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--fixture", str(bad_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2


# ---------------------------------------------------------------- drift guard (kimi refuter round 1)

def test_route_files_base_url_matches_arsenal_probe_constant():
    """kimi refuter round 1: the review_routes/*.json files and tp1_call.py
    (via its arsenal_probe import) are two independently-editable sources for
    the same TP1 endpoint. The lint only proves a route FILE exists, never
    that its content agrees with the constant the actual door uses — so a
    future edit to one could silently drift from the other with nothing red.
    This closes that gap directly: every live TP1 slug's route file must
    declare the exact base_url arsenal_probe.py (and therefore tp1_call.py)
    actually calls."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from arsenal_probe import TP1_BASE_URL, TP1_SEAT_MODELS  # noqa: E402

    route_dir = REPO_ROOT / "scripts" / "review_routes"
    for slug in TP1_SEAT_MODELS.values():
        route_path = route_dir / f"{slug}-v1.json"
        assert route_path.exists(), f"missing route file for live TP1 slug {slug}"
        doc = json.loads(route_path.read_text(encoding="utf-8"))
        assert doc.get("base_url") == TP1_BASE_URL, (
            f"{route_path.name} base_url {doc.get('base_url')!r} has drifted "
            f"from arsenal_probe.TP1_BASE_URL {TP1_BASE_URL!r}"
        )


# ---------------------------------------------------------------- ground truth: the real repo file

def test_real_model_roster_is_clean():
    """Integration check against the actual on-disk MODEL_ROSTER.md and
    scripts/review_routes/ — proves the roster edits and the new route JSONs
    in this PR actually satisfy the lint together, not just in isolation."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"


# ------------------------------------- roster quorum column vs the gate that enforces it

def _roster_quorum_claims() -> dict[str, bool]:
    """Parse MODEL_ROSTER.md's TP1 table into {slug: says_quorum_yes}.

    Parsed, not hardcoded: a test that restates the expected answer would pass
    while both sides are wrong together, which is the exact failure being
    guarded against."""
    import re

    claims: dict[str, bool] = {}
    roster_text = (REPO_ROOT / "MODEL_ROSTER.md").read_text(encoding="utf-8")
    for line in roster_text.splitlines():
        if not line.startswith("|") or "quorum:" not in line:
            continue
        slug_match = re.match(r"\|\s*`([^`]+)`", line)
        if not slug_match:
            continue
        quorum_match = re.search(r"quorum:\s*\**\s*(yes|no)", line, re.IGNORECASE)
        if not quorum_match:
            continue
        claims[slug_match.group(1)] = quorum_match.group(1).lower() == "yes"
    return claims


def test_roster_quorum_column_matches_the_lint():
    """MODEL_ROSTER.md's `quorum:` column must agree with the tuple that
    actually decides quorum.

    They disagreed from 2026-08-14 to 2026-09-02: the roster said `quorum: no`
    for qwen3.8-max while evidence_pack_lint.COUNCIL_REVIEW_SEATS counted it,
    and R9 was a NOTICE for that whole window — so nothing failed, and the
    contradiction was found by hand rather than by CI, one day before it turned
    into a hard gate. A conductor trusting the roster would not have dispatched
    a seat the gate required.

    Both sides are READ here, neither is asserted from memory. The seat token
    in the lint carries a `tp1-` prefix the roster's slug does not, so the
    comparison strips it."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from evidence_pack_lint import COUNCIL_REVIEW_SEATS  # noqa: E402

    counted = {
        seat[len("tp1-") :] for seat in COUNCIL_REVIEW_SEATS if seat.startswith("tp1-")
    }
    claims = _roster_quorum_claims()
    assert claims, (
        "parsed no `quorum:` rows out of MODEL_ROSTER.md — the parser broke, not the docs"
    )

    for slug, says_yes in sorted(claims.items()):
        is_counted = slug in counted
        if says_yes and not is_counted:
            raise AssertionError(
                f"MODEL_ROSTER.md says `quorum: yes` for {slug!r}, but "
                f"evidence_pack_lint.COUNCIL_REVIEW_SEATS does not contain it. A conductor "
                f"would dispatch this seat expecting it to count toward R9, and it would not."
            )
        if is_counted and not says_yes:
            raise AssertionError(
                f"evidence_pack_lint.COUNCIL_REVIEW_SEATS counts {slug!r} toward the Gear-3 "
                f"quorum, but MODEL_ROSTER.md says `quorum: no` for it. A conductor following "
                f"the roster would NOT dispatch it and could then fail R9 on a properly "
                f"reviewed PR — the exact 2026-08-14..09-02 contradiction this test exists to "
                f"prevent recurring."
            )


def test_at_least_one_tp1_seat_is_actually_in_the_quorum_tuple():
    """Innocence control for the test above.

    Without this, deleting every TP1 seat from COUNCIL_REVIEW_SEATS and writing
    `quorum: no` on every roster row would leave the agreement test vacuously
    green while the quorum pool silently shrank from three families to two."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from evidence_pack_lint import COUNCIL_REVIEW_SEATS  # noqa: E402

    assert any(seat.startswith("tp1-") for seat in COUNCIL_REVIEW_SEATS), (
        "no TP1 seat counts toward Gear-3 quorum any more. That may be a deliberate ruling, "
        "but it drops the pool to two families — every Gear-3 PR then needs BOTH survivors "
        "alive. Update this test WITH the ruling, do not delete it."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
