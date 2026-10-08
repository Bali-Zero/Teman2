"""Tests for scripts/visa_reattestation_organ.py.

Real git against a temp bare "origin" and a temp shared clone; everything that is not git
(portal read, judge, fold, gh, Telegram) goes through the runner's single `_run` chokepoint
and is scripted here. Guilt and innocence for each rule the organ exists to keep.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import visa_reattestation_organ as organ  # noqa: E402

BOUNDARY = datetime(2026, 11, 8, 13, 32, 18, tzinfo=timezone.utc)
VERIFIED = BOUNDARY - timedelta(seconds=2_764_800)
SIGNED = f"{organ.PACKS_REL}/rulepack-prod-025.signed.json"
SOURCE = f"{organ.PACKS_REL}/rulepack-prod-025.source.json"


def _payload() -> dict:
    return {"sequence": 25, "environment": "PRODUCTION", "source_records": [
        {"authority_type": "OFFICIAL_PORTAL", "source_record_id": "a" * 36,
         "verified_at": VERIFIED.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "freshness_policy": {"kind": "MAX_AGE_SINCE_VERIFIED_AT", "max_age_seconds": 2_764_800}},
        {"authority_type": "STATUTE", "source_record_id": "b" * 36, "verified_at": "2020-01-01T00:00:00Z"},
    ]}


def _git(cwd: Path, *a: str) -> str:
    out = subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                         capture_output=True, text=True, check=True)
    return out.stdout


@pytest.fixture()
def world(tmp_path: Path, monkeypatch):
    origin, shared = tmp_path / "origin.git", tmp_path / "shared"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(origin), str(shared)], check=True, capture_output=True)
    (shared / organ.PACKS_REL).mkdir(parents=True)
    (shared / SIGNED).write_text(json.dumps({"payload": _payload()}))
    (shared / SOURCE).write_text(json.dumps(_payload()))
    _git(shared, "add", "-A")
    _git(shared, "commit", "-m", "seed")
    _git(shared, "push", "origin", "HEAD:refs/heads/main")
    _git(shared, "fetch", "origin")
    code = tmp_path / "code"
    (code / organ.VISA_SCRIPTS_REL).mkdir(parents=True)
    (code / organ.VISA_SCRIPTS_REL / "portal_judge.py").write_text("# stub")
    tg_script = tmp_path / "tg_notify.py"
    tg_script.write_text("# stub")
    monkeypatch.setattr(organ, "TG_NOTIFY", tg_script)
    calls: list[list[str]] = []
    cwds: dict[str, Path | None] = {}
    cfg = {"judge_rc": 0, "fold_rc": 0, "open_prs": [], "gh_create_rc": 0}
    real = subprocess.run

    def fake_run(cmd, *, cwd=None, env=None, timeout=1800):
        calls.append(list(cmd))
        cwds[" ".join(cmd[:3])] = cwd
        if cmd[0] == "git":
            return real(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
        text = " ".join(cmd)
        done = lambda rc=0, out="", err="": subprocess.CompletedProcess(cmd, rc, out, err)  # noqa: E731
        if cmd[0] == "gh" and cmd[1:3] == ["pr", "list"]:
            return done(out=json.dumps(cfg["open_prs"]))
        if cmd[0] == "gh" and cmd[1:3] == ["pr", "create"]:
            return done(rc=cfg["gh_create_rc"], out="https://github.com/org/repo/pull/9999\n")
        if "tg_notify.py" in text:
            return done()
        if "portal_read_receipt.py" in text:
            out_dir, reader = Path(cmd[cmd.index("--out-dir") + 1]), cmd[cmd.index("--reader") + 1]
            (out_dir / f"{reader}-receipts.jsonl").write_text("{}\n")
            return done()
        if "portal_judge" in text:
            if cfg["judge_rc"] == 0:
                led, reader = Path(cmd[cmd.index("--ledger-dir") + 1]), cmd[cmd.index("--reader") + 1]
                (led / f"{reader}-judgements.jsonl").write_text("{}\n")
            return done(rc=cfg["judge_rc"], out="1 unsure\n", err="boom")
        if "fold_pack_generic" in text:
            if cfg["fold_rc"] == 0:
                Path(cmd[cmd.index("--output") + 1]).write_text("{}")
            return done(rc=cfg["fold_rc"], out="fold_pack_generic: seq-26 payload_sha256 = " + "ab" * 32 + "\n")
        raise AssertionError(f"unscripted command: {text}")

    monkeypatch.setattr(organ, "_run", fake_run)

    def args(*extra: str):
        return organ.build_parser().parse_args(
            ["--repo", str(shared), "--code-root", str(code), "--state-dir", str(tmp_path / "state"),
             "--board", str(tmp_path / "board.jsonl"), *extra])

    class W:
        pass
    w = W()
    w.__dict__.update(origin=origin, shared=shared, calls=calls, cwds=cwds, cfg=cfg, args=args, tmp=tmp_path)
    w.board = lambda: [json.loads(x) for x in (tmp_path / "board.jsonl").read_text().splitlines()] if (tmp_path / "board.jsonl").exists() else []
    w.tg = lambda: [c for c in calls if "tg_notify.py" in " ".join(c)]
    w.gh_create = lambda: [c for c in calls if c[:3] == ["gh", "pr", "create"]]
    w.now = lambda days_before: (BOUNDARY - timedelta(days=days_before)).isoformat()
    return w


# ------------------------------------------------------------------ shared checkout
def test_refuses_the_shared_checkout(tmp_path):
    shared = tmp_path / "shared"
    (shared / ".git").mkdir(parents=True)
    with pytest.raises(organ.OrganError) as exc:
        organ.assert_not_shared_checkout(shared)
    assert exc.value.stage == "worktree"


def test_accepts_a_linked_worktree(world):
    wt = world.tmp / "wt"
    _git(world.shared, "worktree", "add", "-b", "x", str(wt), "origin/main")
    organ.assert_not_shared_checkout(wt)
    assert not (world.shared / ".git").is_file()


def test_the_run_never_leaves_git_work_in_the_shared_checkout(world):
    assert organ.run(world.args("--now", world.now(20))) == 0
    assert _git(world.shared, "status", "--porcelain").strip() == ""
    assert not (world.tmp / "state" / "worktrees").exists() or not list((world.tmp / "state" / "worktrees").iterdir())


# ------------------------------------------------------------------ judge exit 1
def test_judge_exit_1_alerts_and_opens_no_pr(world):
    world.cfg["judge_rc"] = 1
    assert organ.run(world.args("--now", world.now(20))) == 1
    assert world.gh_create() == []
    assert not any(c[:2] == ["git", "-C"] and "push" in c for c in world.calls)
    rows = world.board()
    assert len(rows) == 1 and rows[0]["priority"] == "HIGH" and "judge" in rows[0]["job"]
    assert len(world.tg()) == 1 and "visa-freshness:reattest-judge:25" in world.tg()[0]
    state = json.loads((world.tmp / "state" / "state.json").read_text())
    assert state["outcome"] == "failed" and state["stage"] == "judge"


def test_a_second_failure_does_not_stack_a_second_board_row(world):
    world.cfg["judge_rc"] = 1
    organ.run(world.args("--now", world.now(20)))
    organ.run(world.args("--now", world.now(19)))
    assert len(world.board()) == 1


def test_missing_judge_module_fails_loudly(world):
    (world.tmp / "code" / organ.VISA_SCRIPTS_REL / "portal_judge.py").unlink()
    assert organ.run(world.args("--now", world.now(20))) == 2
    assert "8069" in world.board()[0]["detail"]


# ------------------------------------------------------------------ fold success -> PR
def test_fold_success_pushes_branch_and_opens_an_unarmed_pr(world):
    assert organ.run(world.args("--now", "2026-10-12T18:00:00Z")) == 0
    branch = "organ/visa-reattest/25-2026-10-12"
    assert branch in _git(world.origin, "branch", "--list").replace("*", "")
    tree = _git(world.origin, "ls-tree", "-r", "--name-only", branch)
    assert "research/visa/2026-10-12-organ-reattest-seq26/rulepack-prod-026.source.json" in tree
    assert f"{organ.PACKS_REL}/rulepack-prod-026.source.json" not in tree
    assert "research/visa/2026-10-12-organ-reattest-seq26/organ-sonnet-20261012-receipts.jsonl" in tree
    note = _git(world.origin, "show", f"{branch}:research/visa/2026-10-12-organ-reattest-seq26-attestation.md")
    assert "adversarial_review: pending-session" in note and "## Adversarial review" in note
    (create,) = world.gh_create()
    title, body = create[create.index("--title") + 1], create[create.index("--body") + 1]
    assert title == ("chore(visa-engine): organ re-attestation ledger 2026-10-12 — candidate seq-26 (unsigned)")
    assert "Bites:" in body and "UNSIGNED" in body and "git mv" in body and "inside the ledger dir" in body and "ab" * 32 in body
    assert "--auto" not in create and not any(c[:3] == ["gh", "pr", "merge"] for c in world.calls)
    assert create[create.index("--head") + 1] == branch
    assert world.board() == []


def test_fold_failure_alerts_and_opens_no_pr(world):
    world.cfg["fold_rc"] = 1
    assert organ.run(world.args("--now", world.now(20))) == 2
    assert world.gh_create() == [] and "fold" in world.board()[0]["job"]


# ------------------------------------------------------------------ T-7 alert
def test_t7_alert_fires_at_6_9_days_and_not_at_7_1(world):
    assert organ.t7_due(BOUNDARY, BOUNDARY - timedelta(days=6.9))
    assert not organ.t7_due(BOUNDARY, BOUNDARY - timedelta(days=7.1))
    organ.run(world.args("--now", world.now(7.1)))
    assert world.tg() == []
    organ.run(world.args("--now", world.now(6.9)))
    (tg,) = world.tg()
    assert "pack-ready" in " ".join(tg) and "ready to sign" in tg[-1] and "2026-11-08T13:32:18" in tg[-1]


def test_t7_alert_repeats_from_an_existing_pr_even_when_this_run_fails(world):
    world.cfg["open_prs"] = [{"number": 7, "headRefName": "organ/visa-reattest/25-2026-10-26", "url": "https://x/pull/7"}]
    world.cfg["judge_rc"] = 1
    _git(world.shared, "branch", "organ/visa-reattest/25-2026-10-26", "origin/main")
    _git(world.shared, "push", "origin", "organ/visa-reattest/25-2026-10-26")
    organ.run(world.args("--now", world.now(6.0)))
    texts = [c[-1] for c in world.tg()]
    assert any("ready to sign: https://x/pull/7" in t for t in texts)
    assert any("FAILED" in t for t in texts)


def test_no_candidate_no_t7_alert(world):
    world.cfg["judge_rc"] = 1
    organ.run(world.args("--now", world.now(3.0)))
    assert not any("ready to sign" in c[-1] for c in world.tg())


# ------------------------------------------------------------------ existing PR
def test_existing_open_pr_gets_a_new_commit_not_a_second_pr(world):
    old = "organ/visa-reattest/25-2026-10-05"
    _git(world.shared, "branch", old, "origin/main")
    _git(world.shared, "push", "origin", old)
    world.cfg["open_prs"] = [{"number": 7, "headRefName": old, "url": "https://x/pull/7"}]
    before = _git(world.origin, "rev-list", "--count", old).strip()
    assert organ.run(world.args("--now", "2026-10-12T18:00:00Z")) == 0
    assert world.gh_create() == []
    assert int(_git(world.origin, "rev-list", "--count", old)) == int(before) + 1
    assert "organ/visa-reattest/25-2026-10-12" not in _git(world.origin, "branch", "--list")
    assert json.loads((world.tmp / "state" / "state.json").read_text())["pr_url"] == "https://x/pull/7"


def test_a_pr_for_another_anchor_does_not_count(world):
    world.cfg["open_prs"] = [{"number": 3, "headRefName": "organ/visa-reattest/24-2026-09-01", "url": "https://x/pull/3"}]
    assert organ.find_open_organ_pr(25, world.shared) is None
    organ.run(world.args("--now", "2026-10-12T18:00:00Z"))
    assert len(world.gh_create()) == 1


# ------------------------------------------------------------------ dry-run
def test_dry_run_writes_nothing_and_prints_the_plan(world, capsys):
    refs = _git(world.shared, "for-each-ref")
    origin_refs = _git(world.origin, "for-each-ref")
    world.cfg["judge_rc"] = 1
    assert organ.run(world.args("--dry-run", "--now", world.now(3.0))) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["next_seq"] == 26 and plan["mode"] == "dry-run" and plan["t7_due"] is True
    assert plan["branch"].startswith("organ/visa-reattest/25-")
    assert _git(world.shared, "for-each-ref") == refs and _git(world.origin, "for-each-ref") == origin_refs
    assert not (world.tmp / "state").exists() and not (world.tmp / "board.jsonl").exists()
    assert world.tg() == [] and world.gh_create() == []
    assert not any("worktree" in c and "add" in c for c in world.calls)
    assert not any(c[0] == "git" and "fetch" in c for c in world.calls)


# ------------------------------------------------------------------ offline rehearsal
def test_offline_skip_judge_uses_the_existing_ledger_and_prints_the_pr_text(world, capsys):
    ledger = world.tmp / "old-ledger"
    ledger.mkdir()
    (ledger / "reader-a-receipts.jsonl").write_text("{}\n")
    (ledger / "reader-a-judgements.jsonl").write_text("{}\n")
    assert organ.run(world.args("--offline", "--skip-judge", "--ledger-dir", str(ledger),
                                "--now", "2026-10-12T18:00:00Z")) == 0
    out, _ = json.JSONDecoder().raw_decode(capsys.readouterr().out)
    assert out["candidate"].endswith("rulepack-prod-026.source.json") and "Bites:" in out["pr_body"]
    assert not any(c[0] == "gh" for c in world.calls) and world.tg() == []
    assert not any("portal_read_receipt" in " ".join(c) or "portal_judge" in " ".join(c) for c in world.calls)


def test_skip_judge_without_judgements_fails(world, tmp_path):
    ledger = tmp_path / "empty"
    ledger.mkdir()
    (ledger / "reader-a-receipts.jsonl").write_text("{}\n")
    assert organ.run(world.args("--offline", "--skip-judge", "--ledger-dir", str(ledger),
                                "--now", world.now(20))) == 2
    assert world.gh_create() == []


def test_boundary_is_the_earliest_portal_record_only():
    p = _payload()
    p["source_records"].append({"authority_type": "OFFICIAL_PORTAL", "verified_at": "2030-01-01T00:00:00Z",
                                "freshness_policy": {"max_age_seconds": 1}})
    assert organ.boundary_of(p) == BOUNDARY
    assert organ.boundary_of({"source_records": []}) is None


def test_reader_names_carry_model_and_date_and_fit_the_slug_rule():
    import re
    now = datetime(2026, 10, 12, tzinfo=timezone.utc)
    assert organ.reader_name("claude", "sonnet", now) == "organ-sonnet-20261012"
    assert organ.reader_name("fake", "sonnet", now) == "fake-organ-20261012"
    assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", organ.reader_name("claude", "claude-sonnet-5", now))


def test_a_resolved_board_row_does_not_mute_the_next_failure(world):
    world.cfg["judge_rc"] = 1
    organ.run(world.args("--now", world.now(20)))
    job = world.board()[0]["job"]
    with (world.tmp / "board.jsonl").open("a") as fh:
        fh.write(json.dumps({"job": job, "status": "resolved", "ts": 1.0}) + "\n")
    organ.run(world.args("--now", world.now(19)))
    assert [r["status"] for r in world.board()] == ["pending", "resolved", "pending"]


def test_gh_runs_inside_a_git_directory_never_the_launchd_cwd(world):
    organ.run(world.args("--now", "2026-10-12T18:00:00Z"))
    assert world.cwds["gh pr list"] == world.shared
    assert world.cwds["gh pr create"] is not None and "worktrees" in str(world.cwds["gh pr create"])


def test_python_falls_back_to_the_shared_checkouts_venv(tmp_path):
    shared, wt = tmp_path / "shared", tmp_path / "wt"
    venv = shared / "apps" / "backend-rag" / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("")
    assert organ._python(wt, shared) == str(venv / "python")
    assert organ._python(wt, None) == sys.executable


def test_a_judge_crash_is_not_read_as_an_unsure_page(world):
    world.cfg["judge_rc"] = 3
    assert organ.run(world.args("--now", world.now(20))) == 2


def test_an_unexpected_exception_still_alerts_and_fails(world, monkeypatch):
    real_fold = organ.fold

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("fold", 1)

    monkeypatch.setattr(organ, "fold", boom)
    assert organ.run(world.args("--now", world.now(20))) == 2
    assert world.board()[0]["job"].startswith("visa-reattestation:unexpected") and len(world.tg()) == 1
    monkeypatch.setattr(organ, "fold", real_fold)


def test_a_dead_board_does_not_silence_telegram(world, monkeypatch):
    def broken(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(organ, "_board", broken)
    world.cfg["judge_rc"] = 1
    organ.run(world.args("--now", world.now(20)))
    assert len(world.tg()) == 1


def test_an_orphaned_worktree_of_a_killed_run_is_reaped_not_a_blocker(world):
    state = world.tmp / "state"
    orphan = state / "worktrees" / "seq26-orphan"
    orphan.parent.mkdir(parents=True)
    _git(world.shared, "worktree", "add", "-B", "organ/visa-reattest/25-2026-10-12", str(orphan), "origin/main")
    assert organ.run(world.args("--now", "2026-10-12T18:00:00Z")) == 0
    assert not orphan.exists()
    assert len(world.gh_create()) == 1


def test_a_failed_run_says_so_in_the_pack_ready_alert(world):
    world.cfg["open_prs"] = [{"number": 7, "headRefName": "organ/visa-reattest/25-2026-10-26", "url": "https://x/pull/7"}]
    world.cfg["judge_rc"] = 1
    _git(world.shared, "branch", "organ/visa-reattest/25-2026-10-26", "origin/main")
    _git(world.shared, "push", "origin", "organ/visa-reattest/25-2026-10-26")
    organ.run(world.args("--now", world.now(6.0)))
    ready = [c[-1] for c in world.tg() if "ready to sign" in c[-1]]
    assert ready and "earlier run; this run failed at 'judge'" in ready[0]


def test_a_merged_unmoved_candidate_counts_for_the_t7_alert(world):
    rel = "research/visa/2026-10-05-organ-reattest-seq26/rulepack-prod-026.source.json"
    (world.shared / rel).parent.mkdir(parents=True)
    (world.shared / rel).write_text("{}")
    _git(world.shared, "add", "-A")
    _git(world.shared, "commit", "-m", "merged organ ledger")
    _git(world.shared, "push", "origin", "HEAD:refs/heads/main")
    _git(world.shared, "fetch", "origin")
    world.cfg["judge_rc"] = 1
    organ.run(world.args("--now", world.now(3.0)))
    assert any(rel in c[-1] for c in world.tg())
