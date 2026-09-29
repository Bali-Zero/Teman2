"""v0.3.0 (2026-09-29): candidate code contained (C1), Pysa home measured (C2), no seal minted over exposed state (C4).

The contained tests need docker and the pinned candidate image; where they are absent they SKIP, and a skip is no
evidence of containment — the live proof is their run on Pro, recorded in the mission evidence directory.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from . import fixture_repo as fr
from .fixture_repo import PY, runner
from scripts.localci import pysa_check as pc

pytestmark = pytest.mark.usefixtures("fake_env")
IMAGE = os.environ.get("LOCALCI_ISOLATION_IMAGE", runner.DEFAULT_ISOLATION_IMAGE)


def _docker_ready() -> bool:
    d = shutil.which("docker")
    return bool(d) and subprocess.run([d, "image", "inspect", IMAGE], capture_output=True).returncode == 0


needs_docker = pytest.mark.skipif(not _docker_ready(), reason=f"docker image {IMAGE} unavailable — containment is proven live on Pro, not here")


def events(fx) -> list[dict]:
    return [json.loads(x) for x in (fx["run"] / "state" / "journal.jsonl").read_text().splitlines()]


# ------------------------------------------------------------------------------- C1: where candidate code runs
def attack_source(host: dict) -> str:
    """Candidate code that knows the exact host paths and tries to read secrets, rewrite run state and poison the Pysa home."""
    return f'''import json, os, socket
from pathlib import Path
HOST = {json.dumps(host)}

def attack():
    seen = {{}}
    try:
        seen["canary"] = Path(HOST["canary"]).read_text()
    except OSError as e:
        seen["canary"] = type(e).__name__
    for key in ("state", "receipt", "pysa"):
        try:
            Path(HOST[key]).parent.mkdir(parents=True, exist_ok=True)
            Path(HOST[key]).write_text("PWNED")
            seen[key] = "written"
        except OSError as e:
            seen[key] = type(e).__name__
    seen["env"] = os.environ.get("LOCALCI_CANARY_VISIBLE", "absent")
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3).close()
        seen["net"] = "open"
    except OSError as e:
        seen["net"] = type(e).__name__
    return seen
'''


def host_targets(tmp_path: Path, fx: dict) -> dict:
    canary = tmp_path / "secrets.env"
    canary.write_text("CANARY-NOT-A-REAL-SECRET\n")
    return {"canary": str(canary), "state": str(fx["run"] / "state" / "state.json"), "receipt": str(fx["run"] / "receipts" / "policy.forged.json"),
            "pysa": str(tmp_path / "pysa-home" / "venv" / "bin" / "pyre")}


def attack_repo(tmp_path: Path) -> tuple[dict, dict]:
    """pytest kind: the candidate's own test attacks. trusted_pytest kind: the BASE test exec_module()s the candidate's guard, which attacks."""
    fx = fr.make_repo(tmp_path / "r")
    host = host_targets(tmp_path, fx)
    fr.write(fx["repo"], {   # observations leave as an assertion message: the only channel a passing-or-not pytest always prints
        "scripts/check_ban_predicates.py": attack_source(host) + "raise AssertionError('OBSERVED ' + json.dumps(attack()))\n",
        "t/test_attack.py": attack_source(host) + "def test_attack():\n    raise AssertionError('OBSERVED ' + json.dumps(attack()))\n",
    })
    fr.git(fx["repo"], "add", "-A")
    fr.git(fx["repo"], "commit", "-q", "-m", "attacking candidate")
    base_test = ("import importlib.util\nfrom pathlib import Path\nREPO_ROOT = Path(__file__).resolve().parents[2]\n"
                 "def test_guard_imports():\n    s = importlib.util.spec_from_file_location('g', REPO_ROOT / 'scripts' / 'check_ban_predicates.py')\n"
                 "    m = importlib.util.module_from_spec(s)\n    s.loader.exec_module(m)\n")
    fr.git(fx["repo"], "checkout", "-q", fx["base"])
    fr.write(fx["repo"], {"scripts/tests/test_ban_predicates.py": base_test})
    fr.git(fx["repo"], "add", "-A")
    fr.git(fx["repo"], "commit", "-q", "-m", "base with an exec_module ban test")
    fx["base"] = fr.git(fx["repo"], "rev-parse", "HEAD")
    fr.git(fx["repo"], "checkout", "-q", "main")
    fr.git(fx["repo"], "rebase", "-q", fx["base"])
    fx["candidate"] = fr.git(fx["repo"], "rev-parse", "HEAD")
    return fx, host


def observed(fx: dict, name: str) -> dict:
    lines = [x for x in Path(fr.load_state(fx)["checks"][name]["log"]).read_text().splitlines() if x.startswith("E ") and "OBSERVED {" in x]
    return json.loads(lines[-1].split("OBSERVED ", 1)[1]) if lines else {}


def test_uncontained_candidate_code_really_reaches_host_state(tmp_path, monkeypatch):
    """Guilt twin of the containment test: the same attack under --isolation none does reach the host — the attack is real."""
    monkeypatch.setenv("LOCALCI_CANARY_VISIBLE", "leaked")
    fx, host = attack_repo(tmp_path)
    fr.plan(fx, "--isolation", "none", "--extra-check", fr.pytest_check("ctx.attack", fx["repo"], ["t/test_attack.py"]))
    fr.run(fx)
    seen = observed(fx, "ctx.attack")
    assert fr.load_state(fx)["checks"]["ctx.attack"]["status"] == "FAIL"
    assert seen["canary"].startswith("CANARY") and seen["env"] == "leaked" and seen["pysa"] == "written"
    assert Path(host["pysa"]).read_text() == "PWNED"
    assert runner.candidate_exposure(json.loads((fx["run"] / "state" / "plan.json").read_text()), fr.load_state(fx))["mode"] == "none"


@needs_docker
def test_contained_candidate_code_cannot_touch_host_state_in_pytest_or_trusted_pytest(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALCI_CANARY_VISIBLE", "leaked")
    fx, host = attack_repo(tmp_path)
    fr.plan(fx, "--isolation", "container", "--isolation-image", IMAGE, "--extra-check", fr.pytest_check("ctx.attack", fx["repo"], ["t/test_attack.py"]))
    plan = json.loads((fx["run"] / "state" / "plan.json").read_text())
    assert plan["isolation"]["mode"] == "container" and plan["isolation"]["image_id"].startswith("sha256:")
    fr.run(fx)
    st = fr.load_state(fx)
    for name in ("ctx.attack", "policy.paid_anthropic_ban"):
        c = st["checks"][name]
        assert c["status"] == "FAIL", (name, c["reason"], Path(c["log"]).read_text()[-2000:])   # the attack ran and reported what it saw
        seen = observed(fx, name)
        assert seen["canary"] == "FileNotFoundError", (name, seen)       # the host file does not exist in the container
        assert seen["env"] == "absent" and seen["net"] != "open", (name, seen)
        assert "PWNED" not in (fx["run"] / "state" / "state.json").read_text()
    assert "PWNED" not in (fx["run"] / "state" / "state.json").read_text()
    assert not Path(host["receipt"]).exists() and not Path(host["pysa"]).exists()
    assert Path(host["canary"]).read_text().startswith("CANARY")
    assert runner.candidate_exposure(plan, st)["mode"] == "container"
    ps = subprocess.run(["docker", "ps", "-a", "--filter", "label=org.nuzantara.localci=candidate", "--format", "{{.Names}}"], capture_output=True, text=True).stdout
    assert plan["run_id"] not in ps   # every candidate container is removed


@needs_docker
def test_contained_timeout_kills_the_container_and_is_error(tmp_path):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "t/test_hang.py": "import time\ndef test_h():\n    time.sleep(600)\n"})
    fr.plan(fx, "--isolation", "container", "--isolation-image", IMAGE, "--extra-check", fr.pytest_check("ctx.hang", fx["repo"], ["t/test_hang.py"]))
    fr.run(fx, "--only", "ctx.hang", "--timeout", "15")
    c = fr.load_state(fx)["checks"]["ctx.hang"]
    assert c["status"] == "ERROR" and "timeout" in c["reason"]


def test_container_isolation_unavailable_blocks_instead_of_running_uncontained(fx):
    fr.plan(fx, "--isolation", "container", "--isolation-image", "localci-no-such-image:0", "--extra-check", fr.pytest_check("ctx.t", fx["repo"], ["scripts/tests/test_sample.py"]))
    ch = fr.load_state(fx)["checks"]
    for name in ("policy.paid_anthropic_ban", "ctx.t"):
        assert ch[name]["status"] == "BLOCKED" and "isolation=container unavailable" in ch[name]["reason"]
    fr.run(fx)
    assert not (fx["run"] / "logs" / "ctx.t.log").exists()


def test_a_legacy_plan_carries_no_isolation_claim():
    assert runner.isolation_of({})["mode"] == "none"
    plan = {"checks": {"t": {"kind": "pytest"}}}
    assert runner.candidate_exposure(plan, {"checks": {"t": {"attempts": 1}}})["mode"] == "none"
    forged = {"checks": {"t": {"kind": "pytest", "isolation": {"mode": "container"}}}}   # one spec claiming a container is not a container plan
    assert runner.candidate_exposure(forged, {"checks": {"t": {"attempts": 1}}})["mode"] == "none"


def test_the_tree_goes_in_from_the_object_store_not_the_checkout(fx):
    (fx["repo"] / ".git" / "info" / "exclude").write_text(".env\n")
    (fx["repo"] / ".env").write_text("NOT-FOR-THE-SANDBOX\n")                        # ignored file in the checkout
    fr.write(fx["repo"], {".gitattributes": "scripts/tests/test_sample.py export-ignore\n"})
    fr.git(fx["repo"], "add", "-A")
    fr.git(fx["repo"], "commit", "-q", "-m", "attrs")
    buf = io.BytesIO()
    runner.stream_tree_tar(fx["repo"], "HEAD", buf, {"scripts/check_ban_predicates.py": b"BASE\n"}, {"cfg/x.ini": b"[pytest]\n"})
    buf.seek(0)
    with tarfile.open(fileobj=buf) as t:
        members = {m.name: m for m in t.getmembers()}
        assert "w/.env" not in members and "w/scripts/tests/test_sample.py" in members   # export-ignore does not hide a file
        assert t.extractfile(members["w/scripts/check_ban_predicates.py"]).read() == b"BASE\n"
        assert "cfg/x.ini" in members and "out" in members
        assert {m.uid for m in members.values()} == {runner.SANDBOX_UID}


# ------------------------------------------------------------------------------- C4: one seal, minted before exposure
def seal_events(fx, kind="seal") -> list[dict]:
    return [e for e in events(fx) if e.get("event") == kind]


def test_a_resumed_uncontained_run_refuses_to_mint_a_seal_over_touched_state(tmp_path, capsys):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "t/test_ok.py": "def test_ok():\n    assert True\n"})
    fr.plan(fx, "--extra-check", fr.pytest_check("ctx.aaa_candidate", fx["repo"], ["t/test_ok.py"]),
            "--extra-check", fr.cmd_check("ctx.zzz_trusted", fx["repo"], [PY, "-c", "raise SystemExit(1)"]))
    fr.run(fx)
    first = fr.load_state(fx)["seal"]
    assert len(seal_events(fx)) == 1 and seal_events(fx, "seal_refused")    # end of run: no second mint after candidate code ran
    st = fr.load_state(fx)
    st["checks"]["ctx.zzz_trusted"].update(status="PASS", reason="rc=0", rc=0)  # what uncontained candidate code could do to state...
    fr.save_state(fx, st)
    fr.make_running(fx, "ctx.aaa_candidate")                                   # ...and then the run is interrupted and resumed
    capsys.readouterr()
    fr.run(fx)
    out = capsys.readouterr().out
    assert "seal REFUSED" in out and "seal=" not in out
    assert len(seal_events(fx)) == 1 and fr.load_state(fx)["seal"] == first
    runner.main(["status", "--run-dir", str(fx["run"]), "--seal", first])
    assert json.loads((fx["run"] / "status.json").read_text())["overall"] == "BLOCKED"     # the recorded seal still exposes the forgery


def test_a_trusted_check_is_not_rerun_after_candidate_exposure(tmp_path, capsys):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "t/test_ok.py": "def test_ok():\n    assert True\n"})
    fr.plan(fx, "--extra-check", fr.pytest_check("ctx.aaa_candidate", fx["repo"], ["t/test_ok.py"]),
            "--extra-check", fr.cmd_check("ctx.zzz_trusted", fx["repo"], [PY, "-c", "pass"]))
    fr.run(fx)
    before = fr.load_state(fx)["checks"]["ctx.zzz_trusted"]
    n_seals = len(seal_events(fx))
    fr.run(fx, "--only", "ctx.zzz_trusted")
    after = fr.load_state(fx)["checks"]["ctx.zzz_trusted"]
    assert after["status"] == before["status"] == "PASS" and after["attempts"] == before["attempts"]
    assert "REFUSED" in capsys.readouterr().out and seal_events(fx, "trusted_rerun_refused")
    fr.run(fx)                                                                  # a repeated run with nothing queued mints nothing either
    assert len(seal_events(fx)) == n_seals


def test_a_candidate_first_only_run_blocks_the_trusted_checks_it_skipped(tmp_path):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "t/test_ok.py": "def test_ok():\n    assert True\n"})
    fr.plan(fx, "--extra-check", fr.pytest_check("ctx.aaa_candidate", fx["repo"], ["t/test_ok.py"]),
            "--extra-check", fr.cmd_check("ctx.zzz_trusted", fx["repo"], [PY, "-c", "pass"]))
    fr.run(fx, "--only", "ctx.aaa_candidate")
    fr.run(fx)
    c = fr.load_state(fx)["checks"]["ctx.zzz_trusted"]
    assert c["status"] == "BLOCKED" and "candidate code already executed" in c["reason"]
    assert fr.status(fx)["checks"]["ctx.zzz_trusted"]["status"] == "BLOCKED"   # never PASS: the run dir cannot vouch for it any more


def test_trusted_only_runs_keep_minting_their_seal(fx, capsys):
    fr.plan(fx, "--extra-check", fr.cmd_check("ctx.zzz_trusted", fx["repo"], [PY, "-c", "pass"]))
    fr.run(fx, "--only", "ctx.zzz_trusted")
    fr.run(fx, "--only", "ctx.zzz_trusted")
    assert len(seal_events(fx)) == 2 and not seal_events(fx, "seal_refused")    # no candidate code ran: re-minting is legitimate
    assert runner.candidate_exposure(json.loads((fx["run"] / "state" / "plan.json").read_text()), fr.load_state(fx)) is None


@needs_docker
def test_a_resumed_contained_run_verifies_the_seal_instead_of_minting_one(tmp_path, capsys):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "t/test_ok.py": "def test_ok():\n    assert True\n"})
    fr.plan(fx, "--isolation", "container", "--isolation-image", IMAGE, "--extra-check", fr.pytest_check("ctx.aaa_candidate", fx["repo"], ["t/test_ok.py"]),
            "--extra-check", fr.cmd_check("ctx.zzz_trusted", fx["repo"], [PY, "-c", "pass"]))
    fr.run(fx)
    first = fr.load_state(fx)["seal"]
    fr.make_running(fx, "ctx.aaa_candidate")
    capsys.readouterr()
    fr.run(fx)
    out = capsys.readouterr().out
    assert f"seal={first}" in out and "UNCHANGED" in out and len(seal_events(fx)) == 1 and seal_events(fx, "seal_verified")
    st = fr.load_state(fx)
    st["checks"]["ctx.zzz_trusted"]["reason"] = "operator edit after exposure"
    fr.save_state(fx, st)
    fr.make_running(fx, "ctx.aaa_candidate")
    capsys.readouterr()
    fr.run(fx)
    assert "seal REFUSED" in capsys.readouterr().out and len(seal_events(fx)) == 1


# ------------------------------------------------------------------------------- C2: the Pysa home is a measured identity
def fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    for rel in ("venv/bin/pyre", "venv/bin/pyrefly", "venv/lib/pyre_check/typeshed/stdlib/os.pyi", "pyre-check/stubs/taint/core_privacy_security/logging.pysa"):
        (home / rel).parent.mkdir(parents=True, exist_ok=True)
        (home / rel).write_text(rel)
    pkg = tmp_path / "backend-site" / "fastapi"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("X = 1\n")
    (home / "site").mkdir()
    os.symlink(pkg, home / "site" / "fastapi")
    return home


@pytest.mark.parametrize("tamper", ["binary", "typeshed", "stub", "site", "new_file", "manifest_only"])
def test_a_tampered_home_is_refused(tmp_path, tamper):
    home = fake_home(tmp_path)
    digest, _ = pc.write_manifest(home)
    assert pc.verify_home(home, digest) == (digest, None)
    target = {"binary": "venv/bin/pyre", "typeshed": "venv/lib/pyre_check/typeshed/stdlib/os.pyi", "stub": "pyre-check/stubs/taint/core_privacy_security/logging.pysa"}
    if tamper in target:
        (home / target[tamper]).write_text("replaced")
    elif tamper == "site":
        (tmp_path / "backend-site" / "fastapi" / "__init__.py").write_text("X = 2\n")      # the linked site package, outside the home
    elif tamper == "new_file":
        (home / "venv" / "bin" / "sitecustomize.py").write_text("")
    else:
        man = json.loads((home / "manifest.json").read_text())
        man["files"]["venv/bin/pyre"] = "0" * 64
        (home / "manifest.json").write_text(json.dumps(man))
    got, why = pc.verify_home(home, digest)
    assert got is None and why


def test_a_home_measured_again_is_still_refused_when_the_plan_pinned_another(tmp_path):
    home = fake_home(tmp_path)
    digest, _ = pc.write_manifest(home)
    (home / "venv" / "bin" / "pyre").write_text("replaced")
    pc.write_manifest(home)                                   # a consistent re-measure of a replaced home
    got, why = pc.verify_home(home, digest)
    assert got is None and "replaced" in why


def test_setup_refuses_to_reuse_an_unmeasured_installation(tmp_path, capsys):
    home = fake_home(tmp_path)                                # an existing pre-C2 home: no manifest
    rc = pc.main(["setup", "--home", str(home), "--backend-venv", str(tmp_path / "nowhere")])
    assert rc == 2 and "refusing to reuse" in capsys.readouterr().out
    assert (home / "venv" / "bin" / "pyre").read_text() == "venv/bin/pyre"   # nothing reinstalled over it, nothing trusted either


def test_judge_refuses_an_unmeasured_home_and_never_trusts_a_cached_baseline(tmp_path, capsys, monkeypatch):
    home = fake_home(tmp_path)
    repo = tmp_path / "wt"
    (repo / "apps" / "backend-rag" / "backend").mkdir(parents=True)
    (repo / "apps" / "backend-rag" / "backend" / "a.py").write_text("X = 1\n")
    fr.git(repo, "init", "-q", "-b", "main")
    fr.git(repo, "add", "-A")
    fr.git(repo, "commit", "-q", "-m", "b")
    argv = ["judge", "--home", str(home), "--worktree", str(repo), "--base", "HEAD", "--candidate", "HEAD", "--out", str(tmp_path / "out")]
    assert pc.main(argv) == 2 and "predates measured setup" in capsys.readouterr().out
    digest, _ = pc.write_manifest(home)
    (home / "baselines").mkdir()
    for name in ("index.json", "planted.json"):      # a forged baseline AND an index vouching for it: same-user writable, never read
        (home / "baselines" / name).write_text(json.dumps({"ok": True, "findings": [{"key": "k", "family": "log_injection"}]}))
    scanned = []

    def fake_scan(home_, wt, ref, out, timeout, log):
        scanned.append(out.name)
        return {"ok": True, "tree": "t", "handlers_modelled": 1, "duration_s": 0.0, "findings": [{"key": "k", "family": "log_injection", "source_callable": "s",
                "sink": "a.py:1", "sink_callable": "f", "sink_statement": "x"}] if out.name == "candidate" else []}
    monkeypatch.setattr(pc, "scan", fake_scan)
    assert pc.main(argv + ["--expect-home-digest", digest]) == 1        # the new flow is judged against a FRESH base scan
    assert scanned == ["base", "candidate"]
    assert json.loads((tmp_path / "out" / "report.json").read_text())["base_cached"] is False


@pytest.mark.parametrize("where", ["venv/lib/python3.12/site-packages/sitecustomize.pyc", "venv/lib/python3.12/site-packages/evil.pth"])
def test_startup_poison_in_the_home_venv_is_measured(tmp_path, where):
    home = fake_home(tmp_path)
    digest, _ = pc.write_manifest(home)
    (home / where).parent.mkdir(parents=True, exist_ok=True)
    (home / where).write_bytes(b"\x00poison")                     # source-less bytecode and .pth files run at interpreter start-up
    got, why = pc.verify_home(home, digest)
    assert got is None and where in why
    cache = home / "venv" / "lib" / "python3.12" / "site-packages" / "__pycache__"
    (home / where).unlink()
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "x.cpython-312.pyc").write_bytes(b"ignored")            # __pycache__ is never consulted under PYTHONPYCACHEPREFIX
    assert pc.verify_home(home, digest) == (digest, None)


def test_erased_exposure_metadata_does_not_buy_an_uncontained_run_a_fresh_seal(tmp_path, capsys):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "t/test_ok.py": "def test_ok():\n    assert True\n"})
    fr.plan(fx, "--extra-check", fr.pytest_check("ctx.aaa_candidate", fx["repo"], ["t/test_ok.py"]),
            "--extra-check", fr.cmd_check("ctx.zzz_trusted", fx["repo"], [PY, "-c", "raise SystemExit(1)"]))
    fr.run(fx)
    n_seals = len(seal_events(fx))
    st = fr.load_state(fx)                                    # what a lingering uncontained process can do to same-user state:
    st.pop("candidate_exposure", None)                        # erase the marker, the attempts, the history and the receipt,
    for name in ("ctx.aaa_candidate", "policy.paid_anthropic_ban", "tests.scripts_impacted"):
        if name in st["checks"]:
            st["checks"][name].update(status="QUEUED", attempts=0, history=[], receipt=None)
    st["checks"]["ctx.zzz_trusted"].update(status="PASS", reason="rc=0", rc=0)   # and forge the trusted verdict
    fr.save_state(fx, st)
    capsys.readouterr()
    fr.run(fx)
    out = capsys.readouterr().out
    assert "seal REFUSED" in out and "seal=" not in out
    assert any("inherited" in json.dumps(e) for e in seal_events(fx, "seal_refused"))   # refused at the boundary, before candidate code
    assert len(seal_events(fx)) == n_seals


def test_two_run_dirs_sharing_a_basename_never_share_a_container_label(tmp_path):
    assert runner.run_label(tmp_path / "a" / "run") != runner.run_label(tmp_path / "b" / "run")


@needs_docker
def test_a_contained_check_runs_in_its_mapped_cwd_and_an_outside_cwd_is_refused(tmp_path):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "t/test_x.py": "def test_x():\n    assert False, 'root copy selected'\n",
                                 "sub/t/test_x.py": "def test_x():\n    assert True\n"})
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    fr.plan(fx, "--isolation", "container", "--isolation-image", IMAGE,
            "--extra-check", "ctx.sub=" + json.dumps({"kind": "pytest", "cwd": str(fx["repo"] / "sub"), "modules": ["t/test_x.py"]}),
            "--extra-check", "ctx.out=" + json.dumps({"kind": "pytest", "cwd": str(outside), "modules": ["t/test_x.py"]}))
    fr.run(fx, "--only", "ctx.sub")
    fr.run(fx, "--only", "ctx.out")
    ch = fr.load_state(fx)["checks"]
    assert ch["ctx.sub"]["status"] == "PASS", ch["ctx.sub"]["reason"]
    assert ch["ctx.out"]["status"] == "ERROR" and "outside the candidate worktree" in ch["ctx.out"]["reason"]
