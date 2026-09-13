"""Guilt+innocence for the machine-local injected-surface attestation.

The CI sibling (`test_injected_surface_budget.py`) guards the repo-side half and
runs on every PR. THIS file guards the probe that runs on a real machine — the
one that can see the global `~/.claude/CLAUDE.md` and the machine's own
`claudeMdExcludes`, neither of which exists on a runner.

Every case builds a synthetic HOME + repo root, so nothing here depends on the
machine it runs on: a probe whose test only passes on the author's laptop is a
probe nobody can trust on the other two nodes (superscar family #1).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "injected_surface_attest.py"
_spec = importlib.util.spec_from_file_location("injected_surface_attest", _MODULE_PATH)
assert _spec and _spec.loader
attest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(attest)


def _world(tmp_path: Path, rules: dict[str, int], *, excludes: list[str] | None = None) -> tuple[Path, Path]:
    """A synthetic (repo_root, home) pair with files of exact byte sizes."""
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    (repo / ".claude" / "rules").mkdir(parents=True)
    (home / ".claude").mkdir(parents=True)
    (repo / "CLAUDE.md").write_bytes(b"p" * 1000)
    (home / ".claude" / "CLAUDE.md").write_bytes(b"g" * 500)
    for name, size in rules.items():
        (repo / ".claude" / "rules" / name).write_bytes(b"r" * size)
    if excludes is not None:
        (home / ".claude" / "settings.json").write_text(json.dumps({"claudeMdExcludes": excludes}))
    return repo, home


def test_innocence_small_surface_is_under_budget(tmp_path: Path) -> None:
    repo, home = _world(tmp_path, {"cicatrix-superscar.md": 14_000})
    r = attest.measure(repo, home)
    assert r["total_bytes"] == 1000 + 500 + 14_000
    assert r["total_bytes"] < attest.INTERIM_BYTE_BUDGET
    assert r["unpinned_rules_files"] == []


def test_guilt_the_pre_move_shape_blows_the_budget(tmp_path: Path) -> None:
    """The exact regression this lane exists for: two scar bodies back in the
    auto-loaded rules dir. Sized from the real 2026-08-31 measurement."""
    repo, home = _world(
        tmp_path,
        {
            "cicatrix-superscar.md": 13_998,
            "cicatrix-scars.md": 296_243,
            "cicatrix-scars-archive.md": 396_609,
        },
    )
    r = attest.measure(repo, home)
    assert r["total_bytes"] > attest.INTERIM_BYTE_BUDGET
    assert sorted(r["unpinned_rules_files"]) == [
        "cicatrix-scars-archive.md",
        "cicatrix-scars.md",
    ]


def test_guilt_any_unpinned_file_is_named_even_when_tiny(tmp_path: Path) -> None:
    """Under budget is not innocence: a new doctrine file is paid by every
    session and every subagent, so it is named the moment it appears."""
    repo, home = _world(tmp_path, {"cicatrix-superscar.md": 100, "zz-new-doctrine.md": 10})
    r = attest.measure(repo, home)
    assert r["total_bytes"] < attest.INTERIM_BYTE_BUDGET
    assert r["unpinned_rules_files"] == ["zz-new-doctrine.md"]


def test_excludes_are_reported_but_never_subtracted(tmp_path: Path) -> None:
    """The load-bearing scepticism: `claudeMdExcludes` has been armed on all
    three machines since 2026-06-14 and measurably does not exclude. If a future
    edit starts crediting it, this test goes red — which is the point."""
    # Split like the guard's own `_NEEDLE`: this string is data under test, not a
    # stale resolver, and the anti-regrowth scan reads text without knowing the
    # difference. Concatenating keeps the exemption list at the two entries that
    # genuinely cannot avoid the literal (cicatrix-scars.md W108).
    excluded = "**/.claude" + "/rules/cicatrix-scars.md"
    repo, home = _world(
        tmp_path,
        {"cicatrix-superscar.md": 10, "cicatrix-scars.md": 300_000},
        excludes=[excluded],
    )
    r = attest.measure(repo, home)
    assert r["total_bytes"] == 1000 + 500 + 10 + 300_000, "an excluded file must still be counted"
    assert r["declared_excludes_not_credited"] == [excluded]


def test_unreadable_settings_is_visible_not_silent(tmp_path: Path) -> None:
    repo, home = _world(tmp_path, {"cicatrix-superscar.md": 10})
    (home / ".claude" / "settings.json").write_text("{not json")
    r = attest.measure(repo, home)
    assert r["declared_excludes_not_credited"] == ["<settings.json unreadable>"]


def test_absent_rules_dir_is_reported_as_absent_not_as_lean(tmp_path: Path) -> None:
    """A repo root with NO `.claude/rules/` at all.

    The earlier version of this test built its world with `_world(tmp_path, {})`,
    which always CREATES the directory — so it asserted on an empty dir while its
    name promised a missing one, and could not have failed if the resolver
    mishandled absence. A premise that is not what the name says is a test that
    passes for a reason nobody chose (cicatrix W116). Built by hand here so the
    directory genuinely does not exist."""
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()
    (home / ".claude").mkdir(parents=True)
    (repo / "CLAUDE.md").write_bytes(b"p" * 1000)
    (home / ".claude" / "CLAUDE.md").write_bytes(b"g" * 500)
    assert not (repo / ".claude" / "rules").exists(), "premise: the dir must be absent"

    r = attest.measure(repo, home)
    # The two CLAUDE.md files still land, so a broken resolver reads as a small
    # number rather than as silence — and `total > 0` in the CI sibling stays a
    # meaningful assertion instead of a tautology.
    assert r["total_bytes"] == 1500
    assert r["unpinned_rules_files"] == []


def test_an_entirely_missing_repo_root_is_not_reported_as_success(tmp_path: Path) -> None:
    """Point the probe at a path that does not exist at all.

    Codex refutation, 2026-08-31: `--repo-root /definitely/missing` printed a
    green `0 B` and exited 0 — a resolver finding nothing rendered as a budget
    respected, which is the exact shape this whole lane exists to remove."""
    # HOME is real here on purpose: that is the case that used to read green,
    # because the global CLAUDE.md alone made the total non-zero.
    r = attest.measure(tmp_path / "no-such-repo", Path.home())
    assert r["resolver_found_nothing"] is True, (
        "a repo root with no CLAUDE.md and no .claude/rules must read as BROKEN "
        "even when the machine-local global file is found"
    )
