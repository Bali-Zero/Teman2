"""The two CodeQL Analysis contexts: the pinned bundle image, the plan-time flags and version sentinel, the BASE-trusted commands, and a
verdict that is the commands' exit codes and nothing the findings say. Everything here runs without docker or the CLI: the Dockerfile is
asserted as text, the plan runs against a fake docker, the steps run through the real driver with a fake `codeql` that logs its argv."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from . import fixture_repo as fr
from .fixture_repo import runner

pytestmark = pytest.mark.usefixtures("fake_env")
REAL = fr.REAL_REPO
MATRIX = REAL / "scripts" / "localci" / "contexts_matrix.yaml"
SECURITY, CONFIG = ".github/workflows/security.yml", ".github/codeql-config.yml"
LEG_SH, READER = "scripts/localci/codeql_leg.sh", "scripts/localci/codeql_version_read.py"
LANGS = ("python", "javascript")
PIN = {"version": "2.27.2", "url": "https://github.com/github/codeql-action/releases/download/codeql-bundle-v2.27.2/codeql-bundle-linux-arm64.tar.gz",
       "sha256": "c" * 64}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reader = _load(REAL / READER, "codeql_version_read_under_test")


def matrix_doc() -> dict:
    return yaml.safe_load(MATRIX.read_text())


def matrix_ctx(lang: str) -> dict:
    return next(c for c in matrix_doc()["contexts"] if c["name"] == f"CodeQL Analysis ({lang})")


# ------------------------------------------------------------------------------------------------ fakes
def fake_docker(tmp_path: Path) -> Path:
    """A docker that pins an isolation image, records every argv, and 'builds' a deps image labelled with the digest it was asked for."""
    exe, log, built = tmp_path / "bin" / "docker", tmp_path / "docker.argv", tmp_path / "docker.built"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text('''#!PY
import json, os, sys
a = sys.argv[1:]
open("LOG", "a").write(json.dumps(a) + "\\n")
tags = json.load(open("BUILT")) if os.path.exists("BUILT") else {}
ISO = "sha256:" + "1" * 64
if a[:2] == ["image", "inspect"]:
    fmt, ref = a[3], a[4]
    if fmt.startswith("{{.Id}}\\n"):
        print(ISO)
        print("PYTHON_VERSION=3.12.15")
        sys.exit(0)
    if "RootFS.Layers" in fmt:
        print(json.dumps(["l1"] if ref == ISO else ["l1", "l2"]))
        sys.exit(0)
    if ref in tags:
        print("sha256:" + "2" * 64, tags[ref])
        sys.exit(0)
    sys.exit(1)
if a[0] == "build":
    tags[a[a.index("-t") + 1]] = next(x for x in a if x.startswith("org.nuzantara.localci.deps=")).split("=", 1)[1]
    json.dump(tags, open("BUILT", "w"))
sys.exit(0)
'''.replace("PY", sys.executable, 1).replace('"LOG"', repr(str(log))).replace('"BUILT"', repr(str(built))))
    exe.chmod(0o755)
    return exe


def fake_gh(tmp_path: Path, version: str | None = "2.27.2", rc: int = 0, language_present: bool = True) -> Path:
    """A `gh api` that answers the code-scanning analyses list of the hosted main branch (two languages, newest first)."""
    exe = tmp_path / "bin" / "gh"
    exe.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"id": 3, "category": "/language:python", "created_at": "2026-10-10T22:46:50Z", "tool": {"name": "CodeQL", "version": version}},
            {"id": 2, "category": "/language:javascript", "created_at": "2026-10-10T22:41:02Z", "tool": {"name": "CodeQL", "version": version}},
            {"id": 1, "category": "/language:python", "created_at": "2026-10-08T23:54:33Z", "tool": {"name": "CodeQL", "version": "2.27.1"}}]
    if not language_present:
        rows = [r for r in rows if r["category"] != "/language:python"]
    exe.write_text(f"#!/bin/bash\nif [ {rc} -ne 0 ]; then echo 'gh: HTTP 502' >&2; exit {rc}; fi\ncat <<'JSON'\n{json.dumps(rows)}\nJSON\n")
    exe.chmod(0o755)
    return exe


def base_files(extra: dict | None = None) -> dict:
    files = {p: (REAL / p).read_text() for p in (SECURITY, CONFIG, LEG_SH, READER)}
    return {**files, **(extra or {})}


def plan_codeql(tmp_path: Path, monkeypatch, lang: str, candidate: dict, base_extra: dict | None = None, gh_version: str | None = "2.27.2",
                gh_rc: int = 0, ctx_over: dict | None = None) -> tuple[dict, Path]:
    """Plan the real matrix entry for `lang` against a fixture repo whose BASE carries the real workflow, config, script and reader."""
    docker = fake_docker(tmp_path)
    fake_gh(tmp_path, gh_version, gh_rc)
    monkeypatch.setenv("PATH", f"{docker.parent}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(runner, "READER_RETRY_WAITS", (0, 0, 0))
    ctx = matrix_ctx(lang)
    ctx = {**ctx, "local": {**ctx["local"], **(ctx_over or {})}}
    fx = fr.make_repo(tmp_path, candidate, base_files(base_extra))
    fr.plan(fx, "--isolation", "container", "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [ctx])))
    plan = json.loads((fx["run"] / "state" / "plan.json").read_text())
    return plan["checks"][ctx["local"]["check"]], fx["run"]


DOCS_ONLY = {"docs/note.md": "# a note\n"}
PY_CHANGE = {"apps/backend-rag/backend/app/new_module.py": "VALUE = 1\n"}
JS_CHANGE = {"apps/mouth/src/new.ts": "export const v = 1;\n"}


# ------------------------------------------------------------------------------------------------ 1-2: the bundle image
def deps_dir(run_dir: Path, slug: str = "codeql") -> Path:
    return run_dir / "state" / "deps" / slug


def build_image(tmp_path: Path, pin: dict) -> tuple[str, str]:
    """(digest label the builder was given, the Dockerfile text) for a deps image carrying `pin`."""
    docker = fake_docker(tmp_path)
    (tmp_path / "logs").mkdir(exist_ok=True)
    image, why = runner.plan_deps_image(tmp_path, "c" * 40, {"image_id": "sha256:" + "1" * 64, "docker": str(docker)}, {"node": "24", "codeql": pin},
                                        "", tmp_path, "codeql")
    assert image, why
    argv = [json.loads(x) for x in (tmp_path / "docker.argv").read_text().splitlines()]
    label = next(x for a in argv if a[0] == "build" for x in a if x.startswith("org.nuzantara.localci.deps=")).split("=", 1)[1]
    return label, (deps_dir(tmp_path) / "Dockerfile").read_text()


def test_the_recipe_digest_covers_the_pin_so_a_bump_builds_a_new_image(tmp_path):
    base, _ = build_image(tmp_path / "a", PIN)
    again, _ = build_image(tmp_path / "b", dict(PIN))
    assert base == again   # same pin, same image: the prune keeps the newest per recipe as it does
    for field, value in (("version", "2.27.3"), ("sha256", "d" * 64), ("url", PIN["url"].replace("v2.27.2", "v2.27.3"))):
        bumped, _ = build_image(tmp_path / field, {**PIN, field: value})
        assert bumped != base, field


def test_a_deps_recipe_without_codeql_keeps_its_old_digest(tmp_path):
    docker = fake_docker(tmp_path)
    (tmp_path / "logs").mkdir(exist_ok=True)
    runner.plan_deps_image(tmp_path, "c" * 40, {"image_id": "sha256:" + "1" * 64, "docker": str(docker)}, {"node": "24"}, "", tmp_path, "n")
    plain = next(x for x in (tmp_path / "docker.argv").read_text().splitlines() if '"build"' in x)
    assert "codeql" not in plain.lower() and "codeql" not in (deps_dir(tmp_path, "n") / "Dockerfile").read_text().lower()


def test_the_tarball_is_checksum_fetched_into_a_stage_and_never_lands_in_a_layer(tmp_path):
    _, text = build_image(tmp_path, PIN)
    lines = text.splitlines()
    assert f"ADD --checksum=sha256:{PIN['sha256']} {PIN['url']} /bundle.tgz" in lines and "FROM scratch AS codeqlbundle" in lines
    assert lines.index("FROM scratch AS codeqlbundle") < len(lines) - 1 - lines[::-1].index("FROM ${BASE}")   # a stage of its own, before the final one
    final = text[text.rindex("FROM ${BASE}"):]
    assert "--mount=type=bind,from=codeqlbundle,source=/bundle.tgz,target=/mnt/bundle.tgz" in final and "tar -xzf /mnt/bundle.tgz -C /opt" in final
    assert 'test "$(/opt/codeql/codeql version --format=terse)" = "2.27.2"' in final and "ENV PATH=/opt/codeql:${PATH}" in final
    assert "COPY --from=codeqlbundle" not in text and "COPY --from=wheels" not in text   # no layer copy of the tarball, no wheel stage either
    assert not any(w in text for w in ("curl", "wget", "urllib", "fetch.py", "/bundle.tgz /"))   # not downloaded by a RUN, not read by the fetch script
    assert not (deps_dir(tmp_path) / "fetch.json").read_text().count("codeql")   # and it is not a `fetch` entry, which the fetch script reads whole


@pytest.mark.parametrize("pin", [
    {**PIN, "url": "http://github.com/x.tgz"}, {**PIN, "url": PIN["url"] + "?token=x"}, {**PIN, "url": PIN["url"] + " /etc"}, {**PIN, "sha256": "unpinned"},
    {**PIN, "sha256": "C" * 64}, {**PIN, "version": "latest"}, {"version": "2.27.2", "url": PIN["url"]}, {**PIN, "extra": "x"}, "2.27.2",
])
def test_a_codeql_pin_that_is_not_plain_is_refused_before_anything_is_built(tmp_path, pin):
    image, why = runner.plan_deps_image(tmp_path, "c" * 40, {"image_id": "sha256:" + "1" * 64, "docker": "/nonexistent"}, {"node": "24", "codeql": pin},
                                        "", tmp_path, "t")
    assert image is None and "deps.codeql" in why


# ------------------------------------------------------------------------------------------------ 3: the flags, from BASE
def flags_of(spec: dict) -> dict:
    return spec["needs"]["changes"]


@pytest.mark.parametrize("lang,candidate,want", [
    ("python", DOCS_ONLY, "false"), ("javascript", DOCS_ONLY, "false"),
    ("python", PY_CHANGE, "true"), ("javascript", PY_CHANGE, "false"),
    ("python", JS_CHANGE, "false"), ("javascript", JS_CHANGE, "true"),
])
def test_the_leg_flags_are_decided_at_plan_by_the_base_classifier_on_the_changed_files(tmp_path, monkeypatch, lang, candidate, want):
    spec, _ = plan_codeql(tmp_path, monkeypatch, lang, candidate)
    flag = "run_codeql_python" if lang == "python" else "run_codeql_js"
    assert spec["kind"] == "contained_jobs", spec
    assert flags_of(spec) == {"result": "success", "outputs": {"run_codeql_python": flags_of(spec)["outputs"]["run_codeql_python"],
                                                              "run_codeql_js": flags_of(spec)["outputs"]["run_codeql_js"]}}
    assert flags_of(spec)["outputs"][flag] == want


def test_a_candidate_that_rewrites_the_flag_classifier_cannot_switch_its_own_scan_off(tmp_path, monkeypatch):
    liar = "import sys\nprint('run_codeql_python=false')\nprint('run_codeql_js=false')\n"
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", {"scripts/ci/security_gate_flags.py": liar, **PY_CHANGE})
    assert flags_of(spec)["outputs"]["run_codeql_python"] == "true"   # BASE's file ran: scripts/ci/ is security-sensitive, so everything runs


def test_a_classifier_that_fails_is_hosted_fail_open_the_job_result_is_not_success_and_the_leg_runs(tmp_path):
    (tmp_path / "security_gate_flags.py").write_text("raise SystemExit(2)\n")
    spec = {"job": "changes", "script": "scripts/ci/security_gate_flags.py", "outputs": ["run_codeql_python", "run_codeql_js"]}
    got, note = runner.classifier_needs(tmp_path, {"run_all": False, "domains": {}}, ["docs/x.md"], spec)
    assert got == {"result": "failure", "outputs": {"run_codeql_python": "true", "run_codeql_js": "true"}} and "fail-open" in note
    (tmp_path / "security_gate_flags.py").write_text("print('run_codeql_python=maybe')\nprint('run_codeql_js=false')\n")
    assert runner.classifier_needs(tmp_path, {}, [], spec)[0]["result"] == "failure"   # an answer that is not true/false is no answer
    for bad in ({"job": "changes", "script": "scripts/ci/other.py", "outputs": ["x"]}, {"job": "", "script": "scripts/ci/security_gate_flags.py", "outputs": ["x"]}):
        assert runner.classifier_needs(tmp_path, {}, [], bad)[0] is None


# ------------------------------------------------------------------------------------------------ the commands, with a fake CLI
FAKE_CODEQL = '''#!/bin/bash
echo "$*" >> "$FAKE_LOG"
case "$*" in
  "version --format=terse") echo 2.27.2 ;;
esac
if [ -n "${FAKE_FAIL_ON:-}" ] && [[ "$*" == *"$FAKE_FAIL_ON"* ]]; then exit "${FAKE_RC:-1}"; fi
for a in "$@"; do
  case "$a" in --output=*) python3 -c "
import json, sys
n = int(sys.argv[2])
json.dump({'runs': [{'tool': {'driver': {'rules': [{'id': 'r1'}, {'id': 'r2'}]}}, 'results': [{'ruleId': 'r1'}] * n}]}, open(sys.argv[1], 'w'))
" "${a#--output=}" "${FAKE_RESULTS:-3}" ;; esac
done
exit 0
'''


def leg_env(tmp_path: Path, **extra) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    exe = tmp_path / "codeql"
    exe.write_text(FAKE_CODEQL)
    exe.chmod(0o755)
    src = tmp_path / "w"
    (src / ".github").mkdir(parents=True, exist_ok=True)
    (src / "scripts" / "localci").mkdir(parents=True, exist_ok=True)
    for rel in (CONFIG, LEG_SH):   # BASE's bytes, unless a test has laid its own
        if not (src / rel).exists():
            (src / rel).write_text((REAL / rel).read_text())
    return {"CODEQL_BIN": str(exe), "CODEQL_SOURCE_ROOT": str(src), "LOCALCI_CODEQL_WORK": str(tmp_path / "cq"), "FAKE_LOG": str(tmp_path / "codeql.argv"),
            "HOME": str(tmp_path), **extra}


def run_leg_sh(tmp_path: Path, mode: str, lang: str, **extra) -> subprocess.CompletedProcess:
    env = leg_env(tmp_path, **extra)
    return subprocess.run(["bash", str(tmp_path / "w" / LEG_SH), mode, lang], capture_output=True, text=True, env={**os.environ, **env})


@pytest.mark.parametrize("lang", LANGS)
def test_the_leg_script_builds_the_exact_command_lines_the_hosted_logs_show(tmp_path, lang):
    r1 = run_leg_sh(tmp_path, "init", lang)
    r2 = run_leg_sh(tmp_path, "analyze", lang)
    assert r1.returncode == 0 and r2.returncode == 0, (r1.stderr, r2.stderr)
    w, cq = tmp_path / "w", tmp_path / "cq"
    db, uc = f"{cq}/db", f"{cq}/user-config.yaml"
    trace = f"database trace-command --index-traceless-dbs {'-O=javascript.trap.cache.dir=' + str(cq) + '/trap -O=javascript.trap.cache.bound=1024 -O=javascript.trap.cache.write=true ' if lang == 'javascript' else ''}{db}/{lang}"
    assert (tmp_path / "codeql.argv").read_text().splitlines() == [
        "version --format=terse",
        f"database init --force-overwrite --db-cluster {db} --source-root={w} --calculate-language-specific-baseline --sublanguage-file-coverage "
        f"--extractor-include-aliases --language={lang} --codescanning-config={uc}",
        trace,
        f"database finalize --finalize-dataset --threads=4 --ram=10240 {db}/{lang}",
        f"database run-queries --ram=10240 --threads=4 --expect-discarded-cache {db}/{lang} --min-disk-free=1024 -v",
        f"database interpret-results --threads=4 --format=sarif-latest -v --output={cq}/{lang}.sarif --print-diagnostics-summary --print-metrics-summary "
        f"--sarif-add-baseline-file-info --sarif-codescanning-config={uc} --sarif-group-rules-by-pack --sarif-include-query-help=always "
        f"--sublanguage-file-coverage --sarif-category /language:{lang} --sarif-include-diagnostics {db}/{lang}"]
    assert f"LOCALCI_CODEQL_RESULTS language={lang} results=3 rules=2" in r2.stdout


def test_the_augmented_config_replaces_only_the_queries_block(tmp_path):
    env = leg_env(tmp_path)
    (tmp_path / "w" / CONFIG).write_text("name: c\nqueries:\n  - uses: old\n# keep\nquery-filters:\n  - exclude:\n      id: a/b\npaths-ignore:\n  - '**/t/**'\n")
    assert run_leg_sh(tmp_path, "init", "python", CODEQL_QUERIES="security-extended, security-and-quality").returncode == 0
    assert (tmp_path / "cq" / "user-config.yaml").read_text() == (
        "name: c\nqueries:\n  - uses: security-extended\n  - uses: security-and-quality\n# keep\nquery-filters:\n  - exclude:\n      id: a/b\npaths-ignore:\n  - '**/t/**'\n")
    (tmp_path / "w" / CONFIG).write_text("name: c\npaths-ignore:\n  - x\n")   # a config without queries gets the block, nothing else moves
    assert run_leg_sh(tmp_path, "init", "python").returncode == 0 and env
    assert (tmp_path / "cq" / "user-config.yaml").read_text().splitlines()[:4] == ["queries:", "  - uses: security-extended", "  - uses: security-and-quality", "name: c"]


def test_the_real_config_survives_augmentation_byte_for_byte_below_the_queries(tmp_path):
    assert run_leg_sh(tmp_path, "init", "python").returncode == 0
    real, aug = (REAL / CONFIG).read_text(), (tmp_path / "cq" / "user-config.yaml").read_text()
    assert aug.split("query-filters:", 1)[1] == real.split("query-filters:", 1)[1] and "security-extended" in aug.split("query-filters:")[0]


@pytest.mark.parametrize("args", [(), ("init",), ("build", "python"), ("init", "ruby"), ("init", "../x")])
def test_the_leg_script_refuses_what_it_was_not_written_for(tmp_path, args):
    env = leg_env(tmp_path)
    r = subprocess.run(["bash", str(tmp_path / "w" / LEG_SH), *args], capture_output=True, text=True, env={**os.environ, **env})
    assert r.returncode == 64 and not (tmp_path / "codeql.argv").exists()


# ------------------------------------------------------------------------------------------------ driving a planned leg
def drive_planned(tmp_path: Path, spec: dict, **extra) -> tuple[list, int]:
    """The planned job's steps through the real driver, with the fake CLI and the BASE script laid in the tree."""
    job, env = spec["jobs"][0], leg_env(tmp_path, **extra)
    ctx = {**spec["expr"], "matrix": dict(job["legs"][0]), "needs": {j: spec["needs"][j] for j in job["needs"]}}
    cfg = {"context": "t", "root": env["CODEQL_SOURCE_ROOT"], "path_prefix": "", "venv": False, "env": {**runner.CONTAINED_STEP_ENV, **env},
           "job_env": job["job_env"], "expr": ctx, "steps": job["steps"]}
    (tmp_path / "steps.json").write_text(json.dumps(cfg))
    rc = subprocess.run([sys.executable, "-I", str(runner.STEPS_DRIVER), str(tmp_path / "steps.json"), str(tmp_path / "j.xml")], capture_output=True).returncode
    return runner.parse_expr_junit(tmp_path / "j.xml"), rc


