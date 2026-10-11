"""The two CodeQL Analysis contexts: the pinned bundle image, the plan-time flags and version sentinel, the BASE-trusted commands, and a
verdict that is the commands' exit codes and nothing the findings say. Everything here runs without docker or the CLI: the Dockerfile is
asserted as text, the plan runs against a fake docker, the steps run through the real driver with a fake `codeql` that logs its argv."""
from __future__ import annotations

import datetime
import gzip
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
SARIF_CHECK = "scripts/localci/codeql_sarif_check.py"
RING_SH = "scripts/ci/ring_gating_override.sh"
LANGS = ("python", "javascript")
PIN = {"version": "2.27.2", "url": "https://github.com/github/codeql-action/releases/download/codeql-bundle-v2.27.2/codeql-bundle-linux-arm64.tar.gz",
       "sha256": "c" * 64}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


reader = _load(REAL / READER, "codeql_version_read_under_test")
checker = _load(REAL / SARIF_CHECK, "codeql_sarif_check_under_test")


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


def fake_gh(tmp_path: Path, version: str | None = "2.27.2", rc: int = 0, language_present: bool = True, versions: dict | None = None,
            override: str | None = None, override_rc: int = 0, override_doc: dict | None = None, age_days: float = 1.0, main: dict | None = None, runs_rc: int = 0, jobs_rc: int = 0) -> Path:
    """A `gh api` that answers what the plan reads: the code-scanning analyses list of the hosted main branch (two languages, newest first;
    `versions` sets the reported CLI per language where `version` sets both, `age_days` the newest one's age), the newest completed security.yml
    run on main and its jobs (`main` sets each language's job conclusion), and the MERGEOS_RING_GATING_DISABLED repository variable (`override`
    its value, None for 404, `override_rc` a read that fails)."""
    versions = {"python": version, "javascript": version, **(versions or {})}
    stamp = lambda d: (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")   # noqa: E731
    rows = [{"id": 3, "category": "/language:python", "created_at": stamp(age_days), "tool": {"name": "CodeQL", "version": versions["python"]}},
            {"id": 2, "category": "/language:javascript", "created_at": stamp(age_days + 0.01), "tool": {"name": "CodeQL", "version": versions["javascript"]}},
            {"id": 1, "category": "/language:python", "created_at": stamp(age_days + 2), "tool": {"name": "CodeQL", "version": "2.27.1"}}]
    if not language_present:
        rows = [r for r in rows if r["category"] != "/language:python"]
    conclusions = {"python": "success", "javascript": "success", **(main or {})}
    runs = {"workflow_runs": [{"id": 900, "created_at": stamp(0.5), "head_branch": "main", "status": "completed", "conclusion": "success"},
                              {"id": 800, "created_at": stamp(1.5), "head_branch": "main", "status": "completed", "conclusion": "failure"}]}
    jobs = {"jobs": [{"name": f"CodeQL Analysis ({lang})", "conclusion": c} for lang, c in conclusions.items()] + [{"name": "Bandit", "conclusion": "failure"}]}
    exe = tmp_path / "bin" / "gh"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text(f'''#!{sys.executable}
import json, sys
path, cfg = sys.argv[2], json.loads({json.dumps(json.dumps({"rows": rows, "rc": rc, "override": override, "override_rc": override_rc, "override_doc": override_doc, "runs": runs, "runs_rc": runs_rc,
                                                              "jobs": jobs, "jobs_rc": jobs_rc}))})
def answer(doc, code):
    if code:
        sys.stderr.write("gh: HTTP 502\\n")
        sys.exit(code)
    print(json.dumps(doc))
    sys.exit(0)
if "/code-scanning/analyses" in path:
    answer(cfg["rows"], cfg["rc"])
elif "/actions/variables/" in path:
    if cfg["override_rc"]:
        answer(None, cfg["override_rc"])
    if cfg["override_doc"] is not None:
        answer(cfg["override_doc"], 0)
    if cfg["override"] is None:
        sys.stdout.write('{{"message":"Not Found","status":"404"}}')
        sys.stderr.write("gh: Not Found (HTTP 404)\\n")
        sys.exit(1)
    answer({{"name": "MERGEOS_RING_GATING_DISABLED", "value": cfg["override"]}}, 0)
elif "/actions/workflows/security.yml/runs" in path:
    answer(cfg["runs"], cfg["runs_rc"])
elif "/actions/runs/900/jobs" in path:
    answer(cfg["jobs"], cfg["jobs_rc"])
else:
    sys.stderr.write("fake gh: unexpected " + path + "\\n")
    sys.exit(9)
''')
    exe.chmod(0o755)
    return exe


def base_files(extra: dict | None = None) -> dict:
    files = {p: (REAL / p).read_text() for p in (SECURITY, CONFIG, LEG_SH, READER, SARIF_CHECK, RING_SH)}
    return {**files, **(extra or {})}


def plan_codeql(tmp_path: Path, monkeypatch, lang: str, candidate: dict, base_extra: dict | None = None, gh_version: str | None = "2.27.2",
                gh_rc: int = 0, ctx_over: dict | None = None, gh_versions: dict | None = None, after_candidate=None, gh_kw: dict | None = None) -> tuple[dict, Path]:
    """Plan the real matrix entry for `lang` against a fixture repo whose BASE carries the real workflow, config, script and reader."""
    docker = fake_docker(tmp_path)
    fake_gh(tmp_path, gh_version, gh_rc, versions=gh_versions, **(gh_kw or {}))
    monkeypatch.setenv("PATH", f"{docker.parent}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(runner, "READER_RETRY_WAITS", (0, 0, 0))
    ctx = matrix_ctx(lang)
    ctx = {**ctx, "local": {**ctx["local"], **(ctx_over or {})}}
    fx = fr.make_repo(tmp_path, candidate, base_files(base_extra))
    if after_candidate:   # one more candidate commit (a rename needs a base file to move); the plan reads the worktree HEAD
        after_candidate(fx["repo"])
    fr.plan(fx, "--isolation", "container", "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [ctx])))
    plan = json.loads((fx["run"] / "state" / "plan.json").read_text())
    return plan["checks"][ctx["local"]["check"]], fx["run"]


DOCS_ONLY = {"docs/note.md": "# a note\n"}
UNCLASSIFIED = {"zz_unclassified_top/thing.xyz": "x\n"}
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


@pytest.mark.parametrize("lang", LANGS)
def test_an_unclassified_path_is_run_all_and_both_legs_run(tmp_path, monkeypatch, lang):
    spec, run_dir = plan_codeql(tmp_path, monkeypatch, lang, {**DOCS_ONLY, **UNCLASSIFIED})
    plan = json.loads((run_dir / "state" / "plan.json").read_text())
    assert plan["checks"]["policy.change_map"]["data"]["run_all"] is True   # the BASE map fails open on a path no rule names
    assert flags_of(spec)["outputs"] == {"run_codeql_python": "true", "run_codeql_js": "true"}   # DOCS_ONLY alone reads false/false


def _git_mv_commit(src: str, dst: str):
    def move(repo: Path) -> None:
        (repo / dst).parent.mkdir(parents=True, exist_ok=True)
        fr.git(repo, "mv", src, dst)
        fr.git(repo, "commit", "-q", "-m", "move")
    return move


@pytest.mark.parametrize("lang,old,flag", [("python", "apps/backend-rag/backend/app/old_mod.py", "run_codeql_python"),
                                          ("javascript", "apps/mouth/src/old_mod.ts", "run_codeql_js")])
def test_a_rename_lists_both_paths_so_the_leg_runs_as_hosted_does(tmp_path, monkeypatch, lang, old, flag):
    body = "VALUE = 1\n" * 20   # identical content: git's rename detection sees a rename, not a delete and an add
    spec, run_dir = plan_codeql(tmp_path, monkeypatch, lang, DOCS_ONLY, base_extra={old: body}, after_candidate=_git_mv_commit(old, "docs/moved.txt"))
    changed = json.loads((run_dir / "state" / "plan.json").read_text())["changed_files"]
    assert old in changed and "docs/moved.txt" in changed   # hotzone_changed_files.sh lists both: `git diff --no-renames`
    assert flags_of(spec)["outputs"][flag] == "true"


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
  "version --format=terse") echo "${FAKE_VERSION-2.27.2}" ;;
esac
if [ -n "${FAKE_FAIL_ON:-}" ] && [[ "$*" == *"$FAKE_FAIL_ON"* ]]; then exit "${FAKE_RC:-1}"; fi
for a in "$@"; do
  case "$a" in --output=*) if [ -n "${FAKE_SARIF:-}" ]; then cp "$FAKE_SARIF" "${a#--output=}"; continue; fi; python3 -c "
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
    for rel in (CONFIG, LEG_SH, SARIF_CHECK):   # BASE's bytes, unless a test has laid its own
        if not (src / rel).exists():
            (src / rel).write_text((REAL / rel).read_text())
    return {"CODEQL_BIN": str(exe), "CODEQL_SOURCE_ROOT": str(src), "LOCALCI_CODEQL_WORK": str(tmp_path / "cq"), "FAKE_LOG": str(tmp_path / "codeql.argv"),
            "CODEQL_PIN": PIN["version"], "HOME": str(tmp_path), **extra}


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


def test_a_version_probe_killed_by_a_signal_is_no_verdict_and_one_that_fails_is_its_own_exit(tmp_path):
    probe = "version --format=terse"   # exactly the probe: pytest's tmp_path carries the test's name, so a bare "version" would fail `database init` too
    r = run_leg_sh(tmp_path / "killed", "init", "python", FAKE_FAIL_ON=probe, FAKE_RC="137")
    assert r.returncode == -9 and "died of signal 9" in r.stderr   # step: the same re-raised signal as any other command, never a red exit
    assert (tmp_path / "killed" / "codeql.argv").read_text().splitlines() == [probe]   # and nothing ran after the probe
    r = run_leg_sh(tmp_path / "failed", "init", "python", FAKE_FAIL_ON=probe, FAKE_RC="2")
    assert r.returncode == 2 and "died of signal" not in r.stderr
    assert "database init" not in (tmp_path / "failed" / "codeql.argv").read_text()   # the probe's own exit stops the leg: a swallowed probe would run `database init`


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
    assert seen["overrides"] == {rel: (REAL / rel).read_bytes() for rel in (CONFIG, LEG_SH, SARIF_CHECK)}   # BASE's bytes, not the candidate's
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


@pytest.mark.parametrize("lang,versions,blocked", [
    ("javascript", {"javascript": "2.27.3"}, True), ("python", {"javascript": "2.27.3"}, False),
    ("python", {"python": "2.27.3"}, True), ("javascript", {"python": "2.27.3"}, False)])
def test_the_sentinel_reads_the_category_of_the_leg_own_language(tmp_path, monkeypatch, lang, versions, blocked):
    spec, _ = plan_codeql(tmp_path, monkeypatch, lang, {**PY_CHANGE, **JS_CHANGE}, gh_versions=versions)
    if blocked:
        assert spec["kind"] == "record" and spec["status"] == "BLOCKED" and "reports '2.27.3'" in spec["reason"] and f"for {lang}" in spec["reason"]
    else:
        assert spec["kind"] == "contained_jobs"


def test_the_sentinel_runs_the_base_reader_not_the_candidates(tmp_path, monkeypatch):
    liar = "import sys\nsys.exit(0)\n"
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", {READER: liar, **PY_CHANGE}, gh_version="2.27.3")
    assert spec["status"] == "BLOCKED" and "MISMATCH" in spec["reason"]
    spec, _ = plan_codeql(tmp_path / "gone", monkeypatch, "python", PY_CHANGE, ctx_over={"version_sentinel": {"reader": "scripts/localci/absent.py"}})
    assert spec["status"] == "BLOCKED" and "is not a file at BASE" in spec["reason"]


READER_NOW = datetime.datetime(2026, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
MAIN_RUNS = {"workflow_runs": [{"id": 800, "created_at": "2026-10-10T19:17:00Z", "head_branch": "main"},
                               {"id": 900, "created_at": "2026-10-11T19:17:00Z", "head_branch": "main"}]}   # not newest first: the reader picks by created_at


def main_jobs(**conclusion) -> dict:
    got = {"python": "success", "javascript": "success", **conclusion}
    return {"jobs": [{"name": f"CodeQL Analysis ({lang})", "conclusion": c} for lang, c in got.items()] + [{"name": "Bandit", "conclusion": "failure"}]}


def run_reader(rows, pin="2.27.2", language="python", rc=0, runs=None, jobs=None, runs_rc=0, jobs_rc=0, now=READER_NOW, repo="o/r"):
    """The reader against a stub gh: analyses -> `rows`, the security.yml runs -> `runs`, the newest run's jobs -> `jobs`."""
    answers = {"/code-scanning/analyses": (rc, rows), "/actions/workflows/security.yml/runs": (runs_rc, MAIN_RUNS if runs is None else runs),
               "/actions/runs/900/jobs": (jobs_rc, main_jobs() if jobs is None else jobs)}

    def run(argv, **kw):
        code, doc = next((v for k, v in answers.items() if k in argv[2]), (1, "unexpected path"))
        return subprocess.CompletedProcess(argv, code, json.dumps(doc) if not isinstance(doc, str) else doc, "gh: HTTP 500")
    return reader.main(["--repo", repo, "--language", language, "--pin", pin], run=run, now=now)


def test_the_reader_compares_the_newest_analysis_of_exactly_this_language(capsys):
    rows = [{"id": 1, "category": "/language:python", "created_at": "2026-10-08T00:00:00Z", "tool": {"name": "CodeQL", "version": "2.27.1"}},
            {"id": 2, "category": "/language:python", "created_at": "2026-10-10T00:00:00Z", "tool": {"name": "CodeQL", "version": "2.27.2"}},
            {"id": 3, "category": "/language:javascript", "created_at": "2026-10-11T00:00:00Z", "tool": {"name": "CodeQL", "version": "2.99.0"}},
            {"id": 4, "category": "/language:python-extra", "created_at": "2026-10-12T00:00:00Z", "tool": {"name": "CodeQL", "version": "2.99.0"}}]
    assert run_reader(rows) == 0 and run_reader(rows, language="javascript", pin="2.99.0") == 0
    assert run_reader(rows, pin="2.27.1") == 3 and "MISMATCH" in capsys.readouterr().err   # the older python analysis does not stand in
    assert run_reader(rows, language="go") == 4 and "NO-ANALYSIS" in capsys.readouterr().err


def test_the_reader_ignores_another_scanner_uploading_under_the_same_category(capsys):
    rows = [{"id": 1, "category": "/language:python", "created_at": "2026-10-10T00:00:00Z", "tool": {"name": "CodeQL", "version": "2.27.2"}},
            {"id": 2, "category": "/language:python", "created_at": "2026-10-12T00:00:00Z", "tool": {"name": "OtherScanner", "version": "9.9.9"}},
            {"id": 3, "category": "/language:python", "created_at": "2026-10-13T00:00:00Z", "tool": {"version": "9.9.9"}}]
    assert run_reader(rows) == 0
    assert run_reader(rows[1:]) == 4 and "NO-ANALYSIS" in capsys.readouterr().err   # only a non-CodeQL analysis is no CodeQL analysis


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
    assert spec["judge_modified"] == [] and spec["overlay"] == [CONFIG, LEG_SH, SARIF_CHECK]


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
        assert loc["trusted_files"] == [CONFIG, LEG_SH, SARIF_CHECK] and loc["memory"] == "12g" and loc["git_index"] is False
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


# ------------------------------------------------------------------------------------------------ sentinel freshness and hosted main
def at(days: float) -> str:
    return (READER_NOW - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def one_row(created: str, version: str = "2.27.2") -> list:
    return [{"id": 7, "category": "/language:python", "created_at": created, "tool": {"name": "CodeQL", "version": version}}]


@pytest.mark.parametrize("days,rc", [(0.0, 0), (6.99, 0), (7.0, 0), (7.01, 5), (30, 5)])
def test_the_reader_is_blocked_by_an_analysis_older_than_seven_days(days, rc, capsys):
    assert run_reader(one_row(at(days))) == rc
    if rc:
        err = capsys.readouterr().err
        assert "STALE" in err and f"{int(days)} days old" in err and "limit 7" in err


def test_the_age_is_judged_after_the_version_so_a_stale_other_version_names_the_version(capsys):
    assert run_reader(one_row(at(30), "2.27.1")) == 3 and "MISMATCH" in capsys.readouterr().err


def test_an_unreadable_created_at_is_cannot_verify_never_fresh(capsys):
    assert run_reader(one_row("yesterday")) == 1 and capsys.readouterr().err.startswith(reader.CANNOT)


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "skipped", None])
def test_the_reader_is_blocked_when_hosted_main_is_red_on_this_leg(conclusion, capsys):
    assert run_reader(one_row(at(1)), jobs=main_jobs(python=conclusion)) == 6
    err = capsys.readouterr().err
    assert "MAIN-RED" in err and "CodeQL Analysis (python)" in err and "hosted main is red on this leg" in err


def test_another_languages_red_job_does_not_block_this_leg(capsys):
    assert run_reader(one_row(at(1)), jobs=main_jobs(javascript="failure")) == 0
    rows = one_row(at(1))
    rows[0]["category"] = "/language:javascript"
    assert run_reader(rows, language="javascript", jobs=main_jobs(javascript="failure")) == 6


def test_the_newest_completed_run_is_the_one_by_created_at_not_by_position(capsys):
    older_red = {"workflow_runs": [{"id": 900, "created_at": "2026-10-11T19:17:00Z", "head_branch": "main"},
                                   {"id": 111, "created_at": "2026-10-01T19:17:00Z", "head_branch": "main"}]}
    assert run_reader(one_row(at(1)), runs=older_red) == 0   # run 900 is the newest whatever its position (its jobs are green)
    newer_red = {"workflow_runs": [{"id": 111, "created_at": "2026-10-01T19:17:00Z", "head_branch": "main"},
                                   {"id": 900, "created_at": "2026-10-11T19:17:00Z", "head_branch": "main"}]}
    assert run_reader(one_row(at(1)), runs=newer_red, jobs=main_jobs(python="failure")) == 6


@pytest.mark.parametrize("kw", [{"runs_rc": 1}, {"jobs_rc": 1}, {"runs": {"workflow_runs": []}}, {"runs": {"message": "x"}}, {"jobs": {"jobs": []}},
                                {"jobs": {"jobs": [{"name": "CodeQL Analysis (python)", "conclusion": "success"}] * 2}}, {"jobs": "not json"}])
def test_a_read_of_hosted_main_that_fails_or_cannot_find_the_job_is_cannot_verify_never_green(kw, capsys):
    assert run_reader(one_row(at(1)), **kw) == 1 and capsys.readouterr().err.startswith(reader.CANNOT)


@pytest.mark.parametrize("repo", ["../x", "o/..", "./x", "o/.", "../..", "o/r;x", "o"])
def test_the_reader_refuses_a_repo_that_climbs_the_api_path(repo):
    assert run_reader(one_row(at(1)), repo=repo) == 2


def test_the_reader_takes_an_owner_and_a_name_with_dots_inside_a_segment():
    assert run_reader(one_row(at(1)), repo="my.org/some-repo.v2") == 0


def test_a_stale_newest_analysis_blocks_the_plan_with_the_days_in_the_reason(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE, gh_kw={"age_days": 8})
    assert spec["kind"] == "record" and spec["status"] == "BLOCKED" and "version sentinel" in spec["reason"] and "8 days old" in spec["reason"]
    spec, _ = plan_codeql(tmp_path / "fresh", monkeypatch, "python", PY_CHANGE, gh_kw={"age_days": 6})
    assert spec["kind"] == "contained_jobs"


@pytest.mark.parametrize("lang,main,blocked", [("python", {"python": "failure"}, True), ("javascript", {"javascript": "failure"}, True),
                                               ("python", {"javascript": "failure"}, False), ("javascript", {"python": "failure"}, False)])
def test_a_red_hosted_main_job_of_the_legs_own_language_blocks_the_plan(tmp_path, monkeypatch, lang, main, blocked):
    spec, _ = plan_codeql(tmp_path, monkeypatch, lang, PY_CHANGE, gh_kw={"main": main})
    if blocked:
        assert spec["kind"] == "record" and spec["status"] == "BLOCKED" and "MAIN-RED" in spec["reason"] and f"CodeQL Analysis ({lang})" in spec["reason"]
    else:
        assert spec["kind"] == "contained_jobs"


# ------------------------------------------------------------------------------------------------ the ring-gating override, read live
def test_the_override_is_read_at_plan_and_an_active_one_runs_both_languages_as_hosted_does(tmp_path, monkeypatch):
    for lang in LANGS:
        spec, _ = plan_codeql(tmp_path / lang, monkeypatch, lang, DOCS_ONLY, gh_kw={"override": "true"})   # DOCS_ONLY alone reads false/false
        assert spec["kind"] == "contained_jobs" and spec["ring_gating_override"] == {"read": "ok", "active": True}
        assert flags_of(spec) == {"result": "success", "outputs": {"run_codeql_python": "true", "run_codeql_js": "true"}}
        assert any("ring-gating override ACTIVE" in n for n in spec["plan_notes"])


@pytest.mark.parametrize("value", [None, "false", "", "True", "TRUE", "1", " true", "true ", "yes"])
def test_an_unset_variable_or_any_value_that_is_not_exactly_true_leaves_the_classifier_deciding(tmp_path, monkeypatch, value):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", DOCS_ONLY, gh_kw={"override": value})   # None is a 404: the variable does not exist
    assert spec["ring_gating_override"] == {"read": "ok", "active": False}
    assert flags_of(spec) == {"result": "success", "outputs": {"run_codeql_python": "false", "run_codeql_js": "false"}}


def test_a_read_that_fails_is_fail_open_both_flags_true_and_the_job_result_not_success(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", DOCS_ONLY, gh_kw={"override_rc": 1})
    assert spec["kind"] == "contained_jobs" and spec["ring_gating_override"] == {"read": "error", "active": True}
    assert flags_of(spec) == {"result": "failure", "outputs": {"run_codeql_python": "true", "run_codeql_js": "true"}}
    assert any("override unreadable" in n for n in spec["plan_notes"])


def test_the_truth_table_is_the_base_copy_not_the_candidates_and_not_a_reimplementation(tmp_path, monkeypatch):
    candidate_says_off = "#!/usr/bin/env bash\necho active=false\n"
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", {RING_SH: candidate_says_off, **DOCS_ONLY}, gh_kw={"override": "true"})
    assert spec["ring_gating_override"]["active"] is True   # BASE's script ran
    base_odd = "#!/usr/bin/env bash\necho active=maybe\n"
    spec, _ = plan_codeql(tmp_path / "odd", monkeypatch, "python", DOCS_ONLY, base_extra={RING_SH: base_odd}, gh_kw={"override": "true"})
    assert spec["ring_gating_override"] == {"read": "error", "active": True}   # an answer that is not active=true/false is no answer: fail-open


@pytest.mark.parametrize("doc", [{"value": 1}, {"value": None}, {"name": "x"}, [1], "text"])
def test_a_variable_answer_without_a_string_value_is_a_read_error(tmp_path, monkeypatch, doc):
    docker = fake_docker(tmp_path)
    fake_gh(tmp_path, override_doc=doc)
    monkeypatch.setenv("PATH", f"{docker.parent}{os.pathsep}{os.environ['PATH']}")
    assert runner.ring_gating_override(REAL, "HEAD", tmp_path / "trusted", "o/r") == {"read": "error", "active": True}


# ------------------------------------------------------------------------------------------------ the action ref is pinned
def test_the_matrix_pins_the_three_codeql_actions_to_the_sha_the_workflow_uses():
    ws = {s["name"]: s for s in yaml.safe_load((REAL / SECURITY).read_text())["jobs"]["codeql"]["steps"] if "name" in s}
    for lang in LANGS:
        pins = {x["workflow_step"]: x.get("uses_pin") for x in matrix_ctx(lang)["local"]["steps"]}
        assert set(pins) == {"Initialize CodeQL", "Autobuild", "Perform CodeQL Analysis"}
        assert all(pins[n] == ws[n]["uses"] and pins[n].split("@")[1] == "2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2" for n in pins)


@pytest.mark.parametrize("step,action", [("Initialize CodeQL", "init"), ("Autobuild", "autobuild"), ("Perform CodeQL Analysis", "analyze")])
def test_a_bumped_codeql_action_in_the_base_workflow_blocks_until_the_matrix_follows(tmp_path, monkeypatch, step, action):
    old = "github/codeql-action/" + action + "@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2"
    wf = (REAL / SECURITY).read_text()
    assert wf.count(old) == 1
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE, {SECURITY: wf.replace(old, "github/codeql-action/" + action + "@" + "e" * 40)})
    assert spec["kind"] == "record" and spec["status"] == "BLOCKED" and f"step {step!r}" in spec["reason"] and "an action bump is not emulated" in spec["reason"]
    spec, _ = plan_codeql(tmp_path / "ok", monkeypatch, "python", PY_CHANGE)
    assert spec["kind"] == "contained_jobs"


# ------------------------------------------------------------------------------------------------ the leg's test seams are not inputs
SEAMS = ("CODEQL_BIN", "CODEQL_SOURCE_ROOT", "LOCALCI_CODEQL_WORK", "CODEQL_BASE_CONFIG")


@pytest.mark.parametrize("seam", SEAMS)
def test_a_base_job_env_that_sets_a_leg_seam_blocks_the_plan(tmp_path, monkeypatch, seam):
    wf = (REAL / SECURITY).read_text()
    marker = "    env:\n      RUN_THIS_LANGUAGE: >-"
    assert wf.count(marker) == 1
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE, {SECURITY: wf.replace(marker, f"    env:\n      {seam}: /evil\n      RUN_THIS_LANGUAGE: >-")})
    assert spec["kind"] == "record" and spec["status"] == "BLOCKED" and seam in spec["reason"] and "test seams" in spec["reason"]


