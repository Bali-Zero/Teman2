"""B39: the start floor follows what the run will execute — 68 GB for a plan with a heavy context (or one that cannot be classified), 56 for the rest."""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from .test_merger import GIT_ENV, REPO, FakeGH, FakeGraphQL, FakeRunner, calls_of, commit, floor_world, g, heartbeat, mg, pr, wrap

ROOT = Path(__file__).resolve().parents[3]
REAL = {rel: (ROOT / rel).read_text() for rel in (mg.MATRIX, "scripts/ci/change_map.py", "scripts/ci/security_gate_flags.py",
                                                  ".github/workflows/security.yml", "scripts/ci/ring_gating_override.sh",
                                                  "scripts/localci/runner.py")}
HEAVY = {"E2E Tests (Playwright)", "Backend Tests (Python)", "CodeQL Analysis (python)", "CodeQL Analysis (javascript)",
         "Frontend Tests (Next.js) (mouth, true)", "Visa Oracle fullstack smoke"}
LIGHT = {"Every organ is born with its genes", "R1 gate — adversarial review present", "antidotes", "Harness floor recompute",
         "actionlint — workflow schema + expression gate", "Every guard proves guilt AND innocence", "Merah Putih DAY palette holds its contrast law",
         "catE-sovereignty-lint"}
DOCS, BACKEND = "docs/specs/note.md", "apps/backend-rag/backend/app/main.py"


@pytest.fixture(autouse=True)
def _default_gh(monkeypatch):
    gh = FakeGH()
    monkeypatch.setattr(mg.hc, "gh_get", gh)
    return gh


def mirror(tmp_path, files=None) -> tuple[Path, str]:
    src = tmp_path / "m"
    src.mkdir()
    g(src, "init", "-q", "-b", "main")
    return src, commit(src, {**REAL, **(files or {})}, "base")


def args(**kw):
    return SimpleNamespace(floor_explicit=None, **kw)


# ------------------------------------------------------------------ the classification
def test_every_context_of_the_matrix_is_classified_and_a_new_one_fails_until_it_is():
    contexts = yaml.safe_load(REAL[mg.MATRIX])["contexts"]
    by_deps = {c["name"] for c in contexts if (c.get("local") or {}).get("deps")}
    names = {c["name"] for c in contexts}
    assert names == HEAVY | LIGHT, f"unclassified context(s): {sorted(names - HEAVY - LIGHT)} — add each to HEAVY or LIGHT here, and give a heavy one `local.deps`"
    assert by_deps == HEAVY and not HEAVY & LIGHT


@pytest.mark.parametrize("paths,weight", [([DOCS], "light"), (["scripts/localci/merger.py"], "light"), (["evidence/2026-10/x/brief.yml"], "light"),
                                          ([BACKEND], "heavy"), (["package-lock.json"], "heavy"), (["apps/mouth/src/a.tsx"], "heavy"),
                                          ([DOCS, BACKEND], "heavy")])
def test_the_plan_is_heavy_when_the_trusted_classifiers_select_a_context_with_a_deps_image(tmp_path, paths, weight):
    repo, base = mirror(tmp_path)
    got, why = mg.plan_weight(repo, base, paths)
    assert got == weight, why


def test_the_heavy_set_is_named_by_the_matrix_structure_never_by_a_name(tmp_path):
    doc = yaml.safe_load(REAL[mg.MATRIX])
    for c in doc["contexts"]:   # rename the heavy contexts and give a light one a deps image: only `local.deps` counts
        if c["name"] == "Backend Tests (Python)":
            c["name"] = "Quiet job"
        if c["name"] == "antidotes":
            c["local"]["deps"] = {"node": "24"}
    repo, base = mirror(tmp_path, {mg.MATRIX: yaml.safe_dump(doc)})
    got, why = mg.plan_weight(repo, base, [BACKEND])
    assert got == "heavy" and "Quiet job" in why
    assert mg.plan_weight(repo, base, [DOCS])[0] == "heavy" and "antidotes" in mg.plan_weight(repo, base, [DOCS])[1]   # always selected: no runs_when


@pytest.mark.parametrize("files", [{mg.MATRIX: "not: [a matrix\n"}, {mg.MATRIX: "base matrix\n"}, {"scripts/ci/change_map.py": "raise SystemExit(3)\n"},
                                   {"scripts/ci/change_map.py": "print('not json')\n"}])
def test_a_plan_that_cannot_be_classified_is_heavy(tmp_path, files):
    repo, base = mirror(tmp_path, files)
    got, why = mg.plan_weight(repo, base, [DOCS])
    assert got == "heavy" and ("unclassifiable" in why or "change_map rc" in why)