def combined(steps: list, label: str = "codeql[x]") -> list:
    return [{**s, "name": f"{label} › {s['name']}"} for s in steps]


@pytest.mark.parametrize("lang,candidate", [("python", DOCS_ONLY), ("javascript", DOCS_ONLY), ("python", JS_CHANGE), ("javascript", PY_CHANGE)])
def test_a_language_the_flags_skip_runs_nothing_the_leg_is_pass_and_compares_as_agree_with_full_coverage(tmp_path, monkeypatch, lang, candidate):
    spec, _ = plan_codeql(tmp_path, monkeypatch, lang, candidate)
    steps, rc = drive_planned(tmp_path, spec)
    assert rc == 0 and [s["status"] for s in steps] == ["NOT_APPLICABLE"] * 3
    assert steps[0]["reason"].startswith("if: ") and steps[2]["reason"].startswith("if: ") and not (tmp_path / "codeql.argv").exists()   # the CLI never ran
    status, reason = runner.steps_verdict(combined(steps), spec)
    assert status == "PASS" and "as hosted" in reason
    _compared_as_agree(spec, lang, status)


def _compared_as_agree(spec: dict, lang: str, status: str) -> None:
    hc = _load(Path(runner.__file__).with_name("hosted_compare.py"), "hosted_compare_for_codeql")
    name, check = f"CodeQL Analysis ({lang})", f"ctx.codeql-{lang}"
    contexts = runner.load_contexts(str(MATRIX))
    plan = {"contexts_status": "ok", "required_contexts": contexts["required"], "contexts_map": contexts["map"], "checks": {check: spec}}
    res = runner.evaluate_contexts({check: {"status": status, "reason": "x"}}, {**plan, "contexts_map": {name: contexts["map"][name]}})["results"][name]
    assert res["verdict"] == "OK" and res["coverage"] == "full" and "skipped" not in res
    sha = "a" * 40
    run = {"name": name, "status": "completed", "conclusion": "success", "completed_at": "2026-10-11T07:00:00Z", "head_sha": sha,
           "app": {"id": 15368, "slug": "github-actions"}}
    rep = hc.compare({"candidate_sha": sha, "overall": "PASS", "contexts": {"status": "ok", "results": {name: res}}}, [{"context": name, "app_id": 15368}], [run], [])
    row = rep["rows"][0]
    assert row["class"] == "AGREE" and row["coverage"] == "full" and row["skip"] is None and rep["coverage"]["compared_partial"] == []