def test_a_base_step_env_or_a_matrix_step_env_that_sets_a_leg_seam_blocks_the_plan(tmp_path, monkeypatch):
    wf = (REAL / SECURITY).read_text()
    marker = "      - name: Perform CodeQL Analysis\n        if: env.RUN_THIS_LANGUAGE == 'true'\n"
    assert wf.count(marker) == 1
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE, {SECURITY: wf.replace(marker, marker + "        env:\n          CODEQL_SOURCE_ROOT: /evil\n")})
    assert spec["status"] == "BLOCKED" and "CODEQL_SOURCE_ROOT" in spec["reason"]
    steps = [dict(x) for x in matrix_ctx("python")["local"]["steps"]]
    steps[2] = {**steps[2], "env": {"LOCALCI_CODEQL_WORK": "/tmp/evil"}}
    spec, _ = plan_codeql(tmp_path / "matrix", monkeypatch, "python", PY_CHANGE, ctx_over={"steps": steps})
    assert spec["status"] == "BLOCKED" and "LOCALCI_CODEQL_WORK" in spec["reason"]


def test_the_seams_stay_usable_by_the_legs_own_tests_which_call_the_script_directly(tmp_path):
    r = run_leg_sh(tmp_path, "init", "python")   # leg_env sets all of them
    assert r.returncode == 0, r.stderr


