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
    if a[-1] in world.get("busy", []):
        sys.exit(1)
    if "vm_avail_kb" in world:   # a removal frees the image's size inside the VM
        world["vm_avail_kb"] += next(i["size"] for i in world["images"] if i["tag"] == a[-1]) // 1024
        json.dump(world, open({world!r}, "w"))
elif a[:2] == ["system", "df"]:   # the build cache's size; a builder prune brings it to `cache_after` when the world says so
    print("Images|58.85GB\nContainers|1.2MB\nLocal Volumes|3.9GB\nBuild Cache|" + world.get("cache", "16.93GB"))
elif a[:2] == ["builder", "prune"] and world.get("builder_rcs"):   # one exit code per builder prune, in order
    rc = world["builder_rcs"].pop(0)
    json.dump(world, open({world!r}, "w"))
    sys.exit(rc)
elif a[:2] == ["builder", "prune"] and "cache_after" in world:
    world["cache"] = world["cache_after"]
    json.dump(world, open({world!r}, "w"))
    print("Total: 12.93GB")
elif a[:1] == ["run"] and "df" in a:
    if world.get("df_fails"):
        sys.exit(125)
    print(f"Filesystem 1024-blocks Used Available Capacity Mounted on\noverlay 61609772 30000000 {{world.get('vm_avail_kb', 31609772)}} 49% /")
