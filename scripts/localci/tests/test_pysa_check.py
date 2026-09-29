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
from fastapi import APIRouter, Depends, Query, Request, WebSocket
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
async def ws(websocket: WebSocket):
    pass

@router.get("/named-like-the-framework")
async def query_named(request, response="x"):
    logger.info("q %s %s", request, response)
    return {"ok": True}

@router.route("/legacy", methods=["GET"])
async def legacy(user_input: str):
    logger.info("legacy %s", user_input)
    return {"ok": True}

def described(q: Annotated[str, Query(description="Depends(item) Request")], r: Annotated[str, Query(description="x")] = "d"):
    return {"q": q, "r": r}

router.add_api_route("/registered", described, methods=["GET"])

class Response:
    body: str

@router.post("/own-response-class")
def fetch(payload: Response, real: Request):
    return {"ok": True}

get = router.get

@get("/aliased")
def aliased(x: str):
    return {"x": x}

@router.trace("/traced")
def traced(x: str):
    return {"x": x}

def make():
    @router.get("/nested")
    def nested(x: str):
        return {"x": x}
    return nested
'''


def _fn(src: str, name: str):
    return next(n for n in ast.walk(ast.parse(src)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def _params(src: str, name: str) -> list[str]:
    fw_locals, fw_roots = pc.framework_bindings(ast.parse(src))
    return pc.handler_params(_fn(src, name), fw_locals, fw_roots)


def test_handler_params_keep_user_input_and_drop_injected_or_framework_params():
    assert _params(APP, "guilt") == ["item"]
    assert _params(APP, "innocent") == []          # Request, Depends default, Annotated Depends
    assert _params(APP, "body") == ["payload"]      # a Pydantic-style *Request body is NOT a framework Request
    assert _params(APP, "described") == ["q", "r"]  # 'Depends(' / 'Request' inside a description STRING is not an injector or a framework type
    assert _params(APP, "query_named") == ["request", "response"]   # unannotated = query params = user input, whatever they are called
    assert _params(APP, "fetch") == ["payload"]     # the module's OWN class Response is a body; the imported fastapi Request is the framework's
    aliased = "import fastapi as fa\nfrom starlette import responses\ndef h(a: fa.Request, b: responses.Response, c: str): ...\n"
    assert _params(aliased, "h") == ["c"]          # framework types reached through module aliases are still the framework's


def test_generated_models_cover_every_handler_once(tmp_path):
    app = tmp_path / "apps" / "backend-rag"
    (app / "backend" / "app" / "routers").mkdir(parents=True)
    (app / "backend" / "app" / "routers" / "demo.py").write_text(APP)
    (app / "backend" / "tests").mkdir()
    (app / "backend" / "tests" / "test_x.py").write_text(APP)   # tests are out of scope
    text, n = pc.gen_handler_models(app)
    assert n == 11
    assert "def backend.app.routers.demo.fetch(payload: TaintSource[UserControlled]) -> TaintSink[ReturnedToUser]: ..." in text
    assert "def backend.app.routers.demo.aliased(x: TaintSource[UserControlled]) -> TaintSink[ReturnedToUser]: ..." in text   # get = router.get alias
    assert "def backend.app.routers.demo.traced(x: TaintSource[UserControlled]) -> TaintSink[ReturnedToUser]: ..." in text    # @router.trace
    assert "def backend.app.routers.demo.make.nested(x: TaintSource[UserControlled]) -> TaintSink[ReturnedToUser]: ..." in text   # handler built inside a factory
    assert "async def backend.app.routers.demo.query_named(request: TaintSource[UserControlled], response: TaintSource[UserControlled]) -> TaintSink[ReturnedToUser]: ..." in text
    assert "async def backend.app.routers.demo.legacy(user_input: TaintSource[UserControlled]) -> TaintSink[ReturnedToUser]: ..." in text   # @router.route
    assert "def backend.app.routers.demo.described(q: TaintSource[UserControlled], r: TaintSource[UserControlled]) -> TaintSink[ReturnedToUser]: ..." in text   # add_api_route
    assert "async def backend.app.routers.demo.guilt(item: TaintSource[UserControlled]) -> TaintSink[ReturnedToUser]: ..." in text
    assert "async def backend.app.routers.demo.innocent() -> TaintSink[ReturnedToUser]: ..." in text
    assert "async def backend.app.routers.demo.ws(): ..." in text   # websocket: no ReturnedToUser return
    assert "tests" not in text


def test_export_ignores_the_candidates_gitattributes(tmp_path):
    repo = _tree(tmp_path, APP)
    pkg = repo / "apps" / "backend-rag" / "backend" / "app" / "routers"
    (pkg / ".gitattributes").write_text("demo.py export-ignore\n")
    (pkg / "link.py").symlink_to("demo.py")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "hide")
    dest = tmp_path / "export"
    pc.export_tree(repo, "HEAD", dest)
    assert (dest / "apps/backend-rag/backend/app/routers/demo.py").read_text() == APP      # export-ignore did not hide it
    assert (dest / "apps/backend-rag/backend/app/routers/.gitattributes").exists()
    assert not (dest / "apps/backend-rag/backend/app/routers/link.py").exists()             # symlinks are neither followed nor written
    text, n = pc.gen_handler_models(dest / "apps/backend-rag")
    assert n == 11


def test_identical_sink_statements_are_a_multiset_and_methods_are_qualified(tmp_path):
    app = tmp_path / "app"
    (app / "backend").mkdir(parents=True)
    (app / "backend" / "a.py").write_text("import logging\nlog = logging.getLogger()\nclass A:\n    def m(self, x):\n        log.info(x)\nclass B:\n    def m(self, x):\n        log.info(x)\n")
    assert pc.stmt_of(app, "backend/a.py", 5) == ("A.m", "log.info(x)")
    assert pc.stmt_of(app, "backend/a.py", 8) == ("B.m", "log.info(x)")
    issue = {"kind": "issue", "data": {"code": 9001, "callable": "backend.a.h", "filename": "backend/a.py", "line": 5, "traces": []}}
    model = {"kind": "model", "data": {"callable": "backend.a.h", "filename": "backend/a.py", "sinks": []}}
    one, two = tmp_path / "one.json", tmp_path / "two.json"
    one.write_text(json.dumps(model) + "\n" + json.dumps(issue) + "\n")
    two.write_text(json.dumps(model) + "\n" + json.dumps(issue) + "\n" + json.dumps(issue) + "\n")
    f1, _ = pc.extract_findings(one, app)
    f2, _ = pc.extract_findings(two, app)
    assert len(f1) == 1 and len(f2) == 2 and f1[0]["key"] == f2[0]["key"] and f2[1]["key"] != f2[0]["key"]
    assert pc.diff_findings(f1, f2)["new"] == [f2[1]]     # the second identical statement fed by a flow is NEW, not "unchanged"


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


def _tree(tmp_path: Path, source: str) -> Path:
    repo = tmp_path / "wt"
    pkg = repo / "apps" / "backend-rag" / "backend" / "app" / "routers"
    pkg.mkdir(parents=True)
    (pkg / "demo.py").write_text(source)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def test_scan_refuses_an_empty_taint_output(tmp_path, monkeypatch):
    def fake_pysa(home, app_dir, results, timeout, log):
        results.mkdir(parents=True, exist_ok=True)
        (results / "taint-output.json").write_text("")     # rc 0, file present, nothing inside
        return 0
    monkeypatch.setattr(pc, "run_pysa", fake_pysa)
    res = pc.scan(tmp_path / "home", _tree(tmp_path, APP), "HEAD", tmp_path / "out", 10, open(tmp_path / "log", "w"))
    assert res["ok"] is False and "no model record" in res["reason"]
    assert not (tmp_path / "out" / "findings.json").exists()


def test_scan_refuses_a_tree_without_handlers(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "run_pysa", lambda *a, **k: pytest.fail("pysa must not run on an unmodelled tree"))
    res = pc.scan(tmp_path / "home", _tree(tmp_path, "VALUE = 1\n"), "HEAD", tmp_path / "out", 10, open(tmp_path / "log", "w"))
    assert res["ok"] is False and "no FastAPI route handler" in res["reason"]


def test_scope_escape_is_a_finding_not_a_blind_spot(tmp_path):
    app = tmp_path / "app"
    (app / "backend" / "app").mkdir(parents=True)
    (app / "backend" / "tests").mkdir()
    (app / "backend" / "tests" / "leak.py").write_text(APP)
    (app / "backend" / "app" / "main.py").write_text("from backend.tests.leak import router as r\nfrom . import x\n")
    (app / "backend" / "app" / "clean.py").write_text("import backend.app.x\nfrom ..app import x\n")
    (app / "backend" / "app" / "rel.py").write_text("from ..tests.leak import router\n")
    esc = pc.scope_escapes(app)
    assert sorted(e["source_callable"] for e in esc) == ["backend.app.main", "backend.app.rel"]
    assert all(e["family"] == "scope_escape" and e["sink_callable"] == "<import>" for e in esc)
    assert len({e["key"] for e in esc}) == 2


def test_unlisted_pysa_rule_codes_are_kept_as_flows(tmp_path):
    app = tmp_path / "app"
    (app / "backend").mkdir(parents=True)
    (app / "backend" / "a.py").write_text("import os\ndef h(x):\n    os.system(x)\n")
    taint = tmp_path / "taint-output.json"
    taint.write_text("\n".join([
        json.dumps({"kind": "model", "data": {"callable": "backend.a.h", "filename": "backend/a.py", "sinks": []}}),
        json.dumps({"kind": "issue", "data": {"code": 5001, "callable": "backend.a.h", "filename": "backend/a.py", "line": 3, "traces": []}}),
    ]) + "\n")
    findings, n_models = pc.extract_findings(taint, app)
    assert n_models == 1 and [f["family"] for f in findings] == ["pysa_5001"]


def test_unexpected_crash_is_a_tool_error_rc2(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(pc, "cmd_scan", lambda a: (_ for _ in ()).throw(RuntimeError("boom")))
    rc = pc.main(["scan", "--home", str(tmp_path), "--worktree", str(tmp_path), "--out", str(tmp_path / "o")])
    assert rc == 2 and "RuntimeError: boom" in capsys.readouterr().out


def test_scan_accepts_models_with_zero_issues(tmp_path, monkeypatch):
    def fake_pysa(home, app_dir, results, timeout, log):
        results.mkdir(parents=True, exist_ok=True)
        (results / "taint-output.json").write_text(json.dumps({"kind": "model", "data": {"callable": "backend.app.routers.demo.guilt", "filename": "backend/app/routers/demo.py", "sinks": []}}) + "\n")
        return 0
    monkeypatch.setattr(pc, "run_pysa", fake_pysa)
    res = pc.scan(tmp_path / "home", _tree(tmp_path, APP), "HEAD", tmp_path / "out", 10, open(tmp_path / "log", "w"))
    assert res["ok"] is True and res["models"] == 1 and res["findings"] == []   # a genuinely clean, analysed tree stays clean


# --------------------------------------------------------------- runner wiring
BACKEND_FILE = {"apps/backend-rag/backend/app/x.py": "VALUE = 1\n"}


def test_pysa_check_is_not_applicable_without_backend_python(fx):
    fr.plan(fx)
    st = fr.load_state(fx)["checks"]["security.pysa_python"]
    assert st["status"] == "NOT_APPLICABLE" and "no non-test file" in st["reason"]


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
    pc.write_manifest(home)
    fr.plan(fx, "--pysa-home", str(home))
    plan = json.loads((fx["run"] / "state" / "plan.json").read_text())
    spec = plan["checks"]["security.pysa_python"]
    assert spec["kind"] == "cmd" and spec["error_rcs"] == [2] and "judge" in spec["cmd"]
    trusted_copy = Path(spec["trusted_pythonpath"]) / "pysa_check.py"
    assert trusted_copy.read_bytes() == (REAL_REPO / "scripts/localci/pysa_check.py").read_bytes()   # BASE blob, not the tampered candidate
    assert (Path(spec["trusted_pythonpath"]) / "pysa" / "taint.config").exists()
    assert fr.load_state(fx)["checks"]["security.pysa_python"]["status"] == "QUEUED"


@pytest.mark.parametrize("tamper", ["rewrite", "shadow", "delete"])
def test_trusted_pysa_dir_tampering_is_a_tool_error(tmp_path, tamper):
    fx = _repo_with_trusted_pysa(tmp_path)
    home = tmp_path / "home"
    (home / "venv" / "bin").mkdir(parents=True)
    (home / "venv" / "bin" / "pyre").write_text("")
    pc.write_manifest(home)
    fr.plan(fx, "--pysa-home", str(home))
    tdir = Path(json.loads((fx["run"] / "state" / "plan.json").read_text())["checks"]["security.pysa_python"]["trusted_pythonpath"])
    if tamper == "rewrite":
        (tdir / "pysa_check.py").write_text("import sys\nsys.exit(0)\n")     # a forged judge that always passes
    elif tamper == "shadow":
        (tdir / "json.py").write_text("")                                     # a stdlib shadow on the trusted PYTHONPATH
    else:
        (tdir / "pysa" / "taint.config").unlink()
    fr.run(fx, "--only", "security.pysa_python")
    st = fr.load_state(fx)["checks"]["security.pysa_python"]
    assert st["status"] == "ERROR" and "trusted dir tampered" in st["reason"]


def test_any_non_test_file_under_the_scope_plans_the_judge(tmp_path):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "apps/backend-rag/backend/app/routers/.gitattributes": "demo.py export-ignore\n"})
    fr.plan(fx)
    assert fr.load_state(fx)["checks"]["security.pysa_python"]["status"] == "BLOCKED"   # planned (judge missing at base), not NOT_APPLICABLE
    fx2 = fr.make_repo(tmp_path / "b", {**fr.CANDIDATE_FILES, "apps/backend-rag/backend/tests/test_x.py": "VALUE = 1\n"})
    fr.plan(fx2)
    assert fr.load_state(fx2)["checks"]["security.pysa_python"]["status"] == "NOT_APPLICABLE"


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
