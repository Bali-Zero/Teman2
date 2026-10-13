"""Stand-in services the matrix adds beside BASE's (E2E's local Qdrant): digest-pinned, present, healthy or BLOCKED, values made up per leg."""
from __future__ import annotations

import re

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
