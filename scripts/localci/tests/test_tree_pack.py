"""B14: the sandbox indexes the candidate tree from a pack the host built once, instead of hashing and packing it per container.

Real git in tmp dirs: the pack path must leave exactly the repo the old path leaves (same trees, same index, clean status, nothing
loose), and a pack that does not verify must raise, never fall back. The runner side: who gets the pack, how it is tarred, what a
failed build costs, and that it is gone when the run ends."""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tracemalloc
from pathlib import Path

import pytest

from scripts.localci import steps_driver

from . import fixture_repo as fr

runner = fr.runner
CAND_ONLY = "ignored.log"


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    runner._TREE_PACK_FAILED.clear()
    yield
    runner._TREE_PACK_FAILED.clear()


@pytest.fixture
def repo(tmp_path):
    """BASE, then a candidate that adds, changes and deletes a file; carries an executable, a symlink, a nested dir and a tracked file a
    .gitignore ignores."""
    r = tmp_path / "wt"
    r.mkdir()
    fr.git(r, "init", "-q", "-b", "main")
    fr.write(r, {"a.txt": "a\n", "docs/gone.md": "gone\n", "docs/changed.md": "old\n", "run.sh": "#!/bin/sh\necho hi\n",
                 "sub/dir/deep/n.txt": "n\n", ".gitignore": f"{CAND_ONLY}\n"})
    (r / "run.sh").chmod(0o755)
    os.symlink("a.txt", r / "link")
    fr.git(r, "add", "-A")
    fr.git(r, "commit", "-q", "-m", "base")
    base = fr.git(r, "rev-parse", "HEAD")
    fr.git(r, "rm", "-q", "docs/gone.md")
    fr.write(r, {"docs/changed.md": "new\n", "docs/added.md": "added\n", CAND_ONLY: "tracked though ignored\n"})
    fr.git(r, "add", "-A")
    fr.git(r, "add", "-f", CAND_ONLY)
    fr.git(r, "commit", "-q", "-m", "candidate")
    return {"repo": r, "base": base, "cand": fr.git(r, "rev-parse", "HEAD"), "tmp": tmp_path}


def sandbox_w(fx: dict, name: str, history: bool) -> tuple[Path, Path, dict | None]:
    """/w and /cfg as the sandbox is handed them: the runner's own tar, extracted; plus an artifact file and an override."""
    root = fx["tmp"] / name
    buf = io.BytesIO()
    extra = {"w/artifacts/dl/report.txt": b"downloaded\n"}
    runner.stream_tree_tar(fx["repo"], fx["cand"], buf, {"docs/changed.md": b"overridden by a BASE blob\n"}, extra)
    buf.seek(0)
    with tarfile.open(fileobj=buf) as t:
        t.extractall(root)
    hist = runner.history_delta(fx["repo"], fx["base"], fx["cand"]) if history else None
    cfg = root / "cfg"
    cfg.mkdir(exist_ok=True)
    for (rel, _m, _o), blob in zip(hist["base"] if hist else [], runner.read_blobs(fx["repo"], [o for _, _, o in hist["base"]]) if hist else []):
        (cfg / "base" / rel).parent.mkdir(parents=True, exist_ok=True)
        (cfg / "base" / rel).write_bytes(blob)
    return root / "w", cfg, hist


def observe(w: Path, history: bool) -> dict:
    def g(*a: str) -> str:
        return fr.git(w, *a)
    obs = {"tree": g("rev-parse", "HEAD^{tree}"), "index": g("ls-files", "-s"), "status": g("status", "--porcelain"),
           "loose": [ln for ln in g("count-objects", "-v").splitlines() if ln.startswith("count:")],
           "fsck": subprocess.run(["git", "fsck", "--connectivity-only"], cwd=w, capture_output=True).returncode}
    if history:
        obs.update(main=g("rev-parse", "main^{tree}"), origin=g("rev-parse", "origin/main^{tree}"), diff=g("diff", "--name-status", "main", "HEAD"))
    return obs


