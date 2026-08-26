"""W41 (2026-05-23) — tests for lint_migration_numbers.py.

Locks the contract: the inlined find_duplicates() must produce the SAME
verdict as `backend.db.migration_manager._assert_unique_migration_numbers`.
Drift between the two would re-open the W40 class.

mig-collision-281 (2026-08-26) adds the cross-branch collision check's own
guilt/innocence pairs — see the module docstring in lint_migration_numbers.py
for what problem it closes (find_duplicates only ever sees ONE tree; the
281_team_bot_ingress_leader.sql vs 281_garuda_voa_retention.sql collision was
invisible to it on both branches).
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "lint_migration_numbers.py"


def _load_lint():
    spec = importlib.util.spec_from_file_location("lint_mignum", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint()


def _mk(tmp_path: Path, *names: str) -> list[Path]:
    out: list[Path] = []
    for n in names:
        p = tmp_path / n
        p.write_text("-- empty\n")
        out.append(p)
    return out


def test_no_files_returns_empty(lint, tmp_path):
    assert lint.find_duplicates(_mk(tmp_path)) == {}


def test_unique_prefixes_clean(lint, tmp_path):
    files = _mk(tmp_path, "192_a.sql", "193_b.sql", "194_c.sql")
    assert lint.find_duplicates(files) == {}


def test_w40_collision_caught(lint, tmp_path):
    """The actual W40 case: 194_organism_incident_ledger vs 194_reconcile_107."""
    files = _mk(
        tmp_path,
        "194_organism_incident_ledger.sql",
        "194_reconcile_107_bridge_outbox_tracking.sql",
    )
    dups = lint.find_duplicates(files)
    assert 194 in dups
    assert len(dups[194]) == 2


def test_2026_04_29_legacy_pattern_caught(lint, tmp_path):
    """The original P0-7 cicatrix: dup 129 + dup 130."""
    files = _mk(
        tmp_path,
        "129_a.sql",
        "129_b.sql",
        "130_x.sql",
        "130_y.sql",
        "131_solo.sql",
    )
    dups = lint.find_duplicates(files)
    assert set(dups.keys()) == {129, 130}
    assert len(dups[129]) == 2
    assert len(dups[130]) == 2


def test_non_numeric_prefix_ignored(lint, tmp_path):
    files = _mk(tmp_path, "194_real.sql", "rollback_one.sql", "README.sql")
    assert lint.find_duplicates(files) == {}


def test_triple_collision_lists_all(lint, tmp_path):
    files = _mk(tmp_path, "200_a.sql", "200_b.sql", "200_c.sql")
    dups = lint.find_duplicates(files)
    assert 200 in dups
    assert len(dups[200]) == 3


def test_main_exits_0_on_live_repo(capsys, monkeypatch):
    """Live state should be green post-W40."""
    mod = _load_lint()
    rc = mod.main()
    captured = capsys.readouterr()
    assert rc == 0, f"live migrations_v2 has duplicate prefixes:\n{captured.out}"
    assert "all unique prefixes" in captured.out


def test_main_exits_1_on_synthetic_collision(lint, tmp_path, monkeypatch, capsys):
    """Point MIGRATIONS_DIR at a tmp_path with a duplicate."""
    _mk(tmp_path, "194_a.sql", "194_b.sql", "195_c.sql")
    monkeypatch.setattr(lint, "MIGRATIONS_DIR", tmp_path)
    # This test is about the SAME-TREE check only. Real main() also runs
    # check_cross_branch(sql_files) against the real REPO_ROOT/origin-main —
    # and these synthetic numbers (194/195) collide BY NAME with real
    # migrations on this repo's actual main, which would fail the test for
    # an unrelated reason. Neutralize it here; it's exercised on its own
    # below.
    monkeypatch.setattr(lint, "check_cross_branch", lambda *a, **k: (None, {}))
    rc = lint.main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "duplicate prefixes" in captured.out + captured.err


def test_main_exits_0_on_synthetic_clean(lint, tmp_path, monkeypatch, capsys):
    _mk(tmp_path, "194_a.sql", "195_b.sql", "196_c.sql")
    monkeypatch.setattr(lint, "MIGRATIONS_DIR", tmp_path)
    # Same reason as above: isolate the same-tree check from the (real,
    # network-free but repo-real) cross-branch check.
    monkeypatch.setattr(lint, "check_cross_branch", lambda *a, **k: (None, {}))
    rc = lint.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert "all unique prefixes" in captured.out


def test_drift_check_vs_canonical(lint, tmp_path):
    """Contract: find_duplicates must agree with the manager's algorithm.

    We re-implement the manager's algorithm here verbatim (6 lines, the
    same as inlined in the lint script) and assert the two produce
    identical results on a stressed input set.
    """
    files = _mk(
        tmp_path,
        "1_a.sql", "2_b.sql", "2_c.sql", "10_d.sql",
        "100_e.sql", "100_f.sql", "100_g.sql",
        "weird.sql", "rollback_old.sql",
    )

    def canonical(sql_files):
        seen: dict[int, str] = {}
        duplicates: dict[int, list[str]] = {}
        for sql_file in sql_files:
            try:
                num = int(sql_file.stem.split("_")[0])
            except (ValueError, IndexError):
                continue
            if num in seen:
                duplicates.setdefault(num, [seen[num]]).append(sql_file.name)
            else:
                seen[num] = sql_file.name
        return duplicates

    assert lint.find_duplicates(files) == canonical(files)


def test_guilt_empty_migrations_dir_refuses_to_report_clean(lint, tmp_path, monkeypatch, capsys):
    """An EXISTING but empty migrations dir must fail loud, not warn-and-pass.

    cicatrix #4 / W84: "0 files traversed != clean". The missing-directory case
    already exited 2; this closes the narrower sibling a partial/sparse checkout
    produces — the directory is there, the .sql files are not.
    """
    monkeypatch.setattr(lint, "MIGRATIONS_DIR", tmp_path)
    rc = lint.main()
    captured = capsys.readouterr()
    assert rc == 2, "a lint that read zero files must not report success"
    assert "BLIND SCAN" in captured.err


# ---------------------------------------------------------------------------
# Cross-branch collision check (mig-collision-281, 2026-08-26)
#
# find_cross_branch_collisions() is pure: {number: filename} maps in,
# {number: (working, target)} out. These pairs use the ACTUAL filenames from
# the incident this check exists to catch.
# ---------------------------------------------------------------------------


def test_guilt_cross_branch_collision_is_the_real_281_incident(lint):
    """GUILT: reproduce the exact shape that motivated this check."""
    working = {
        281: "281_team_bot_ingress_leader.sql",
        282: "282_team_bot_ingress_leader_epoch_monotonic.sql",
        283: "283_wa_reply_claims.sql",
    }
    target = {
        281: "281_garuda_voa_retention.sql",
        283: "283_wa_reply_claims.sql",
        284: "284_garuda_orders.sql",
    }
    collisions = lint.find_cross_branch_collisions(working, target)
    assert collisions == {
        281: ("281_team_bot_ingress_leader.sql", "281_garuda_voa_retention.sql"),
    }


def test_innocence_same_filename_both_sides_is_not_a_collision(lint):
    """INNOCENCE: a migration already converged across branches (283, in the
    real incident) must never be reported — same number, same file, no
    collision, regardless of what else diverges.
    """
    working = {283: "283_wa_reply_claims.sql", 290: "290_broker_jobs_client_bot.sql"}
    target = {283: "283_wa_reply_claims.sql", 284: "284_garuda_orders.sql"}
    assert lint.find_cross_branch_collisions(working, target) == {}


def test_innocence_no_numeric_overlap_is_not_a_collision(lint):
    """INNOCENCE: the ordinary case — a branch adding new, non-overlapping
    numbers ahead of the target's tip — must stay clean."""
    working = {291: "291_team_bot_ingress_leader.sql", 292: "292_team_bot_ingress_leader_epoch_monotonic.sql"}
    target = {287: "287_garuda_practices.sql"}
    assert lint.find_cross_branch_collisions(working, target) == {}


