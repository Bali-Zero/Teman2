"""Guilt+innocence for scripts/chore_dispatch.py (receptor-live PART B).

Never hits the network or the real Jules API: `_jules_new`/`_jules_status`
are monkeypatched to recorders/fakes, same isolation pattern as
scripts/tests/test_army_jules_lane.py uses for jules_lane.py's own
`run_jules_dispatch`. Every case proves the behaviour FIRES on the
condition it exists to catch (status written / not written, file touched /
untouched), not merely that the caller survives (W107 discipline).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SPEC_PATH = Path(__file__).resolve().parent.parent / "chore_dispatch.py"
spec = importlib.util.spec_from_file_location("chore_dispatch", SPEC_PATH)
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)  # type: ignore[union-attr]


# --------------------------------------------------------------------- utils
def make_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> "cd.Paths":
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    monkeypatch.setenv("CHORE_REPO", str(repo))
    monkeypatch.setenv("CHORE_QUEUE_DIR", str(tmp_path / "chore-queue"))
    monkeypatch.setenv("CHORE_SPARK_QUEUE_DIR", str(tmp_path / "spark-queue"))
    monkeypatch.setenv("CHORE_JULES_DISPATCH_SCRIPT", str(repo / "scripts" / "jules_dispatch.py"))
    paths = cd.Paths()
    paths.queue_dir.mkdir(parents=True, exist_ok=True)
    return paths


def write_chore(paths: "cd.Paths", chore_id: str, *, seat: str = "jules",
                 status: str = "pending", extra: str = "") -> Path:
    f = paths.queue_dir / f"{chore_id}.md"
    f.write_text(
        "---\n"
        f"id: {chore_id}\n"
        "title: Do the thing\n"
        f"seat: {seat}\n"
        "scope: scripts/example.py\n"
        "acceptance: pytest scripts/tests/test_example.py -q\n"
        f"status: {status}\n"
        f"{extra}"
        "---\n\n"
        "Body of the task, anchors and all.\n",
        encoding="utf-8",
    )
    return f


def fake_jules_new(monkeypatch: pytest.MonkeyPatch, *, rc: int = 0,
                    session: str = "sessions/abc123") -> list[tuple]:
    calls: list[tuple] = []

    def _fake(paths, prompt, title, branch=None):
        calls.append((prompt, title, branch))
        if rc != 0:
            return rc, "", "boom"
        return 0, f'{{"name": "{session}", "state": "PENDING"}}', ""

    monkeypatch.setattr(cd, "_jules_new", _fake)
    return calls


def fake_jules_status(monkeypatch: pytest.MonkeyPatch, state: str, rc: int = 0) -> None:
    def _fake(paths, session):
        if rc != 0:
            return rc, "", "boom"
        return 0, f'{{"state": "{state}"}}', ""

    monkeypatch.setattr(cd, "_jules_status", _fake)


# --------------------------------------------------------------------- dry-run
class TestDryRun:
    def test_jules_dry_run_touches_nothing(self, tmp_path, monkeypatch, capsys):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-a", seat="jules")
        calls = fake_jules_new(monkeypatch)

        rc = cd.cmd_dispatch(paths, "chore-a", "jules", dry_run=True)

        assert rc == 0
        assert calls == []  # guilt: the real dispatch call must NEVER fire under --dry-run
        fields, _ = cd.parse_chore(paths.queue_dir / "chore-a.md")
        assert fields["status"] == "pending"  # innocence: file unchanged
        assert "session" not in fields
        assert "[dry-run]" in capsys.readouterr().out

    def test_spark_dry_run_does_not_write_queue_file(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-b", seat="spark")

        rc = cd.cmd_dispatch(paths, "chore-b", "spark", dry_run=True)

        assert rc == 0
        assert not (paths.spark_queue_dir / "chore-b.md").exists()
        fields, _ = cd.parse_chore(paths.queue_dir / "chore-b.md")
        assert fields["status"] == "pending"


# --------------------------------------------------------------------- schema
class TestSchemaValidation:
    def test_missing_required_field_rejected(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        f = paths.queue_dir / "chore-c.md"
        f.write_text("---\nid: chore-c\ntitle: X\nseat: jules\nstatus: pending\n---\n\nbody\n",
                     encoding="utf-8")  # no scope/acceptance

        rc = cd.cmd_dispatch(paths, "chore-c", "jules", dry_run=True)

        assert rc == 2

    def test_bad_seat_value_in_file_rejected(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-d", seat="gpt5")  # not in VALID_SEATS

        rc = cd.cmd_dispatch(paths, "chore-d", "jules", dry_run=True)

        assert rc == 2

    def test_unknown_seat_flag_rejected(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-e")

        rc = cd.cmd_dispatch(paths, "chore-e", "not-a-real-seat", dry_run=True)

        assert rc == 3

    def test_no_such_chore_id(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)

        rc = cd.cmd_dispatch(paths, "ghost", "jules", dry_run=True)

        assert rc == 3

    def test_seat_without_dispatch_code_refuses_cleanly(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-f", seat="haiku")

        rc = cd.cmd_dispatch(paths, "chore-f", "haiku", dry_run=False)

        assert rc == 3
        fields, _ = cd.parse_chore(paths.queue_dir / "chore-f.md")
        assert fields["status"] == "pending"  # never marked dispatched for a no-op


# --------------------------------------------------------------------- status transition
class TestStatusTransition:
    def test_jules_dispatch_writes_status_and_session(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-g", seat="jules")
        calls = fake_jules_new(monkeypatch, session="sessions/real1")

        rc = cd.cmd_dispatch(paths, "chore-g", "jules", dry_run=False)

        assert rc == 0
        assert len(calls) == 1
        fields, body = cd.parse_chore(paths.queue_dir / "chore-g.md")
        assert fields["status"] == "dispatched"
        assert fields["session"] == "sessions/real1"
        assert "dispatched_at" in fields
        assert "Body of the task" in body  # body survives the rewrite untouched

    def test_jules_dispatch_passes_branch_field_through(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-branch", seat="jules", extra="branch: agent/x/y\n")
        calls = fake_jules_new(monkeypatch)

        rc = cd.cmd_dispatch(paths, "chore-branch", "jules", dry_run=False)

        assert rc == 0
        assert calls[0][2] == "agent/x/y"

    def test_jules_dispatch_failure_leaves_status_pending(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-h", seat="jules")
        fake_jules_new(monkeypatch, rc=1)

        rc = cd.cmd_dispatch(paths, "chore-h", "jules", dry_run=False)

        assert rc != 0
        fields, _ = cd.parse_chore(paths.queue_dir / "chore-h.md")
        assert fields["status"] == "pending"
        assert "session" not in fields

    def test_already_dispatched_chore_refuses_redispatch(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-i", seat="jules", status="dispatched",
                    extra="session: sessions/old\n")
        calls = fake_jules_new(monkeypatch)

        rc = cd.cmd_dispatch(paths, "chore-i", "jules", dry_run=False)

        assert rc == 4
        assert calls == []

    def test_spark_dispatch_writes_queue_file_and_status(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-j", seat="spark")

        rc = cd.cmd_dispatch(paths, "chore-j", "spark", dry_run=False)

        assert rc == 0
        target = paths.spark_queue_dir / "chore-j.md"
        assert target.is_file()
        assert "Body of the task" in target.read_text(encoding="utf-8")
        fields, _ = cd.parse_chore(paths.queue_dir / "chore-j.md")
        assert fields["status"] == "queued-spark"

    def test_harvest_marks_completed_on_jules_completed_state(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-k", seat="jules", status="dispatched",
                    extra="session: sessions/xyz\n")
        fake_jules_status(monkeypatch, "COMPLETED")

        rc = cd.cmd_harvest(paths)

        assert rc == 0
        fields, _ = cd.parse_chore(paths.queue_dir / "chore-k.md")
        assert fields["status"] == "completed"

    def test_harvest_marks_failed_on_jules_failed_state(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-l", seat="jules", status="dispatched",
                    extra="session: sessions/xyz2\n")
        fake_jules_status(monkeypatch, "FAILED")

        rc = cd.cmd_harvest(paths)

        assert rc == 0
        fields, _ = cd.parse_chore(paths.queue_dir / "chore-l.md")
        assert fields["status"] == "failed"

    def test_harvest_leaves_in_progress_pending_state_untouched_status(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-m", seat="jules", status="dispatched",
                    extra="session: sessions/xyz3\n")
        fake_jules_status(monkeypatch, "RUNNING")

        cd.cmd_harvest(paths)

        fields, _ = cd.parse_chore(paths.queue_dir / "chore-m.md")
        assert fields["status"] == "in-progress"

    def test_harvest_ignores_spark_chores(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-n", seat="spark", status="queued-spark")

        rc = cd.cmd_harvest(paths)

        assert rc == 0
        fields, _ = cd.parse_chore(paths.queue_dir / "chore-n.md")
        assert fields["status"] == "queued-spark"  # untouched — not jules, not polled

    def test_dispatch_next_picks_oldest_pending_by_glob_order(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-o-z", seat="jules", status="completed")
        write_chore(paths, "chore-o-a", seat="jules", status="pending")
        calls = fake_jules_new(monkeypatch, session="sessions/next1")

        rc = cd.cmd_dispatch_next(paths, dry_run=False)

        assert rc == 0
        assert len(calls) == 1
        fields, _ = cd.parse_chore(paths.queue_dir / "chore-o-a.md")
        assert fields["status"] == "dispatched"

    def test_dispatch_next_empty_queue_is_a_clean_noop(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-p", seat="jules", status="completed")

        rc = cd.cmd_dispatch_next(paths, dry_run=False)

        assert rc == 0


class TestListAndParsing:
    def test_list_on_empty_queue_does_not_crash(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        assert cd.cmd_list(paths) == 0

    def test_parse_chore_roundtrips_through_write_chore(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        write_chore(paths, "chore-q")
        fields, body = cd.parse_chore(paths.queue_dir / "chore-q.md")
        fields["status"] = "dispatched"
        cd.write_chore(paths.queue_dir / "chore-q.md", fields, body)

        fields2, body2 = cd.parse_chore(paths.queue_dir / "chore-q.md")
        assert fields2["status"] == "dispatched"
        assert fields2["id"] == "chore-q"
        assert body2.strip() == body.strip()

    def test_malformed_frontmatter_raises_valueerror(self, tmp_path, monkeypatch):
        paths = make_paths(tmp_path, monkeypatch)
        f = paths.queue_dir / "chore-r.md"
        f.write_text("no frontmatter here at all\n", encoding="utf-8")
        with pytest.raises(ValueError):
            cd.parse_chore(f)
