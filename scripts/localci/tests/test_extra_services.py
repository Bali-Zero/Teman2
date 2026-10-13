"""Stand-in services the matrix adds beside BASE's (E2E's local Qdrant): digest-pinned, present, healthy or BLOCKED, values made up per leg."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from .fixture_repo import runner
from .test_service_contexts import IMAGES, SVC, fake_docker

pytestmark = pytest.mark.usefixtures("fake_env")
DIGEST = "sha256:" + "c" * 64
REF = f"qdrant/qdrant@{DIGEST}"
EXTRA = {"name": "qdrant", "image": REF, "env": {"QDRANT__SERVICE__API_KEY": "$LOCALCI_GEN.qdrant"},
         "health": {"cmd": "true", "interval": "1s", "timeout": "1s", "retries": "2"}}


def docker_knowing(tmp_path, health: str = "healthy") -> str:
    exe = fake_docker(tmp_path, health)
    exe.write_text(exe.read_text().replace("postgres:15|redis:7)", f"postgres:15|redis:7|{REF})"))
    return str(exe)


def test_a_stand_in_is_pinned_by_digest_present_locally_and_shaped_like_a_base_service(tmp_path):
    svcs, why = runner.plan_extra_services([EXTRA], {"postgres"}, docker_knowing(tmp_path))
    assert why is None and svcs[0]["image_id"] == "sha256:" + "a" * 64 and svcs[0]["image"] == REF and svcs[0]["health_budget_s"] > 0
    assert svcs[0]["env"] == EXTRA["env"] and set(svcs[0]) == {"name", "image", "local_image", "image_id", "env", "ports", "health", "health_budget_s"}


@pytest.mark.parametrize("change,needle", [
    ({"image": "qdrant/qdrant:v1.17.0"}, "not pinned by digest"),                       # a tag moves
    ({"image": "qdrant/qdrant@sha256:" + "d" * 64}, "not present locally"),            # never pulled by a run
    ({"name": "postgres"}, "already a service"),
    ({"name": "Q d"}, "not a plain name"),
    ({"env": {"K": "${{ secrets.K }}"}}, "carry expressions"),
    ({"health": {"cmd": "true"}}, "health needs exactly"),
    ({"health": {**EXTRA["health"], "retries": "many"}}, "health unreadable"),
    ({"ports": ["6333:6333"]}, "mapping of"),                                           # a key the runner does not read is refused, not ignored
])
def test_a_stand_in_the_runner_cannot_reproduce_is_blocked_naming_why(tmp_path, change, needle):
    svcs, why = runner.plan_extra_services([{**EXTRA, **change}], {"postgres"}, docker_knowing(tmp_path))
    assert svcs is None and needle in why


def test_no_extra_services_is_no_change_and_a_non_list_is_refused(tmp_path):
    docker = docker_knowing(tmp_path)
    assert runner.plan_extra_services(None, set(), docker) == ([], None) and runner.plan_extra_services([], set(), docker) == ([], None)
    assert runner.plan_extra_services({"name": "q"}, set(), docker)[0] is None


def test_a_generated_value_is_random_per_leg_shared_by_name_and_never_a_literal():
    a, b = {}, {}
    ea = runner.fill_generated({"X": "$LOCALCI_GEN.qdrant", "Y": "$LOCALCI_GEN.qdrant", "Z": "sk-$LOCALCI_GEN.openai", "L": "literal"}, a)
    eb = runner.fill_generated({"X": "$LOCALCI_GEN.qdrant"}, b)
    assert ea["X"] == ea["Y"] and re.fullmatch(r"[0-9a-f]{48}", ea["X"]) and ea["X"] != eb["X"]
    assert re.fullmatch(r"sk-[0-9a-f]{48}", ea["Z"]) and ea["Z"] != "sk-" + ea["X"] and ea["L"] == "literal" and set(a) == {"qdrant", "openai"}
    assert runner.fill_generated({"X": "$LOCALCI_GEN.qdrant"}, a)["X"] == ea["X"]   # the services started later read the same store


def test_the_stand_in_joins_the_job_netns_with_the_value_the_steps_get_and_no_sentinel_reaches_docker(tmp_path):
    docker = docker_knowing(tmp_path)
    base, _ = runner.plan_services({"services": {"postgres": SVC}}, IMAGES, docker)
    extra, _ = runner.plan_extra_services([EXTRA], {"postgres"}, docker)
    gen = {}
    steps_env = runner.fill_generated({"QDRANT_API_KEY": "$LOCALCI_GEN.qdrant"}, gen)
    svcs = [{**s, "env": runner.fill_generated(s["env"], gen)} for s in base + extra]
    names, owner, why = runner.start_services(docker, svcs, "localci-t", "lbl", runner.trusted_env(), tmp_path / "log")
    runs = [ln for ln in (tmp_path / "docker.argv").read_text().splitlines() if ln.startswith("run -d")]
    assert why is None and len(runs) == 2 and f"--network container:{owner}" in runs[1] and "--network none" in runs[0]
    assert f"--env=QDRANT__SERVICE__API_KEY={steps_env['QDRANT_API_KEY']}" in runs[1] and "LOCALCI_GEN" not in "\n".join(runs)


def test_a_stand_in_that_is_not_healthy_is_no_verdict_not_green_and_is_handed_back_for_removal(tmp_path):
    docker = docker_knowing(tmp_path, health="unhealthy")
    extra, _ = runner.plan_extra_services([EXTRA], set(), docker)
    names, owner, why = runner.start_services(docker, extra, "localci-t", "lbl", runner.trusted_env(), tmp_path / "log")
    assert why and "'unhealthy'" in why and names == [owner]   # the caller turns a `why` into BLOCKED: infra, never a code RED


def _planned(tmp_path, monkeypatch, extra: list, known: bool) -> dict:
    from . import fixture_repo as fr
    from . import test_service_contexts as sc

    def fake(tp, health="healthy"):
        exe = fake_docker(tp, health)
        if known:
            exe.write_text(exe.read_text().replace("postgres:15|redis:7)", f"postgres:15|redis:7|{REF})"))
        return exe

    monkeypatch.setattr(sc, "fake_docker", fake)
    ctx = sc.svc_ctx(jobs=[{"job_id": "unit", "extra_services": extra, "steps": [{"workflow_step": "test"}]}])
    return sc.planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, ctx)


def test_a_planned_job_carries_the_stand_in_after_base_services_and_a_missing_image_blocks_the_whole_context(tmp_path, monkeypatch):
    spec = _planned(tmp_path / "ok", monkeypatch, [EXTRA], known=True)
    assert [s["name"] for s in spec["jobs"][0]["services"]] == ["postgres", "qdrant"] and spec["jobs"][0]["services"][1]["image"] == REF
    spec = _planned(tmp_path / "gone", monkeypatch, [EXTRA], known=False)
    assert spec["status"] == "BLOCKED" and "not present locally" in spec["reason"] and "docker pull" in spec["reason"]


# ------------------------------------------------------------------ the real E2E context
def _e2e() -> dict:
    import yaml
    from .test_service_contexts import MATRIX

    return next(c for c in yaml.safe_load(MATRIX.read_text())["contexts"] if c["name"] == "E2E Tests (Playwright)")["local"]


def test_the_real_e2e_context_feeds_the_backend_a_stand_in_for_each_secret_and_holds_no_key_shaped_literal(tmp_path):
    import yaml
    from . import fixture_repo as fr

    local = _e2e()
    backend = next(s for s in local["steps"] if s["workflow_step"].startswith("Start backend"))["env"]
    base = yaml.safe_load((fr.REAL_REPO / ".github/workflows/tests.yml").read_text())["jobs"]["e2e-tests"]["steps"]
    base_env = next(s for s in base if s.get("name", "").startswith("Start backend"))["env"]
    assert set(backend) == {"QDRANT_URL", "QDRANT_API_KEY", "OPENAI_API_KEY", "JWT_SECRET"} <= set(base_env)   # a renamed BASE var is seen here, not fed to nothing
    assert all(v for v in backend.values()) and backend["QDRANT_URL"] == "http://localhost:6333"
    assert all(re.fullmatch(r"(sk-)?\$LOCALCI_GEN\.[a-z]+", v) for k, v in backend.items() if k != "QDRANT_URL")   # made up at the leg, never written here
    svc = local["extra_services"][0]
    assert svc["env"] == {"QDRANT__SERVICE__API_KEY": backend["QDRANT_API_KEY"]}   # the service starts with the key the backend sends
    run_env = next(s for s in local["steps"] if s["workflow_step"] == "Run E2E tests")["env"]
    assert run_env == {"E2E_TEST_EMAIL": "", "E2E_TEST_PIN": ""}   # BASE's 135 selected tests never read them (matrix note)
    svcs, why = runner.plan_extra_services(local["extra_services"], {"postgres", "redis"}, docker_knowing_ref(tmp_path, svc["image"]),
                                           lambda rel: (fr.REAL_REPO / rel).read_bytes())
    assert why is None and svcs[0]["image"] == svc["image"] and svc["image"].startswith("qdrant/qdrant@sha256:")
    assert svcs[0]["seed"] == {"collection": "knowledge_base", "size": 1536, "distance": "Cosine", "api_key_env": "QDRANT__SERVICE__API_KEY"}


def docker_knowing_ref(tmp_path, ref: str) -> str:
    exe = fake_docker(tmp_path)
    exe.write_text(exe.read_text().replace("postgres:15|redis:7)", f"postgres:15|redis:7|{ref})"))
    return str(exe)


def test_a_leg_hands_the_stand_in_and_the_steps_the_same_made_up_value_and_nothing_is_left_unexpanded(monkeypatch, tmp_path):
    import json

    from .test_host_disk import _leg_args

    seen = {}
    monkeypatch.setenv(runner.MIN_FREE_ENV, "0")
    monkeypatch.setattr(runner, "start_services", lambda docker, svcs, *a, **k: seen.setdefault("svcs", svcs) and ([], None, None))
    monkeypatch.setattr(runner, "execute_contained", lambda *a, **k: seen.setdefault("extra", a[6]) and (None, "stopped by the test"))
    spec, job, plan = _leg_args(tmp_path)
    job.update(git_index=False, services=[{"name": "qdrant", "env": dict(EXTRA["env"]), "image_id": "sha256:" + "a" * 64}],
               steps=[{"name": "s", "argv": ["true"], "env": {"QDRANT_API_KEY": "$LOCALCI_GEN.qdrant", "OPENAI_API_KEY": "sk-$LOCALCI_GEN.openai"}}])
    runner._run_leg("ctx.e2e-tests", spec, job, {}, tmp_path, plan, {}, {}, runner._gh_expr())
    step_env = json.loads(seen["extra"]["cfg/steps.json"])["steps"][0]["env"]
    key = seen["svcs"][0]["env"]["QDRANT__SERVICE__API_KEY"]
    assert re.fullmatch(r"[0-9a-f]{48}", key) and step_env["QDRANT_API_KEY"] == key and re.fullmatch(r"sk-[0-9a-f]{48}", step_env["OPENAI_API_KEY"])


# ------------------------------------------------------------------ the seed: one empty collection, named and sized by BASE
CONFIG = b'class Settings:\n    qdrant_collection_name: str = "knowledge_base"\n    embedding_dimensions: int = 1536\n'
SEED = {"file": "cfg.py", "class": "Settings", "name_field": "qdrant_collection_name", "size_field": "embedding_dimensions",
        "distance": "Cosine", "api_key_env": "QDRANT__SERVICE__API_KEY"}


def test_the_seed_is_what_base_settings_declare_read_as_data_and_frozen_in_the_plan(tmp_path):
    got, why = runner.read_seed(SEED, lambda rel: CONFIG)
    assert why is None and got == {"collection": "knowledge_base", "size": 1536, "distance": "Cosine", "api_key_env": "QDRANT__SERVICE__API_KEY"}
    svcs, why = runner.plan_extra_services([{**EXTRA, "seed": SEED}], set(), docker_knowing(tmp_path), lambda rel: CONFIG)
    assert why is None and svcs[0]["seed"]["collection"] == "knowledge_base"


@pytest.mark.parametrize("blob,seed,needle", [
    (None, SEED, "absent from BASE"),
    (b"class Other:\n    x: int = 1\n", SEED, "unreadable"),
    (b"class Settings:\n    qdrant_collection_name: str = 'a/b'\n    embedding_dimensions: int = 1536\n", SEED, "no plain"),    # a name that is a path
    (b"class Settings:\n    qdrant_collection_name: str = 'k'\n    embedding_dimensions: int = 0\n", SEED, "no plain"),
    (b"class Settings:\n    qdrant_collection_name: str = 'k'\n    embedding_dimensions: int = True\n", SEED, "no plain"),
    (b"class Settings:\n    qdrant_collection_name: str = os.getenv('K')\n    embedding_dimensions: int = 1\n", SEED, "no plain"),
    (CONFIG, {**SEED, "distance": "x; rm"}, "unreadable"),
    (CONFIG, {k: v for k, v in SEED.items() if k != "class"}, "needs exactly"),
])
def test_a_seed_BASE_does_not_declare_plainly_is_refused(blob, seed, needle):
    got, why = runner.read_seed(seed, lambda rel: blob)
    assert got is None and needle in why


def test_a_seed_whose_key_is_not_in_the_service_env_is_refused(tmp_path):
    svcs, why = runner.plan_extra_services([{**EXTRA, "env": {}, "seed": SEED}], set(), docker_knowing(tmp_path), lambda rel: CONFIG)
    assert svcs is None and "api_key_env" in why


def test_the_seed_runs_in_the_healthy_container_with_its_own_key_and_a_failed_seed_is_no_verdict(tmp_path):
    docker = docker_knowing(tmp_path)
    exe = tmp_path / "bin" / "docker"
    exe.write_text(exe.read_text().replace('  *) exit 0;;', '  exec\\ *) echo seeded;;\n  *) exit 0;;', 1))
    extra, _ = runner.plan_extra_services([{**EXTRA, "seed": SEED}], set(), docker, lambda rel: CONFIG)
    names, owner, why = runner.start_services(docker, extra, "e2eh", "lbl", runner.trusted_env(), tmp_path / "log")
    argv = (tmp_path / "docker.argv").read_text()   # the script has newlines: the fake logs it over several lines
    assert why is None and argv.count("\nexec ") + argv.startswith("exec ") == 1
    assert "PUT /collections/knowledge_base" in argv and '"size":1536' in argv and "$QDRANT__SERVICE__API_KEY" in argv
    assert "seeded empty collection knowledge_base (1536, Cosine): ok" in (tmp_path / "log").read_text()
    exe.write_text(exe.read_text().replace('echo seeded;;', 'exit 1;;'))   # the container refuses: the context has no verdict, never a green on an unseeded stand-in
    names, owner, why = runner.start_services(docker, extra, "e2eh2", "lbl", runner.trusted_env(), tmp_path / "log2")
    assert why and "could not be seeded" in why and names


def test_the_seed_a_plan_freezes_is_the_one_in_base_whatever_the_candidate_writes(tmp_path, monkeypatch):
    import yaml

    from . import test_service_contexts as sc

    evil = CONFIG.replace(b"knowledge_base", b"evil").replace(b"1536", b"7")
    orig = sc.fake_docker

    def fake(tp, health="healthy"):
        exe = orig(tp, health)
        exe.write_text(exe.read_text().replace("postgres:15|redis:7)", f"postgres:15|redis:7|{REF})"))
        return exe

    monkeypatch.setattr(sc, "fake_docker", fake)
    ctx = sc.svc_ctx(jobs=[{"job_id": "unit", "extra_services": [{**EXTRA, "seed": {**SEED, "file": "cfg.py"}}], "steps": [{"workflow_step": "test"}]}])
    spec = sc.planned_svc(tmp_path, monkeypatch, {"cfg.py": evil.decode()}, ctx, {sc.WF: yaml.safe_dump(sc.WORKFLOW), "cfg.py": CONFIG.decode()})
    assert spec["jobs"][0]["services"][1]["seed"]["collection"] == "knowledge_base" and spec["jobs"][0]["services"][1]["seed"]["size"] == 1536


# ------------------------------------------------------------------ the gates after the run: the stand-in was asked, the skips are BASE's
REACHED = {"request": "GET /collections", "min": 1, "api_key_env": "QDRANT__SERVICE__API_KEY"}


@pytest.mark.parametrize("change", [{"request": "GET /a b"}, {"request": "DELETE /collections"}, {"min": 0}, {"min": True}, {"api_key_env": "OTHER"}, {"extra": 1}])
def test_a_reached_gate_the_runner_cannot_read_is_refused(tmp_path, change):
    svcs, why = runner.plan_extra_services([{**EXTRA, "reached": {**REACHED, **change}}], set(), docker_knowing(tmp_path))
    assert svcs is None and "reached needs exactly" in why
    ok, why = runner.plan_extra_services([{**EXTRA, "reached": REACHED}], set(), docker_knowing(tmp_path))
    assert why is None and ok[0]["reached"] == REACHED


@pytest.mark.parametrize("body,want", [
    ('{"result":{"requests":{"rest":{"responses":{"GET /collections":{"200":{"count":3},"401":{"count":9}}}}}}}', 3),   # only 2xx answers count
    ('{"result":{"requests":{"rest":{"responses":{"PUT /collections/k":{"200":{"count":1}}}}}}}', 0),                   # the seed's PUT is not the backend's GET
    ('{"result":{"requests":{"rest":{"responses":{}}}}}', 0),
    ("not json", None), ("", None), ('{"result":{}}', None),
])
def test_the_stand_ins_own_count_of_a_request_is_read_from_its_telemetry(tmp_path, body, want):
    exe = fake_docker(tmp_path)
    exe.write_text(exe.read_text().replace("  *) exit 0;;", f"  exec\\ *) echo '{body}';;\n  *) exit 0;;", 1))
    assert runner.requests_seen(str(exe), "ctr", REACHED) == want


def _leg(monkeypatch, tmp_path, *, seen, log_text="", pw=None, services=True):
    from .test_host_disk import _leg_args

    junit_ok = [{"name": "s", "status": "PASS", "reason": "rc=0", "cpu": 0.0}]
    monkeypatch.setenv(runner.MIN_FREE_ENV, "0")
    monkeypatch.setattr(runner, "start_services", lambda docker, svcs, *a, **k: (["c1"] if services else [], None, None))
    monkeypatch.setattr(runner, "requests_seen", lambda docker, ctr, reached: seen)

    def execute(*a, **k):
        Path(a[8]).write_text(Path(a[8]).read_text() + log_text)
        return 0, None
    monkeypatch.setattr(runner, "execute_contained", execute)
    monkeypatch.setattr(runner, "parse_expr_junit", lambda p: junit_ok)
    spec, job, plan = _leg_args(tmp_path)
    job.update(git_index=False, steps=[{"name": "s", "argv": ["true"]}], **({"playwright_skips": pw} if pw else {}),
               services=[{"name": "qdrant", "env": {}, "image_id": "sha256:" + "a" * 64, "reached": REACHED}] if services else [])
    return runner._run_leg("ctx.e2e-tests", spec, job, {}, tmp_path, plan, {}, {}, runner._gh_expr())


@pytest.mark.parametrize("seen,blocked", [(0, True), (None, True), (1, False), (14, False)])
def test_a_stand_in_the_backend_never_asked_makes_a_passing_run_no_verdict(monkeypatch, tmp_path, seen, blocked):
    out = _leg(monkeypatch, tmp_path, seen=seen)
    assert (out["infra"] is not None and out["infra"][0] == "BLOCKED" and "never reached it" in out["infra"][1]) if blocked else out["infra"] is None


SUMMARY = "##[localci] step 1: Run E2E tests\n{body}\n##[localci] step 1 rc=0\n"


@pytest.mark.parametrize("body,max_,blocked", [
    ("  135 passed (1.2m)", 0, False),
    ("  1 skipped\n  134 passed (1.2m)", 0, True),            # a cred-gated test.skip: hosted runs it
    ("  1 skipped\n  134 passed (1.2m)", 1, False),
    ("  134 passed (1.2m)\n  1 flaky", 0, False),
    ("no summary at all", 0, True),                           # nothing to count is not a pass
])
def test_a_run_that_skipped_more_than_bases_selection_does_is_no_verdict(monkeypatch, tmp_path, body, max_, blocked):
    out = _leg(monkeypatch, tmp_path, seen=1, log_text=SUMMARY.format(body=body), pw={"step": "Run E2E tests", "max": max_}, services=False)
    assert (out["infra"] is not None and out["infra"][0] == "BLOCKED" and "never PASS" in out["infra"][1]) if blocked else out["infra"] is None


def test_the_summary_is_the_steps_own_last_one_and_a_line_a_test_printed_earlier_does_not_count():
    forged = "##[localci] step 1: Run E2E tests\n  0 skipped\n  9 passed\n  5 skipped\n  8 passed (1m)\n##[localci] step 1 rc=0\n  0 skipped\n"
    assert runner.step_summary(forged, "Run E2E tests") == {"passed": 8, "skipped": 5}
    assert runner.step_summary("##[localci] step 1: other\n  1 passed\n", "Run E2E tests") is None


def test_two_legs_never_share_a_made_up_value_and_every_container_is_on_none_or_the_job_netns(monkeypatch, tmp_path):
    import json

    keys = []
    for i in range(2):
        seen = {}
        from .test_host_disk import _leg_args
        monkeypatch.setenv(runner.MIN_FREE_ENV, "0")
        monkeypatch.setattr(runner, "start_services", lambda docker, svcs, *a, **k: seen.setdefault("svcs", svcs) and ([], None, None))
        monkeypatch.setattr(runner, "execute_contained", lambda *a, **k: seen.setdefault("extra", a[6]) and (None, "stopped"))
        (tmp_path / f"l{i}").mkdir()
        spec, job, plan = _leg_args(tmp_path / f"l{i}")
        job.update(git_index=False, services=[{"name": "q", "env": dict(EXTRA["env"]), "image_id": "sha256:" + "a" * 64}],
                   steps=[{"name": "s", "argv": ["true"], "env": {"K": "$LOCALCI_GEN.qdrant"}}])
        runner._run_leg("ctx.e2e-tests", spec, job, {}, tmp_path / f"l{i}", plan, {}, {}, runner._gh_expr())
        keys.append(json.loads(seen["extra"]["cfg/steps.json"])["steps"][0]["env"]["K"])
    assert keys[0] != keys[1]
    src = Path(runner.__file__).read_text()
    started = src.split("def start_services")[1].split("def _collect_dir")[0]
    assert started.count('"--network", f"container:{owner}" if owner else "none"') == 1 and "bridge" not in started   # the first service owns a none netns, the rest join it
