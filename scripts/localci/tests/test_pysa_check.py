"""pysa_check: model generation, line-shift-proof keys, leaf resolution, runner wiring, and a real guilt/innocence run."""
from __future__ import annotations

import ast
import json
import os
import subprocess
from pathlib import Path

import pytest

from . import fixture_repo as fr
from .fixture_repo import PY, REAL_REPO, git, runner
from scripts.localci import pysa_check as pc

pytestmark = pytest.mark.usefixtures("fake_env")
HOME = Path(os.environ.get("LOCALCI_PYSA_HOME") or runner.DEFAULT_PYSA_HOME)
PYSA_READY = pc.home_ready(HOME) is None

APP = '''import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Request
router = APIRouter()
logger = logging.getLogger(__name__)

def current_user():
    return {"id": 1}

class ChatRequest:
    text: str

@router.get("/guilt/{item}")
async def guilt(item: str):
    logger.info("item %s", item)
    return {"ok": True}

@router.post("/innocent")
async def innocent(request: Request, user: dict = Depends(current_user), who: Annotated[dict, Depends(current_user)] = None):
    logger.info("static message")
    return {"ok": True}

@router.post("/body")
def body(payload: ChatRequest):
    return {"ok": True}

@router.websocket("/ws")
async def ws(websocket):
    pass
'''


def _fn(src: str, name: str):
    return next(n for n in ast.walk(ast.parse(src)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def test_handler_params_keep_user_input_and_drop_injected_or_framework_params():
    assert pc.handler_params(_fn(APP, "guilt")) == ["item"]
    assert pc.handler_params(_fn(APP, "innocent")) == []          # Request, Depends default, Annotated Depends
    assert pc.handler_params(_fn(APP, "body")) == ["payload"]      # a Pydantic-style *Request body is NOT a framework Request


def test_generated_models_cover_every_handler_once(tmp_path):
    app = tmp_path / "apps" / "backend-rag"
    (app / "backend" / "app" / "routers").mkdir(parents=True)
    (app / "backend" / "app" / "routers" / "demo.py").write_text(APP)
    (app / "backend" / "tests").mkdir()
    (app / "backend" / "tests" / "test_x.py").write_text(APP)   # tests are out of scope
    text, n = pc.gen_handler_models(app)
    assert n == 4
    assert "async def backend.app.routers.demo.guilt(item: TaintSource[UserControlled]) -> TaintSink[ReturnedToUser]: ..." in text
    assert "async def backend.app.routers.demo.innocent() -> TaintSink[ReturnedToUser]: ..." in text
    assert "async def backend.app.routers.demo.ws(): ..." in text   # websocket: no ReturnedToUser return
    assert "tests" not in text


def test_statement_key_survives_line_shifts(tmp_path):
    app = tmp_path / "app"
    (app / "backend").mkdir(parents=True)
    body = "import logging\nlogger = logging.getLogger()\n\ndef f(x):\n    logger.info(\n        'x=%s',\n        x,\n    )\n"
    (app / "backend" / "a.py").write_text(body)
    (app / "backend" / "b.py").write_text("# moved\n# down\n\n" + body)
    assert pc.stmt_of(app, "backend/a.py", 6) == ("f", "logger.info( 'x=%s', x, )")
    assert pc.stmt_of(app, "backend/a.py", 6) == pc.stmt_of(app, "backend/b.py", 9)   # same statement, different line
    assert pc.stmt_of(app, "backend/a.py", 5) == pc.stmt_of(app, "backend/a.py", 7)   # any line of the call maps to it


def test_leaves_follow_project_callees_and_stop_at_external_ones():
    models = {
        "backend.a.handler": {"filename": "backend/a.py", "sinks": []},
        "backend.b.helper": {"filename": "backend/b.py", "sinks": [{"port": "formal(v, position=0)", "taint": [{"kinds": [{"kind": "Logging"}], "origin": {"line": 10}}]}]},
        "backend.c.nosink": {"filename": "backend/c.py", "sinks": []},
    }
    lv = pc.Leaves(models)

    def call(tgt, line):
        return {"kinds": [{"kind": "Logging"}], "call": {"position": {"line": line}, "resolves_to": [tgt], "port": "formal(v, position=0)[k]"}}

    assert lv.hop("backend/a.py", call("backend.b.helper", 3), {"Logging"}, 0) == {("backend/b.py", 10, True)}
    assert lv.hop("backend/a.py", call("httpx._client.AsyncClient.post", 4), {"Logging"}, 0) == {("backend/a.py", 4, True)}
    assert lv.hop("backend/a.py", call("backend.c.nosink", 5), {"Logging"}, 0) == {("backend/a.py", 5, False)}
    assert lv.hop("backend/a.py", call("backend.b.helper", 3), {"Logging"}, 0) == {("backend/b.py", 10, True)}  # memoised, still answers


def test_diff_is_keyed_not_positional():
    base = [{"key": "k1"}, {"key": "k2"}]
    cand = [{"key": "k2"}, {"key": "k3"}]
    d = pc.diff_findings(base, cand)
    assert [x["key"] for x in d["new"]] == ["k3"] and [x["key"] for x in d["fixed"]] == ["k1"] and d["unchanged"] == 1


# --------------------------------------------------------------- runner wiring
BACKEND_FILE = {"apps/backend-rag/backend/app/x.py": "VALUE = 1\n"}


def test_pysa_check_is_not_applicable_without_backend_python(fx):
    fr.plan(fx)
    st = fr.load_state(fx)["checks"]["security.pysa_python"]
    assert st["status"] == "NOT_APPLICABLE" and "no non-test python file" in st["reason"]


def test_pysa_check_blocked_when_judge_missing_at_base(tmp_path):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, **BACKEND_FILE})
    fr.plan(fx)
    st = fr.load_state(fx)["checks"]["security.pysa_python"]
    assert st["status"] == "BLOCKED" and "missing at base" in st["reason"]