'''


def iso(age_h: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.123456789Z", time.gmtime(NOW - age_h * H))


def image(tag16: str, age_h: float, recipe: str | None = None, gb: float = 9.85) -> dict:
    return {"tag": f"localci-deps:{tag16}", "id": "sha256:" + (tag16 * 4), "created": iso(age_h), "size": int(gb * 1e9),
            "labels": {"org.nuzantara.localci.deps": "d" * 64, **({"org.nuzantara.localci.recipe": recipe} if recipe else {})}}


def world(tmp_path: Path, images: list, plans: dict | None = None, in_progress: tuple = (), **extra) -> tuple[Path, str]:
    """A merger state dir whose runs hold `plans` ({run name: (age_h, {check: tag})}), finished (a status.json) unless named in
    `in_progress`, and a docker that knows `images`."""
    state = tmp_path / "state"
    (state / "runs").mkdir(parents=True)
    (state / "repo").write_text("o/r\n")
    for run, (age_h, uses) in (plans or {}).items():
        p = state / "runs" / run / "state" / "plan.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"checks": {chk: {"kind": "contained_jobs", "jobs": [{"job_id": "j", "deps": f"deps {tag} (3 pins + [])"}]}
                                            for chk, tag in uses.items()}}))
        os.utime(p, (NOW - age_h * H, NOW - age_h * H))
        if run not in in_progress:
            (state / "runs" / run / "status.json").write_text("{}")
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
    recent, ids, recipes, _, live, named = pm.plan_refs(state / "runs", NOW)
    return {d["tag"]: d for d in pm.image_decisions(pm.deps_images(docker), recent, ids, recipes, NOW, live, pm.stand_ins(pm.MATRIX), named)}


def test_the_second_image_a_plan_named_47_hours_ago_is_kept_and_one_unnamed_for_three_days_goes(tmp_path):
    imgs = [image("a" * 16, 80, "backend-tests"), image("c" * 16, 50, "backend-tests"), image("e" * 16, 72, "e2e-tests"),
            image("f" * 16, 10, "e2e-tests")]
    state, docker = world(tmp_path, imgs, {"pr1-x-20261006T120000Z": (47, {"ctx.backend-tests": imgs[0]["tag"]})})
    d = decided(state, docker)
    assert d[imgs[0]["tag"]]["remove"] is False and d[imgs[0]["tag"]]["rule"] == "slot 2 of 2 of recipe backend-tests: named by 1 plan(s) of the last 48 h, the youngest 47.0 h ago"
    assert d[imgs[1]["tag"]]["remove"] is False and d[imgs[1]["tag"]]["rule"] == "the newest image of recipe backend-tests"
    assert d[imgs[2]["tag"]]["remove"] is True and d[imgs[2]["tag"]]["rule"] == (
        f"not the newest of recipe e2e-tests (newest {imgs[3]['tag']}) and no plan of the last 48 h names it")


def test_a_third_image_of_a_recipe_goes_even_named_47_hours_ago(tmp_path):   # the cap wins
    imgs = [image("a" * 16, 100, "e2e-tests"), image("b" * 16, 50, "e2e-tests"), image("c" * 16, 2, "e2e-tests")]
    plans = {"pr1-x-20261006T120000Z": (47, {"ctx.e2e-tests": imgs[0]["tag"]}), "pr2-x-20261006T130000Z": (20, {"ctx.e2e-tests": imgs[1]["tag"]})}
    d = decided(*world(tmp_path, imgs, plans))
    assert d[imgs[0]["tag"]]["remove"] is True and d[imgs[0]["tag"]]["rule"] == (
        f"recipe e2e-tests already keeps 2 images (newest {imgs[2]['tag']}): beyond the cap, named by 1 plan(s), the youngest 47.0 h ago")
    assert d[imgs[1]["tag"]]["remove"] is False and d[imgs[2]["tag"]]["remove"] is False


def test_two_images_of_a_recipe_named_in_the_window_are_both_kept_and_the_run_in_progress_keeps_what_it_names(tmp_path):
    imgs = [image("a" * 16, 100, "backend-tests"), image("b" * 16, 30, "backend-tests")]
    d = decided(*world(tmp_path, imgs, {"pr1-x-20261008T000000Z": (30, {"ctx.backend-tests": imgs[0]["tag"]})}))
    assert d[imgs[0]["tag"]]["remove"] is False and d[imgs[1]["tag"]]["remove"] is False
    three = imgs + [image("c" * 16, 1, "backend-tests")]
    d = decided(*world(tmp_path / "live", three, {"pr1-x-20261008T000000Z": (30, {"ctx.backend-tests": imgs[0]["tag"]})},
                       in_progress=("pr1-x-20261008T000000Z",)))
    assert d[imgs[0]["tag"]]["remove"] is False and d[imgs[0]["tag"]]["rule"] == "named by the run in progress (no status.json yet)"


def test_a_plan_older_than_48_hours_names_nothing_and_the_recipe_comes_from_it_when_no_label_says(tmp_path):
    imgs = [image("a" * 16, 100), image("b" * 16, 60)]   # no recipe label: built before B6
    state, docker = world(tmp_path, imgs, {"pr1-x-20261005T000000Z": (49, {"ctx.e2e-tests": imgs[0]["tag"], "ctx.visa-oracle-smoke": imgs[0]["tag"]}),
                                           "pr2-x-20261006T000000Z": (60, {"ctx.e2e-tests": imgs[1]["tag"]})})
    d = decided(state, docker)
    assert d[imgs[0]["tag"]]["recipe"] == d[imgs[1]["tag"]]["recipe"] == "e2e-tests"
    assert d[imgs[0]["tag"]]["remove"] is True and d[imgs[1]["tag"]]["remove"] is False


def test_the_newest_of_a_recipe_is_kept_with_no_reference_and_a_young_second_one_unnamed_goes(tmp_path):
    imgs = [image("a" * 16, 200, "frontend-tests-mouth", 1.4), image("b" * 16, 30, "backend-tests"), image("c" * 16, 10, "backend-tests")]
    d = decided(*world(tmp_path, imgs))
    assert d[imgs[0]["tag"]]["remove"] is False and d[imgs[0]["tag"]]["rule"] == "the newest image of recipe frontend-tests-mouth"
    assert d[imgs[1]["tag"]]["remove"] is True   # the second image stays only while a plan of the last 48 h names it


def test_an_image_whose_recipe_nothing_records_is_its_own_newest_and_stays(tmp_path):
    d = decided(*world(tmp_path, [image("a" * 16, 300)]))
    assert d["localci-deps:" + "a" * 16]["remove"] is False and d["localci-deps:" + "a" * 16]["recipe"] == "unknown:localci-deps:" + "a" * 16


@pytest.mark.parametrize("tag", ["localci-candidate:1", "localci-deps-base:2c9b1d54104db6cd", "postgres:15"])
def test_the_candidate_and_base_images_are_never_in_a_removal_set(tmp_path, tag):
    assert pm.never(tag) is True
    im = {**image("a" * 16, 300, "backend-tests"), "tag": tag, "created": NOW - 300 * H, "label_recipe": "backend-tests"}
    young = {**image("b" * 16, 10, "backend-tests"), "created": NOW - 10 * H, "label_recipe": "backend-tests"}
    rows = pm.image_decisions([im, young], {}, {}, {}, NOW)
    assert rows[0]["remove"] is False and rows[0]["rule"].endswith("never pruned")
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
    assert line["images"]["removed"][0]["rule"] == f"not the newest of recipe backend-tests (newest {imgs[1]['tag']}) and no plan of the last 48 h names it"
    assert line["images"]["kept"] == [{"tag": imgs[1]["tag"], "rule": "the newest image of recipe backend-tests"}] and line["images"]["errors"] == []
    assert line["vm_free_gb"] == {"before": 32.4, "after": 32.4} and set(line["host_free_gb"]) == {"before", "after"}
    rm = [c for c in calls(tmp_path) if c.startswith(("image rm", "builder prune"))]
    assert rm == [f"image rm {imgs[0]['tag']}", "builder prune -af --keep-storage 4GB"]   # by explicit tag, never -a, never until= on images
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
    assert [c for c in calls(tmp_path) if c.startswith("builder")] == ["builder prune -af --keep-storage 4GB"]
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


def test_every_real_prune_ends_with_fstrim_even_with_no_removal_and_the_host_is_read_again_after_it(tmp_path):   # B7
    colima = tmp_path / "colima"
    colima.write_text(f'#!/bin/sh\necho "$*" >> {tmp_path / "colima.log"}\necho "/: 11.4 GiB (12240656384 bytes) trimmed"\n')
    colima.chmod(0o755)
    state, docker = world(tmp_path, [image("a" * 16, 10, "backend-tests")])   # nothing to remove
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--fstrim", "--colima", str(colima)]) == 0
    line = journal(state)[-1]
    assert line["images"]["removed"] == [] and (tmp_path / "colima.log").read_text() == "ssh -- sudo fstrim -av\n"
    assert line["fstrim"] == {"rc": 0, "tail": "/: 11.4 GiB (12240656384 bytes) trimmed"} and line["failed"] == []
    assert set(line["host_free_gb"]) == {"before", "after", "after_fstrim"}


def test_a_dry_run_and_a_lease_skipped_prune_never_trim(tmp_path):   # B7 innocence
    colima = tmp_path / "colima"
    colima.write_text(f'#!/bin/sh\necho "$*" >> {tmp_path / "colima.log"}\n')
    colima.chmod(0o755)
    state, docker = world(tmp_path, [image("a" * 16, 80, "backend-tests"), image("b" * 16, 10, "backend-tests")])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--dry-run", "--fstrim", "--colima", str(colima)]) == 0
    assert "fstrim" not in journal(state)[-1] and "after_fstrim" not in journal(state)[-1]["host_free_gb"]
    fh, lease = mg.take_lease(state, "o/r")
    try:
        assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--fstrim", "--colima", str(colima)]) == 0
    finally:
        mg.drop_lease(state, fh, lease)
    assert journal(state)[-1]["skipped"] == "lease" and not (tmp_path / "colima.log").exists()


def test_an_unreadable_plan_blocks_every_removal_and_a_half_written_one_still_names_its_images(tmp_path):
    imgs = [image("a" * 16, 80, "backend-tests"), image("b" * 16, 72, "backend-tests"), image("c" * 16, 10, "backend-tests")]
    state, docker = world(tmp_path, imgs, {"pr1-x-20261008T000000Z": (5, {"ctx.backend-tests": imgs[0]["tag"]}),
                                           "pr2-x-20261008T010000Z": (5, {"ctx.backend-tests": imgs[1]["tag"]})})
    half = state / "runs" / "pr1-x-20261008T000000Z" / "state" / "plan.json"
    half.write_text(half.read_text()[:-20])   # half-written: not JSON, still names the tag
    d = decided(state, docker)
    assert d[imgs[0]["tag"]]["remove"] is False and "named" in d[imgs[0]["tag"]]["rule"]
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


# ------------------------------------------------------------------ lead's addendum (2026-10-08): service stand-ins from the BASE matrix
STAND_INS = sorted(pm.stand_ins(pm.MATRIX))


def test_the_matrix_names_the_stand_ins_and_the_list_is_read_not_hardcoded(tmp_path):
    assert {"postgres:15", "redis:7"} <= set(STAND_INS)
    m = tmp_path / "m.yaml"
    m.write_text('contexts:\n  x:\n    local:\n      service_images:\n        "ghcr.io/x/mysql:8": "mysql:8"\n')
    assert pm.stand_ins(m) == {"mysql:8"} and pm.never("mysql:8", pm.stand_ins(m)) and not pm.protected("postgres:15", pm.stand_ins(m))


@pytest.mark.parametrize("stand_in", STAND_INS)
def test_every_service_stand_in_of_the_base_matrix_is_never_removed_and_is_journalled_kept(tmp_path, stand_in):
    imgs = [image("a" * 16, 80, "backend-tests"), image("b" * 16, 10, "backend-tests")]
    state, docker = world(tmp_path, imgs, others=[stand_in, "localci-candidate:1", "nginx:latest"])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 0
    assert [c for c in calls(tmp_path) if c.startswith("image rm")] == ["image rm " + imgs[0]["tag"]]
    kept = {k["tag"]: k["rule"] for k in journal(state)[-1]["images"]["kept"]}
    assert kept[stand_in] == "service stand-in of the BASE matrix: never pruned" and "nginx:latest" not in kept
    assert kept["localci-candidate:1"] == "never-list (the candidate or a base image): never pruned"


def test_an_unreadable_matrix_removes_nothing(tmp_path):
    state, docker = world(tmp_path, [image("a" * 16, 80, "backend-tests"), image("b" * 16, 10, "backend-tests")])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--matrix", str(tmp_path / "absent.yaml")]) == 1
    line = journal(state)[-1]
    assert line["images"]["removed"] == [] and line["images"]["errors"][0]["error"].startswith("unreadable (FileNotFoundError)")


def test_the_cap_counts_images_not_tags_an_image_with_two_tags_is_one(tmp_path):   # council round 3 (Codex)
    newest = image("c" * 16, 2, "backend-tests")
    twin = {**image("d" * 16, 2, "backend-tests"), "id": newest["id"], "created": newest["created"]}   # one image, two deps tags
    second = image("a" * 16, 60, "backend-tests")
    d = decided(*world(tmp_path, [newest, twin, second], {"pr1-x-20261006T120000Z": (47, {"ctx.backend-tests": second["tag"]})}))
    assert d[second["tag"]]["remove"] is False and d[second["tag"]]["rule"] == "slot 2 of 2 of recipe backend-tests: named by 1 plan(s) of the last 48 h, the youngest 47.0 h ago"


def test_an_unnamed_image_takes_no_slot_so_the_next_named_one_keeps_the_second(tmp_path):   # 13:03Z sample: 1 kept where 2 may
    imgs = [image("a" * 16, 100, "e2e-tests"), image("b" * 16, 72, "e2e-tests"), image("c" * 16, 2, "e2e-tests")]
    d = decided(*world(tmp_path, imgs, {"pr1-x-20261006T120000Z": (47, {"ctx.e2e-tests": imgs[0]["tag"]})}))
    assert d[imgs[1]["tag"]]["remove"] is True and d[imgs[0]["tag"]]["remove"] is False
    assert d[imgs[0]["tag"]]["rule"] == "slot 2 of 2 of recipe e2e-tests: named by 1 plan(s) of the last 48 h, the youngest 47.0 h ago"


def test_a_kept_image_keeps_all_its_tags_an_unnamed_twin_tag_is_not_untagged(tmp_path):
    newest, second = image("c" * 16, 2, "backend-tests"), image("a" * 16, 60, "backend-tests")
    twin = {**image("b" * 16, 60, "backend-tests"), "id": second["id"], "created": second["created"]}   # the second image's other tag
    d = decided(*world(tmp_path, [newest, second, twin], {"pr1-x-20261006T120000Z": (20, {"ctx.backend-tests": second["tag"]})}))
    assert d[twin["tag"]]["remove"] is False and d[twin["tag"]]["rule"] == "another tag of an image recipe backend-tests keeps"


@pytest.mark.parametrize("stand_in", STAND_INS)
def test_a_stand_in_no_plan_names_and_ten_days_old_is_kept_as_a_service_stand_in(tmp_path, stand_in):   # B6-1b, the lead's guilt
    old = {**image("e" * 16, 240), "tag": stand_in, "labels": None}   # docker lists it, built 10 days ago, named by no plan
    state, docker = world(tmp_path, [old, image("a" * 16, 300, "backend-tests"), image("b" * 16, 1, "backend-tests")])
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 0
    line = journal(state)[-1]
    assert {k["tag"]: k["rule"] for k in line["images"]["kept"]}[stand_in] == "service stand-in of the BASE matrix: never pruned"
    assert [r["tag"] for r in line["images"]["removed"]] == ["localci-deps:" + "a" * 16]
    assert f"image rm {stand_in}" not in calls(tmp_path)


# B8 (Pro, 2026-10-08T15:27Z: the VM's /var/lib/docker at 100 %, four 5.35 GB e2e images all named under 3 h ago, the one four
# armed PRs named about to lose slot 2 to a younger one PR named, the build cache 16.9 GB with 0.5 GB reclaimable by age).
def kb(gb: float) -> int:
    return int(gb * 1e9 / 1024)


def prune_line(state: Path, docker: str) -> dict:
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) in (0, 1)
    return journal(state)[-1]


def test_b8_a_third_image_named_under_an_hour_ago_goes_when_no_run_in_progress_names_it(tmp_path):   # no clock grace
    imgs = [image("a" * 16, 100, "e2e-tests"), image("b" * 16, 50, "e2e-tests"), image("c" * 16, 2, "e2e-tests")]
    plans = {"pr1-x-20261008T120000Z": (0.9, {"ctx.e2e-tests": imgs[0]["tag"]}), "pr2-x-20261008T130000Z": (0.5, {"ctx.e2e-tests": imgs[1]["tag"]}),
             "pr3-x-20261008T140000Z": (0.2, {"ctx.e2e-tests": imgs[2]["tag"]})}
    d = decided(*world(tmp_path, imgs, plans))
    assert d[imgs[0]["tag"]]["remove"] is True and d[imgs[0]["tag"]]["rule"] == (
        f"recipe e2e-tests already keeps 2 images (newest {imgs[2]['tag']}): beyond the cap, named by 1 plan(s), the youngest 0.9 h ago")
    assert [d[i["tag"]]["remove"] for i in imgs[1:]] == [False, False]
    assert not hasattr(pm, "IN_FLIGHT_GRACE_H")


def test_b8_the_run_in_progress_keeps_the_third_image_it_names(tmp_path):   # innocence: the lease, not a clock
    imgs = [image("a" * 16, 100, "e2e-tests"), image("b" * 16, 50, "e2e-tests"), image("c" * 16, 2, "e2e-tests")]
    plans = {"pr1-x-20261008T120000Z": (0.9, {"ctx.e2e-tests": imgs[0]["tag"]}), "pr2-x-20261008T130000Z": (0.5, {"ctx.e2e-tests": imgs[1]["tag"]})}
    d = decided(*world(tmp_path, imgs, plans, in_progress=("pr1-x-20261008T120000Z",)))
    assert d[imgs[0]["tag"]]["remove"] is False and d[imgs[0]["tag"]]["rule"] == "named by the run in progress (no status.json yet)"
    assert d[imgs[1]["tag"]]["remove"] is False and d[imgs[1]["tag"]]["slot"] == 2


def test_b8_slot_2_goes_to_the_image_three_plans_name_over_a_younger_one_a_single_plan_names(tmp_path):
    shared, lone, newest = image("a" * 16, 30, "e2e-tests"), image("b" * 16, 10, "e2e-tests"), image("c" * 16, 2, "e2e-tests")
    plans = {f"pr{n}-x-20261008T0{n}0000Z": (h, {"ctx.e2e-tests": shared["tag"]}) for n, h in ((1, 20), (2, 15), (3, 9))}
    plans["pr4-x-20261008T090000Z"] = (1, {"ctx.e2e-tests": lone["tag"], "ctx.e2e-a": lone["tag"], "ctx.e2e-b": lone["tag"]})   # 1 plan, 3 mentions
    d = decided(*world(tmp_path, [shared, lone, newest], plans))
    assert d[shared["tag"]]["remove"] is False and d[shared["tag"]]["rule"] == (
        "slot 2 of 2 of recipe e2e-tests: named by 3 plan(s) of the last 48 h, the youngest 9.0 h ago")
    assert d[lone["tag"]]["remove"] is True and "named by 1 plan(s), the youngest 1.0 h ago" in d[lone["tag"]]["rule"]


def test_b8_a_tie_in_plans_gives_slot_2_to_the_youngest_reference(tmp_path):
    old, young, newest = image("a" * 16, 30, "e2e-tests"), image("b" * 16, 40, "e2e-tests"), image("c" * 16, 2, "e2e-tests")
    plans = {"pr1-x-20261008T010000Z": (12, {"ctx.e2e-tests": old["tag"]}), "pr2-x-20261008T020000Z": (3, {"ctx.e2e-tests": young["tag"]})}
    d = decided(*world(tmp_path, [old, young, newest], plans))
    assert (d[young["tag"]]["slot"], d[old["tag"]]["remove"]) == (2, True)


def two_recipes_with_slot_2(tmp_path: Path, vm_gb: float, extra_images: list = (), **kw) -> tuple[Path, str, list]:
    imgs = [image("a" * 16, 50, "e2e-tests", gb=2.0), image("b" * 16, 1, "e2e-tests", gb=5.35),
            image("d" * 16, 30, "backend-tests", gb=2.0), image("e" * 16, 1, "backend-tests", gb=4.64)]
    plans = {"pr1-x-20261008T100000Z": (5, {"ctx.e2e-tests": imgs[0]["tag"], "ctx.backend-tests": imgs[2]["tag"]})}
    return (*world(tmp_path, imgs + list(extra_images), plans, vm_avail_kb=kb(vm_gb), **kw), imgs)


def three_recipes(tmp_path: Path, vm_gb: float, **kw) -> tuple[Path, str, dict]:
    """The 17:26Z shape (amended B8): three live recipes, each a newest image and a slot-2 one, references 1 to 4."""
    im = {"e_new": image("1" * 16, 1, "e2e-tests", gb=5.0), "e_old": image("2" * 16, 30, "e2e-tests", gb=5.0),
          "b_new": image("3" * 16, 2, "backend-tests", gb=4.0), "b_old": image("4" * 16, 20, "backend-tests", gb=4.0),
          "f_new": image("5" * 16, 3, "frontend-tests", gb=0.5), "f_old": image("6" * 16, 40, "frontend-tests", gb=0.5)}
    names = [("e_old", "b_new", "f_new"), ("e_old", "b_new", "f_new"), ("e_old", "b_old", "f_new"), ("e_old", None, "f_old"), ("e_new", None, "f_old")]
    plans = {f"pr{n}-x-20261008T1{n}0000Z": (n, {f"ctx.{c}": im[k]["tag"] for c, k in zip(("e2e-tests", "backend-tests", "frontend-tests"), row) if k})
             for n, row in enumerate(names, 1)}   # references: e_old 4, f_new 3, b_new 2, f_old 2, e_new 1, b_old 1
    return (*world(tmp_path, list(im.values()), plans, vm_avail_kb=kb(vm_gb), **kw), im)


def test_b8_under_the_vm_floor_the_fewest_references_go_first_even_the_newest_of_a_recipe(tmp_path):   # guilt (amended)
    state, docker, im = three_recipes(tmp_path, 5)
    line = prune_line(state, docker)
    assert [r["tag"] for r in line["images"]["removed"]] == [im[k]["tag"] for k in ("b_old", "e_new", "f_old", "b_new")]
    assert [r["rule"] for r in line["images"]["removed"][:2]] == [
        "vm floor: VM free 5 GB < 15 GB after the cap; 1 plan(s) of the last 48 h name it, built 20.0 h ago",
        "vm floor: VM free 9 GB < 15 GB after the cap; 1 plan(s) of the last 48 h name it, built 1.0 h ago"]   # e_new: the newest of e2e
    assert {k["tag"] for k in line["images"]["kept"]} == {im["e_old"]["tag"], im["f_new"]["tag"]}   # 4 and 3 references stay
    assert line["vm_floor"] == {"floor_gb": 15.0, "removed": 4, "met": True} and line["vm_free_gb"]["after"] == 18.5
    seq = [c for c in calls(tmp_path) if c.startswith(("image rm", "builder prune"))]
    assert seq == ["builder prune -af --keep-storage 4GB"] + [x for k in ("b_old", "e_new", "f_old", "b_new")
                                                              for x in (f"image rm {im[k]['tag']}", "builder prune -af --keep-storage 4GB")]
    assert line["builder_prune"]["runs"] == 5


@pytest.mark.parametrize("vm_gb, gone", [(14.5, 1), (15.0, 0), (15.5, 0)])   # under the floor one goes and it is met; at it, none
def test_b8_the_floor_stops_once_met_and_a_vm_at_the_floor_keeps_every_image(tmp_path, vm_gb, gone):
    state, docker, im = three_recipes(tmp_path, vm_gb)
    line = prune_line(state, docker)
    assert [r["tag"] for r in line["images"]["removed"]] == [im["b_old"]["tag"]][:gone] and line["vm_floor"]["met"] is True


@pytest.mark.parametrize("rcs, rc", [([0, 1], 1), ([1, 0], 0)])   # as ruled: rc and tail are the LAST call's, `runs` the count
def test_b8_the_line_carries_the_last_builder_prune_and_how_many_ran(tmp_path, rcs, rc):
    state, docker, im = three_recipes(tmp_path, 14.5, builder_rcs=rcs)
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == rc
    line = journal(state)[-1]
    assert line["builder_prune"]["runs"] == 2 and line["builder_prune"]["rc"] == rc and line["failed"] == (["builder_prune"] if rc else [])


def test_b8_equal_references_under_the_floor_evict_the_oldest_first_and_an_undated_image_last(tmp_path):   # the tie
    old, young = image("a" * 16, 30, "e2e-tests", gb=1.0), image("b" * 16, 3, "backend-tests", gb=1.0)
    undated = {**image("c" * 16, 1, "frontend-tests", gb=1.0), "created": "unknown"}   # unparseable: undated
    plans = {"pr1-x-20261008T100000Z": (2, {"ctx.e2e-tests": old["tag"], "ctx.backend-tests": young["tag"], "ctx.frontend-tests": undated["tag"]})}
    state, docker = world(tmp_path, [young, undated, old], plans, vm_avail_kb=kb(1))
    line = prune_line(state, docker)
    assert [r["tag"] for r in line["images"]["removed"]] == [old["tag"], young["tag"], undated["tag"]]
    assert line["images"]["removed"][2]["rule"].endswith("1 plan(s) of the last 48 h name it, undated")


def test_b8_a_refused_cap_removal_is_journalled_and_the_floor_still_acts_on_the_others(tmp_path):   # gate MEDIUM, 470fdba320
    imgs = [image("a" * 16, 100, "e2e-tests", gb=2.0), image("b" * 16, 50, "e2e-tests", gb=2.0), image("c" * 16, 1, "e2e-tests", gb=2.0)]
    plans = {"pr1-x-20261008T100000Z": (5, {"ctx.e2e-tests": imgs[1]["tag"]}), "pr2-x-20261008T110000Z": (4, {"ctx.e2e-tests": imgs[2]["tag"]})}
    state, docker = world(tmp_path, imgs, plans, vm_avail_kb=kb(1), busy=[imgs[0]["tag"]])   # a stopped container holds the cap's image
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker]) == 1
    line = journal(state)[-1]
    assert [e["tag"] for e in line["images"]["errors"]] == [imgs[0]["tag"]] and line["failed"] == ["images"]
    assert "skipped" not in line["vm_floor"] and line["vm_floor"]["removed"] == 2
    assert [r["tag"] for r in line["images"]["removed"]] == [imgs[1]["tag"], imgs[2]["tag"]]   # 1 plan each: the older first


def test_b8_an_image_named_by_tag_in_one_plan_and_by_id_in_another_counts_two_plans_and_one_plan_naming_both_counts_one(tmp_path):
    img, other, newest = image("a" * 16, 30, "e2e-tests"), image("b" * 16, 20, "e2e-tests"), image("c" * 16, 1, "e2e-tests")
    plans = {"pr1-x-20261008T010000Z": (12, {"ctx.e2e-tests": img["tag"]}), "pr2-x-20261008T020000Z": (10, {"ctx.e2e-tests": img["id"]}),
             "pr3-x-20261008T030000Z": (8, {"ctx.e2e-tests": other["tag"], "ctx.e2e-b": other["id"]}),
             "pr4-x-20261008T040000Z": (2, {"ctx.e2e-tests": newest["tag"]})}
    d = decided(*world(tmp_path, [img, other, newest], plans))
    assert (d[img["tag"]]["refs"], d[other["tag"]]["refs"]) == (2, 1)
    assert d[img["tag"]]["slot"] == 2 and d[other["tag"]]["remove"] is True   # two plans outrank one younger


def test_b8_above_the_floor_the_newest_of_a_recipe_is_never_removed_even_named_by_no_plan(tmp_path):   # innocence
    state, docker, imgs = two_recipes_with_slot_2(tmp_path, 20)
    line = prune_line(state, docker)
    assert line["images"]["removed"] == [] and line["vm_floor"] == {"floor_gb": 15.0, "removed": 0, "met": True}
    assert {k["rule"] for k in line["images"]["kept"] if k["tag"] in (imgs[1]["tag"], imgs[3]["tag"])} == {
        "the newest image of recipe e2e-tests", "the newest image of recipe backend-tests"}
    assert not [c for c in calls(tmp_path) if c.startswith("image rm")]


def test_b8_the_floor_never_touches_the_never_list_or_what_the_lease_run_names(tmp_path):   # innocence
    imgs = [image("a" * 16, 50, "e2e-tests", gb=1.0), image("b" * 16, 1, "e2e-tests", gb=1.0), image("c" * 16, 80, "e2e-tests", gb=1.0)]
    plans = {"pr1-x-20261008T100000Z": (2, {"ctx.e2e-tests": imgs[2]["tag"]})}
    state, docker = world(tmp_path, imgs, plans, in_progress=("pr1-x-20261008T100000Z",), vm_avail_kb=kb(1),
                          others=["localci-candidate:1", "localci-deps-base:1", *STAND_INS])
    line = prune_line(state, docker)
    assert [r["tag"] for r in line["images"]["removed"]] == [imgs[0]["tag"], imgs[1]["tag"]]   # by the cap, then the newest by the floor
    assert line["images"]["removed"][1]["rule"] == "vm floor: VM free 2 GB < 15 GB after the cap; 0 plan(s) of the last 48 h name it, built 1.0 h ago"   # the cap freed 1 GB first
    assert line["vm_floor"] == {"floor_gb": 15.0, "removed": 1, "met": False}
    assert [c for c in calls(tmp_path) if c.startswith("image rm")] == [f"image rm {imgs[0]['tag']}", f"image rm {imgs[1]['tag']}"]
    kept = {k["tag"]: k["rule"] for k in line["images"]["kept"]}
    assert kept[imgs[2]["tag"]] == "named by the run in progress (no status.json yet)" and set(STAND_INS) <= set(kept)
    assert {"localci-candidate:1", "localci-deps-base:1"} <= set(kept)


def test_b8_the_floor_is_skipped_unmeasured_dry_or_with_an_unreadable_input(tmp_path, monkeypatch):
    state, docker, _ = two_recipes_with_slot_2(tmp_path, 10, df_fails=True)
    line = prune_line(state, docker)
    assert line["vm_floor"]["skipped"] == "the VM's free space is unmeasured" and line["images"]["removed"] == []
    state, docker, _ = two_recipes_with_slot_2(tmp_path / "dry", 10)
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--dry-run"]) == 0
    assert journal(state)[-1]["vm_floor"]["skipped"] == "dry run" and journal(state)[-1]["images"]["would_remove"] == []
    state, docker, _ = two_recipes_with_slot_2(tmp_path / "blind", 10)
    assert mg.main(["prune", "--state-dir", str(state), "--docker", docker, "--matrix", str(tmp_path / "absent.yaml")]) == 1
    assert journal(state)[-1]["vm_floor"]["skipped"] == "an input is unreadable" and journal(state)[-1]["images"]["removed"] == []


def test_b8_the_floor_and_the_cache_budget_read_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALCI_VM_MIN_FREE_GB", "25")
    monkeypatch.setenv("LOCALCI_BUILDER_CACHE_GB", "6")
    state, docker, imgs = two_recipes_with_slot_2(tmp_path, 20)
    line = prune_line(state, docker)
    assert line["vm_floor"]["floor_gb"] == 25.0 and [r["tag"] for r in line["images"]["removed"]] == [imgs[1]["tag"]]   # 0 references first
    assert "builder prune -af --keep-storage 6GB" in calls(tmp_path) and line["builder_prune"]["keep_storage_gb"] == 6.0
    for bad in ("inf", "nan", "-3", "lots"):
        monkeypatch.setenv("LOCALCI_VM_MIN_FREE_GB", bad)
        assert pm._env_gb("LOCALCI_VM_MIN_FREE_GB", pm.VM_MIN_FREE_GB) == 15.0


def test_b8_the_build_cache_is_pruned_to_a_budget_not_by_age(tmp_path):
    state, docker = world(tmp_path, [image("a" * 16, 2, "e2e-tests")], cache="16.93GB", cache_after="4GB")
    line = prune_line(state, docker)
    assert "builder prune -af --keep-storage 4GB" in calls(tmp_path) and not [c for c in calls(tmp_path) if "until=" in c]
    assert line["builder_prune"] == {"rc": 0, "keep_storage_gb": 4, "cache_gb": {"before": 16.93, "after": 4.0}, "runs": 1,
                                     "tail": "Total: 12.93GB"}


@pytest.mark.parametrize("cache, gb", [("512MB", 0.51), ("1.3kB", 0.0), ("21.8GB", 21.8), ("0B", 0.0), ("n/a", None), ("12 parsecs", None)])
def test_b8_the_build_cache_size_is_read_from_system_df_and_an_unreadable_one_is_none(tmp_path, cache, gb):
    _, docker = world(tmp_path, [], cache=cache)
    assert pm.build_cache_gb(docker) == gb


# B8a (Pro, 2026-10-09T02:49:24Z: B8's first live floor removal journalled "built -5.3 h ago"): docker on Pro prints Created
# in local time with its offset, `2026-10-08T20:00:21.883530525+08:00`, and _ts dropped the offset.
@pytest.mark.parametrize("text, utc", [
    ("2026-10-08T20:00:21.883530525+08:00", "2026-10-08T12:00:21.883530525Z"),
    ("2026-10-08T06:30:00-05:30", "2026-10-08T12:00:00Z"),
    ("2026-10-08T20:00:21+0800", "2026-10-08T12:00:21Z"),
    ("2026-10-08T12:00:21.5", "2026-10-08T12:00:21.5Z"),   # no offset reads as UTC, as before
])
def test_b8a_created_is_read_as_a_utc_instant_whatever_its_offset(text, utc):
    assert pm._ts(text) == pm._ts(utc) and pm._ts(utc) is not None


@pytest.mark.parametrize("text", ["", "garbage", "2026-10-08T20:00:21+8", "2026-10-08T20:00:21+25:00", "2026-10-08T20:00:21+08:60",
                                  "2026-13-08T20:00:21Z", "2026-10-08T20:00:21Z trailing"])
def test_b8a_a_malformed_created_is_none(text):
    assert pm._ts(text) is None


def test_b8a_nanoseconds_still_order_two_builds_of_one_second():
    assert pm._ts("2026-10-08T20:00:21.900000000+08:00") - pm._ts("2026-10-08T20:00:21.100000000+08:00") == pytest.approx(0.8)


def local8(age_h: float) -> str:   # Pro's shape: local time, nanoseconds, +08:00
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(NOW - age_h * H + 8 * H)) + ".883530525+08:00"


def test_b8a_an_image_dated_in_utc_and_one_dated_in_local_time_are_ordered_by_their_instants(tmp_path):
    utc_new = image("a" * 16, 2, "e2e-tests")
    local_old = {**image("b" * 16, 5, "e2e-tests"), "created": local8(5)}   # dropping +08:00 made it read 3 h in the future
    d = decided(*world(tmp_path, [utc_new, local_old]))
    assert d[utc_new["tag"]]["rule"] == "the newest image of recipe e2e-tests" and d[local_old["tag"]]["remove"] is True


def test_b8a_a_floor_removal_of_images_dated_with_an_offset_journals_their_true_age(tmp_path):
    old = {**image("a" * 16, 20, "e2e-tests", gb=1.0), "created": local8(20)}
    new = {**image("b" * 16, 1, "e2e-tests", gb=1.0), "created": local8(1)}
    plans = {"pr1-x-20261008T100000Z": (2, {"ctx.e2e-tests": new["tag"]}), "pr2-x-20261008T110000Z": (3, {"ctx.e2e-tests": new["tag"]}),
             "pr3-x-20261008T120000Z": (4, {"ctx.e2e-tests": old["tag"]})}
    line = prune_line(*world(tmp_path, [old, new], plans, vm_avail_kb=kb(1)))
    assert [r["rule"] for r in line["images"]["removed"]] == [
        "vm floor: VM free 1 GB < 15 GB after the cap; 1 plan(s) of the last 48 h name it, built 20.0 h ago",
        "vm floor: VM free 2 GB < 15 GB after the cap; 2 plan(s) of the last 48 h name it, built 1.0 h ago"]