def test_a_missing_classifier_file_is_heavy(tmp_path):
    src = tmp_path / "m"
    src.mkdir()
    g(src, "init", "-q", "-b", "main")
    base = commit(src, {mg.MATRIX: REAL[mg.MATRIX]}, "base without the classifiers")
    assert mg.plan_weight(src, base, [DOCS])[0] == "heavy"


def test_a_classifier_that_fails_open_selects_codeql(tmp_path):
    repo, base = mirror(tmp_path, {"scripts/ci/security_gate_flags.py": "raise SystemExit(1)\n"})
    got, why = mg.plan_weight(repo, base, [DOCS])
    assert got == "heavy" and "CodeQL" in why


def test_an_active_or_unreadable_ring_gating_override_makes_a_docs_plan_heavy(tmp_path, _default_gh):
    repo, base = mirror(tmp_path)
    _default_gh.variables = {"total_count": 1, "variables": [{"name": "MERGEOS_RING_GATING_DISABLED", "value": "true"}]}
    got, why = mg.plan_weight(repo, base, [DOCS])
    assert got == "heavy" and "CodeQL" in why
    _default_gh.variables = mg.hc.GhError("gh api failed")
    got, why = mg.plan_weight(repo, base, [DOCS])
    assert got == "heavy" and "CodeQL" in why
    _default_gh.variables = {"total_count": 0, "variables": []}
    base_bad = commit(repo, {".github/workflows/security.yml": "not: [yaml\n"}, "bad wf")
    assert mg.plan_weight(repo, base_bad, [DOCS])[0] == "heavy"


def test_a_failing_changed_callable_fails_closed_to_the_heavy_floor(tmp_path):
    repo, base = mirror(tmp_path)
    def broken():
        raise mg.MergerError("merge-tree failed")
    floor, kind, why = mg.start_floor(args(), repo, base, broken)
    assert (floor, kind) == (68.0, "heavy") and "unclassifiable: MergerError" in why


@pytest.mark.parametrize("free,explicit,floor,kind", [(0, None, 68.0, "heavy"), (0, 60.0, 60.0, "explicit")])
def test_the_floor_of_a_heavy_plan_is_68_and_an_explicit_floor_wins(tmp_path, free, explicit, floor, kind):
    repo, base = mirror(tmp_path)
    a = SimpleNamespace(floor_explicit=explicit)
    got = mg.start_floor(a, repo, base, lambda: [BACKEND])
    assert got[:2] == (floor, kind) and mg.HOST_FLOOR_GB + mg.START_MARGIN_HEAVY_GB == 68.0


def test_the_floor_of_a_light_plan_is_56_and_the_eviction_rule_is_unchanged(tmp_path):
    repo, base = mirror(tmp_path)
    assert mg.start_floor(SimpleNamespace(floor_explicit=None), repo, base, lambda: [DOCS])[:2] == (56.0, "light")
    assert (mg.HOST_FLOOR_GB, mg.EVICT_MARGIN_GB, mg.START_MARGIN_GB, mg.RUN_HEADROOM_GB) == (50.0, 1.5, 10.0, 15.0)   # Zero's floor, eviction and the prune's line stand
    assert mg.HostGuard(mg.HOST_FLOOR_GB, Path("/x"), measure=lambda: 51.49).breach()[0] and not mg.HostGuard(mg.HOST_FLOOR_GB, Path("/x"), measure=lambda: 51.5).breach()[0]


# ------------------------------------------------------------------ the tick
@pytest.fixture
def plan_world(tmp_path, monkeypatch):
    """main carries the real matrix and classifiers; #1 changes a doc (light), #2 a backend file (heavy)."""
    src = tmp_path / "src"
    src.mkdir()
    g(src, "init", "-q", "-b", "main")
    base0 = commit(src, {**REAL, "a.txt": "a\n"}, "base")
    g(src, "checkout", "-q", "-b", "light", base0)
    light = commit(src, {DOCS: "doc\n"}, "light")
    g(src, "checkout", "-q", "-b", "heavy", base0)
    heavy = commit(src, {BACKEND: "x = 1\n"}, "heavy")
    g(src, "checkout", "-q", "main")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(origin)], check=True, env=GIT_ENV)
    g(origin, "update-ref", "refs/pull/1/head", light)
    g(origin, "update-ref", "refs/pull/2/head", heavy)
    gh, runner = FakeGH(), FakeRunner()
    monkeypatch.setattr(mg.hc, "gh_get", gh)
    monkeypatch.setattr(mg, "gh_graphql", FakeGraphQL(gh))
    monkeypatch.setattr(mg, "runner_exec", runner)
    monkeypatch.delenv(mg.ARM_ENV, raising=False)
    monkeypatch.setattr(mg, "ready_refresh_due", lambda state, recs: False)
    w = SimpleNamespace(state=tmp_path / "state", origin=origin, src=src, gh=gh, runner=runner, light=light, heavy=heavy)
    w.tick = lambda *extra: mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(w.state), "--remote-url", str(origin), "--python", "py", *extra])
    w.journal = lambda: mg.read_journal(w.state)
    w.decisions = lambda: [r for r in w.journal() if r["kind"] == "decision"]
    return w


