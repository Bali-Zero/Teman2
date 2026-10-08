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
    recent, ids, recipes, _ = pm.plan_refs(state / "runs", NOW)
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


def test_the_builder_is_pruned_with_nothing_to_remove_and_an_image_in_use_is_an_error_never_forced(tmp_path):
    state, docker = world(tmp_path, [image("a" * 16, 10, "backend-tests")])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 0
    assert [c for c in calls(tmp_path) if c.startswith("builder")] == ["builder prune -f --filter until=24h"]
    assert journal(state)[-1]["images"]["removed"] == [] and journal(state)[-1]["failed"] == []
    imgs = [image("b" * 16, 80, "backend-tests"), image("c" * 16, 10, "backend-tests")]
    state, docker = world(tmp_path / "busy", imgs, busy=[imgs[0]["tag"]])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 1
    assert [e["tag"] for e in journal(state)[-1]["images"]["errors"]] == [imgs[0]["tag"]]
    assert not any("-f" in c.split() for c in calls(tmp_path / "busy") if c.startswith("image rm"))


def test_the_prune_line_names_the_code_that_wrote_it_and_refuses_a_short_sha(tmp_path):
    state, docker = world(tmp_path, [image("a" * 16, 10, "backend-tests")])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--code-sha", "f" * 40]) == 0
    assert journal(state)[-1]["code_sha"] == "f" * 40
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--code-sha", "abc123"]) == 2


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


# ------------------------------------------------------------------ B6-2: run directories keep their verdict and lose their bulk
RUN_FILES = ("status.json", "hosted_compare.json", "merger.log", "state/plan.json", "state/journal.jsonl", "state/state.json",
             "receipts/ctx.a.junit.xml", "receipts/ctx.a.json", "logs/ctx.a.log", "logs/deps-backend-tests.log",
             "receipts/pysa/base/results/call-graph.json", "receipts/pysa/base/results/higher-order-call-graph.json",
             "receipts/pysa/base/results/taint-output.json", "receipts/pysa/candidate/results/call-graph.json")
SEVEN_DAY_KEEPS = {f for f in RUN_FILES if not f.startswith("logs/") and not f.endswith("call-graph.json")}


def run_dir(runs: Path, age_days: float) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(NOW - age_days * 24 * H))
    run = runs / f"pr1-{'a' * 12}-{'b' * 12}-{stamp}"
    for rel in RUN_FILES:
        (run / rel).parent.mkdir(parents=True, exist_ok=True)
        (run / rel).write_text(rel)
    return run


def files(run: Path) -> set:
    return {p.relative_to(run).as_posix() for p in run.rglob("*") if p.is_file() or p.is_symlink()}


def test_a_run_keeps_everything_for_seven_days_then_its_verdict_and_loses_logs_and_call_graphs(tmp_path):
    runs = tmp_path / "runs"
    young, week, month_less, month = (run_dir(runs, d) for d in (6.5, 7.5, 29.5, 30.5))
    out = pm.trim_runs(runs, NOW, dry=False)
    assert files(young) == set(RUN_FILES)
    assert files(week) == files(month_less) == SEVEN_DAY_KEEPS and not (week / "logs").exists()
    assert files(month) == {"status.json", "hosted_compare.json", "state/plan.json"} and not (month / "receipts").exists()
    assert (set(out["trimmed_7d"]), out["trimmed_30d"]) == ({week.name, month_less.name}, [month.name]) and out["freed_gb"] >= 0
    again = pm.trim_runs(runs, NOW, dry=False)   # a trimmed run is not trimmed twice
    assert again["trimmed_7d"] == [] and again["trimmed_30d"] == []


def test_a_dry_run_trims_nothing_a_run_without_a_dated_name_is_never_touched_and_a_link_goes_as_a_link(tmp_path):
    runs = tmp_path / "runs"
    week = run_dir(runs, 9)
    undated = runs / "hand-made"
    (undated / "logs").mkdir(parents=True)
    (undated / "logs" / "x.log").write_text("x")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    (week / "logs" / "linked").symlink_to(outside)
    out = pm.trim_runs(runs, NOW, dry=True)
    assert out["trimmed_7d"] == [week.name] and files(week) == set(RUN_FILES) | {"logs/linked"}
    pm.trim_runs(runs, NOW, dry=False)
    assert (undated / "logs" / "x.log").exists() and (outside / "keep.txt").read_text() == "keep" and not (week / "logs").exists()


def test_prune_journals_the_trim_and_never_touches_the_decisions_journal(tmp_path):
    state, docker = world(tmp_path, [image("a" * 16, 10, "backend-tests")])
    (state / "decisions.jsonl").write_text('{"kind": "decision", "ts": "2026-09-01T00:00:00Z"}\n')
    week = run_dir(state / "runs", 8)
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 0
    lines = journal(state)
    assert lines[0] == {"kind": "decision", "ts": "2026-09-01T00:00:00Z"} and lines[-1]["runs"]["trimmed_7d"] == [week.name]