def index_both_ways(fx: dict, history: bool) -> tuple[dict, dict, Path]:
    w0, cfg0, hist = sandbox_w(fx, "plain", history)
    steps_driver.index_tree(str(w0), hist, cfg0 / "base")
    w1, cfg1, hist = sandbox_w(fx, "packed", history)
    meta = runner.build_tree_pack(fx["repo"], fx["cand"], fx["tmp"] / "tree.pack", 60)
    shutil.copy(fx["tmp"] / "tree.pack", cfg1 / "tree.pack")
    steps_driver.index_tree(str(w1), hist, cfg1 / "base", {"path": str(cfg1 / "tree.pack"), "tree": meta["tree"]})
    assert not (cfg1 / "tree.pack").exists()   # indexed, so the container frees the copy
    return observe(w0, history), observe(w1, history), w1


@pytest.mark.parametrize("history", [False, True])
def test_the_packed_index_is_the_same_repo_the_old_path_makes(repo, history):
    plain, packed, w1 = index_both_ways(repo, history)
    assert packed == plain
    assert plain["status"] == "" and plain["loose"] == ["count: 0"] and plain["fsck"] == 0
    assert plain["tree"] != fr.git(repo["repo"], "rev-parse", f"{repo['cand']}^{{tree}}")   # the artifact and the override are in /w: the tree is /w's
    assert "docs/changed.md" in plain["index"] and CAND_ONLY in plain["index"] and "120000" in plain["index"] and "100755" in plain["index"]
    if history:
        assert plain["diff"].split() and "docs/added.md" in plain["diff"] and "docs/gone.md" in plain["diff"]


def test_without_artifacts_or_overrides_the_packed_tree_is_the_candidates_tree(repo):
    w, cfg, _ = sandbox_w(repo, "clean", False)
    shutil.rmtree(w / "artifacts")
    (w / "docs" / "changed.md").write_text("new\n")
    meta = runner.build_tree_pack(repo["repo"], repo["cand"], repo["tmp"] / "t.pack", 60)
    steps_driver.index_tree(str(w), None, cfg / "base", {"path": str(repo["tmp"] / "t.pack"), "tree": meta["tree"]})
    assert fr.git(w, "rev-parse", "HEAD^{tree}") == meta["tree"] == fr.git(repo["repo"], "rev-parse", f"{repo['cand']}^{{tree}}")


def test_the_pack_keeps_its_objects_in_one_pack_and_repack_does_not_rewrite_it(repo):
    _plain, _packed, w1 = index_both_ways(repo, False)
    packs = sorted((w1 / ".git" / "objects" / "pack").glob("*.pack"))
    assert len(packs) == 2   # the shipped one, untouched, and one holding only what it lacked (`repack -a -d` would leave one)


def test_a_pack_of_another_tree_raises_the_driver_and_names_the_missing_tree(repo):
    w, cfg, _ = sandbox_w(repo, "wrong", False)
    other = runner.build_tree_pack(repo["repo"], repo["base"], repo["tmp"] / "other.pack", 60)
    want = fr.git(repo["repo"], "rev-parse", f"{repo['cand']}^{{tree}}")
    assert other["tree"] != want
    with pytest.raises(RuntimeError, match="does not carry tree"):
        steps_driver.index_tree(str(w), None, cfg / "base", {"path": str(repo["tmp"] / "other.pack"), "tree": want})