def test_a_light_plan_starts_at_56_and_journals_its_floor_and_nothing_to_skip(plan_world):
    plan_world.gh.prs = [pr(1, plan_world.light)]
    assert plan_world.tick("--host-free-gb", "56") == 0
    (d,) = plan_world.decisions()
    assert (d["start_floor_gb"], d["floor_kind"]) == (56.0, "light") and "select no context" in d["floor_why"]
    assert not [r for r in plan_world.journal() if r.get("why") == "host_below_floor"]


def test_under_56_nothing_starts_and_the_skip_says_it_is_the_light_floor(plan_world):
    plan_world.gh.prs = [pr(1, plan_world.light)]
    assert plan_world.tick("--host-free-gb", "55.9") == 0
    row = plan_world.journal()[-1]
    assert (row["why"], row["start_floor_gb"], row["floor_kind"], row["floor_gb"], row["floor_why"]) == (
        "host_below_floor", 56.0, "light", 50.0, "below lowest plan floor (light)") and not plan_world.decisions()


@pytest.mark.parametrize("free", [56, 60, 67.9])
def test_a_heavy_plan_is_not_started_under_68_and_the_journal_names_the_floor_and_why(plan_world, free):
    plan_world.gh.prs = [pr(2, plan_world.heavy)]
    assert plan_world.tick("--host-free-gb", str(free)) == 0
    row = plan_world.journal()[-1]
    assert (row["why"], row["start_floor_gb"], row["floor_kind"], row["free_gb"], row["pr"]) == ("host_below_floor", 68.0, "heavy", free, 2)
    assert "backend-tests".split("-")[0] in row["floor_why"].lower() and not plan_world.decisions() and not plan_world.runner.calls


def test_a_heavy_plan_starts_at_68_and_journals_its_floor(plan_world):
    plan_world.gh.prs = [pr(2, plan_world.heavy)]
    assert plan_world.tick("--host-free-gb", "68") == 0
    (d,) = plan_world.decisions()
    assert (d["start_floor_gb"], d["floor_kind"]) == (68.0, "heavy") and "Backend Tests (Python)" in d["floor_why"]


def test_pr_paths_diffs_the_squash_merge_tree_so_a_doc_change_already_on_main_takes_the_heavy_floor(plan_world):
    g(plan_world.src, "checkout", "-q", "main")
    commit(plan_world.src, {DOCS: "doc\n"}, "main already has the doc change")   # three-dot diff still sees DOCS; squash onto main is empty -> run_all
    g(plan_world.src, "push", "-q", str(plan_world.origin), "main")
    plan_world.gh.prs = [pr(1, plan_world.light)]
    assert plan_world.tick("--host-free-gb", "60") == 0
    row = plan_world.journal()[-1]
    assert (row["why"], row["start_floor_gb"], row["floor_kind"]) == ("host_below_floor", 68.0, "heavy") and not plan_world.decisions()


def test_a_light_pr_behind_a_heavy_one_runs_when_the_host_cannot_afford_the_heavy_one(plan_world):
    plan_world.gh.prs = [pr(2, plan_world.heavy, created="2026-10-01T00:00:00Z"), pr(1, plan_world.light, created="2026-10-02T00:00:00Z")]
    assert plan_world.tick("--host-free-gb", "60") == 0
    assert [d["pr"] for d in plan_world.decisions()] == [1]
    assert [r["pr"] for r in plan_world.journal() if r.get("why") == "host_below_floor"] == [2]