@pytest.mark.parametrize("lang,candidate", [("python", PY_CHANGE), ("javascript", JS_CHANGE)])
def test_a_language_the_flags_run_executes_init_and_analyze_and_autobuild_is_not_applicable(tmp_path, monkeypatch, lang, candidate):
    spec, _ = plan_codeql(tmp_path, monkeypatch, lang, candidate)
    steps, rc = drive_planned(tmp_path, spec, FAKE_RESULTS="7")
    assert rc == 0 and [s["status"] for s in steps] == ["PASS", "NOT_APPLICABLE", "PASS"] and "no command" in steps[1]["reason"]
    assert runner.steps_verdict(combined(steps), spec)[0] == "PASS"
    assert len((tmp_path / "codeql.argv").read_text().splitlines()) == 6


def test_a_matrix_not_applicable_step_alone_is_never_a_pass(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", DOCS_ONLY)
    gate = [{"name": "a", "status": "NOT_APPLICABLE", "reason": "if: env.RUN_THIS_LANGUAGE == 'true' -> false (status success)"}]
    assert runner.steps_verdict(gate, {**spec, "skip_is_pass": False})[0] == "ERROR"   # without the declaration an all-skipped leg is still no evidence
    assert runner.steps_verdict(gate, spec)[0] == "PASS"
    matrix = [{"name": "a", "status": "NOT_APPLICABLE", "reason": "a written reason"}]
    assert runner.steps_verdict(matrix, spec)[0] == "ERROR"                            # and a skip that is no evaluated `if:` is not the gate's skip


# ------------------------------------------------------------------------------------------------ 5: the verdict
def test_a_command_that_exits_non_zero_is_a_fail_and_findings_never_are(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    steps, rc = drive_planned(tmp_path / "many", spec, FAKE_RESULTS="2499")   # 2499 findings: still green, they are data
    assert rc == 0 and runner.steps_verdict(combined(steps), spec)[0] == "PASS"
    for needle in ("database init", "database run-queries", "interpret-results", "database finalize"):
        steps, rc = drive_planned(tmp_path / needle.replace(" ", "-"), spec, FAKE_FAIL_ON=needle, FAKE_RC="2")
        status, reason = runner.steps_verdict(combined(steps), spec)
        assert rc == 1 and status == "FAIL", (needle, steps)


def test_a_command_killed_by_a_signal_is_no_verdict_never_a_fail(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    r = run_leg_sh(tmp_path / "direct", "analyze", "python", FAKE_FAIL_ON="run-queries", FAKE_RC="137")   # the shell's report of a SIGKILL (an OOM kill)
    assert r.returncode == -9 and "died of signal 9" in r.stderr   # the script dies of the same signal: its caller cannot read it as a red exit
    steps, rc = drive_planned(tmp_path / "driven", spec, FAKE_FAIL_ON="run-queries", FAKE_RC="137")
    assert rc == 4 and steps[2]["status"] == "ERROR"
    assert runner.steps_verdict(combined(steps), spec)[0] == "ERROR"


def test_a_timeout_or_a_driver_that_died_gives_no_verdict(tmp_path, monkeypatch):
    spec, run_dir = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    (run_dir / "logs").mkdir(exist_ok=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    plan = json.loads((run_dir / "state" / "plan.json").read_text())
    spec = {**spec, "isolation": plan["isolation"]}
    monkeypatch.setattr(runner, "disk_floor_refusal", lambda *a, **k: None)
    monkeypatch.setattr(runner, "start_services", lambda *a, **k: ([], None, None))
    monkeypatch.setattr(runner, "tree_pack_ship_safe", lambda *a: (None, {}, ""))
    for err in ("timeout after 1800s (container killed; removal verified below or the run aborts)", "container create failed: out of memory"):
        monkeypatch.setattr(runner, "execute_contained", lambda *a, **k: (None, err))
        out = runner._execute_jobs("ctx.codeql-python", spec, run_dir, plan, run_dir / "logs" / "ctx.log")
        assert out["status"] == "ERROR" and out["rc"] is None and err in out["reason"]
    monkeypatch.setattr(runner, "execute_contained", lambda *a, **k: (137, None))   # the container's init killed (cgroup OOM): rc without a junit
    out = runner._execute_jobs("ctx.codeql-python", spec, run_dir, plan, run_dir / "logs" / "ctx.log")
    assert out["status"] == "ERROR" and "no verdict" in out["reason"]


def test_the_results_per_language_go_to_the_receipt_as_data_and_the_leg_gets_the_base_overlay_and_no_git_index(tmp_path, monkeypatch):
    spec, run_dir = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    (run_dir / "logs").mkdir(exist_ok=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    plan = json.loads((run_dir / "state" / "plan.json").read_text())
    spec = {**spec, "isolation": plan["isolation"]}
    seen = {}

    def fake_exec(name, sp, rd, pl, inner, overrides, extra, env, log, junit, timeout, workdir, **kw):
        seen.update(overrides=overrides, cfg=json.loads(extra["cfg/steps.json"]), memory=kw["memory"], network=kw["network"], timeout=timeout)
        log.write_text("LOCALCI_CODEQL_RESULTS language=python results=2499 rules=172\n")
        suite = runner.ET.Element("testsuite")
        for n, skipped in (("Initialize CodeQL", False), ("Autobuild", True), ("Perform CodeQL Analysis", False)):
            tc = runner.ET.SubElement(suite, "testcase", name=n, time="1", cpu="1")
            if skipped:
                runner.ET.SubElement(tc, "skipped", message="matrix: written reason")
        runner.ET.ElementTree(suite).write(junit)
        return 0, None
    monkeypatch.setattr(runner, "execute_contained", fake_exec)
    monkeypatch.setattr(runner, "disk_floor_refusal", lambda *a, **k: None)
    monkeypatch.setattr(runner, "start_services", lambda *a, **k: ([], None, None))
    out = runner._execute_jobs("ctx.codeql-python", spec, run_dir, plan, run_dir / "logs" / "ctx.log")
    assert out["status"] == "PASS" and out["codeql"] == {"python": {"results": 2499, "rules": 172}}   # 2499 findings, PASS
    assert seen["cfg"]["git_index"] is False and seen["memory"] == "12g" and seen["network"] == "none" and seen["timeout"] == 30 * 60
    assert seen["overrides"] == {CONFIG: (REAL / CONFIG).read_bytes(), LEG_SH: (REAL / LEG_SH).read_bytes()}   # BASE's bytes, not the candidate's
    assert plan["trusted_files_sha256"][CONFIG] == runner.sha256_bytes((REAL / CONFIG).read_bytes())


def test_a_laid_judge_whose_hash_differs_from_the_plans_is_no_verdict(tmp_path, monkeypatch):
    spec, run_dir = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    (run_dir / "logs").mkdir(exist_ok=True)
    (run_dir / "receipts").mkdir(exist_ok=True)
    plan = json.loads((run_dir / "state" / "plan.json").read_text())
    (run_dir / "state" / "trusted" / "base_files" / CONFIG).write_text("paths-ignore: ['**']\n")   # the laid blob was swapped after the plan
    monkeypatch.setattr(runner, "disk_floor_refusal", lambda *a, **k: None)
    monkeypatch.setattr(runner, "start_services", lambda *a, **k: ([], None, None))
    monkeypatch.setattr(runner, "tree_pack_ship_safe", lambda *a: (None, {}, ""))
    monkeypatch.setattr(runner, "execute_contained", lambda *a, **k: pytest.fail("the sandbox must not start on a judge the plan did not freeze"))
    out = runner._execute_jobs("ctx.codeql-python", {**spec, "isolation": plan["isolation"]}, run_dir, plan, run_dir / "logs" / "ctx.log")
    assert out["status"] == "ERROR" and "differs from the plan's sha256" in out["reason"]


# ------------------------------------------------------------------------------------------------ 6: the version sentinel
@pytest.mark.parametrize("lang", LANGS)
def test_a_hosted_version_that_matches_the_pin_runs(tmp_path, monkeypatch, lang):
    spec, _ = plan_codeql(tmp_path, monkeypatch, lang, PY_CHANGE)
    assert spec["kind"] == "contained_jobs" and any("== the pin 2.27.2" in n for n in spec["plan_notes"])


@pytest.mark.parametrize("version,rc,needle", [("2.27.3", 0, "reports '2.27.3'"), (None, 0, "reports None"), ("2.27.2", 1, "could not read GitHub")])
def test_a_hosted_version_that_differs_or_a_read_that_fails_is_blocked_never_green(tmp_path, monkeypatch, version, rc, needle):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE, gh_version=version, gh_rc=rc)
    assert spec["kind"] == "record" and spec["status"] == "BLOCKED" and needle in spec["reason"] and "version sentinel" in spec["reason"]


def test_the_sentinel_runs_the_base_reader_not_the_candidates(tmp_path, monkeypatch):
    liar = "import sys\nsys.exit(0)\n"
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", {READER: liar, **PY_CHANGE}, gh_version="2.27.3")
    assert spec["status"] == "BLOCKED" and "MISMATCH" in spec["reason"]
    spec, _ = plan_codeql(tmp_path / "gone", monkeypatch, "python", PY_CHANGE, ctx_over={"version_sentinel": {"reader": "scripts/localci/absent.py"}})
    assert spec["status"] == "BLOCKED" and "is not a file at BASE" in spec["reason"]


def run_reader(rows, pin="2.27.2", language="python", rc=0):
    def run(argv, **kw):
        return subprocess.CompletedProcess(argv, rc, json.dumps(rows) if not isinstance(rows, str) else rows, "gh: HTTP 500")
    return reader.main(["--repo", "o/r", "--language", language, "--pin", pin], run=run)


def test_the_reader_compares_the_newest_analysis_of_exactly_this_language(capsys):
    rows = [{"id": 1, "category": "/language:python", "created_at": "2026-10-08T00:00:00Z", "tool": {"version": "2.27.1"}},
            {"id": 2, "category": "/language:python", "created_at": "2026-10-10T00:00:00Z", "tool": {"version": "2.27.2"}},
            {"id": 3, "category": "/language:javascript", "created_at": "2026-10-11T00:00:00Z", "tool": {"version": "2.99.0"}},
            {"id": 4, "category": "/language:python-extra", "created_at": "2026-10-12T00:00:00Z", "tool": {"version": "2.99.0"}}]
    assert run_reader(rows) == 0 and run_reader(rows, language="javascript", pin="2.99.0") == 0
    assert run_reader(rows, pin="2.27.1") == 3 and "MISMATCH" in capsys.readouterr().err   # the older python analysis does not stand in
    assert run_reader(rows, language="go") == 4 and "NO-ANALYSIS" in capsys.readouterr().err


@pytest.mark.parametrize("rows,rc", [("not json", 0), ({"message": "Not Found"}, 0), ([], 1)])
def test_the_reader_says_cannot_verify_on_every_failed_read(rows, rc, capsys):
    assert run_reader(rows, rc=rc) == 1 and capsys.readouterr().err.startswith(reader.CANNOT)


@pytest.mark.parametrize("argv", [["--repo", "o/r;x", "--language", "python", "--pin", "2.27.2"], ["--repo", "o/r", "--language", "py thon", "--pin", "2.27.2"],
                                  ["--repo", "o/r", "--language", "python", "--pin", "latest"]])
def test_the_reader_refuses_arguments_that_are_not_plain(argv):
    assert reader.main(argv, run=lambda *a, **k: pytest.fail("gh must not be asked")) == 2


# ------------------------------------------------------------------------------------------------ 7: the judges
@pytest.mark.parametrize("changed", [CONFIG, LEG_SH])
def test_a_candidate_that_changes_the_config_or_the_script_gets_its_green_blocked(tmp_path, monkeypatch, changed):
    edit = (REAL / changed).read_text() + ("\n# candidate\n" if changed == LEG_SH else "\npaths-ignore:\n  - '**'\n")
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", {changed: edit, **PY_CHANGE})
    assert spec["judge_modified"] == [changed]
    steps, _ = drive_planned(tmp_path, spec)
    assert [s["status"] for s in steps] == ["PASS", "NOT_APPLICABLE", "PASS"]
    status, reason = runner.steps_verdict(combined(steps), spec)
    assert status == "BLOCKED" and changed in reason and "hosted judges with the candidate's copy" in reason
    skipped = {**spec, "judge_modified": [changed]}
    assert runner.steps_verdict(combined([{"name": "x", "status": "NOT_APPLICABLE", "reason": "if: a -> false"}]), skipped)[0] == "BLOCKED"


def test_a_red_leg_with_a_rewritten_config_is_blocked_not_fail(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", {CONFIG: (REAL / CONFIG).read_text() + "\n# c\n", **PY_CHANGE})
    steps, rc = drive_planned(tmp_path, spec, FAKE_FAIL_ON="run-queries", FAKE_RC="2")
    assert rc == 1 and runner.steps_verdict(combined(steps), spec)[0] == "BLOCKED"


def test_an_untouched_config_and_script_leave_the_green_a_green(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    assert spec["judge_modified"] == [] and spec["overlay"] == [CONFIG, LEG_SH]


def test_a_missing_base_judge_blocks_the_plan(tmp_path, monkeypatch):
    docker = fake_docker(tmp_path)
    fake_gh(tmp_path)
    monkeypatch.setenv("PATH", f"{docker.parent}{os.pathsep}{os.environ['PATH']}")
    files = base_files()
    del files[LEG_SH]
    fx = fr.make_repo(tmp_path, PY_CHANGE, files)
    ctx = matrix_ctx("python")
    fr.plan(fx, "--isolation", "container", "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [ctx])))
    spec = json.loads((fx["run"] / "state" / "plan.json").read_text())["checks"]["ctx.codeql-python"]
    assert spec["status"] == "BLOCKED" and LEG_SH in spec["reason"] and "missing at base" in spec["reason"]


def test_a_changed_action_input_in_the_base_workflow_blocks_until_the_matrix_follows(tmp_path, monkeypatch):
    wf = (REAL / SECURITY).read_text().replace("queries: security-extended,security-and-quality", "queries: security-extended", 1)
    assert wf != (REAL / SECURITY).read_text()
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE, {SECURITY: wf})
    assert spec["status"] == "BLOCKED" and "not the ones the matrix transcribed" in spec["reason"]


# ------------------------------------------------------------------------------------------------ 8: the matrix suite
def test_the_summary_counts_and_the_never_claim_list_are_the_matrix_itself():
    doc = matrix_doc()
    by = {m: [c["name"] for c in doc["contexts"] if c["mapping"] == m] for m in runner.MAPPINGS}
    s = doc["summary"]
    assert (s["executed"], s["blocked"], s["not_implemented"], s["not_applicable_rule"]) == tuple(len(by[m]) for m in
                                                                                                   ("executed", "blocked", "not_implemented", "not_applicable_rule"))
    assert s["required_contexts"] == len(doc["contexts"]) == 14 and s["blocked"] == 0 and s["never_claim_parity_for"] == []
    assert sorted(s["never_claim_parity_for"]) == sorted(n for m, ns in by.items() if m != "executed" for n in ns)


def test_both_codeql_contexts_are_executed_full_and_judged_from_base():
    a, b = matrix_ctx("python"), matrix_ctx("javascript")
    for lang, c in zip(LANGS, (a, b)):
        loc = c["local"]
        assert (c["mapping"], c.get("coverage"), c["trusted_base_required"], c["job_id"]) == ("executed", "full", True, "codeql")
        assert loc["leg"] == {"language": lang} and loc["check"] == f"ctx.codeql-{lang}" and loc["trusted_overlay"] is True and loc["skip_is_pass"] is True
        assert loc["trusted_files"] == [CONFIG, LEG_SH] and loc["memory"] == "12g" and loc["git_index"] is False
        assert [x["argv"][-1] for x in loc["steps"] if "argv" in x] == [lang, lang]
        assert [x["argv"][2] for x in loc["steps"] if "argv" in x] == ["init", "analyze"]
        assert loc["classifier"]["script"] == "scripts/ci/security_gate_flags.py" and loc["version_sentinel"]["reader"] == READER
    assert a["local"]["deps"] == b["local"]["deps"] and a["local"]["deps_recipe"] == b["local"]["deps_recipe"] == "codeql"   # one image
    assert runner.codeql_pin(a["local"]["deps"]["codeql"])[1] is None and a["local"]["deps"]["codeql"]["version"] == "2.27.2"


def test_the_matrix_transcribes_the_workflows_action_inputs_exactly():
    job = yaml.safe_load((REAL / SECURITY).read_text())["jobs"]["codeql"]
    ws = {s["name"]: s for s in job["steps"] if "name" in s}
    for lang in LANGS:
        pins = {x["workflow_step"]: x.get("with_pin") for x in matrix_ctx(lang)["local"]["steps"]}
        for name in ("Initialize CodeQL", "Perform CodeQL Analysis"):
            assert {k: " ".join(str(v).split()) for k, v in ws[name]["with"].items()} == {k: " ".join(v.split()) for k, v in pins[name].items()}, name
        assert ws["Initialize CodeQL"]["with"]["queries"] == matrix_ctx(lang)["local"]["steps"][0]["env"]["CODEQL_QUERIES"]


def test_the_parity_gaps_name_the_four_codeql_differences_and_the_vm_size_is_current():
    gaps = matrix_doc()["summary"]["parity_gaps"]
    for key in ("version:", "flags:", "architecture:", "shape:"):
        assert sum(1 for g in gaps if g.startswith("CodeQL (python, javascript) " + key)) == 1, key
    assert not any("4 CPU / 8 GiB" in g for g in gaps) and any("8 CPU / 16 GiB" in g for g in gaps)
    assert any("feature flags" in g for g in gaps if "version:" in g) and any("src/codeql.ts" in g for g in gaps)