# ------------------------------------------------------------------------------------------------ the local CLI is the pin
def test_the_matrix_passes_the_recipe_pin_to_the_leg_as_the_one_literal():
    for lang in LANGS:
        loc = matrix_ctx(lang)["local"]
        assert loc["steps"][0]["env"]["CODEQL_PIN"] == loc["deps"]["codeql"]["version"]


def test_the_planned_init_step_carries_the_pin_in_its_env(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    assert spec["jobs"][0]["steps"][0]["env"]["CODEQL_PIN"] == "2.27.2"


@pytest.mark.parametrize("reported", ["2.27.1", "2.27.3", "2.27.2-rc1", "", "v2.27.2"])
def test_a_local_cli_other_than_the_pin_is_no_verdict_before_anything_is_extracted(tmp_path, reported):
    r = run_leg_sh(tmp_path, "init", "python", FAKE_VERSION=reported)
    assert r.returncode == -9 and "no verdict" in r.stderr and "the pin is '2.27.2'" in r.stderr   # a signal, as for an OOM kill: never a red exit
    assert (tmp_path / "codeql.argv").read_text().splitlines() == ["version --format=terse"]


@pytest.mark.parametrize("pin", ["", None])
def test_a_leg_without_a_pin_has_nothing_to_compare_and_gives_no_verdict(tmp_path, pin):
    env = leg_env(tmp_path)
    if pin is None:
        env.pop("CODEQL_PIN")
    else:
        env["CODEQL_PIN"] = pin
    r = subprocess.run(["bash", str(tmp_path / "w" / LEG_SH), "init", "python"], capture_output=True, text=True, env={**{k: v for k, v in os.environ.items() if k != "CODEQL_PIN"}, **env})
    assert r.returncode == -9 and "CODEQL_PIN" in r.stderr


def test_a_driven_leg_on_another_cli_is_error_never_fail_or_pass(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    steps, rc = drive_planned(tmp_path / "other", spec, FAKE_VERSION="2.27.3")
    assert rc == 4 and steps[0]["status"] == "ERROR"
    assert runner.steps_verdict(combined(steps), spec)[0] == "ERROR"
    steps, rc = drive_planned(tmp_path / "same", spec)
    assert rc == 0 and runner.steps_verdict(combined(steps), spec)[0] == "PASS"


# ------------------------------------------------------------------------------------------------ skip_is_pass, tightened
def test_a_leg_that_mixes_the_gate_skip_with_any_other_skip_is_not_a_pass(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", DOCS_ONLY)
    steps, rc = drive_planned(tmp_path, spec)
    base = combined(steps)
    assert rc == 0 and runner.steps_verdict(base, spec)[0] == "PASS"
    assert [s["name"].rsplit(" › ", 1)[1] for s in base] == ["Initialize CodeQL", "Autobuild", "Perform CodeQL Analysis"]
    for i in (0, 2):   # a step BASE gates with an `if:`, skipped for some other written reason
        mixed = [dict(s) for s in base]
        mixed[i]["reason"] = "skipped for a reason of its own"
        status, reason = runner.steps_verdict(mixed, spec)
        assert status == "ERROR" and "not PASS" in reason, (i, status)
    swapped = [dict(s) for s in base]
    swapped[1]["reason"] = "if: env.RUN_THIS_LANGUAGE == 'true' -> false (status success)"   # an `if:` skip anywhere is the gate's: Autobuild's matrix N/A may be one
    assert runner.steps_verdict(swapped, spec)[0] == "PASS"
    stranger = [*base[:2], {"name": "codeql[x] › A step the plan does not know", "status": "NOT_APPLICABLE", "reason": "written, but nobody planned it"}]
    assert runner.steps_verdict(stranger, spec)[0] == "ERROR"
    only_matrix = [{**base[1]}]
    assert runner.steps_verdict(only_matrix, spec)[0] == "ERROR"   # a matrix N/A alone, with no `if:` skip, is no gate evidence


def test_the_drivers_if_false_wording_is_the_one_the_runner_matches():
    assert runner.IF_FALSE.match("if: env.RUN_THIS_LANGUAGE == 'true' -> false (status success)")
    assert runner.IF_FALSE.match("if: always() -> false (status failure)") and runner.IF_FALSE.match("if: x -> false")
    assert not runner.IF_FALSE.match("the action runs no command for python") and not runner.IF_FALSE.match("if: x -> true")
    assert not runner.IF_FALSE.match("an if: x -> false inside a sentence")


# ------------------------------------------------------------------------------------------------ the config rewriter fails closed
@pytest.mark.parametrize("config", ["name: c\nqueries: [security-extended, security-and-quality]\npaths-ignore:\n  - x\n", "name: c\nqueries: security-extended\n",
                                    "queries:   [a]  # inline\nname: c\n",
                                    "name: c\nqueries:\n  - uses: a\n# a comment between items\n  - uses: b\npaths-ignore:\n  - x\n",
                                    "queries:\n  - uses: a\n\n# a comment after a blank\n  - uses: b\nname: c\n"])
def test_a_queries_block_the_rewriter_cannot_read_as_text_is_no_verdict_and_writes_nothing(tmp_path, config):
    leg_env(tmp_path)
    (tmp_path / "w" / CONFIG).write_text(config)
    r = run_leg_sh(tmp_path, "init", "python")
    assert r.returncode == -9 and "no verdict" in r.stderr and "queries block" in r.stderr
    assert not (tmp_path / "cq" / "user-config.yaml").exists() and not (tmp_path / "codeql.argv").exists()


@pytest.mark.parametrize("config,expected_tail", [
    ("# queries: [a]\nname: c\nqueries:\n  - uses: a\n", "name: c\nqueries:\n  - uses: security-extended\n  - uses: security-and-quality\n"),                                   # a commented-out inline queries is a comment
    ("name: c\nqueries:\n  - uses: a\n# trailing comment\npaths-ignore:\n  - x\n", "# trailing comment\npaths-ignore:\n  - x\n"),
    ("name: c\nqueries:\n  - uses: a\n\n# comment after a blank\npaths-ignore:\n  - x\n", "\n# comment after a blank\npaths-ignore:\n  - x\n"),
    ("name: c\nqueries:\n- uses: a\n- uses: b\npaths-ignore:\n  - x\n", "paths-ignore:\n  - x\n"),     # a block whose items sit at column 0 is still a block
])
def test_a_queries_block_in_a_shape_the_rewriter_reads_keeps_everything_around_it(tmp_path, config, expected_tail):
    leg_env(tmp_path)
    (tmp_path / "w" / CONFIG).write_text(config)
    assert run_leg_sh(tmp_path, "init", "python").returncode == 0
    out = (tmp_path / "cq" / "user-config.yaml").read_text()
    assert out.endswith(expected_tail) and sum(ln.startswith("queries:") for ln in out.splitlines()) == 1 and "uses: security-extended" in out and "uses: b" not in out and "uses: a\n" not in out


# ------------------------------------------------------------------------------------------------ the SARIF, as the analyze action judges it
def sarif(results: int = 3, rules: int = 2, **run_over) -> dict:
    return {"runs": [{"tool": {"driver": {"rules": [{"id": f"r{i}"} for i in range(rules)]}}, "results": [{"ruleId": "r0"}] * results, **run_over}]}


def check(tmp_path: Path, doc, name: str = "out.sarif", raw: str | None = None, lang: str = "python") -> tuple[int, str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    f = tmp_path / name
    f.write_text(raw if raw is not None else json.dumps(doc))
    r = subprocess.run([sys.executable, "-I", str(REAL / SARIF_CHECK), str(f), lang], capture_output=True, text=True)
    return r.returncode, r.stdout


@pytest.mark.parametrize("raw", ["", "not json", "{", "{\"runs\": [", "[1, 2]", "null", "{\"runs\": NaN}", "{\"runs\": [{\"results\": Infinity}]}", "﻿{\"runs\": []}"])
def test_a_sarif_that_does_not_parse_as_json_is_a_fail_the_action_throws_on_it(tmp_path, raw):
    rc, out = check(tmp_path, None, raw=raw)
    assert rc == 1 and "LOCALCI_CODEQL_SARIF_REJECTED language=python Invalid SARIF" in out and "LOCALCI_CODEQL_RESULTS" not in out


def test_a_sarif_file_that_is_not_there_is_a_fail(tmp_path):
    r = subprocess.run([sys.executable, "-I", str(REAL / SARIF_CHECK), str(tmp_path / "absent.sarif"), "python"], capture_output=True, text=True)
    assert r.returncode == 1 and "Invalid SARIF" in r.stdout


@pytest.mark.parametrize("doc,needle", [({}, "Missing 'runs' array"), ({"runs": None}, "Missing 'runs' array"), ({"runs": {}}, "Missing 'runs' array"),
                                        ([], "Missing 'runs' array"), ({"runs": [{}]}, "Missing 'results' array in run 0"),
                                        ({"runs": [{"results": []}, {"results": None}]}, "Missing 'results' array in run 1"),
                                        ({"runs": [{"results": {}}]}, "Missing 'results' array in run 0"), ({"runs": [None]}, "Missing 'results' array in run 0"),
                                        ({"runs": [{"tool": {}}]}, "Missing 'results' array")])
def test_a_sarif_without_runs_or_with_a_run_without_results_is_a_fail(tmp_path, doc, needle):
    rc, out = check(tmp_path, doc)
    assert rc == 1 and needle in out and "LOCALCI_CODEQL_RESULTS" not in out


def test_an_empty_runs_array_and_a_run_with_no_findings_are_valid(tmp_path):
    assert check(tmp_path / "a", {"runs": []}) == (0, "LOCALCI_CODEQL_RESULTS language=python results=0 rules=0\n")
    assert check(tmp_path / "b", sarif(results=0, rules=0))[0] == 0


def test_the_action_does_not_validate_the_codeql_schema_so_neither_does_the_check(tmp_path):
    odd = {"version": "not-a-version", "$schema": 5, "runs": [{"results": [{"unknown": 1, "locations": "x"}], "tool": "not an object", "extra": {}}]}
    assert check(tmp_path, odd)[0] == 0   # a stricter check than hosted's would be a FALSE_RED


LIMIT_CASES = {   # name -> (builder of a document at n, the documented maximum, the limit's name in the message)
    "runs per file": (lambda n: {"runs": [{"results": []}] * n}, 20, "runs per file"),
    "results per run": (lambda n: sarif(results=n, rules=0), 25_000, "results per run"),
    "rules per run": (lambda n: {"runs": [{"results": [], "tool": {"driver": {"rules": [{"id": "x"}] * n}}}]}, 25_000, "rules per run"),
    "rules per run, split between the driver and an extension": (
        lambda n: {"runs": [{"results": [], "tool": {"driver": {"rules": [{"id": "x"}] * (n - 7)}, "extensions": [{"rules": [{"id": "y"}] * 7}]}}]}, 25_000, "rules per run"),
    "tool extensions per run": (lambda n: {"runs": [{"results": [], "tool": {"extensions": [{"name": "e"}] * n}}]}, 100, "tool extensions per run"),
    "locations per result": (lambda n: {"runs": [{"results": [{"locations": [{}] * n}]}]}, 1_000, "locations per result"),
    "thread flow locations per result": (
        lambda n: {"runs": [{"results": [{"codeFlows": [{"threadFlows": [{"locations": [{}] * n}]}]}]}]}, 10_000, "thread flow locations per result"),
    "thread flow locations, summed over a result's flows": (
        lambda n: {"runs": [{"results": [{"codeFlows": [{"threadFlows": [{"locations": [{}] * (n - 3)}, {"locations": [{}] * 3}]}]}]}]}, 10_000,
        "thread flow locations per result"),
    "tags per rule": (lambda n: {"runs": [{"results": [], "tool": {"driver": {"rules": [{"id": "a"}, {"id": "b", "properties": {"tags": ["t"] * n}}]}}}]}, 20, "tags per rule"),
}


@pytest.mark.parametrize("name", sorted(LIMIT_CASES))
def test_each_documented_upload_limit_is_ok_at_the_maximum_and_a_fail_one_over(name):
    build, cap, label = LIMIT_CASES[name]
    assert checker.shape_problem(build(cap)) is None
    assert checker.limit_problems(build(cap), 1) == []
    over = checker.limit_problems(build(cap + 1), 1)
    assert len(over) == 1 and over[0].startswith(label + ": ") and f"> {cap}" in over[0], over


def test_the_limits_are_the_documented_numbers():
    assert (checker.MAX_RUNS, checker.MAX_RESULTS, checker.MAX_RULES, checker.MAX_EXTENSIONS) == (20, 25_000, 25_000, 100)
    assert (checker.MAX_THREAD_FLOW_LOCATIONS, checker.MAX_LOCATIONS, checker.MAX_TAGS, checker.GZIP_MAX_BYTES) == (10_000, 1_000, 20, 10_000_000)   # "10 MB" read the smaller way: FALSE_GREEN 0


def test_the_gzip_limit_is_ok_at_the_maximum_and_a_fail_one_byte_over_and_names_the_limit():
    doc = sarif()
    assert checker.limit_problems(doc, checker.GZIP_MAX_BYTES) == []
    over = checker.limit_problems(doc, checker.GZIP_MAX_BYTES + 1)
    assert len(over) == 1 and over[0].startswith("gzip size: ") and str(checker.GZIP_MAX_BYTES + 1) in over[0]


def test_the_gzip_size_is_what_zlib_gzipsync_makes_of_the_json_text_at_its_default_level():
    doc = sarif(results=200, automationDetails={"id": "/language:python/"})   # nothing for the action to add, so the size is the gzip alone
    text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode()
    assert checker.gzip_size(doc) == len(gzip.compress(text, compresslevel=6, mtime=0)) and checker.gzip_size(doc) < len(text)
    assert checker.gzip_size({"runs": [], "x": "é"}) == len(gzip.compress(json.dumps({"runs": [], "x": "é"}, separators=(",", ":"), ensure_ascii=False).encode(), 6, mtime=0))


def test_a_sarif_whose_gzip_is_over_ten_mb_is_a_fail_even_with_no_other_limit_exceeded(tmp_path):
    doc = sarif(results=1)
    doc["runs"][0]["results"][0]["message"] = {"text": os.urandom(11 * 1000 * 1000).hex()}   # hex of random bytes: about 4 bits a character, 11 MB gzipped
    rc, out = check(tmp_path, doc)
    assert rc == 1 and "gzip size: " in out and "10 MB per gzip-compressed file" in out and "LOCALCI_CODEQL_RESULTS language=python results=1 rules=2" in out


def lacking(n: int = 1, **run_over) -> dict:
    """A document the way the action would find it if the CLI stopped writing fingerprints and automation details."""
    loc = {"physicalLocation": {"artifactLocation": {"uri": "a.py"}, "region": {"startLine": 3}}}
    return {"runs": [{"tool": {"driver": {"rules": []}}, "results": [{"ruleId": "r", "locations": [loc]} for _ in range(n)], **run_over}]}


def test_the_gzip_limit_is_checked_on_a_bound_of_what_hosted_would_send(monkeypatch):
    doc = lacking(3)
    bound = 3 * checker.FINGERPRINT_BOUND + checker.AUTOMATION_BOUND
    assert checker.action_adds(doc) == bound == 352
    written = len(gzip.compress(json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode(), compresslevel=6, mtime=0))   # what is sent as written
    monkeypatch.setattr(checker, "GZIP_MAX_BYTES", written + 100)   # under the limit as written, over it with the bound
    problems = checker.limit_problems(doc, checker.gzip_size(doc))
    assert len(problems) == 1 and problems[0].startswith("gzip size: ")
    monkeypatch.setattr(checker, "GZIP_MAX_BYTES", written + bound)   # exactly at the bound: still accepted
    assert checker.limit_problems(doc, checker.gzip_size(doc)) == []


def test_a_real_shaped_document_every_hash_and_automation_id_present_adds_nothing():
    doc = lacking(2, automationDetails={"id": "/language:python/"})
    for res in doc["runs"][0]["results"]:
        res["partialFingerprints"] = {"primaryLocationLineHash": "0123456789abcdef:1"}
    assert checker.action_adds(doc) == 0
    text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode()
    assert checker.gzip_size(doc) == len(gzip.compress(text, compresslevel=6, mtime=0))


def test_what_the_action_would_not_fingerprint_is_not_in_the_bound():
    nowhere = {"physicalLocation": {"artifactLocation": {"uri": "a.py"}}}   # no region.startLine: fingerprints.ts skips it
    doc = {"runs": [{"automationDetails": {"id": "x"}, "results": [{"locations": [nowhere]}, {"locations": []}, {}, {"locations": [{}]}]}]}
    assert checker.action_adds(doc) == 0
    assert checker.action_adds({"runs": [{"results": []}, {"results": [], "automationDetails": None}]}) == checker.AUTOMATION_BOUND   # undefined, not null


def test_the_size_is_the_compact_serialisation_whatever_the_input_whitespace(tmp_path):
    doc = lacking(5, automationDetails={"id": "x"})
    compact, indented = tmp_path / "c.sarif", tmp_path / "i.sarif"
    compact.write_text(json.dumps(doc, separators=(",", ":")))
    indented.write_text(json.dumps(doc, indent=4))
    assert checker.gzip_size(checker.load(str(compact))[0]) == checker.gzip_size(checker.load(str(indented))[0]) == checker.gzip_size(doc)


def test_a_sarif_of_the_real_size_is_under_every_limit_and_the_results_line_is_receipt_data(tmp_path):
    results = [{"ruleId": f"r{i % 172}", "message": {"text": "m" * 80}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": f"f{i}.py"},
               "region": {"startLine": i}}}] * 3, "codeFlows": [{"threadFlows": [{"locations": [{"location": {}}] * 12}]}]} for i in range(2499)]
    doc = {"runs": [{"tool": {"driver": {"name": "CodeQL", "rules": [{"id": f"r{i}", "properties": {"tags": ["security"] * 8}} for i in range(172)]}}, "results": results}]}
    assert checker.limit_problems(doc, checker.gzip_size(doc)) == [] and checker.gzip_size(doc) < checker.GZIP_MAX_BYTES // 4
    assert check(tmp_path, doc) == (0, "LOCALCI_CODEQL_RESULTS language=python results=2499 rules=172\n")


def test_rules_are_counted_once_by_id_across_the_driver_and_its_extensions(tmp_path):
    doc = {"runs": [{"results": [], "tool": {"driver": {"rules": [{"id": "a"}, {"id": "b"}]}, "extensions": [{"rules": [{"id": "b"}, {"id": "c"}]}]}}]}
    assert check(tmp_path, doc) == (0, "LOCALCI_CODEQL_RESULTS language=javascript results=0 rules=3\n".replace("javascript", "python"))


@pytest.mark.parametrize("sarif_doc,rc,needle", [("{", 1, "Invalid SARIF"), ('{"runs": [{}]}', 1, "Missing 'results' array in run 0"), ('{"runs": []}', 0, "results=0"),
                                                 (json.dumps(sarif(results=25_001)), 1, "results per run: 25001 > 25000"), (json.dumps(sarif(results=25_000)), 0, "results=25000")])
def test_the_leg_script_exits_1_on_a_sarif_hosted_would_reject_and_0_on_one_it_takes(tmp_path, sarif_doc, rc, needle):
    f = tmp_path / "fake.sarif"
    f.write_text(sarif_doc)
    r = run_leg_sh(tmp_path, "analyze", "python", FAKE_SARIF=str(f))
    assert r.returncode == rc and needle in r.stdout
    assert len((tmp_path / "codeql.argv").read_text().splitlines()) == 4   # the four commands ran; only the judgement of their SARIF differs


def test_a_driven_leg_whose_sarif_hosted_would_reject_is_a_fail_and_findings_alone_never_are(tmp_path, monkeypatch):
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    bad = tmp_path / "bad.sarif"
    bad.write_text("{")
    steps, rc = drive_planned(tmp_path / "bad", spec, FAKE_SARIF=str(bad))
    status, reason = runner.steps_verdict(combined(steps), spec)
    assert rc == 1 and status == "FAIL" and "Perform CodeQL Analysis" in reason
    many = tmp_path / "many.sarif"
    many.write_text(json.dumps(sarif(results=24_999)))
    steps, rc = drive_planned(tmp_path / "many", spec, FAKE_SARIF=str(many))
    assert rc == 0 and runner.steps_verdict(combined(steps), spec)[0] == "PASS"


def test_the_checker_is_a_base_judge_laid_over_the_candidate_tree(tmp_path, monkeypatch):
    liar = "import sys\nsys.exit(0)\n"
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", {SARIF_CHECK: liar, **PY_CHANGE})
    assert spec["judge_modified"] == [SARIF_CHECK] and SARIF_CHECK in spec["overlay"]
    steps, _ = drive_planned(tmp_path, spec)
    status, reason = runner.steps_verdict(combined(steps), spec)
    assert status == "BLOCKED" and SARIF_CHECK in reason   # the candidate's checker is not the one that judged


# ------------------------------------------------------------------------------------------------ the checker's own crash is no verdict
def test_a_document_the_checker_cannot_hold_is_no_verdict_exit_70_never_the_exit_1_of_a_rejection(tmp_path):
    deep = tmp_path / "deep.sarif"
    deep.write_text('{"runs":' + "[" * 400_000 + "]" * 400_000 + "}")
    r = subprocess.run([sys.executable, "-I", str(REAL / SARIF_CHECK), str(deep), "python"], capture_output=True, text=True)
    assert r.returncode == checker.NO_VERDICT_RC == 70 and "REJECTED" not in r.stdout and "CRASHED" in r.stderr and "RecursionError" in r.stderr


@pytest.mark.parametrize("exc", [RecursionError, MemoryError, UnicodeEncodeError])
def test_every_crash_of_the_checker_itself_is_exit_70(tmp_path, monkeypatch, capsys, exc):
    f = tmp_path / "ok.sarif"
    f.write_text(json.dumps(sarif()))

    def boom(*a):
        raise exc("x") if exc is not UnicodeEncodeError else UnicodeEncodeError("utf-8", "x", 0, 1, "surrogate")
    monkeypatch.setattr(checker, "gzip_size", boom)
    assert checker.main([str(f), "python"]) == 70
    assert "no verdict" in capsys.readouterr().err
    monkeypatch.setattr(checker, "load", boom)
    assert checker.main([str(f), "python"]) == 70   # a UnicodeEncodeError is a ValueError, and load() must not read it as an unparsable file


def test_the_leg_turns_a_checker_crash_into_a_killed_leg_and_the_driver_reads_it_as_error(tmp_path, monkeypatch):
    """The exit-code map end to end: the pin mismatch and the checker's crash both end the leg in its no-verdict signal, which the driver
    classifies ERROR (exit 4), never FAIL (a red exit) and never PASS."""
    spec, _ = plan_codeql(tmp_path, monkeypatch, "python", PY_CHANGE)
    deep = tmp_path / "deep.sarif"
    deep.write_text('{"runs":' + "[" * 400_000 + "]" * 400_000 + "}")
    r = run_leg_sh(tmp_path / "direct", "analyze", "python", FAKE_SARIF=str(deep))
    assert r.returncode == -9 and "no verdict" in r.stderr
    for name, extra, idx in (("crash", {"FAKE_SARIF": str(deep)}, 2), ("pin", {"FAKE_VERSION": "2.27.3"}, 0)):
        steps, rc = drive_planned(tmp_path / name, spec, **extra)
        status, reason = runner.steps_verdict(combined(steps), spec)
        assert rc == 4 and steps[idx]["status"] == "ERROR" and status == "ERROR", (name, steps, reason)