def test_a_plan_the_tick_cannot_classify_takes_the_heavy_floor(plan_world, monkeypatch):
    def unreadable(self):
        raise mg.MergerError("the BASE matrix cannot be read")
    monkeypatch.setattr(mg.StaleJudge, "contexts", unreadable)
    plan_world.gh.prs = [pr(1, plan_world.light)]
    assert plan_world.tick("--host-free-gb", "60") == 0
    row = plan_world.journal()[-1]
    assert (row["floor_kind"], row["start_floor_gb"]) == ("heavy", 68.0) and "unclassifiable" in row["floor_why"] and not plan_world.decisions()


def test_a_replay_is_held_to_the_floor_of_its_plan_too(plan_world, monkeypatch):
    plan_world.gh.prs = [pr(1, plan_world.light)]
    base = g(plan_world.origin, "rev-parse", "main")
    monkeypatch.setattr(mg, "replay_pending", lambda a, state, repo_dir, recs: {"pr": 9, "head": plan_world.light, "base_sha": base, "merge_commit": base})
    monkeypatch.setattr(mg, "plan_weight", lambda repo, b, changed: ("heavy", "stood in"))
    assert plan_world.tick("--host-free-gb", "60") == 0
    row = plan_world.journal()[-1]
    assert (row["why"], row["pr"], row["start_floor_gb"], row["floor_kind"]) == ("host_below_floor", 9, 68.0, "heavy") and not plan_world.decisions()


def test_an_explicit_floor_wins_for_every_plan(plan_world):
    plan_world.gh.prs = [pr(2, plan_world.heavy)]
    assert plan_world.tick("--host-free-gb", "59.9", "--min-host-free-gb", "60") == 0
    row = plan_world.journal()[-1]
    assert (row["why"], row["start_floor_gb"], row["floor_kind"]) == ("host_below_floor", 60.0, "explicit") and not plan_world.decisions()
    assert plan_world.tick("--host-free-gb", "60", "--min-host-free-gb", "60") == 0 and len(plan_world.decisions()) == 1   # a heavy plan, below 68, by the operator's word


def test_the_kill_switch_gives_every_plan_the_one_legacy_floor_of_60(plan_world):
    plan_world.gh.prs = [pr(2, plan_world.heavy)]
    assert plan_world.tick("--no-floor-by-plan", "--host-free-gb", "59.9") == 0
    row = plan_world.journal()[-1]
    assert (row["start_floor_gb"], row["floor_kind"]) == (60.0, "explicit") and not plan_world.decisions()
    assert plan_world.tick("--no-floor-by-plan", "--host-free-gb", "60") == 0 and len(plan_world.decisions()) == 1


def test_an_explicit_floor_given_by_abbreviation_still_wins(plan_world):
    plan_world.gh.prs = [pr(1, plan_world.light)]
    assert plan_world.tick("--host-free-gb", "59", "--min-host-free", "59.5") == 0
    assert plan_world.journal()[-1]["floor_kind"] == "explicit" and not plan_world.decisions()


def test_a_run_below_a_light_floor_is_still_evicted_under_zeros_floor_plus_one_and_a_half(plan_world):
    plan_world.gh.prs = [pr(1, plan_world.light)]
    assert plan_world.tick("--host-free-gb", "56") == 0
    guards = {c["guard"] for c in plan_world.runner.calls if c["sub"] != "status"}
    assert all(gd is not None and gd.floor_gb == 50.0 and gd.evict_gb == 51.5 for gd in guards)


def test_with_no_host_reading_no_floor_applies_as_before(plan_world):
    plan_world.gh.prs = [pr(2, plan_world.heavy)]
    assert plan_world.tick() == 0 and len(plan_world.decisions()) == 1


# ------------------------------------------------------------------ the wrapper
def test_the_wrapper_passes_no_floor_unless_the_operator_set_one(tmp_path):
    env = floor_world(tmp_path, 200)
    assert wrap(env).returncode == 0
    first = (tmp_path / "calls").read_text().splitlines()[0]
    assert "--host-free-gb=200" in first and "--min-host-free-gb" not in first
    (tmp_path / "calls").unlink()
    assert wrap({**env, "MERGER_MIN_HOST_FREE_GB": "64"}).returncode == 0
    assert (tmp_path / "calls").read_text().splitlines()[0].endswith("--host-free-gb=200 --min-host-free-gb=64")


def test_between_56_and_60_the_organ_says_warning_and_names_the_plan_rule(tmp_path):
    env = floor_world(tmp_path, 57)
    assert wrap(env).returncode == 0 and calls_of(tmp_path) == ["tick", "prune"]
    note = heartbeat(tmp_path)["note"]
    assert heartbeat(tmp_path)["status"] == "warning" and "heavy runs wait" in note and "from 56" in note


REAL_GH_GET = mg.hc.gh_get