@pytest.mark.parametrize("damage", ["truncated", "flipped"])
def test_a_corrupt_pack_raises_the_driver(repo, damage):
    w, cfg, _ = sandbox_w(repo, "bad", False)
    meta = runner.build_tree_pack(repo["repo"], repo["cand"], repo["tmp"] / "bad.pack", 60)
    raw = (repo["tmp"] / "bad.pack").read_bytes()
    raw = raw[: len(raw) // 2] if damage == "truncated" else raw[:40] + bytes([raw[40] ^ 0xFF]) + raw[41:]
    (repo["tmp"] / "bad.pack").write_bytes(raw)
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        steps_driver.index_tree(str(w), None, cfg / "base", {"path": str(repo["tmp"] / "bad.pack"), "tree": meta["tree"]})


def test_the_driver_process_exits_2_with_no_junit_on_a_corrupt_pack(repo):
    w, cfg, _ = sandbox_w(repo, "proc", False)
    (cfg / "tree.pack").write_bytes(b"PACK-not-a-pack")
    tree = fr.git(repo["repo"], "rev-parse", f"{repo['cand']}^{{tree}}")
    (cfg / "steps.json").write_text(json.dumps({"context": "t", "root": str(w), "git_index": True, "history": None, "env": {},
                                                "tree_pack": {"path": str(cfg / "tree.pack"), "tree": tree},
                                                "steps": [{"name": "s", "argv": ["true"]}]}))
    r = subprocess.run([sys.executable, "-I", str(runner.STEPS_DRIVER), str(cfg / "steps.json"), str(repo["tmp"] / "j.xml")], capture_output=True, text=True,
                       env={**fr.GIT_ENV, "HOME": str(repo["tmp"])})
    assert r.returncode == 2 and not (repo["tmp"] / "j.xml").exists()


def test_without_the_key_the_driver_hashes_the_tree_itself_and_repacks_all(repo):
    w, cfg, hist = sandbox_w(repo, "nokey", True)
    steps_driver.index_tree(str(w), hist, cfg / "base")
    assert observe(w, True)["loose"] == ["count: 0"] and len(list((w / ".git" / "objects" / "pack").glob("*.pack"))) == 1


# ------------------------------------------------------------------------------------------------------------ the runner side
def test_build_tree_pack_reports_tree_objects_bytes_and_sha_and_skips_a_gitlink(repo):
    r = repo["repo"]
    fr.git(r, "update-index", "--add", "--cacheinfo", f"160000,{repo['base']},vendor/sub")
    fr.git(r, "commit", "-q", "-m", "gitlink")
    cand = fr.git(r, "rev-parse", "HEAD")
    dest = repo["tmp"] / "p.pack"
    meta = runner.build_tree_pack(r, cand, dest, 60)
    listing = fr.git(r, "ls-tree", "-r", "-t", "--full-tree", cand).splitlines()
    want = {ln.split()[2] for ln in listing if ln.split()[1] in ("blob", "tree")} | {fr.git(r, "rev-parse", f"{cand}^{{tree}}")}
    assert set(meta) == {"tree", "objects", "bytes", "sha256"} and meta["objects"] == len(want)
    assert meta["bytes"] == dest.stat().st_size and meta["sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest()
    assert not dest.with_name("p.pack.part").exists()


def test_a_failed_build_leaves_no_partial_file(repo):
    dest = repo["tmp"] / "p.pack"
    with pytest.raises(subprocess.CalledProcessError):
        runner.build_tree_pack(repo["repo"], "0" * 40, dest, 60)
    assert not dest.exists() and not dest.with_name("p.pack.part").exists()


def test_a_pack_file_is_tarred_from_disk_with_its_size_uid_and_mode(repo):
    pack = repo["tmp"] / "big.bin"
    pack.write_bytes(os.urandom(3 << 20))
    sink = repo["tmp"] / "sink.tar"
    tracemalloc.start()
    with open(sink, "wb") as fh:
        runner.stream_tree_tar(repo["repo"], repo["cand"], fh, {}, {"cfg/x.json": b"{}"}, files={"cfg/tree.pack": pack})
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    assert peak < 1 << 20   # a 3 MiB pack streamed in chunks: never held whole
    buf = io.BytesIO(sink.read_bytes())
    with tarfile.open(fileobj=buf) as t:
        m = {x.name: x for x in t.getmembers()}
        e = m["cfg/tree.pack"]
        assert e.size == 3 << 20 and e.uid == e.gid == runner.SANDBOX_UID and e.mode == 0o644 and e.isfile()
        assert hashlib.sha256(t.extractfile(e).read()).hexdigest() == hashlib.sha256(open(pack, "rb").read()).hexdigest()
        assert "cfg" in m and "cfg/x.json" in m


@pytest.mark.parametrize("sidecar", ["[1, 2]", '{"commit": "x"}', '{"commit": null, "bytes": 1}', "null"])
def test_b14_a_malformed_sidecar_falls_back_to_rebuilding_never_raises(repo, monkeypatch, sidecar):
    run_dir = repo["tmp"] / "run"
    (run_dir / "state").mkdir(parents=True)
    (run_dir / "state" / "tree.pack").write_bytes(b"x")
    (run_dir / "state" / "tree.pack.json").write_text(sidecar)
    monkeypatch.setattr(runner, "build_tree_pack", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no build")))
    res, seen, log = run_contained(repo, monkeypatch, True, run_dir)
    assert res["status"] == "PASS" and "tree_pack" not in seen["cfg"] and "# tree pack: unavailable" in log


def test_b14_a_sidecar_that_is_a_nonempty_list_gives_the_fallback_pair_from_the_check_itself(repo):
    run_dir = repo["tmp"] / "run"
    (run_dir / "state").mkdir(parents=True)
    (run_dir / "state" / "tree.pack").write_bytes(b"x")
    (run_dir / "state" / "tree.pack.json").write_text("[1]")
    pack, meta, why = runner.tree_pack_for(run_dir, {"candidate_sha": "a" * 40, "worktree": str(repo["repo"] / "missing")})
    assert pack is None and meta is None and why


def contained_spec(fx: dict, git_index: bool) -> dict:
    return {"kind": "contained_steps", "context": "t", "driver_sha256": hashlib.sha256(runner.STEPS_DRIVER.read_bytes()).hexdigest(), "git_index": git_index,
            "history": {"added": [], "base": []}, "path_prefix": "", "venv": False, "env": {}, "steps": [{"name": "s", "argv": ["true"]}],
            "cwd": str(fx["repo"]), "isolation": {"mode": "container", "docker": "/nonexistent/docker", "image_id": "sha256:" + "0" * 64, "user": "65534:65534"}}


def run_contained(fx: dict, monkeypatch, git_index: bool, run_dir: Path, name: str = "ctx.t") -> tuple[dict, dict, str]:
    seen: dict = {}

    def fake(n, spec, rd, plan, inner, overrides, extra, env, log, junit, timeout, workdir="/w", **kw):
        seen.update(cfg=json.loads(extra["cfg/steps.json"]), files=dict(kw.get("files") or {}), kw=kw)
        junit.write_text('<testsuite><testcase name="s" time="0.1"/></testsuite>')
        return 0, None
    monkeypatch.setattr(runner, "execute_contained", fake)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    plan = {"run_id": "r", "worktree": str(fx["repo"]), "candidate_sha": fx["cand"]}
    log = run_dir / "logs" / f"{name}.log"
    res = runner._execute_candidate_contained(name, contained_spec(fx, git_index), run_dir, plan, 60, log, run_dir / "receipts" / f"{name}.junit.xml")
    return res, seen, log.read_text()


def test_a_git_index_container_ships_the_pack_and_the_steps_json_names_it_and_a_later_one_reuses_it(repo, monkeypatch):
    run_dir = repo["tmp"] / "run"
    (run_dir / "state").mkdir(parents=True)
    built = []
    real = runner.build_tree_pack
    monkeypatch.setattr(runner, "build_tree_pack", lambda *a, **k: built.append(a) or real(*a, **k))
    tree = fr.git(repo["repo"], "rev-parse", f"{repo['cand']}^{{tree}}")
    for _ in range(2):
        res, seen, log = run_contained(repo, monkeypatch, True, run_dir)
        assert res["status"] == "PASS"
        assert seen["files"] == {"cfg/tree.pack": run_dir / "state" / "tree.pack"}
        assert seen["cfg"]["tree_pack"] == {"path": "/cfg/tree.pack", "tree": tree} and "tree pack: unavailable" not in log
    assert len(built) == 1


def test_a_container_without_git_index_gets_no_pack_and_builds_none(repo, monkeypatch):
    run_dir = repo["tmp"] / "run"
    (run_dir / "state").mkdir(parents=True)
    res, seen, log = run_contained(repo, monkeypatch, False, run_dir)
    assert res["status"] == "PASS" and seen["files"] == {} and "tree_pack" not in seen["cfg"]
    assert not (run_dir / "state" / "tree.pack").exists() and "tree pack" not in log


def test_a_failed_build_ships_nothing_says_so_in_the_log_and_the_run_still_decides(repo, monkeypatch):
    run_dir = repo["tmp"] / "run"
    (run_dir / "state").mkdir(parents=True)
    calls = []

    def boom(*a, **k):
        calls.append(1)
        Path(a[2]).write_bytes(b"partial")
        raise RuntimeError("pack-objects died")
    monkeypatch.setattr(runner, "build_tree_pack", boom)
    for n in range(2):
        res, seen, log = run_contained(repo, monkeypatch, True, run_dir, name=f"ctx.t{n}")
        assert res["status"] == "PASS" and seen["files"] == {} and "tree_pack" not in seen["cfg"]
        assert "# tree pack: unavailable (RuntimeError: pack-objects died) — the sandbox indexes the tree itself\n" in log
    assert len(calls) == 1 and not (run_dir / "state" / "tree.pack").exists()   # a failure is remembered for the run: no 300 s retry per container


def test_a_leg_ships_the_pack_and_an_egress_step_never_gets_it(repo, monkeypatch):
    run_dir = repo["tmp"] / "run"
    (run_dir / "state").mkdir(parents=True)
    (run_dir / "logs").mkdir()
    (run_dir / "receipts").mkdir()
    monkeypatch.setenv("LOCALCI_MIN_FREE_GB", "0")
    monkeypatch.setattr(runner, "start_services", lambda *a, **k: ([], None, None))
    seen = []

    def fake(n, spec, rd, plan, inner, overrides, extra, env, log, junit, timeout, workdir="/w", **kw):
        seen.append((n, json.loads(extra["cfg/steps.json"]), dict(kw.get("files") or {})))
        junit.write_text('<testsuite><testcase name="s" time="0.1"/><testcase name="audit" time="0.1"/></testsuite>')
        return 0, None
    monkeypatch.setattr(runner, "execute_contained", fake)
    X = runner._gh_expr()
    spec = {"isolation": contained_spec(repo, True)["isolation"], "expr": {}, "context": "t", "history": {"added": [], "base": []}, "memory": "4g",
            "driver_sha256": hashlib.sha256(runner.STEPS_DRIVER.read_bytes()).hexdigest(), "expr_sha256": hashlib.sha256(runner.GH_EXPR.read_bytes()).hexdigest()}
    job = {"job_id": "j", "needs": [], "path_prefix": "", "venv": False, "job_env": {}, "services": [], "image_id": "sha256:" + "1" * 64, "timeout_s": 60,
           "checkout": None, "steps": [{"name": "s", "argv": ["true"]},
                                       {"name": "audit", "argv": ["true"], "side": {"where": "egress", "inputs": ["a.txt"], "rewrite": []}}]}
    plan = {"run_id": "r", "worktree": str(repo["repo"]), "candidate_sha": repo["cand"]}
    out = runner._run_leg("ctx.t", spec, job, {}, run_dir, plan, {}, {}, X)
    legs = [s for s in seen if not s[0].endswith(".egress")]
    egress = [s for s in seen if s[0].endswith(".egress")]
    assert out["infra"] is None and len(legs) == 1 and len(egress) == 1
    assert legs[0][2] == {"cfg/tree.pack": run_dir / "state" / "tree.pack"} and legs[0][1]["tree_pack"]["path"] == "/cfg/tree.pack"
    assert egress[0][2] == {} and "tree_pack" not in egress[0][1]


def test_the_pack_is_gone_when_the_run_ends_whatever_the_verdicts(tmp_path, monkeypatch):
    fx = fr.make_repo(tmp_path)
    fr.plan(fx)
    seen = {}

    def fake_execute(name, spec, run_dir, plan, timeout):
        pack, _meta, why = runner.tree_pack_for(run_dir, plan)
        seen["pack"], seen["why"], seen["exists_during"] = pack, why, pack is not None and pack.exists()
        return {"status": "PASS", "reason": "faked", "rc": 0, "counts": None, "duration_s": 0.0}
    monkeypatch.setattr(runner, "execute", fake_execute)
    monkeypatch.setattr(runner, "env_fingerprint", fr.FakeEnv())
    fr.run(fx)
    assert seen["exists_during"] is True and seen["why"] is None
    state = fx["run"] / "state"
    assert not any(p.name.startswith("tree.pack") for p in state.iterdir())


def test_the_pack_is_gone_when_a_check_crashes_the_run(tmp_path, monkeypatch):
    fx = fr.make_repo(tmp_path)
    fr.plan(fx)

    def crash(name, spec, run_dir, plan, timeout):
        runner.tree_pack_for(run_dir, plan)
        raise KeyboardInterrupt("signal 15")
    monkeypatch.setattr(runner, "execute", crash)
    monkeypatch.setattr(runner, "env_fingerprint", fr.FakeEnv())
    with pytest.raises(KeyboardInterrupt):
        fr.run(fx)
    assert not any(p.name.startswith("tree.pack") for p in (fx["run"] / "state").iterdir())


def test_b14_a_leg_whose_pack_machinery_raises_runs_on_the_fallback_path(repo, monkeypatch):
    run_dir = repo["tmp"] / "run"
    for d in ("state", "logs", "receipts"):
        (run_dir / d).mkdir(parents=True)
    monkeypatch.setenv("LOCALCI_MIN_FREE_GB", "0")
    monkeypatch.setattr(runner, "start_services", lambda *a, **k: ([], None, None))
    monkeypatch.setattr(runner, "tree_pack_ship", lambda *a, **k: (_ for _ in ()).throw(AttributeError("boom")))
    seen = []

    def fake(n, spec, rd, plan, inner, overrides, extra, env, log, junit, timeout, workdir="/w", **kw):
        seen.append((json.loads(extra["cfg/steps.json"]), dict(kw.get("files") or {})))
        junit.write_text('<testsuite><testcase name="s" time="0.1"/></testsuite>')
        return 0, None
    monkeypatch.setattr(runner, "execute_contained", fake)
    spec = {"isolation": contained_spec(repo, True)["isolation"], "expr": {}, "context": "t", "history": {"added": [], "base": []}, "memory": "4g",
            "driver_sha256": hashlib.sha256(runner.STEPS_DRIVER.read_bytes()).hexdigest(), "expr_sha256": hashlib.sha256(runner.GH_EXPR.read_bytes()).hexdigest()}
    job = {"job_id": "j", "needs": [], "path_prefix": "", "venv": False, "job_env": {}, "services": [], "image_id": "sha256:" + "1" * 64, "timeout_s": 60,
           "checkout": None, "steps": [{"name": "s", "argv": ["true"]}]}
    plan = {"run_id": "r", "worktree": str(repo["repo"]), "candidate_sha": repo["cand"]}
    out = runner._run_leg("ctx.t", spec, job, {}, run_dir, plan, {}, {}, runner._gh_expr())
    assert out["infra"] is None and len(seen) == 1 and seen[0][1] == {} and "tree_pack" not in seen[0][0]
