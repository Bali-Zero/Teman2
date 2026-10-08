"""B6: merger.py prune — the gate removes what it wrote, by rule, and journals it."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

from .fixture_repo import runner

_DIR = Path(runner.__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_b6_under_test", _DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pm, mg = _load("prune"), _load("merger")
NOW = time.time()
H = 3600
FAKE = r'''#!{py}
import json, sys
world = json.load(open({world!r}))
open({log!r}, "a").write(" ".join(sys.argv[1:]) + "\n")
a = sys.argv[1:]
if a[:2] == ["image", "ls"]:
    print("\n".join([im["tag"] for im in world["images"]] + world.get("others", [])))
elif a[:2] == ["image", "inspect"]:
    im = next((i for i in world["images"] if i["tag"] == a[-1]), None)
    if im is None:
        sys.exit(1)
    print(f"{{im['id']}}|{{im['created']}}|{{im['size']}}|{{json.dumps(im.get('labels') or None)}}")
elif a[:2] == ["image", "rm"]:
    sys.exit(1 if a[-1] in world.get("busy", []) else 0)
elif a[:1] == ["run"] and "df" in a:
    print("Filesystem 1024-blocks Used Available Capacity Mounted on\noverlay 61609772 30000000 31609772 49% /")
'''


def iso(age_h: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.123456789Z", time.gmtime(NOW - age_h * H))


def image(tag16: str, age_h: float, recipe: str | None = None, gb: float = 9.85) -> dict:
    return {"tag": f"localci-deps:{tag16}", "id": "sha256:" + (tag16 * 4), "created": iso(age_h), "size": int(gb * 1e9),
            "labels": {"org.nuzantara.localci.deps": "d" * 64, **({"org.nuzantara.localci.recipe": recipe} if recipe else {})}}


def world(tmp_path: Path, images: list, plans: dict | None = None, **extra) -> tuple[Path, str]:
    """A merger state dir whose runs hold `plans` ({run name: (age_h, {check: tag})}) and a docker that knows `images`."""
    state = tmp_path / "state"
    (state / "runs").mkdir(parents=True)
    (state / "repo").write_text("o/r\n")
    for run, (age_h, uses) in (plans or {}).items():
        p = state / "runs" / run / "state" / "plan.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"checks": {chk: {"kind": "contained_jobs", "jobs": [{"job_id": "j", "deps": f"deps {tag} (3 pins + [])"}]}
                                            for chk, tag in uses.items()}}))
        os.utime(p, (NOW - age_h * H, NOW - age_h * H))
    w = tmp_path / "world.json"
    w.write_text(json.dumps({"images": images, **extra}))
    exe = tmp_path / "docker"
    exe.write_text(FAKE.format(py=sys.executable, world=str(w), log=str(tmp_path / "docker.log")))
    exe.chmod(0o755)
    return state, str(exe)


def calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "docker.log"
    return log.read_text().splitlines() if log.exists() else []


def decided(state: Path, docker: str) -> dict:
    recent, ids, recipes = pm.plan_refs(state / "runs", NOW)
    return {d["tag"]: d for d in pm.image_decisions(pm.deps_images(docker), recent, ids, recipes, NOW)}


def test_an_image_a_plan_named_47_hours_ago_is_kept_and_one_unnamed_for_three_days_goes(tmp_path):
    imgs = [image("a" * 16, 80, "backend-tests"), image("b" * 16, 72, "backend-tests"), image("c" * 16, 50, "backend-tests")]
    state, docker = world(tmp_path, imgs, {"pr1-x-20261006T120000Z": (47, {"ctx.backend-tests": imgs[0]["tag"]})})
    d = decided(state, docker)
    assert d[imgs[0]["tag"]]["remove"] is False and "named by a plan of the last 48 h (47.0 h ago)" in d[imgs[0]["tag"]]["rule"]
    assert d[imgs[1]["tag"]]["remove"] is True and d[imgs[1]["tag"]]["rule"] == (
        f"no plan of the last 48 h names it, built 72.0 h ago, not the newest of recipe backend-tests (newest {imgs[2]['tag']})")
    assert d[imgs[2]["tag"]]["remove"] is False and d[imgs[2]["tag"]]["rule"] == "the newest image of recipe backend-tests"


def test_a_plan_older_than_48_hours_names_nothing_and_the_recipe_comes_from_it_when_no_label_says(tmp_path):
    imgs = [image("a" * 16, 100), image("b" * 16, 60)]   # no recipe label: built before B6
    state, docker = world(tmp_path, imgs, {"pr1-x-20261005T000000Z": (49, {"ctx.e2e-tests": imgs[0]["tag"], "ctx.visa-oracle-smoke": imgs[0]["tag"]}),
                                           "pr2-x-20261006T000000Z": (60, {"ctx.e2e-tests": imgs[1]["tag"]})})
    d = decided(state, docker)
    assert d[imgs[0]["tag"]]["recipe"] == d[imgs[1]["tag"]]["recipe"] == "e2e-tests"
    assert d[imgs[0]["tag"]]["remove"] is True and d[imgs[1]["tag"]]["remove"] is False


def test_the_newest_of_a_recipe_is_kept_with_no_reference_and_a_young_image_is_kept_unreferenced(tmp_path):
    imgs = [image("a" * 16, 200, "frontend-tests-mouth", 1.4), image("b" * 16, 30, "backend-tests"), image("c" * 16, 10, "backend-tests")]
    d = decided(*world(tmp_path, imgs))
    assert d[imgs[0]["tag"]]["remove"] is False and d[imgs[0]["tag"]]["rule"] == "the newest image of recipe frontend-tests-mouth"
    assert d[imgs[1]["tag"]]["remove"] is False and d[imgs[1]["tag"]]["rule"] == "built 30.0 h ago, under 48 h"


def test_an_image_whose_recipe_nothing_records_is_its_own_newest_and_stays(tmp_path):
    d = decided(*world(tmp_path, [image("a" * 16, 300)]))
    assert d["localci-deps:" + "a" * 16]["remove"] is False and d["localci-deps:" + "a" * 16]["recipe"] == "unknown:localci-deps:" + "a" * 16


@pytest.mark.parametrize("tag", ["localci-candidate:1", "localci-deps-base:2c9b1d54104db6cd", "postgres:15"])
def test_the_candidate_and_base_images_are_never_in_a_removal_set(tmp_path, tag):
    assert pm.never(tag) is True
    im = {**image("a" * 16, 300, "backend-tests"), "tag": tag, "created": NOW - 300 * H, "label_recipe": "backend-tests"}
    young = {**image("b" * 16, 10, "backend-tests"), "created": NOW - 10 * H, "label_recipe": "backend-tests"}
    rows = pm.image_decisions([im, young], {}, set(), {}, NOW)
    assert rows[0]["remove"] is False and rows[0]["rule"].startswith("never-list")
    state, docker = world(tmp_path, [image("b" * 16, 300, "backend-tests"), image("c" * 16, 10, "backend-tests")],
                          others=["localci-candidate:1", "localci-deps-base:2c9b1d54104db6cd"])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 0
    assert [c for c in calls(tmp_path) if c.startswith("image rm")] == ["image rm localci-deps:" + "b" * 16]


def journal(state: Path) -> list[dict]:
    return [json.loads(ln) for ln in (state / "decisions.jsonl").read_text().splitlines()]


def test_prune_removes_by_tag_prunes_the_builder_and_journals_what_went_by_which_rule(tmp_path, capsys):
    imgs = [image("a" * 16, 80, "backend-tests"), image("b" * 16, 10, "backend-tests")]
    state, docker = world(tmp_path, imgs)
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 0
    line = journal(state)[-1]
    assert line["kind"] == "prune" and line["dry_run"] is False
    assert line["images"]["removed"] == [{"tag": imgs[0]["tag"], "gb": 9.85, "rule": imgs and line["images"]["removed"][0]["rule"]}]
    assert "not the newest of recipe backend-tests" in line["images"]["removed"][0]["rule"]
    assert line["images"]["kept"] == [{"tag": imgs[1]["tag"], "rule": "built 10.0 h ago, under 48 h"}] and line["images"]["errors"] == []
    assert line["vm_free_gb"] == {"before": 32.4, "after": 32.4} and set(line["host_free_gb"]) == {"before", "after"}
    rm = [c for c in calls(tmp_path) if c.startswith(("image rm", "builder prune"))]
    assert rm == [f"image rm {imgs[0]['tag']}", "builder prune -f --filter until=24h"]   # by explicit tag, never -a, never until= on images
    assert "merger prune: images_removed=1 image_errors=0" in capsys.readouterr().out


def test_a_dry_run_removes_nothing_and_journals_the_would_list(tmp_path):
    imgs = [image("a" * 16, 80, "backend-tests"), image("b" * 16, 10, "backend-tests")]
    state, docker = world(tmp_path, imgs)
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--dry-run"]) == 0
    line = journal(state)[-1]
    assert line["dry_run"] is True and [r["tag"] for r in line["images"]["would_remove"]] == [imgs[0]["tag"]] and "removed" not in line["images"]
    assert not [c for c in calls(tmp_path) if c.startswith(("image rm", "builder prune"))]


def test_nothing_to_remove_prunes_no_builder_and_an_image_in_use_is_an_error_never_forced(tmp_path):
    state, docker = world(tmp_path, [image("a" * 16, 10, "backend-tests")])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 0
    assert not [c for c in calls(tmp_path) if c.startswith("builder")] and journal(state)[-1]["images"]["removed"] == []
    imgs = [image("b" * 16, 80, "backend-tests"), image("c" * 16, 10, "backend-tests")]
    state, docker = world(tmp_path / "busy", imgs, busy=[imgs[0]["tag"]])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 1
    assert [e["tag"] for e in journal(state)[-1]["images"]["errors"]] == [imgs[0]["tag"]]
    assert not any("-f" in c.split() for c in calls(tmp_path / "busy") if c.startswith("image rm"))


def test_prune_refuses_a_directory_that_is_not_a_merger_state(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    assert mg.main(["prune", "--state-dir", str(tmp_path / "elsewhere"), "--docker", "/nonexistent"]) == 2


def test_the_deps_build_labels_the_recipe_it_built(tmp_path):
    from .test_service_contexts import fake_docker
    exe = fake_docker(tmp_path)
    (tmp_path / "logs").mkdir()
    runner.plan_deps_image(tmp_path, "c" * 40, {"image_id": "sha256:" + "a" * 64, "docker": str(exe)}, {"packages": ["pytest"]}, "",
                           tmp_path, "backend-tests")
    build = [ln for ln in (tmp_path / "docker.argv").read_text().splitlines() if ln.startswith("build ")]
    assert build and "--label org.nuzantara.localci.recipe=backend-tests" in build[0]