def test_a_historical_base_runner_without_classifier_off_deps_skip_takes_the_heavy_floor(plan_world, monkeypatch):
    legacy_runner = REAL["scripts/localci/runner.py"].replace("skipped at plan (classifier flags all false)", "legacy-always-plans-deps")
    assert legacy_runner != REAL["scripts/localci/runner.py"]
    g(plan_world.src, "checkout", "-q", "-b", "legacy-base", "main")
    base_old = commit(plan_world.src, {"scripts/localci/runner.py": legacy_runner}, "pre-b39 base")
    merge_old = commit(plan_world.src, {DOCS: "historical replay doc\n"}, "merge doc (#9)")
    g(plan_world.src, "push", "-q", str(plan_world.origin), "legacy-base")
    g(plan_world.src, "checkout", "-q", "main")
    got, why = mg.plan_weight(plan_world.src, base_old, [DOCS])
    assert got == "heavy" and "CodeQL" in why
    monkeypatch.setattr(mg, "replay_pending", lambda a, state, repo_dir, recs: {"pr": 9, "head": merge_old, "base_sha": base_old, "merge_commit": merge_old})
    plan_world.gh.prs = [pr(1, plan_world.light)]
    assert plan_world.tick("--host-free-gb", "60") == 0
    row = plan_world.journal()[-1]
    assert (row["why"], row["pr"], row["start_floor_gb"], row["floor_kind"]) == ("host_below_floor", 9, 68.0, "heavy") and "CodeQL" in row["floor_why"]


def test_preflight_and_runner_read_ring_gating_override_with_the_same_stripped_environment(tmp_path, monkeypatch):
    repo, base = mirror(tmp_path)
    monkeypatch.setattr(mg.hc, "gh_get", REAL_GH_GET)
    monkeypatch.setenv("GH_CONFIG_DIR", str(tmp_path / "custom-gh"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "custom-xdg"))
    gate_envs: list[dict] = []
    monkeypatch.setattr(mg, "runner_exec", lambda argv, cwd, env, timeout, **kw: (gate_envs.append(dict(env)), subprocess.CompletedProcess(argv, 1, "", ""))[1])
    mg.run_gate(args(python="python3", host_floor_gb=0, plan_timeout=60, run_timeout=60), tmp_path, tmp_path, tmp_path / "run", base, base, 1)
    assert gate_envs and "GH_CONFIG_DIR" not in gate_envs[0] and "XDG_CONFIG_HOME" not in gate_envs[0]
    rn = mg.StaleJudge(repo, base)._runner()
    real_run = subprocess.run
    seen_envs: list[dict] = []

    def transport(argv, *a, **kw):
        if isinstance(argv, list) and argv[:2] == ["gh", "api"]:
            env = kw.get("env")
            seen_envs.append({} if env is None else dict(env))
            if env is None or "GH_CONFIG_DIR" in env or "XDG_CONFIG_HOME" in env:
                body = '{"owner":{"type":"User"}}' if argv[2].count("/") == 2 else '{"total_count":0,"variables":[]}'
                return subprocess.CompletedProcess(argv, 0, body, "")
            return subprocess.CompletedProcess(argv, 1, "", "default gh config cannot read")
        return real_run(argv, *a, **kw)

    monkeypatch.setattr(subprocess, "run", transport)
    monkeypatch.setattr(rn, "trusted_env", lambda base_env=None, _te=rn.trusted_env: _te(gate_envs[0] if base_env is None else base_env))
    assert rn.ring_gating_override(repo, base, tmp_path, REPO, {}, get=mg.hc.gh_get) == {"read": "error", "active": True}
    got, why = mg.plan_weight(repo, base, [DOCS])
    assert got == "heavy" and "CodeQL" in why
    assert seen_envs and all("GH_CONFIG_DIR" not in e and "XDG_CONFIG_HOME" not in e for e in seen_envs)


@pytest.mark.parametrize("exc_cls", [mg.Stopped, mg.TickTimeout])
def test_stopped_and_tick_timeout_propagate_through_start_floor_and_plan_weight(tmp_path, exc_cls):
    repo, base = mirror(tmp_path)

    def interrupted():
        raise exc_cls("signal")

    with pytest.raises(exc_cls):
        mg.start_floor(args(), repo, base, interrupted)
    try:
        mg._WATCHDOG["fired"] = True
        with pytest.raises(mg.TickTimeout):
            mg.start_floor(args(), repo, base, lambda: [DOCS])
    finally:
        mg._WATCHDOG["fired"] = False