def _repo_with_trusted_pysa(tmp_path) -> dict:
    fx = fr.make_repo(tmp_path)
    for rel in runner.TRUSTED_PYSA_FILES:
        (fx["repo"] / rel).parent.mkdir(parents=True, exist_ok=True)
        (fx["repo"] / rel).write_bytes((REAL_REPO / rel).read_bytes())
    git(fx["repo"], "add", "-A")
    git(fx["repo"], "commit", "-q", "-m", "base2")
    fx["base"] = git(fx["repo"], "rev-parse", "HEAD")
    fr.write(fx["repo"], BACKEND_FILE)
    (fx["repo"] / "scripts/localci/pysa_check.py").write_text("print('candidate-supplied judge')\n")   # the candidate tampers
    git(fx["repo"], "add", "-A")
    git(fx["repo"], "commit", "-q", "-m", "candidate")
    fx["candidate"] = git(fx["repo"], "rev-parse", "HEAD")
    return fx


def test_pysa_check_blocked_when_home_not_set_up(tmp_path):
    fx = _repo_with_trusted_pysa(tmp_path)
    fr.plan(fx, "--pysa-home", str(tmp_path / "nohome"))
    st = fr.load_state(fx)["checks"]["security.pysa_python"]
    assert st["status"] == "BLOCKED" and "not set up" in st["reason"]


def test_pysa_check_runs_the_base_judge_not_the_candidate_one(tmp_path):
    fx = _repo_with_trusted_pysa(tmp_path)
    home = tmp_path / "home"
    (home / "venv" / "bin").mkdir(parents=True)
    (home / "venv" / "bin" / "pyre").write_text("")
    fr.plan(fx, "--pysa-home", str(home))
    plan = json.loads((fx["run"] / "state" / "plan.json").read_text())
    spec = plan["checks"]["security.pysa_python"]
    assert spec["kind"] == "cmd" and spec["error_rcs"] == [2] and "judge" in spec["cmd"]
    trusted_copy = Path(spec["trusted_pythonpath"]) / "pysa_check.py"
    assert trusted_copy.read_bytes() == (REAL_REPO / "scripts/localci/pysa_check.py").read_bytes()   # BASE blob, not the tampered candidate
    assert (Path(spec["trusted_pythonpath"]) / "pysa" / "taint.config").exists()
    assert fr.load_state(fx)["checks"]["security.pysa_python"]["status"] == "QUEUED"


def test_declared_error_rcs_map_to_error_not_fail(fx):
    fr.plan(fx, "--extra-check", "ctx.tool=" + json.dumps({"kind": "cmd", "cwd": str(fx["repo"]), "cmd": [PY, "-c", "raise SystemExit(2)"], "error_rcs": [2]}),
            "--extra-check", "ctx.fail=" + json.dumps({"kind": "cmd", "cwd": str(fx["repo"]), "cmd": [PY, "-c", "raise SystemExit(2)"]}))
    fr.run(fx)
    ch = fr.load_state(fx)["checks"]
    assert ch["ctx.tool"]["status"] == "ERROR" and "tool error" in ch["ctx.tool"]["reason"]
    assert ch["ctx.fail"]["status"] == "FAIL"


# --------------------------------------------------------------- the real thing (needs a Pysa home)
@pytest.mark.skipif(not PYSA_READY, reason=f"Pysa home not set up at {HOME}")
def test_judge_flags_new_guilt_flows_and_not_innocent_ones(tmp_path):
    repo = tmp_path / "wt"
    pkg = repo / "apps" / "backend-rag" / "backend"
    (pkg / "app" / "routers").mkdir(parents=True)
    for d in (pkg, pkg / "app", pkg / "app" / "routers"):
        (d / "__init__.py").write_text("")
    innocent_only = "\n".join(line for line in APP.splitlines() if "item %s" not in line) + "\n"
    (pkg / "app" / "routers" / "demo.py").write_text(innocent_only)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    (pkg / "app" / "routers" / "demo.py").write_text(APP + '''
@router.get("/trace")
async def trace(x: str):
    try:
        int(x)
    except ValueError as e:
        return {"error": str(e)}
    return {"ok": True}
''')
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "candidate")
    out = tmp_path / "out"
    r = subprocess.run([PY, "-I", str(REAL_REPO / "scripts/localci/pysa_check.py"), "judge", "--home", str(HOME), "--worktree", str(repo), "--base", base, "--candidate", "HEAD", "--out", str(out)],
                       capture_output=True, text=True, timeout=1500)
    assert r.returncode == 1, r.stdout + r.stderr
    report = json.loads((out / "report.json").read_text())
    fams = sorted(x["family"] for x in report["new"])
    assert "log_injection" in fams and "stack_trace_exposure" in fams, report
    assert all("innocent" not in x["source_callable"] for x in report["new"]), report
    assert all(x["source_callable"].endswith(("guilt", "trace")) for x in report["new"]), report