def test_innocence_empty_target_is_not_a_collision(lint):
    """INNOCENCE: nothing on the target side (e.g. the migrations_v2/ dir
    doesn't exist yet at that ref) can't collide with anything."""
    working = {194: "194_a.sql"}
    assert lint.find_cross_branch_collisions(working, {}) == {}


# --- integration level: exercises the real git plumbing (_resolve_ref,
# --- _list_migration_numbers_at_ref, check_cross_branch), not just the
# --- pure comparison above.


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _write(repo: Path, relpath: str, name: str, content: str = "-- x\n") -> None:
    p = repo / relpath / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


_REL = "apps/backend-rag/backend/db/migrations_v2"


@pytest.fixture
def collision_repo(tmp_path: Path) -> Path:
    """A tiny real git repo reproducing the 281 incident: `main` and
    `feature` each independently claim 281 for a different migration, with
    283 landing identically on both (the innocence case) and a number
    (282) only `feature` has.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _write(repo, _REL, "280_base.sql")
    _write(repo, _REL, "283_wa_reply_claims.sql", "-- shared, identical both sides\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    # main independently adds its own 281 AFTER the branch point below.
    _write(repo, _REL, "281_garuda_voa_retention.sql")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "main: add 281 garuda_voa_retention")

    # feature branches from BEFORE main's 281 and independently claims 281/282.
    _git(repo, "branch", "feature", "HEAD~1")
    _git(repo, "checkout", "-q", "feature")
    _write(repo, _REL, "281_team_bot_ingress_leader.sql")
    _write(repo, _REL, "282_team_bot_ingress_leader_epoch_monotonic.sql")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feature: add 281/282 team_bot")
    return repo


def test_guilt_integration_real_git_repo_catches_the_collision(lint, collision_repo: Path):
    sql_files = sorted((collision_repo / _REL).glob("*.sql"))
    resolved, cross = lint.check_cross_branch(sql_files, cwd=collision_repo, target="main")
    assert resolved == "main"
    assert cross == {
        281: ("281_team_bot_ingress_leader.sql", "281_garuda_voa_retention.sql"),
    }


def test_innocence_integration_converged_file_not_flagged(lint, collision_repo: Path):
    sql_files = sorted((collision_repo / _REL).glob("*.sql"))
    _, cross = lint.check_cross_branch(sql_files, cwd=collision_repo, target="main")
    assert 283 not in cross


def test_innocence_integration_unresolvable_target_degrades_gracefully(
    lint, collision_repo: Path
):
    """INNOCENCE: a target ref nobody fetched (shallow checkout, no
    `origin` configured) must skip the check, not crash or false-positive.
    """
    sql_files = sorted((collision_repo / _REL).glob("*.sql"))
    resolved, cross = lint.check_cross_branch(
        sql_files, cwd=collision_repo, target="origin/main"
    )
    assert resolved is None
    assert cross == {}


def test_innocence_integration_ordinary_pr_no_overlap(lint, tmp_path: Path):
    """INNOCENCE: the common case — a short-lived branch that already has
    main's own migrations plus new ones ahead of the tip — must stay clean.
    """
    repo = tmp_path / "repo2"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _write(repo, _REL, "280_base.sql")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    _write(repo, _REL, "281_something_new.sql")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feature: add unrelated 281")

    sql_files = sorted((repo / _REL).glob("*.sql"))
    resolved, cross = lint.check_cross_branch(sql_files, cwd=repo, target="main")
    assert resolved == "main"
    assert cross == {}


def test_target_ref_priority_env_override_wins(lint):
    assert lint._target_ref({"MIGRATION_LINT_MERGE_TARGET": "origin/custom"}) == "origin/custom"


def test_target_ref_priority_github_base_ref_used_in_ci(lint):
    assert lint._target_ref({"GITHUB_BASE_REF": "feature/due-bot"}) == "origin/feature/due-bot"


def test_target_ref_default_is_origin_main(lint):
    assert lint._target_ref({}) == "origin/main"


def test_main_prints_notice_not_failure_when_target_unresolvable(
    lint, tmp_path, monkeypatch, capsys
):
    """main() must exit 0 (not crash, not fail) when the cross-branch check
    can't resolve a target — same-tree clean + unresolvable target is still
    a clean run."""
    _mk(tmp_path, "194_a.sql", "195_b.sql")
    monkeypatch.setattr(lint, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(lint, "check_cross_branch", lambda *a, **k: (None, {}))
    rc = lint.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert "cross-branch check skipped" in captured.out


def test_main_exits_1_on_synthetic_cross_branch_collision(lint, tmp_path, monkeypatch, capsys):
    """main() must fail on a cross-branch collision even when the SAME-TREE
    check (find_duplicates) is perfectly clean — this is the exact scenario
    that shipped green before this check existed."""
    _mk(tmp_path, "291_team_bot_ingress_leader.sql")
    monkeypatch.setattr(lint, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(
        lint,
        "check_cross_branch",
        lambda *a, **k: (
            "origin/main",
            {291: ("291_team_bot_ingress_leader.sql", "291_something_else.sql")},
        ),
    )
    rc = lint.main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "cross-branch collision" in captured.out + captured.err