def test_fstrim_runs_only_after_an_image_went_and_the_host_is_read_again_after_it(tmp_path):
    colima = tmp_path / "colima"
    colima.write_text(f'#!/bin/sh\necho "$*" >> {tmp_path / "colima.log"}\necho "/: 12 GiB (12884901888 bytes) trimmed"\n')
    colima.chmod(0o755)
    state, docker = world(tmp_path, [image("a" * 16, 10, "backend-tests")])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--fstrim", "--colima", str(colima)]) == 0
    assert not (tmp_path / "colima.log").exists() and "fstrim" not in journal(state)[-1]
    imgs = [image("b" * 16, 80, "backend-tests"), image("c" * 16, 10, "backend-tests")]
    state, docker = world(tmp_path / "w2", imgs)
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--dry-run", "--fstrim", "--colima", str(colima)]) == 0
    assert not (tmp_path / "colima.log").exists()
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--fstrim", "--colima", str(colima)]) == 0
    line = journal(state)[-1]
    assert (tmp_path / "colima.log").read_text() == "ssh -- sudo fstrim -av\n" and line["fstrim"]["rc"] == 0
    assert set(line["host_free_gb"]) == {"before", "after", "after_fstrim"}


# ------------------------------------------------------------------ council round 1 (2026-10-08): the findings it confirmed
def test_an_unreadable_plan_blocks_every_removal_and_a_half_written_one_still_names_its_images(tmp_path):
    imgs = [image("a" * 16, 80, "backend-tests"), image("b" * 16, 72, "backend-tests"), image("c" * 16, 10, "backend-tests")]
    state, docker = world(tmp_path, imgs, {"pr1-x-20261008T000000Z": (5, {"ctx.backend-tests": imgs[0]["tag"]}),
                                           "pr2-x-20261008T010000Z": (5, {"ctx.backend-tests": imgs[1]["tag"]})})
    half = state / "runs" / "pr1-x-20261008T000000Z" / "state" / "plan.json"
    half.write_text(half.read_text()[:-20])   # half-written: not JSON, still names the tag
    d = decided(state, docker)
    assert d[imgs[0]["tag"]]["remove"] is False and "named by a plan" in d[imgs[0]["tag"]]["rule"]
    locked = state / "runs" / "pr2-x-20261008T010000Z" / "state" / "plan.json"
    locked.chmod(0)
    try:
        assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 1
    finally:
        locked.chmod(0o644)
    line = journal(state)[-1]
    assert line["images"]["removed"] == [] and "images" in line["failed"]
    assert [e["plan"] for e in line["images"]["errors"]] == ["pr2-x-20261008T010000Z: PermissionError"]
    assert not [c for c in calls(tmp_path) if c.startswith("image rm")]


def test_images_built_in_the_same_second_are_ordered_by_their_nanoseconds_and_an_exact_tie_keeps_both(tmp_path):
    a, b = image("a" * 16, 80, "backend-tests"), image("b" * 16, 80, "backend-tests")
    a["created"], b["created"] = "2026-10-05T10:00:00.900000000Z", "2026-10-05T10:00:00.100000000Z"
    d = decided(*world(tmp_path, [a, b]))
    assert d[a["tag"]]["remove"] is False and d[b["tag"]]["remove"] is True
    b["created"] = a["created"]
    d = decided(*world(tmp_path / "tie", [a, b]))
    assert d[a["tag"]]["remove"] is False and d[b["tag"]]["remove"] is False


def test_a_linked_runs_directory_is_never_trimmed(tmp_path):
    outside = tmp_path / "archive"
    run = run_dir(outside, 40)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "runs").symlink_to(outside)
    out = pm.trim_runs(tmp_path / "state" / "runs", NOW, dry=False)
    assert out["refused"].endswith("is a symlink") and files(run) == set(RUN_FILES)


def test_a_failed_builder_prune_or_fstrim_is_a_failed_prune_and_the_lease_holder_is_never_pruned_beside(tmp_path):
    state, docker = world(tmp_path, [image("a" * 16, 80, "backend-tests"), image("b" * 16, 10, "backend-tests")])
    colima = tmp_path / "colima"
    colima.write_text("#!/bin/sh\nexit 1\n")
    colima.chmod(0o755)
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--fstrim", "--colima", str(colima)]) == 1
    assert journal(state)[-1]["failed"] == ["fstrim"] and journal(state)[-1]["fstrim"]["rc"] == 1
    fh, lease = mg.take_lease(state, "o/r")
    try:
        assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 0
    finally:
        mg.drop_lease(state, fh, lease)
    assert journal(state)[-1]["skipped"] == "lease" and not [c for c in calls(tmp_path) if c == "image ls --format {{.Repository}}:{{.Tag}}"][1:]


def test_an_unmeasurable_vm_is_none_never_a_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "_runner", lambda: (_ for _ in ()).throw(AttributeError("no runner.py")))
    assert pm.vm_free_gb("/nonexistent", tmp_path) is None
