"""Inert release stub: DENY on anything but a fresh, fully-covered PASS; one ALLOW per key; serialized; reconcilable."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from . import fixture_repo as fr
from .fixture_repo import PY, cmd_check, git, release_stub, stub_propose

STUB = Path(release_stub.__file__)


def journal(fx):
    return [json.loads(x) for x in (fx["run"] / "state" / "release_journal.jsonl").read_text().splitlines()]


@pytest.fixture
def g(fx, tmp_path, fake_env):
    fr.green(fx, tmp_path)
    assert fr.status(fx)["overall"] == "PASS"
    return fx


def test_allow_proposed_once_then_duplicate_is_denied(g):
    a = stub_propose(g, "r1")
    assert a["verdict"] == "ALLOW_PROPOSED" and a["reasons"] == [] and a["proposed_action"]["executed"] is False
    assert a["idempotency_key"] == f"{g['candidate']}:{g['tree']}:none" and {"hostname", "pid", "token"} <= set(a["owner"])
    b = stub_propose(g, "r2")
    assert b["verdict"] == "DENY" and any("duplicate" in r for r in b["reasons"])


def test_a_different_artifact_digest_is_a_different_key(g):
    assert stub_propose(g, "r1", "sha256:aaa")["verdict"] == "ALLOW_PROPOSED"
    assert stub_propose(g, "r2", "sha256:bbb")["verdict"] == "ALLOW_PROPOSED"
    assert stub_propose(g, "r3", "sha256:aaa")["verdict"] == "DENY"


def test_requesting_another_candidate_is_denied(g):
    rec = release_stub.propose(g["run"], "r1", g["base"])
    assert rec["verdict"] == "DENY" and any("!= bound candidate" in r for r in rec["reasons"])


def deny(fx, why):
    rec = stub_propose(fx, "rq")
    assert rec["verdict"] == "DENY", rec
    assert any(why in r for r in rec["reasons"]), rec["reasons"]
    assert rec["proposed_action"]["executed"] is False
    return rec


def test_deny_on_fail(fx, tmp_path, fake_env):
    fr.green(fx, tmp_path, "--extra-check", cmd_check("c.fail", fx["repo"], [PY, "-c", "raise SystemExit(1)"]))
    assert deny(fx, "overall=FAIL")["verdict"] == "DENY"
def test_deny_on_error(fx, tmp_path, fake_env):
    fr.green(fx, tmp_path, "--extra-check", cmd_check("c.gone", fx["repo"], ["/nonexistent/tool"]))
    rec = deny(fx, "overall=BLOCKED")
    assert "ERROR" in json.dumps(rec["reasons"])


def test_deny_on_blocked_context(fx, tmp_path, fake_env):
    fr.green(fx, tmp_path, contexts=[{"name": "policy.change_map", "local": {"kind": "rule"}, "mapping": "executed"}, {"name": "e2e", "local": {"kind": "cmd"}, "mapping": "not_implemented"}])
    assert deny(fx, "overall=BLOCKED")["verdict"] == "DENY"
def test_deny_on_stale(g):
    git(g["repo"], "commit", "-q", "--allow-empty", "-m", "moved")
    rec = deny(g, "stale")
    assert any("STALE" in r for r in rec["reasons"])


def test_deny_on_interrupted(g):
    fr.make_running(g, "tests.scripts_impacted")
    rec = deny(g, "overall=BLOCKED")
    assert "INTERRUPTED" in json.dumps(rec["reasons"])


def test_deny_on_subset_pass(fx, tmp_path, fake_env):
    fr.green(fx, tmp_path, with_contexts=False)
    assert fr.status(fx)["overall"] == "SUBSET_PASS"
    assert deny(fx, "overall=SUBSET_PASS")["verdict"] == "DENY"
def test_deny_on_missing_review(fx, tmp_path, fake_env):
    fr.green(fx, tmp_path, with_review=False)
    rec = deny(fx, "independent review not PASS")
    assert rec["overall"] == "BLOCKED"


def test_deny_on_review_by_the_builder(fx, tmp_path, fake_env):
    fr.green(fx, tmp_path, with_review=False)
    fr.import_review(fx, tmp_path, reviewer_seat="builder-a")
    assert deny(fx, "independent review not PASS")["verdict"] == "DENY"
def test_deny_on_env_drift(g, fake_env):
    fake_env.env["deps_lock_sha256"] = "9" * 64
    assert deny(g, "STALE")["verdict"] == "DENY"
def test_release_credentials_in_the_environment_are_refused(g, monkeypatch):
    monkeypatch.setenv("FLY_API_TOKEN", "x")
    with pytest.raises(SystemExit):
        stub_propose(g, "r1")
    assert not (g["run"] / "state" / "release_journal.jsonl").exists()


def test_stub_is_inert_by_construction():
    src = STUB.read_text()
    assert "import subprocess" not in src and "os.system" not in src and "os.exec" not in src and "Popen" not in src


def test_three_competing_threads_yield_exactly_one_allow(g):
    out, barrier = [], threading.Barrier(3)

    def go(i):
        barrier.wait()
        out.append(release_stub.propose(g["run"], f"t{i}", g["candidate"], hold_s=0.2))

    ts = [threading.Thread(target=go, args=(i,)) for i in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(r["verdict"] for r in out) == ["ALLOW_PROPOSED", "DENY", "DENY"]
    assert all("duplicate" in " ".join(r["reasons"]) for r in out if r["verdict"] == "DENY")
    assert len({r["owner"]["token"] for r in out}) == 3 and len(journal(g)) == 3


def test_three_competing_processes_yield_exactly_one_allow(tmp_path):
    fx = fr.make_repo(tmp_path)  # REAL env fingerprint here: the subprocesses cannot see a monkeypatch
    fr.green(fx, tmp_path)
    assert fr.status(fx)["overall"] == "PASS"
    procs = [subprocess.Popen([sys.executable, str(STUB), "propose", "--run-dir", str(fx["run"]), "--request", f"p{i}", "--candidate", fx["candidate"], "--hold-s", "0.3"],
                              stdout=subprocess.PIPE, text=True) for i in range(3)]
    outs = [(p.communicate()[0], p.returncode) for p in procs]
    assert sorted(rc for _, rc in outs) == [0, 2, 2]
    rows = journal(fx)
    assert sorted(r["verdict"] for r in rows) == ["ALLOW_PROPOSED", "DENY", "DENY"]
    assert len({r["owner"]["pid"] for r in rows}) == 3


def test_lock_owner_is_recorded_and_waiters_do_not_wipe_it(g):
    with release_stub.Locked(g["run"]) as lk:
        rec = json.loads((g["run"] / "state" / "release.lock").read_text())
        assert rec == lk.owner and {"hostname", "pid", "token"} == set(rec)


# ------------------------------------------------------------------- reconcile
def test_reconcile_lists_unacked_proposals_and_ack_clears_them(g):
    stub_propose(g, "r1", "sha256:a")
    stub_propose(g, "r2", "sha256:b")
    stub_propose(g, "r3", "sha256:a")  # duplicate -> DENY, never pending
    pend, corrupt = release_stub.pending(g["run"])
    assert sorted(j["request"] for j in pend) == ["r1", "r2"] and corrupt == 0
    release_stub.ack(g["run"], "r1", "observed live")
    assert [j["request"] for j in release_stub.pending(g["run"])[0]] == ["r2"]
    with pytest.raises(SystemExit):
        release_stub.ack(g["run"], "r1")  # already acked
    with pytest.raises(SystemExit):
        release_stub.ack(g["run"], "never-proposed")
    release_stub.ack(g["run"], "r2")
    assert release_stub.pending(g["run"])[0] == []
    assert [j["verdict"] for j in journal(g)].count("ACKED") == 2


def test_reconcile_cli_and_strict_exit(g, capsys):
    stub_propose(g, "r1")
    assert release_stub.main(["reconcile", "--run-dir", str(g["run"]), "--strict"]) == 1
    assert json.loads(capsys.readouterr().out)["unacked"][0]["request"] == "r1"
    assert release_stub.main(["reconcile", "--run-dir", str(g["run"]), "--ack", "r1", "--strict"]) == 0


def test_a_torn_journal_line_is_reported_not_swallowed(g):
    stub_propose(g, "r1")
    with open(g["run"] / "state" / "release_journal.jsonl", "a") as fh:
        fh.write('{"verdict": "ALLOW_PRO')
    assert release_stub.pending(g["run"])[1] == 1
    assert stub_propose(g, "r2")["corrupt_journal_lines"] == 1
